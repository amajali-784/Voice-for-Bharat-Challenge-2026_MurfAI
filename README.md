# Day 10 — Share Your Voice Agent Journey

**Challenge:** [10 Days of Voice Agents — #VoiceForBharat Edition](https://github.com/murf-ai/voice-for-bharat-challenge-2026)
**Track:** Health Access
**Official task:** [`challenges/Day 10 Task.md`](https://github.com/murf-ai/voice-for-bharat-challenge-2026/blob/main/challenges/Day%2010%20Task.md)

> Over the last nine days, you built a voice agent that can talk, follow
> guardrails, remember users, use tools, make outbound calls, ask humans for
> help, track call outcomes, and hand conversations to a specialist. Today, you
> will share what you learned so someone else can build one too.

---

## The Day 10 task (official)

1. **Choose a format** for your blog post — a story, a build guide, or both.
2. **Introduce your agent** — the problem, your track, who it is for, and why voice.
3. **Describe the important features** — the ones that best tell your story.
4. **Write about the difficult parts** — what went wrong, what you tried, what worked.
5. **Help the reader build their own** — components, setup, API keys, testing.
6. **Add evidence** — screenshots, diagrams, code snippets, demo links.
7. **Publish the post** on any public blogging platform (Medium, DEV, Hashnode…).
8. **Share it on LinkedIn** — Murf Falcon (fastest TTS API), 10 Days of Voice
   Agents, tag **Murf AI**, **#VoiceForBharat**.
9. **Submit your LinkedIn post link** on the Day 10 submission form.

**"You've finished Day 10 if":**
- ☐ The blog explains what your agent does and who it helps
- ☐ It covers important features without listing every day
- ☐ It honestly describes at least one difficulty and how you handled it
- ☐ It gives readers a practical starting point to build their own
- ☐ It links to your public repository and exposes no private information
- ☐ The blog is published and the LinkedIn post is live

---

## Our submission at a glance

| Deliverable | Where | Status |
| --- | --- | --- |
| Blog post | Medium (draft below) | ☐ publish |
| LinkedIn post | LinkedIn (draft below) | ☐ publish |
| Repository | https://github.com/amajali-784/voice-for-bharat-challenge-2026 | ☐ live |
| Submission form | Day 10 Google Form (blog + LinkedIn + repo links) | ☐ submit |

The project — **स्वास्थ्य सहायक (Swasthya Sahayak)**, a bilingual Hindi/English
Health Access voice agent — is fully documented across the 10 days:

| Day | What was built | Documented in |
| --- | --- | --- |
| 4 | Persistent caller memory (SQLite) + `/admin` page | `README.md` |
| 5 | Real nearby health-facility lookup (live OSM + offline fallback) | `README.md` |
| 6 | Outbound reminder calls (SIP, opt-out) | `Day6.md` |
| 7 | Human-help escalations + `/escalations` dashboard | `Day7.md` |
| 8 | Anonymised call analytics + `/analytics` dashboard | `Day8.md` |
| 9 | Clinic-appointment specialist handoff | `backend/tests/test_handoff.py` |
| 10 | Blog post + LinkedIn post + submission | `Day10.md` (this file) |

---

## Blog post (draft — paste into Medium)

> ### How to publish in Medium
> 1. Paste the whole draft into Medium's editor.
> 2. Apply **Heading 1 / Heading 2** to the section titles via the toolbar.
> 3. Turn the code blocks into code blocks with the `</>` toolbar button.
> 4. Replace the `[PLACEHOLDER]` bits before publishing.
> 5. Publish, then paste the live URL into the LinkedIn draft below.

---

### I Built a Hindi Voice Agent for Health Access in 10 Days — and It Remembers Callers, Looks Up Real Hospitals, and Calls You Back

**The problem.** Half of India's population lives in rural and semi-urban
areas, and for most of them the first point of health guidance is a family
member, a local pharmacy, or WhatsApp forwards — not a doctor. The nearest PHC
may be kilometres away, and calling a busy health worker just to ask *"is this
fever serious?"* feels like wasting their time.

A phone is the one piece of technology almost everyone in that situation
already owns and knows how to use. An AI voice agent can sit on the other end
of that call and do the jobs that should never wait for a booking: explain
symptoms in plain language, say which symptoms need urgent care, point to the
nearest real facility, and remember a returning caller so a second call doesn't
start from zero.

That is what I built during **10 Days of Voice Agents — VoiceForBharat
Edition**, on the **Health Access** track. The result is **स्वास्थ्य सहायक
(Swasthya Sahayak)** — "Health Assistant" — a Hindi-speaking voice agent that
helps people in rural and semi-urban India make sense of their symptoms, and
never pretends to be a doctor.

**What the agent does.**

- Listens and replies in the caller's own register — Hindi, English, or
  Hinglish — in simple, non-technical language.
- Talks through symptoms conversationally, without ever diagnosing or prescribing.
- Looks up real nearby health facilities (hospitals, clinics, PHCs, pharmacies)
  from live OpenStreetMap data, with a curated offline fallback, and says out
  loud where the data came from and how fresh it is.
- Remembers returning callers — name, village, conditions, medicines,
  allergies — across calls, and forgets everything on request.
- Escalates red-flag symptoms (chest pain, trouble breathing, stroke-like
  weakness…) straight to "call 108 / go to the hospital", and can file a
  human-help request for a health worker — only with the caller's permission.
- Makes outbound calls to remind people about medication, vaccination, or
  follow-ups, with a clear opt-out ("कॉल बंद करो").
- Hands off to a specialist agent when the caller wants to plan a clinic visit —
  appointments, OPD tokens, what documents to bring.
- Records every call's anonymised outcome on a live analytics dashboard, so I
  can see how many calls actually succeed.

**How the system works.** The whole thing is built on the LiveKit Agents
framework, which wires five pieces into one real-time voice pipeline:

<img width="1440" height="1800" alt="image" src="https://github.com/user-attachments/assets/89bf0e25-9ed1-4cde-936c-82da4d0629fa" />


LiveKit handles the real-time transport and the voice activity detection; I
only had to wire the speech-to-text, the LLM, and the text-to-speech.

The voice is **Murf Falcon's `hi-IN-anisha`** — a calm, patient Hindi voice
that also speaks English and 12 other Indian languages, so the agent can switch
register with every caller. Murf Falcon is the fastest TTS API I've tried (55
ms model latency, ~130 ms time-to-first-audio), and at $0.01/1,000 characters
it keeps a health line affordable.

**The most important features.**

*1. A real personality with hard guardrails.* The system prompt (in
`backend/src/agent.py`) gives the agent an identity, objectives, and a strict
guardrails section. It may help you understand symptoms, but it can never name
a disease, never suggest a medicine, never claim to be a doctor, and must send
anyone with a red-flag symptom to 108 or a hospital immediately. I then
"red-teamed" it with ten adversarial prompts — "direct diagnosis pressure",
"just guess the disease", drug-naming pressure in Hinglish — and each run is
logged in `RED_TEAM.md`.

*2. Memory that survives between calls.* A 1-year `caller_id` cookie is minted
by the frontend token route and used as the LiveKit participant identity. The
agent resolves that identity on every call and greets a returning caller by
name. A small SQLite store keeps their profile, and `forget_caller` erases it
when they ask ("भूल जाइए"). An admin page lists what's remembered with a
Forget button.

*3. A tool that returns real data — and never hallucinates.*
`find_nearby_health_facilities` geocodes a place name with Nominatim and pulls
nearby facilities from the Overpass API (live OpenStreetMap), falling back to a
curated offline list when the network is down. Every result carries
`source` (live / local) and `data_as_of`, and the prompt forces the agent to
say how fresh the data is. If both sources fail it returns
`status: "unavailable"` and speaks a graceful line — it is explicitly built
never to invent a hospital name, distance, or phone number.

*4. Knowing when to ask a human.* The agent files a human-help request in
exactly two situations: a red-flag symptom, or a diagnosis request. It must ask
permission first — `caller_consent=False` creates nothing — and the summary is
scrubbed of phone numbers, OTPs, PINs, and Aadhaar numbers before storage. The
caller gets a reference ID (`ESC-XXXXXX`) and an honest next step, and an
already-open request is never duplicated. A dashboard at `/escalations` shows
the queue for a human worker.

*5. Outbound calls.* Instead of only answering, the agent dials out for
medication and vaccination reminders over a SIP trunk. Every call opens with
who is calling, why, and how to stop the calls — spoken deterministically so
the LLM can't skip it — and an opt-out is recorded forever.

*6. Call analytics with privacy by design.* Every call's outcome (success/failed
and why) is recorded in an anonymised SQLite store — caller IDs are SHA-256
hashed and no transcripts, names, phones, or medical details are ever stored. A
live dashboard at `/analytics` shows total / successful / failed calls, success
rate, per-channel breakdown, failure reasons, a daily trend, and latency.
`[PLACEHOLDER: paste a screenshot of your dashboard]`

