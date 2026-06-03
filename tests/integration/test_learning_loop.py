from app.evaluation.metrics import compute_reward
from app.evaluation.simulated_doctor import SimulatedDoctor
from app.models.summary_models import DischargeSummaryDraft, SummarySection, SectionStatus


def test_learning_loop():
    draft = DischargeSummaryDraft(
        patient_id="p1",
        sections=[
            SummarySection(name="Hospital Course", status=SectionStatus.PRESENT, content="Pt with HTN."),
            SummarySection(name="Pending Results", status=SectionStatus.PENDING, content="Culture pending"),
        ],
    )
    doctor = SimulatedDoctor()
    original, edited = doctor.generate_pair(draft)
    metrics = compute_reward(original, edited)
    assert "composite_reward" in metrics
    assert metrics["composite_reward"] >= 0
