from __future__ import annotations

from fastapi.testclient import TestClient
import pytest

import fitback_ai.api as api_module
from fitback_ai.api import app


client = TestClient(app)

PREVIEW_KEYS = [
    "INTEREST_SERVICE",
    "EXERCISE_GOAL",
    "EXERCISE_EXPERIENCE",
    "INJURY_HISTORY",
    "CUSTOMER_REQUEST",
    "COUNSELOR_RESPONSE",
    "SPECIAL_NOTE",
]
PREVIEW_LABELS = [
    "관심 상품",
    "운동 목적",
    "운동 경험",
    "부상 이력",
    "고객 요청",
    "나의 응대",
    "특이사항",
]


@pytest.fixture(autouse=True)
def use_heuristic_ai_provider(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "heuristic")
    monkeypatch.setenv("GRAPH_PERSISTENCE_ENABLED", "false")


def test_openapi_exposes_required_paths():
    schema = client.get("/openapi.json").json()

    for path in [
        "/ai/v1/inquiries/check-preview",
        "/ai/v1/consultations/check-preview",
        "/ai/v1/consultations/analyze",
        "/ai/v1/graph/consultations/sync",
        "/ai/v1/consultations/next-action",
        "/ai/v1/messages/generate",
    ]:
        assert "post" in schema["paths"][path]


