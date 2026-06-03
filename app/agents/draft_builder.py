from __future__ import annotations

from typing import Any, Optional

from app.agents.narrative_agent import NarrativeSynthesisAgent
from app.agents.narrative_synthesizer import enhance_draft_summary
from app.memory.correction_memory import CorrectionMemory
from app.models.constants import CONFLICT_LITERAL, DRAFT_BANNER, MISSING_LITERAL, PENDING_LITERAL
from app.models.evidence import EvidenceStore
from app.models.summary_models import (
    DischargeSummaryDraft,
    SectionStatus,
    SummarySection,
    section_content_or_literal,
)
from app.tools.conflict_detector import detect_conflicts
from app.tools.medication_reconciliation import reconcile_medications


SECTION_FIELD_MAP = {
    "Patient Demographics": "patient_demographics",
    "Admission Date": "admission_date",
    "Discharge Date": "discharge_date",
    "Principal Diagnosis": "principal_diagnosis",
    "Secondary Diagnoses": "secondary_diagnoses",
    "Hospital Course": "hospital_course",
    "Procedures": "procedures",
    "Lab Results": "lab_results",
    "Discharge Medications": "discharge_medications",
    "Allergies": "allergies",
    "Follow-up Instructions": "follow_up_instructions",
    "Pending Results": "pending_results",
    "Discharge Condition": "discharge_condition",
}


DEMOGRAPHIC_FIELDS = ("patient_name", "patient_dob", "patient_mrn", "patient_demographics")


def _field_status(
    field_key: str,
    evidence_store: list[dict[str, Any]],
    missing_fields: list[str],
    conflicts: list[dict[str, Any]],
    pending_results: list[dict[str, Any]],
) -> SectionStatus:
    conflict_fields = {c.get("field_name") for c in conflicts}
    if field_key == "patient_demographics":
        if conflict_fields & set(DEMOGRAPHIC_FIELDS):
            return SectionStatus.CONFLICT
    elif field_key in conflict_fields:
        return SectionStatus.CONFLICT
    if field_key == "pending_results":
        return SectionStatus.PENDING if pending_results else SectionStatus.MISSING
    check_field = field_key
    if field_key == "medications" or field_key == "discharge_medications":
        check_field = "medications"
    if check_field in missing_fields:
        return SectionStatus.MISSING
    if field_key == "patient_demographics":
        items = [e for e in evidence_store if e.get("field_name") in DEMOGRAPHIC_FIELDS]
        if items:
            return SectionStatus.PRESENT
    items = [e for e in evidence_store if e.get("field_name") == field_key]
    if field_key == "discharge_medications":
        items = [e for e in evidence_store if e.get("field_name") == "discharge_medications"]
    if items or (field_key == "pending_results" and pending_results):
        return SectionStatus.PRESENT
    if field_key in missing_fields:
        return SectionStatus.MISSING
    return SectionStatus.MISSING


