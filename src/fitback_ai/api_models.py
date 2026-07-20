from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


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


PREVIEW_UNKNOWN_VALUE = "아직 확인되지 않음"

PREVIEW_CODEBOOK = [
    ("INTEREST_SERVICE", "관심 상품"),
    ("EXERCISE_GOAL", "운동 목적"),
    ("EXERCISE_EXPERIENCE", "운동 경험"),
    ("INJURY_HISTORY", "부상 이력"),
    ("CUSTOMER_REQUEST", "고객 요청"),
    ("COUNSELOR_RESPONSE", "나의 응대"),
    ("SPECIAL_NOTE", "특이사항"),
]


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


class PreviewItem(ApiModel):
    key: str = Field(min_length=1)
    label: str = Field(min_length=1)
    confirmed: bool
    value: str = Field(min_length=1)

    @field_validator("key", "label", "value")
    @classmethod
    def validate_text(cls, value: str) -> str:
        return require_text(value)


class PreviewResponse(ApiModel):
    confirmed_count: int = Field(ge=0)
    total_count: int = Field(ge=0)
    items: list[PreviewItem]

    @model_validator(mode="after")
    def canonicalize_preview_items(self) -> PreviewResponse:
        items_by_key = {item.key: item for item in self.items}
        canonical_items = []
        for key, label in PREVIEW_CODEBOOK:
            source = items_by_key.get(key)
            confirmed = bool(source and source.confirmed)
            value = source.value if confirmed and source.value.strip() else PREVIEW_UNKNOWN_VALUE
            canonical_items.append(PreviewItem(key=key, label=label, confirmed=confirmed, value=value))
        self.items = canonical_items
        self.total_count = len(canonical_items)
        self.confirmed_count = sum(1 for item in canonical_items if item.confirmed)
        return self


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


class AttachedMaterial(ApiModel):
    material_type: str = Field(min_length=1)
    title: str = Field(min_length=1)
    content: str = Field(min_length=1)

    @field_validator("material_type", "title", "content")
    @classmethod
    def validate_text(cls, value: str) -> str:
        return require_text(value)


class ConsultationAnalyzeRequest(ApiModel):
    customer: AnalysisCustomer
    consultation: AnalysisConsultation
    service: AnalysisService
    store_context: StoreContext
    attached_materials: list[AttachedMaterial]


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


class GraphSyncStore(ApiModel):
    store_id: UUID
    store_type: StoreType


class GraphSyncService(ApiModel):
    service_id: UUID
    store_id: UUID
    service_name: str = Field(min_length=1)
    description: str | None = None
    price: float | None = Field(default=None, ge=0)
    active: bool | None = None

    @field_validator("service_name")
    @classmethod
    def validate_service_name(cls, value: str) -> str:
        return require_text(value)


class GraphSyncCustomer(ApiModel):
    customer_id: UUID
    store_id: UUID
    registered_service_id: UUID | None = None
    name: str = Field(min_length=1)
    gender: Gender
    birth_date: date
    phone_num: str = Field(min_length=1)
    preferred_contact_channel: PreferredContactChannel
    status: CustomerStatus
    inflow_path_id: UUID
    inflow_path_name: str = Field(min_length=1)
    registered_at: datetime | None = None
    first_consult_at: date
    latest_consult_at: date

    @field_validator("name", "phone_num", "inflow_path_name")
    @classmethod
    def validate_text(cls, value: str) -> str:
        return require_text(value)


class GraphSyncConsultation(ApiModel):
    consultation_id: UUID
    customer_id: UUID
    consulted_service_id: UUID
    session_no: int = Field(ge=1)
    consulted_at: datetime
    stage: ConsultationStage | None = None
    source_type: ConsultationSourceType
    raw_text: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    ai_analysis_status: str = Field(min_length=1)
    ai_parsed_at: datetime | None = None

    @field_validator("raw_text", "summary", "ai_analysis_status")
    @classmethod
    def validate_text(cls, value: str) -> str:
        return require_text(value)


class GraphSyncCustomerAiInsight(ApiModel):
    customer_id: UUID
    lead_temperature: str = Field(min_length=1)
    temperature_basis: str = Field(min_length=1)
    priority_score: int = Field(ge=0, le=100)
    analyzed_at: datetime | None = None

    @field_validator("lead_temperature", "temperature_basis")
    @classmethod
    def validate_text(cls, value: str) -> str:
        return require_text(value)


