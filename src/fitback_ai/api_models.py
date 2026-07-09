from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


def to_camel(value: str) -> str:
    head, *tail = value.split("_")
    return head + "".join(part.capitalize() for part in tail)


class ApiModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        serialize_by_alias=True,
        use_enum_values=True,
        extra="forbid",
    )


class Gender(StrEnum):
    MALE = "MALE"
    FEMALE = "FEMALE"


class InquiryStatus(StrEnum):
    RECEIVED = "RECEIVED"
    VISIT_SCHEDULED = "VISIT_SCHEDULED"
    VISIT_CANCELED = "VISIT_CANCELED"
    CONVERTED = "CONVERTED"


class ConsultationStage(StrEnum):
    CONSULTATION = "CONSULTATION"
    FIRST_FOLLOW_UP = "FIRST_FOLLOW_UP"
    SECOND_FOLLOW_UP = "SECOND_FOLLOW_UP"
    TRIAL = "TRIAL"
    FINAL_DECISION = "FINAL_DECISION"


class ConsultationSourceType(StrEnum):
    DIRECT = "DIRECT"
    IMPORT = "IMPORT"
    INQUIRY = "INQUIRY"


class ConsultationRegistrationStatus(StrEnum):
    REGISTERED = "REGISTERED"
    PENDING = "PENDING"
    SCHEDULED = "SCHEDULED"
    LOST = "LOST"


class CustomerStatus(StrEnum):
    REGISTERED = "REGISTERED"
    PENDING = "PENDING"
    SCHEDULED = "SCHEDULED"
    LOST = "LOST"
    NO_SHOW = "NO_SHOW"


class PreferredContactChannel(StrEnum):
    SMS = "SMS"
    PHONE = "PHONE"
    KAKAO = "KAKAO"


class StoreType(StrEnum):
    GYM = "GYM"
    OTHER = "OTHER"


class MessageTonePreset(StrEnum):
    FRIENDLY = "FRIENDLY"
    PROFESSIONAL = "PROFESSIONAL"
    SOFT = "SOFT"


class MessageVersionType(StrEnum):
    SHORT = "SHORT"
    STANDARD = "STANDARD"


class CustomerInfo(ApiModel):
    name: str = Field(min_length=1)
    gender: Gender
    birth_date: date

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        return require_text(value)


class InquiryPreviewRequest(ApiModel):
    raw_text: str = Field(min_length=1)
    service_name: str = Field(min_length=1)
    inquiry_status: InquiryStatus
    customer_info: CustomerInfo

    @field_validator("raw_text", "service_name")
    @classmethod
    def validate_text(cls, value: str) -> str:
        return require_text(value)


class ConsultationPreviewRequest(ApiModel):
    raw_text: str = Field(min_length=1)
    service_name: str = Field(min_length=1)
    customer_info: CustomerInfo

    @field_validator("raw_text", "service_name")
    @classmethod
    def validate_text(cls, value: str) -> str:
        return require_text(value)


class PreviewResponse(ApiModel):
    is_valid: bool
    warnings: list[str]
    suggestions: list[str]


class AnalysisCustomer(ApiModel):
    customer_id: UUID
    name: str = Field(min_length=1)
    gender: Gender
    birth_date: date
    phone_num: str = Field(min_length=1)
    preferred_contact_channel: PreferredContactChannel
    status: CustomerStatus
    inflow_path_id: UUID
    inflow_path_name: str = Field(min_length=1)

    @field_validator("name", "phone_num", "inflow_path_name")
    @classmethod
    def validate_text(cls, value: str) -> str:
        return require_text(value)


class AnalysisConsultation(ApiModel):
    consultation_id: UUID
    session_no: int = Field(ge=1)
    consulted_at: datetime
    consulted_service_id: UUID
    stage: ConsultationStage | None = None
    source_type: ConsultationSourceType
    raw_text: str = Field(min_length=1)

    @field_validator("raw_text")
    @classmethod
    def validate_raw_text(cls, value: str) -> str:
        return require_text(value)

    @field_validator("consulted_at")
    @classmethod
    def validate_consulted_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
            raise ValueError("must include a UTC offset")
        return value


class AnalysisService(ApiModel):
    service_id: UUID
    service_name: str = Field(min_length=1)
    description: str | None = None
    price: float | None = Field(default=None, ge=0)

    @field_validator("service_name")
    @classmethod
    def validate_service_name(cls, value: str) -> str:
        return require_text(value)


class StoreContext(ApiModel):
    store_id: UUID
    store_type: StoreType
    registration_status: ConsultationRegistrationStatus


class ConsultationAnalyzeRequest(ApiModel):
    customer: AnalysisCustomer
    consultation: AnalysisConsultation
    service: AnalysisService
    store_context: StoreContext


class CustomerInsight(ApiModel):
    lead_temperature: str = Field(min_length=1)
    temperature_basis: str = Field(min_length=1)
    priority_score: int = Field(ge=0, le=100)

    @field_validator("lead_temperature", "temperature_basis")
    @classmethod
    def validate_text(cls, value: str) -> str:
        return require_text(value)


class NonConversionReason(ApiModel):
    reason_type: str = Field(min_length=1)
    role: str = Field(min_length=1)
    reason_basis: str = Field(min_length=1)
    confidence: str | None = None

    @field_validator("reason_type", "role", "reason_basis")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        return require_text(value)

    @field_validator("confidence")
    @classmethod
    def validate_optional_text(cls, value: str | None) -> str | None:
        return require_optional_text(value)


