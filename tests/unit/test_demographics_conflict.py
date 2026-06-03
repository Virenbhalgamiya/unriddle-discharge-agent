from app.tools.conflict_detector import detect_conflicts


def test_demographics_complementary_not_conflict():
    evidence = [
        {"field_name": "patient_name", "value": "John Doe", "source_document": "a.pdf", "page_number": 1, "id": "1"},
        {"field_name": "patient_dob", "value": "01/15/1970", "source_document": "a.pdf", "page_number": 1, "id": "2"},
    ]
    conflicts, _, _, _ = detect_conflicts(evidence)
    assert conflicts == []


def test_conflicting_patient_names():
    evidence = [
        {"field_name": "patient_name", "value": "John Doe", "source_document": "a.pdf", "page_number": 1, "id": "1"},
        {"field_name": "patient_name", "value": "Jane Doe", "source_document": "b.pdf", "page_number": 1, "id": "2"},
    ]
    conflicts, _, _, _ = detect_conflicts(evidence)
    assert len(conflicts) == 1
