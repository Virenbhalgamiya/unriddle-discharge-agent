"""Rubric-based discharge summary quality scoring."""

from __future__ import annotations

import re
from typing import Any

from app.models.constants import CONFLICT_LITERAL, MISSING_LITERAL, PENDING_LITERAL
from app.models.summary_models import DischargeSummaryDraft, SectionStatus

REQUIRED_SECTIONS = (
    "Patient Demographics",
    "Principal Diagnosis",
    "Hospital Course",
    "Discharge Medications",
    "Allergies",
)


def _section(draft: DischargeSummaryDraft, name: str):
    for section in draft.sections:
        if section.name == name:
            return section
    return None


def _token_set(text: str) -> set[str]:
    return {t.lower() for t in re.findall(r"[a-zA-Z]{4,}", text)}


def score_readability(draft: DischargeSummaryDraft) -> tuple[float, list[str]]:
    issues: list[str] = []
    score = 100.0
    for section in draft.sections:
        if section.name not in REQUIRED_SECTIONS and section.name not in {
            "Lab Results",
            "Follow-up Instructions",
            "Medication Changes",
        }:
            continue
        if section.status != SectionStatus.PRESENT:
            continue
        if "; " in section.content and section.name not in {"Secondary Diagnoses"}:
            score -= 12
            issues.append(f"{section.name}:semicolon_dump")
        if section.name == "Hospital Course" and len(section.content.split()) < 8:
            score -= 8
            issues.append("hospital_course:too_short")
        if section.name == "Patient Demographics" and "Name:" in section.content:
            score -= 10
            issues.append("demographics:label_format")
    if getattr(draft, "executive_summary", "") and len(draft.executive_summary.split()) >= 20:
        score += 5
    elif not getattr(draft, "executive_summary", ""):
        score -= 15
        issues.append("missing_executive_summary")
    return max(0.0, min(100.0, score)), issues


def score_grounding(draft: DischargeSummaryDraft, evidence_store: list[dict[str, Any]]) -> tuple[float, list[str]]:
    issues: list[str] = []
    course = _section(draft, "Hospital Course")
    if not course or course.status != SectionStatus.PRESENT:
        return 100.0, issues

    evidence_values = [
        e.get("value", "")
        for e in evidence_store
        if e.get("field_name") == "hospital_course" and e.get("value")
    ]
    if not evidence_values:
        return 100.0, issues

    content_tokens = _token_set(course.content)
    hits = 0
    total = 0
    for value in evidence_values:
        tokens = _token_set(value)
        tokens = {t for t in tokens if t not in {"patient", "with", "and", "the", "was"}}
        if not tokens:
            continue
        total += len(tokens)
        hits += sum(1 for t in tokens if t in content_tokens)

    ratio = hits / total if total else 1.0
    score = round(ratio * 100, 1)
    if ratio < 0.5:
        issues.append("hospital_course:weak_grounding")
    return score, issues


def score_safety_compliance(draft: DischargeSummaryDraft) -> tuple[float, list[str]]:
    issues: list[str] = []
    score = 100.0
    for section in draft.sections:
        if section.status == SectionStatus.MISSING and MISSING_LITERAL not in section.content:
            score -= 20
            issues.append(f"{section.name}:missing_literal")
        if section.status == SectionStatus.CONFLICT and CONFLICT_LITERAL not in section.content:
            score -= 20
            issues.append(f"{section.name}:conflict_literal")
        if section.status == SectionStatus.PENDING and PENDING_LITERAL not in section.content:
            score -= 20
            issues.append(f"{section.name}:pending_literal")
    if not draft.is_final is False:
        score -= 30
        issues.append("is_final_not_false")
    return max(0.0, score), issues


def score_completeness(draft: DischargeSummaryDraft) -> tuple[float, list[str]]:
    issues: list[str] = []
    present = {s.name for s in draft.sections if s.status == SectionStatus.PRESENT}
    missing = [name for name in REQUIRED_SECTIONS if name not in present]
    if missing:
        issues.extend(f"missing_section:{name}" for name in missing)
    score = 100.0 - (len(missing) * 15)
    return max(0.0, score), issues


def evaluate_summary_quality(
    draft: DischargeSummaryDraft,
    evidence_store: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    evidence_store = evidence_store or draft.evidence_references or []
    readability, r_issues = score_readability(draft)
    grounding, g_issues = score_grounding(draft, evidence_store)
    safety, s_issues = score_safety_compliance(draft)
    completeness, c_issues = score_completeness(draft)

    overall = round(
        readability * 0.35 + grounding * 0.25 + safety * 0.25 + completeness * 0.15,
        1,
    )
    return {
        "overall_score": overall,
        "readability": readability,
        "grounding": grounding,
        "safety_compliance": safety,
        "completeness": completeness,
        "issues": r_issues + g_issues + s_issues + c_issues,
    }
