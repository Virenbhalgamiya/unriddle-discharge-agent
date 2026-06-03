from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


class CorrectionMemory:
    """SQLite-backed correction memory. Formatting only — never overrides evidence."""

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS corrections (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    mistake TEXT NOT NULL,
                    correction TEXT NOT NULL,
                    frequency INTEGER DEFAULT 1,
                    affected_section TEXT,
                    recommendation TEXT,
                    updated_at TEXT
                );
                CREATE TABLE IF NOT EXISTS escalations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    reason TEXT NOT NULL,
                    details TEXT NOT NULL,
                    section TEXT,
                    created_at TEXT
                );
                """
            )

    def record_correction(
        self,
        mistake: str,
        correction: str,
        affected_section: str,
        recommendation: str,
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            row = conn.execute(
                "SELECT id, frequency FROM corrections WHERE mistake = ? AND affected_section = ?",
                (mistake, affected_section),
            ).fetchone()
            if row:
                conn.execute(
                    "UPDATE corrections SET correction = ?, frequency = ?, recommendation = ?, updated_at = ? WHERE id = ?",
                    (correction, row["frequency"] + 1, recommendation, now, row["id"]),
                )
            else:
                conn.execute(
                    "INSERT INTO corrections (mistake, correction, frequency, affected_section, recommendation, updated_at) VALUES (?, ?, 1, ?, ?, ?)",
                    (mistake, correction, affected_section, recommendation, now),
                )

    def store_escalation(self, reason: str, details: str, section: str = "general") -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO escalations (reason, details, section, created_at) VALUES (?, ?, ?, ?)",
                (reason, details, section, datetime.now(timezone.utc).isoformat()),
            )

    def get_recommendations(self, section: Optional[str] = None) -> list[dict[str, Any]]:
        with self._connect() as conn:
            if section:
                rows = conn.execute(
                    "SELECT * FROM corrections WHERE affected_section = ? ORDER BY frequency DESC",
                    (section,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM corrections ORDER BY frequency DESC"
                ).fetchall()
        return [dict(r) for r in rows]

    def get_formatting_hints(self) -> dict[str, str]:
        hints: dict[str, str] = {}
        for rec in self.get_recommendations():
            section = rec.get("affected_section", "")
            if section and rec.get("recommendation"):
                hints[section] = rec["recommendation"]
        return hints

    def get_escalations(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM escalations ORDER BY created_at DESC").fetchall()
        return [dict(r) for r in rows]

    def clear(self) -> None:
        """Reset all stored corrections and escalations (for evaluation baselines)."""
        with self._connect() as conn:
            conn.execute("DELETE FROM corrections")
            conn.execute("DELETE FROM escalations")
