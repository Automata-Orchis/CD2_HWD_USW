# Plan

이 문서는 프로젝트 진행을 위한 계획서다. 모든 작업은 이 문서를 기반으로 진행된다.

## 0. local / server 분리 원칙

**서버에서는 AI agent 사용이 불가하므로, 서버 측 파일들도 local 의 `server/` 폴더에 미러로 관리한다.**

- `local/` : frontend 와 로컬 환경 설정. 서버 backend 의 trycloudflare URL 로 접속한다.
- `server/` (local 미러) : backend / data / model. 실서버에는 `server/` 폴더 자체가 없으며 그 내용물이 홈 디렉토리(`~/backend`, `~/data`, `~/model`) 직하에 위치한다.
- 서버 사양 : RTX 4090 / 24 GiB VRAM (단일 GPU).

## 1. 목표

**VLM 을 활용하여 한글 손글씨가 작성된 문서로부터 손글씨를 정확히 인식하고 Excel 등의 결과물을 생성한다.**

- 인터넷이 차단된 폐쇄망에서 오픈소스 모델 활용을 가정한다.
- JupyterHub 를 통해 서버의 GPU(우선) 와 CPU 를 사용한다.
- 모델 추론만 다루며 모델 학습은 범위 밖이다.
- 여러 오픈소스 모델의 예측 결과를 Database 에 저장한다.

## 2. 작업 방향

**모델이 문서를 정확히 인식해 사람이 다량 문서를 수기로 옮기는 부담을 줄이는 것이 목적이다.**

레포 구성은 다음과 같다.

```
CD2_HWD_USW/
├── .gitattributes                # git 속성(라인엔딩 등)
├── .gitignore
├── CLAUDE.md                     # 코딩 행동 가이드
├── PLAN.md                       # 작업 계획 저장 (이 문서)
├── LOG.md                        # 작업 기록 저장
├── README.md                     # 시스템의 사용법 등의 기초 정보
├── SCHEMA.md                     # frontend ↔ backend ↔ model 데이터 스키마 정의
├── TODO.md                       # 현재 검증 사항 및 개선 항목
├── local/                        # 로컬에서 작동할 모든 것
│   └── frontend/                 # Vite + React 앱 (§3 레이아웃 구현)
│       ├── index.html
│       ├── package.json
│       ├── package-lock.json
│       ├── vite.config.js
│       ├── .env.example          # VITE_BACKEND_URL 템플릿 (.env 는 gitignore)
│       ├── .gitignore
│       ├── README.md
│       └── src/
│           ├── main.jsx          # 엔트리
│           ├── App.jsx           # Toolbar/ImageList/ImageView/ImageSummary/Preview 통합
│           ├── api.js            # backend 호출 래퍼 (SCHEMA.md 엔드포인트와 1:1)
│           └── styles.css
└── server/                       # 서버에서 작동할 모든 것
    ├── model/                    # model 파라미터는 서버에 저장되어 있으며, 로컬 환경에는 없다.
    │    └── Qwen3.5-9B/          # Qwen3.5-9B에 대한 필요 파일들이 저장되어 있다.
    ├── data/                     # 사전 적재 신청서 + SQLite 상태
    │   ├── state.db              # 런타임 생성 (applications/jobs/field_results 등)
    │   ├── <template_name>/      # 카테고리 폴더 — 관리자가 직접 생성·채움
    │   │   └── *.pdf | *.png     # 신청서 파일 1개 = application 1건
    │   └── original_data/        # 스캔 제외 — 원본 양식 보관용 reserved 폴더
    └── backend/                  # FastAPI 백엔드
        ├── main.py               # FastAPI 앱 진입점 (라우터 정의)
        ├── db.py                 # SQLite 초기화 및 상태 저장
        ├── schemas.py            # Pydantic 모델/Enum 정의
        ├── model_registry.py     # 모델 어댑터 레지스트리 (predict 인터페이스)
        ├── templates_io.py       # templates/*.yml 디스크 로더 (매 요청 재스캔)
        ├── categories.py         # data/<template>/ 스캔 + 인입 + 카테고리 통계
        ├── templates/            # 신청서 종류 정의 (yml 1개 = 1종류)
        │   ├── default.yml       # 기본 5필드
        │   └── direct_payment.yml # 직불금 신청서 14필드
        ├── verify_qwen.py        # Qwen3.5-9B GPU 단독 검증 스크립트
        ├── requirements.txt
        ├── bootstrap.sh          # 세션 1회 셋업 (멱등): pip --user, cloudflared 다운로드
        ├── run.sh                # uvicorn + cloudflared 무한 재시도 루프
        └── README.md
```

