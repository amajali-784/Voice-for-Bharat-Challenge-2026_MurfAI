"""Day 8 tests: call analytics.

Store + classification + privacy tests are fully network-free.  The LLM eval
at the bottom exercises the real agent loop and then classifies the resulting
session history — a successful symptom consultation must record as "success".
"""

import json

import pytest
from livekit.agents import llm

from analytics import (
    CallRecordStore,
    build_call_record,
    classify_call,
    extract_call_signals,
    privacy_id,
)

# ---------------------------------------------------------------------------
# Success / failure classification
# ---------------------------------------------------------------------------


def test_escalation_is_success() -> None:
    outcome, failure_type, reason = classify_call(
        user_turns=2,
        agent_turns=3,
        duration_seconds=40,
        escalation_created=True,
        facility_delivered=False,
        profile_saved=False,
    )
    assert outcome == "success"
    assert failure_type is None
    assert "escalat" in reason


def test_facility_delivery_is_success() -> None:
    outcome, *_ = classify_call(
        user_turns=1,
        agent_turns=2,
        duration_seconds=20,
        escalation_created=False,
        facility_delivered=True,
        profile_saved=False,
    )
    assert outcome == "success"


def test_profile_saved_with_exchange_is_success() -> None:
    outcome, *_ = classify_call(
        user_turns=1,
        agent_turns=1,
        duration_seconds=15,
        escalation_created=False,
        facility_delivered=False,
        profile_saved=True,
    )
    assert outcome == "success"


def test_completed_consultation_is_success() -> None:
    outcome, *_ = classify_call(
        user_turns=2,
        agent_turns=2,
        duration_seconds=45,
        escalation_created=False,
        facility_delivered=False,
        profile_saved=False,
    )
    assert outcome == "success"


def test_no_response() -> None:
    outcome, failure_type, _ = classify_call(
        user_turns=0,
        agent_turns=1,
        duration_seconds=120,
        escalation_created=False,
        facility_delivered=False,
        profile_saved=False,
    )
    assert outcome == "failed"
    assert failure_type == "no_response"


def test_user_hangup() -> None:
    outcome, failure_type, _ = classify_call(
        user_turns=1,
        agent_turns=2,
        duration_seconds=12,
        escalation_created=False,
        facility_delivered=False,
        profile_saved=False,
    )
    assert outcome == "failed"
    assert failure_type == "user_hangup"


def test_incomplete() -> None:
    outcome, failure_type, _ = classify_call(
        user_turns=1,
        agent_turns=2,
        duration_seconds=90,
        escalation_created=False,
        facility_delivered=False,
        profile_saved=False,
    )
    assert outcome == "failed"
    assert failure_type == "incomplete"


def test_tool_error_is_failure() -> None:
    outcome, failure_type, _ = classify_call(
        user_turns=1,
        agent_turns=1,
        duration_seconds=10,
        escalation_created=False,
        facility_delivered=False,
        profile_saved=False,
        error="deepgram failed",
    )
    assert outcome == "failed"
    assert failure_type == "tool_error"


# ---------------------------------------------------------------------------
# Signal extraction from a session history (anonymised)
# ---------------------------------------------------------------------------


def _ctx(items: list) -> llm.ChatContext:
    return llm.ChatContext(items=items)


def test_extract_signals_from_history() -> None:
    ctx = _ctx(
        [
            llm.ChatMessage(role="user", content=["मुझे बुखार है"]),
            llm.ChatMessage(
                role="assistant",
                content=["कितने दिनों से?"],
                metrics={"e2e_latency": 0.8},
            ),
            llm.FunctionCall(call_id="c1", name="save_caller_info", arguments="{}"),
            llm.FunctionCallOutput(
                call_id="c1",
                name="save_caller_info",
                output='{"saved": true}',
                is_error=False,
            ),
            llm.ChatMessage(role="user", content=["दो दिन से"]),
            llm.ChatMessage(
                role="assistant",
                content=["आराम कीजिए"],
                metrics={"e2e_latency": 1.2},
            ),
        ]
    )
    sig = extract_call_signals(ctx)
    assert sig["user_turns"] == 2
    assert sig["agent_turns"] == 2
    assert sig["message_count"] == 4
    assert sig["tools_used"] == ["save_caller_info"]
    assert sig["profile_saved"] is True
    assert sig["escalation_created"] is False
    assert sig["facility_delivered"] is False
    assert sig["avg_latency_ms"] == pytest.approx(1000.0)
    assert sig["p95_latency_ms"] == pytest.approx(1200.0)


