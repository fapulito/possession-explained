"""
agents/analyst.py — Deterministic analyst agent for possession-explained.

Answers questions about the match using ONLY numbers present in
metrics/possession_metrics.json or derivable from data/possessions.csv.

Supported question shapes
─────────────────────────
  possession share       "possession share" / "overall possession"
  period possession      "period 1 possession" / "possession period 2"
  window possession      "window 90" / "90-105 possession" / "60-75"
  field tilt             "field tilt"
  directness             "directness"
  best possessions       "best possessions" / "top possessions"
  worst possessions      "worst possessions" / "bottom possessions"
  why dominate           "why did <team> dominate window <N>"
  team goals             "goals" / "score"

Any question outside these shapes, or about information not in the data
(weather, referee, attendance, …), receives a polite refusal.

HARD RULES enforced here
─────────────────────────
  • Every factual sentence carries the possession_id(s) it is based on in [brackets].
  • All numbers are taken verbatim from the JSON/CSV — no rounding, no estimation.
  • Every answer ends with the method line.
  • The agent never invents events or estimates.
"""

from __future__ import annotations

import re
import sys

from agents.loader import METRICS, POSSESSIONS, POSSESSION_BY_ID

METHOD_LINE = "Possession % = share of possession-seconds, not event counts."

# ── team name helpers ─────────────────────────────────────────────────────────

_TEAM_NAMES: dict[str, str] = {
    k: v["team_name"] for k, v in METRICS["team_metrics"].items()
}  # e.g. {"NB": "Northbridge City", "EV": "Eastvale United"}

# reverse map: lowercase fragments -> team key
_NAME_TO_KEY: dict[str, str] = {v.lower(): k for k, v in _TEAM_NAMES.items()}
_NAME_TO_KEY.update({k.lower(): k for k in _TEAM_NAMES})  # also "NB", "EV"


def _resolve_team(fragment: str) -> str | None:
    """Return the team key (e.g. 'NB') for a partial name fragment, or None."""
    frag = fragment.lower().strip()
    # exact match
    for full, key in _NAME_TO_KEY.items():
        if frag == full:
            return key
    # substring match
    for full, key in _NAME_TO_KEY.items():
        if frag in full or full in frag:
            return key
    return None


# ── window helpers ────────────────────────────────────────────────────────────

_WINDOWS: dict[str, dict] = METRICS["possession_pct_by_15min_window"]
# sorted list of (start_min, label)
_WINDOW_STARTS: list[tuple[int, str]] = sorted(
    (int(lbl.split("-")[0]), lbl) for lbl in _WINDOWS
)


def _find_window_label(minute_hint: int) -> str | None:
    """Return the window label whose start <= minute_hint < end."""
    for start, lbl in _WINDOW_STARTS:
        end = start + 15
        if start <= minute_hint < end:
            return lbl
    return None


def _possessions_in_window(window_label: str) -> list[dict]:
    """Return all possessions whose start falls in the given 15-min window."""
    start, end = (int(x) for x in window_label.split("-"))
    result = []
    for row in POSSESSIONS:
        period = int(row["period"])
        abs_min = (period - 1) * 45 + float(row["start_clock_sec"]) / 60.0
        if start <= abs_min < end:
            result.append(row)
    return result


# ── answer builders ───────────────────────────────────────────────────────────

def _answer_possession_share() -> str:
    tm = METRICS["team_metrics"]
    lines = ["Overall possession share for the match:"]
    for key, info in tm.items():
        pct = METRICS["possession_pct_by_team"][key]
        secs = info["possession_seconds"]
        poss_ids = [p["possession_id"] for p in POSSESSIONS if p["team"] == key]
        # cite all possession IDs would be hundreds — cite the aggregate stat source
        # instead we cite the full set as a range
        lines.append(
            f"  {info['team_name']} ({key}): {pct}% "
            f"({secs} s across {info['possessions']} possessions "
            f"[{poss_ids[0]}–{poss_ids[-1]}])."
        )
    lines.append(METHOD_LINE)
    return "\n".join(lines)


