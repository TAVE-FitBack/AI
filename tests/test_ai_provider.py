from __future__ import annotations

import json
from types import SimpleNamespace

from fitback_ai.ai_provider import XaiGrokProvider
from fitback_ai.config import AiSettings, load_ai_settings
from tests.test_api import analysis_payload


def test_load_ai_settings_uses_xai_key_alias(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "auto")
    monkeypatch.setenv("XAI_API_KEY", "test-key")
    monkeypatch.delenv("AI_API_KEY", raising=False)
    monkeypatch.setenv("XAI_MODEL", "grok-4.5")
    monkeypatch.setenv("XAI_BASE_URL", "https://api.x.ai/v1")

    settings = load_ai_settings()

    assert settings.provider == "xai"
    assert settings.xai_api_key == "test-key"
    assert settings.xai_model == "grok-4.5"
    assert settings.xai_base_url == "https://api.x.ai/v1"


def test_xai_provider_requests_structured_output():
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
    provider = XaiGrokProvider(
        AiSettings(
            provider="xai",
            xai_api_key="test-key",
            xai_model="grok-4.5",
            xai_base_url="https://api.x.ai/v1",
            timeout_seconds=25,
        ),
        client=fake_client,
    )

    result = provider.analyze_consultation(provider_request())

    assert result.summary == response_payload["summary"]
    call = fake_client.calls[0]
    assert call["model"] == "grok-4.5"
    assert call["response_format"]["type"] == "json_schema"
    assert call["response_format"]["json_schema"]["strict"] is True
    assert call["response_format"]["json_schema"]["schema"]["properties"]["summary"]


def provider_request():
    from fitback_ai.api_models import ConsultationAnalyzeRequest

    return ConsultationAnalyzeRequest.model_validate(analysis_payload())


class FakeOpenAIClient:
    def __init__(self, content: str) -> None:
        self.calls = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))
        self.content = content

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content=self.content),
                )
            ]
        )
