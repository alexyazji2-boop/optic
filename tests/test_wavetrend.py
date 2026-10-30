"""WaveTrend (app/analytics/wavetrend.py and GET /api/indicators/wavetrend/{ticker}): LazyBear's oscillator, its
crosses and divergences, and what followed them.

The values are checked against a case worked by hand and against an independent loop at the defaults; the signals
on series built to carry known crosses and a planted divergence, including that nothing is reported before the bar
that makes it known; the measurement on closes whose later changes are known in advance; and the route's answer
on a stubbed price feed, so nothing here reaches the network.
"""
import json
import math

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

import app.main as main
from app.analytics import wavetrend as wt

SIGNAL_IDS = ["strong_bullish_cross", "strong_bearish_cross", "bullish_divergence", "bearish_divergence"]


def _bars(ap, spread=1.0, start="2026-01-05"):
    """Daily bars whose typical price is `ap`: the high and the low a spread either side of the close."""
    idx = pd.date_range(start, periods=len(ap), freq="B", tz="America/New_York")
    close = pd.Series(ap, index=idx, dtype=float)
    return pd.DataFrame({"Open": close, "High": close + spread, "Low": close - spread, "Close": close,
                         "Volume": 1e6})


def _walk(n=600, seed=3):
    """A random walk with wicks, the same every run."""
    rng = np.random.default_rng(seed)
    close = 100 * np.exp(np.cumsum(rng.normal(0, 0.015, n)))
    wick = np.abs(rng.normal(0, 0.008, n))
    idx = pd.date_range("2023-01-02", periods=n, freq="B", tz="America/New_York")
    return pd.DataFrame({"Open": close, "High": close * (1 + wick), "Low": close * (1 - wick), "Close": close,
                         "Volume": 1e6}, index=idx)


# ------------------------------------------------------------------ values


def test_the_values_match_a_case_worked_by_hand():
    """Lengths 2, 2 and 2 (alpha 2/3) on seven bars whose typical prices are 10, 12, 11, 14, 13, 16, 15.

    esa, seeded at 10 and shown from the second bar: 34/3, 100/9, 352/27, 1054/81, 3646/243, 10936/729.
    d = EMA(|ap - esa|), seeded at 2/3 on the second bar, shown from the third: 8/27, 20/27, 62/243, 182/243,
    548/2187. ci = (ap - esa) / (0.015 d): -25, 260/3, -100/31, 24200/273, -50/137.
    wt1 = EMA(ci), seeded at -25, shown from the fourth bar: 445/9, then 2/3 ci + 1/3 the last.
    wt2 is the mean of the last two wt1, from the fifth bar.
    """
    s = wt.series(_bars([10, 12, 11, 14, 13, 16, 15]), channel_len=2, avg_len=2, ma_len=2)
    want_wt1 = [None, None, None, 445 / 9, 14.330943847072879, 63.873440378816724, 21.047837790505817]
    want_wt2 = [None, None, None, None, 31.887694145758662, 39.1021921129448, 42.46063908466127]
    for got, want in ((s["wt1"], want_wt1), (s["wt2"], want_wt2)):
        for g, w in zip(got.tolist(), want):
            assert (math.isnan(g) if w is None else g == pytest.approx(w, rel=1e-12))
    assert s["hist"].iloc[-1] == pytest.approx(21.047837790505817 - 42.46063908466127, rel=1e-12)


def _ema_loop(xs, n):
    """The textbook recursion, written out: seeded with the first value, alpha 2 / (n + 1), shown from the nth."""
    alpha, out, e, seen = 2.0 / (n + 1), [], None, 0
    for x in xs:
        if x is None:
            out.append(None)
            continue
        e = x if e is None else alpha * x + (1 - alpha) * e
        seen += 1
        out.append(e if seen >= n else None)
    return out


def test_the_defaults_agree_with_an_independent_loop():
    df = _walk(200)
    ap = ((df["High"] + df["Low"] + df["Close"]) / 3).tolist()
    esa = _ema_loop(ap, 9)
    d = _ema_loop([None if e is None else abs(a - e) for a, e in zip(ap, esa)], 9)
    ci = [None if dd is None else (a - e) / (0.015 * dd) for a, e, dd in zip(ap, esa, d)]
    w1 = _ema_loop(ci, 12)
    w2 = [None if i < 2 or None in w1[i - 2:i + 1] else sum(w1[i - 2:i + 1]) / 3 for i in range(len(w1))]
    s = wt.series(df)
    for got, want in ((s["wt1"], w1), (s["wt2"], w2)):
        for g, w in zip(got.tolist(), want):
            assert (math.isnan(g) if w is None else g == pytest.approx(w, rel=1e-9, abs=1e-9))


