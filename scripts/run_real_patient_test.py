#!/usr/bin/env python3
"""Smoke test for the reviewer scanned PDF (fixtures/patient_real/)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.agents.discharge_agent import run_discharge_agent
from app.tools.pdf_reader import load_patient_folder, tesseract_available

REAL_FOLDER = ROOT / "fixtures" / "patient_real"
DOWNLOAD_CANDIDATES = [
    Path(r"C:\Users\Viren\Downloads\patient 2 (1).pdf"),
    REAL_FOLDER / "patient 2 (1).pdf",
]


def _resolve_pdf_folder() -> Path:
    REAL_FOLDER.mkdir(parents=True, exist_ok=True)
    pdfs = list(REAL_FOLDER.glob("*.pdf"))
    if pdfs:
        return REAL_FOLDER

    for candidate in DOWNLOAD_CANDIDATES:
        if candidate.exists():
            target = REAL_FOLDER / candidate.name
            if not target.exists():
                target.write_bytes(candidate.read_bytes())
            return REAL_FOLDER

    raise FileNotFoundError(
        "No PDF in fixtures/patient_real/. Copy patient 2 (1).pdf per fixtures/patient_real/README.md"
    )


def main() -> int:
    folder = _resolve_pdf_folder()
    pdf_files = sorted(folder.glob("*.pdf"))
    print(f"Testing folder: {folder} ({len(pdf_files)} PDF(s))")

    if not tesseract_available():
        print("WARNING: Tesseract not installed — OCR will fail for scanned PDFs.")
        print("Install: winget install UB-Mannheim.TesseractOCR")

    documents, failures = load_patient_folder(folder)
    if failures:
        print("PDF load failures:", failures)
        return 1

    for name, result in documents.items():
        total_chars = sum(len(t.strip()) for t in result.page_mapping.values())
        print(f"  {name}: parser={result.parser_used}, pages={len(result.pages)}, chars={total_chars}")
        if "ocr" not in result.parser_used and total_chars == 0:
            print("ERROR: scanned PDF produced no text and OCR was not used")
            return 1
        if total_chars == 0:
            print("ERROR: no text extracted after OCR")
            return 1

    print("Running discharge agent (mock provider for deterministic smoke test)...")
    result = run_discharge_agent(folder, llm_provider="mock")
    evidence_count = len(result.evidence_store.items)
    quality = result.draft_summary.quality_score or 0

    print(f"Status: {result.status}")
    print(f"Evidence items: {evidence_count}")
    print(f"Quality score: {quality}")
    print(f"Executive summary present: {bool(result.draft_summary.executive_summary)}")

    report = {
        "patient_id": result.patient_id,
        "status": result.status,
        "parser_used": next(iter(documents.values())).parser_used,
        "evidence_count": evidence_count,
        "quality_score": quality,
        "has_executive_summary": bool(result.draft_summary.executive_summary),
        "output_dir": result.output_dir,
    }
    out = ROOT / "outputs" / "real_patient_test_report.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Report written to {out}")

    if evidence_count < 3:
        print("FAIL: expected at least 3 evidence items")
        return 1
    if not result.draft_summary.executive_summary:
        print("FAIL: expected executive summary")
        return 1

    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
