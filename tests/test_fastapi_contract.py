from __future__ import annotations

from collections.abc import Mapping

import pytest
from fastapi.testclient import TestClient

import fitback_ai.api as api_module
from fitback_ai.api import app


client = TestClient(app)

REQUIRED_POST_PATHS = [
    "/ai/v1/inquiries/check-preview",
    "/ai/v1/consultations/check-preview",
    "/ai/v1/consultations/analyze",
    "/ai/v1/graph/consultations/sync",
    "/ai/v1/consultations/next-action",
    "/ai/v1/messages/generate",
]

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


def test_openapi_contract_exposes_only_documented_post_operations():
    schema = client.get("/openapi.json").json()
    ai_paths = {path for path in schema["paths"] if path.startswith("/ai/v1/")}

    assert ai_paths == set(REQUIRED_POST_PATHS)

    for path in REQUIRED_POST_PATHS:
        assert path in schema["paths"]
        assert set(schema["paths"][path]) == {"post"}


def test_success_responses_are_json_objects_with_application_json():
    cases = [
        ("/ai/v1/inquiries/check-preview", inquiry_preview_payload()),
        ("/ai/v1/consultations/check-preview", consultation_preview_payload()),
        ("/ai/v1/consultations/analyze", analysis_payload()),
        ("/ai/v1/graph/consultations/sync", graph_sync_payload()),
        ("/ai/v1/consultations/next-action", next_action_payload()),
        ("/ai/v1/messages/generate", message_payload()),
    ]

    for path, payload in cases:
        response = client.post(path, json=payload)

        assert response.status_code == 200, path
        assert response.headers["content-type"].startswith("application/json"), path
        assert isinstance(response.json(), dict), path


def test_success_responses_use_camel_case_not_snake_case():
    cases = [
        ("/ai/v1/inquiries/check-preview", inquiry_preview_payload()),
        ("/ai/v1/consultations/analyze", analysis_payload()),
        ("/ai/v1/consultations/next-action", next_action_payload()),
        ("/ai/v1/messages/generate", message_payload()),
    ]

    for path, payload in cases:
        body = client.post(path, json=payload).json()

        assert_no_snake_case_keys(body)


def test_preview_success_responses_use_documented_fixed_items():
    cases = [
        ("/ai/v1/inquiries/check-preview", inquiry_preview_payload()),
        ("/ai/v1/consultations/check-preview", consultation_preview_payload()),
    ]

    for path, payload in cases:
        response = client.post(path, json=payload)

        assert response.status_code == 200, path
        body = response.json()
        assert set(body) == {"confirmedCount", "totalCount", "items"}
        assert body["totalCount"] == 7
        assert [item["key"] for item in body["items"]] == PREVIEW_KEYS
        assert [item["label"] for item in body["items"]] == PREVIEW_LABELS
        assert body["confirmedCount"] == sum(1 for item in body["items"] if item["confirmed"])
        assert all(isinstance(item["confirmed"], bool) for item in body["items"])
        assert all(item["label"].strip() for item in body["items"])
        assert all(item["value"].strip() for item in body["items"])


