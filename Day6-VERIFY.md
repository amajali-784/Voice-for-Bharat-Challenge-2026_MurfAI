# Day 6 — Ask & Verify (Outbound Calls)

**What:** The agent (Swasthya Sahayak, Health Access track) dials **you** with a
medication / vaccination reminder and gently follows up. Built on **Murf Falcon**
`hi-IN-anisha` + Deepgram + Gemini + LiveKit outbound trunk → Linphone.

**Full reference:** `Day6.md` (setup + evaluate) and `backend/src/telephony/outbound/README.md` (trunk setup).

---

## 1. Pre-flight — check these are true

| # | Check | Pass |
|---|-------|------|
| 1 | `backend/.env.local` has `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`, `MURF_API_KEY`, `DEEPGRAM_API_KEY`, `GOOGLE_API_KEY` | ☐ |
| 2 | `LIVEKIT_SIP_OUTBOUND_TRUNK_ID` is set to your `ST_xxxx` Linphone trunk | ☐ |
| 3 | LiveKit trunk exists: address `sip.linphone.org`, transport `SIP_TRANSPORT_TLS`; `lk sip outbound list` shows it | ☐ |
| 4 | Linphone app logged in; **Media encryption mandatory = OFF** (Settings → Calls → Advanced) | ☐ |

---

## 2. Run it (2 terminals)

```bash
# Terminal 1 — outbound worker (from backend/)
cd backend
uv run python src/telephony/outbound/agent.py dev

# Terminal 2 — dial your Linphone account (username is enough)
uv run python src/telephony/outbound/dial.py --to sunita \
  --name "Sunita Devi" \
  --reminder medication --medication मधुमेह \
  --location Varanasi
```

`--reminder` = `medication` | `vaccination` | `followup`. `--to` also accepts
`sip:sunita@sip.linphone.org` or an E.164 number.

---

## 3. What to ask the agent during the call

| # | Say this | Expected response |
|---|----------|-------------------|
| 1 | *(just answer)* | **Opening (first 2 sentences)** — who (स्वास्थ्य सहायक), why (दवा/टीका याद दिलाना), how to stop (कॉल बंद करो) |
| 2 | "मुझे याद आया, दवा ले ली" | Acknowledge, gentle follow-up — how are you feeling, remember the dose |
| 3 | "नज़दीकी अस्पताल कहाँ है?" | Day 5 facility lookup (live OSM / local fallback, says the source) |
| 4 | "कॉल बंद करो" | `opt_out` — polite hang-up; recorded in memory; **never called again** |
| 5 | *(call again after opt-out)* | Agent must **not** call an opted-out number |
| 6 | "बुखार बहुत तेज़ है" (any serious symptom) | Defers to doctor / 108 — never diagnoses |

---

## 4. Verify against the official criteria

| # | Official requirement | Pass |
|---|----------------------|------|
| 1 | **Outbound use case for the track** — call is a medication/vaccination reminder (Health Access) | ☐ |
| 2 | **Telephony integrated** — LiveKit outbound trunk → Linphone (`sip.linphone.org`, TLS) | ☐ |
| 3 | **Agent actually calls a number you control** and completes the interaction | ☐ |
| 4 | **Opening says who / why / how-to-stop in the first two sentences** | ☐ |
| 5 | **Short video** recorded of the phone ringing + the call playing out | ☐ |
| 6 | **LinkedIn post** — mentions Murf Falcon (fastest TTS API), 10 Days of Voice Agents, tags **Murf AI**, uses **#VoiceForBharat** | ☐ |
| 7 | **Form submitted** — post link + name + email | ☐ |

**"You've finished Day 6 if":**
- ☐ Agent places a call and delivers something useful
- ☐ Opening states who is calling, why, and how to opt out
- ☐ LinkedIn post is live and the form submission is in

---

## 5. Outcome handling (Advanced, optional)

| Outcome | How to trigger | Expected behaviour |
|---------|---------------|--------------------|
| `answered` | Pick up and talk | Normal reminder conversation |
| `no_answer` | Don't pick up | Logged; **retried once after 10 min** |
| `busy` | Be on another call | Logged; **retried once after 10 min** |
| `declined` | Reject the call (603) | Logged; **no retry** |
| `voicemail` | Let it hit voicemail | Hang up; **no retry** |
| `opted_out` | Say "कॉल बंद करो" | Marked in memory; **never dialed again** |

Each attempt is appended to `backend/logs/outcomes.jsonl` — check `outcome`, `retry`, `attempt`.

---

## 6. Automated checks (run once)

```bash
cd backend
uv run pytest -q          # expects 57 passed
uv run ruff check .       # all checks passed
```
