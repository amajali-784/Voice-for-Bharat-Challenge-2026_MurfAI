"""Twilio bridge — trial-account outbound calls via the LiveKit Twilio Connector.

Day 6's documented flow needs Twilio *Elastic SIP Trunking*, which is only
available on a paid account.  This bridge keeps the free trial: it drives the
LiveKit **Twilio Connector** (``ConnectTwilioCall`` -> WebSocket media stream)
together with Twilio **Programmable Voice**, which trial accounts can use to
call their verified numbers.

Flow
----
dial.py --to +919876543210
  -> POST /place               (this server, on 127.0.0.1:8899 by default)
       -> LiveKitAPI.connector.connect_twilio_call(...)   # creates room + dispatches worker
       -> store token -> connect_url
       -> Twilio REST Calls.json { To, From, Url = PUBLIC/twiml?token=.. }
  -> Twilio rings the phone
  -> when answered, Twilio opens the connect_url WebSocket -> audio is bridged
     into the LiveKit room -> the health-reminder worker runs the conversation

The TwiML webhook must be reachable over public HTTPS.  Start a tunnel (e.g.):

    cloudflared tunnel --url http://127.0.0.1:8899

and set ``TWILIO_PUBLIC_BASE_URL`` to the printed ``https://...trycloudflare.com``
URL (or drop it in ``backend/.tunnel_url``; the bridge reads that file too).

Endpoints
---------
- POST /place  JSON body: to, name, reminder, medication, vaccine, location, room
- GET|POST /twiml?token=...   Twilio TwiML webhook (embeds the connect_url)
- POST /status                Twilio StatusCallback (logs outcomes)
- GET /health
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import httpx
from dotenv import load_dotenv
from livekit import api

from memory import DEFAULT_DB_PATH, CallerStore
from telephony.outbound.agent import has_opted_out
from telephony.outbound.outcome import (
    build_outcome,
    log_outcome,
    should_retry,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("twilio-bridge")

_ENV_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".env.local"
)
load_dotenv(_ENV_FILE)

# Must match the worker's agent_name in telephony/outbound/agent.py.
AGENT_NAME = "health-reminder-agent"

ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
FROM_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")

HOST = os.getenv("TWILIO_BRIDGE_HOST", "127.0.0.1")
PORT = int(os.getenv("TWILIO_BRIDGE_PORT", "8899"))
RINGING_TIMEOUT = int(os.getenv("SIP_RINGING_TIMEOUT", "30"))

_TUNNEL_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".tunnel_url"
)

# token -> connect_url, written by /place and read by /twiml.
_PENDING: dict[str, str] = {}
_PENDING_LOCK = threading.Lock()

# Twilio CallStatus -> our outcome label (see outcome.py).
_STATUS_TO_OUTCOME = {
    "completed": "completed",
    "busy": "busy",
    "no-answer": "no_answer",
    "canceled": "declined",
    "failed": "trunk_failure",
}
_TERMINAL_STATUSES = set(_STATUS_TO_OUTCOME)


def public_base_url() -> str:
    """The public base URL of this server, for Twilio to reach /twiml."""
    env = os.getenv("TWILIO_PUBLIC_BASE_URL")
    if env:
        return env.rstrip("/")
    try:
        with open(_TUNNEL_FILE, encoding="utf-8") as f:
            url = f.read().strip()
        if url:
            return url.rstrip("/")
    except OSError:
        pass
    return f"http://{HOST}:{PORT}"


def build_metadata(payload: dict) -> dict:
    """Dispatch metadata for the worker (same keys the SIP path uses)."""
    meta: dict = {
        "phone_number": payload["to"],
        "connector": True,
        "attempt": int(payload.get("attempt", 1)),
    }
    for key in ("name", "reminder", "medication", "vaccine", "location"):
        if payload.get(key):
            meta[key] = payload[key]
    return meta


def _log_status_outcome(status: str, form: dict) -> None:
    """Map a Twilio status callback to an outcome record in outcomes.jsonl."""
    outcome = _STATUS_TO_OUTCOME.get(status)
    if outcome is None:
        return
    entry = build_outcome(
        phone_number=form.get("To") or form.get("to") or "unknown",
        room_name=form.get("room_name") or "",
        name=form.get("name"),
        outcome=outcome,
        detail=f"twilio_status_callback={status}",
        call_id=form.get("CallSid") or form.get("call_sid"),
    )
    path = log_outcome(entry)
    retry, reason = should_retry(outcome, entry["attempt"])
    logger.info(
        "twilio status %s -> %s (retry=%s: %s) logged to %s",
        status,
        outcome,
        retry,
        reason,
        path,
    )


async def place_call(payload: dict) -> dict:
    """Connect the LiveKit Twilio Connector and dial the number via Twilio."""
    to = (payload.get("to") or "").strip()
    if not to:
        return {"status": 400, "body": {"error": "missing 'to' (E.164 number)"}}

    store = CallerStore(DEFAULT_DB_PATH)
    if has_opted_out(store.get(to)):
        entry = build_outcome(
            phone_number=to,
            room_name=payload.get("room") or "",
            name=payload.get("name"),
            outcome="opted_out",
            detail="skipped before dialing — prior opt-out on record",
            attempt=int(payload.get("attempt", 1)),
        )
        log_outcome(entry)
        return {
            "status": 409,
            "body": {"error": "caller has opted out — will not dial"},
        }

    if not ACCOUNT_SID or not AUTH_TOKEN or not FROM_NUMBER:
        return {
            "status": 500,
            "body": {
                "error": (
                    "TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN / "
                    "TWILIO_PHONE_NUMBER must be set in backend/.env.local"
                )
            },
        }

    room_name = payload.get("room") or f"outbound-{uuid.uuid4().hex[:8]}"
    metadata = json.dumps(build_metadata(payload), ensure_ascii=False)

    lk = api.LiveKitAPI()
    try:
        res = await lk.connector.connect_twilio_call(
            api.ConnectTwilioCallRequest(
                twilio_call_direction=(
                    api.ConnectTwilioCallRequest.TWILIO_CALL_DIRECTION_OUTBOUND
                ),
                room_name=room_name,
                participant_identity="phone-user",
                participant_name=payload.get("name") or "Phone user",
                agents=[
                    api.RoomAgentDispatch(agent_name=AGENT_NAME, metadata=metadata)
                ],
            )
        )
    finally:
        await lk.aclose()

    connect_url = res.connect_url
    token = uuid.uuid4().hex
    with _PENDING_LOCK:
        _PENDING[token] = connect_url

    public = public_base_url()
    twiml_url = f"{public}/twiml?token={token}"
    data = {
        "To": to,
        "From": FROM_NUMBER,
        "Url": twiml_url,
        "StatusCallback": f"{public}/status?token={token}",
        "StatusCallbackEvent": "initiated ringing answered completed busy no-answer canceled failed",
        "Timeout": str(RINGING_TIMEOUT),
    }

    async with httpx.AsyncClient() as client:
        r = await client.post(
            f"https://api.twilio.com/2010-04-01/Accounts/{ACCOUNT_SID}/Calls.json",
            data=data,
            auth=(ACCOUNT_SID, AUTH_TOKEN),
            timeout=30,
        )

    if r.status_code >= 400:
        logger.error("twilio create call failed (%s): %s", r.status_code, r.text)
        entry = build_outcome(
            phone_number=to,
            room_name=room_name,
            name=payload.get("name"),
            outcome="trunk_failure",
            detail=f"twilio_create_call_http={r.status_code}",
            attempt=int(payload.get("attempt", 1)),
        )
        log_outcome(entry)
        return {
            "status": r.status_code,
            "body": {"error": r.text, "room_name": room_name},
        }

    call = r.json()
    logger.info(
        "placed call to %s (call_sid=%s room=%s) twiml=%s",
        to,
        call.get("sid"),
        room_name,
        twiml_url,
    )
    return {
        "status": 200,
        "body": {
            "call_sid": call.get("sid"),
            "room_name": room_name,
            "twiml_url": twiml_url,
            "message": f"Ringing {to} — watch the worker terminal.",
        },
    }


def _run_coro(coro) -> tuple[int, dict]:
    """Run an async coroutine on the background loop and return (status, body)."""
    fut = asyncio.run_coroutine_threadsafe(coro, _LOOP)
    result = fut.result(timeout=60)
    return result["status"], result["body"]


class _Handler(BaseHTTPRequestHandler):
    server_version = "TwilioBridge/1.0"

    def _read_body(self) -> bytes:
        length = int(self.headers.get("Content-Length", 0) or 0)
        return self.rfile.read(length) if length else b""

    def _send_json(self, status: int, body: dict) -> None:
        payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _send_text(self, status: int, content: str, content_type: str) -> None:
        payload = content.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _query(self) -> dict:
        return parse_qs(urlparse(self.path).query)

    def _twiml(self) -> None:
        token = (self._query().get("token") or [""])[0]
        with _PENDING_LOCK:
            connect_url = _PENDING.get(token)
        if not connect_url:
            logger.warning("twiml webhook with unknown token %r", token)
            self._send_json(404, {"error": "unknown token"})
            return
        twiml = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            "<Response>\n"
            "  <Connect>\n"
            f'    <Stream url="{connect_url}" />\n'
            "  </Connect>\n"
            "</Response>\n"
        )
        logger.info("served TwiML for token %s", token)
        self._send_text(200, twiml, "text/xml")

    def _status(self) -> None:
        body = self._read_body().decode("utf-8", "replace")
        form = dict(parse_qs(body))
        form = {k: v[0] for k, v in form.items()}
        call_status = form.get("CallStatus")
        with _PENDING_LOCK:
            _PENDING.pop(form.get("token", ""), None)
        if call_status:
            _log_status_outcome(call_status, form)
        self._send_text(200, "", "text/plain")

    def _place(self) -> None:
        raw = self._read_body().decode("utf-8", "replace")
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            self._send_json(400, {"error": "invalid JSON body"})
            return
        status, body = _run_coro(place_call(payload))
        self._send_json(status, body)

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/health":
            self._send_json(200, {"status": "ok"})
        elif path == "/twiml":
            self._twiml()
        else:
            self._send_json(404, {"error": "not found"})

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path == "/place":
            self._place()
        elif path == "/twiml":
            self._twiml()
        elif path == "/status":
            self._status()
        else:
            self._send_json(404, {"error": "not found"})

    def log_message(self, fmt: str, *args) -> None:
        logger.info("%s - %s", self.address_string(), fmt % args)


_LOOP = asyncio.new_event_loop()
_LOOP_THREAD = threading.Thread(target=_LOOP.run_forever, name="bridge-loop", daemon=True)


def main() -> None:
    _LOOP_THREAD.start()
    server = ThreadingHTTPServer((HOST, PORT), _Handler)
    logger.info(
        "Twilio bridge listening on http://%s:%d (public base: %s)",
        HOST,
        PORT,
        public_base_url(),
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
