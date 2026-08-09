"""Persistent caller memory for the Swasthya Sahayak voice agent.

Callers are identified by a stable ``caller_id`` that the frontend persists
across sessions (a cookie).  The voice agent can read, update and forget a
caller's health profile between calls using the SQLite-backed :class:`CallerStore`.
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone

DEFAULT_DB_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "caller_memory.db"
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS callers (
    caller_id      TEXT PRIMARY KEY,
    name           TEXT,
    language       TEXT,
    location       TEXT,
    phone          TEXT,
    dob            TEXT,
    gender         TEXT,
    conditions     TEXT NOT NULL DEFAULT '[]',
    medications    TEXT NOT NULL DEFAULT '[]',
    allergies      TEXT NOT NULL DEFAULT '[]',
    notes          TEXT NOT NULL DEFAULT '[]',
    last_called_at TEXT,
    created_at     TEXT NOT NULL
);
"""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class CallerStore:
    """SQLite-backed store for caller health profiles.

    The store is safe to use from multiple threads (e.g. one background thread
    per voice session).  All JSON column values are Python ``list[str]``.
    """

    def __init__(self, db_path: str = DEFAULT_DB_PATH) -> None:
        self._db_path = db_path
        self._lock = threading.RLock()
        os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
        with self._connect() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute(_SCHEMA)
            conn.commit()

    @contextmanager
    def _connect(self) -> None:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def get(self, caller_id: str) -> dict | None:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM callers WHERE caller_id = ?", (caller_id,)
            ).fetchone()
        return self._row_to_profile(row) if row else None

    def _row_to_profile(self, row: sqlite3.Row) -> dict:
        return {
            "caller_id": row["caller_id"],
            "name": row["name"],
            "language": row["language"],
            "location": row["location"],
            "phone": row["phone"],
            "dob": row["dob"],
            "gender": row["gender"],
            "conditions": json.loads(row["conditions"]),
            "medications": json.loads(row["medications"]),
            "allergies": json.loads(row["allergies"]),
            "notes": json.loads(row["notes"]),
            "last_called_at": row["last_called_at"],
            "created_at": row["created_at"],
        }

    def upsert(self, profile: dict) -> dict:
        """Insert a new caller or merge a profile into an existing record.

        ``None`` fields in ``profile`` are ignored so a partial update never
        wipes previously known information.
        """
        existing = self.get(profile["caller_id"])
        merged = {
            "caller_id": profile["caller_id"],
            "name": None,
            "language": None,
            "location": None,
            "phone": None,
            "dob": None,
            "gender": None,
            "conditions": [],
            "medications": [],
            "allergies": [],
            "notes": [],
            "created_at": (existing or {}).get("created_at", _now_iso()),
            "last_called_at": _now_iso(),
        }
        if existing:
            merged.update(existing)
        for key in (
            "name",
            "language",
            "location",
            "phone",
            "dob",
            "gender",
            "conditions",
            "medications",
            "allergies",
            "notes",
        ):
            value = profile.get(key)
            if value is not None:
                merged[key] = value
        for key in ("conditions", "medications", "allergies", "notes"):
            merged[key] = list(dict.fromkeys(merged.get(key) or []))
        with self._lock, self._connect() as conn:
            conn.execute(
                "INSERT INTO callers (caller_id, name, language, location, phone, dob,"
                " gender, conditions, medications, allergies, notes, last_called_at,"
                " created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)"
                " ON CONFLICT(caller_id) DO UPDATE SET"
                " name=excluded.name, language=excluded.language,"
                " location=excluded.location, phone=excluded.phone, dob=excluded.dob,"
                " gender=excluded.gender, conditions=excluded.conditions,"
                " medications=excluded.medications, allergies=excluded.allergies,"
                " notes=excluded.notes, last_called_at=excluded.last_called_at",
                (
                    merged["caller_id"],
                    merged["name"],
                    merged["language"],
                    merged["location"],
                    merged["phone"],
                    merged["dob"],
                    merged["gender"],
                    json.dumps(merged["conditions"]),
                    json.dumps(merged["medications"]),
                    json.dumps(merged["allergies"]),
                    json.dumps(merged["notes"]),
                    merged["last_called_at"],
                    merged["created_at"],
                ),
            )
            conn.commit()
        return merged

    def touch(self, caller_id: str) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                "UPDATE callers SET last_called_at = ? WHERE caller_id = ?",
                (_now_iso(), caller_id),
            )
            conn.commit()

    def delete(self, caller_id: str) -> bool:
        with self._lock, self._connect() as conn:
            cur = conn.execute("DELETE FROM callers WHERE caller_id = ?", (caller_id,))
            conn.commit()
        return cur.rowcount > 0

    def list(self) -> list[dict]:
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM callers ORDER BY last_called_at DESC"
            ).fetchall()
        return [self._row_to_profile(row) for row in rows]

    def count(self) -> int:
        with self._lock, self._connect() as conn:
            row = conn.execute("SELECT COUNT(*) AS n FROM callers").fetchone()
        return int(row["n"])


def new_caller_id() -> str:
    return str(uuid.uuid4())
