from fitback_ai.mock_data import generate_records


def test_generate_records_creates_expected_count():
    payload = generate_records(100, "store-1", "batch-1")

    assert payload["recordCount"] == 100
    assert len(payload["consultationRows"]) == 100
    assert len(payload["services"]) == 3
    assert len(payload["events"]) == 3


def test_generated_records_include_manager_use_case_fields():
    row = generate_records(1, "store-1", "batch-1")["consultationRows"][0]

    assert row["customer"]["inflowPath"]
    assert row["consultation"]["rawText"]
    assert row["followUp"]["memo"]
    assert row["nonConversionReason"]["reasonType"]
    assert row["eventTarget"]["status"]
    assert row["messageTemplate"]["content"]
