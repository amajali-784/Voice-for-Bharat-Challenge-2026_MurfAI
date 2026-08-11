"""Trigger an outbound health-reminder call.

The outbound agent doesn't call anyone on its own — it waits to be dispatched
into a room with a phone number in the job metadata. This script does that
dispatch.

Make sure the worker is running first:

    uv run python src/telephony/outbound/agent.py dev

Then place a call (E.164 number, e.g. +919876543210):

    uv run python src/telephony/outbound/dial.py --to +919876543210

Optional caller/reminder context (the agent opens with these):

    uv run python src/telephony/outbound/dial.py --to +919876543210 \
        --name "Sunita Devi" --reminder medication --medication मधुमेह \
        --location Varanasi

This is the scriptable equivalent of:

    lk dispatch create --agent-name health-reminder-agent --room my-room \\
      --metadata '{"phone_number": "+919876543210"}'
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

# Must match the agent_name in agent.py.
AGENT_NAME = "health-reminder-agent"

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


async def dial(phone_number: str, room_name: str, metadata: str) -> None:
    """Create the room and dispatch the outbound agent into it."""
    lk = api.LiveKitAPI()
    try:
        await lk.room.create_room(api.CreateRoomRequest(name=room_name))
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

    asyncio.run(dial(args.to, room_name, metadata))

    print(f"Dispatched {AGENT_NAME} to room '{room_name}' to call {args.to}.")
    print("Your phone will ring in ~5 s. Watch the worker terminal for progress.")


if __name__ == "__main__":
    main()
