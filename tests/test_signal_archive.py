"""O3 (Options audit): Optic's own reads, kept as they stood, then tested.

The archive's rules (once a day, in session, never updated) and each test,
checked on synthetic markets where the answer is known: a score built to
predict returns must pass, a shuffled one must not, and below the minimums
nothing is reported but the counts."""
from __future__ import annotations

import random
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

import app.main as m
from app import signal_archive as sa

ROOT = Path(__file__).resolve().parents[1]
ET = sa.ET
OPEN = datetime(2026, 10, 13, 11, 0, tzinfo=ET)


def _gex(regime="positive", call=110.0, put=90.0):
    return {"regime": {"state": regime, "flip_point": 98.0},
            "totals": {"net_gex": 1e9},
            "levels": {"call_wall": {"strike": call}, "put_wall": {"strike": put}}}


def test_records_the_first_in_session_read_of_the_day_only():
    v = {"composite_score": 12.5, "stance": "leaning bullish", "components": {"technicals": 30}}
    strikes = [80, 85, 90, 95, 100, 105, 110, 115, 120]
    assert sa.record("aapl", 100.0, v, _gex(), strikes=strikes, iv30=25.0, now=OPEN)
    assert not sa.record("AAPL", 101.0, {"composite_score": -40}, _gex(), now=OPEN.replace(hour=14))
    got = [r for r in sa.reads() if r["symbol"] == "AAPL"]
    assert len(got) == 1 and got[0]["composite"] == 12.5 and got[0]["spot"] == 100.0
    assert got[0]["placebo"] == {"call": [120.0], "put": [80.0]}
    assert got[0]["regime"] == "positive" and got[0]["call_wall"] == 110.0


def test_nothing_is_recorded_outside_the_session():
    v = {"composite_score": 5}
    assert not sa.record("MSFT", 100.0, v, _gex(), now=OPEN.replace(hour=9, minute=35))
    assert not sa.record("MSFT", 100.0, v, _gex(), now=OPEN.replace(hour=16, minute=1))
    assert not sa.record("MSFT", 100.0, v, _gex(), now=datetime(2026, 10, 11, 12, tzinfo=ET))  # Sunday
    assert not sa.record("MSFT", None, v, _gex(), now=OPEN)


def test_reads_cannot_be_rewritten():
    sa.record("NVDA", 100.0, {"composite_score": 1}, _gex(), now=OPEN)
    with sqlite3.connect(sa.DB_PATH) as conn, pytest.raises(sqlite3.DatabaseError, match="immutable"):
        conn.execute("UPDATE reads SET composite = 99 WHERE symbol = 'NVDA'")


def test_placebo_strikes_are_two_steps_out_on_the_walls_side():
    ks = [90, 95, 100, 105, 110, 115, 120]
    assert sa.placebo_strikes(ks, 110.0, 100.0, True) == [120.0], "100 is not above the price"
    assert sa.placebo_strikes(ks, 115.0, 100.0, True) == [105.0]
    assert sa.placebo_strikes(ks, 95.0, 100.0, False) == []
    assert sa.placebo_strikes(ks, 100.0, 102.0, False) == [90.0]
    assert sa.placebo_strikes(ks, None, 100.0, True) == []


# ------------------------------------------------------------ synthetic market

def _market(n_names=12, n_days=40, signal=0.0, seed=1):
    """Daily bars for n names, and one read per name per day whose composite
    carries `signal` times the next 10 days' return plus noise."""
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2026-06-01", periods=n_days + 40)
    bars, rows = {}, []
    for j in range(n_names):
        r = rng.normal(0, 0.015, len(idx))
        close = 100 * np.exp(np.cumsum(r))
        hi = close * (1 + np.abs(rng.normal(0, 0.006, len(idx))))
        lo = close * (1 - np.abs(rng.normal(0, 0.006, len(idx))))
        sym = "S{}".format(j)
        bars[sym] = pd.DataFrame({"Open": close, "High": hi, "Low": lo, "Close": close}, index=idx)
        for i in range(25, 25 + n_days):
            fwd = close[i + 10] / close[i] - 1
            score = signal * fwd * 1000 + rng.normal(0, 10)
            rows.append({"symbol": sym, "day": idx[i].date().isoformat(), "spot": float(close[i]),
                         "composite": float(score), "stance": "leaning bullish" if score > 0 else "leaning bearish",
                         "macro_included": 0, "regime": "positive" if j % 2 else "negative", "iv30": 24.0,
                         "call_wall": float(round(close[i] * 1.02)), "put_wall": float(round(close[i] * 0.98)),
                         "placebo": {"call": [float(round(close[i] * 1.02)) + 2.0],
                                     "put": [float(round(close[i] * 0.98)) - 2.0]}})
    return rows, bars


