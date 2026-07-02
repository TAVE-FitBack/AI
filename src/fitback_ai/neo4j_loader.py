from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Any

from neo4j import GraphDatabase
from neo4j.exceptions import ServiceUnavailable

from .config import Settings


@dataclass(frozen=True)
class LoadResult:
    batch_id: str
    record_count: int
    elapsed_ms: float
    counts: dict[str, int]


LABELS = [
    "Store",
    "User",
    "Service",
    "Customer",
    "Consultation",
    "FollowUp",
    "NonConversionReason",
    "ConsultationSignal",
    "CustomerAiInsight",
    "Event",
    "EventTarget",
    "MessageTemplate",
    "ContactResult",
]


def load_graph(settings: Settings, payload: dict[str, Any]) -> LoadResult:
    started = perf_counter()
    with _driver(settings) as driver:
        driver.verify_connectivity()
        with driver.session(database=settings.neo4j_database) as session:
            setup_schema(session)
            session.execute_write(_delete_batch, payload["mockBatchId"])
            session.execute_write(_upsert_payload, payload)
            counts = session.execute_read(_counts, payload["mockBatchId"])
    elapsed_ms = (perf_counter() - started) * 1000
    return LoadResult(
        batch_id=payload["mockBatchId"],
        record_count=payload["recordCount"],
        elapsed_ms=elapsed_ms,
        counts=counts,
    )


def verify_graph(settings: Settings, batch_id: str) -> dict[str, int]:
    with _driver(settings) as driver:
        driver.verify_connectivity()
        with driver.session(database=settings.neo4j_database) as session:
            return session.execute_read(_counts, batch_id)


def _driver(settings: Settings):
    try:
        return GraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_username, settings.neo4j_password),
        )
    except ServiceUnavailable as exc:
        raise RuntimeError("Neo4j driver could not be created") from exc


def setup_schema(session) -> None:
    for label in LABELS:
        session.run(f"CREATE CONSTRAINT {label.lower()}_id IF NOT EXISTS FOR (n:{label}) REQUIRE n.id IS UNIQUE")
    session.run("CREATE INDEX mock_batch_id IF NOT EXISTS FOR (n:MockData) ON (n.mockBatchId)")
    session.run("CREATE TEXT INDEX consultation_rag_text IF NOT EXISTS FOR (n:Consultation) ON (n.ragText)")
    session.run("CREATE TEXT INDEX follow_up_rag_text IF NOT EXISTS FOR (n:FollowUp) ON (n.ragText)")


def _delete_batch(tx, batch_id: str) -> None:
    tx.run(
        """
        MATCH (n:MockData {mockBatchId: $batchId})
        DETACH DELETE n
        """,
        batchId=batch_id,
    )


def _upsert_payload(tx, payload: dict[str, Any]) -> None:
    tx.run(
        """
        MERGE (store:Store:MockData {id: $store.id})
        SET store += $store

        WITH store
        UNWIND $users AS item
        MERGE (user:User:MockData {id: item.id})
        SET user += item
        MERGE (store)-[:HAS_USER]->(user)

        WITH store
        UNWIND $services AS item
        MERGE (service:Service:MockData {id: item.id})
        SET service += item
        MERGE (store)-[:OFFERS]->(service)

        WITH store
        UNWIND $events AS item
        MERGE (event:Event:MockData {id: item.id})
        SET event += item
        MERGE (store)-[:RUNS_EVENT]->(event)
        WITH event, item
        MATCH (service:Service {id: item.serviceId})
        MERGE (event)-[:PROMOTES]->(service)
        """,
        store=payload["store"],
        users=payload["users"],
        services=payload["services"],
        events=payload["events"],
    )
    tx.run(
        """
        UNWIND $rows AS row
        MATCH (store:Store {id: row.customer.storeId})
        MATCH (service:Service {id: row.consultation.consultedServiceId})
        MATCH (user:User {id: row.consultation.userId})
        MATCH (event:Event {id: row.eventTarget.eventId})

        MERGE (customer:Customer:MockData {id: row.customer.id})
        SET customer += row.customer
        MERGE (store)-[:HAS_CUSTOMER]->(customer)
        MERGE (customer)-[:INTERESTED_IN]->(service)

        MERGE (consultation:Consultation:MockData {id: row.consultation.id})
        SET consultation += row.consultation,
            consultation.ragText = row.consultation.rawText + ' ' + coalesce(row.consultation.summary, '')
        MERGE (customer)-[:HAD_CONSULTATION]->(consultation)
        MERGE (consultation)-[:ABOUT_SERVICE]->(service)
        MERGE (consultation)-[:CONSULTED_BY]->(user)

        MERGE (followUp:FollowUp:MockData {id: row.followUp.id})
        SET followUp += row.followUp,
            followUp.ragText = row.followUp.memo
        MERGE (consultation)-[:HAS_FOLLOW_UP]->(followUp)

        MERGE (reason:NonConversionReason:MockData {id: row.nonConversionReason.id})
        SET reason += row.nonConversionReason
        MERGE (customer)-[:HAS_NON_CONVERSION_REASON]->(reason)
        MERGE (consultation)-[:HAS_NON_CONVERSION_REASON]->(reason)

        MERGE (signal:ConsultationSignal:MockData {id: row.consultationSignal.id})
        SET signal += row.consultationSignal
        MERGE (consultation)-[:HAS_SIGNAL]->(signal)

        MERGE (insight:CustomerAiInsight:MockData {id: row.customerAiInsight.customerId})
        SET insight += row.customerAiInsight
        MERGE (customer)-[:HAS_AI_INSIGHT]->(insight)

        MERGE (target:EventTarget:MockData {id: row.eventTarget.id})
        SET target += row.eventTarget
        MERGE (event)-[:TARGETS]->(target)
        MERGE (target)-[:TARGET_CUSTOMER]->(customer)

        MERGE (message:MessageTemplate:MockData {id: row.messageTemplate.id})
        SET message += row.messageTemplate
        MERGE (customer)-[:HAS_MESSAGE]->(message)
        MERGE (followUp)-[:GENERATED_MESSAGE]->(message)
        MERGE (target)-[:HAS_MESSAGE]->(message)

        MERGE (contact:ContactResult:MockData {id: row.contactResult.id})
        SET contact += row.contactResult
        MERGE (customer)-[:HAS_CONTACT_RESULT]->(contact)
        MERGE (followUp)-[:HAS_CONTACT_RESULT]->(contact)
        """,
        rows=payload["consultationRows"],
    )


def _counts(tx, batch_id: str) -> dict[str, int]:
    result = {}
    for label in LABELS:
        record = tx.run(
            f"MATCH (n:{label}:MockData {{mockBatchId: $batchId}}) RETURN count(n) AS count",
            batchId=batch_id,
        ).single()
        result[label] = int(record["count"])
    rel_record = tx.run(
        """
        MATCH (n:MockData {mockBatchId: $batchId})-[r]-()
        RETURN count(DISTINCT r) AS count
        """,
        batchId=batch_id,
    ).single()
    result["Relationships"] = int(rel_record["count"])
    return result
