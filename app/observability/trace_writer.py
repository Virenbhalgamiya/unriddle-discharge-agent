from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.models.summary_models import TraceStep


def append_trace_step(state: dict[str, Any], step: TraceStep) -> list[dict[str, Any]]:
    trace = list(state.get("trace_log", []))
    trace.append(step.model_dump(mode="json"))
    return trace


def write_trace(
    patient_id: str,
    trace_log: list[dict[str, Any]],
    traces_dir: Path,
) -> dict[str, str]:
    traces_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    json_path = traces_dir / f"{patient_id}_{timestamp}.json"
    txt_path = traces_dir / f"{patient_id}_{timestamp}.txt"

    payload = {"patient_id": patient_id, "generated_at": datetime.now(timezone.utc).isoformat(), "steps": trace_log}
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    lines = [f"Execution Trace — Patient: {patient_id}", "=" * 60, ""]
    for step in trace_log:
        lines.extend(
            [
                f"Step {step.get('step_number', '?')}",
                f"  Reasoning: {step.get('reasoning_summary', '')}",
                f"  Action: {step.get('chosen_action', '')}",
                f"  Tool: {step.get('tool_name', '')}",
                f"  Input: {json.dumps(step.get('tool_input', {}), default=str)[:200]}",
                f"  Output: {json.dumps(step.get('tool_output', {}), default=str)[:300]}",
                f"  Result: {step.get('result', '')}",
                f"  Errors: {step.get('errors', [])}",
                f"  Retries: {step.get('retries', 0)}",
                f"  Next: {step.get('next_decision', '')}",
                "",
            ]
        )
    txt_path.write_text("\n".join(lines), encoding="utf-8")
    return {"json": str(json_path), "txt": str(txt_path)}


def write_outputs(
    patient_id: str,
    outputs_dir: Path,
    draft: dict[str, Any],
    medication_report: dict[str, Any],
    conflicts: list[dict[str, Any]],
    pending_results: list[dict[str, Any]],
    review_queue: list[dict[str, Any]],
    safety_flags: list[dict[str, Any]],
    evidence_store: list[dict[str, Any]],
) -> Path:
    out_dir = outputs_dir / patient_id
    out_dir.mkdir(parents=True, exist_ok=True)

    files = {
        "discharge_summary_draft.json": draft,
        "medication_reconciliation.json": medication_report,
        "conflict_report.json": {"conflicts": conflicts},
        "pending_results.json": {"pending_results": pending_results},
        "clinician_review_queue.json": {"items": review_queue},
        "safety_flags.json": {"flags": safety_flags},
        "evidence_store.json": {"evidence": evidence_store},
    }
    for name, data in files.items():
        (out_dir / name).write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
    return out_dir
