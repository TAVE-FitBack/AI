from __future__ import annotations

import json
from typing import Any

from .api_models import ConsultationGraphSyncRequest
from .config import load_optional_settings
from .neo4j_loader import _counts, _driver, _upsert_ontology, setup_schema


def persist_consultation_graph(request: ConsultationGraphSyncRequest) -> dict[str, int] | None:
    settings = load_optional_settings()
    if settings is None:
        return None

    payload = _graph_sync_projection(request)
    try:
        with _driver(settings) as driver:
            driver.verify_connectivity()
            with driver.session(database=settings.neo4j_database) as session:
                setup_schema(session)
                session.execute_write(_upsert_ontology)
                session.execute_write(_upsert_graph_sync_projection, payload)
                return session.execute_read(_counts)
    except Exception as exc:
        raise RuntimeError("AuraDB graph persistence failed.") from exc


def _graph_sync_projection(request: ConsultationGraphSyncRequest) -> dict[str, Any]:
    dumped = request.model_dump(mode="json", by_alias=False)
    return {
        "store": {
            "id": dumped["store"]["store_id"],
            "storeType": dumped["store"]["store_type"],
        },
        "service": {
            "id": dumped["service"]["service_id"],
            "storeId": dumped["service"]["store_id"],
            "name": dumped["service"]["service_name"],
            "description": dumped["service"]["description"],
            "price": dumped["service"]["price"],
            "active": dumped["service"]["active"],
        },
        "customer": {
            "id": dumped["customer"]["customer_id"],
            "storeId": dumped["customer"]["store_id"],
            "registeredServiceId": dumped["customer"]["registered_service_id"],
            "name": dumped["customer"]["name"],
            "gender": dumped["customer"]["gender"],
            "birthDate": dumped["customer"]["birth_date"],
            "phoneNum": dumped["customer"]["phone_num"],
            "preferredContactChannel": dumped["customer"]["preferred_contact_channel"],
            "status": dumped["customer"]["status"],
            "inflowPathId": dumped["customer"]["inflow_path_id"],
            "inflowPathName": dumped["customer"]["inflow_path_name"],
            "registeredAt": dumped["customer"]["registered_at"],
            "firstConsultAt": dumped["customer"]["first_consult_at"],
            "latestConsultAt": dumped["customer"]["latest_consult_at"],
        },
        "consultation": {
            "id": dumped["consultation"]["consultation_id"],
            "customerId": dumped["consultation"]["customer_id"],
            "consultedServiceId": dumped["consultation"]["consulted_service_id"],
            "sessionNo": dumped["consultation"]["session_no"],
            "consultedAt": dumped["consultation"]["consulted_at"],
            "stage": dumped["consultation"]["stage"],
            "sourceType": dumped["consultation"]["source_type"],
            "rawText": dumped["consultation"]["raw_text"],
            "summary": dumped["consultation"]["summary"],
            "aiAnalysisStatus": dumped["consultation"]["ai_analysis_status"],
            "aiParsedAt": dumped["consultation"]["ai_parsed_at"],
        },
        "customerAiInsight": {
            "customerId": dumped["customer_ai_insight"]["customer_id"],
            "leadTemperature": dumped["customer_ai_insight"]["lead_temperature"],
            "temperatureBasis": dumped["customer_ai_insight"]["temperature_basis"],
            "priorityScore": dumped["customer_ai_insight"]["priority_score"],
            "analyzedAt": dumped["customer_ai_insight"]["analyzed_at"],
        },
        "nonConversionReasons": [
            {
                "id": reason["reason_id"],
                "customerId": reason["customer_id"],
                "consultationId": reason["consultation_id"],
                "reasonType": reason["reason_type"],
                "role": reason["role"],
                "reasonBasis": reason["reason_basis"],
                "confidence": reason["confidence"],
            }
            for reason in dumped["non_conversion_reasons"]
        ],
        "followUp": _optional_follow_up(dumped["follow_up"]),
        "followUpAiInsight": _optional_follow_up_ai_insight(dumped["follow_up_ai_insight"]),
    }


def _optional_follow_up(value: dict[str, Any] | None) -> dict[str, Any] | None:
    if value is None:
        return None
    return {
        "id": value["follow_up_id"],
        "customerId": value["customer_id"],
        "consultationId": value["consultation_id"],
        "recommendContactDate": value["recommend_contact_date"],
        "status": value["status"],
        "contactRound": value["contact_round"],
        "hasReply": value["has_reply"],
        "repliedAt": value["replied_at"],
        "snoozedUntil": value["snoozed_until"],
        "memo": value["memo"],
    }


