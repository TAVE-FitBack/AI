from __future__ import annotations

from .ai_provider import get_ai_provider
from .api_models import (
    ConsultationAnalyzeRequest,
    ConsultationAnalyzeResponse,
    ConsultationPreviewRequest,
    InquiryPreviewRequest,
    MessageGenerateRequest,
    MessageGenerateResponse,
    NextActionRequest,
    NextActionResponse,
    PreviewResponse,
)


def check_inquiry_preview(request: InquiryPreviewRequest) -> PreviewResponse:
    return get_ai_provider().check_inquiry_preview(request)


def check_consultation_preview(request: ConsultationPreviewRequest) -> PreviewResponse:
    return get_ai_provider().check_consultation_preview(request)


def analyze_consultation(request: ConsultationAnalyzeRequest) -> ConsultationAnalyzeResponse:
    return get_ai_provider().analyze_consultation(request)


def recommend_next_action(request: NextActionRequest) -> NextActionResponse:
    return get_ai_provider().recommend_next_action(request)


def generate_message(request: MessageGenerateRequest) -> MessageGenerateResponse:
    return get_ai_provider().generate_message(request)
