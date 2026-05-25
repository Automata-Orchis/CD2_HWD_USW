고려 사항
- JSON 출력 강건화 — 이미지마다 모델 응답 형식이 달라 `_qwen_predict` 파서를 지속적으로 보강.

검증 대상
- frontend `/analyze` 의 Qwen3.5-9B end-to-end 통합 동작(필드 채움 / JSON 파싱 / 두 번째 이미지부터 ~8s/장) 실측 미완.
- 빈 `fewshot: []` 로 default 양식이 실용 정확도를 내는지, 어떤 양식에서 fewshot 보강이 필요한지 실측 미완.
- Stop 후 backend 재기동 시 first-call cost(~161s) 재발생 여부 + SQLite `done` 결과 보존 여부 미확인.
- cloudflared 임의 종료 시 `run.sh` 가 새 trycloudflare URL 출력으로 복구되는지 미실측.

개선 대상
- DB 조회 GUI — `python -m sqlite_utils` 가 불편하므로 별도 팝업창 형태의 GUI 접근 방식 도입.
- 이미지 소스 전환 — 작업자 업로드 누적 방식을 폐기하고 서버에 사전 저장된 이미지를 frontend 에서 선택하는 구조로 전환.
- 신청서별 디렉토리 분류 — `server/data/<신청서종류>/` (예: `직불금신청서/`) 단위로 이미지 보관 (한글 경로 문제 시 변경 여지).
- 작업 선택 UX — frontend 에 신청서 종류별 진행도(전체/완료) 표시 + 미완료 처리 + 완료 이미지 재수정 흐름.
- 로그인 + 작업자 추적 — frontend 로그인으로 직원 소속/이름 수집 → DB `worker` 컬럼에 기록.
- DB 컬럼 확장 — 이미지 경로 / 추출 내용 / 작업 상태 / 작업자 / 작업 종료일 기본, 진행 따라 추가.
- 다중 페이지 신청서 — PDF 8장 또는 이미지 N장을 하나의 신청서로 묶어 단일 Image Summary 를 산출하도록 `_qwen_predict` 확장.

추후 개선 대상
- 모델 캐시 정리 — 두 번째 VLM 어댑터 추가 직전에 "단일 VLM 슬롯" 정책(이전 모델 `del` + `torch.cuda.empty_cache()`) 도입 (미도입 시 즉시 OOM).
- Device(CPU/GPU) 라우팅 — 어댑터가 `device_map="auto"` 고정이라 frontend 라디오 버튼이 no-op, `_run_job` 이 `req.device` 를 어댑터에 전달하도록 시그니처 확장.
- Stop 입도 — 진행 중 단일 이미지 추론은 cancel 불가, 즉시 중단하려면 추론을 별도 프로세스로 분리 후 SIGTERM 종료하는 구조 변경.
- frontend 폴링 종료 — terminal status(`completed`/`stopped`) 이후에도 `App.jsx` 의 `setInterval` 이 매초 3 GET 발생, 종료 분기 추가.
- cloudflared URL 갱신 — 재시작 시 발급되는 새 trycloudflare URL 을 frontend `.env` 에 수동 반영하는 흐름 자동화.
- 결과 export — Preview 시트 내용을 CSV/Excel 파일로 내보내는 기능 추가.
- 작업 보존 — 분석 도중 backend 강제 종료 시 SQLite 까지 진행한 결과로부터 사용자 시각의 복귀 흐름 정립.
- 추론 가속 — bf16 17.5 GiB / ~8s/장에서 더 빠르게 하려면 INT8/INT4 quantization 또는 대체 모델 후보 검토.
