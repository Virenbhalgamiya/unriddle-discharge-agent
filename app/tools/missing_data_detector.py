from __future__ import annotations

from typing import Any

from app.models.constants import MISSING_LITERAL
from app.models.evidence import EvidenceItem
from app.models.summary_models import ClinicianReviewItem, SafetyFlag


REQUIRED_FIELDS = [
    "patient_demographics",
    "admission_date",
    "discharge_date",
    "principal_diagnosis",
    "medications",
    "allergies",
    "follow_up_instructions",
    "discharge_condition",
]


def _has_field(evidence: list[dict[str, Any]], field: str) -> bool:
    if field == "medications":
        return any(
            e.get("field_name") in ("admission_medications", "discharge_medications")
            for e in evidence
        )
    if field == "patient_demographics":
        return any(
            e.get("field_name") in ("patient_demographics", "patient_name", "patient_dob", "patient_mrn")
            for e in evidence
        )
    return any(e.get("field_name") == field for e in evidence)


def detect_missing_fields(
    evidence_store: list[dict[str, Any]],
    required_fields: list[str] | None = None,
) -> tuple[list[str], list[SafetyFlag], list[ClinicianReviewItem]]:
    fields = required_fields or REQUIRED_FIELDS
    missing: list[str] = []
    flags: list[SafetyFlag] = []
    reviews: list[ClinicianReviewItem] = []

    for field in fields:
        if not _has_field(evidence_store, field):
            missing.append(field)
            flags.append(
                SafetyFlag(
                    category="missing_data",
                    message=f"{field}: {MISSING_LITERAL}",
                    severity="high",
                    source="missing_data_detector",
                )
            )
            reviews.append(
                ClinicianReviewItem(
                    reason="Missing data",
                    details=f"Required field '{field}' not found in source documents.",
                    section=field,
                    priority="high",
                )
            )

    return missing, flags, reviews
