"""Generate fixture PDFs and validate assignment outputs."""
from __future__ import annotations

import json
from pathlib import Path

from dotenv import load_dotenv

from app.agents.discharge_agent import run_discharge_agent
from tests.helpers import create_complete_patient_folder, create_test_pdf

load_dotenv()


def setup_missing(folder: Path) -> None:
    create_test_pdf(
        folder / "admission_note.pdf",
        ["Patient Name: Jane Doe", "Admission Date: 03/01/2026", "Allergies: NKDA"],
    )
    create_test_pdf(folder / "medication_admission.pdf", ["Medications:", "- Aspirin 81mg PO daily"])
    create_test_pdf(folder / "medication_discharge.pdf", ["Medications:", "- Aspirin 81mg PO daily"])


def setup_conflicts(folder: Path) -> None:
    create_test_pdf(
        folder / "admission_note.pdf",
        [
            "Patient Name: John",
            "Admission Date: 03/01/2026",
            "Discharge Date: 03/05/2026",
            "Principal Diagnosis: Pneumonia",
            "Allergies: NKDA",
            "Follow-up: PCP",
            "Discharge Condition: Stable",
        ],
    )
    create_test_pdf(folder / "progress_note_1.pdf", ["Principal Diagnosis: Bronchitis"])
    create_test_pdf(folder / "medication_admission.pdf", ["Medications:", "- Aspirin 81mg PO daily"])
    create_test_pdf(folder / "medication_discharge.pdf", ["Medications:", "- Aspirin 81mg PO daily"])


def setup_pending(folder: Path) -> None:
    create_test_pdf(
        folder / "admission_note.pdf",
        [
            "Patient Name: John",
            "Admission Date: 03/01/2026",
            "Discharge Date: 03/05/2026",
            "Principal Diagnosis: UTI",
            "Allergies: NKDA",
            "Follow-up: PCP",
            "Discharge Condition: Stable",
        ],
    )
    create_test_pdf(folder / "labs.pdf", ["WBC: 12.5 K/uL", "Blood culture pending"])
    create_test_pdf(folder / "medication_admission.pdf", ["Medications:", "- Aspirin 81mg PO daily"])
    create_test_pdf(folder / "medication_discharge.pdf", ["Medications:", "- Aspirin 81mg PO daily"])


def setup_med_discrepancy(folder: Path) -> None:
    create_test_pdf(
        folder / "admission_note.pdf",
        [
            "Patient Name: John",
            "Admission Date: 03/01/2026",
            "Discharge Date: 03/05/2026",
            "Principal Diagnosis: HTN",
            "Allergies: NKDA",
            "Follow-up: PCP",
            "Discharge Condition: Stable",
        ],
    )
    create_test_pdf(
        folder / "medication_admission.pdf",
        ["Medications:", "- Lisinopril 10mg PO daily", "- Aspirin 81mg PO daily"],
    )
    create_test_pdf(
        folder / "medication_discharge.pdf",
        ["Medications:", "- Lisinopril 20mg PO daily", "- Warfarin 5mg PO daily"],
    )


def setup_multi_flags(folder: Path) -> None:
    create_complete_patient_folder(folder)
    create_test_pdf(
        folder / "progress_note_2.pdf",
        ["Principal Diagnosis: Pneumonia", "Hospital Course: Continued antibiotics."],
    )


FOLDERS = {
    "complete": create_complete_patient_folder,
    "missing": setup_missing,
    "conflicts": setup_conflicts,
    "pending": setup_pending,
    "med_discrepancy": setup_med_discrepancy,
    "multi_flags": setup_multi_flags,
}


def main() -> None:
    root = Path("fixtures/patient_folders")
    for name, setup in FOLDERS.items():
        folder = root / name
        folder.mkdir(parents=True, exist_ok=True)
        for pdf in folder.glob("*.pdf"):
            pdf.unlink()
        setup(folder)
        result = run_discharge_agent(folder, llm_provider="gemini")
        hc = next((s for s in result.draft_summary.sections if s.name == "Hospital Course"), None)
        pending = next((s for s in result.draft_summary.sections if s.name == "Pending Results"), None)
        print(
            f"{name:16} status={result.status:8} flags={len(result.safety_flags)} "
            f"conflicts={len(result.conflicts)} | HC={hc.content[:55] if hc else '-'} | "
            f"Pending={pending.content[:45] if pending else '-'}"
        )

    complete = json.loads(Path("outputs/complete/discharge_summary_draft.json").read_text())
    print("\nComplete patient draft sections:")
    for section in complete["sections"]:
        print(f"  {section['name']:22} [{section['status']:8}] {section['content'][:72]}")


if __name__ == "__main__":
    main()
