"""The swing-setup engine: the rules, the candles they read and when.

Asked for as a scanner that finds explainable entry setups and raises alerts
for review, with the integrity of the calculation spelled out: completed
candles by default, only what was known at the signal's timestamp, pivots
usable only after their confirmation bars, no alert backdated to the pivot
candle, higher-timeframe filters on completed higher-timeframe candles, and
tests for "indicator calculations, crossover boundaries, Donchian exclusion of
the current bar, pivot confirmation timing, alert deduplication, and state
transitions". Each of those has a section here.
"""

from __future__ import annotations

import math
from datetime import date, datetime, timedelta, timezone

import numpy as np
import pandas as pd
import pytest

from app import session as session_mod
from app.analytics import setups as S
from app.analytics import technicals as T

ET = session_mod.ET


# ------------------------------------------------------------------ helpers

def frame(close, high=None, low=None, open_=None, volume=None, start="2024-01-02"):
    """Daily candles on the exchange's own calendar, naive dates like the
    batch download returns."""
    close = np.asarray(close, dtype=float)
    days = []
    d = date.fromisoformat(start)
    while session_mod.regular_close(d) is None:
        d += timedelta(days=1)
    for _ in range(len(close)):
        days.append(d)
        d = session_mod.next_trading_day(d)
    high = close + 0.5 if high is None else np.asarray(high, dtype=float)
    low = close - 0.5 if low is None else np.asarray(low, dtype=float)
    open_ = close if open_ is None else np.asarray(open_, dtype=float)
    volume = np.full(len(close), 1e6) if volume is None else np.asarray(volume, dtype=float)
    return pd.DataFrame({"Open": open_, "High": high, "Low": low, "Close": close,
                         "Volume": volume}, index=pd.DatetimeIndex(days))


def after(df):
    """A moment after the last candle's session has closed."""
    last = df.index[-1].date()
    return datetime(last.year, last.month, last.day, 21, 0, tzinfo=timezone.utc)


def bars_of(df):
    return S.daily_bars(df, after(df))


def walk(n=400, seed=7, drift=0.02, vol=1.0, base=100.0):
    rng = np.random.default_rng(seed)
    steps = rng.normal(drift, vol, n)
    close = base + np.cumsum(steps)
    close = np.maximum(close, 5.0)
    span = np.abs(rng.normal(0.0, vol * 0.8, n)) + 0.2
    high = close + span * rng.uniform(0.2, 1.0, n)
    low = close - span * rng.uniform(0.2, 1.0, n)
    open_ = low + (high - low) * rng.uniform(0.0, 1.0, n)
    volume = rng.uniform(5e5, 2e6, n)
    return frame(close, high, low, open_, volume)


def params(preset, **kw):
    return S.resolve_params(preset, kw)


# =========================================================== indicators

def test_sma_and_ema_are_the_charts_own():
    """"Closed above the 21 EMA" has to be a claim about the line the chart
    draws, so the engine's averages are technicals' averages."""
    c = walk(120)["Close"].to_numpy()
    assert np.allclose(S.ema(c, 21)[30:], T.ema(pd.Series(c), 21).to_numpy()[30:])
    assert np.allclose(S.sma(c, 50)[60:], T.sma(pd.Series(c), 50).to_numpy()[60:])
    assert np.isnan(S.sma(c, 50)[48]) and np.isfinite(S.sma(c, 50)[49])


def test_rsi_is_wilders_with_the_classic_seed_and_a_real_warm_up():
    """The textbook's worked example (44.34, 44.09, ...), worked by hand.

    The first fourteen changes gain 3.34 and lose 1.40, so the first averages
    are 0.238571 and 0.100000: RS 2.385714, RSI 70.464. References that print
    70.53 rounded the averages to 0.24 and 0.10 first. After that each average
    is (previous x 13 + this change) / 14: a 0.28 loss gives 66.249, then a
    0.03 gain 66.481."""
    c = np.array([44.34, 44.09, 44.15, 43.61, 44.33, 44.83, 45.10, 45.42, 45.84,
                  46.08, 45.89, 46.03, 45.61, 46.28, 46.28, 46.00, 46.03, 46.41,
                  46.22, 45.64])
    r = S.rsi(c, 14)
    assert np.all(np.isnan(r[:14])), "the warm-up is NaN, not a pinned 50"
    assert r[14] == pytest.approx(70.464, abs=0.002)
    assert r[15] == pytest.approx(66.249, abs=0.002)
    assert r[16] == pytest.approx(66.481, abs=0.002)


def test_rsi_of_the_mirrored_chart_is_100_minus_rsi():
    """What makes the bearish rules the bullish ones upside down."""
    c = walk(200)["Close"].to_numpy()
    a, b = S.rsi(c, 14), S.rsi(-c, 14)
    ok = np.isfinite(a)
    assert np.allclose(a[ok] + b[ok], 100.0)


