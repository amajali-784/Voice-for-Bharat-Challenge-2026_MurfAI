"""Day 7 tests: the human-help escalation flow.

Store + sanitizer + tool tests are fully network-free.  The LLM-as-judge eval
tests at the bottom exercise the real agent decision loop: an escalation is
created when a red-flag symptom is reported with consent, and *not* created
when the caller declines or when nothing serious is going on.
"""

import pytest
from livekit.agents import RunContext

from agent import Assistant
from escalation import (
    EscalationStore,
    new_reference_id,
    sanitize_summary,
)
from memory import CallerStore, new_caller_id

# ---------------------------------------------------------------------------
# Store behaviour
# ---------------------------------------------------------------------------


@pytest.fixture()
def store(tmp_path) -> EscalationStore:
    return EscalationStore(db_path=str(tmp_path / "escalations.db"))


def _request(**overrides) -> dict:
    base = {
        "caller_id": "caller-1",
        "caller_name": "Sunita Devi",
        "category": "red_flag_symptom",
        "urgency": "high",
        "summary": "Chest pain since this morning",
        "checked": "looked up saved profile",
        "followup": "call back",
        "language": "Hindi",
    }
    return {**base, **overrides}


def test_create_then_get(store: EscalationStore) -> None:
    created = store.create(_request())
    assert created["created"] is True
    assert created["duplicate"] is False
    assert created["status"] == "open"
    assert created["reference_id"].startswith("ESC-")

    fetched = store.get(created["reference_id"])
    assert fetched is not None
    assert fetched["caller_name"] == "Sunita Devi"
    assert fetched["urgency"] == "high"
    assert fetched["created_at"]


def test_list_orders_emergency_first(store: EscalationStore) -> None:
    store.create(_request(category="diagnosis_request", urgency="low"))
    store.create(_request(category="red_flag_symptom", urgency="emergency"))
    requests = store.list()
    assert requests[0]["urgency"] == "emergency"
    assert requests[1]["urgency"] == "low"


def test_update_status_lifecycle(store: EscalationStore) -> None:
    created = store.create(_request())
    assert store.update_status(created["reference_id"], "in_progress") is True
    assert store.get(created["reference_id"])["status"] == "in_progress"
    assert store.update_status(created["reference_id"], "resolved") is True
    assert store.get(created["reference_id"])["status"] == "resolved"


def test_update_status_rejects_bad_status(store: EscalationStore) -> None:
    created = store.create(_request())
    assert store.update_status(created["reference_id"], "banana") is False
    assert store.get(created["reference_id"])["status"] == "open"


def test_duplicate_open_request_is_updated_not_recreated(
    store: EscalationStore,
) -> None:
    first = store.create(_request())
    second = store.create(_request(summary="Chest pain got worse", urgency="emergency"))
    assert second["reference_id"] == first["reference_id"]
    assert second["duplicate"] is True
    assert store.count() == 1
    assert store.get(first["reference_id"])["summary"] == "Chest pain got worse"
    assert store.get(first["reference_id"])["urgency"] == "emergency"


def test_resolved_request_can_be_reopened_as_new(store: EscalationStore) -> None:
    first = store.create(_request())
    store.update_status(first["reference_id"], "resolved")
    second = store.create(_request(summary="Pain is back"))
    assert second["reference_id"] != first["reference_id"]
    assert store.count() == 2


def test_different_categories_are_separate_requests(store: EscalationStore) -> None:
    red = store.create(_request(category="red_flag_symptom"))
    diag = store.create(_request(category="diagnosis_request"))
    assert red["reference_id"] != diag["reference_id"]
    assert store.count() == 2


def test_count_by_status(store: EscalationStore) -> None:
    r1 = store.create(_request())
    store.create(_request(category="diagnosis_request"))
    store.update_status(r1["reference_id"], "resolved")
    assert store.count() == 2
    assert store.count("open") == 1
    assert store.count("resolved") == 1
    assert store.count("in_progress") == 0


def test_new_reference_id_has_expected_shape() -> None:
    assert len(new_reference_id()) == 10
    assert new_reference_id().startswith("ESC-")
    assert len({new_reference_id() for _ in range(100)}) == 100


# ---------------------------------------------------------------------------
# Private-info scrubbing
# ---------------------------------------------------------------------------


