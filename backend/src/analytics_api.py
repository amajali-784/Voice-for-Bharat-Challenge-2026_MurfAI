"""Admin HTTP API for the call analytics store (stdlib only).

Powers the Day 8 frontend dashboard.  Returns anonymised aggregates and recent
call metadata — hashed caller ids, counts, timings and tool names only.  No
transcripts, names, phone numbers or private details are ever exposed.

Run:  uv run python src/analytics_api.py
Then: curl http://localhost:8702/analytics
"""

from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from analytics import DEFAULT_DB_PATH, CallRecordStore

HOST = os.getenv("ANALYTICS_API_HOST", "127.0.0.1")
PORT = int(os.getenv("ANALYTICS_API_PORT", "8702"))

STORE = CallRecordStore(DEFAULT_DB_PATH)


def _json_response(handler: BaseHTTPRequestHandler, status: int, payload: dict) -> None:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
    handler.send_header("Access-Control-Allow-Headers", "Content-Type")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


class AnalyticsAPIHandler(BaseHTTPRequestHandler):
    def do_OPTIONS(self) -> None:
        _json_response(self, 204, {})

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)

        if parsed.path == "/" or parsed.path == "/analytics":
            days = _int_query(query, "days", 14)
            _json_response(
                self,
                200,
                {
                    "summary": STORE.summary(),
                    "daily": STORE.daily(days),
                    "latency_trend": STORE.latency_trend(days),
                    "recent_calls": STORE.recent(20),
                },
            )
        elif parsed.path == "/analytics/calls":
            limit = _int_query(query, "limit", 50)
            channel = (query.get("channel") or [""])[0] or None
            _json_response(
                self,
                200,
                {
                    "count": len(STORE.recent(limit, channel)),
                    "calls": STORE.recent(limit, channel),
                },
            )
        elif parsed.path == "/analytics/summary":
            _json_response(self, 200, {"summary": STORE.summary()})
        elif parsed.path == "/analytics/daily":
            days = _int_query(query, "days", 14)
            _json_response(self, 200, {"daily": STORE.daily(days)})
        elif parsed.path == "/healthz":
            _json_response(self, 200, {"ok": True})
        else:
            _json_response(self, 404, {"error": "not found"})

    def log_message(self, fmt: str, *args: object) -> None:
        print(f"[analytics-api] {self.address_string()} - {fmt % args}")


def _int_query(query: dict, key: str, default: int) -> int:
    try:
        return max(1, min(int(query.get(key, [str(default)])[0]), 90))
    except ValueError:
        return default


def main() -> None:
    server = ThreadingHTTPServer((HOST, PORT), AnalyticsAPIHandler)
    print(f"Call analytics admin API listening on http://{HOST}:{PORT}")
    print("  GET /analytics           summary + daily + latency + recent calls")
    print("  GET /analytics/calls     recent calls (limit, channel filters)")
    print("  GET /analytics/summary   just the headline numbers")
    print("  GET /analytics/daily     per-day totals for charts")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")


if __name__ == "__main__":
    main()
