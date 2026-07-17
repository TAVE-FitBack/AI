from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class OntologyConcept:
    code: str
    label: str
    description: str
    keywords: tuple[str, ...]
    priority_score: int | None = None
    default_action_code: str | None = None
    category_code: str | None = None
    llm_guidance: str = ""
    title: str | None = None
    action_description: str | None = None


REASON_CATEGORIES: dict[str, OntologyConcept] = {
    "ECONOMIC": OntologyConcept(
        code="ECONOMIC",
        label="경제적 부담",
        description="가격, 예산, 결제 방식이 의사결정을 막는 상태",
        keywords=("가격", "예산", "비싸", "할인", "price", "budget"),
        llm_guidance="비용, 예산, 할인, 결제 부담이 핵심이면 이 범주로 분류한다.",
    ),
    "TIME": OntologyConcept(
        code="TIME",
        label="시간/일정 제약",
        description="방문 가능 시간, 일정 충돌, 예약 조율 문제가 있는 상태",
        keywords=("시간", "일정", "예약", "schedule", "time"),
        llm_guidance="시간대, 예약, 방문 일정 조율이 핵심이면 이 범주로 분류한다.",
    ),
    "DECISION": OntologyConcept(
        code="DECISION",
        label="의사결정 보류",
        description="가족, 비교, 내부 검토 등으로 결정이 보류된 상태",
        keywords=("가족", "상의", "비교", "고민", "family", "compare"),
        llm_guidance="타인과 상의하거나 대안을 비교하느라 결정하지 못하면 이 범주로 분류한다.",
    ),
    "ENGAGEMENT": OntologyConcept(
        code="ENGAGEMENT",
        label="후속 반응 필요",
        description="응답 부재, 관심 약화, 추가 리마인드가 필요한 상태",
        keywords=("무응답", "연락", "답변", "no response", "follow"),
        llm_guidance="명확한 반대 사유보다 후속 연락과 관심 회복이 핵심이면 이 범주로 분류한다.",
    ),
}


ACTION_CONCEPTS: dict[str, OntologyConcept] = {
    "BUDGET_OPTION_GUIDE": OntologyConcept(
        code="BUDGET_OPTION_GUIDE",
        label="예산 맞춤 상품 안내",
        description="예산 안에서 시작 가능한 상품, 분납, 혜택을 정리해 안내한다.",
        keywords=("예산", "가격", "할인", "분납"),
        llm_guidance="가격 압박보다 선택지를 넓히는 표현을 사용한다.",
        title="예산 맞춤 상품 안내",
        action_description="{service_name} 선택지를 예산별로 정리해 부담을 낮춥니다.",
    ),
    "SCHEDULE_RECONFIRM": OntologyConcept(
        code="SCHEDULE_RECONFIRM",
        label="가능 시간 재확인",
        description="고객이 방문 가능한 시간대를 다시 확인하고 대체 일정을 제안한다.",
        keywords=("시간", "일정", "예약"),
        llm_guidance="고객의 가능한 시간대를 먼저 확인하고 좁은 선택지를 제안한다.",
        title="가능 시간 재확인",
        action_description="방문 가능한 시간대를 확인하고 대체 일정을 제안합니다.",
    ),
    "DECISION_SUMMARY_SEND": OntologyConcept(
        code="DECISION_SUMMARY_SEND",
        label="결정 요약 전달",
        description="가족이나 동료와 공유할 수 있도록 혜택과 조건을 짧게 요약한다.",
        keywords=("가족", "상의", "공유", "요약"),
        llm_guidance="공유 가능한 요약과 결정 기준을 제공한다.",
        title="결정에 필요한 요약 전달",
        action_description="상의에 필요한 핵심 혜택과 조건을 간단히 정리합니다.",
    ),
    "RESPONSE_REMINDER": OntologyConcept(
        code="RESPONSE_REMINDER",
        label="응답 리마인드",
        description="부담 없는 톤으로 미응답 고객에게 후속 연락한다.",
        keywords=("무응답", "리마인드", "연락"),
        llm_guidance="압박 없이 이전 상담 맥락을 짧게 환기한다.",
        title="상담 내용 기반 후속 연락",
        action_description="상담에서 확인한 관심사와 망설임을 바탕으로 다음 연락을 진행합니다.",
    ),
    "COMPARISON_SUPPORT": OntologyConcept(
        code="COMPARISON_SUPPORT",
        label="비교 기준 지원",
        description="다른 선택지와 비교 중인 고객에게 판단 기준을 제공한다.",
        keywords=("비교", "다른 곳", "대안"),
        llm_guidance="경쟁 비교를 공격하지 말고 판단 기준을 정리한다.",
        title="비교 기준 정리",
        action_description="{service_name} 선택 시 확인할 기준과 장점을 정리합니다.",
    ),
    "GENERAL_FOLLOW_UP": OntologyConcept(
        code="GENERAL_FOLLOW_UP",
        label="일반 후속 연락",
        description="명확한 사유가 없을 때 상담 맥락 기반으로 후속 연락한다.",
        keywords=("후속", "관심", "상담"),
        llm_guidance="확정되지 않은 사유를 단정하지 말고 관심사를 확인한다.",
        title="상담 내용 기반 후속 연락",
        action_description="상담에서 확인한 관심사와 망설임을 바탕으로 다음 연락을 진행합니다.",
    ),
}


