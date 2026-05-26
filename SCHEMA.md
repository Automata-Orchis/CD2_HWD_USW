# SCHEMA

`frontend ↔ backend ↔ model` 사이에서 주고받는 데이터의 형식 정의.
모든 통신은 FastAPI 기반 HTTP/JSON, 바이너리(이미지)는 `multipart/form-data`.

> PLAN.md §3의 5개 필드(성명·계좌·주민번호·주소·전화)는 예시이며, 실제 추출 항목은 문서 종류에 따라 달라진다. 따라서 필드 집합은 하드코딩하지 않고 신청서 종류별 **Template**(서버 측 `server/backend/templates/<name>.yml`)에 정의한다. 분석 요청 시 frontend 는 선택된 `template_name` 만 보내며 backend 가 그 template 의 `field_spec` 과 `fewshot` 을 읽어 적용한다.

## 0. 작업 단위 — Application

작업·추론·저장의 단위는 **신청서(application)** 다. 한 신청서는 1장의 이미지 또는 N장의 페이지(PDF 내부 페이지) 로 구성된다.

신청서는 **서버에 사전 적재된다.** 관리자가 `server/data/<template_name>/` 폴더에 PDF / 이미지를 직접 배치하고, backend 가 그 폴더를 스캔해 `applications` 테이블에 등록한다 (재스캔 멱등). frontend 는 카테고리(=template)별 통계를 받아 작업자가 카테고리를 선택하면 해당 카테고리의 신청서들을 List 에 띄운다.

- **이미지 파일 1개** → 1장짜리 신청서 1건
- **PDF 파일 1개** → 페이지 수만큼의 N장짜리 신청서 1건 (페이지는 요청 시 즉석 렌더링, 디스크 캐시 없음)
- 같은 신청서에 속한 페이지들은 모델에게 한 번에 전달되어 **단일 ApplicationSummary** (한 명·한 신청서의 결론) 가 산출된다.
- `server/data/original_data/` 등 reserved 폴더는 스캔 대상에서 제외된다.

## 1. 열거형 (Enums)

| 이름 | 값 |
|---|---|
| `Device` | `"cpu"`, `"gpu"` |
| `ImageStatus` | `"blank"`, `"working"`, `"done"` |
| `JobStatus` | `"running"`, `"stopped"`, `"completed"` |

## 2. 기본 타입

### 2.1 FieldSpec — 추출할 필드 정의

```json
{
  "key": "full_name",
  "label": "성명",
  "type": "text"
}
```
- `key` : 시스템 내 식별자 (snake_case 권장)
- `label` : 화면에 표시될 명칭
- `type` : 값의 형식. 초기엔 `"text"`만 사용. 추후 `"number"`, `"date"` 등 확장 가능

### 2.2 FieldResult — 모델 예측값 + 사용자 수정값

```json
{
  "key": "full_name",
  "predicted": "홍길동",
  "accuracy": 0.92,
  "edited": null
}
```
- `accuracy` : `0.0 ~ 1.0`. 모델이 신뢰도를 제공하지 않으면 `null`
- `edited` : 사용자가 수정한 값. 미수정 시 `null`. 최종 저장값은 `edited ?? predicted`

### 2.3 ApplicationInfo

```json
{
  "application_id": "app_a1b2c3d4e5",
  "filename": "홍길동.pdf",
  "status": "working",
  "page_count": 8,
  "template_name": "direct_payment"
}
```
- `application_id` : `app_<sha1(template/filename)[:10]>` — 결정론적, 재스캔 멱등
- `filename` : `server/data/<template>/` 내부 파일명 (PDF 또는 이미지)
- `page_count` : 1 이면 단일 이미지 신청서, ≥2 이면 PDF 내부 페이지 수
- `template_name` : 소속 카테고리 (= yml 파일 stem). 사전 적재 신청서는 모두 값 보유

### 2.4 ApplicationSummary

```json
{
  "application_id": "app_001",
  "status": "done",
  "page_count": 8,
  "fields": [ /* FieldResult, ... */ ]
}
```
- 한 신청서의 모든 페이지를 종합한 단일 결론. `fields` 는 신청서 1건당 1세트.

### 2.5 Job

```json
{
  "job_id": "job_abc",
  "model": "Qwen3.5-9B",
  "device": "gpu",
  "status": "running",
  "field_spec": [ /* FieldSpec, ... */ ],
  "applications": [ /* ApplicationInfo, ... */ ]
}
```

### 2.6 FewshotPair — 모델 프롬프트에 끼우는 텍스트 예시

```json
{
  "user": "이미지에서 ... JSON 객체로만 답하라.",
  "assistant": "{\"full_name\": \"홍길동\", ...}"
}
```
- 이미지를 포함하지 않는 텍스트 user/assistant 페어. 실제 분석 대상 이미지 메시지 앞에 삽입되어 출력 형식을 시연한다.

### 2.7 Template — 신청서 종류 정의

```json
{
  "name": "default",
  "label": "기본 (5필드)",
  "field_spec": [ /* FieldSpec, ... */ ],
  "fewshot":    [ /* FewshotPair, ... */ ]
}
```
- 서버 측 `server/backend/templates/<name>.yml` 에 YAML 로 저장. 매 요청마다 디스크에서 다시 읽으므로 서버 재시작 없이 추가/수정 가능.
- 파일 stem 은 `server/data/<stem>/` 폴더명과 일치해야 한다 (스캔이 stem 으로 폴더를 찾는다).

### 2.8 CategoryStat — 카테고리별 작업 통계

