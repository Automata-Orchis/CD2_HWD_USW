"""모델 어댑터 레지스트리.

각 모델은 `predict(image_paths, field_spec, fewshot) -> list[FieldResult]`를 구현한다.
- `image_paths` 는 하나의 신청서를 구성하는 페이지 이미지 리스트(길이 ≥ 1). 단일 이미지
  신청서는 길이 1, PDF 분할 신청서는 길이 N. 모델은 N장 전체를 한 번에 보고 단일 결과를
  산출해야 한다.
- `fewshot` 은 [{"user": str, "assistant": str}, ...] 형태(이미지 없는 텍스트 페어).
  사용하지 않는 모델은 인자만 받고 무시한다.
"""
from __future__ import annotations

import json
import random
import re
import threading
import time
from pathlib import Path
from typing import Callable

from schemas import FieldResult, FieldSpec

# Qwen3.5-9B 의 적재 소요 시간 추정(실측 ~161s). 게이지 % 산출용 — 실제 호출 완료가 신호이며
# 이 값은 어디까지나 frontend 시각 표현용 추정값이다.
_QWEN_LOAD_EST_SEC = 180.0

# 모델별 적재 상태. predict() 호출자가 lazy 로드를 트리거하기 전에 사용자가 명시적으로
# start_loading() 을 부르면 백그라운드 스레드에서 미리 적재한다.
_load_state: dict[str, dict] = {}
# RLock — start_loading 이 락을 쥔 상태에서 _snapshot() 을 호출하는 재귀 진입을 허용한다.
_load_lock = threading.RLock()


def _init_load_state() -> None:
    # Mock-Model 은 적재 비용이 없으므로 항상 loaded 로 둔다.
    _load_state.setdefault("Mock-Model", {"state": "loaded", "progress": 1.0, "started_at": None, "error": None})
    _load_state.setdefault("Qwen3.5-9B", {"state": "unloaded", "progress": 0.0, "started_at": None, "error": None})


