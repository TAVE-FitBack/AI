from fitback_ai.ontology import (
    ACTION_CONCEPTS,
    LEAD_TEMPERATURE_CONCEPTS,
    REASON_CATEGORIES,
    REASON_CONCEPTS,
    classify_reason,
    normalize_reason_code,
)


def test_ontology_codes_are_unique_and_complete():
    assert set(REASON_CONCEPTS) == {
        "PRICE",
        "SCHEDULE",
        "FAMILY_DISCUSSION",
        "NO_RESPONSE",
        "COMPARING_OPTIONS",
        "NEEDS_FOLLOW_UP",
    }
    assert set(ACTION_CONCEPTS) == {
        "BUDGET_OPTION_GUIDE",
        "SCHEDULE_RECONFIRM",
        "DECISION_SUMMARY_SEND",
        "RESPONSE_REMINDER",
        "COMPARISON_SUPPORT",
        "GENERAL_FOLLOW_UP",
    }
    assert set(LEAD_TEMPERATURE_CONCEPTS) == {"HOT", "WARM", "COLD"}


def test_each_reason_has_valid_category_and_default_action():
    for reason in REASON_CONCEPTS.values():
        assert reason.category_code in REASON_CATEGORIES
        assert reason.default_action_code in ACTION_CONCEPTS
        assert reason.priority_score is not None


def test_reason_classification_uses_keywords_and_fallback():
    assert classify_reason("가격이 부담돼서 예산을 다시 봐야 합니다.") == "PRICE"
    assert classify_reason("방문 시간이 안 맞아서 일정을 다시 잡고 싶어요.") == "SCHEDULE"
    assert classify_reason("아직 더 확인이 필요합니다.") == "NEEDS_FOLLOW_UP"


def test_legacy_reason_aliases_normalize_to_ontology_codes():
    assert normalize_reason_code("PRICE_CONCERN") == "PRICE"
    assert normalize_reason_code("SCHEDULE_CONFLICT") == "SCHEDULE"
    assert normalize_reason_code("unknown") == "NEEDS_FOLLOW_UP"
