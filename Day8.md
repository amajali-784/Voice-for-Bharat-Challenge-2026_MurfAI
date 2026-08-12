# Day 8 — Build a Call Analytics Dashboard

**Challenge:** [10 Days of Voice Agents — #VoiceForBharat Edition](https://github.com/murf-ai/voice-for-bharat-challenge-2026)
**Track:** Health Access
**Official task:** [`challenges/Day 8 Task.md`](https://github.com/murf-ai/voice-for-bharat-challenge-2026/blob/main/challenges/Day%208%20Task.md)

> The agent can now talk, remember, use tools, make calls, and ask humans for
> help. Today we add a simple dashboard to see how it is actually performing.

---

## The Day 8 task (official)

1. **Define what a successful call means** for the Health Access track (keep it simple and specific).
2. **Record the outcome of every call** — save success/failed when a call ends.
3. **Build a simple web dashboard** showing **total calls**, **successful calls**, and **failed calls**.
4. **Use real data** — the numbers must come from actual browser/SIP calls, never hardcoded.
5. **Test the success path** — make at least one successful call and watch total + successful go up.
6. **Protect caller information** — never show passwords, OTPs, PINs, account numbers, medical details, or full transcripts on the public dashboard.
7. **Record a short video** showing a successful call and total/successful increasing on the dashboard.
8. **Post on LinkedIn** — mention building a voice agent on **Murf Falcon** (fastest TTS API), that you're part of **10 Days of Voice Agents**, tag **Murf AI**, and use **#VoiceForBharat**.
9. **Submit your post link** on the submission form.

**Advanced (optional, all done):** failure path test, failure types (no response, hang-up, incomplete, tool/API error, SIP failures), success rate, call history with time/duration/channel/outcome, track-specific outcomes (escalations + facility guidance), per-channel breakdown, daily trend chart, live auto-refresh, latency (avg + p95).

---

## Our Day 8 use case (Health Access)

### Step 1 — What a successful call means

On Day 2 we defined the Health Access objectives: *help the caller understand
their symptoms, tell them the next right step, and escalate red-flag symptoms*.
That translates into one simple success rule:

> **A call is successful when the caller receives safe guidance or an
> appropriate escalation.**

Because the agent cannot always know the caller's intent perfectly, we infer it
from what actually happened during the call (`backend/src/analytics.py`):

| Success condition | Detected when |
| --- | --- |
| **Appropriate escalation filed** | the `create_escalation` tool returned `created: true` |
| **Facility guidance delivered** | `find_nearby_health_facilities` returned `status: "ok"` |
| **Health situation captured + guidance given** | `save_caller_info` ran and there was a real exchange of turns |
| **Completed consultation** | ≥ 2 user turns, ≥ 2 agent turns, and 30+ seconds of conversation |

Everything else is a **failed** call, grouped by **failure type**:

- `no_response` — the caller joined but never spoke.
- `user_hangup` — the caller left within 30 s, before any guidance.
- `incomplete` — the conversation ended before guidance was delivered.
- `tool_error` — the agent reported an error.
- `sip_no_answer` / `sip_busy` / `sip_declined` / `sip_trunk_failure` /
  `sip_voicemail` / `sip_opted_out` / `sip_unknown` — outbound calls that
  never connected or never reached a live person.

### Step 2 — Record the outcome of every call

When any call ends, the entrypoint's shutdown callback builds an **anonymised**
record from the session history and writes it into a SQLite store
(`call_analytics.db`, gitignored):

- **Browser calls** — the inbound `entrypoint` in `backend/src/agent.py` registers
  `_record_call` on `ctx.add_shutdown_callback(...)`.
- **Outbound SIP calls** — `backend/src/telephony/outbound/agent.py` records dial
  failures separately (they never connect) and records connected calls from its
  own shutdown callback, marking voicemail / opt-out / completed-reminder outcomes.

### Step 6 — Privacy

The store never keeps transcripts, names, phone numbers, OTPs, or medical
details. Caller identifiers are stored as an opaque SHA-256 hash
(`privacy_id()`), and only counts, timings, and tool names survive. That
anonymised data is exactly what the public dashboard may show — and all it
shows.

---

## What was built

| File | What it does |
| --- | --- |
| `backend/src/analytics.py` | `CallRecordStore` — SQLite (WAL, thread-safe) store of anonymised call records. `classify_call()` implements the success definition above, `extract_call_signals()` reads only counts/tool names/latency from a session history, `build_call_record()` turns a finished call into a record, `privacy_id()` hashes caller ids, and `summary()` / `daily()` / `latency_trend()` / `recent()` feed the dashboard. |
| `backend/src/analytics_api.py` | stdlib admin HTTP API on **`127.0.0.1:8702`** — `GET /analytics` (summary + daily + latency + recent), `GET /analytics/calls`, `/analytics/summary`, `/analytics/daily`, `/healthz`. CORS-enabled so the browser dashboard can read it. |
| `backend/src/agent.py` | Day 8 hook in the inbound `entrypoint`: a shutdown callback records every call's outcome with `channel="browser"`. |
| `backend/src/telephony/outbound/agent.py` | Day 8 hooks for SIP: `record_dial_failure()` for calls that never connect + a shutdown callback for answered calls (`channel="sip"`), including voicemail / opted-out / completed-reminder classification. |
| `backend/tests/test_analytics.py` | 24 tests — success/failure classification, signal extraction, privacy (a phone number never reaches the DB), store behaviour, plus one agent-level eval proving a real symptom call records as `success`. |
| `frontend/app/analytics/page.tsx` | **Call Analytics dashboard** at `/analytics` — total / successful / failed stat cards, success rate, today, avg duration, first-reply latency, a daily trend chart, per-channel split, failure reasons, and a recent-calls table. Live auto-refresh every 5 s (toggleable). |
| `frontend/app/layout.tsx` | Header link to the dashboard. |
| `frontend/.env.example` / `backend/.env.example` | Document `ANALYTICS_API_HOST` / `ANALYTICS_API_PORT` and `NEXT_PUBLIC_ANALYTICS_API_URL`. |
| `start_app.ps1` / `start_app.sh` | Now also start the analytics API. |

---

## Flow

```
call starts (browser or SIP)
  → agent session runs (memory, facility lookup, escalation tools)
  → call ends (hang up / job shutdown)
  → shutdown callback builds an anonymised record:
      history → extract_call_signals()   (counts, tool names, latency — no text)
             → classify_call()           (success / failed + why)
             → privacy_id(caller)        (SHA-256 hash)
  → CallRecordStore.record() into call_analytics.db (idempotent by call_id)
  → /analytics dashboard polls http://localhost:8702/analytics every 5 s
      total | success | failed | success rate | daily chart | recent calls
```

Nothing is hardcoded — every number on the dashboard comes from a real recorded
call.

---

## Setup (one time)

Add to `backend/.env.local` (both optional):

```bash
ANALYTICS_API_HOST=127.0.0.1
ANALYTICS_API_PORT=8702
```

Add to `frontend/.env.local` (optional — default is `http://localhost:8702`):

```bash
NEXT_PUBLIC_ANALYTICS_API_URL=http://localhost:8702
```

No new API keys. Everything runs locally on top of Days 1–7. The DB
`call_analytics.db` is created automatically at the repo root and is
gitignored.

---

## Run it

```bash
# Terminal 1 — agent (as usual)
cd backend
uv run python src/agent.py dev

# Terminal 2 — analytics dashboard API
cd backend
uv run python src/analytics_api.py

# Terminal 3 — frontend (as usual)
cd frontend
pnpm dev
```

(`start_app.ps1` on Windows / `start_app.sh` on macOS–Linux starts all of these,
including the memory and escalation APIs.)

Open **http://localhost:3000** and talk to the agent. Then open
**http://localhost:3000/analytics** — the call analytics dashboard.

Verify the API by hand:

```bash
curl http://localhost:8702/analytics          # summary + daily + latency + recent
curl http://localhost:8702/analytics/calls    # recent call records
curl http://localhost:8702/healthz            # {"ok": true}
```

---

## How to evaluate Day 8

### A. Automated checks (run once)

```bash
cd backend
uv run pytest tests/test_analytics.py -q   # 24 passed
uv run pytest -q                          # full suite (103 passed)
uv run ruff check . && uv run ruff format --check .
cd ../frontend
pnpm exec tsc --noEmit
pnpm exec prettier --check app/analytics/page.tsx app/layout.tsx
```

`tests/test_analytics.py` covers the pieces that must not break:

- **success definition** — escalation / facility guidance / saved profile +
  exchange / completed consultation each classify as `success`;
- **failure types** — no response, user hang-up, incomplete, tool error;
- **privacy** — a raw phone number can never reach the record or the DB
  (hashed at build time *and* defensively at insert time);
- **store** — insert/get/idempotency, summary aggregates, daily zero-fill,
  latency trend, recent ordering + channel filter;
- **agent eval** — a real symptom conversation (fever + cough + profile) records
  as a **successful** call.

### B. Manual checklist — official criteria

| # | Check | Pass |
| --- | --- | --- |
| 1 | **Success defined** — "caller received safe guidance or an appropriate escalation" (Health Access) | ☐ |
| 2 | **Outcome recorded for every call** — browser + SIP, success/failed + why | ☐ |
| 3 | **Dashboard shows total / successful / failed** at `/analytics` | ☐ |
| 4 | **Real data** — numbers come from `call_analytics.db`, not hardcoded | ☐ |
| 5 | **Success path tested** — one real call, total + successful both increase | ☐ |
| 6 | **No private data** — hashed caller ids only; no transcripts/OTPs/PINs/phones/medical details | ☐ |
| 7 | **Short video recorded** — successful call + dashboard counters increasing | ☐ |
| 8 | **LinkedIn post live** — Murf Falcon, 10 Days of Voice Agents, tag **Murf AI**, **#VoiceForBharat** | ☐ |
| 9 | **Form submitted** with the post link | ☐ |

**"You've finished Day 8 if":**
- ☐ The dashboard is connected to real call data
- ☐ It shows total, successful, and failed calls
- ☐ You have defined what success means for your agent
- ☐ At least one successful test call increased total and successful counts
- ☐ The dashboard does not expose sensitive caller information

### C. What to ask in the call + what to show in the video

**Before recording** — start the agent, the analytics API, and the frontend.
On the dashboard (or via `curl http://localhost:8702/analytics`) note the current
**total**, **success**, and **failed** counts so you can show them going up.

**Video part 1 — the successful call (browser).**
Open http://localhost:3000, press **"बातचीत शुरू करें"** and say:

| You say (in Hindi) | What the agent should do |
| --- | --- |
| *"मेरा नाम सुनीता है, मैं दिल्ली में रहती हूँ। मुझे हल्का बुखार और खाँसी है, क्या करूँ?"* | greets you, **saves your profile** (`save_caller_info`), asks how long, then gives safe home-care guidance — no diagnosis, no medicine names |
| *"दो दिनों से बुखार है।"* | asks follow-ups and finishes with safe advice |
| *"मेरे घर के पास कोई अस्पताल या क्लिनिक है?"* | calls **`find_nearby_health_facilities`** and reads back the closest facility with source + recency (Day 5) |

This call should record as **success** (profile saved + real exchange / facility
delivered).

**Video part 2 — the dashboard increasing.**
Without stopping the screen recording, open **http://localhost:3000/analytics**
(or keep it open in another tab with live updates on):

- **Total calls** increased by 1.
- **Successful calls** increased by 1.
- The **recent calls** table shows the new call with outcome **Successful** and
  the reason ("caller received facility guidance" / "health situation was
  captured…").
- Show the **success rate**, the **Today** card, and the **daily trend chart**
  reflecting the new call.
- Point out the **By channel** breakdown (Browser) and the **Why calls failed**
  section (no private details anywhere — only hashed caller ids).

**Video part 3 — (optional, advanced) the failure path.**
Make a short call that ends before guidance, e.g. join and immediately hang up,
or say *"बस जानकारी चाहिए थी, धन्यवाद"* and disconnect after one turn. Show the
dashboard: **Total** increases, **Successful** stays the same, **Failed**
increases by 1, and the reason shows "caller hung up before guidance" or
"conversation ended before guidance".

**Scripting tips**

- Keep it to ~60–90 seconds: successful call → dashboard counters going up →
  (optional) failure call → failed counter going up.
- Say out loud that the numbers are real: *"ये आँकड़े असली कॉल से आते हैं।"*
- Do **not** read your phone number, Aadhaar, or OTP into the call — everything
  is stored anonymised, but the video itself shouldn't show private data either.
- Mention **Murf Falcon** (fastest TTS API — the Anisha voice you hear is
  Murf Falcon), that you're part of **10 Days of Voice Agents**, tag **Murf AI**,
  and use **#VoiceForBharat** in the LinkedIn caption.

---

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| Dashboard shows "Could not reach the analytics API" | Start `uv run python src/analytics_api.py` (or use `start_app.ps1`), or set `NEXT_PUBLIC_ANALYTICS_API_URL` to the right host/port. Check `curl http://localhost:8702/healthz`. |
| Dashboard shows 0 after a real call | The record is written by the agent's shutdown callback — make sure the **agent worker** is running (`uv run python src/agent.py dev`), not just the frontend. Confirm a new row appears with `curl http://localhost:8702/analytics/calls`. |
| A "successful" call records as failed | The conversation was probably too short (< 2 user turns + 2 agent turns + 30 s) with no profile saved and no facility delivered. Have a real 2–3 turn consultation and save your name/village so `profile_saved` triggers success. |
| A test/eval call shows on the dashboard | Eval calls write to a temporary DB by default, but console-mode calls use `channel="console"` and do count. Reset with `Remove-Item call_analytics.db` (gitignored) before recording the video. |
| Devanagari prints as mojibake in the terminal | Set `$env:PYTHONIOENCODING='utf-8'` (PowerShell) before running. |

---

## Submission

1. Record the video (successful call → dashboard total + successful increasing →
   optional failure call → failed increasing) — under ~1 min is fine.
2. LinkedIn post: what you built, **Murf Falcon** (fastest TTS API) + **10 Days of
   Voice Agents**, tag **Murf AI**, **#VoiceForBharat**.
3. Submit the post link on the Day 8 submission form.