def test_a_score_that_predicts_passes_and_beats_the_shuffle():
    rows, bars = _market(signal=1.0)
    got = sa.test_composite(rows, bars, random.Random(1))
    assert got["status"] == "tested"
    assert got["result"]["mean_rank_correlation"] > 0.3
    assert got["result"]["shuffled_as_good_pct"] < 1
    assert got["counts"]["observations"] >= sa.MINIMUMS["composite"]["observations"]


def test_a_score_of_noise_is_not_distinguishable_from_chance():
    rows, bars = _market(signal=0.0, seed=7)
    got = sa.test_composite(rows, bars, random.Random(2))
    assert got["status"] == "tested"
    assert abs(got["result"]["mean_rank_correlation"]) < 0.1
    assert got["result"]["shuffled_as_good_pct"] > 5


def test_below_the_minimum_only_counts_are_reported():
    rows, bars = _market(n_names=6, n_days=10, signal=1.0)
    got = sa.test_composite(rows, bars)
    assert got["status"] == "collecting" and got["result"] is None
    assert got["counts"]["days"] == 10 and got["since"] == rows[0]["day"]


def test_regime_moves_are_normalised_by_the_implied_move():
    rows, bars = _market(n_names=12, n_days=40)
    got = sa.test_regime(rows, bars)
    assert got["status"] == "tested"
    five = got["result"]["by_horizon"]["5d"]
    # Same random walk in both groups: no real difference.
    assert abs(five["difference_t"]) < 3
    # 1.5% daily vol against 24% IV: moves come in below the implied size.
    assert 0.5 < five["positive_mean_move_vs_implied"] < 1.5


def test_walls_are_compared_with_their_placebo_strikes():
    rows, bars = _market(n_names=12, n_days=40)
    got = sa.test_walls(rows, bars)
    assert got["status"] == "tested"
    r = got["result"]
    assert 0 <= r["wall_hold_pct"] <= 100 and 0 <= r["placebo_hold_pct"] <= 100
    # Nothing in a random walk knows where the wall is.
    assert abs(r["wall_hold_pct"] - r["placebo_hold_pct"]) < 15


def test_setups_are_measured_against_spy_over_the_same_candles():
    idx = pd.bdate_range("2026-06-01", periods=90)
    spy = pd.DataFrame({"Close": np.linspace(100, 110, 90)}, index=idx)
    obs = []
    for i in range(70):
        for h in sa.SETUP_HORIZONS:
            if i + h >= 90:
                continue
            spy_chg = (spy["Close"].iloc[i + h] / spy["Close"].iloc[i] - 1) * 100
            obs.append({"direction": "bull", "horizon": h, "trigger_day": str(idx[i].date()),
                        "observed_day": str(idx[i + h].date()), "change_pct": spy_chg + 1.0})
    got = sa.test_setups(obs, spy)
    assert got["status"] == "tested"
    ten = got["result"]["by_horizon"]["10 candles"]
    assert ten["mean_excess_pct"] == pytest.approx(1.0, abs=1e-6) and ten["beat_spy_pct"] == 100.0


def test_evaluate_fetches_no_prices_while_every_claim_is_collecting():
    calls = []
    out = sa.evaluate([], lambda syms: calls.append(syms) or {}, [])
    assert calls == []
    assert all(c["status"] == "collecting" for c in out["claims"].values())
    assert set(out["claims"]) == {"composite", "regime", "walls", "setups"}


def test_the_endpoint_answers_collecting_on_an_empty_archive(monkeypatch):
    monkeypatch.setattr(m, "_VALIDATION", {"at": 0.0, "body": None})
    monkeypatch.setattr(sa, "reads", lambda: [])
    got = TestClient(m.app).get("/api/validation").json()
    assert got["claims"]["composite"]["status"] == "collecting"
    assert "composite score" in got["method"]


def test_the_panels_never_imply_an_edge_meanwhile():
    js = (ROOT / "static" / "app.js").read_text()
    for slot in ("composite", "regime", "walls", "setups"):
        assert "trackRecordSlot('{}')".format(slot) in js
    assert "not yet shown to predict returns." in js
    assert "ctx.track_record = trackRecordContext();" in js
    src = (ROOT / "app" / "main.py").read_text()
    assert "signal_archive.record(" in src and '@app.get("/api/validation")' in src


def test_milo_is_told_the_reads_are_untested():
    from app import ai
    assert "have not been shown to predict returns" in ai.SYSTEM_PROMPT
    assert "track_record" in ai._ORDER_BASE
