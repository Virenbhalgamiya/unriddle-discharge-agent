from __future__ import annotations

import logging
import shutil
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

import fitz
import pdfplumber

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[int, int, str], None]

TESSERACT_WINDOWS_PATHS = (
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
)


@dataclass
class PDFPage:
    page_number: int
    text: str


@dataclass
class PDFReadResult:
    success: bool
    file_path: str
    pages: list[PDFPage] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    page_mapping: dict[int, str] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    retries: int = 0
    parser_used: str = ""


def _configure_tesseract() -> bool:
    """Return True if Tesseract binary is available for pytesseract."""
    try:
        import pytesseract
    except ImportError:
        return False

    if shutil.which("tesseract"):
        return True

    for candidate in TESSERACT_WINDOWS_PATHS:
        if Path(candidate).exists():
            pytesseract.pytesseract.tesseract_cmd = candidate
            return True

    try:
        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


def tesseract_available() -> bool:
    return _configure_tesseract()


def _read_with_pymupdf(path: Path) -> PDFReadResult:
    doc = fitz.open(str(path))
    pages: list[PDFPage] = []
    mapping: dict[int, str] = {}
    for i, page in enumerate(doc):
        text = page.get_text("text") or ""
        page_num = i + 1
        pages.append(PDFPage(page_number=page_num, text=text))
        mapping[page_num] = text
    metadata = dict(doc.metadata or {})
    doc.close()
    return PDFReadResult(
        success=True,
        file_path=str(path),
        pages=pages,
        metadata=metadata,
        page_mapping=mapping,
        parser_used="pymupdf",
    )


def _read_with_pdfplumber(path: Path) -> PDFReadResult:
    pages: list[PDFPage] = []
    mapping: dict[int, str] = {}
    with pdfplumber.open(str(path)) as pdf:
        for i, page in enumerate(pdf.pages):
            text = page.extract_text() or ""
            page_num = i + 1
            pages.append(PDFPage(page_number=page_num, text=text))
            mapping[page_num] = text
        metadata = pdf.metadata or {}
    return PDFReadResult(
        success=True,
        file_path=str(path),
        pages=pages,
        metadata=dict(metadata),
        page_mapping=mapping,
        parser_used="pdfplumber",
    )


def _read_with_ocr(
    path: Path,
    dpi_scale: float = 2.0,
    progress_callback: Optional[ProgressCallback] = None,
) -> PDFReadResult:
    if not _configure_tesseract():
        return PDFReadResult(
            success=False,
            file_path=str(path),
            errors=[
                "OCR required for scanned PDF but Tesseract is not installed. "
                "Install via: winget install UB-Mannheim.TesseractOCR"
            ],
        )

    import pytesseract
    from PIL import Image

    doc = fitz.open(str(path))
    pages: list[PDFPage] = []
    mapping: dict[int, str] = {}
    matrix = fitz.Matrix(dpi_scale, dpi_scale)
    total = len(doc)
    ocr_config = "--psm 6"

    for i, page in enumerate(doc):
        page_num = i + 1
        if progress_callback:
            progress_callback(page_num, total, path.name)

        pixmap = page.get_pixmap(matrix=matrix, alpha=False)
        img = Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)
        text = pytesseract.image_to_string(img, config=ocr_config) or ""
        pages.append(PDFPage(page_number=page_num, text=text))
        mapping[page_num] = text

    metadata = dict(doc.metadata or {})
    doc.close()

    if any(p.text.strip() for p in pages):
        return PDFReadResult(
            success=True,
            file_path=str(path),
            pages=pages,
            metadata=metadata,
            page_mapping=mapping,
            parser_used="pymupdf+ocr",
        )

    return PDFReadResult(
        success=False,
        file_path=str(path),
        pages=pages,
        metadata=metadata,
        page_mapping=mapping,
        parser_used="pymupdf+ocr",
        errors=["OCR produced no text across all pages"],
    )


def read_pdf(
    path: str | Path,
    max_retries: int = 3,
    timeout_seconds: int = 30,
    ocr_enabled: bool = True,
    ocr_dpi_scale: float = 2.0,
    ocr_timeout_seconds: int = 600,
    progress_callback: Optional[ProgressCallback] = None,
) -> PDFReadResult:
    """Read PDF with retry, timeout, fallback parser, and optional OCR for scanned pages."""
    pdf_path = Path(path)
    if not pdf_path.exists():
        return PDFReadResult(
            success=False,
            file_path=str(pdf_path),
            errors=[f"File not found: {pdf_path}"],
        )

    errors: list[str] = []
    retries = 0

    for attempt in range(max_retries):
        retries = attempt
        for parser_name, parser_fn in [
            ("pymupdf", _read_with_pymupdf),
            ("pdfplumber", _read_with_pdfplumber),
        ]:
            try:
                with ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(parser_fn, pdf_path)
                    result = future.result(timeout=timeout_seconds)
                if result.pages and any(p.text.strip() for p in result.pages):
                    result.retries = retries
                    return result
                errors.append(f"{parser_name}: empty extraction")
            except FuturesTimeoutError:
                errors.append(f"{parser_name}: timeout after {timeout_seconds}s")
            except Exception as exc:
                errors.append(f"{parser_name}: {exc}")
                logger.exception("PDF read failed with %s", parser_name)

        if ocr_enabled:
            try:
                with ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(
                        _read_with_ocr,
                        pdf_path,
                        ocr_dpi_scale,
                        progress_callback,
                    )
                    result = future.result(timeout=ocr_timeout_seconds)
                if result.success:
                    result.retries = retries
                    return result
                errors.extend(result.errors or ["ocr: empty extraction"])
            except FuturesTimeoutError:
                errors.append(f"ocr: timeout after {ocr_timeout_seconds}s")
            except Exception as exc:
                errors.append(f"ocr: {exc}")
                logger.exception("PDF OCR failed")

        time.sleep(0.3 * (attempt + 1))

    return PDFReadResult(
        success=False,
        file_path=str(pdf_path),
        errors=errors,
        retries=max_retries,
    )


def load_patient_folder(
    folder: str | Path,
    max_retries: int = 3,
    timeout_seconds: int = 30,
    ocr_enabled: bool = True,
    ocr_dpi_scale: float = 2.0,
    ocr_timeout_seconds: int = 600,
    progress_callback: Optional[ProgressCallback] = None,
) -> tuple[dict[str, PDFReadResult], list[str]]:
    folder_path = Path(folder)
    documents: dict[str, PDFReadResult] = {}
    failures: list[str] = []

    if not folder_path.exists():
        return documents, [f"Patient folder not found: {folder_path}"]

    pdf_files = sorted(folder_path.glob("*.pdf"))
    if not pdf_files:
        return documents, [f"No PDF files in {folder_path}"]

    for pdf in pdf_files:
        file_callback: Optional[ProgressCallback] = None
        if progress_callback:
            file_callback = lambda cur, total, name=pdf.name, fn=progress_callback: fn(cur, total, name)
        result = read_pdf(
            pdf,
            max_retries=max_retries,
            timeout_seconds=timeout_seconds,
            ocr_enabled=ocr_enabled,
            ocr_dpi_scale=ocr_dpi_scale,
            ocr_timeout_seconds=ocr_timeout_seconds,
            progress_callback=file_callback,
        )
        documents[pdf.name] = result
        if not result.success:
            failures.append(f"{pdf.name}: {'; '.join(result.errors)}")

    return documents, failures