def test_sanitize_masks_phone_number() -> None:
    assert "9876543210" not in sanitize_summary("Call me at 9876543210 please")
    assert "[redacted]" in sanitize_summary("Call me at 9876543210 please")


def test_sanitize_masks_formatted_phone() -> None:
    out = sanitize_summary("Reach me on +91-98765-43210")
    assert "98765" not in out
    assert "[redacted]" in out


def test_sanitize_masks_aadhaar_and_card_numbers() -> None:
    assert "1234 5678 9012" not in sanitize_summary("my Aadhaar is 1234 5678 9012")
    assert "[redacted]" in sanitize_summary("my Aadhaar is 1234 5678 9012")


def test_sanitize_masks_otp_and_pin() -> None:
    assert "4521" not in sanitize_summary("OTP is 4521")
    assert "9999" not in sanitize_summary("my PIN is 9999")
    assert "[redacted]" in sanitize_summary("OTP is 4521")


def test_sanitize_leaves_plain_health_text_alone() -> None:
    out = sanitize_summary("Chest pain since morning, in Varanasi, 3 days")
    assert out == "Chest pain since morning, in Varanasi, 3 days"


def test_sanitize_handles_none_and_empty() -> None:
    assert sanitize_summary(None) == ""
    assert sanitize_summary("") == ""
    assert sanitize_summary("   ") == ""


# ---------------------------------------------------------------------------
# The create_escalation tool (fake RunContext, network-free)
# ---------------------------------------------------------------------------


class _FakeSpeechHandle:
    num_steps = 1


class _FakeSession:
    def __init__(self, userdata: dict) -> None:
        self.userdata = userdata


def _make_ctx(userdata: dict) -> RunContext:
    return RunContext(
        session=_FakeSession(userdata),
        speech_handle=_FakeSpeechHandle(),
        function_call=None,
    )


@pytest.fixture()
def caller_id() -> str:
    return new_caller_id()


@pytest.fixture()
def esc_store(tmp_path) -> EscalationStore:
    return EscalationStore(db_path=str(tmp_path / "escalations.db"))


@pytest.fixture()
def mem_store(tmp_path) -> CallerStore:
    return CallerStore(db_path=str(tmp_path / "memory.db"))


@pytest.mark.asyncio
async def test_tool_refuses_without_consent(
    esc_store: EscalationStore, mem_store: CallerStore, caller_id: str
) -> None:
    ctx = _make_ctx(
        {"caller_id": caller_id, "store": mem_store, "escalations": esc_store}
    )
    result = await Assistant().create_escalation(
        ctx,
        category="red_flag_symptom",
        summary="Chest pain",
        caller_consent=False,
    )
    assert result["created"] is False
    assert esc_store.count() == 0


@pytest.mark.asyncio
async def test_tool_creates_with_consent(
    esc_store: EscalationStore, mem_store: CallerStore, caller_id: str
) -> None:
    mem_store.upsert({"caller_id": caller_id, "name": "Sunita Devi"})
    ctx = _make_ctx(
        {"caller_id": caller_id, "store": mem_store, "escalations": esc_store}
    )
    result = await Assistant().create_escalation(
        ctx,
        category="red_flag_symptom",
        summary="Chest pain since morning, in Varanasi",
        urgency="emergency",
        checked="looked up saved profile",
        followup="call back",
        language="Hindi",
        caller_consent=True,
    )
    assert result["created"] is True
    assert result["reference_id"].startswith("ESC-")
    assert result["status"] == "open"

    stored = esc_store.get(result["reference_id"])
    assert stored["caller_name"] == "Sunita Devi"
    assert stored["category"] == "red_flag_symptom"
    assert stored["urgency"] == "emergency"
    assert stored["followup"] == "call back"
    assert stored["language"] == "Hindi"


@pytest.mark.asyncio
async def test_tool_sanitizes_summary_before_storing(
    esc_store: EscalationStore, mem_store: CallerStore, caller_id: str
) -> None:
    ctx = _make_ctx(
        {"caller_id": caller_id, "store": mem_store, "escalations": esc_store}
    )
    result = await Assistant().create_escalation(
        ctx,
        category="red_flag_symptom",
        summary="Call back at 9876543210, chest pain",
        caller_consent=True,
    )
    stored = esc_store.get(result["reference_id"])
    assert "9876543210" not in stored["summary"]


