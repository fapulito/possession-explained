"""
app/serve.py — Single-command demo server for Possession, Explained.

Serves the static app (index.html) at / and provides:
  GET /api/summary          → possession_metrics.json
  GET /api/windows          → 15-min window data
  GET /api/top              → top-5 / bottom-5 possessions by value
  GET /api/possessions/<id> → one possession + its events
  GET /api/agents/narrative → narrative agent output
  GET /api/agents/recap     → recap agent output
  GET /api/agents/analyst?q=<question> → analyst agent answer

Usage:
    python3 app/serve.py
    PORT=9000 python3 app/serve.py
"""

import csv
import json
import os
import re
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
APP_DIR = Path(__file__).resolve().parent
REPO_ROOT = APP_DIR.parent

# Add repo root to sys.path so "agents" package is importable
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

METRICS_FILE = REPO_ROOT / "metrics" / "possession_metrics.json"
POSSESSIONS_CSV = REPO_ROOT / "data" / "possessions.csv"
EVENTS_CSV = REPO_ROOT / "data" / "events.csv"

# ---------------------------------------------------------------------------
# Load data once
# ---------------------------------------------------------------------------
with METRICS_FILE.open() as f:
    METRICS = json.load(f)


def _load_csv(path: Path) -> list[dict]:
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


POSSESSIONS: list[dict] = _load_csv(POSSESSIONS_CSV)
EVENTS: list[dict] = _load_csv(EVENTS_CSV)

EVENTS_BY_POSSESSION: dict[str, list[dict]] = {}
for _ev in EVENTS:
    EVENTS_BY_POSSESSION.setdefault(_ev["possession_id"], []).append(_ev)

# ---------------------------------------------------------------------------
# Lazy-import agents (they load the same data via agents.loader)
# ---------------------------------------------------------------------------
def _get_narrative() -> str:
    from agents.narrative import narrative
    return narrative()


def _get_recap() -> str:
    from agents.recap import recap
    return recap()


def _get_analyst(question: str) -> str:
    from agents.analyst import answer
    return answer(question)


# ---------------------------------------------------------------------------
# Route handlers (same logic as api/server.py)
# ---------------------------------------------------------------------------
def handle_summary() -> dict:
    return METRICS


def handle_windows() -> dict:
    return METRICS["possession_pct_by_15min_window"]


def handle_top() -> dict:
    ranked = sorted(POSSESSIONS, key=lambda p: float(p["possession_value"]), reverse=True)
    return {
        "top5": [{"possession_id": p["possession_id"], "value": float(p["possession_value"])} for p in ranked[:5]],
        "bottom5": [{"possession_id": p["possession_id"], "value": float(p["possession_value"])} for p in ranked[-5:]],
    }


def handle_possession(possession_id: str) -> tuple[dict, int]:
    row = next((p for p in POSSESSIONS if p["possession_id"] == possession_id), None)
    if row is None:
        return {"error": f"Possession {possession_id!r} not found"}, 404
    events = sorted(
        EVENTS_BY_POSSESSION.get(possession_id, []),
        key=lambda e: float(e["clock_sec"]),
    )
    return {"possession": row, "events": events}, 200


# ---------------------------------------------------------------------------
# HTTP handler
# ---------------------------------------------------------------------------
POSSESSION_RE = re.compile(r"^/api/possessions/([^/?]+)$")
ANALYST_RE = re.compile(r"^/api/agents/analyst$")

STATIC_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css",
    ".js": "application/javascript",
    ".json": "application/json",
    ".ico": "image/x-icon",
    ".png": "image/png",
    ".svg": "image/svg+xml",
}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print(f"  {self.address_string()} {fmt % args}")

    def do_GET(self):
        # Strip query string for routing
        path_qs = self.path.split("?", 1)
        path = path_qs[0]
        qs = path_qs[1] if len(path_qs) > 1 else ""

        # ── API routes ────────────────────────────────────────────────────
        if path == "/api/summary":
            self._json(handle_summary(), 200)
        elif path == "/api/windows":
            self._json(handle_windows(), 200)
        elif path == "/api/top":
            self._json(handle_top(), 200)
        elif m := POSSESSION_RE.match(path):
            body, status = handle_possession(m.group(1))
            self._json(body, status)
        elif path == "/api/agents/narrative":
            self._json({"result": _get_narrative()}, 200)
        elif path == "/api/agents/recap":
            self._json({"result": _get_recap()}, 200)
        elif ANALYST_RE.match(path):
            q = _parse_qs(qs).get("q", "")
            if not q:
                self._json({"error": "Missing ?q= parameter"}, 400)
            else:
                self._json({"result": _get_analyst(q)}, 200)
        # ── Static files ─────────────────────────────────────────────────
        elif path == "/" or path == "/index.html":
            self._serve_file(APP_DIR / "index.html")
        elif path.startswith("/") and ".." not in path:
            file_path = APP_DIR / path.lstrip("/")
            if file_path.is_file():
                self._serve_file(file_path)
            else:
                self._json({"error": "Not found"}, 404)
        else:
            self._json({"error": "Not found"}, 404)

    def _serve_file(self, path: Path):
        suffix = path.suffix.lower()
        content_type = STATIC_TYPES.get(suffix, "application/octet-stream")
        try:
            data = path.read_bytes()
        except FileNotFoundError:
            self._json({"error": "Not found"}, 404)
            return
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        # CORS for local dev
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(data)

    def _json(self, data, status: int):
        payload = json.dumps(data, indent=2).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(payload)


def _parse_qs(qs: str) -> dict[str, str]:
    """Minimal URL query-string parser (no external deps)."""
    result: dict[str, str] = {}
    if not qs:
        return result
    for part in qs.split("&"):
        if "=" in part:
            k, v = part.split("=", 1)
            result[_url_decode(k)] = _url_decode(v)
        else:
            result[_url_decode(part)] = ""
    return result


def _url_decode(s: str) -> str:
    """Decode %xx and + in query-string values."""
    s = s.replace("+", " ")
    result = []
    i = 0
    while i < len(s):
        if s[i] == "%" and i + 2 < len(s):
            try:
                result.append(chr(int(s[i + 1:i + 3], 16)))
                i += 3
                continue
            except ValueError:
                pass
        result.append(s[i])
        i += 1
    return "".join(result)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("", port), Handler)
    url = f"http://localhost:{port}"
    print("=" * 56)
    print("  Possession, Explained — Demo Server")
    print(f"  {url}")
    print("=" * 56)
    print(f"  API: {url}/api/summary")
    print(f"  App: {url}/")
    print("  Press Ctrl+C to stop.")
    print()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutdown.")
