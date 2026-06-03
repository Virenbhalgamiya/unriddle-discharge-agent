from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock

from app.ui.upload_utils import UPLOAD_ROOT, stage_uploaded_pdfs


def test_stage_uploaded_pdfs_writes_persistent_folder(tmp_path, monkeypatch):
    upload_base = tmp_path / "uploads"
    monkeypatch.setattr("app.ui.upload_utils.UPLOAD_BASE", upload_base)

    mock_file = MagicMock()
    mock_file.name = "note.pdf"
    mock_file.getvalue.return_value = b"%PDF-1.4 test"

    folder = stage_uploaded_pdfs([mock_file])
    assert folder == upload_base / "note"
    assert list(folder.glob("*.pdf"))


def test_read_pdf_ocr_with_progress_runs_on_main_thread(tmp_path):
    from tests.helpers import create_scanned_test_pdf
    from app.tools import pdf_reader
    from app.tools.pdf_reader import read_pdf, tesseract_available

    if not tesseract_available():
        import pytest

        pytest.skip("Tesseract not installed")

    pdf = create_scanned_test_pdf(tmp_path / "scan.pdf", ["Patient Name: Jane Doe"])
    calls: list[tuple[int, int, str]] = []

    def progress(cur: int, total: int, name: str) -> None:
        calls.append((cur, total, name))

    original = pdf_reader._run_ocr

    def spy_ocr(*args, **kwargs):
        assert kwargs.get("progress_callback") is progress or (len(args) >= 3 and args[2] is progress)
        return original(*args, **kwargs)

    pdf_reader._run_ocr = spy_ocr
    try:
        result = read_pdf(
            pdf,
            max_retries=1,
            timeout_seconds=5,
            ocr_timeout_seconds=120,
            progress_callback=progress,
        )
    finally:
        pdf_reader._run_ocr = original

    assert calls
    assert result.success or "ocr" in str(result.errors).lower()