```json
{
  "template_name": "direct_payment",
  "label": "기본직접지불금_지급대상자_등록신청서(농업인용)",
  "total": 12,
  "done": 3,
  "incomplete": 9,
  "rate": 0.25
}
```
- `rate` : `done / total`, `total=0` 이면 `0.0`
- frontend "작업 선택" 대시보드의 Sub Box 한 칸이 1개의 CategoryStat 에 대응

## 3. Endpoints

### 3.1 환경 조회

| Method | Path | Response |
|---|---|---|
| `GET` | `/models` | `{"models": ["Qwen3.5-9B", ...]}` |
| `POST` | `/models/{name}/load` | `{"state": "loading", "progress": 0.0, "error": null}` |
| `GET` | `/models/{name}/status` | `{"state": "...", "progress": 0.0~1.0, "error": null}` |
| `GET` | `/devices` | `{"devices": ["cpu", "gpu"]}` |
| `GET` | `/templates` | `{"templates": [ /* Template, ... */ ]}` |

**모델 적재 상태(`state`)** : `unloaded` / `loading` / `loaded` / `failed`. frontend "모델 로드" 버튼이 `POST /models/{name}/load` 를 호출하면 backend 가 백그라운드 스레드로 가중치를 적재한다. 첫 추론을 lazy 로드로 기다리는 ~161s 의 UX 지연을 피하기 위함. `loading` 중에는 `progress` 가 시간 기반 추정값(실측 적재 ~180s 기준 클램프 0.95)으로 채워지고, 적재 완료 시 worker 가 1.0 으로 갱신. `Mock-Model` 처럼 적재 비용이 없는 모델은 항상 `loaded`. Analyze 시점에 모델이 미적재면 frontend 가 동일한 `POST /models/{name}/load` 를 자동 호출해 같은 적재 경로(`_qwen_load_mutex` 로 단일 적재 보장)에 진입하므로, Load 버튼은 선제 적재의 단축 UX 일 뿐 누르지 않아도 분석은 가능하다.

### 3.2 카테고리(작업) 조회

`GET /work-categories`
→ `{"categories": [ /* CategoryStat, ... */ ]}`

호출 시 backend 가 `server/data/<template>/` 를 스캔해 신규 파일을 자동 인입한 뒤 통계를 산출한다 (매 호출 재스캔). frontend "작업 선택" 버튼이 트리거한다.

`GET /applications?template_name=<name>`
→ `{"applications": [ /* ApplicationInfo, ... */ ]}`

해당 카테고리의 신청서 목록. Sub Box 클릭 시 호출. 동일하게 호출 시점에 디스크 재스캔 후 반환.

### 3.3 페이지 파일 조회

`GET /applications/{application_id}/pages/{ord}/file`
→ 해당 페이지 이미지 (PNG bytes). `ord` 는 0-based.
- PDF 신청서 : `pypdfium2` 로 매 요청 즉석 렌더링 (디스크 캐시 없음, 브라우저 캐시로 흡수).
- 이미지 신청서 : `ord=0` 일 때 원본 파일 그대로 반환.

### 3.4 분석 시작

`POST /analyze`
```json
{
  "application_ids": ["app_001", "app_002"],
  "model": "Qwen3.5-9B",
  "device": "gpu",
  "template_name": "default"
}
```
→ `{"job_id": "job_abc"}`

`template_name` 으로 지정한 Template 의 `field_spec` 과 `fewshot` 이 자동 적용된다. 모델은 각 신청서의 모든 페이지를 한 번에 보고 단일 결과를 산출한다.

### 3.5 분석 정지

`POST /jobs/{job_id}/stop` → `{"status": "stopped"}`
정지 시점까지 완료된 신청서의 결과는 보존된다.

### 3.6 작업 상태 조회

`GET /jobs/{job_id}` → `Job`
프론트엔드는 짧은 간격으로 폴링한다. 추후 WebSocket `/jobs/{job_id}/stream`으로 대체 가능.

### 3.7 신청서 결과 조회

`GET /jobs/{job_id}/applications/{application_id}` → `ApplicationSummary`

### 3.8 사용자 수정 저장

`PUT /jobs/{job_id}/applications/{application_id}`
```json
{ "fields": [ /* FieldResult, ... */ ] }
```
→ `ApplicationSummary` (서버 반영본)

### 3.9 신청서 완료 처리

`POST /jobs/{job_id}/applications/{application_id}/complete` → `ApplicationSummary` (`status: "done"`)

### 3.10 시트 미리보기 / 내보내기

`GET /jobs/{job_id}/sheet`
→ 행 = 신청서, 열 = `field_spec` 순서. 값은 `edited ?? predicted`.
```json
{
  "columns": [{"key": "full_name", "label": "성명"}, ...],
  "rows": [
    {"application_id": "app_001", "values": {"full_name": "홍길동", ...}}
  ]
}
```

## 4. 에러 응답

모든 에러는 동일 형식:
```json
{ "error": "code_string", "message": "사람이 읽을 메시지" }
```

## 5. 범위 밖 (미정)

이 문서가 아직 다루지 않는 항목 — 필요 시점에 본 문서에 추가한다.

- 인증 / 권한
- DB 스키마 (PLAN.md §1의 "Database에 저장" 요구사항)
- 다중 작업자 동시 편집 시 충돌 처리
- 이미지 파일 크기·형식 제한
- 여러 이미지 파일을 하나의 신청서로 묶는 그룹핑 (현재는 PDF 1파일=1신청서 또는 이미지 1파일=1신청서)
- 관리자용 사전 적재 / 폴더 관리 UI (현재 서버 쉘에서 파일 배치)
