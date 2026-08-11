# Day 6 — Make Outbound Calls

**Challenge:** [10 Days of Voice Agents — #VoiceForBharat Edition](https://github.com/murf-ai/voice-for-bharat-challenge-2026)
**Track:** Health Access
**Official task:** [`challenges/Day 6 Task.md`](https://github.com/murf-ai/voice-for-bharat-challenge-2026/blob/main/challenges/Day%206%20Task.md)

> Yesterday the agent waited to be called over the browser. Today it calls *you*.

---

## The Day 6 task (official)

1. Find the **outbound use case** for your track.
2. **Integrate a telephony service** (Twilio — or Linphone if the Twilio free trial is exhausted).
3. **Have your agent call you** (a number you control) and complete the interaction.
4. **Open the call properly** — in the first two sentences say *who is calling, why, and how to make it stop*.
5. **Record a short video** of the phone ringing and the call playing out.
6. **Post on LinkedIn** — mention building a voice agent on **Murf Falcon** (fastest TTS API), that you're part of **10 Days of Voice Agents**, tag **Murf AI**, and use **#VoiceForBharat**.
7. **Submit your post link** on the submission form (name + email).

**Advanced (optional):** Outcome handling — no answer, busy, voicemail, immediate hang-up, each with a defined behaviour and a retry rule.

---

## Our Day 6 use case (Health Access)

The agent dials a **medication / vaccination reminder** and does a gentle follow-up
on how the person is doing. It reuses everything from Days 1–5 (Deepgram → Gemini →
**Murf Falcon `hi-IN-anisha`** pipeline, SQLite caller memory, facility lookup).

The person didn't ask for this call, so **every call opens deterministically** with:

1. **Who** — "मैं स्वास्थ्य सहायक बोल रहा हूँ" (I'm Swasthya Sahayak)
2. **Why** — "हम आपकी मधुमेह दवा की याद दिलाने के लिए कॉल कर रहे हैं" (reminding you about your medicine/vaccine/follow-up)
3. **How to stop it** — "अगर आपको ये कॉल नहीं चाहिए, तो बस 'कॉल बंद करो' कह दीजिए" (say "stop calling" and we'll never call again)

The opening is spoken by `session.say(...)` **before** the LLM takes over, so it can
never be skipped. Opt-outs are stored in the Day 4 caller memory and checked before
the phone even rings.

---

## What was built

| File | What it does |
| --- | --- |
| `backend/src/telephony/outbound/agent.py` | Outbound worker (`health-reminder-agent`). Dials via `create_sip_participant`, speaks the opening, runs the reminder convo, records the outcome. Adds 3 tools to the Day 4 `Assistant`: `opt_out`, `end_call`, `detected_voicemail`. |
| `backend/src/telephony/outbound/dial.py` | CLI that creates a room + dispatch with the phone number and reminder metadata (`--to`, `--name`, `--reminder`, `--medication`, `--vaccine`, `--location`). |
| `backend/src/telephony/outbound/outcome.py` | SIP status → outcome mapping, retry rule, JSONL call log (`backend/logs/outcomes.jsonl`). |
| `backend/src/telephony/outbound/README.md` | Full Twilio + LiveKit trunk setup reference. |
| `backend/tests/test_outbound.py` | 23 network-free tests (opening, opt-out, outcomes, dial metadata). |

---

## Setup (one time)

### Step 1 — Twilio account

1. Sign up at [console.twilio.com](https://console.twilio.com) (free trial works for outgoing calls to a verified number).
2. **Add your phone as a verified caller ID**: Console → Phone Numbers → Verified Caller IDs → add your number. This is who your calls appear to come from.
3. **Buy (or trial-activate) a Twilio phone number** — the caller ID for outbound calls.

> If the Twilio free trial is exhausted, use the [Linphone fallback](https://github.com/murf-ai/voice-for-bharat-challenge-2026/blob/main/supplementary/outbound-over-linphone.md) instead.

### Step 2 — Twilio Elastic SIP Trunk

1. Console → **Elastic SIP Trunking → Trunks → Create** (e.g. `health-reminder`).
2. Note the **Termination URI** shown at the top (e.g. `mytrunk.pstn.twilio.com`).
3. Under **Credentials**, create a **Credential List** (username + password) and attach it to the trunk. Save these — the LiveKit trunk needs them.

### Step 3 — LiveKit outbound trunk

Create `outbound-trunk.json` with the Elastic SIP Trunk's **Termination URI**
and your Twilio number (the caller ID):

```json
{
  "trunk": {
    "name": "health-reminder-trunk",
    "address": "<your-trunk>.pstn.twilio.com",
    "numbers": ["+1xxxxxxxxxx"]
  }
}
```

Then create the trunk with the credential-list username/password from Step 2:

```bash
lk sip outbound create outbound-trunk.json \
  --auth-user "<sip-credential-username>" \
  --auth-pass "<sip-credential-password>"
```

The output prints the trunk ID (`ST_xxxx`) — that is `LIVEKIT_SIP_OUTBOUND_TRUNK_ID`.
Verify with `lk sip outbound list`.

(Alternative: LiveKit Cloud console → Telephony → SIP Trunks → **Create outbound trunk** with the same values.)

### Step 4 — Environment variables

In `backend/.env.local`:

| Variable | Value |
| --- | --- |
| `LIVEKIT_SIP_OUTBOUND_TRUNK_ID` | the `ST_xxxx` trunk id (required) |
| `TWILIO_PHONE_NUMBER` | your Twilio number — the caller ID (optional) |
| `SIP_RINGING_TIMEOUT` | seconds to ring before giving up (default `30`) |

Already present from Days 1–5: `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`, `MURF_API_KEY`, `DEEPGRAM_API_KEY`, `GOOGLE_API_KEY`.

> `TWILIO_ACCOUNT_SID` / `TWILIO_AUTH_TOKEN` are **not** needed to make calls — only to script the trunk setup.

---

## Run it (2 terminals)

```bash
# Terminal 1 — start the outbound worker (from backend/)
cd backend
uv run python src/telephony/outbound/agent.py dev

# Terminal 2 — dial your phone (E.164, with + and country code)
uv run python src/telephony/outbound/dial.py --to +919876543210
```

With reminder context (the opening uses it):

```bash
uv run python src/telephony/outbound/dial.py --to +919876543210 \
  --name "Sunita Devi" \
  --reminder medication --medication मधुमेह \
  --location Varanasi
```

`--reminder` is `medication` | `vaccination` | `followup`.

**Expected:** your phone rings within ~5 s of the dispatch. When you answer, the agent
speaks the opening (who / why / opt-out), then delivers the reminder. Say **"कॉल बंद
करो"** to test opt-out — the agent hangs up politely and will never dial you again.

---

## How to evaluate Day 6

### A. Automated checks (run once)

```bash
cd backend
uv run pytest -q                  # expects 54 passed
uv run ruff check .               # all checks passed
```

`tests/test_outbound.py` covers the pieces that must not break:
- opening contains who + why + opt-out instruction,
- `opt_out` is recorded once and blocks a second call,
- outcome mapping (no_answer / busy / declined / trunk_failure / voicemail / opted_out),
- retry rule (only no_answer/busy/trunk_failure retried, max 2 attempts, 10 min wait),
- E.164 validation in `dial.py`.

### B. Manual checklist — official criteria

Mark each item done before recording the video:

| # | Check | Pass |
| --- | --- | --- |
| 1 | **Outbound use case for the track** — the call is a medication/vaccination reminder (Health Access) | ☐ |
| 2 | **Telephony service integrated** — LiveKit outbound trunk → Twilio Elastic SIP Trunk | ☐ |
| 3 | **Agent actually calls a number you control** and completes the interaction | ☐ |
| 4 | **Opening says all three things in the first two sentences**: who is calling, why, how to stop it | ☐ |
| 5 | **Short video recorded** showing the phone ringing + the call playing out | ☐ |
| 6 | **LinkedIn post live** — mentions Murf Falcon (fastest TTS API), 10 Days of Voice Agents, tags **Murf AI**, uses **#VoiceForBharat** | ☐ |
| 7 | **Form submitted** with the post link + name + email | ☐ |

**"You've finished Day 6 if":**
- ☐ The agent places a call and delivers something useful
- ☐ The opening states who is calling, why, and how to opt out
- ☐ The LinkedIn post is live and the form submission is in

### C. Conversation quality (judge by ear)

1. **Opening** — first two sentences say who / why / opt-out in clear Hindi. (Deterministic, so this must be perfect every time.)
2. **Reminder** — the agent mentions the right medication/vaccine, checks whether it was taken, and answers follow-up questions.
3. **Opt-out** — saying "कॉल बंद करो" ends the call politely and permanently.
4. **Escalation** — anything serious still defers to a doctor / 108 (Day 1–3 behaviour intact).
5. **Voice + latency** — natural Anisha voice, no long gaps, correct Hindi pronunciation.

### D. Outcome handling (Advanced, optional)

Test the ones you can trigger on a call you control:

| Outcome | How to trigger it | Expected behaviour |
| --- | --- | --- |
| `no_answer` | Don't pick up | logged; retried once after 10 min |
| `busy` | Be on another call | logged; retried once after 10 min |
| `declined` | Reject the call (603) | logged; **no retry** (actively refused) |
| `voicemail` | Let it hit voicemail; agent says `detected_voicemail` | hang up; **no retry** |
| `opted_out` | Say "कॉल बंद करो" | recorded in memory; never dialed again |
| `answered` | Pick up and talk | normal conversation |

Every attempt is appended to `backend/logs/outcomes.jsonl` — check the `outcome`,
`retry` and `attempt` fields after each test.

---

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| Worker logs `LIVEKIT_SIP_OUTBOUND_TRUNK_ID is not set` | Create the LiveKit outbound trunk (Step 3) and set the env var (Step 4), then restart the worker. |
| Call ends instantly / never rings | Confirm the Elastic SIP Trunk Termination URI + credential list are correct and attached, and that your number is a **verified caller ID** on Twilio. |
| `dial.py` refuses a number | Use E.164 format: `+` then country code then number (e.g. `+919876543210`), 7–15 digits. |
| Devanagari prints as mojibake in the terminal | Set `$env:PYTHONIOENCODING='utf-8'` (PowerShell) before running. |

---

## Submission

1. Record the video (phone ringing + call playing out) — under ~1 min is fine.
2. LinkedIn post: what you built, **Murf Falcon** + **10 Days of Voice Agents**, tag **Murf AI**, **#VoiceForBharat**.
3. Submit the post link on the Day 6 submission form.
