"""Narrative synthesis agent — evidence-grounded clinical prose + executive summary."""

from __future__ import annotations

import json
import re
from typing import Any, Optional

from app.evaluation.simulated_doctor import SimulatedDoctor
from app.evaluation.summary_rubric import evaluate_summary_quality
from app.llm.base_provider import LLMMessage
from app.llm.provider_factory import get_provider
from app.memory.correction_memory import CorrectionMemory
from app.models.summary_models import DischargeSummaryDraft, SectionStatus, SummarySection


class NarrativeSynthesisAgent:
    """Transforms extracted evidence into clinician-ready narrative with grounding checks."""

    def __init__(self, memory: Optional[CorrectionMemory] = None) -> None:
        self.memory = memory
        self.doctor = SimulatedDoctor()

    def refine(
        self,
        draft: DischargeSummaryDraft,
        state: dict[str, Any],
    ) -> tuple[DischargeSummaryDraft, dict[str, Any]]:
        provider = state.get("llm_provider", "mock")
        config = state.get("config") or {}
        llm_enhance = config.get("narrative", {}).get("llm_enhance", True)

        sections = [s.model_copy() for s in draft.sections]
        for section in sections:
            if not section.raw_content:
                section.raw_content = section.content

        sections = self._synthesize_key_sections(sections, state, provider, llm_enhance)
        executive = self._build_executive_summary(sections, state, provider, llm_enhance)

        refined = draft.model_copy(update={"sections": sections, "executive_summary": executive})
        refined = self.doctor.edit(refined)
        refined = self._apply_memory_learnings(refined)
        refined = self._rebuild_narrative_document(refined)

        quality = evaluate_summary_quality(refined, state.get("evidence_store", []))
        refined = refined.model_copy(update={"quality_score": quality["overall_score"]})

        metadata = {
            "synthesis_provider": provider,
            "quality": quality,
            "executive_summary_generated": bool(executive),
        }
        return refined, metadata

    def _synthesize_key_sections(
        self,
        sections: list[SummarySection],
        state: dict[str, Any],
        provider: str,
        llm_enhance: bool,
    ) -> list[SummarySection]:
        evidence = state.get("evidence_store", [])
        updated: list[SummarySection] = []

        for section in sections:
            if section.name == "Hospital Course" and section.status == SectionStatus.PRESENT:
                values = [
                    e.get("value", "")
                    for e in evidence
                    if e.get("field_name") == "hospital_course" and e.get("value")
                ]
                synthesized = self._synthesize_hospital_course(values, section.content, provider, llm_enhance)
                updated.append(section.model_copy(update={"content": synthesized}))
            elif section.name == "Follow-up Instructions" and section.status == SectionStatus.PRESENT:
                values = [
                    e.get("value", "")
                    for e in evidence
                    if e.get("field_name") == "follow_up_instructions" and e.get("value")
                ]
                synthesized = self._synthesize_follow_up(values, section.content, provider, llm_enhance)
                updated.append(section.model_copy(update={"content": synthesized}))
            else:
                updated.append(section)

        return updated

    def _synthesize_hospital_course(
        self,
        evidence_values: list[str],
        fallback: str,
        provider: str,
        llm_enhance: bool,
    ) -> str:
        unique = _dedupe(evidence_values)
        if not unique:
            return fallback

        if llm_enhance:
            llm_text = self._llm_synthesize(
                section="Hospital Course",
                evidence=unique,
                fallback=fallback,
                provider=provider,
                instruction=(
                    "Write 2-4 sentences describing the inpatient course in chronological clinical prose. "
                    "Merge overlapping progress notes. Use only provided evidence."
                ),
            )
            if llm_text:
                return llm_text

        return self._mock_synthesize_course(unique, fallback)

    def _synthesize_follow_up(
        self,
        evidence_values: list[str],
        fallback: str,
        provider: str,
        llm_enhance: bool,
    ) -> str:
        unique = _dedupe(evidence_values)
        if not unique:
            return fallback
        if llm_enhance:
            llm_text = self._llm_synthesize(
                section="Follow-up Instructions",
                evidence=unique,
                fallback=fallback,
                provider=provider,
                instruction="Write 1-2 sentences with clear follow-up plan using only evidence.",
            )
            if llm_text:
                return llm_text
        joined = "; ".join(unique)
        return f"Follow-up plan: {joined}. Patient should maintain scheduled outpatient care as documented."

    def _build_executive_summary(
        self,
        sections: list[SummarySection],
        state: dict[str, Any],
        provider: str,
        llm_enhance: bool,
    ) -> str:
        bundle = self._evidence_bundle(sections, state)
        if llm_enhance and provider != "mock":
            text = self._llm_synthesize(
                section="Executive Summary",
                evidence=[json.dumps(bundle)],
                fallback="",
                provider=provider,
                instruction=(
                    "Write a 3-5 sentence attending-style discharge summary paragraph covering "
                    "patient identity, admission/discharge dates, principal diagnosis, hospital course, "
                    "discharge condition, key med changes, and follow-up. Use ONLY facts in the bundle."
                ),
            )
            if text:
                return text
        return self._mock_executive_summary(bundle)

    def _evidence_bundle(self, sections: list[SummarySection], state: dict[str, Any]) -> dict[str, Any]:
        def content(name: str) -> str:
            sec = next((s for s in sections if s.name == name), None)
            return sec.content if sec and sec.status == SectionStatus.PRESENT else ""

        return {
            "demographics": content("Patient Demographics"),
            "admission_date": content("Admission Date"),
            "discharge_date": content("Discharge Date"),
            "principal_diagnosis": content("Principal Diagnosis"),
            "secondary_diagnoses": content("Secondary Diagnoses"),
            "hospital_course": content("Hospital Course"),
            "discharge_condition": content("Discharge Condition"),
            "discharge_medications": content("Discharge Medications"),
            "follow_up": content("Follow-up Instructions"),
            "pending_results": content("Pending Results"),
            "medication_changes": [
                c.get("medication_name", "") for c in state.get("medication_changes", [])
            ],
        }

    def _llm_synthesize(
        self,
        section: str,
        evidence: list[str],
        fallback: str,
        provider: str,
        instruction: str,
    ) -> Optional[str]:
        try:
            llm = get_provider(provider)
            result = llm.structured_complete(
                messages=[
                    LLMMessage(
                        role="system",
                        content=(
                            "You are a hospitalist writing discharge summary prose. "
                            "Never invent clinical facts. Preserve safety literals if present."
                        ),
                    ),
                    LLMMessage(
                        role="user",
                        content=f"{instruction}\nSection: {section}\nEvidence: {evidence}\nFallback: {fallback}",
                    ),
                ],
                schema={
                    "type": "object",
                    "properties": {"content": {"type": "string"}},
                    "required": ["content"],
                },
            )
            content = str(result.get("content", "")).strip()
            if content and self._grounding_ok(content, evidence):
                return content
        except Exception:
            return None
        return None

    def _grounding_ok(self, content: str, evidence_values: list[str]) -> bool:
        if not evidence_values:
            return True
        content_lower = content.lower()
        for value in evidence_values:
            if value.startswith("{"):
                continue
            tokens = [t for t in re.findall(r"[a-zA-Z]{4,}", value.lower()) if t not in {"patient", "with", "and"}]
            if not tokens:
                continue
            hits = sum(1 for t in tokens if t in content_lower)
            if hits / len(tokens) < 0.4:
                return False
        return True

    def _mock_synthesize_course(self, values: list[str], fallback: str) -> str:
        primary = values[0].strip().rstrip(".")
        if not primary.lower().startswith(("the patient", "patient")):
            primary = f"The patient {primary[0].lower()}{primary[1:]}" if primary else primary

        extras: list[str] = []
        for value in values[1:]:
            clause = value.strip().rstrip(".")
            lower = clause.lower()
            if lower in primary.lower() or ("improv" in lower and "improv" in primary.lower()):
                continue
            if not clause.lower().startswith(("the patient", "patient")):
                clause = f"Progress notes document {clause[0].lower()}{clause[1:]}"
            extras.append(clause + ".")

        if extras:
            return f"{primary.rstrip('.')}. {' '.join(extras)}"
        return primary + ("." if not primary.endswith(".") else "")

    def _mock_executive_summary(self, bundle: dict[str, Any]) -> str:
        demo = bundle.get("demographics") or "The patient"
        admit = bundle.get("admission_date") or "documented admission date"
        discharge = bundle.get("discharge_date") or "documented discharge date"
        dx = bundle.get("principal_diagnosis") or "the principal diagnosis"
        course = bundle.get("hospital_course") or "the documented hospital course"
        condition = bundle.get("discharge_condition") or "stable condition"
        follow = bundle.get("follow_up") or "outpatient follow-up as documented"

        summary = (
            f"{demo.rstrip('.')} was hospitalized from {admit} to {discharge} "
            f"for {dx.rstrip('.')}. {course.rstrip('.')}. "
            f"At discharge the patient was in {condition.rstrip('.')}. "
            f"{follow.rstrip('.')}."
        )
        if bundle.get("pending_results"):
            summary += " Outstanding pending results require clinician follow-up."
        return re.sub(r"\s+", " ", summary).strip()

    def _apply_memory_learnings(self, draft: DischargeSummaryDraft) -> DischargeSummaryDraft:
        if not self.memory:
            return draft
        hints = self.memory.get_formatting_hints()
        sections: list[SummarySection] = []
        for section in draft.sections:
            hint = hints.get(section.name) or hints.get(section.name.lower().replace(" ", "_"))
            if hint and section.status == SectionStatus.PRESENT and hint not in section.content:
                sections.append(section.model_copy(update={"content": f"{section.content}\n\n_Note: {hint}_"}))
            else:
                sections.append(section)
        return draft.model_copy(update={"sections": sections})

    def _rebuild_narrative_document(self, draft: DischargeSummaryDraft) -> DischargeSummaryDraft:
        lines = ["# Discharge Summary Draft", ""]
        if draft.executive_summary:
            lines.extend(["## Executive Summary", draft.executive_summary, ""])

        skip = {"Safety Flags", "Conflicts", "Clinician Review Items", "Medication Changes"}
        for section in draft.sections:
            if section.name in skip:
                continue
            lines.extend([f"## {section.name}", section.content, ""])

        med = next((s for s in draft.sections if s.name == "Medication Changes"), None)
        if med and med.status == SectionStatus.PRESENT and med.content:
            lines.extend(["## Medication Changes", med.content, ""])

        review = next((s for s in draft.sections if s.name == "Clinician Review Items"), None)
        if review and review.content and review.content != "None":
            lines.extend(["## Items Requiring Clinician Review", review.content, ""])

        return draft.model_copy(update={"narrative_summary": "\n".join(lines).strip()})

    def record_learning_from_pair(
        self,
        before: DischargeSummaryDraft,
        after: DischargeSummaryDraft,
    ) -> None:
        if not self.memory:
            return
        for orig, edited in zip(before.sections, after.sections):
            if orig.content != edited.content and orig.status == SectionStatus.PRESENT:
                self.memory.record_correction(
                    mistake=f"Formatting in {orig.name}",
                    correction=edited.content[:200],
                    affected_section=orig.name,
                    recommendation=f"Prefer clinician-style formatting for {orig.name}",
                )


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        key = re.sub(r"\s+", " ", value.strip().lower())
        if key and key not in seen:
            seen.add(key)
            out.append(value.strip())
    return out
