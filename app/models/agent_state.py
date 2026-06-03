from __future__ import annotations

from enum import Enum
from typing import Annotated, Any, Optional, TypedDict

from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field

from app.models.evidence import EvidenceItem, EvidenceStore
from app.models.summary_models import (
    ClinicianReviewItem,
    ConflictReport,
    DischargeSummaryDraft,
    MedicationChange,
    PendingResultsReport,
    SafetyFlag,
    TraceStep,
)

from app.models.constants import (
    CONFLICT_LITERAL,
    DRAFT_BANNER,
    MAX_STEPS,
    MISSING_LITERAL,
    PENDING_LITERAL,
)


class AgentStatus(str, Enum):
    INIT = "init"
    RUNNING = "running"
    AUDIT_FAILED = "audit_failed"
    COMPLETE = "complete"
    MAX_STEPS_REACHED = "max_steps_reached"
    ERROR = "error"


class AgentState(TypedDict, total=False):
    patient_id: str
    patient_folder: str
    loaded_documents: dict[str, dict[str, Any]]
    current_plan: list[str]
    completed_tasks: list[str]
    pending_tasks: list[str]
    missing_fields: list[str]
    conflicts: list[dict[str, Any]]
    pending_results: list[dict[str, Any]]
    safety_flags: list[dict[str, Any]]
    clinician_review_items: list[dict[str, Any]]
    evidence_store: list[dict[str, Any]]
    medication_changes: list[dict[str, Any]]
    audit_failures: list[str]
    draft_summary: dict[str, Any]
    trace_log: list[dict[str, Any]]
    current_step: int
    max_steps: int
    status: str
    next_tool: str
    reasoning_summary: str
    llm_provider: str
    page_text_cache: dict[str, dict[int, str]]
    messages: Annotated[list, add_messages]
    config: dict[str, Any]
    all_tasks_complete: bool
    audit_passed: bool
    pdf_progress_callback: Any


def create_initial_state(
    patient_id: str,
    patient_folder: str,
    llm_provider: str = "openai",
    max_steps: int = MAX_STEPS,
    config: Optional[dict[str, Any]] = None,
    pdf_progress_callback: Any = None,
) -> AgentState:
    default_tasks = [
        "load_documents",
        "extract_fields",
        "medication_reconciliation",
        "detect_missing_fields",
        "detect_conflicts",
        "detect_pending_results",
        "check_interactions",
        "finalize_review_queue",
    ]
    return AgentState(
        patient_id=patient_id,
        patient_folder=patient_folder,
        loaded_documents={},
        current_plan=default_tasks.copy(),
        completed_tasks=[],
        pending_tasks=default_tasks.copy(),
        missing_fields=[],
        conflicts=[],
        pending_results=[],
        safety_flags=[],
        clinician_review_items=[],
        evidence_store=[],
        medication_changes=[],
        audit_failures=[],
        draft_summary={},
        trace_log=[],
        current_step=0,
        max_steps=max_steps,
        status=AgentStatus.INIT.value,
        next_tool="",
        reasoning_summary="",
        llm_provider=llm_provider,
        page_text_cache={},
        messages=[],
        config=config or {},
        all_tasks_complete=False,
        audit_passed=False,
        pdf_progress_callback=pdf_progress_callback,
    )


class AgentResult(BaseModel):
    patient_id: str
    status: str
    draft_summary: DischargeSummaryDraft
    safety_flags: list[SafetyFlag]
    clinician_review_items: list[ClinicianReviewItem]
    medication_changes: list[MedicationChange]
    conflicts: list[ConflictReport]
    pending_results: list[PendingResultsReport]
    evidence_store: EvidenceStore
    trace_log: list[TraceStep]
    output_dir: str = ""
    trace_paths: dict[str, str] = Field(default_factory=dict)
