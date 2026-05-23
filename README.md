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

JupyterHub 환경은 ephemeral이다 — 세션 재시작 시 `pip install`로 설치한 패키지가 모두 사라진다. 단 홈 디렉토리는 영속이므로 cloudflared 바이너리는 최초 1회만 다운로드된다. **세션 시작마다 `bootstrap.sh` 를 1회 실행**한다.

```bash
cd ~/backend
bash bootstrap.sh            # 매 세션 1회: pip install --user + cloudflared 다운로드(최초 1회)
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
`predict(image_path, field_spec) -> list[FieldResult]` 시그니처의 함수를 등록하면 frontend/SCHEMA를 건드리지 않고 새 모델이 노출된다.

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

## VLM 환경 준비 (세션 초기화 후)

JupyterHub 는 ephemeral — `pip install --user` 패키지와 모델 weight 파일 모두 세션 재시작 시 사라진다. 아래는 시행착오를 거쳐 **검증된 명령 시퀀스**. 매 세션 1회 실행.

### 1) Python 패키지 설치

```bash
# torch + torchvision 페어 (cu121 wheel). driver 535.288.01 환경에서 검증
python -m pip install --user --upgrade \
  --timeout 600 --retries 5 \
  torch==2.5.1 torchvision==0.20.1 \
  --index-url https://download.pytorch.org/whl/cu121

# transformers v5.9.0 핀 — qwen3_5 model_type 보유 + FSDP2 hard import 회귀 없는 stable tag
python -m pip install --user --force-reinstall --no-deps \
  --timeout 600 --retries 5 \
  "transformers @ git+https://github.com/huggingface/transformers.git@v5.9.0"

# 모델 다운로드 가속용 (Rust 가속기). 없으면 다운로드만 느려질 뿐 동작은 함
python -m pip install --user --upgrade hf_transfer
```

`--timeout 600 --retries 5` 는 PyTorch CDN 의 read timeout 우회용. `transformers` 는 `--no-deps` 로 torch/accelerate 등 다른 의존성 변동 방지.

### 2) 모델 weight 다운로드 (~18 GiB)

`~/model/Qwen3.5-9B/` 의 4개 `.safetensors` shard. `huggingface_hub 1.16.1` 에서 `huggingface-cli` 진입점이 깨져 있어 **Python API 직접 호출**.

```bash
HF_HUB_ENABLE_HF_TRANSFER=1 python -c "
from huggingface_hub import snapshot_download
snapshot_download(
    repo_id='Qwen/Qwen3.5-9B',
    allow_patterns=['*.safetensors'],
    local_dir='/home/jovyan/model/Qwen3.5-9B',
)
"
```

`allow_patterns=['*.safetensors']` 로 weight 만 받는다. config / tokenizer / chat_template 등은 이미 폴더에 있다고 가정 (없으면 패턴 확장: `allow_patterns=['*.safetensors', '*.json', 'chat_template.jinja', 'merges.txt', 'vocab.json']`).

### 3) 다운로드 무결성 검증

```bash
python -c "
from pathlib import Path
from safetensors import safe_open
total = 0
for p in sorted((Path.home()/'model/Qwen3.5-9B').glob('*.safetensors')):
    with safe_open(str(p), framework='pt', device='cpu') as f:
        n = len(list(f.keys()))
    sz = p.stat().st_size; total += sz
    print(f'OK {p.name} tensors={n} size={sz:_}')
print(f'total {total:_}  (expected ~19_306_216_416)')
"
```

4 shard 모두 `OK` + 총합 약 19.3 GiB 일치하면 정상 (실제 합계 ~19,306,310,880 — 메타 헤더 오버헤드 ~94 KB).

### 4) transformers 인식 확인

```bash
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

기대 출력:

```
transformers: 5.9.0
config: Qwen3_5Config | model_type: qwen3_5
processor: Qwen3VLProcessor
```

여기까지 통과하면 환경 구성 완료. 이후 `bootstrap.sh` / `run.sh` 로 backend 기동 + `verify_qwen.py` 로 실제 추론 검증 (아래 섹션).

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
