"""Outbound telephony agent — Swasthya Sahayak makes reminder calls.

Day 6: the agent stops waiting to be called and dials out instead.  Use case
for the Health Access track: a medication / vaccination reminder and a gentle
follow-up on how the person is doing, chained to the Day 4 caller memory and
the Day 5 facility lookup.

Unlike inbound calls, the person did not ask for this call and does not know
who we are, so every call must open with *who is calling, why, and how to stop
the calls* — enforced by a deterministic opening that is spoken before the LLM
takes over, plus an opt_out tool that records the request in memory.

Flow
----
worker (`uv run python src/telephony/outbound/agent.py dev`)
  <- dispatched by `dial.py --to sunita` (any Linphone username)
  -> reads phone_number from job metadata (a sip: URI or an E.164 number)
  -> dials via LiveKit SIP (outbound trunk -> sip.linphone.org, TLS)
     -> the Linphone app on the person's phone rings
  -> speaks the opening, then runs the reminder conversation
  -> records the outcome (answered / no_answer / busy / voicemail / opted_out)
"""

import asyncio
import contextlib
import json
import logging
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Script-mode bootstrap.  Running `python src/telephony/outbound/agent.py`
# puts this file's own directory first on sys.path, which would shadow the
# top-level `agent` module.  Force the backend `src/` dir to the front so the
# top-level `agent`, `memory` and `facilities` modules resolve the same way
# they do for the inbound worker (it may already be present from the editable
# install, but too far down to win).
_SRC_DIR = Path(__file__).resolve().parents[2]
_src = str(_SRC_DIR)
sys.path[:] = [_src] + [
    p for p in sys.path if os.path.normcase(p) != os.path.normcase(_src)
]

from dotenv import load_dotenv
from livekit import api, rtc
from livekit.agents import (
    AgentSession,
    JobContext,
    JobProcess,
    RunContext,
    WorkerOptions,
    cli,
    function_tool,
    get_job_context,
    room_io,
)
from livekit.agents.tokenize.basic import SentenceTokenizer
from livekit.plugins import deepgram, google, murf, silero
from livekit.plugins.turn_detector.multilingual import MultilingualModel