원칙은 다음과 같다.
- 뼈대 시스템을 두고, 서로 다른 모델의 입출력은 어댑터에서 통일한다.
- 시스템 관리를 위해 최대한 간결하게, 필요한 것만 작성한다.
- 필요에 따라 구성 요소가 추가·수정될 수 있다.

## 3. local — frontend

**frontend 는 작업자가 서버 사전 적재본 중에서 카테고리를 골라 작업하고 모델 결과를 확인·수정하는 화면이다.** 작업자는 파일을 업로드하지 않는다.

레이아웃은 다음과 같다.

```
	Model            Device                Work                 Analysis and Stop Button
┌──────────────┐ ┌──────────────┐ ┌──────────────────────┐ ┌───────────────────────┐
|              | |              | |                      | | ┌──────────┐ ┌──────┐ |
| Select Model | | CPU □  GPU □ | | 작업 선택 (현재 카테고리) | | | Analysis | | Stop | |
|              | |              | |                      | | └──────────┘ └──────┘ |
└──────────────┘ └──────────────┘ └──────────────────────┘ └───────────────────────┘
	Dashboard (작업 선택 클릭 시 표시)
┌──────────────────────────────────────────────────────────────────────────────────────┐
| ┌────────────────────────┐  ┌────────────────────────┐  ┌────────────────────────┐  |
| | 직불금 신청서             |  | 주택신고서                |  | 기본 (5필드)             |  |
| | 총 12 · 완료 3 · 미완료 9 |  | 총 0 · 완료 0 · 미완료 0  |  | 총 5 · 완료 5 · 미완료 0 |  |
| | 작업률 25%               |  | 작업률 0%                |  | 작업률 100%             |  |
| | [▓▓▓░░░░░░░░░░░░░░]    |  | [░░░░░░░░░░░░░░░░░░░░]  |  | [▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓]  |  |
| └────────────────────────┘  └────────────────────────┘  └────────────────────────┘  |
└──────────────────────────────────────────────────────────────────────────────────────┘
	Application List      Image                Application Summary
┌───────────────────┐ ┌────────────────┐  ┌─────────────────────────────────────────────────────────────┐
| App 1 - Done      │ |                |  │ Full Name: [Predicted Answer] [Accuracy]                    |
| App 2 - Working   │ | Working Image  |  | Account No. (Bank Name): [Predicted Answer] [Accuracy]      |
| App 3 -           │ | in Now         |  | Resident Registration Number: [Predicted Answer] [Accuracy] |
| ...               │ |                |  | ...                                                         |
└───────────────────┘ └────────────────┘  └─────────────────────────────────────────────────────────────┘
 Complete Button
┌──────────┐
| Complete |
└──────────┘
	Preview
┌───────────────────────────────────────┐
| Update Documet like Exel in real-time |
└───────────────────────────────────────┘
 ...
```

초기 화면 컨트롤은 다음과 같다.
- **Model** : 사용 가능한 모델 중 택일 (`/models`).
- **Device** : CPU / GPU 선택 (현재 실 라우팅은 GPU 고정 — 어댑터가 `device_map="auto"` 사용).
- **작업 선택** : 클릭 시 하단 Dashboard 토글. 현재 카테고리가 있으면 버튼 라벨에 표시.
- **Analysis / Stop** : 분석 시작 / 중지 (분석 중 토글).

