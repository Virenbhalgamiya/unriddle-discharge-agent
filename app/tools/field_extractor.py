from __future__ import annotations

import re
from typing import Any

from app.models.evidence import EvidenceItem, EvidenceStore
from app.tools.pdf_reader import PDFReadResult

# Ordered section headers used to bound multi-line extraction.
SECTION_HEADERS = [
    "Patient Name",
    "Name",
    "DOB",
    "Date of Birth",
    "MRN",
    "Medical Record",
    "Admission Date",
    "Admitted",
    "Discharge Date",
    "Discharged",
    "Principal Diagnosis",
    "Primary Diagnosis",
    "Secondary Diagnoses",
    "Secondary Diagnosis",
    "Comorbidities",
    "Hospital Course",
    "Clinical Course",
    "Procedures",
    "Procedure",
    "Surgery",
    "Allergies",
    "Allergy",
    "Follow-up",
    "Follow up",
    "Followup Instructions",
    "Followup",
    "Discharge Condition",
    "Condition at Discharge",
    "Medications",
    "Current Medications",
    "Diagnosis",
]

HEADER_PATTERN = re.compile(
    r"^(" + "|".join(re.escape(h) for h in SECTION_HEADERS) + r")\s*[:]\s*(.*)$",
    re.I,
)


def _parse_sections(text: str) -> list[tuple[str, str]]:
    """Parse label:value lines from clinical note text."""
    sections: list[tuple[str, str]] = []
    current_label: str | None = None
    current_lines: list[str] = []

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        match = HEADER_PATTERN.match(line)
        if match:
            if current_label and current_lines:
                sections.append((current_label, " ".join(current_lines).strip()))
            current_label = match.group(1).strip()
            first_value = match.group(2).strip()
            current_lines = [first_value] if first_value else []
        elif current_label:
            current_lines.append(line)

    if current_label and current_lines:
        sections.append((current_label, " ".join(current_lines).strip()))
    return sections


def _label_matches(label: str, candidates: list[str]) -> bool:
    norm = label.lower().replace("-", " ").strip()
    for candidate in candidates:
        if norm == candidate.lower().replace("-", " ").strip():
            return True
    return False


def _find_section_value(sections: list[tuple[str, str]], labels: list[str]) -> str | None:
    for label, value in sections:
        if _label_matches(label, labels) and value:
            return value[:500]
    return None


def _add_evidence(
    store: EvidenceStore,
    value: str,
    doc_name: str,
    page_num: int,
    field_name: str,
    source_text: str,
) -> None:
    if value and len(value.strip()) > 0:
        store.add(
            EvidenceItem(
                value=value.strip()[:500],
                source_document=doc_name,
                page_number=page_num,
                field_name=field_name,
                source_text=source_text[:2000],
            )
        )


MED_LINE = re.compile(
    r"^[\-\*]?\s*([A-Za-z][A-Za-z0-9\s\-]+?)(?:\s+(\d+\s*(?:mg|mcg|g|units?)))?"
    r"(?:\s+(PO|IV|IM|SC|subcutaneous|oral))?(?:\s+(daily|BID|TID|QID|q\d+h))?",
    re.I,
)

MED_SECTION_HINT = re.compile(
    r"(?:discharge\s+medications?|current\s+medications?|medications?\s*at\s+discharge|"
    r"home\s+medications?|medications?\s*[:])",
    re.I,
)
ADMISSION_MED_HINT = re.compile(
    r"(?:admission\s+medications?|medications?\s+on\s+admission|meds?\s+on\s+admit)",
    re.I,
)
LAB_SECTION_HINT = re.compile(
    r"(?:lab\s+results?|laboratory|cbc|chemistry|hematology|bmp|cmp|blood\s+work)",
    re.I,
)
LAB_LINE = re.compile(r"^(.+?)\s*[:]\s*([\d.]+)\s*(mg/dL|mmol/L|g/dL|K/uL|mEq/L|%)?$", re.I)

HOSPITAL_COURSE_MAX_CHARS = 3000
HOSPITAL_COURSE_MAX_SNIPPETS = 15


def extract_medications(text: str, doc_name: str, page_num: int, field_name: str) -> list[EvidenceItem]:
    items: list[EvidenceItem] = []
    seen: set[str] = set()
    for match in MED_LINE.finditer(text):
        name = match.group(1).strip()
        dose = match.group(2) or ""
        route = match.group(3) or ""
        freq = match.group(4) or ""
        value = " ".join(p for p in [name, dose, route, freq] if p).strip()
        key = value.lower()
        if name and len(name) > 2 and key not in seen:
            seen.add(key)
            items.append(
                EvidenceItem(
                    value=value,
                    source_document=doc_name,
                    page_number=page_num,
                    field_name=field_name,
                    source_text=text[:2000],
                )
            )
    med_section = re.search(r"(?:Medications?|Current Medications?)\s*[:]\s*(.+?)(?:\n\n|\Z)", text, re.I | re.S)
    if med_section:
        block = med_section.group(1)
        for line in block.splitlines():
            line = line.strip(" -\t")
            key = line.lower()
            if line and len(line) > 2 and not line.lower().startswith("medication") and key not in seen:
                seen.add(key)
                items.append(
                    EvidenceItem(
                        value=line[:200],
                        source_document=doc_name,
                        page_number=page_num,
                        field_name=field_name,
                        source_text=text[:2000],
                    )
                )
    return items


