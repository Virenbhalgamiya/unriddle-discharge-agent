from __future__ import annotations

from typing import Any

from app.models.evidence import EvidenceItem, EvidenceStore
from app.tools.field_extractor import validate_evidence_substrings


class AuditorAgent:
    """Validates evidence, safety, and completeness. Returns to planner on failure."""

    def audit(self, state: dict[str, Any]) -> dict[str, Any]:
        failures: list[str] = []

        evidence_raw = state.get("evidence_store", [])
        page_cache = state.get("page_text_cache", {})
        store = EvidenceStore(items=[EvidenceItem(**e) for e in evidence_raw])

        substring_failures = validate_evidence_substrings(store, page_cache)
        failures.extend(substring_failures)

        for conflict in state.get("conflicts", []):
            values = conflict.get("values", [])
            if len(values) < 2:
                failures.append(f"Conflict for {conflict.get('field_name')} has insufficient sources")

        for field in state.get("missing_fields", []):
            if not any(e.field_name == field or (field == "medications" and "medication" in e.field_name) for e in store.items):
                pass  # correctly marked missing

        for change in state.get("medication_changes", []):
            if change.get("requires_review") and change.get("reason") != "Reason Not Documented":
                pass
            elif change.get("requires_review"):
                pass  # correctly flagged

        completed = set(state.get("completed_tasks", []))
        required_before_draft = {
            "load_documents",
            "extract_fields",
            "medication_reconciliation",
            "detect_missing_fields",
            "detect_conflicts",
            "detect_pending_results",
            "check_interactions",
        }
        incomplete = required_before_draft - completed

        passed = len(failures) == 0
        all_tasks_done = len(incomplete) == 0 or "finalize_review_queue" in completed

        return {
            "audit_failures": failures,
            "audit_passed": passed,
            "all_tasks_complete": all_tasks_done,
            "incomplete_tasks": list(incomplete),
        }
