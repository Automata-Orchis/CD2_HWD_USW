# Plan

이 문서는 특정 프로젝트 진행을 위해 작성된 계획서다. 모든 작업은 이 문서를 기반으로 진행된다. 

## 0. local과 server의 분리에 대하여

**서버에서는 ai agent 사용이 불가하여, 불가피하게 local 환경에서 해당 파일들이 작성된다.**

현 프로젝트는 Jupyter hub 상의 서버와 loacl 환경의 연결을 기반으로 한다. 

서버에 대한 것은 아래와 같다. 
- 대용량 모델인 VLM 파라미터, 이미지 및 라벨 등의 data, backend가 저장되어 있다. 
- 서버의 사양은 RTX 4090, 24GiB이다. 
- 서버에서는 ai agent 사용이 불가하여, 부득이하게 현 로컬 환경에 `server/` 폴더 하에 미러로 작성된다. 

로컬에 대한 것은 아래와 같다. 
- 현 로컬 환경에 대한 것은 `server/` 폴더와의 분리를 위해 `local/` 폴더 하에 작성된다. 
- frontend나 환경 설정 등이 저장되며, 서버 상의 backend와 연결되어야 한다. 

## 1. 목표에 대하여

**VLM을 활용하여 한글 손글씨가 작성된 문서로부터 손글씨를 정확히 인식하여 Exel 등의 결과물을 생성하라.**

목표에 대한 참고 사항은 아래와 같다.
- 보안을 위해 인터넷이 차단된 폐쇄망 환경에서의 오픈소스 모델 활용을 가정한다. 
- `Jupyter hub`를 통해 서버의 `CPU`와 `GPU`를 사용해야 한다. 우선되는 것은 `GPU`다.
- 모델의 추론이 정상적으로 이루어지는 것이 목적이다. 모델의 학습은 계획에 없다. 
- 여러 오픈소스 모델의 예측과 그 정확도 등의 테스트를 진행, 그 결과는 `Database`에 저장되어야 한다. 

## 2. 작업 방향에 대하여

**이 작업은 모델이 문서를 정확히 인식하여, 사람이 다량의 문서를 읽고 텍스트를 작성하는 부담을 줄이는 데에 있다.**

작업의 기본 구성은 다음과 같다
```
project_gamma/
├── .gitignore
├── CLAUDE.md
├── PLAN.md                                    # 작업 계획 저장
├── LOG.md                                     # 작업 기록 저장
├── README.md                                  # 시스템의 사용법 등의 기초 정보
├── local/									   # 로컬에서 작동할 모든 것
│	└── frontend/
└── server/									   # 서버에서 작동할 모든 것
	├── model/								   # model 파라미터는 서버에 저장되어 있으며, 로컬 환경에는 없다.
	│	└── Qwen3.5-9B/						   # Qwen3.5-9B에 대한 필요 파일들이 저장되어 있다. 
	├── data/
	└── backend/
```

고려 사항은 다음과 같다. 
- 뼈대가 되는 시스템이 존재해야하며, 서로 다른 모델의 입출력은 그에 맞춰 적절히 변환되어야 한다. 
- 시스템 관리를 위해 최대한 간결하게, 필요한 것만을 작성해야 한다. 

모든 작업은 위와 같은 구성 요소를 기반으로 진행된다. 이후 작업을 진행하며 필요에 의해 추가적으로 생성되거나 수정될 수 있다. 

## 3. frontend에 대하여

**frontend에서는 사용자가 이미지를 쉽게 전달하고 결과를 쉽게 확인하며 그 결과를 쉽게 수정할 수 있어야 한다.**