def extract_fields_from_page(
    text: str,
    doc_name: str,
    page_num: int,
) -> list[EvidenceItem]:
    """Extract structured clinical fields from a single page."""
    items: list[EvidenceItem] = []
    sections = _parse_sections(text)
    source_text = text[:2000]

    field_map: list[tuple[str, list[str]]] = [
        ("patient_name", ["Patient Name", "Name"]),
        ("patient_dob", ["DOB", "Date of Birth"]),
        ("patient_mrn", ["MRN", "Medical Record"]),
        ("admission_date", ["Admission Date", "Admitted"]),
        ("discharge_date", ["Discharge Date", "Discharged"]),
        ("principal_diagnosis", ["Principal Diagnosis", "Primary Diagnosis"]),
        ("secondary_diagnoses", ["Secondary Diagnoses", "Secondary Diagnosis", "Comorbidities"]),
        ("hospital_course", ["Hospital Course", "Clinical Course"]),
        ("procedures", ["Procedures", "Procedure", "Surgery"]),
        ("allergies", ["Allergies", "Allergy"]),
        ("follow_up_instructions", ["Follow-up", "Follow up", "Followup Instructions", "Followup"]),
        ("discharge_condition", ["Discharge Condition", "Condition at Discharge"]),
    ]

    for field_name, labels in field_map:
        value = _find_section_value(sections, labels)
        if value:
            items.append(
                EvidenceItem(
                    value=value,
                    source_document=doc_name,
                    page_number=page_num,
                    field_name=field_name,
                    source_text=source_text,
                )
            )

    # Progress notes may use generic "Diagnosis" when principal diagnosis absent.
    if not any(i.field_name == "principal_diagnosis" for i in items):
        for label, value in sections:
            if _label_matches(label, ["Diagnosis"]) and value:
                items.append(
                    EvidenceItem(
                        value=value,
                        source_document=doc_name,
                        page_number=page_num,
                        field_name="principal_diagnosis",
                        source_text=source_text,
                    )
                )
                break

    if len(items) < 4:
        items.extend(_extract_unstructured_prose(text, doc_name, page_num, source_text, items))

    return items


def _has_field(items: list[EvidenceItem], field_name: str) -> bool:
    return any(i.field_name == field_name for i in items)


def _extract_unstructured_prose(
    text: str,
    doc_name: str,
    page_num: int,
    source_text: str,
    existing: list[EvidenceItem],
) -> list[EvidenceItem]:
    """Fallback extraction for narrative-style hospital notes without label:value lines."""
    found: list[EvidenceItem] = []
    patterns: list[tuple[str, str]] = [
        (r"(?:Patient Name|Name)\s*[:]\s*([A-Za-z ,.'-]+)", "patient_name"),
        (r"(?:DOB|Date of Birth)\s*[:]\s*(\d{1,2}/\d{1,2}/\d{2,4})", "patient_dob"),
        (r"(?:admitted on|Admission Date)\s*[:.]?\s*(\d{1,2}/\d{1,2}/\d{2,4})", "admission_date"),
        (r"(?:discharged on|Discharge Date)\s*[:.]?\s*(\d{1,2}/\d{1,2}/\d{2,4})", "discharge_date"),
        (r"(?:Principal Diagnosis|Assessment|Impression)\s*[:]\s*([^\n.]+)", "principal_diagnosis"),
        (r"(?:Hospital Course|Clinical Course|Course)\s*[:]\s*([^\n]+)", "hospital_course"),
        (r"(?:Allergies|Allergy)\s*[:]\s*([^\n.]+)", "allergies"),
        (r"(?:Plan|Follow-up|Follow up)\s*[:]\s*([^\n.]+)", "follow_up_instructions"),
        (r"(?:Discharge Condition|Condition at discharge)\s*[:]\s*([^\n.]+)", "discharge_condition"),
        (r"presented with ([^\n.]+)", "principal_diagnosis"),
        (r"in stable condition", "discharge_condition"),
    ]

    for pattern, field_name in patterns:
        if _has_field(existing, field_name) or _has_field(found, field_name):
            continue
        match = re.search(pattern, text, re.I)
        if not match:
            continue
        value = match.group(1).strip() if match.lastindex else match.group(0).strip()
        if field_name == "discharge_condition" and match.lastindex is None:
            value = "Stable"
        if value:
            found.append(
                EvidenceItem(
                    value=value[:500],
                    source_document=doc_name,
                    page_number=page_num,
                    field_name=field_name,
                    source_text=source_text,
                )
            )

    name_match = re.search(r"([A-Z][a-z]+ [A-Z][a-z]+)\s*\(\s*DOB\s*(\d{1,2}/\d{1,2}/\d{2,4})\s*\)", text)
    if name_match and not _has_field(existing, "patient_name") and not _has_field(found, "patient_name"):
        found.append(
            EvidenceItem(
                value=name_match.group(1),
                source_document=doc_name,
                page_number=page_num,
                field_name="patient_name",
                source_text=source_text,
            )
        )
        if not _has_field(existing, "patient_dob") and not _has_field(found, "patient_dob"):
            found.append(
                EvidenceItem(
                    value=name_match.group(2),
                    source_document=doc_name,
                    page_number=page_num,
                    field_name="patient_dob",
                    source_text=source_text,
                )
            )

    return found


