"""The S&P's daily move as its options price it, beside what the index does.

Asked for as "if not already implemented, use the ATR, calculating VIX/16 for
expected S&P volatility being price from its options". It was not: the
terminal priced an earnings move per ticker from its straddle and annualised
realised volatility, and never said what the VIX implies for a day.

VIX / 16 is the one-standard-deviation daily move (a year of about 252
trading days, whose square root is close to 16). The ATR is a range, which
runs about 1.6 times a close-to-close move, so the comparison divides it by
1.6 first; side by side unadjusted, a 0.9% ATR beside a 1.0% VIX/16 reads as
options pricing what the tape delivers when they price nearly twice.
"""
from __future__ import annotations

import pandas as pd
import pytest

from app.analytics import macro

ROOT_APP = open("static/app.js", encoding="utf-8").read()


def _spx(days=60, close=6000.0, spread=0.005):
    idx = pd.bdate_range("2026-06-01", periods=days, tz="America/New_York")
    c = pd.Series([close] * days, index=idx)
    return pd.DataFrame({"Open": c, "High": c * (1 + spread), "Low": c * (1 - spread),
                         "Close": c, "Volume": 1.0}, index=idx)


def _move(vix, frame=None, spot=6000.0):
    snaps = {"^VIX": {"last": vix}, "^GSPC": {"last": spot}}
    return macro._expected_move(snaps, {"^GSPC": _spx() if frame is None else frame})


def test_the_rule_of_16():
    em = _move(16.0)
    assert em["implied_pct"] == pytest.approx(1.0)
    assert em["implied_points"] == pytest.approx(60.0)


def test_the_atr_is_the_indexs_own_day_and_is_put_on_one_footing():
    em = _move(16.0)
    # Every day spans 1% of 6,000 high to low.
    assert em["atr14"] == pytest.approx(60.0) and em["atr_pct"] == pytest.approx(1.0)
    assert em["realized_pct"] == pytest.approx(1.0 / 1.6, abs=1e-3)
    assert em["ratio"] == pytest.approx(1.6, abs=0.01)
    assert em["reading"].startswith("Options are pricing about 1.6 times the movement")


def test_the_reading_turns_on_the_ratio():
    assert _move(8.0)["reading"] == "Options are pricing about the movement the index has been delivering."
    assert _move(6.0)["reading"].startswith("Options are pricing less movement")
    assert "dear" in _move(24.0)["reading"]


def test_nothing_to_say_without_the_inputs():
    assert macro._expected_move({"^GSPC": {"last": 6000.0}}, {"^GSPC": _spx()}) is None
    assert _move(16.0, frame=_spx(days=10)) is None
    assert macro._expected_move({"^VIX": {"last": 16.0}}, {}) is None


def test_it_is_on_the_payload_and_on_the_macro_tab():
    src = open("app/analytics/macro.py", encoding="utf-8").read()
    assert '"expected_move": _expected_move(snaps, frames),' in src
    body = ROOT_APP[ROOT_APP.index("function renderMarket(d) {"):]
    row_end = body.index("${macroExpectedMove(m.expected_move)}")
    assert body.index('<div class="grid c2 gap macro-row">') < row_end < body.index('<div id="rotation-host"')
    fn = ROOT_APP[ROOT_APP.index("function macroExpectedMove(em) {"):]
    fn = fn[:fn.index("\n}\n")]
    for words in ("Options price", "The S&P moves", "On one footing", "Why VIX ÷ 16."):
        assert words in fn, words
    assert "—" not in fn