class NextBestAction(ApiModel):
    title: str = Field(min_length=1)
    description: str = Field(min_length=1)

    @field_validator("title", "description")
    @classmethod
    def validate_text(cls, value: str) -> str:
        return require_text(value)


class FollowUp(ApiModel):
    recommend_contact_date: date
    memo: str = Field(min_length=1)

    @field_validator("memo")
    @classmethod
    def validate_memo(cls, value: str) -> str:
        return require_text(value)


class PersuasionPoint(ApiModel):
    key_message: str = Field(min_length=1)

    @field_validator("key_message")
    @classmethod
    def validate_key_message(cls, value: str) -> str:
        return require_text(value)


class FollowUpInsight(ApiModel):
    persuasion_point: PersuasionPoint
    caution_note: str = Field(min_length=1)
    action_basis: NextBestAction

    @field_validator("caution_note")
    @classmethod
    def validate_caution_note(cls, value: str) -> str:
        return require_text(value)


class ConsultationAnalyzeResponse(ApiModel):
    summary: str = Field(min_length=1)
    customer_insight: CustomerInsight
    non_conversion_reasons: list[NonConversionReason]
    next_best_action: NextBestAction
    follow_up: FollowUp
    follow_up_insight: FollowUpInsight

    @field_validator("summary")
    @classmethod
    def validate_summary(cls, value: str) -> str:
        return require_text(value)


class NextActionCustomer(ApiModel):
    customer_id: UUID
    status: CustomerStatus


class LatestConsultation(ApiModel):
    consultation_id: UUID
    summary: str | None = None
    raw_text: str | None = None

    @field_validator("summary", "raw_text")
    @classmethod
    def validate_optional_text(cls, value: str | None) -> str | None:
        return require_optional_text(value)


class ExistingAiAnalysis(ApiModel):
    lead_temperature: str | None = None
    temperature_basis: str | None = None
    non_conversion_reasons: list[NonConversionReason] = Field(default_factory=list)

    @field_validator("lead_temperature", "temperature_basis")
    @classmethod
    def validate_optional_text(cls, value: str | None) -> str | None:
        return require_optional_text(value)


class NextActionRequest(ApiModel):
    customer: NextActionCustomer
    latest_consultation: LatestConsultation
    ai_analysis: ExistingAiAnalysis


class NextActionResponse(ApiModel):
    priority_score: int = Field(ge=0, le=100)
    next_best_action: NextBestAction
    follow_up: FollowUp
    follow_up_insight: FollowUpInsight


class MessageCustomer(ApiModel):
    customer_id: UUID
    name: str = Field(min_length=1)
    preferred_contact_channel: PreferredContactChannel
    status: CustomerStatus

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        return require_text(value)


class MessageConsultation(ApiModel):
    consultation_id: UUID
    summary: str | None = None

    @field_validator("summary")
    @classmethod
    def validate_summary(cls, value: str | None) -> str | None:
        return require_optional_text(value)


class MessageAiInsight(ApiModel):
    lead_temperature: str | None = None
    priority_score: int | None = Field(default=None, ge=0, le=100)

    @field_validator("lead_temperature")
    @classmethod
    def validate_lead_temperature(cls, value: str | None) -> str | None:
        return require_optional_text(value)


class MessageAction(ApiModel):
    title: str = Field(min_length=1)
    description: str = Field(min_length=1)
    persuasion_point: PersuasionPoint | None = None
    caution_note: str | None = None
    action_basis: NextBestAction | None = None

    @field_validator("title", "description")
    @classmethod
    def validate_text(cls, value: str) -> str:
        return require_text(value)

    @field_validator("caution_note")
    @classmethod
    def validate_caution_note(cls, value: str | None) -> str | None:
        return require_optional_text(value)


class MessageEvent(ApiModel):
    event_id: UUID
    title: str = Field(min_length=1)
    description: str | None = None
    discount_rate: float | None = Field(default=None, ge=0)

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        return require_text(value)

    @field_validator("description")
    @classmethod
    def validate_description(cls, value: str | None) -> str | None:
        return require_optional_text(value)


class MessageOptions(ApiModel):
    tone_preset: MessageTonePreset
    version_type: MessageVersionType
    additional_instruction: str | None = None

    @field_validator("additional_instruction")
    @classmethod
    def validate_instruction(cls, value: str | None) -> str | None:
        return require_optional_text(value)


class MessageGenerateRequest(ApiModel):
    customer: MessageCustomer
    latest_consultation: MessageConsultation
    ai_insight: MessageAiInsight
    non_conversion_reasons: list[NonConversionReason] = Field(default_factory=list)
    next_best_action: MessageAction
    event: MessageEvent | None = None
    message_options: MessageOptions


class MessageGenerateResponse(ApiModel):
    content: str = Field(min_length=1)
    version_type: MessageVersionType
    tone_preset: MessageTonePreset

    @field_validator("content")
    @classmethod
    def validate_content(cls, value: str) -> str:
        return require_text(value)


def require_text(value: str) -> str:
    stripped = value.strip()
    if not stripped:
        raise ValueError("must not be blank")
    return stripped


def require_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    return require_text(value)
