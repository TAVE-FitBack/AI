from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from fitback_ai.ai_provider import OpenAiProvider
from fitback_ai.config import AiSettings, load_ai_settings
from tests.test_api import analysis_payload, inquiry_preview_payload, message_payload


def test_load_ai_settings_uses_openai_key(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "auto")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.delenv("AI_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_MODEL", "gpt-4.1-mini")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://api.openai.com/v1")

    settings = load_ai_settings()

    assert settings.provider == "openai"
    assert settings.api_key == "test-key"
    assert settings.model == "gpt-4.1-mini"
    assert settings.base_url == "https://api.openai.com/v1"


def test_load_ai_settings_strips_duplicate_env_name(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "auto")
    monkeypatch.setenv("OPENAI_API_KEY", "OPENAI_API_KEY=test-key")
    monkeypatch.delenv("AI_API_KEY", raising=False)

    settings = load_ai_settings()

    assert settings.provider == "openai"
    assert settings.api_key == "test-key"


def test_openai_provider_requests_structured_output():
    response_payload = {
        "summary": "가격 부담이 있는 PT 상담입니다.",
        "customerInsight": {
            "leadTemperature": "WARM",
            "temperatureBasis": "운동 의사는 있으나 가격을 고민하고 있습니다.",
            "priorityScore": 75,
        },
        "nonConversionReasons": [
            {
                "reasonType": "PRICE",
                "role": "PRIMARY",
                "reasonBasis": "가격을 고민 중입니다.",
                "confidence": "HIGH",
            }
        ],
        "nextBestAction": {
            "title": "예산에 맞는 상품 안내",
            "description": "예산별 상품 선택지를 제안합니다.",
        },
        "followUp": {
            "recommendContactDate": "2026-07-12",
            "memo": "카카오톡으로 예산별 상품 안내",
        },
        "followUpInsight": {
            "persuasionPoint": {"keyMessage": "예산에 맞춘 단계별 상품"},
            "cautionNote": "가격을 압박하지 않습니다.",
            "actionBasis": {
                "title": "예산에 맞는 상품 안내",
                "description": "예산별 상품 선택지를 제안합니다.",
            },
        },
    }
    fake_client = FakeOpenAIClient(json.dumps(response_payload, ensure_ascii=False))
    provider = OpenAiProvider(
        AiSettings(
            provider="openai",
            api_key="test-key",
            model="gpt-4.1-mini",
            base_url="https://api.openai.com/v1",
            timeout_seconds=25,
        ),
        client=fake_client,
    )

    result = provider.analyze_consultation(provider_request())

    assert result.summary == response_payload["summary"]
    call = fake_client.calls[0]
    assert call["model"] == "gpt-4.1-mini"
    assert call["response_format"].__name__ == "ConsultationAnalyzeResponse"
    assert "reasonType" in call["messages"][0]["content"]
    assert "PRICE" in call["messages"][0]["content"]


def test_openai_provider_normalizes_legacy_reason_aliases():
    response_payload = {
        "summary": "상담 분석입니다.",
        "customerInsight": {
            "leadTemperature": "WARM",
            "temperatureBasis": "관심이 있습니다.",
            "priorityScore": 75,
        },
        "nonConversionReasons": [
            {
                "reasonType": "PRICE_CONCERN",
                "role": "PRIMARY",
                "reasonBasis": "가격을 고민 중입니다.",
                "confidence": "HIGH",
            }
        ],
        "nextBestAction": {
            "title": "예산 맞춤 상품 안내",
            "description": "예산별 상품 선택지를 제안합니다.",
        },
        "followUp": {
            "recommendContactDate": "2026-07-12",
            "memo": "예산별 상품 안내",
        },
        "followUpInsight": {
            "persuasionPoint": {"keyMessage": "예산에 맞춘 선택지"},
            "cautionNote": "가격 압박을 피합니다.",
            "actionBasis": {
                "title": "예산 맞춤 상품 안내",
                "description": "예산별 상품 선택지를 제안합니다.",
            },
        },
    }
    provider = OpenAiProvider(
        AiSettings(
            provider="openai",
            api_key="test-key",
            model="gpt-4.1-mini",
            base_url="https://api.openai.com/v1",
            timeout_seconds=25,
        ),
        client=FakeOpenAIClient(json.dumps(response_payload, ensure_ascii=False)),
    )

    result = provider.analyze_consultation(provider_request())

    assert result.non_conversion_reasons[0].reason_type == "PRICE"


