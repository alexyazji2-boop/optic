"""Implied correlation.

The estimate is an approximation of a licensed index, so the tests care most
about it never presenting itself as the real thing, and about failing loudly
when the basket stops representing the index.
"""
from __future__ import annotations

import pandas as pd
import pytest

from app.analytics import correlation as corr


class _P:
    def __init__(self, ivs, caps=None):
        self.ivs, self.caps = ivs, caps or {}

    def quote(self, s):
        return {"price": 100.0}

    def profile(self, s):
        return {"market_cap": self.caps.get(s)} if s in self.caps else {}

    def options_chain(self, s, max_expiries=4):
        iv = self.ivs.get(s)
        if iv is None:
            return pd.DataFrame()
        return pd.DataFrame({"strike": [98.0, 100.0, 102.0], "dte": [30, 30, 30],
                             "iv": [iv, iv, iv]})


def _ivs(index_iv, comp_iv):
    out = {corr.INDEX: index_iv}
    for s in corr.BASKET:
        out[s] = comp_iv
    return out


def test_identical_vols_imply_perfect_correlation():
    """If the index is exactly as volatile as its parts, nothing is cancelling."""
    r = corr.build(_P(_ivs(0.30, 0.30)))
    assert r["available"] is True
    assert r["implied_correlation"] == pytest.approx(1.0, abs=0.01)


def test_calmer_index_implies_lower_correlation():
    high = corr.build(_P(_ivs(0.25, 0.30)))["implied_correlation"]
    low = corr.build(_P(_ivs(0.15, 0.30)))["implied_correlation"]
    assert low < high


def test_arithmetic_matches_the_stated_identity():
    r = corr.build(_P(_ivs(0.15, 0.30)))
    assert r["implied_correlation"] == pytest.approx((0.15 ** 2) / (0.30 ** 2), abs=0.001)


def test_index_more_volatile_than_parts_is_flagged_as_strained():
    """The identity can exceed 1 when the basket misrepresents the index.

    That must surface rather than be silently clipped, because it means the
    reading should not be trusted that day.
    """
    r = corr.build(_P(_ivs(0.45, 0.30)))
    assert r["strained"] is True
    assert r["implied_correlation_raw"] > 1.0
    assert r["implied_correlation"] <= 1.0


def test_missing_index_chain_is_fatal_and_explained():
    ivs = _ivs(0.20, 0.30)
    ivs.pop(corr.INDEX)
    r = corr.build(_P(ivs))
    assert r["available"] is False
    assert corr.INDEX in r["reason"]


def test_too_few_components_refuses_to_estimate():
    ivs = {corr.INDEX: 0.20}
    for s in corr.BASKET[:3]:
        ivs[s] = 0.30
    r = corr.build(_P(ivs))
    assert r["available"] is False
    assert "fewer than five" in r["reason"]


def test_weighting_scheme_is_reported():
    """Cap-weighted and equal-weighted are different instruments."""
    equal = corr.build(_P(_ivs(0.15, 0.30)))
    assert equal["weighted_by"] == "equal weight"
    caps = {s: 1e12 for s in corr.BASKET}
    weighted = corr.build(_P(_ivs(0.15, 0.30), caps))
    assert weighted["weighted_by"] == "market cap"


def test_weights_sum_to_one_hundred():
    r = corr.build(_P(_ivs(0.15, 0.30)))
    assert sum(c["weight_pct"] for c in r["components"]) == pytest.approx(100.0, abs=0.5)


def test_method_disclaims_the_cboe_index():
    r = corr.build(_P(_ivs(0.15, 0.30)))
    assert "not CBOE" in r["method"]
    assert "approximation" in r["method"].lower()


def test_absurd_ivs_are_rejected_rather_than_scored():
    ivs = _ivs(0.15, 0.30)
    ivs["AAPL"] = 9.0        # 900% vol — a data error, not a market
    r = corr.build(_P(ivs))
    assert all(c["symbol"] != "AAPL" for c in r["components"])