def build_draft_summary(
    state: dict[str, Any],
    memory: Optional[CorrectionMemory] = None,
    partial: bool = False,
) -> DischargeSummaryDraft:
    evidence_store = state.get("evidence_store", [])
    missing_fields = state.get("missing_fields", [])
    conflicts = state.get("conflicts", [])
    pending_results = state.get("pending_results", [])
    formatting_hints = memory.get_formatting_hints() if memory else {}

    sections: list[SummarySection] = []
    for section_name, field_key in SECTION_FIELD_MAP.items():
        status = _field_status(field_key, evidence_store, missing_fields, conflicts, pending_results)
        values: list[str] = []
        evidence_ids: list[str] = []

        if field_key == "pending_results":
            if pending_results:
                values = [p.get("description", PENDING_LITERAL) for p in pending_results]
                status = SectionStatus.PENDING
            content = section_content_or_literal(status, values)
        elif field_key == "patient_demographics":
            items = [e for e in evidence_store if e.get("field_name") in DEMOGRAPHIC_FIELDS]
            labels = {"patient_name": "Name", "patient_dob": "DOB", "patient_mrn": "MRN", "patient_demographics": "Info"}
            values = []
            for item in items:
                label = labels.get(item.get("field_name", ""), "Info")
                values.append(f"{label}: {item.get('value', '')}")
            evidence_ids = [e.get("id", "") for e in items if e.get("id")]
            status = SectionStatus.MISSING if not items else status
            content = section_content_or_literal(status, values)
        elif field_key == "discharge_medications":
            items = [e for e in evidence_store if e.get("field_name") == "discharge_medications"]
            values = [e.get("value", "") for e in items]
            evidence_ids = [e.get("id", "") for e in items if e.get("id")]
            status = SectionStatus.MISSING if not items else status
            content = section_content_or_literal(status, values)
        elif field_key == "lab_results":
            items = [e for e in evidence_store if e.get("field_name") == "lab_results"]
            values = [e.get("value", "") for e in items]
            evidence_ids = [e.get("id", "") for e in items if e.get("id")]
            status = SectionStatus.MISSING if not items else SectionStatus.PRESENT
            content = section_content_or_literal(status, values)
        else:
            items = [e for e in evidence_store if e.get("field_name") == field_key]
            values = [e.get("value", "") for e in items]
            evidence_ids = [e.get("id", "") for e in items if e.get("id")]
            content = section_content_or_literal(status, values)

        hint = formatting_hints.get(field_key)
        if hint and status == SectionStatus.PRESENT and not partial:
            content = f"{content}\n[Formatting note: {hint}]"

        sections.append(
            SummarySection(
                name=section_name,
                status=status,
                content=content,
                raw_content=content,
                evidence_ids=evidence_ids,
            )
        )

    med_changes = state.get("medication_changes", [])
    if med_changes:
        change_lines = [
            f"{c.get('medication_name')}: {c.get('change_type')} — {c.get('reason', 'Reason Not Documented')}"
            for c in med_changes
        ]
        sections.append(
            SummarySection(
                name="Medication Changes",
                status=SectionStatus.PRESENT,
                content="; ".join(change_lines),
            )
        )

    sections.append(
        SummarySection(
            name="Safety Flags",
            status=SectionStatus.PRESENT if state.get("safety_flags") else SectionStatus.MISSING,
            content="; ".join(f.get("message", "") for f in state.get("safety_flags", [])) or MISSING_LITERAL,
        )
    )
    sections.append(
        SummarySection(
            name="Conflicts",
            status=SectionStatus.PRESENT if conflicts else SectionStatus.MISSING,
            content="; ".join(c.get("message", CONFLICT_LITERAL) for c in conflicts) or "No conflicts detected",
        )
    )
    sections.append(
        SummarySection(
            name="Clinician Review Items",
            status=SectionStatus.PRESENT,
            content="; ".join(r.get("details", "") for r in state.get("clinician_review_items", [])) or "None",
        )
    )

    store = EvidenceStore(items=[])
    for e in evidence_store:
        try:
            from app.models.evidence import EvidenceItem
            store.add(EvidenceItem(**e))
        except Exception:
            pass

    draft = DischargeSummaryDraft(
        patient_id=state.get("patient_id", "unknown"),
        sections=sections,
        safety_flags_summary=[f.get("message", "") for f in state.get("safety_flags", [])],
        conflicts_summary=[c.get("message", CONFLICT_LITERAL) for c in conflicts],
        clinician_review_summary=[r.get("details", "") for r in state.get("clinician_review_items", [])],
        evidence_references=store.to_dict_list(),
        is_final=False,
        banner=DRAFT_BANNER + (" (PARTIAL — MAX STEPS REACHED)" if partial else ""),
    )

    config = state.get("config") or {}
    narrative_cfg = config.get("narrative", {})
    llm_enhance = narrative_cfg.get("llm_enhance", True) and not partial
    polished = enhance_draft_summary(
        draft,
        state,
        llm_provider=state.get("llm_provider", "mock"),
        llm_enhance=llm_enhance,
    )

    synthesizer = NarrativeSynthesisAgent(memory=memory)
    before_doctor = polished
    final_draft, synthesis_meta = synthesizer.refine(polished, state)
    synthesizer.record_learning_from_pair(before_doctor, final_draft)
    state["_synthesis_metadata"] = synthesis_meta
    return final_draft
