"""FastAPI backend — SCHEMA.md의 엔드포인트를 구현한다.

서버에서:
    uvicorn main:app --host 0.0.0.0 --port 8000
    cloudflared tunnel --url http://localhost:8000
"""
from __future__ import annotations

import asyncio
import shutil
import uuid
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

import db
import model_registry
import templates_io
from schemas import (
    AnalyzeRequest,
    Device,
    EditRequest,
    FewshotPair,
    FieldResult,
    FieldSpec,
    ImageInfo,
    ImageStatus,
    ImageSummary,
    Job,
    JobStatus,
    Sheet,
    SheetColumn,
    SheetRow,
)

app = FastAPI(title="project_gamma backend")

# 로컬 frontend(개발 서버) ↔ cloudflared 공개 URL의 backend 사이 CORS 허용.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_running_tasks: dict[str, asyncio.Task] = {}
_stop_flags: dict[str, bool] = {}


@app.on_event("startup")
def _startup() -> None:
    db.init()


# ---------- 환경 조회 ----------

@app.get("/models")
def list_models() -> dict:
    return {"models": model_registry.available_models()}


@app.get("/devices")
def list_devices() -> dict:
    return {"devices": [d.value for d in Device]}


@app.get("/templates")
def list_templates() -> dict:
    return {"templates": [t.model_dump() for t in templates_io.list_templates()]}


# ---------- 업로드 ----------

@app.post("/upload")
async def upload(files: list[UploadFile] = File(...)) -> dict:
    if not files:
        raise HTTPException(400, detail={"error": "no_files", "message": "files[] required"})
    saved: list[ImageInfo] = []
    with db.connect() as cx:
        for f in files:
            image_id = f"img_{uuid.uuid4().hex[:10]}"
            suffix = Path(f.filename or "").suffix
            dst = db.UPLOAD_DIR / f"{image_id}{suffix}"
            with dst.open("wb") as out:
                shutil.copyfileobj(f.file, out)
            cx.execute(
                "INSERT INTO images(image_id, filename, path, status) VALUES (?,?,?,?)",
                (image_id, f.filename or dst.name, str(dst), ImageStatus.blank.value),
            )
            saved.append(ImageInfo(image_id=image_id, filename=f.filename or dst.name, status=ImageStatus.blank))
    return {"images": [s.model_dump() for s in saved]}


@app.get("/images/{image_id}/file")
def image_file(image_id: str):
    with db.connect() as cx:
        row = cx.execute("SELECT path FROM images WHERE image_id=?", (image_id,)).fetchone()
    if not row:
        raise HTTPException(404, detail={"error": "image_not_found", "message": image_id})
    return FileResponse(row["path"])


# ---------- 분석 ----------

@app.post("/analyze")
async def analyze(req: AnalyzeRequest) -> dict:
    if req.model not in model_registry.available_models():
        raise HTTPException(400, detail={"error": "unknown_model", "message": req.model})
    template = templates_io.load_template(req.template_name)
    if template is None:
        raise HTTPException(400, detail={"error": "unknown_template", "message": req.template_name})
    job_id = f"job_{uuid.uuid4().hex[:10]}"
    with db.connect() as cx:
        cx.execute(
            "INSERT INTO jobs(job_id, model, device, status, field_spec) VALUES (?,?,?,?,?)",
            (job_id, req.model, req.device.value, JobStatus.running.value, db.dump_field_spec(template.field_spec)),
        )
        for ord_, image_id in enumerate(req.image_ids):
            cx.execute(
                "INSERT INTO job_images(job_id, image_id, ord) VALUES (?,?,?)",
                (job_id, image_id, ord_),
            )

    _stop_flags[job_id] = False
    _running_tasks[job_id] = asyncio.create_task(
        _run_job(job_id, req.model, req.image_ids, template.field_spec, template.fewshot)
    )
    return {"job_id": job_id}


