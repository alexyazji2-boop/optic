"""The sector board: overnight levels and rotation.

The levels are deliberately a definition anyone can check — the prior completed
session's high and low — so most of these tests pin that definition down rather
than testing a model. The rest guard the one judgement call in the module: that
trend and rotation are separate questions and must not be merged.
"""

from __future__ import annotations

import pandas as pd
import pytest

from app.analytics import sector_board as sb


def _frame(rows):
    """rows: list of (high, low, close), oldest first."""
    return pd.DataFrame({
        "High": [r[0] for r in rows],
        "Low": [r[1] for r in rows],
        "Close": [r[2] for r in rows],
        "Open": [r[2] for r in rows],
        "Volume": [1_000_000] * len(rows),
    })


class _Provider:
    def __init__(self, frames):
        self.frames = frames

    def batch_history(self, symbols, period="3mo", interval="1d"):
        return {s: self.frames.get(s) for s in symbols if s in self.frames}


def _flat(n, price):
    return [(price, price, price)] * n


def _board(sector_rows, bench_rows=None, symbol="XLK"):
    frames = {symbol: _frame(sector_rows),
              sb.BENCHMARK: _frame(bench_rows or sector_rows)}
    return sb.build(_Provider(frames))


def _row(board, symbol="XLK"):
    return next(r for r in board["rows"] if r["symbol"] == symbol)


# ------------------------------------------------------------- the levels

def test_levels_are_the_prior_completed_session():
    """Not today's bar. A level price is currently inside is not a level."""
    rows = _flat(25, 100.0) + [(191.74, 188.86, 190.0), (999.0, 1.0, 190.01)]
    r = _row(_board(rows))
    assert r["bull_above"] == 191.74
    assert r["bear_below"] == 188.86


def test_deltas_are_signed_from_price_to_the_level():
    """Reproduces the reference table: XLK 190.01 against 191.74 / 188.86."""
    rows = _flat(25, 100.0) + [(191.74, 188.86, 190.0), (191.35, 189.25, 190.01)]
    r = _row(_board(rows))
    assert r["to_break_pct"] == pytest.approx(-0.90, abs=0.01)
    assert r["to_breakdown_pct"] == pytest.approx(0.61, abs=0.01)


@pytest.mark.parametrize("close,expected", [
    (192.00, "uptrend"),     # above the prior high
    (188.00, "downtrend"),   # below the prior low
    (190.01, "neutral"),     # inside the prior range
    (191.74, "neutral"),     # exactly at the high is not through it
    (188.86, "neutral"),     # exactly at the low is not through it
])
def test_trend_classification(close, expected):
    rows = _flat(25, 190.0) + [(191.74, 188.86, 190.0), (999.0, 1.0, close)]
    assert _row(_board(rows))["trend"] == expected


def test_intact_versus_new_trend():
    """A trend that has held is different information from one that just turned."""
    # Two consecutive sessions closing above the preceding session's high.
    rising = _flat(24, 100.0) + [(101.0, 99.0, 100.0), (102.0, 100.5, 103.0), (999.0, 1.0, 104.0)]
    r = _row(_board(rising))
    assert r["trend"] == "uptrend"
    assert r["intact"] is True
    assert r["changed"] is False


def test_neutral_never_claims_to_be_intact():
    """'Neutral, intact' is not a statement about anything."""
    rows = _flat(26, 100.0) + [(999.0, 1.0, 100.0)]
    r = _row(_board(rows))
    assert r["trend"] == "neutral"
    assert r["intact"] in (False, None)


# ----------------------------------------------------------- the rotation

def test_rotation_requires_both_windows_to_agree():
    """One good week against a bad month is a bounce, not a reallocation."""
    assert sb._rotation(5.0, 5.0)["state"] == "in"
    assert sb._rotation(-5.0, -5.0)["state"] == "out"
    assert sb._rotation(5.0, -5.0)["state"] == "turning"
    assert sb._rotation(-5.0, 5.0)["state"] == "turning"


def test_small_divergence_is_not_rotation():
    """Sector funds drift from the index without anything happening."""
    assert sb._rotation(0.3, 0.4)["state"] == "neutral"
    assert sb._rotation(-0.5, -0.2)["state"] == "neutral"


def test_rotation_is_relative_not_absolute():
    """A sector up less than the index is rotating OUT despite rising.

    This is the case the board exists to expose, and the reason trend and
    rotation are separate columns: absolute strength and relative strength
    genuinely disagree here.
    """
    sector = [(100 + i * 0.1, 99 + i * 0.1, 100 + i * 0.1) for i in range(30)]
    bench = [(100 + i * 1.0, 99 + i * 1.0, 100 + i * 1.0) for i in range(30)]
    r = _row(_board(sector, bench))
    assert r["rel_month_pct"] < 0
    assert r["rotation"]["state"] == "out"


def test_rotation_unknown_without_history():
    got = sb._rotation(None, None)
    assert got["state"] == "unknown"


# -------------------------------------------------------------- plumbing

def test_all_eleven_sectors_are_reported_even_when_data_is_missing():
    """A silently absent sector reads as 'nothing to see', which is wrong."""
    board = sb.build(_Provider({}))
    assert len(board["rows"]) == 11
    assert all(r["available"] is False for r in board["rows"])
    assert board["available"] is False


def test_short_history_is_reported_not_guessed():
    board = _board([(1.0, 1.0, 1.0)])
    assert _row(board)["available"] is False


def test_counts_match_the_rows():
    rows = _flat(25, 190.0) + [(191.74, 188.86, 190.0), (999.0, 1.0, 195.0)]
    board = _board(rows)
    usable = [r for r in board["rows"] if r.get("available")]
    assert board["counts"]["uptrend"] == sum(1 for r in usable if r["trend"] == "uptrend")


def test_provider_failure_does_not_raise():
    class Broken:
        def batch_history(self, *a, **k):
            raise RuntimeError("network down")
    got = sb.build(Broken())
    assert got["available"] is False
    assert "unavailable" in got["reason"]


def test_method_note_disclaims_a_futures_feed():
    """'Overnight' must not imply data the terminal does not have."""
    rows = _flat(26, 100.0) + [(999.0, 1.0, 100.0)]
    note = _board(rows)["method"]
    assert "no futures feed" in note.lower()
    assert "regular-session daily bars" in note
