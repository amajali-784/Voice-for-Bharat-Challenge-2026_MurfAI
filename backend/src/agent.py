"""
Voice Agent — Health Access Track (#VoiceForBharat, Day 4)
Speaks Hindi (or matches the caller's register) via Murf Falcon TTS (Anisha,
a multilingual Indian voice) with a conversational style.

Pipeline: Deepgram Nova-3 (multilingual) → Gemini LLM → Murf Falcon (Anisha,
Conversational style, sentence-tokenized, text-paced) with MultilingualModel
turn detection and preemptive generation for snappier responses.

Day 4 adds: persistent caller memory.  Each caller has a stable `caller_id`
(the frontend persists it as a cookie) and the agent can look up, save and
forget their health profile across calls using a SQLite-backed store
(`memory.py`).  A first-time caller is greeted normally; a returning caller
is greeted by name and by what we remember.
"""

import asyncio
import logging
from pathlib import Path

from dotenv import load_dotenv
from livekit.agents import (
    Agent,
    AgentSession,
    JobContext,
    JobProcess,
    RunContext,
    WorkerOptions,
    cli,
    function_tool,
)
from livekit.agents.tokenize.basic import SentenceTokenizer
from livekit.plugins import deepgram, google, murf, silero
from livekit.plugins.turn_detector.multilingual import MultilingualModel

from memory import DEFAULT_DB_PATH, CallerStore

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("health-access-agent")

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env.local")

# One shared store for all worker sessions.  SQLite + WAL handles concurrent
# sessions fine; each tool call opens a short-lived connection.
MEMORY_STORE = CallerStore(DEFAULT_DB_PATH)

# ---------------------------------------------------------------------------
# SYSTEM PROMPT — Health Access track, Day 4
# Structured per: IDENTITY / OBJECTIVES / KNOWLEDGE / LANGUAGE / MEMORY /
#                 GUARDRAILS / STYLE
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """
IDENTITY
आपका नाम "स्वास्थ्य सहायक" है। आप एक सामुदायिक स्वास्थ्य जानकारी वॉइस असिस्टेंट हैं,
जो ग्रामीण और अर्ध-शहरी भारत के लोगों की मदद के लिए बनाया गया है। आप किसी अस्पताल,
क्लिनिक या डॉक्टर की तरफ़ से बात नहीं कर रहे — आप एक स्वतंत्र जानकारी सहायक हैं।

OBJECTIVES (एक सफल कॉल में यह होना चाहिए)
1. उपयोगकर्ता को उनके लक्षणों को सरल भाषा में समझने में मदद करना — बिना निदान किए।
2. उन्हें अगला सही कदम बताना: घर पर आराम, नज़दीकी स्वास्थ्य केंद्र जाना, या तुरंत
   आपातकालीन मदद लेना।
3. गंभीर ("red-flag") लक्षणों को तुरंत पहचानना और तुरंत अस्पताल/108 की तरफ़
   एस्केलेट करना — बातचीत जारी रखने से पहले।

KNOWLEDGE (आप क्या जानते हैं, और कहाँ रुकते हैं)
- आपके पास सामान्य स्वास्थ्य जानकारी है, लेकिन आपके पास उपयोगकर्ता के नज़दीक किसी
  विशेष अस्पताल या क्लिनिक का लाइव डेटा नहीं है। नज़दीकी केंद्र के लिए हमेशा सुझाव दें
  कि वे स्थानीय ASHA वर्कर, PHC (Primary Health Centre), या 108 से संपर्क करें।
- आप कोई प्रयोगशाला रिपोर्ट, स्कैन, या तस्वीर पढ़ या समझ नहीं सकते।

LANGUAGE (कोड-मिश्रित भाषा को संभालना)
- उपयोगकर्ता जिस भाषा या मिश्रण में बोले — हिंदी, अंग्रेज़ी, Hinglish, या कोई अन्य
  भारतीय भाषा — उसी रजिस्टर में जवाब दें। अगर वे "fever" कहें तो आप भी "fever" शब्द
  इस्तेमाल कर सकते हैं, पूरे वाक्य को जबरन शुद्ध हिंदी में अनुवाद करने की ज़रूरत नहीं।
- अगर उपयोगकर्ता पूरी तरह अंग्रेज़ी में बोले, तो भारतीय अंग्रेज़ी (Indian English) में
  जवाब दें, हिंदी में नहीं।
- अगर भाषा बिल्कुल समझ न आए, तो विनम्रता से पूछें: "क्षमा करें, क्या आप दोबारा बता सकते हैं?"
- हमेशा सम्मानजनक "आप" का प्रयोग करें, "तुम" का नहीं।

MEMORY (याददाश्त — कॉल के बीच में)
- आपके पास तीन उपकरण हैं: lookup_caller, save_caller_info, और forget_caller।
- बातचीत शुरू होते ही lookup_caller से देखें कि यह कॉलर पहले बात कर चुका है या नहीं।
- जब कॉलर अपना नाम, उम्र, शहर/गाँव, फोन नंबर, पुरानी बीमारियाँ (conditions), चल रही
  दवाइयाँ (medications), या एलर्जी बताए — तो save_caller_info से उसे याद रखें।
- वापस आने वाले कॉलर से मिलते समय जो याद है उसे नाम से संदर्भित करके बताएं, लेकिन ज़ोर
  न दें और पूरी प्राइवेट जानकारी ज़ोर से न दोहराएँ। धीरे से पूछें कि उनकी सेहत अब कैसी है।
- अगर कॉलर कहे कि वे अपनी जानकारी भुला देना चाहते हैं, तो forget_caller से उसका पूरा
  रिकॉर्ड मिटा दें और पुष्टि करें।
- याद रखी गई बातें सिर्फ़ इस कॉलर के बारे में होती हैं; कभी किसी दूसरे व्यक्ति की जानकारी
  न बताएँ और न ही सुझाएँ।

GUARDRAILS (सख्त नियम — कभी न तोड़ें)
- कभी किसी बीमारी का नाम लेकर निदान (diagnosis) न करें — जैसे "आपको डेंगू है" कभी न कहें।
  इसकी जगह कहें: "यह लक्षण कई चीज़ों से हो सकते हैं, डॉक्टर जाँच करके बता सकेंगे।"
- कभी किसी दवा, टैबलेट या डोज़ का नाम न लें या सुझाव न दें — पर्ची (prescription) देना
  पूरी तरह वर्जित है।
- कभी यह दावा न करें कि आप डॉक्टर, नर्स या किसी मेडिकल पेशे से जुड़े व्यक्ति हैं।
- गंभीर लक्षण सुनते ही (सीने में दर्द, साँस लेने में तकलीफ़, बेहोशी, तेज़ खून बहना, आधे
  शरीर में कमज़ोरी/लकवा जैसे लक्षण, बच्चे में तेज़ बुखार के साथ सुस्ती, आत्महत्या के विचार)
  — तुरंत रुकें और कहें: नज़दीकी अस्पताल तुरंत जाएँ या 108 पर कॉल करें। इसके बाद सामान्य
  बातचीत जारी न रखें, एस्केलेशन को दोहराएँ अगर ज़रूरत हो।
- स्वास्थ्य से बाहर के अनुरोध (जैसे पैसे, कानूनी सलाह, या असंबंधित काम) को विनम्रता से
  मना करें और बताएं कि आप केवल स्वास्थ्य से जुड़ी जानकारी में मदद कर सकते हैं।

STYLE
- छोटे, स्पष्ट वाक्य — यह एक फोन कॉल है, निबंध नहीं। एक बार में एक ही बात पूछें।
- गर्मजोशी और धैर्य के साथ बोलें, जैसे भरोसेमंद कम्युनिटी हेल्थ वर्कर बोलता है।
- कभी बुलेट पॉइंट, ब्रैकेट, या 20 शब्दों से लंबे वाक्य न बोलें — यह सुनने के लिए है,
  पढ़ने के लिए नहीं।
""".strip()


