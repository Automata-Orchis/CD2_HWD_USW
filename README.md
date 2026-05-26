# project_gamma

VLM 기반 한글 손글씨 문서 인식 시연 시스템.
설계: `PLAN.md` · 통신 계약: `SCHEMA.md` · 작업 기록: `LOG.md` · 검증/개선 항목: `TODO.md`.

## 레포 구조

```
CD2_HWD_USW/
├── local/frontend/         # 로컬 UI (Vite + React)
└── server/                 # JupyterHub 서버 측 미러 (실서버는 ~/ 직하 배치)
    ├── backend/            # FastAPI + cloudflared
    ├── data/               # SQLite + 신청서별 페이지 이미지 (런타임 생성)
    └── model/Qwen3.5-9B/   # VLM 파라미터 (실 weight 는 서버에만 존재)
```

## 구동 — 서버 (JupyterHub 터미널)

```bash
cd ~/backend
bash bootstrap.sh    # 매 세션 1회: pip --user + transformers v5.9.0 + cloudflared/모델 weight 복원
bash run.sh          # uvicorn + cloudflared (기본 8000, PORT=9000 등으로 변경 가능)
```

cloudflared 로그에서 `https://<random>.trycloudflare.com` 형태의 URL 을 복사한다.

## 구동 — 로컬 (frontend)

```bash
cd local/frontend
npm install
copy .env.example .env
# .env 의 VITE_BACKEND_URL 을 위에서 복사한 trycloudflare URL 로 교체
npm run dev          # http://localhost:5173
```

## 사용 흐름

1. 상단 toolbar 에서 **Model / Device / Form Type** 선택.
2. **Upload Images or PDFs** 로 신청서 등록 — 이미지 1장 또는 PDF 1개 = 신청서 1건. PDF 는 backend 가 페이지 PNG 로 자동 분할.
3. **Analysis** 클릭 → 진행 중에는 **Stop** 으로 토글.
4. **Application List** 에서 신청서 선택 → 다중 페이지면 **Image** 패널 아래 ◀ ▶ 로 페이지 이동 → **Application Summary** 에서 예측값 수정.
5. **Complete** → 신청서가 `done` 으로 전환되고 **Preview** 시트에 1행 누적.

## 모델 추가

`server/backend/model_registry.py` 의 `_REGISTRY` 에 다음 시그니처 함수를 등록한다.

```python
def predict(image_paths: list[Path], field_spec, fewshot) -> list[FieldResult]
```

- `image_paths` 는 한 신청서의 페이지 이미지 리스트 (길이 ≥ 1). 모델은 모든 페이지를 종합해 1세트의 결과를 반환.
- `fewshot` 미사용 모델은 인자만 받고 무시.
- 등록 즉시 `/models` 응답과 frontend Model 드롭다운에 노출 (SCHEMA/frontend 수정 불필요).

## 신청서 종류 추가 (Form Template)

`server/backend/templates/<name>.yml` 한 파일이 하나의 신청서 종류. backend 가 매 요청마다 디렉토리를 재스캔하므로 추가/수정 후 backend 재시작 불필요 (frontend 만 새로고침).

### yml 구조

```yaml
name: default              # 식별자 — 영문 snake_case, 다른 yml 과 중복 금지 (파일명과 일치 권장)
label: 테스트_1             # 화면 표시명 — 한국어 자유

field_spec:                # 추출 항목 — 순서 = Application Summary · Preview 시트 컬럼 순서
  - key: full_name         #   영문 식별자, 모델 응답 키로도 사용
    label: 성명             #   사람이 읽는 라벨
    type: text             #   현재 Qwen 어댑터에서는 미사용 (mock 어댑터만 참조). 자리만 유지, 추후 검증/렌더 분기 여지
  - key: account
    label: 계좌번호(은행명)
    type: text
  # ... 필요한 만큼

fewshot: []                # 모델 답안 예시 (user/assistant 페어). 비어 있어도 동작
```

### fewshot 채워 넣기

이미지를 포함하지 않는 텍스트 user/assistant 페어. 실제 분석 이미지 메시지 앞에 그대로 삽입되어 출력 형식을 시연한다 (`_qwen_predict` 의 messages 구성과 동일 구조).

```yaml
fewshot:
  - user: "이미지에서 full_name, account, rrn, address, phone 을 JSON 객체로만 답하라. 값이 없으면 (Unknown)."
    assistant: '{"full_name": "홍길동", "account": "신한은행 110-123-456789", "rrn": "900101-1234567", "address": "서울시 강남구 테헤란로 1", "phone": "010-1234-5678"}'
```

페어는 보통 2~5쌍 권장 (너무 많으면 프롬프트가 길어져 추론 느려짐). assistant 의 JSON 큰따옴표가 YAML 파싱과 충돌하지 않도록 작은따옴표(`'…'`)로 감싼다.

### 작성 주의