class GraphSyncNonConversionReason(ApiModel):
    reason_id: UUID
    customer_id: UUID
    consultation_id: UUID | None = None
    reason_type: str = Field(min_length=1)
    role: str | None = None
    reason_basis: str | None = None
    confidence: str | None = None

    @field_validator("reason_type")
    @classmethod
    def validate_reason_type(cls, value: str) -> str:
        return require_text(value)

    @field_validator("role", "reason_basis", "confidence")
    @classmethod
    def validate_optional_text(cls, value: str | None) -> str | None:
        return require_optional_text(value)


class GraphSyncFollowUp(ApiModel):
    follow_up_id: UUID
    customer_id: UUID
    consultation_id: UUID
    recommend_contact_date: date
    status: str = Field(min_length=1)
    contact_round: int = Field(ge=1, le=3)
    has_reply: bool
    replied_at: datetime | None = None
    snoozed_until: date | None = None
    memo: str | None = None

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str) -> str:
        return require_text(value)

    @field_validator("memo")
    @classmethod
    def validate_optional_text(cls, value: str | None) -> str | None:
        return require_optional_text(value)


class GraphSyncFollowUpAiInsight(ApiModel):
    follow_up_id: UUID
    persuasion_point: dict[str, Any] = Field(default_factory=dict)
    caution_note: str | None = None
    action_basis: dict[str, Any] = Field(default_factory=dict)
    analyzed_at: datetime | None = None

    @field_validator("caution_note")
    @classmethod
    def validate_optional_text(cls, value: str | None) -> str | None:
        return require_optional_text(value)


class ConsultationGraphSyncRequest(ApiModel):
    store: GraphSyncStore
    service: GraphSyncService
    customer: GraphSyncCustomer
    consultation: GraphSyncConsultation
    customer_ai_insight: GraphSyncCustomerAiInsight
    non_conversion_reasons: list[GraphSyncNonConversionReason] = Field(default_factory=list)
    follow_up: GraphSyncFollowUp | None = None
    follow_up_ai_insight: GraphSyncFollowUpAiInsight | None = None

    @model_validator(mode="after")
    def validate_rds_references(self) -> ConsultationGraphSyncRequest:
        if self.service.store_id != self.store.store_id:
            raise ValueError("service.storeId must match store.storeId")
        if self.customer.store_id != self.store.store_id:
            raise ValueError("customer.storeId must match store.storeId")
        if self.consultation.customer_id != self.customer.customer_id:
            raise ValueError("consultation.customerId must match customer.customerId")
        if self.consultation.consulted_service_id != self.service.service_id:
            raise ValueError("consultation.consultedServiceId must match service.serviceId")
        if self.customer_ai_insight.customer_id != self.customer.customer_id:
            raise ValueError("customerAiInsight.customerId must match customer.customerId")

        reason_ids = set()
        for reason in self.non_conversion_reasons:
            if reason.reason_id in reason_ids:
                raise ValueError("nonConversionReasons[].reasonId must be unique")
            reason_ids.add(reason.reason_id)
            if reason.customer_id != self.customer.customer_id:
                raise ValueError("nonConversionReasons[].customerId must match customer.customerId")
            if reason.consultation_id is not None and reason.consultation_id != self.consultation.consultation_id:
                raise ValueError("nonConversionReasons[].consultationId must match consultation.consultationId")

        if self.follow_up is None:
            if self.follow_up_ai_insight is not None:
                raise ValueError("followUpAiInsight requires followUp")
            return self

        if self.follow_up.customer_id != self.customer.customer_id:
            raise ValueError("followUp.customerId must match customer.customerId")
        if self.follow_up.consultation_id != self.consultation.consultation_id:
            raise ValueError("followUp.consultationId must match consultation.consultationId")
        if self.follow_up_ai_insight is not None and self.follow_up_ai_insight.follow_up_id != self.follow_up.follow_up_id:
            raise ValueError("followUpAiInsight.followUpId must match followUp.followUpId")
        return self


class GraphSyncResponse(ApiModel):
    persisted: bool
    counts: dict[str, int] | None = None


def require_text(value: str) -> str:
    stripped = value.strip()
    if not stripped:
        raise ValueError("must not be blank")
    return stripped


def require_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    return require_text(value)
