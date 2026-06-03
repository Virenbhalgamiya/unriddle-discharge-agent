from app.agents.planner import PlannerAgent
from app.models.agent_state import create_initial_state
from app.tools.tool_registry import execute_tool


def test_planner_selects_load_documents():
    state = create_initial_state("p1", "/tmp/patient")
    planner = PlannerAgent()
    plan = planner.plan(state)
    assert plan["next_tool"] == "load_documents"


def test_execute_load_documents(tmp_path):
    from tests.helpers import create_complete_patient_folder

    folder = create_complete_patient_folder(tmp_path / "patient")
    state = create_initial_state("patient", str(folder))
    result = execute_tool("load_documents", state)
    assert "admission_note.pdf" in result["loaded_documents"]