def _normalize_evidence_value(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def _page_indicates_med_section(text: str) -> bool:
    return bool(MED_SECTION_HINT.search(text) or ADMISSION_MED_HINT.search(text))


def _page_indicates_lab_section(text: str) -> bool:
    return bool(LAB_SECTION_HINT.search(text))


def _med_field_for_page(text: str, doc_name: str) -> str:
    lower = text.lower()
    if "discharge" in lower or "home med" in lower or "at discharge" in lower:
        return "discharge_medications"
    if "admission" in doc_name.lower() or ADMISSION_MED_HINT.search(text):
        return "admission_medications"
    return "discharge_medications"


def _extract_labs_from_text(text: str, doc_name: str, page_num: int) -> list[EvidenceItem]:
    items: list[EvidenceItem] = []
    seen: set[str] = set()
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        lab_match = LAB_LINE.match(line)
        if not lab_match:
            continue
        value = f"{lab_match.group(1).strip()}: {lab_match.group(2)} {lab_match.group(3) or ''}".strip()
        key = _normalize_evidence_value(value)
        if key in seen:
            continue
        seen.add(key)
        items.append(
            EvidenceItem(
                value=value,
                source_document=doc_name,
                page_number=page_num,
                field_name="lab_results",
                source_text=text[:2000],
            )
        )
    return items


def _aggregate_evidence_store(store: EvidenceStore) -> EvidenceStore:
    """Dedupe noisy multi-page OCR extractions and cap hospital course length."""
    grouped: dict[str, list[EvidenceItem]] = {}
    for item in store.items:
        grouped.setdefault(item.field_name, []).append(item)

    aggregated: list[EvidenceItem] = []
    for field_name, items in grouped.items():
        if field_name == "hospital_course":
            aggregated.extend(_aggregate_hospital_course(items))
            continue

        seen: set[str] = set()
        sorted_items = sorted(items, key=lambda i: i.page_number)
        for item in sorted_items:
            key = _normalize_evidence_value(item.value)
            if not key or key in seen:
                continue
            seen.add(key)
            aggregated.append(item)

    return EvidenceStore(items=aggregated)


def _aggregate_hospital_course(items: list[EvidenceItem]) -> list[EvidenceItem]:
    if not items:
        return []

    unique: list[EvidenceItem] = []
    seen: set[str] = set()
    for item in sorted(items, key=lambda i: i.page_number):
        norm = _normalize_evidence_value(item.value)
        if len(norm) < 8 or norm in seen:
            continue
        seen.add(norm)
        unique.append(item)
        if len(unique) >= HOSPITAL_COURSE_MAX_SNIPPETS:
            break

    if len(unique) == 1:
        return unique

    merged_text = " ".join(i.value for i in unique)[:HOSPITAL_COURSE_MAX_CHARS]
    anchor = unique[-1]
    return [
        EvidenceItem(
            value=merged_text,
            source_document=anchor.source_document,
            page_number=anchor.page_number,
            field_name="hospital_course",
            source_text=anchor.source_text,
        )
    ]


def extract_fields_from_documents(
    documents: dict[str, PDFReadResult],
) -> tuple[EvidenceStore, dict[str, dict[int, str]]]:
    store = EvidenceStore()
    page_cache: dict[str, dict[int, str]] = {}

    for doc_name, doc in documents.items():
        if not doc.success:
            continue
        page_cache[doc_name] = doc.page_mapping
        for page in doc.pages:
            text = page.text
            for item in extract_fields_from_page(text, doc_name, page.page_number):
                store.add(item)

            filename_has_med = "medication" in doc_name.lower() or "med" in doc_name.lower()
            page_has_med = _page_indicates_med_section(text)
            if filename_has_med or page_has_med:
                field = _med_field_for_page(text, doc_name)
                for item in extract_medications(text, doc_name, page.page_number, field):
                    store.add(item)

            filename_has_lab = "lab" in doc_name.lower()
            page_has_lab = _page_indicates_lab_section(text)
            if filename_has_lab or page_has_lab:
                for item in _extract_labs_from_text(text, doc_name, page.page_number):
                    store.add(item)

    return _aggregate_evidence_store(store), page_cache


def validate_evidence_substrings(
    store: EvidenceStore,
    page_cache: dict[str, dict[int, str]],
) -> list[str]:
    failures: list[str] = []
    for item in store.items:
        pages = page_cache.get(item.source_document, {})
        page_text = pages.get(item.page_number, item.source_text)
        if page_text and not item.is_substring_valid(page_text):
            failures.append(
                f"Evidence {item.id} value '{item.value}' not found in {item.source_document} p{item.page_number}"
            )
    return failures
