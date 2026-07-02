# Fitback AI - (AI한테 explore하라고 하면 토큰 줄일 수 있음)

Fitback AI is the graph-projection and GraphRAG validation workspace for Fitback's store-management assistant.

The current code is intentionally small: it generates 100 deterministic mock store-management records, loads them into Neo4j AuraDB, and verifies graph counts and timing. This lets the team prove that customer, consultation, follow-up, event, message, and conversion-analysis data can be represented as an AI-readable graph before building the full FastAPI GraphRAG service.

## Read This First

- Source-of-truth business data should live in the main RDS-backed backend.
- AuraDB is a graph projection for AI search, relationship traversal, event targeting, and recommendation evidence.
- `.env` contains real AuraDB credentials and must never be committed or printed.
- `.env.example` is the safe reference for required environment keys.
- Spreadsheet samples such as `상담메모_예시.xlsx` are intentionally ignored by Git.
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
│   └── issue-log.md
├── src/
│   └── fitback_ai/
│       ├── cli.py
│       ├── config.py
│       ├── mock_data.py
│       └── neo4j_loader.py
└── tests/
    └── test_mock_data.py
```

Key files:

- `src/fitback_ai/mock_data.py`: deterministic mock data generator aligned with the consultation memo and store-management domain.
- `src/fitback_ai/neo4j_loader.py`: Neo4j schema setup, batch replacement, graph upsert, and count verification.
- `src/fitback_ai/cli.py`: `generate`, `load`, `verify`, and `smoke` commands.
- `sql.example`: target RDS-style business schema used as the domain reference.
- `docs/issue-log.md`: records why GitHub issue creation was blocked in this environment.

## Domain Model

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

## Environment

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

## Setup

PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
```

## Commands

Generate 100 deterministic mock records without touching Neo4j:

```powershell
.\.venv\Scripts\python -m fitback_ai generate --count 100 --output .omx\mock-data.json
```

Insert the records into Neo4j/AuraDB and print timing evidence:

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

Expected successful 100-record smoke shape:

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

## Useful AuraDB Queries

Find one loaded customer and connected graph paths:

```cypher
MATCH p = (c:Customer {name: '테스트고객001'})-[*1..3]-(n)
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
3. Keep `상담메모_예시.xlsx` and other spreadsheets untracked.
4. Prefer changing `mock_data.py` for sample-domain changes and `neo4j_loader.py` for graph-write changes.
5. Preserve idempotency: the loader deletes only nodes with the selected `mockBatchId`, then recreates that batch.
6. Preserve tenant boundaries: keep `storeId` on mock business nodes.
7. Run `python -m pytest -q` before committing code changes.
8. Run `python -m fitback_ai smoke --count 100` when AuraDB credentials are available.

## Current Limitations

- This is not yet the full FastAPI GraphRAG service.
- Embeddings/vector indexes are not created yet.
- OpenAI/LLM integration is not implemented in this repository yet.
- Aura Agent/Bloom may need explicit Cypher tools or prompts to query the graph correctly.
- RDS remains the intended source of truth; AuraDB is an AI projection layer.
