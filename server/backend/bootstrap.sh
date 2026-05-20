#!/usr/bin/env bash
# 매 JupyterHub 세션 시작 시 1회 실행. 멱등(idempotent).
# - pip 의존성을 --user로 설치 (site-packages 쓰기 권한이 없는 환경 대비)
# - cloudflared 바이너리가 없으면 GitHub release에서 다운로드 (홈 영속이므로 1회로 충분)
# sudo / /usr/local/bin 등 시스템 경로는 사용하지 않는다.
set -eu
cd "$(dirname "$0")"

CLOUDFLARED_URL="https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64"

echo "[bootstrap] pip install --user -r requirements.txt"
pip install --user -r requirements.txt

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

echo "[bootstrap] cloudflared: $(./cloudflared --version 2>&1 | head -1)"
echo "[bootstrap] done. Next: bash run.sh"