def test_docs_endpoint_is_available():
    response = client.get("/docs")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_inquiry_preview_accepts_camel_case_and_returns_json_object():
    response = client.post(
        "/ai/v1/inquiries/check-preview",
        json={
            "rawText": "가격과 주 3회 PT 가능 여부를 문의했습니다.",
            "serviceName": "퍼스널 트레이닝",
            "inquiryStatus": "RECEIVED",
            "customerInfo": {
                "name": "홍길동",
                "gender": "MALE",
                "birthDate": "1995-04-12",
            },
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["totalCount"] == 7
    assert [item["key"] for item in body["items"]] == PREVIEW_KEYS
    assert [item["label"] for item in body["items"]] == PREVIEW_LABELS
    assert body["confirmedCount"] == sum(1 for item in body["items"] if item["confirmed"])
    assert body["items"][0]["value"] == "퍼스널 트레이닝"
    assert "raw_text" not in body
    assert "isValid" not in body


def test_consultation_preview_accepts_camel_case_and_returns_json_object():
    response = client.post(
        "/ai/v1/consultations/check-preview",
        json={
            "rawText": "체중 감량을 목표로 평일 저녁 운동 가능 여부를 상담했습니다.",
            "serviceName": "퍼스널 트레이닝",
            "customerInfo": {
                "name": "홍길동",
                "gender": "MALE",
                "birthDate": "1995-04-12",
            },
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["totalCount"] == 7
    assert [item["key"] for item in body["items"]] == PREVIEW_KEYS
    assert [item["label"] for item in body["items"]] == PREVIEW_LABELS
    assert body["confirmedCount"] == sum(1 for item in body["items"] if item["confirmed"])


def test_consultation_analyze_returns_required_fields():
    response = client.post("/ai/v1/consultations/analyze", json=analysis_payload())

    assert response.status_code == 200
    body = response.json()
    assert body["summary"].strip()
    assert body["customerInsight"]["leadTemperature"].strip()
    assert body["customerInsight"]["leadTemperature"] in {"HOT", "WARM", "COLD"}
    assert body["nonConversionReasons"][0]["reasonType"] in {
        "PRICE",
        "SCHEDULE",
        "FAMILY_DISCUSSION",
        "NO_RESPONSE",
        "COMPARING_OPTIONS",
        "NEEDS_FOLLOW_UP",
    }
    assert body["nextBestAction"]["title"].strip()
    assert body["nextBestAction"]["description"].strip()
    assert body["followUp"]["recommendContactDate"]
    assert isinstance(body["nonConversionReasons"], list)
    assert body["followUpInsight"]["actionBasis"]["title"] == body["nextBestAction"]["title"]


def test_consultation_analyze_rejects_bad_datetime():
    payload = analysis_payload()
    payload["consultation"]["consultedAt"] = "2026-07-09 14:30:00"

    response = client.post("/ai/v1/consultations/analyze", json=payload)

    assert response.status_code == 422


def test_consultation_graph_sync_returns_noop_when_persistence_disabled():
    response = client.post("/ai/v1/graph/consultations/sync", json=graph_sync_payload())

    assert response.status_code == 200
    assert response.json() == {"persisted": False, "counts": None}


def test_consultation_graph_sync_rejects_mismatched_rds_references():
    payload = graph_sync_payload()
    payload["consultation"]["customerId"] = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"

    response = client.post("/ai/v1/graph/consultations/sync", json=payload)

    assert response.status_code == 422


def test_next_action_returns_required_contract():
    response = client.post(
        "/ai/v1/consultations/next-action",
        json={
            "customer": {
                "customerId": "6c2d9b87-90aa-4ce2-96cb-a0875f103f04",
                "status": "PENDING",
            },
            "latestConsultation": {
                "consultationId": "6570aa21-d458-4885-9e69-d984fea51830",
                "summary": "가격 부담으로 보류",
                "rawText": "가격이 부담되어 고민 중입니다.",
            },
            "aiAnalysis": {
                "leadTemperature": "WARM",
                "temperatureBasis": "운동 의사는 명확하지만 가격 고민이 있습니다.",
                "nonConversionReasons": [
                    {
                        "reasonType": "PRICE",
                        "role": "PRIMARY",
                        "reasonBasis": "가격 부담",
                    }
                ],
            },
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert isinstance(body["priorityScore"], int)
    assert body["priorityScore"] == 80
    assert body["nextBestAction"]["title"].strip()
    assert body["followUp"]["recommendContactDate"]


def test_message_generate_returns_requested_enums():
    response = client.post(
        "/ai/v1/messages/generate",
        json={
            "customer": {
                "customerId": "6c2d9b87-90aa-4ce2-96cb-a0875f103f04",
                "name": "홍길동",
                "preferredContactChannel": "KAKAO",
                "status": "PENDING",
            },
            "latestConsultation": {
                "consultationId": "6570aa21-d458-4885-9e69-d984fea51830",
                "summary": "가격 부담으로 보류",
            },
            "aiInsight": {"leadTemperature": "WARM", "priorityScore": 75},
            "nonConversionReasons": [
                {
                    "reasonType": "PRICE",
                    "role": "PRIMARY",
                    "reasonBasis": "가격 부담",
                }
            ],
            "nextBestAction": {
                "title": "예산에 맞는 상품 안내",
                "description": "예산별 상품을 제안합니다.",
                "persuasionPoint": {"keyMessage": "목표에 맞춘 단계별 상품"},
                "cautionNote": "가격 압박은 피합니다.",
                "actionBasis": {
                    "title": "예산에 맞는 상품 안내",
                    "description": "가격 이슈",
                },
            },
            "event": None,
            "messageOptions": {
                "tonePreset": "FRIENDLY",
                "versionType": "STANDARD",
                "additionalInstruction": "첫 문장에 고객 이름을 넣어 주세요.",
            },
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["content"].strip()
    assert body["versionType"] == "STANDARD"
    assert body["tonePreset"] == "FRIENDLY"


def test_all_endpoints_return_422_for_invalid_payloads():
    cases = [
        (
            "/ai/v1/inquiries/check-preview",
            {
                **inquiry_preview_payload(),
                "inquiryStatus": "INVALID",
            },
        ),
        (
            "/ai/v1/consultations/check-preview",
            {
                **consultation_preview_payload(),
                "customerInfo": {
                    "name": "홍길동",
                    "gender": "UNKNOWN",
                    "birthDate": "1995-04-12",
                },
            },
        ),
        (
            "/ai/v1/consultations/analyze",
            {
                **analysis_payload(),
                "attachedMaterials": None,
            },
        ),
        (
            "/ai/v1/consultations/next-action",
            {
                **next_action_payload(),
                "customer": {
                    "customerId": "not-a-uuid",
                    "status": "PENDING",
                },
            },
        ),
        (
            "/ai/v1/graph/consultations/sync",
            {
                **graph_sync_payload(),
                "followUp": {
                    **graph_sync_payload()["followUp"],
                    "contactRound": 4,
                },
            },
        ),
        (
            "/ai/v1/messages/generate",
            {
                **message_payload(),
                "messageOptions": {
                    "tonePreset": "LOUD",
                    "versionType": "STANDARD",
                },
            },
        ),
    ]

    for path, payload in cases:
        response = client.post(path, json=payload)
        assert response.status_code == 422, path


def test_all_endpoints_return_processing_error_for_runtime_failures(monkeypatch):
    def fail(_):
        raise RuntimeError("AI processing failed")

    cases = [
        ("/ai/v1/inquiries/check-preview", "check_inquiry_preview", inquiry_preview_payload()),
        ("/ai/v1/consultations/check-preview", "check_consultation_preview", consultation_preview_payload()),
        ("/ai/v1/consultations/analyze", "analyze_consultation", analysis_payload()),
        ("/ai/v1/graph/consultations/sync", "sync_consultation_graph", graph_sync_payload()),
        ("/ai/v1/consultations/next-action", "recommend_next_action", next_action_payload()),
        ("/ai/v1/messages/generate", "generate_message", message_payload()),
    ]

    for path, function_name, payload in cases:
        monkeypatch.setattr(api_module, function_name, fail)
        response = client.post(path, json=payload)
        assert response.status_code == 500, path
        assert response.json() == {
            "detail": "AI processing failed",
            "code": "AI_PROCESSING_FAILED",
        }


def inquiry_preview_payload():
    return {
        "rawText": "가격과 주 3회 PT 가능 여부를 문의했습니다.",
        "serviceName": "퍼스널 트레이닝",
        "inquiryStatus": "RECEIVED",
        "customerInfo": {
            "name": "홍길동",
            "gender": "MALE",
            "birthDate": "1995-04-12",
        },
    }


def consultation_preview_payload():
    return {
        "rawText": "체중 감량을 목표로 평일 저녁 운동 가능 여부를 상담했습니다.",
        "serviceName": "퍼스널 트레이닝",
        "customerInfo": {
            "name": "홍길동",
            "gender": "MALE",
            "birthDate": "1995-04-12",
        },
    }


def next_action_payload():
    return {
        "customer": {
            "customerId": "6c2d9b87-90aa-4ce2-96cb-a0875f103f04",
            "status": "PENDING",
        },
        "latestConsultation": {
            "consultationId": "6570aa21-d458-4885-9e69-d984fea51830",
            "summary": "가격 부담으로 보류",
            "rawText": "가격이 부담되어 고민 중입니다.",
        },
        "aiAnalysis": {
            "leadTemperature": "WARM",
            "temperatureBasis": "운동 의사는 명확하지만 가격 고민이 있습니다.",
            "nonConversionReasons": [
                {
                    "reasonType": "PRICE",
                    "role": "PRIMARY",
                    "reasonBasis": "가격 부담",
                }
            ],
        },
    }


def message_payload():
    return {
        "customer": {
            "customerId": "6c2d9b87-90aa-4ce2-96cb-a0875f103f04",
            "name": "홍길동",
            "preferredContactChannel": "KAKAO",
            "status": "PENDING",
        },
        "latestConsultation": {
            "consultationId": "6570aa21-d458-4885-9e69-d984fea51830",
            "summary": "가격 부담으로 보류",
        },
        "aiInsight": {"leadTemperature": "WARM", "priorityScore": 75},
        "nonConversionReasons": [
            {
                "reasonType": "PRICE",
                "role": "PRIMARY",
                "reasonBasis": "가격 부담",
            }
        ],
        "nextBestAction": {
            "title": "예산에 맞는 상품 안내",
            "description": "예산별 상품을 제안합니다.",
            "persuasionPoint": {"keyMessage": "목표에 맞춘 단계별 상품"},
            "cautionNote": "가격 압박은 피합니다.",
            "actionBasis": {
                "title": "예산에 맞는 상품 안내",
                "description": "가격 이슈",
            },
        },
        "event": None,
        "messageOptions": {
            "tonePreset": "FRIENDLY",
            "versionType": "STANDARD",
            "additionalInstruction": "첫 문장에 고객 이름을 넣어 주세요.",
        },
    }


def analysis_payload():
    return {
        "customer": {
            "customerId": "6c2d9b87-90aa-4ce2-96cb-a0875f103f04",
            "name": "홍길동",
            "gender": "MALE",
            "birthDate": "1995-04-12",
            "phoneNum": "010-1234-5678",
            "preferredContactChannel": "KAKAO",
            "status": "PENDING",
            "inflowPathId": "71564cdc-6ad1-4978-a74e-150c576ce13c",
            "inflowPathName": "인스타그램",
        },
        "consultation": {
            "consultationId": "6570aa21-d458-4885-9e69-d984fea51830",
            "sessionNo": 1,
            "consultedAt": "2026-07-09T14:30:00+09:00",
            "consultedServiceId": "88d53bb7-7210-4e77-a0c4-01778a54d68d",
            "stage": "CONSULTATION",
            "sourceType": "DIRECT",
            "rawText": "체중 감량이 목표이고 가격을 고민 중입니다.",
        },
        "service": {
            "serviceId": "88d53bb7-7210-4e77-a0c4-01778a54d68d",
            "serviceName": "퍼스널 트레이닝",
            "description": "주 3회 1:1 트레이닝",
            "price": 600000,
        },
        "storeContext": {
            "storeId": "28f43532-f2fc-4581-827e-880d06f3cd88",
            "storeType": "GYM",
            "registrationStatus": "PENDING",
        },
        "attachedMaterials": [
            {
                "materialType": "OTHER",
                "title": "kakao-chat",
                "content": "고객: PT 가격 문의드립니다.\n상담사: 현재 6개월권 이벤트가 있습니다.",
            }
        ],
    }


def graph_sync_payload():
    return {
        "store": {
            "storeId": "28f43532-f2fc-4581-827e-880d06f3cd88",
            "storeType": "GYM",
        },
        "service": {
            "serviceId": "88d53bb7-7210-4e77-a0c4-01778a54d68d",
            "storeId": "28f43532-f2fc-4581-827e-880d06f3cd88",
            "serviceName": "PT",
            "description": "1:1 training",
            "price": 600000,
            "active": True,
        },
        "customer": {
            "customerId": "6c2d9b87-90aa-4ce2-96cb-a0875f103f04",
            "storeId": "28f43532-f2fc-4581-827e-880d06f3cd88",
            "registeredServiceId": None,
            "name": "Hong",
            "gender": "MALE",
            "birthDate": "1995-04-12",
            "phoneNum": "010-1234-5678",
            "preferredContactChannel": "KAKAO",
            "status": "PENDING",
            "inflowPathId": "71564cdc-6ad1-4978-a74e-150c576ce13c",
            "inflowPathName": "Instagram",
            "registeredAt": None,
            "firstConsultAt": "2026-07-09",
            "latestConsultAt": "2026-07-09",
        },
        "consultation": {
            "consultationId": "6570aa21-d458-4885-9e69-d984fea51830",
            "customerId": "6c2d9b87-90aa-4ce2-96cb-a0875f103f04",
            "consultedServiceId": "88d53bb7-7210-4e77-a0c4-01778a54d68d",
            "sessionNo": 1,
            "consultedAt": "2026-07-09T14:30:00+09:00",
            "stage": "CONSULTATION",
            "sourceType": "DIRECT",
            "rawText": "price concern",
            "summary": "Customer has price concern.",
            "aiAnalysisStatus": "COMPLETED",
            "aiParsedAt": "2026-07-09T14:31:00+09:00",
        },
        "customerAiInsight": {
            "customerId": "6c2d9b87-90aa-4ce2-96cb-a0875f103f04",
            "leadTemperature": "WARM",
            "temperatureBasis": "Interested but worried about price.",
            "priorityScore": 78,
            "analyzedAt": "2026-07-09T14:31:00+09:00",
        },
        "nonConversionReasons": [
            {
                "reasonId": "f5ceceea-4fa4-4317-bf68-6752af1cc0bd",
                "customerId": "6c2d9b87-90aa-4ce2-96cb-a0875f103f04",
                "consultationId": "6570aa21-d458-4885-9e69-d984fea51830",
                "reasonType": "PRICE",
                "role": "PRIMARY",
                "reasonBasis": "Budget concern.",
                "confidence": "HIGH",
            }
        ],
        "followUp": {
            "followUpId": "7e08bfd1-247d-4ca2-8038-5185945b7c37",
            "customerId": "6c2d9b87-90aa-4ce2-96cb-a0875f103f04",
            "consultationId": "6570aa21-d458-4885-9e69-d984fea51830",
            "recommendContactDate": "2026-07-11",
            "status": "PENDING",
            "contactRound": 1,
            "hasReply": False,
            "repliedAt": None,
            "snoozedUntil": None,
            "memo": "Send budget option.",
        },
        "followUpAiInsight": {
            "followUpId": "7e08bfd1-247d-4ca2-8038-5185945b7c37",
            "persuasionPoint": {"main": "Lower initial cost."},
            "cautionNote": "Avoid pressure.",
            "actionBasis": {"title": "Budget option", "description": "Offer starter plan."},
            "analyzedAt": "2026-07-09T14:31:00+09:00",
        },
    }
