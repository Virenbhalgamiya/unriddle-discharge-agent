from app.tools.missing_data_detector import detect_missing_fields


def test_all_fields_present():
    evidence = [
        {"field_name": "patient_demographics", "value": "John Doe"},
        {"field_name": "admission_date", "value": "03/01/2026"},
        {"field_name": "discharge_date", "value": "03/05/2026"},
        {"field_name": "principal_diagnosis", "value": "Pneumonia"},
        {"field_name": "admission_medications", "value": "Aspirin"},
        {"field_name": "allergies", "value": "NKDA"},
        {"field_name": "follow_up_instructions", "value": "PCP 1 week"},
        {"field_name": "discharge_condition", "value": "Stable"},
    ]
    missing, flags, reviews = detect_missing_fields(evidence)
    assert missing == []


def test_missing_diagnosis():
    evidence = [{"field_name": "patient_demographics", "value": "John Doe"}]
    missing, flags, reviews = detect_missing_fields(evidence)
    assert "principal_diagnosis" in missing
    assert len(flags) > 0


def test_missing_discharge_date():
    evidence = [{"field_name": "admission_date", "value": "03/01/2026"}]
    missing, _, _ = detect_missing_fields(evidence)
    assert "discharge_date" in missing


def test_missing_allergies():
    evidence = [{"field_name": "principal_diagnosis", "value": "Pneumonia"}]
    missing, _, _ = detect_missing_fields(evidence)
    assert "allergies" in missing
