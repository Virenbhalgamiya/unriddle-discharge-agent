from __future__ import annotations

import re
from typing import Any

from app.models.summary_models import (
    ClinicianReviewItem,
    InteractionResult,
    MedicationChange,
    MedicationChangeType,
    MedicationReconciliationReport,
    SafetyFlag,
)

DOSE_PATTERN = re.compile(r"(\d+(?:\.\d+)?)\s*(mg|mcg|g|units?)", re.I)
FREQ_PATTERN = re.compile(r"\b(daily|BID|TID|QID|q\d+h|once daily|twice daily)\b", re.I)
ROUTE_PATTERN = re.compile(r"\b(PO|IV|IM|SC|oral|subcutaneous|intravenous)\b", re.I)


def _parse_med(value: str) -> dict[str, str]:
    name = value.split()[0] if value.split() else value
    dose_match = DOSE_PATTERN.search(value)
    freq_match = FREQ_PATTERN.search(value)
    route_match = ROUTE_PATTERN.search(value)
    return {
        "name": name.lower(),
        "full": value.strip(),
        "dose": dose_match.group(0) if dose_match else "",
        "frequency": freq_match.group(0) if freq_match else "",
        "route": route_match.group(0) if route_match else "",
    }


def _find_reason(notes_text: str, med_name: str) -> str:
    patterns = [
        re.compile(rf"{re.escape(med_name)}.{{0,80}}(?:because|due to|reason|stopped|discontinued|changed)\s*[:\-]?\s*(.+)", re.I),
        re.compile(rf"(?:stopped|discontinued|added|started)\s+{re.escape(med_name)}.{{0,60}}(?:because|due to|for)\s*(.+)", re.I),
    ]
    for p in patterns:
        m = p.search(notes_text)
        if m:
            return m.group(1).strip()[:200]
    return "Reason Not Documented"


def reconcile_medications(
    evidence_store: list[dict[str, Any]],
    loaded_documents: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], MedicationReconciliationReport, list[ClinicianReviewItem], list[SafetyFlag]]:
    admission = [e for e in evidence_store if e.get("field_name") == "admission_medications"]
    discharge = [e for e in evidence_store if e.get("field_name") == "discharge_medications"]

    adm_map = {_parse_med(e["value"])["name"]: e for e in admission}
    dis_map = {_parse_med(e["value"])["name"]: e for e in discharge}

    notes_text = ""
    for doc in loaded_documents.values():
        for text in doc.get("page_mapping", {}).values():
            notes_text += text + "\n"

    changes: list[MedicationChange] = []
    reviews: list[ClinicianReviewItem] = []
    flags: list[SafetyFlag] = []

    all_names = set(adm_map.keys()) | set(dis_map.keys())
    for name in sorted(all_names):
        adm = adm_map.get(name)
        dis = dis_map.get(name)
        adm_val = adm["value"] if adm else None
        dis_val = dis["value"] if dis else None
        adm_parsed = _parse_med(adm_val) if adm_val else {}
        dis_parsed = _parse_med(dis_val) if dis_val else {}

        if adm and not dis:
            change_type = MedicationChangeType.REMOVED
        elif dis and not adm:
            change_type = MedicationChangeType.ADDED
        elif adm_parsed.get("dose") != dis_parsed.get("dose") and adm_parsed.get("dose") and dis_parsed.get("dose"):
            change_type = MedicationChangeType.DOSE_CHANGED
        elif adm_parsed.get("frequency") != dis_parsed.get("frequency") and adm_parsed.get("frequency") and dis_parsed.get("frequency"):
            change_type = MedicationChangeType.FREQUENCY_CHANGED
        elif adm_parsed.get("route") != dis_parsed.get("route") and adm_parsed.get("route") and dis_parsed.get("route"):
            change_type = MedicationChangeType.ROUTE_CHANGED
        else:
            change_type = MedicationChangeType.CONTINUED

        reason = "Reason Not Documented"
        requires_review = False
        if change_type != MedicationChangeType.CONTINUED:
            reason = _find_reason(notes_text, name)
            if reason == "Reason Not Documented":
                requires_review = True
                reviews.append(
                    ClinicianReviewItem(
                        reason="Medication discrepancy",
                        details=f"{change_type.value} for {name}: {reason}",
                        section="medications",
                        priority="high",
                    )
                )
                flags.append(
                    SafetyFlag(
                        category="medication_discrepancy",
                        message=f"{name} {change_type.value}: Reason Not Documented",
                        severity="high",
                        source="medication_reconciliation",
                    )
                )

        evidence_ids = []
        if adm:
            evidence_ids.append(adm.get("id", ""))
        if dis:
            evidence_ids.append(dis.get("id", ""))

        changes.append(
            MedicationChange(
                medication_name=name.title(),
                change_type=change_type,
                admission_value=adm_val,
                discharge_value=dis_val,
                reason=reason,
                requires_review=requires_review,
                evidence_ids=[e for e in evidence_ids if e],
            )
        )

    report = MedicationReconciliationReport(
        patient_id="",
        changes=changes,
        admission_count=len(admission),
        discharge_count=len(discharge),
        undocumented_changes=sum(1 for c in changes if c.requires_review),
    )
    return [c.model_dump(mode="json") for c in changes], report, reviews, flags
