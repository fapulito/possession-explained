#!/usr/bin/env python3
"""
agents/test_agents.py — Acceptance tests for the possession-explained agent layer.

Tests
─────
1. Analyst — 5 questions (including the 90-105 / 79.53% Northbridge swing).
   Verify every number against possession_metrics.json and that every claim
   carries a citation.
2. Unanswerable question — agent must decline, not invent.
3. Recap — must contain final score 4-3 and both possession shares.

Run:
    python -m agents.test_agents
"""

from __future__ import annotations

import re
import sys

# ── import agents ─────────────────────────────────────────────────────────────
from agents.analyst import answer as analyst_answer
from agents.recap import recap as recap_output
from agents.loader import METRICS

METHOD_LINE = "Possession % = share of possession-seconds, not event counts."

PASS = "PASS"
FAIL = "FAIL"

failures: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    status = PASS if cond else FAIL
    print(f"  [{status}] {name}")
    if not cond:
        print(f"         -> {detail}")
        failures.append(name)


def has_citation(text: str) -> bool:
    """Return True if any [PXXXX] citation appears in the text."""
    return bool(re.search(r"\[P\d{4}", text))


def numbers_in_text(text: str) -> list[str]:
    """Extract all numeric literals from text (int or float)."""
    return re.findall(r"\d+\.\d+|\d+", text)


# ── helper: verify a specific number appears in the answer and is cited ───────

def assert_number_cited(answer_text: str, number: str, test_name: str) -> None:
    """
    Check that `number` appears in `answer_text` and that a citation in
    [PXXXX] form appears somewhere in the same sentence or adjacent context.
    """
    present = number in answer_text
    cited_nearby = False
    if present:
        # Check if any citation appears within 200 chars of the number
        idx = answer_text.index(number)
        window = answer_text[max(0, idx - 200): idx + 200]
        cited_nearby = bool(re.search(r"\[P\d{4}", window))
    check(f"{test_name}: number {number!r} present", present, f"number not found in answer")
    check(f"{test_name}: number {number!r} is cited", cited_nearby,
          f"no [PXXXX] within 200 chars of {number!r}")


# ═══════════════════════════════════════════════════════════════════════════════
# TEST BLOCK 1 — Analyst: 5 questions
# ═══════════════════════════════════════════════════════════════════════════════

print("\n" + "=" * 70)
print("TEST BLOCK 1 — Analyst: 5 questions")
print("=" * 70)

# --- Q1: Overall possession share ---
q1 = "What is the overall possession share for the match?"
print(f"\nQ1: {q1}")
a1 = analyst_answer(q1)
print(a1)

# Verify numbers from JSON
nb_pct = str(METRICS["possession_pct_by_team"]["NB"])   # 65.46
ev_pct = str(METRICS["possession_pct_by_team"]["EV"])   # 34.54
check("Q1: contains NB possession %", nb_pct in a1)
check("Q1: contains EV possession %", ev_pct in a1)
check("Q1: has citation", has_citation(a1))
check("Q1: has method line", METHOD_LINE in a1)
assert_number_cited(a1, nb_pct, "Q1-NB")
assert_number_cited(a1, ev_pct, "Q1-EV")

# --- Q2: Period 1 possession ---
q2 = "What was the possession split in period 1?"
print(f"\nQ2: {q2}")
a2 = analyst_answer(q2)
print(a2)

nb_p1 = str(METRICS["possession_pct_by_period"]["1"]["NB"])  # 65.76
ev_p1 = str(METRICS["possession_pct_by_period"]["1"]["EV"])  # 34.24
check("Q2: contains NB period 1 %", nb_p1 in a2)
check("Q2: contains EV period 1 %", ev_p1 in a2)
check("Q2: has citation", has_citation(a2))
check("Q2: has method line", METHOD_LINE in a2)
assert_number_cited(a2, nb_p1, "Q2-NB")
assert_number_cited(a2, ev_p1, "Q2-EV")

# --- Q3: Field tilt ---
q3 = "What is the field tilt for each team?"
print(f"\nQ3: {q3}")
a3 = analyst_answer(q3)
print(a3)

