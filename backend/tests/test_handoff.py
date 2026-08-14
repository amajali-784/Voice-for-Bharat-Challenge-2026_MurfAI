"""Day 9 tests: handing off to the clinic & appointment specialist.

Unit tests (network-free) check that the main agent exposes the handoff tool,
that the tool returns a `ClinicAppointmentSpecialist`, that the specialist has
a narrower, focused toolset, and that `book_appointment` records the visit
plan.  LLM-as-judge evals at the bottom exercise the real routing rules: a
normal health question stays with the main agent, an appointment request is
handed off (with the specialist then continuing the same conversation), and
the specialist hands back when the request is really the main agent's job.
"""

import pytest
from livekit.agents import AgentSession, RunContext, inference

from agent import (
    CLINIC_APPOINTMENT_PROMPT,
    SYSTEM_PROMPT,
    Assistant,
    ClinicAppointmentSpecialist,
)
from memory import CallerStore, new_caller_id


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


def _tool_names(agent) -> set[str]:
    return {t.info.name for t in agent.tools if hasattr(t, "info")}


def _function_calls(result) -> list:
    """Extract executed function calls from a run result."""
    return [e.item for e in result.events if e.type == "function_call"]


@pytest.fixture()
def caller_id() -> str:
    return new_caller_id()


@pytest.fixture()
def store(tmp_path) -> CallerStore:
    return CallerStore(db_path=str(tmp_path / "memory.db"))


# ---------------------------------------------------------------------------
# Unit tests: tools and toolset shape (network-free)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_main_agent_exposes_handoff_tool() -> None:
    assert "transfer_to_appointment_specialist" in _tool_names(Assistant())


@pytest.mark.asyncio
async def test_handoff_tool_returns_specialist_agent() -> None:
    result = await Assistant().transfer_to_appointment_specialist(
        _make_ctx({"caller_id": "c1"})
    )
    specialist, message = result
    assert isinstance(specialist, ClinicAppointmentSpecialist)
    assert "स्पेशलिस्ट" in message
    assert specialist.instructions == CLINIC_APPOINTMENT_PROMPT


@pytest.mark.asyncio
async def test_specialist_has_focused_toolset() -> None:
    names = _tool_names(ClinicAppointmentSpecialist())
    assert "book_appointment" in names
    assert "transfer_back_to_main_agent" in names
    assert "find_nearby_health_facilities" in names
    assert "lookup_caller" in names
    assert "transfer_to_appointment_specialist" not in names
    assert "create_escalation" not in names


def test_main_and_specialist_have_different_jobs() -> None:
    assert CLINIC_APPOINTMENT_PROMPT != SYSTEM_PROMPT
    assert Assistant().instructions == SYSTEM_PROMPT
    assert ClinicAppointmentSpecialist().instructions == CLINIC_APPOINTMENT_PROMPT


@pytest.mark.asyncio
async def test_book_appointment_saves_visit_plan(
    store: CallerStore, caller_id: str
) -> None:
    ctx = _make_ctx({"caller_id": caller_id, "store": store})
    result = await ClinicAppointmentSpecialist().book_appointment(
        ctx,
        clinic="सामुदायिक स्वास्थ्य केंद्र, वाराणसी",
        date="सोमवार",
        time="सुबह 10 बजे",
        reason="आँखों की जाँच",
    )
    assert result["saved"] is True
    profile = store.get(caller_id)
    assert any("सामुदायिक स्वास्थ्य केंद्र" in (n or "") for n in profile["notes"])


@pytest.mark.asyncio
async def test_handoff_tool_preserves_conversation(store: CallerStore) -> None:
    """The specialist receives the caller's memory and a chat context, so the
    caller never has to explain the whole problem again."""
    caller_id = new_caller_id()
    store.upsert(
        {"caller_id": caller_id, "name": "Sunita Devi", "location": "Varanasi"}
    )
    main = Assistant()
    main._chat_ctx.add_message(role="user", content="मुझे डॉक्टर से अपॉइंटमेंट लेना है")
    result = await main.transfer_to_appointment_specialist(
        _make_ctx({"caller_id": caller_id, "store": store})
    )
    specialist, _ = result
    texts = [i.text_content or "" for i in specialist.chat_ctx.items]
    assert any("अपॉइंटमेंट" in t for t in texts), (
        "specialist should see the prior turn, got: " + str(texts)
    )