def test_a_constant_price_has_no_reading_and_no_infinity():
    """d == 0: there is no deviation to scale by. Every value is null rather than a division by zero (or the
    float noise an average of a constant leaves), there are no signals, and the answer is valid JSON, which
    FastAPI would refuse with a NaN or an infinity in it."""
    flat = _bars([101.37] * 120, spread=0.0)
    s = wt.series(flat)
    for k in ("wt1", "wt2", "hist"):
        assert not np.isinf(s[k]).any() and s[k].isna().all()
    out = wt.build(flat)
    assert out["available"] is True
    assert set(out["wt1"]) == set(out["wt2"]) == set(out["hist"]) == {None}
    assert out["crosses"] == [] and out["divergences"] == []
    assert [r["count"] for r in out["evidence"]["signals"]] == [0, 0, 0, 0]
    json.dumps(out, allow_nan=False)


def test_a_flat_start_reads_once_the_price_moves():
    df = pd.concat([_bars([50.0] * 40, spread=0.0, start="2025-01-01"),
                    _walk(200).set_index(pd.date_range("2025-02-26", periods=200, freq="B", tz="America/New_York"))])
    s = wt.series(df)
    assert not any(np.isinf(s[k]).any() for k in ("wt1", "wt2"))
    assert s["wt1"].iloc[:40].isna().all() and s["wt1"].iloc[-100:].notna().all()


@pytest.mark.parametrize("lengths", [(9, 12, 3), (10, 21, 4), (2, 2, 1)])
def test_the_warmup_bars_are_null_and_the_next_is_not(lengths):
    c, a, m = lengths
    out = wt.build(_walk(300), channel_len=c, avg_len=a, ma_len=m)
    n1 = 2 * c + a - 3
    n2 = n1 + m - 1
    assert out["warmup"] == {"wt1": n1, "wt2": n2}
    assert out["wt1"][:n1] == [None] * n1 and out["wt1"][n1] is not None
    assert out["wt2"][:n2] == [None] * n2 and out["wt2"][n2] is not None
    assert out["hist"][:n2] == [None] * n2 and out["hist"][n2] is not None


def test_too_few_bars_say_so():
    out = wt.build(_walk(25))
    assert out["available"] is False and "needs more than 30 bars" in out["reason"]


# ------------------------------------------------------------------ crosses


def test_crosses_on_a_series_with_known_ones():
    nan = float("nan")
    wt1 = pd.Series([nan, -70, -65, -50, -40, -45, 10, 55, 70, 50, 40, 60, 62, 61, 62, 60])
    wt2 = pd.Series([nan, -60, -68, -55, -42, -42, 5, 50, 60, 58, 45, 45, 62, 62.5, 62, 61])
    got = [(x["i"], x["type"], x["strong"]) for x in wt.crosses(wt1, wt2)]
    assert got == [
        (2, "bullish", True),     # up through WT2 at -68, beyond -53
        (5, "bearish", False),    # down through it at -42
        (6, "bullish", False),
        (9, "bearish", True),     # down through it at 58, beyond 53
        (11, "bullish", False),
        (13, "bearish", True),    # equal on bar 12, then through and below: one cross, where it came out
    ]                             # bars 14 and 15: met WT2 from below and turned back, a touch and no cross


def test_a_cross_on_the_level_is_strong_and_the_level_is_the_callers():
    wt1, wt2 = pd.Series([-60.0, -52.0]), pd.Series([-55.0, -53.0])
    assert wt.crosses(wt1, wt2) == [{"i": 1, "type": "bullish", "strong": True}]
    assert wt.crosses(wt1, wt2, oversold=-60.0) == [{"i": 1, "type": "bullish", "strong": False}]


def test_a_gap_in_the_reading_is_not_a_cross():
    nan = float("nan")
    assert wt.crosses(pd.Series([-5.0, nan, 5.0]), pd.Series([0.0, nan, 0.0])) == []


