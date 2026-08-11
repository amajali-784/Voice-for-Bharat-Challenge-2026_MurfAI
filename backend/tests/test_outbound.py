"""Day 6 tests: outbound-call outcomes, opt-out handling, the opening disclosure,
and the dial metadata builder.  All network-free — nothing here places a call.
"""

import argparse
import json

import pytest

from telephony.outbound import agent as outbound_agent
from telephony.outbound import dial as dial_mod
from telephony.outbound.outcome import (
    build_outcome,
    classify_sip_status,
    log_outcome,
    should_retry,
)

# ---------------------------------------------------------------------------
# Outcome classification (SIP status codes -> label)
# ---------------------------------------------------------------------------


def test_classify_no_answer_statuses() -> None:
    assert classify_sip_status(408) == "no_answer"
    assert classify_sip_status(480) == "no_answer"
    assert classify_sip_status(487) == "no_answer"


def test_classify_busy_and_declined() -> None:
    assert classify_sip_status(486) == "busy"
    assert classify_sip_status(603) == "declined"


def test_classify_trunk_failure() -> None:
    assert classify_sip_status(500) == "trunk_failure"
    assert classify_sip_status(503) == "trunk_failure"


def test_classify_unknown_status() -> None:
    assert classify_sip_status(404) == "no_answer"
    assert classify_sip_status(999) == "unknown"


# ---------------------------------------------------------------------------
# Retry rules (Advanced task)
# ---------------------------------------------------------------------------


def test_retry_transient_failures_once() -> None:
    retry, reason = should_retry("no_answer", attempt=1)
    assert retry is True
    assert "10" in reason

    retry, _ = should_retry("busy", attempt=1)
    assert retry is True


def test_no_retry_after_max_attempts() -> None:
    retry, reason = should_retry("no_answer", attempt=2)
    assert retry is False
    assert "max attempts" in reason


def test_no_retry_for_terminal_outcomes() -> None:
    assert should_retry("declined", 1)[0] is False
    assert should_retry("completed", 1)[0] is False
    assert should_retry("opted_out", 1)[0] is False
    assert should_retry("voicemail", 1)[0] is False


# ---------------------------------------------------------------------------
# Outcome logging
# ---------------------------------------------------------------------------


def test_build_outcome_shape() -> None:
    entry = build_outcome(
        phone_number="+919876543210",
        room_name="outbound-abc",
        name="Sunita Devi",
        outcome="no_answer",
        detail="sip_status=408",
    )
    assert entry["phone_number"] == "+919876543210"
    assert entry["outcome"] == "no_answer"
    assert entry["call_id"]
    assert entry["ts"]


def test_log_outcome_writes_jsonl(tmp_path) -> None:
    entry = build_outcome(
        phone_number="+919876543210",
        room_name="outbound-abc",
        outcome="completed",
    )
    path = log_outcome(entry, log_dir=str(tmp_path))
    assert path.endswith("outcomes.jsonl")
    with open(path, encoding="utf-8") as f:
        lines = [json.loads(line) for line in f]
    assert len(lines) == 1
    assert lines[0]["outcome"] == "completed"
    assert lines[0]["phone_number"] == "+919876543210"


# ---------------------------------------------------------------------------
# The mandatory opening: who, why, and how to stop it
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "meta",
    [
        {"name": "Sunita Devi", "reminder": "medication", "medication": "मधुमेह"},
        {"reminder": "vaccination", "vaccine": "खसरा"},
        {"reminder": "followup"},
        {},
    ],
)
def test_opening_states_who_why_and_opt_out(meta: dict) -> None:
    opening = outbound_agent.build_opening(meta, None)
    assert "स्वास्थ्य सहायक" in opening  # who is calling
    assert "कॉल कर रहे हैं" in opening  # why
    assert "कॉल बंद करो" in opening  # how to make it stop
    assert "फिर कभी कॉल नहीं करेंगे" in opening


def test_opening_uses_name_from_profile_when_metadata_has_none() -> None:
    opening = outbound_agent.build_opening(
        {"reminder": "followup"}, {"name": "Ram Prasad"}
    )
    assert "Ram Prasad" in opening


