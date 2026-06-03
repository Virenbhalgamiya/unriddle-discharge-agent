"""Evidence-grounded narrative polish for discharge summary sections."""

from __future__ import annotations

import re
from typing import Any, Optional

from app.llm.base_provider import LLMMessage
from app.llm.provider_factory import get_provider
from app.models.constants import CONFLICT_LITERAL, MISSING_LITERAL, PENDING_LITERAL
from app.models.summary_models import DischargeSummaryDraft, SectionStatus, SummarySection

NARRATIVE_SECTIONS = frozenset(
    {
        "Patient Demographics",
        "Principal Diagnosis",
        "Secondary Diagnoses",
        "Hospital Course",
        "Procedures",
        "Lab Results",
        "Discharge Medications",
        "Allergies",
        "Follow-up Instructions",
        "Discharge Condition",
        "Medication Changes",
    }
)

LLM_NARRATIVE_SECTIONS = frozenset({"Hospital Course", "Follow-up Instructions"})


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        key = re.sub(r"\s+", " ", value.strip().lower())
        if key and key not in seen:
            seen.add(key)
            out.append(value.strip())
    return out


def _ensure_sentence(text: str) -> str:
    text = text.strip()
    if not text:
        return text
    if text.endswith((".", "!", "?")):
        return text
    return f"{text}."


def _parse_demographic_values(values: list[str]) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for value in values:
        if ":" in value:
            label, content = value.split(":", 1)
            parsed[label.strip().lower()] = content.strip()
        else:
            parsed.setdefault("info", value.strip())
    return parsed


def _format_demographics(values: list[str], evidence_store: Optional[list[dict[str, Any]]] = None) -> str:
    name = dob = mrn = ""
    if evidence_store:
        for item in evidence_store:
            field = item.get("field_name", "")
            val = str(item.get("value", "")).strip()
            if field == "patient_name" and val:
                name = val
            elif field == "patient_dob" and val:
                dob = val
            elif field == "patient_mrn" and val:
                mrn = val
            elif field == "patient_demographics" and val and not name:
                name = val

    if not name and not dob:
        parsed = _parse_demographic_values(values)
        name = parsed.get("name") or parsed.get("info", "")
        dob = parsed.get("dob", "")
        mrn = parsed.get("mrn", "") or mrn

        if not dob and values:
            plain = _dedupe_preserve_order(values)
            if len(plain) == 1:
                if re.match(r"\d{1,2}/\d{1,2}/\d{2,4}", plain[0]):
                    dob = plain[0]
                elif not name:
                    name = plain[0]
            elif len(plain) >= 2:
                if not name:
                    name = plain[0]
                for item in plain[1:]:
                    if re.match(r"\d{1,2}/\d{1,2}/\d{2,4}", item):
                        dob = item
                    elif not mrn:
                        mrn = item.replace("MRN", "").strip()

    if name and dob:
        line = f"{name} (DOB {dob})"
    elif name:
        line = name
    elif dob:
        line = f"DOB {dob}"
    else:
        line = "; ".join(values)

    if mrn:
        line = f"{line}; MRN {mrn.lstrip(': ')}"
    return _ensure_sentence(line)


def _format_hospital_course(values: list[str]) -> str:
    unique = _dedupe_preserve_order(values)
    if not unique:
        return ""
    if len(unique) == 1:
        text = unique[0]
        if not text.lower().startswith(("the patient", "patient")):
            text = f"The patient {text[0].lower()}{text[1:]}" if text else text
        return _ensure_sentence(text)

    primary = unique[0].strip().rstrip(".")
    if not primary.lower().startswith(("the patient", "patient")):
        primary = f"The patient {primary[0].lower()}{primary[1:]}"

    supplemental: list[str] = []
    for value in unique[1:]:
        clause = value.strip().rstrip(".")
        lower = clause.lower()
        if lower in primary.lower():
            continue
        if "improv" in lower and "improv" in primary.lower():
            continue
        if not clause.lower().startswith(("the patient", "patient", "on ", "during")):
            clause = f"Progress notes additionally document {clause[0].lower()}{clause[1:]}"
        supplemental.append(_ensure_sentence(clause))

    if supplemental:
        return f"{_ensure_sentence(primary)} {' '.join(supplemental)}"
    return _ensure_sentence(primary)


