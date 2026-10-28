"""
Possession-Explained API
Serves data from metrics/possession_metrics.json, data/possessions.csv,
and data/events.csv using only the Python 3 standard library.

Usage:
    python3 api/server.py
    PORT=9000 python3 api/server.py
"""

import csv
import json
import os
import re
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

# ---------------------------------------------------------------------------
# Resolve paths relative to repo root (one level above this file)
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parent.parent
METRICS_FILE = REPO_ROOT / "metrics" / "possession_metrics.json"
POSSESSIONS_CSV = REPO_ROOT / "data" / "possessions.csv"
EVENTS_CSV = REPO_ROOT / "data" / "events.csv"

# ---------------------------------------------------------------------------
# Load data once at import time
# ---------------------------------------------------------------------------
with METRICS_FILE.open() as f:
    METRICS = json.load(f)


def _load_csv(path: Path) -> list[dict]:
    with path.open(newline="") as f:
        reader = csv.DictReader(f)
        return list(reader)


POSSESSIONS: list[dict] = _load_csv(POSSESSIONS_CSV)
EVENTS: list[dict] = _load_csv(EVENTS_CSV)

# Index events by possession_id for O(1) lookup
EVENTS_BY_POSSESSION: dict[str, list[dict]] = {}
for ev in EVENTS:
    pid = ev["possession_id"]
    EVENTS_BY_POSSESSION.setdefault(pid, []).append(ev)


# ---------------------------------------------------------------------------
# Route handlers
# ---------------------------------------------------------------------------

def handle_summary() -> dict:
    """Return the full contents of possession_metrics.json."""
    return METRICS


def handle_windows() -> dict:
    """Return possession percentages by 15-minute window, keyed by window label."""
    return METRICS["possession_pct_by_15min_window"]


def handle_possession(possession_id: str) -> tuple[dict | None, int]:
    """
    Return the matching row from possessions.csv plus its events from
    events.csv sorted by clock_sec ascending.  Returns (body, status_code).
    """
    row = next((p for p in POSSESSIONS if p["possession_id"] == possession_id), None)
    if row is None:
        return {"error": f"Possession {possession_id!r} not found"}, 404

    events = sorted(
        EVENTS_BY_POSSESSION.get(possession_id, []),
        key=lambda e: float(e["clock_sec"]),
    )
    return {"possession": row, "events": events}, 200


def handle_top() -> dict:
    """Return top-5 and bottom-5 possessions by value field in possessions.csv."""
    ranked = sorted(POSSESSIONS, key=lambda p: float(p["possession_value"]), reverse=True)
    top5 = [{"possession_id": p["possession_id"], "value": float(p["possession_value"])} for p in ranked[:5]]
    bottom5 = [{"possession_id": p["possession_id"], "value": float(p["possession_value"])} for p in ranked[-5:]]
    return {"top5": top5, "bottom5": bottom5}


# ---------------------------------------------------------------------------
# HTTP handler
# ---------------------------------------------------------------------------

POSSESSION_RE = re.compile(r"^/api/possessions/([^/?]+)$")


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):  # quiet down the default access log slightly
        print(f"{self.address_string()} - {fmt % args}")

    def do_GET(self):
        path = self.path.split("?", 1)[0]

        if path == "/api/summary":
            self._json(handle_summary(), 200)

        elif path == "/api/windows":
            self._json(handle_windows(), 200)

        elif path == "/api/top":
            self._json(handle_top(), 200)

        elif m := POSSESSION_RE.match(path):
            body, status = handle_possession(m.group(1))
            self._json(body, status)

        else:
            self._json({"error": "Not found"}, 404)

    def _json(self, data, status: int):
        payload = json.dumps(data, indent=2).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    server = HTTPServer(("", port), Handler)
    print(f"Possession-Explained API listening on http://localhost:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutdown.")
