import time

import pytest

from app.agents.discharge_agent import DischargeAgentRunner
from tests.helpers import create_test_pdf


def test_large_pdf_folder(tmp_path):
    folder = tmp_path / "large_patient"
    folder.mkdir()
    for i in range(22):
        create_test_pdf(
            folder / f"progress_note_{i}.pdf",
            [f"Progress note {i}", "Patient stable.", "Medications: Aspirin 81mg PO daily"],
        )
    create_test_pdf(folder / "admission_note.pdf", ["Patient Name: Load Test", "Admission Date: 01/01/2026"])
    create_test_pdf(folder / "medication_admission.pdf", ["Medications:", "- Aspirin 81mg PO daily"])
    create_test_pdf(folder / "medication_discharge.pdf", ["Medications:", "- Aspirin 81mg PO daily"])

    start = time.time()
    runner = DischargeAgentRunner(llm_provider="mock")
    result = runner.run(folder)
    elapsed = time.time() - start

    assert result.draft_summary
    assert elapsed < 120
    tool_steps = [s for s in result.trace_log if s.tool_name not in ("planner", "auditor")]
    assert len(tool_steps) <= 20