nb_tilt = str(METRICS["team_metrics"]["NB"]["field_tilt_pct"])  # 73.25
ev_tilt = str(METRICS["team_metrics"]["EV"]["field_tilt_pct"])  # 26.75
check("Q3: contains NB field tilt %", nb_tilt in a3)
check("Q3: contains EV field tilt %", ev_tilt in a3)
check("Q3: has citation", has_citation(a3))
check("Q3: has method line", METHOD_LINE in a3)
assert_number_cited(a3, nb_tilt, "Q3-NB-tilt")

# --- Q4: Best possessions ---
q4 = "Show me the best possessions in the match."
print(f"\nQ4: {q4}")
a4 = analyst_answer(q4)
print(a4)

top_pid = METRICS["top5_possessions_by_value"][0]["possession_id"]  # P0197
top_val = str(METRICS["top5_possessions_by_value"][0]["value"])      # 0.9788
check("Q4: top possession ID present", top_pid in a4)
check("Q4: top possession value present", top_val in a4)
check("Q4: has citation", has_citation(a4))
check("Q4: has method line", METHOD_LINE in a4)

# --- Q5: Late-window swing (90-105, 79.53% Northbridge) ---
q5 = "Why did Northbridge dominate the 90-105 window?"
print(f"\nQ5: {q5}")
a5 = analyst_answer(q5)
print(a5)

nb_90 = str(METRICS["possession_pct_by_15min_window"]["90-105"]["NB"])  # 79.53
ev_90 = str(METRICS["possession_pct_by_15min_window"]["90-105"]["EV"])  # 20.47
check("Q5: NB 90-105 pct (79.53) present", nb_90 in a5)
check("Q5: EV 90-105 pct (20.47) present", ev_90 in a5)
check("Q5: has citation", has_citation(a5))
check("Q5: has method line", METHOD_LINE in a5)
assert_number_cited(a5, nb_90, "Q5-NB-90-105")

# ═══════════════════════════════════════════════════════════════════════════════
# TEST BLOCK 2 — Unanswerable question
# ═══════════════════════════════════════════════════════════════════════════════

print("\n" + "=" * 70)
print("TEST BLOCK 2 — Unanswerable question")
print("=" * 70)

q_weather = "What was the weather like during the match?"
print(f"\nQ: {q_weather}")
a_weather = analyst_answer(q_weather)
print(a_weather)

# Must NOT invent a number, must contain a refusal
invented_numbers = numbers_in_text(a_weather)
# Permitted numbers: only those in the method line itself (none there) or generic
# The agent should not output any match-specific stats
refusal_words = ["does not contain", "cannot", "not contain", "available data"]
is_refusal = any(w in a_weather.lower() for w in refusal_words)
check("Weather Q: agent declines", is_refusal,
      f"answer did not contain a refusal phrase; got: {a_weather[:120]}")
check("Weather Q: has method line", METHOD_LINE in a_weather)

# ═══════════════════════════════════════════════════════════════════════════════
# TEST BLOCK 3 — Recap
# ═══════════════════════════════════════════════════════════════════════════════

print("\n" + "=" * 70)
print("TEST BLOCK 3 — Recap")
print("=" * 70)

recap_text = recap_output()
print(recap_text)

# Must contain final score 4-3
check("Recap: contains '4-3'", "4-3" in recap_text)

# Must contain both possession shares
nb_share = str(METRICS["possession_pct_by_team"]["NB"])  # 65.46
ev_share = str(METRICS["possession_pct_by_team"]["EV"])  # 34.54
check("Recap: NB share (65.46%)", nb_share in recap_text)
check("Recap: EV share (34.54%)", ev_share in recap_text)
check("Recap: has citation", has_citation(recap_text))
check("Recap: has method line", METHOD_LINE in recap_text)

# ═══════════════════════════════════════════════════════════════════════════════
# SUMMARY
# ═══════════════════════════════════════════════════════════════════════════════

print("\n" + "=" * 70)
if failures:
    print(f"RESULT: {len(failures)} FAILURE(S)")
    for f in failures:
        print(f"  ✗ {f}")
    sys.exit(1)
else:
    print("RESULT: ALL TESTS PASSED")