REASON_CONCEPTS: dict[str, OntologyConcept] = {
    "PRICE": OntologyConcept(
        code="PRICE",
        label="가격 부담",
        description="가격, 예산, 결제 부담 때문에 전환이 보류된 상태",
        keywords=("가격", "예산", "비싸", "금액", "할인", "price", "budget"),
        priority_score=80,
        default_action_code="BUDGET_OPTION_GUIDE",
        category_code="ECONOMIC",
        llm_guidance="가격, 예산, 할인, 결제 부담을 직접 또는 강하게 암시하면 PRICE를 사용한다.",
    ),
    "SCHEDULE": OntologyConcept(
        code="SCHEDULE",
        label="일정 충돌",
        description="방문 시간이나 일정 조율 문제 때문에 전환이 보류된 상태",
        keywords=("시간", "일정", "예약", "스케줄", "schedule", "time"),
        priority_score=72,
        default_action_code="SCHEDULE_RECONFIRM",
        category_code="TIME",
        llm_guidance="방문 가능 시간, 일정, 예약 조율이 핵심이면 SCHEDULE을 사용한다.",
    ),
    "FAMILY_DISCUSSION": OntologyConcept(
        code="FAMILY_DISCUSSION",
        label="가족 상의",
        description="가족 또는 주변 사람과 상의가 필요해 결정이 보류된 상태",
        keywords=("가족", "상의", "배우자", "부모", "family"),
        priority_score=68,
        default_action_code="DECISION_SUMMARY_SEND",
        category_code="DECISION",
        llm_guidance="가족이나 지인과 상의해야 한다는 맥락이면 FAMILY_DISCUSSION을 사용한다.",
    ),
    "NO_RESPONSE": OntologyConcept(
        code="NO_RESPONSE",
        label="무응답",
        description="상담 이후 고객 응답이 없어 후속 확인이 필요한 상태",
        keywords=("무응답", "연락 안", "답변 없음", "no response"),
        priority_score=62,
        default_action_code="RESPONSE_REMINDER",
        category_code="ENGAGEMENT",
        llm_guidance="고객 반응이 끊겼거나 연락이 닿지 않는 맥락이면 NO_RESPONSE를 사용한다.",
    ),
    "COMPARING_OPTIONS": OntologyConcept(
        code="COMPARING_OPTIONS",
        label="대안 비교",
        description="다른 서비스나 매장과 비교 중이라 결정이 보류된 상태",
        keywords=("비교", "다른 곳", "타 센터", "compare", "option"),
        priority_score=70,
        default_action_code="COMPARISON_SUPPORT",
        category_code="DECISION",
        llm_guidance="다른 선택지와 비교 중이면 COMPARING_OPTIONS를 사용한다.",
    ),
    "NEEDS_FOLLOW_UP": OntologyConcept(
        code="NEEDS_FOLLOW_UP",
        label="후속 확인 필요",
        description="명확한 미전환 사유가 없어 추가 확인이 필요한 상태",
        keywords=("후속", "확인", "관심", "follow"),
        priority_score=65,
        default_action_code="GENERAL_FOLLOW_UP",
        category_code="ENGAGEMENT",
        llm_guidance="뚜렷한 미전환 사유를 특정하기 어려우면 NEEDS_FOLLOW_UP을 사용한다.",
    ),
}


LEAD_TEMPERATURE_CONCEPTS: dict[str, OntologyConcept] = {
    "HOT": OntologyConcept(
        code="HOT",
        label="높은 전환 가능성",
        description="등록했거나 체험/방문 의사가 매우 구체적인 상태",
        keywords=("등록", "체험 예약", "방문 확정", "hot"),
        priority_score=90,
        llm_guidance="등록 또는 체험 예약처럼 전환 행동이 명확하면 HOT을 사용한다.",
    ),
    "WARM": OntologyConcept(
        code="WARM",
        label="중간 전환 가능성",
        description="관심은 있으나 가격/일정/비교 이슈로 후속 설득이 필요한 상태",
        keywords=("관심", "고민", "가격", "일정", "warm"),
        priority_score=70,
        llm_guidance="관심과 보류 사유가 함께 있으면 WARM을 사용한다.",
    ),
    "COLD": OntologyConcept(
        code="COLD",
        label="낮은 전환 가능성",
        description="관심 신호가 약하거나 명확한 후속 동기가 낮은 상태",
        keywords=("관심 낮음", "보류", "cold"),
        priority_score=40,
        llm_guidance="관심 신호가 약하고 구체적 후속 근거가 부족하면 COLD를 사용한다.",
    ),
}