async def _run_job(
    job_id: str,
    model: str,
    image_ids: list[str],
    field_spec: list[FieldSpec],
    fewshot: list[FewshotPair],
) -> None:
    loop = asyncio.get_running_loop()
    fewshot_dicts = [f.model_dump() for f in fewshot]
    try:
        for image_id in image_ids:
            if _stop_flags.get(job_id):
                break
            _set_image_status(image_id, ImageStatus.working)
            with db.connect() as cx:
                row = cx.execute("SELECT path FROM images WHERE image_id=?", (image_id,)).fetchone()
            if not row:
                continue
            results: list[FieldResult] = await loop.run_in_executor(
                None, model_registry.predict, model, Path(row["path"]), field_spec, fewshot_dicts
            )
            if _stop_flags.get(job_id):
                _set_image_status(image_id, ImageStatus.blank)
                break
            _save_results(job_id, image_id, results)
            # working 상태 유지 — 사용자가 Complete 누르면 done으로 전환
        with db.connect() as cx:
            stopped = bool(_stop_flags.get(job_id))
            final = JobStatus.stopped.value if stopped else JobStatus.completed.value
            cx.execute("UPDATE jobs SET status=? WHERE job_id=?", (final, job_id))
            if stopped:
                # 사용자가 Complete 하지 않은 이미지의 결과는 모두 폐기한다.
                # Stop = 진행 중이던 작업의 추론 결과는 신뢰하지 않는다는 의미.
                cx.execute(
                    """DELETE FROM field_results
                       WHERE job_id = ? AND image_id IN (
                         SELECT ji.image_id FROM job_images ji
                         JOIN images i ON ji.image_id = i.image_id
                         WHERE ji.job_id = ? AND i.status != ?
                       )""",
                    (job_id, job_id, ImageStatus.done.value),
                )
                cx.execute(
                    """UPDATE images SET status = ?
                       WHERE image_id IN (
                         SELECT ji.image_id FROM job_images WHERE job_id = ?
                       ) AND status != ?""",
                    (ImageStatus.blank.value, job_id, ImageStatus.done.value),
                )
    finally:
        _running_tasks.pop(job_id, None)
        _stop_flags.pop(job_id, None)


def _set_image_status(image_id: str, status: ImageStatus) -> None:
    with db.connect() as cx:
        cx.execute("UPDATE images SET status=? WHERE image_id=?", (status.value, image_id))


def _save_results(job_id: str, image_id: str, results: list[FieldResult]) -> None:
    with db.connect() as cx:
        for r in results:
            cx.execute(
                """INSERT INTO field_results(job_id, image_id, key, predicted, accuracy, edited)
                   VALUES (?,?,?,?,?,?)
                   ON CONFLICT(job_id, image_id, key) DO UPDATE SET
                     predicted=excluded.predicted, accuracy=excluded.accuracy""",
                (job_id, image_id, r.key, r.predicted, r.accuracy, r.edited),
            )


@app.post("/jobs/{job_id}/stop")
async def stop_job(job_id: str) -> dict:
    if job_id not in _running_tasks:
        # 이미 끝났거나 없는 job
        with db.connect() as cx:
            row = cx.execute("SELECT status FROM jobs WHERE job_id=?", (job_id,)).fetchone()
        if not row:
            raise HTTPException(404, detail={"error": "job_not_found", "message": job_id})
        return {"status": row["status"]}
    _stop_flags[job_id] = True
    return {"status": JobStatus.stopped.value}


# ---------- 조회 ----------

@app.get("/jobs/{job_id}")
def get_job(job_id: str) -> Job:
    with db.connect() as cx:
        j = cx.execute("SELECT * FROM jobs WHERE job_id=?", (job_id,)).fetchone()
        if not j:
            raise HTTPException(404, detail={"error": "job_not_found", "message": job_id})
        rows = cx.execute(
            """SELECT i.image_id, i.filename, i.status
                 FROM job_images ji JOIN images i ON ji.image_id = i.image_id
                WHERE ji.job_id=? ORDER BY ji.ord""",
            (job_id,),
        ).fetchall()
    images = [ImageInfo(image_id=r["image_id"], filename=r["filename"], status=ImageStatus(r["status"])) for r in rows]
    spec = [FieldSpec(**s) for s in db.load_field_spec(j["field_spec"])]
    return Job(
        job_id=j["job_id"],
        model=j["model"],
        device=Device(j["device"]),
        status=JobStatus(j["status"]),
        field_spec=spec,
        images=images,
    )


