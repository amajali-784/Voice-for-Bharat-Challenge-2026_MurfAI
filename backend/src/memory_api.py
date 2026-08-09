"""Admin HTTP API for the caller-memory store (stdlib only).

Lets you inspect and forget remembered callers without touching the database
directly.  Used by the frontend's /admin page.

Run:  uv run python -m src.memory_api            (or `python src/memory_api.py`)
Then: curl http://localhost:8700/callers
"""

from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlparse

from memory import DEFAULT_DB_PATH, CallerStore

HOST = os.getenv("MEMORY_API_HOST", "127.0.0.1")
PORT = int(os.getenv("MEMORY_API_PORT", "8700"))

STORE = CallerStore(DEFAULT_DB_PATH)


def _json_response(handler: BaseHTTPRequestHandler, status: int, payload: dict) -> None:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Access-Control-Allow-Methods", "GET, DELETE, OPTIONS")
    handler.send_header("Access-Control-Allow-Headers", "Content-Type")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


class MemoryAPIHandler(BaseHTTPRequestHandler):
    def do_OPTIONS(self) -> None:
        _json_response(self, 204, {})

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/" or parsed.path == "/callers":
            _json_response(
                self,
                200,
                {"count": STORE.count(), "callers": STORE.list()},
            )
        else:
            _json_response(self, 404, {"error": "not found"})

    def do_DELETE(self) -> None:
        parsed = urlparse(self.path)
        prefix = "/callers/"
        if parsed.path.startswith(prefix):
            caller_id = unquote(parsed.path[len(prefix) :])
            deleted = STORE.delete(caller_id)
            _json_response(
                self,
                200,
                {"caller_id": caller_id, "forgotten": deleted},
            )
        else:
            _json_response(self, 404, {"error": "not found"})

    def log_message(self, fmt: str, *args: object) -> None:
        print(f"[memory-api] {self.address_string()} - {fmt % args}")


def main() -> None:
    server = ThreadingHTTPServer((HOST, PORT), MemoryAPIHandler)
    print(f"Caller memory admin API listening on http://{HOST}:{PORT}")
    print("  GET    /callers        list remembered callers")
    print("  DELETE /callers/<id>   forget one caller")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")


if __name__ == "__main__":
    main()
