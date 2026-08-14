# AGENTS.md

This is a monorepo for a voice AI agent starter, powered by Murf Falcon TTS and LiveKit Agents.

## Repository structure

```
voice-for-bharat-challenge-2026/
├── backend/          # Python voice agent (LiveKit Agents + Murf Falcon TTS)
│   ├── src/agent.py  # Agent entrypoint — pipeline + memory + facility tools + system prompt
│   ├── src/memory.py # SQLite CallerStore — persistent caller memory (Day 4)
│   ├── src/facilities.py # Nearby health-facility lookup — live OSM + offline fallback (Day 5)
│   ├── src/memory_api.py # Admin HTTP API — GET/DELETE callers on :8700 (Day 4)
│   ├── src/escalation.py # Human-help EscalationStore + sanitizer + reference IDs (Day 7)
│   ├── src/escalation_api.py # Admin HTTP API — GET/PATCH escalations on :8701 (Day 7)
│   ├── src/analytics.py # Anonymised CallRecordStore — call outcomes for the dashboard (Day 8)
│   ├── src/analytics_api.py # Admin HTTP API — GET /analytics aggregates on :8702 (Day 8)
│   └── tests/        # LLM-judged eval tests + memory/facility/tool unit tests
├── frontend/         # Next.js UI (LiveKit Agents UI components)
│   ├── app/          # Pages and API routes (incl. /admin, /escalations and /api/token)
│   ├── components/   # UI components (agents-ui, app, ui)
│   └── app-config.ts # Branding and feature config
├── start_app.sh      # Start all services (macOS/Linux)
└── start_app.ps1     # Start all services (Windows)
```

## Backend

### Tech stack
- **Python 3.10+** with **uv** package manager
- **LiveKit Agents SDK** (`livekit-agents ~1.4`) — voice AI agent framework
- **Murf Falcon** (`livekit-murf`) — text-to-speech
- **Deepgram Nova-3** — speech-to-text
- **Google Gemini** — LLM
- **Silero VAD** + **LiveKit Turn Detector** — voice activity and turn detection

### Key file: `backend/src/agent.py`
This is the single entrypoint. It contains:
- `SYSTEM_PROMPT` — controls the agent's behavior (change this to change the use case)
- `Assistant` class — extends `Agent`, where tools are added via `@function_tool` (Day 4: `lookup_caller`, `save_caller_info`, `add_note`, `forget_caller`; Day 5: `find_nearby_health_facilities`; Day 7: `create_escalation`; Day 9: `transfer_to_appointment_specialist`)
- `ClinicAppointmentSpecialist` class — the Day 9 specialist agent (appointment planning), with its own `CLINIC_APPOINTMENT_PROMPT`, `book_appointment` and `transfer_back_to_main_agent` tools
- `entrypoint()` — sets up the voice pipeline (STT → LLM → TTS) and connects to LiveKit
- `prewarm()` — pre-loads the Silero VAD model

### Health-facility lookup (Day 5)
- `backend/src/facilities.py` — `lookup_health_facilities(location, facility_type)`. Prefers
  live OpenStreetMap (Nominatim geocode + Overpass API, keyless), falls back to the curated
  offline `LOCAL_FACILITIES` list, and returns `status="unavailable"` (never fabricated data)
  if both fail. Every result has `source` ("live" | "local" | "none") and `data_as_of`.
- The `find_nearby_health_facilities` tool chains with Day 4 memory: use the caller's saved
  `location` from `lookup_caller` when they haven't just named a new one.
- Kill-switch env vars to demo the failure path: `FACILITIES_NOMINATIM_URL`,
  `FACILITIES_OVERPASS_URL`, or `FACILITIES_OVERPASS_URLS` (comma-separated mirrors).
- When writing a response, the agent must say the data source and recency out loud and must
  NOT read JSON or invent facility names/phones. This is enforced in the `TOOLS`/`STYLE`
  sections of `SYSTEM_PROMPT`.