def test_stochastic_is_lookback_then_k_then_d():
    """(lookback, %K smoothing, %D smoothing), each written out."""
    h = np.array([10, 11, 12, 13, 12, 11, 12, 13, 14, 15], dtype=float)
    l = h - 2.0
    c = h - 0.5
    k, d = S.stochastic(h, l, c, 3, 1, 1)
    # Bar 2: highest high of bars 0-2 is 12, lowest low 8. (11.5 - 8) / 4.
    assert k[2] == pytest.approx(100.0 * 3.5 / 4.0)
    assert np.isnan(k[1]), "fewer than `lookback` bars has no value"
    ks, ds = S.stochastic(h, l, c, 3, 2, 3)
    assert ks[3] == pytest.approx((k[2] + k[3]) / 2.0)
    assert ds[5] == pytest.approx((ks[3] + ks[4] + ks[5]) / 3.0)


def test_bollinger_and_keltner_formulas():
    df = walk(80)
    b = bars_of(df)
    up, mid, lo = S.bollinger(b.c, 20, 2.0)
    window = b.c[40:60]
    assert mid[59] == pytest.approx(window.mean())
    assert up[59] == pytest.approx(window.mean() + 2.0 * window.std(ddof=0))
    ku, km, kl = S.keltner(b.h, b.l, b.c, 20, 1.5, 20)
    ref = T.atr(pd.DataFrame({"High": b.h, "Low": b.l, "Close": b.c}), 20).to_numpy()
    assert ku[70] - km[70] == pytest.approx(1.5 * ref[70])
    assert km[70] == pytest.approx(T.ema(pd.Series(b.c), 20).to_numpy()[70])


def test_anchored_vwap_from_the_anchor_on():
    h = np.array([11, 12, 13, 14], dtype=float)
    l = h - 2
    c = h - 1
    v = np.array([100, 200, 300, 400], dtype=float)
    av = S.anchored_vwap(h, l, c, v, 1)
    assert np.isnan(av[0])
    tp = (h + l + c) / 3
    assert av[1] == pytest.approx(tp[1])
    assert av[3] == pytest.approx((tp[1] * 200 + tp[2] * 300 + tp[3] * 400) / 900)


# =================================================== crossover boundaries

def test_equality_now_is_not_a_cross_and_equality_before_counts():
    a = np.array([1.0, 2.0, 3.0, 3.0, 4.0])
    b = np.array([2.0, 2.0, 3.0, 3.5, 3.5])
    out = S.cross_above(a, b)
    # t=1: 2 vs 2 is not above. t=2: 3 vs 3 still not above. t=4: 4 > 3.5 after 3 <= 3.5.
    assert out.tolist() == [False, False, False, False, True]
    # Equality on the bar before counts as "at or below".
    assert S.cross_above(np.array([2.0, 2.5]), np.array([2.0, 2.0])).tolist() == [False, True]
    assert S.cross_above(np.array([np.nan, 3.0]), np.array([2.0, 2.0])).tolist() == [False, False]


# ================================================= donchian and the current bar

def test_a_breakout_is_against_the_bars_before_not_against_itself():
    """A close above the highest high of the preceding N bars, this bar
    excluded. Including it, no close could ever exceed the channel: a bar's
    close is never above its own high."""
    close = np.full(40, 100.0)
    high = np.full(40, 101.0)
    close[35], high[35] = 101.5, 102.0
    top, _bottom = S.prior_channel(high, close - 1, 20)
    assert top[35] == pytest.approx(101.0), "bar 35's own high is not in its channel"
    assert top[36] == pytest.approx(102.0)
    df = frame(close, high=high, low=close - 1.0)
    out = S.analyse("X", df, None, presets=["donchian_20"], directions=["bull"],
                    overrides={"*": {"htf_filter": False}}, now=after(df))
    row = out["rows"][0]
    assert row["status"] == "triggered" and row["trigger"]["stamp"] == out["recent_stamps"][-5]
    assert row["trigger_level"] == pytest.approx(101.0)


# ================================================== pivots and their timing

def test_a_pivot_is_usable_only_after_its_confirmation_bars():
    h = np.array([1, 2, 3, 9, 3, 2, 1, 1, 1, 1], dtype=float)
    l = h - 0.5
    highs, _ = S.confirmed_pivots(h, l, 2, 3)
    assert highs == [3]
    # From a series that ends one bar short of confirmation, it does not exist.
    short, _ = S.confirmed_pivots(h[:6], l[:6], 2, 3)
    assert short == []
    ready, _ = S.confirmed_pivots(h[:7], l[:7], 2, 3)
    assert ready == [3]