def test_analysis_accepts_documented_nullable_request_fields():
    payload = analysis_payload()
    payload["consultation"]["stage"] = None
    payload["service"]["description"] = None
    payload["service"]["price"] = None
    payload["attachedMaterials"] = []

    response = client.post("/ai/v1/consultations/analyze", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["summary"].strip()
    assert body["followUp"]["recommendContactDate"]


def test_message_generation_accepts_documented_nullable_and_empty_values():
    payload = message_payload()
    payload["aiInsight"]["leadTemperature"] = None
    payload["aiInsight"]["priorityScore"] = None
    payload["nonConversionReasons"] = []
    payload["event"] = {
        "eventId": "7f3e50a8-3b22-4616-9663-0aa00e828f04",
        "title": "여름 PT 할인",
        "description": None,
        "discountRate": None,
    }
    payload["messageOptions"]["additionalInstruction"] = None
    payload["nextBestAction"]["persuasionPoint"] = None
    payload["nextBestAction"]["cautionNote"] = None
    payload["nextBestAction"]["actionBasis"] = None

    response = client.post("/ai/v1/messages/generate", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["content"].strip()
    assert body["versionType"] == payload["messageOptions"]["versionType"]
    assert body["tonePreset"] == payload["messageOptions"]["tonePreset"]


def test_analysis_success_response_contains_required_non_blank_fields():
    response = client.post("/ai/v1/consultations/analyze", json=analysis_payload())

    assert response.status_code == 200
    body = response.json()
    assert body["summary"].strip()
    assert body["customerInsight"]["leadTemperature"].strip()
    assert isinstance(body["customerInsight"]["priorityScore"], int)
    assert body["nextBestAction"]["title"].strip()
    assert body["nextBestAction"]["description"].strip()
    assert body["followUp"]["recommendContactDate"]
    assert isinstance(body["nonConversionReasons"], list)
    assert body["nonConversionReasons"] is not None


def test_analysis_requires_attached_materials_field_even_when_empty():
    payload = analysis_payload()
    payload.pop("attachedMaterials")

    response = client.post("/ai/v1/consultations/analyze", json=payload)

    assert response.status_code == 422


def test_next_action_success_response_contains_required_non_null_fields():
    response = client.post("/ai/v1/consultations/next-action", json=next_action_payload())

    assert response.status_code == 200
    body = response.json()
    assert isinstance(body["priorityScore"], int)
    assert body["nextBestAction"]["title"].strip()
    assert body["nextBestAction"]["description"].strip()
    assert body["followUp"]["recommendContactDate"]


def test_invalid_date_datetime_and_enum_values_return_422():
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
                    **consultation_preview_payload()["customerInfo"],
                    "birthDate": "04-12-1995",
                },
            },
        ),
        (
            "/ai/v1/consultations/analyze",
            {
                **analysis_payload(),
                "consultation": {
                    **analysis_payload()["consultation"],
                    "consultedAt": "2026-07-09T14:30:00",
                },
            },
        ),
        (
            "/ai/v1/consultations/next-action",
            {
                **next_action_payload(),
                "customer": {
                    **next_action_payload()["customer"],
                    "customerId": "not-a-uuid",
                },
            },
        ),
        (
            "/ai/v1/messages/generate",
            {
                **message_payload(),
                "messageOptions": {
                    **message_payload()["messageOptions"],
                    "tonePreset": "friendly",
                },
            },
        ),
    ]

    for path, payload in cases:
        response = client.post(path, json=payload)

        assert response.status_code == 422, path


def test_each_endpoint_runtime_failure_returns_documented_processing_error(monkeypatch):
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


def assert_no_snake_case_keys(value):
    if isinstance(value, Mapping):
        for key, child in value.items():
            assert "_" not in key, key
            assert_no_snake_case_keys(child)
    elif isinstance(value, list):
        for child in value:
            assert_no_snake_case_keys(child)


def inquiry_preview_payload():
    return {
        "rawText": "가격과 주 3회 PT 가능 여부를 문의함",
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
        "rawText": "체중 감량이 목표이며 평일 저녁 운동을 희망함",
        "serviceName": "퍼스널 트레이닝",
        "customerInfo": {
            "name": "홍길동",
            "gender": "MALE",
            "birthDate": "1995-04-12",
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
            "rawText": "체중 감량이 목표이고 가격을 고민 중임",
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


def next_action_payload():
    return {
        "customer": {
            "customerId": "6c2d9b87-90aa-4ce2-96cb-a0875f103f04",
            "status": "PENDING",
        },
        "latestConsultation": {
            "consultationId": "6570aa21-d458-4885-9e69-d984fea51830",
            "summary": "가격 부담으로 결정을 보류함",
            "rawText": "운동은 시작하고 싶지만 가격이 부담됨",
        },
        "aiAnalysis": {
            "leadTemperature": "WARM",
            "temperatureBasis": "운동 의사는 명확하지만 가격을 고민함",
            "nonConversionReasons": [
                {
                    "reasonType": "PRICE",
                    "role": "PRIMARY",
                    "reasonBasis": "가격 부담을 직접 언급함",
                }
            ],
        },
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
        "followUp": None,
        "followUpAiInsight": None,
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
            "summary": "가격 부담으로 결정을 보류함",
        },
        "aiInsight": {
            "leadTemperature": "WARM",
            "priorityScore": 75,
        },
        "nonConversionReasons": [
            {
                "reasonType": "PRICE",
                "role": "PRIMARY",
                "reasonBasis": "가격 부담을 직접 언급함",
            }
        ],
        "nextBestAction": {
            "title": "할인 가능한 상품 안내",
            "description": "예산에 맞는 상품을 제안한다.",
            "persuasionPoint": {
                "keyMessage": "목표에 맞춘 단계별 상품",
            },
            "cautionNote": "가격 압박을 피할 것",
            "actionBasis": {
                "title": "할인 가능한 상품 안내",
                "description": "가격이 핵심 미전환 사유임",
            },
        },
        "event": {
            "eventId": "7f3e50a8-3b22-4616-9663-0aa00e828f04",
            "title": "여름 PT 할인",
            "description": "PT 20회 등록 시 할인",
            "discountRate": 10.0,
        },
        "messageOptions": {
            "tonePreset": "FRIENDLY",
            "versionType": "STANDARD",
            "additionalInstruction": "첫 문장에 고객 이름을 넣어 주세요.",
        },
    }
