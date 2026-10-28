#!/usr/bin/env python3
"""
Synthetic match generator — Premier League x Microsoft hackathon, Possession by Team.
SYNTHETIC DATA: invented teams, simulated events. Not real match data.

Deterministic: fixed seed -> identical output on every run.
Possession model: a possession is a run of consecutive events by one team,
ending on a shot, goal, foul, turnover, or ball out of play.
possession_id is sequential by time (P0001, P0002, ...) and therefore stable:
regenerating with the same seed reproduces the same ids for the same possessions.

Coordinates: 105 x 68 pitch, stored in the possessing team's attacking frame
(x = 0 own goal line, x = 105 opponent goal line), per period.
"""
import csv
import math
import os
import random

SEED = 20261025
MATCH_ID = "SYNTH-001"
OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "data")

TEAMS = {
    "NB": {  # Northbridge City — possession-heavy
        "name": "Northbridge City",
        "mean_passes": 10.0,
        "event_sec": 3.4,
        "pass_completion": 0.88,
        "advance_m": 5.5,       # metres gained per completed action
        "shot_prob_final_third": 0.07,
        "foul_prob": 0.02,
    },
    "EV": {  # Eastvale United — direct / counter
        "name": "Eastvale United",
        "mean_passes": 5.0,
        "event_sec": 3.0,
        "pass_completion": 0.76,
        "advance_m": 11.0,
        "shot_prob_final_third": 0.11,
        "foul_prob": 0.025,
    },
}
OTHER = {"NB": "EV", "EV": "NB"}


def xt_value(x: float) -> float:
    """Simple xT-style value of holding the ball at pitch position x."""
    return 1.0 / (1.0 + math.exp(-(x - 58.0) / 11.0))


def poissonish(rng: random.Random, mean: float) -> int:
    # Knuth Poisson, fine for small means.
    L = math.exp(-mean)
    k, p = 0, 1.0
    while True:
        p *= rng.random()
        if p <= L:
            return k
        k += 1