Dashboard 는 다음과 같다.
- 카테고리(=template) 별 Sub Box. `server/data/<template>/` 폴더에 대응.
- 각 Sub Box : 카테고리 label, 총 / 완료 / 미완료 건수, 작업률 (%) + 진행 막대.
- 완료 판정은 backend DB 의 `applications.status='done'` 기준. 작업자가 Complete 한 신청서만 done.
- Sub Box 클릭 → 해당 카테고리의 신청서들이 Application List 에 로드 + `template_name` 자동 설정. 카테고리가 바뀌면 진행 중이던 작업 상태(jobId / 시트 누적) 초기화.

작업 진행 중 표시되는 영역은 다음과 같다.
- **Application List** : 선택된 카테고리의 신청서 목록과 상태(Working / Done). 클릭으로 해당 신청서 작업 화면 전환, 이미 done 인 신청서의 기록은 그대로 표시된다.
- **Image** : 선택된 신청서의 현재 페이지. 다중 페이지면 ◀ ▶ 네비 제공. 줌·팬·미니맵 지원.
- **Application Summary** : 선택된 신청서의 예측값. 사용자 편집 가능.
- **Complete** : 현재 신청서를 Done 처리하고 다음 신청서로 이동.
- **Preview** : Done 처리된 신청서를 Excel 같은 시트 형태로 누적 표시.

backend 와의 연결은 다음과 같다.
- 작업 선택 → `/work-categories` 로 카테고리 통계 조회 (매 호출 시 디스크 재스캔).
- 카테고리 선택 → `/applications?template_name=...` 로 해당 카테고리 신청서 목록 조회.
- Analysis → 선택된 model / device / template + application_ids 로 분석 작업 시작.
- Stop → 모든 작업 중지 신호 (진행 중이던 신청서의 비-done 결과는 폐기됨).
- 폴링으로 작업 상태와 시트를 받아 화면 갱신.
- 사용자 수정 / Complete 시 backend 에 저장 요청. 디스크 원본 파일은 그대로 유지.

## 4. server — backend

**backend 는 frontend 신호를 받아 모델을 활성화하고 모델 출력을 frontend 에 변환·전달한다.**

기본 흐름은 다음과 같다.

```
get information from frontend → set environment → use model → transform model output to frontend
```

요구 사항은 다음과 같다.
- 모델의 추가·삭제·교체가 자유로워야 한다 — `model_registry.py` 의 `_REGISTRY` 에 `predict(image_paths, field_spec, fewshot) -> list[FieldResult]` 시그니처 함수 등록.
- 모델은 JupyterHub 서버의 GPU 를 사용한다.
- 서로 다른 모델 출력을 통일하여 frontend 에 전달한다 — 어댑터가 결과를 `list[FieldResult]` 로 정규화.
- 작업 단위는 신청서(application). 한 신청서는 1장(이미지) 또는 N장(PDF 분할)의 페이지로 구성되며, 모델은 모든 페이지를 한 번에 보고 단일 결론을 산출한다.

## 5. server — data

**`~/data/` (local 미러 : `server/data/`) 는 사전 적재 신청서 + SQLite 상태 저장소다. 신청서 폴더는 관리자가 직접 생성·채우고, `state.db` 는 backend 첫 기동 시 자동 생성된다.**

- `state.db` : applications / jobs / job_applications / field_results 테이블.
- `<template_name>/` : 카테고리(=신청서 종류) 폴더. 폴더명은 `server/backend/templates/<name>.yml` 의 파일 stem 과 동일. 안에는 PDF / 이미지가 평면으로 놓이며, 각 파일 = application 1건. 신청서 개수가 늘어나도 폴더는 카테고리 수만큼만 유지된다.
- `original_data/` : 원본 양식 등 작업 대상이 아닌 자료. `categories._RESERVED_DIRS` 로 스캔에서 명시적 제외.
- PDF 페이지는 디스크 캐시 없이 요청 시 `pypdfium2` 로 즉석 렌더링한다 (신청서당 폴더가 추가로 생기지 않는다).

## 6. server — model

