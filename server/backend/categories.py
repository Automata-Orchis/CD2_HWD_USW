"""사전 적재본 카테고리 스캔.

`server/data/<yml-stem>/` 의 각 폴더가 한 신청서 종류(template)에 대응한다.
- 폴더명은 `server/backend/templates/<name>.yml` 의 파일 stem 과 동일해야 한다.
- 폴더 안의 PDF / 이미지 1개 = 신청서(application) 1건.
- `original_data/` 등 RESERVED 디렉터리는 스캔 대상에서 제외한다.

스캔은 GET /work-categories 와 GET /applications 호출 시 매번 수행되며
신규 파일만 결정론적 ID 로 applications 테이블에 인입한다 (멱등).
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import db
import templates_io
from schemas import ApplicationInfo, CategoryStat, ImageStatus

# 작업 탐색에서 제외할 폴더명 (원본 신청서 양식 등).
_RESERVED_DIRS: set[str] = {"original_data"}
# 인입 대상 확장자. 이외의 파일은 무시한다.
_SUPPORTED_EXTS: set[str] = {".pdf", ".png", ".jpg", ".jpeg"}


def _make_application_id(template_name: str, filename: str) -> str:
    """`<template>/<filename>` 을 sha1 해시해 결정론적 10자 ID 를 만든다.

    같은 경로의 파일은 재스캔해도 같은 ID 로 들어와 멱등성을 보장한다.
    """
    key = f"{template_name}/{filename}".encode("utf-8")
    return f"app_{hashlib.sha1(key).hexdigest()[:10]}"


def _pdf_page_count(path: Path) -> int:
    """PDF 페이지 수. 손상 파일이면 0 을 돌려준다 (이 경우 인입 스킵)."""
    import pypdfium2 as pdfium

    try:
        pdf = pdfium.PdfDocument(str(path))
    except Exception:
        return 0
    try:
        return len(pdf)
    finally:
        pdf.close()


def _page_count_for(path: Path) -> int:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return _pdf_page_count(path)
    # 이미지(.png/.jpg/.jpeg) 는 항상 1 페이지.
    return 1


def _scan_template_dir(template_name: str) -> list[Path]:
    """카테고리 폴더 직속 파일만 반환 (재귀 없음). 알파벳 정렬."""
    folder = db.DATA_DIR / template_name
    if not folder.is_dir():
        return []
    out: list[Path] = []
    for p in sorted(folder.iterdir()):
        if not p.is_file():
            continue
        if p.name.startswith("."):
            continue
        if p.suffix.lower() not in _SUPPORTED_EXTS:
            continue
        out.append(p)
    return out


def scan_and_ingest() -> None:
    """모든 template stem 폴더를 스캔해 신규 파일을 applications 에 등록한다."""
    templates = templates_io.list_templates()
    template_names = [t.name for t in templates if t.name not in _RESERVED_DIRS]
    with db.connect() as cx:
        existing = {
            r["application_id"]
            for r in cx.execute("SELECT application_id FROM applications").fetchall()
        }
        for tname in template_names:
            for path in _scan_template_dir(tname):
                aid = _make_application_id(tname, path.name)
                if aid in existing:
                    continue
                pages = _page_count_for(path)
                if pages <= 0:
                    continue
                cx.execute(
                    "INSERT INTO applications(application_id, filename, status, page_count, template_name, source_path) "
                    "VALUES (?,?,?,?,?,?)",
                    (
                        aid,
                        path.name,
                        ImageStatus.blank.value,
                        pages,
                        tname,
                        str(path),
                    ),
                )
                existing.add(aid)


def category_stats() -> list[CategoryStat]:
    """카테고리(template)별 통계. scan_and_ingest 호출자가 먼저 실행 보장."""
    stats: list[CategoryStat] = []
    with db.connect() as cx:
        for t in templates_io.list_templates():
            if t.name in _RESERVED_DIRS:
                continue
            rows = cx.execute(
                "SELECT status, COUNT(*) AS c FROM applications WHERE template_name=? GROUP BY status",
                (t.name,),
            ).fetchall()
            counts = {r["status"]: r["c"] for r in rows}
            total = sum(counts.values())
            done = counts.get(ImageStatus.done.value, 0)
            incomplete = total - done
            rate = (done / total) if total else 0.0
            stats.append(CategoryStat(
                template_name=t.name,
                label=t.label,
                total=total,
                done=done,
                incomplete=incomplete,
                rate=rate,
            ))
    return stats


def applications_for(template_name: str) -> list[ApplicationInfo]:
    """해당 카테고리의 신청서 목록을 파일명 순으로 반환."""
    with db.connect() as cx:
        rows = cx.execute(
            "SELECT application_id, filename, status, page_count, template_name "
            "FROM applications WHERE template_name=? ORDER BY filename",
            (template_name,),
        ).fetchall()
    return [
        ApplicationInfo(
            application_id=r["application_id"],
            filename=r["filename"],
            status=ImageStatus(r["status"]),
            page_count=r["page_count"],
            template_name=r["template_name"],
        )
        for r in rows
    ]
