# Fitback AI

Fitback AI is the FastAPI AI-contract and Neo4j graph-projection workspace for Fitback's store-management assistant.

The repository currently provides two local capabilities:

- A FastAPI service that matches the Spring Boot AI integration contract in `docs/fastapi요구사항.md`.
- Deterministic mock store-management data generation, Neo4j AuraDB loading, and graph-count verification.

The FastAPI service uses deterministic heuristics today. It does not call an external LLM provider yet.

## Read This First

- Source-of-truth business data should live in the main RDS-backed backend.
- AuraDB is a graph projection for AI search, relationship traversal, event targeting, and recommendation evidence.
- `.env` contains real AuraDB credentials and must never be committed or printed.
- `.env.example` is the safe reference for required environment keys.
- Spreadsheet samples such as `*상담메모_예시.xlsx` and other `.xlsx` files are intentionally ignored by Git.
- All mock graph nodes include `storeId` and `mockBatchId` so test data can be counted or replaced safely.

## Repository Map

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

Key files:

- `src/fitback_ai/api.py`: FastAPI app and route declarations.
- `src/fitback_ai/api_models.py`: Pydantic request/response models, camelCase aliases, enum/date/UUID validation.
- `src/fitback_ai/ai_service.py`: deterministic AI-contract response generation.
- `tests/test_api.py`: FastAPI contract tests for paths, OpenAPI docs, success responses, validation failures, and internal error bodies.
- `src/fitback_ai/mock_data.py`: deterministic mock data generator aligned with the consultation and store-management domain.
- `src/fitback_ai/neo4j_loader.py`: Neo4j schema setup, batch replacement, graph upsert, and count verification.
- `src/fitback_ai/cli.py`: `generate`, `load`, `verify`, and `smoke` commands.
- `sql.example`: target RDS-style business schema used as the domain reference.
- `docs/fastapi요구사항.md`: Spring-to-FastAPI HTTP API contract.

## Setup

PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
```

The project currently pins:

- `fastapi==0.139.0`
- `uvicorn==0.38.0`
- `neo4j==5.28.1`
- `pytest==8.4.1`
- `httpx==0.28.1`

## FastAPI Service

Run the AI server locally:

```powershell
.\.venv\Scripts\python -m uvicorn fitback_ai.api:app --host 0.0.0.0 --port 8000
```

Spring can point `AI_BASE_URL` to:

```text
http://localhost:8000
```

Interactive API docs:

- Swagger UI: `http://localhost:8000/docs`
- OpenAPI JSON: `http://localhost:8000/openapi.json`

Implemented endpoints:

| Feature | Method | Path |
|---|---|---|
| Inquiry preview check | `POST` | `/ai/v1/inquiries/check-preview` |
| Consultation preview check | `POST` | `/ai/v1/consultations/check-preview` |
| Consultation AI analysis | `POST` | `/ai/v1/consultations/analyze` |
| Next-action recommendation | `POST` | `/ai/v1/consultations/next-action` |
| Customer message generation | `POST` | `/ai/v1/messages/generate` |

Contract behavior:

- Request and response JSON field names use camelCase.
- UUID, date, offset datetime, and documented enum fields are validated by Pydantic/FastAPI.
- Invalid request bodies return FastAPI validation errors with `422`.
- Runtime processing errors are returned as JSON:

```json
{
  "detail": "AI processing failed",
  "code": "AI_PROCESSING_FAILED"
}
```

- Successful responses are JSON objects and preserve the required non-null/non-blank response fields from `docs/fastapi요구사항.md`.
- Empty list responses use `[]`, not `null`.

## FastAPI Smoke Examples

Inquiry preview:

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

Message generation:

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

## Tests

Run all tests:

```powershell
.\.venv\Scripts\python -m pytest -q
```

Useful quick checks:

```powershell
.\.venv\Scripts\python -m compileall -q src tests
.\.venv\Scripts\python -m pytest -q tests\test_api.py
```

The API tests cover:

- all five required POST paths in `/openapi.json`
- `/docs` availability
- camelCase request/response handling
- valid success responses
- validation failures with `422`
- runtime error JSON with `code: AI_PROCESSING_FAILED`

## Neo4j Mock Graph Commands

Create `.env` from `.env.example` and fill in real values locally:

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

If a local network or security product replaces TLS certificates and `neo4j+s` fails with routing or certificate errors, use `NEO4J_TRUST_SELF_SIGNED=true` only for local development verification. The default is `false`.

Generate 100 deterministic mock records without touching Neo4j:

```powershell
.\.venv\Scripts\python -m fitback_ai generate --count 100 --output .omx\mock-data.json
```

Insert records into Neo4j/AuraDB and print timing evidence:

```powershell
.\.venv\Scripts\python -m fitback_ai load --count 100
```

Verify stored counts for the default mock batch:

```powershell
.\.venv\Scripts\python -m fitback_ai verify
```

Run generate + load + verify in one command:

```powershell
.\.venv\Scripts\python -m fitback_ai smoke --count 100
```

The smoke command prints:

- `loadElapsedMs`
- `verifyElapsedMs`
- per-label counts
- `passed`

Expected successful 100-record smoke count shape:

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

## Graph Domain Model

The mock projection creates these Neo4j labels:

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

Important relationship patterns:

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

This structure supports manager-facing questions such as:

- Which customers need follow-up today?
- Why is this customer high priority?
- Which customers should receive a specific event campaign?
- What are the common non-conversion reasons?
- What message draft fits this customer's consultation history?

## Useful AuraDB Queries

Find one loaded customer and connected graph paths:

```cypher
MATCH p = (c:Customer)-[*1..3]-(n)
RETURN p
LIMIT 50
```

Get label counts for the mock batch:

```cypher
MATCH (n:MockData {mockBatchId: 'mock-graph-rag-v1'})
RETURN labels(n) AS labels, count(*) AS count
ORDER BY labels
```

Delete only the mock batch:

```cypher
MATCH (n:MockData {mockBatchId: 'mock-graph-rag-v1'})
DETACH DELETE n
```

## AI Agent Notes

If you are an AI agent reading this folder:

1. Do not read, print, commit, or summarize `.env` values.
2. Use `.env.example` to understand configuration shape.
3. Keep spreadsheets and other ignored local samples untracked.
4. Prefer changing `api_models.py` for HTTP contract shape changes.
5. Prefer changing `ai_service.py` for deterministic response behavior.
6. Prefer changing `mock_data.py` for sample-domain changes and `neo4j_loader.py` for graph-write changes.
7. Preserve graph idempotency: the loader deletes only nodes with the selected `mockBatchId`, then recreates that batch.
8. Preserve tenant boundaries: keep `storeId` on mock business nodes.
9. Run `python -m pytest -q` before committing code changes.
10. Run `python -m fitback_ai smoke --count 100` when AuraDB credentials are available.

## Current Limitations

- FastAPI responses are deterministic heuristics, not real LLM output.
- OpenAI/LLM integration is not implemented yet.
- Embeddings/vector indexes are not created yet.
- Spring-to-FastAPI integration must still be tested from the Spring development environment with `AI_BASE_URL`.
- Aura Agent/Bloom may need explicit Cypher tools or prompts to query the graph correctly.
- RDS remains the intended source of truth; AuraDB is an AI projection layer.