def test_reminder_phrases() -> None:
    assert "मधुमेह दवा" in outbound_agent.reminder_phrase(
        {"reminder": "medication", "medication": "मधुमेह"}
    )
    assert "खसरा टीकाकरण" in outbound_agent.reminder_phrase(
        {"reminder": "vaccination", "vaccine": "खसरा"}
    )
    assert "फॉलो-अप" in outbound_agent.reminder_phrase({"reminder": "followup"})
    assert "आपकी दवा की" in outbound_agent.reminder_phrase({"reminder": "medication"})


# ---------------------------------------------------------------------------
# Opt-out handling
# ---------------------------------------------------------------------------


def test_has_opted_out_detects_marker() -> None:
    assert outbound_agent.has_opted_out({"notes": ["OPTED_OUT:2026-08-11T00:00:00Z"]})
    assert not outbound_agent.has_opted_out({"notes": ["some other note"]})
    assert not outbound_agent.has_opted_out(None)
    assert not outbound_agent.has_opted_out({})


def test_mark_opted_out_is_idempotent(tmp_path) -> None:
    from memory import CallerStore, new_caller_id

    store = CallerStore(db_path=str(tmp_path / "memory.db"))
    caller_id = new_caller_id()

    profile = {"caller_id": caller_id, "name": "Sunita Devi"}
    first = outbound_agent.mark_opted_out(profile, store)
    assert outbound_agent.has_opted_out(first)

    outbound_agent.mark_opted_out(first, store)
    saved = store.get(caller_id)
    markers = [n for n in saved["notes"] if n.startswith("OPTED_OUT")]
    assert len(markers) == 1


def test_opt_out_survives_a_reload(tmp_path) -> None:
    from memory import CallerStore, new_caller_id

    store = CallerStore(db_path=str(tmp_path / "memory.db"))
    caller_id = new_caller_id()
    outbound_agent.mark_opted_out({"caller_id": caller_id}, store)

    reloaded = CallerStore(db_path=str(tmp_path / "memory.db"))
    assert outbound_agent.has_opted_out(reloaded.get(caller_id))


# ---------------------------------------------------------------------------
# Dispatch metadata parsing / building
# ---------------------------------------------------------------------------


def test_parse_metadata_json() -> None:
    meta = outbound_agent.parse_metadata(
        '{"phone_number": "+919876543210", "name": "Sunita", "reminder": "medication"}'
    )
    assert meta == {
        "phone_number": "+919876543210",
        "name": "Sunita",
        "reminder": "medication",
    }


def test_parse_metadata_bare_phone() -> None:
    meta = outbound_agent.parse_metadata("+919876543210")
    assert meta == {"phone_number": "+919876543210"}


def test_parse_metadata_missing_or_empty() -> None:
    assert outbound_agent.parse_metadata(None) is None
    assert outbound_agent.parse_metadata("") is None
    assert outbound_agent.parse_metadata("{}") is None


def test_dial_build_metadata() -> None:
    args = argparse.Namespace(
        to="+919876543210",
        name="Sunita Devi",
        reminder="vaccination",
        medication=None,
        vaccine="खसरा",
        location="Varanasi",
    )
    meta = json.loads(dial_mod.build_metadata(args))
    assert meta["phone_number"] == "+919876543210"
    assert meta["name"] == "Sunita Devi"
    assert meta["reminder"] == "vaccination"
    assert meta["vaccine"] == "खसरा"
    assert meta["location"] == "Varanasi"


def test_dial_normalizes_bare_linphone_username() -> None:
    assert dial_mod.normalize_dial_target("sunita") == "sunita"


def test_dial_strips_sip_scheme_and_domain() -> None:
    assert dial_mod.normalize_dial_target("sip:sunita@sip.linphone.org") == "sunita"
    assert dial_mod.normalize_dial_target("sunita@sip.linphone.org") == "sunita"


def test_dial_keeps_e164_number() -> None:
    assert dial_mod.normalize_dial_target("+919876543210") == "+919876543210"


def test_dial_rejects_invalid_target() -> None:
    args = argparse.Namespace(
        to="bad target!",
        name=None,
        reminder="medication",
        medication=None,
        vaccine=None,
        location=None,
    )
    with pytest.raises(SystemExit):
        dial_mod.build_metadata(args)
