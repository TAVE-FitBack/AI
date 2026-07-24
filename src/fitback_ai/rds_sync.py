from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import Any

from .api_models import ConsultationGraphSyncRequest
from .config import RdsSyncSettings
from .graph_persistence import persist_consultation_graph


RDS_TABLES = [
    "store",
    "users",
    "service",
    "inflow_path_option",
    "customer",
    "consultation",
    "customer_ai_insight",
    "non_conversion_reason",
    "follow_up",
    "follow_up_ai_insight",
    "interest_service",
    "message_template",
    "follow_up_conversion",
    "event",
]

CORE_LABEL_BY_TABLE = {
    "store": "Store",
    "service": "Service",
    "customer": "Customer",
    "consultation": "Consultation",
    "customer_ai_insight": "CustomerAiInsight",
    "non_conversion_reason": "NonConversionReason",
    "follow_up": "FollowUp",
    "follow_up_ai_insight": "FollowUpAiInsight",
}


@dataclass(frozen=True)
class SyncResult:
    dry_run: bool
    scanned: int
    succeeded: int
    failed: int
    rds_counts: dict[str, int]
    aura_counts: dict[str, int] | None
    errors: list[str]


@dataclass(frozen=True)
class VerifyResult:
    rds_counts: dict[str, int]
    aura_counts: dict[str, int]
    comparisons: dict[str, dict[str, int]]


def connect_rds(settings: RdsSyncSettings):
    try:
        import psycopg
        from psycopg.rows import dict_row
    except ImportError as exc:
        raise RuntimeError("psycopg is required for RDS sync. Install project dependencies first.") from exc

    return psycopg.connect(
        _postgres_dsn(settings.database_url),
        user=settings.username,
        password=settings.password,
        row_factory=dict_row,
        connect_timeout=10,
    )


def sync_initial(
    settings: RdsSyncSettings,
    *,
    dry_run: bool,
    limit: int | None = None,
    connect: Callable[[RdsSyncSettings], Any] = connect_rds,
    persist: Callable[[ConsultationGraphSyncRequest], dict[str, int] | None] = persist_consultation_graph,
) -> SyncResult:
    scanned = 0
    succeeded = 0
    failed = 0
    errors: list[str] = []
    aura_counts: dict[str, int] | None = None

    with connect(settings) as conn:
        rds_counts = count_rds_tables(conn)
        for payload in iter_graph_sync_payloads(conn, batch_size=settings.batch_size, limit=limit):
            scanned += 1
            if dry_run:
                succeeded += 1
                continue
            try:
                request = ConsultationGraphSyncRequest.model_validate(payload)
                aura_counts = persist(request)
                succeeded += 1
            except Exception as exc:  # keep one bad row from stopping the full backfill
                failed += 1
                consultation_id = payload.get("consultation", {}).get("consultationId")
                errors.append(f"consultationId={consultation_id}: {type(exc).__name__}")

    return SyncResult(
        dry_run=dry_run,
        scanned=scanned,
        succeeded=succeeded,
        failed=failed,
        rds_counts=rds_counts,
        aura_counts=aura_counts,
        errors=errors,
    )


def verify_sync(
    settings: RdsSyncSettings,
    *,
    connect: Callable[[RdsSyncSettings], Any] = connect_rds,
    graph_counts: Callable[[], dict[str, int]],
) -> VerifyResult:
    with connect(settings) as conn:
        rds_counts = count_rds_tables(conn)
        expected_counts = count_expected_graph_projection(conn)

    aura_counts = graph_counts()
    comparisons = {}
    for table, label in CORE_LABEL_BY_TABLE.items():
        rds = expected_counts.get(table, 0)
        aura = aura_counts.get(label, 0)
        comparisons[table] = {
            "rds": rds,
            "aura": aura,
            "missing": max(rds - aura, 0),
            "duplicate": aura_counts.get(f"{label}DuplicateId", 0),
        }
    return VerifyResult(rds_counts=rds_counts, aura_counts=aura_counts, comparisons=comparisons)


def count_rds_tables(conn) -> dict[str, int]:
    existing = set(_fetch_existing_tables(conn))
    counts = {}
    for table in RDS_TABLES:
        if table not in existing:
            counts[table] = 0
            continue
        with conn.cursor() as cur:
            cur.execute(f"SELECT count(*) AS count FROM {table}")
            row = cur.fetchone()
            counts[table] = int(row["count"])
    counts["eligible_consultation_graph_sync"] = count_eligible_consultations(conn)
    return counts


