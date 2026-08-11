"""Human-help escalation store for the Swasthya Sahayak voice agent.

Day 7: the agent should not try to solve every problem alone.  When a caller
reports a red-flag symptom or asks for a diagnosis, the agent asks their
permission and then files a *short, useful* request for a human health worker
using :class:`EscalationStore`.

Each request keeps only what the worker needs:
  - who needs help (caller name, caller_id)
  - what happened (a 2-3 sentence summary)
  - what the agent already checked
  - how urgent it is (low / medium / high / emergency)
  - the caller's language and preferred follow-up method

Private details (phone numbers, OTPs, PINs, Aadhaar, account numbers, …) are
never meant to be written into the summary — :func:`sanitize_summary` strips
them anyway as a defence in depth.  The full conversation is never stored.
"""

from __future__ import annotations

import os
import re
import sqlite3
import string
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone

DEFAULT_DB_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "escalations.db"
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS escalations (
    reference_id TEXT PRIMARY KEY,
    caller_id    TEXT NOT NULL,
    caller_name  TEXT,
    category     TEXT NOT NULL,
    urgency      TEXT NOT NULL DEFAULT 'medium',
    summary      TEXT NOT NULL,
    checked      TEXT NOT NULL DEFAULT '',
    followup     TEXT NOT NULL DEFAULT '',
    language     TEXT NOT NULL DEFAULT '',
    status       TEXT NOT NULL DEFAULT 'open',
    created_at   TEXT NOT NULL,
    updated_at   TEXT NOT NULL
);
"""

SCHEMA_INDEX = "CREATE INDEX IF NOT EXISTS idx_escalations_open ON escalations(status)"

VALID_CATEGORIES = ("red_flag_symptom", "diagnosis_request")
VALID_URGENCIES = ("low", "medium", "high", "emergency")
VALID_STATUSES = ("open", "in_progress", "resolved")

_REDACTED = "[redacted]"

# Long digit runs that look like account numbers / Aadhaar / card numbers.
_DIGIT_RUN = re.compile(r"\b(?:\d[ -]?){11,15}\d\b")

# A word like OTP / PIN / password followed by (up to a few words then) digits.
_SECRET_PATTERN = re.compile(
    r"\b(?:otp|one[- ]?time[- ]?password|pin|passcode|password)\b"
    r"[^\d]{0,15}\d{3,8}",
    re.IGNORECASE,
)

# Bare 10-digit phone numbers (with optional spaces/hyphens).
_PHONE_RUN = re.compile(r"\b(?:\d[ -]?){9}\d\b")

# Words that only ever sit next to private data in a health call.
_SECRET_WORD = re.compile(
    r"\b(?:aadhaar|aadhar|pan\s+card|account\s+number|card\s+number|upi)\b",
    re.IGNORECASE,
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe(parts: list[str]) -> str:
    return _REDACTED if parts else ""


def sanitize_summary(text: str | None) -> str:
    """Remove private numbers and secrets from a free-text summary.

    The agent is instructed never to write private details into the summary in
    the first place; this is a second line of defence so a stray digit run can
    never reach the dashboard.  Returns a (possibly shorter) plain string.
    """
    if not text:
        return ""
    out = _SECRET_PATTERN.sub(lambda m: _safe(re.findall(r"[^\d]", m.group(0))), text)
    out = _DIGIT_RUN.sub(_REDACTED, out)
    out = _PHONE_RUN.sub(_REDACTED, out)
    out = _SECRET_WORD.sub(_REDACTED, out)
    return re.sub(r"\s+", " ", out).strip()


def new_reference_id() -> str:
    """A short, human-readable reference the caller can quote later (ESC-XXXXXX)."""
    alphabet = string.ascii_uppercase + string.digits
    return "ESC-" + "".join(
        alphabet[int(uuid.uuid4().hex[:8], 16) % len(alphabet)] for _ in range(6)
    )


class EscalationStore:
    """SQLite-backed queue of human-help requests.

    Thread-safe (RLock), same pattern as :class:`memory.CallerStore`.  The DB
    file lives at the repo root as ``escalations.db`` (gitignored).
    """

    def __init__(self, db_path: str = DEFAULT_DB_PATH) -> None:
        self._db_path = db_path
        self._lock = threading.RLock()
        os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
        with self._connect() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute(SCHEMA)
            conn.execute(SCHEMA_INDEX)
            conn.commit()

    @contextmanager
    def _connect(self) -> None:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def _row_to_request(self, row: sqlite3.Row) -> dict:
        return {
            "reference_id": row["reference_id"],
            "caller_id": row["caller_id"],
            "caller_name": row["caller_name"],
            "category": row["category"],
            "urgency": row["urgency"],
            "summary": row["summary"],
            "checked": row["checked"],
            "followup": row["followup"],
            "language": row["language"],
            "status": row["status"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def create(self, request: dict) -> dict:
        """File a human-help request.

        A request with the same ``caller_id`` and ``category`` that is still
        ``open`` is *updated* instead of duplicated (same reference_id returned
        with ``duplicate=True``) so a caller never sees two tickets for the
        same problem.
        """
        now = _now_iso()
        caller_id = request.get("caller_id") or "anonymous"

        existing = self._find_open(caller_id, request.get("category"))
        if existing is not None:
            updates = {
                "urgency": request.get("urgency", existing["urgency"]),
                "summary": request.get("summary", existing["summary"]),
                "checked": request.get("checked", existing["checked"]),
                "followup": request.get("followup", existing["followup"]),
                "language": request.get("language", existing["language"]),
                "caller_name": request.get("caller_name") or existing["caller_name"],
                "status": "open",
                "updated_at": now,
            }
            with self._lock, self._connect() as conn:
                conn.execute(
                    "UPDATE escalations SET caller_name=?, urgency=?, summary=?,"
                    " checked=?, followup=?, language=?, status='open', updated_at=?"
                    " WHERE reference_id=?",
                    (
                        updates["caller_name"],
                        updates["urgency"],
                        updates["summary"],
                        updates["checked"],
                        updates["followup"],
                        updates["language"],
                        now,
                        existing["reference_id"],
                    ),
                )
                conn.commit()
            stored = self.get(existing["reference_id"])
            return {**stored, "duplicate": True, "created": True}

        reference_id = new_reference_id()
        row = {
            "reference_id": reference_id,
            "caller_id": caller_id,
            "caller_name": request.get("caller_name"),
            "category": request.get("category", "diagnosis_request"),
            "urgency": request.get("urgency", "medium"),
            "summary": request.get("summary", ""),
            "checked": request.get("checked", ""),
            "followup": request.get("followup", ""),
            "language": request.get("language", ""),
            "status": "open",
            "created_at": now,
            "updated_at": now,
        }
        with self._lock, self._connect() as conn:
            conn.execute(
                "INSERT INTO escalations (reference_id, caller_id, caller_name,"
                " category, urgency, summary, checked, followup, language, status,"
                " created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    row["reference_id"],
                    row["caller_id"],
                    row["caller_name"],
                    row["category"],
                    row["urgency"],
                    row["summary"],
                    row["checked"],
                    row["followup"],
                    row["language"],
                    row["status"],
                    row["created_at"],
                    row["updated_at"],
                ),
            )
            conn.commit()
        return {**row, "duplicate": False, "created": True}

    def _find_open(self, caller_id: str, category: str | None) -> dict | None:
        with self._lock, self._connect() as conn:
            if category:
                row = conn.execute(
                    "SELECT * FROM escalations WHERE caller_id = ? AND category = ?"
                    " AND status = 'open' ORDER BY created_at DESC LIMIT 1",
                    (caller_id, category),
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT * FROM escalations WHERE caller_id = ? AND status = 'open'"
                    " ORDER BY created_at DESC LIMIT 1",
                    (caller_id,),
                ).fetchone()
        return self._row_to_request(row) if row else None

    def get(self, reference_id: str) -> dict | None:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM escalations WHERE reference_id = ?", (reference_id,)
            ).fetchone()
        return self._row_to_request(row) if row else None

    def list(self, status: str | None = None) -> list[dict]:
        with self._lock, self._connect() as conn:
            if status:
                rows = conn.execute(
                    "SELECT * FROM escalations WHERE status = ?"
                    " ORDER BY CASE urgency WHEN 'emergency' THEN 0 WHEN 'high' THEN 1"
                    " WHEN 'medium' THEN 2 ELSE 3 END, created_at DESC",
                    (status,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM escalations"
                    " ORDER BY CASE urgency WHEN 'emergency' THEN 0 WHEN 'high' THEN 1"
                    " WHEN 'medium' THEN 2 ELSE 3 END, created_at DESC"
                ).fetchall()
        return [self._row_to_request(row) for row in rows]

    def update_status(self, reference_id: str, status: str) -> bool:
        """Move a request through open -> in_progress -> resolved."""
        if status not in VALID_STATUSES:
            return False
        with self._lock, self._connect() as conn:
            cur = conn.execute(
                "UPDATE escalations SET status = ?, updated_at = ?"
                " WHERE reference_id = ?",
                (status, _now_iso(), reference_id),
            )
            conn.commit()
        return cur.rowcount > 0

    def count(self, status: str | None = None) -> int:
        with self._lock, self._connect() as conn:
            if status:
                row = conn.execute(
                    "SELECT COUNT(*) AS n FROM escalations WHERE status = ?",
                    (status,),
                ).fetchone()
            else:
                row = conn.execute("SELECT COUNT(*) AS n FROM escalations").fetchone()
        return int(row["n"])
