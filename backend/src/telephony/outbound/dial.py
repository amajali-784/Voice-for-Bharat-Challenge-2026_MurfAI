"""Trigger an outbound health-reminder call over Linphone.

The outbound agent doesn't call anyone on its own — it waits to be dispatched
into a room with a dial target in the job metadata. This script creates the
room and dispatches the ``health-reminder-agent`` worker through LiveKit's API.
The worker then dials out through the LiveKit outbound trunk
(``sip.linphone.org``, TLS) and the **Linphone app on your phone rings**.

Make sure the worker is running first (Terminal 1):

    uv run python src/telephony/outbound/agent.py dev

Then place a call from a second terminal (Terminal 2). ``--to`` accepts:

* a bare Linphone username   -> ``sunita``
* a full SIP address         -> ``sip:sunita@sip.linphone.org``
* an E.164 phone number      -> ``+919876543210`` (only if your trunk reaches it)

LiveKit's ``sip_call_to`` takes a phone number or SIP **user** (the trunk's
``address`` supplies the domain), so ``sunita`` and
``sip:sunita@sip.linphone.org`` both dial ``sunita`` on your trunk.

    uv run python src/telephony/outbound/dial.py --to sunita

Optional caller/reminder context (the agent opens with these):

    uv run python src/telephony/outbound/dial.py --to sunita \
        --name "Sunita Devi" --reminder medication --medication मधुमेह \
        --location Varanasi

This is the scriptable equivalent of the LiveKit CLI:

    lk room create --name <room> && lk dispatch create \
        --agent health-reminder-agent --room <room> --metadata '<json>'
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
import uuid

from dotenv import load_dotenv
from livekit import api

load_dotenv(".env.local")

# Must match the worker's agent_name in telephony/outbound/agent.py.
AGENT_NAME = "health-reminder-agent"

# E.164: a leading + and 7-15 digits, e.g. +919876543210.
E164 = re.compile(r"^\+[1-9]\d{6,14}$")

# A bare username is any single token with no spaces/slashes (RFC-ish user part).
_USERNAME = re.compile(r"^[A-Za-z0-9._%+-]+$")


def normalize_dial_target(target: str) -> str:
    """Turn ``--to`` into the value LiveKit's ``sip_call_to`` accepts.

    LiveKit rejects full SIP URIs ("SipCallTo should be a phone number or SIP
    user, not a full SIP URI") — the trunk's ``address`` already supplies the
    domain. So a username, a ``sip:user@host`` address, or a ``user@host``
    address all reduce to the bare SIP user; an E.164 number passes through.
    """
    target = (target or "").strip()
    if not target:
        sys.exit("--to is required: a Linphone username, sip: URI, or E.164 number.")
    if target.lower().startswith("sip:"):
        target = target[4:]
    if "@" in target:
        target = target.split("@", 1)[0]
    if E164.match(target):
        return target
    if _USERNAME.match(target):
        return target
    sys.exit(
        f"'{target}' is not a valid dial target. Use a Linphone username "
        "(e.g. sunita), a SIP address (e.g. sip:sunita@sip.linphone.org), "
        "or an E.164 phone number (e.g. +919876543210)."
    )


def build_metadata(args: argparse.Namespace) -> str:
    """Assemble the dispatch metadata (the reminder context the agent reads)."""
    meta: dict = {"phone_number": normalize_dial_target(args.to)}
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


async def dispatch(room_name: str, metadata: str) -> None:
    """Create the room and dispatch the outbound worker into it (LiveKit API)."""
    lk = api.LiveKitAPI()
    try:
        await lk.room.create_room(
            api.CreateRoomRequest(name=room_name, empty_timeout=300)
        )
        await lk.agent_dispatch.create_dispatch(
            api.CreateAgentDispatchRequest(
                agent_name=AGENT_NAME,
                room=room_name,
                metadata=metadata,
            )
        )
    finally:
        await lk.aclose()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Place an outbound health-reminder call over Linphone.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--to",
        required=True,
        help=(
            "Who to call: a Linphone username (sunita), a full SIP address "
            "(sip:sunita@sip.linphone.org), or an E.164 number (+919876543210)"
        ),
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

    asyncio.run(dispatch(room_name, metadata))
    print(f"Dispatched {AGENT_NAME} into room '{room_name}' to call {args.to}.")
    print("Your Linphone app will ring shortly. Watch the worker terminal.")


if __name__ == "__main__":
    main()