def _fib_bars():
    """A clean impulse up from a swing low, then a pullback into the golden
    zone and a reclaim. Built bar by bar so the pivots are unambiguous."""
    close = list(np.linspace(100, 100, 60))
    close += list(np.linspace(100, 90, 10))           # down into a swing low
    close += list(np.linspace(91, 140, 25))           # the impulse up
    # Swing low 89.4, swing high 140.6: the 0.618 edge is 108.96 and the 0.65
    # one 107.32. The pullback ends at 107.9, inside the zone.
    close += list(np.linspace(139, 107.9, 15))
    close += [109.6, 110.8, 111.5]                    # the reclaim, then follow-through
    c = np.array(close)
    h, l = c + 0.6, c - 0.6
    o = c + 0.2                                        # down candles on the way down
    o[-3:] = c[-3:] - 0.4                              # up candles once it turns
    return frame(c, h, l, o)


def test_fibonacci_anchors_wait_for_confirmation_and_never_backdate():
    df = _fib_bars()
    p = params("fib_zone", htf_filter=False)
    b = bars_of(df)
    ind = S.Indicators(b)
    det = S.detect_fib(ind, p, S.Words(True))
    highs, lows = ind.pivots(p["pivot_left"], p["pivot_right"])
    top_i = max(highs)
    # Before the high is confirmed there is no grid to measure from.
    for t in range(top_i, top_i + p["pivot_right"]):
        assert det.anchors(t) == [] or det.anchors(t)[1]["index"] != top_i
    events, state, inst = S.lifecycle(b, det, np.ones(len(b), dtype=bool), p)
    fired = [e for e in events if e["type"] == "triggered"]
    assert fired, "the reclaim of the golden zone should trigger"
    assert fired[-1]["index"] > top_i + p["pivot_right"], "a signal before the anchor existed"
    assert fired[-1]["stamp"] == b.stamps[fired[-1]["index"]], "stamped on its own candle"


def test_touching_the_zone_alone_does_not_trigger():
    df = _fib_bars()
    cut = df.iloc[:-3]                                # the touch, without the reclaim
    out = S.analyse("X", cut, None, presets=["fib_zone"], directions=["bull"],
                    overrides={"*": {"htf_filter": False}}, now=after(cut))
    assert out["rows"][0]["status"] in ("armed", "watching")
    assert out["rows"][0]["trigger"] is None


# ======================================================== no look-ahead

@pytest.mark.parametrize("preset", [p["id"] for p in S.PRESETS])
@pytest.mark.parametrize("direction", ["bull", "bear"])
def test_no_rule_reads_a_candle_from_after_its_own(preset, direction):
    """Every array a rule produces at bar t is the same whether or not the
    candles after t exist. One test for indicators, pivots, anchors and levels
    together, because a look-ahead anywhere shows up here."""
    df = walk(330, seed=11)
    full = bars_of(df)
    bull = direction == "bull"
    p = params(preset, htf_filter=False)
    w = S.Words(bull)

    def run(b):
        b = b if bull else b.mirrored()
        return S.DETECTORS[preset](S.Indicators(b), p, w)

    whole = run(full)
    for t in range(150, 330, 23):
        part = run(S.daily_bars(df.iloc[:t + 1], after(df.iloc[:t + 1])))
        for name in ("arm", "trigger"):
            assert bool(getattr(part, name)[t]) == bool(getattr(whole, name)[t]), (name, t)
        for name in ("trigger_level", "stop", "arm_stop"):
            a, b = getattr(part, name)[t], getattr(whole, name)[t]
            assert (np.isnan(a) and np.isnan(b)) or a == pytest.approx(b, rel=1e-9, abs=1e-9), (name, t)


def test_events_are_a_prefix_of_the_events_with_more_history():
    """No backdating: adding candles never changes or adds an event on a candle
    that already existed."""
    df = walk(330, seed=5)
    p = params("trend_pullback", htf_filter=False)
    full = bars_of(df)
    det = S.detect_trend_pullback(S.Indicators(full), p, S.Words(True))
    ev_full, _, _ = S.lifecycle(full, det, np.ones(len(full), dtype=bool), p)
    for t in (200, 260, 300):
        part = S.daily_bars(df.iloc[:t + 1], after(df.iloc[:t + 1]))
        dp = S.detect_trend_pullback(S.Indicators(part), p, S.Words(True))
        ev, _, _ = S.lifecycle(part, dp, np.ones(len(part), dtype=bool), p)
        assert ev == [e for e in ev_full if e["index"] <= t]


# ======================================================== completed candles

def test_todays_candle_is_left_out_until_the_close():
    df = walk(60)
    last = df.index[-1].date()
    before = datetime(last.year, last.month, last.day, 15, 59, tzinfo=ET)
    at_close = datetime(last.year, last.month, last.day, 16, 0, tzinfo=ET)
    b1 = S.daily_bars(df, before)
    b2 = S.daily_bars(df, at_close)
    assert len(b1) == len(df) - 1 and b1.forming["stamp"] == last.isoformat()
    assert len(b2) == len(df) and b2.forming is None