def count_eligible_consultations(conn) -> int:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT count(*) AS count
            FROM consultation c
            JOIN customer cu ON cu.id = c.customer_id
            JOIN store st ON st.id = cu.store_id
            JOIN service sv ON sv.id = c.consulted_service_id
            JOIN inflow_path_option ip ON ip.id = cu.inflow_path_id
            JOIN customer_ai_insight cai ON cai.customer_id = cu.id
            WHERE c.ai_analysis_status = 'COMPLETED'
              AND c.summary IS NOT NULL
              AND btrim(c.summary) <> ''
            """
        )
        row = cur.fetchone()
        return int(row["count"])


def count_expected_graph_projection(conn) -> dict[str, int]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                count(DISTINCT st.id) AS store,
                count(DISTINCT sv.id) AS service,
                count(DISTINCT cu.id) AS customer,
                count(DISTINCT c.id) AS consultation,
                count(DISTINCT cai.customer_id) AS customer_ai_insight,
                count(DISTINCT ncr.id) AS non_conversion_reason,
                count(DISTINCT fu.id) AS follow_up,
                count(DISTINCT fuai.follow_up_id) AS follow_up_ai_insight
            FROM consultation c
            JOIN customer cu ON cu.id = c.customer_id
            JOIN store st ON st.id = cu.store_id
            JOIN service sv ON sv.id = c.consulted_service_id
            JOIN inflow_path_option ip ON ip.id = cu.inflow_path_id
            JOIN customer_ai_insight cai ON cai.customer_id = cu.id
            LEFT JOIN non_conversion_reason ncr ON ncr.consultation_id = c.id
            LEFT JOIN LATERAL (
                SELECT *
                FROM follow_up
                WHERE consultation_id = c.id
                ORDER BY created_at DESC
                LIMIT 1
            ) fu ON true
            LEFT JOIN follow_up_ai_insight fuai ON fuai.follow_up_id = fu.id
            WHERE c.ai_analysis_status = 'COMPLETED'
              AND c.summary IS NOT NULL
              AND btrim(c.summary) <> ''
            """
        )
        row = cur.fetchone()
        return {table: int(row[table]) for table in CORE_LABEL_BY_TABLE}


def iter_graph_sync_payloads(conn, *, batch_size: int, limit: int | None = None) -> Iterator[dict[str, Any]]:
    offset = 0
    emitted = 0
    while limit is None or emitted < limit:
        page_size = batch_size if limit is None else min(batch_size, limit - emitted)
        rows = _fetch_consultation_page(conn, limit=page_size, offset=offset)
        if not rows:
            break
        reasons = _fetch_reasons(conn, [row["consultation_id"] for row in rows])
        for row in rows:
            yield _row_to_graph_sync_payload(row, reasons.get(str(row["consultation_id"]), []))
            emitted += 1
        offset += len(rows)


def _fetch_existing_tables(conn) -> list[str]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            """
        )
        return [row["table_name"] for row in cur.fetchall()]


def _fetch_consultation_page(conn, *, limit: int, offset: int) -> list[dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                st.id AS store_id,
                st.store_type AS store_type,
                sv.id AS service_id,
                sv.store_id AS service_store_id,
                sv.name AS service_name,
                sv.description AS service_description,
                sv.price AS service_price,
                sv.is_active AS service_active,
                cu.id AS customer_id,
                cu.store_id AS customer_store_id,
                cu.registered_service_id AS registered_service_id,
                cu.name AS customer_name,
                cu.gender AS customer_gender,
                cu.birth_date AS customer_birth_date,
                cu.phone_num AS customer_phone_num,
                cu.preferred_contact_channel AS preferred_contact_channel,
                cu.status AS customer_status,
                cu.inflow_path_id AS inflow_path_id,
                ip.name AS inflow_path_name,
                cu.registered_at AS registered_at,
                cu.first_consult_at AS first_consult_at,
                cu.latest_consult_at AS latest_consult_at,
                c.id AS consultation_id,
                c.session_no AS session_no,
                c.consulted_at AS consulted_at,
                c.stage AS consultation_stage,
                c.source_type AS source_type,
                c.raw_text AS raw_text,
                c.summary AS summary,
                c.ai_analysis_status AS ai_analysis_status,
                c.ai_parsed_at AS ai_parsed_at,
                cai.lead_temperature AS lead_temperature,
                cai.temperature_basis AS temperature_basis,
                cai.priority_score AS priority_score,
                cai.analyzed_at AS insight_analyzed_at,
                fu.id AS follow_up_id,
                fu.recommend_contact_date AS recommend_contact_date,
                fu.status AS follow_up_status,
                fu.contact_round AS contact_round,
                fu.has_reply AS has_reply,
                fu.replied_at AS replied_at,
                fu.snoozed_until AS snoozed_until,
                fu.memo AS follow_up_memo,
                fuai.persuasion_point AS persuasion_point,
                fuai.caution_note AS caution_note,
                fuai.action_basis AS action_basis,
                fuai.analyzed_at AS follow_up_ai_analyzed_at
            FROM consultation c
            JOIN customer cu ON cu.id = c.customer_id
            JOIN store st ON st.id = cu.store_id
            JOIN service sv ON sv.id = c.consulted_service_id
            JOIN inflow_path_option ip ON ip.id = cu.inflow_path_id
            JOIN customer_ai_insight cai ON cai.customer_id = cu.id
            LEFT JOIN LATERAL (
                SELECT *
                FROM follow_up
                WHERE consultation_id = c.id
                ORDER BY created_at DESC
                LIMIT 1
            ) fu ON true
            LEFT JOIN follow_up_ai_insight fuai ON fuai.follow_up_id = fu.id
            WHERE c.ai_analysis_status = 'COMPLETED'
              AND c.summary IS NOT NULL
              AND btrim(c.summary) <> ''
            ORDER BY c.consulted_at, c.id
            LIMIT %s OFFSET %s
            """,
            (limit, offset),
        )
        return list(cur.fetchall())


