from __future__ import annotations

from datetime import date, datetime, timezone
from uuid import UUID

from fitback_ai.config import RdsSyncSettings
from fitback_ai import rds_sync


def test_postgres_dsn_accepts_jdbc_url():
    assert (
        rds_sync._postgres_dsn("jdbc:postgresql://fitback-db.example.com:5432/fitback")
        == "postgresql://fitback-db.example.com:5432/fitback"
    )


def test_sync_initial_dry_run_reads_without_persisting():
    settings = sync_settings(batch_size=2)
    persist_calls = []

    result = rds_sync.sync_initial(
        settings,
        dry_run=True,
        connect=lambda _: FakeConnection(rows=[consultation_row()]),
        persist=lambda request: persist_calls.append(request) or {},
    )

    assert result.dry_run is True
    assert result.scanned == 1
    assert result.succeeded == 1
    assert result.failed == 0
    assert result.rds_counts["consultation"] == 1
    assert result.rds_counts["eligible_consultation_graph_sync"] == 1
    assert persist_calls == []


def test_sync_initial_continues_after_row_failure():
    settings = sync_settings(batch_size=2)
    rows = [
        consultation_row(consultation_id="77777777-7777-7777-7777-777777777777"),
        consultation_row(consultation_id="88888888-8888-8888-8888-888888888888"),
    ]

    def persist(request):
        if str(request.consultation.consultation_id).startswith("7777"):
            raise RuntimeError("AuraDB unavailable")
        return {"Consultation": 1}

    result = rds_sync.sync_initial(
        settings,
        dry_run=False,
        connect=lambda _: FakeConnection(rows=rows),
        persist=persist,
    )

    assert result.scanned == 2
    assert result.succeeded == 1
    assert result.failed == 1
    assert result.aura_counts == {"Consultation": 1}
    assert "77777777-7777-7777-7777-777777777777" in result.errors[0]


def test_iter_graph_sync_payloads_maps_rds_rows_to_existing_fastapi_contract():
    conn = FakeConnection(rows=[consultation_row()])

    payloads = list(rds_sync.iter_graph_sync_payloads(conn, batch_size=10))

    assert len(payloads) == 1
    payload = payloads[0]
    assert payload["store"]["storeId"] == UUID("11111111-1111-1111-1111-111111111111")
    assert payload["service"]["serviceName"] == "PT"
    assert payload["customer"]["inflowPathName"] == "Naver"
    assert payload["consultation"]["aiAnalysisStatus"] == "COMPLETED"
    assert payload["nonConversionReasons"][0]["reasonType"] == "PRICE"
    assert payload["followUp"]["followUpId"] == UUID("55555555-5555-5555-5555-555555555555")
    assert payload["followUpAiInsight"]["actionBasis"] == {"title": "Budget option"}


def test_verify_sync_compares_rds_and_aura_counts():
    settings = sync_settings()

    result = rds_sync.verify_sync(
        settings,
        connect=lambda _: FakeConnection(rows=[consultation_row()]),
        graph_counts=lambda: {
            "Store": 1,
            "Service": 1,
            "Customer": 1,
            "Consultation": 0,
            "CustomerAiInsight": 1,
            "NonConversionReason": 1,
            "FollowUp": 1,
            "FollowUpAiInsight": 1,
            "ConsultationDuplicateId": 0,
        },
    )

    assert result.comparisons["consultation"] == {
        "rds": 1,
        "aura": 0,
        "missing": 1,
        "duplicate": 0,
    }


class FakeConnection:
    def __init__(self, *, rows):
        self.rows = rows

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def cursor(self):
        return FakeCursor(self)


