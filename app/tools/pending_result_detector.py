from __future__ import annotations

import re
from typing import Any

from app.models.constants import PENDING_LITERAL
from app.models.summary_models import ClinicianReviewItem, PendingResultsReport, SafetyFlag

PENDING_PATTERNS = [
    re.compile(r"\b(pending|awaiting|in progress|not finalized)\b", re.I),
    re.compile(r"\b(culture pending|pathology pending|result pending)\b", re.I),
    re.compile(r"\b(pending labs?|pending results?)\b", re.I),
]

COMPLETED_PATTERNS = [
    re.compile(r"\b(final|completed|resulted|negative|positive)\b", re.I),
]


def _is_pending_line(line: str) -> bool:
    if any(p.search(line) for p in COMPLETED_PATTERNS) and "pending" not in line.lower():
        return False
    return any(p.search(line) for p in PENDING_PATTERNS)


def detect_pending_results(
    loaded_documents: dict[str, dict[str, Any]],
    evidence_store: list[dict[str, Any]] | None = None,
) -> tuple[list[dict[str, Any]], list[PendingResultsReport], list[ClinicianReviewItem], list[SafetyFlag]]:
    pending: list[dict[str, Any]] = []
    reports: list[PendingResultsReport] = []
    reviews: list[ClinicianReviewItem] = []
    flags: list[SafetyFlag] = []

    for doc_name, doc in loaded_documents.items():
        page_mapping = doc.get("page_mapping", {})
        for page_num, text in page_mapping.items():
            for line in text.splitlines():
                line = line.strip()
                if not line or not _is_pending_line(line):
                    continue
                entry = {
                    "description": line[:300],
                    "source_document": doc_name,
                    "page_number": int(page_num),
                    "status": PENDING_LITERAL,
                }
                pending.append(entry)
                reports.append(
                    PendingResultsReport(
                        description=entry["description"],
                        source_document=doc_name,
                        page_number=int(page_num),
                    )
                )
                reviews.append(
                    ClinicianReviewItem(
                        reason="Pending critical result",
                        details=f"Pending result: {line[:200]}",
                        section="pending_results",
                        priority="high",
                    )
                )
                flags.append(
                    SafetyFlag(
                        category="pending_result",
                        message=f"{PENDING_LITERAL}: {line[:100]}",
                        severity="medium",
                        source="pending_result_detector",
                    )
                )

    return pending, reports, reviews, flags
