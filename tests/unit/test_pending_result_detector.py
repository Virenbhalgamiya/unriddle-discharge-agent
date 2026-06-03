from app.tools.pending_result_detector import detect_pending_results


def test_pending_lab():
    docs = {"labs.pdf": {"page_mapping": {1: "Blood culture pending results."}}}
    pending, reports, reviews, flags = detect_pending_results(docs)
    assert len(pending) >= 1
    assert pending[0]["status"] == "PENDING"


def test_pending_pathology():
    docs = {"labs.pdf": {"page_mapping": {1: "Pathology pending final review."}}}
    pending, _, _, _ = detect_pending_results(docs)
    assert len(pending) >= 1


def test_completed_result():
    docs = {"labs.pdf": {"page_mapping": {1: "Culture final: negative."}}}
    pending, _, _, _ = detect_pending_results(docs)
    assert pending == []
