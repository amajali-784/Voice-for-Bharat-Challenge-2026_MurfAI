"""Admin HTTP API for the human-help escalation store (stdlib only).

Lets a health worker (or the dashboard) see open human-help requests, open one
request, and move requests from open -> in_progress -> resolved.

Run:  uv run python src/escalation_api.py
Then: curl http://localhost:8701/escalations
"""

from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlparse

from escalation import DEFAULT_DB_PATH, VALID_STATUSES, EscalationStore

HOST = os.getenv("ESCALATION_API_HOST", "127.0.0.1")
PORT = int(os.getenv("ESCALATION_API_PORT", "8701"))

STORE = EscalationStore(DEFAULT_DB_PATH)


def _json_response(handler: BaseHTTPRequestHandler, status: int, payload: dict) -> None:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Access-Control-Allow-Methods", "GET, PATCH, OPTIONS")
    handler.send_header("Access-Control-Allow-Headers", "Content-Type")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _read_json_body(handler: BaseHTTPRequestHandler) -> dict:
    length = int(handler.headers.get("Content-Length") or 0)
    if length <= 0:
        return {}
    try:
        return json.loads(handler.rfile.read(length).decode("utf-8"))
    except json.JSONDecodeError:
        return {}


class EscalationAPIHandler(BaseHTTPRequestHandler):
    def do_OPTIONS(self) -> None:
        _json_response(self, 204, {})

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        prefix = "/escalations/"
        if parsed.path == "/" or parsed.path == "/escalations":
            _json_response(
                self,
                200,
                {
                    "count": STORE.count(),
                    "open_count": STORE.count("open"),
                    "requests": STORE.list(),
                },
            )
        elif parsed.path.startswith(prefix):
            reference_id = unquote(parsed.path[len(prefix) :])
            request = STORE.get(reference_id)
            if request is None:
                _json_response(self, 404, {"error": "request not found"})
            else:
                _json_response(self, 200, request)
        else:
            _json_response(self, 404, {"error": "not found"})

    def do_PATCH(self) -> None:
        parsed = urlparse(self.path)
        prefix = "/escalations/"
        if not parsed.path.startswith(prefix):
            _json_response(self, 404, {"error": "not found"})
            return
        reference_id = unquote(parsed.path[len(prefix) :])
        body = _read_json_body(self)
        status = (body.get("status") or "").strip().lower()
        if status not in VALID_STATUSES:
            _json_response(
                self,
                400,
                {
                    "error": f"invalid status '{status}'",
                    "valid": list(VALID_STATUSES),
                },
            )
            return
        updated = STORE.update_status(reference_id, status)
        if not updated:
            _json_response(self, 404, {"error": "request not found"})
            return
        _json_response(self, 200, STORE.get(reference_id))

    def log_message(self, fmt: str, *args: object) -> None:
        print(f"[escalation-api] {self.address_string()} - {fmt % args}")


def main() -> None:
    server = ThreadingHTTPServer((HOST, PORT), EscalationAPIHandler)
    print(f"Escalation admin API listening on http://{HOST}:{PORT}")
    print("  GET    /escalations            list human-help requests")
    print("  GET    /escalations/<ref_id>   one request")
    print('  PATCH  /escalations/<ref_id>   {"status": "in_progress|resolved"}')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")


if __name__ == "__main__":
    main()