frontend의 구성 및 설명은 아래와 같다.
```
	Model            Device          Upload Images or PDFs      Analysis and Stop Button
┌──────────────┐ ┌──────────────┐ ┌───────────────────────┐ ┌───────────────────────┐
|              | |              | |                       | | ┌──────────┐ ┌──────┐ |
| Select Model | | CPU □  GPU □ | | Select Images or PDFs | | | Analysis | | Stop | |
|              | |              | |                       | | └──────────┘ └──────┘ |
└──────────────┘ └──────────────┘ └───────────────────────┘ └───────────────────────┘
	Image List           Image                Image Summary                                                 
┌───────────────────┐ ┌────────────────┐  ┌─────────────────────────────────────────────────────────────┐
| Image 1 - Done    │ |                |  │ Full Name: [Predicted Answer] [Accuracy]                    |
| Image 2 - Working │ | Working Image  |  | Account No. (Bank Name): [Predicted Answer] [Accuracy]      |
| Image 3 -         │ | in Now         |  | Resident Registration Number: [Predicted Answer] [Accuracy] |
| Image 4 -         │ |                |  | Address: [Predicted Answer] [Accuracy]                      |
| ...               │ |                |  | Phone Number: [Predicted Answer] [Accuracy]                 |
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
초기 화면에 띄워질 것은 아래와 같다.  
- "Model" : 사용 가능한 모델 중 택일
- "Device" : 분석 환경 (CPU or GPU) 설정
- "Image Upload Button" : 둘 이상의 이미지 등록
- "Analysis Button"
		- Model, Device, Image Upload Button의 선택이 완료되면 활성화되며, 지정된 설정으로 작업이 실시 
		- 작업이 진행 중이면 해당 버튼은 Stop Button으로 바뀐다.
- "Stop Button" : 진행중인 작업을 중지한다. 이후 Analysis Button으로 바뀐다. 

작업이 진행될 경우 아래의 구성이 나타난다. 
- "Image List" : 전달받은 이미지 목록과 함께 각 이미지의 상태가 뜬다. 
		- 상태 : 작업 종료(Done), 작업 중(Working), 미작업(Blank)
		- 이미지 목록을 클릭하면 해당 이미지의 작업 화면을 띄울 수 있다. 이미 진행된 작업의 경우 그 작업 기록이 뜬다.
- "Image" : 현재 선택된 이미지
- "Image Summary" : 현재 선택된 이미지의 요약본. Predicted Answer의 수정이 가능. 
- "Complete Button" : 현재 선택된 이미지의 작업이 완료되었을 때 누르는 확인 버튼. 
		- 해당 버튼을 누르면 Image List에서 현재 이미지 상태가 Working에서 Done으로 바뀐 뒤, 다음 이미지로 넘어간다.
- "Preview" : Done으로 처리된 이미지의 정보를 저장했을 때의 결과물을 실시간으로 보여주는 화면이다. 
		- Exel과 같은 sheet 형태로 결과물을 저장한다고 가정한다.

backend와의 연결은 다음과 같다.
- `Image Upload Button` 클릭 시, 선택된 여러 개의 이미지 경로를 backend로 전달한다. 
- `Analysis Button` 클릭 시, 선택된 `Model`, `Device`를 전달해 분석 환경을 전달한다. 
- `Stop Button` 클릭 시, backend에 모든 작업을 중지하라고 신호를 전달한다. 
- 전달받은 이미지에 대한 모델 출력을 적절히 정제한 backend의 신호를 받아 화면에 띄운다. 
- 작업자가 각 이미지에 대하여 작업한 기록을 backend에 전달하여 효율적으로 저장한다. 

## 4. backend에 대하여

**backend는 frontend의 신호를 받아들여 모델을 적절히 활성화하고, 모델 출력을 frontend에 적절히 변환하여 전달한다.**

backend의 기본적인 흐름은 다음과 같다. 
```
get information from frontend → set environment → use model → transform model output to frontend
```

backend의 요구 사항은 아래와 같다. 
- model의 추가나 삭제, 그리고 교체가 자유로워야 한다. 
- model은 Jupyter hub를 통해 제공되는 서버의 GPU를 사용해야 한다. 
- 서로 다른 모델 출력을 통일시킨 뒤 적절히 변환하여 frontend에 전달해야 한다. 

## 5. 개선점에 대하여
필요
- 작업을 중간에 정지할 수 있어야 하며, 그 때까지의 작업 기록이 남아있는 기능
- 이미지와 요약본 이미지를 쉽게 비교할 수 있는 기능 (이미지가 너무 작거나 비교하기 불편한 점 등)

고려
- 작업 결과물을 저장할 파일을 선택하여, 저장된 기록에 이어 새로운 기록을 저장하는 기능
- 작업의 결과물을 새로운 학습 데이터로 저장하고 활용할 수 있는 시스템 (작업을 진행할 수록 모델 발전 가능)
- Exel 등의 sheet 작업물 이외의 형태로 저장하는 기능

## 6. 현재 서버 상황에 대하여

**JupyterHub 서버는 권한이 제한된 ephemeral 환경이며, 외부에서 backend에 접근하기 위해서는 Cloudflare Quick Tunnel을 우회책으로 사용한다.**

(출처: ChatGPT 대화 "JupyterHub FastAPI 구동", 공유 링크 `6a0d7a45-f7c8-83a5-a953-00196f7dc806` 의 내용을 정리)

### 6.1 환경 및 제약
- **JupyterHub 기반 컨테이너성 환경.** 세션 단위로 컨테이너가 재시작되며, 재시작 시:
    - `pip install`로 설치한 패키지 등 **컨테이너 site-packages 상의 모든 추가 설치는 초기화**된다.
    - 그러나 **홈 디렉토리(`~/`)는 영속이다.** 홈 안의 파일(이 프로젝트도 홈에 두는 것을 전제로 한다), 영구 보관용 바이너리, `~/.local/`·`~/.cloudflared/` 같은 사용자 설정은 살아남는다.
- **sudo 등 관리자 권한 사용 불가.** `/usr/local/bin` 등 시스템 경로 쓰기 불가.
- **외부 포트 노출이 막혀 있다.** JupyterHub의 `/user/<username>/proxy/<port>/` 경로는 인증 redirect로 인해 HTML 로그인 페이지를 반환하거나 404를 돌려준다. `jupyter-server-proxy`를 `jupyter server extension enable --py jupyter_server_proxy`로 활성화해도 **이미 실행 중인 Jupyter Server에는 반영되지 않으며**, 재시작이 불가능하므로 이 경로는 실질적으로 사용할 수 없다.
- **사전 설치된 외부 노출 도구가 없다.** `cloudflared`는 기본 설치되어 있지 않고, 바이너리(`cloudflared-linux-amd64`)를 직접 받아서 실행하는 방식으로만 사용 가능하다. 홈 영속성 덕분에 1회 다운로드 후 재사용된다.

### 6.2 검증된 동작 (서버 내부)
- `uvicorn`은 `0.0.0.0:8000`으로 정상 바인딩된다.
- 서버 내부에서 `curl http://127.0.0.1:8000/health` 시 FastAPI의 정상 JSON 응답(`{"status":"ok"}`)이 돌아온다.
- FastAPI 애플리케이션, Uvicorn, 포트 바인딩, Python 환경, 내부 loopback 네트워크 모두 정상.
- 즉 **"서버 프로세스가 떠 있는가"** 관점에서는 문제 없음.

