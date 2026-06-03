from app.agents.draft_builder import build_draft_summary
from app.agents.narrative_synthesizer import (
    build_narrative_document,
    polish_section_content,
)
from app.models.constants import MISSING_LITERAL, PENDING_LITERAL
from app.models.summary_models import SectionStatus, SummarySection


def test_hospital_course_deduplicates_redundant_progress():
    content = polish_section_content(
        "Hospital Course",
        SectionStatus.PRESENT,
        [
            "Patient treated with antibiotics and improved.",
            "Patient improving.",
        ],
        {},
    )
    assert "antibiotics" in content.lower()
    assert content.lower().count("improv") == 1


def test_demographics_from_plain_evidence_values():
    content = polish_section_content(
        "Patient Demographics",
        SectionStatus.PRESENT,
        ["John Doe", "01/15/1970"],
        {},
    )
    assert "John Doe (DOB 01/15/1970)" in content


def test_missing_literal_preserved():
    content = polish_section_content("Allergies", SectionStatus.MISSING, [], {})
    assert content == MISSING_LITERAL


def test_pending_literal_preserved():
    content = polish_section_content(
        "Pending Results",
        SectionStatus.PENDING,
        ["Culture pending"],
        {},
    )
    assert "Culture pending" in content
    assert PENDING_LITERAL in content


def test_build_draft_includes_narrative_summary():
    state = {
        "patient_id": "test",
        "evidence_store": [
            {
                "id": "1",
                "field_name": "patient_name",
                "value": "Jane Smith",
                "source_document": "a.pdf",
                "page_number": 1,
                "source_text": "Name: Jane Smith",
            },
            {
                "id": "2",
                "field_name": "principal_diagnosis",
                "value": "CHF",
                "source_document": "a.pdf",
                "page_number": 1,
                "source_text": "Diagnosis: CHF",
            },
        ],
        "missing_fields": ["admission_date", "discharge_date", "medications", "allergies", "follow_up_instructions", "discharge_condition"],
        "conflicts": [],
        "pending_results": [],
        "medication_changes": [],
        "safety_flags": [],
        "clinician_review_items": [],
        "llm_provider": "mock",
        "config": {"narrative": {"llm_enhance": False}},
    }
    draft = build_draft_summary(state)
    assert draft.narrative_summary
    assert "Jane Smith" in draft.narrative_summary
    demo = next(s for s in draft.sections if s.name == "Patient Demographics")
    assert "Jane Smith" in demo.content


def test_narrative_document_skips_internal_sections():
    sections = [
        SummarySection(name="Principal Diagnosis", status=SectionStatus.PRESENT, content="Principal diagnosis: CHF."),
        SummarySection(name="Safety Flags", status=SectionStatus.PRESENT, content="flag"),
    ]
    doc = build_narrative_document(sections)
    assert "Principal Diagnosis" in doc
    assert "Safety Flags" not in doc
