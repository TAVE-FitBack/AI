# Fitback AI GraphRAG Mock Ingestion

This repository contains a small CLI for validating Neo4j AuraDB graph projection ingestion with mock store-management data.

## Setup

Create `.env` from `.env.example` and fill in the real AuraDB values. Do not commit `.env`.
If your local network replaces TLS certificates and `neo4j+s` fails with routing or certificate errors, set
`NEO4J_TRUST_SELF_SIGNED=true` in your shell or local `.env` for development-only verification.

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

The smoke command prints `loadElapsedMs`, `verifyElapsedMs`, per-label counts, and a boolean `passed` flag.

## Data Shape

Each mock record represents one consultation memo row and projects these graph entities:

- `Store`
- `Customer`
- `Service`
- `Consultation`
- `FollowUp`
- `NonConversionReason`
- `ConsultationSignal`
- `CustomerAiInsight`
- `Event`
- `EventTarget`
- `MessageTemplate`
- `ContactResult`

All mock nodes include `storeId` and `mockBatchId` so test data can be counted or removed safely.
