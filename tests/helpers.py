from io import BytesIO
from pathlib import Path

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas


def create_test_pdf(path: Path, lines: list[str]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(path), pagesize=letter)
    y = 750
    for line in lines:
        c.drawString(72, y, line[:100])
        y -= 20
        if y < 72:
            c.showPage()
            y = 750
    c.save()
    return path


def create_scanned_test_pdf(path: Path, lines: list[str]) -> Path:
    """Create an image-only PDF (no text layer) for OCR tests."""
    import fitz
    from PIL import Image, ImageDraw, ImageFont

    path.parent.mkdir(parents=True, exist_ok=True)
    doc = fitz.open()
    y_start = 40
    line_height = 36
    height = max(200, y_start + len(lines) * line_height + 40)
    page = doc.new_page(width=850, height=height)

    img = Image.new("RGB", (850, height), "white")
    draw = ImageDraw.Draw(img)
    font = ImageFont.load_default()
    y = y_start
    for line in lines:
        draw.text((50, y), line[:100], fill="black", font=font)
        y += line_height

    buf = BytesIO()
    img.save(buf, format="PNG")
    page.insert_image(page.rect, stream=buf.getvalue())
    doc.save(str(path))
    doc.close()
    return path


def create_complete_patient_folder(folder: Path) -> Path:
    create_test_pdf(
        folder / "admission_note.pdf",
        [
            "Patient Name: John Doe",
            "DOB: 01/15/1970",
            "Admission Date: 03/01/2026",
            "Discharge Date: 03/05/2026",
            "Principal Diagnosis: Pneumonia",
            "Secondary Diagnoses: Hypertension",
            "Hospital Course: Patient treated with antibiotics.",
            "Procedures: Chest X-ray",
            "Allergies: Penicillin",
            "Follow-up: Primary care in 1 week",
            "Discharge Condition: Stable",
        ],
    )
    create_test_pdf(
        folder / "medication_admission.pdf",
        ["Medications:", "- Lisinopril 10mg PO daily", "- Aspirin 81mg PO daily"],
    )
    create_test_pdf(
        folder / "medication_discharge.pdf",
        ["Medications:", "- Lisinopril 10mg PO daily", "- Warfarin 5mg PO daily"],
    )
    create_test_pdf(folder / "labs.pdf", ["WBC: 12.5 K/uL", "Culture pending"])
    create_test_pdf(folder / "progress_note_1.pdf", ["Patient improving on antibiotics."])
    return folder
