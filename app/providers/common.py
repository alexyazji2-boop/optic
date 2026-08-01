"""Helpers shared by more than one market-data provider adapter."""

from __future__ import annotations

from typing import List, Tuple

import numpy as np
import pandas as pd


def pick_swing_expiries(available: List[str], max_expiries: int) -> List[str]:
    """Span the swing horizon (roughly 1-16 weeks) instead of grabbing the N
    nearest listed dates — on a weekly-listed name, the N-nearest approach
    leaves nothing beyond three weeks out, the wrong tenor for a multi-week
    thesis. Shared so every provider selects expiries the same way.
    """
    if not available:
        return []
    today = pd.Timestamp.today().normalize()
    dated: List[Tuple[str, int]] = [(e, int((pd.Timestamp(e) - today).days)) for e in available]
    usable = [(e, d) for e, d in dated if d >= 2] or dated

    targets = [7, 21, 35, 60, 90, 120][:max_expiries]
    picked: List[str] = []
    for target in targets:
        candidate = min(usable, key=lambda pair: abs(pair[1] - target))[0]
        if candidate not in picked:
            picked.append(candidate)
    # Top up from the front of the curve if the name has few listed expiries.
    for exp, _ in usable:
        if len(picked) >= max_expiries:
            break
        if exp not in picked:
            picked.append(exp)
    return sorted(picked)[:max_expiries]


def clean_iv(chain: pd.DataFrame) -> pd.DataFrame:
    """Replace obviously-bad implied vols with a sane fallback.

    Illiquid strikes routinely report IV of 0 or >400% from any vendor; left
    alone, those poison every Black-Scholes greek computed for that contract.
    """
    if chain.empty or "iv" not in chain.columns:
        return chain
    chain = chain.copy()
    chain.loc[(chain["iv"] <= 0.01) | (chain["iv"] > 4.0), "iv"] = np.nan
    if "expiry" in chain.columns:
        chain["iv"] = chain.groupby("expiry")["iv"].transform(lambda s: s.fillna(s.median()))
    chain["iv"] = chain["iv"].fillna(chain["iv"].median()).fillna(0.35)
    return chain


def period_to_days(period: str) -> int:
    """Convert a yfinance-style period string ('2y', '6mo', '10d') to days."""
    period = (period or "1y").strip().lower()
    try:
        if period.endswith("mo"):
            return int(float(period[:-2]) * 30)
        if period.endswith("y"):
            return int(float(period[:-1]) * 365)
        if period.endswith("d"):
            return int(float(period[:-1]))
    except ValueError:
        pass
    return 365
