고려 사항
- 이미지에 따라 json 출력이 상이할 수 있음. 지속적으로 신경써야 하는 부분임.

현재 검증 사항
- enable_thinking=False 통합 경로 검증 — `model_registry.py` 의 `_qwen_predict` 가 frontend 분석 요청에 대해 동일하게 안정적인지(Image Summary 필드 채움, JSON 파싱 일관성) 미검증.
- Qwen3.5-9B 두 번째 이후 이미지 처리 속도(~8s/장) 일관성 — 같은 uvicorn 프로세스 안에서 모듈 캐시 재사용이 실측대로 동작하는지.
- Stop 도중 backend 종료 후 재기동 시 모델 재적재 거동 — first-call cost(~161s)가 재발생하는지, SQLite 의 기존 `done` 결과는 보존되는지.
- cloudflared 자동 재시작 거동 — 임의로 cloudflared 프로세스를 종료시켰을 때 `run.sh` 의 재시도 루프가 새 trycloudflare URL 을 stderr 에 출력하며 복구되는지.

현재 결정 사항
- 신청서별 추출 정보 가변 처리 방향. 이 결정이 few-shot 구성, frontend Form Type UI 도입 여부, Preview sheet 동작 모두에 영향.
  - **A. Form Template 방식**: 신청서 타입마다 사전 정의된 template(field_spec + 자체 few-shot)을 등록. frontend 가 template 을 선택해 backend 에 전송. 출력 스키마 예측 가능, 정확도 우선.
  - **B. 완전 auto-discovery**: Qwen 이 이미지에서 식별 가능한 모든 항목을 자유 추출. 사전 정의 불필요. 출력 스키마 가변, hallucination 위험, Preview sheet 컬럼 정렬이 매 이미지마다 달라짐.
  - **C. 하이브리드**: A 베이스 + 새 양식을 처음 마주칠 시 B 로 1차 추출 → 사용자가 결과를 검토해 template 으로 등재.

미래 개선 사항
- `model_registry` 의 모델 캐시가 모듈 전역 변수(`_qwen_model` 등) + eviction 메커니즘 없음. 현재는 Qwen3.5-9B 가 첫 분석 후 uvicorn 프로세스 수명 동안 GPU(~22 GiB) 를 영구 점유한다. Mock-Model 만 있는 지금은 무해하지만, **두 번째 VLM 어댑터를 추가하는 순간 즉시 OOM 위험** (Qwen 17.5 GiB + 신규 VLM 10~15 GiB > 24 GiB). 추가로 같은 모델을 별도 프로세스(예: 단독 verify_qwen.py)에서 띄울 때도 uvicorn 의 VRAM 점유 때문에 `device_map="auto"` 가 CPU offload 로 떨어져 추론 속도가 10~30배 느려지는 부수 증상이 발생한다. 권장 처방은 "단일 VLM 슬롯 정책" — 새 VLM 호출 시 이전 모델 `del` + `torch.cuda.empty_cache()` 후 적재. 두 번째 VLM 어댑터 작성 직전에 처리.
- Qwen3.5-9B 어댑터에 Device(CPU/GPU) 라우팅 미구현 — 현재 `device_map="auto"` 고정, frontend 라디오 버튼이 no-op. `_run_job` 이 `req.device` 를 어댑터에 전달하도록 시그니처 확장 필요. 단 9B 모델 CPU 추론은 실용 속도가 아니므로 안내 메시지로 차단하는 안도 함께 검토.
- Stop 의 작업 중단 입도가 "이미지 사이" 뿐 — `run_in_executor` 의 동기 스레드 안에서 도는 model 추론/적재는 cancel 불가. 진행 중인 단일 이미지 추론을 즉시 끊으려면 추론을 별도 프로세스로 분리 후 SIGTERM 으로 종료하는 구조 변경이 필요.
- frontend 폴링(`App.jsx:65` 의 `setInterval(tick, 1000)`)이 jobId 가 살아 있는 동안 job.status 와 무관하게 무한 반복 — 분석 완료(`completed`/`stopped`) 후에도 매초 3개 GET 이 발생한다. terminal status 진입 시 폴링을 종료하도록 분기 추가 권장.
- .env 파일에 직접 접근하여 cloudflared의 url을 갱신하는 과정이 매우 번거롭다. cloudflared가 끊겼을 경우 재시작된 cloudflared의 url을 쉽게 변경할 수 있는 방법을 제시하라.
- Preview에 작성된 대로 그 결과를 파일로서 내놓는 기능이 빠져있다. 이를 추가하라.
- 작업 진행 도중 예기치 못한 상황으로 인해 강제적으로 종료될 경우, 그 이전 시점까지의 작업이 사라지지 않도록 할 방법을 제시하라.
- 추론 속도 — bf16 17.5 GiB / ~8s/장. 더 가속하려면 quantization(INT8/INT4) 또는 다른 모델 후보 검토.
