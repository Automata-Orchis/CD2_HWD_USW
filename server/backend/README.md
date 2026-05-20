# backend

FastAPI 기반 backend. 폐쇄망/Jupyter Hub 환경의 GPU 자원에서 모델을 돌리고, 로컬 frontend는 cloudflared가 발급한 공개 URL로 접근한다.

## 세션 셋업 (매 JupyterHub 세션 시작 시 1회)

```bash
bash bootstrap.sh
```

`bootstrap.sh` 는 멱등 스크립트이며 다음을 수행한다:

1. `pip install --user -r requirements.txt` — JupyterHub site-packages 쓰기 권한이 없는 환경 대비
2. `./cloudflared` (Linux amd64 바이너리)가 없으면 GitHub release에서 받아 실행권한 부여

JupyterHub는 ephemeral하다 — 세션 재시작 시 pip 설치는 모두 사라진다. 하지만 홈 디렉토리(이 프로젝트 포함)는 영속이므로 cloudflared 바이너리는 1회 다운로드 후 재사용된다. sudo / `/usr/local/bin` 등 시스템 경로는 사용하지 않는다.

## 기동

```bash
bash run.sh                 # 기본 포트 8000
PORT=9000 bash run.sh       # 포트 변경
```

`run.sh` 가 두 프로세스를 띄운다:

1. `uvicorn main:app --host 127.0.0.1 --port 8000` — 외부 노출은 cloudflared가 담당하므로 loopback에만 바인딩
2. `./cloudflared tunnel --url http://127.0.0.1:8000` — 죽으면 자동 재시작(작업 보존). 단 URL은 매번 새로 발급

cloudflared 로그에 다음 형태의 줄이 출력된다:

```
https://<random>.trycloudflare.com
```

이 URL을 로컬 `local/frontend/.env` 의 `VITE_BACKEND_URL` 에 넣는다. 자동 재시작 시 새 URL이 다시 출력되니 그때마다 갱신한다.

## 엔드포인트

`SCHEMA.md` 의 정의를 그대로 구현한다.

| Method | Path | 용도 |
|---|---|---|
| GET  | /models | 사용 가능한 모델 목록 |
| GET  | /devices | cpu/gpu 목록 |
| POST | /upload | 이미지 업로드 (multipart `files[]`) |
| GET  | /images/{image_id}/file | 업로드된 이미지 바이너리 |
| POST | /analyze | 잡 생성 + 백그라운드 추론 시작 |
| POST | /jobs/{job_id}/stop | 진행 중인 잡 중지 |
| GET  | /jobs/{job_id} | 잡 상태 + 이미지 목록 |
| GET  | /jobs/{job_id}/images/{image_id} | 이미지 요약 |
| PUT  | /jobs/{job_id}/images/{image_id} | 사용자 수정값 저장 |
| POST | /jobs/{job_id}/images/{image_id}/complete | 이미지 완료 처리 |
| GET  | /jobs/{job_id}/sheet | 시트 미리보기 |

## 데이터 저장

- 상태 DB : `server/data/state.db` (SQLite, 첫 기동 시 자동 생성)
- 업로드 이미지 : `server/data/uploads/`

## 모델 추가

`model_registry.py` 에 함수를 등록하면 frontend/SCHEMA를 건드리지 않고 새 모델을 노출할 수 있다.

```python
def _qwen_predict(image_path, field_spec):
    ...
    return [FieldResult(key=..., predicted=..., accuracy=..., edited=None), ...]

_REGISTRY["Qwen3.5-9B"] = _qwen_predict
```

현재는 `Mock-Model` 만 등록되어 있어 시연용 더미 응답을 반환한다.