def test_a_half_day_closes_at_one():
    day = date(2026, 11, 27)                   # the day after Thanksgiving
    df = frame(np.linspace(100, 110, 30), start="2026-10-16")
    df = df[df.index.date <= day]
    assert df.index[-1].date() == day
    assert len(S.daily_bars(df, datetime(2026, 11, 27, 12, 59, tzinfo=ET))) == len(df) - 1
    assert len(S.daily_bars(df, datetime(2026, 11, 27, 13, 0, tzinfo=ET))) == len(df)


def test_the_week_in_progress_is_not_a_weekly_candle():
    df = frame(np.linspace(100, 130, 60), start="2026-06-01")
    b = bars_of(df)
    wk = S.weekly_context(b)
    last_day = date.fromisoformat(b.stamps[-1])
    nxt = session_mod.next_trading_day(last_day)
    same_week = (nxt - timedelta(days=nxt.weekday())) == (last_day - timedelta(days=last_day.weekday()))
    assert (wk.stamps[-1] != b.stamps[-1]) == same_week
    # Each bar reads only weeks that ended on or before it.
    for t in range(len(b)):
        j = wk.latest[t]
        if j >= 0:
            assert wk.stamps[j] <= b.stamps[t]


def test_good_friday_ends_the_week_on_thursday():
    df = frame(np.linspace(100, 110, 30), start="2026-03-02")
    df = df[df.index.date <= date(2026, 4, 2)]
    wk = S.weekly_context(bars_of(df))
    assert wk.stamps[-1] == "2026-04-02"


def test_the_trend_filter_ignores_the_forming_candle():
    df = walk(330, seed=3, drift=0.15)
    p = params("trend_pullback")
    b = bars_of(df)
    ctx = S.build_context(b, S.weekly_context(b), None, p, True, "SPY")
    wild = df.copy()
    wild.iloc[-1, wild.columns.get_loc("Close")] = 1.0     # today's print, still forming
    last = wild.index[-1].date()
    b2 = S.daily_bars(wild, datetime(last.year, last.month, last.day, 15, 0, tzinfo=ET))
    ctx2 = S.build_context(b2, S.weekly_context(b2), None, p, True, "SPY")
    assert ctx2.ok[-1] == ctx.ok[-2]


# ======================================================== the lifecycle

def _pullback_df():
    """An uptrend, a pullback to the 21 EMA on down candles, then a reclaim.

    Four down days of 1.6 from 211.6 take the close under the 21 EMA (about
    207.5) and leave it above the 50-day SMA (about 203), so the setup arms on
    the first touch and stays armed until the up candle that closes back over
    the EMA."""
    n = 280
    close = [100.0 + 0.4 * i for i in range(n)]
    for _ in range(4):                                  # the pullback
        close.append(close[-1] - 1.6)
    c = np.array(close + [0.0])
    e = S.ema(c[:-1], 21)
    c[-1] = e[-1] + 1.5                                 # closes back above the EMA
    o = c - 0.3
    o[n:-1] = c[n:-1] + 0.3                             # the pullback closes down
    h = np.maximum(o, c) + 0.4
    l = np.minimum(o, c) - 0.6
    l[-1] = e[-1] - 0.5                                 # traded through it
    o[-1] = e[-1] - 0.2
    return frame(c, h, l, o)


def test_watching_armed_triggered_on_the_reclaim():
    df = _pullback_df()
    out = S.analyse("X", df, None, presets=["trend_pullback"], directions=["bull"],
                    overrides={"*": {"htf_filter": False}}, now=after(df))
    row = out["rows"][0]
    assert row["status"] == "triggered", row["explanation"]
    assert row["trigger"]["stamp"] == out["as_of"]
    assert row["armed_at"] < row["trigger"]["stamp"]
    assert "21 EMA" in row["explanation"] and row["explanation"].startswith("Daily candle")
    assert row["key"] == "setup:X:trend_pullback:bull:daily:" + out["as_of"]


