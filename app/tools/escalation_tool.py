from __future__ import annotations

from typing import Any, Optional

from app.memory.correction_memory import CorrectionMemory
from app.models.summary_models import ClinicianReviewItem, SafetyFlag


def flag_for_clinician_review(
    reason: str,
    details: str,
    section: str = "general",
    priority: str = "medium",
    memory: Optional[CorrectionMemory] = None,
) -> tuple[ClinicianReviewItem, SafetyFlag, dict[str, Any]]:
    review = ClinicianReviewItem(
        reason=reason,
        details=details,
        section=section,
        priority=priority,
    )
    severity = "critical" if priority == "critical" else "high" if priority == "high" else "medium"
    flag = SafetyFlag(
        category=reason.lower().replace(" ", "_"),
        message=details,
        severity=severity,
        source="escalation_tool",
    )
    record = review.model_dump(mode="json")
    if memory:
        memory.store_escalation(reason, details, section)
    return review, flag, record


def escalate_extraction_failure(
    document: str,
    errors: list[str],
    memory: Optional[CorrectionMemory] = None,
) -> tuple[ClinicianReviewItem, SafetyFlag]:
    details = f"Extraction failure for {document}: {'; '.join(errors)}"
    review, flag, _ = flag_for_clinician_review(
        reason="Extraction failure",
        details=details,
        section="documents",
        priority="high",
        memory=memory,
    )
    return review, flag
