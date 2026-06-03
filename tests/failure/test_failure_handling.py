from unittest.mock import patch

import pytest

from app.agents.discharge_agent import DischargeAgentRunner
from app.llm.provider_factory import get_provider
from app.memory.correction_memory import CorrectionMemory
from app.tools.tool_registry import execute_tool
from tests.helpers import create_complete_patient_folder, create_test_pdf


def test_corrupted_pdf_graceful(tmp_path):
    folder = tmp_path / "patient"
    folder.mkdir()
    (folder / "bad.pdf").write_bytes(b"corrupt")
    state = {"patient_folder": str(folder), "config": {}, "clinician_review_items": [], "safety_flags": []}
    result = execute_tool("load_documents", state)
    assert result["loaded_documents"]["bad.pdf"]["success"] is False


def test_missing_pdf_folder():
    state = {"patient_folder": "/nonexistent/path", "config": {}, "clinician_review_items": [], "safety_flags": []}
    result = execute_tool("load_documents", state)
    assert result["loaded_documents"] == {}


def test_tool_crash_handled(tmp_path):
    folder = create_complete_patient_folder(tmp_path / "patient")
    state = {"patient_folder": str(folder), "config": {}, "clinician_review_items": [], "safety_flags": []}
    with patch("app.tools.tool_registry.run_extract_fields", side_effect=RuntimeError("crash")):
        from app.tools.tool_registry import TOOL_REGISTRY

        original = TOOL_REGISTRY["extract_fields"]
        TOOL_REGISTRY["extract_fields"] = lambda s, m=None: (_ for _ in ()).throw(RuntimeError("crash"))
        try:
            result = execute_tool("extract_fields", state)
            assert "error" in result
        finally:
            TOOL_REGISTRY["extract_fields"] = original


def test_llm_unavailable_fallback():
    provider = get_provider("mock", fallback_to_mock=False)
    response = provider.complete([])
    assert response.content


def test_db_unavailable_creates_path(tmp_path):
    db_path = tmp_path / "nested" / "mem.db"
    memory = CorrectionMemory(str(db_path))
    memory.store_escalation("test", "details")
    assert db_path.exists()
