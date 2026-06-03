from app.tools.medication_reconciliation import reconcile_medications


def _loaded(text=""):
    return {"notes.pdf": {"page_mapping": {1: text}}}


def test_medication_added():
    evidence = [
        {"field_name": "admission_medications", "value": "Aspirin 81mg PO daily", "id": "1"},
        {"field_name": "discharge_medications", "value": "Aspirin 81mg PO daily", "id": "2"},
        {"field_name": "discharge_medications", "value": "Warfarin 5mg PO daily", "id": "3"},
    ]
    changes, report, _, _ = reconcile_medications(evidence, _loaded())
    types = [c.change_type.value for c in report.changes]
    assert "Added" in types


def test_medication_removed():
    evidence = [
        {"field_name": "admission_medications", "value": "Aspirin 81mg PO daily", "id": "1"},
        {"field_name": "discharge_medications", "value": "Warfarin 5mg PO daily", "id": "2"},
    ]
    _, report, _, _ = reconcile_medications(evidence, _loaded())
    types = [c.change_type.value for c in report.changes]
    assert "Removed" in types


def test_dose_changed():
    evidence = [
        {"field_name": "admission_medications", "value": "Lisinopril 10mg PO daily", "id": "1"},
        {"field_name": "discharge_medications", "value": "Lisinopril 20mg PO daily", "id": "2"},
    ]
    _, report, _, _ = reconcile_medications(evidence, _loaded())
    assert any(c.change_type.value == "Dose Changed" for c in report.changes)


def test_frequency_changed():
    evidence = [
        {"field_name": "admission_medications", "value": "Metformin 500mg PO daily", "id": "1"},
        {"field_name": "discharge_medications", "value": "Metformin 500mg PO BID", "id": "2"},
    ]
    _, report, _, _ = reconcile_medications(evidence, _loaded())
    assert any(c.change_type.value == "Frequency Changed" for c in report.changes)


def test_route_changed():
    evidence = [
        {"field_name": "admission_medications", "value": "Morphine 10mg PO daily", "id": "1"},
        {"field_name": "discharge_medications", "value": "Morphine 10mg IV daily", "id": "2"},
    ]
    _, report, _, _ = reconcile_medications(evidence, _loaded())
    assert any(c.change_type.value == "Route Changed" for c in report.changes)
