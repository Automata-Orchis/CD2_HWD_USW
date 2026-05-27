# Log

## 2026-05-20

- **SCHEMA.md 작성** — FastAPI HTTP/JSON 계약 정의, 추출 필드는 `field_spec` 가변 명세 (PLAN.md 의 5필드는 하드코딩하지 않음).
- **시연 골격 도입** — `server/backend/` (FastAPI + SQLite + Mock 모델 + cloudflared `run.sh`) + `local/frontend/` (Vite + React) 가 SCHEMA 의 모든 엔드포인트와 1:1 wiring.
- **서버 배치 가정 정정** — `server/` prefix 는 로컬 분리 전용으로 취급, 실서버는 `~/backend`/`~/data`/`~/model` 직하 배치로 README/문서 일치.
- **shell 라인엔딩 호환** — `.gitattributes` (`*.sh text eol=lf`) + 기존 sh 파일 LF 변환으로 Linux 실행 시 `\r` 파싱 오류 제거.
- **uvicorn 호출 호환** — `python -m uvicorn` 으로 교체해 `~/.local/bin` PATH 누락 환경에서도 동작.
- **ImageSummary 입력 안정화** — 컴포넌트 로컬 draft state + PUT 은 Complete 1회로 통합, 커서 튐과 한글 IME composition 끊김 해소.
- **Image Summary 필드 순서 정렬** — `job.field_spec` 기준으로 정렬해 Preview 컬럼 순서와 일치.
- **PDF 업로드 미리보기 도입** — `<embed type="application/pdf">` (이후 2026-05-25~26 의 다중 페이지 도입으로 PDF embed 제거됨).
- **Image List blank 표기 정규화** — 사용자 노출 status 를 working/done 으로 제한.
- **재분석 시 done 보존** — `Analyze` 가 done 이 아닌 image_id 만 전송 + frontend `accumulatedRows` 로 시트 행 누적해 새 job 시작 시에도 이전 done 유지.

## 2026-05-21

- **PDF 미리보기 toolbar 제거** — `<embed src="...#toolbar=0&navpanes=0">` 로 Chromium PDF viewer 상단 toolbar 숨김.
- **Stop 시 비-done 결과 폐기** — `_run_job` 종료 블록에서 `field_results` 삭제 + `status='blank'` 처리. Stop = 진행 중 추론 결과는 신뢰하지 않는다는 의미.
- **재분석 done 상태 보존** — `imagesForList` status 에 `accumulatedRows` 반영 + `doneSummariesRef` 로 빈 fields 폴백 (새 job 이 이전 job_id 의 결과를 모르는 케이스 대응).
- **Toolbar / Preview / Device 정렬 마무리** — 컨트롤 4종 높이 32px 통일, Device 박스를 `<fieldset>/<legend>` 에서 `<div className="device-field">` 2단 구조로 교체 (캡션 라인 비는 문제 해소), Preview·Sheet 제목을 박스 바깥 위로 이동, Preview 6행 초과 시 thead sticky 세로 스크롤, h1/h2/`.toolbar .cap` 들여쓰기 10px 통일.
- **Image 줌·팬·미니맵 도입** — `.zoom-stage` 에 native wheel(passive 회피) 1~8× 줌, 드래그 팬, 더블클릭 1× 리셋, 이미지 전환 자동 리셋, `clampPan` 으로 한 축당 `max(0, (img.offsetDim*zoom - stage.offsetDim)/2)` 경계 클램프, 우하단 ≤100px 미니맵 (줌>1 일 때만 표시, `pointer-events: none`).
- **임시 산출물 제거** — `local/` 루트의 `chat_share.html` / `enqueue_*.txt` 4종 (PLAN §6 본문 추출용 ChatGPT 공유 페이지 덤프) 삭제.
- **PLAN.md §2 트리 갱신** — 루트명 `CD2_HWD_USW` 반영, SCHEMA/TODO/.gitattributes 추가, `local/frontend/` Vite+React 골격과 `server/backend/` 구현 파일들에 한 줄 설명 부여.

## 2026-05-22~24