# --------------------------------------------------------------- divergences


def _wave(n, marks, base=-10.0, slope=15.0):
    """A WT2 flat at `base` with a tent at each (bar, value): a peak above it or a trough below."""
    v = np.full(n, base)
    for p, x in marks:
        tent = x - np.sign(x - base) * slope * np.abs(np.arange(n) - p)
        v = np.maximum(v, tent) if x > base else np.minimum(v, tent)
    return v


def _planted():
    """Peaks at bars 15 (70), 35 (55) and 55 (80) and troughs at 68 (-70) and 80 (-55). Price makes a higher high
    at 35 than at 15 and at 55 than at 35, and a lower low at 80 than at 68: a bearish divergence from 15 to 35
    (WT2's high is lower), none from 35 to 55 (both higher), and a bullish one from 68 to 80."""
    n = 90
    idx = pd.date_range("2026-01-05", periods=n, freq="B")
    highs, lows = np.full(n, 100.0), np.full(n, 90.0)
    highs[[15, 35, 55]] = [110.0, 115.0, 120.0]
    lows[[68, 80]] = [85.0, 80.0]
    df = pd.DataFrame({"High": highs, "Low": lows, "Close": (highs + lows) / 2}, index=idx)
    return df, pd.Series(_wave(n, [(15, 70), (35, 55), (55, 80), (68, -70), (80, -55)]), index=idx)


def test_a_planted_divergence_is_found_with_its_two_pivots():
    df, wave = _planted()
    assert wt.pivots(wave.to_numpy(), 5) == [15, 35, 55]
    assert wt.pivots(wave.to_numpy(), 5, high=False) == [68, 80]
    assert wt.divergences(df, wave, 5) == [
        {"type": "bearish", "from": 15, "to": 35, "known": 40},
        {"type": "bullish", "from": 68, "to": 80, "known": 85},
    ]


def test_a_divergence_is_not_reported_before_its_pivot_is_confirmed():
    """Cut the series at every bar: what is found is exactly what the whole series found and had confirmed by then.
    The bearish one appears at bar 40, five bars after its second pivot, and not at 39."""
    df, wave = _planted()
    full = wt.divergences(df, wave, 5)
    for t in range(len(wave)):
        assert wt.divergences(df.iloc[:t + 1], wave.iloc[:t + 1], 5) == [d for d in full if d["known"] <= t], t
    assert wt.divergences(df.iloc[:40], wave.iloc[:40], 5) == []
    assert [d["type"] for d in wt.divergences(df.iloc[:41], wave.iloc[:41], 5)] == ["bearish"]


def test_a_pivot_on_the_wrong_side_of_zero_pairs_with_nothing():
    df, _ = _planted()
    wave = pd.Series(_wave(90, [(15, 70), (35, -5)], base=-30.0), index=df.index)   # the second peak is below 0
    assert wt.pivots(wave.to_numpy(), 5) == [15, 35]
    assert wt.divergences(df, wave, 5) == []


def test_the_whole_answer_has_no_lookahead():
    """WT1 and WT2 only average what came before, and a signal is listed at the bar that makes it known, so the
    answer for the bars up to t is the full answer's for those bars."""
    df = _walk(600)
    full = wt.build(df)
    assert full["crosses"] and full["divergences"]
    for t in range(80, 600, 37):
        cut = wt.build(df.iloc[:t + 1])
        assert cut["wt2"] == full["wt2"][:t + 1]
        assert cut["crosses"] == [x for x in full["crosses"] if x["i"] <= t]
        assert cut["divergences"] == [d for d in full["divergences"] if d["confirmed"]["i"] <= t]


# ------------------------------------------------------------------ evidence


def _alternating(n=200):
    """Closes of 100 on even bars and 110 on odd ones: five bars on (odd), every even bar has risen 10% and every
    odd one fallen 1/11; ten and twenty bars on, nothing has moved."""
    return pd.Series([100.0 if i % 2 == 0 else 110.0 for i in range(n)])


