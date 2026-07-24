# RDS to AuraDB Sync

RDS is the source of truth. AuraDB is a graph projection for AI retrieval and relationship traversal.

The FastAPI analysis endpoint does not write to AuraDB directly:

- `POST /ai/v1/consultations/analyze` returns the AI analysis response.
- `POST /ai/v1/graph/consultations/sync` upserts the RDS-saved consultation analysis projection into AuraDB.

The sync payload should be sent after BE saves the AI analysis result to RDS, because the payload must include persisted RDS ids such as:

- `followUp.followUpId`
- `nonConversionReasons[].reasonId`
- `consultation.consultationId`
- `customer.customerId`

When `GRAPH_PERSISTENCE_ENABLED=false` or unset, the sync endpoint returns:

```json
{
  "persisted": false,
  "counts": null
}
```

When `GRAPH_PERSISTENCE_ENABLED=true`, Neo4j settings must also be present:

```env
NEO4J_URI=neo4j+s://example.databases.neo4j.io
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=...
NEO4J_DATABASE=neo4j
GRAPH_PERSISTENCE_ENABLED=true
```

If AuraDB persistence fails while enabled, FastAPI returns `500` with `AI_PROCESSING_FAILED`.

## Initial RDS Backfill

Use the AI container or EC2 host that can reach the private RDS endpoint. The command reads RDS and writes only to AuraDB; it must not update or delete RDS rows.

Required environment variables:

```env
RDS_SYNC_DATABASE_URL=jdbc:postgresql://fitback-db.example.ap-northeast-2.rds.amazonaws.com:5432/fitback
RDS_SYNC_USERNAME=postgres
RDS_SYNC_PASSWORD=...
NEO4J_URI=neo4j+s://...
NEO4J_USERNAME=...
NEO4J_PASSWORD=...
NEO4J_DATABASE=neo4j
NEO4J_SYNC_ENABLED=true
GRAPH_INCLUDE_PII=false
```

Always run a dry run first:

```bash
python -m fitback_ai rds-sync --dry-run
```

The dry run prints:

- RDS table counts
- eligible completed consultation count
- scanned/succeeded/failed counts
- no AuraDB write

Run the initial backfill after reviewing the dry-run output:

```bash
python -m fitback_ai rds-sync
```

The backfill is idempotent because AuraDB writes use RDS ids with Neo4j `MERGE` and label constraints. Re-running the command updates properties and relationships instead of creating duplicate business nodes.

To compare RDS and AuraDB counts:

```bash
python -m fitback_ai rds-verify
```

Example output shape:

```json
{
  "command": "rds-verify",
  "comparisons": {
    "consultation": {
      "rds": 96,
      "aura": 96,
      "missing": 0,
      "duplicate": 0
    }
  }
}
```

## Sync Scope

The first production backfill scope is the same persisted analysis projection that Spring already sends to FastAPI:

- `Store`
- `Service`
- `Customer`
- `Consultation`
- `CustomerAiInsight`
- `NonConversionReason`
- `FollowUp`
- `FollowUpAiInsight`
- ontology labels and relationships

`users`, `inflow_path_option`, `message_template`, `event`, and conversion tables are counted during verification, but their wider graph expansion should be introduced as a follow-up when the recommendation queries need those relationships.

`rdsCounts` shows raw table counts. `comparisons` uses the eligible graph projection count, meaning consultations that are `COMPLETED`, have a non-empty summary, and have the related AI insight row needed to build the graph payload.

## Privacy

`GRAPH_INCLUDE_PII=false` is the recommended default. With that default, AuraDB omits direct customer identifiers such as customer name, phone number, birth date, and consultation raw text from the graph projection. `summary`, reason codes, service metadata, follow-up state, and ontology links remain available for GraphRAG and pattern analysis.

## Rollback

This tooling does not modify RDS. If a backfill must be rolled back, disable sync first:

```env
NEO4J_SYNC_ENABLED=false
GRAPH_PERSISTENCE_ENABLED=false
```

Then inspect AuraDB labels and remove only the projection nodes that were created from the verified RDS id set. Do not run broad `MATCH (n) DETACH DELETE n` commands on production AuraDB.
