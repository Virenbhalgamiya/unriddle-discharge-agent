#!/usr/bin/env python3
"""Batch-run discharge agent on all official assignment patients and write submission manifest."""

from __future__ import annotations

import json
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.agents.discharge_agent import run_discharge_agent

OFFICIAL_ROOT = ROOT / "fixtures" / "official_patients"
OUTPUT_ARTIFACTS = ROOT / "outputs" / "submission_artifacts"
TRACE_SUBMISSION = ROOT / "traces" / "submission"
MANIFEST_PATH = ROOT / "outputs" / "submission_manifest.json"


def _discover_patient_folders(root: Path) -> list[Path]:
    if not root.exists():
        raise FileNotFoundError(
            f"Official patient root not found: {root}. See fixtures/official_patients/README.md"
        )
    folders = sorted(p for p in root.iterdir() if p.is_dir() and list(p.glob("*.pdf")))
    if not folders:
        raise FileNotFoundError(f"No patient PDF folders under {root}")
    return folders


def _copy_patient_artifacts(patient_id: str, output_dir: str, trace_paths: dict[str, str]) -> None:
    dest = OUTPUT_ARTIFACTS / patient_id
    if dest.exists():
        shutil.rmtree(dest)
    src = Path(output_dir)
    if src.exists():
        shutil.copytree(src, dest)

    TRACE_SUBMISSION.mkdir(parents=True, exist_ok=True)
    for kind, path in trace_paths.items():
        src_trace = Path(path)
        if src_trace.exists():
            shutil.copy2(src_trace, TRACE_SUBMISSION / src_trace.name)


def run_batch(provider: str = "mock") -> dict:
    folders = _discover_patient_folders(OFFICIAL_ROOT)
    OUTPUT_ARTIFACTS.mkdir(parents=True, exist_ok=True)
    TRACE_SUBMISSION.mkdir(parents=True, exist_ok=True)

    entries: list[dict] = []
    failed = 0
    start = time.time()

    for folder in folders:
        patient_id = folder.name
        t0 = time.time()
        try:
            result = run_discharge_agent(folder, llm_provider=provider)
            section_count = len(result.draft_summary.sections) if result.draft_summary else 0
            ok = section_count > 0 and result.status in ("complete", "max_steps_reached")
            trace_json = result.trace_paths.get("json", "") if result.trace_paths else ""
            if ok:
                _copy_patient_artifacts(patient_id, result.output_dir, result.trace_paths or {})
            else:
                failed += 1
            entries.append(
                {
                    "patient_id": patient_id,
                    "status": result.status,
                    "passed": ok,
                    "output_dir": result.output_dir,
                    "trace_json": trace_json,
                    "trace_submission": str(TRACE_SUBMISSION / Path(trace_json).name) if trace_json else "",
                    "evidence_count": len(result.evidence_store.items),
                    "safety_flags": len(result.safety_flags),
                    "conflicts": len(result.conflicts),
                    "pending_results": len(result.pending_results),
                    "quality_score": result.draft_summary.quality_score,
                    "duration_sec": round(time.time() - t0, 2),
                }
            )
        except Exception as exc:
            failed += 1
            entries.append(
                {
                    "patient_id": patient_id,
                    "status": "error",
                    "passed": False,
                    "error": str(exc),
                    "duration_sec": round(time.time() - t0, 2),
                }
            )

    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "provider": provider,
        "source_root": str(OFFICIAL_ROOT),
        "total_patients": len(entries),
        "passed": sum(1 for e in entries if e.get("passed")),
        "failed": failed,
        "duration_sec": round(time.time() - start, 1),
        "artifacts_dir": str(OUTPUT_ARTIFACTS),
        "traces_dir": str(TRACE_SUBMISSION),
        "patients": entries,
    }
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def main() -> int:
    provider = sys.argv[1] if len(sys.argv) > 1 else "mock"
    manifest = run_batch(provider)
    print(
        f"Submission batch: {manifest['passed']}/{manifest['total_patients']} passed "
        f"in {manifest['duration_sec']}s"
    )
    print(f"Manifest: {MANIFEST_PATH}")
    if manifest["failed"]:
        for p in manifest["patients"]:
            if not p.get("passed"):
                print(f"  FAIL {p['patient_id']}: {p.get('error', p.get('status'))}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