### Human-help escalations (Day 7)
- `backend/src/escalation.py` — `EscalationStore` (SQLite, WAL) — a queue of human-help
  requests filed by the agent. Fields: reference_id (`ESC-XXXXXX`), caller_id, caller_name,
  category (`red_flag_symptom` | `diagnosis_request`), urgency (`low`/`medium`/`high`/`emergency`),
  summary, checked, followup, language, status (`open`/`in_progress`/`resolved`). `create()`
  dedupes: an already-open request for the same caller + category is updated, not duplicated.
  `sanitize_summary()` scrubs phone numbers / OTPs / PINs / Aadhaar / account numbers.
- `backend/src/escalation_api.py` — stdlib admin HTTP API. Default `127.0.0.1:8701`, override
  with `ESCALATION_API_HOST` / `ESCALATION_API_PORT`. Endpoints: `GET /escalations`,
  `GET /escalations/<ref>`, `PATCH /escalations/<ref>` with `{"status": ...}`.
- The `create_escalation` tool (in `agent.py`) is gated on `caller_consent=True` — the agent
  must ask the caller's permission first and must NOT file anything if they decline. The
  `ESCALATION` section of `SYSTEM_PROMPT` defines the two triggers (red-flag symptom,
  diagnosis request) and the rules (short summary, no private details, reference ID + honest
  next step, never on a routine call).
- Frontend dashboard: `frontend/app/escalations/page.tsx` (lists requests, urgency badges,
  status buttons), reachable from the header link. Base URL `NEXT_PUBLIC_ESCALATION_API_URL`
  (default `http://localhost:8701`).

### Call analytics (Day 8)
- `backend/src/analytics.py` — `CallRecordStore` (SQLite, WAL) records every call's outcome
  into `call_analytics.db` (repo root, gitignored). `build_call_record()` extracts anonymised
  signals from `session.history()` (turn counts, tool names, latency — never message text),
  and `classify_call()` decides success/failure using the Health Access definition: a call is
  **successful** when a human-help escalation was filed, facility guidance was delivered, the
  caller's health situation was captured with a real exchange, or a 30s+ two-way consultation
  happened. Everything else is **failed**, grouped by `failure_type` (`no_response`,
  `user_hangup`, `incomplete`, `tool_error`, `sip_*`).
- Privacy: caller identifiers are stored as an opaque SHA-256 hash (`privacy_id()`); no
  transcripts, names, phones, OTPs or medical details are ever written. That anonymised data
  is exactly what the public dashboard may show.
- `backend/src/analytics_api.py` — stdlib admin HTTP API. Default `127.0.0.1:8702`, override
  with `ANALYTICS_API_HOST` / `ANALYTICS_API_PORT`. Endpoints: `GET /analytics` (summary +
  daily + latency trend + recent calls), `GET /analytics/calls`, `GET /analytics/summary`,
  `GET /analytics/daily`.
- Recording hook: the inbound `entrypoint` in `agent.py` registers a shutdown callback that
  records the call when the job ends; the outbound SIP worker (`telephony/outbound/agent.py`)
  records dial failures separately (they never connect) and records connected calls from its
  own shutdown callback, marking voicemail / opt-out / completed-reminder outcomes.
- Frontend dashboard: `frontend/app/analytics/page.tsx` — total / successful / failed stat
  cards, success rate, today, per-channel breakdown, failure reasons, a CSS-only daily trend
  chart and a recent-calls table, with a live auto-refresh toggle. Base URL
  `NEXT_PUBLIC_ANALYTICS_API_URL` (default `http://localhost:8702`).

### Agent handoff (Day 9)
- `backend/src/agent.py` defines a second, focused agent: `ClinicAppointmentSpecialist`
  ("अपॉइंटमेंट सहायक", prompt `CLINIC_APPOINTMENT_PROMPT`) whose only job is planning
  clinic/hospital visits — appointments/OPD tokens, opening times, documents to bring,
  how to prepare. It inherits the caller-memory + facility tools from `Assistant` and
  adds `book_appointment` (records the visit plan in caller notes) and
  `transfer_back_to_main_agent`.
- Routing: the main `Assistant` has a `transfer_to_appointment_specialist` tool
  (decorated with `@function_tool`). It returns
  `(ClinicAppointmentSpecialist(chat_ctx=self.chat_ctx.copy(exclude_instructions=True)), message)`
  so the specialist sees the caller's prior turns (no re-explaining) and the caller
  hears a handoff line first. The specialist's `on_enter` introduces itself.
