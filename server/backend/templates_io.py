"""Form template loader.

각 신청서 타입은 templates/<name>.yml 에 정의된다:
    name: <식별자>
    label: <UI 표시명>
    field_spec: [{key, label, type}]
    fewshot: [{user, assistant}]   # 비어 있어도 됨

매 요청마다 디스크에서 다시 읽으므로 서버 재시작 없이 추가/수정 가능.
"""
from __future__ import annotations

from pathlib import Path

import yaml

from schemas import Template

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"


def list_templates() -> list[Template]:
    if not TEMPLATES_DIR.exists():
        return []
    out: list[Template] = []
    for p in sorted(TEMPLATES_DIR.glob("*.yml")):
        out.append(Template(**yaml.safe_load(p.read_text(encoding="utf-8"))))
    return out


def load_template(name: str) -> Template | None:
    for t in list_templates():
        if t.name == name:
            return t
    return None
