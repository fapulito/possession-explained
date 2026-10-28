# Synthetic possession dataset — SYNTHETIC DATA

**This dataset is synthetic.** The teams (Northbridge City, Eastvale United),
players, and the match itself are simulated by a seeded generator. It is not
real match data and must never be presented as such.

Built early for the Premier League x Microsoft hackathon sprint (Oct 25–27)
so the sprint starts on the demo and agents, not on data generation.

## What's here
- `data/events.csv` — 1,491 events: match_id, period, clock_sec, event_id,
  possession_id, team_in_possession, player_id, event_type, x, y, end_x,
  end_y, outcome, pressure_flag.
- `data/possessions.csv` — 252 possessions, one row per possession, each with
  a stable `possession_id` (P0001…P0252) that agents can cite verbatim.
- `metrics/possession_metrics.json` — possession by team (match, per period,
  per 15-minute window), possession quality, field tilt, directness,
  top/bottom 5 possessions by value, and turnover-danger sequences — each
  citing the possession_ids behind it.
- `generator/generate_match.py` — the seeded generator (seed 20261025).
- `metrics/compute_metrics.py` — the deterministic metrics calculator.

## Method (state this in the app and pitch)
- Possession % = share of **possession-seconds**, not event counts.
- A possession is a run of consecutive events by one team, ending on a shot,
  goal, foul, turnover, or ball out of play.
- Coordinates are a 105 x 68 pitch in the possessing team's attacking frame
  (x = 0 own goal line, x = 105 opponent goal line).
- Possession value is a simple xT-style surface: value gained between the
  possession's start and its deepest point.

## Reproduce
```
python3 generator/generate_match.py   # regenerates the identical dataset
python3 metrics/compute_metrics.py    # recomputes identical metrics
```
Regeneration and recomputation are verified deterministic: same seed, same
possession_ids, same metrics, byte-identical metrics file.

## The match story (for the pitch)
Northbridge City (possession-heavy) held 65.5% of possession-seconds and a
73.25% field tilt; Eastvale United (direct/counter) scored 3 goals from
34.5% of the ball. Final score 4–3 — the dataset itself makes the argument
that possession volume and match control are not the same thing.
