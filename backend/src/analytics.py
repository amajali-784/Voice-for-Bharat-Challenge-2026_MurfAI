"""Call analytics for the Swasthya Sahayak voice agent.

Day 8: every call's outcome is recorded into a SQLite store so the frontend
dashboard can show real numbers (total / successful / failed calls) that come
from actual browser and SIP calls — never hardcoded.

Success definition (Health Access track)
----------------------------------------
A successful call means **the caller received safe guidance or an appropriate
escalation**.  The agent cannot always know this perfectly, so we infer it from
what actually happened during the call:

1. A human-help request was filed (red-flag symptom / diagnosis request)  →
   an appropriate escalation was created.
2. Nearby health facilities were delivered from a real lookup (status "ok") →
   the caller received facility guidance.
3. The agent saved part of the caller's health profile (name / conditions /
   medications / location) and there was a real exchange of turns →
   the conversation produced personalised guidance.
4. Otherwise, a completed consultation: at least two caller turns, two agent
   turns, and 30+ seconds of conversation → general safe guidance was given.

Anything else is a **failed** call, grouped by failure type:
  - ``no_response``  — the caller joined but never spoke.
  - ``user_hangup``  — the caller left quickly, before any guidance.
  - ``incomplete``   — the conversation ended before guidance was delivered.
  - ``sip_*``        — an outbound SIP call that never connected.

Privacy
-------
This store never keeps transcripts, names, phone numbers or any private
detail.  Caller identifiers are stored as an opaque SHA-256 hash, and only
counts / timings / tool names are kept.  This is the data the public dashboard
is allowed to see.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import sqlite3
import statistics
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

DEFAULT_DB_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "call_analytics.db"
)

# Valid channels. "browser" covers the main frontend, "sip" covers outbound
# telephony, "console" covers terminal-only testing, "eval" covers the LLM
# test suite (written to whatever store a test points at).
VALID_CHANNELS = ("browser", "sip", "console", "eval")

VALID_OUTCOMES = ("success", "failed")
VALID_FAILURE_TYPES = (
    "no_response",
    "user_hangup",
    "incomplete",
    "tool_error",
    "sip_no_answer",
    "sip_busy",
    "sip_declined",
    "sip_trunk_failure",
    "sip_voicemail",
    "sip_hung_up_immediate",
    "sip_opted_out",
    "sip_unknown",
)

# How long a call must last to count as a "completed consultation".
MIN_CONSULTATION_SECONDS = 30.0
# How long before we call an early exit a "hang-up" rather than "no response".
HANGUP_WINDOW_SECONDS = 30.0

_SCHEMA = """
CREATE TABLE IF NOT EXISTS calls (
    call_id            TEXT PRIMARY KEY,
    caller_id          TEXT NOT NULL,
    channel            TEXT NOT NULL DEFAULT 'browser',
    outcome            TEXT NOT NULL,
    failure_type       TEXT,
    reason             TEXT,
    started_at         TEXT NOT NULL,
    ended_at           TEXT NOT NULL,
    duration_seconds   REAL,
    user_turns         INTEGER NOT NULL DEFAULT 0,
    agent_turns        INTEGER NOT NULL DEFAULT 0,
    message_count      INTEGER NOT NULL DEFAULT 0,
    tools_used         TEXT NOT NULL DEFAULT '[]',
    escalation_created INTEGER NOT NULL DEFAULT 0,
    facility_delivered INTEGER NOT NULL DEFAULT 0,
    avg_latency_ms     REAL,
    p95_latency_ms     REAL,
    error              TEXT,
    detail             TEXT
);
"""

_SCHEMA_INDEXES = (
    "CREATE INDEX IF NOT EXISTS idx_calls_started ON calls(started_at)",
    "CREATE INDEX IF NOT EXISTS idx_calls_outcome ON calls(outcome)",
    "CREATE INDEX IF NOT EXISTS idx_calls_channel ON calls(channel)",
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def privacy_id(identifier: str) -> str:
    """Turn a caller identifier (a UUID cookie or a phone number) into an
    opaque, irreversible hash so the dashboard never sees the raw value."""
    raw = (identifier or "anonymous").strip()
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _row_to_call(row: sqlite3.Row) -> dict:
    return {
        "call_id": row["call_id"],
        "caller_id": row["caller_id"],
        "channel": row["channel"],
        "outcome": row["outcome"],
        "failure_type": row["failure_type"],
        "reason": row["reason"],
        "started_at": row["started_at"],
        "ended_at": row["ended_at"],
        "duration_seconds": row["duration_seconds"],
        "user_turns": row["user_turns"],
        "agent_turns": row["agent_turns"],
        "message_count": row["message_count"],
        "tools_used": json.loads(row["tools_used"]),
        "escalation_created": bool(row["escalation_created"]),
        "facility_delivered": bool(row["facility_delivered"]),
        "avg_latency_ms": row["avg_latency_ms"],
        "p95_latency_ms": row["p95_latency_ms"],
        "error": row["error"],
        "detail": row["detail"],
    }


def classify_call(
    *,
    user_turns: int,
    agent_turns: int,
    duration_seconds: float | None,
    escalation_created: bool,
    facility_delivered: bool,
    profile_saved: bool,
    error: str | None = None,
) -> tuple[str, str | None, str]:
    """Decide whether a call succeeded and, if not, why.

    Returns ``(outcome, failure_type, reason)``.  See the module docstring for
    the success definition.
    """
    if error:
        return "failed", "tool_error", "agent reported an error"

    if escalation_created:
        return "success", None, "caller was escalated for human help"
    if facility_delivered:
        return "success", None, "caller received facility guidance"
    if profile_saved and user_turns >= 1 and agent_turns >= 1:
        return (
            "success",
            None,
            "caller's health situation was captured and guidance given",
        )

    duration = duration_seconds or 0.0
    if user_turns >= 2 and agent_turns >= 2 and duration >= MIN_CONSULTATION_SECONDS:
        return "success", None, "completed consultation — safe guidance given"

    if user_turns == 0:
        return "failed", "no_response", "caller never spoke"
    if duration < HANGUP_WINDOW_SECONDS:
        return "failed", "user_hangup", "caller hung up before guidance"
    return "failed", "incomplete", "conversation ended before guidance"


def extract_call_signals(history) -> dict:
    """Pull anonymised, aggregated signals out of a session's chat history.

    Only counts and tool names are extracted — never message text — so this is
    safe to feed straight into the analytics store.
    """
    user_turns = 0
    agent_turns = 0
    interruptions = 0
    tools: list[str] = []
    latencies_ms: list[float] = []
    escalation_created = False
    facility_delivered = False
    profile_saved = False

    for item in history.items:
        if getattr(item, "type", None) == "message":
            text = item.text_content or ""
            if not text.strip():
                continue
            if item.role == "user":
                user_turns += 1
            elif item.role == "assistant":
                agent_turns += 1
                if item.interrupted:
                    interruptions += 1
                latency = _metrics_field(item, "e2e_latency")
                if isinstance(latency, (int, float)) and latency > 0:
                    latencies_ms.append(latency * 1000.0)
        elif getattr(item, "type", None) == "function_call":
            name = item.name
            if name and name not in tools:
                tools.append(name)
            if name == "save_caller_info":
                profile_saved = True
        elif getattr(item, "type", None) == "function_call_output":
            name = item.name
            if name == "create_escalation":
                escalation_created = escalation_created or _tool_output_flag(
                    item.output, "created", True
                )
            elif name == "find_nearby_health_facilities":
                facility_delivered = facility_delivered or _tool_output_flag(
                    item.output, "status", "ok"
                )
            elif name == "save_caller_info":
                profile_saved = profile_saved or _tool_output_flag(
                    item.output, "saved", True
                )

    avg_ms = round(statistics.mean(latencies_ms), 1) if latencies_ms else None
    p95_ms = _percentile(latencies_ms, 95) if latencies_ms else None

    return {
        "user_turns": user_turns,
        "agent_turns": agent_turns,
        "message_count": user_turns + agent_turns,
        "interruptions": interruptions,
        "tools_used": tools,
        "escalation_created": escalation_created,
        "facility_delivered": facility_delivered,
        "profile_saved": profile_saved,
        "latency_samples": len(latencies_ms),
        "avg_latency_ms": avg_ms,
        "p95_latency_ms": p95_ms,
    }


def _tool_output_flag(output: str, key: str, expected) -> bool:
    """True when a tool's JSON output has ``key == expected``.  Defensive: a
    tool may return a plain string instead of a dict."""
    if not output:
        return False
    try:
        return json.loads(output).get(key) == expected
    except (json.JSONDecodeError, AttributeError, TypeError):
        return False


def _metrics_field(item, name: str):
    """Read a metric from a chat message, tolerating both dict and object
    representations used by different LiveKit versions."""
    metrics = getattr(item, "metrics", None)
    if isinstance(metrics, dict):
        return metrics.get(name)
    return getattr(metrics, name, None)


def _percentile(values: list[float], pct: float) -> float:
    """Nearest-rank percentile — the common "p95" of a small sample."""
    values = sorted(values)
    if not values:
        return 0.0
    rank = math.ceil(len(values) * pct / 100.0)
    return round(values[max(0, min(rank, len(values)) - 1)], 1)


def build_call_record(
    *,
    call_id: str,
    caller_id: str,
    channel: str,
    history,
    started_at: str,
    ended_at: str,
    duration_seconds: float | None,
    error: str | None = None,
    detail: str | None = None,
) -> dict:
    """Turn a session history plus call metadata into a complete call record."""
    signals = extract_call_signals(history)
    outcome, failure_type, reason = classify_call(
        user_turns=signals["user_turns"],
        agent_turns=signals["agent_turns"],
        duration_seconds=duration_seconds,
        escalation_created=signals["escalation_created"],
        facility_delivered=signals["facility_delivered"],
        profile_saved=signals["profile_saved"],
        error=error,
    )
    return {
        "call_id": call_id,
        "caller_id": privacy_id(caller_id),
        "channel": channel,
        "outcome": outcome,
        "failure_type": failure_type,
        "reason": reason,
        "started_at": started_at,
        "ended_at": ended_at,
        "duration_seconds": duration_seconds,
        "user_turns": signals["user_turns"],
        "agent_turns": signals["agent_turns"],
        "message_count": signals["message_count"],
        "tools_used": signals["tools_used"],
        "escalation_created": signals["escalation_created"],
        "facility_delivered": signals["facility_delivered"],
        "avg_latency_ms": signals["avg_latency_ms"],
        "p95_latency_ms": signals["p95_latency_ms"],
        "error": error,
        "detail": detail,
    }


class CallRecordStore:
    """SQLite-backed store of anonymised call records.

    Thread-safe (RLock), same pattern as ``memory.CallerStore`` and
    ``escalation.EscalationStore``.  The DB file lives at the repo root as
    ``call_analytics.db`` (gitignored).
    """

    def __init__(self, db_path: str = DEFAULT_DB_PATH) -> None:
        self._db_path = db_path
        self._lock = threading.RLock()
        os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
        with self._connect() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute(_SCHEMA)
            for stmt in _SCHEMA_INDEXES:
                conn.execute(stmt)
            conn.commit()

    @contextmanager
    def _connect(self) -> None:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def record(self, call: dict) -> dict:
        """Insert one call record.  ``call_id`` is primary-keyed, so recording
        the same call twice (e.g. a dial failure + a session shutdown) is
        idempotent — the first write wins.

        The caller identifier is always stored hashed, so even a caller that
        passes a raw phone number or cookie UUID cannot put private data into
        the store (defence in depth on top of ``build_call_record``).
        """
        now = _now_iso()
        with self._lock, self._connect() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO calls (call_id, caller_id, channel, outcome,"
                " failure_type, reason, started_at, ended_at, duration_seconds,"
                " user_turns, agent_turns, message_count, tools_used,"
                " escalation_created, facility_delivered, avg_latency_ms, p95_latency_ms,"
                " error, detail) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    call.get("call_id") or uuid.uuid4().hex[:12],
                    privacy_id(call.get("caller_id") or "anonymous"),
                    call.get("channel") or "browser",
                    call.get("outcome") or "failed",
                    call.get("failure_type"),
                    call.get("reason"),
                    call.get("started_at") or now,
                    call.get("ended_at") or now,
                    call.get("duration_seconds"),
                    int(call.get("user_turns") or 0),
                    int(call.get("agent_turns") or 0),
                    int(call.get("message_count") or 0),
                    json.dumps(call.get("tools_used") or []),
                    int(bool(call.get("escalation_created"))),
                    int(bool(call.get("facility_delivered"))),
                    call.get("avg_latency_ms"),
                    call.get("p95_latency_ms"),
                    call.get("error"),
                    call.get("detail"),
                ),
            )
            conn.commit()
        return self.get(call.get("call_id") or now)

    def get(self, call_id: str) -> dict | None:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM calls WHERE call_id = ?", (call_id,)
            ).fetchone()
        return _row_to_call(row) if row else None

    def count(self) -> int:
        with self._lock, self._connect() as conn:
            row = conn.execute("SELECT COUNT(*) AS n FROM calls").fetchone()
        return int(row["n"])

    def summary(self) -> dict:
        """Aggregate stats across all recorded calls."""
        with self._lock, self._connect() as conn:
            totals = dict(
                conn.execute(
                    "SELECT outcome, COUNT(*) FROM calls GROUP BY outcome"
                ).fetchall()
            )
            total = int(totals.get("success", 0)) + int(totals.get("failed", 0))
            success = int(totals.get("success", 0))
            failed = int(totals.get("failed", 0))

            duration_row = conn.execute(
                "SELECT AVG(duration_seconds) AS avg FROM calls"
                " WHERE duration_seconds IS NOT NULL"
            ).fetchone()
            avg_duration = (
                round(duration_row["avg"], 1) if duration_row["avg"] else None
            )

            latency_row = conn.execute(
                "SELECT AVG(avg_latency_ms) AS avg FROM calls WHERE avg_latency_ms IS NOT NULL"
            ).fetchone()
            avg_latency = (
                round(latency_row["avg"], 1) if latency_row["avg"] is not None else None
            )

            by_channel = {}
            for row in conn.execute(
                "SELECT channel, outcome, COUNT(*) AS n FROM calls"
                " GROUP BY channel, outcome"
            ):
                bucket = by_channel.setdefault(
                    row["channel"], {"total": 0, "success": 0, "failed": 0}
                )
                bucket[row["outcome"]] = int(row["n"])
                bucket["total"] = sum(bucket[o] for o in VALID_OUTCOMES)

            by_failure = dict(
                conn.execute(
                    "SELECT failure_type, COUNT(*) FROM calls"
                    " WHERE failure_type IS NOT NULL GROUP BY failure_type"
                ).fetchall()
            )
            by_reason = dict(
                conn.execute(
                    "SELECT reason, COUNT(*) FROM calls WHERE reason IS NOT NULL"
                    " GROUP BY reason ORDER BY COUNT(*) DESC"
                ).fetchall()
            )

            today = _today_str()
            today_counts = dict(
                conn.execute(
                    "SELECT outcome, COUNT(*) FROM calls WHERE substr(started_at,1,10) = ?"
                    " GROUP BY outcome",
                    (today,),
                ).fetchall()
            )

        return {
            "total": total,
            "success": success,
            "failed": failed,
            "success_rate": round(success / total * 100, 1) if total else None,
            "avg_duration_seconds": avg_duration,
            "avg_latency_ms": avg_latency,
            "today": {
                "date": today,
                "total": int(today_counts.get("success", 0))
                + int(today_counts.get("failed", 0)),
                "success": int(today_counts.get("success", 0)),
                "failed": int(today_counts.get("failed", 0)),
            },
            "by_channel": by_channel,
            "by_failure": {k: int(v) for k, v in by_failure.items()},
            "by_reason": by_reason,
        }

    def daily(self, days: int = 14) -> list[dict]:
        """Per-day totals for the last ``days`` days, oldest first.  Days with
        no calls still appear with zeros so charts stay aligned."""
        start = datetime.now(timezone.utc) - timedelta(days=days - 1)
        start_str = start.strftime("%Y-%m-%d")
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                "SELECT substr(started_at,1,10) AS day, outcome, COUNT(*) AS n"
                " FROM calls WHERE started_at >= ? GROUP BY day, outcome",
                (start_str,),
            ).fetchall()
        by_day: dict[str, dict] = {}
        for row in rows:
            bucket = by_day.setdefault(
                row["day"], {"date": row["day"], "total": 0, "success": 0, "failed": 0}
            )
            bucket[row["outcome"]] = int(row["n"])
            bucket["total"] = sum(bucket[o] for o in VALID_OUTCOMES)
        out = []
        for i in range(days):
            day = (start + timedelta(days=i)).strftime("%Y-%m-%d")
            out.append(
                by_day.get(day, {"date": day, "total": 0, "success": 0, "failed": 0})
            )
        return out

    def latency_trend(self, days: int = 14) -> list[dict]:
        """Average first-response latency per day (ms), oldest first."""
        start = datetime.now(timezone.utc) - timedelta(days=days - 1)
        start_str = start.strftime("%Y-%m-%d")
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                "SELECT substr(started_at,1,10) AS day, AVG(avg_latency_ms) AS avg"
                " FROM calls WHERE avg_latency_ms IS NOT NULL AND started_at >= ?"
                " GROUP BY day",
                (start_str,),
            ).fetchall()
        by_day = {row["day"]: round(row["avg"], 1) for row in rows}
        return [
            {
                "date": (start + timedelta(days=i)).strftime("%Y-%m-%d"),
                "avg_ms": by_day.get((start + timedelta(days=i)).strftime("%Y-%m-%d")),
            }
            for i in range(days)
        ]

    def recent(self, limit: int = 50, channel: str | None = None) -> list[dict]:
        """The most recent calls, newest first, limited.  Records are already
        anonymised (hashed caller, no transcripts)."""
        limit = max(1, min(int(limit), 500))
        sql = "SELECT * FROM calls"
        args: list[object] = []
        if channel:
            sql += " WHERE channel = ?"
            args.append(channel)
        sql += " ORDER BY started_at DESC LIMIT ?"
        args.append(limit)
        with self._lock, self._connect() as conn:
            rows = conn.execute(sql, args).fetchall()
        return [_row_to_call(row) for row in rows]


def _today_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")