- 들여쓰기는 공백만 (탭 금지). 한 파일 안에서 일관성만 지키면 2칸/4칸 자유, 기본 2칸.
- `:` 뒤에는 공백 1칸. 리스트 항목은 `-` (대시 + 공백) 시작.
- 값에 콜론/따옴표 포함 시 큰따옴표로 감싸기 (`label: "Account No. (Bank Name)"`).

## 검증 스크립트 — verify_qwen.py

Qwen3.5-9B 가 GPU 에서 실제로 멀티모달 추론을 수행하는지 단독 확인. 어댑터 수정 전 4단계 분리 검증 (processor / bf16 적재 / chat template / generate).

```bash
cd ~/backend
python verify_qwen.py <image_path> [prompt]
```

## DB 조회

`sqlite3` CLI 가 없는 JupyterHub 환경 대응으로 `sqlite-utils` 를 사용한다 (`bootstrap.sh` 가 함께 설치). 백엔드의 `import sqlite3` 는 Python 표준 라이브러리라 별도 설치 불필요.

```bash
# 테이블 목록
python -m sqlite_utils tables ~/data/state.db

# 신청서 전체
python -m sqlite_utils ~/data/state.db \
  "SELECT application_id, filename, status, page_count FROM applications" --table

# 특정 신청서의 페이지 경로
python -m sqlite_utils ~/data/state.db \
  "SELECT ord, path FROM application_pages WHERE application_id='app_xxx' ORDER BY ord" --table

# 특정 신청서의 필드 결과
python -m sqlite_utils ~/data/state.db \
  "SELECT key, predicted, edited FROM field_results WHERE application_id='app_xxx'" --table

# 완료 시트 CSV
python -m sqlite_utils ~/data/state.db \
  "SELECT a.filename, fr.key, COALESCE(fr.edited, fr.predicted) AS value
     FROM field_results fr JOIN applications a ON fr.application_id = a.application_id
    WHERE a.status='done'" --csv > sheet.csv
```

`~/.local/bin` 이 PATH 에 있으면 `sqlite-utils ~/data/state.db ...` 형태로도 호출 가능.

## 필요 패키지

`server/backend/requirements.txt` 에 일괄 정의. `bash bootstrap.sh` 가 다음을 자동 처리한다.

- **API server** : FastAPI 0.115.0 / uvicorn[standard] 0.30.6 / python-multipart 0.0.9 / pydantic 2.9.2 / PyYAML 6.0.2.
- **PDF 분할** : pypdfium2 4.30.0 (pure wheel + 내장 PDFium, poppler/시스템 바이너리 불요 → 폐쇄망·non-sudo 환경 적합).
- **PyTorch (cu121 wheel, driver 535.288.01 호환)** : torch 2.5.1+cu121 / torchvision 0.20.1+cu121.
- **ML stack (transformers 5.9.0 검증 환경)** : accelerate 1.13.0 / Pillow 10.3.0 / safetensors 0.7.0 / tokenizers 0.22.2 / huggingface_hub 1.16.1 / hf_transfer 0.1.9.
- **DB CLI** : sqlite-utils 3.38.
- **git tag 핀** : `transformers @ git+...@v5.9.0` — `qwen3_5` model_type 보유 + FSDP2 hard import 회귀 없는 stable tag. `bootstrap.sh` 가 멱등 처리.
- **바이너리** : `cloudflared-linux-amd64` — 홈 영속, 1회 다운로드.
- **모델 weight** : Qwen3.5-9B (~18 GiB) — `hf_transfer` 가속, 홈 영속.

frontend 측은 `local/frontend/package.json` 의 Vite + React 의존성을 `npm install` 로 설치.

## 주의사항

- **세션 재시작마다 `bootstrap.sh` 1회 실행** — JupyterHub 의 site-packages 는 휘발성이라 pip 의존성이 매 세션 사라진다 (홈 디렉토리만 영속).
- **trycloudflare URL 은 재발급 시 바뀐다** — cloudflared 재시작 후에는 frontend `.env` 의 `VITE_BACKEND_URL` 을 새 URL 로 교체해야 backend 재접속이 된다.
- **분석 첫 요청은 ~161s 지연** — 모듈 전역 lazy 캐시로 모델을 1회 적재. 두 번째 요청부터 ~8s/이미지.
- **단일 워커 가정** — `run.sh` 의 `--workers 1`. 멀티 워커 시 워커당 18 GiB VRAM 점유로 24 GiB GPU 한 장을 초과한다.
- **CORS 가 `allow_origins=["*"]`** — 개발/시연 전용. 운영 시 origin 제한 필요.
- **공개 URL 에 인증 없음** — Quick Tunnel 은 누구나 접근 가능하므로 민감 데이터 주의.
- **Device 라디오는 현재 no-op** — 어댑터가 `device_map="auto"` 고정. TODO 참조.
- **PDF 외 이미지 N장 그룹핑 UX 미구현** — 한 신청서가 여러 이미지 파일로 존재하는 경우는 현재 PDF 입력에서만 지원. TODO 참조.
- **DB 스키마 변경 시 기존 `~/data/` 통째 삭제 필요** — `images` → `applications` 같은 비호환 전환에서는 backend 기동 전에 정리.
