"""Score discharge summary quality using clinical rubric."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from app.agents.discharge_agent import run_discharge_agent
from app.evaluation.summary_rubric import evaluate_summary_quality

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures" / "patient_folders"
REPORT_PATH = ROOT / "outputs" / "summary_quality_report.json"


def run_sample_evaluation(provider: str = "mock", limit: int | None = None) -> dict:
    load_dotenv()
    manifest = json.loads((FIXTURES / "manifest.json").read_text(encoding="utf-8"))
    scenarios = manifest["scenarios"] if limit is None else manifest["scenarios"][:limit]
    rows = []
    scores = []

    for entry in scenarios:
        folder = FIXTURES / entry["name"]
        result = run_discharge_agent(folder, llm_provider=provider)
        quality = evaluate_summary_quality(result.draft_summary, result.evidence_store.to_dict_list())
        scores.append(quality["overall_score"])
        rows.append(
            {
                "scenario": entry["name"],
                "category": entry["category"],
                "overall_score": quality["overall_score"],
                "readability": quality["readability"],
                "grounding": quality["grounding"],
                "safety_compliance": quality["safety_compliance"],
                "completeness": quality["completeness"],
                "executive_summary": bool(result.draft_summary.executive_summary),
                "issues": quality["issues"],
            }
        )

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "provider": provider,
        "sample_size": len(rows),
        "average_score": round(sum(scores) / len(scores), 1) if scores else 0,
        "min_score": min(scores) if scores else 0,
        "max_score": max(scores) if scores else 0,
        "scenarios": rows,
        "notes": (
            "Rubric-weighted score: readability (35%), evidence grounding (25%), "
            "safety literal compliance (25%), section completeness (15%)."
        ),
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    import sys

    provider = sys.argv[1] if len(sys.argv) > 1 else "mock"
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 10
    report = run_sample_evaluation(provider, limit)
    print(
        f"Summary quality ({provider}): avg {report['average_score']}/100 "
        f"(min {report['min_score']}, max {report['max_score']}) over {report['sample_size']} scenarios"
    )
