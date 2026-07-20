# Fitback AI

Fitback AI는 Fitback 매장 관리 어시스턴트를 위한 FastAPI AI 계약 서버와 Neo4j 그래프 프로젝션 작업 공간입니다.

현재 이 저장소는 두 가지 기능을 제공합니다.

- Spring Boot 서버가 호출할 수 있는 FastAPI AI HTTP 계약 구현
- 실제 서비스 그래프 초기화, Neo4j AuraDB 적재, 그래프 카운트 검증

현재 FastAPI 응답은 `OPENAI_API_KEY` 또는 `AI_API_KEY`가 설정되어 있으면 OpenAI API를 호출하고, 키가 없으면 로컬 개발용 결정적 휴리스틱으로 생성됩니다.

## 먼저 확인할 것

- 실제 업무 데이터의 원천은 RDS 기반 메인 백엔드입니다.
- AuraDB는 AI 검색, 관계 탐색, 이벤트 타겟팅, 추천 근거 생성을 위한 그래프 프로젝션입니다.
- `.env`에는 실제 AuraDB 인증 정보가 들어가므로 커밋하거나 출력하지 않습니다.
- `.env.example`은 필요한 환경 변수 형식을 보여주는 안전한 참고 파일입니다.
- `*상담메모_예시.xlsx` 같은 샘플 스프레드시트와 `.xlsx` 파일은 Git에서 제외합니다.
- 처음에는 업무 데이터가 없어도 Neo4j schema와 온톨로지 노드만 먼저 초기화할 수 있습니다.

## 저장소 구조

```text
.
├── README.md
├── .env.example
├── requirements.txt
├── pyproject.toml
├── sql.example
├── docs/
│   └── fastapi요구사항.md
├── src/
│   └── fitback_ai/
│       ├── api.py
│       ├── api_models.py
│       ├── ai_provider.py
│       ├── ai_service.py
│       ├── cli.py
│       ├── config.py
│       ├── graph_persistence.py
│       ├── ontology.py
│       └── neo4j_loader.py
└── tests/
    ├── test_api.py
    ├── test_fastapi_contract.py
    ├── test_graph_persistence.py
    ├── test_neo4j_loader.py
    └── test_ontology.py
```

주요 파일:

- `src/fitback_ai/api.py`: FastAPI 앱과 라우트 선언
- `src/fitback_ai/api_models.py`: Pydantic 요청/응답 모델, camelCase alias, enum/date/UUID 검증
- `src/fitback_ai/ai_service.py`: FastAPI route에서 AI provider를 호출하는 facade
- `src/fitback_ai/ai_provider.py`: OpenAI API provider와 로컬 휴리스틱 provider
- `tests/test_api.py`, `tests/test_fastapi_contract.py`: FastAPI 계약 테스트
- `src/fitback_ai/graph_persistence.py`: RDS 저장 완료 projection을 AuraDB graph projection으로 upsert
- `src/fitback_ai/ontology.py`: AI 판단과 그래프 적재가 공유하는 온톨로지 코드북
- `src/fitback_ai/neo4j_loader.py`: Neo4j schema 설정, ontology sync, graph upsert, count 검증
- `src/fitback_ai/cli.py`: `init`, `load`, `verify` 명령
- `sql.example`: 목표 RDS 스타일 업무 schema 참고 자료
- `docs/fastapi요구사항.md`: Spring-to-FastAPI HTTP API 계약 문서

## 설치

PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
```

현재 주요 의존성:

- `fastapi==0.139.0`
- `uvicorn==0.38.0`
- `neo4j==5.28.1`
- `openai==2.44.0`
- `pytest==8.4.1`
- `httpx==0.28.1`

## FastAPI 서비스

OpenAI 연동 환경 변수:

```env
AI_PROVIDER=auto
OPENAI_API_KEY=your-openai-api-key
OPENAI_MODEL=gpt-4.1-mini
OPENAI_BASE_URL=https://api.openai.com/v1
AI_TIMEOUT_SECONDS=25
```

`AI_PROVIDER=auto`에서는 `OPENAI_API_KEY` 또는 호환 alias인 `AI_API_KEY`가 있으면 OpenAI API를 사용하고, 키가 없으면 로컬 휴리스틱을 사용합니다. 운영에서는 `OPENAI_API_KEY`를 권장합니다.

로컬 AI 서버 실행:

```powershell
.\.venv\Scripts\python -m uvicorn fitback_ai.api:app --host 0.0.0.0 --port 8000
```

Spring 개발 환경에서는 `AI_BASE_URL`을 다음 주소로 설정합니다.

```text
http://localhost:8000
```

API 문서:

- Swagger UI: `http://localhost:8000/docs`
- OpenAPI JSON: `http://localhost:8000/openapi.json`

구현된 엔드포인트:

| 기능 | Method | Path |
|---|---|---|
| 문의 내용 중간 평가 | `POST` | `/ai/v1/inquiries/check-preview` |
| 상담 내용 중간 평가 | `POST` | `/ai/v1/consultations/check-preview` |
| 상담 AI 분석 | `POST` | `/ai/v1/consultations/analyze` |
| RDS/AuraDB graph sync | `POST` | `/ai/v1/graph/consultations/sync` |
| 다음 행동 추천 | `POST` | `/ai/v1/consultations/next-action` |
| 고객 메시지 생성 | `POST` | `/ai/v1/messages/generate` |

계약 동작:

- 요청/응답 JSON 필드명은 camelCase를 사용합니다.
- UUID, 날짜, offset 포함 일시, 문서화된 enum 값은 Pydantic/FastAPI가 검증합니다.
- 잘못된 요청 body는 FastAPI validation error와 함께 `422`를 반환합니다.
- 처리 중 `RuntimeError`가 발생하면 다음 JSON 형식의 `500` 응답을 반환합니다.

```json
{
  "detail": "AI processing failed",
  "code": "AI_PROCESSING_FAILED"
}
```

- 성공 응답은 JSON object입니다.
- 필수 응답 문자열은 `null`, 빈 문자열, 공백 문자열로 반환하지 않습니다.
- 빈 목록은 `null` 대신 `[]`로 반환합니다.

## FastAPI 호출 예시

문의 내용 중간 평가:

```powershell
Invoke-RestMethod -Method Post `
  -Uri http://localhost:8000/ai/v1/inquiries/check-preview `
  -ContentType "application/json" `
  -Body '{
    "rawText": "가격과 주 3회 PT 가능 여부를 문의했습니다.",
    "serviceName": "퍼스널 트레이닝",
    "inquiryStatus": "RECEIVED",
    "customerInfo": {
      "name": "홍길동",
      "gender": "MALE",
      "birthDate": "1995-04-12"
    }
  }'
```

고객 메시지 생성:

```powershell
Invoke-RestMethod -Method Post `
  -Uri http://localhost:8000/ai/v1/messages/generate `
  -ContentType "application/json" `
  -Body '{
    "customer": {
      "customerId": "6c2d9b87-90aa-4ce2-96cb-a0875f103f04",
      "name": "홍길동",
      "preferredContactChannel": "KAKAO",
      "status": "PENDING"
    },
    "latestConsultation": {
      "consultationId": "6570aa21-d458-4885-9e69-d984fea51830",
      "summary": "가격 부담으로 보류"
    },
    "aiInsight": {
      "leadTemperature": "WARM",
      "priorityScore": 75
    },
    "nonConversionReasons": [
      {
        "reasonType": "PRICE",
        "role": "PRIMARY",
        "reasonBasis": "가격 부담"
      }
    ],
    "nextBestAction": {
      "title": "예산에 맞는 상품 안내",
      "description": "예산별 상품을 제안합니다."
    },
    "event": null,
    "messageOptions": {
      "tonePreset": "FRIENDLY",
      "versionType": "STANDARD"
    }
  }'
```

