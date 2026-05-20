# project_gamma

VLM 기반 한글 손글씨 문서 인식 시연 시스템.
설계 문서는 `PLAN.md`, 통신 계약은 `SCHEMA.md`, 작업 기록은 `LOG.md` 참고.

```
project_gamma/
├── local/frontend/      # 로컬 UI (Vite + React)
└── server/backend/      # Jupyter Hub 서버 backend (FastAPI + cloudflared)
```

## 구동 절차

### 1) 서버 (Jupyter Hub 터미널)

JupyterHub 환경은 ephemeral이다 — 세션 재시작 시 `pip install`로 설치한 패키지가 모두 사라진다. 단 홈 디렉토리는 영속이므로 cloudflared 바이너리는 최초 1회만 다운로드된다. **세션 시작마다 `bootstrap.sh` 를 1회 실행**한다.

```bash
cd server/backend
bash bootstrap.sh            # 매 세션 1회: pip install --user + cloudflared 다운로드(최초 1회)
bash run.sh                  # 기본 포트 8000, 변경은 PORT=9000 bash run.sh
```

`run.sh` 가 `uvicorn` 과 `cloudflared` 를 같이 띄운다. cloudflared 로그에서 다음 형태의 줄을 찾아 URL을 복사한다.

```
https://<random>.trycloudflare.com
```

sudo / `/usr/local/bin` 등 시스템 경로는 사용하지 않는다. cloudflared 바이너리는 `server/backend/cloudflared` 로 받아 그 자리에서 실행한다.

> cloudflared가 일시적으로 끊기면 자동 재시작되며, 이때 **새 URL이 발급**된다. backend 작업 자체는 끊기지 않으니, 새 URL이 출력되면 frontend `.env` 만 갱신해 재접속하면 된다.

### 2) 로컬 (frontend)

```bash
cd local/frontend
npm install
cp .env.example .env
# .env 의 VITE_BACKEND_URL 을 위에서 복사한 trycloudflare URL 로 교체
npm run dev                  # http://localhost:5173
```

## 사용 흐름

1. 화면 상단에서 **Model** (현재 `Mock-Model`), **Device** 선택
2. **Upload Images** 로 이미지/PDF 업로드
3. **Analysis** 클릭 → 진행 중에는 버튼이 **Stop** 으로 전환
4. **Image List** 에서 항목 선택 → **Image Summary** 에서 예측값 수정
5. **Complete** 클릭 시 해당 이미지가 `done` 으로 바뀌고 **Preview** 시트에 누적

## 모델 추가

`server/backend/model_registry.py` 의 `_REGISTRY` 에 `predict(image_path, field_spec) -> list[FieldResult]`
시그니처의 함수를 등록하면 frontend/SCHEMA를 건드리지 않고 새 모델이 노출된다.

## 상태 저장 위치

- `server/data/state.db` — Job / 이미지 / 필드 결과 (SQLite)
- `server/data/uploads/` — 업로드된 원본 이미지

두 디렉터리는 backend 첫 기동 시 자동 생성된다.