def test_the_measurement_on_closes_whose_changes_are_known():
    evens = list(range(40, 120, 2))   # 40 entries, all on 100
    out = wt.evidence(_alternating(), {"strong_bullish_cross": evens, "bearish_divergence": evens[:5]}, start=30)
    rows = {r["id"]: r for r in out["signals"]}
    assert [r["id"] for r in out["signals"]] == SIGNAL_IDS
    up = rows["strong_bullish_cross"]["by_horizon"]
    assert up["5"]["n"] == 40 and up["5"]["hit_rate_pct"] == 100.0 and up["5"]["mean_pct"] == 10.0
    # the window is bars 30 to 194 for five bars on: 83 even bars up 10% and 82 odd ones down 1/11
    assert out["baseline"]["5"] == {"n": 165, "mean_pct": 0.51, "up_pct": 50.3, "down_pct": 49.7}
    assert up["5"]["baseline_mean_pct"] == 0.51 and up["5"]["baseline_hit_rate_pct"] == 50.3
    assert up["5"]["edge_pct"] == 9.49
    assert up["5"]["beats_random_pct"] == 100.0    # no draw of 40 bars from the window is all even
    assert up["10"]["mean_pct"] == 0.0 and up["10"]["hit_rate_pct"] == 0.0 and up["10"]["beats_random_pct"] == 0.0
    few = rows["bearish_divergence"]
    assert few["count"] == 5 and few["by_horizon"]["5"]["too_few"] is True
    assert few["by_horizon"]["5"]["mean_pct"] is None and few["by_horizon"]["5"]["hit_rate_pct"] is None
    assert rows["bullish_divergence"]["count"] == 0


def test_a_bearish_signal_hits_when_the_close_falls():
    odds = list(range(41, 121, 2))   # on 110, five bars on 100
    row = wt.evidence(_alternating(), {"strong_bearish_cross": odds}, start=30)["signals"][1]
    assert row["by_horizon"]["5"]["hit_rate_pct"] == 100.0 and row["by_horizon"]["5"]["mean_pct"] == -9.09
    assert row["by_horizon"]["5"]["baseline_hit_rate_pct"] == 49.7
    assert row["by_horizon"]["5"]["beats_random_pct"] == 100.0


def test_signals_too_near_the_end_are_counted_and_left_out_of_that_horizon():
    late = list(range(150, 200, 2)) + [10]   # bar 10 is before the window and is dropped
    row = wt.evidence(_alternating(), {"strong_bearish_cross": late}, start=30)["signals"][1]
    assert row["count"] == 25
    assert [row["by_horizon"][h]["n"] for h in ("5", "10", "20")] == [23, 20, 15]
    assert row["by_horizon"]["10"]["too_few"] is False and row["by_horizon"]["20"]["too_few"] is True


def test_the_random_draws_are_the_same_every_time():
    df = _walk(600)
    assert wt.build(df)["evidence"] == wt.build(df)["evidence"]


def test_each_signal_is_entered_where_it_became_known(monkeypatch):
    """The cross on its own bar; a divergence at the bar its second pivot was confirmed, never at the pivot."""
    seen = {}
    real = wt.evidence

    def spy(close, entries, start, *a, **k):
        seen.update(entries=entries, start=start)
        return real(close, entries, start, *a, **k)

    monkeypatch.setattr(wt, "evidence", spy)
    out = wt.build(_walk(600))
    xs, dv = out["crosses"], out["divergences"]
    assert seen["start"] == out["warmup"]["wt2"]
    assert seen["entries"]["strong_bullish_cross"] == [x["i"] for x in xs if x["strong"] and x["type"] == "bullish"]
    assert seen["entries"]["strong_bearish_cross"] == [x["i"] for x in xs if x["strong"] and x["type"] == "bearish"]
    for kind in ("bullish", "bearish"):
        assert seen["entries"][kind + "_divergence"] == [d["confirmed"]["i"] for d in dv if d["type"] == kind]
        assert all(d["confirmed"]["i"] == d["to"]["i"] + 5 for d in dv)


def test_the_finding_says_how_each_did_and_claims_nothing_it_did_not_measure():
    ev = wt.build(_walk(2500))["evidence"]
    assert ev["finding"].startswith("10 bars on, ")
    assert "random draws" in ev["finding"] and "\u2014" not in ev["finding"] + ev["method"]
    few = wt.evidence(_alternating(), {}, start=30)
    assert few["finding"] == ("Too few signals on these bars to measure any of them: each kind needs 20 with 10 bars "
                              "after them.")


# ------------------------------------------------------------------ the route


