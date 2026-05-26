"""FastAPI backend — SCHEMA.md의 엔드포인트를 구현한다.

서버에서:
    uvicorn main:app --host 0.0.0.0 --port 8000
    cloudflared tunnel --url http://localhost:8000

한 신청서(application)는 1장(이미지) 또는 N장(PDF 페이지 분할)의 이미지로 구성된다.
모델 추론과 사용자 작업의 단위는 모두 application 이며, image 는 그 application 의 페이지일 뿐이다.
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
    ApplicationInfo,
    ApplicationSummary,
    Device,
    EditRequest,
    FewshotPair,
    FieldResult,
    FieldSpec,
    ImageStatus,
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

def _split_pdf_to_pngs(pdf_path: Path, dst_dir: Path) -> list[Path]:
    """PDF 의 각 페이지를 PNG 로 저장하고 결과 경로 리스트를 반환한다.

    scale=2.0 — 기본 72 DPI 의 2배(=144 DPI) 로 렌더. 손글씨 인식에 충분하면서
    파일 크기·VRAM 부담이 과하지 않은 절충점.
    """
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(str(pdf_path))
    pages: list[Path] = []
    try:
        for i in range(len(pdf)):
            page = pdf[i]
            try:
                bitmap = page.render(scale=2.0)
                pil = bitmap.to_pil()
                dst = dst_dir / f"{i}.png"
                pil.save(dst, "PNG")
                pages.append(dst)
            finally:
                page.close()
    finally:
        pdf.close()
    return pages


@app.post("/upload")
async def upload(files: list[UploadFile] = File(...)) -> dict:
    if not files:
        raise HTTPException(400, detail={"error": "no_files", "message": "files[] required"})
    saved: list[ApplicationInfo] = []
    with db.connect() as cx:
        for f in files:
            application_id = f"app_{uuid.uuid4().hex[:10]}"
            filename = f.filename or application_id
            suffix = Path(filename).suffix.lower()
            app_dir = db.UPLOAD_DIR / application_id
            app_dir.mkdir(parents=True, exist_ok=True)

            if suffix == ".pdf":
                # PDF: 원본을 임시 저장 후 페이지별 PNG 로 분할. 분할 후 원본 PDF 는 제거한다
                # (페이지 PNG 만 있으면 모델·미리보기 모두 충분).
                tmp_pdf = app_dir / "source.pdf"
                with tmp_pdf.open("wb") as out:
                    shutil.copyfileobj(f.file, out)
                try:
                    pages = _split_pdf_to_pngs(tmp_pdf, app_dir)
                finally:
                    tmp_pdf.unlink(missing_ok=True)
                if not pages:
                    raise HTTPException(400, detail={
                        "error": "empty_pdf", "message": f"{filename} has no pages"
                    })
            else:
                # 단일 이미지: 그대로 한 장짜리 신청서. 확장자 유지.
                dst = app_dir / f"0{suffix or '.bin'}"
                with dst.open("wb") as out:
                    shutil.copyfileobj(f.file, out)
                pages = [dst]

            page_count = len(pages)
            cx.execute(
                "INSERT INTO applications(application_id, filename, status, page_count) VALUES (?,?,?,?)",
                (application_id, filename, ImageStatus.blank.value, page_count),
            )
            for ord_, p in enumerate(pages):
                cx.execute(
                    "INSERT INTO application_pages(application_id, ord, path) VALUES (?,?,?)",
                    (application_id, ord_, str(p)),
                )
            saved.append(ApplicationInfo(
                application_id=application_id,
                filename=filename,
                status=ImageStatus.blank,
                page_count=page_count,
            ))
    return {"applications": [s.model_dump() for s in saved]}


@app.get("/applications/{application_id}/pages/{ord}/file")
def page_file(application_id: str, ord: int):
    with db.connect() as cx:
        row = cx.execute(
            "SELECT path FROM application_pages WHERE application_id=? AND ord=?",
            (application_id, ord),
        ).fetchone()
    if not row:
        raise HTTPException(404, detail={
            "error": "page_not_found", "message": f"{application_id}/{ord}"
        })
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
        for ord_, application_id in enumerate(req.application_ids):
            cx.execute(
                "INSERT INTO job_applications(job_id, application_id, ord) VALUES (?,?,?)",
                (job_id, application_id, ord_),
            )

    _stop_flags[job_id] = False
    _running_tasks[job_id] = asyncio.create_task(
        _run_job(job_id, req.model, req.application_ids, template.field_spec, template.fewshot)
    )
    return {"job_id": job_id}


def _load_pages(application_id: str) -> list[Path]:
    with db.connect() as cx:
        rows = cx.execute(
            "SELECT path FROM application_pages WHERE application_id=? ORDER BY ord",
            (application_id,),
        ).fetchall()
    return [Path(r["path"]) for r in rows]


async def _run_job(
    job_id: str,
    model: str,
    application_ids: list[str],
    field_spec: list[FieldSpec],
    fewshot: list[FewshotPair],
) -> None:
    loop = asyncio.get_running_loop()
    fewshot_dicts = [f.model_dump() for f in fewshot]
    try:
        for application_id in application_ids:
            if _stop_flags.get(job_id):
                break
            _set_application_status(application_id, ImageStatus.working)
            pages = _load_pages(application_id)
            if not pages:
                continue
            results: list[FieldResult] = await loop.run_in_executor(
                None, model_registry.predict, model, pages, field_spec, fewshot_dicts
            )
            if _stop_flags.get(job_id):
                _set_application_status(application_id, ImageStatus.blank)
                break
            _save_results(job_id, application_id, results)
            # working 상태 유지 — 사용자가 Complete 누르면 done으로 전환
        with db.connect() as cx:
            stopped = bool(_stop_flags.get(job_id))
            final = JobStatus.stopped.value if stopped else JobStatus.completed.value
            cx.execute("UPDATE jobs SET status=? WHERE job_id=?", (final, job_id))
            if stopped:
                # 사용자가 Complete 하지 않은 신청서의 결과는 모두 폐기한다.
                # Stop = 진행 중이던 작업의 추론 결과는 신뢰하지 않는다는 의미.
                cx.execute(
                    """DELETE FROM field_results
                       WHERE job_id = ? AND application_id IN (
                         SELECT ja.application_id FROM job_applications ja
                         JOIN applications a ON ja.application_id = a.application_id
                         WHERE ja.job_id = ? AND a.status != ?
                       )""",
                    (job_id, job_id, ImageStatus.done.value),
                )
                cx.execute(
                    """UPDATE applications SET status = ?
                       WHERE application_id IN (
                         SELECT ja.application_id FROM job_applications ja WHERE ja.job_id = ?
                       ) AND status != ?""",
                    (ImageStatus.blank.value, job_id, ImageStatus.done.value),
                )
    finally:
        _running_tasks.pop(job_id, None)
        _stop_flags.pop(job_id, None)


def _set_application_status(application_id: str, status: ImageStatus) -> None:
    with db.connect() as cx:
        cx.execute(
            "UPDATE applications SET status=? WHERE application_id=?",
            (status.value, application_id),
        )


def _save_results(job_id: str, application_id: str, results: list[FieldResult]) -> None:
    with db.connect() as cx:
        for r in results:
            cx.execute(
                """INSERT INTO field_results(job_id, application_id, key, predicted, accuracy, edited)
                   VALUES (?,?,?,?,?,?)
                   ON CONFLICT(job_id, application_id, key) DO UPDATE SET
                     predicted=excluded.predicted, accuracy=excluded.accuracy""",
                (job_id, application_id, r.key, r.predicted, r.accuracy, r.edited),
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
            """SELECT a.application_id, a.filename, a.status, a.page_count
                 FROM job_applications ja JOIN applications a
                   ON ja.application_id = a.application_id
                WHERE ja.job_id=? ORDER BY ja.ord""",
            (job_id,),
        ).fetchall()
    applications = [
        ApplicationInfo(
            application_id=r["application_id"],
            filename=r["filename"],
            status=ImageStatus(r["status"]),
            page_count=r["page_count"],
        )
        for r in rows
    ]
    spec = [FieldSpec(**s) for s in db.load_field_spec(j["field_spec"])]
    return Job(
        job_id=j["job_id"],
        model=j["model"],
        device=Device(j["device"]),
        status=JobStatus(j["status"]),
        field_spec=spec,
        applications=applications,
    )


@app.get("/jobs/{job_id}/applications/{application_id}")
def get_application_summary(job_id: str, application_id: str) -> ApplicationSummary:
    with db.connect() as cx:
        a = cx.execute(
            "SELECT status, page_count FROM applications WHERE application_id=?",
            (application_id,),
        ).fetchone()
        if not a:
            raise HTTPException(404, detail={
                "error": "application_not_found", "message": application_id
            })
        fields = cx.execute(
            "SELECT key, predicted, accuracy, edited FROM field_results "
            "WHERE job_id=? AND application_id=?",
            (job_id, application_id),
        ).fetchall()
    return ApplicationSummary(
        application_id=application_id,
        status=ImageStatus(a["status"]),
        page_count=a["page_count"],
        fields=[FieldResult(**dict(f)) for f in fields],
    )


# ---------- 수정 / 완료 ----------

@app.put("/jobs/{job_id}/applications/{application_id}")
def edit_application(job_id: str, application_id: str, body: EditRequest) -> ApplicationSummary:
    with db.connect() as cx:
        for r in body.fields:
            cx.execute(
                """INSERT INTO field_results(job_id, application_id, key, predicted, accuracy, edited)
                   VALUES (?,?,?,?,?,?)
                   ON CONFLICT(job_id, application_id, key) DO UPDATE SET edited=excluded.edited""",
                (job_id, application_id, r.key, r.predicted, r.accuracy, r.edited),
            )
    return get_application_summary(job_id, application_id)


@app.post("/jobs/{job_id}/applications/{application_id}/complete")
def complete_application(job_id: str, application_id: str) -> ApplicationSummary:
    _set_application_status(application_id, ImageStatus.done)
    return get_application_summary(job_id, application_id)


# ---------- 시트 ----------

@app.get("/jobs/{job_id}/sheet")
def get_sheet(job_id: str) -> Sheet:
    with db.connect() as cx:
        j = cx.execute("SELECT field_spec FROM jobs WHERE job_id=?", (job_id,)).fetchone()
        if not j:
            raise HTTPException(404, detail={"error": "job_not_found", "message": job_id})
        spec = db.load_field_spec(j["field_spec"])
        app_rows = cx.execute(
            """SELECT a.application_id, a.status
                 FROM job_applications ja JOIN applications a
                   ON ja.application_id = a.application_id
                WHERE ja.job_id=? ORDER BY ja.ord""",
            (job_id,),
        ).fetchall()
        field_rows = cx.execute(
            "SELECT application_id, key, predicted, edited FROM field_results WHERE job_id=?",
            (job_id,),
        ).fetchall()
    by_app: dict[str, dict[str, str | None]] = {}
    for r in field_rows:
        by_app.setdefault(r["application_id"], {})[r["key"]] = (
            r["edited"] if r["edited"] is not None else r["predicted"]
        )
    rows: list[SheetRow] = []
    for ar in app_rows:
        if ar["status"] != ImageStatus.done.value:
            continue
        values = {s["key"]: by_app.get(ar["application_id"], {}).get(s["key"]) for s in spec}
        rows.append(SheetRow(application_id=ar["application_id"], values=values))
    columns = [SheetColumn(key=s["key"], label=s["label"]) for s in spec]
    return Sheet(columns=columns, rows=rows)


# ---------- 에러 포맷 통일 ----------

@app.exception_handler(HTTPException)
async def _http_exc(_, exc: HTTPException):  # noqa: ANN001
    detail = exc.detail if isinstance(exc.detail, dict) else {"error": "http_error", "message": str(exc.detail)}
    return JSONResponse(status_code=exc.status_code, content=detail)
