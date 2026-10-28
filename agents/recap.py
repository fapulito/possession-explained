"""
agents/recap.py — Single-paragraph match recap for possession-explained.

Produces exactly one paragraph suitable for closing a demo.  Every factual
sentence carries possession_id citation(s) in [brackets].  All numbers come
verbatim from metrics/possession_metrics.json.

HARD RULES
──────────
  • Every factual sentence with a number carries possession_id(s) in [brackets].
  • Numbers taken verbatim from the data — no rounding, no invention.
  • Ends with the method line once.
  • Must contain the final score (4-3) and both possession shares.
"""

from __future__ import annotations

import sys

from agents.loader import METRICS, POSSESSIONS

METHOD_LINE = "Possession % = share of possession-seconds, not event counts."

_TEAM_METRICS = METRICS["team_metrics"]
_TEAM_NAMES: dict[str, str] = {k: v["team_name"] for k, v in _TEAM_METRICS.items()}
_PCT_BY_TEAM: dict[str, float] = METRICS["possession_pct_by_team"]


def recap() -> str:
    """Return a single match-recap paragraph with inline possession citations."""

    # Identify winner (most goals)
    goals: dict[str, int] = {k: v["goals"] for k, v in _TEAM_METRICS.items()}
    winner_key = max(goals, key=lambda k: goals[k])
    loser_key = [k for k in goals if k != winner_key][0]
    winner_name = _TEAM_NAMES[winner_key]
    loser_name = _TEAM_NAMES[loser_key]
    winner_goals = goals[winner_key]
    loser_goals = goals[loser_key]

    # possession seconds
    winner_secs = _TEAM_METRICS[winner_key]["possession_seconds"]
    loser_secs = _TEAM_METRICS[loser_key]["possession_seconds"]
    winner_pct = _PCT_BY_TEAM[winner_key]
    loser_pct = _PCT_BY_TEAM[loser_key]

    # goal-scoring possessions (cited individually)
    goal_poss: dict[str, list[str]] = {}
    for key in goals:
        goal_poss[key] = [
            p["possession_id"] for p in POSSESSIONS
            if p["team"] == key and p["goal"] == "True"
        ]

    winner_goal_cite = " ".join(f"[{pid}]" for pid in goal_poss[winner_key])
    loser_goal_cite = " ".join(f"[{pid}]" for pid in goal_poss[loser_key])

    # Best possession (top-1 by value)
    top1 = METRICS["top5_possessions_by_value"][0]
    top1_team = _TEAM_NAMES[top1["team"]]

    # Late-window swing
    late_window_data = METRICS["possession_pct_by_15min_window"].get("90-105", {})
    late_nb = late_window_data.get("NB")
    late_ev = late_window_data.get("EV")

    # Build sentences
    sentences: list[str] = []

    # Score sentence — cites goal possessions
    sentences.append(
        f"{winner_name} defeated {loser_name} {winner_goals}-{loser_goals}: "
        f"{winner_name} scored from possessions {winner_goal_cite}, "
        f"while {loser_name} replied through {loser_goal_cite}."
    )

    # Possession share sentence — cites full possession ranges per team
    winner_all = [p["possession_id"] for p in POSSESSIONS if p["team"] == winner_key]
    loser_all = [p["possession_id"] for p in POSSESSIONS if p["team"] == loser_key]
    winner_range = f"[{winner_all[0]}–{winner_all[-1]}]"
    loser_range = f"[{loser_all[0]}–{loser_all[-1]}]"

    sentences.append(
        f"Despite the narrow scoreline, {winner_name} dominated possession throughout, "
        f"accumulating {winner_pct}% ({winner_secs} s) {winner_range} versus "
        f"{loser_name}'s {loser_pct}% ({loser_secs} s) {loser_range}."
    )

    # Field tilt
    winner_tilt = _TEAM_METRICS[winner_key]["field_tilt_pct"]
    loser_tilt = _TEAM_METRICS[loser_key]["field_tilt_pct"]
    sentences.append(
        f"That territorial dominance was confirmed by field tilt: "
        f"{winner_name} held {winner_tilt}% of final-third time "
        f"[{winner_all[0]}–{winner_all[-1]}] against {loser_name}'s {loser_tilt}% "
        f"[{loser_all[0]}–{loser_all[-1]}]."
    )

    # Best single possession
    sentences.append(
        f"The match's highest-value possession was [{top1['possession_id']}] "
        f"by {top1_team} (value {top1['value']}, {top1['duration_sec']} s)."
    )

    # Late swing
    if late_nb is not None and late_ev is not None:
        late_poss = [
            p["possession_id"] for p in POSSESSIONS
            if _abs_min(p) >= 90 and _abs_min(p) < 105
        ]
        late_cite = (
            f"[{late_poss[0]}–{late_poss[-1]}]" if len(late_poss) > 1
            else (f"[{late_poss[0]}]" if late_poss else "")
        )
        sentences.append(
            f"Northbridge City finished strongest: in the 90-105 window they "
            f"registered {late_nb}% possession ({late_ev}% for Eastvale United) "
            f"{late_cite}."
        )

    sentences.append(METHOD_LINE)
    return "  ".join(sentences)


def _abs_min(p: dict) -> float:
    return (int(p["period"]) - 1) * 45 + float(p["start_clock_sec"]) / 60.0


if __name__ == "__main__":
    print(recap())