def _optional_follow_up_ai_insight(value: dict[str, Any] | None) -> dict[str, Any] | None:
    if value is None:
        return None
    return {
        "followUpId": value["follow_up_id"],
        "persuasionPoint": _json_property(value["persuasion_point"]),
        "cautionNote": value["caution_note"],
        "actionBasis": _json_property(value["action_basis"]),
        "analyzedAt": value["analyzed_at"],
    }


def _json_property(value: Any) -> str:
    return json.dumps(value or {}, ensure_ascii=False, sort_keys=True)


def _upsert_graph_sync_projection(tx, payload: dict[str, Any]) -> None:
    tx.run(
        """
        MERGE (store:Store {id: $store.id})
        SET store += $store

        MERGE (service:Service {id: $service.id})
        SET service += $service
        MERGE (store)-[:OFFERS]->(service)

        MERGE (customer:Customer {id: $customer.id})
        SET customer += $customer
        MERGE (store)-[:HAS_CUSTOMER]->(customer)
        MERGE (customer)-[:INTERESTED_IN]->(service)

        MERGE (consultation:Consultation {id: $consultation.id})
        SET consultation += $consultation,
            consultation.ragText = $consultation.rawText + ' ' + coalesce($consultation.summary, '')
        MERGE (customer)-[:HAD_CONSULTATION]->(consultation)
        MERGE (consultation)-[:ABOUT_SERVICE]->(service)

        MERGE (insight:CustomerAiInsight {id: $customerAiInsight.customerId})
        SET insight += $customerAiInsight
        MERGE (customer)-[:HAS_AI_INSIGHT]->(insight)
        WITH insight, $customerAiInsight AS insightPayload
        OPTIONAL MATCH (matchedTemperatureConcept:LeadTemperatureConcept {code: insightPayload.leadTemperature})
        MATCH (fallbackTemperatureConcept:LeadTemperatureConcept {code: 'COLD'})
        WITH insight, coalesce(matchedTemperatureConcept, fallbackTemperatureConcept) AS temperatureConcept
        MERGE (insight)-[:HAS_TEMPERATURE]->(temperatureConcept)
        """,
        **payload,
    )
    tx.run(
        """
        MATCH (customer:Customer {id: $customer.id})
        MATCH (consultation:Consultation {id: $consultation.id})
        UNWIND $nonConversionReasons AS reasonPayload
        MERGE (reason:NonConversionReason {id: reasonPayload.id})
        SET reason += reasonPayload
        MERGE (customer)-[:HAS_NON_CONVERSION_REASON]->(reason)
        MERGE (consultation)-[:HAS_NON_CONVERSION_REASON]->(reason)
        WITH reason, reasonPayload
        OPTIONAL MATCH (matchedReasonConcept:ReasonConcept {code: reasonPayload.reasonType})
        MATCH (fallbackReasonConcept:ReasonConcept {code: 'NEEDS_FOLLOW_UP'})
        WITH reason, coalesce(matchedReasonConcept, fallbackReasonConcept) AS reasonConcept
        MERGE (reason)-[:INSTANCE_OF]->(reasonConcept)
        """,
        **payload,
    )
    if payload["followUp"] is not None:
        tx.run(
            """
            MATCH (customer:Customer {id: $customer.id})
            MATCH (consultation:Consultation {id: $consultation.id})
            MERGE (followUp:FollowUp {id: $followUp.id})
            SET followUp += $followUp,
                followUp.ragText = coalesce($followUp.memo, '')
            MERGE (customer)-[:HAS_FOLLOW_UP]->(followUp)
            MERGE (consultation)-[:HAS_FOLLOW_UP]->(followUp)
            """,
            **payload,
        )
    if payload["followUpAiInsight"] is not None:
        tx.run(
            """
            MATCH (followUp:FollowUp {id: $followUpAiInsight.followUpId})
            MERGE (insight:FollowUpAiInsight {id: $followUpAiInsight.followUpId})
            SET insight += $followUpAiInsight
            MERGE (followUp)-[:HAS_AI_INSIGHT]->(insight)
            """,
            **payload,
        )