*7. A specialist agent.* When the caller wants to plan a clinic visit, the main
agent hands off to a focused `ClinicAppointmentSpecialist` that inherits the
caller's memory and conversation, and can hand the conversation back when the
topic is outside its job.

All of this is covered by a growing pytest suite — memory, facility lookup,
escalation, analytics, handoff — including LLM-as-judge evals that run real
simulated conversations against the agent (100+ tests passing at the end of the
challenge).

**The difficult parts (the honest bits).**

*Getting the agent to never make up a hospital.* The first version would
happily invent a plausible-sounding "महात्मा गांधी अस्पताल" for a village that
had none. Fix: the tool now returns structured `status` / `source` /
`data_as_of` and the prompt makes the agent state the source and recency out
loud; when nothing is reachable it says so instead of fabricating.
Hallucination isn't just an LLM problem — it's a tool-design and
prompt-engineering problem.

*Multilingual turn detection.* A health call is full of mid-sentence pauses,
and the agent needs to know when the caller is done without cutting them off.
`preemptive_generation` plus the `MultilingualModel()` turn detector (from
`livekit.plugins.turn_detector.multilingual`) fixed the "replies over the
caller" problem. Small import gotcha: it is not exposed on
`livekit.plugins.turn_detector` directly.

*Caller identity was a timing problem.* Right after `ctx.connect()`, the
participant list can be empty, so the agent could resolve the caller to
"anonymous" and lose the memory hook. Fix: `resolve_caller_id()` waits briefly
for the caller to appear before falling back. Relatedly, `RunContext.userdata`
raises `ValueError` when unset, so every memory tool wraps it in try/except —
worth knowing before it bites you.

