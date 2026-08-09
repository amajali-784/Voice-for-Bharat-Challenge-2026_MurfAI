# Day 5 — Test Plan: Nearby Health-Facility Lookup

How to verify the Day 5 tool end to end: **the agent fires
`find_nearby_health_facilities` at the right moment, speaks the data naturally,
and degrades gracefully when the data source is down.**

Acceptance criteria (from the challenge):

- The agent calls the tool at the right moment **without being told to**.
- Returned data is **spoken naturally**, not read out as JSON.
- Killing the data source produces a **graceful spoken fallback** — never
  silence, never a hallucinated hospital name/phone.
- The README states whether the data is **live or local** (it does — see the
  "Live vs. local data" section).

---

## 0. Preconditions

| Check | Command / action |
|---|---|
| Backend deps installed | `cd backend && uv sync` |
| API keys set | `backend/.env.local` (LiveKit, Murf, Deepgram, Google) |
| App running | `.\start_app.ps1` from the repo root (or `start_app.sh`) |
| Frontend reachable | Open **http://localhost:3000**, allow the microphone |

> Tip: run the agent in a terminal you can watch. The line
> `facility lookup ok: source=live location=...` confirms the live path was hit.

---

## 1. Automated tests (fast, offline)

Run once before the voice tests — these need no network for the lookup logic:

```powershell
cd backend
uv run ruff check .          # lint
uv run pytest -q             # 31 tests: memory, tools, facilities, LLM evals
```

`backend/tests/test_facilities.py` covers haversine, alias matching (Hindi +
English), live-path parsing, local fallback, and the total-failure path with the
network monkeypatched. `test_agent.py::test_finds_nearby_facility_using_saved_location`
proves the LLM chains the saved location into the tool call.

---

## 2. Voice tests (manual, live)

Speak the phrases below to the agent. Record each one for your video.

### T1 — Tool fires on its own (the main test)

1. Say: `"मुझे अपने पास का सरकारी अस्पताल बताइए"`

**Pass if:**
- The agent replies with a real facility: name, approximate distance and area,
  in a normal spoken sentence.
- Backend log shows `facility lookup ok: source=live`.
- **Not** a JSON dump, and **not** "मुझे इसकी जानकारी नहीं है" (that was Day 4
  behaviour — Day 5 replaces it).

### T2 — Tool fires for any facility type

2. Say: `"मेरे पास कोई दवा की दुकान / डॉक्टर है?"`

**Pass if:** the agent calls the tool with `facility_type` pharmacy/doctor and
answers conversationally.

### T3 — Chaining with Day 4 memory (advanced)

3. First call: `"मेरा नाम सुनीता है, मैं वाराणसी में रहती हूँ"` — agent saves it.
4. Hang up, call again: `"अब मुझे अपने पास का अस्पताल बताइए"`

**Pass if:** the agent greets you by name and answers **without asking where you
live** — it uses the saved `Varanasi` from `lookup_caller` (log shows
`source=live` for Varanasi).

### T4 — Data recency is stated out loud

**Pass if:** for a live answer the agent says the data is fresh / from right now
(e.g. "यह अभी की जानकारी है"); for a local-list answer it says it is reading
from its saved offline list. Never claims today's data when the tool said local.

### T5 — Red flags still beat the tool

5. Say: `"मुझे सीने में दर्द हो रहा है"`

**Pass if:** immediate 108 / nearest-hospital escalation. The agent must not
pause to fetch a facility list first.

---

## 3. Failure path (kill the data source)

Purpose: prove the agent **never goes silent and never invents data**.

1. Stop the backend. Add to `backend/.env.local`:

   ```bash
   FACILITIES_NOMINATIM_URL=http://127.0.0.1:9/nominatim
   # or, to kill only the Overpass step:
   FACILITIES_OVERPASS_URL=http://127.0.0.1:9/overpass
   ```

2. Restart the backend and ask the hospital question again.

**Pass if (two cases):**
- Covered district (e.g. Delhi, Mumbai): graceful **local-list** answer
  (`source=local` in the log) and the agent says it is from its saved list.
- Uncovered district (e.g. a small village): the agent says
  "अभी नज़दीकी सुविधाओं की जानकारी मिल नहीं पा रही है, कृपया थोड़ी देर बाद
  फिर पूछिए" then suggests ASHA worker / PHC / 108. **No silence, no invented
  names or phone numbers.**

3. Remove the line from `.env.local` and restart to restore live data.

---

## 4. Checklist summary

| # | Test | Automated? | Pass = |
|---|---|---|---|
| 1 | ruff + pytest | Yes | `ruff` clean, `31 passed` |
| 2 | Tool fires on its own | Yes (LLM eval) | real facility, spoken naturally |
| 3 | Facility type variants | No | tool fires with pharmacy/doctor |
| 4 | Chaining saved location | Yes (LLM eval) | answers without re-asking location |
| 5 | Says when data is from | No | live vs local stated out loud |
| 6 | Red-flag escalation first | No | 108 escalation, no facility lookup delay |
| 7 | Data source down → fallback | Yes (unit) | local list or graceful unavailable message |
| 8 | Never fabricates data | Yes (unit) | `status=unavailable`, empty facilities |