class _Feed:
    def __init__(self, frame):
        self.frame, self.calls = frame, []

    def history(self, symbol, period="2y", interval="1d"):
        self.calls.append(("history", symbol, period, interval))
        return self.frame

    def intraday_history(self, symbol, period="5d", interval="1m", prepost=False):
        self.calls.append(("intraday", symbol, period, interval, prepost))
        return self.frame


def _client(monkeypatch, frame, yahoo=None):
    feed, yf = _Feed(frame), _Feed(frame) if yahoo is None else yahoo
    monkeypatch.setattr(main, "PROVIDER", feed)
    monkeypatch.setattr(main, "YF_PROVIDER", yf)
    return TestClient(main.app), feed, yf


def test_the_route_answers_in_the_documented_shape(monkeypatch):
    client, feed, _ = _client(monkeypatch, _walk(600))
    r = client.get("/api/indicators/wavetrend/aapl")
    assert r.status_code == 200 and "NaN" not in r.text and "Infinity" not in r.text
    j = r.json()
    assert feed.calls == [("history", "AAPL", "10y", "1d")]   # ten years of daily bars unless the chart asks
    assert {"available", "ticker", "interval", "generated_at", "params", "levels", "warmup", "timestamps", "wt1",
            "wt2", "hist", "crosses", "divergences", "evidence", "name", "measures", "represents", "why",
            "caveat"} <= set(j)
    assert j["available"] is True and j["ticker"] == "AAPL" and j["interval"] == "1d" and j["name"] == "WaveTrend"
    assert len(j["timestamps"]) == len(j["wt1"]) == len(j["wt2"]) == len(j["hist"]) == 600
    assert j["timestamps"][:2] == ["2023-01-02", "2023-01-03"]
    assert j["params"] == {"channel_len": 9, "avg_len": 12, "ma_len": 3, "pivot_lookback": 5}
    assert j["levels"] == {"overbought": [53.0, 60.0], "oversold": [-53.0, -60.0]}
    assert j["wt1"][:27] == [None] * 27 and j["wt2"][:29] == [None] * 29 and j["wt2"][29] is not None
    for a, b, h in zip(j["wt1"], j["wt2"], j["hist"]):
        if a is not None and b is not None:
            assert h == pytest.approx(a - b, abs=0.011)
    assert j["crosses"] and any(x["strong"] for x in j["crosses"])
    for x in j["crosses"]:
        assert set(x) == {"i", "t", "type", "strong", "wt1", "wt2"} and x["type"] in ("bullish", "bearish")
        assert x["t"] == j["timestamps"][x["i"]]
    assert j["divergences"]
    for d in j["divergences"]:
        assert set(d) == {"type", "from", "to", "confirmed"} and d["type"] in ("bullish", "bearish")
        assert set(d["from"]) == set(d["to"]) == {"i", "t", "wt2", "price"}
        assert d["from"]["i"] < d["to"]["i"] and d["confirmed"]["i"] == d["to"]["i"] + 5
        assert d["confirmed"]["t"] == j["timestamps"][d["confirmed"]["i"]]
        assert (d["to"]["wt2"] > 0) == (d["type"] == "bearish")
    ev = j["evidence"]
    assert ev["horizons"] == [5, 10, 20] and ev["min_sample"] == 20 and ev["random_runs"] == 500
    assert [s["id"] for s in ev["signals"]] == SIGNAL_IDS and set(ev["baseline"]) == {"5", "10", "20"}
    assert ev["window"] == {"from": j["timestamps"][29], "to": j["timestamps"][-1], "bars": 571}
    for s in ev["signals"]:
        assert set(s["by_horizon"]) == {"5", "10", "20"}
        for m in s["by_horizon"].values():
            assert {"n", "too_few", "hit_rate_pct", "mean_pct", "baseline_hit_rate_pct", "baseline_mean_pct",
                    "edge_pct", "beats_random_pct"} == set(m)