*The SIP outbound setup is fiddly.* The LiveKit trunk editor only accepts
E.164 numbers, so I used the wildcard (`numbers=["*"]`) and set
`SIP_FROM_NUMBER` per call. Linphone (my free SIP softphone for testing) also
needs "Media encryption mandatory" turned off — that alone cost me a session of
silent calls.

*Keeping analytics private.* The tempting shortcut is to log the conversation.
Instead, the recording hook only extracts counts, tool names, and timings from
the session history and hashes identifiers. The dashboard is safe to show
publicly because nothing private ever reaches the database.

**Build your own — a practical starting point.** You can run this exact agent
from the repo:

```text
https://github.com/amajali-784/voice-for-bharat-challenge-2026
```

The four components you'll always need:

1. **Speech-to-text** — here Deepgram `nova-3` in multilingual mode
   (`language="multi"`) so Hindi, Hinglish, and English are all understood.
2. **An LLM** — here Google Gemini (`gemini-3.5-flash-lite`) with a strong
   system prompt; your whole persona and guardrails live there.
3. **Text-to-speech** — here Murf Falcon
   (`murf.TTS(voice="hi-IN-anisha", style="Conversational", ...)`). Pick any of
   150+ voices from the Murf Voice Library.
4. **Real-time transport** — LiveKit Agents connects it all and handles rooms,
   VAD, and turn detection.

Setup (summary of the repo README):

```bash
# backend
cd backend
uv sync                                   # Python 3.10+, uv package manager
uv run python src/agent.py download-files # first time only (VAD model)
uv run python src/agent.py dev            # run the agent

# frontend (separate terminal)
cd frontend
pnpm install
pnpm dev                                  # http://localhost:3000
```

**Where to put API keys without exposing them.** Copy `backend/.env.example` →
`backend/.env.local` and `frontend/.env.example` → `frontend/.env.local`, and
fill in `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`,
`MURF_API_KEY`, `DEEPGRAM_API_KEY`, and `GOOGLE_API_KEY`. Both files are
gitignored, so the keys never reach the repo. Do not hardcode keys in code.

**To test the agent.** Open http://localhost:3000, click
**बातचीत शुरू करें** (Start talking), allow the microphone, and speak in Hindi —
the agent replies with Murf Falcon's Anisha voice. Or try the terminal-only
mode:

```bash
uv run python src/agent.py console
```

Optional admin APIs (each is a separate tiny server):

```bash
uv run python src/memory_api.py       # :8700 — powers /admin page
uv run python src/escalation_api.py   # :8701 — powers /escalations dashboard
uv run python src/analytics_api.py    # :8702 — powers /analytics dashboard
```

**What I'd improve next.**

- A real deployment. It runs locally today; the next step is a hosted agent
  worker plus a phone number via a SIP provider so it can serve a real community.
- More Indian languages. The voice and STT support them; the hard part is
  localising the facility data and the offline fallback list.
- A feedback loop into the analytics. Today the dashboard tells me whether a
  call succeeded; I'd like it to tell me why not at a per-utterance level so I
  can retrain the prompt on real failures.
- A human in the loop for escalations. Right now requests land in a dashboard;
  next, notify an actual health worker via SMS.

**Links.**

- Repository: https://github.com/amajali-784/voice-for-bharat-challenge-2026
- Murf Falcon (fastest TTS API): https://murf.ai/api/docs/text-to-speech/streaming
- Murf Voice Library: https://murf.ai/api/docs/voices-styles/voice-library
- LiveKit Agents docs: https://docs.livekit.io/agents
- Challenge: 10 Days of Voice Agents — VoiceForBharat Edition

#10DaysofAIVoiceAgents #MurfFalcon #VoiceForBharat @Murf AI

```

<img width="2879" height="1697" alt="image" src="https://github.com/user-attachments/assets/666a3368-acc4-44d8-a608-9507712e6559" />


<img width="2432" height="1029" alt="image" src="https://github.com/user-attachments/assets/39ab8090-023e-425c-9bad-006dce1db6ed" />
