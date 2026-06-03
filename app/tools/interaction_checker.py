from __future__ import annotations

from typing import Any

from app.models.summary_models import ClinicianReviewItem, InteractionResult, SafetyFlag

MOCK_INTERACTIONS: list[tuple[str, str, str, str]] = [
    ("warfarin", "aspirin", "High", "Increased bleeding risk"),
    ("warfarin", "ibuprofen", "High", "Increased bleeding risk"),
    ("metformin", "contrast", "Moderate", "Risk of lactic acidosis with contrast"),
    ("lisinopril", "potassium", "Moderate", "Hyperkalemia risk"),
    ("simvastatin", "amlodipine", "Low", "Increased statin exposure"),
]


def _med_names(evidence_store: list[dict[str, Any]]) -> list[str]:
    names = []
    for e in evidence_store:
        if e.get("field_name") == "discharge_medications":
            val = e.get("value", "")
            name = val.split()[0].lower() if val.split() else ""
            if name:
                names.append(name)
    return names


def check_interactions(
    evidence_store: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[InteractionResult], list[ClinicianReviewItem], list[SafetyFlag]]:
    meds = _med_names(evidence_store)
    interactions: list[InteractionResult] = []
    reviews: list[ClinicianReviewItem] = []
    flags: list[SafetyFlag] = []
    output: list[dict[str, Any]] = []

    for a in meds:
        for b in meds:
            if a >= b:
                continue
            for drug_a, drug_b, severity, desc in MOCK_INTERACTIONS:
                pair = {drug_a, drug_b}
                if pair == {a, b}:
                    result = InteractionResult(
                        drug_a=a.title(),
                        drug_b=b.title(),
                        severity=severity,
                        description=desc,
                    )
                    interactions.append(result)
                    entry = result.model_dump(mode="json")
                    output.append(entry)
                    if severity == "High":
                        reviews.append(
                            ClinicianReviewItem(
                                reason="High-risk interaction",
                                details=f"{a} + {b}: {desc}",
                                section="medications",
                                priority="critical",
                            )
                        )
                        flags.append(
                            SafetyFlag(
                                category="drug_interaction",
                                message=f"High severity interaction: {a} + {b}",
                                severity="critical",
                                source="interaction_checker",
                            )
                        )

    return output, interactions, reviews, flags