- **verify_qwen.py 작성** — Qwen3.5-9B GPU 적재 + 멀티모달 추론 단독 검증 (processor / bf16 적재 / chat template / generate 4단계 분리).
- **transformers v5.9.0 핀 확정** — 4.57.6 의 `qwen3_5` 미인식, main 빌드의 `ParallelStyle` NameError, 같은 dev 빌드의 `CPUOffloadPolicy` ImportError(torch≥2.6 FSDP2 hard import), driver 535.288.01 의 CUDA 12.4 wheel 미수용을 차례로 검증 후 v5.9.0 이 qwen3_5 보유 + FSDP2 hard import 회귀 없는 stable tag 임을 확인하여 `--force-reinstall --no-deps` 로 고정.
- **torchvision 0.20.1+cu121 정합** — `torchvision::nms` 누락 해소 + torch 2.5.1+cu121 정합 (`--timeout 600 --retries 5` 로 PyTorch CDN read timeout 우회).
- **모델 weight 재다운** — 4 shard 손상(declared 19.3 GiB vs 실제 1.18 GiB) 발견, `huggingface_hub.snapshot_download(allow_patterns=['*.safetensors'])` + `hf_transfer` Rust 가속으로 무결성+총합 일치 복원.
- **verify_qwen 실측 통과** — bf16 17.53 GiB / 32.5 tok/s / 한국어 손글씨(시편 23편) 인식 확인.
- **`_qwen_predict` 어댑터 도입** — `_REGISTRY` 에 `"Qwen3.5-9B"` 등록, 모듈 전역 lazy 캐시 + JSON 강제 프롬프트 + 코드 펜스 제거 파서 + 단일 generate. 첫 호출 ~161s 적재, 이후 ~8s/이미지.
- **README VLM 환경 섹션 신설** — 최종 검증 환경(transformers 5.9.0 / torch 2.5.1+cu121 / torchvision 0.20.1+cu121 / hf_transfer 0.1.9 등) 으로 "서버 환경" 라인 교체.
- **세션 영속화 자동화** — `requirements.txt` 에 cu121 torch wheel 핀 + ML stack 추가, `bootstrap.sh` 가 transformers `@v5.9.0` git pin 멱등 처리 + 모델 weight 부재 시 `snapshot_download` 까지 수행 → 매 세션 `bash bootstrap.sh` 한 줄로 전 환경 복원.

## 2026-05-25~26

- **Form Template 시스템 도입** — `server/backend/templates/<name>.yml` 에 신청서별 추출 필드 / few-shot 정의, frontend Form Type 드롭다운에서 선택, `/analyze` 가 `template_name` 만 받고 backend 가 template 의 `field_spec`/`fewshot` 을 expand. `templates_io.py` 가 매 요청 디스크 재스캔 → backend 재시작 없이 추가/수정 가능.
- **schemas / 어댑터 / frontend Form Type 연동** — `schemas.py` 에 `Template`/`FewshotPair` 추가, `AnalyzeRequest.field_spec` → `template_name` 교체, `_qwen_predict` 가 fewshot user/assistant 페어를 image 메시지 앞에 삽입 (verify_qwen 의 messages[1~4] 구조 일치), frontend `api.js` 에 `listTemplates` 추가, `App.jsx` 의 `DEFAULT_FIELD_SPEC` 하드코딩 제거.
- **`templates/default.yml` 작성** — 기본 5필드, `fewshot: []`.
- **PyYAML / sqlite-utils 추가** — `requirements.txt` 에 `PyYAML 6.0.2` (template 로더) + `sqlite-utils 3.38` (JupyterHub `sqlite3` binary 부재 대응 DB 조회 CLI).
- **Toolbar 5트랙 재정의** — Form Type 추가로 자식이 5개가 되어 `1fr auto 1fr 1fr auto` 로 교체 (Device 컨텐츠 폭, 나머지 3종 균등 분할).
- **Device 박스 좌우 여백 대칭** — Chrome 기본 `input[type=radio]` 마진(좌5/우3) 을 `0` reset + `justify-content: center`.
- **TODO.md 3-tier 재편** — Form Template 채택으로 해결된 "현재 결정 사항" 삭제, "검증 대상 / 개선 대상 / 추후 개선 대상" 3-tier 로 재구성.
- **다중 페이지 신청서 도입** — 작업 단위를 image 에서 application 으로 일괄 전환: 1 application = 1장(이미지) 또는 N장(PDF 분할), `_qwen_predict` 가 페이지 N장을 한 번의 `generate` 로 종합해 단일 ApplicationSummary 산출.
    - **schemas.py** — `ImageInfo`/`ImageSummary` → `ApplicationInfo`/`ApplicationSummary` (+ `page_count`), `AnalyzeRequest.image_ids` → `application_ids`, `SheetRow.image_id` → `application_id`, `Job.images` → `Job.applications`. `ImageStatus` enum 이름은 그대로 둔다.
    - **db.py** — `applications`/`application_pages`/`job_applications`/`field_results(PK: job+app+key)` 새 스키마 (기존 `images`/`job_images` 폐기 → `server/data/state.db` 와 `uploads/` 수동 삭제 후 신규 기동).
    - **main.py** — `/upload` 가 PDF 를 `_split_pdf_to_pngs(scale=2.0)` 로 분할 후 원본 폐기, 신규 `GET /applications/{aid}/pages/{ord}/file`, `/analyze` 가 `application_ids` 수신, `_run_job` 이 application 단위로 모든 페이지를 한 번에 `predict(model, pages, ...)`, Stop 시 비-done application 결과 폐기.
    - **model_registry.py** — `predict(image_paths: list[Path], ...)` 시그니처, `_qwen_predict` 가 messages user content 에 `{"type":"image"}` N개 + 텍스트 1개로 multi-image 입력, N>1 프롬프트에 "N장 종합 + 같은 항목 다중 페이지면 가장 명확한 값" 규칙 추가.
    - **requirements.txt** — `pypdfium2==4.30.0` 추가 (pure wheel + 내장 PDFium, poppler/시스템 바이너리 불요 → 폐쇄망 적합).
    - **frontend** — `api.js` 엔드포인트 전부 application 기반 + `pageUrl(aid, ord)` 추가, PDF embed 제거(서버 분할 결과 이미지로 통일), `App.jsx` `selectedApp`/`selectedPage` 도입, `ApplicationList` page_count>1 일 때 `Np` 칩, `ImageView` 에 페이지 prev/next 네비, Summary/Sheet 키 `application_id`, `styles.css` 에 `.pages`/`.page-nav` 추가 + 미사용 `.pdf-embed` 제거.
    - **문서 일괄 갱신** — SCHEMA / PLAN §7 / TODO / README 가 application 단위로 갱신, PLAN §7 에 "이미지 N장 그룹핑 UX(Upload 1회 = 신청서 1건)" 향후 작업 명시.