def test_a_close_beyond_the_level_invalidates_a_signal():
    df = _pullback_df()
    p = params("trend_pullback", htf_filter=False)
    b = bars_of(df)
    det = S.detect_trend_pullback(S.Indicators(b), p, S.Words(True))
    events, state, inst = S.lifecycle(b, det, np.ones(len(b), dtype=bool), p)
    assert state == "triggered"
    stop = inst["stop"]
    extra = df.iloc[-1:].copy()
    extra.index = pd.DatetimeIndex([session_mod.next_trading_day(df.index[-1].date())])
    extra["Close"] = stop - 1.0
    extra["Low"] = stop - 1.5
    extra["Open"] = stop
    extra["High"] = stop + 0.5
    df2 = pd.concat([df, extra])
    b2 = bars_of(df2)
    det2 = S.detect_trend_pullback(S.Indicators(b2), p, S.Words(True))
    ev2, state2, _ = S.lifecycle(b2, det2, np.ones(len(b2), dtype=bool), p)
    assert state2 == "watching" and ev2[-1]["type"] == "invalidated"
    assert ev2[-1]["of"] == "signal" and ev2[-1]["index"] == len(b2) - 1


def test_an_armed_setup_expires_and_needs_a_fresh_setup_to_arm_again():
    n = 40
    b = S.Bars([str(i) for i in range(n)], [None] * n, np.zeros(n), np.ones(n), -np.ones(n),
               np.zeros(n), np.ones(n))
    arm = np.zeros(n, dtype=bool)
    arm[5:30] = True                                    # a setup that is a state
    det = S.Detection(np.ones(n, dtype=bool), arm, np.zeros(n, dtype=bool), S._nan(n),
                      S._nan(n), S._nan(n))
    p = params("trend_pullback")
    events, state, _ = S.lifecycle(b, det, np.ones(n, dtype=bool), p)
    kinds = [(e["type"], e["index"]) for e in events]
    assert kinds[0] == ("armed", 5)
    assert kinds[1] == ("expired", 5 + p["arm_expiry"])
    assert all(k != "armed" for k, i in kinds[2:] if i < 30), "re-armed on the same stale state"


def test_a_trigger_is_never_lost_to_the_re_arm_rule():
    n = 40
    b = S.Bars([str(i) for i in range(n)], [None] * n, np.zeros(n), np.ones(n), -np.ones(n),
               np.zeros(n), np.ones(n))
    arm = np.zeros(n, dtype=bool)
    arm[5:30] = True
    trig = np.zeros(n, dtype=bool)
    trig[20] = True
    det = S.Detection(np.ones(n, dtype=bool), arm, trig, np.zeros(n), np.full(n, -5.0), S._nan(n))
    events, state, inst = S.lifecycle(b, det, np.ones(n, dtype=bool), params("trend_pullback"))
    assert ("triggered", 20) in [(e["type"], e["index"]) for e in events]


def test_context_gates_both_arming_and_triggering():
    n = 30
    b = S.Bars([str(i) for i in range(n)], [None] * n, np.zeros(n), np.ones(n), -np.ones(n),
               np.zeros(n), np.ones(n))
    arm = np.zeros(n, dtype=bool)
    arm[10] = True
    trig = np.zeros(n, dtype=bool)
    trig[12] = True
    det = S.Detection(np.ones(n, dtype=bool), arm, trig, np.zeros(n), np.full(n, -5.0), S._nan(n))
    ctx = np.ones(n, dtype=bool)
    ctx[12] = False
    events, _, _ = S.lifecycle(b, det, ctx, params("trend_pullback"))
    assert ("triggered", 12) not in [(e["type"], e["index"]) for e in events]


def test_the_cooldown_spaces_out_repeat_triggers():
    n = 40
    b = S.Bars([str(i) for i in range(n)], [None] * n, np.zeros(n), np.ones(n), -np.ones(n),
               np.zeros(n), np.ones(n))
    trig = np.zeros(n, dtype=bool)
    trig[[10, 13, 17]] = True
    stop = np.full(n, -5.0)
    c = np.zeros(n)
    c[11] = -10.0                                       # invalidates the first one at once
    b = S.Bars(b.stamps, b.ends, b.o, b.h, b.l, c, b.v)
    det = S.Detection(np.ones(n, dtype=bool), trig.copy(), trig, np.zeros(n), stop, S._nan(n))
    p = params("trend_pullback", cooldown=5)
    events, _, _ = S.lifecycle(b, det, np.ones(n, dtype=bool), p)
    fired = [e["index"] for e in events if e["type"] == "triggered"]
    assert fired == [10, 17], "13 is inside the five-bar cooldown"


# ======================================================== both directions

def test_the_bearish_rule_is_the_bullish_one_upside_down():
    """Turn the chart over around a constant and the bearish evaluation of it
    triggers on exactly the bars the bullish one did on the original."""
    df = _pullback_df()
    flip = df.copy()
    K = 400.0
    flip["Close"] = K - df["Close"]
    flip["Open"] = K - df["Open"]
    flip["High"] = K - df["Low"]
    flip["Low"] = K - df["High"]
    up = S.analyse("X", df, None, presets=["trend_pullback"], directions=["bull"],
                   overrides={"*": {"htf_filter": False}}, now=after(df))["rows"][0]
    down = S.analyse("X", flip, None, presets=["trend_pullback"], directions=["bear"],
                     overrides={"*": {"htf_filter": False}}, now=after(flip))["rows"][0]
    assert up["status"] == down["status"] == "triggered"
    assert up["trigger"]["stamp"] == down["trigger"]["stamp"]
    assert down["invalidation"] == pytest.approx(K - up["invalidation"])
    assert "below" in down["explanation"] and "above" in up["explanation"]


