"""Pairs (app/analytics/pairs.py): the statistics on series with known answers,
and the rule on hand-made spreads."""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from app.analytics import pairs as pr

COST = pr.COST_BPS / 10000.0


def _walk(n, seed, sigma=0.01):
    rng = np.random.default_rng(seed)
    return np.cumsum(rng.normal(0, sigma, n))


def _ou(n, seed, phi=0.9, sigma=0.01):
    rng = np.random.default_rng(seed)
    x = np.zeros(n)
    for i in range(1, n):
        x[i] = phi * x[i - 1] + rng.normal(0, sigma)
    return x


def test_half_life_of_a_known_ar1():
    s = _ou(5000, 1, phi=0.9)
    assert pr.half_life(s) == pytest.approx(math.log(2) / -math.log(0.9), rel=0.15)


def test_a_cointegrated_pair_passes_and_a_pair_of_walks_does_not():
    lb = 4.0 + _walk(252, 2, sigma=0.03)
    la = 0.3 + 1.5 * lb + _ou(252, 3, phi=0.85)
    f = pr.fit(la, lb)
    assert f["beta"] == pytest.approx(1.5, abs=0.15)
    assert f["coint_level"] == 0.01
    walks = [pr.fit(4 + _walk(252, 100 + k), 4 + _walk(252, 200 + k))["coint_level"] for k in range(40)]
    # Two unrelated walks should pass at 5% about one time in twenty.
    assert sum(1 for lv in walks if lv is not None and lv <= 0.05) <= 6


def test_the_adf_statistic_tells_noise_from_a_walk():
    assert pr.adf_t(np.random.default_rng(4).normal(0, 1, 500)) < -10
    assert pr.adf_t(_walk(500, 5)) > -3.0
    assert pr.eg_level(-4.2) == 0.01 and pr.eg_level(-3.5) == 0.05 and pr.eg_level(-3.1) == 0.10
    assert pr.eg_level(-2.0) is None and pr.eg_level(None) is None


# A frozen fit with beta 1 and a spread sd of 1%, so log A - log B = z / 100.
FROZEN = {"alpha": 0.0, "beta": 1.0, "mean": 0.0, "sd": 0.01, "half_life": 10.0}


def _prices(zs):
    pb = np.full(len(zs), 100.0)
    pa = 100.0 * np.exp(np.asarray(zs) * 0.01)
    return pa, pb, ["2026-01-%02d" % (i + 1) for i in range(len(zs))]


def test_a_rich_leader_is_shorted_at_the_next_close_and_closed_when_it_comes_back():
    zs = [0, 1.0, 2.1, 1.5, 0.5, -0.1, 0.0, 0.0]
    pa, pb, dates = _prices(zs)
    t = pr.trade_window(pa, pb, dates, FROZEN, 0, len(zs), pr.params_for({}))
    assert len(t) == 1
    t = t[0]
    # Signal on the close of day 2, filled at day 3's close; exit signal on day
    # 5 (z crossed 0), filled at day 6's close.
    assert (t["entry_index"], t["exit_index"]) == (3, 6)
    assert t["side"] == "short A, long B" and t["exit_reason"] == "spread came back"
    ra = pa[6] / pa[3] - 1
    borrow = (1.0 / 2.0) * pr.BORROW_PCT / 100 / 252 * 3
    assert t["return_pct"] == pytest.approx((-ra / 2 - 2 * COST - borrow) * 100, abs=0.01)
    assert t["return_pct"] > 0


def test_a_laggard_is_bought_and_a_blowout_is_stopped():
    zs = [0, -2.2, -2.6, -3.5, -4.3, -4.5, -4.5]
    pa, pb, dates = _prices(zs)
    t = pr.trade_window(pa, pb, dates, FROZEN, 0, len(zs), pr.params_for({}))[0]
    assert t["side"] == "long A, short B"
    assert t["exit_reason"].startswith("stopped") and (t["entry_index"], t["exit_index"]) == (2, 5)
    assert t["return_pct"] < 0


def test_a_trade_that_never_reverts_gives_up_after_three_half_lives():
    zs = [0, 2.5] + [2.4] * 40
    pa, pb, dates = _prices(zs)
    f = dict(FROZEN, half_life=4.0)
    t = pr.trade_window(pa, pb, dates, f, 0, len(zs), pr.params_for({}))[0]
    assert t["exit_reason"] == "gave up after 12 sessions" and t["bars"] == 13


