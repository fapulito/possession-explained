# Possession, Explained

> **SYNTHETIC DATASET — invented teams, not real match data.**

A hackathon demo that turns a synthetic football match into an interactive,
agent-powered possession analysis. The pitch: *possession volume does not equal
match control*. Northbridge City held 65.46 % of the ball and still only won
4–3; Eastvale United scored three goals from 34.54 % possession by being
direct and dangerous in transition. Every number is traceable to a
`possession_id`.

---

## Architecture

```
generator/generate_match.py          # seeded synthetic data (read-only)
          │
          ▼
data/possessions.csv (252 rows)
data/events.csv     (1 491 rows)
          │
          ▼
metrics/compute_metrics.py           # deterministic metrics (read-only)
          │
          ▼
metrics/possession_metrics.json      # pre-computed, byte-stable
          │
          ▼
api/server.py                        # Python stdlib HTTP API (port 8000)
          │
          ▼
agents/analyst.py                    # Q&A over the data
agents/narrative.py                  # window-by-window story
agents/recap.py                      # one-paragraph match recap
          │
          ▼
app/index.html  +  app/serve.py      # static single-page UI
```

---

## Method

> **Possession % = share of possession-seconds, not event counts.**

A possession is a run of consecutive events by one team, ending on a shot,
goal, foul, turnover, or ball out of play. 15-minute windows are assigned by
the possession's start minute. Possession value is an xT-style surface: value
gained between the possession's start position and its deepest point.

---

## How to run each layer

### 1. Generator (read-only — already run)
```bash
python3 generator/generate_match.py
# → writes data/possessions.csv (252 rows) and data/events.csv (1 491 events)
```

### 2. Metrics (read-only — already run)
```bash
python3 metrics/compute_metrics.py
# → writes metrics/possession_metrics.json (byte-identical on every run)
```

### 3. API
```bash
python3 api/server.py          # default port 8000
PORT=9000 python3 api/server.py
```

Endpoints:

| Endpoint | Description |
|---|---|
| `GET /api/summary` | Full `possession_metrics.json` |
| `GET /api/windows` | Possession % by 15-min window |
| `GET /api/possessions/{id}` | Possession row + events in clock order |
| `GET /api/top` | Top-5 and bottom-5 possessions by value |

API acceptance tests (start the server first, or let the test script spawn it):
```bash
python3 api/test_api.py
```

### 4. Agents (no server required — read files directly)
```bash
# Analyst — ask a question
python -m agents.analyst "Why did Northbridge dominate the 90-105 window?"

# Narrative — window-by-window story
python -m agents.narrative

# Recap — single match paragraph
python -m agents.recap
```

Agent acceptance tests:
```bash
python -m agents.test_agents
```

### 5. UI
```bash
python3 app/serve.py           # starts API + serves app/ on http://localhost:8000
```
Open `http://localhost:8000` in a browser. The page loads with no build step,
no npm, no external CDN assets.

---

## Sample agent answer (Analyst — Q5)

**Question:** *"Why did Northbridge dominate the 90-105 window?"*

```
Why did Northbridge City dominate window 90-105?

In the 90-105 window, Northbridge City held 79.53% of possession
(122.0 s across 4 possessions) [P0246–P0252].
Their opponents (Eastvale United) held 20.47% (31.4 s in 3 possessions) [P0247–P0251].
The longest Northbridge City possession in this window was [P0246]: 43.1 s,
ending in 'clearance'.
4 of those possessions reached the final third [P0246], [P0248], [P0250], [P0252].

Possession % = share of possession-seconds, not event counts.
```

Every factual sentence carries the `[PXXXX]` possession ID(s) it is based on.
All numbers are taken verbatim from `metrics/possession_metrics.json` — no
rounding, no estimation, no invented events.

---

## Key numbers at a glance

| Stat | Northbridge City (NB) | Eastvale United (EV) |
|---|---|---|
| Final score | **4** | **3** |
| Possession share | **65.46 %** | 34.54 % |
| Possession seconds | 2 864.6 s | 1 511.2 s |
| Field tilt | **73.25 %** | 26.75 % |
| Directness | 1.087 m/s | **1.988 m/s** |
| Possessions | 126 | 126 |
| Goals | 4 | 3 |

Window with biggest swing: **90-105 min → NB 79.53 % / EV 20.47 %**
[P0246–P0252]

Highest-value possession: **[P0197]** (Eastvale United, value 0.9788, 31.6 s)

---

## Files

```
generator/generate_match.py      Seeded synthetic data generator (SEED=20261025)
metrics/compute_metrics.py       Deterministic metrics calculator
metrics/possession_metrics.json  Pre-computed metrics (byte-stable)
data/possessions.csv             252 possessions (P0001–P0252)
data/events.csv                  1 491 events (E00001–E01491)
api/server.py                    Python stdlib HTTP API
api/test_api.py                  API acceptance tests (3 tests, 7 assertions)
agents/loader.py                 Shared data loader
agents/analyst.py                Q&A agent — 9 question shapes
agents/narrative.py              Window-by-window narrative
agents/recap.py                  Single-paragraph match recap
agents/foundry_adapter.py        Stub showing where a Foundry/Azure AI call slots in
agents/test_agents.py            Agent acceptance tests (3 blocks, 25 assertions)
app/index.html                   Single-page UI (plain HTML/CSS/JS)
app/serve.py                     Serves the UI + API in one command
DATA-README.md                   Full dataset documentation
```

---

## Synthetic-data disclaimer

This project uses a **100 % synthetic dataset**. The teams (Northbridge City
and Eastvale United), all player IDs, and the match itself are generated by a
seeded Python script (`generator/generate_match.py`, seed `20261025`). The
data has never been near a real football pitch and must never be presented as
real match data. The generator is deterministic: the same seed always produces
the same 252 possessions, 1 491 events, and byte-identical metrics file.

`metrics/possession_metrics.json` carries `"synthetic": true` and the note:
> "SYNTHETIC dataset (invented teams, simulated). Not real match data."

The UI displays a persistent banner: *"SYNTHETIC dataset — invented teams, not
real match data"*.