VALID_CONFIDENCE_CODES = {"LOW", "MEDIUM", "HIGH"}
REASON_ALIASES = {
    "PRICE_CONCERN": "PRICE",
    "SCHEDULE_CONFLICT": "SCHEDULE",
    "FAMILY": "FAMILY_DISCUSSION",
    "FOLLOW_UP": "NEEDS_FOLLOW_UP",
}


def normalize_reason_code(value: str | None, *, allow_unknown: bool = True) -> str:
    if not value:
        if not allow_unknown:
            raise ValueError("reasonType is required")
        return "NEEDS_FOLLOW_UP"
    normalized = value.strip().upper()
    normalized = REASON_ALIASES.get(normalized, normalized)
    if normalized in REASON_CONCEPTS:
        return normalized
    if allow_unknown:
        return "NEEDS_FOLLOW_UP"
    raise ValueError(f"Unsupported reasonType: {value}")


def normalize_action_code(value: str | None, *, allow_unknown: bool = True) -> str:
    if not value:
        if not allow_unknown:
            raise ValueError("action code is required")
        return "GENERAL_FOLLOW_UP"
    normalized = value.strip().upper()
    if normalized in ACTION_CONCEPTS:
        return normalized
    if allow_unknown:
        return "GENERAL_FOLLOW_UP"
    raise ValueError(f"Unsupported action code: {value}")


def normalize_temperature_code(value: str | None, *, allow_unknown: bool = True) -> str:
    if not value:
        if not allow_unknown:
            raise ValueError("leadTemperature is required")
        return "COLD"
    normalized = value.strip().upper()
    if normalized in LEAD_TEMPERATURE_CONCEPTS:
        return normalized
    if allow_unknown:
        return "COLD"
    raise ValueError(f"Unsupported leadTemperature: {value}")


def normalize_confidence(value: str | None, *, allow_unknown: bool = True) -> str | None:
    if value is None:
        return None
    normalized = value.strip().upper()
    if normalized in VALID_CONFIDENCE_CODES:
        return normalized
    if allow_unknown:
        return "MEDIUM"
    raise ValueError(f"Unsupported confidence: {value}")


def classify_reason(text: str) -> str:
    lowered = text.lower()
    for concept in REASON_CONCEPTS.values():
        if concept.code == "NEEDS_FOLLOW_UP":
            continue
        if any(keyword.lower() in lowered for keyword in concept.keywords):
            return concept.code
    return "NEEDS_FOLLOW_UP"


def action_for_reason(reason_code: str) -> OntologyConcept:
    reason = REASON_CONCEPTS[normalize_reason_code(reason_code)]
    return ACTION_CONCEPTS[normalize_action_code(reason.default_action_code)]


def priority_for_reason(reason_code: str) -> int:
    return REASON_CONCEPTS[normalize_reason_code(reason_code)].priority_score or 65


def temperature_for_status(status: str, reason_code: str) -> str:
    if status == "REGISTERED":
        return "HOT"
    if normalize_reason_code(reason_code) in {"PRICE", "SCHEDULE", "COMPARING_OPTIONS"}:
        return "WARM"
    return "COLD"


def ontology_prompt_context() -> str:
    reason_lines = [
        f"- {item.code}: {item.label}. {item.llm_guidance}"
        for item in REASON_CONCEPTS.values()
    ]
    temperature_lines = [
        f"- {item.code}: {item.label}. {item.llm_guidance}"
        for item in LEAD_TEMPERATURE_CONCEPTS.values()
    ]
    confidence = ", ".join(sorted(VALID_CONFIDENCE_CODES))
    return (
        "Use only these ontology codes when filling controlled fields.\n"
        "reasonType:\n"
        + "\n".join(reason_lines)
        + "\nleadTemperature:\n"
        + "\n".join(temperature_lines)
        + f"\nconfidence: {confidence}"
    )


def reason_rows() -> list[dict[str, object]]:
    return [_concept_row(item) for item in REASON_CONCEPTS.values()]


def reason_category_rows() -> list[dict[str, object]]:
    return [_concept_row(item) for item in REASON_CATEGORIES.values()]


def action_rows() -> list[dict[str, object]]:
    return [_concept_row(item) for item in ACTION_CONCEPTS.values()]


def temperature_rows() -> list[dict[str, object]]:
    return [_concept_row(item) for item in LEAD_TEMPERATURE_CONCEPTS.values()]


def _concept_row(concept: OntologyConcept) -> dict[str, object]:
    return {
        "id": concept.code,
        "code": concept.code,
        "label": concept.label,
        "description": concept.description,
        "keywords": list(concept.keywords),
        "priorityScore": concept.priority_score,
        "defaultActionCode": concept.default_action_code,
        "categoryCode": concept.category_code,
        "llmGuidance": concept.llm_guidance,
        "title": concept.title,
        "actionDescription": concept.action_description,
    }
