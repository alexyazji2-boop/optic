"""Sector relative rotation.

The arithmetic is a ratio, a moving average and a z-score, none of which needs
defending. What needs testing is that the chart means what the four quadrant
labels say it means: that a sector beating the index lands on the right of the
centre line, that one whose lead is shrinking lands below it, and that the two
axes stay independent — a sector can be strong and losing momentum at the same
time, and that combination is the entire reason the chart has four boxes rather
than one ranking.
"""

import zlib

import numpy as np
import pandas as pd
import pytest

from app.analytics import rotation


def _seed_for(symbol):
    """A stable seed per symbol.

    This used to be `hash(symbol) % 997`. Python randomises string hashing per
    process unless PYTHONHASHSEED is pinned, so every run built a different
    synthetic market and the smoothing test passed or failed depending on the
    day. A test that is a coin flip is worse than no test: it trains you to
    re-run it until it goes green.
    """
    return zlib.crc32(symbol.encode()) % 9973


class _Provider:
    def __init__(self, frames):
        self._frames = frames

    def batch_history(self, tickers, period="2y", interval="1wk"):
        return {t: self._frames[t] for t in tickers if t in self._frames}


def _weeks(n=160):
    return pd.date_range("2023-01-06", periods=n, freq="W-FRI")


def _frame(values, idx):
    return pd.DataFrame({"Close": values}, index=idx)


def _flat(idx, level=100.0, seed=0, vol=0.004):
    rng = np.random.default_rng(seed)
    return level * np.exp(np.cumsum(rng.normal(0, vol, len(idx))))


# ------------------------------------------------------------ the quadrants

def test_the_quadrant_names_come_only_from_the_two_signs():
    assert rotation.quadrant(101, 101) == "leading"
    assert rotation.quadrant(101, 99) == "weakening"
    assert rotation.quadrant(99, 99) == "lagging"
    assert rotation.quadrant(99, 101) == "improving"


def test_the_centre_lines_belong_to_the_stronger_quadrant():
    """Exactly 100 has to fall somewhere, and it must be decided rather than
    left to a floating-point comparison nobody wrote down."""
    assert rotation.quadrant(100, 100) == "leading"
    assert rotation.quadrant(100, 99) == "weakening"
    assert rotation.quadrant(99, 100) == "improving"


# ------------------------------------------------------- what the axes mean

def test_a_sector_pulling_away_from_the_index_leads():
    idx = _weeks()
    bench = _flat(idx, seed=1)
    # Steadily accelerating outperformance: strong AND still gaining.
    ramp = np.exp(np.cumsum(np.linspace(0.0, 0.006, len(idx))))
    frames = {"SPY": _frame(bench, idx)}
    for meta in rotation.SECTORS:
        frames[meta["symbol"]] = _frame(bench * (ramp if meta["symbol"] == "XLK" else 1.0), idx)
    out = rotation.build(_Provider(frames))
    xlk = next(r for r in out["sectors"] if r["symbol"] == "XLK")
    assert xlk["strength"] > 100, xlk
    assert xlk["quadrant"] in ("leading", "improving"), xlk


