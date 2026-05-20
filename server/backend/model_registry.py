"""모델 어댑터 레지스트리.

각 모델은 `predict(image_path, field_spec) -> list[FieldResult]`를 구현하면 된다.
현재는 Mock 모델만 등록. 실제 VLM(Qwen 등)은 동일 인터페이스로 추가하면 frontend/SCHEMA는 손대지 않는다.
"""
from __future__ import annotations

import random
import time
from pathlib import Path
from typing import Callable

from schemas import FieldResult, FieldSpec


def _mock_predict(image_path: Path, field_spec: list[FieldSpec]) -> list[FieldResult]:
    time.sleep(0.6)  # 시연용 지연 — 진행 상태를 눈으로 보기 위함
    samples = {
        "text": ["홍길동", "김철수", "이영희", "박민수"],
        "number": ["010-1234-5678", "123-456-7890"],
    }
    out: list[FieldResult] = []
    for spec in field_spec:
        bag = samples.get(spec.type, samples["text"])
        out.append(
            FieldResult(
                key=spec.key,
                predicted=f"[mock:{image_path.stem}] {random.choice(bag)}",
                accuracy=round(random.uniform(0.6, 0.99), 2),
                edited=None,
            )
        )
    return out


_REGISTRY: dict[str, Callable[[Path, list[FieldSpec]], list[FieldResult]]] = {
    "Mock-Model": _mock_predict,
    # 실제 VLM은 여기에 등록한다.
    # "Qwen3.5-9B": _qwen_predict,
}


def available_models() -> list[str]:
    return list(_REGISTRY.keys())


def predict(model_name: str, image_path: Path, field_spec: list[FieldSpec]) -> list[FieldResult]:
    if model_name not in _REGISTRY:
        raise KeyError(f"unknown model: {model_name}")
    return _REGISTRY[model_name](image_path, field_spec)
