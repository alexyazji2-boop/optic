"""Candles and Fibonacci on every chart size under a day.

Reported as: candles do not work on any time frame under 1D, and neither does
Fibs. Both had one cause each. /api/intraday sent closes only, so the Candles
button was disabled on all eight intraday rungs; and the Fibonacci grid came
from the daily payload, anchored to a swing across months, so on intraday the
charts drew nothing at all when Fibs was on. The feed carried open, high and
low all along: measured on PLTR, every rung from 1m to 4h came back complete.
"""
from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

import app.main as main

ROOT = Path(__file__).resolve().parent.parent


def _strip(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.S)
    return re.sub(r"^\s*//.*$", " ", text, flags=re.M)


APP = _strip((ROOT / "static/app.js").read_text())


def _fn(name: str) -> str:
    body = APP[APP.index("function " + name + "("):]
    return body[:body.index("\n}") + 2]


class _Feed:
    def __init__(self, frame):
        self.frame, self.calls = frame, []

    def intraday_history(self, symbol, period="5d", interval="1m"):
        self.calls.append((symbol, period, interval))
        return self.frame


def _bars(highs, lows, closes=None, opens=None):
    n = len(highs)
    idx = pd.date_range("2026-09-25 09:30", periods=n, freq="5min", tz="America/New_York")
    closes = closes or [(h + l) / 2 for h, l in zip(highs, lows)]
    opens = opens or closes
    return pd.DataFrame({"Open": opens, "High": highs, "Low": lows, "Close": closes,
                         "Volume": [1000.0] * n}, index=idx)


def _get(monkeypatch, frame, rng="5"):
    monkeypatch.setattr(main, "YF_PROVIDER", _Feed(frame))
    return TestClient(main.app).get("/api/intraday/PLTR", params={"range": rng}).json()


# ------------------------------------------------------------------ OHLC


@pytest.mark.parametrize("rng", sorted(main.INTRADAY_SPECS))
def test_every_rung_sends_open_high_and_low_beside_the_close(monkeypatch, rng):
    body = _get(monkeypatch, _bars([11, 12, 13], [9, 10, 11], opens=[10, 11, 12]), rng)
    assert body["opens"] == [10, 11, 12]
    assert body["highs"] == [11, 12, 13]
    assert body["lows"] == [9, 10, 11]
    assert len(body["opens"]) == len(body["closes"]) == len(body["times"])


def test_a_missing_value_is_null_not_guessed(monkeypatch):
    """The chart leaves that one candle out; inventing a high from the close
    would draw a candle that never traded."""
    body = _get(monkeypatch, _bars([11, np.nan, 13], [9, 10, 11], closes=[10, 10.5, 12]))
    assert body["highs"] == [11, None, 13]
    assert body["closes"] == [10, 10.5, 12], "the bar itself stays"


def test_a_bar_with_no_close_takes_its_open_high_and_low_with_it(monkeypatch):
    """Skipping the close alone would slide every later candle a bar left."""
    frame = _bars([11, 12, 13], [9, 10, 11], closes=[10, np.nan, 12], opens=[10, 11, 12])
    body = _get(monkeypatch, frame)
    assert body["closes"] == [10, 12]
    assert body["opens"] == [10, 12]
    assert body["highs"] == [11, 13] and body["lows"] == [9, 11]


# ------------------------------------------------------------ Fibonacci


def test_the_grid_hangs_off_the_high_and_low_of_these_bars(monkeypatch):
    body = _get(monkeypatch, _bars([101, 104, 109, 106], [99, 100, 105, 103]))
    fib = body["fibonacci"]
    assert fib["anchor_high"] == 109 and fib["anchor_low"] == 99
    prices = sorted(lv["price"] for lv in fib["levels"] if "ext" not in lv["label"])
    assert prices[0] == pytest.approx(99) and prices[-1] == pytest.approx(109)


def test_a_high_after_the_low_is_an_up_leg(monkeypatch):
    """Retracements of an up leg sit under price, as support."""
    body = _get(monkeypatch, _bars([101, 104, 109, 108], [95, 100, 105, 104]))
    assert body["fibonacci"]["direction"] == "bullish"


def test_a_low_after_the_high_is_a_down_leg(monkeypatch):
    body = _get(monkeypatch, _bars([109, 104, 101, 102], [105, 100, 95, 97]))
    assert body["fibonacci"]["direction"] == "bearish"


def test_one_bar_is_no_grid_rather_than_an_error(monkeypatch):
    body = _get(monkeypatch, _bars([11], [9]))
    assert body["available"] is True and body["fibonacci"] == {}


def test_a_flat_window_is_no_grid_rather_than_a_divide_by_zero(monkeypatch):
    body = _get(monkeypatch, _bars([10, 10, 10], [10, 10, 10]))
    assert body["fibonacci"] == {}


# ------------------------------------------------------------ the client


def test_the_series_carries_ohlc_only_when_the_payload_does():
    fn = _fn("intradaySeries")
    assert "Array.isArray(intra.opens) && Array.isArray(intra.highs)" in fn
    assert "...(ohlc ? { open: intra.opens, high: intra.highs, low: intra.lows } : {})" in fn
    assert "fib: intra.fibonacci || null" in fn and "spot: intra.last" in fn


def test_the_candles_button_asks_the_bars_not_the_range():
    fn = _fn("wsCandlesPossible")
    assert "return !!(intra.opens && intra.highs && intra.lows);" in fn
    assert "if (isIntradayRange(chartRange)) return false;" not in fn


def test_the_disabled_button_no_longer_blames_the_feed():
    assert "The intraday feed sends closes only" not in APP


def test_both_charts_draw_the_intraday_grid_when_fibs_is_on():
    assert "refLines: intraday ? (showFib ? intradayFibLines(ps) : []) : [" in _fn("wsMountChart")
    swing = _fn("swingPriceBlock")
    assert "const overlayRefs = ps.intraday ? (showFib ? intradayFibLines(ps) : []) : [" in swing
    assert "showFib ? { name: 'Fibonacci level'" in swing, "the key must say so on intraday too"
    assert "showFib && !ps.intraday ? { name: 'Fibonacci level'" not in swing


def test_it_goes_through_the_shared_builder():
    """fibLines is the one place a level is coloured and labelled, for the
    Charting tab, the Options chart and the Investing chart alike."""
    assert "return fibLines(((ps && ps.fib) || {}).levels, ps && ps.spot);" in _fn("intradayFibLines")


def test_the_options_menu_lets_on_what_is_computed_on_these_bars():
    """Fibonacci, the averages and the clouds are computed on the intraday bars
    and are live there. Support, resistance, supply and demand and insider
    trades are read from daily bars and stay disabled; the note says which is
    which."""
    menu = APP[APP.index('data-level-opt="ma"'):]
    menu = menu[:menu.index("data-clear-levels")]

    def box(opt):
        part = menu[menu.index('data-level-opt="%s"' % opt):]
        return part[:part.index("</label>")]
    for live in ("fib", "ma", "ema", "cloud921", "cloud2150"):
        assert "ps.intraday ? 'disabled'" not in box(live), live
    for daily in ("sr", "zones", "insiders"):
        assert "ps.intraday ? 'disabled'" in box(daily), daily
    assert "Fibonacci levels come from the high and" in APP


def test_the_options_key_names_an_intraday_candle_a_bar_not_a_day():
    swing = _fn("swingPriceBlock")
    assert "ps.intraday ? 'Up bar' : ps.weekly ? 'Up week' : 'Up day'" in swing
    assert "ps.intraday ? 'Down bar' : ps.weekly ? 'Down week' : 'Down day'" in swing
