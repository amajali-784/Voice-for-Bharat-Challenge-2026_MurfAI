# स्वास्थ्य सहायक (Swasthya Sahayak) — Voice Agent Starter, Powered by Murf Falcon

Built for **10 Days of AI Voice Agents — #VoiceForBharat Edition**, Day 1.

**Track:** Health Access

**Voice:** `hi-IN-pooja` — Murf Falcon, Hindi

**Why this voice:** a health-guidance line needs to sound calm, patient, and trustworthy rather than upbeat or transactional — Pooja's warmer register fits someone anxious about symptoms better than a brisk customer-support tone would.

<img width="2880" height="1534" alt="Screenshot 2026-08-08 213800" src="https://github.com/user-attachments/assets/5739e96d-72e3-484a-9c97-f203245677f2" />


Forked from the original [Murf LiveKit Starter](https://github.com/murf-ai/murf-livekit-starter) and customized into a Hindi-speaking health-access assistant that helps people understand symptoms in plain language, points them to nearby care, and always defers real diagnosis to a doctor.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT) [![Murf Falcon](https://img.shields.io/badge/TTS-Murf%20Falcon-6366F1)](https://murf.ai/api/docs/text-to-speech/streaming) [![LiveKit](https://img.shields.io/badge/Transport-LiveKit-002cf2)](https://docs.livekit.io) [![TypeScript](https://img.shields.io/badge/TypeScript-007ACC?logo=typescript&logoColor=white)](https://www.typescriptlang.org/) [![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white)](https://www.python.org/)

---

## What this agent does

- Listens and replies entirely in **Hindi**, using simple, non-technical language.
- Helps users talk through symptoms conversationally — without ever diagnosing or prescribing.
- Points users toward nearby health centres and explains when a symptom warrants urgent care.
- Always defers to a real doctor or the **108** emergency line for anything serious.
- Runs on the same STT → LLM → TTS pipeline as the original starter, just repointed to a Hindi voice and a Health Access system prompt.

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
    A[🎙️ User speaks Hindi] -->|audio| B[Deepgram STT — hi]
    B -->|text| C[Gemini LLM]
    C -->|response text| D[Murf Falcon TTS — hi-IN-pooja]
    D -->|audio| E[LiveKit]
    E -->|stream| F[🔊 User hears Hindi reply]

    style A fill:#444441,stroke:#888780,color:#fff
    style B fill:#185FA5,stroke:#85B7EB,color:#fff
    style C fill:#534AB7,stroke:#AFA9EC,color:#fff
    style D fill:#0F6E56,stroke:#5DCAA5,color:#fff
    style E fill:#D85A30,stroke:#F0997B,color:#fff
    style F fill:#444441,stroke:#888780,color:#fff
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

# Terminal 3 — Frontend
cd frontend && pnpm dev
```

Then open **http://localhost:3000**. Click **बातचीत शुरू करें** (Start talking), allow microphone access, and speak in Hindi — the agent replies with Murf Falcon TTS.

---

## Configuration in this fork

### Murf voice

Set in `backend/src/agent.py`, inside the `tts=murf.TTS(...)` call:

```python
tts=murf.TTS(voice="hi-IN-pooja")
```

Other Hindi options from the recommended list: `hi-IN-samar` (male), `hi-IN-anisha` (female). Browse all voices in the [Murf Voice Library](https://murf.ai/api/docs/voices-styles/voice-library).

### STT provider

`AgentSession(stt=deepgram.STT(model="nova-2", language="hi"))` — `nova-2` was chosen over `nova-3` for broader Hindi coverage.

### LLM

`llm=google.LLM(model="gemini-2.5-flash")` — `GOOGLE_API_KEY` required.

### System prompt

Lives in `SYSTEM_PROMPT` near the top of `backend/src/agent.py`. It instructs the agent to stay in simple Hindi, never diagnose or prescribe, and escalate to 108 / a nearby hospital for anything serious.

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
│   │   └── agent.py         # Health Access system prompt + hi-IN-pooja pipeline
│   ├── tests/
│   ├── .env.example
│   ├── pyproject.toml
│   └── railway.toml
├── frontend/                # Next.js UI, rebranded as "Swasthya Sahayak"
│   ├── app/
│   │   ├── page.tsx
│   │   └── api/token/
│   ├── components/
│   ├── app-config.ts        # Branding/title updated for Health Access
│   ├── .env.example
│   └── package.json
├── start_app.sh
├── start_app.ps1
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
