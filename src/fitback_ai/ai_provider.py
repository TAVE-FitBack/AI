from __future__ import annotations

import json
from datetime import date, timedelta
from typing import TypeVar
from uuid import UUID

from openai import OpenAI, OpenAIError
from pydantic import BaseModel

from .api_models import (
    ConsultationAnalyzeRequest,
    ConsultationAnalyzeResponse,
    ConsultationPreviewRequest,
    CustomerInsight,
    FollowUp,
    FollowUpInsight,
    InquiryPreviewRequest,
    MessageGenerateRequest,
    MessageGenerateResponse,
    NextActionRequest,
    NextActionResponse,
    NextBestAction,
    NonConversionReason,
    PersuasionPoint,
    PreviewResponse,
)
from .config import AiSettings, load_ai_settings
from .ontology import (
    action_for_reason,
    classify_reason,
    normalize_confidence,
    normalize_reason_code,
    normalize_temperature_code,
    ontology_prompt_context,
    priority_for_reason,
    temperature_for_status,
)

ResponseModel = TypeVar("ResponseModel", bound=BaseModel)


class AiProvider:
    def check_inquiry_preview(self, request: InquiryPreviewRequest) -> PreviewResponse:
        raise NotImplementedError

    def check_consultation_preview(self, request: ConsultationPreviewRequest) -> PreviewResponse:
        raise NotImplementedError

    def analyze_consultation(self, request: ConsultationAnalyzeRequest) -> ConsultationAnalyzeResponse:
        raise NotImplementedError

    def recommend_next_action(self, request: NextActionRequest) -> NextActionResponse:
        raise NotImplementedError

    def generate_message(self, request: MessageGenerateRequest) -> MessageGenerateResponse:
        raise NotImplementedError


class HeuristicAiProvider(AiProvider):
    def check_inquiry_preview(self, request: InquiryPreviewRequest) -> PreviewResponse:
        return _preview_response(request.raw_text, request.service_name)

    def check_consultation_preview(self, request: ConsultationPreviewRequest) -> PreviewResponse:
        return _preview_response(request.raw_text, request.service_name)

    def analyze_consultation(self, request: ConsultationAnalyzeRequest) -> ConsultationAnalyzeResponse:
        reason = classify_reason(request.consultation.raw_text)
        action = _action_for_reason(reason, request.service.service_name)
        contact_date = request.consultation.consulted_at.date() + timedelta(days=3)
        insight = CustomerInsight(
            lead_temperature=temperature_for_status(str(request.store_context.registration_status), reason),
            temperature_basis=f"{request.service.service_name} 상담 내용과 {reason} 신호를 함께 고려했습니다.",
            priority_score=priority_for_reason(reason),
        )
        non_conversion_reasons = [
            NonConversionReason(
                reason_type=reason,
                role="PRIMARY",
                reason_basis=request.consultation.raw_text,
                confidence="HIGH",
            )
        ]
        follow_up = FollowUp(
            recommend_contact_date=contact_date,
            memo=f"{request.customer.preferred_contact_channel}로 {action.title} 내용을 안내",
        )
        return ConsultationAnalyzeResponse(
            summary=f"{request.customer.name} 고객은 {request.service.service_name} 상담에서 {reason} 관련 보류 신호를 보였습니다.",
            customer_insight=insight,
            non_conversion_reasons=non_conversion_reasons,
            next_best_action=action,
            follow_up=follow_up,
            follow_up_insight=_follow_up_insight(action, reason),
        )

    def recommend_next_action(self, request: NextActionRequest) -> NextActionResponse:
        reason = _first_reason_type(request.ai_analysis.non_conversion_reasons)
        action = _action_for_reason(reason, "상담 상품")
        base_date = _date_from_uuid(request.latest_consultation.consultation_id)
        return NextActionResponse(
            priority_score=priority_for_reason(reason),
            next_best_action=action,
            follow_up=FollowUp(
                recommend_contact_date=base_date + timedelta(days=2),
                memo=f"{action.title} 후속 연락",
            ),
            follow_up_insight=_follow_up_insight(action, reason),
        )

    def generate_message(self, request: MessageGenerateRequest) -> MessageGenerateResponse:
        reason = _first_reason_type(request.non_conversion_reasons)
        event_text = ""
        if request.event is not None:
            event_text = f" 현재 {request.event.title} 혜택도 함께 확인하실 수 있습니다."
        instruction_text = ""
        if request.message_options.additional_instruction:
            instruction_text = f" {request.message_options.additional_instruction}"
        content = (
            f"{request.customer.name}님, 상담 때 말씀해주신 부분을 바탕으로 "
            f"{request.next_best_action.title} 안내를 드립니다. "
            f"{request.next_best_action.description} {reason} 부담을 줄일 수 있게 선택지를 정리했습니다."
            f"{event_text}{instruction_text}"
        )
        return MessageGenerateResponse(
            content=content,
            version_type=request.message_options.version_type,
            tone_preset=request.message_options.tone_preset,
        )


