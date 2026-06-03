import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


@pytest.fixture
def project_root():
    return ROOT


@pytest.fixture
def config_path(project_root):
    return project_root / "config" / "config.yaml"


@pytest.fixture
def sample_evidence():
    from app.models.evidence import EvidenceItem

    return EvidenceItem(
        value="Pneumonia",
        source_document="admission_note.pdf",
        page_number=1,
        field_name="principal_diagnosis",
        confidence=1.0,
    )


@pytest.fixture
def empty_state():
    from app.models.agent_state import create_initial_state

    return create_initial_state(patient_id="test_patient", patient_folder=str(ROOT / "fixtures"))


def pytest_configure(config):
    config.addinivalue_line("markers", "live: real API tests")
    config.addinivalue_line("markers", "e2e: requires fixture PDFs")


def has_fixture_pdfs(folder: Path) -> bool:
    if not folder.exists():
        return False
    pdfs = list(folder.glob("*.pdf"))
    return len(pdfs) > 0


@pytest.fixture
def skip_if_no_pdfs(project_root):
    def _skip(folder_name: str):
        folder = project_root / "fixtures" / "patient_folders" / folder_name
        if not has_fixture_pdfs(folder):
            pytest.skip(f"No PDFs in {folder}")
        return folder

    return _skip
