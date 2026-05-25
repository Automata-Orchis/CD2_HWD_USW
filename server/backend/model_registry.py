"""모델 어댑터 레지스트리.

각 모델은 `predict(image_path, field_spec, fewshot) -> list[FieldResult]`를 구현하면 된다.
fewshot 은 [{"user": str, "assistant": str}, ...] 형태(이미지 없는 텍스트 페어)이며,
사용하지 않는 모델은 인자만 받고 무시한다.
"""
from __future__ import annotations

import json
import random
import re
import time
from pathlib import Path
from typing import Callable

from schemas import FieldResult, FieldSpec


def _mock_predict(
    image_path: Path,
    field_spec: list[FieldSpec],
    fewshot: list[dict],
) -> list[FieldResult]:
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


# ---------- Qwen3.5-9B ----------
# 첫 호출에서 processor/model 을 1회 lazy 적재해 모듈 전역에 캐시.
# 이후 같은 프로세스 안의 모든 호출은 generate 비용만 든다 (~8s/256토큰 @ 32 tok/s).

_QWEN_MODEL_DIR = Path.home() / "model" / "Qwen3.5-9B"
_qwen_processor = None
_qwen_model = None


def _qwen_get():
    global _qwen_processor, _qwen_model
    if _qwen_model is None:
        import torch
        from transformers import AutoModelForImageTextToText, AutoProcessor

        # local_files_only=True — 폐쇄망/불안정 네트워크에서 HF Hub 메타 조회로
        # from_pretrained 가 다운로드 재시도 루프에 빠지는 것을 차단.
        _qwen_processor = AutoProcessor.from_pretrained(
            str(_QWEN_MODEL_DIR), local_files_only=True
        )
        _qwen_model = AutoModelForImageTextToText.from_pretrained(
            str(_QWEN_MODEL_DIR),
            dtype=torch.bfloat16,
            device_map="auto",
            local_files_only=True,
        )
        _qwen_model.eval()
    return _qwen_processor, _qwen_model


def _qwen_build_prompt(field_spec: list[FieldSpec]) -> str:
    lines = ["이 이미지에서 다음 항목들을 읽어 JSON 객체로만 답하라.", "", "항목:"]
    for s in field_spec:
        lines.append(f'- "{s.key}": {s.label}')
    lines += [
        "",
        "규칙:",
        "1. 출력은 반드시 JSON 객체 한 개. 그 외 텍스트나 코드 블록 금지.",
        "2. 키는 위 영문 그대로 사용.",
        '3. 값을 읽을 수 없으면 빈 문자열 "".',
    ]
    return "\n".join(lines)


def _qwen_parse(text: str, field_spec: list[FieldSpec]) -> dict[str, str | None]:
    body = text.strip()
    body = re.sub(r"^```(?:json)?\s*", "", body)
    body = re.sub(r"\s*```$", "", body)
    parsed: dict = {}
    start, end = body.find("{"), body.rfind("}")
    if start != -1 and end > start:
        try:
            raw = json.loads(body[start : end + 1])
            if isinstance(raw, dict):
                parsed = raw
        except json.JSONDecodeError:
            pass
    out: dict[str, str | None] = {}
    for s in field_spec:
        v = parsed.get(s.key)
        if v in (None, ""):
            out[s.key] = None
        else:
            out[s.key] = str(v).strip() or None
    return out


def _qwen_predict(
    image_path: Path,
    field_spec: list[FieldSpec],
    fewshot: list[dict],
) -> list[FieldResult]:
    import torch
    from PIL import Image

    processor, model = _qwen_get()
    image = Image.open(image_path).convert("RGB")
    # fewshot 은 이미지 없는 텍스트 user/assistant 페어. 실제 분석 대상 이미지 메시지 앞에
    # 그대로 끼워 넣어 출력 형식을 시연한다 (verify_qwen.py 의 messages[1~4] 와 동일 구조).
    messages: list[dict] = []
    for pair in fewshot:
        messages.append({"role": "user", "content": pair["user"]})
        messages.append({"role": "assistant", "content": pair["assistant"]})
    messages.append(
        {
            "role": "user",
            "content": [
                {"type": "image"},
                {"type": "text", "text": _qwen_build_prompt(field_spec)},
            ],
        }
    )
    text = processor.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True,
        enable_thinking=False,
    )
    inputs = processor(text=[text], images=[image], return_tensors="pt", padding=True).to(model.device)
    with torch.inference_mode():
        out = model.generate(**inputs, max_new_tokens=512, do_sample=False)
    new_tokens = out[:, inputs.input_ids.shape[1] :]
    output_text = processor.batch_decode(new_tokens, skip_special_tokens=True)[0]
    parsed = _qwen_parse(output_text, field_spec)
    return [
        FieldResult(key=s.key, predicted=parsed[s.key], accuracy=None, edited=None)
        for s in field_spec
    ]


_REGISTRY: dict[str, Callable[[Path, list[FieldSpec], list[dict]], list[FieldResult]]] = {
    "Mock-Model": _mock_predict,
    "Qwen3.5-9B": _qwen_predict,
}


def available_models() -> list[str]:
    return list(_REGISTRY.keys())


def predict(
    model_name: str,
    image_path: Path,
    field_spec: list[FieldSpec],
    fewshot: list[dict],
) -> list[FieldResult]:
    if model_name not in _REGISTRY:
        raise KeyError(f"unknown model: {model_name}")
    return _REGISTRY[model_name](image_path, field_spec, fewshot)
