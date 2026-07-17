from fitback_ai import neo4j_loader
from fitback_ai.mock_data import generate_records


def test_setup_schema_includes_ontology_labels():
    session = FakeSession()

    neo4j_loader.setup_schema(session)

    queries = "\n".join(call.query for call in session.calls)
    assert "ReasonConcept" in queries
    assert "ReasonCategory" in queries
    assert "ActionConcept" in queries
    assert "LeadTemperatureConcept" in queries


def test_upsert_ontology_creates_semantic_relationships():
    tx = FakeSession()

    neo4j_loader._upsert_ontology(tx)

    queries = "\n".join(call.query for call in tx.calls)
    prune_call = tx.calls[0]
    assert "DETACH DELETE concept" in prune_call.query
    assert "PRICE" in prune_call.kwargs["currentIds"]
    assert "BUDGET_OPTION_GUIDE" in prune_call.kwargs["currentIds"]
    assert "BELONGS_TO" in queries
    assert "RECOMMENDS_ACTION" in queries


def test_upsert_payload_links_mock_nodes_to_ontology_concepts():
    tx = FakeSession()
    payload = generate_records(1, "store-1", "batch-1")

    neo4j_loader._upsert_payload(tx, payload)

    queries = "\n".join(call.query for call in tx.calls)
    assert "INSTANCE_OF" in queries
    assert "HAS_TEMPERATURE" in queries


def test_upsert_payload_stores_canonical_ontology_properties():
    tx = FakeSession()
    payload = generate_records(1, "store-1", "batch-1")
    row = payload["consultationRows"][0]
    row["nonConversionReason"]["reasonType"] = "PRICE_CONCERN"
    row["customerAiInsight"]["leadTemperature"] = "VERY_HOT"

    neo4j_loader._upsert_payload(tx, payload)

    row_params = tx.calls[1].kwargs["rows"][0]
    assert row_params["nonConversionReason"]["reasonType"] == "PRICE"
    assert row_params["nonConversionReason"]["originalReasonType"] == "PRICE_CONCERN"
    assert row_params["nonConversionReason"]["ontologyFallbackApplied"] is True
    assert row_params["customerAiInsight"]["leadTemperature"] == "COLD"
    assert row_params["customerAiInsight"]["originalLeadTemperature"] == "VERY_HOT"
    assert row_params["customerAiInsight"]["ontologyFallbackApplied"] is True


class FakeSession:
    def __init__(self) -> None:
        self.calls = []

    def run(self, query: str, **kwargs):
        self.calls.append(FakeCall(query=query, kwargs=kwargs))
        return FakeResult()


class FakeCall:
    def __init__(self, query: str, kwargs: dict) -> None:
        self.query = query
        self.kwargs = kwargs


class FakeResult:
    def single(self):
        return {"count": 0}
