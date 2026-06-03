"""Feature-level test runner for all patient scenarios."""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from app.agents.discharge_agent import run_discharge_agent
from app.models.constants import CONFLICT_LITERAL, MISSING_LITERAL, PENDING_LITERAL

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures" / "patient_folders"
REPORT_PATH = ROOT / "outputs" / "feature_test_report.json"


def _section(draft, name: str):
    for s in draft.sections:
        if s.name == name:
            return s
    return None


def evaluate_scenario(folder: Path, expected: dict, result) -> tuple[bool, list[str]]:
    failures: list[str] = []
    draft = result.draft_summary

    if expected.get("has_draft"):
        if not draft or not draft.sections:
            failures.append("No draft sections generated")
        if not draft.is_final is False:
            failures.append("Draft must have is_final=false")

    if expected.get("no_false_demo_conflict"):
        demo = _section(draft, "Patient Demographics")
        if demo and demo.status.value == "Conflict":
            failures.append("False demographics conflict")

    if expected.get("min_evidence") and len(result.evidence_store.items) < expected["min_evidence"]:
        failures.append(f"Evidence count {len(result.evidence_store.items)} < {expected['min_evidence']}")

    if expected.get("has_missing"):
        missing_field = expected.get("missing_field", "")
        field_section_map = {
            "diagnosis": "Principal Diagnosis",
            "allergies": "Allergies",
            "discharge_date": "Discharge Date",
            "demographics": "Patient Demographics",
            "follow_up": "Follow-up Instructions",
            "discharge_condition": "Discharge Condition",
            "medications": "Discharge Medications",
        }
        section_name = field_section_map.get(missing_field)
        if section_name:
            sec = _section(draft, section_name)
            if not sec or MISSING_LITERAL not in sec.content:
                failures.append(f"Expected MISSING for {section_name}, got: {sec.content if sec else 'none'}")

    if expected.get("has_conflict"):
        if not result.conflicts and not any(CONFLICT_LITERAL in s.content for s in draft.sections):
            failures.append("Expected conflict not detected")

    if expected.get("has_pending"):
        sec = _section(draft, "Pending Results")
        if not result.pending_results and (not sec or PENDING_LITERAL not in sec.content):
            failures.append("Expected pending results not detected")

    if expected.get("has_med_changes"):
        if not result.medication_changes:
            failures.append("Expected medication changes")

    if expected.get("has_high_interaction"):
        if not any(f.category == "drug_interaction" for f in result.safety_flags):
            failures.append("Expected high-risk drug interaction flag")

    if expected.get("min_safety_flags"):
        if len(result.safety_flags) < expected["min_safety_flags"]:
            failures.append(f"Safety flags {len(result.safety_flags)} < {expected['min_safety_flags']}")

    if expected.get("max_tool_steps"):
        tool_steps = [t for t in result.trace_log if t.tool_name not in ("planner", "auditor")]
        if len(tool_steps) > expected["max_tool_steps"]:
            failures.append(f"Tool steps {len(tool_steps)} exceeded {expected['max_tool_steps']}")

    if not result.trace_log:
        failures.append("No execution trace generated")

    if not result.output_dir or not Path(result.output_dir).exists():
        failures.append("Output directory not created")

    min_quality = expected.get("min_quality_score")
    if min_quality is not None:
        score = getattr(result.draft_summary, "quality_score", 0) or 0
        if score < min_quality:
            failures.append(f"Quality score {score} < {min_quality}")

    if expected.get("requires_executive_summary"):
        if not getattr(result.draft_summary, "executive_summary", ""):
            failures.append("Executive summary not generated")

    if expected.get("min_hospital_course_words"):
        hc = _section(draft, "Hospital Course")
        words = len(hc.content.split()) if hc else 0
        if words < expected["min_hospital_course_words"]:
            failures.append(f"Hospital course too short: {words} words")

    return len(failures) == 0, failures


def run_all(provider: str = "mock") -> dict:
    load_dotenv()
    manifest_path = FIXTURES / "manifest.json"
    if not manifest_path.exists():
        from scripts.generate_feature_fixtures import generate_all

        generate_all()

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    results = []
    passed = 0
    failed = 0
    start = time.time()

    for entry in manifest["scenarios"]:
        folder = FIXTURES / entry["name"]
        t0 = time.time()
        try:
            agent_result = run_discharge_agent(folder, llm_provider=provider)
            ok, failures = evaluate_scenario(folder, entry["expected"], agent_result)
        except Exception as exc:
            ok = False
            failures = [str(exc)]
            agent_result = None

        if ok:
            passed += 1
        else:
            failed += 1

        results.append(
            {
                "scenario": entry["name"],
                "category": entry["category"],
                "passed": ok,
                "failures": failures,
                "status": getattr(agent_result, "status", "error"),
                "duration_sec": round(time.time() - t0, 2),
                "pdf_count": entry["pdf_count"],
            }
        )

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "provider": provider,
        "total_scenarios": len(results),
        "passed": passed,
        "failed": failed,
        "pass_rate": round(passed / len(results) * 100, 1) if results else 0,
        "total_pdfs": manifest.get("total_pdfs", 0),
        "duration_sec": round(time.time() - start, 1),
        "results": results,
    }

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    import sys

    provider = sys.argv[1] if len(sys.argv) > 1 else "mock"
    if provider == "anthropic":
        load_dotenv()
    report = run_all(provider)
    print(f"Feature tests: {report['passed']}/{report['total_scenarios']} passed ({report['pass_rate']}%)")
    if report["failed"]:
        print("Failures:")
        for r in report["results"]:
            if not r["passed"]:
                print(f"  - {r['scenario']}: {r['failures']}")
