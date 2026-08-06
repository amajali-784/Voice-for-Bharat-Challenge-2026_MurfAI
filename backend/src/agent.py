"""
Voice Agent — Health Access Track (#VoiceForBharat, Day 1)
Speaks Hindi via Murf Falcon TTS. STT: Deepgram. LLM: Gemini.

Drop this in as backend/src/agent.py in your fork of
https://github.com/murf-ai/murf-livekit-starter
(replace the existing file, keep everything else in the repo as-is).
"""

import logging
from pathlib import Path
from dotenv import load_dotenv
from livekit.agents import (
    Agent,
    AgentSession,
    JobContext,
    WorkerOptions,
    cli,
)
from livekit.plugins import deepgram, google, murf, silero

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("health-access-agent")

# Load backend/.env.local explicitly — python-dotenv's default load_dotenv()
# only looks for a file literally named ".env", so ".env.local" is ignored
# unless you point it there directly.
load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env.local")

# ---------------------------------------------------------------------------
# SYSTEM PROMPT — Health Access track
# Keep this in Hindi so the LLM's own text output is Hindi-first; Murf then
# speaks it natively rather than translating on the fly.
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """
आप एक सहायक स्वास्थ्य सहायता वॉइस एजेंट हैं, जो ग्रामीण और अर्ध-शहरी भारत में
लोगों को बुनियादी स्वास्थ्य जानकारी, नज़दीकी स्वास्थ्य केंद्र ढूंढने में मदद,
और डॉक्टर से मिलने से पहले लक्षण समझने में मदद करते हैं।

नियम:
- हमेशा हिंदी में, सरल और साफ भाषा में बात करें। कोई मुश्किल मेडिकल शब्द नहीं।
- आप डॉक्टर नहीं हैं — कभी निदान (diagnosis) या दवा न बताएं।
  गंभीर लक्षण सुनते ही तुरंत नज़दीकी अस्पताल या 108 पर कॉल करने की सलाह दें।
- छोटे, स्पष्ट वाक्यों में जवाब दें — यह एक फोन कॉल जैसा वॉइस एजेंट है, लेख नहीं।
- सहानुभूति और धैर्य के साथ बात करें, जैसे कोई भरोसेमंद कम्युनिटी हेल्थ वर्कर बोलता है।
- अगर बात समझ न आए, तो विनम्रता से दोबारा पूछें।
""".strip()


async def entrypoint(ctx: JobContext):
    await ctx.connect()

    session = AgentSession(
        # STT — Deepgram nova-2 has broader multilingual coverage than nova-3;
        # use language="hi" for Hindi speech recognition.
        stt=deepgram.STT(model="nova-2", language="hi"),
        # LLM — Gemini Flash, fast enough to keep round-trip latency low.
        # NOTE: gemini-2.5-flash is no longer available to new Google AI Studio
        # accounts (HTTP 404). gemini-3.5-flash-lite is the current replacement.
        llm=google.LLM(model="gemini-3.5-flash-lite"),
        # TTS — Murf Falcon, Hindi voice built for India.
        # Swap voice="hi-IN-pooja" for "hi-IN-samar" / "hi-IN-anisha" to try others.
        tts=murf.TTS(voice="hi-IN-pooja"),
        vad=silero.VAD.load(),
    )

    agent = Agent(instructions=SYSTEM_PROMPT)

    await session.start(agent=agent, room=ctx.room)

    # Kick off with a spoken greeting so the user isn't met with silence.
    await session.generate_reply(
        instructions="उपयोगकर्ता का गर्मजोशी से स्वागत करें और पूछें कि आज आप उनकी "
        "स्वास्थ्य से जुड़ी किस तरह मदद कर सकते हैं।"
    )


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, agent_name="my-agent"))