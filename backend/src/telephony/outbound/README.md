# Outbound calls — Swasthya Sahayak makes reminder calls (Day 6)

This is the **Health Access** outbound use case: the agent dials out to remind
people about their **medication or vaccination** and gently follows up on how
they are doing. It is the same `hi-IN-anisha` (Murf Falcon) voice, the same
Deepgram → Gemini → Murf pipeline, and it reuses the Day 4 caller memory and
Day 5 facility lookup.

The person did not ask for this call and does not know who we are, so **every
call opens with who is calling, why, and how to make it stop** — the opening is
spoken deterministically (not generated) so it can never be skipped. If the
person says "कॉल बंद करो" / "stop calling", the `opt_out` tool records that in
memory and the agent never dials them again.

```
dial.py --to +919876543210
  → LiveKit: create room + dispatch (phone + reminder metadata)
    → health-reminder-agent worker (this folder)
      → session.start() (models warm up while it rings)
        → create_sip_participant (outbound trunk → Twilio → PSTN)
          → phone rings → person answers
            → agent speaks the opening (who / why / opt-out)
              → reminder conversation → opt_out or end_call
```

---

## One-time setup

### 1. Twilio — Elastic SIP Trunk

1. [console.twilio.com](https://console.twilio.com) → **Elastic SIP Trunking** → **Trunks** → **Create**.
2. Give it a name (e.g. `health-reminder`) and note the **Termination URI**
   shown at the top (e.g. `mytrunk.pstn.twilio.com`).
3. Create a **Credential List** (username + password) under that trunk and
   attach it to the trunk. Save the username/password.
4. Under the trunk's **Origination**, add one origination URI pointing at your
   LiveKit SIP URI (`xxx.sip.livekit.cloud`) — only needed if you ever want
   *inbound* calls; outbound calls do not need it.
5. Make sure the **number you will call from** is a verified Twilio number
   (Twilio Console → Phone Numbers → verified caller IDs). This number is the
   caller ID on your outbound calls.

### 2. LiveKit — outbound trunk

Create an outbound trunk that routes through the Twilio Elastic SIP Trunk. From
the LiveKit CLI, write `outbound-trunk.json` with the trunk's **Termination
URI** and your Twilio number (the caller ID):

```json
{
  "trunk": {
    "name": "health-reminder-trunk",
    "address": "<your-trunk>.pstn.twilio.com",
    "numbers": ["+1xxxxxxxxxx"]
  }
}
```

Then create it with the SIP credential-list username/password from step 1:

```bash
lk sip outbound create outbound-trunk.json \
  --auth-user <sip-credential-username> \
  --auth-pass <sip-credential-password>
```

> `address` is the Elastic SIP trunk's Termination URI from step 1; `numbers`
> holds your Twilio phone number (the caller ID).

The command prints a trunk ID like `ST_xxxx`. Save it as
`LIVEKIT_SIP_OUTBOUND_TRUNK_ID` in `backend/.env.local`. Verify with
`lk sip outbound list`.

You can also create the trunk from the **LiveKit Cloud console** → **Telephony →
SIP Trunks → Create outbound trunk** with the same values.

### 3. Environment variables

Copy `backend/.env.example` to `backend/.env.local` and set at minimum:

| Variable                          | Value                                                        |
| --------------------------------- | ------------------------------------------------------------ |
| `LIVEKIT_SIP_OUTBOUND_TRUNK_ID`   | the `ST_xxxx` trunk id from step 2                          |
| `TWILIO_PHONE_NUMBER`             | your Twilio number, the caller ID (optional if on the trunk) |
| `SIP_RINGING_TIMEOUT`             | seconds to let it ring (default `30`)                        |

`TWILIO_ACCOUNT_SID` / `TWILIO_AUTH_TOKEN` are **not required** to make calls —
only if you script the trunk setup or add post-call messages.

---

## Run it

Terminal 1 — start the outbound worker:

```bash
cd backend
uv run python src/telephony/outbound/agent.py dev
```

Terminal 2 — place a call (E.164 number):

```bash
uv run python src/telephony/outbound/dial.py --to +919876543210
```

With reminder context (the opening will use it):

```bash
uv run python src/telephony/outbound/dial.py --to +919876543210 \
  --name "Sunita Devi" \
  --reminder medication --medication मधुमेह \
  --location Varanasi
```

`--reminder` is one of `medication` | `vaccination` | `followup`.

Your phone rings, the agent opens with who/why/opt-out, and the conversation
follows the reminder script.

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

| Outcome          | When                                               | Behaviour                                        |
| ---------------- | ------------------------------------------------- | ------------------------------------------------ |
| `answered`       | `create_sip_participant` returns                  | run the conversation                             |
| `no_answer`      | SIP 408 / 480 / 487                               | log + **retry once after 10 min**                |
| `busy`           | SIP 486 / 600                                     | log + **retry once after 10 min**                |
| `declined`       | SIP 603                                           | log, **no retry** (person actively refused)      |
| `trunk_failure`  | SIP 5xx                                           | log + retry once                                 |
| `voicemail`      | agent hears a greeting/beep → `detected_voicemail`| hang up, **no retry**                            |
| `opted_out`      | person asks to stop → `opt_out`                   | mark in memory, hang up, **never dial again**    |
| `hung_up_immediate` | answered but caller hangs up right away        | log                                              |

Every attempt is appended as a JSON line to `backend/logs/outcomes.jsonl`
(with `retry` and `attempt` fields), and the retry decision is computed in
`outcome.py` (`should_retry`).

---

## Files

| File       | Purpose                                                    |
| ---------- | ---------------------------------------------------------- |
| `agent.py` | Outbound worker: dials, opens the call, runs the reminder, records outcomes |
| `dial.py`  | CLI that dispatches the worker with a phone number + reminder metadata |
| `outcome.py` | SIP status → outcome mapping, retry rules, JSONL call log |
| `../../tests/test_outbound.py` | Network-free tests for the above |