def _mock_predict(
    image_paths: list[Path],
    field_spec: list[FieldSpec],
    fewshot: list[dict],
) -> list[FieldResult]:
    time.sleep(0.6)  # 시연용 지연 — 진행 상태를 눈으로 보기 위함
    samples = {
        "text": ["홍길동", "김철수", "이영희", "박민수"],
        "number": ["010-1234-5678", "123-456-7890"],
    }
    stem = image_paths[0].parent.name if image_paths else "?"
    out: list[FieldResult] = []
    for spec in field_spec:
        bag = samples.get(spec.type, samples["text"])
        out.append(
            FieldResult(
                key=spec.key,
                predicted=f"[mock:{stem}/{len(image_paths)}p] {random.choice(bag)}",
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
# 동시에 두 진입자(예: Load 버튼 worker + Analyze 의 lazy load) 가 _qwen_get 에 들어와도
# 실제 적재는 단 한 번만 수행되도록 보호하는 mutex. RLock 인 _load_lock 과 분리한 이유 —
# 적재 161s 동안 _load_lock 을 점유하면 _snapshot()/get_load_status 가 막혀 frontend
# 진행률 폴링이 멈춘다. 적재용 mutex 와 status 접근용 lock 을 분리한다.
_qwen_load_mutex = threading.Lock()


def _qwen_get():
    """가중치 lazy load. 이미 적재됐으면 즉시 반환.

    explicit Load 버튼 흐름(`start_loading` → `_qwen_load_worker`)과 자동 lazy load
    흐름(`predict` → `_qwen_predict`) 둘 다 이 함수를 거친다. mutex 로 단일 적재 보장 +
    _load_state 갱신을 함수 안에 일원화해 두 흐름 모두 frontend 진행률을 본다.
    """
    global _qwen_processor, _qwen_model
    if _qwen_model is not None:
        return _qwen_processor, _qwen_model
    _init_load_state()
    with _qwen_load_mutex:
        # double-check — 대기 중에 다른 호출자가 적재를 완료했을 수 있다.
        if _qwen_model is not None:
            return _qwen_processor, _qwen_model
        with _load_lock:
            _load_state["Qwen3.5-9B"].update({
                "state": "loading", "progress": 0.0, "started_at": time.time(), "error": None,
            })
        try:
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
            with _load_lock:
                _load_state["Qwen3.5-9B"].update({"state": "loaded", "progress": 1.0})
        except Exception as e:
            with _load_lock:
                _load_state["Qwen3.5-9B"].update({"state": "failed", "error": repr(e)})
            raise
    return _qwen_processor, _qwen_model


# ---------- 모델 적재 제어 (frontend "모델 로드" 버튼 + 게이지) ----------

def _qwen_load_worker() -> None:
    """백그라운드 스레드 — Qwen 적재 트리거. state 전환은 `_qwen_get` 안에서 처리."""
    try:
        _qwen_get()
    except Exception:
        # _qwen_get 안의 except 가 이미 state=failed 로 마킹했다. 여기선 추가 처리 없음.
        pass


def start_loading(model_name: str) -> dict:
    """사용자 명시적 적재 트리거. 이미 loading/loaded 면 현 상태만 반환."""
    _init_load_state()
    if model_name not in _load_state:
        return {"state": "unknown", "progress": 0.0, "error": f"unknown model: {model_name}"}
    with _load_lock:
        state = _load_state[model_name]
        if state["state"] in ("loading", "loaded"):
            return _snapshot(model_name)
        if model_name == "Qwen3.5-9B":
            state.update({"state": "loading", "progress": 0.0, "started_at": time.time(), "error": None})
            threading.Thread(target=_qwen_load_worker, daemon=True).start()
        else:
            # Mock 등 적재 비용 없는 모델 — 즉시 loaded.
            state.update({"state": "loaded", "progress": 1.0, "started_at": None, "error": None})
    return _snapshot(model_name)


def get_load_status(model_name: str) -> dict:
    _init_load_state()
    if model_name not in _load_state:
        return {"state": "unknown", "progress": 0.0, "error": None}
    return _snapshot(model_name)


def _snapshot(model_name: str) -> dict:
    """현재 상태의 얕은 복사 + loading 중이면 경과시간 기반 progress 추정."""
    with _load_lock:
        s = dict(_load_state[model_name])
    if s["state"] == "loading" and s.get("started_at"):
        elapsed = time.time() - s["started_at"]
        # 1.0 미만으로 클램프 — 실제 적재 완료 시 worker 가 1.0 으로 갱신한다.
        s["progress"] = max(s.get("progress", 0.0), min(0.95, elapsed / _QWEN_LOAD_EST_SEC))
    return {"state": s["state"], "progress": s["progress"], "error": s.get("error")}


def _qwen_build_prompt(field_spec: list[FieldSpec], n_pages: int) -> str:
    if n_pages > 1:
        head = [
            f"이 신청서는 {n_pages}장의 페이지로 구성되어 있다. "
            "주어진 모든 페이지의 내용을 종합해서 다음 항목들을 읽어 JSON 객체로만 답하라.",
        ]
    else:
        head = ["이 이미지에서 다음 항목들을 읽어 JSON 객체로만 답하라."]
    lines = head + ["", "항목:"]
    for s in field_spec:
        lines.append(f'- "{s.key}": {s.label}')
    lines += [
        "",
        "규칙:",
        "1. 출력은 반드시 JSON 객체 한 개. 그 외 텍스트나 코드 블록 금지.",
        "2. 키는 위 영문 그대로 사용.",
        '3. 값을 읽을 수 없으면 빈 문자열 "".',
        "4. 같은 항목이 여러 페이지에 나타나면 가장 명확히 적힌 값을 사용한다.",
    ]
    return "\n".join(lines)


def _qwen_parse(text: str, field_spec: list[FieldSpec]) -> dict[str, str | None]:
    body = text.strip()
    body = re.sub(r"^```(?:json)?\s*", "", body)
    body = re.sub(r"\s*```$", "", body)
    parsed: dict = {}
    parse_error: str | None = None
    start, end = body.find("{"), body.rfind("}")
    if start != -1 and end > start:
        try:
            raw = json.loads(body[start : end + 1])
            if isinstance(raw, dict):
                parsed = raw
            else:
                parse_error = f"top-level is {type(raw).__name__}, not dict"
        except json.JSONDecodeError as e:
            parse_error = f"JSONDecodeError: {e}"
    else:
        parse_error = f"no balanced braces (find='{start}', rfind='{end}')"
    if parse_error or not parsed:
        # 파싱 실패 시 raw 를 stdout 에 그대로 찍는다 — 잘림(`}` 누락) vs 형식 깨짐 진단용.
        print(f"[qwen parse fail] {parse_error or 'empty dict'} | raw_len={len(text)} | raw={text!r}", flush=True)
    out: dict[str, str | None] = {}
    for s in field_spec:
        v = parsed.get(s.key)
        if v in (None, ""):
            out[s.key] = None
        else:
            out[s.key] = str(v).strip() or None
    return out


def _qwen_predict(
    image_paths: list[Path],
    field_spec: list[FieldSpec],
    fewshot: list[dict],
) -> list[FieldResult]:
    import torch
    from PIL import Image

    if not image_paths:
        return [FieldResult(key=s.key, predicted=None, accuracy=None, edited=None) for s in field_spec]

    processor, model = _qwen_get()
    images = [Image.open(p).convert("RGB") for p in image_paths]

    # fewshot 은 이미지 없는 텍스트 user/assistant 페어. 실제 분석 대상 이미지 메시지 앞에
    # 그대로 끼워 넣어 출력 형식을 시연한다 (verify_qwen.py 의 messages[1~4] 와 동일 구조).
    messages: list[dict] = []
    for pair in fewshot:
        messages.append({"role": "user", "content": pair["user"]})
        messages.append({"role": "assistant", "content": pair["assistant"]})

    # 다중 페이지: image content 블록을 페이지 수만큼 앞에 두고 텍스트 프롬프트는 1개.
    content: list[dict] = [{"type": "image"} for _ in images]
    content.append({"type": "text", "text": _qwen_build_prompt(field_spec, len(images))})
    messages.append({"role": "user", "content": content})

    text = processor.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True,
        enable_thinking=False,
    )
    inputs = processor(text=[text], images=images, return_tensors="pt", padding=True).to(model.device)
    with torch.inference_mode():
        out = model.generate(**inputs, max_new_tokens=1024, do_sample=False)
    new_tokens = out[:, inputs.input_ids.shape[1] :]
    output_text = processor.batch_decode(new_tokens, skip_special_tokens=True)[0]
    parsed = _qwen_parse(output_text, field_spec)
    return [
        FieldResult(key=s.key, predicted=parsed[s.key], accuracy=None, edited=None)
        for s in field_spec
    ]


_REGISTRY: dict[str, Callable[[list[Path], list[FieldSpec], list[dict]], list[FieldResult]]] = {
    "Mock-Model": _mock_predict,
    "Qwen3.5-9B": _qwen_predict,
}


def available_models() -> list[str]:
    return list(_REGISTRY.keys())


def predict(
    model_name: str,
    image_paths: list[Path],
    field_spec: list[FieldSpec],
    fewshot: list[dict],
) -> list[FieldResult]:
    if model_name not in _REGISTRY:
        raise KeyError(f"unknown model: {model_name}")
    return _REGISTRY[model_name](image_paths, field_spec, fewshot)
