from app.tools.field_extractor import extract_fields_from_documents, extract_fields_from_page
from app.tools.pdf_reader import PDFReadResult, PDFPage


def test_hospital_course_does_not_bleed():
    text = "\n".join(
        [
            "Patient Name: John Doe",
            "Admission Date: 03/01/2026",
            "Hospital Course: Patient treated with antibiotics.",
            "Procedures: Chest X-ray",
            "Allergies: Penicillin",
            "Follow-up: Primary care in 1 week",
            "Discharge Condition: Stable",
        ]
    )
    items = extract_fields_from_page(text, "admission_note.pdf", 1)
    by_field = {i.field_name: i.value for i in items}
    assert by_field["hospital_course"] == "Patient treated with antibiotics."
    assert by_field["procedures"] == "Chest X-ray"
    assert by_field["allergies"] == "Penicillin"
    assert by_field["follow_up_instructions"] == "Primary care in 1 week"
    assert by_field["discharge_condition"] == "Stable"


def test_progress_note_diagnosis_extraction():
    text = "Principal Diagnosis: Bronchitis"
    items = extract_fields_from_page(text, "progress_note_1.pdf", 1)
    assert any(i.field_name == "principal_diagnosis" and i.value == "Bronchitis" for i in items)


def test_content_based_med_lab_extraction():
    text = "\n".join(
        [
            "Discharge Medications:",
            "- Lisinopril 10mg PO daily",
            "Lab Results:",
            "WBC: 12.5 K/uL",
        ]
    )
    doc = PDFReadResult(
        success=True,
        file_path="patient_chart.pdf",
        pages=[PDFPage(page_number=1, text=text)],
        page_mapping={1: text},
        parser_used="pymupdf+ocr",
    )
    store, _ = extract_fields_from_documents({"patient_chart.pdf": doc})
    fields = {i.field_name for i in store.items}
    assert "discharge_medications" in fields
    assert "lab_results" in fields