**`~/model/` (local 미러 : `server/model/`) 은 VLM 파라미터 저장소다. 로컬에는 비어 있고 서버 홈에만 실제 weight 가 존재한다.**

- 현재 운용 모델 : `~/model/Qwen3.5-9B/` — bf16 ≈ 18 GiB, RTX 4090 24 GiB 에 단일 적재.
- 신규 모델 추가 : `~/model/<모델명>/` 배치 + `model_registry.py` 에 어댑터 등록.
- 폐쇄망 가정 — `bootstrap.sh` 가 `huggingface_hub.snapshot_download` 로 weight 부재 시 자동 다운로드, 홈 영속성 덕분에 1회 후 재사용된다.

## 7. JupyterHub 운영 환경

**JupyterHub 서버는 권한이 제한된 ephemeral 환경이며, 외부에서 backend 에 접근하기 위해 Cloudflare Quick Tunnel 을 우회책으로 사용한다.**

(출처: ChatGPT 대화 "JupyterHub FastAPI 구동", 공유 링크 `6a0d7a45-f7c8-83a5-a953-00196f7dc806` 의 내용을 정리)

### 7.1 환경 제약

- **컨테이너성 환경** — 세션 단위로 컨테이너가 재시작되며, `pip install --user` 패키지를 포함한 site-packages 추가 설치는 모두 초기화된다.
- **홈 디렉토리(`~/`)는 영속** — 프로젝트 파일, 영구 바이너리, 모델 weight, `~/.local/`·`~/.cloudflared/` 사용자 설정은 살아남는다.
- **sudo 등 관리자 권한 사용 불가** — `/usr/local/bin` 등 시스템 경로 쓰기 불가.
- **외부 포트 노출 차단** — JupyterHub 의 `/user/<u>/proxy/<port>/` 는 인증 redirect 로 HTML 로그인 페이지 또는 404 를 반환. `jupyter-server-proxy` 활성화도 실행 중인 Jupyter Server 재시작 불가로 반영되지 않음 → 실질적으로 사용 불가.
- **사전 설치된 외부 노출 도구 없음** — `cloudflared` 는 바이너리(`cloudflared-linux-amd64`)를 직접 받아 홈에서 실행하는 방식만 사용 가능 (홈 영속성으로 1회 다운로드 후 재사용).

### 7.2 검증된 내부 동작

- `uvicorn` 0.0.0.0:8000 정상 바인딩.
- `curl http://127.0.0.1:8000/health` → FastAPI 정상 JSON 응답.
- 서버 프로세스 / 포트 / Python 환경 / loopback 네트워크 모두 정상.

### 7.3 외부 노출 — Cloudflare Quick Tunnel

명령 : `./cloudflared-linux-amd64 tunnel --url http://localhost:8000`. 실행 시 매번 새로운 `*.trycloudflare.com` URL 이 발급된다.

특성과 한계:
- 인증 없음, 누구나 접근 가능 → 민감 데이터 주의, 개발/테스트 단계 한정.
- 실행할 때마다 URL 이 바뀜 → frontend `.env` 의 `VITE_BACKEND_URL` 매번 갱신.
- 경로 지연 : `frontend → Cloudflare → tunnel → backend` (대부분의 지연은 inference 자체).

검증 절차:
1. `curl https://<발급URL>/health` → JSON 응답 확인.
2. 브라우저로 `https://<발급URL>/docs` → Swagger UI 확인.

### 7.4 CORS 설정

브라우저에서 tunnel URL 로 fetch 호출 시 CORS 차단을 피하기 위해 FastAPI 에 다음 미들웨어가 필요하다.

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # 개발 단계에서만, 운영 단계에서는 origin 제한
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### 7.5 아키텍처

```
[원격 JupyterHub 서버]                              [로컬 PC]
- GPU (RTX 4090, 24 GiB)                            - frontend 실행
- VLM / 모델 추론                              ←→   - backend API 호출 (tunnel URL)
- FastAPI backend (127.0.0.1:8000)
- cloudflared Quick Tunnel
        ↓ 외부 노출
  https://<random>.trycloudflare.com
```

