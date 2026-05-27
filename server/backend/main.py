"""FastAPI backend — SCHEMA.md의 엔드포인트를 구현한다.

서버에서:
    uvicorn main:app --host 0.0.0.0 --port 8000
    cloudflared tunnel --url http://localhost:8000

신청서는 서버 디스크에 사전 적재된다 — `server/data/<template_name>/` 폴더 (template_name 은
`server/backend/templates/<name>.yml` 의 파일 stem). 한 파일(PDF 또는 이미지)이 한 application 이며,
PDF 의 페이지는 요청 시 즉석 렌더링된다 (디스크 캐시 없음).
"""
from __future__ import annotations

import asyncio
import io
import tempfile
import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response

import categories
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


@app.post("/models/{model_name}/load")
def load_model(model_name: str) -> dict:
    """사용자 명시적 적재 트리거. 첫 추론을 lazy 로드로 기다리는 ~161s 지연을
    피하기 위해 frontend "모델 로드" 버튼이 호출한다. 이미 적재된 경우 즉시 반환.
    """
    if model_name not in model_registry.available_models():
        raise HTTPException(400, detail={"error": "unknown_model", "message": model_name})
    return model_registry.start_loading(model_name)


@app.get("/models/{model_name}/status")
def model_status(model_name: str) -> dict:
    """현재 적재 상태와 진행률(0.0~1.0). loading 중에는 시간 기반 추정값."""
    if model_name not in model_registry.available_models():
        raise HTTPException(400, detail={"error": "unknown_model", "message": model_name})
    return model_registry.get_load_status(model_name)


@app.get("/devices")
def list_devices() -> dict:
    return {"devices": [d.value for d in Device]}


@app.get("/templates")
def list_templates() -> dict:
    return {"templates": [t.model_dump() for t in templates_io.list_templates()]}


# ---------- 카테고리(작업 선택) ----------

@app.get("/work-categories")
def list_work_categories() -> dict:
    """`server/data/<template>/` 폴더를 스캔·인입한 뒤 카테고리별 통계 반환.

    frontend 의 "작업 선택" 대시보드가 호출한다. 매 호출마다 디스크 재스캔.
    """
    categories.scan_and_ingest()
    return {"categories": [c.model_dump() for c in categories.category_stats()]}


@app.get("/applications")
def list_applications(template_name: str = Query(...)) -> dict:
    """카테고리(template) 의 신청서 목록. 사용자가 Sub Box 클릭 시 호출."""
    categories.scan_and_ingest()
    return {"applications": [a.model_dump() for a in categories.applications_for(template_name)]}


# ---------- 페이지 파일 ----------

def _render_pdf_page(pdf_path: Path, ord_: int) -> bytes:
    """PDF 의 특정 페이지를 PNG 바이트로 즉석 렌더링.

    scale=2.0 — 기본 72 DPI 의 2배(=144 DPI). 손글씨 가독성과 응답 크기의 절충점.
    디스크 캐시 없이 매 요청 시 렌더. 브라우저 캐시가 반복 요청을 흡수한다.
    """
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(str(pdf_path))
    try:
        page = pdf[ord_]
        try:
            bitmap = page.render(scale=2.0)
            pil = bitmap.to_pil()
            buf = io.BytesIO()
            pil.save(buf, "PNG")
            return buf.getvalue()
        finally:
            page.close()
    finally:
        pdf.close()


@app.get("/applications/{application_id}/pages/{ord}/file")
def page_file(application_id: str, ord: int):
    with db.connect() as cx:
        row = cx.execute(
            "SELECT source_path, page_count FROM applications WHERE application_id=?",
            (application_id,),
        ).fetchone()
    if not row or not row["source_path"]:
        raise HTTPException(404, detail={
            "error": "application_not_found", "message": application_id
        })
    source = Path(row["source_path"])
    if not source.exists():
        raise HTTPException(404, detail={
            "error": "source_missing", "message": str(source)
        })
    if ord < 0 or ord >= row["page_count"]:
        raise HTTPException(404, detail={
            "error": "page_out_of_range", "message": f"{application_id}/{ord}"
        })
    if source.suffix.lower() == ".pdf":
        return Response(content=_render_pdf_page(source, ord), media_type="image/png")
    # 이미지 신청서(.png/.jpg/.jpeg): ord 는 항상 0, 파일 그대로 서빙.
    return FileResponse(source)


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


