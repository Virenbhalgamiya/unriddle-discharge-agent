from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, Field

from app.models.constants import CONFLICT_LITERAL, DRAFT_BANNER, MISSING_LITERAL, PENDING_LITERAL


class SectionStatus(str, Enum):
    PRESENT = "Present"
    MISSING = "Missing"
    PENDING = "Pending"
    CONFLICT = "Conflict"


class SummarySection(BaseModel):
    name: str
    status: SectionStatus
    content: str
    raw_content: str = ""
    evidence_ids: list[str] = Field(default_factory=list)


class DischargeSummaryDraft(BaseModel):
    banner: str = DRAFT_BANNER
    is_final: bool = False
    patient_id: str
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    sections: list[SummarySection] = Field(default_factory=list)
    narrative_summary: str = ""
    executive_summary: str = ""
    quality_score: float = 0.0
    safety_flags_summary: list[str] = Field(default_factory=list)
    conflicts_summary: list[str] = Field(default_factory=list)
    clinician_review_summary: list[str] = Field(default_factory=list)
    evidence_references: list[dict[str, Any]] = Field(default_factory=list)


class MedicationChangeType(str, Enum):
    ADDED = "Added"
    REMOVED = "Removed"
    CONTINUED = "Continued"
    DOSE_CHANGED = "Dose Changed"
    FREQUENCY_CHANGED = "Frequency Changed"
    ROUTE_CHANGED = "Route Changed"


class MedicationChange(BaseModel):
    medication_name: str
    change_type: MedicationChangeType
    admission_value: Optional[str] = None
    discharge_value: Optional[str] = None
    reason: str = "Reason Not Documented"
    requires_review: bool = False
    evidence_ids: list[str] = Field(default_factory=list)


class MedicationReconciliationReport(BaseModel):
    patient_id: str
    changes: list[MedicationChange] = Field(default_factory=list)
    admission_count: int = 0
    discharge_count: int = 0
    undocumented_changes: int = 0


class ConflictReport(BaseModel):
    field_name: str
    values: list[dict[str, Any]]
    message: str = CONFLICT_LITERAL


class PendingResultsReport(BaseModel):
    description: str
    source_document: str
    page_number: int
    status: str = PENDING_LITERAL
    evidence_id: Optional[str] = None


class SafetyFlag(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    category: str
    message: str
    severity: str = "medium"
    source: str = "system"


class ClinicianReviewItem(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    reason: str
    details: str
    section: str = "general"
    priority: str = "medium"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class TraceStep(BaseModel):
    step_number: int
    reasoning_summary: str = ""
    chosen_action: str = ""
    tool_name: str = ""
    tool_input: dict[str, Any] = Field(default_factory=dict)
    tool_output: dict[str, Any] = Field(default_factory=dict)
    result: str = ""
    errors: list[str] = Field(default_factory=list)
    retries: int = 0
    next_decision: str = ""


class InteractionResult(BaseModel):
    drug_a: str
    drug_b: str
    severity: str
    description: str


def section_content_or_literal(
    status: SectionStatus,
    values: list[str],
) -> str:
    if status == SectionStatus.MISSING:
        return MISSING_LITERAL
    if status == SectionStatus.CONFLICT:
        return CONFLICT_LITERAL
    if status == SectionStatus.PENDING:
        if values:
            return "; ".join(values) + f" — {PENDING_LITERAL}"
        return PENDING_LITERAL
    return "; ".join(values) if values else MISSING_LITERAL
