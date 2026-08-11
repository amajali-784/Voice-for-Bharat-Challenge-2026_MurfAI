"""Trigger an outbound health-reminder call.

The outbound agent doesn't call anyone on its own — it waits to be dispatched
into a room with a phone number in the job metadata. This script sends the
dispatch request to the Twilio bridge (twilio_bridge.py), which uses the
LiveKit Twilio Connector + Twilio Programmable Voice so the call works on a
free trial account.

Make sure the worker and the bridge are running first (two terminals):

    uv run python src/telephony/outbound/agent.py dev
    uv run python src/telephony/outbound/twilio_bridge.py

Then place a call (E.164 number, e.g. +919876543210):

    uv run python src/telephony/outbound/dial.py --to +919876543210

Optional caller/reminder context (the agent opens with these):

    uv run python src/telephony/outbound/dial.py --to +919876543210 \
        --name "Sunita Devi" --reminder medication --medication मधुमेह \
        --location Varanasi

This is the scriptable equivalent of:

    curl -X POST http://127.0.0.1:8899/place \
        -H "Content-Type: application/json" \
        -d '{"to": "+919876543210"}'
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import uuid

import httpx
from dotenv import load_dotenv

load_dotenv(".env.local")

# The Twilio bridge (src/telephony/outbound/twilio_bridge.py). Override with
# TWILIO_BRIDGE_URL if the bridge runs elsewhere.
BRIDGE_URL = os.getenv("TWILIO_BRIDGE_URL", "http://127.0.0.1:8899")

# E.164: a leading + and 7-15 digits, e.g. +919876543210.
E164 = re.compile(r"^\+[1-9]\d{6,14}$")


def build_metadata(args: argparse.Namespace) -> str:
    """Assemble the dispatch metadata (the reminder context the agent reads)."""
    if not E164.match(args.to):
        sys.exit(
            f"'{args.to}' is not a valid E.164 number. "
            "Include the country code and a leading +, e.g. +919876543210."
        )
    meta: dict = {"phone_number": args.to}
    if args.name:
        meta["name"] = args.name
    if args.reminder:
        meta["reminder"] = args.reminder
    if args.medication:
        meta["medication"] = args.medication
    if args.vaccine:
        meta["vaccine"] = args.vaccine
    if args.location:
        meta["location"] = args.location
    return json.dumps(meta, ensure_ascii=False)


def dial(phone_number: str, room_name: str, metadata: str) -> None:
    """Ask the Twilio bridge to place the call (LiveKit connector + Twilio)."""
    payload = json.loads(metadata)
    payload["room"] = room_name
    r = httpx.post(f"{BRIDGE_URL}/place", json=payload, timeout=60)
    if r.status_code >= 400:
        sys.exit(f"bridge returned {r.status_code}: {r.text}")
    print(r.json().get("message", r.text))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Place an outbound health-reminder call.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--to",
        required=True,
        help="Number to call, in E.164 format (e.g. +919876543210)",
    )
    parser.add_argument("--name", default=None, help="Caller's name, for the opening.")
    parser.add_argument(
        "--reminder",
        choices=["medication", "vaccination", "followup"],
        default="medication",
        help="What the call is about (default: medication).",
    )
    parser.add_argument(
        "--medication", default=None, help="Medication name for the reminder."
    )
    parser.add_argument(
        "--vaccine", default=None, help="Vaccine name for the reminder."
    )
    parser.add_argument(
        "--location", default=None, help="Village/town, for facility lookups."
    )
    parser.add_argument(
        "--room",
        default=None,
        help="Room name to use. Defaults to a generated one.",
    )
    args = parser.parse_args()

    metadata = build_metadata(args)
    room_name = args.room or f"outbound-{uuid.uuid4().hex[:8]}"

    dial(args.to, room_name, metadata)
    print(f"Sent to bridge for room '{room_name}' to call {args.to}.")
    print("Your phone will ring shortly. Watch the worker terminal for progress.")


if __name__ == "__main__":
    main()