# ---------------------------------------------------------------------------
# LLM-as-judge evals: routing rules
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_normal_question_stays_with_main_agent(tmp_path) -> None:
    """A routine symptom question must not trigger a handoff."""
    mem_store = CallerStore(db_path=str(tmp_path / "memory.db"))
    caller_id = new_caller_id()

    async with (
        inference.LLM(model="openai/gpt-4.1-mini") as llm,
        AgentSession(
            llm=llm,
            userdata={"caller_id": caller_id, "store": mem_store},
        ) as session,
    ):
        await session.start(Assistant())

        result = await session.run(user_input="मुझे हल्का बुखार और खाँसी है, क्या करूँ?")

        calls = _function_calls(result)
        assert not any(e.name == "transfer_to_appointment_specialist" for e in calls), (
            f"routine call must not hand off, got: {[e.name for e in calls]}"
        )
        assert not any(e.type == "agent_handoff" for e in result.events)

        await result.expect.next_event(type="message").judge(
            llm,
            intent="""
            The main Swasthya Sahayak assistant gives gentle, non-diagnostic
            advice for mild fever and cough — home care, when to see a doctor,
            or asking a short clarifying question. It does NOT transfer the
            caller to an appointment specialist.
            """,
        )


@pytest.mark.asyncio
async def test_appointment_request_hands_off_to_specialist(tmp_path) -> None:
    """An appointment-planning request is handed to the specialist, who then
    continues the same conversation without making the caller repeat it."""
    mem_store = CallerStore(db_path=str(tmp_path / "memory.db"))
    caller_id = new_caller_id()
    mem_store.upsert(
        {"caller_id": caller_id, "name": "Sunita Devi", "location": "वाराणसी"}
    )

    async with (
        inference.LLM(model="openai/gpt-4.1-mini") as llm,
        AgentSession(
            llm=llm,
            userdata={"caller_id": caller_id, "store": mem_store},
        ) as session,
    ):
        await session.start(Assistant())

        r1 = await session.run(
            user_input=(
                "मुझे डॉक्टर से मिलने जाना है, अपॉइंटमेंट लेने के लिए मुझे कौन-से दस्तावेज़ चाहिए?"
            )
        )

        calls = _function_calls(r1)
        assert any(e.name == "transfer_to_appointment_specialist" for e in calls), (
            f"expected handoff tool, got: {[e.name for e in calls]}"
        )
        assert any(e.type == "agent_handoff" for e in r1.events), (
            "expected an agent_handoff event in r1"
        )
        r1.expect.contains_agent_handoff(new_agent_type=ClinicAppointmentSpecialist)

        # The specialist introduces itself and continues the conversation.
        r2 = await session.run(user_input="हाँ, मैं सोमवार को सुबह जाना चाहती हूँ")
        await r2.expect.next_event(type="message").judge(
            llm,
            intent="""
            The speaker acts as the clinic & appointment specialist and keeps
            helping with the Monday-morning visit plan — e.g. confirming where
            she plans to go, what to bring (ID, old prescriptions, reports),
            when to arrive, or which counter to go to. A short clarifying
            question (which clinic/area) is acceptable. It does NOT ask the
            caller to re-explain that they want an appointment or what the
            visit is for, and it does NOT hand the conversation back to the
            main agent.
            """,
        )


@pytest.mark.asyncio
async def test_specialist_hands_back_when_asked_for_symptom_help(tmp_path) -> None:
    """When the caller turns to symptoms after the handoff, the specialist
    hands the conversation back to the main agent."""
    mem_store = CallerStore(db_path=str(tmp_path / "memory.db"))
    caller_id = new_caller_id()

    async with (
        inference.LLM(model="openai/gpt-4.1-mini") as llm,
        AgentSession(
            llm=llm,
            userdata={"caller_id": caller_id, "store": mem_store},
        ) as session,
    ):
        await session.start(Assistant())

        await session.run(user_input="मुझे क्लिनिक में अपॉइंटमेंट लेना है, क्या लेकर जाना होगा?")

        r2 = await session.run(user_input="असल में मुझे बुखार और खाँसी है, इसके लिए मैं क्या करूँ?")

        calls = _function_calls(r2)
        assert any(e.name == "transfer_back_to_main_agent" for e in calls), (
            f"expected hand-back tool, got: {[e.name for e in calls]}"
        )