## 버튼 액션별 입력/출력 예시

사용자가 LLM에 직접 질문을 입력하지 않습니다. 화면의 버튼을 누르면 프론트/Spring이 현재 화면의 고객, 문의, 상담, 분석 데이터를 정해진 FastAPI 요청 body로 조립하고, FastAPI가 OpenAI provider를 호출해 계약된 JSON object를 반환합니다.

아래 `AI 출력` 값은 `2026-07-18`에 `AI_PROVIDER=heuristic`을 명시하고 FastAPI `TestClient`로 실제 endpoint를 호출해 받은 응답입니다.

### 1. 문의 내용 중간 평가

사용자 액션:

```text
문의 등록 화면에서 `문의 내용 검토` 버튼 클릭
```

처리 흐름:

프론트/Spring이 문의 메모, 서비스명, 문의 상태, 고객 기본 정보를 모아 `/ai/v1/inquiries/check-preview`로 POST합니다. 응답은 저장 전 AI가 확인한 7개 고정 항목과 확인 여부로 표시합니다.

FastAPI 입력:

```json
{
  "rawText": "가격과 주 3회 PT 가능 여부를 문의했습니다.",
  "serviceName": "퍼스널 트레이닝",
  "inquiryStatus": "RECEIVED",
  "customerInfo": {
    "name": "홍길동",
    "gender": "MALE",
    "birthDate": "1995-04-12"
  }
}
```

AI 출력:

```json
{
  "confirmedCount": 3,
  "totalCount": 7,
  "items": [
    {
      "key": "INTEREST_SERVICE",
      "label": "관심 상품",
      "confirmed": true,
      "value": "퍼스널 트레이닝"
    },
    {
      "key": "EXERCISE_GOAL",
      "label": "운동 목적",
      "confirmed": false,
      "value": "아직 확인되지 않음"
    },
    {
      "key": "EXERCISE_EXPERIENCE",
      "label": "운동 경험",
      "confirmed": true,
      "value": "운동 경험이 언급됨"
    },
    {
      "key": "INJURY_HISTORY",
      "label": "부상 이력",
      "confirmed": false,
      "value": "아직 확인되지 않음"
    },
    {
      "key": "CUSTOMER_REQUEST",
      "label": "고객 요청",
      "confirmed": true,
      "value": "고객 요청이 언급됨"
    },
    {
      "key": "COUNSELOR_RESPONSE",
      "label": "나의 응대",
      "confirmed": false,
      "value": "아직 확인되지 않음"
    },
    {
      "key": "SPECIAL_NOTE",
      "label": "특이사항",
      "confirmed": false,
      "value": "아직 확인되지 않음"
    }
  ]
}
```

### 2. 상담 내용 중간 평가

사용자 액션:

```text
상담 등록 화면에서 `상담 메모 검토` 버튼 클릭
```

처리 흐름:

프론트/Spring이 상담 메모, 서비스명, 고객 기본 정보를 모아 `/ai/v1/consultations/check-preview`로 POST합니다. 응답은 상담 저장 전 AI가 확인한 7개 고정 항목과 확인 여부로 표시합니다.

FastAPI 입력:

```json
{
  "rawText": "체중 감량을 목표로 평일 저녁 운동 가능 여부를 상담했습니다.",
  "serviceName": "퍼스널 트레이닝",
  "customerInfo": {
    "name": "홍길동",
    "gender": "MALE",
    "birthDate": "1995-04-12"
  }
}
```

AI 출력:

```json
{
  "confirmedCount": 3,
  "totalCount": 7,
  "items": [
    {
      "key": "INTEREST_SERVICE",
      "label": "관심 상품",
      "confirmed": true,
      "value": "퍼스널 트레이닝"
    },
    {
      "key": "EXERCISE_GOAL",
      "label": "운동 목적",
      "confirmed": true,
      "value": "운동 목표가 언급됨"
    },
    {
      "key": "EXERCISE_EXPERIENCE",
      "label": "운동 경험",
      "confirmed": false,
      "value": "아직 확인되지 않음"
    },
    {
      "key": "INJURY_HISTORY",
      "label": "부상 이력",
      "confirmed": false,
      "value": "아직 확인되지 않음"
    },
    {
      "key": "CUSTOMER_REQUEST",
      "label": "고객 요청",
      "confirmed": true,
      "value": "고객 요청이 언급됨"
    },
    {
      "key": "COUNSELOR_RESPONSE",
      "label": "나의 응대",
      "confirmed": false,
      "value": "아직 확인되지 않음"
    },
    {
      "key": "SPECIAL_NOTE",
      "label": "특이사항",
      "confirmed": false,
      "value": "아직 확인되지 않음"
    }
  ]
}
```

### 3. 상담 AI 분석

사용자 액션:

```text
상담 상세 화면에서 `AI 상담 분석` 버튼 클릭
```

처리 흐름:

프론트/Spring이 고객 정보, 상담 원문, 상담 상품, 매장 context, 첨부 상담 자료를 모아 `/ai/v1/consultations/analyze`로 POST합니다. 응답은 상담 요약, 고객 온도, 미전환 사유, 다음 행동, 후속 연락 정보로 저장하거나 화면에 표시합니다.

FastAPI 입력:

```json
{
  "customer": {
    "customerId": "6c2d9b87-90aa-4ce2-96cb-a0875f103f04",
    "name": "홍길동",
    "gender": "MALE",
    "birthDate": "1995-04-12",
    "phoneNum": "010-1234-5678",
    "preferredContactChannel": "KAKAO",
    "status": "PENDING",
    "inflowPathId": "71564cdc-6ad1-4978-a74e-150c576ce13c",
    "inflowPathName": "인스타그램"
  },
  "consultation": {
    "consultationId": "6570aa21-d458-4885-9e69-d984fea51830",
    "sessionNo": 1,
    "consultedAt": "2026-07-09T14:30:00+09:00",
    "consultedServiceId": "88d53bb7-7210-4e77-a0c4-01778a54d68d",
    "stage": "CONSULTATION",
    "sourceType": "DIRECT",
    "rawText": "체중 감량이 목표이고 가격을 고민 중입니다."
  },
  "service": {
    "serviceId": "88d53bb7-7210-4e77-a0c4-01778a54d68d",
    "serviceName": "퍼스널 트레이닝",
    "description": "주 3회 1:1 트레이닝",
    "price": 600000
  },
  "storeContext": {
    "storeId": "28f43532-f2fc-4581-827e-880d06f3cd88",
    "storeType": "GYM",
    "registrationStatus": "PENDING"
  },
  "attachedMaterials": [
    {
      "materialType": "OTHER",
      "title": "kakao-chat",
      "content": "고객: PT 가격 문의드립니다.\n상담사: 현재 6개월권 이벤트가 있습니다."
    }
  ]
}
```

AI 출력:

```json
{
  "summary": "홍길동 고객은 퍼스널 트레이닝 상담에서 PRICE 관련 보류 신호를 보였습니다.",
  "customerInsight": {
    "leadTemperature": "WARM",
    "temperatureBasis": "퍼스널 트레이닝 상담 내용과 PRICE 신호를 함께 고려했습니다.",
    "priorityScore": 80
  },
  "nonConversionReasons": [
    {
      "reasonType": "PRICE",
      "role": "PRIMARY",
      "reasonBasis": "체중 감량이 목표이고 가격을 고민 중입니다.",
      "confidence": "HIGH"
    }
  ],
  "nextBestAction": {
    "title": "예산 맞춤 상품 안내",
    "description": "퍼스널 트레이닝 선택지를 예산별로 정리해 부담을 낮춥니다."
  },
  "followUp": {
    "recommendContactDate": "2026-07-12",
    "memo": "KAKAO로 예산 맞춤 상품 안내 내용을 안내"
  },
  "followUpInsight": {
    "persuasionPoint": {
      "keyMessage": "퍼스널 트레이닝 선택지를 예산별로 정리해 부담을 낮춥니다."
    },
    "cautionNote": "PRICE 이슈를 압박하지 말고 선택지를 제안합니다.",
    "actionBasis": {
      "title": "예산 맞춤 상품 안내",
      "description": "퍼스널 트레이닝 선택지를 예산별로 정리해 부담을 낮춥니다."
    }
  }
}
```

