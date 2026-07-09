# Fitback AI

Fitback AI는 Fitback 매장 관리 어시스턴트를 위한 FastAPI AI 계약 서버와 Neo4j 그래프 프로젝션 작업 공간입니다.

현재 이 저장소는 두 가지 기능을 제공합니다.

- Spring Boot 서버가 호출할 수 있는 FastAPI AI HTTP 계약 구현
- 결정적 mock 매장 관리 데이터 생성, Neo4j AuraDB 적재, 그래프 카운트 검증

현재 FastAPI 응답은 `OPENAI_API_KEY` 또는 `AI_API_KEY`가 설정되어 있으면 OpenAI API를 호출하고, 키가 없으면 로컬 개발용 결정적 휴리스틱으로 생성됩니다.

## 먼저 확인할 것

- 실제 업무 데이터의 원천은 RDS 기반 메인 백엔드입니다.
- AuraDB는 AI 검색, 관계 탐색, 이벤트 타겟팅, 추천 근거 생성을 위한 그래프 프로젝션입니다.
- `.env`에는 실제 AuraDB 인증 정보가 들어가므로 커밋하거나 출력하지 않습니다.
- `.env.example`은 필요한 환경 변수 형식을 보여주는 안전한 참고 파일입니다.
- `*상담메모_예시.xlsx` 같은 샘플 스프레드시트와 `.xlsx` 파일은 Git에서 제외합니다.
- 모든 mock 그래프 노드는 `storeId`와 `mockBatchId`를 포함해 테스트 데이터를 안전하게 집계하거나 교체할 수 있습니다.

## 저장소 구조

```text
.
├── README.md
├── .env.example
├── requirements.txt
├── pyproject.toml
├── sql.example
├── docs/
│   ├── fastapi요구사항.md
│   └── issue-log.md
├── src/
│   └── fitback_ai/
│       ├── api.py
│       ├── api_models.py
│       ├── ai_provider.py
│       ├── ai_service.py
│       ├── cli.py
│       ├── config.py
│       ├── mock_data.py
│       └── neo4j_loader.py
└── tests/
    ├── test_api.py
    └── test_mock_data.py
```

주요 파일:

- `src/fitback_ai/api.py`: FastAPI 앱과 라우트 선언
- `src/fitback_ai/api_models.py`: Pydantic 요청/응답 모델, camelCase alias, enum/date/UUID 검증
- `src/fitback_ai/ai_service.py`: FastAPI route에서 AI provider를 호출하는 facade
- `src/fitback_ai/ai_provider.py`: OpenAI API provider와 로컬 휴리스틱 provider
- `tests/test_api.py`: FastAPI 계약 테스트
- `src/fitback_ai/mock_data.py`: 상담/매장 관리 도메인에 맞춘 결정적 mock 데이터 생성기
- `src/fitback_ai/neo4j_loader.py`: Neo4j schema 설정, batch 교체, graph upsert, count 검증
- `src/fitback_ai/cli.py`: `generate`, `load`, `verify`, `smoke` 명령
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

## 예상 상황별 입력/출력 예시

Spring 또는 프론트에서 받은 자연어 질문/상황을 FastAPI 요청 body로 정리해 보내면, AI provider는 아래처럼 계약된 JSON object를 반환합니다. 아래 `AI 출력` 값은 `2026-07-09`에 `OPENAI_API_KEY`, `AI_PROVIDER=auto`, `OPENAI_MODEL=gpt-4.1-mini` 설정으로 실제 FastAPI endpoint를 호출해 받은 OpenAI API 응답입니다.

### 1. 문의 내용 중간 평가

예상 질문:

```text
고객이 "가격이랑 주 3회 PT 가능 여부가 궁금해요"라고 문의했는데, 상담 전에 입력 내용이 충분한지 확인해줘.
```

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
  "isValid": false,
  "warnings": [
    "문의 내용에 이해하기 어려운 문자가 포함되어 있습니다.",
    "서비스 이름에 공백 또는 인식 불가 문자가 포함되어 있습니다."
  ],
  "suggestions": [
    "문의 내용을 명확하고 구체적으로 작성해주세요.",
    "서비스 이름을 정확하게 입력해주세요."
  ]
}
```

### 2. 상담 내용 중간 평가

예상 질문:

```text
상담 메모에 "체중 감량 목표, 평일 저녁 가능" 정도만 적혀 있는데 AI 분석 전에 부족한 내용이 있는지 확인해줘.
```

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
  "isValid": false,
  "warnings": [
    "입력 내용에 이해할 수 없는 문자가 포함되어 있습니다."
  ],
  "suggestions": [
    "입력 내용을 다시 확인하고 정확한 문장으로 작성해 주세요."
  ]
}
```

### 3. 상담 AI 분석

예상 질문:

```text
가격 때문에 PT 등록을 망설이는 고객이야. 이 상담 내용을 분석해서 미전환 사유와 다음 행동을 추천해줘.
```

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
  }
}
```

AI 출력:

```json
{
  "summary": "고객은 3개월 1:1 퍼스널 트레이닝 서비스에 관심을 보였으나, 상세 정보 부족으로 구매 결정에 이르지 못함.",
  "customerInsight": {
    "leadTemperature": "미온적",
    "temperatureBasis": "초기 상담에서 서비스를 충분히 이해하지 못함",
    "priorityScore": 3
  },
  "nonConversionReasons": [
    {
      "reasonType": "정보부족",
      "role": "고객",
      "reasonBasis": "서비스에 대한 구체적인 설명이 부족하여 신뢰도와 이해도가 낮음",
      "confidence": "높음"
    }
  ],
  "nextBestAction": {
    "title": "서비스 상세 안내 및 추가 상담 제안",
    "description": "고객이 서비스를 충분히 이해할 수 있도록 상세한 안내 자료 제공 및 추가 상담 일정을 잡아 구매 전환 유도"
  },
  "followUp": {
    "recommendContactDate": "2026-07-12",
    "memo": "카카오톡을 통한 상세 서비스 설명 메시지 발송 후 추가 상담 일정 조율 권장"
  },
  "followUpInsight": {
    "persuasionPoint": {
      "keyMessage": "3개월 동안 1:1 맞춤 트레이닝으로 체계적인 관리가 가능합니다."
    },
    "cautionNote": "초기 상담에서 서비스 이해도가 낮아 이탈 가능성이 있으니 빠른 후속 조치 필요",
    "actionBasis": {
      "title": "추가 상담 권유",
      "description": "고객이 서비스의 이점을 명확히 이해하게 하여 구매 결정에 도움"
    }
  }
}
```

### 4. 다음 행동 추천

예상 질문:

```text
이미 AI 분석 결과가 있어. 가격 부담이 1순위 미전환 사유인 고객에게 다음 연락 액션을 추천해줘.
```

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
  "priorityScore": 85,
  "nextBestAction": {
    "title": "가격 할인 프로모션 안내",
    "description": "고객님께 현재 진행 중인 가격 할인 및 혜택을 자세히 안내하여 구매 결정을 유도하세요."
  },
  "followUp": {
    "recommendContactDate": "2024-06-10",
    "memo": "최근 상담에서 가격에 대한 부담을 보이셨습니다. 할인 프로모션 정보를 제공하며 다시 연락드리겠습니다."
  },
  "followUpInsight": {
    "persuasionPoint": {
      "keyMessage": "현재 적용 가능한 가격 할인 혜택으로 부담을 줄일 수 있습니다."
    },
    "cautionNote": "가격에 민감한 고객이므로 무리한 판매 압박은 피하세요.",
    "actionBasis": {
      "title": "가격 관련 우려 해소",
      "description": "가격 부담이 주요 비구매 사유이므로 가격 할인 혜택 안내가 필요합니다."
    }
  }
}
```

### 5. 고객 메시지 생성

예상 질문:

```text
가격 때문에 고민 중인 고객에게 카카오톡으로 보낼 친근한 후속 메시지를 만들어줘.
```

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
  "content": "안녕하세요! 최근에 상담해주셔서 감사합니다. 가격 때문에 고민이 많으신 걸로 알고 있는데, 저희가 더 좋은 혜택이나 맞춤 제안을 드릴 수 있도록 노력하겠습니다. 궁금한 점 있으시면 언제든지 편하게 문의해 주세요. 항상 고객님께 최선을 다하는 Fitback이 되겠습니다!",
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
- 정상 성공 응답 확인
- validation 실패 시 `422` 확인
- 내부 처리 오류 시 `code: AI_PROCESSING_FAILED` JSON 확인
- OpenAI provider가 `gpt-4.1-mini`와 Pydantic response format으로 구조화 응답을 요청하는지 fake client로 확인

API별 호출 테스트:

| API | 테스트 함수 | 확인 내용 |
| --- | --- | --- |
| `GET /docs` | `test_docs_endpoint_is_available` | Swagger UI 문서 endpoint가 `200`과 `text/html`로 응답하는지 확인 |
| `GET /openapi.json` | `test_openapi_exposes_required_paths` | Spring에서 호출할 5개 POST path가 OpenAPI schema에 노출되는지 확인 |
| `POST /ai/v1/inquiries/check-preview` | `test_inquiry_preview_accepts_camel_case_and_returns_json_object` | camelCase 요청을 받고 `isValid`, `warnings`, `suggestions` JSON을 반환하는지 확인 |
| `POST /ai/v1/consultations/check-preview` | `test_consultation_preview_accepts_camel_case_and_returns_json_object` | 상담 preview 요청이 `200`과 `isValid: true`로 응답하는지 확인 |
| `POST /ai/v1/consultations/analyze` | `test_consultation_analyze_returns_required_fields` | `summary`, `customerInsight`, `nonConversionReasons`, `nextBestAction`, `followUp`, `followUpInsight` 필수 필드를 반환하는지 확인 |
| `POST /ai/v1/consultations/analyze` | `test_consultation_analyze_rejects_bad_datetime` | 잘못된 datetime 입력을 `422` validation error로 거절하는지 확인 |
| `POST /ai/v1/consultations/next-action` | `test_next_action_returns_required_contract` | `priorityScore`, `nextBestAction`, `followUp` 계약 필드를 반환하는지 확인 |
| `POST /ai/v1/messages/generate` | `test_message_generate_returns_requested_enums` | 요청한 `tonePreset`, `versionType`을 유지하고 메시지 본문을 반환하는지 확인 |
| 전체 POST API | `test_all_endpoints_return_422_for_invalid_payloads` | 각 API가 잘못된 payload를 `422`로 거절하는지 확인 |
| 전체 POST API | `test_all_endpoints_return_processing_error_for_runtime_failures` | 내부 AI 처리 예외가 `500`과 `AI_PROCESSING_FAILED` JSON으로 매핑되는지 확인 |

최근 검증 결과:

```text
python -m compileall -q src tests
PASS

python -m pytest -q
15 passed, 1 warning
```

참고: 실제 OpenAI API 호출은 비용이 발생할 수 있어 자동 테스트에서 실행하지 않습니다. 운영 키 검증은 로컬에서 `AI_PROVIDER=openai`와 `OPENAI_API_KEY`를 설정한 뒤 FastAPI endpoint를 직접 호출해 확인합니다.

## Neo4j Mock Graph 명령

`.env.example`을 참고해 `.env`를 만들고 로컬 값으로 채웁니다.

```env
NEO4J_URI=neo4j+s://example.databases.neo4j.io
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=replace-with-aura-password
NEO4J_DATABASE=neo4j
NEO4J_TRUST_SELF_SIGNED=false
AURA_INSTANCEID=optional-instance-id
AURA_INSTANCENAME=optional-instance-name

MOCK_STORE_ID=00000000-0000-4000-8000-000000000001
MOCK_BATCH_ID=mock-graph-rag-v1
MOCK_RECORD_COUNT=100
```