- The specialist deliberately overrides `create_escalation` and
  `transfer_to_appointment_specialist` with plain (non-`@function_tool`) methods so
  those tools are NOT offered to it. Keep that pattern when editing: tools are
  discovered with `inspect.getmembers`, so a subclass override without the decorator
  removes an inherited tool.
- The `HANDOFF` section of `SYSTEM_PROMPT` tells the main agent to hand off only for
  appointment-planning requests and to keep symptoms, facility lookup, memory and
  escalation itself. The `LIMITS` section of `CLINIC_APPOINTMENT_PROMPT` tells the
  specialist to hand back for symptoms/diagnosis/medicine questions.
- Tests: `backend/tests/test_handoff.py` — network-free unit tests for the handoff
  tool, specialist toolset and `book_appointment`, plus LLM-as-judge routing evals
  (normal question stays; appointment request hands off and the specialist continues;
  specialist hands back when the caller changes topic).

### Caller memory (Day 4)
- `backend/src/memory.py` — `CallerStore` (SQLite, WAL). `upsert` does a partial merge: `None` fields are left untouched, list fields (conditions/medications/allergies/notes) are deduped and appended.
- `backend/src/memory_api.py` — stdlib HTTP admin API. Default `127.0.0.1:8700`, override with `MEMORY_API_HOST` / `MEMORY_API_PORT`.
- Identity flow: `frontend/app/api/token/route.ts` mints a 1-year `caller_id` cookie and sets it as the LiveKit participant identity; the agent's `entrypoint` resolves it and greets returning callers.
- Tool helpers must tolerate a missing `ctx.userdata` (wrap in try/except, fall back to `MEMORY_STORE` / `"anonymous"`), because `RunContext.userdata` raises `ValueError` when unset.

### Running the backend
```bash
cd backend
uv sync
uv run python src/agent.py download-files   # first time only
uv run python src/agent.py dev              # development
uv run python src/agent.py console          # terminal-only testing
uv run python src/memory_api.py             # admin API (optional, for /admin page)
uv run python src/escalation_api.py         # escalation API (optional, for /escalations page)
uv run python src/analytics_api.py          # analytics API (optional, for /analytics page)
```

### Environment variables
Copy `backend/.env.example` to `backend/.env.local`. Required keys:
- `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`
- `MURF_API_KEY`
- `DEEPGRAM_API_KEY`
- `GOOGLE_API_KEY`

Optional (memory admin API): `MEMORY_API_HOST` (default `127.0.0.1`), `MEMORY_API_PORT` (default `8700`).
Optional (escalation admin API): `ESCALATION_API_HOST` (default `127.0.0.1`), `ESCALATION_API_PORT` (default `8701`).
Optional (analytics admin API): `ANALYTICS_API_HOST` (default `127.0.0.1`), `ANALYTICS_API_PORT` (default `8702`).

### Code style
Uses **ruff** for linting and formatting:
```bash
uv run ruff check .
uv run ruff format .
```
Config is in `pyproject.toml` — 88 char line length, double quotes, space indent.

### Testing
Tests are in `backend/tests/test_agent.py` (LLM-as-judge evals), `backend/tests/test_memory.py` (CallerStore), `backend/tests/test_tools.py` (tool methods with a fake RunContext), `backend/tests/test_facilities.py` (lookup logic; network is monkeypatched so tests never hit Overpass/Nominatim), `backend/tests/test_escalation.py` (Day 7 human-help store + sanitizer + tool + agent evals), `backend/tests/test_analytics.py` (Day 8 call classification, privacy and store tests — network-free, plus one agent-level eval), and `backend/tests/test_handoff.py` (Day 9 specialist handoff — network-free unit tests plus LLM-as-judge routing evals). They use LiveKit's testing framework with LLM-as-judge evaluation (not mocks). Run with:
```bash
uv run pytest
```
Requires `LIVEKIT_URL`, `LIVEKIT_API_KEY`, and `LIVEKIT_API_SECRET` to be set.

When modifying the system prompt or adding tools, write tests first. Use the existing tests as a pattern — they call `session.run(user_input=...)`, use `next_event(type="message")` (do not chain `.is_message()` — `next_event` already returns a `ChatMessageAssert`), and `.judge()` to evaluate responses. Eval LLM is `inference.LLM(model="openai/gpt-4.1-mini")`.

