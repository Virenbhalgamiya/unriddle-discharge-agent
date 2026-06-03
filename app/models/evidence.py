from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class EvidenceItem(BaseModel):
    """Provenance-backed clinical fact."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    value: str
    source_document: str
    page_number: int
    extraction_timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    confidence: float = 1.0
    field_name: str
    source_text: str = ""

    def is_substring_valid(self, page_text: str) -> bool:
        if not self.value.strip():
            return False
        candidates = [page_text, self.source_text]
        return any(self.value.lower() in text.lower() for text in candidates if text)


class EvidenceStore(BaseModel):
    items: list[EvidenceItem] = Field(default_factory=list)

    def add(self, item: EvidenceItem) -> EvidenceItem:
        self.items.append(item)
        return item

    def by_field(self, field_name: str) -> list[EvidenceItem]:
        return [i for i in self.items if i.field_name == field_name]

    def to_dict_list(self) -> list[dict[str, Any]]:
        return [i.model_dump(mode="json") for i in self.items]
