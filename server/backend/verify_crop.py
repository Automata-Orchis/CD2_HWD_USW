"""다중 PDF × FULL 검증 — CSV 누적 출력.

배경
----
v2 검증 (FULL) 결과 분류는 라벨의 위치 텍스트 + 프롬프트 규칙 5 만으로 사실상 해결됐고,
CROP 추가 호출은 정확도 ROI 가 음수 (맥락 손실로 글자 인식이 오히려 떨어짐) 임이 확인됨.
사용자 결정으로 CROP 호출은 폐기, FULL 만 다중 PDF 에 적용해 정답 대조용 CSV 를 생성.

(좌표 자체는 TODO.md 의 "최우선" 챕터에 메타로 남겨 둠 — frontend UI overlay 등 추후
용도. 본 스크립트는 좌표를 사용하지 않는다.)

사용 (서버)
----
    cd ~/backend
    python verify_crop.py [pdf_or_dir] [template_name] [model_name] [out_csv]
    # 모든 인자 생략 시 기본 — ~/data/direct_payment/*.pdf, direct_payment_v2, Qwen3.5-9B, ./verify_results.csv
    # 단일 PDF 지정 : python verify_crop.py ~/data/direct_payment/direct_payment_1.pdf
    # 폴더 명시     : python verify_crop.py ~/data/direct_payment/
    # 4B 폴백 (1번 자리 빈 문자열로 default 사용) :
    #   python verify_crop.py "" direct_payment_v2 Qwen3.5-4B

각 PDF 별로 페이지 0·1 전체 + 전체 spec 1 회 FULL 호출.

출력 (UTF-8 BOM CSV, wide)
----
  한 행 = 한 키. 컬럼: key, label, <pdf_id>, ..., answer (빈 칸 — 사용자가 직접 채워 대조).
"""
from __future__ import annotations

import csv
import sys
import tempfile
import time
from pathlib import Path

import pypdfium2 as pdfium

import model_registry
import templates_io

DEFAULT_MODEL = "Qwen3.5-9B"
DEFAULT_TEMPLATE = "direct_payment"
DEFAULT_PDF_DIR = Path.home() / "data" / "direct_payment"
DEFAULT_OUT_CSV = Path("verify_results.csv")


def _render(pdf_path: Path, n: int, dst: Path) -> list[Path]:
    """PDF 전 페이지를 scale=2.0 PNG 로 — backend _materialize_pages 와 동일 배율."""
    pdf = pdfium.PdfDocument(str(pdf_path))
    out: list[Path] = []
    try:
        for i in range(min(n, len(pdf))):
            page = pdf[i]
            page.render(scale=2.0).to_pil().save(dst / f"{i}.png", "PNG")
            out.append(dst / f"{i}.png")
            page.close()
    finally:
        pdf.close()
    return out


def _pdf_id(p: Path) -> str:
    """파일 stem 에서 'direct_payment_' 접두 제거. 없으면 stem 그대로."""
    stem = p.stem
    return stem[len("direct_payment_"):] if stem.startswith("direct_payment_") else stem


def main() -> None:
    pdf_arg = sys.argv[1] if len(sys.argv) >= 2 and sys.argv[1] else None
    template_name = sys.argv[2] if len(sys.argv) >= 3 and sys.argv[2] else DEFAULT_TEMPLATE
    model_name = sys.argv[3] if len(sys.argv) >= 4 and sys.argv[3] else DEFAULT_MODEL
    out_csv = Path(sys.argv[4]) if len(sys.argv) >= 5 and sys.argv[4] else DEFAULT_OUT_CSV

    # PDF 목록 — 단일 파일 인자 vs 디렉토리 자동 순회 vs default 디렉토리.
    if pdf_arg:
        p = Path(pdf_arg)
        if p.is_dir():
            pdfs = sorted(p.glob("*.pdf"))
        elif p.is_file():
            pdfs = [p]
        else:
            print(f"pdf arg not found: {p}")
            sys.exit(1)
    else:
        pdfs = sorted(DEFAULT_PDF_DIR.glob("*.pdf"))
    if not pdfs:
        print("no PDFs found")
        sys.exit(1)

    template = templates_io.load_template(template_name)
    if template is None:
        print(f"template not found: {template_name}")
        sys.exit(1)
    full_spec = template.field_spec
    fewshot = [f.model_dump() for f in template.fewshot]
    print(f"template={template_name}, total fields={len(full_spec)}, model={model_name}, pdfs={len(pdfs)}")
    print(f"out_csv={out_csv.resolve()}")

    # 결과 누적 — results[key][pdf_id] = value
    results: dict[str, dict[str, str]] = {s.key: {} for s in full_spec}
    pdf_ids: list[str] = []

    grand_t0 = time.time()
    for pdf_path in pdfs:
        pid = _pdf_id(pdf_path)
        pdf_ids.append(pid)
        print(f"\n=== [{pid}] {pdf_path.name} ===")
        with tempfile.TemporaryDirectory() as tmp:
            tmpd = Path(tmp)
            pages = _render(pdf_path, n=2, dst=tmpd)
            t0 = time.time()
            res = model_registry.predict(model_name, pages, full_spec, fewshot)
            print(f"  [FULL] {time.time()-t0:.1f}s")
            for r in res:
                results[r.key][pid] = r.predicted if r.predicted is not None else ""

    # CSV 출력 — wide, UTF-8 BOM (Excel 한글 호환).
    with out_csv.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        header = ["key", "label"] + pdf_ids + ["answer"]
        writer.writerow(header)
        for spec in full_spec:
            row = [spec.key, spec.label] + [results[spec.key].get(pid, "") for pid in pdf_ids] + [""]
            writer.writerow(row)

    print(f"\n총 {time.time()-grand_t0:.1f}s, {len(pdfs)} PDF × 1 FULL = {len(pdfs)} predict")
    print(f"CSV 저장: {out_csv.resolve()}")


if __name__ == "__main__":
    main()