### 4. 다음 행동 추천

사용자 액션:

```text
고객 상세 또는 상담 상세 화면에서 `다음 행동 추천` 버튼 클릭
```

처리 흐름:

프론트/Spring이 고객 상태, 최근 상담 요약, 기존 AI 분석 결과를 모아 `/ai/v1/consultations/next-action`으로 POST합니다. 응답은 우선순위와 다음 행동, follow-up 일정 추천으로 사용합니다.

FastAPI 입력:

```json
{
  "customer": {
    "customerId": "6c2d9b87-90aa-4ce2-96cb-a0875f103f04",
    "status": "PENDING"
  },
  "latestConsultation": {
    "consultationId": "6570aa21-d458-4885-9e69-d984fea51830",
    "summary": "가격 부담으로 보류",
    "rawText": "가격이 부담되어 고민 중입니다."
  },
  "aiAnalysis": {
    "leadTemperature": "WARM",
    "temperatureBasis": "운동 의사는 명확하지만 가격 고민이 있습니다.",
    "nonConversionReasons": [
      {
        "reasonType": "PRICE",
        "role": "PRIMARY",
        "reasonBasis": "가격 부담"
      }
    ]
  }
}
```

AI 출력:

```json
{
  "priorityScore": 80,
  "nextBestAction": {
    "title": "예산 맞춤 상품 안내",
    "description": "상담 상품 선택지를 예산별로 정리해 부담을 낮춥니다."
  },
  "followUp": {
    "recommendContactDate": "2026-07-26",
    "memo": "예산 맞춤 상품 안내 후속 연락"
  },
  "followUpInsight": {
    "persuasionPoint": {
      "keyMessage": "상담 상품 선택지를 예산별로 정리해 부담을 낮춥니다."
    },
    "cautionNote": "PRICE 이슈를 압박하지 말고 선택지를 제안합니다.",
    "actionBasis": {
      "title": "예산 맞춤 상품 안내",
      "description": "상담 상품 선택지를 예산별로 정리해 부담을 낮춥니다."
    }
  }
}
```

### 5. 고객 메시지 생성

사용자 액션:

```text
후속 연락 화면에서 `고객 메시지 생성` 버튼 클릭
```

처리 흐름:

프론트/Spring이 고객 정보, 최근 상담 요약, AI insight, 미전환 사유, 다음 행동, 메시지 옵션을 모아 `/ai/v1/messages/generate`로 POST합니다. 응답은 담당자가 발송 전에 확인하고 수정할 수 있는 메시지 초안으로 표시합니다.

FastAPI 입력:

```json
{
  "customer": {
    "customerId": "6c2d9b87-90aa-4ce2-96cb-a0875f103f04",
    "name": "홍길동",
    "preferredContactChannel": "KAKAO",
    "status": "PENDING"
  },
  "latestConsultation": {
    "consultationId": "6570aa21-d458-4885-9e69-d984fea51830",
    "summary": "가격 부담으로 보류"
  },
  "aiInsight": {
    "leadTemperature": "WARM",
    "priorityScore": 75
  },
  "nonConversionReasons": [
    {
      "reasonType": "PRICE",
      "role": "PRIMARY",
      "reasonBasis": "가격 부담"
    }
  ],
  "nextBestAction": {
    "title": "예산에 맞는 상품 안내",
    "description": "예산별 상품을 제안합니다."
  },
  "event": null,
  "messageOptions": {
    "tonePreset": "FRIENDLY",
    "versionType": "STANDARD",
    "additionalInstruction": "첫 문장에 고객 이름을 넣어 주세요."
  }
}
```