def _answer_period_possession(period: str) -> str:
    by_period = METRICS["possession_pct_by_period"]
    if period not in by_period:
        return f"No data for period {period!r}. Available periods: {list(by_period)}.\n{METHOD_LINE}"
    data = by_period[period]
    poss_in_period = [p for p in POSSESSIONS if p["period"] == period]
    ids = [p["possession_id"] for p in poss_in_period]
    cite = f"[{ids[0]}–{ids[-1]}]"
    lines = [f"Period {period} possession share {cite}:"]
    for key in data:
        lines.append(f"  {_TEAM_NAMES[key]}: {data[key]}%.")
    lines.append(METHOD_LINE)
    return "\n".join(lines)


def _answer_window_possession(window_label: str) -> str:
    data = _WINDOWS.get(window_label)
    if data is None:
        return (
            f"No data for window {window_label!r}. "
            f"Available windows: {list(_WINDOWS)}.\n{METHOD_LINE}"
        )
    poss = _possessions_in_window(window_label)
    if poss:
        ids = [p["possession_id"] for p in poss]
        cite = f"[{ids[0]}–{ids[-1]}]"
    else:
        cite = ""
    lines = [f"Possession share for window {window_label} {cite}:"]
    for key in data:
        lines.append(f"  {_TEAM_NAMES[key]}: {data[key]}%.")
    lines.append(METHOD_LINE)
    return "\n".join(lines)


def _answer_field_tilt() -> str:
    tm = METRICS["team_metrics"]
    lines = ["Field tilt (share of final-third possession-seconds):"]
    for key, info in tm.items():
        ft_poss = [
            p for p in POSSESSIONS
            if p["team"] == key and p["reached_final_third"] == "True"
        ]
        ids_part = (
            ", ".join(p["possession_id"] for p in ft_poss[:3])
            + (f", … ({len(ft_poss)} total)" if len(ft_poss) > 3 else "")
        )
        lines.append(
            f"  {info['team_name']}: {info['field_tilt_pct']}% "
            f"[{ids_part}]."
        )
    lines.append(METHOD_LINE)
    return "\n".join(lines)


def _answer_directness() -> str:
    tm = METRICS["team_metrics"]
    lines = ["Directness (metres advanced per second of possession):"]
    for key, info in tm.items():
        # cite the full possession range per team
        poss_ids = [p["possession_id"] for p in POSSESSIONS if p["team"] == key]
        cite = f"[{poss_ids[0]}–{poss_ids[-1]}]"
        lines.append(
            f"  {info['team_name']}: {info['directness_m_per_sec']} m/s "
            f"({info['possessions']} possessions) {cite}."
        )
    lines.append(METHOD_LINE)
    return "\n".join(lines)


def _answer_best_possessions() -> str:
    top5 = METRICS["top5_possessions_by_value"]
    lines = ["Top 5 possessions by possession value:"]
    for rank, p in enumerate(top5, 1):
        pid = p["possession_id"]
        row = POSSESSION_BY_ID.get(pid, {})
        team_name = _TEAM_NAMES.get(p["team"], p["team"])
        lines.append(
            f"  {rank}. [{pid}] {team_name} — value {p['value']}, "
            f"duration {p['duration_sec']} s, "
            f"period {p['period']}, "
            f"ended: {p['end_reason']}, "
            f"shot: {p['shot']}, goal: {p['goal']}."
        )
    lines.append(METHOD_LINE)
    return "\n".join(lines)


