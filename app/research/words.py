"""Reader-facing words for the research framework's internal labels (advice policy, 2026-10-29).

The framework's labels drive its own logic and stay exactly as they are: "Avoid" is a
grade the caps work with, "Attractive" and "Fair" lift a long-term conviction. What
changes is how a reader is told them. "Avoid", "Not Investable" and "High Conviction"
read as instructions or endorsements, and "Attractive" as a recommendation; these words
say what the rules found instead.

static/v2/js/core/research-words.js holds the same three tables for the pages, and
tests/test_ai_policy.py keeps the two copies equal, because two records of one fact
drift.
"""

from __future__ import annotations

from typing import Optional

# The short form, for a tile's headline value.
SETUP_GRADE = {"S": "Grade S", "A": "Grade A", "B": "Grade B", "Avoid": "No setup"}

# A phrase that reads inside a sentence ("Quality and price together: strong on the long-term rules").
CONVICTION = {
    "High Conviction": "strong on the long-term rules",
    "Constructive": "positive on the long-term rules",
    "Neutral": "neutral on the long-term rules",
    "Weak Structure": "weak on the long-term rules",
    "Not Investable": "fails the long-term rules",
}

# The short form, for the price tile's headline value: what the valuation rules found, in plain words.
VALUATION = {"Attractive": "Cheap", "Fair": "Fair", "Full": "Full", "Stretched": "Expensive"}


def setup_grade(grade: Optional[str]) -> str:
    return SETUP_GRADE.get(str(grade or ""), str(grade or ""))


def conviction(label: Optional[str]) -> str:
    return CONVICTION.get(str(label or ""), str(label or "").lower())


def valuation(label: Optional[str]) -> str:
    return VALUATION.get(str(label or ""), str(label or ""))