AI 출력:

```json
{
  "content": "홍길동님, 상담 때 말씀해주신 부분을 바탕으로 예산에 맞는 상품 안내 안내를 드립니다. 예산별 상품을 제안합니다. PRICE 부담을 줄일 수 있게 선택지를 정리했습니다. 첫 문장에 고객 이름을 넣어 주세요.",
  "versionType": "STANDARD",
  "tonePreset": "FRIENDLY"
}
```

## 테스트

전체 테스트:

```powershell
.\.venv\Scripts\python -m pytest -q
```

빠른 확인:

```powershell
.\.venv\Scripts\python -m compileall -q src tests
.\.venv\Scripts\python -m pytest -q tests\test_api.py
```

API 테스트 범위:

- `/openapi.json`에 5개 POST path가 존재하는지 확인
- `/docs` 접근 가능 여부 확인
- camelCase 요청/응답 처리 확인
- preview 응답이 `confirmedCount`, `totalCount`, 7개 고정 `items`를 반환하는지 확인
- 분석 요청이 `attachedMaterials` 필드를 필수로 요구하고, 빈 배열은 허용하는지 확인
- 정상 성공 응답 확인
- validation 실패 시 `422` 확인
- 내부 처리 오류 시 `code: AI_PROCESSING_FAILED` JSON 확인
- OpenAI provider가 Pydantic response format으로 구조화 응답을 요청하고 preview 코드북/count를 정규화하는지 fake client로 확인

API별 호출 테스트:

| API | 테스트 함수 | 확인 내용 |
| --- | --- | --- |
| `GET /docs` | `test_docs_endpoint_is_available` | Swagger UI 문서 endpoint가 `200`과 `text/html`로 응답하는지 확인 |
| `GET /openapi.json` | `test_openapi_exposes_required_paths` | Spring에서 호출할 5개 POST path가 OpenAPI schema에 노출되는지 확인 |
| `POST /ai/v1/inquiries/check-preview` | `test_inquiry_preview_accepts_camel_case_and_returns_json_object` | camelCase 요청을 받고 `confirmedCount`, `totalCount`, 7개 고정 `items` JSON을 반환하는지 확인 |
| `POST /ai/v1/consultations/check-preview` | `test_consultation_preview_accepts_camel_case_and_returns_json_object` | 상담 preview 요청이 7개 고정 preview item과 canonical label(`나의 응대` 포함)을 반환하는지 확인 |
| `POST /ai/v1/consultations/analyze` | `test_consultation_analyze_returns_required_fields` | `summary`, `customerInsight`, `nonConversionReasons`, `nextBestAction`, `followUp`, `followUpInsight` 필수 필드를 반환하는지 확인 |
| `POST /ai/v1/consultations/analyze` | `test_consultation_analyze_rejects_bad_datetime` | 잘못된 datetime 입력을 `422` validation error로 거절하는지 확인 |
| `POST /ai/v1/consultations/analyze` | `test_analysis_requires_attached_materials_field_even_when_empty` | `attachedMaterials` 누락을 `422`로 거절하고 빈 배열은 허용하는지 확인 |
| `POST /ai/v1/consultations/next-action` | `test_next_action_returns_required_contract` | `priorityScore`, `nextBestAction`, `followUp` 계약 필드를 반환하는지 확인 |
| `POST /ai/v1/messages/generate` | `test_message_generate_returns_requested_enums` | 요청한 `tonePreset`, `versionType`을 유지하고 메시지 본문을 반환하는지 확인 |
| 전체 POST API | `test_all_endpoints_return_422_for_invalid_payloads` | 각 API가 잘못된 payload를 `422`로 거절하는지 확인 |
| 전체 POST API | `test_all_endpoints_return_processing_error_for_runtime_failures` | 내부 AI 처리 예외가 `500`과 `AI_PROCESSING_FAILED` JSON으로 매핑되는지 확인 |