def test_a_sector_losing_its_lead_shows_falling_momentum():
    """Strong but decelerating is the Weakening quadrant, and it is the one the
    chart adds over a plain relative-strength ranking — a table sorted by
    strength alone puts this sector at the top on the week it starts rolling
    over."""
    idx = _weeks()
    bench = _flat(idx, seed=2)
    # Outperform hard, then flatten out: the lead stops growing.
    step = np.concatenate([np.full(len(idx) // 2, 0.006), np.full(len(idx) - len(idx) // 2, 0.0)])
    frames = {"SPY": _frame(bench, idx)}
    for meta in rotation.SECTORS:
        frames[meta["symbol"]] = _frame(
            bench * (np.exp(np.cumsum(step)) if meta["symbol"] == "XLF" else 1.0), idx)
    out = rotation.build(_Provider(frames))
    xlf = next(r for r in out["sectors"] if r["symbol"] == "XLF")
    assert xlf["momentum"] < 100, xlf


def test_a_sector_that_tracks_the_index_exactly_sits_at_the_centre():
    """No relative move means no reading. Not 'slightly positive'."""
    idx = _weeks()
    bench = _flat(idx, seed=3)
    frames = {"SPY": _frame(bench, idx)}
    for meta in rotation.SECTORS:
        frames[meta["symbol"]] = _frame(bench * 1.7, idx)     # same shape, different price
    out = rotation.build(_Provider(frames))
    for r in out["sectors"]:
        assert r["strength"] == pytest.approx(100.0, abs=0.01), r
        assert r["momentum"] == pytest.approx(100.0, abs=0.01), r


def test_a_flat_ratio_does_not_divide_by_zero():
    """A sector that moves exactly with the index has zero variance in the
    z-score window. That is 'perfectly ordinary' — 100 — not NaN or infinity."""
    idx = _weeks()
    bench = _flat(idx, seed=4)
    frames = {"SPY": _frame(bench, idx)}
    for meta in rotation.SECTORS:
        frames[meta["symbol"]] = _frame(bench, idx)
    out = rotation.build(_Provider(frames))
    for r in out["sectors"]:
        assert r["strength"] is not None and np.isfinite(r["strength"])
        assert r["momentum"] is not None and np.isfinite(r["momentum"])


# ----------------------------------------------------------------- the tail

def test_the_tail_runs_oldest_to_newest():
    """The chart fades the tail by index, so a reversed path would draw the
    brightest dot at the oldest point and the direction would read backwards."""
    idx = _weeks()
    bench = _flat(idx, seed=5)
    frames = {"SPY": _frame(bench, idx)}
    for meta in rotation.SECTORS:
        frames[meta["symbol"]] = _frame(_flat(idx, seed=_seed_for(meta["symbol"])), idx)
    out = rotation.build(_Provider(frames))
    for r in out["sectors"]:
        dates = [p["date"] for p in r["path"]]
        assert dates == sorted(dates), r["symbol"]
        # The headline reading is the last point, not the first.
        assert r["strength"] == r["path"][-1]["strength"]
        assert r["momentum"] == r["path"][-1]["momentum"]


def test_the_tail_length_is_honoured():
    idx = _weeks()
    bench = _flat(idx, seed=6)
    frames = {"SPY": _frame(bench, idx)}
    for meta in rotation.SECTORS:
        frames[meta["symbol"]] = _frame(_flat(idx, seed=_seed_for(meta["symbol"])), idx)
    out = rotation.build(_Provider(frames), tail=5)
    assert out["tail"] == 5
    for r in out["sectors"]:
        assert len(r["path"]) == 5


def test_a_crossing_is_reported_only_when_the_quadrant_actually_changed():
    idx = _weeks()
    bench = _flat(idx, seed=7)
    frames = {"SPY": _frame(bench, idx)}
    for meta in rotation.SECTORS:
        frames[meta["symbol"]] = _frame(_flat(idx, seed=_seed_for(meta["symbol"])), idx)
    out = rotation.build(_Provider(frames))
    reported = {c["symbol"] for c in out["crossed"]}
    actual = {r["symbol"] for r in out["sectors"]
              if r["quadrant"] != r["previous_quadrant"]}
    assert reported == actual


# ------------------------------------------------------------------ refusals

def test_too_little_history_is_skipped_not_plotted_at_a_made_up_centre():
    """A sector with 20 weeks has no z-score. Plotting it at 100 would put it on
    the boundary of all four quadrants and it would read as 'neutral' rather than
    'unknown'."""
    long_idx = _weeks()
    short_idx = _weeks(20)
    bench = _flat(long_idx, seed=8)
    frames = {"SPY": _frame(bench, long_idx)}
    for meta in rotation.SECTORS:
        if meta["symbol"] == "XLU":
            frames[meta["symbol"]] = _frame(_flat(short_idx, seed=9), short_idx)
        else:
            frames[meta["symbol"]] = _frame(_flat(long_idx, seed=_seed_for(meta["symbol"])),
                                            long_idx)
    out = rotation.build(_Provider(frames))
    assert "XLU" in out["skipped"]
    assert all(r["symbol"] != "XLU" for r in out["sectors"])


def test_a_missing_benchmark_is_an_error():
    idx = _weeks()
    frames = {m["symbol"]: _frame(_flat(idx, seed=1), idx) for m in rotation.SECTORS}
    out = rotation.build(_Provider(frames))
    assert "error" in out and "benchmark" in out["error"]


def test_the_counts_add_up_to_the_sectors_plotted():
    idx = _weeks()
    bench = _flat(idx, seed=10)
    frames = {"SPY": _frame(bench, idx)}
    for meta in rotation.SECTORS:
        frames[meta["symbol"]] = _frame(_flat(idx, seed=_seed_for(meta["symbol"])), idx)
    out = rotation.build(_Provider(frames))
    assert sum(out["counts"].values()) == len(out["sectors"])
    assert set(out["counts"]) <= {"leading", "weakening", "lagging", "improving"}


def test_smoothing_actually_smooths():
    """A guard on the constant, not the concept.

    Unsmoothed, the median week-to-week step measured 1.6 units against a plot
    half-width of 5.9 — a quarter of the chart per week, which drew the tails as
    a tangle rather than as arcs. Someone reading SMOOTH later and thinking it is
    cosmetic should find this failing before the chart goes back to unreadable.
    """
    idx = _weeks()
    bench = _flat(idx, seed=20)
    frames = {"SPY": _frame(bench, idx)}
    for meta in rotation.SECTORS:
        frames[meta["symbol"]] = _frame(_flat(idx, seed=_seed_for(meta["symbol"])), idx)
    out = rotation.build(_Provider(frames))

    steps, points = [], []
    for r in out["sectors"]:
        pts = [(p["strength"], p["momentum"]) for p in r["path"]]
        points += pts
        steps += [float(np.hypot(b[0] - a[0], b[1] - a[1])) for a, b in zip(pts, pts[1:])]

    half = max(max(abs(x - 100) for x, _ in points),
               max(abs(y - 100) for _, y in points))
    assert half > 0
    assert float(np.median(steps)) / half < 0.20, (
        "tails move more than a fifth of the plot per week — they will read as a "
        "tangle rather than as rotation")


def test_smoothing_does_not_move_a_flat_sector_off_centre():
    """An EMA of a constant is that constant. If smoothing introduced a drift,
    a sector tracking the index exactly would wander off 100."""
    idx = _weeks()
    bench = _flat(idx, seed=21)
    frames = {"SPY": _frame(bench, idx)}
    for meta in rotation.SECTORS:
        frames[meta["symbol"]] = _frame(bench * 2.5, idx)
    out = rotation.build(_Provider(frames))
    for r in out["sectors"]:
        assert r["strength"] == pytest.approx(100.0, abs=0.01), r
        assert r["momentum"] == pytest.approx(100.0, abs=0.01), r
