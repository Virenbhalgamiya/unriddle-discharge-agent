from __future__ import annotations

from typing import Any, Callable

from app.memory.correction_memory import CorrectionMemory
from app.tools.conflict_detector import detect_conflicts
from app.tools.escalation_tool import escalate_extraction_failure, flag_for_clinician_review
from app.tools.field_extractor import extract_fields_from_documents
from app.tools.interaction_checker import check_interactions
from app.tools.medication_reconciliation import reconcile_medications
from app.tools.missing_data_detector import detect_missing_fields
from app.tools.pdf_reader import PDFReadResult, load_patient_folder
from app.tools.pending_result_detector import detect_pending_results

ToolFn = Callable[..., dict[str, Any]]


def _merge_unique_dicts(existing: list[dict], new: list[dict], key: str = "id") -> list[dict]:
    seen = {item.get(key) for item in existing if item.get(key)}
    merged = list(existing)
    for item in new:
        item_key = item.get(key)
        if item_key and item_key in seen:
            continue
        if item_key:
            seen.add(item_key)
        merged.append(item)
    return merged


def _merge_flags(existing: list[dict], new: list) -> list[dict]:
    return _merge_unique_dicts(existing, [f.model_dump(mode="json") if hasattr(f, "model_dump") else f for f in new], key="id")


def _merge_reviews(existing: list[dict], new: list) -> list[dict]:
    return _merge_unique_dicts(existing, [r.model_dump(mode="json") if hasattr(r, "model_dump") else r for r in new], key="id")


def run_load_documents(state: dict[str, Any], memory: CorrectionMemory | None = None) -> dict[str, Any]:
    config = state.get("config", {})
    pdf_cfg = config.get("pdf_reader", {})
    folder = state["patient_folder"]
    documents, failures = load_patient_folder(
        folder,
        max_retries=pdf_cfg.get("max_retries", 3),
        timeout_seconds=pdf_cfg.get("timeout_seconds", 30),
        ocr_enabled=pdf_cfg.get("ocr_enabled", True),
        ocr_dpi_scale=pdf_cfg.get("ocr_dpi_scale", 2),
        ocr_timeout_seconds=pdf_cfg.get("ocr_timeout_seconds", 600),
        progress_callback=state.get("pdf_progress_callback"),
    )

    loaded: dict[str, dict[str, Any]] = {}
    reviews = list(state.get("clinician_review_items", []))
    flags = list(state.get("safety_flags", []))

    for name, result in documents.items():
        loaded[name] = {
            "success": result.success,
            "file_path": result.file_path,
            "metadata": result.metadata,
            "page_mapping": {str(k): v for k, v in result.page_mapping.items()},
            "errors": result.errors,
            "retries": result.retries,
            "parser_used": result.parser_used,
            "page_count": len(result.pages),
        }
        if not result.success:
            review, flag = escalate_extraction_failure(name, result.errors, memory)
            reviews = _merge_reviews(reviews, [review])
            flags = _merge_flags(flags, [flag])

    return {
        "loaded_documents": loaded,
        "clinician_review_items": reviews,
        "safety_flags": flags,
        "failures": failures,
    }


def run_extract_fields(state: dict[str, Any], _memory: CorrectionMemory | None = None) -> dict[str, Any]:
    documents_raw = state.get("loaded_documents", {})
    pdf_results: dict[str, PDFReadResult] = {}
    for name, doc in documents_raw.items():
        if not doc.get("success"):
            continue
        mapping = {int(k): v for k, v in doc.get("page_mapping", {}).items()}
        pages = [{"page_number": k, "text": v} for k, v in mapping.items()]
        from app.tools.pdf_reader import PDFPage

        pdf_results[name] = PDFReadResult(
            success=True,
            file_path=doc.get("file_path", name),
            pages=[PDFPage(page_number=p["page_number"], text=p["text"]) for p in pages],
            metadata=doc.get("metadata", {}),
            page_mapping=mapping,
            parser_used=doc.get("parser_used", ""),
        )

    store, page_cache = extract_fields_from_documents(pdf_results)
    existing = state.get("evidence_store", [])
    new_items = store.to_dict_list()
    merged = _merge_unique_dicts(existing, new_items, key="id")
    cache = dict(state.get("page_text_cache", {}))
    cache.update(page_cache)
    return {"evidence_store": merged, "page_text_cache": cache}


