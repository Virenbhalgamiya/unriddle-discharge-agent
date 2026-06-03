from __future__ import annotations

from collections import defaultdict
from typing import Any

from app.models.constants import CONFLICT_LITERAL
from app.models.summary_models import ClinicianReviewItem, ConflictReport, SafetyFlag


def _normalize(value: str) -> str:
    return " ".join(value.lower().split())


MULTI_VALUE_FIELDS = frozenset(
    {
        "admission_medications",
        "discharge_medications",
        "lab_results",
        "secondary_diagnoses",
        "hospital_course",
        "procedures",
        "patient_name",
        "patient_dob",
        "patient_mrn",
    }
)

CONFLICT_FIELDS = frozenset(
    {
        "admission_date",
        "discharge_date",
        "principal_diagnosis",
        "allergies",
        "follow_up_instructions",
        "discharge_condition",
        "patient_name",
    }
)


def detect_conflicts(
    evidence_store: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[ConflictReport], list[ClinicianReviewItem], list[SafetyFlag]]:
    by_field: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in evidence_store:
        field = item.get("field_name", "")
        if field in MULTI_VALUE_FIELDS and field not in CONFLICT_FIELDS:
            continue
        if field not in CONFLICT_FIELDS:
            continue
        by_field[field].append(item)

    conflicts: list[dict[str, Any]] = []
    reports: list[ConflictReport] = []
    reviews: list[ClinicianReviewItem] = []
    flags: list[SafetyFlag] = []

    for field_name, items in by_field.items():
        unique_values: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for item in items:
            norm = _normalize(str(item.get("value", "")))
            if norm:
                unique_values[norm].append(item)

        if len(unique_values) <= 1:
            continue

        # Same document may contain complementary facts; conflict requires differing sources.
        source_docs = {item.get("source_document") for item in items}
        if len(source_docs) == 1 and field_name != "principal_diagnosis":
            continue

        sources = []
        for norm, group in unique_values.items():
            for item in group:
                sources.append(
                    {
                        "value": item.get("value"),
                        "source_document": item.get("source_document"),
                        "page_number": item.get("page_number"),
                        "evidence_id": item.get("id"),
                    }
                )

        conflict_entry = {
            "field_name": field_name,
            "message": CONFLICT_LITERAL,
            "values": sources,
        }
        conflicts.append(conflict_entry)
        reports.append(ConflictReport(field_name=field_name, values=sources))
        reviews.append(
            ClinicianReviewItem(
                reason="Conflict",
                details=f"Conflicting values for '{field_name}': {CONFLICT_LITERAL}",
                section=field_name,
                priority="high",
            )
        )
        flags.append(
            SafetyFlag(
                category="conflict",
                message=f"{field_name}: {CONFLICT_LITERAL}",
                severity="high",
                source="conflict_detector",
            )
        )

    return conflicts, reports, reviews, flags