최근 검증 결과:

```text
python -m compileall -q src tests
PASS

python -m pytest -q
39 passed, 1 warning
```

참고: 실제 OpenAI API 호출은 비용이 발생할 수 있어 자동 테스트에서 실행하지 않습니다. 운영 키 검증은 로컬에서 `AI_PROVIDER=openai`와 `OPENAI_API_KEY`를 설정한 뒤 FastAPI endpoint를 직접 호출해 확인합니다.

## Neo4j Production Graph 명령

`.env.example`을 참고해 `.env`를 만들고 로컬 값으로 채웁니다.

```env
NEO4J_URI=neo4j+s://example.databases.neo4j.io
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=replace-with-aura-password
NEO4J_DATABASE=neo4j
NEO4J_TRUST_SELF_SIGNED=false
GRAPH_PERSISTENCE_ENABLED=false
AURA_INSTANCEID=optional-instance-id
AURA_INSTANCENAME=optional-instance-name
```

로컬 네트워크나 보안 제품이 TLS 인증서를 대체해 `neo4j+s` 연결이 실패할 때만 로컬 검증 용도로 `NEO4J_TRUST_SELF_SIGNED=true`를 사용합니다. 기본값은 `false`입니다.

RDS에 저장된 상담 분석 결과를 AuraDB에 동기화하려면 `.env`에서 다음 값을 켭니다.

```env
GRAPH_PERSISTENCE_ENABLED=true
```

이 값이 `true`일 때 `/ai/v1/graph/consultations/sync`는 BE/RDS가 저장한 실제 id를 기준으로 다음 projection을 AuraDB에 upsert합니다. `/ai/v1/consultations/analyze`는 AI 분석 응답만 반환하며 AuraDB에 직접 쓰지 않습니다.

- `Store`, `Service`, `Customer`, `Consultation`
- `FollowUp`, `NonConversionReason`, `CustomerAiInsight`
- `ReasonConcept`, `LeadTemperatureConcept`와의 의미 관계

Neo4j 설정이 없거나 AuraDB 연결이 실패하면 sync API는 `500`과 `AI_PROCESSING_FAILED`로 실패합니다. 이 값이 `false`이거나 없으면 sync API는 `persisted=false`를 반환하고 AuraDB에는 쓰지 않습니다.

업무 데이터가 아직 없을 때 schema와 온톨로지만 초기화:

```powershell
.\.venv\Scripts\python -m fitback_ai init
```

Spring/RDS에서 추출한 JSON payload를 Neo4j/AuraDB에 적재:

```powershell
.\.venv\Scripts\python -m fitback_ai load --input .omx\production-graph.json
```

입력 파일 없이 `load`를 실행하면 `init`과 동일하게 빈 그래프를 준비합니다.

```powershell
.\.venv\Scripts\python -m fitback_ai load
```

현재 graph count 검증:

```powershell
.\.venv\Scripts\python -m fitback_ai verify
```

명령 출력 항목:

- `elapsedMs`
- `recordCount` (`init`, `load`)
- label별 count

초기 빈 데이터 기준 count 예시:

```json
{
  "Store": 0,
  "Customer": 0,
  "Consultation": 0,
  "ReasonConcept": 6,
  "ActionConcept": 6,
  "LeadTemperatureConcept": 3
}
```

## 그래프 도메인 모델

production projection은 다음 Neo4j label을 생성합니다.

- `Store`
- `User`
- `Service`
- `Customer`
- `Consultation`
- `FollowUp`
- `NonConversionReason`
- `ConsultationSignal`
- `CustomerAiInsight`
- `Event`
- `EventTarget`
- `MessageTemplate`
- `ContactResult`
- `OntologyConcept`
- `ReasonConcept`
- `ReasonCategory`
- `ActionConcept`
- `LeadTemperatureConcept`