def test_openai_provider_rejects_unknown_controlled_ontology_fields():
    response_payload = {
        "summary": "상담 분석입니다.",
        "customerInsight": {
            "leadTemperature": "VERY_HOT",
            "temperatureBasis": "관심이 있습니다.",
            "priorityScore": 75,
        },
        "nonConversionReasons": [
            {
                "reasonType": "PRICE",
                "role": "PRIMARY",
                "reasonBasis": "가격을 고민 중입니다.",
                "confidence": "HIGH",
            }
        ],
        "nextBestAction": {
            "title": "예산 맞춤 상품 안내",
            "description": "예산별 상품 선택지를 제안합니다.",
        },
        "followUp": {
            "recommendContactDate": "2026-07-12",
            "memo": "예산별 상품 안내",
        },
        "followUpInsight": {
            "persuasionPoint": {"keyMessage": "예산에 맞춘 선택지"},
            "cautionNote": "가격 압박을 피합니다.",
            "actionBasis": {
                "title": "예산 맞춤 상품 안내",
                "description": "예산별 상품 선택지를 제안합니다.",
            },
        },
    }
    provider = OpenAiProvider(
        AiSettings(
            provider="openai",
            api_key="test-key",
            model="gpt-4.1-mini",
            base_url="https://api.openai.com/v1",
            timeout_seconds=25,
        ),
        client=FakeOpenAIClient(json.dumps(response_payload, ensure_ascii=False)),
    )

    with pytest.raises(RuntimeError):
        provider.analyze_consultation(provider_request())


def test_openai_provider_normalizes_preview_codebook_and_counts():
    response_payload = {
        "confirmedCount": 99,
        "totalCount": 1,
        "items": [
            {
                "key": "CUSTOMER_REQUEST",
                "label": "고객요청사항",
                "confirmed": True,
                "value": "가격 문의",
            },
            {
                "key": "EXERCISE_GOAL",
                "label": "운동목표",
                "confirmed": False,
                "value": "DIET-VALUE",
            },
            {
                "key": "INTEREST_SERVICE",
                "label": "관심서비스",
                "confirmed": True,
                "value": "퍼스널 트레이닝",
            },
        ],
    }
    provider = OpenAiProvider(
        AiSettings(
            provider="openai",
            api_key="test-key",
            model="gpt-4.1-mini",
            base_url="https://api.openai.com/v1",
            timeout_seconds=25,
        ),
        client=FakeOpenAIClient(json.dumps(response_payload, ensure_ascii=False)),
    )

    from fitback_ai.api_models import InquiryPreviewRequest

    result = provider.check_inquiry_preview(InquiryPreviewRequest.model_validate(inquiry_preview_payload()))

    assert result.confirmed_count == 2
    assert result.total_count == 7
    assert [item.key for item in result.items] == [
        "INTEREST_SERVICE",
        "EXERCISE_GOAL",
        "EXERCISE_EXPERIENCE",
        "INJURY_HISTORY",
        "CUSTOMER_REQUEST",
        "COUNSELOR_RESPONSE",
        "SPECIAL_NOTE",
    ]
    assert [item.label for item in result.items] == [
        "관심 상품",
        "운동 목적",
        "운동 경험",
        "부상 이력",
        "고객 요청",
        "나의 응대",
        "특이사항",
    ]
    assert result.items[1].confirmed is False
    assert result.items[1].value == "아직 확인되지 않음"


def test_openai_provider_overwrites_message_enums_with_request_values():
    response_payload = {
        "content": "고객님께 보낼 메시지입니다.",
        "versionType": "SHORT",
        "tonePreset": "PROFESSIONAL",
    }
    provider = OpenAiProvider(
        AiSettings(
            provider="openai",
            api_key="test-key",
            model="gpt-4.1-mini",
            base_url="https://api.openai.com/v1",
            timeout_seconds=25,
        ),
        client=FakeOpenAIClient(json.dumps(response_payload, ensure_ascii=False)),
    )

    from fitback_ai.api_models import MessageGenerateRequest

    request = MessageGenerateRequest.model_validate(message_payload())
    result = provider.generate_message(request)

    assert result.version_type == request.message_options.version_type
    assert result.tone_preset == request.message_options.tone_preset


def provider_request():
    from fitback_ai.api_models import ConsultationAnalyzeRequest

    return ConsultationAnalyzeRequest.model_validate(analysis_payload())


class FakeOpenAIClient:
    def __init__(self, content: str) -> None:
        self.calls = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(parse=self.parse))
        self.content = content

    def parse(self, **kwargs):
        self.calls.append(kwargs)
        response_format = kwargs["response_format"]
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content=self.content,
                        parsed=response_format.model_validate_json(self.content),
                    ),
                )
            ]
        )