from agent import Assistant
from memory import DEFAULT_DB_PATH, CallerStore
from telephony.outbound.outcome import (
    build_outcome,
    classify_sip_status,
    log_outcome,
    should_retry,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("health-reminder-outbound")

load_dotenv(
    dotenv_path=os.path.join(os.path.dirname(__file__), "..", "..", "..", ".env.local")
)

# One shared store, same as the inbound worker.
MEMORY_STORE = CallerStore(DEFAULT_DB_PATH)

# Required — the LiveKit outbound trunk that routes to sip.linphone.org.
# Create it in the LiveKit Cloud console (Telephony -> SIP Trunks) or with the
# LiveKit CLI; see README.md for the Linphone setup.
OUTBOUND_TRUNK_ID = os.getenv("LIVEKIT_SIP_OUTBOUND_TRUNK_ID")

# Optional caller ID (a SIP identity) shown to the person we dial. If unset,
# the number(s) configured on the LiveKit trunk are used.
# LiveKit validates the From header like the dial target — a phone number or
# bare SIP user, NOT a full sip: URI or even user@host — so reduce any pasted
# value down to the bare user part (LiveKit appends the trunk's domain).
FROM_NUMBER = os.getenv("SIP_FROM_NUMBER")
if FROM_NUMBER:
    raw = FROM_NUMBER.strip()
    scheme = re.match(r"^(?:sips?):(.+)$", raw, re.IGNORECASE)
    if scheme:
        raw = scheme.group(1).strip()
    if "@" in raw:
        raw = raw.split("@", 1)[0]
    FROM_NUMBER = raw.strip()

# How long to let the phone ring before giving up (seconds).
RINGING_TIMEOUT = int(os.getenv("SIP_RINGING_TIMEOUT", "30"))

# The identity LiveKit gives the person we called.
CALLEE_IDENTITY = "phone-user"

# Marker the agent writes into caller notes when someone opts out.
OPT_OUT_PREFIX = "OPTED_OUT:"


# ---------------------------------------------------------------------------
# OUTBOUND SYSTEM PROMPT — Health Access track, Day 6
# ---------------------------------------------------------------------------
OUTBOUND_SYSTEM_PROMPT = """
IDENTITY
आपका नाम "स्वास्थ्य सहायक" है। आप एक सामुदायिक स्वास्थ्य जानकारी वॉइस असिस्टेंट हैं,
जो ग्रामीण और अर्ध-शहरी भारत के लोगों की मदद के लिए बनाया गया है। आप किसी अस्पताल
या डॉक्टर की तरफ़ से बात नहीं कर रहे — आप एक स्वतंत्र जानकारी सहायक हैं।

CONTEXT (यह एक आउटबाउंड कॉल है)
- आपने खुद कॉल किया है — व्यक्ति ने कॉल नहीं किया और आपको नहीं जानता।
- परिचय (आप कौन हैं), कॉल का कारण, और कॉल बंद करने का तरीका पहले ही कहा जा चुका है —
  उसे दोहराने की ज़रूरत नहीं है, जब तक व्यक्ति दोबारा न पूछे।
- कॉल छोटा और सम्मानजनक रखें। लोगों का समय बर्बाद न करें।

OBJECTIVES (एक सफल कॉल में यह होना चाहिए)
1. पूछें कि क्या उन्होंने आज अपनी दवा/टीका ली — जैसे "क्या आपने आज अपनी दवा ली?"
2. जवाब को memory में दर्ज करें (save_caller_info / add_note) ताकि अगली कॉल पर पता चले।
3. अगर दवा छूटी है, तो बिना निदान किए धीरे से प्रोत्साहित करें और याद दिलाएँ कि डॉक्टर की
   सलाह का पालन करें। कभी दवा/डोज़ सुझाव न दें।
4. अगर उन्हें नज़दीकी स्वास्थ्य सुविधा चाहिए या डॉक्टर से मिलना है, तो
   find_nearby_health_facilities से पता करें।
5. गंभीर (red-flag) लक्षण सुनते ही तुरंत रुकें और 108 / नज़दीकी अस्पताल जाने को कहें।
6. जैसे ही व्यक्ति कहे कि कॉल नहीं चाहिए ("कॉल बंद करो", "stop calling", "मुझे कॉल मत
   करो"), तुरंत opt_out टूल कॉल करें — बहस न करें, मनाने की कोशिश न करें।
7. जब बातचीत खत्म हो जाए, तो end_call टूल कॉल करें और विदा लें।
8. अगर आवाज़ बजाय बिना एक recorded ग्रीटिंग/बीप सुनें, तो detected_voicemail टूल कॉल करें।

MEMORY (याददाश्त — कॉल के बीच में)
- आपके पास ये उपकरण हैं: lookup_caller, save_caller_info, add_note, forget_caller,
  find_nearby_health_facilities, opt_out, end_call, detected_voicemail।
- कॉल शुरू होते ही lookup_caller से देखें कि इस व्यक्ति के बारे में क्या जानते हैं।
- व्यक्ति जो बताए (दवा ली/नहीं, कैसा महसूस कर रहे हैं) उसे save_caller_info या add_note
  से याद रखें।
- कभी किसी दूसरे व्यक्ति की जानकारी न बताएँ।

GUARDRAILS (सख्त नियम — कभी न तोड़ें)
- कभी निदान न करें, कभी दवा/डोज़ न लिखें या सुझाव न दें।
- कभी यह दावा न करें कि आप डॉक्टर/नर्स हैं।
- गंभीर लक्षणों पर पहले 108/अस्पताल — बातचीत जारी न रखें।
- कॉल बंद करने का अनुरोध हमेशा मानें — तुरंत और बिना सवाल किए।

STYLE
- छोटे, स्पष्ट वाक्य — यह एक फोन कॉल है। एक बार में एक ही बात पूछें।
- गर्मजोशी और धैर्य के साथ बोलें, जैसे भरोसेमंद कम्युनिटी हेल्थ वर्कर बोलता है।
- कभी बुलेट पॉइंट, ब्रैकेट, या 20 शब्दों से लंबे वाक्य न बोलें।
""".strip()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def has_opted_out(profile: dict | None) -> bool:
    """True if this caller has already asked us to stop calling them."""
    if not profile:
        return False
    return any(
        (note or "").startswith(OPT_OUT_PREFIX) for note in profile.get("notes") or []
    )


def mark_opted_out(profile: dict, store: CallerStore) -> dict:
    """Append the opt-out marker to a caller's notes (idempotent)."""
    notes = list(profile.get("notes") or [])
    if not has_opted_out(profile):
        notes.append(f"{OPT_OUT_PREFIX}{_now_iso()}")
        profile = {**profile, "notes": notes}
        store.upsert(profile)
    return profile


def parse_metadata(raw: str | None) -> dict | None:
    """Read the dial target and reminder details out of the dispatch metadata."""
    if not raw:
        return None
    try:
        meta = json.loads(raw)
    except json.JSONDecodeError:
        # Allow a bare phone number as metadata for quick `lk dispatch` tests.
        meta = {"phone_number": raw.strip()}
    if not meta.get("phone_number"):
        return None
    return meta


def reminder_phrase(meta: dict) -> str:
    """The reason-for-calling phrase, in Hindi, from the reminder metadata."""
    kind = (meta.get("reminder") or "medication").lower()
    if kind == "vaccination":
        vaccine = meta.get("vaccine") or "टीका"
        return f"आपके {vaccine} टीकाकरण की याद दिलाने के लिए"
    if kind == "followup":
        return "आपकी सेहत की फॉलो-अप जाँच के लिए"
    medication = meta.get("medication")
    if medication:
        return f"आपकी {medication} दवा की याद दिलाने के लिए"
    return "आपकी दवा की याद दिलाने के लिए"


def build_opening(meta: dict, profile: dict | None) -> str:
    """The mandatory opening: who is calling, why, and how to make it stop."""
    name = meta.get("name") or (profile or {}).get("name")
    greeting = f"नमस्ते {name} जी, " if name else "नमस्ते, "
    return (
        f"{greeting}मैं स्वास्थ्य सहायक बोल रहा हूँ। "
        f"हम {reminder_phrase(meta)} कॉल कर रहे हैं। "
        "अगर आपको ये कॉल नहीं चाहिए, तो बस 'कॉल बंद करो' कह दीजिए — "
        "हम फिर कभी कॉल नहीं करेंगे।"
    )


class HealthReminderAgent(Assistant):
    """Swasthya Sahayak, dialing out: inherits the Day 4 memory tools and the
    Day 5 facility lookup from `Assistant`, and adds the outbound-only tools:
    opt_out, end_call, detected_voicemail."""

    def __init__(self, *, instructions: str | None = None, **kwargs) -> None:
        super().__init__(instructions=instructions or OUTBOUND_SYSTEM_PROMPT, **kwargs)

    async def _hangup(self) -> None:
        """Delete the room, which drops the SIP leg and ends the phone call."""
        job_ctx = get_job_context()
        if job_ctx is None:
            logger.warning("hangup: no job context — cannot delete room")
            return
        try:
            await job_ctx.delete_room()
        except Exception:
            logger.exception("hangup: failed to delete room")

    @function_tool
    async def opt_out(self, ctx: RunContext) -> str:
        """Record that the person wants no further reminder calls, and end the call.

        Use this the moment they say "कॉल बंद करो", "stop calling", "मुझे कॉल
        मत करो", or anything that sounds like they don't want to be called.
        Do not keep talking or try to convince them.
        """
        store = self._store(ctx)
        caller_id = self._caller_id(ctx)
        profile = store.get(caller_id) or {"caller_id": caller_id}
        mark_opted_out(profile, store)
        logger.info("caller %s opted out of reminder calls", caller_id)

        await ctx.session.generate_reply(
            allow_interruptions=False,
            instructions=(
                "व्यक्ति ने कॉल बंद करने के लिए कहा है। सम्मान के साथ एक छोटे वाक्य में "
                "पुष्टि करें कि हम फिर कभी कॉल नहीं करेंगे, और विदा लें।"
            ),
        )
        await ctx.wait_for_playout()
        await self._hangup()
        return "Opted out — reminder calls stopped and call ended."

    @function_tool
    async def end_call(self, ctx: RunContext) -> str:
        """End the call with a short goodbye.

        Use this once the reminder conversation is finished.
        """
        await ctx.session.generate_reply(
            allow_interruptions=False,
            instructions=(
                "बातचीत पूरी हो गई है। छोटे, गर्मजोशी भरे वाक्य में विदा लें — जैसे "
                "'अपना ध्यान रखिए, स्वस्थ रहिए। धन्यवाद।' कुछ भी नया न पूछें।"
            ),
        )
        await ctx.wait_for_playout()
        await self._hangup()
        return "Call ended."

    @function_tool
    async def detected_voicemail(self, ctx: RunContext) -> str:
        """Hang up because the call reached a voicemail or answering machine.

        Use this as soon as you hear a recorded greeting or a beep rather than
        a live person.
        """
        logger.info("voicemail detected — hanging up")
        await self._hangup()
        return "Voicemail detected; call ended."


def prewarm(proc: JobProcess) -> None:
    """Pre-load the Silero VAD model so the first call isn't slow."""
    proc.userdata["vad"] = silero.VAD.load()


async def entrypoint(ctx: JobContext):
    meta = parse_metadata(ctx.job.metadata)
    if meta is None:
        logger.error("no phone number in job metadata — dispatch with dial.py --to")
        ctx.shutdown()
        return

    if not OUTBOUND_TRUNK_ID:
        logger.error("LIVEKIT_SIP_OUTBOUND_TRUNK_ID is not set — cannot place calls")
        ctx.shutdown()
        return

    phone_number = meta["phone_number"]
    room_name = ctx.room.name
    name = meta.get("name")
    attempt = int(meta.get("attempt", 1))

    # Respect a previous opt-out before the phone even rings.
    profile = MEMORY_STORE.get(phone_number)
    if has_opted_out(profile):
        logger.info(
            "skipping %s — caller has opted out of reminder calls", phone_number
        )
        log_outcome(
            build_outcome(
                phone_number=phone_number,
                room_name=room_name,
                name=name,
                outcome="opted_out",
                detail="skipped before dialing — prior opt-out on record",
                attempt=attempt,
            )
        )
        ctx.shutdown()
        return

    await ctx.connect()

    @ctx.room.on("participant_disconnected")
    def _on_disconnect(participant: rtc.RemoteParticipant) -> None:
        """Log how the call ended (hang-up, rejection, etc.)."""
        try:
            if participant.identity != CALLEE_IDENTITY:
                return
            reason = participant.disconnect_reason
            if reason == rtc.DisconnectReason.CLIENT_INITIATED:
                logger.info("callee hung up after the call was answered")
            elif reason == rtc.DisconnectReason.USER_REJECTED:
                logger.info("callee rejected the call before answering")
            elif reason == rtc.DisconnectReason.USER_UNAVAILABLE:
                logger.info("callee was unavailable")
            elif reason == rtc.DisconnectReason.SIP_TRUNK_FAILURE:
                logger.info("sip trunk or protocol failure")
            else:
                logger.info(
                    "callee disconnected: %s", rtc.DisconnectReason.Name(reason)
                )
        except Exception:
            logger.exception("error handling participant disconnect")

    # Start the session while the phone is still ringing so the models are warm
    # by the time somebody picks up.
    session = AgentSession(
        stt=deepgram.STT(model="nova-3", language="multi"),
        llm=google.LLM(model="gemini-3.5-flash-lite"),
        tts=murf.TTS(
            voice="hi-IN-anisha",
            style="Conversational",
            tokenizer=SentenceTokenizer(min_sentence_len=2),
            text_pacing=True,
        ),
        vad=ctx.proc.userdata.get("vad") or silero.VAD.load(),
        turn_detection=MultilingualModel(),
        preemptive_generation=True,
        userdata={
            "caller_id": phone_number,
            "store": MEMORY_STORE,
            "profile": profile,
        },
    )
    agent = HealthReminderAgent()

    try:
        session_started = asyncio.create_task(
            session.start(
                agent=agent,
                room=ctx.room,
                room_options=room_io.RoomOptions(
                    audio_input=room_io.AudioInputOptions(noise_cancellation=True),
                ),
            )
        )
    except Exception:
        logger.exception("failed to start session")
        ctx.shutdown()
        return

    dial_kwargs = {
        "room_name": room_name,
        "sip_trunk_id": OUTBOUND_TRUNK_ID,
        "sip_call_to": phone_number,
        "participant_identity": CALLEE_IDENTITY,
        "participant_name": name or "Phone user",
        "wait_until_answered": True,
        "ringing_timeout": timedelta(seconds=RINGING_TIMEOUT),
    }
    if FROM_NUMBER:
        dial_kwargs["sip_number"] = FROM_NUMBER

    logger.info("dialing %s in room %s", phone_number, room_name)
    try:
        # wait_until_answered means this returns once the call connects — if the
        # line is busy, declines, or never answers, it raises instead.
        await ctx.api.sip.create_sip_participant(
            api.CreateSIPParticipantRequest(**dial_kwargs)
        )
    except api.TwirpError as e:
        status_code = _sip_status_from_error(e)
        outcome = classify_sip_status(status_code)
        detail = f"sip_status={status_code} {e.message}"
        entry = build_outcome(
            phone_number=phone_number,
            room_name=room_name,
            name=name,
            outcome=outcome,
            detail=detail,
            attempt=attempt,
        )
        log_outcome(entry)
        retry, reason = should_retry(outcome, attempt)
        logger.info(
            "call to %s failed: %s (%s) — retry=%s (%s)",
            phone_number,
            outcome,
            detail,
            retry,
            reason,
        )
        with contextlib.suppress(Exception):
            session_started.cancel()
        ctx.shutdown()
        return

    await session_started
    logger.info("call answered: %s", phone_number)

    # The opening is spoken deterministically (not via the LLM) so the mandatory
    # who/why/opt-out disclosure can never be skipped.
    opening = build_opening(meta, profile)
    await session.say(opening, allow_interruptions=True)


def _sip_status_from_error(e: api.TwirpError) -> int:
    """Best-effort extraction of the SIP status code from a dial error."""
    try:
        raw = e.metadata.get("sip_status") if hasattr(e, "metadata") else None
        return int(raw)
    except (TypeError, ValueError):
        return 0


if __name__ == "__main__":
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            agent_name="health-reminder-agent",
            prewarm_fnc=prewarm,
        )
    )