def _format_bullet_list(values: list[str], intro: str = "") -> str:
    items = _dedupe_preserve_order(values)
    bullets = "\n".join(f"- {item}" for item in items)
    if intro:
        return f"{intro}\n{bullets}"
    return bullets


def _format_diagnosis(values: list[str], label: str) -> str:
    items = _dedupe_preserve_order(values)
    if len(items) == 1:
        return _ensure_sentence(f"{label}: {items[0]}")
    joined = "; ".join(items)
    return _ensure_sentence(f"{label}: {joined}")


def _format_discharge_condition(values: list[str]) -> str:
    condition = _dedupe_preserve_order(values)[0] if values else ""
    if not condition:
        return ""
    return _ensure_sentence(f"Patient discharged in {condition.lower()} condition")


def _format_medication_changes(state: dict[str, Any]) -> str:
    lines: list[str] = []
    for change in state.get("medication_changes", []):
        name = change.get("medication_name", "Unknown")
        change_type = change.get("change_type", "Changed")
        reason = change.get("reason", "Reason Not Documented")
        admission = change.get("admission_value") or "not listed"
        discharge = change.get("discharge_value") or "not listed"
        lines.append(
            f"- **{name}** ({change_type}): admission `{admission}` → discharge `{discharge}` "
            f"({reason})."
        )
    return "\n".join(lines)


def _format_pending(values: list[str]) -> str:
    items = _dedupe_preserve_order(values)
    if not items:
        return PENDING_LITERAL
    listed = "; ".join(items)
    return f"The following results remain outstanding at discharge: {listed}. {PENDING_LITERAL}"


def polish_section_content(
    section_name: str,
    status: SectionStatus,
    values: list[str],
    state: dict[str, Any],
) -> str:
    """Reformat extracted evidence into readable clinical prose without adding facts."""
    if status == SectionStatus.MISSING:
        return MISSING_LITERAL
    if status == SectionStatus.CONFLICT:
        return CONFLICT_LITERAL
    if status == SectionStatus.PENDING:
        return _format_pending(values)

    if section_name == "Patient Demographics":
        return _format_demographics(values)
    if section_name == "Principal Diagnosis":
        return _format_diagnosis(values, "Principal diagnosis")
    if section_name == "Secondary Diagnoses":
        return _format_diagnosis(values, "Secondary diagnoses")
    if section_name == "Hospital Course":
        return _format_hospital_course(values)
    if section_name == "Procedures":
        joined = ", ".join(_dedupe_preserve_order(values))
        return _ensure_sentence(f"Procedures during this admission included {joined}")
    if section_name == "Lab Results":
        return _format_bullet_list(values, "Relevant laboratory findings:")
    if section_name == "Discharge Medications":
        return _format_bullet_list(values, "Discharge medication regimen:")
    if section_name == "Allergies":
        joined = ", ".join(_dedupe_preserve_order(values))
        return _ensure_sentence(f"Documented allergies: {joined}")
    if section_name == "Follow-up Instructions":
        joined = "; ".join(_dedupe_preserve_order(values))
        return _ensure_sentence(f"Follow-up plan: {joined}")
    if section_name == "Discharge Condition":
        return _format_discharge_condition(values)
    if section_name == "Medication Changes":
        return _format_medication_changes(state)

    joined = "; ".join(_dedupe_preserve_order(values))
    return _ensure_sentence(joined) if joined else MISSING_LITERAL


def _evidence_values_for_section(section_name: str, evidence_store: list[dict[str, Any]]) -> list[str]:
    field_map = {
        "Patient Demographics": ("patient_name", "patient_dob", "patient_mrn", "patient_demographics"),
        "Admission Date": ("admission_date",),
        "Discharge Date": ("discharge_date",),
        "Principal Diagnosis": ("principal_diagnosis",),
        "Secondary Diagnoses": ("secondary_diagnoses",),
        "Hospital Course": ("hospital_course",),
        "Procedures": ("procedures",),
        "Lab Results": ("lab_results",),
        "Discharge Medications": ("discharge_medications",),
        "Allergies": ("allergies",),
        "Follow-up Instructions": ("follow_up_instructions",),
        "Discharge Condition": ("discharge_condition",),
    }
    fields = field_map.get(section_name, ())
    return [e.get("value", "") for e in evidence_store if e.get("field_name") in fields and e.get("value")]


