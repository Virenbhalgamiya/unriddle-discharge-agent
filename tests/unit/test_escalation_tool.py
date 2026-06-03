from app.memory.correction_memory import CorrectionMemory
from app.tools.escalation_tool import flag_for_clinician_review


def test_escalation_creation(tmp_path):
    memory = CorrectionMemory(tmp_path / "test.db")
    review, flag, record = flag_for_clinician_review(
        reason="Missing data",
        details="Diagnosis missing",
        section="diagnosis",
        priority="high",
        memory=memory,
    )
    assert review.reason == "Missing data"
    assert flag.severity == "high"
    assert record["details"] == "Diagnosis missing"


def test_escalation_persistence(tmp_path):
    memory = CorrectionMemory(tmp_path / "test.db")
    flag_for_clinician_review("Conflict", "Date mismatch", memory=memory)
    escalations = memory.get_escalations()
    assert len(escalations) == 1
    assert escalations[0]["reason"] == "Conflict"
