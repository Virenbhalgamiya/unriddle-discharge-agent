from app.tools.interaction_checker import check_interactions


def test_high_severity_escalation():
    evidence = [
        {"field_name": "discharge_medications", "value": "Warfarin 5mg PO daily"},
        {"field_name": "discharge_medications", "value": "Aspirin 81mg PO daily"},
    ]
    output, interactions, reviews, flags = check_interactions(evidence)
    assert any(i.severity == "High" for i in interactions)
    assert any(f.severity == "critical" for f in flags)
    assert reviews


def test_no_interaction_single_med():
    evidence = [{"field_name": "discharge_medications", "value": "Lisinopril 10mg PO daily"}]
    output, interactions, _, _ = check_interactions(evidence)
    assert interactions == []