### 7.6 운영 정책

- **Quick Tunnel + URL 변경 수용** — Named Tunnel(고정 URL) 의 도메인 등록·계정 셋업 부담을 회피.
- **cloudflared 자동 재시작** — `run.sh` 의 무한 재시도 루프. cloudflared 가 죽어도 uvicorn 은 살아 진행 중인 추론과 SQLite 저장을 이어간다. URL 만 새로 발급됨.
- **세션 셋업은 `bootstrap.sh` 일원화** — 멱등 스크립트로 매 세션 1회 실행. pip 는 `--user`, cloudflared 와 모델 weight 는 홈 영속성 활용.
- **운영용 파일은 `data/` 밖에 둔다** — `data/` 는 모델 테스트 데이터/결과 전용. cloudflared URL 같은 운영 정보는 표준 출력(터미널 로그)으로만 노출.
- **uvicorn 은 `127.0.0.1` 바인딩** — 외부 노출은 cloudflared 가 담당. 같은 노드 내 타 사용자 노출 가능성 차단.

### 7.7 알려진 한계

- 인증이 없는 공개 URL 이므로 실험/시연 외 사용 비권장. 장기 운영은 Named Tunnel + 도메인 + 인증 전환 필요.
- `/proxy/<port>/` 경로는 사실상 사용 불가로 간주, 외부 접근은 Cloudflare Tunnel 만 신뢰.
- cloudflared 자동 재시작은 단순 무한 루프 — 바이너리 손상이나 영구 네트워크 단절 시 재시작이 반복되며 사용자 로그 확인이 필요하다.

## 8. 다중 페이지 신청서

**한 사람의 신청서는 여러 페이지로 존재할 수 있다. 시스템은 그 페이지들을 하나의 신청서로 취합하여 단일 결론을 산출해야 한다.**

현재 구현은 **PDF 1파일 = N페이지 신청서 1건** 형태만 다룬다.
- PDF 파일 1개 (`server/data/<template>/foo.pdf`) = N페이지 신청서 1건. 페이지 수는 `pypdfium2.PdfDocument(...)` 로 인입 시점에 산출해 `applications.page_count` 에 기록.
- 이미지 파일 1개 (`server/data/<template>/foo.png|jpg|jpeg`) = 1페이지 신청서 1건.
- 모델은 신청서의 모든 페이지를 한 번의 `generate` 호출로 받아 단일 JSON 결과 산출.
- `/applications/{aid}/pages/{ord}/file` 호출 시 PDF 는 즉석 렌더링, 이미지는 원본 직접 서빙.
- `_run_job` 은 PDF 신청서를 `tempfile.TemporaryDirectory()` 에 페이지별 PNG 로 풀어 모델에 전달하고, predict 종료 시 자동 정리한다.

향후 작업 — 여러 이미지 파일을 "하나의 신청서"로 그룹핑하는 UX (TODO 항목):
- 현재는 1 파일 = 1 신청서 라 다중 이미지(예: 휴대폰 카메라 N장)를 한 신청서로 묶을 방법이 없다.
- 옵션 : 폴더 내 prefix 컨벤션(`홍길동_1.png`, `홍길동_2.png` 가 하나의 신청서) 또는 sub-sub-folder 허용(`server/data/<template>/<applicant>/*.png` 한 응답자 = 한 폴더). 후자는 "신청서 종류만큼만 폴더" 원칙과 절충 필요.

## 9. 개선점

**필요**
- 작업을 중간에 정지할 수 있어야 하며, 그 때까지의 작업 기록이 남아 있는 기능.
- 이미지와 요약본을 쉽게 비교할 수 있는 기능 (이미지가 너무 작거나 비교하기 불편한 점 등).

**고려**
- 작업 결과를 저장할 파일을 선택해 기존 기록에 이어 새 기록을 저장하는 기능.
- 작업 결과를 새로운 학습 데이터로 저장·활용하는 시스템 (작업을 진행할수록 모델 발전 가능).
- Excel 등 sheet 작업물 이외의 형태로 저장하는 기능.