def _grounding_ok(content: str, evidence_values: list[str]) -> bool:
    if not evidence_values:
        return True
    normalized = re.sub(r"\s+", " ", content.lower())
    for value in evidence_values:
        needle = re.sub(r"\s+", " ", value.lower()).strip()
        if len(needle) < 4:
            continue
        if needle not in normalized:
            return False
    return True


def _llm_polish_section(
    section_name: str,
    raw_content: str,
    evidence_values: list[str],
    provider_name: str,
) -> Optional[str]:
    if provider_name == "mock" or not evidence_values:
        return None
    try:
        provider = get_provider(provider_name)
        result = provider.structured_complete(
            messages=[
                LLMMessage(
                    role="system",
                    content=(
                        "You rewrite one discharge-summary section into clear clinical prose. "
                        "Use ONLY facts present in the evidence list. Do not invent diagnoses, "
                        "dates, medications, or instructions. Keep 1-3 sentences."
                    ),
                ),
                LLMMessage(
                    role="user",
                    content=(
                        f"Section: {section_name}\n"
                        f"Current text: {raw_content}\n"
                        f"Evidence (must all appear verbatim or near-verbatim): {evidence_values}\n"
                        "Return polished prose."
                    ),
                ),
            ],
            schema={
                "type": "object",
                "properties": {"content": {"type": "string"}},
                "required": ["content"],
            },
            temperature=0.0,
        )
        content = str(result.get("content", "")).strip()
        if content and _grounding_ok(content, evidence_values):
            return content
    except Exception:
        return None
    return None


def build_narrative_document(sections: list[SummarySection]) -> str:
    """Assemble a readable discharge document from polished sections."""
    lines = ["# Discharge Summary Draft", ""]
    skip = {"Safety Flags", "Conflicts", "Clinician Review Items", "Medication Changes"}

    for section in sections:
        if section.name in skip:
            continue
        lines.append(f"## {section.name}")
        lines.append(section.content)
        lines.append("")

    med_changes = next((s for s in sections if s.name == "Medication Changes"), None)
    if med_changes and med_changes.content and med_changes.status == SectionStatus.PRESENT:
        lines.append("## Medication Changes")
        lines.append(med_changes.content)
        lines.append("")

    review = [s for s in sections if s.name == "Clinician Review Items"]
    if review and review[0].content and review[0].content != "None":
        lines.append("## Items Requiring Clinician Review")
        lines.append(review[0].content)
        lines.append("")

    return "\n".join(lines).strip()


def enhance_draft_sections(
    sections: list[SummarySection],
    state: dict[str, Any],
    llm_provider: str = "mock",
    llm_enhance: bool = True,
) -> list[SummarySection]:
    evidence_store = state.get("evidence_store", [])
    enhanced: list[SummarySection] = []

    for section in sections:
        if section.name not in NARRATIVE_SECTIONS:
            enhanced.append(section)
            continue

        if section.status in (SectionStatus.MISSING, SectionStatus.CONFLICT, SectionStatus.PENDING):
            enhanced.append(section)
            continue

        values = _evidence_values_for_section(section.name, evidence_store)
        if section.name == "Medication Changes":
            polished = _format_medication_changes(state)
        elif section.name == "Patient Demographics":
            polished = _format_demographics(values, evidence_store)
        else:
            polished = polish_section_content(section.name, section.status, values or [section.content], state)

        if llm_enhance and section.name in LLM_NARRATIVE_SECTIONS and values:
            llm_text = _llm_polish_section(section.name, polished, values, llm_provider)
            if llm_text:
                polished = llm_text

        enhanced.append(
            SummarySection(
                name=section.name,
                status=section.status,
                content=polished,
                raw_content=section.raw_content or section.content,
                evidence_ids=section.evidence_ids,
            )
        )

    return enhanced


def enhance_draft_summary(
    draft: DischargeSummaryDraft,
    state: dict[str, Any],
    llm_provider: str = "mock",
    llm_enhance: bool = True,
) -> DischargeSummaryDraft:
    sections = enhance_draft_sections(
        draft.sections,
        state,
        llm_provider=llm_provider,
        llm_enhance=llm_enhance,
    )
    narrative = build_narrative_document(sections)
    return draft.model_copy(update={"sections": sections, "narrative_summary": narrative})
