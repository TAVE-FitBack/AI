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
