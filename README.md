# project_gamma

VLM 기반 한글 손글씨 문서 인식 시연 시스템.
설계 문서는 `PLAN.md`, 통신 계약은 `SCHEMA.md`, 작업 기록은 `LOG.md` 참고.

레포 트리(로컬 작업용):

```
project_gamma/
├── local/
│   └── frontend/                 # 로컬 UI (Vite + React)
└── server/                       # JupyterHub 서버 측의 미러 (prefix는 로컬 분리용)
    ├── model/                    # VLM 파라미터 (예: Qwen3.5-9B) — 실제 파일은 서버에만 존재
    ├── data/                     # SQLite + 업로드 이미지 (backend 첫 기동 시 자동 생성)
    └── backend/                  # FastAPI + cloudflared
```

서버 배치(JupyterHub 홈, 영속): `server/` 폴더 자체는 로컬 분리용이므로 서버에는 존재하지 않는다. 그 **내용물**을 홈 직하에 둔다.

```
~/
├── backend/                      # 로컬의 server/backend/ 내용
├── data/                         # backend 첫 기동 시 자동 생성
└── model/
    └── Qwen3.5-9B/               # VLM 파라미터
```

## 구동 절차

### 1) 서버 (Jupyter Hub 터미널)

JupyterHub 환경은 ephemeral이다 — 세션 재시작 시 `pip install`로 설치한 패키지가 모두 사라진다. 단 홈 디렉토리는 NFS 영속이므로 cloudflared 바이너리와 Qwen3.5-9B 모델 weight 는 최초 1회만 다운로드된다. **세션 시작마다 `bootstrap.sh` 를 1회 실행**한다.

```bash
cd ~/backend
bash bootstrap.sh            # 매 세션 1회: pip install --user + transformers v5.9.0 git pin + cloudflared/모델 weight 자동 복원
bash run.sh                  # 기본 포트 8000, 변경은 PORT=9000 bash run.sh
```

`run.sh` 가 `uvicorn` 과 `cloudflared` 를 같이 띄운다. cloudflared 로그에서 다음 형태의 줄을 찾아 URL을 복사한다.

```
https://<random>.trycloudflare.com
```

sudo / `/usr/local/bin` 등 시스템 경로는 사용하지 않는다. cloudflared 바이너리는 `~/backend/cloudflared` 로 받아 그 자리에서 실행한다.

> cloudflared가 일시적으로 끊기면 자동 재시작되며, 이때 **새 URL이 발급**된다. backend 작업 자체는 끊기지 않으니, 새 URL이 출력되면 frontend `.env` 만 갱신해 재접속하면 된다.

### 2) 로컬 (frontend)

```bash
cd local/frontend
npm install
copy .env.example .env
# .env 의 VITE_BACKEND_URL 을 위에서 복사한 trycloudflare URL 로 교체
npm run dev                  # http://localhost:5173
```

## 사용 흐름

1. 화면 상단에서 **Model** (`Mock-Model` / `Qwen3.5-9B`), **Device** 선택
2. **Upload Images** 로 이미지/PDF 업로드
3. **Analysis** 클릭 → 진행 중에는 버튼이 **Stop** 으로 전환
4. **Image List** 에서 항목 선택 → **Image Summary** 에서 예측값 수정
5. **Complete** 클릭 시 해당 이미지가 `done` 으로 바뀌고 **Preview** 시트에 누적

## 모델 추가

레포에서는 `server/backend/model_registry.py` (서버에서는 `~/backend/model_registry.py`)의 `_REGISTRY` 에
`predict(image_path, field_spec, fewshot) -> list[FieldResult]` 시그니처의 함수를 등록하면 frontend/SCHEMA를 건드리지 않고 새 모델이 노출된다. `fewshot` 을 사용하지 않는 모델은 인자만 받고 무시한다.

## 신청서 종류 추가 (Form Template)

추출 항목과 (선택적으로) 모델용 답변 예시를 **신청서 종류마다 하나의 yml 파일**로 관리한다. 위치는 `server/backend/templates/`. 새 파일을 만들면 frontend 의 **Form Type 드롭다운에 자동 추가**된다 (backend 재시작 불필요, frontend 만 새로고침).

### 파일 구조 (`templates/<name>.yml`)

```yaml
name: default              # 식별자 — 영문 snake_case, 다른 yml 과 중복 금지
label: 테스트_1             # 화면에 보일 이름 — 한국어 자유

field_spec:                # 추출할 항목 목록 (순서 = Image Summary · Preview 시트 컬럼 순서)
  - key: full_name         #   시스템 식별자. 모델에게도 이 키로 답하라고 시키므로 영문 권장
    label: 성명             #   사람이 읽는 라벨. 한국어 가능
    type: text             #   현재 text 만 유효 (number/date 등은 추후 확장)
  - key: account
    label: 계좌번호(은행명)
    type: text
  # ... 필요한 만큼

fewshot: []                # 모델에게 보여줄 답안 예시. 비어 있어도 동작 (현 기본값)
```