### Dependencies
Managed via `uv` and defined in `pyproject.toml`. Always use `uv sync` and `uv run` — never `pip install`.

## Frontend

### Tech stack
- **Next.js** (React, TypeScript)
- **pnpm** package manager
- **LiveKit Agents UI** (shadcn-based components)
- **Tailwind CSS**

### Key files
- `frontend/app-config.ts` — branding, feature flags, accent colors, visualizer config
- `frontend/app/page.tsx` — main page
- `frontend/app/api/token/route.ts` — LiveKit token endpoint (also mints the persistent `caller_id` cookie used as agent identity)
- `frontend/app/admin/page.tsx` — admin page listing remembered callers with Forget buttons (Day 4)
- `frontend/app/escalations/page.tsx` — human-help dashboard listing open requests with status buttons (Day 7)
- `frontend/app/analytics/page.tsx` — call analytics dashboard (Day 8)
- `frontend/components/app/` — app-level logic (welcome view, view controller, theme)
- `frontend/components/agents-ui/` — voice UI components (visualizers, controls, chat)

### Running the frontend
```bash
cd frontend
pnpm install
pnpm dev
```

### Environment variables
Copy `frontend/.env.example` to `frontend/.env.local`. Required:
- `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`
- `AGENT_NAME` (optional — set to `my-agent` for explicit dispatch)
- `NEXT_PUBLIC_MEMORY_API_URL` (optional — admin API base URL, default `http://localhost:8700`)
- `NEXT_PUBLIC_ESCALATION_API_URL` (optional — admin API base URL, default `http://localhost:8701`)
- `NEXT_PUBLIC_ANALYTICS_API_URL` (optional — admin API base URL, default `http://localhost:8702`)

### Linting
```bash
pnpm lint         # ESLint
pnpm format:check # Prettier
```

Note: `pnpm lint` still flags pre-existing prettier errors in stock files (`app/opengraph-image.tsx`, `components/agents-ui/*`). Only new/changed files must be clean — run `pnpm exec prettier --write` on them before finishing.

## Common tasks

### Change what the agent does
Edit `SYSTEM_PROMPT` in `backend/src/agent.py`. See `backend/README.md` for example prompts.

### Change the voice
Edit the `voice` argument in `murf.TTS(...)` in `backend/src/agent.py`. Current: `voice="hi-IN-anisha", style="Conversational"`. Browse voices at https://murf.ai/api/docs/voices-styles/voice-library.

### Add a tool to the agent
Add a method to the `Assistant` class in `backend/src/agent.py` with the `@function_tool` decorator. There's a commented example (weather lookup) in the file. Import `function_tool` and `RunContext` from `livekit.agents`. Follow the memory-tool pattern: pull the store and caller_id from `ctx.userdata` with a try/except fallback.

### Change the system prompt / pipeline
Edit `SYSTEM_PROMPT` in `backend/src/agent.py`. Current pipeline: Deepgram `nova-3` (multilingual), Gemini (`gemini-3.5-flash-lite`), Murf Anisha, Silero VAD, `MultilingualModel()` turn detection, `preemptive_generation=True`. Import `MultilingualModel` from `livekit.plugins.turn_detector.multilingual` (it is not exposed on `livekit.plugins.turn_detector` directly).

### Add a tool to the agent
Add a method to the `Assistant` class in `backend/src/agent.py` with the `@function_tool` decorator. There's a commented example (weather lookup) in the file. Import `function_tool` and `RunContext` from `livekit.agents`.

### Switch the LLM
Replace the `llm=google.LLM(...)` call in `agent.py`. For OpenAI: install `livekit-agents[openai]`, set `OPENAI_API_KEY`, import `openai` from `livekit.plugins`, and use `openai.LLM(...)`.

### Change frontend branding
Edit `frontend/app-config.ts` — company name, page title, logo paths, accent colors, button text, visualizer type.

## Documentation references

- Murf Falcon TTS: https://murf.ai/api/docs/text-to-speech/streaming
- Murf Voice Library: https://murf.ai/api/docs/voices-styles/voice-library
- LiveKit Agents SDK: https://docs.livekit.io/agents
- LiveKit Agents UI: https://livekit.io/ui
- Deepgram STT: https://developers.deepgram.com
