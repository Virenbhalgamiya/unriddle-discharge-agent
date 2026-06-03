from app.tools.conflict_detector import detect_conflicts


def test_diagnosis_conflict():
    evidence = [
        {"field_name": "principal_diagnosis", "value": "Pneumonia", "source_document": "a.pdf", "page_number": 1, "id": "1"},
        {"field_name": "principal_diagnosis", "value": "Bronchitis", "source_document": "b.pdf", "page_number": 1, "id": "2"},
    ]
    conflicts, reports, reviews, flags = detect_conflicts(evidence)
    assert len(conflicts) == 1
    assert len(reports[0].values) >= 2


def test_discharge_date_conflict():
    evidence = [
        {"field_name": "discharge_date", "value": "03/05/2026", "source_document": "a.pdf", "page_number": 1, "id": "1"},
        {"field_name": "discharge_date", "value": "03/06/2026", "source_document": "b.pdf", "page_number": 1, "id": "2"},
    ]
    conflicts, _, _, _ = detect_conflicts(evidence)
    assert len(conflicts) == 1


def test_medication_conflict_not_checked():
    evidence = [
        {"field_name": "admission_medications", "value": "Aspirin", "source_document": "a.pdf", "page_number": 1, "id": "1"},
        {"field_name": "discharge_medications", "value": "Warfarin", "source_document": "b.pdf", "page_number": 1, "id": "2"},
    ]
    conflicts, _, _, _ = detect_conflicts(evidence)
    assert conflicts == []
