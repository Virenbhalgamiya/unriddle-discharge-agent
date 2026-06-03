from app.agents.auditor import AuditorAgent
from app.agents.draft_builder import build_draft_summary
from app.models.constants import CONFLICT_LITERAL, MISSING_LITERAL
from app.models.evidence import EvidenceItem


def test_missing_diagnosis_marked():
    state = {
        "patient_id": "p1",
        "evidence_store": [],
        "missing_fields": ["principal_diagnosis"],
        "conflicts": [],
        "pending_results": [],
        "safety_flags": [],
        "clinician_review_items": [],
        "medication_changes": [],
    }
    draft = build_draft_summary(state)
    diag = next(s for s in draft.sections if s.name == "Principal Diagnosis")
    assert MISSING_LITERAL in diag.content


def test_conflict_preserved():
    state = {
        "patient_id": "p1",
        "evidence_store": [
            EvidenceItem(value="A", source_document="a.pdf", page_number=1, field_name="principal_diagnosis").model_dump(mode="json")
        ],
        "missing_fields": [],
        "conflicts": [{"field_name": "principal_diagnosis", "message": CONFLICT_LITERAL, "values": []}],
        "pending_results": [],
        "safety_flags": [],
        "clinician_review_items": [],
        "medication_changes": [],
    }
    draft = build_draft_summary(state)
    diag = next(s for s in draft.sections if s.name == "Principal Diagnosis")
    assert CONFLICT_LITERAL in diag.content


def test_auditor_blocks_hallucination():
    auditor = AuditorAgent()
    state = {
        "evidence_store": [
            EvidenceItem(
                value="Fake Med",
                source_document="a.pdf",
                page_number=1,
                field_name="discharge_medications",
                source_text="No medications listed",
            ).model_dump(mode="json")
        ],
        "page_text_cache": {"a.pdf": {1: "No medications listed"}},
        "conflicts": [],
        "missing_fields": [],
        "medication_changes": [],
        "completed_tasks": set(),
    }
    assert not auditor.audit(state)["audit_passed"]