class Assistant(Agent):
    """Swasthya Sahayak — a community health-information voice assistant with
    persistent caller memory."""

    def __init__(
        self,
        *,
        instructions: str | None = None,
        **kwargs,
    ) -> None:
        super().__init__(instructions=instructions or SYSTEM_PROMPT, **kwargs)

    def _store(self, ctx: RunContext) -> CallerStore:
        """The per-session store, overridable for tests via userdata."""
        try:
            return ctx.userdata.get("store", MEMORY_STORE)
        except ValueError:
            return MEMORY_STORE

    def _caller_id(self, ctx: RunContext) -> str:
        try:
            return ctx.userdata.get("caller_id", "anonymous")
        except ValueError:
            return "anonymous"

    @function_tool
    async def lookup_caller(self, ctx: RunContext) -> dict:
        """Return the saved health profile for the current caller, or an empty
        profile if we have never spoken with them before.

        Call this near the start of every call to greet a returning caller by
        name and to avoid asking for facts we already know.

        Returns:
            A dict with the caller's stored name, language, location, phone,
            dob, gender, conditions, medications, allergies and notes.
        """
        profile = self._store(ctx).get(self._caller_id(ctx))
        if profile is None:
            return {
                "caller_id": self._caller_id(ctx),
                "known": False,
                "message": "No saved profile yet.",
            }
        return {**profile, "known": True}

    @function_tool
    async def save_caller_info(
        self,
        ctx: RunContext,
        name: str | None = None,
        language: str | None = None,
        location: str | None = None,
        phone: str | None = None,
        dob: str | None = None,
        gender: str | None = None,
        conditions: list[str] | None = None,
        medications: list[str] | None = None,
        allergies: list[str] | None = None,
    ) -> dict:
        """Remember what the caller told us about themselves so we can help
        them better on future calls.

        Call this whenever the caller shares a stable fact: their name, age or
        date of birth, the language they speak, the village/town they live in,
        their phone number, known long-term conditions (e.g. diabetes, high
        blood pressure), medicines they are currently taking, or allergies.

        Args:
            name: The caller's name.
            language: The language(s) the caller speaks.
            location: The caller's village, town or district.
            phone: The caller's phone number.
            dob: The caller's date of birth or approximate age.
            gender: The caller's gender.
            conditions: Long-term health conditions the caller has mentioned.
            medications: Medicines the caller is currently taking.
            allergies: Known allergies the caller has mentioned.
        """
        store = self._store(ctx)
        profile = store.get(self._caller_id(ctx)) or {"caller_id": self._caller_id(ctx)}
        profile.update(
            {
                "name": name or profile.get("name"),
                "language": language or profile.get("language"),
                "location": location or profile.get("location"),
                "phone": phone or profile.get("phone"),
                "dob": dob or profile.get("dob"),
                "gender": gender or profile.get("gender"),
                "conditions": (conditions or profile.get("conditions") or [])
                if conditions is not None
                else profile.get("conditions"),
                "medications": (medications or profile.get("medications") or [])
                if medications is not None
                else profile.get("medications"),
                "allergies": (allergies or profile.get("allergies") or [])
                if allergies is not None
                else profile.get("allergies"),
            }
        )
        saved = store.upsert(profile)
        return {
            "saved": True,
            "caller_id": saved["caller_id"],
            "message": "I have remembered this information about the caller.",
        }

    @function_tool
    async def add_note(self, ctx: RunContext, note: str) -> dict:
        """Attach a short note to the caller's record (e.g. a follow-up reminder
        or a notable symptom pattern). Use sparingly — prefer structured fields
        in save_caller_info for stable facts.

        Args:
            note: The one-line note to remember.
        """
        store = self._store(ctx)
        profile = store.get(self._caller_id(ctx)) or {"caller_id": self._caller_id(ctx)}
        notes = list(profile.get("notes") or [])
        if note not in notes:
            notes.append(note)
        store.upsert({**profile, "notes": notes})
        return {"saved": True, "message": "Note added to the caller's record."}

    @function_tool
    async def forget_caller(self, ctx: RunContext) -> dict:
        """Permanently delete everything we have stored about the current
        caller. Call this only when the caller explicitly asks us to forget
        them.
        """
        store = self._store(ctx)
        deleted = store.delete(self._caller_id(ctx))
        return {
            "forgotten": deleted,
            "message": (
                "All information about this caller has been erased."
                if deleted
                else "There was no saved information to erase."
            ),
        }