### `fewshot` 채워 넣을 때

이미지를 포함하지 않는 텍스트 user/assistant 페어. 실제 분석 이미지 메시지 앞에 그대로 삽입되어 출력 형식을 시연한다 (`_qwen_predict` 의 messages 구성과 동일 구조).

```yaml
fewshot:
  - user: "이미지에서 full_name, account, rrn, address, phone 을 JSON 객체로만 답하라. 값이 없으면 (Unknown)."
    assistant: '{"full_name": "홍길동", "account": "신한은행 110-123-456789", "rrn": "900101-1234567", "address": "서울시 강남구 테헤란로 1", "phone": "010-1234-5678"}'
  - user: "이미지에서 full_name, account, rrn, address, phone 을 JSON 객체로만 답하라. 값이 없으면 (Unknown)."
    assistant: '{"full_name": "김민수", "account": "(Unknown)", "rrn": "(Unknown)", "address": "부산시 해운대구 우동", "phone": "010-9876-5432"}'
```

- 페어 수는 보통 2~5쌍 권장. 너무 많으면 프롬프트가 길어져 추론이 느려진다.
- `assistant` 값은 작은따옴표(`'…'`)로 감싸는 것이 안전 — 안쪽 JSON 의 큰따옴표를 YAML 이 종료 따옴표로 오해하지 않게.

### 새 신청서 추가 절차

1. `server/backend/templates/account_open.yml` 같이 새 파일 생성 (기존 `default.yml` 복사 → 수정이 가장 빠름)
2. `name` 을 파일명과 일치하는 고유 식별자로, `label` 을 화면 표시명으로, `field_spec` 을 그 신청서에 맞는 항목 목록으로 변경
3. 파일 저장 — backend 는 매 요청마다 디렉토리를 다시 스캔하므로 재시작 불필요
4. frontend 페이지 새로고침 → Form Type 드롭다운에 새 항목이 노출됨

### 작성 시 주의

- 들여쓰기는 **공백만** (탭 금지). 한 파일 안에서 일관성만 지키면 2칸·4칸 자유. 기본은 2칸.
- 콜론(`:`) 뒤에 반드시 공백 한 칸.
- 리스트 항목은 `-` (대시 + 공백) 으로 시작.
- 값에 콜론·따옴표가 들어가면 큰따옴표로 감싸기: `label: "Account No. (Bank Name)"`.

## 모델 정보 — Qwen3.5-9B

서버 `~/model/Qwen3.5-9B/` 에 적재된 VLM. 모델 폴더 검사로 확정된 사양:

- **모델 클래스**: `Qwen3_5ForConditionalGeneration` (멀티모달, image+text → text)
- **프로세서**: `Qwen3VLProcessor` (이미지 처리기 `Qwen2VLImageProcessorFast` 재사용)
- **채팅 템플릿**: 모델 폴더 내 `chat_template.jinja` — 프로세서가 자동 로딩
- **비전 토큰**: `<|vision_start|>`(248053), `<|vision_end|>`(248054), `image_token_id`=248056
- **커스텀 코드 없음** — 모델 폴더에 `.py` 없음 → 표준 `transformers` 클래스로 로딩 가능
- **모델 생성 시 transformers**: 4.57.0.dev0 (config 의 `transformers_version`)

서버 환경 (검증 완료):

- 패키지: `transformers 5.9.0` (tag 핀), `torch 2.5.1+cu121`, `torchvision 0.20.1+cu121`, `accelerate 1.13.0`, `pillow 10.3.0`, `huggingface_hub 1.16.1`, `hf_transfer 0.1.9`
- GPU / Driver: RTX 4090 24GiB / NVIDIA driver 535.288.01 — bf16 9B ≈ 18 GiB 적재 가능
- verify_qwen.py 실측: 첫 적재 ~161s / VRAM 17.53 GiB / generate 32.5 tok/s
- 세션 초기화 후 환경 재구성은 아래 "VLM 환경 준비" 섹션 참조

어댑터 (`server/backend/model_registry.py` 의 `_qwen_predict`):

- `_REGISTRY` 에 `"Qwen3.5-9B"` 로 등록됨 — `/models` 응답에 자동 노출, frontend Model 드롭다운에 표시
- 모듈 전역 lazy 캐시: backend 기동 후 **첫 분석 요청에만 ~161s** 적재 지연, 이후 같은 프로세스 내 모든 호출은 generate 비용만 (~8s/이미지)
- 프롬프트: `field_spec` 의 `key`/`label` 쌍을 받아 JSON 객체 한 개로만 답하도록 강제. 출력에서 코드 펜스 제거 → 첫 `{` ~ 마지막 `}` 구간을 `json.loads` → 실패 시 모든 필드 `None`
- `accuracy` 는 v1 에서 모두 `None` (logprob 기반 산출은 후속)
- 단일 워커(`run.sh` 의 `--workers 1`) 가정. 멀티 워커 시 워커당 18 GiB VRAM 점유로 24 GiB 1장 초과