class OpenAiProvider(AiProvider):
    def __init__(self, settings: AiSettings, client: OpenAI | None = None) -> None:
        if not settings.api_key:
            raise RuntimeError(f"API key is required when AI_PROVIDER is {settings.provider}.")
        self.settings = settings
        self.client = client or OpenAI(
            api_key=settings.api_key,
            base_url=settings.base_url,
            timeout=settings.timeout_seconds,
        )

    def check_inquiry_preview(self, request: InquiryPreviewRequest) -> PreviewResponse:
        return self._complete(
            PreviewResponse,
            (
                "문의 등록 전 입력 내용을 평가하세요. 한국어, 숫자, 일반 문장부호는 정상 입력입니다. "
                "request.rawText가 10자 이상이고 request.serviceName이 비어 있지 않으면 기본적으로 isValid=true입니다. "
                "문의 내용에 서비스 관심사나 가격/일정/목표 중 하나 이상이 있으면 isValid=true로 판단하세요. "
                "warnings는 실제 누락이나 모호함이 있을 때만 작성하고, suggestions는 다음 상담에서 확인할 보완 질문을 한국어로 작성하세요."
            ),
            request,
        )

    def check_consultation_preview(self, request: ConsultationPreviewRequest) -> PreviewResponse:
        return self._complete(
            PreviewResponse,
            (
                "상담 등록 전 입력 내용을 평가하세요. 한국어, 숫자, 일반 문장부호는 정상 입력입니다. "
                "request.rawText가 10자 이상이고 request.serviceName이 비어 있지 않으면 기본적으로 isValid=true입니다. "
                "상담 내용에 고객 목표, 가능 시간, 가격, 서비스 관심사 중 하나 이상이 있으면 isValid=true로 판단하세요. "
                "rawText에 이미 있는 내용을 누락됐다고 경고하지 마세요. "
                "warnings는 실제 누락이나 모호함이 있을 때만 작성하고, suggestions는 다음 상담에서 확인할 보완 질문을 한국어로 작성하세요."
            ),
            request,
        )

    def analyze_consultation(self, request: ConsultationAnalyzeRequest) -> ConsultationAnalyzeResponse:
        return self._complete(
            ConsultationAnalyzeResponse,
            "상담 내용을 분석해 고객 인사이트, 미전환 사유, 다음 행동, 후속 연락 정보를 한국어로 작성하세요.",
            request,
        )

    def recommend_next_action(self, request: NextActionRequest) -> NextActionResponse:
        return self._complete(
            NextActionResponse,
            "기존 분석과 최근 상담을 바탕으로 다음 행동과 후속 연락 정보를 한국어로 작성하세요.",
            request,
        )

    def generate_message(self, request: MessageGenerateRequest) -> MessageGenerateResponse:
        return self._complete(
            MessageGenerateResponse,
            "고객에게 보낼 자연스러운 한국어 메시지를 작성하고 요청된 tonePreset/versionType을 그대로 유지하세요.",
            request,
        )

    def _complete(
        self,
        response_model: type[ResponseModel],
        task: str,
        request: BaseModel,
    ) -> ResponseModel:
        try:
            completion = self.client.chat.completions.parse(
                model=self.settings.model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "당신은 Fitback 매장 관리 AI 서버입니다. "
                            "반드시 제공된 JSON Schema와 일치하는 JSON만 반환하세요. "
                            "필수 문자열은 빈 문자열이나 공백으로 두지 마세요.\n"
                            f"{ontology_prompt_context()}"
                        ),
                    },
                    {
                        "role": "user",
                        "content": json.dumps(
                            {
                                "task": task,
                                "request": request.model_dump(mode="json", by_alias=True),
                            },
                            ensure_ascii=False,
                        ),
                    },
                ],
                response_format=response_model,
            )
            parsed = completion.choices[0].message.parsed
            if parsed is None:
                content = completion.choices[0].message.content
                if not content:
                    raise RuntimeError("OpenAI returned an empty response.")
                parsed = response_model.model_validate_json(content)
            return _normalize_response(parsed)
        except (OpenAIError, json.JSONDecodeError, ValueError, IndexError, AttributeError) as exc:
            raise RuntimeError("OpenAI AI processing failed") from exc