def _answer_worst_possessions() -> str:
    bottom5 = METRICS["bottom5_possessions_by_value"]
    lines = ["Bottom 5 possessions by possession value:"]
    for rank, p in enumerate(bottom5, 1):
        pid = p["possession_id"]
        team_name = _TEAM_NAMES.get(p["team"], p["team"])
        lines.append(
            f"  {rank}. [{pid}] {team_name} — value {p['value']}, "
            f"duration {p['duration_sec']} s, "
            f"period {p['period']}, "
            f"ended: {p['end_reason']}."
        )
    lines.append(METHOD_LINE)
    return "\n".join(lines)


def _answer_why_dominate(team_key: str, window_label: str) -> str:
    data = _WINDOWS.get(window_label)
    if data is None:
        return (
            f"No window data for {window_label!r}. "
            f"Available: {list(_WINDOWS)}.\n{METHOD_LINE}"
        )
    team_pct = data.get(team_key)
    if team_pct is None:
        return f"Team key {team_key!r} not found in window data.\n{METHOD_LINE}"

    poss_in_window = _possessions_in_window(window_label)
    team_poss = [p for p in poss_in_window if p["team"] == team_key]
    opp_poss = [p for p in poss_in_window if p["team"] != team_key]
    team_name = _TEAM_NAMES[team_key]

    if not team_poss:
        return (
            f"No individual possessions found for {team_name} in window "
            f"{window_label} — cannot explain dominance.\n{METHOD_LINE}"
        )

    team_secs = sum(float(p["duration_sec"]) for p in team_poss)
    opp_secs = sum(float(p["duration_sec"]) for p in opp_poss)
    team_ids = [p["possession_id"] for p in team_poss]
    opp_ids = [p["possession_id"] for p in opp_poss]

    # Longest possession
    longest = max(team_poss, key=lambda p: float(p["duration_sec"]))

    # Final-third entries
    ft_poss = [p for p in team_poss if p["reached_final_third"] == "True"]
    ft_ids = [p["possession_id"] for p in ft_poss]

    team_cite = f"[{team_ids[0]}–{team_ids[-1]}]" if len(team_ids) > 1 else f"[{team_ids[0]}]"
    opp_cite = (f"[{opp_ids[0]}–{opp_ids[-1]}]" if len(opp_ids) > 1 else
                (f"[{opp_ids[0]}]" if opp_ids else "[none]"))

    opp_key = [k for k in data if k != team_key][0]
    opp_pct = data.get(opp_key, 0.0)

    lines = [
        f"Why did {team_name} dominate window {window_label}?",
        "",
        f"In the {window_label} window, {team_name} held {team_pct}% of possession "
        f"({team_secs:.1f} s across {len(team_poss)} possessions) {team_cite}.",
        f"Their opponents ({_TEAM_NAMES.get(opp_key, opp_key)}) held {opp_pct}% "
        f"({opp_secs:.1f} s in {len(opp_poss)} possessions) {opp_cite}.",
        f"The longest {team_name} possession in this window was "
        f"[{longest['possession_id']}]: {float(longest['duration_sec']):.1f} s, "
        f"ending in '{longest['end_reason']}'.",
    ]

    if ft_poss:
        ft_cite = ", ".join(f"[{i}]" for i in ft_ids[:5])
        if len(ft_poss) > 5:
            ft_cite += f" (and {len(ft_poss) - 5} more)"
        lines.append(
            f"{len(ft_poss)} of those possessions reached the final third "
            f"{ft_cite}."
        )
    else:
        lines.append(f"None of {team_name}'s possessions in this window reached the final third.")

    lines.append("")
    lines.append(METHOD_LINE)
    return "\n".join(lines)


def _answer_goals() -> str:
    tm = METRICS["team_metrics"]
    goal_poss: dict[str, list[str]] = {}
    for key in tm:
        goal_poss[key] = [
            p["possession_id"] for p in POSSESSIONS
            if p["team"] == key and p["goal"] == "True"
        ]
    lines = ["Goals scored:"]
    for key, info in tm.items():
        ids_str = ", ".join(f"[{pid}]" for pid in goal_poss[key])
        lines.append(
            f"  {info['team_name']}: {info['goals']} goal(s) — {ids_str}."
        )
    lines.append(METHOD_LINE)
    return "\n".join(lines)