- **문서 4종 (README/PLAN/TODO/LOG) 정리** — README 를 기능별 사용법 + 필요 패키지 + 주의사항 챕터로 재편, PLAN 을 local(frontend) / server(backend/data/model) / JupyterHub 운영 / 다중 페이지 / 개선점 순으로 재정렬(코드/트리/UI 박스 등 ``` 블록은 보존), TODO/LOG 를 챕터 + 굵은 문제점 + 한 문장 설명 포맷으로 통일.
- **문서 4종 정보 최신화** — PLAN §2 트리에 실재 파일(`templates_io.py` / `templates/default.yml` / `verify_qwen.py`) 추가, README "신청서 종류 추가" 의 `type: text` 주석을 "현재 Qwen 어댑터 미참조 (mock 만 사용), 자리만 유지" 로 정정 (`default.yml` 사용자 코멘트로 발견 + 코드 grep 으로 확인), TODO/LOG 는 미해결 항목 그대로 유효해 변경 없음.
- **사전 적재본 + 카테고리 기반 작업 선택으로 전환** — 작업자가 frontend 에서 파일을 업로드하는 방식을 폐기. 신청서는 관리자가 `server/data/<template_name>/` (yml 파일 stem 폴더) 에 사전 배치하고, backend 가 매 `/work-categories` / `/applications` 호출 시 폴더를 재스캔해 `applications` 테이블에 결정론적 ID (`app_<sha1(template/filename)[:10]>`) 로 인입한다. 폴더는 신청서 종류 수만큼만 유지 (신청서당 폴더 X). `original_data/` 는 reserved 폴더로 스캔 제외.
    - **db.py** — `applications` 테이블에 `template_name` / `source_path` 컬럼 추가 (PRAGMA `table_info` 검사 후 멱등 ALTER). `application_pages` / `UPLOAD_DIR` 폐기 (PDF 즉석 렌더로 페이지 경로 불필요).
    - **categories.py 신설** — `scan_and_ingest()` 가 yml stem 폴더의 `.pdf|.png|.jpg|.jpeg` 파일을 인입하고 `_pdf_page_count` 로 페이지 수 산출. `category_stats()` 는 `applications` GROUP BY template_name × status 로 total/done/incomplete/rate 집계. `applications_for(template_name)` 은 파일명 정렬.
    - **main.py** — 신규 `GET /work-categories`, `GET /applications?template_name=`. `/applications/{aid}/pages/{ord}/file` 은 source_path 의 확장자로 분기 — PDF 는 `pypdfium2` 로 즉석 PNG 바이트 응답(scale=2.0), 이미지는 `FileResponse` 직접. `_run_job` 의 페이지 자료화는 `tempfile.TemporaryDirectory()` 안에 분할 (predict 종료 시 자동 정리). `POST /upload` 와 `_split_pdf_to_pngs`, `_load_pages` 제거.
    - **schemas.py** — `ApplicationInfo.template_name` 추가, 신규 `CategoryStat(template_name, label, total, done, incomplete, rate)`.
    - **frontend** — `api.js` 에 `listCategories`/`listApplications` 추가, `upload` 제거. `App.jsx` 의 Toolbar 에서 Form Type 셀렉터 + Upload `<input>` 삭제, 자리에 **"작업 선택" 버튼** + Dashboard 섹션 추가. 카테고리 Sub Box 는 `label / 총·완료·미완료 / 작업률% / 진행 막대`. 카테고리 클릭 시 `template_name` 자동 설정 + 카테고리 변경이면 `jobId/job/selectedApp/summary/accumulatedRows/doneSummariesRef` 일괄 리셋. `templates` state 와 `fileRef` 제거. `styles.css` 에 `.dashboard`/`.cat-grid`/`.cat-box` 추가, toolbar grid 를 `1fr auto auto auto` 로 축소.
    - **문서 일괄 갱신** — README 의 "사용 흐름" 을 카테고리 선택 기반으로 재작성 + 트리/DB 조회 예시 갱신, SCHEMA §0/2.3/2.7~8/3.1~3 갱신 (CategoryStat 추가, /upload 삭제, /work-categories 와 /applications 추가), PLAN §2 트리 + §3 frontend 레이아웃 + §5 data 구조 + §8 다중 페이지 정책 재정렬.

## 2026-05-27

- **모델 명시적 적재 + 진행 표시** — Qwen 첫 추론의 ~161s lazy-load 지연을 UI 에서 가시화. `model_registry` 에 `_load_state` / `start_loading(name)` / `get_load_status(name)` 도입, Qwen 은 백그라운드 스레드(`threading.Thread(daemon=True)`)로 `_qwen_get` 호출 후 `loaded` 로 전환. `loading` 중에는 `_QWEN_LOAD_EST_SEC=180.0` 기반 경과시간 추정으로 `progress` 를 0~0.95 클램프(실측 완료 시 1.0 으로 worker 가 덮어씀). Mock-Model 은 비용 없으므로 즉시 `loaded`.
    - **main.py** — `POST /models/{name}/load` (적재 트리거, 이미 적재됐으면 현 상태만 반환), `GET /models/{name}/status` (state/progress/error 반환).
    - **frontend** — `api.js` 의 `loadModel`/`modelStatus`. `App.jsx` 의 `modelStatus` state + 두 useEffect (model 변경 시 1회 조회 / `loading` 중에만 1초 폴링). Toolbar Model 칸에 `<select>` 옆 Load 버튼 — 상태별 라벨 (`모델 로드` / `로딩 중 NN%` / `✓ 로드됨` / `재시도`) 과 배경색 (회/노/녹/적). `canAnalyze` 에 `isModelLoaded` 추가해 미적재 상태에서 Analyze 차단.
    - **styles.css** — toolbar grid 를 `1fr auto auto auto` → `auto auto auto auto` 로 축소(Model Box 가 1fr 로 너무 넓어지던 문제 해소). `.model-row` flex 컨테이너, `.load-model` 의 `unloaded/loading/loaded/failed` 클래스별 색.
- **Work 버튼 라벨 단순화** — 카테고리 선택 후에도 "작업 선택 (label)" prefix 가 남던 문제. `templateLabel || templateName || '작업 선택'` 으로 교체.
- **per-application try/except** — `_run_job` 의 한 신청서 처리 중 `predict()` 가 예외를 던지면 전체 task 가 조용히 종료되어 이후 신청서가 시작 안 되고 jobs.status 가 `running` 으로 고착되던 문제. 각 application 처리를 try/except 로 감싸 실패 시 빈 `FieldResult` 한 세트를 저장하고 다음 신청서로 진행. ApplicationSummary 가 항상 표를 그릴 수 있게 되고, job 종료 상태(`completed`/`stopped`) 가 항상 갱신된다.
- **자동 lazy load + Load 버튼 통합** — `_qwen_get` 안에 `_qwen_load_mutex` (적재 전용 Lock) + `_load_state` 갱신을 일원화. explicit Load 버튼과 Analyze 시점의 자동 lazy load 가 동일 경로로 수렴, 단일 적재 보장(double-check). `_qwen_load_worker` 는 호출 트리거로 단순화. frontend `canAnalyze` 에서 `isModelLoaded` 제거 → `!isModelLoading`, `handleAnalyze` 가 미적재 시 `api.loadModel` 자동 호출 → 진행률 폴링 useEffect 가 켜져 % 표시. Load 버튼은 선제 적재의 단축 UX 일 뿐, 누르지 않아도 분석 가능.
- **`max_new_tokens` 512 → 1024** — `_qwen_predict` 의 출력 토큰 한도 상향. `direct_payment` 14필드(중 6필드가 다행 표) 출력이 512 안에 JSON 을 닫지 못해 `_qwen_parse` 가 빈 dict 폴백, 10건 중 5건이 모든 필드 None 으로 저장되던 문제 해결. greedy decoding(`do_sample=False`) 이라 정상 신청서는 EOS 에서 자동 종료, 잘리던 신청서만 추가 토큰 생성.
- **`_qwen_parse` 실패 로깅** — silent 폴백을 stdout `[qwen parse fail] <reason> | raw_len=N | raw=...` 로 가시화. `JSONDecodeError` (잘림/형식 깨짐) / `no balanced braces` (빈 응답) / `top-level is list` (배열 응답) 등 실패 사유를 한 줄로 구분 가능.
- **TODO** — 다행 표 필드(세대원 등) 평탄화 한계 + 모델의 세대원/분리세대 혼동 항목 신설.
- **Toolbar 버튼 위치 고정** — `auto` 트랙의 가변 여유로 Load 버튼↔Device 간격이 벌어지고, Work 버튼이 카테고리 라벨 길이만큼 늘어 뒤의 Analysis 를 밀던 문제. `styles.css` 에서 `.model-row select` 를 `min/max-width`(130/200) → 고정 `width:150px`, `.load-model` 을 `min-width:100` → 고정 `width:108px`("로딩 중 100%" 수용), `.select-work` 를 가변폭 → 고정 `width:200px` + `text-overflow:ellipsis`(좌측 정렬)로 교체. 잘린 카테고리 라벨 전체는 `App.jsx` 의 Work 버튼 `title` 속성으로 hover 노출. 세 칸이 결정론적 폭이 되어 모든 선택 버튼 위치가 라벨 내용과 무관하게 고정.
- **신청서 분석 상태 표기 (analyzed/error 추가)** — List 에서 "미분석 vs 분석완료 vs 추론오류" 를 구분 못 해 전체 작업 완료 시점을 알 수 없던 문제. `ImageStatus` enum 에 `analyzed`(추론 완료·검토 대기) / `error`(predict 예외·소스 누락) 추가. `_run_job` 이 성공 시 `analyzed`, 실패 3경로(소스 None / 페이지 0 / 예외) 시 `error` 로 status 전이(기존엔 모두 `working` 유지라 구분 불가). frontend `appsForList` 가 실시간 status 를 그대로 노출(기존 `done|working` 2분 정규화 제거), `STATUS_LABEL` 로 대기/분석중/분석완료/오류/완료 라벨 + `.badge.analyzed`(녹)/`.badge.error`(적) 색 추가. Stop 시 비-done 폐기 로직은 analyzed/error 도 비-done 이라 그대로 적용(변경 없음).
- **모델 로드 게이지 실측화** — `progress` 가 `elapsed/_QWEN_LOAD_EST_SEC` 시간 추정이라 실제 파라미터 적재와 괴리(미적재에도 상승 / 빠른 적재 미반영 / 완료 시 점프)되던 문제. `_qwen_mem_monitor` 도입 — 적재 중 0.4s 마다 `torch.cuda.memory_allocated()` 를 가중치 총 바이트(`model.safetensors.index.json` 의 `metadata.total_size`, 폴백: `*.safetensors` 크기 합)로 나눠 0.99 상한·`max()` 단조 증가로 `progress` 갱신, 완료 시 worker 가 1.0 으로 덮음. `_snapshot` 의 시간 기반 추정 제거, `_QWEN_LOAD_EST_SEC` 삭제. GPU 부재 시 모니터 미가동(완료 시 1.0). `_qwen_get` 에 `[qwen load] start` / `done in Ns` wall-time 로그 추가 — "작업 선택 후 로딩 느림"(TODO) 을 추정 아닌 실측으로 비교하기 위함.
