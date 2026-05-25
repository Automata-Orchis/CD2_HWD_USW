# SCHEMA

`frontend ↔ backend ↔ model` 사이에서 주고받는 데이터의 형식 정의.
모든 통신은 FastAPI 기반 HTTP/JSON, 바이너리(이미지)는 `multipart/form-data`.

> PLAN.md §3의 5개 필드(성명·계좌·주민번호·주소·전화)는 예시이며, 실제 추출 항목은 문서 종류에 따라 달라진다. 따라서 필드 집합은 하드코딩하지 않고 신청서 종류별 **Template**(서버 측 `server/backend/templates/<name>.yml`)에 정의한다. 분석 요청 시 frontend 는 선택된 `template_name` 만 보내며 backend 가 그 template 의 `field_spec` 과 `fewshot` 을 읽어 적용한다.

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

### 2.3 ImageInfo

```json
{
  "image_id": "img_001",
  "filename": "001.jpg",
  "status": "working"
}
```

### 2.4 ImageSummary

```json
{
  "image_id": "img_001",
  "status": "done",
  "fields": [ /* FieldResult, ... */ ]
}
```

### 2.5 Job

```json
{
  "job_id": "job_abc",
  "model": "Qwen3.5-9B",
  "device": "gpu",
  "status": "running",
  "field_spec": [ /* FieldSpec, ... */ ],
  "images": [ /* ImageInfo, ... */ ]
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

## 3. Endpoints

### 3.1 환경 조회

| Method | Path | Response |
|---|---|---|
| `GET` | `/models` | `{"models": ["Qwen3.5-9B", ...]}` |
| `GET` | `/devices` | `{"devices": ["cpu", "gpu"]}` |
| `GET` | `/templates` | `{"templates": [ /* Template, ... */ ]}` |

### 3.2 이미지 업로드

`POST /upload` — `multipart/form-data`, 필드명 `files[]`
→ `{"images": [ /* ImageInfo, ... */ ]}`

### 3.3 분석 시작

`POST /analyze`
```json
{
  "image_ids": ["img_001", "img_002"],
  "model": "Qwen3.5-9B",
  "device": "gpu",
  "template_name": "default"
}
```
→ `{"job_id": "job_abc"}`

`template_name` 으로 지정한 Template 의 `field_spec` 과 `fewshot` 이 자동 적용된다.

### 3.4 분석 정지

`POST /jobs/{job_id}/stop` → `{"status": "stopped"}`
정지 시점까지 완료된 이미지의 결과는 보존된다.

### 3.5 작업 상태 조회

`GET /jobs/{job_id}` → `Job`
프론트엔드는 짧은 간격으로 폴링한다. 추후 WebSocket `/jobs/{job_id}/stream`으로 대체 가능.

### 3.6 이미지 결과 조회

`GET /jobs/{job_id}/images/{image_id}` → `ImageSummary`

### 3.7 사용자 수정 저장

`PUT /jobs/{job_id}/images/{image_id}`
```json
{ "fields": [ /* FieldResult, ... */ ] }
```
→ `ImageSummary` (서버 반영본)

### 3.8 이미지 완료 처리

`POST /jobs/{job_id}/images/{image_id}/complete` → `ImageSummary` (`status: "done"`)

### 3.9 시트 미리보기 / 내보내기

`GET /jobs/{job_id}/sheet`
→ 행 = 이미지, 열 = `field_spec` 순서. 값은 `edited ?? predicted`.
```json
{
  "columns": [{"key": "full_name", "label": "성명"}, ...],
  "rows": [
    {"image_id": "img_001", "values": {"full_name": "홍길동", ...}}
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
