from __future__ import annotations

import re

from app.models.summary_models import DischargeSummaryDraft, SectionStatus


ABBREVIATIONS = {
    r"\bHTN\b": "Hypertension",
    r"\bDM\b": "Diabetes Mellitus",
    r"\bCAD\b": "Coronary Artery Disease",
    r"\bCHF\b": "Congestive Heart Failure",
    r"\bCOPD\b": "Chronic Obstructive Pulmonary Disease",
    r"\bMI\b": "Myocardial Infarction",
    r"\bUTI\b": "Urinary Tract Infection",
    r"\bPO\b": "by mouth (PO)",
    r"\bBID\b": "twice daily (BID)",
    r"\bTID\b": "three times daily (TID)",
}


class SimulatedDoctor:
    """Hidden rule-based editor generating (draft, edited) pairs for the learning loop."""

    def edit(self, draft: DischargeSummaryDraft) -> DischargeSummaryDraft:
        edited_sections = []
        pending_section = None

        for section in draft.sections:
            content = section.content
            for pattern, expansion in ABBREVIATIONS.items():
                content = re.sub(pattern, expansion, content)

            if section.name == "Hospital Course":
                content = content.replace("; ", ". ")
                if content and not content.lower().startswith("the patient"):
                    content = f"The patient was hospitalized and {content[0].lower()}{content[1:]}"

            if section.name == "Medication Changes":
                content = content.replace(
                    "Reason Not Documented",
                    "Reason Not Documented — clinician to verify",
                )

            if section.name == "Follow-up Instructions" and "Follow-up plan:" in content:
                content = content.replace("Follow-up plan:", "Recommended follow-up:")

            new_section = section.model_copy(update={"content": content})
            if section.name == "Pending Results":
                pending_section = new_section
            else:
                edited_sections.append(new_section)

        if pending_section:
            edited_sections.append(pending_section)

        executive = draft.executive_summary
        if executive:
            for pattern, expansion in ABBREVIATIONS.items():
                executive = re.sub(pattern, expansion, executive)

        return draft.model_copy(update={"sections": edited_sections, "executive_summary": executive})

    def generate_pair(self, draft: DischargeSummaryDraft) -> tuple[DischargeSummaryDraft, DischargeSummaryDraft]:
        edited = self.edit(draft)
        return draft, edited
