from app.agents.auditor import AuditorAgent
from app.models.evidence import EvidenceItem


def test_unsupported_fact_rejection():
    auditor = AuditorAgent()
    state = {
        "evidence_store": [
            EvidenceItem(
                value="Fabricated Diagnosis",
                source_document="a.pdf",
                page_number=1,
                field_name="principal_diagnosis",
                source_text="Actual text without fabricated",
            ).model_dump(mode="json")
        ],
        "page_text_cache": {"a.pdf": {1: "Actual text without fabricated"}},
        "conflicts": [],
        "missing_fields": [],
        "medication_changes": [],
        "completed_tasks": set(),
    }
    result = auditor.audit(state)
    assert not result["audit_passed"]


def test_conflict_reporting_validation():
    auditor = AuditorAgent()
    state = {
        "evidence_store": [],
        "page_text_cache": {},
        "conflicts": [{"field_name": "diagnosis", "values": [{"value": "A"}, {"value": "B"}]}],
        "missing_fields": [],
        "medication_changes": [],
        "completed_tasks": set(),
    }
    result = auditor.audit(state)
    assert result["audit_passed"]


def test_evidence_validation_passes():
    auditor = AuditorAgent()
    item = EvidenceItem(
        value="Pneumonia",
        source_document="a.pdf",
        page_number=1,
        field_name="principal_diagnosis",
        source_text="Diagnosis: Pneumonia",
    )
    state = {
        "evidence_store": [item.model_dump(mode="json")],
        "page_text_cache": {"a.pdf": {1: "Diagnosis: Pneumonia"}},
        "conflicts": [],
        "missing_fields": [],
        "medication_changes": [],
        "completed_tasks": set(),
    }
    result = auditor.audit(state)
    assert result["audit_passed"]
