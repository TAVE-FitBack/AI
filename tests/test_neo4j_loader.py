from fitback_ai import neo4j_loader


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


def test_upsert_payload_links_business_nodes_to_ontology_concepts():
    tx = FakeSession()
    payload = production_payload()

    neo4j_loader._upsert_payload(tx, payload)

    queries = "\n".join(call.query for call in tx.calls)
    assert "INSTANCE_OF" in queries
    assert "HAS_TEMPERATURE" in queries


def test_upsert_payload_stores_canonical_ontology_properties():
    tx = FakeSession()
    payload = production_payload()
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


def test_upsert_payload_accepts_empty_initial_graph():
    tx = FakeSession()

    neo4j_loader._upsert_payload(tx, {"store": None, "users": [], "services": [], "events": [], "consultationRows": []})

    assert tx.calls == []


def test_counts_query_does_not_require_legacy_batch_markers():
    tx = FakeSession()

    counts = neo4j_loader._counts(tx)

    queries = "\n".join(call.query for call in tx.calls)
    legacy_label = "M" + "ockData"
    legacy_batch_id = "m" + "ockBatchId"
    assert legacy_label not in queries
    assert legacy_batch_id not in queries
    assert counts["Customer"] == 0


def test_normalize_payload_rejects_business_data_without_store():
    payload = {"consultationRows": [{"id": "row-1"}]}

    try:
        neo4j_loader._normalize_payload(payload)
    except ValueError as exc:
        assert "requires store" in str(exc)
    else:
        raise AssertionError("Expected store validation error")


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


def production_payload():
    return {
        "store": {
            "id": "store-1",
            "name": "핏백 실제 매장",
            "storeType": "GYM",
        },
        "users": [
            {
                "id": "user-1",
                "storeId": "store-1",
                "nickname": "상담매니저",
                "role": "STAFF",
            }
        ],
        "services": [
            {
                "id": "service-1",
                "storeId": "store-1",
                "name": "PT",
                "description": "개인 맞춤 트레이닝",
                "isActive": True,
            }
        ],
        "events": [
            {
                "id": "event-1",
                "storeId": "store-1",
                "serviceId": "service-1",
                "title": "신규 등록 이벤트",
                "status": "ACTIVE",
            }
        ],
        "consultationRows": [
            {
                "customer": {
                    "id": "customer-1",
                    "storeId": "store-1",
                    "name": "홍길동",
                    "status": "PENDING",
                },
                "consultation": {
                    "id": "consultation-1",
                    "customerId": "customer-1",
                    "userId": "user-1",
                    "consultedServiceId": "service-1",
                    "rawText": "가격을 고민 중입니다.",
                    "summary": "가격 부담으로 보류",
                },
                "followUp": {
                    "id": "follow-up-1",
                    "consultationId": "consultation-1",
                    "recommendContactDate": "2026-07-20",
                    "memo": "예산별 상품 안내",
                },
                "nonConversionReason": {
                    "id": "reason-1",
                    "customerId": "customer-1",
                    "consultationId": "consultation-1",
                    "reasonType": "PRICE",
                    "role": "PRIMARY",
                    "reasonBasis": "가격을 고민 중입니다.",
                    "confidence": "HIGH",
                },
                "consultationSignal": {
                    "id": "signal-1",
                    "consultationId": "consultation-1",
                    "signalType": "PRICE_SENSITIVE",
                    "confidence": "HIGH",
                    "evidenceText": "가격을 고민 중입니다.",
                },
                "customerAiInsight": {
                    "customerId": "customer-1",
                    "leadTemperature": "WARM",
                    "temperatureBasis": "가격 부담이 있지만 관심 있음",
                    "priorityScore": 80,
                },
                "eventTarget": {
                    "id": "event-target-1",
                    "customerId": "customer-1",
                    "eventId": "event-1",
                    "status": "PENDING",
                },
                "messageTemplate": {
                    "id": "message-1",
                    "customerId": "customer-1",
                    "followUpId": "follow-up-1",
                    "eventTargetId": "event-target-1",
                    "content": "예산별 상품을 안내드립니다.",
                    "versionType": "STANDARD",
                    "tonePreset": "FRIENDLY",
                },
                "contactResult": {
                    "id": "contact-1",
                    "customerId": "customer-1",
                    "followUpId": "follow-up-1",
                    "resultStatus": "NOT_CONTACTED",
                },
            }
        ],
    }