로컬 네트워크나 보안 제품이 TLS 인증서를 대체해 `neo4j+s` 연결이 실패할 때만 로컬 검증 용도로 `NEO4J_TRUST_SELF_SIGNED=true`를 사용합니다. 기본값은 `false`입니다.

Neo4j에 접근하지 않고 100개 mock record 생성:

```powershell
.\.venv\Scripts\python -m fitback_ai generate --count 100 --output .omx\mock-data.json
```

Neo4j/AuraDB에 record 적재:

```powershell
.\.venv\Scripts\python -m fitback_ai load --count 100
```

기본 mock batch count 검증:

```powershell
.\.venv\Scripts\python -m fitback_ai verify
```

생성, 적재, 검증을 한 번에 실행:

```powershell
.\.venv\Scripts\python -m fitback_ai smoke --count 100
```

`smoke` 명령 출력 항목:

- `loadElapsedMs`
- `verifyElapsedMs`
- label별 count
- `passed`

100개 record 기준 성공 count 예시:

```json
{
  "Customer": 100,
  "Consultation": 100,
  "FollowUp": 100,
  "NonConversionReason": 100,
  "ConsultationSignal": 100,
  "CustomerAiInsight": 100,
  "EventTarget": 100,
  "MessageTemplate": 100,
  "ContactResult": 100
}
```

## 그래프 도메인 모델

mock projection은 다음 Neo4j label을 생성합니다.

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
- `MockData`

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

mock batch label별 count 확인:

```cypher
MATCH (n:MockData {mockBatchId: 'mock-graph-rag-v1'})
RETURN labels(n) AS labels, count(*) AS count
ORDER BY labels
```

mock batch만 삭제:

```cypher
MATCH (n:MockData {mockBatchId: 'mock-graph-rag-v1'})
DETACH DELETE n
```

## AI Agent 참고 사항

이 폴더를 읽는 AI agent는 다음 규칙을 지킵니다.

1. `.env` 값을 읽거나 출력하거나 커밋하거나 요약하지 않습니다.
2. 설정 형식 확인에는 `.env.example`을 사용합니다.
3. 스프레드시트와 무시된 로컬 샘플은 untracked 상태로 둡니다.
4. HTTP 계약 형태 변경은 우선 `api_models.py`를 수정합니다.
5. AI provider 동작 변경은 우선 `ai_provider.py`, route 연결 변경은 `ai_service.py`를 수정합니다.
6. 샘플 도메인 변경은 `mock_data.py`, graph write 변경은 `neo4j_loader.py`를 우선 수정합니다.
7. graph idempotency를 보존합니다. loader는 선택된 `mockBatchId` 노드만 삭제한 뒤 batch를 재생성합니다.
8. tenant boundary를 보존합니다. mock business node에는 `storeId`를 유지합니다.
9. 코드 변경 커밋 전 `python -m pytest -q`를 실행합니다.
10. AuraDB 인증 정보가 있을 때 `python -m fitback_ai smoke --count 100`을 실행합니다.

## 현재 제한 사항

- OpenAI 연동은 구현되어 있지만 실제 운영 품질은 Spring 개발 환경에서 추가 통합 테스트가 필요합니다.
- `AI_PROVIDER=heuristic` 또는 API key가 없는 `auto` 모드는 실제 LLM 출력이 아니라 결정적 휴리스틱입니다.
- embedding/vector index는 아직 생성하지 않습니다.
- Spring 개발 환경에서 `AI_BASE_URL`로 실제 통합 테스트를 추가로 수행해야 합니다.
- Aura Agent/Bloom이 graph를 올바르게 조회하려면 별도의 Cypher tool이나 prompt가 필요할 수 있습니다.
- RDS가 원천 데이터 저장소이며, AuraDB는 AI projection layer입니다.