def test_extract_signals_flags_escalation_and_facility() -> None:
    ctx = _ctx(
        [
            llm.FunctionCall(call_id="c1", name="create_escalation", arguments="{}"),
            llm.FunctionCallOutput(
                call_id="c1",
                name="create_escalation",
                output='{"created": true, "reference_id": "ESC-ABC123"}',
                is_error=False,
            ),
            llm.FunctionCall(
                call_id="c2", name="find_nearby_health_facilities", arguments="{}"
            ),
            llm.FunctionCallOutput(
                call_id="c2",
                name="find_nearby_health_facilities",
                output='{"status": "ok", "facilities": []}',
                is_error=False,
            ),
        ]
    )
    sig = extract_call_signals(ctx)
    assert sig["escalation_created"] is True
    assert sig["facility_delivered"] is True


def test_extract_signals_ignores_transcript_text() -> None:
    ctx = _ctx(
        [
            llm.ChatMessage(
                role="user",
                content=["my Aadhaar is 123456789012 and phone 9876543210"],
            )
        ]
    )
    sig = extract_call_signals(ctx)
    assert sig["user_turns"] == 1
    assert sig["tools_used"] == []
    assert sig["escalation_created"] is False


def test_build_call_record_marks_success() -> None:
    ctx = _ctx(
        [
            llm.ChatMessage(role="user", content=["बुखार है"]),
            llm.ChatMessage(role="assistant", content=["कितने दिनों से?"]),
            llm.ChatMessage(role="user", content=["दो दिन"]),
            llm.ChatMessage(role="assistant", content=["आराम कीजिए"]),
        ]
    )
    record = build_call_record(
        call_id="call-1",
        caller_id="browser-cookie-uuid",
        channel="browser",
        history=ctx,
        started_at="2026-08-12T10:00:00+00:00",
        ended_at="2026-08-12T10:01:00+00:00",
        duration_seconds=60,
    )
    assert record["outcome"] == "success"
    assert record["failure_type"] is None
    assert record["duration_seconds"] == 60


def test_build_call_record_marks_failure() -> None:
    ctx = _ctx(
        [
            llm.ChatMessage(role="user", content=["hello"]),
            llm.ChatMessage(role="assistant", content=["नमस्ते, कैसे मदद करूँ?"]),
        ]
    )
    record = build_call_record(
        call_id="call-2",
        caller_id="someone",
        channel="browser",
        history=ctx,
        started_at="2026-08-12T10:00:00+00:00",
        ended_at="2026-08-12T10:00:10+00:00",
        duration_seconds=10,
    )
    assert record["outcome"] == "failed"
    assert record["failure_type"] == "user_hangup"


# ---------------------------------------------------------------------------
# Privacy
# ---------------------------------------------------------------------------


def test_privacy_id_is_an_irreversible_hash() -> None:
    assert privacy_id("9876543210") == privacy_id("9876543210")
    assert privacy_id("9876543210") != "9876543210"
    assert len(privacy_id("9876543210")) == 16
    assert privacy_id("") != ""
    assert privacy_id(None) != "None"


def test_phone_number_never_stored_raw() -> None:
    ctx = _ctx([llm.ChatMessage(role="user", content=["hello"])])
    record = build_call_record(
        call_id="call-3",
        caller_id="+91-9876543210",
        channel="sip",
        history=ctx,
        started_at="2026-08-12T10:00:00+00:00",
        ended_at="2026-08-12T10:00:05+00:00",
        duration_seconds=5,
    )
    blob = json.dumps(record, ensure_ascii=False)
    assert "9876543210" not in blob
    assert "9876543210" not in record["caller_id"]
    assert record["caller_id"] == privacy_id("+91-9876543210")


