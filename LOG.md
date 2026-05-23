# Log

## 2026-05-20

- 공통 I/O 스키마 정의 시작점으로 채택. PLAN.md §2의 "뼈대" 요구사항과 §4의 "모델 출력 통일" 요구사항을 충족하기 위해 frontend/backend/model이 공유할 데이터 계약을 먼저 확정.
- `SCHEMA.md` 작성. FastAPI 기반 HTTP/JSON 계약. 추출 필드는 `field_spec`으로 분석 요청 시 가변 명세 (PLAN.md의 5개 필드는 하드코딩하지 않음).
- 시연용 골격 추가. `server/backend/` (FastAPI + SQLite + Mock 모델 + cloudflared `run.sh`) 와 `local/frontend/` (Vite + React, SCHEMA.md 의 모든 엔드포인트와 1:1 wiring) 작성. 실제 VLM 호출은 `model_registry.py` 의 `_REGISTRY` 에 어댑터를 추가하는 방식으로 후속 작업.
- 서버 배치 가정 정정 — `server/` prefix 는 로컬 분리용으로만 취급, 서버에서는 `~/backend`, `~/data`, `~/model` 직하 배치로 README/문서 일치화.
- `.gitattributes` 신설(`*.sh text eol=lf`) + `bootstrap.sh`/`run.sh` 를 LF 로 변환해 Linux 실행 시 `\r` 파싱 오류 제거.
- `run.sh` 의 uvicorn 호출을 `python -m uvicorn` 으로 교체해 `~/.local/bin` PATH 누락 환경에서도 동작.
- Preview Sheet 가로 오버플로 처리 — `.preview { overflow-x: auto }`.
- ImageSummary 입력을 컴포넌트 로컬 draft state 로 전환, 서버 PUT 은 Complete 1회로 통합 — 커서 튐과 한글 IME 끊김 해소.
- Image Summary 필드 렌더 순서를 `job.field_spec` 기준으로 정렬해 Preview 컬럼 순서와 일치.
- PDF 업로드 미리보기에 `<embed type="application/pdf">` 적용.
- Image List 의 `blank` 표기를 `working` 으로 정규화 — BLANK 상태는 사용자 노출에서 제거.
- `Analyze` 가 `done` 이 아닌 image_id 만 전송 — 신규 이미지 추가 후 재분석해도 기존 done 보존.
- Preview Sheet 행을 `image_id` 키로 frontend 에서 누적 — 새 job 시작 시에도 이전 done 행 유지.

## 2026-05-21

- PDF 미리보기의 Chromium PDF viewer 상단 toolbar 숨김 — `<embed src="...#toolbar=0&navpanes=0">`.
- Image Summary 행 라벨을 `field_spec.label` 기준 Title Case 로 표기.
- Preview 패널 세로 스크롤 부여 — `max-height: 360px; overflow: auto`.
- Device 옵션 가로 배치 — `.device label { display: inline-flex }` + 인접 형제 `margin-left`.
- Stop 시 비-`done` 이미지 결과 폐기 — `_run_job` 종료 블록에서 `field_results` 삭제 + `status='blank'` 처리.
- Toolbar 컨트롤 4종 높이 통일 — `height: 32px` + `.toolbar { align-items: end }`.
- Preview 시트 6행 초과 시 세로 스크롤 — `<table>` 을 `.sheet-scroll`(max-height 189px) 로 감싸고 thead sticky.
- 재분석 시 done 이미지 상태 보존 — `imagesForList` status 에 `accumulatedRows` 함께 반영, `doneSummariesRef` 로 ImageSummary 폴백.
- Device 박스 정렬 — `<fieldset>/<legend>` (legend 가 border 와 겹쳐 캡션 라인이 비는 구조) 를 `<div className="device-field">캡션 + <div className="device">` 2단 구조로 교체. 다른 셀과 동일한 캡션-컨트롤 레이아웃 + border 스타일 통일.
- Preview · Sheet 제목을 `.preview` 박스 바깥(위)으로 이동 — 박스 안쪽 상단의 과한 공백 제거.
- Toolbar 캡션 텍스트를 `<span className="cap">` 으로 감싸 `padding-left: 4px` 적용 — Model/Device/Upload Images 글자를 박스 좌측 끝에서 살짝 안쪽으로 들여 정렬.
- 헤더/캡션 들여쓰기 통일 — h1(Title), h2(Preview · Sheet), `.toolbar .cap`(Model/Device/Upload Images) 모두 `padding-left: 10px` 로 통일.
- Image 미리보기 줌·팬 추가 — `.zoom-stage` 래퍼에 native wheel 리스너(passive 회피)로 1~8× 줌, 줌 상태에서 마우스 드래그로 팬, 더블클릭 시 1× 리셋, 이미지 전환 시 자동 리셋.
- Image 팬 경계 클램프 — `clampPan` 으로 한 축당 `max(0, (img.offsetDim*zoom - stage.offsetDim)/2)` 안으로 제한, 드래그 onMove 와 zoom 변화 useEffect 양쪽에 적용.
- Image 확대 시 우하단 반투명 미니맵 — `.zoom-stage` 우하단에 이미지 종횡비 기반 ≤100px 박스, 내부 viewport 사각형의 위치/크기를 `fracW/H = min(1, stageDim/(imgDim*zoom))` 및 `c = 0.5 − pan/(imgDim*zoom)` 으로 계산. 줌 > 1 일 때만 표시, `pointer-events: none`.
- `local/` 루트의 임시 산출물 4종(`chat_share.html`, `enqueue_0.txt`, `enqueue_decoded.txt`, `enqueue_main.txt`) 제거 — PLAN §6 본문 추출용 ChatGPT 공유 페이지 덤프, 본문 정리 완료로 보존 가치 소실.
- PLAN.md §2 트리를 실제 구조에 맞춰 갱신 — 루트명 `project_gamma` → `CD2_HWD_USW`, `SCHEMA.md`/`TODO.md`/`.gitattributes` 추가, `local/frontend/` Vite+React 골격과 `server/backend/` 구현 파일들에 한 줄 설명 부여. `server/model·data/` 는 서버 전용 디렉토리로 트리에 유지.

