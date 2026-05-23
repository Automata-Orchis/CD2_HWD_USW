"""Qwen3.5-9B 멀티모달 추론 검증 스크립트.

목적
----
어댑터(model_registry.py) 를 수정하기 전, Qwen3.5-9B 가 서버 GPU 에서
실제로 이미지 + 텍스트 추론을 수행할 수 있는지 단독 확인한다.

사용
----
    cd ~/backend
    python verify_qwen.py <image_path> [prompt]

확인 지점
--------
1. Processor / Model 로딩 성공 — AutoClass 우선, 실패 시 직접 클래스 import
2. bf16 + device_map=auto 적재 후 VRAM 점유량
3. chat_template.jinja 기반 메시지 토크나이즈 성공
4. generate 결과 텍스트가 이미지 내용을 반영하는지 (육안 확인)
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import torch
from PIL import Image

MODEL_DIR = Path.home() / "model" / "Qwen3.5-9B"


def main() -> None:
    if len(sys.argv) < 2:
        print("usage: python verify_qwen.py <image_path> [prompt]")
        sys.exit(1)

    image_path = Path(sys.argv[1])
    prompt = sys.argv[2] if len(sys.argv) >= 3 else "이 이미지에 보이는 내용을 한 문장으로 설명하라."

    if not MODEL_DIR.exists():
        print(f"model dir not found: {MODEL_DIR}")
        sys.exit(1)
    if not image_path.exists():
        print(f"image not found: {image_path}")
        sys.exit(1)

    # [1/4] Processor
    print(f"[1/4] loading processor from {MODEL_DIR}")
    t0 = time.time()
    try:
        from transformers import AutoProcessor
        processor = AutoProcessor.from_pretrained(str(MODEL_DIR))
    except Exception as e:
        print(f"      AutoProcessor failed ({type(e).__name__}: {e})")
        print(f"      fallback: from transformers import Qwen3VLProcessor")
        from transformers import Qwen3VLProcessor  # type: ignore[attr-defined]
        processor = Qwen3VLProcessor.from_pretrained(str(MODEL_DIR))
    print(f"      class={type(processor).__name__}  ({time.time()-t0:.1f}s)")

    # [2/4] Model
    print(f"[2/4] loading model (bfloat16, device_map=auto)")
    t0 = time.time()
    try:
        from transformers import AutoModelForImageTextToText
        model = AutoModelForImageTextToText.from_pretrained(
            str(MODEL_DIR), torch_dtype=torch.bfloat16, device_map="auto",
        )
    except Exception as e:
        print(f"      AutoModelForImageTextToText failed ({type(e).__name__}: {e})")
        print(f"      fallback: from transformers import Qwen3_5ForConditionalGeneration")
        from transformers import Qwen3_5ForConditionalGeneration  # type: ignore[attr-defined]
        model = Qwen3_5ForConditionalGeneration.from_pretrained(
            str(MODEL_DIR), torch_dtype=torch.bfloat16, device_map="auto",
        )
    model.eval()
    elapsed = time.time() - t0
    vram = torch.cuda.memory_allocated() / 1024**3 if torch.cuda.is_available() else 0
    print(f"      class={type(model).__name__}  ({elapsed:.1f}s)")
    print(f"      VRAM allocated: {vram:.2f} GiB")

    # [3/4] Input
    print(f"[3/4] preparing input")
    image = Image.open(image_path).convert("RGB")
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "image"},
                {"type": "text", "text": prompt},
            ],
        }
    ]
    text = processor.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True,
    )
    inputs = processor(
        text=[text], images=[image], return_tensors="pt", padding=True,
    ).to(model.device)
    print(f"      image size: {image.size}, input_ids shape: {tuple(inputs.input_ids.shape)}")

    # [4/4] Generate
    print(f"[4/4] generating (max_new_tokens=256, greedy)")
    t0 = time.time()
    with torch.inference_mode():
        out = model.generate(**inputs, max_new_tokens=256, do_sample=False)
    new_tokens = out[:, inputs.input_ids.shape[1]:]
    output_text = processor.batch_decode(new_tokens, skip_special_tokens=True)[0]
    elapsed = time.time() - t0
    n_new = new_tokens.shape[1]
    print(f"      generate: {elapsed:.1f}s, {n_new} new tokens ({n_new/max(elapsed,1e-6):.1f} tok/s)")

    print()
    print("=" * 60)
    print("PROMPT:", prompt)
    print("-" * 60)
    print(output_text)
    print("=" * 60)


if __name__ == "__main__":
    main()