def run_medication_reconciliation(state: dict[str, Any], memory: CorrectionMemory | None = None) -> dict[str, Any]:
    changes, report, reviews, flags = reconcile_medications(
        state.get("evidence_store", []),
        state.get("loaded_documents", {}),
    )
    report.patient_id = state.get("patient_id", "")
    return {
        "medication_changes": changes,
        "medication_report": report.model_dump(mode="json"),
        "clinician_review_items": _merge_reviews(state.get("clinician_review_items", []), reviews),
        "safety_flags": _merge_flags(state.get("safety_flags", []), flags),
    }


def run_detect_missing_fields(state: dict[str, Any], _memory: CorrectionMemory | None = None) -> dict[str, Any]:
    required = state.get("config", {}).get("required_fields")
    missing, flags, reviews = detect_missing_fields(state.get("evidence_store", []), required)
    return {
        "missing_fields": missing,
        "safety_flags": _merge_flags(state.get("safety_flags", []), flags),
        "clinician_review_items": _merge_reviews(state.get("clinician_review_items", []), reviews),
    }


def run_detect_conflicts(state: dict[str, Any], _memory: CorrectionMemory | None = None) -> dict[str, Any]:
    conflicts, _reports, reviews, flags = detect_conflicts(state.get("evidence_store", []))
    return {
        "conflicts": conflicts,
        "safety_flags": _merge_flags(state.get("safety_flags", []), flags),
        "clinician_review_items": _merge_reviews(state.get("clinician_review_items", []), reviews),
    }


def run_detect_pending_results(state: dict[str, Any], _memory: CorrectionMemory | None = None) -> dict[str, Any]:
    pending, _reports, reviews, flags = detect_pending_results(
        state.get("loaded_documents", {}),
        state.get("evidence_store", []),
    )
    return {
        "pending_results": pending,
        "safety_flags": _merge_flags(state.get("safety_flags", []), flags),
        "clinician_review_items": _merge_reviews(state.get("clinician_review_items", []), reviews),
    }


def run_check_interactions(state: dict[str, Any], _memory: CorrectionMemory | None = None) -> dict[str, Any]:
    _output, _interactions, reviews, flags = check_interactions(state.get("evidence_store", []))
    return {
        "safety_flags": _merge_flags(state.get("safety_flags", []), flags),
        "clinician_review_items": _merge_reviews(state.get("clinician_review_items", []), reviews),
    }


def run_finalize_review_queue(state: dict[str, Any], memory: CorrectionMemory | None = None) -> dict[str, Any]:
    completed = list(state.get("completed_tasks", []))
    if "finalize_review_queue" not in completed:
        completed.append("finalize_review_queue")
    pending = [t for t in state.get("pending_tasks", []) if t != "finalize_review_queue"]
    return {"status": "review_queue_finalized", "completed_tasks": completed, "pending_tasks": pending}


TOOL_REGISTRY: dict[str, Callable[..., dict[str, Any]]] = {
    "load_documents": run_load_documents,
    "extract_fields": run_extract_fields,
    "medication_reconciliation": run_medication_reconciliation,
    "detect_missing_fields": run_detect_missing_fields,
    "detect_conflicts": run_detect_conflicts,
    "detect_pending_results": run_detect_pending_results,
    "check_interactions": run_check_interactions,
    "finalize_review_queue": run_finalize_review_queue,
}

TASK_TO_TOOL = {
    "load_documents": "load_documents",
    "extract_fields": "extract_fields",
    "medication_reconciliation": "medication_reconciliation",
    "detect_missing_fields": "detect_missing_fields",
    "detect_conflicts": "detect_conflicts",
    "detect_pending_results": "detect_pending_results",
    "check_interactions": "check_interactions",
    "finalize_review_queue": "finalize_review_queue",
}


def execute_tool(tool_name: str, state: dict[str, Any], memory: CorrectionMemory | None = None) -> dict[str, Any]:
    fn = TOOL_REGISTRY.get(tool_name)
    if fn is None:
        review, flag, _ = flag_for_clinician_review(
            reason="Tool failure",
            details=f"Unknown tool: {tool_name}",
            priority="high",
            memory=memory,
        )
        return {
            "error": f"Unknown tool: {tool_name}",
            "clinician_review_items": _merge_reviews(state.get("clinician_review_items", []), [review]),
            "safety_flags": _merge_flags(state.get("safety_flags", []), [flag]),
        }
    try:
        return fn(state, memory)
    except Exception as exc:
        review, flag, _ = flag_for_clinician_review(
            reason="Tool failure",
            details=f"Tool {tool_name} crashed: {exc}",
            priority="high",
            memory=memory,
        )
        return {
            "error": str(exc),
            "clinician_review_items": _merge_reviews(state.get("clinician_review_items", []), [review]),
            "safety_flags": _merge_flags(state.get("safety_flags", []), [flag]),
        }