@app.get("/jobs/{job_id}/images/{image_id}")
def get_image_summary(job_id: str, image_id: str) -> ImageSummary:
    with db.connect() as cx:
        img = cx.execute("SELECT status FROM images WHERE image_id=?", (image_id,)).fetchone()
        if not img:
            raise HTTPException(404, detail={"error": "image_not_found", "message": image_id})
        fields = cx.execute(
            "SELECT key, predicted, accuracy, edited FROM field_results WHERE job_id=? AND image_id=?",
            (job_id, image_id),
        ).fetchall()
    return ImageSummary(
        image_id=image_id,
        status=ImageStatus(img["status"]),
        fields=[FieldResult(**dict(f)) for f in fields],
    )


# ---------- 수정 / 완료 ----------

@app.put("/jobs/{job_id}/images/{image_id}")
def edit_image(job_id: str, image_id: str, body: EditRequest) -> ImageSummary:
    with db.connect() as cx:
        for r in body.fields:
            cx.execute(
                """INSERT INTO field_results(job_id, image_id, key, predicted, accuracy, edited)
                   VALUES (?,?,?,?,?,?)
                   ON CONFLICT(job_id, image_id, key) DO UPDATE SET edited=excluded.edited""",
                (job_id, image_id, r.key, r.predicted, r.accuracy, r.edited),
            )
    return get_image_summary(job_id, image_id)


@app.post("/jobs/{job_id}/images/{image_id}/complete")
def complete_image(job_id: str, image_id: str) -> ImageSummary:
    _set_image_status(image_id, ImageStatus.done)
    return get_image_summary(job_id, image_id)


# ---------- 시트 ----------

@app.get("/jobs/{job_id}/sheet")
def get_sheet(job_id: str) -> Sheet:
    with db.connect() as cx:
        j = cx.execute("SELECT field_spec FROM jobs WHERE job_id=?", (job_id,)).fetchone()
        if not j:
            raise HTTPException(404, detail={"error": "job_not_found", "message": job_id})
        spec = db.load_field_spec(j["field_spec"])
        img_rows = cx.execute(
            """SELECT i.image_id, i.status
                 FROM job_images ji JOIN images i ON ji.image_id = i.image_id
                WHERE ji.job_id=? ORDER BY ji.ord""",
            (job_id,),
        ).fetchall()
        field_rows = cx.execute(
            "SELECT image_id, key, predicted, edited FROM field_results WHERE job_id=?",
            (job_id,),
        ).fetchall()
    by_image: dict[str, dict[str, str | None]] = {}
    for r in field_rows:
        by_image.setdefault(r["image_id"], {})[r["key"]] = r["edited"] if r["edited"] is not None else r["predicted"]
    rows: list[SheetRow] = []
    for ir in img_rows:
        if ir["status"] != ImageStatus.done.value:
            continue
        values = {s["key"]: by_image.get(ir["image_id"], {}).get(s["key"]) for s in spec}
        rows.append(SheetRow(image_id=ir["image_id"], values=values))
    columns = [SheetColumn(key=s["key"], label=s["label"]) for s in spec]
    return Sheet(columns=columns, rows=rows)


# ---------- 에러 포맷 통일 ----------

@app.exception_handler(HTTPException)
async def _http_exc(_, exc: HTTPException):  # noqa: ANN001
    detail = exc.detail if isinstance(exc.detail, dict) else {"error": "http_error", "message": str(exc.detail)}
    return JSONResponse(status_code=exc.status_code, content=detail)
