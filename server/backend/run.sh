#!/usr/bin/env bash
# 서버(JupyterHub)에서 backend + cloudflared Quick Tunnel 동시 기동.
# - 외부 노출은 cloudflared가 담당 → uvicorn은 loopback(127.0.0.1)에만 바인딩
# - cloudflared가 죽으면 자동 재시작(uvicorn은 살아 있으므로 진행 중 작업 보존)
#   단 trycloudflare URL은 재시작마다 새로 발급되므로 frontend의 backend URL 갱신 필요
set -u
PORT="${PORT:-8000}"
CLOUDFLARED_BIN="${CLOUDFLARED_BIN:-./cloudflared}"

cd "$(dirname "$0")"

if [ ! -x "$CLOUDFLARED_BIN" ]; then
    echo "[run] cloudflared not found at $CLOUDFLARED_BIN. Run 'bash bootstrap.sh' first." >&2
    exit 1
fi

if command -v ss >/dev/null 2>&1 && ss -ltn 2>/dev/null | grep -qE "[:.]${PORT}[[:space:]]"; then
    echo "[run] port ${PORT} already in use. Retry with: PORT=9000 bash run.sh" >&2
    exit 1
fi

uvicorn main:app --host 127.0.0.1 --port "$PORT" &
UVICORN_PID=$!

(
    while true; do
        "$CLOUDFLARED_BIN" tunnel --url "http://127.0.0.1:${PORT}"
        echo "[run] cloudflared exited; restarting in 5s. The trycloudflare URL will change — copy the new URL into the frontend .env after it prints. (Ctrl-C to stop)" >&2
        sleep 5
    done
) &
CF_LOOP_PID=$!

cleanup() {
    trap - EXIT INT TERM
    kill "$UVICORN_PID" 2>/dev/null || true
    pkill -P "$CF_LOOP_PID" 2>/dev/null || true
    kill "$CF_LOOP_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

# uvicorn이 죽으면 전체 종료(터널만 살아남는 상태를 방지)
wait "$UVICORN_PID"