### 6.3 채택한 외부 노출 방식 — Cloudflare Quick Tunnel
- **명령:** `./cloudflared-linux-amd64 tunnel --url http://localhost:8000`
- 실행 시 매번 새로운 `*.trycloudflare.com` ephemeral URL이 발급된다.
- **특성과 한계:**
    - 인증 없음, 누구나 접근 가능 → 민감 데이터 주의, 개발/테스트 단계에서만 사용
    - 실행할 때마다 URL이 바뀌므로, frontend는 해당 URL을 매번 갱신해야 한다.
    - latency: `frontend → Cloudflare → tunnel → backend` 경로로 약간의 지연이 추가된다 (대부분의 지연은 inference 자체에서 발생).
- 검증 절차:
    1. `curl https://<발급URL>/health` → JSON 응답 확인
    2. 브라우저로 `https://<발급URL>/docs` → Swagger UI 확인

### 6.4 backend(FastAPI) 측 필수 설정 — CORS
브라우저에서 tunnel URL로 fetch 호출 시 CORS 차단을 피하기 위해 FastAPI에 다음 미들웨어가 필요하다.

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

### 6.5 확정된 아키텍처
```
[원격 JupyterHub 서버]                              [로컬 PC]
- GPU (RTX 4090, 24 GiB)                            - frontend 실행
- VLM / 모델 추론                              ←→   - backend API 호출 (tunnel URL)
- FastAPI backend (127.0.0.1:8000)
- cloudflared Quick Tunnel
        ↓ 외부 노출
  https://<random>.trycloudflare.com
```

### 6.6 운영 정책 / 알려진 이슈

**채택된 정책:**
- **Quick Tunnel + URL 변경 수용.** Named Tunnel(고정 URL)은 도메인 등록·계정 셋업 부담이 있어 채택하지 않는다. 사용자는 cloudflared 로그에 출력되는 새 URL을 frontend `.env` 의 `VITE_BACKEND_URL` 에 그때마다 복사해 사용한다.
- **cloudflared 자동 재시작.** `run.sh` 가 cloudflared를 무한 재시도 루프로 띄운다 — cloudflared가 죽어도 uvicorn(backend)은 그대로 살아서 진행 중인 추론 작업과 SQLite 저장을 이어간다. 단 trycloudflare URL은 재시작마다 새로 발급되므로 frontend 측에서 URL 갱신만 하면 결과를 누락 없이 받을 수 있다.
- **세션 셋업은 `server/backend/bootstrap.sh` 로 일원화.** 멱등 스크립트로 매 세션 1회 실행. pip 의존성은 `--user` 로 설치한다(컨테이너 site-packages는 쓰기 권한이 없을 수 있음). cloudflared 바이너리는 1회 다운로드 후 홈 영속성에 의해 재사용된다.
- **운영용 파일은 `server/data/` 밖에 둔다.** `server/data/` 는 모델 테스트 데이터와 결과 저장 전용이다. cloudflared URL 같은 운영 정보는 표준 출력(터미널 로그)으로만 노출하고 별도 파일에 저장하지 않는다.
- **uvicorn은 `127.0.0.1` 에만 바인딩한다.** 외부 노출은 cloudflared가 담당하므로 `0.0.0.0` 이 불필요하며, 같은 노드 내 다른 사용자에 대한 노출 가능성을 배제한다.

**알려진 한계:**
- 인증이 없는 공개 URL이므로 실험·시연 단계 외의 사용은 권장하지 않는다. 장기 운영이 필요하면 Named Tunnel + 도메인 + 인증으로의 전환이 필요.
- `/proxy/<port>/` 경로는 현재 환경에서 사실상 사용 불가로 간주하고, 외부 접근은 Cloudflare Tunnel만 신뢰한다.
- cloudflared 자동 재시작은 단순 무한 루프이므로, 바이너리 자체가 깨졌거나 네트워크가 영구 불통인 경우 재시작이 반복된다. 비정상 상황 인지는 사용자가 로그를 보고 판단해야 한다.