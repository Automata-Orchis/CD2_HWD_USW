# TODO

## 검증 대상

- **Qwen3.5-9B end-to-end** — `/analyze` 통합 동작과 두 번째 이미지부터 ~8s/장 시간 실측 미완.
- **default 양식 실용 정확도** — 빈 `fewshot: []` 로 충분한지, 어떤 양식에서 fewshot 보강이 필요한지 미실측.
- **Stop 후 재기동 시 결과 보존** — first-call ~161s 재발생 여부와 SQLite `done` 결과 보존 미확인.
- **cloudflared 자동 복구** — 임의 종료 시 `run.sh` 가 새 trycloudflare URL 출력으로 복구되는지 미실측.
- **다중 페이지 PDF e2e** — `pypdfium2 scale=2.0` 분할의 한글 손글씨 가독성, N장 동시 입력의 VRAM/시간 증가 폭, 페이지 정보의 단일 JSON 통합 정확도 미실측.

## 고려 사항

- **JSON 출력 강건화** — 이미지마다 모델 응답 형식이 달라 `_qwen_predict` 파서를 지속 보강.

## 개선 대상

- **DB 조회 GUI** — `python -m sqlite_utils` 가 불편하므로 별도 팝업 GUI 도입.
- **이미지 소스 전환** — 작업자 업로드 누적 방식 폐기, 서버 사전 저장 이미지를 frontend 에서 선택하는 구조로 전환.
- **신청서별 디렉토리 분류** — `server/data/<신청서종류>/` (예: `직불금신청서/`) 단위로 이미지 보관 (한글 경로 이슈 시 변경 여지).
- **작업 선택 UX** — frontend 에 신청서 종류별 진행도(전체/완료) 표시, 미완료 처리, 완료 신청서 재수정 흐름.
- **로그인 + 작업자 추적** — frontend 로그인으로 직원 소속/이름 수집 → DB `worker` 컬럼 기록.
- **DB 컬럼 확장** — 이미지 경로 / 추출 내용 / 작업 상태 / 작업자 / 작업 종료일 기본, 진행에 따라 추가.
- **이미지 N장 그룹핑 UX** — PDF 외 다중 이미지 신청서 그룹핑 미구현. PLAN.md §8 의 "Upload 1회 = 신청서 1건" 안 권장. 백엔드 DB/모델은 이미 신청서 단위라 `/upload` 와 frontend 업로드 핸들러만 손보면 된다.
- **표 형태 입력 정보 저장 방식** — 신청서에 표가 있을 경우 어떤 스키마/UI 로 저장할지 미정.

## 추후 개선 대상

- **모델 캐시 정리** — 두 번째 VLM 어댑터 추가 직전, 이전 모델 `del` + `torch.cuda.empty_cache()` 의 "단일 VLM 슬롯" 정책 도입 (미도입 시 즉시 OOM).
- **Device 라우팅** — 어댑터가 `device_map="auto"` 고정이라 frontend 라디오가 no-op. `_run_job` 이 `req.device` 를 어댑터에 전달하도록 시그니처 확장.
- **Stop 입도** — 진행 중 단일 이미지 추론은 cancel 불가. 즉시 중단하려면 추론을 별도 프로세스로 분리 후 SIGTERM 종료.
- **frontend 폴링 종료** — terminal status(`completed`/`stopped`) 이후에도 `App.jsx` 의 `setInterval` 이 매초 3 GET 발생, 종료 분기 추가.
- **cloudflared URL 자동 갱신** — 재시작 시 발급되는 새 URL 을 frontend `.env` 에 수동 반영하는 흐름 자동화.
- **결과 export** — Preview 시트 내용을 CSV/Excel 파일로 내보내기.
- **작업 보존** — 분석 도중 backend 강제 종료 시 SQLite 진행 결과로부터 사용자 시각의 복귀 흐름 정립.
- **추론 가속** — bf16 17.5 GiB / ~8s/장에서 INT8/INT4 quantization 또는 대체 모델 후보 검토.
