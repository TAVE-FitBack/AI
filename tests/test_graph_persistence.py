from __future__ import annotations

import pytest

from fitback_ai import graph_persistence
from fitback_ai.api_models import ConsultationGraphSyncRequest


def test_persist_consultation_graph_is_noop_when_disabled(monkeypatch):
    monkeypatch.setenv("GRAPH_PERSISTENCE_ENABLED", "false")
    request = ConsultationGraphSyncRequest.model_validate(graph_sync_payload())

    result = graph_persistence.persist_consultation_graph(request)

    assert result is None


def test_persist_consultation_graph_requires_neo4j_settings_when_enabled(monkeypatch):
    monkeypatch.setenv("GRAPH_PERSISTENCE_ENABLED", "true")
    monkeypatch.setenv("NEO4J_URI", "")
    monkeypatch.setenv("NEO4J_USERNAME", "")
    monkeypatch.setenv("NEO4J_PASSWORD", "")
    request = ConsultationGraphSyncRequest.model_validate(graph_sync_payload())

    with pytest.raises(RuntimeError, match="GRAPH_PERSISTENCE_ENABLED=true"):
        graph_persistence.persist_consultation_graph(request)


def test_persist_consultation_graph_wraps_auradb_failures(monkeypatch):
    monkeypatch.setenv("GRAPH_PERSISTENCE_ENABLED", "true")
    monkeypatch.setenv("NEO4J_URI", "neo4j+s://example.databases.neo4j.io")
    monkeypatch.setenv("NEO4J_USERNAME", "neo4j")
    monkeypatch.setenv("NEO4J_PASSWORD", "secret")
    request = ConsultationGraphSyncRequest.model_validate(graph_sync_payload())

    def fail_driver(_):
        raise ValueError("connection failed")

    monkeypatch.setattr(graph_persistence, "_driver", fail_driver)

    with pytest.raises(RuntimeError, match="AuraDB graph persistence failed"):
        graph_persistence.persist_consultation_graph(request)


def test_graph_sync_projection_uses_persisted_rds_ids():
    request = ConsultationGraphSyncRequest.model_validate(graph_sync_payload())
    payload = graph_persistence._graph_sync_projection(request)

    assert payload["followUp"]["id"] == "55555555-5555-5555-5555-555555555555"
    assert payload["nonConversionReasons"][0]["id"] == "44444444-4444-4444-4444-444444444444"
    assert payload["consultation"]["aiAnalysisStatus"] == "COMPLETED"
    assert payload["followUpAiInsight"]["persuasionPoint"] == '{"main": "Lower initial cost."}'
    assert (
        payload["followUpAiInsight"]["actionBasis"]
        == '{"description": "Offer starter plan.", "title": "Budget option"}'
    )


def test_upsert_graph_sync_projection_writes_saved_ids_and_ontology_links():
    tx = FakeSession()
    request = ConsultationGraphSyncRequest.model_validate(graph_sync_payload())
    payload = graph_persistence._graph_sync_projection(request)

    graph_persistence._upsert_graph_sync_projection(tx, payload)

    queries = "\n".join(call.query for call in tx.calls)
    assert "MERGE (store:Store" in queries
    assert "MERGE (consultation:Consultation" in queries
    assert "MERGE (reason:NonConversionReason {id: reasonPayload.id})" in queries
    assert "MERGE (reason)-[:INSTANCE_OF]->(reasonConcept)" in queries
    assert "MERGE (insight)-[:HAS_TEMPERATURE]->(temperatureConcept)" in queries
    assert "MERGE (followUp:FollowUp {id: $followUp.id})" in queries
    assert "MERGE (insight:FollowUpAiInsight {id: $followUpAiInsight.followUpId})" in queries


def test_upsert_graph_sync_projection_allows_registered_customer_without_follow_up():
    tx = FakeSession()
    data = graph_sync_payload()
    data["customer"]["status"] = "REGISTERED"
    data["followUp"] = None
    data["followUpAiInsight"] = None
    request = ConsultationGraphSyncRequest.model_validate(data)
    payload = graph_persistence._graph_sync_projection(request)

    graph_persistence._upsert_graph_sync_projection(tx, payload)

    queries = "\n".join(call.query for call in tx.calls)
    assert "MERGE (consultation:Consultation" in queries
    assert "MERGE (followUp:FollowUp" not in queries


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


def graph_sync_payload():
    return {
        "store": {
            "storeId": "11111111-1111-1111-1111-111111111111",
            "storeType": "GYM",
        },
        "service": {
            "serviceId": "22222222-2222-2222-2222-222222222222",
            "storeId": "11111111-1111-1111-1111-111111111111",
            "serviceName": "PT",
            "description": "1:1 training",
            "price": 300000,
            "active": True,
        },
        "customer": {
            "customerId": "33333333-3333-3333-3333-333333333333",
            "storeId": "11111111-1111-1111-1111-111111111111",
            "registeredServiceId": None,
            "name": "Hong",
            "gender": "FEMALE",
            "birthDate": "1995-01-01",
            "phoneNum": "010-1234-5678",
            "preferredContactChannel": "KAKAO",
            "status": "PENDING",
            "inflowPathId": "66666666-6666-6666-6666-666666666666",
            "inflowPathName": "Naver",
            "registeredAt": None,
            "firstConsultAt": "2026-07-01",
            "latestConsultAt": "2026-07-01",
        },
        "consultation": {
            "consultationId": "77777777-7777-7777-7777-777777777777",
            "customerId": "33333333-3333-3333-3333-333333333333",
            "consultedServiceId": "22222222-2222-2222-2222-222222222222",
            "sessionNo": 1,
            "consultedAt": "2026-07-01T13:00:00+09:00",
            "stage": "CONSULTATION",
            "sourceType": "INQUIRY",
            "rawText": "price concern",
            "summary": "Customer has price concern.",
            "aiAnalysisStatus": "COMPLETED",
            "aiParsedAt": "2026-07-01T13:01:00+09:00",
        },
        "customerAiInsight": {
            "customerId": "33333333-3333-3333-3333-333333333333",
            "leadTemperature": "WARM",
            "temperatureBasis": "Interested but worried about price.",
            "priorityScore": 78,
            "analyzedAt": "2026-07-01T13:01:00+09:00",
        },
        "nonConversionReasons": [
            {
                "reasonId": "44444444-4444-4444-4444-444444444444",
                "customerId": "33333333-3333-3333-3333-333333333333",
                "consultationId": "77777777-7777-7777-7777-777777777777",
                "reasonType": "PRICE",
                "role": "PRIMARY",
                "reasonBasis": "Budget concern.",
                "confidence": "HIGH",
            }
        ],
        "followUp": {
            "followUpId": "55555555-5555-5555-5555-555555555555",
            "customerId": "33333333-3333-3333-3333-333333333333",
            "consultationId": "77777777-7777-7777-7777-777777777777",
            "recommendContactDate": "2026-07-03",
            "status": "PENDING",
            "contactRound": 1,
            "hasReply": False,
            "repliedAt": None,
            "snoozedUntil": None,
            "memo": "Send budget option.",
        },
        "followUpAiInsight": {
            "followUpId": "55555555-5555-5555-5555-555555555555",
            "persuasionPoint": {"main": "Lower initial cost."},
            "cautionNote": "Avoid pressure.",
            "actionBasis": {"title": "Budget option", "description": "Offer starter plan."},
            "analyzedAt": "2026-07-01T13:01:00+09:00",
        },
    }
