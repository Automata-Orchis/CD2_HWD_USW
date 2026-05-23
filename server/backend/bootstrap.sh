#!/usr/bin/env bash
# 매 JupyterHub 세션 시작 시 1회 실행. 멱등(idempotent).
# - pip 의존성을 --user 로 설치 (site-packages 쓰기 권한 없는 환경 대비)
# - cloudflared 바이너리가 없으면 GitHub release 에서 다운로드 (홈 영속, 1회로 충분)
# - Qwen3.5-9B weight 가 없으면 HuggingFace 에서 다운로드 (홈 영속, ~18 GiB)
# sudo / /usr/local/bin 등 시스템 경로는 사용하지 않는다.
set -eu
cd "$(dirname "$0")"

CLOUDFLARED_URL="https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64"
MODEL_DIR="${HOME}/model/Qwen3.5-9B"
TRANSFORMERS_TAG="v5.9.0"

# --- 1. PyPI 의존성 (API server + ML stack + cu121 torch wheel) ---
echo "[bootstrap] pip install --user -r requirements.txt"
python -m pip install --user --timeout 600 --retries 5 -r requirements.txt

# --- 2. transformers ${TRANSFORMERS_TAG} (qwen3_5 보유, FSDP2 회귀 없음. --no-deps 로 torch pin 보존) ---
if ! python -c "import transformers; assert transformers.__version__.startswith('5.9.')" 2>/dev/null; then
    echo "[bootstrap] installing transformers @ ${TRANSFORMERS_TAG} (--no-deps)"
    python -m pip install --user --force-reinstall --no-deps \
        --timeout 600 --retries 5 \
        "transformers @ git+https://github.com/huggingface/transformers.git@${TRANSFORMERS_TAG}"
else
    echo "[bootstrap] transformers $(python -c 'import transformers;print(transformers.__version__)') already installed — skip"
fi

# --- 3. cloudflared 바이너리 (없으면 wget) ---
if [ ! -x ./cloudflared ]; then
    echo "[bootstrap] downloading cloudflared from $CLOUDFLARED_URL"
    if command -v curl >/dev/null 2>&1; then
        curl -fL -o ./cloudflared "$CLOUDFLARED_URL"
    elif command -v wget >/dev/null 2>&1; then
        wget -O ./cloudflared "$CLOUDFLARED_URL"
    else
        echo "[bootstrap] neither curl nor wget available; download cloudflared manually to $(pwd)/cloudflared" >&2
        exit 1
    fi
    chmod +x ./cloudflared
fi

# --- 4. Qwen3.5-9B weight (부재 시에만 ~18 GiB 다운로드) ---
if [ ! -d "$MODEL_DIR" ] || ! ls "$MODEL_DIR"/*.safetensors >/dev/null 2>&1; then
    echo "[bootstrap] Qwen3.5-9B weights not found at $MODEL_DIR — downloading (~18 GiB)"
    HF_HUB_ENABLE_HF_TRANSFER=1 python -c "
from huggingface_hub import snapshot_download
snapshot_download(repo_id='Qwen/Qwen3.5-9B', local_dir='$MODEL_DIR')
"
else
    echo "[bootstrap] Qwen3.5-9B weights present at $MODEL_DIR — skip"
fi

# --- 5. 환경 fail-fast 검증 ---
echo "[bootstrap] cloudflared: $(./cloudflared --version 2>&1 | head -1)"
python -c "import torch, transformers; print(f'[bootstrap] torch {torch.__version__} / transformers {transformers.__version__}')"
echo "[bootstrap] done. Next: bash run.sh"
