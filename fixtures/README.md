# Patient PDF Fixtures

Place patient PDF folders here for E2E and evaluation tests. Each scenario folder should contain:

## Required filenames

| File | Description |
|------|-------------|
| `admission_note.pdf` | Admission note with demographics, diagnosis, hospital course |
| `progress_note_1.pdf` … `progress_note_n.pdf` | Progress notes |
| `labs.pdf` | Laboratory results |
| `medication_admission.pdf` | Admission medication list |
| `medication_discharge.pdf` | Discharge medication list |

## Scenario folders

| Folder | Purpose |
|--------|---------|
| `complete/` | All fields present, consistent records |
| `missing/` | Missing diagnosis, allergies, or discharge date |
| `conflicts/` | Conflicting diagnoses or discharge dates across documents |
| `pending/` | Pending labs, cultures, or pathology |
| `med_discrepancy/` | Medication changes without documented reasons |
| `extraction_fail/` | Corrupted or unreadable PDF (for failure testing) |
| `multi_flags/` | Multiple safety flags combined |

Tests skip E2E scenarios when PDFs are absent.