def _fetch_reasons(conn, consultation_ids: list[Any]) -> dict[str, list[dict[str, Any]]]:
    if not consultation_ids:
        return {}
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                id AS reason_id,
                customer_id,
                consultation_id,
                reason_type,
                role,
                reason_basis,
                confidence
            FROM non_conversion_reason
            WHERE consultation_id = ANY(%s)
            ORDER BY created_at, id
            """,
            (consultation_ids,),
        )
        grouped: dict[str, list[dict[str, Any]]] = {}
        for row in cur.fetchall():
            grouped.setdefault(str(row["consultation_id"]), []).append(row)
        return grouped


def _row_to_graph_sync_payload(row: dict[str, Any], reasons: list[dict[str, Any]]) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "store": {
            "storeId": row["store_id"],
            "storeType": row["store_type"],
        },
        "service": {
            "serviceId": row["service_id"],
            "storeId": row["service_store_id"],
            "serviceName": row["service_name"],
            "description": row["service_description"],
            "price": row["service_price"],
            "active": row["service_active"],
        },
        "customer": {
            "customerId": row["customer_id"],
            "storeId": row["customer_store_id"],
            "registeredServiceId": row["registered_service_id"],
            "name": row["customer_name"],
            "gender": row["customer_gender"],
            "birthDate": row["customer_birth_date"],
            "phoneNum": row["customer_phone_num"],
            "preferredContactChannel": row["preferred_contact_channel"],
            "status": row["customer_status"],
            "inflowPathId": row["inflow_path_id"],
            "inflowPathName": row["inflow_path_name"],
            "registeredAt": row["registered_at"],
            "firstConsultAt": row["first_consult_at"],
            "latestConsultAt": row["latest_consult_at"],
        },
        "consultation": {
            "consultationId": row["consultation_id"],
            "customerId": row["customer_id"],
            "consultedServiceId": row["service_id"],
            "sessionNo": row["session_no"],
            "consultedAt": row["consulted_at"],
            "stage": row["consultation_stage"],
            "sourceType": row["source_type"],
            "rawText": row["raw_text"],
            "summary": row["summary"],
            "aiAnalysisStatus": row["ai_analysis_status"],
            "aiParsedAt": row["ai_parsed_at"],
        },
        "customerAiInsight": {
            "customerId": row["customer_id"],
            "leadTemperature": row["lead_temperature"],
            "temperatureBasis": row["temperature_basis"],
            "priorityScore": row["priority_score"],
            "analyzedAt": row["insight_analyzed_at"],
        },
        "nonConversionReasons": [
            {
                "reasonId": reason["reason_id"],
                "customerId": reason["customer_id"],
                "consultationId": reason["consultation_id"],
                "reasonType": reason["reason_type"],
                "role": reason["role"],
                "reasonBasis": reason["reason_basis"],
                "confidence": reason["confidence"],
            }
            for reason in reasons
        ],
        "followUp": None,
        "followUpAiInsight": None,
    }
    if row["follow_up_id"] is not None:
        payload["followUp"] = {
            "followUpId": row["follow_up_id"],
            "customerId": row["customer_id"],
            "consultationId": row["consultation_id"],
            "recommendContactDate": row["recommend_contact_date"],
            "status": row["follow_up_status"],
            "contactRound": row["contact_round"],
            "hasReply": row["has_reply"],
            "repliedAt": row["replied_at"],
            "snoozedUntil": row["snoozed_until"],
            "memo": row["follow_up_memo"],
        }
        if row["persuasion_point"] is not None or row["action_basis"] is not None:
            payload["followUpAiInsight"] = {
                "followUpId": row["follow_up_id"],
                "persuasionPoint": row["persuasion_point"] or {},
                "cautionNote": row["caution_note"],
                "actionBasis": row["action_basis"] or {},
                "analyzedAt": row["follow_up_ai_analyzed_at"],
            }
    return payload


def _postgres_dsn(database_url: str) -> str:
    if database_url.startswith("jdbc:postgresql://"):
        return "postgresql://" + database_url.removeprefix("jdbc:postgresql://")
    return database_url
