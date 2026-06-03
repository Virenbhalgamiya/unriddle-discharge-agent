import json
from pathlib import Path

from app.tools.conflict_detector import detect_conflicts
from app.tools.medication_reconciliation import reconcile_medications
from app.tools.missing_data_detector import detect_missing_fields
from app.tools.pending_result_detector import detect_pending_results


GOLDEN_DIR = Path(__file__).parent / "golden"


def test_medication_reconciliation_regression():
    evidence = [
        {"field_name": "admission_medications", "value": "Aspirin 81mg PO daily", "id": "1"},
        {"field_name": "discharge_medications", "value": "Warfarin 5mg PO daily", "id": "2"},
    ]
    _, report, _, _ = reconcile_medications(evidence, {"n.pdf": {"page_mapping": {1: ""}}})
    golden_path = GOLDEN_DIR / "med_recon_summary.json"
    if golden_path.exists():
        golden = json.loads(golden_path.read_text())
        assert report.admission_count == golden["admission_count"]
    else:
        GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
        golden_path.write_text(json.dumps({"admission_count": report.admission_count, "discharge_count": report.discharge_count}))


def test_conflict_detection_regression():
    evidence = [
        {"field_name": "discharge_date", "value": "03/01/2026", "source_document": "a.pdf", "page_number": 1, "id": "1"},
        {"field_name": "discharge_date", "value": "03/02/2026", "source_document": "b.pdf", "page_number": 1, "id": "2"},
    ]
    conflicts, _, _, _ = detect_conflicts(evidence)
    assert len(conflicts) == 1


def test_pending_results_regression():
    docs = {"labs.pdf": {"page_mapping": {1: "Culture pending"}}}
    pending, _, _, _ = detect_pending_results(docs)
    assert len(pending) >= 1


def test_missing_data_regression():
    missing, flags, _ = detect_missing_fields([])
    assert "principal_diagnosis" in missing
    assert flags
