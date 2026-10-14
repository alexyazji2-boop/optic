"""The Chart tab's Backtest widget (app/analytics/backtest.py).

Built on synthetic bars where the right answer is known, then the reporting
rules: buy and hold beside every result, random entries with the same
exposure, next-bar fills, costs, split-adjusted intraday bars."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from app.analytics import backtest as bt

ROOT = Path(__file__).resolve().parents[1]


def _frame(close, start="2018-01-01", freq="B"):
    close = np.asarray(close, dtype=float)
    idx = pd.date_range(start, periods=len(close), freq=freq)
    return pd.DataFrame({"Open": close, "High": close * 1.01, "Low": close * 0.99, "Close": close,
                         "Volume": 1e6}, index=idx)


def _wave(n=1500, period=60, drift=0.0, amp=0.15, seed=0):
    rng = np.random.default_rng(seed)
    t = np.arange(n)
    return 100 * np.exp(drift * t + amp * np.sin(2 * np.pi * t / period) + rng.normal(0, 0.002, n).cumsum() * 0.1)


def test_indicators_match_their_definitions():
    x = np.arange(1, 31, dtype=float)
    assert bt.sma(x, 5)[4] == pytest.approx(3.0) and np.isnan(bt.sma(x, 5)[3])
    e = bt.ema(x, 10)
    assert e[9] == pytest.approx(5.5) and e[10] == pytest.approx(2 / 11 * 11 + 9 / 11 * 5.5)
    r = bt.rsi(np.array([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16], dtype=float), 14)
    assert r[14] == pytest.approx(100.0)


def test_fills_are_at_the_next_bars_open_never_the_signal_bar():
    f = _frame(_wave())
    f["Open"] = f["Close"].shift(1).fillna(f["Close"]) * 1.003   # opens differ from closes
    r = bt.run(f, "macd_turn_below_zero", {"max_bars": 10})
    assert r["available"] and r["stats"]["trades"] > 5
    opens = f["Open"]
    for t in r["trades"][:5]:
        assert t["entry_price"] == pytest.approx(float(opens.loc[t["entry_date"]]), rel=1e-6)
        assert t["exit_price"] == pytest.approx(float(opens.loc[t["exit_date"]]), rel=1e-6)
    assert r["fill"].startswith("Signals on a completed bar, filled at the next bar's open")


def test_the_macd_rule_only_buys_below_zero_and_obeys_its_exits():
    f = _frame(_wave())
    r = bt.run(f, "macd_turn_below_zero", {"max_bars": 7})
    assert r["trades"]
    for t in r["trades"]:
        assert "below zero" in t["entry_reason"]
        assert t["bars"] <= 8, "the time stop fires on the 7th candle and fills on the next open"
    reasons = set(r["stats"]["exit_reasons"])
    assert reasons <= {"MACD crossed below its signal line", "50-day average crossed below the 200-day", "held 7 candles"}


def test_costs_reduce_every_trade():
    f = _frame(_wave())
    free = bt.run(f, "golden_cross", {"fast": 10, "slow": 30}, cost_bps=0)
    paid = bt.run(f, "golden_cross", {"fast": 10, "slow": 30}, cost_bps=50)
    assert [t["entry_date"] for t in free["trades"]] == [t["entry_date"] for t in paid["trades"]]
    for a, b in zip(free["trades"], paid["trades"]):
        assert b["return_pct"] < a["return_pct"]


def test_a_rule_on_a_stock_that_rose_is_measured_against_holding_it():
    rising = _frame(100 * np.exp(np.linspace(0, 2.5, 1500)))   # +1,118%, no dips
    r = bt.run(rising, "rsi_rebound", {})
    assert r["benchmark"]["buy_hold_return_pct"] > 1000
    assert r["stats"]["total_return_pct"] < r["benchmark"]["buy_hold_return_pct"]
    assert "Too few trades" in r["verdict"] or "worse than buying and holding" in r["verdict"]


def test_random_entries_are_seeded_and_use_the_rules_own_exposure():
    f = _frame(_wave(seed=3))
    a = bt.run(f, "macd_turn_below_zero", {})
    b = bt.run(f, "macd_turn_below_zero", {})
    assert a["benchmark"]["random_runs"] == bt.RANDOM_RUNS
    assert a["benchmark"]["beats_random_pct"] == b["benchmark"]["beats_random_pct"], "fixed seed"
    assert "holding periods" in a["benchmark"]["random_method"]


def test_the_window_starts_trading_at_its_start():
    f = _frame(_wave(n=2500))
    r = bt.run(f, "macd_turn_below_zero", {}, years=2)
    assert r["window"]["years"] == pytest.approx(2.0, abs=0.05)
    assert all(t["entry_date"] >= r["window"]["from"] for t in r["trades"])
    assert r["equity"][0]["strategy"] == 1.0 and r["equity"][0]["buy_hold"] == 1.0


def test_win_rate_carries_its_uncertainty():
    lo, hi = bt._wilson(14, 30)
    assert 28 < lo < 31 and 63 < hi < 65


def test_params_are_clamped_and_inconsistent_ones_repaired():
    p = bt.params_for("macd_turn_below_zero", {"fast": 40, "slow": 20, "max_bars": 99999, "exit_macd": "false"})
    assert p["fast"] < p["slow"] and p["max_bars"] == 500 and p["exit_macd"] is False


def test_intraday_bars_are_split_adjusted_and_bucketed_into_four_hours():
    idx = pd.date_range("2024-06-06 09:30", periods=7 * 3, freq="h", tz="America/New_York")
    idx = idx[(idx.hour >= 9) & (idx.hour <= 15)]
    price = np.where(idx < pd.Timestamp("2024-06-10", tz="America/New_York"), 1200.0, 120.0)
    df = pd.DataFrame({"Open": price, "High": price, "Low": price, "Close": price, "Volume": 100.0}, index=idx)
    adj = bt.intraday_frame(df, [{"date": "2024-06-10", "ratio": 10}])
    assert adj["Close"].max() == pytest.approx(120.0), "a 10-for-1 split is not a 90% fall"
    four = bt.intraday_frame(df, [{"date": "2024-06-10", "ratio": 10}], four_hour=True)
    days = sorted({d.date() for d in four.index})
    assert len(four) <= 2 * len(days)


def test_the_route_and_the_widget_are_wired():
    src = (ROOT / "app/main.py").read_text()
    assert '@app.get("/api/backtest/{ticker}")' in src and '@app.get("/api/backtest/strategies")' in src
    js = (ROOT / "static/app.js").read_text()
    assert "{ id: 'backtest', label: 'Backtest'" in js
    assert "if (id === 'backtest') return wsBacktestHTML();" in js
    assert ".concat(backtestMarkers(ps, d.ticker || STATE.chartSymbol))" in js
    assert "Buy and hold ${btSigned(bm.buy_hold_return_pct, 0)}" in js, "the benchmark is beside the return"
    assert "ctx.backtest = " in js
    from app import ai
    assert "`backtest` in CONTEXT is one rule replayed" in ai.SYSTEM_PROMPT


def test_routes_answer(monkeypatch):
    from fastapi.testclient import TestClient
    import app.main as m

    class P:
        def history(self, t, period="max", interval="1d"):
            return _frame(_wave())
    monkeypatch.setattr(m, "YF_PROVIDER", P())
    c = TestClient(m.app)
    cat = c.get("/api/backtest/strategies").json()
    assert {s["id"] for s in cat["strategies"]} >= {"macd_turn_below_zero", "golden_cross"}
    r = c.get("/api/backtest/TEST", params={"strategy": "macd_turn_below_zero", "max_bars": 20}).json()
    assert r["available"] and r["params"]["max_bars"] == 20 and r["ticker"] == "TEST"
    assert c.get("/api/backtest/TEST", params={"strategy": "nope"}).status_code == 422