def gen_possession(rng, team, period, start_clock, poss_no, start_x, start_type):
    """Generate one possession. Returns (events, possession_row, end_clock, next_start_x, next_team)."""
    cfg = TEAMS[team]
    events = []
    clock = start_clock
    x = max(2.0, min(100.0, start_x))
    y = rng.uniform(8, 60)
    n_passes = max(1, poissonish(rng, cfg["mean_passes"]))
    end_reason = None
    shot = False
    goal = False

    def add(etype, ex, ey, nx, ny, outcome, pressure):
        nonlocal clock
        dur = max(1.2, rng.gauss(cfg["event_sec"], 0.8))
        clock_end = clock + dur
        events.append({
            "match_id": MATCH_ID, "period": period, "clock_sec": round(clock, 1),
            "event_id": "", "possession_id": f"P{poss_no:04d}",
            "team_in_possession": team, "player_id": f"{team}{rng.randint(1, 11)}",
            "event_type": etype, "x": round(ex, 1), "y": round(ey, 1),
            "end_x": round(nx, 1), "end_y": round(ny, 1),
            "outcome": outcome, "pressure_flag": pressure,
        })
        return clock_end

    # Restart / first event
    clock = add(start_type, x, y, x, y, "complete", False)
    max_x = x
    passes_done = 0
    while True:
        in_final_third = x >= 70
        # Shoot?
        if in_final_third and rng.random() < cfg["shot_prob_final_third"]:
            gx = 105.0
            gy = rng.uniform(30, 38)
            is_goal = rng.random() < 0.12
            clock = add("goal" if is_goal else "shot", x, y, gx, gy,
                        "goal" if is_goal else "complete", True)
            shot, goal = True, is_goal
            end_reason = "goal" if is_goal else "shot"
            max_x = 105.0
            break
        # Foul?
        if rng.random() < cfg["foul_prob"]:
            clock = add("foul", x, y, x, y, "complete", rng.random() < 0.4)
            end_reason = "foul"
            break
        # Next action: pass / carry / dribble
        etype = rng.choices(["pass", "carry", "dribble"], weights=[0.72, 0.18, 0.10])[0]
        complete = rng.random() < cfg["pass_completion"]
        adv = max(0.0, rng.gauss(cfg["advance_m"], 5.0)) if complete else max(0.0, rng.gauss(2.0, 2.0))
        nx = max(0.0, min(104.0, x + adv))
        ny = max(2.0, min(66.0, y + rng.gauss(0, 7)))
        pressure = rng.random() < (0.45 if nx >= 70 else 0.2)
        clock = add(etype, x, y, nx, ny, "complete" if complete else "incomplete", pressure)
        if etype == "pass":
            passes_done += 1
        x, y = nx, ny
        max_x = max(max_x, x)
        if not complete:
            end_reason = rng.choice(["interception", "incomplete_pass", "tackle"])
            # closing defensive event by the opponent at the turnover point
            events.append({
                "match_id": MATCH_ID, "period": period, "clock_sec": round(clock, 1),
                "event_id": "", "possession_id": f"P{poss_no:04d}",
                "team_in_possession": team, "player_id": f"{OTHER[team]}{rng.randint(1, 11)}",
                "event_type": "interception" if end_reason == "interception" else "tackle",
                "x": round(x, 1), "y": round(y, 1), "end_x": round(x, 1), "end_y": round(y, 1),
                "outcome": "complete", "pressure_flag": pressure,
            })
            break
        if passes_done >= n_passes:
            # possession dies without a shot: misplaced final ball / clearance / out of play
            end_reason = rng.choice(["out_of_play", "clearance", "incomplete_pass"])
            break

    duration = clock - start_clock
    row = {
        "possession_id": f"P{poss_no:04d}", "match_id": MATCH_ID, "period": period,
        "team": team, "team_name": cfg["name"],
        "start_clock_sec": round(start_clock, 1), "end_clock_sec": round(clock, 1),
        "duration_sec": round(duration, 1), "num_events": len(events),
        "num_passes": sum(1 for e in events if e["event_type"] == "pass"),
        "start_x": round(start_x, 1), "end_x": round(x, 1), "max_x": round(max_x, 1),
        "reached_final_third": max_x >= 70, "end_reason": end_reason,
        "shot": shot, "goal": goal,
        "possession_value": round(xt_value(max_x) - xt_value(start_x), 4),
        "start_zone": "defensive" if start_x < 35 else ("middle" if start_x < 70 else "final"),
    }
    # Next possession: opponent, mirrored start position
    next_start_x = 105.0 - x if end_reason in ("shot",) else (105.0 - x)
    if end_reason == "goal":
        next_start_x = 52.5  # kickoff
    if end_reason == "out_of_play":
        next_start_x = rng.uniform(20, 60)
    next_type = {"goal": "kickoff", "shot": "goal_kick", "foul": "free_kick",
                 "out_of_play": "throw_in"}.get(end_reason, "pass")
    return events, row, clock, max(2.0, min(100.0, next_start_x)), OTHER[team], next_type


def gen_period(rng, period, first_team, poss_no_start):
    events, rows = [], []
    clock = 0.0
    length = rng.uniform(47 * 60, 49 * 60) if period == 1 else rng.uniform(48 * 60, 51 * 60)
    team = first_team
    start_x, start_type = 52.5, "kickoff"
    poss_no = poss_no_start
    while clock < length:
        ev, row, clock, start_x, team, start_type = gen_possession(
            rng, team, period, clock, poss_no, start_x, start_type)
        events.extend(ev)
        rows.append(row)
        poss_no += 1
        clock += rng.uniform(2, 9)  # dead-ball gap between possessions
    return events, rows, poss_no


def main():
    rng = random.Random(SEED)
    all_events, all_rows = [], []
    poss_no = 1
    for period, first in ((1, "NB"), (2, "EV")):
        ev, rows, poss_no = gen_period(rng, period, first, poss_no)
        all_events.extend(ev)
        all_rows.extend(rows)
    for i, e in enumerate(all_events, 1):
        e["event_id"] = f"E{i:05d}"

    os.makedirs(OUT_DIR, exist_ok=True)
    with open(os.path.join(OUT_DIR, "events.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(all_events[0].keys()))
        w.writeheader()
        w.writerows(all_events)
    with open(os.path.join(OUT_DIR, "possessions.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(all_rows[0].keys()))
        w.writeheader()
        w.writerows(all_rows)
    tot = {t: sum(r["duration_sec"] for r in all_rows if r["team"] == t) for t in TEAMS}
    s = sum(tot.values())
    print(f"events={len(all_events)} possessions={len(all_rows)}")
    for t in TEAMS:
        print(f"{TEAMS[t]['name']}: {tot[t]/s*100:.1f}% of possession-seconds")


if __name__ == "__main__":
    main()