class FakeCursor:
    def __init__(self, conn):
        self.conn = conn
        self.query = ""
        self.params = ()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, query, params=None):
        self.query = " ".join(query.split())
        self.params = params or ()

    def fetchone(self):
        if "count(DISTINCT st.id)" in self.query:
            count = 1 if self.conn.rows else 0
            return {
                "store": count,
                "service": count,
                "customer": count,
                "consultation": len(self.conn.rows),
                "customer_ai_insight": count,
                "non_conversion_reason": len(self.conn.rows),
                "follow_up": len(self.conn.rows),
                "follow_up_ai_insight": len(self.conn.rows),
            }
        if "eligible_consultation_graph_sync" in self.query:
            return {"count": len(self.conn.rows)}
        if "FROM consultation c JOIN customer" in self.query:
            return {"count": len(self.conn.rows)}
        if "SELECT count(*) AS count FROM" in self.query:
            table = self.query.rsplit(" ", 1)[-1]
            return {"count": table_count(table, self.conn.rows)}
        return {"count": 0}

    def fetchall(self):
        if "information_schema.tables" in self.query:
            return [{"table_name": table} for table in rds_sync.RDS_TABLES]
        if "FROM consultation c JOIN customer" in self.query:
            limit, offset = self.params
            return self.conn.rows[offset : offset + limit]
        if "FROM non_conversion_reason" in self.query:
            consultation_ids = {str(item) for item in self.params[0]}
            return [
                reason_row(consultation_id)
                for consultation_id in consultation_ids
            ]
        return []


def table_count(table: str, rows) -> int:
    if table in {"non_conversion_reason", "follow_up", "follow_up_ai_insight"}:
        return len(rows)
    return 1 if rows else 0


def sync_settings(batch_size=100):
    return RdsSyncSettings(
        database_url="jdbc:postgresql://fitback-db.example.com:5432/fitback",
        username="postgres",
        password="secret",
        batch_size=batch_size,
        include_pii=False,
    )


def consultation_row(consultation_id="77777777-7777-7777-7777-777777777777"):
    return {
        "store_id": UUID("11111111-1111-1111-1111-111111111111"),
        "store_type": "GYM",
        "service_id": UUID("22222222-2222-2222-2222-222222222222"),
        "service_store_id": UUID("11111111-1111-1111-1111-111111111111"),
        "service_name": "PT",
        "service_description": "1:1 training",
        "service_price": 300000,
        "service_active": True,
        "customer_id": UUID("33333333-3333-3333-3333-333333333333"),
        "customer_store_id": UUID("11111111-1111-1111-1111-111111111111"),
        "registered_service_id": None,
        "customer_name": "Hong",
        "customer_gender": "FEMALE",
        "customer_birth_date": date(1995, 1, 1),
        "customer_phone_num": "010-1234-5678",
        "preferred_contact_channel": "KAKAO",
        "customer_status": "PENDING",
        "inflow_path_id": UUID("66666666-6666-6666-6666-666666666666"),
        "inflow_path_name": "Naver",
        "registered_at": None,
        "first_consult_at": date(2026, 7, 1),
        "latest_consult_at": date(2026, 7, 1),
        "consultation_id": UUID(consultation_id),
        "session_no": 1,
        "consulted_at": datetime(2026, 7, 1, 13, 0, tzinfo=timezone.utc),
        "consultation_stage": "CONSULTATION",
        "source_type": "INQUIRY",
        "raw_text": "price concern",
        "summary": "Customer has price concern.",
        "ai_analysis_status": "COMPLETED",
        "ai_parsed_at": datetime(2026, 7, 1, 13, 1, tzinfo=timezone.utc),
        "lead_temperature": "WARM",
        "temperature_basis": "Interested but worried about price.",
        "priority_score": 78,
        "insight_analyzed_at": datetime(2026, 7, 1, 13, 1, tzinfo=timezone.utc),
        "follow_up_id": UUID("55555555-5555-5555-5555-555555555555"),
        "recommend_contact_date": date(2026, 7, 3),
        "follow_up_status": "PENDING",
        "contact_round": 1,
        "has_reply": False,
        "replied_at": None,
        "snoozed_until": None,
        "follow_up_memo": "Send budget option.",
        "persuasion_point": {"main": "Lower initial cost."},
        "caution_note": "Avoid pressure.",
        "action_basis": {"title": "Budget option"},
        "follow_up_ai_analyzed_at": datetime(2026, 7, 1, 13, 1, tzinfo=timezone.utc),
    }


def reason_row(consultation_id):
    return {
        "reason_id": UUID("44444444-4444-4444-4444-444444444444"),
        "customer_id": UUID("33333333-3333-3333-3333-333333333333"),
        "consultation_id": UUID(consultation_id),
        "reason_type": "PRICE",
        "role": "PRIMARY",
        "reason_basis": "Budget concern.",
        "confidence": "HIGH",
    }
