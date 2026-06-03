from app.tools.field_extractor import extract_fields_from_page


def test_unstructured_prose_extraction():
    text = """
    History & Physical — Jane Smith (DOB 02/20/1985)
    Patient admitted on 03/01/2026 with pneumonia.
    Hospital Course: Received IV antibiotics; improved.
    Plan: Primary care in 1 week
    Discharged on 03/05/2026 in stable condition
    Allergies: Penicillin
    """
    items = extract_fields_from_page(text, "hp.pdf", 1)
    fields = {i.field_name for i in items}
    assert "patient_name" in fields
    assert "admission_date" in fields
    assert "hospital_course" in fields
