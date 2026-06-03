from app.evaluation.summary_rubric import evaluate_summary_quality
from app.models.summary_models import DischargeSummaryDraft, SectionStatus, SummarySection


def test_rubric_penalizes_semicolon_dump():
    draft = DischargeSummaryDraft(
        patient_id="t",
        sections=[
            SummarySection(name="Hospital Course", status=SectionStatus.PRESENT, content="A; B; C"),
        ],
        executive_summary="",
    )
    result = evaluate_summary_quality(draft, [])
    assert result["readability"] < 100
    assert any("semicolon" in i for i in result["issues"])


def test_rubric_rewards_executive_summary():
    draft = DischargeSummaryDraft(
        patient_id="t",
        is_final=False,
        sections=[
            SummarySection(name="Patient Demographics", status=SectionStatus.PRESENT, content="John Doe (DOB 01/01/1970)."),
            SummarySection(name="Principal Diagnosis", status=SectionStatus.PRESENT, content="Principal diagnosis: Pneumonia."),
            SummarySection(name="Hospital Course", status=SectionStatus.PRESENT, content="The patient was treated with antibiotics and improved during the hospital stay."),
            SummarySection(name="Discharge Medications", status=SectionStatus.PRESENT, content="- Lisinopril 10mg"),
            SummarySection(name="Allergies", status=SectionStatus.PRESENT, content="Documented allergies: NKDA."),
        ],
        executive_summary="John Doe was hospitalized for pneumonia, treated with antibiotics, and discharged stable with outpatient follow-up planned.",
    )
    result = evaluate_summary_quality(draft, [])
    assert result["overall_score"] >= 70
