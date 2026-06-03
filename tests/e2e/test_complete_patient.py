from app.agents.discharge_agent import DischargeAgentRunner
from tests.helpers import create_complete_patient_folder


def test_full_agent_run(tmp_path):
    folder = create_complete_patient_folder(tmp_path / "complete_patient")
    runner = DischargeAgentRunner(llm_provider="mock")
    result = runner.run(folder)
    assert result.draft_summary.is_final is False
    assert result.draft_summary.banner
    assert result.trace_log
    assert result.output_dir


def test_trace_generated(tmp_path):
    folder = create_complete_patient_folder(tmp_path / "patient")
    runner = DischargeAgentRunner(llm_provider="mock")
    result = runner.run(folder)
    assert result.trace_paths.get("json")
    assert result.trace_paths.get("txt")
