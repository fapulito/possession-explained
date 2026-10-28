"""
Acceptance tests for the Possession-Explained API.

Run the server first:
    python3 api/server.py &

Then run tests:
    python3 api/test_api.py

The script starts the server in-process (no external process needed) so it
can be run as a single self-contained command.
"""

import csv
import json
import sys
import threading
import time
import urllib.request
from http.server import HTTPServer
from pathlib import Path

# ---------------------------------------------------------------------------
# Import the handler from api/server.py without running __main__
# ---------------------------------------------------------------------------
sys.path.insert(0, str(Path(__file__).resolve().parent))
from server import Handler, METRICS, POSSESSIONS, EVENTS  # noqa: E402

# ---------------------------------------------------------------------------
# Spin up a test server on a free port
# ---------------------------------------------------------------------------
TEST_PORT = 18432
_server = HTTPServer(("127.0.0.1", TEST_PORT), Handler)
_thread = threading.Thread(target=_server.serve_forever, daemon=True)
_thread.start()
time.sleep(0.2)  # give the server a moment to bind

BASE = f"http://127.0.0.1:{TEST_PORT}"


def get_json(path: str) -> dict | list:
    with urllib.request.urlopen(BASE + path) as resp:
        return json.loads(resp.read())


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------

PASS = "\033[32mPASS\033[0m"
FAIL = "\033[31mFAIL\033[0m"
failures: list[str] = []


def assert_eq(label: str, actual, expected):
    if actual == expected:
        print(f"  {PASS}  {label}")
    else:
        print(f"  {FAIL}  {label}")
        print(f"         expected: {expected!r}")
        print(f"         got:      {actual!r}")
        failures.append(label)


def assert_true(label: str, condition: bool, detail: str = ""):
    if condition:
        print(f"  {PASS}  {label}")
    else:
        msg = f"{label}" + (f" — {detail}" if detail else "")
        print(f"  {FAIL}  {msg}")
        failures.append(label)


# ---------------------------------------------------------------------------
# Test 1 — /api/possessions/P0197
# ---------------------------------------------------------------------------

def test_possession_p0197():
    print("\n[Test 1] GET /api/possessions/P0197")
    data = get_json("/api/possessions/P0197")

    # 1a — possession row matches CSV
    csv_row = next(p for p in POSSESSIONS if p["possession_id"] == "P0197")
    assert_eq("possession row matches possessions.csv", data["possession"], csv_row)

    # 1b — all returned events belong to P0197
    bad = [e for e in data["events"] if e["possession_id"] != "P0197"]
    assert_true("all events have possession_id == P0197", len(bad) == 0,
                f"{len(bad)} foreign events found")

    # 1c — event count matches CSV
    expected_events = [e for e in EVENTS if e["possession_id"] == "P0197"]
    assert_eq("event count matches CSV", len(data["events"]), len(expected_events))

    # 1d — events are in clock order
    clocks = [float(e["clock_sec"]) for e in data["events"]]
    assert_true("events are in ascending clock order", clocks == sorted(clocks))


# ---------------------------------------------------------------------------
# Test 2 — /api/windows: percentages sum to 100.00 per window
# ---------------------------------------------------------------------------

def test_windows_sum_to_100():
    print("\n[Test 2] GET /api/windows — percentages sum to 100.00 per window")
    data = get_json("/api/windows")

    for window, teams in data.items():
        total = sum(float(v) for v in teams.values())
        ok = abs(total - 100.0) <= 0.01
        assert_true(
            f"window '{window}' sums to 100.00 (got {total:.4f})",
            ok,
        )


# ---------------------------------------------------------------------------
# Test 3 — /api/summary matches possession_metrics.json exactly
# ---------------------------------------------------------------------------

def test_summary_matches_metrics():
    print("\n[Test 3] GET /api/summary — matches possession_metrics.json exactly")
    data = get_json("/api/summary")
    assert_eq("summary body == possession_metrics.json", data, METRICS)


# ---------------------------------------------------------------------------
# Run all tests
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    test_possession_p0197()
    test_windows_sum_to_100()
    test_summary_matches_metrics()

    print()
    if failures:
        print(f"\033[31m{len(failures)} test(s) FAILED:\033[0m")
        for f in failures:
            print(f"  - {f}")
        _server.shutdown()
        sys.exit(1)
    else:
        print("\033[32mAll tests passed.\033[0m")
        _server.shutdown()
        sys.exit(0)
