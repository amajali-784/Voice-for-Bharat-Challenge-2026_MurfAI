# Outbound calls — Swasthya Sahayak makes reminder calls (Day 6)

This is the **Health Access** outbound use case: the agent dials out to remind
people about their **medication or vaccination** and gently follows up on how
they are doing. It is the same `hi-IN-anisha` (Murf Falcon) voice, the same
Deepgram → Gemini → Murf pipeline, and it reuses the Day 4 caller memory and
Day 5 facility lookup.

Calls go out over **Linphone** — a free SIP softphone that registers to
`sip.linphone.org` over TLS, so you do **not** need Twilio, a phone number, or
any paid telephony. You install the Linphone app, log in with a free account,
and the agent's outbound call rings your app like a normal phone call.

The person did not ask for this call and does not know who we are, so **every
call opens with who is calling, why, and how to make it stop** — the opening is
spoken deterministically (not generated) so it can never be skipped. If the
person says "कॉल बंद करो" / "stop calling", the `opt_out` tool records that in
memory and the agent never dials them again.

```
dial.py --to sunita
  → LiveKit: create room + dispatch (sip:sunita@sip.linphone.org + reminder metadata)
    → health-reminder-agent worker (this folder)
      → session.start() (models warm up while it rings)
        → create_sip_participant (outbound trunk → sip.linphone.org, TLS)
          → Linphone app rings → you answer
            → agent speaks the opening (who / why / opt-out)
              → reminder conversation → opt_out or end_call
```

---

## One-time setup

### 1. Linphone account + app

1. Create a free account at
   [subscribe.linphone.org/register/email](https://subscribe.linphone.org/register/email).
   After registering you get a **SIP address** like
   `sip:<your-username>@sip.linphone.org`. Note it down.
2. Install the **Linphone** app on your phone (iOS / Android / desktop) from
   [linphone.org](https://www.linphone.org/en/) and log in with those
   credentials. Allow microphone access.
3. Turn **Media encryption mandatory OFF**:
   Settings → Calls → Advanced calls settings → toggle it off. Without this the
   call fails at the SRTP negotiation.

### 2. LiveKit — outbound trunk

In LiveKit Cloud → **Telephony → SIP Trunks → Create outbound trunk**, enter:

```json
{
  "name": "linphone-trunk",
  "address": "sip.linphone.org",
  "transport": "SIP_TRANSPORT_TLS",
  "numbers": ["*"]
}
```

`address` is the Linphone SIP server and `transport` must be
`SIP_TRANSPORT_TLS`. The editor only accepts **E.164 phone numbers** in
`numbers`, so use the wildcard `["*"]` ("calls from any number") and set the
actual caller ID per call with `SIP_FROM_NUMBER` (step 3). LiveKit documents
this: when `numbers` is `*` or empty, you pick the from-number on each
`CreateSIPParticipant` call via `sip_number`.

LiveKit Cloud shows a **TRUNK ID** (e.g. `ST_xxxx`) when the trunk is created.
Save it as `LIVEKIT_SIP_OUTBOUND_TRUNK_ID` in `backend/.env.local`.

> If you prefer the CLI, the same trunk can be created with
> `lk sip outbound create --name linphone-trunk --address sip.linphone.org
> --number "*" --transport tls` and listed with
> `lk sip outbound list`.

### 3. Environment variables

Copy `backend/.env.example` to `backend/.env.local` and set at minimum:

| Variable                          | Value                                                        |
| --------------------------------- | ------------------------------------------------------------ |
| `LIVEKIT_SIP_OUTBOUND_TRUNK_ID`   | the `ST_xxxx` trunk id from step 2                          |
| `SIP_FROM_NUMBER`                 | `<your-linphone-username>` — the caller ID your app sees. Bare username only (no `@domain`, no `sip:` scheme): LiveKit validates the From header like the dial target and appends the trunk's domain |

Optional: `SIP_RINGING_TIMEOUT` (seconds to ring, default `30`).

No Twilio, no SIP credentials, no tunnel — the Linphone path needs nothing else.

---

## Run it

Terminal 1 — start the outbound worker:

```bash
cd backend
uv run python src/telephony/outbound/agent.py dev
```

Terminal 2 — place a call to your Linphone account (username is enough):

```bash
uv run python src/telephony/outbound/dial.py --to sunita
```

`--to` also accepts a full SIP address (`sip:sunita@sip.linphone.org`) or an
E.164 number (`+919876543210`) if your trunk can reach it. Either way the trunk
dials the SIP **user** (`sunita`) — LiveKit's `sip_call_to` rejects full URIs
and takes the phone number or user part only.

With reminder context (the opening will use it):

```bash
uv run python src/telephony/outbound/dial.py --to sunita \
  --name "Sunita Devi" \
  --reminder medication --medication मधुमेह \
  --location Varanasi
```

`--reminder` is one of `medication` | `vaccination` | `followup`.

Your Linphone app rings, the agent opens with who/why/opt-out, and the
conversation follows the reminder script.

---

## What the opening sounds like

> "नमस्ते Sunita Devi जी, मैं स्वास्थ्य सहायक बोल रहा हूँ। हम आपकी मधुमेह दवा की
> याद दिलाने के लिए कॉल कर रहे हैं। अगर आपको ये कॉल नहीं चाहिए, तो बस 'कॉल बंद
> करो' कह दीजिए — हम फिर कभी कॉल नहीं करेंगे।"

Three things, up front: **who** (स्वास्थ्य सहायक), **why** (दवा/टीका याद
दिलाना), **how to stop** (कॉल बंद करो → never called again).

---

## Outcome handling (Advanced)

Inbound never sees these; outbound hits them daily:

| Outcome            | When                                               | Behaviour                                        |
| ------------------ | ------------------------------------------------- | ------------------------------------------------ |
| `answered`         | `create_sip_participant` returns                  | run the conversation                             |
| `no_answer`        | SIP 408 / 480 / 487                               | log + **retry once after 10 min**                |
| `busy`             | SIP 486 / 600                                     | log + **retry once after 10 min**                |
| `declined`         | SIP 603                                           | log, **no retry** (person actively refused)      |
| `trunk_failure`    | SIP 5xx                                           | log + retry once                                 |
| `voicemail`        | agent hears a greeting/beep → `detected_voicemail`| hang up, **no retry**                            |
| `opted_out`        | person asks to stop → `opt_out`                   | mark in memory, hang up, **never dial again**    |
| `hung_up_immediate`| answered but caller hangs up right away           | log                                              |

Every attempt is appended as a JSON line to `backend/logs/outcomes.jsonl`
(with `retry` and `attempt` fields), and the retry decision is computed in
`outcome.py` (`should_retry`).

---

## Files

| File       | Purpose                                                    |
| ---------- | ---------------------------------------------------------- |
| `agent.py` | Outbound worker: dials, opens the call, runs the reminder, records outcomes |
| `dial.py`  | CLI that creates a room + dispatches the worker with a SIP address + reminder metadata |
| `outcome.py` | SIP status → outcome mapping, retry rules, JSONL call log |
| `../../tests/test_outbound.py` | Network-free tests for the above |
