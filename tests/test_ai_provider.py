from __future__ import annotations

import json
from types import SimpleNamespace

from fitback_ai.ai_provider import OpenAiProvider
from fitback_ai.config import AiSettings, load_ai_settings
from tests.test_api import analysis_payload


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
