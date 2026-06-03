from app.agents.narrative_agent import NarrativeSynthesisAgent
from app.models.summary_models import DischargeSummaryDraft, SectionStatus, SummarySection


def test_narrative_agent_generates_executive_summary():
    draft = DischargeSummaryDraft(
        patient_id="demo",
        is_final=False,
        sections=[
            SummarySection(name="Patient Demographics", status=SectionStatus.PRESENT, content="John Doe (DOB 01/15/1970)."),
            SummarySection(name="Admission Date", status=SectionStatus.PRESENT, content="03/01/2026"),
            SummarySection(name="Discharge Date", status=SectionStatus.PRESENT, content="03/05/2026"),
            SummarySection(name="Principal Diagnosis", status=SectionStatus.PRESENT, content="Principal diagnosis: Pneumonia."),
            SummarySection(name="Hospital Course", status=SectionStatus.PRESENT, content="Patient treated with antibiotics."),
            SummarySection(name="Discharge Condition", status=SectionStatus.PRESENT, content="Patient discharged in stable condition."),
            SummarySection(name="Follow-up Instructions", status=SectionStatus.PRESENT, content="Follow-up plan: PCP in 1 week."),
        ],
    )
    state = {
        "llm_provider": "mock",
        "config": {"narrative": {"llm_enhance": False}},
        "evidence_store": [
            {"field_name": "hospital_course", "value": "Patient treated with antibiotics and improved."},
            {"field_name": "hospital_course", "value": "Patient improving."},
        ],
        "medication_changes": [],
    }
    agent = NarrativeSynthesisAgent()
    refined, meta = agent.refine(draft, state)
    assert refined.executive_summary
    assert refined.narrative_summary
    assert refined.quality_score > 0
    assert meta["quality"]["overall_score"] > 0
