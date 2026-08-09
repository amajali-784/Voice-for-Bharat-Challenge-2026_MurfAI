# स्वास्थ्य सहायक (Swasthya Sahayak) — Voice Agent Starter, Powered by Murf Falcon

Built for **10 Days of AI Voice Agents — #VoiceForBharat Edition**, Day 4.

**Track:** Health Access

**Voice:** `hi-IN-anisha` — Murf Falcon, Hindi (multilingual: 13 Indian locales)

**Why this voice:** Anisha is a calm, patient, trustworthy Hindi voice that also speaks English and 12 other Indian languages, so the assistant can naturally switch register with every caller — ideal for a health-guidance line that serves a multilingual Bharat.

Forked from the original [Murf LiveKit Starter](https://github.com/murf-ai/murf-livekit-starter) and customized into a Hindi-speaking health-access assistant that helps people understand symptoms in plain language, points them to nearby care, always defers real diagnosis to a doctor, and **remembers callers between calls**.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT) [![Murf Falcon](https://img.shields.io/badge/TTS-Murf%20Falcon-6366F1)](https://murf.ai/api/docs/text-to-speech/streaming) [![LiveKit](https://img.shields.io/badge/Transport-LiveKit-002cf2)](https://docs.livekit.io) [![TypeScript](https://img.shields.io/badge/TypeScript-007ACC?logo=typescript&logoColor=white)](https://www.typescriptlang.org/) [![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white)](https://www.python.org/)

---

## What this agent does

- Listens and replies in the caller's own register — Hindi, English, or Hinglish — using simple, non-technical language.
- Helps users talk through symptoms conversationally — without ever diagnosing or prescribing.
- Points users toward nearby health centres and explains when a symptom warrants urgent care.
- Always defers to a real doctor or the **108** emergency line for anything serious.
- **Remembers returning callers** (name, village, conditions, medicines, allergies) via a SQLite-backed memory store, so a second call doesn't start from zero.
- Forgets everything on request — the caller can ask to be erased, and an admin page lists what's remembered.

---

## Why Murf Falcon

- **55ms model latency** — fastest production TTS
- **130ms time-to-first-audio** across 10+ global regions
- **$0.01/1000 characters** — up to 10x cheaper than alternatives
- **150+ voices** across 35+ languages, including 11 Indian languages
- **99.38% pronunciation accuracy**

---

## Architecture

```mermaid
flowchart LR
    A[🎙️ Caller speaks Hindi/Hinglish] -->|audio| B[Deepgram STT — nova-3, multilingual]
    B -->|text| C[Gemini LLM + memory tools]
    C <-->|lookup / save / forget| M[(SQLite caller memory)]
    C -->|response text| D[Murf Falcon TTS — hi-IN-anisha]
    D -->|audio| E[LiveKit]
    E -->|stream| F[🔊 Caller hears Hindi reply]
    M -->|GET /callers| G[Admin page /admin]

    style A fill:#444441,stroke:#888780,color:#fff
    style B fill:#185FA5,stroke:#85B7EB,color:#fff
    style C fill:#534AB7,stroke:#AFA9EC,color:#fff
    style D fill:#0F6E56,stroke:#5DCAA5,color:#fff
    style E fill:#D85A30,stroke:#F0997B,color:#fff
    style F fill:#444441,stroke:#888780,color:#fff
    style G fill:#444441,stroke:#888780,color:#fff
```

---

## Quickstart

### Prerequisites

- **Python** 3.10+
- **[uv](https://docs.astral.sh/uv/)** — fast Python package manager
  ```bash
  # macOS/Linux
  curl -LsSf https://astral.sh/uv/install.sh | sh
  # Windows (PowerShell)
  powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
  ```
- **Node.js** 18+
- **pnpm**
  ```bash
  npm install -g pnpm
  ```
- A [LiveKit](https://cloud.livekit.io/) project (free tier available)

### Step 1: Clone your fork

```bash
git clone https://github.com/YOUR-USERNAME/voice-for-bharat-challenge-2026.git
cd voice-for-bharat-challenge-2026
```

### Step 2: Set up environment variables

Create `.env.local` in both `backend/` and `frontend/` (copy from `.env.example` in each). You need:

| Variable                               | Where to get it                                        | Required |
| --------------------------------------- | -------------------------------------------------------- | -------- |
| `LIVEKIT_URL`                          | LiveKit Cloud dashboard — your project's real WS URL     | Yes      |
| `LIVEKIT_API_KEY`                      | LiveKit Cloud dashboard                                  | Yes      |
| `LIVEKIT_API_SECRET`                   | LiveKit Cloud dashboard                                  | Yes      |
| `MURF_API_KEY`                         | [murf.ai/api/dashboard](https://murf.ai/api/dashboard)   | Yes      |
| `DEEPGRAM_API_KEY`                     | [deepgram.com](https://deepgram.com)                     | Yes      |
| `GOOGLE_API_KEY` (or `OPENAI_API_KEY`) | Google AI Studio (Gemini is the default LLM here)         | Yes      |
| `MEMORY_API_PORT` / `MEMORY_API_HOST`  | Optional — admin API port/host (default `8700`, `127.0.0.1`) | No |
| `NEXT_PUBLIC_MEMORY_API_URL`           | Frontend only — admin API base URL (default `http://localhost:8700`) | No |

> ⚠️ `LIVEKIT_URL` must be your **actual** project URL (e.g. `wss://my-app-ab12cd34.livekit.cloud`), not the `your-project.livekit.cloud` placeholder from `.env.example`.

### Step 3: Install backend dependencies

```bash
cd backend
uv sync
uv run python src/agent.py download-files
```

### Step 4: Install frontend dependencies

```bash
cd frontend
pnpm install
```

### Step 5: Run it

**Option A — All-in-one (from repo root):**

```bash
# macOS/Linux
chmod +x start_app.sh
./start_app.sh

# Windows (PowerShell)
.\start_app.ps1
```

**Option B — Separate terminals:**

```bash
# Terminal 1 — LiveKit Server
livekit-server --dev

# Terminal 2 — Backend agent
cd backend && uv run python src/agent.py dev

# Terminal 3 — Memory admin API (optional, powers the /admin page)
cd backend && uv run python src/memory_api.py

# Terminal 4 — Frontend
cd frontend && pnpm dev
```

Then open **http://localhost:3000**. Click **बातचीत शुरू करें** (Start talking), allow microphone access, and speak in Hindi — the agent replies with Murf Falcon TTS. Visit **http://localhost:3000/admin** to see which callers the agent remembers, and use the **Forget** button to erase a caller's record.

---

## Day 4 — Persistent caller memory

The agent remembers callers across calls so a returning patient doesn't repeat their story. On the first visit the frontend mints a `caller_id` cookie (1 year) and passes it as the LiveKit participant identity; on every call the backend resolves that identity and greets returning callers by name.

- **`backend/src/memory.py`** — a small SQLite `CallerStore` (WAL mode) storing caller name, language, gender, DOB, location, phone, conditions, medications, allergies, and free-form notes. It supports `upsert` (partial merge, so saving one field never wipes others), `get`, `delete`, `list`, and `count`. The DB file lives at the repo root as `caller_memory.db` (gitignored).
- **Agent tools** (`backend/src/agent.py`) — the LLM gets four `@function_tool`s:
  - `lookup_caller` — fetch what's known before answering;
  - `save_caller_info` — record facts a caller shares;
  - `add_note` — append a free-form note;
  - `forget_caller` — erase the caller on request ("भूल जाइए / forget me").
- **Admin API** (`backend/src/memory_api.py`) — a stdlib HTTP server (`GET /callers`, `DELETE /callers/<id>`) with CORS, default `127.0.0.1:8700`.
- **Admin page** (`frontend/app/admin/page.tsx`) — lists every remembered caller with their details and a **Forget** button. Read-only unless you also run the memory API.

---

## Configuration in this fork

### Murf voice

Set in `backend/src/agent.py`, inside the `tts=murf.TTS(...)` call:

```python
tts=murf.TTS(
    voice="hi-IN-anisha",
    style="Conversational",
    tokenizer=SentenceTokenizer(min_sentence_len=2),
    text_pacing=True,
)
```

Anisha speaks Hindi plus English and 12 other Indian languages, so the same voice can answer in the caller's own register. Browse all voices in the [Murf Voice Library](https://murf.ai/api/docs/voices-styles/voice-library).

### STT provider

`AgentSession(stt=deepgram.STT(model="nova-3", language="multi"))` — `nova-3` in multilingual mode so Hindi, Hinglish, and English callers are all understood.

### LLM

`llm=google.LLM(model="gemini-3.5-flash-lite")` — `GOOGLE_API_KEY` required.

### Turn detection

`turn_detection=MultilingualModel()` (from `livekit.plugins.turn_detector.multilingual`) plus `preemptive_generation=True`, so the agent replies over natural mid-speech pauses in any language.

### System prompt

Lives in `SYSTEM_PROMPT` near the top of `backend/src/agent.py`. It instructs the agent to stay in simple Hindi (or the caller's language), never diagnose or prescribe, escalate to 108 / a nearby hospital for anything serious, and to use the memory tools to remember returning callers.

---

## Latency note (Advanced/optional task)

Log your own end-of-speech → first-audio-out latency here once you've run a session, e.g.:

```
Day 1 latency (end-of-user-speech → first audio out): ___ ms
```

---

## Project Structure

```
voice-for-bharat-challenge-2026/
├── backend/                 # Python voice agent (LiveKit Agents + Murf Falcon)
│   ├── src/
│   │   ├── agent.py         # Health Access system prompt + memory tools + Anisha pipeline
│   │   ├── memory.py        # SQLite CallerStore — persistent caller memory
│   │   └── memory_api.py    # Admin API (GET/DELETE callers) on :8700
│   ├── tests/               # Pytest: memory store, tools, and agent evals
│   ├── .env.example
│   ├── pyproject.toml
│   └── railway.toml
├── frontend/                # Next.js UI, rebranded as "Swasthya Sahayak"
│   ├── app/
│   │   ├── page.tsx
│   │   ├── admin/page.tsx   # Day 4 — list/forget remembered callers
│   │   └── api/token/       # Mint persistent caller_id cookie (identity)
│   ├── components/
│   ├── app-config.ts        # Branding/title updated for Health Access
│   ├── .env.example
│   └── package.json
├── start_app.sh
├── start_app.ps1
├── caller_memory.db         # SQLite DB, created at runtime (gitignored)
├── README.md                # This file
```

---

## Links

- [Murf API Docs](https://murf.ai/api/docs)
- [Murf Voice Library](https://murf.ai/api/docs/voices-styles/voice-library)
- [LiveKit Docs](https://docs.livekit.io)
- [Deepgram Docs](https://developers.deepgram.com)
- [10 Days of AI Voice Agents — #VoiceForBharat Edition](https://github.com/murf-ai/voice-for-bharat-challenge-2026)

---

## License

MIT