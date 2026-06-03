"""Persist Streamlit uploads to a stable on-disk patient folder."""

from __future__ import annotations

import re
from pathlib import Path

UPLOAD_BASE = Path(__file__).resolve().parents[2] / "data" / "uploads"
# Back-compat alias for tests that monkeypatch a single staging root.
UPLOAD_ROOT = UPLOAD_BASE / "active"


def _patient_id_from_filename(filename: str) -> str:
    stem = Path(filename).stem
    safe = re.sub(r"[^\w\-]+", "_", stem).strip("_").lower()
    return (safe[:64] or "upload")


def stage_uploaded_pdfs(uploaded_files: list) -> Path:
    """
    Write uploaded PDFs to a persistent folder for agent processing.

    Uses a stable path so Windows file locks from PDF parsers are not racing
    temp-directory cleanup. Folder name matches the primary PDF stem so
    patient_id in traces/outputs is meaningful (not a generic "active").
    """
    if not uploaded_files:
        raise ValueError("No PDF files to stage")

    primary_name: str | None = None
    staged_names: list[str] = []

    for uploaded in uploaded_files:
        name = Path(uploaded.name).name
        if not name.lower().endswith(".pdf"):
            continue
        if primary_name is None:
            primary_name = name
        staged_names.append(name)

    if not staged_names:
        raise ValueError("No valid PDF files were staged")

    case_dir = UPLOAD_BASE / _patient_id_from_filename(primary_name or "upload")
    case_dir.mkdir(parents=True, exist_ok=True)

    for existing in case_dir.glob("*.pdf"):
        try:
            existing.unlink()
        except OSError:
            pass

    for uploaded in uploaded_files:
        name = Path(uploaded.name).name
        if not name.lower().endswith(".pdf"):
            continue
        dest = case_dir / name
        dest.write_bytes(uploaded.getvalue())

    staged = sorted(case_dir.glob("*.pdf"))
    if not staged:
        raise ValueError("No valid PDF files were staged")

    return case_dir
