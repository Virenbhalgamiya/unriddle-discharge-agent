from __future__ import annotations

from difflib import SequenceMatcher
from typing import Any

from app.models.summary_models import DischargeSummaryDraft


def normalized_edit_distance(original: str, edited: str) -> float:
    if not original and not edited:
        return 1.0
    ratio = SequenceMatcher(None, original, edited).ratio()
    return 1.0 - ratio


def section_accuracy(draft: DischargeSummaryDraft, edited: DischargeSummaryDraft) -> float:
    orig_map = {s.name: s.content for s in draft.sections}
    edit_map = {s.name: s.content for s in edited.sections}
    if not orig_map:
        return 0.0
    matches = sum(1 for k, v in orig_map.items() if edit_map.get(k, "") == v)
    return matches / len(orig_map)


def field_accuracy(draft: DischargeSummaryDraft, edited: DischargeSummaryDraft) -> float:
    key_sections = [
        "Principal Diagnosis",
        "Admission Date",
        "Discharge Date",
        "Allergies",
        "Discharge Condition",
    ]
    orig_map = {s.name: s.content for s in draft.sections}
    edit_map = {s.name: s.content for s in edited.sections}
    if not key_sections:
        return 0.0
    matches = sum(1 for k in key_sections if orig_map.get(k) == edit_map.get(k))
    return matches / len(key_sections)


def medication_accuracy(draft: DischargeSummaryDraft, edited: DischargeSummaryDraft) -> float:
    orig = next((s.content for s in draft.sections if s.name == "Medication Changes"), "")
    edit = next((s.content for s in edited.sections if s.name == "Medication Changes"), "")
    if not orig:
        return 1.0
    return SequenceMatcher(None, orig, edit).ratio()


def recall_metric(detected: list[Any], expected: list[Any]) -> float:
    if not expected:
        return 1.0
    if not detected:
        return 0.0
    return min(len(detected) / len(expected), 1.0)


def compute_reward(
    draft: DischargeSummaryDraft,
    edited: DischargeSummaryDraft,
    metrics_context: dict[str, Any] | None = None,
) -> dict[str, float]:
    ctx = metrics_context or {}
    orig_text = " ".join(s.content for s in draft.sections)
    edit_text = " ".join(s.content for s in edited.sections)

    ned = normalized_edit_distance(orig_text, edit_text)
    edit_score = 1.0 - ned

    scores = {
        "normalized_edit_distance": ned,
        "edit_score": edit_score,
        "section_accuracy": section_accuracy(draft, edited),
        "field_accuracy": field_accuracy(draft, edited),
        "medication_accuracy": medication_accuracy(draft, edited),
        "conflict_detection_accuracy": recall_metric(
            ctx.get("conflicts", []), ctx.get("expected_conflicts", ctx.get("conflicts", []))
        ),
        "missing_data_recall": recall_metric(
            ctx.get("missing_fields", []), ctx.get("expected_missing", ctx.get("missing_fields", []))
        ),
        "pending_result_recall": recall_metric(
            ctx.get("pending_results", []), ctx.get("expected_pending", ctx.get("pending_results", []))
        ),
        "safety_flag_recall": recall_metric(
            ctx.get("safety_flags", []), ctx.get("expected_flags", ctx.get("safety_flags", []))
        ),
    }
    weights = {
        "edit_score": 0.25,
        "section_accuracy": 0.15,
        "field_accuracy": 0.15,
        "medication_accuracy": 0.15,
        "conflict_detection_accuracy": 0.1,
        "missing_data_recall": 0.1,
        "pending_result_recall": 0.05,
        "safety_flag_recall": 0.05,
    }
    scores["composite_reward"] = sum(scores[k] * w for k, w in weights.items())
    return scores