def test_every_preset_runs_both_ways_on_a_real_looking_chart():
    df = walk(400, seed=21)
    out = S.analyse("X", df, None, now=after(df))
    assert len(out["rows"]) == 2 * len(S.PRESETS)
    assert {r["status"] for r in out["rows"]} <= set(S.STATES)
    for r in out["rows"]:
        assert r["explanation"] and "None" not in r["explanation"], (r["preset"], r["explanation"])
        assert "—" not in r["explanation"], "no em dashes in what a reader sees"


# =================================================== momentum and oscillators

def test_an_oversold_reading_alone_arms_and_never_triggers():
    close = list(np.linspace(150, 100, 80))              # a long fall: RSI deep under 30
    df = frame(close)
    out = S.analyse("X", df, None, presets=["rsi_oversold"], directions=["bull"], now=after(df))
    row = out["rows"][0]
    assert row["status"] in ("armed", "watching", "expired")
    assert row["trigger"] is None
    bounced = frame(close + [101.5, 103.5, 105.0])
    out2 = S.analyse("X", bounced, None, presets=["rsi_oversold"], directions=["bull"],
                     now=after(bounced))
    assert out2["rows"][0]["trigger"] is not None, "closing back above 30 is the trigger"


@pytest.mark.parametrize("preset,words", [
    ("momentum_confirm", ("RSI", "MACD")),
    ("triple_stoch", ("Slow (", "Middle (")),
])
def test_momentum_readings_count_as_one_condition(preset, words):
    """The readings a rule uses to confirm momentum (RSI with MACD, or the
    slow and middle stochastics) are one reading of one thing, so however many
    there are, "conditions met" counts one. The triple stochastic's fast pair
    is that rule's setup and trigger, which every rule has one of each."""
    df = walk(300, seed=9)
    row = S.analyse("X", df, None, presets=[preset], directions=["bull"],
                    now=after(df))["rows"][0]
    momentum = [c for c in row["checks"] if any(w in c["rule"] for w in words)]
    assert len(momentum) >= 2, "the rule checks more than one reading"
    assert len({c["group"] for c in momentum}) == 1, {c["group"] for c in momentum}
    counted = [g["group"] for g in row["conditions"]["groups"]]
    assert counted.count(momentum[0]["group"]) == 1
    assert "Not a probability" in row["conditions"]["note"]


def _stoch_case(fast_k, fast_d, window):
    """The rule on oscillator values chosen by hand, the slow and middle ones
    rising and above 50 throughout, so only the fast pair decides."""
    n = len(fast_k)
    c = np.linspace(100, 110, n)
    b = S.Bars([str(i) for i in range(n)], [None] * n, c, c + 1, c - 1, c, np.ones(n))
    p = params("triple_stoch", window=window)
    ind = S.Indicators(b)
    rising = np.linspace(55, 80, n)
    ind._memo[("stoch", p["fast_len"], p["fast_k"], p["fast_d"])] = (np.array(fast_k), np.array(fast_d))
    ind._memo[("stoch", p["mid_len"], p["mid_k"], p["mid_d"])] = (rising, rising)
    ind._memo[("stoch", p["slow_len"], p["slow_k"], p["slow_d"])] = (rising, rising)
    return S.detect_triple_stoch(ind, p, S.Words(True))


def test_the_triple_stochastic_window_is_counted_back_from_the_crossing_bar():
    """"An oversold reading within the 5 bars ending at the cross": the window
    includes the crossing bar and counts back from it."""
    # Fast %K crosses above %D at bar 50 while itself at 18: oversold on the
    # crossing bar, so a one-bar window is enough.
    k = [40.0] * 60
    d = [30.0] * 60
    k[49], d[49] = 12.0, 15.0
    k[50], d[50] = 18.0, 16.0
    assert _stoch_case(k, d, 1).trigger[50]
    # Oversold only the bar before, the cross itself at 25: one bar is not
    # enough, two is.
    k[50] = 25.0
    assert not _stoch_case(k, d, 1).trigger[50]
    assert _stoch_case(k, d, 2).trigger[50]


