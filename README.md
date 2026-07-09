# Fitback AI

Fitback AI는 Fitback 매장 관리 어시스턴트를 위한 FastAPI AI 계약 서버와 Neo4j 그래프 프로젝션 작업 공간입니다.

현재 이 저장소는 두 가지 기능을 제공합니다.

- Spring Boot 서버가 호출할 수 있는 FastAPI AI HTTP 계약 구현
- 결정적 mock 매장 관리 데이터 생성, Neo4j AuraDB 적재, 그래프 카운트 검증

현재 FastAPI 응답은 외부 LLM을 호출하지 않고 결정적 휴리스틱으로 생성됩니다.

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
- `src/fitback_ai/ai_service.py`: 결정적 AI 계약 응답 생성 로직
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
- `pytest==8.4.1`
- `httpx==0.28.1`

## FastAPI 서비스

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
5. 결정적 응답 동작 변경은 우선 `ai_service.py`를 수정합니다.
6. 샘플 도메인 변경은 `mock_data.py`, graph write 변경은 `neo4j_loader.py`를 우선 수정합니다.
7. graph idempotency를 보존합니다. loader는 선택된 `mockBatchId` 노드만 삭제한 뒤 batch를 재생성합니다.
8. tenant boundary를 보존합니다. mock business node에는 `storeId`를 유지합니다.
9. 코드 변경 커밋 전 `python -m pytest -q`를 실행합니다.
10. AuraDB 인증 정보가 있을 때 `python -m fitback_ai smoke --count 100`을 실행합니다.

## 현재 제한 사항

- FastAPI 응답은 실제 LLM 출력이 아니라 결정적 휴리스틱입니다.
- OpenAI/LLM 연동은 아직 구현되어 있지 않습니다.
- embedding/vector index는 아직 생성하지 않습니다.
- Spring 개발 환경에서 `AI_BASE_URL`로 실제 통합 테스트를 추가로 수행해야 합니다.
- Aura Agent/Bloom이 graph를 올바르게 조회하려면 별도의 Cypher tool이나 prompt가 필요할 수 있습니다.
- RDS가 원천 데이터 저장소이며, AuraDB는 AI projection layer입니다.