@pytest.mark.asyncio
async def test_tool_deduplicates_open_request(
    esc_store: EscalationStore, mem_store: CallerStore, caller_id: str
) -> None:
    ctx = _make_ctx(
        {"caller_id": caller_id, "store": mem_store, "escalations": esc_store}
    )
    agent = Assistant()
    first = await agent.create_escalation(
        ctx,
        category="diagnosis_request",
        summary="Wants a doctor's opinion",
        caller_consent=True,
    )
    second = await agent.create_escalation(
        ctx,
        category="diagnosis_request",
        summary="Still wants a doctor's opinion",
        caller_consent=True,
    )
    assert second["reference_id"] == first["reference_id"]
    assert second["duplicate"] is True
    assert esc_store.count() == 1


# ---------------------------------------------------------------------------
# Agent-level evals: escalation happens when it should, and not otherwise
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_red_flag_symptom_creates_escalation(tmp_path) -> None:
    """A caller with a red-flag symptom: agent tells them to seek urgent care,
    asks permission, and files a request once they agree."""
    from livekit.agents import AgentSession, inference

    mem_store = CallerStore(db_path=str(tmp_path / "memory.db"))
    esc_store = EscalationStore(db_path=str(tmp_path / "escalations.db"))
    caller_id = new_caller_id()

    async with (
        inference.LLM(model="openai/gpt-4.1-mini") as llm,
        AgentSession(
            llm=llm,
            userdata={
                "caller_id": caller_id,
                "store": mem_store,
                "escalations": esc_store,
            },
        ) as session,
    ):
        await session.start(Assistant())

        r1 = await session.run(
            user_input=("मेरे सीने में बहुत दर्द हो रहा है और साँस लेने में तकलीफ़ हो रही है")
        )
        r2 = await session.run(user_input="हाँ, हेल्थ वर्कर को बता दीजिए")

    calls = _function_calls(r1) + _function_calls(r2)
    assert any(e.name == "create_escalation" for e in calls), (
        f"expected create_escalation, got: {[(e.name, e.type) for e in calls]}"
    )
    assert esc_store.count() > 0, "a consenting red-flag call must file a request"


@pytest.mark.asyncio
async def test_declined_permission_does_not_create_escalation(tmp_path) -> None:
    """The caller says no to sharing: no request may be filed."""
    from livekit.agents import AgentSession, inference

    mem_store = CallerStore(db_path=str(tmp_path / "memory.db"))
    esc_store = EscalationStore(db_path=str(tmp_path / "escalations.db"))
    caller_id = new_caller_id()

    async with (
        inference.LLM(model="openai/gpt-4.1-mini") as llm,
        AgentSession(
            llm=llm,
            userdata={
                "caller_id": caller_id,
                "store": mem_store,
                "escalations": esc_store,
            },
        ) as session,
    ):
        await session.start(Assistant())

        await session.run(user_input=("मेरे सीने में दर्द हो रहा है और साँस लेने में तकलीफ़ है"))
        await session.run(user_input="नहीं, मेरी जानकारी किसी को मत भेजिए")

    assert esc_store.count() == 0


@pytest.mark.asyncio
async def test_normal_call_creates_no_escalation(tmp_path) -> None:
    """A routine symptom chat must not file a human-help request."""
    from livekit.agents import AgentSession, inference

    mem_store = CallerStore(db_path=str(tmp_path / "memory.db"))
    esc_store = EscalationStore(db_path=str(tmp_path / "escalations.db"))
    caller_id = new_caller_id()

    async with (
        inference.LLM(model="openai/gpt-4.1-mini") as llm,
        AgentSession(
            llm=llm,
            userdata={
                "caller_id": caller_id,
                "store": mem_store,
                "escalations": esc_store,
            },
        ) as session,
    ):
        await session.start(Assistant())

        result = await session.run(user_input="मुझे हल्का बुखार और खाँसी है, क्या करूँ?")

        calls = _function_calls(result)
        assert not any(e.name == "create_escalation" for e in calls), (
            f"routine call must not escalate, got: {[e.name for e in calls]}"
        )

    assert esc_store.count() == 0, "a routine advice call must not escalate"


def _function_calls(result) -> list:
    """Extract executed function calls from a run result."""
    return [e.item for e in result.events if e.type == "function_call"]