def test_an_open_trade_closes_with_its_window():
    zs = [0, 2.5, 2.4, 2.3]
    pa, pb, dates = _prices(zs)
    t = pr.trade_window(pa, pb, dates, FROZEN, 0, len(zs), pr.params_for({}))[0]
    assert t["exit_reason"] == "window ended" and t["exit_index"] == 3


def test_the_rule_reads_only_its_own_window_and_the_frozen_fit():
    zs = [0, 1.0, 2.1, 1.5, 0.5, -0.1, 0.0, 0.0]
    pa, pb, dates = _prices(zs + [9.0] * 5)
    t = pr.trade_window(pa, pb, dates, FROZEN, 0, len(zs), pr.params_for({}))
    assert len(t) == 1 and t[0]["exit_index"] == 6


def test_parameters_are_clamped_and_kept_in_order():
    p = pr.params_for({"entry_z": "9", "exit_z": "5", "stop_z": "1"})
    assert p["entry_z"] == 4.0 and p["exit_z"] < p["entry_z"] < p["stop_z"]


def _frame(close, start="2010-01-04", adj=None):
    idx = pd.bdate_range(start, periods=len(close))
    df = pd.DataFrame({"Close": close}, index=idx)
    if adj is not None:
        df["Adj Close"] = adj
    return df


def test_walk_forward_on_a_true_pair_trades_out_of_sample():
    n = 252 * 4
    lb = 4.0 + _walk(n, 7)
    la = 0.2 + 1.2 * lb + _ou(n, 8, phi=0.8, sigma=0.012)
    r = pr.run("AAA", "BBB", _frame(np.exp(la)), _frame(np.exp(lb)))
    assert r["available"]
    wf = r["walk_forward"]
    # Windows start after the first formation year and roll on by 126.
    assert wf["windows"][0]["from"] == r["history"]["from"] or len(wf["windows"]) >= 5
    assert len(wf["windows"]) == math.ceil((n - pr.FORMATION - 5) / pr.TRADE)
    assert wf["coint_share_pct"] == 100.0
    assert wf["all"]["trades"] >= 10 and wf["all"]["avg_trade_pct"] > 0
    assert r["now"]["coint_level"] is not None and r["now"]["beta"] == pytest.approx(1.2, abs=0.2)
    assert len(r["z_history"]) >= 100


def test_it_uses_dividend_adjusted_closes_when_there_are_any():
    n = 400
    a = np.exp(4 + _walk(n, 9))
    flat = _frame(np.full(n, 50.0), adj=a)
    r = pr.run("AAA", "BBB", flat, _frame(a * 1.01))
    # Adj Close is the walk, so the two legs are the same series and beta ~ 1.
    assert r["now"]["beta"] == pytest.approx(1.0, abs=0.01)


def test_refusals():
    df = _frame(np.full(100, 10.0))
    assert pr.run("A", "A", df, df)["available"] is False
    assert "shared sessions" in pr.run("A", "B", df, df)["reason"]


def test_the_random_baseline_takes_no_side():
    """Random days on the rule's own sides inherit its bet against a trending
    spread; the baseline flips a coin for each trade's side instead."""
    src = (pr.__file__ and open(pr.__file__).read())
    body = src[src.index("def _random_book("):src.index("def walk_forward(")]
    assert "side = 1 if rng.random() < 0.5 else -1" in body
    assert 't["side"]' not in body


def test_the_widget_is_wired():
    from pathlib import Path
    app = (Path(__file__).resolve().parent.parent / "static/app.js").read_text()
    assert "{ id: 'pairs', label: 'Pairs'," in app
    assert "if (id === 'pairs') return wsPairsHTML();" in app
    assert "if (on && id === 'pairs') loadPairs(STATE.chartSymbol);" in app
    assert "ctx.pairs = {" in app and "how_tested: r.method" in app
    assert "/api/pairs/${encodeURIComponent(sym)}/peers" in app


def test_a_negative_hedge_ratio_is_not_traded():
    f = dict(FROZEN, beta=-0.4)
    zs = [0, 1.0, 2.1, 1.5, 0.5, -0.1, 0.0, 0.0]
    pa, pb, dates = _prices(zs)
    assert pr.trade_window(pa, pb, dates, f, 0, len(zs), pr.params_for({})) == []
    n = 400
    up, down = np.exp(4 + np.linspace(0, 0.5, n)), np.exp(4 - np.linspace(0, 0.5, n) + _walk(n, 11, 0.002))
    r = pr.run("UPP", "DWN", _frame(up), _frame(down))
    assert r["now"]["beta"] < 0 and "opposite directions" in r["now"]["stance"]
