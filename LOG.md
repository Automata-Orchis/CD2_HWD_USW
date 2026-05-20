# Log

## 2026-05-20

- 공통 I/O 스키마 정의 시작점으로 채택. PLAN.md §2의 "뼈대" 요구사항과 §4의 "모델 출력 통일" 요구사항을 충족하기 위해 frontend/backend/model이 공유할 데이터 계약을 먼저 확정.
- `SCHEMA.md` 작성. FastAPI 기반 HTTP/JSON 계약. 추출 필드는 `field_spec`으로 분석 요청 시 가변 명세 (PLAN.md의 5개 필드는 하드코딩하지 않음).
- 시연용 골격 추가. `server/backend/` (FastAPI + SQLite + Mock 모델 + cloudflared `run.sh`) 와 `local/frontend/` (Vite + React, SCHEMA.md 의 모든 엔드포인트와 1:1 wiring) 작성. 실제 VLM 호출은 `model_registry.py` 의 `_REGISTRY` 에 어댑터를 추가하는 방식으로 후속 작업.
