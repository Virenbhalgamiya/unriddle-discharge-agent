"""Generate 52+ patient scenario folders with 200+ PDFs for feature testing."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from tests.helpers import create_test_pdf

FIXTURES_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "patient_folders"


@dataclass
class Scenario:
    name: str
    category: str
    expected: dict[str, Any]
    build: Callable[[Path], None]


def _admission_full(
    name: str = "John Doe",
    diagnosis: str = "Pneumonia",
    discharge: str = "03/05/2026",
    allergies: str = "Penicillin",
) -> list[str]:
    return [
        f"Patient Name: {name}",
        "DOB: 01/15/1970",
        "Admission Date: 03/01/2026",
        f"Discharge Date: {discharge}",
        f"Principal Diagnosis: {diagnosis}",
        "Secondary Diagnoses: Hypertension",
        "Hospital Course: Patient treated with antibiotics and improved.",
        "Procedures: Chest X-ray",
        f"Allergies: {allergies}",
        "Follow-up: Primary care in 1 week",
        "Discharge Condition: Stable",
    ]


def build_complete(folder: Path, variant: int) -> None:
    names = ["John Doe", "Jane Smith", "Robert Lee", "Maria Garcia", "Ahmed Khan"]
    dx = ["Pneumonia", "COPD exacerbation", "Heart failure", "Cellulitis", "UTI"]
    n = names[variant % len(names)]
    d = dx[variant % len(dx)]
    create_test_pdf(folder / "admission_note.pdf", _admission_full(name=n, diagnosis=d))
    create_test_pdf(folder / "medication_admission.pdf", ["Medications:", "- Lisinopril 10mg PO daily", "- Aspirin 81mg PO daily"])
    create_test_pdf(folder / "medication_discharge.pdf", ["Medications:", "- Lisinopril 10mg PO daily", "- Warfarin 5mg PO daily"])
    create_test_pdf(folder / "labs.pdf", ["WBC: 12.5 K/uL", "Culture pending"])
    create_test_pdf(folder / "progress_note_1.pdf", ["Hospital Course: Patient improving."])


def build_missing(folder: Path, missing_field: str) -> None:
    lines = _admission_full()
    if missing_field == "diagnosis":
        lines = [l for l in lines if not l.startswith("Principal Diagnosis")]
    elif missing_field == "allergies":
        lines = [l for l in lines if not l.startswith("Allergies")]
    elif missing_field == "discharge_date":
        lines = [l for l in lines if not l.startswith("Discharge Date")]
    elif missing_field == "demographics":
        lines = [l for l in lines if not l.startswith("Patient Name") and not l.startswith("DOB")]
    elif missing_field == "follow_up":
        lines = [l for l in lines if not l.startswith("Follow-up")]
    elif missing_field == "discharge_condition":
        lines = [l for l in lines if not l.startswith("Discharge Condition")]
    elif missing_field == "medications":
        create_test_pdf(folder / "admission_note.pdf", lines)
        create_test_pdf(folder / "medication_admission.pdf", ["Medications:"])
        create_test_pdf(folder / "medication_discharge.pdf", ["Medications:"])
        return
    create_test_pdf(folder / "admission_note.pdf", lines)
    create_test_pdf(folder / "medication_admission.pdf", ["Medications:", "- Aspirin 81mg PO daily"])
    create_test_pdf(folder / "medication_discharge.pdf", ["Medications:", "- Aspirin 81mg PO daily"])


def build_conflict(folder: Path, conflict_type: str) -> None:
    create_test_pdf(folder / "admission_note.pdf", _admission_full())
    if conflict_type == "diagnosis":
        create_test_pdf(folder / "progress_note_1.pdf", ["Principal Diagnosis: Bronchitis"])
    elif conflict_type == "discharge_date":
        create_test_pdf(folder / "progress_note_1.pdf", ["Discharge Date: 03/10/2026"])
    elif conflict_type == "allergies":
        create_test_pdf(folder / "progress_note_1.pdf", ["Allergies: Sulfa"])
    elif conflict_type == "patient_name":
        create_test_pdf(folder / "progress_note_1.pdf", ["Patient Name: Jonathan Doe"])
    create_test_pdf(folder / "medication_admission.pdf", ["Medications:", "- Aspirin 81mg PO daily"])
    create_test_pdf(folder / "medication_discharge.pdf", ["Medications:", "- Aspirin 81mg PO daily"])


def build_pending(folder: Path, pending_type: str) -> None:
    create_test_pdf(folder / "admission_note.pdf", _admission_full())
    create_test_pdf(folder / "medication_admission.pdf", ["Medications:", "- Aspirin 81mg PO daily"])
    create_test_pdf(folder / "medication_discharge.pdf", ["Medications:", "- Aspirin 81mg PO daily"])
    if pending_type == "culture":
        create_test_pdf(folder / "labs.pdf", ["Blood culture pending"])
    elif pending_type == "pathology":
        create_test_pdf(folder / "labs.pdf", ["Pathology pending final review"])
    elif pending_type == "multiple":
        create_test_pdf(folder / "labs.pdf", ["Culture pending", "Pathology pending", "MRI awaiting report"])


def build_med_change(folder: Path, change_type: str) -> None:
    create_test_pdf(folder / "admission_note.pdf", _admission_full(diagnosis="Hypertension"))
    adm = ["Medications:", "- Lisinopril 10mg PO daily", "- Aspirin 81mg PO daily", "- Metformin 500mg PO daily"]
    dis = ["Medications:", "- Lisinopril 10mg PO daily", "- Aspirin 81mg PO daily", "- Metformin 500mg PO daily"]
    if change_type == "added":
        dis.append("- Warfarin 5mg PO daily")
    elif change_type == "removed":
        dis = ["Medications:", "- Lisinopril 10mg PO daily"]
    elif change_type == "dose":
        dis = ["Medications:", "- Lisinopril 20mg PO daily", "- Aspirin 81mg PO daily"]
    elif change_type == "frequency":
        dis = ["Medications:", "- Lisinopril 10mg PO daily", "- Metformin 500mg PO BID"]
    elif change_type == "route":
        dis = ["Medications:", "- Morphine 10mg IV daily"]
        adm = ["Medications:", "- Morphine 10mg PO daily"]
    elif change_type == "multi":
        dis = ["Medications:", "- Lisinopril 20mg PO BID", "- Warfarin 5mg PO daily"]
        adm = ["Medications:", "- Lisinopril 10mg PO daily", "- Aspirin 81mg PO daily"]
    create_test_pdf(folder / "medication_admission.pdf", adm)
    create_test_pdf(folder / "medication_discharge.pdf", dis)


def build_interaction(folder: Path) -> None:
    create_test_pdf(folder / "admission_note.pdf", _admission_full())
    create_test_pdf(
        folder / "medication_discharge.pdf",
        ["Medications:", "- Warfarin 5mg PO daily", "- Aspirin 81mg PO daily"],
    )
    create_test_pdf(folder / "medication_admission.pdf", ["Medications:", "- Warfarin 5mg PO daily", "- Aspirin 81mg PO daily"])


def build_multi_flags(folder: Path) -> None:
    create_test_pdf(
        folder / "admission_note.pdf",
        [l for l in _admission_full() if not l.startswith("Allergies")],
    )
    create_test_pdf(folder / "progress_note_1.pdf", ["Principal Diagnosis: Bronchitis"])
    create_test_pdf(folder / "labs.pdf", ["Culture pending"])
    create_test_pdf(folder / "medication_admission.pdf", ["Medications:", "- Lisinopril 10mg PO daily"])
    create_test_pdf(folder / "medication_discharge.pdf", ["Medications:", "- Warfarin 5mg PO daily"])


def build_large_folder(folder: Path, note_count: int) -> None:
    create_test_pdf(folder / "admission_note.pdf", _admission_full())
    create_test_pdf(folder / "medication_admission.pdf", ["Medications:", "- Aspirin 81mg PO daily"])
    create_test_pdf(folder / "medication_discharge.pdf", ["Medications:", "- Aspirin 81mg PO daily"])
    for i in range(note_count):
        create_test_pdf(folder / f"progress_note_{i + 1}.pdf", [f"Progress note {i + 1}: Patient stable."])


def build_unstructured(folder: Path) -> None:
    create_test_pdf(
        folder / "hp_note.pdf",
        [
            "History & Physical — Jane Smith (DOB 02/20/1985)",
            "Patient admitted on 03/01/2026 with community-acquired pneumonia.",
            "Hospital Course: Received IV antibiotics and oxygen; clinically improved.",
            "Assessment: Pneumonia, Hypertension",
            "Allergies: Penicillin",
            "Plan: Primary care follow-up in 1 week",
            "Discharged on 03/05/2026 in stable condition",
        ],
    )
    create_test_pdf(
        folder / "medication_discharge.pdf",
        ["Discharge Medications:", "- Lisinopril 10mg PO daily", "- Azithromycin 250mg PO daily"],
    )
    create_test_pdf(folder / "medication_admission.pdf", ["Medications:", "- Lisinopril 10mg PO daily"])
    create_test_pdf(folder / "labs.pdf", ["WBC: 11.2 K/uL"])


def build_scenarios() -> list[Scenario]:
    scenarios: list[Scenario] = []

    for i in range(5):
        scenarios.append(
            Scenario(
                name=f"complete_{i + 1}",
                category="complete",
                expected={"has_draft": True, "no_false_demo_conflict": True, "min_evidence": 8},
                build=lambda f, v=i: build_complete(f, v),
            )
        )

    for i in range(5, 11):
        scenarios.append(
            Scenario(
                name=f"complete_extra_{i}",
                category="complete",
                expected={"has_draft": True, "no_false_demo_conflict": True, "min_evidence": 8},
                build=lambda f, v=i: build_complete(f, v),
            )
        )

    scenarios.append(
        Scenario(
            name="complete_with_labs_only_pending",
            category="complete",
            expected={"has_draft": True, "has_pending": True},
            build=lambda f: (
                create_test_pdf(f / "admission_note.pdf", _admission_full()),
                create_test_pdf(f / "medication_admission.pdf", ["Medications:", "- Aspirin 81mg PO daily"]),
                create_test_pdf(f / "medication_discharge.pdf", ["Medications:", "- Aspirin 81mg PO daily"]),
                create_test_pdf(f / "labs.pdf", ["Hemoglobin: 11.2 g/dL", "Urinalysis pending"]),
            ),
        )
    )

    for field in ["diagnosis", "allergies", "discharge_date", "demographics", "follow_up", "discharge_condition", "medications"]:
        scenarios.append(
            Scenario(
                name=f"missing_{field}",
                category="missing",
                expected={"has_missing": True, "missing_field": field},
                build=lambda f, fld=field: build_missing(f, fld),
            )
        )

    for ctype in ["diagnosis", "discharge_date", "allergies", "patient_name"]:
        scenarios.append(
            Scenario(
                name=f"conflict_{ctype}",
                category="conflicts",
                expected={"has_conflict": True},
                build=lambda f, c=ctype: build_conflict(f, c),
            )
        )

    for ptype in ["culture", "pathology", "multiple"]:
        scenarios.append(
            Scenario(
                name=f"pending_{ptype}",
                category="pending",
                expected={"has_pending": True},
                build=lambda f, p=ptype: build_pending(f, p),
            )
        )

    for mtype in ["added", "removed", "dose", "frequency", "route", "multi"]:
        scenarios.append(
            Scenario(
                name=f"med_{mtype}",
                category="med_discrepancy",
                expected={"has_med_changes": True},
                build=lambda f, m=mtype: build_med_change(f, m),
            )
        )

    for i in range(4):
        scenarios.append(
            Scenario(
                name=f"interaction_{i + 1}",
                category="interactions",
                expected={"has_high_interaction": True},
                build=build_interaction,
            )
        )

    for i in range(6):
        scenarios.append(
            Scenario(
                name=f"multi_flags_{i + 1}",
                category="multi_flags",
                expected={"min_safety_flags": 2},
                build=build_multi_flags,
            )
        )

    for i, count in enumerate([5, 10, 15, 20, 25]):
        scenarios.append(
            Scenario(
                name=f"large_{count}_notes",
                category="performance",
                expected={"has_draft": True, "max_tool_steps": 20},
                build=lambda f, c=count: build_large_folder(f, c),
            )
        )

    for i in range(3):
        scenarios.append(
            Scenario(
                name=f"variant_copd_{i + 1}",
                category="complete",
                expected={"has_draft": True, "min_evidence": 6},
                build=lambda f, v=i: build_complete(f, v + 2),
            )
        )

    for i in range(3):
        scenarios.append(
            Scenario(
                name=f"unstructured_note_{i + 1}",
                category="unstructured",
                expected={"has_draft": True, "min_evidence": 6, "min_quality_score": 60},
                build=build_unstructured,
            )
        )

    return scenarios


def generate_all() -> dict:
    FIXTURES_ROOT.mkdir(parents=True, exist_ok=True)
    scenarios = build_scenarios()
    manifest = []
    pdf_count = 0

    for scenario in scenarios:
        folder = FIXTURES_ROOT / scenario.name
        folder.mkdir(parents=True, exist_ok=True)
        for pdf in folder.glob("*.pdf"):
            pdf.unlink()
        scenario.build(folder)
        pdfs = list(folder.glob("*.pdf"))
        pdf_count += len(pdfs)
        manifest.append(
            {
                "name": scenario.name,
                "category": scenario.category,
                "pdf_count": len(pdfs),
                "expected": scenario.expected,
            }
        )

    index_path = FIXTURES_ROOT / "manifest.json"
    index_path.write_text(json.dumps({"scenarios": manifest, "total_pdfs": pdf_count}, indent=2), encoding="utf-8")
    return {"scenarios": len(manifest), "total_pdfs": pdf_count, "manifest_path": str(index_path)}


if __name__ == "__main__":
    stats = generate_all()
    print(json.dumps(stats, indent=2))