def get_ai_provider() -> AiProvider:
    settings = load_ai_settings()
    if settings.provider == "heuristic":
        return HeuristicAiProvider()
    if settings.provider == "openai":
        return OpenAiProvider(settings)
    raise RuntimeError(f"Unsupported AI_PROVIDER: {settings.provider}")


def _preview_response(raw_text: str, service_name: str) -> PreviewResponse:
    warnings = []
    suggestions = []
    if len(raw_text) < 20:
        warnings.append("입력 내용이 짧아 AI 판단 근거가 부족할 수 있습니다.")
        suggestions.append("고객의 목표, 예산, 가능한 방문 시간을 더 적어주세요.")
    else:
        suggestions.append(f"{service_name} 상담 목적과 방문 가능 시간을 확인해 주세요.")
    return PreviewResponse(is_valid=True, warnings=warnings, suggestions=suggestions)


def _first_reason_type(reasons: list[NonConversionReason]) -> str:
    if not reasons:
        return "NEEDS_FOLLOW_UP"
    return normalize_reason_code(reasons[0].reason_type)


def _action_for_reason(reason: str, service_name: str) -> NextBestAction:
    action = action_for_reason(reason)
    return NextBestAction(
        title=action.title or action.label,
        description=(action.action_description or action.description).format(service_name=service_name),
    )


def _follow_up_insight(action: NextBestAction, reason: str) -> FollowUpInsight:
    return FollowUpInsight(
        persuasion_point=PersuasionPoint(key_message=action.description),
        caution_note=f"{reason} 이슈를 압박하지 말고 선택지를 제안합니다.",
        action_basis=action,
    )


def _date_from_uuid(value: UUID) -> date:
    day_offset = int(value.hex[-2:], 16) % 7
    return date.today() + timedelta(days=day_offset)


def _normalize_response(response: ResponseModel) -> ResponseModel:
    if isinstance(response, ConsultationAnalyzeResponse):
        response.customer_insight.lead_temperature = normalize_temperature_code(
            response.customer_insight.lead_temperature,
            allow_unknown=False,
        )
        response.non_conversion_reasons = _normalize_reasons(response.non_conversion_reasons)
    elif isinstance(response, NextActionResponse):
        response.priority_score = max(0, min(100, response.priority_score))
    return response


def _normalize_reasons(reasons: list[NonConversionReason]) -> list[NonConversionReason]:
    for reason in reasons:
        reason.reason_type = normalize_reason_code(reason.reason_type, allow_unknown=False)
        reason.confidence = normalize_confidence(reason.confidence, allow_unknown=False)
    return reasons