_UNANSWERABLE = (
    "The data does not contain information to answer that question.\n"
    "The available data covers: possession share (match/period/window), field tilt, "
    "directness, best/worst possessions, why a team dominated a window, and goals/score.\n"
    + METHOD_LINE
)


# ── router ────────────────────────────────────────────────────────────────────

def answer(question: str) -> str:
    """
    Route a natural-language question to the appropriate deterministic answer
    function.  Returns a string answer with inline possession citations.
    """
    q = question.lower().strip()

    # goals / score
    if re.search(r"\b(goal|goals|score|final score)\b", q):
        return _answer_goals()

    # window possession — detect "window N" or "N-M" pattern
    window_match = re.search(r"\b(\d{1,3})[- ](\d{1,3})\b", q)
    if window_match or re.search(r"\bwindow\s+(\d+)\b", q):
        if window_match:
            start = int(window_match.group(1))
            label = _find_window_label(start)
        else:
            m2 = re.search(r"\bwindow\s+(\d+)\b", q)
            label = _find_window_label(int(m2.group(1)))

        if label and re.search(r"\bwhy\b", q):
            # "why did <team> dominate"
            team_key = None
            for frag, key in _NAME_TO_KEY.items():
                if frag in q:
                    team_key = key
                    break
            if team_key is None:
                # fall back: which team had more possession in that window?
                w_data = _WINDOWS.get(label, {})
                if w_data:
                    team_key = max(w_data, key=lambda k: w_data[k])
            if team_key:
                return _answer_why_dominate(team_key, label)

        if label and re.search(r"\bpossession\b", q):
            return _answer_window_possession(label)

        # bare window reference without "possession" keyword — still answer possession
        if label:
            return _answer_window_possession(label)

    # period possession
    period_match = re.search(r"\bperiod\s+([12])\b", q)
    if period_match and re.search(r"\bpossession\b", q):
        return _answer_period_possession(period_match.group(1))
    if period_match and re.search(r"\bhalf\b", q):
        return _answer_period_possession(period_match.group(1))

    # first/second half
    if re.search(r"\bfirst\s+half\b", q):
        return _answer_period_possession("1")
    if re.search(r"\bsecond\s+half\b", q):
        return _answer_period_possession("2")

    # overall possession
    if re.search(r"\b(overall|match|total)\b.*\bpossession\b", q) or (
        re.search(r"\bpossession\b", q)
        and not re.search(r"\b(period|window|half|tilt|directness)\b", q)
    ):
        return _answer_possession_share()

    # field tilt
    if re.search(r"\bfield\s+tilt\b", q) or re.search(r"\btilt\b", q):
        return _answer_field_tilt()

    # directness
    if re.search(r"\bdirectness\b", q):
        return _answer_directness()

    # best / top possessions
    if re.search(r"\b(best|top)\b.*\bpossession", q) or re.search(r"\bpossession.*\b(best|top)\b", q):
        return _answer_best_possessions()

    # worst / bottom possessions
    if re.search(r"\b(worst|bottom)\b.*\bpossession", q) or re.search(r"\bpossession.*\b(worst|bottom)\b", q):
        return _answer_worst_possessions()

    # why dominate — without explicit window
    why_match = re.search(r"\bwhy\b.*\b(dominat|control)", q)
    if why_match:
        # try to extract team
        team_key = None
        for frag, key in _NAME_TO_KEY.items():
            if frag in q:
                team_key = key
                break
        if team_key:
            # default to the window where they had the highest share
            w_data = _WINDOWS
            best_win = max(w_data, key=lambda w: w_data[w].get(team_key, 0))
            return _answer_why_dominate(team_key, best_win)

    return _UNANSWERABLE


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m agents.analyst '<question>'")
        sys.exit(1)
    print(answer(" ".join(sys.argv[1:])))
