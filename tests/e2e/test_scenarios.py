from app.agents.discharge_agent import DischargeAgentRunner
from tests.helpers import create_test_pdf


def test_missing_records(tmp_path):
    folder = tmp_path / "missing_patient"
    folder.mkdir()
    create_test_pdf(folder / "admission_note.pdf", ["Patient Name: Jane Doe", "Admission Date: 03/01/2026"])
    create_test_pdf(folder / "medication_admission.pdf", ["Medications:", "- Aspirin 81mg PO daily"])
    create_test_pdf(folder / "medication_discharge.pdf", ["Medications:", "- Aspirin 81mg PO daily"])

    runner = DischargeAgentRunner(llm_provider="mock")
    result = runner.run(folder)
    assert result.draft_summary
    assert any("MISSING" in s.content for s in result.draft_summary.sections)


def test_conflicting_diagnoses(tmp_path):
    folder = tmp_path / "conflict_patient"
    folder.mkdir()
    create_test_pdf(folder / "admission_note.pdf", ["Principal Diagnosis: Pneumonia", "Admission Date: 03/01/2026"])
    create_test_pdf(folder / "progress_note_1.pdf", ["Principal Diagnosis: Bronchitis"])
    create_test_pdf(folder / "medication_admission.pdf", ["Medications:", "- Aspirin 81mg PO daily"])
    create_test_pdf(folder / "medication_discharge.pdf", ["Medications:", "- Aspirin 81mg PO daily"])

    runner = DischargeAgentRunner(llm_provider="mock")
    result = runner.run(folder)
    assert result.conflicts or any("CONFLICT" in s.content for s in result.draft_summary.sections)


def test_pending_labs(tmp_path):
    folder = tmp_path / "pending_patient"
    folder.mkdir()
    create_test_pdf(
        folder / "admission_note.pdf",
        ["Patient Name: John", "Admission Date: 03/01/2026", "Discharge Date: 03/05/2026",
         "Principal Diagnosis: UTI", "Allergies: NKDA", "Follow-up: PCP", "Discharge Condition: Stable"],
    )
    create_test_pdf(folder / "labs.pdf", ["Blood culture pending"])
    create_test_pdf(folder / "medication_admission.pdf", ["Medications:", "- Aspirin 81mg PO daily"])
    create_test_pdf(folder / "medication_discharge.pdf", ["Medications:", "- Aspirin 81mg PO daily"])

    runner = DischargeAgentRunner(llm_provider="mock")
    result = runner.run(folder)
    assert result.pending_results or any(s.name == "Pending Results" for s in result.draft_summary.sections)


def test_no_hallucination_banner(tmp_path):
    folder = tmp_path / "patient"
    folder.mkdir()
    create_test_pdf(folder / "admission_note.pdf", ["Patient Name: Test", "Admission Date: 01/01/2026"])
    create_test_pdf(folder / "medication_admission.pdf", ["Medications:", "- Med A"])
    create_test_pdf(folder / "medication_discharge.pdf", ["Medications:", "- Med A"])

    runner = DischargeAgentRunner(llm_provider="mock")
    result = runner.run(folder)
    assert result.draft_summary.is_final is False
    assert "DRAFT" in result.draft_summary.banner