def test_a_retest_ends_on_a_close_through_the_level():
    n = 40                                            # past the 14-bar ATR's warm-up
    c = np.full(n, 100.0)
    h, l = c + 0.5, c - 0.5
    c[20], h[20] = 106.0, 106.5                      # the breakout above 100.5
    c[21], l[21], h[21] = 101.0, 100.4, 101.5        # back to the level, holding
    c[22], h[22] = 102.2, 102.5                      # closes above the prior high
    b = S.Bars([str(i) for i in range(n)], [None] * n, c - 0.1, h, l, c, np.ones(n))
    ind = S.Indicators(b)
    level = np.full(n, 100.5)
    broke = np.zeros(n, dtype=bool)
    broke[20] = True
    p = {"retest_window": 10, "touch_atr": 0.25, "tolerance_atr": 0.5}
    arm, trig, lvl, fail, low = S._retest(ind, p, level, broke)
    assert arm[21] and trig[22] and not trig[21]
    c2 = c.copy()
    c2[21] = 90.0                                     # closed straight through it
    b2 = S.Bars(b.stamps, b.ends, b.o, h, np.minimum(l, c2 - 0.5), c2, b.v)
    arm2, trig2, *_ = S._retest(S.Indicators(b2), p, level, broke)
    assert not trig2[22], "a failed retest does not get a second chance"


def test_a_swing_high_already_closed_through_is_not_a_level():
    close = [100.0] * 20 + [110.0] + [100.0] * 10 + [112.0] + [104.0] * 10
    df = frame(close, high=np.array(close) + 0.5, low=np.array(close) - 0.5)
    b = bars_of(df)
    p = params("sr_breakout")
    level, source = S._sr_levels(S.Indicators(b), p)
    # The 110.5 high (bar 20) was closed through at bar 31; by the end the only
    # unbroken one above the close is the 112.5 high.
    assert level[-1] == pytest.approx(112.5)


# ======================================================== conditions met

def test_switched_off_filters_are_shown_and_not_counted():
    df = walk(330, seed=2)
    row = S.analyse("X", df, None, presets=["donchian_20"], directions=["bull"],
                    overrides={"*": {"htf_filter": False}}, now=after(df))["rows"][0]
    context = [c for c in row["checks"] if c["group"] == "Context"]
    assert context and all(c["required"] is False for c in context)
    assert "Context" not in [g["group"] for g in row["conditions"]["groups"]]


# ======================================================== parameters

def test_parameters_are_clamped_and_unknown_ones_dropped():
    p = S.resolve_params("donchian_20", {"channel": 9999, "bogus": 1, "vol_mult": "abc",
                                         "benchmark": "spy; drop", "htf_filter": "false"})
    assert p["channel"] == 120 and "bogus" not in p
    assert p["vol_mult"] == 0.0 and p["benchmark"] == "SPY" and p["htf_filter"] is False


def test_the_catalogue_says_every_rule_both_ways():
    cat = S.catalogue()
    assert len(cat["presets"]) == len(S.PRESETS)
    for p in cat["presets"]:
        assert p["rules"]["bull"] and p["rules"]["bear"]
        assert p["kind"] in S.KINDS
        assert "institutional" not in (p["rules"]["bull"] + p["rules"]["bear"]).lower()
    stoch = next(p for p in cat["presets"] if p["id"] == "triple_stoch")
    assert stoch["experimental"] is True and "no standard model" in stoch["rules"]["bull"]
    fib = next(p for p in cat["presets"] if p["id"] == "fib_zone")
    assert "this app's" in fib["rules"]["bull"] and "configurable" in fib["rules"]["bull"]


# ======================================================== freshness for alerts

def test_only_recent_triggers_are_news():
    df = _pullback_df()
    out = S.analyse("X", df, None, presets=["trend_pullback"], directions=["bull"],
                    overrides={"*": {"htf_filter": False}}, now=after(df))
    assert [r["preset"] for r in S.fresh_triggers(out)] == ["trend_pullback"]
    assert S.fresh_triggers(out, preset="donchian_20") == []
    later = dict(out, recent_stamps=out["recent_stamps"] + ["x1", "x2", "x3"], as_of="x3")
    assert S.fresh_triggers(later) == [], "three candles on, it is not news"


# ======================================================== history

def test_history_enters_on_the_next_open_and_stops_first_on_a_tie():
    n = 30
    o = np.full(n, 100.0)
    h = np.full(n, 101.0)
    l = np.full(n, 99.0)
    c = np.full(n, 100.0)
    o[11], h[11], l[11] = 100.5, 120.0, 90.0           # both stop and target in one candle
    b = S.Bars([str(i) for i in range(n)], [None] * n, o, h, l, c, np.ones(n))
    events = [{"type": "triggered", "index": 10, "stamp": "10", "close": 100.0, "level": 100.0,
               "stop": 95.0}]
    out = S.history(b, True, events, {"slippage_bps": 0, "target_r": 2.0, "max_hold": 20})
    trade = out["trades"][0]
    assert trade["entry_at"] == "11" and trade["entry"] == pytest.approx(100.5)
    assert trade["why"] == "invalidation" and trade["exit"] == pytest.approx(95.0)
    assert "not options returns" in out["caveat"]
    assert "too few" in out["small_sample"]