주요 관계 패턴:

```cypher
(:Store)-[:HAS_CUSTOMER]->(:Customer)
(:Store)-[:OFFERS]->(:Service)
(:Store)-[:RUNS_EVENT]->(:Event)
(:Customer)-[:INTERESTED_IN]->(:Service)
(:Customer)-[:HAD_CONSULTATION]->(:Consultation)
(:Consultation)-[:HAS_FOLLOW_UP]->(:FollowUp)
(:Consultation)-[:HAS_NON_CONVERSION_REASON]->(:NonConversionReason)
(:Consultation)-[:HAS_SIGNAL]->(:ConsultationSignal)
(:Customer)-[:HAS_AI_INSIGHT]->(:CustomerAiInsight)
(:Event)-[:TARGETS]->(:EventTarget)
(:EventTarget)-[:TARGET_CUSTOMER]->(:Customer)
(:Customer)-[:HAS_MESSAGE]->(:MessageTemplate)
(:FollowUp)-[:GENERATED_MESSAGE]->(:MessageTemplate)
(:Customer)-[:HAS_CONTACT_RESULT]->(:ContactResult)
```

이 구조는 다음 관리자 질문을 지원하기 위한 기반입니다.

- 오늘 후속 연락이 필요한 고객은 누구인가?
- 이 고객의 우선순위가 높은 이유는 무엇인가?
- 특정 이벤트 캠페인을 보낼 고객은 누구인가?
- 주요 미전환 사유는 무엇인가?
- 고객 상담 이력에 맞는 메시지 초안은 무엇인가?

## 유용한 AuraDB 쿼리

적재된 고객과 연결 그래프 확인:

```cypher
MATCH p = (c:Customer)-[*1..3]-(n)
RETURN p
LIMIT 50
```

label별 count 확인:

```cypher
MATCH (n)
RETURN labels(n) AS labels, count(*) AS count
ORDER BY labels
```

## AI Agent 참고 사항

이 폴더를 읽는 AI agent는 다음 규칙을 지킵니다.

1. `.env` 값을 읽거나 출력하거나 커밋하거나 요약하지 않습니다.
2. 설정 형식 확인에는 `.env.example`을 사용합니다.
3. 스프레드시트와 무시된 로컬 샘플은 untracked 상태로 둡니다.
4. HTTP 계약 형태 변경은 우선 `api_models.py`를 수정합니다.
5. AI provider 동작 변경은 우선 `ai_provider.py`, route 연결 변경은 `ai_service.py`를 수정합니다.
6. Ontology 변경은 `ontology.py`, graph write 변경은 `neo4j_loader.py`를 우선 수정합니다.
7. 처음 데이터가 없는 운영 환경을 지원합니다. `init`과 빈 `load`는 schema와 ontology만 준비해야 합니다.
8. tenant boundary를 보존합니다. 실제 business node에는 `storeId`를 유지합니다.
9. 코드 변경 커밋 전 `python -m pytest -q`를 실행합니다.
10. AuraDB 인증 정보가 있을 때 `python -m fitback_ai init`과 `python -m fitback_ai verify`를 실행합니다.

## 현재 제한 사항

- OpenAI 연동은 구현되어 있지만 실제 운영 품질은 Spring 개발 환경에서 추가 통합 테스트가 필요합니다.
- `AI_PROVIDER=heuristic` 또는 API key가 없는 `auto` 모드는 실제 LLM 출력이 아니라 결정적 휴리스틱입니다.
- embedding/vector index는 아직 생성하지 않습니다.
- Spring 개발 환경에서 `AI_BASE_URL`로 실제 통합 테스트를 추가로 수행해야 합니다.
- Aura Agent/Bloom이 graph를 올바르게 조회하려면 별도의 Cypher tool이나 prompt가 필요할 수 있습니다.
- RDS가 원천 데이터 저장소이며, AuraDB는 AI projection layer입니다.
