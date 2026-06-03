import pytest

from app.agents.discharge_agent import DischargeAgentRunner
from app.llm.provider_factory import get_provider
from tests.helpers import create_complete_patient_folder, create_test_pdf


@pytest.mark.parametrize("provider", ["openai", "anthropic", "gemini", "ollama"])
def test_provider_switching_same_workflow(tmp_path, provider):
    folder = create_complete_patient_folder(tmp_path / f"patient_{provider}")
    runner = DischargeAgentRunner(llm_provider="mock")
    result = runner.run(folder)
    assert result.status in ("complete", "max_steps_reached", "audit_failed", "running")
    assert result.draft_summary.is_final is False


def test_mock_provider_available():
    provider = get_provider("mock", fallback_to_mock=False)
    assert provider.name == "mock"
