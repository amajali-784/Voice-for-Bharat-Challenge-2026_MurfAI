# Day 7 — Know When to Ask for Human Help

**Challenge:** [10 Days of Voice Agents — #VoiceForBharat Edition](https://github.com/murf-ai/voice-for-bharat-challenge-2026)
**Track:** Health Access
**Official task:** [`challenges/Day 7 Task.md`](https://github.com/murf-ai/voice-for-bharat-challenge-2026/blob/main/challenges/Day%207%20Task.md)

> Your agent can now remember users, use real data, and make outbound calls. But
> it should not try to solve every problem on its own.

---

## The Day 7 task (official)

1. **Choose two reasons for human help** — situations where the agent stops and files a request for a human.
2. **Build a human-help tool** — a `create_escalation` function the agent calls in those situations.
3. **Create a short summary for the human** — who needs help, what happened, what the agent already checked, how urgent it is, the caller's language and preferred follow-up. No passwords, OTPs, PINs, account numbers.
4. **Ask before sharing** — tell the caller what you'll send and ask permission; if they say no, don't file the request.
5. **Send the request somewhere real** — here: a local SQLite store + a dashboard page showing open requests.
6. **Give the caller a clear next step** — a reference ID and an honest "what happens next".
7. **Test both paths** — one conversation that needs human help, one that doesn't.
8. Record a video, post on LinkedIn (Murf Falcon, 10 Days of Voice Agents, tag **Murf AI**, **#VoiceForBharat**), submit the form.

**Advanced (optional, all done):** urgency levels, private-info removal, duplicate-request suppression, request status (open / in progress / resolved).

---

## Our Day 7 use case (Health Access)

The agent files a human-help request in exactly **two situations**:

| Reason | Trigger | Urgency |
| --- | --- | --- |
| **Red-flag symptom** | Chest pain, trouble breathing, fainting, heavy bleeding, stroke-like weakness, dangerously drowsy child, thoughts of self-harm. First: go to hospital / call **108**. Then: offer to notify a health worker. | `high` / `emergency` |
| **Diagnosis request** | The caller asks "what disease do I have?" or "what would a doctor say?". The agent explains it cannot diagnose and offers a health-worker callback. | `low` / `medium` |

In both cases the agent **must ask permission** first. The request is filed only
if the caller says yes. The caller gets a **reference ID** (e.g. `ESC-AB12CD`)
and an honest next step — *never* a promise of an immediate human reply.

---

## What was built

| File | What it does |
| --- | --- |
| `backend/src/escalation.py` | `EscalationStore` — SQLite queue of human-help requests (WAL, thread-safe, same pattern as `memory.py`). Holds reference ID, caller, category, urgency, short summary, what was checked, follow-up preference, language, status. `sanitize_summary()` strips phone / OTP / PIN / Aadhaar / account numbers as a second line of defence. `new_reference_id()` → `ESC-XXXXXX`. |
| `backend/src/escalation_api.py` | stdlib admin HTTP API on **`127.0.0.1:8701`** — `GET /escalations`, `GET /escalations/<ref>`, `PATCH /escalations/<ref>` `{"status": "in_progress"|"resolved"}`. Powers the dashboard. |
| `backend/src/agent.py` | New `create_escalation` `@function_tool` + an `ESCALATION` section in `SYSTEM_PROMPT` telling the agent *when*, *how* (permission first, sanitised summary), and *how not* to escalate (never on a routine call, never without consent, never with private details). |
| `backend/tests/test_escalation.py` | 22 tests — store lifecycle & dedupe, sanitizer, the tool (consent gate, redaction, dedupe), and 3 agent-level evals (escalation on red-flag + consent, **no** escalation on decline, **no** escalation on a routine call). |
| `frontend/app/escalations/page.tsx` | **Human Help dashboard** at `/escalations` — lists requests (emergency first), shows urgency badges + status, and lets a worker move them open → in progress → resolved. |
| `frontend/app/layout.tsx` | Header link to the dashboard. |
| `start_app.ps1` / `start_app.sh` | Now also start the escalation API. |

---

## Flow

```
caller reports chest pain / asks "what disease do I have?"
  → agent: urgent-care guidance (108/hospital) OR "I can't diagnose"
  → agent: "can I send a short note to a health worker so they can follow up?"
  → caller agrees? 
      ─ yes → create_escalation(category, urgency, summary, checked, followup, language, caller_consent=True)
      ─ no  → no request; agent gives PHC / doctor / 108 suggestions
  → request stored with reference_id ESC-XXXXXX (deduped if the same problem is already open)
  → agent reads the reference ID + an honest next step
  → health worker sees it on the /escalations dashboard, moves it to in_progress / resolved
```

---

## Setup (one time)

Add to `backend/.env.local` (both optional):

```bash
ESCALATION_API_HOST=127.0.0.1
ESCALATION_API_PORT=8701
```

Add to `frontend/.env.local` (optional — default is `http://localhost:8701`):

```bash
NEXT_PUBLIC_ESCALATION_API_URL=http://localhost:8701
```

No new API keys. Everything runs locally on top of Days 1–6.

---

## Run it

```bash
# Terminal 1 — agent (as usual)
cd backend
uv run python src/agent.py dev

# Terminal 2 — escalation dashboard API
cd backend
uv run python src/escalation_api.py

# Terminal 3 — frontend (as usual)
cd frontend
pnpm dev
```

Open **http://localhost:3000**, talk to the agent. Then open
**http://localhost:3000/escalations** — the human-help dashboard.

---

## How to evaluate Day 7

### A. Automated checks (run once)

```bash
cd backend
uv run pytest tests/test_escalation.py -q   # 22 passed
uv run pytest -q                            # full suite (expect 79 passed)*
uv run ruff check . && uv run ruff format --check .
```

`tests/test_escalation.py` covers the pieces that must not break:

- store: create → get → list (emergency first) → status lifecycle → count;
- **duplicates**: an already-open request for the same caller + category is
  *updated*, not recreated; a resolved request can be reopened as new;
- **consent gate**: `create_escalation` with `caller_consent=False` creates nothing;
- **redaction**: phone numbers, Aadhaar, OTPs/PINs never reach the stored summary;
- **agent evals**: a red-flag symptom + "हाँ" files a request; a red-flag symptom + "नहीं"
  files nothing; a mild-fever routine call files nothing.

> \* `tests/test_agent.py::test_finds_nearby_facility_using_saved_location` (Day 5)
> is an LLM-judged eval and is occasionally flaky (the eval LLM sometimes answers
> without calling the facility tool). It is unrelated to Day 7 — re-run it once and
> it passes.

### B. Manual checklist — official criteria

| # | Check | Pass |
| --- | --- | --- |
| 1 | **Two reasons chosen** — red-flag symptom + diagnosis request (Health Access) | ☐ |
| 2 | **`create_escalation` tool** the agent calls in those situations | ☐ |
| 3 | **Short, useful summary** — who, what, already-checked, urgency, language, follow-up method; no OTP/PIN/phone/account numbers | ☐ |
| 4 | **Asks before sharing** — and creates nothing if the caller declines | ☐ |
| 5 | **Sent somewhere real** — SQLite store + `/escalations` dashboard (localhost:8701) | ☐ |
| 6 | **Reference ID + honest next step** given to the caller | ☐ |
| 7 | **Both paths tested** — escalation call files a request; routine call does not | ☐ |
| 8 | **Short video** recorded (agent finds the problem → asks permission → files the request → dashboard shows it) | ☐ |
| 9 | **LinkedIn post** — Murf Falcon, 10 Days of Voice Agents, tag **Murf AI**, **#VoiceForBharat** | ☐ |
| 10 | **Form submitted** with the post link | ☐ |

**"You've finished Day 7 if":**
- ☐ The agent knows when it needs human help
- ☐ It asks for permission before sharing the caller's information
- ☐ It creates a real request with a short and useful summary
- ☐ It gives the caller a reference ID and an honest next step
- ☐ A normal conversation does not create an unnecessary request

### C. Conversation to script for the video

1. **Red-flag path** — caller: "मेरे सीने में दर्द है और साँस लेने में तकलीफ़ हो रही है।"
   Expect: 108/hospital guidance → permission ask → caller says "हाँ" → agent gives
   reference ID (ESC-…) → dashboard shows the request with high urgency.
2. **Decline path** — same opener, caller says "नहीं, मत भेजिए" → agent reassures and
   gives PHC/doctor/108 guidance; dashboard has **no** new request.
3. **Normal path** — caller: "मुझे हल्का बुखार और खाँसी है, क्या करूँ?" → sensible
   home-care advice, no request filed.
4. **Status** — on the dashboard, click "Start working" and "Mark resolved" and watch
   the status change.

---

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| Dashboard shows "Could not reach the escalation API" | Start `uv run python src/escalation_api.py` (or use `start_app.ps1`), or set `NEXT_PUBLIC_ESCALATION_API_URL` to the right host/port. |
| A request is created but `summary` looks empty | The agent should fill it in; check the `create_escalation` args in the agent log. Private fields are scrubbed by design. |
| Same caller keeps getting new requests | Only if the earlier request was marked **resolved** — an open one is updated, never duplicated. |
| Devanagari prints as mojibake in the terminal | Set `$env:PYTHONIOENCODING='utf-8'` (PowerShell) before running. |

---

## Submission

1. Record the video (agent finds problem → asks permission → files request → dashboard shows it) — under ~1 min is fine.
2. LinkedIn post: what you built, **Murf Falcon** (fastest TTS API) + **10 Days of Voice Agents**, tag **Murf AI**, **#VoiceForBharat**.
3. Submit the post link on the Day 7 submission form.
