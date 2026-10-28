#!/usr/bin/env python3
"""
Deterministic possession metrics — Premier League x Microsoft hackathon.
Reads ONLY data/possessions.csv and data/events.csv; no randomness, no LLM.
Running it any number of times on the same dataset yields identical output.

Method: possession % = share of possession-seconds (not event counts).
15-minute windows are by absolute match minute; a possession's seconds are
attributed to the window in which the possession starts.
"""
import csv
import json
import os

BASE = os.path.join(os.path.dirname(__file__), "..")
DATA = os.path.join(BASE, "data")
OUT = os.path.join(BASE, "metrics", "possession_metrics.json")


def load(name):
    with open(os.path.join(DATA, name), newline="") as f:
        return list(csv.DictReader(f))


def pct(n, d):
    return round(100.0 * n / d, 2) if d else 0.0


def main():
    poss = load("possessions.csv")
    teams = sorted({r["team"] for r in poss})
    names = {r["team"]: r["team_name"] for r in poss}

    def share(rows):
        tot = sum(float(r["duration_sec"]) for r in rows)
        return {t: pct(sum(float(r["duration_sec"]) for r in rows if r["team"] == t), tot)
                for t in teams}

    by_period = {p: share([r for r in poss if r["period"] == p]) for p in ("1", "2")}
    windows = {}
    for r in poss:
        abs_min = (int(r["period"]) - 1) * 45 + float(r["start_clock_sec"]) / 60.0
        w = f"{int(abs_min // 15) * 15}-{int(abs_min // 15) * 15 + 15}"
        windows.setdefault(w, []).append(r)
    by_window = {w: share(rows) for w, rows in sorted(windows.items())}

    per_team = {}
    for t in teams:
        rows = [r for r in poss if r["team"] == t]
        dur = sum(float(r["duration_sec"]) for r in rows)
        ft = [r for r in rows if r["reached_final_third"] == "True"]
        ft_sec = sum(float(r["duration_sec"]) for r in ft)
        total_ft_sec = sum(float(r["duration_sec"]) for r in poss if r["reached_final_third"] == "True")
        per_team[t] = {
            "team_name": names[t],
            "possessions": len(rows),
            "possession_seconds": round(dur, 1),
            "avg_duration_sec": round(dur / len(rows), 2),
            "avg_passes_per_possession": round(sum(int(r["num_passes"]) for r in rows) / len(rows), 2),
            "pct_reaching_final_third": pct(len(ft), len(rows)),
            "pct_ending_in_shot": pct(sum(1 for r in rows if r["shot"] == "True"), len(rows)),
            "goals": sum(1 for r in rows if r["goal"] == "True"),
            "field_tilt_pct": pct(ft_sec, total_ft_sec),
            "directness_m_per_sec": round(
                sum(max(0.0, float(r["max_x"]) - float(r["start_x"])) for r in rows) / dur, 3),
        }

    ranked = sorted(poss, key=lambda r: float(r["possession_value"]), reverse=True)
    cite = lambda r: {
        "possession_id": r["possession_id"], "team": r["team"], "period": int(r["period"]),
        "start_clock_sec": float(r["start_clock_sec"]), "duration_sec": float(r["duration_sec"]),
        "start_x": float(r["start_x"]), "max_x": float(r["max_x"]),
        "value": float(r["possession_value"]), "end_reason": r["end_reason"],
        "shot": r["shot"] == "True", "goal": r["goal"] == "True",
    }
    top5 = [cite(r) for r in ranked[:5]]
    bottom5 = [cite(r) for r in ranked[-5:]]

    # Turnover danger: lost in own defensive third, opponent shoots within 15 s.
    danger = []
    ordered = sorted(poss, key=lambda r: (int(r["period"]), float(r["start_clock_sec"])))
    for i, r in enumerate(ordered[:-1]):
        nxt = ordered[i + 1]
        if (r["end_reason"] in ("interception", "tackle", "incomplete_pass")
                and float(r["end_x"]) < 35 and nxt["team"] != r["team"]
                and nxt["period"] == r["period"] and nxt["shot"] == "True"
                and float(nxt["start_clock_sec"]) - float(r["end_clock_sec"]) <= 15):
            danger.append({
                "lost_possession_id": r["possession_id"], "team": r["team"],
                "end_x": float(r["end_x"]),
                "resulting_shot_possession_id": nxt["possession_id"],
                "shooting_team": nxt["team"], "goal": nxt["goal"] == "True",
            })

    out = {
        "synthetic": True,
        "note": "SYNTHETIC dataset (invented teams, simulated). Not real match data.",
        "match_id": poss[0]["match_id"],
        "method": "Possession % = share of possession-seconds. Windows by possession start.",
        "possession_pct_by_team": share(poss),
        "possession_pct_by_period": by_period,
        "possession_pct_by_15min_window": by_window,
        "team_metrics": per_team,
        "top5_possessions_by_value": top5,
        "bottom5_possessions_by_value": bottom5,
        "turnover_danger": danger,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        json.dump(out, f, indent=2, sort_keys=True)
    print(json.dumps({t: out["possession_pct_by_team"][t] for t in teams}, indent=2))
    print(f"top possession: {top5[0]['possession_id']} (value {top5[0]['value']})")
    print(f"turnover-danger sequences: {len(danger)}")


if __name__ == "__main__":
    main()