def prewarm(proc: JobProcess) -> None:
    """Pre-load the Silero VAD model into the job process at startup so the
    first call doesn't pay the one-time ONNX model load inside the entrypoint
    (which can make the first call slow or silent)."""
    proc.userdata["vad"] = silero.VAD.load()


async def resolve_caller_id(ctx: JobContext) -> str:
    """The caller's identity on the room is their persistent caller_id,
    minted by the frontend token route.

    The participant list can be empty right after `ctx.connect()`, so wait
    briefly for the caller to appear before falling back to 'anonymous'."""
    for _ in range(100):  # wait up to ~5s for the caller to join
        for participant in ctx.room.remote_participants.values():
            if participant.identity:
                return participant.identity
        await asyncio.sleep(0.05)
    return "anonymous"


async def entrypoint(ctx: JobContext):
    await ctx.connect()

    caller_id = await resolve_caller_id(ctx)
    profile = MEMORY_STORE.get(caller_id)
    is_returning = bool(profile and profile.get("name"))

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
        userdata={"caller_id": caller_id, "store": MEMORY_STORE, "profile": profile},
    )

    agent = Assistant(instructions=SYSTEM_PROMPT)

    await session.start(agent=agent, room=ctx.room)

    if is_returning:
        logger.info("Returning caller '%s' (%s)", profile["name"], caller_id)
        await session.generate_reply(
            allow_interruptions=False,
            instructions=(
                f"यह एक वापस आने वाला कॉलर है जिसका नाम {profile['name']} है। "
                "गर्मजोशी से नाम लेकर अभिवादन करें और एक वाक्य में बताएं कि उन्हें पहले "
                "से याद है, फिर पूछें कि उनकी सेहत अब कैसी है और आज किस चीज़ में मदद करें। "
                "पूरी प्राइवेट जानकारी न दोहराएँ। छोटा रखें।"
            ),
        )
    else:
        await session.generate_reply(
            allow_interruptions=False,
            instructions=(
                "अपना परिचय दें: आप 'स्वास्थ्य सहायक' हैं। एक वाक्य में बताएं कि आप किस "
                "तरह मदद कर सकते हैं — लक्षण समझने में और नज़दीकी देखभाल खोजने में — और "
                "पूछें कि आज आप किस चीज़ में मदद कर सकते हैं। छोटा और गर्मजोशी भरा रखें।"
            ),
        )


if __name__ == "__main__":
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            agent_name="my-agent",
            prewarm_fnc=prewarm,
        )
    )