def _load_source(application_id: str) -> tuple[Path, int] | None:
    """application 의 source 파일 경로와 페이지 수 조회. 없으면 None."""
    with db.connect() as cx:
        row = cx.execute(
            "SELECT source_path, page_count FROM applications WHERE application_id=?",
            (application_id,),
        ).fetchone()
    if not row or not row["source_path"]:
        return None
    return Path(row["source_path"]), int(row["page_count"])


def _materialize_pages(source: Path, page_count: int, tmpdir: Path) -> list[Path]:
    """모델 predict 호출용 페이지 경로 리스트 생성.

    - 이미지 신청서: 원본 파일 경로 그대로 (page_count=1).
    - PDF 신청서: 페이지별 PNG 를 tmpdir 에 분할 저장. caller 가 tmpdir 정리.
    """
    if source.suffix.lower() != ".pdf":
        return [source]
    import pypdfium2 as pdfium

    out: list[Path] = []
    pdf = pdfium.PdfDocument(str(source))
    try:
        for i in range(page_count):
            page = pdf[i]
            try:
                bitmap = page.render(scale=2.0)
                pil = bitmap.to_pil()
                dst = tmpdir / f"{i}.png"
                pil.save(dst, "PNG")
                out.append(dst)
            finally:
                page.close()
    finally:
        pdf.close()
    return out


async def _run_job(
    job_id: str,
    model: str,
    application_ids: list[str],
    field_spec: list[FieldSpec],
    fewshot: list[FewshotPair],
) -> None:
    loop = asyncio.get_running_loop()
    fewshot_dicts = [f.model_dump() for f in fewshot]

    def _empty_results() -> list[FieldResult]:
        # 빈 FieldResult 한 세트 — 추론 실패 / 소스 누락 시 frontend 가 표를 그리고
        # 사용자가 수동 입력할 수 있도록 키만 채워 저장한다.
        return [FieldResult(key=s.key, predicted=None, accuracy=None, edited=None) for s in field_spec]

    try:
        for application_id in application_ids:
            if _stop_flags.get(job_id):
                break
            _set_application_status(application_id, ImageStatus.working)
            # per-application try/except — 한 신청서의 실패가 이후 신청서를 막지 않게 한다.
            # 실패 시에도 빈 FieldResult 를 저장해 ApplicationSummary 가 빈 표로 렌더된다.
            # 추론 성공/실패는 status(analyzed/error)로 구분 표기해 사용자가 "미분석"·
            # "분석완료"·"추론오류"를 List 에서 구별할 수 있게 한다.
            try:
                info = _load_source(application_id)
                if info is None:
                    _save_results(job_id, application_id, _empty_results())
                    _set_application_status(application_id, ImageStatus.error)
                    continue
                source, page_count = info
                with tempfile.TemporaryDirectory() as tmp:
                    pages = _materialize_pages(source, page_count, Path(tmp))
                    if not pages:
                        _save_results(job_id, application_id, _empty_results())
                        _set_application_status(application_id, ImageStatus.error)
                        continue
                    results: list[FieldResult] = await loop.run_in_executor(
                        None, model_registry.predict, model, pages, field_spec, fewshot_dicts
                    )
            except Exception as exc:
                print(f"[predict failed] job={job_id} app={application_id}: {exc!r}", flush=True)
                _save_results(job_id, application_id, _empty_results())
                _set_application_status(application_id, ImageStatus.error)
                continue
            if _stop_flags.get(job_id):
                _set_application_status(application_id, ImageStatus.blank)
                break
            _save_results(job_id, application_id, results)
            # 추론 완료 — 결과 저장됨. 사용자가 Complete 누르면 done 으로 전환.
            _set_application_status(application_id, ImageStatus.analyzed)
        with db.connect() as cx:
            stopped = bool(_stop_flags.get(job_id))
            final = JobStatus.stopped.value if stopped else JobStatus.completed.value
            cx.execute("UPDATE jobs SET status=? WHERE job_id=?", (final, job_id))
            if stopped:
                # Stop = 진행 중이던 신청서의 비-done 결과는 폐기한다.
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
            """SELECT a.application_id, a.filename, a.status, a.page_count, a.template_name
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
            template_name=r["template_name"],
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
