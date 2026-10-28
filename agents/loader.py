"""
agents/loader.py — shared data loader for the possession-explained agents.

Reads metrics/possession_metrics.json and data/possessions.csv using exactly
the same path resolution as api/server.py.  No HTTP call needed; agents access
the same pre-computed metrics file the API serves from.
"""

import csv
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
METRICS_FILE = REPO_ROOT / "metrics" / "possession_metrics.json"
POSSESSIONS_CSV = REPO_ROOT / "data" / "possessions.csv"

# ── load once ────────────────────────────────────────────────────────────────

def load_metrics() -> dict:
    with METRICS_FILE.open() as f:
        return json.load(f)


def load_possessions() -> list[dict]:
    with POSSESSIONS_CSV.open(newline="") as f:
        return list(csv.DictReader(f))


# Module-level singletons so callers pay the I/O cost once per process.
METRICS: dict = load_metrics()
POSSESSIONS: list[dict] = load_possessions()

# Convenience index: possession_id -> row
POSSESSION_BY_ID: dict[str, dict] = {p["possession_id"]: p for p in POSSESSIONS}