def test_the_route_takes_its_lengths_levels_and_lookback(monkeypatch):
    client, _, _ = _client(monkeypatch, _walk(600))
    j = client.get("/api/indicators/wavetrend/AAPL", params={
        "channel_len": 10, "avg_len": 21, "ma_len": 4, "ob1": 40, "ob2": 70, "os1": -40, "os2": -70,
        "pivot_lookback": 3}).json()
    assert j["params"] == {"channel_len": 10, "avg_len": 21, "ma_len": 4, "pivot_lookback": 3}
    assert j["levels"] == {"overbought": [40.0, 70.0], "oversold": [-40.0, -70.0]}
    assert j["warmup"] == {"wt1": 38, "wt2": 41} and j["wt2"][40] is None and j["wt2"][41] is not None
    assert all(d["confirmed"]["i"] == d["to"]["i"] + 3 for d in j["divergences"])
    s = wt.series(_walk(600), 10, 21, 4)["wt2"]
    for x in j["crosses"]:
        assert x["strong"] == (s.iloc[x["i"]] <= -40 if x["type"] == "bullish" else s.iloc[x["i"]] >= 40)


@pytest.mark.parametrize("params", [{"channel_len": 1}, {"avg_len": 0}, {"ma_len": 0}, {"pivot_lookback": 0},
                                    {"ob1": -5}, {"os1": 5}, {"channel_len": "nine"}])
def test_the_route_refuses_parameters_out_of_range(monkeypatch, params):
    client, feed, _ = _client(monkeypatch, _walk(100))
    assert client.get("/api/indicators/wavetrend/AAPL", params=params).status_code == 422
    assert feed.calls == []


@pytest.mark.parametrize("params", [{"ob1": 70, "ob2": 60}, {"os1": -70, "os2": -60}])
def test_the_route_refuses_levels_in_the_wrong_order(monkeypatch, params):
    client, feed, _ = _client(monkeypatch, _walk(100))
    r = client.get("/api/indicators/wavetrend/AAPL", params=params)
    assert r.status_code == 400 and "outer" in r.json()["detail"] and feed.calls == []


def test_the_route_refuses_what_is_not_a_ticker_or_a_range(monkeypatch):
    client, feed, _ = _client(monkeypatch, _walk(100))
    assert client.get("/api/indicators/wavetrend/A$B").status_code == 400
    bad = client.get("/api/indicators/wavetrend/AAPL", params={"range": "7y"}).json()
    assert bad["available"] is False and bad["reason"].startswith("Unknown range '7y'")
    odd = client.get("/api/indicators/wavetrend/AAPL", params={"intraday": "7"}).json()
    assert odd["available"] is False and odd["reason"].startswith("Unknown intraday range '7'")
    assert feed.calls == []


def test_the_route_reads_the_bars_the_chart_drew(monkeypatch):
    """The same feed and frame /api/indicators reads for each chart: the brokerage feed for daily bars, Yahoo for
    All (`max`, which the brokerage feed would read as a year) and for intraday bars, weekly bars when asked."""
    hourly = _walk(300)
    hourly.index = pd.date_range("2026-06-01 09:30", periods=300, freq="60min", tz="America/New_York")
    client, feed, yf = _client(monkeypatch, _walk(400), yahoo=_Feed(hourly))
    j = client.get("/api/indicators/wavetrend/AAPL", params={"intraday": "60", "window": "6mo"}).json()
    assert yf.calls[-1] == ("intraday", "AAPL", "6mo", "60m", False)
    assert j["interval"] == "60m" and j["intraday"] == "60" and j["timestamps"][0] == "2026-06-01T09:30:00-04:00"
    assert client.get("/api/indicators/wavetrend/AAPL", params={"range": "max"}).json()["interval"] == "1d"
    assert yf.calls[-1] == ("history", "AAPL", "max", "1d")
    assert client.get("/api/indicators/wavetrend/AAPL", params={"weekly": "true", "range": "5y"}).json()["interval"] == "1wk"
    assert feed.calls[-1] == ("history", "AAPL", "5y", "1wk")


def test_the_route_says_when_there_are_no_bars(monkeypatch):
    client, _, _ = _client(monkeypatch, pd.DataFrame())
    assert client.get("/api/indicators/wavetrend/AAPL").status_code == 404
    j = client.get("/api/indicators/wavetrend/AAPL", params={"intraday": "5"}).json()
    assert j["available"] is False and j["reason"] == "No intraday bars came back for AAPL."
    short, _, _ = _client(monkeypatch, _walk(20))
    j = short.get("/api/indicators/wavetrend/AAPL").json()
    assert j["available"] is False and "needs more than 30 bars" in j["reason"]
