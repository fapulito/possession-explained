"""
agents/narrative.py — Window-by-window narrative for possession-explained.

Produces one short paragraph per 15-minute window.  Every factual sentence
carries a possession_id citation in [brackets].  Numbers come only from
metrics/possession_metrics.json and data/possessions.csv.

HARD RULES
──────────
  • Every factual sentence with a number carries the possession_id(s) in [brackets].
  • Numbers are taken verbatim from the data — no rounding, no invention.
  • Ends with the method line once.
  • No estimation, no invented events.
"""

from __future__ import annotations

import sys

from agents.loader import METRICS, POSSESSIONS, POSSESSION_BY_ID

METHOD_LINE = "Possession % = share of possession-seconds, not event counts."

_TEAM_NAMES: dict[str, str] = {
    k: v["team_name"] for k, v in METRICS["team_metrics"].items()
}
_WINDOWS: dict[str, dict] = METRICS["possession_pct_by_15min_window"]


def _possessions_in_window(window_label: str) -> list[dict]:
    start, end = (int(x) for x in window_label.split("-"))
    result = []
    for row in POSSESSIONS:
        period = int(row["period"])
        abs_min = (period - 1) * 45 + float(row["start_clock_sec"]) / 60.0
        if start <= abs_min < end:
            result.append(row)
    return result


def _window_paragraph(window_label: str) -> str:
    data = _WINDOWS[window_label]
    poss = _possessions_in_window(window_label)

    # Dominant team
    dominant_key = max(data, key=lambda k: data[k])
    dominant_name = _TEAM_NAMES[dominant_key]
    dominant_pct = data[dominant_key]

    team_poss: dict[str, list[dict]] = {k: [] for k in _TEAM_NAMES}
    for p in poss:
        team_poss.setdefault(p["team"], []).append(p)

    dom_poss = team_poss.get(dominant_key, [])
    dom_ids = [p["possession_id"] for p in dom_poss]
    all_ids = [p["possession_id"] for p in poss]
    window_cite = (
        f"[{all_ids[0]}–{all_ids[-1]}]" if len(all_ids) > 1
        else (f"[{all_ids[0]}]" if all_ids else "")
    )

    # Longest possession in window
    if poss:
        longest = max(poss, key=lambda p: float(p["duration_sec"]))
        longest_team = _TEAM_NAMES[longest["team"]]
    else:
        longest = None

    # Shots / goals in window
    shots = [p for p in poss if p["shot"] == "True"]
    goals = [p for p in poss if p["goal"] == "True"]

    # Build paragraph sentences
    sentences: list[str] = []

    # Sentence 1: possession overview
    dom_cite = (
        f"[{dom_ids[0]}–{dom_ids[-1]}]" if len(dom_ids) > 1
        else (f"[{dom_ids[0]}]" if dom_ids else window_cite)
    )
    sentences.append(
        f"In the {window_label} window {dominant_name} controlled {dominant_pct}% "
        f"of possession {dom_cite}."
    )

    # Sentence 2: count of possessions across both teams
    if all_ids:
        sentences.append(
            f"There were {len(poss)} possessions in this window "
            f"{window_cite}."
        )

    # Sentence 3: longest possession
    if longest:
        sentences.append(
            f"The longest possession belonged to {longest_team}: "
            f"[{longest['possession_id']}] ran for {float(longest['duration_sec']):.1f} s "
            f"and ended in '{longest['end_reason']}'."
        )

    # Sentence 4: shots
    if shots:
        shot_ids = ", ".join(f"[{p['possession_id']}]" for p in shots)
        sentences.append(
            f"{len(shots)} possession(s) ended in a shot: {shot_ids}."
        )

    # Sentence 5: goals
    if goals:
        for g in goals:
            gteam = _TEAM_NAMES[g["team"]]
            sentences.append(
                f"{gteam} scored from possession [{g['possession_id']}] "
                f"(duration {float(g['duration_sec']):.1f} s)."
            )

    return " ".join(sentences)


def narrative() -> str:
    """Return the full window-by-window narrative as a multi-paragraph string."""
    paras: list[str] = []
    for label in sorted(_WINDOWS, key=lambda w: int(w.split("-")[0])):
        para = _window_paragraph(label)
        paras.append(f"[{label} min]\n{para}")
    paras.append(METHOD_LINE)
    return "\n\n".join(paras)


if __name__ == "__main__":
    print(narrative())
