# frontend

Vite + React 기반 로컬 UI. PLAN.md §3 레이아웃을 구현한다.

## 사전 준비

Node.js 18 이상.

```bash
cd local/frontend
npm install
cp .env.example .env
# .env 의 VITE_BACKEND_URL 을 cloudflared 가 출력한 trycloudflare URL 로 바꾼다.
```

## 개발 서버

```bash
npm run dev   # http://localhost:5173
```

## 백엔드 연결

`.env` 의 `VITE_BACKEND_URL` 만 바꾸면 된다. 서버에서 `bash server/backend/run.sh` 를 띄우면 cloudflared 로그에
`https://<random>.trycloudflare.com` 형태의 줄이 찍히는데, 그 값을 그대로 넣는다.

## 구성

- `src/App.jsx` — Toolbar / ImageList / ImageView / ImageSummary / Preview 모두 한 파일
- `src/api.js` — backend 호출 래퍼 (SCHEMA.md 의 엔드포인트와 1:1)
- 잡 진행 상태와 이미지 요약은 1초 간격 폴링으로 갱신
- 추출 필드는 `App.jsx` 의 `DEFAULT_FIELD_SPEC` 으로 정의 — 다른 문서 종류라면 이 배열만 바꾸면 된다