## VLM 환경 준비 (세션 초기화 후 자동 복원)

JupyterHub 는 ephemeral — `pip install --user` 패키지가 매 세션 사라진다. 그러나 `~/backend/bootstrap.sh` 1회 실행이 다음을 모두 처리해 영속 환경을 재구성한다.

| # | 항목 | 비용 (첫 세션 / 이후) |
|---|---|---|
| 1 | `requirements.txt` 의 PyPI 의존성 설치 (FastAPI + cu121 torch + ML stack) | ~1~2 분 / ~1~2 분 (pip 가 skip) |
| 2 | `transformers @ v5.9.0` git tag 핀 설치 (`--no-deps`) | ~30 초 / skip (멱등 검사) |
| 3 | cloudflared 바이너리 다운로드 | ~10 초 / skip (홈 영속) |
| 4 | Qwen3.5-9B weight 다운로드 (`hf_transfer` 가속) | ~5~15 분 (≈18 GiB) / skip (홈 영속) |
| 5 | `import torch, transformers` 성공 여부 fail-fast 검증 | 즉시 |

홈 디렉토리는 NFS 영속이라 cloudflared 와 모델 weight 는 보통 첫 세션 이후 다시 받지 않는다 — pip 의존성 재설치만 매 세션 비용으로 든다.

### 수동 재구성 (디버깅용)

bootstrap.sh 가 어딘가에서 깨졌을 때 단계별로 분리해 추적. 정상 흐름에선 불필요.

```bash
# (1) PyPI 의존성만 (requirements.txt 그대로)
python -m pip install --user --timeout 600 --retries 5 -r requirements.txt

# (2) transformers v5.9.0 핀 — qwen3_5 model_type 보유 + FSDP2 hard import 회귀 없는 stable tag
python -m pip install --user --force-reinstall --no-deps \
  --timeout 600 --retries 5 \
  "transformers @ git+https://github.com/huggingface/transformers.git@v5.9.0"

# (3) 모델 weight 단독 재다운 (`huggingface-cli` 는 hub 1.16.1 에서 깨져 Python API 사용)
HF_HUB_ENABLE_HF_TRANSFER=1 python -c "
from huggingface_hub import snapshot_download
snapshot_download(repo_id='Qwen/Qwen3.5-9B', local_dir='/home/jovyan/model/Qwen3.5-9B')
"

# (4) 다운로드 무결성 — 4 shard 모두 OK + 총합 ~19.3 GiB 면 정상
python -c "
from pathlib import Path
from safetensors import safe_open
total = 0
for p in sorted((Path.home()/'model/Qwen3.5-9B').glob('*.safetensors')):
    with safe_open(str(p), framework='pt', device='cpu') as f: n = len(list(f.keys()))
    sz = p.stat().st_size; total += sz
    print(f'OK {p.name} tensors={n} size={sz:_}')
print(f'total {total:_}  (expected ~19_306_216_416)')
"

# (5) transformers 인식 확인 — config: Qwen3_5Config / model_type: qwen3_5 / processor: Qwen3VLProcessor
python -c "
from pathlib import Path
import transformers; print('transformers:', transformers.__version__)
from transformers import AutoConfig, AutoProcessor
cfg = AutoConfig.from_pretrained(str(Path.home()/'model/Qwen3.5-9B'))
proc = AutoProcessor.from_pretrained(str(Path.home()/'model/Qwen3.5-9B'))
print('config:', type(cfg).__name__, '| model_type:', cfg.model_type)
print('processor:', type(proc).__name__)
"
```

## 검증 스크립트

`server/backend/verify_qwen.py` — Qwen3.5-9B 가 GPU 에서 실제로 멀티모달 추론을 수행하는지 단독 확인.
어댑터(`model_registry.py`) 수정 전, 다음 4가지를 분리 검증한다.

1. `AutoProcessor` / `AutoModelForImageTextToText` 로딩 (실패 시 직접 클래스 import 폴백)
2. bf16 + `device_map="auto"` 적재 후 실제 VRAM 점유량
3. `chat_template.jinja` 기반 메시지 토크나이즈
4. 이미지 1장 + 프롬프트로 1회 `generate` → 출력이 이미지를 반영하는지 육안 확인

```bash
cd ~/backend
python verify_qwen.py <image_path> [prompt]
```

## 상태 저장 위치 (서버 기준)

- `~/data/state.db` — Job / 이미지 / 필드 결과 (SQLite)
- `~/data/uploads/` — 업로드된 원본 이미지

`db.py` 는 `backend/` 의 부모 디렉토리 옆에 `data/` 를 만든다. backend 첫 기동 시 자동 생성된다.