def test_store_hashes_caller_id_defensively(store: CallRecordStore) -> None:
    """Even a caller that passes a raw phone to record() can't put it in the
    DB — the store hashes caller ids at insertion."""
    store.record(_record(caller_id="+91-9876543210"))
    stored = store.get("call-1")
    assert stored is not None
    assert stored["caller_id"] == privacy_id("+91-9876543210")
    assert "9876543210" not in stored["caller_id"]
    assert "9876543210" not in json.dumps(stored, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Store behaviour
# ---------------------------------------------------------------------------


@pytest.fixture()
def store(tmp_path) -> CallRecordStore:
    return CallRecordStore(db_path=str(tmp_path / "analytics.db"))


def _record(**overrides) -> dict:
    base = {
        "call_id": "call-1",
        "caller_id": "caller-1",
        "channel": "browser",
        "outcome": "success",
        "failure_type": None,
        "reason": "completed consultation",
        "started_at": "2026-08-12T10:00:00+00:00",
        "ended_at": "2026-08-12T10:01:00+00:00",
        "duration_seconds": 60.0,
        "user_turns": 3,
        "agent_turns": 3,
        "tools_used": ["save_caller_info"],
        "escalation_created": False,
        "facility_delivered": False,
        "avg_latency_ms": 950.0,
        "p95_latency_ms": 1300.0,
        "error": None,
        "detail": None,
    }
    return {**base, **overrides}


def test_record_then_get(store: CallRecordStore) -> None:
    store.record(_record())
    stored = store.get("call-1")
    assert stored is not None
    assert stored["outcome"] == "success"
    assert stored["tools_used"] == ["save_caller_info"]
    assert stored["caller_id"] == privacy_id("caller-1")
    assert store.count() == 1

def test_record_is_idempotent(store: CallRecordStore) -> None:
    store.record(_record())
    store.record(_record(duration_seconds=999))
    assert store.count() == 1
    assert store.get("call-1")["duration_seconds"] == 60.0


def test_summary_aggregates(store: CallRecordStore) -> None:
    store.record(_record())
    store.record(
        _record(call_id="call-2", outcome="failed", failure_type="user_hangup")
    )
    store.record(
        _record(
            call_id="call-3",
            outcome="failed",
            failure_type="no_response",
            channel="sip",
            caller_id="+91123",
        )
    )
    summary = store.summary()
    assert summary["total"] == 3
    assert summary["success"] == 1
    assert summary["failed"] == 2
    assert summary["success_rate"] == pytest.approx(33.3)
    assert summary["by_failure"]["user_hangup"] == 1
    assert summary["by_failure"]["no_response"] == 1
    assert summary["by_channel"]["browser"]["total"] == 2
    assert summary["by_channel"]["sip"]["total"] == 1


def test_daily_has_zero_filled_days(store: CallRecordStore) -> None:
    store.record(_record())
    daily = store.daily(days=7)
    assert len(daily) == 7
    assert daily[-1]["date"] == "2026-08-12"
    assert sum(d["total"] for d in daily) == 1
    assert all(d["total"] == 0 for d in daily[:-1])


def test_recent_orders_newest_first(store: CallRecordStore) -> None:
    for i in range(5):
        store.record(
            _record(
                call_id=f"call-{i}",
                started_at=f"2026-08-12T10:0{i}:00+00:00",
            )
        )
    recent = store.recent(limit=3)
    assert len(recent) == 3
    assert recent[0]["call_id"] == "call-4"


def test_recent_channel_filter(store: CallRecordStore) -> None:
    store.record(_record(channel="browser"))
    store.record(_record(call_id="call-2", channel="sip"))
    assert len(store.recent(limit=10, channel="sip")) == 1
    assert store.recent(limit=10, channel="sip")[0]["channel"] == "sip"


def test_latency_trend(store: CallRecordStore) -> None:
    store.record(_record(avg_latency_ms=800.0))
    trend = store.latency_trend(days=3)
    assert len(trend) == 3
    assert trend[-1]["avg_ms"] == pytest.approx(800.0)
    assert trend[0]["avg_ms"] is None


# ---------------------------------------------------------------------------
# Agent-level eval: a real symptom call records as a success
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_symptom_call_records_as_success(tmp_path) -> None:
    """A normal symptom consultation produces history that classifies as a
    successful call — the caller received safe guidance."""
    from livekit.agents import AgentSession, inference

    from agent import Assistant
    from memory import CallerStore

    mem_store = CallerStore(db_path=str(tmp_path / "memory.db"))

    async with (
        inference.LLM(model="openai/gpt-4.1-mini") as llm_,
        AgentSession(
            llm=llm_,
            userdata={
                "caller_id": "eval-caller",
                "store": mem_store,
                "profile": None,
            },
        ) as session,
    ):
        await session.start(Assistant())
        await session.run(user_input="मुझे हल्का बुखार और खाँसी है, क्या करूँ?")
        await session.run(user_input="दो दिनों से बुखार है")
        await session.run(user_input="मेरा नाम सुनीता है और मैं दिल्ली में रहती हूँ")

    record = build_call_record(
        call_id="eval-call-1",
        caller_id="eval-caller",
        channel="eval",
        history=session.history,
        started_at="2026-08-12T10:00:00+00:00",
        ended_at="2026-08-12T10:01:00+00:00",
        duration_seconds=60,
    )
    assert record["user_turns"] >= 2
    assert record["outcome"] == "success", record["reason"]
