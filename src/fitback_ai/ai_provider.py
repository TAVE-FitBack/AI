from __future__ import annotations

import json
from datetime import date, timedelta
from typing import TypeVar, cast
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
    PREVIEW_CODEBOOK,
    PREVIEW_UNKNOWN_VALUE,
    PersuasionPoint,
    PreviewItem,
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
        priority_score = priority_for_reason(reason)
        contact_date = _recommended_contact_date(
            request.consultation.consulted_at.date() + timedelta(days=3),
            priority_score,
        )
        insight = CustomerInsight(
            lead_temperature=temperature_for_status(str(request.store_context.registration_status), reason),
            temperature_basis=f"{request.service.service_name} 상담 내용과 {reason} 신호를 함께 고려했습니다.",
            priority_score=priority_score,
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
        priority_score = priority_for_reason(reason)
        return NextActionResponse(
            priority_score=priority_score,
            next_best_action=action,
            follow_up=FollowUp(
                recommend_contact_date=_recommended_contact_date(base_date + timedelta(days=2), priority_score),
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
                "문의 등록 전 입력 내용을 평가하세요. 응답은 confirmedCount, totalCount, items만 포함합니다. "
                "items는 반드시 INTEREST_SERVICE, EXERCISE_GOAL, EXERCISE_EXPERIENCE, INJURY_HISTORY, "
                "CUSTOMER_REQUEST, COUNSELOR_RESPONSE, SPECIAL_NOTE 순서의 7개 항목을 모두 반환하세요. "
                "확인되지 않은 항목은 confirmed=false, value='아직 확인되지 않음'으로 반환하세요."
                "value는 반드시 한국어로 작성하고 그 값은 한눈에 알아볼 수 있도록하세요."
                "value에 들어갈 말은 언급됨으로 끝나는게 아니라 실제 세부 내용을 담아야 합니다. 예를 들어 '운동 목표가 언급됨'이 아니라 '체중 감량을 목표로 함'과 같이 작성해야 합니다."
            ),
            request,
        )

    def check_consultation_preview(self, request: ConsultationPreviewRequest) -> PreviewResponse:
        return self._complete(
            PreviewResponse,
            (
                "상담 등록 전 입력 내용을 평가하세요. 응답은 confirmedCount, totalCount, items만 포함합니다. "
                "items는 반드시 INTEREST_SERVICE, EXERCISE_GOAL, EXERCISE_EXPERIENCE, INJURY_HISTORY, "
                "CUSTOMER_REQUEST, COUNSELOR_RESPONSE, SPECIAL_NOTE 순서의 7개 항목을 모두 반환하세요. "
                "확인되지 않은 항목은 confirmed=false, value='아직 확인되지 않음'으로 반환하세요."
                "value는 반드시 한국어로 작성하고 그 값은 한눈에 알아볼 수 있도록하세요."
                "value에 들어갈 말은 언급됨으로 끝나는게 아니라 실제 세부 내용을 담아야 합니다. 예를 들어 '상담 내용이 언급됨'이 아니라 '고객의 운동 목표는 체중 감량입니다'와 같이 작성해야 합니다."
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
            return _normalize_response(parsed, request)
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
    text = raw_text.casefold()
    detected_values = {
        "INTEREST_SERVICE": service_name,
        "EXERCISE_GOAL": _detect_value(text, ["감량", "다이어트", "체중", "근력", "목표"], "운동 목표가 언급됨"),
        "EXERCISE_EXPERIENCE": _detect_value(text, ["경험", "해봤", "운동했", "pt", "헬스"], "운동 경험이 언급됨"),
        "INJURY_HISTORY": _detect_value(text, ["부상", "통증", "허리", "무릎", "어깨"], "부상 또는 통증 이력이 언급됨"),
        "CUSTOMER_REQUEST": _detect_value(text, ["문의", "요청", "궁금", "가능", "가격", "일정"], "고객 요청이 언급됨"),
        "COUNSELOR_RESPONSE": _detect_value(text, ["안내", "상담사", "답변", "설명", "추천"], "상담 응대가 언급됨"),
        "SPECIAL_NOTE": _detect_value(text, ["특이", "주의", "메모", "기타", "참고"], "특이사항이 언급됨"),
    }
    items = [
        PreviewItem(
            key=key,
            label=label,
            confirmed=detected_values[key] is not None,
            value=detected_values[key] or PREVIEW_UNKNOWN_VALUE,
        )
        for key, label in PREVIEW_CODEBOOK
    ]
    return PreviewResponse(
        confirmed_count=sum(1 for item in items if item.confirmed),
        total_count=len(items),
        items=items,
    )


def _detect_value(text: str, keywords: list[str], value: str) -> str | None:
    if any(keyword in text for keyword in keywords):
        return value
    return None


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
    return _today() + timedelta(days=day_offset)


def _recommended_contact_date(value: date, priority_score: int) -> date:
    minimum = _today() + timedelta(days=_follow_up_delay_days(priority_score))
    maximum = _today() + timedelta(days=14)
    if value < minimum:
        return minimum
    if value > maximum:
        return maximum
    return value


def _follow_up_delay_days(priority_score: int) -> int:
    if priority_score >= 80:
        return 1
    if priority_score >= 60:
        return 2
    return 3


def _today() -> date:
    return date.today()


def _normalize_response(response: ResponseModel, request: BaseModel) -> ResponseModel:
    if isinstance(response, PreviewResponse):
        return cast(ResponseModel, response)
    elif isinstance(response, ConsultationAnalyzeResponse):
        response.customer_insight.lead_temperature = normalize_temperature_code(
            response.customer_insight.lead_temperature,
            allow_unknown=False,
        )
        response.non_conversion_reasons = _normalize_reasons(response.non_conversion_reasons)
        response.follow_up.recommend_contact_date = _recommended_contact_date(
            response.follow_up.recommend_contact_date,
            response.customer_insight.priority_score,
        )
    elif isinstance(response, NextActionResponse):
        response.priority_score = max(0, min(100, response.priority_score))
        response.follow_up.recommend_contact_date = _recommended_contact_date(
            response.follow_up.recommend_contact_date,
            response.priority_score,
        )
    elif isinstance(response, MessageGenerateResponse) and isinstance(request, MessageGenerateRequest):
        response.version_type = request.message_options.version_type
        response.tone_preset = request.message_options.tone_preset
    return response


def _normalize_reasons(reasons: list[NonConversionReason]) -> list[NonConversionReason]:
    for reason in reasons:
        reason.reason_type = normalize_reason_code(reason.reason_type, allow_unknown=False)
        reason.confidence = normalize_confidence(reason.confidence, allow_unknown=False)
    return reasons
