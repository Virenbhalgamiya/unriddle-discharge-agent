from pathlib import Path

import pytest

from tests.helpers import create_test_pdf


def test_successful_extraction(tmp_path):
    from app.tools.pdf_reader import read_pdf

    pdf = create_test_pdf(tmp_path / "test.pdf", ["Patient Name: Jane Doe", "Diagnosis: Flu"])
    result = read_pdf(pdf)
    assert result.success
    assert result.pages
    assert "Jane Doe" in result.page_mapping[1]


def test_empty_pdf(tmp_path):
    from app.tools.pdf_reader import read_pdf

    pdf = tmp_path / "empty.pdf"
    pdf.write_bytes(b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF")
    result = read_pdf(pdf, max_retries=1, timeout_seconds=5, ocr_enabled=False)
    assert not result.success or not any(p.text.strip() for p in result.pages)


def test_corrupted_pdf(tmp_path):
    from app.tools.pdf_reader import read_pdf

    pdf = tmp_path / "bad.pdf"
    pdf.write_bytes(b"not a pdf")
    result = read_pdf(pdf, max_retries=1, timeout_seconds=5, ocr_enabled=False)
    assert not result.success


def test_missing_file():
    from app.tools.pdf_reader import read_pdf

    result = read_pdf("/nonexistent/file.pdf", max_retries=1)
    assert not result.success
    assert "not found" in result.errors[0].lower()


@pytest.mark.slow
def test_ocr_scanned_pdf(tmp_path):
    from app.tools.pdf_reader import read_pdf, tesseract_available

    if not tesseract_available():
        pytest.skip("Tesseract OCR not installed")

    from tests.helpers import create_scanned_test_pdf

    pdf = create_scanned_test_pdf(
        tmp_path / "scanned.pdf",
        ["Patient Name: Jane Doe", "Principal Diagnosis: Pneumonia"],
    )
    result = read_pdf(pdf, max_retries=1, timeout_seconds=10, ocr_timeout_seconds=120)
    assert result.success
    assert "ocr" in result.parser_used
    combined = " ".join(result.page_mapping.values()).lower()
    assert "jane" in combined or "pneumonia" in combined