def test_history_skips_a_trade_that_opens_through_its_stop():
    n = 20
    o = np.full(n, 100.0)
    o[6] = 94.0
    b = S.Bars([str(i) for i in range(n)], [None] * n, o, o + 1, o - 1, o, np.ones(n))
    events = [{"type": "triggered", "index": 5, "stamp": "5", "close": 100.0, "level": 100.0,
               "stop": 95.0}]
    assert S.history(b, True, events, {})["all"]["n"] == 0


# ======================================================== option contracts

def _chain():
    rows = []
    for k in (90, 95, 100, 105, 110):
        for call in (True, False):
            rows.append({"contract": "C%d%s" % (k, "C" if call else "P"), "expiry": "2026-11-20",
                         "dte": 46, "strike": float(k), "is_call": call, "bid": 2.0, "ask": 2.1,
                         "mid": 2.05, "spread_pct": 4.9, "volume": 50, "open_interest": 500,
                         "iv": 0.3, "iv_filled": k == 110, "delta": 0.5 if call else -0.5,
                         "gamma": 0.02, "theta": -0.03, "vega": 0.1,
                         "last_trade": pd.Timestamp("2026-10-05T19:59:00Z"),
                         "fetched_at": "2026-10-05T20:10:00+00:00"})
    return pd.DataFrame(rows)


def test_contracts_are_listed_with_the_filters_that_chose_them_and_none_is_best():
    out = S.contracts_for(_chain(), 100.0, True, {"min_oi": 100, "budget": 300},
                          "2026-10-28", now=datetime(2026, 10, 5, 20, 0, tzinfo=timezone.utc))
    assert out["available"] and out["side"] == "call" and out["considered"] == 5
    assert all("best" not in str(v).lower() for v in out["contracts"])
    assert "Not ranked" in out["order"]
    assert any("Open interest" in n and "nothing about how easily" in n for n in out["notes"])
    assert any("does not cap what an option can lose" in n for n in out["notes"])
    assert any("IV rank" in n and "not shown" in n for n in out["notes"])
    assert out["earnings_in_hold"] is True
    assert all(c["through_earnings"] for c in out["contracts"])
    assert set(out["dropped"]) >= {"open interest at least 100", "costs at most $300 for one"}


def test_a_filled_in_iv_and_its_greeks_are_withheld():
    out = S.contracts_for(_chain(), 100.0, True, {}, None,
                          now=datetime(2026, 10, 5, 20, 0, tzinfo=timezone.utc))
    row = next(c for c in out["contracts"] if c["strike"] == 110)
    assert row["iv_pct"] is None and row["delta"] is None and row["iv_note"]
    other = next(c for c in out["contracts"] if c["strike"] == 100)
    assert other["iv_pct"] == pytest.approx(30.0) and other["last_trade"].startswith("2026-10-05")


def test_no_chain_keeps_the_stock_setup_and_says_why():
    out = S.contracts_for(None, 100.0, True, {}, None)
    assert out["available"] is False and out["reason"] and out["contracts"] == []


# ======================================================== four-hour candles

def test_a_four_hour_candle_is_stamped_when_it_completed_and_reads_only_closed_days():
    """The feed stamps a 4-hour candle at its open. A trigger on the 9:30 candle
    happened at 1:30pm, and a 4-hour candle may read a daily candle only once
    that day has closed: the 1:30pm candle cannot see its own day's close."""
    idx = pd.DatetimeIndex(["2026-10-05 09:30", "2026-10-05 13:30", "2026-10-06 09:30"]).tz_localize(ET)
    df = pd.DataFrame({"Open": [1.0, 2.0, 3.0], "High": [2.0, 3.0, 4.0], "Low": [0.5, 1.0, 2.0],
                       "Close": [1.5, 2.5, 3.5], "Volume": [1.0, 1.0, 1.0]}, index=idx)
    b = S.intraday_bars(df, 240, datetime(2026, 10, 6, 12, 0, tzinfo=ET))
    assert b.stamps == ["2026-10-05T13:30", "2026-10-05T16:00"]
    assert b.forming["stamp"] == "2026-10-06T13:30", "still forming at noon"
    days = frame([100.0, 101.0], start="2026-10-02")           # Oct 2 and Oct 5
    daily = S.daily_bars(days, datetime(2026, 10, 6, 12, 0, tzinfo=ET))
    htf = S.daily_context_for(b, daily)
    assert daily.stamps[htf.latest[0]] == "2026-10-02", "1:30pm reads the day before"
    assert daily.stamps[htf.latest[1]] == "2026-10-05", "the close reads its own day"
