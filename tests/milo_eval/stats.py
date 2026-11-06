"""Intervals for the evaluation's rates (Phase 13, directive 15 Part 9).

A pass rate from a small sample is a range, not a number. `wilson` gives the 95% Wilson score interval for k passes
in n trials; `zero_failure_upper` the bound on a failure rate when none was seen (the rule of three, 3/n at 95%,
exact here: 1 - 0.05 ** (1/n)); `needed_for_zero_failures` how many failure-free trials it takes to show a failure
rate below a target. Used by the reports so that "100%" from 15 cases is printed with what it can and cannot rule out.
"""
from __future__ import annotations

import math
from typing import Tuple

Z95 = 1.959963984540054


def wilson(k: int, n: int, z: float = Z95) -> Tuple[float, float]:
    """The 95% Wilson interval for a proportion k/n, as (low, high), each from 0 to 1."""
    if n <= 0:
        return (0.0, 1.0)
    p = k / n
    den = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (max(0.0, centre - half), min(1.0, centre + half))


def zero_failure_upper(n: int, confidence: float = 0.95) -> float:
    """The upper bound on a failure rate after n trials with no failure: 1 - (1 - confidence) ** (1 / n)."""
    return 1.0 if n <= 0 else 1 - (1 - confidence) ** (1 / n)


def needed_for_zero_failures(rate: float, confidence: float = 0.95) -> int:
    """Failure-free trials needed before the upper bound on the failure rate falls below `rate`."""
    return math.ceil(math.log(1 - confidence) / math.log(1 - rate))


def describe(k: int, n: int) -> str:
    lo, hi = wilson(k, n)
    return "{} of {} ({:.1f}%; 95% interval {:.1f}% to {:.1f}%)".format(k, n, 100 * k / n if n else 0, 100 * lo, 100 * hi)
