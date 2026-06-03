# Submit checklist

Complete these steps before the 48-hour deadline.

## Google Form

**Form:** https://docs.google.com/forms/d/e/1FAIpQLSfZPmXIi8AdfBx2lDAw3bObv75ikfGrU-33XBSaLP19mXuM3Q/viewform

| Field | Value |
|-------|--------|
| GitHub repo | https://github.com/viren-cognitivTrust/unriddle-discharge-agent (local commit ready; no further push until you choose) |
| Video demo (Loom 3–5 min) | _[LOOM LINK — record later]_ |
| Part 2 attempted? | Yes — correction memory + simulated doctor + `outputs/evaluation/learning_report.json` |
| Notes | Part 1 complete; 53 synthetic patients batch-run; video pending |

## Video script (when ready)

1. **Complete patient** — Streamlit → `complete_1` → Run Agent → Clinical Narrative + trace  
2. **Conflict or pending** — e.g. `conflict_diagnosis` or `pending_culture` → show CONFLICT/PENDING literals  
3. **Escalation moment** — Agent Trace step where auditor/tool flagged missing/conflict instead of guessing  
4. **Part 2 (optional in video)** — show `learning_report.json` before/after delta  

## Pre-submit verification

```powershell
$env:PYTHONPATH='.'
python scripts/run_submission_batch.py mock
python -c "from app.evaluation.evaluation_runner import EvaluationRunner; EvaluationRunner().run_full_evaluation('mock')"
python scripts/run_feature_tests.py mock
pytest tests/ -q -m "not slow"
```

All should pass. Manifest at `outputs/submission_manifest.json`.

## Do not submit

- Real patient PDFs (`fixtures/patient_real/`)  
- `.env` or API keys  
