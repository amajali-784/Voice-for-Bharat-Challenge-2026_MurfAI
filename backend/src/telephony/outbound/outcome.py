"""Outcome classification, retry rules, and structured logging for outbound calls.

Outbound calls end in outcomes an inbound agent never sees: no answer, busy,
declined, trunk failure, voicemail, an immediate hang-up, or a completed call.
This module turns those into a small set of labels, decides whether a retry is
worth it, and appends one JSON line per call to ``logs/outcomes.jsonl`` so the
Day 6 "outcome handling" story is observable.
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone

# SIP status codes LiveKit surfaces on a failed dial (see the SIPStatus enum).
#  408 Request Timeout / 480 Temporarily Unavailable -> the callee never answered
#  486 Busy Here / 600 / 603                        -> actively rejected
#  5xx                                              -> our trunk/provider failed
SIP_STATUS_TO_OUTCOME = {
    408: "no_answer",
    480: "no_answer",
    487: "no_answer",
    486: "busy",
    600: "busy",
    603: "declined",
    500: "trunk_failure",
    502: "trunk_failure",
    503: "trunk_failure",
    504: "trunk_failure",
}

# A human or machine answered. The conversation then decides the real outcome
# (see OUTCOME_TOOL names below).
ANSWERED_OUTCOMES = ("completed", "opted_out", "voicemail", "hung_up_immediate")

# Retry rule for the Advanced task: retry only transient failures, never after a
# rejection or a completed conversation. One automatic retry, ten minutes later.
RETRYABLE_OUTCOMES = ("no_answer", "busy", "trunk_failure")
MAX_ATTEMPTS = 2
RETRY_WAIT_MINUTES = 10

# Where the call log lives. Overridable so tests can write to a tmp dir.
DEFAULT_LOG_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "..", "logs"
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def classify_sip_status(status_code: int) -> str:
    """Map a SIP status code from a failed dial to an outcome label."""
    if status_code in SIP_STATUS_TO_OUTCOME:
        return SIP_STATUS_TO_OUTCOME[status_code]
    if 500 <= status_code < 600:
        return "trunk_failure"
    if 400 <= status_code < 500:
        return "no_answer"
    return "unknown"


def should_retry(outcome: str, attempt: int = 1) -> tuple[bool, str]:
    """Decide whether to redial after a failed call.

    Returns ``(retry, reason)``. Only transient failures are retried, and only
    up to ``MAX_ATTEMPTS`` total attempts.
    """
    if attempt >= MAX_ATTEMPTS:
        return False, "max attempts reached"
    if outcome not in RETRYABLE_OUTCOMES:
        return False, f"'{outcome}' is not retryable"
    return True, f"retry in ~{RETRY_WAIT_MINUTES} minutes"


def build_outcome(
    *,
    phone_number: str,
    room_name: str,
    outcome: str,
    detail: str = "",
    attempt: int = 1,
    name: str | None = None,
    call_id: str | None = None,
    log_dir: str = DEFAULT_LOG_DIR,
) -> dict:
    """Build a structured outcome record for one outbound call attempt."""
    return {
        "ts": _now_iso(),
        "call_id": call_id or uuid.uuid4().hex[:12],
        "phone_number": phone_number,
        "room_name": room_name,
        "name": name,
        "attempt": attempt,
        "outcome": outcome,
        "detail": detail,
        "retry": should_retry(outcome, attempt),
    }


def log_outcome(entry: dict, log_dir: str = DEFAULT_LOG_DIR) -> str:
    """Append one outcome record as a JSON line and return the file path."""
    os.makedirs(log_dir, exist_ok=True)
    path = os.path.join(log_dir, "outcomes.jsonl")
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return path
