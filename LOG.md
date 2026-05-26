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