## 2026-05-22~24

- `server/backend/verify_qwen.py` 작성 — Qwen3.5-9B GPU 적재 + 멀티모달 추론 단독 검증 (processor / bf16 적재 / chat template / generate 4단계 분리).
- torchvision 0.19.1+cu121 로 ABI 정합 — stable transformers 4.57.6 적재 시 conda torchvision 0.18.0 ↔ user-site torch 2.4.1 의 `torchvision::nms` 누락 해결.
- stable 4.57.6 의 `qwen3_5` model_type 미인식 확정 (4.57.x 가 `qwen3_vl` 로 rename) — HF 모델 카드가 "transformers main 필요" 명시.
- `transformers @main` (5.8.0.dev0) 설치 → `ParallelStyle` NameError → torch 2.5.1+cu121 + torchvision 0.20.1+cu121 업그레이드 (`--timeout 600 --retries 5` 로 PyTorch CDN read timeout 우회), AutoConfig 통과.
- 같은 dev 빌드에서 `CPUOffloadPolicy` ImportError (torch≥2.6 FSDP2 hard import) — driver 535.288.01 은 CUDA 12.4 wheel 미수용으로 torch 추가 업그레이드 차단, main 두더지 잡기 종료.
- transformers v5.x stable tag 매핑 (curl HEAD) → v5.2.0 부터 `qwen3_5`, v5.9.0 까지 FSDP2 hard import 부재 → **`transformers @ v5.9.0` 핀** (`--force-reinstall --no-deps`), AutoConfig + AutoProcessor 통과.
- 모델 weight 4 shard 손상 발견 (declared 19.3 GiB 대비 실제 1.18 GiB) — `huggingface_hub.snapshot_download(allow_patterns=['*.safetensors'])` + `hf_transfer` Rust 가속으로 재다운, 무결성 + 총합 일치 확인.
- verify_qwen.py 실측 통과 — bf16 17.53 GiB / 32.5 tok/s / 한국어 손글씨(시편 23편) 인식.
- `model_registry.py` 에 `_qwen_predict` 어댑터 작성 + `_REGISTRY` 에 `"Qwen3.5-9B"` 등록 — 모듈 전역 lazy 캐시 + JSON 강제 프롬프트 + 코드 펜스 제거 파서 + 단일 generate. 첫 호출 ~161s 적재, 이후 ~8s/이미지.
- README.md 갱신 — "VLM 환경 준비" 섹션 신설 + "서버 환경" 라인을 최종 검증 환경(transformers 5.9.0 / torch 2.5.1+cu121 / torchvision 0.20.1+cu121 / hf_transfer 0.1.9 등) 으로 교체.
- 세션 영속화 자동화 — `requirements.txt` 에 cu121 torch wheel 핀 + ML stack 추가, `bootstrap.sh` 가 transformers `@v5.9.0` git pin (멱등 skip) + 모델 weight 부재 시 `snapshot_download` 까지 처리하도록 확장. 매 세션 `bash bootstrap.sh` 한 줄로 전 환경 복원 가능.
