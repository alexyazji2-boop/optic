"""Named scans over the ranked universe.

The bug worth remembering here was not a crash. Filtering "steady uptrends" on
average true range alone put FBRX at the top of the list: up 57% in a month with
the smallest daily range in the entire universe, because it gapped once and then
went flat. Both numbers were correct, the filter did exactly what it said, and
the result was absurd — which is why several of these tests assert on the
*meaning* of a scan rather than only on its mechanics.
"""

from __future__ import annotations

import time

import pytest

from app.analytics import scanners


def _row(symbol="TEST", price=100.0, **kw):
    """A ranking row with sane defaults, overridable per test."""
    base = {
        "symbol": symbol, "price": price, "score": 50.0,
        "sma20": 95.0, "sma50": 90.0, "sma200": 80.0,
        "roc20": 5.0, "roc60": 12.0,
        "range_position": 0.7, "volume_expansion": 1.0, "atr_pct": 2.0,
    }
    base.update(kw)
    return base


def _ranking(rows, age_hours=1.0):
    return {"ranked": rows, "universe_size": 3000,
            "ranked_at": time.time() - age_hours * 3600, "gates": {}}


# ------------------------------------------------------------- catalogue

def test_every_scan_declares_what_it_cannot_see():
    """A scan without a stated blind spot reads as a list of tips."""
    for entry in scanners.catalogue():
        assert entry["looks_for"].strip()
        assert entry["blind_spot"].strip()
        assert len(entry["blind_spot"]) > 60, entry["id"]


def test_catalogue_ids_are_unique_and_runnable():
    ids = [s["id"] for s in scanners.catalogue()]
    assert len(ids) == len(set(ids))
    for scan_id in ids:
        assert scan_id in scanners.SCAN_BY_ID


def test_every_scan_column_has_a_label_and_a_kind():
    """An unlabelled column renders as a raw field name to the reader."""
    for scan in scanners.SCANS:
        for col in scan["columns"]:
            assert col in scanners.COLUMN_LABELS, col
            assert col in scanners.COLUMN_KINDS, col


# ------------------------------------------------------------ the filters

def test_breakout_requires_volume_confirmation():
    """A 52-week high on quiet trade is a different event from one on volume."""
    quiet = _row("QUIET", range_position=0.99, volume_expansion=1.0)
    loud = _row("LOUD", range_position=0.99, volume_expansion=1.5)
    got = scanners.run(_ranking([quiet, loud]), "breakout")
    assert [r["symbol"] for r in got["rows"]] == ["LOUD"]


def test_breakout_excludes_names_below_the_50_day():
    r = _row("WEAK", price=85.0, range_position=0.99, volume_expansion=1.5, sma50=90.0)
    assert scanners.run(_ranking([r]), "breakout")["matched"] == 0


def test_pullback_wants_below_the_20_day_but_above_the_50():
    """The distinction the scan exists to draw."""
    dip = _row("DIP", price=93.0)          # under sma20 95, over sma50 90
    broken = _row("BROKEN", price=88.0)    # under both
    strong = _row("STRONG", price=99.0)    # over both
    got = scanners.run(_ranking([dip, broken, strong]), "pullback")
    assert [r["symbol"] for r in got["rows"]] == ["DIP"]


def test_pullback_requires_the_long_term_trend_to_be_intact():
    """A dip is only a pullback if there is a trend to pull back within."""
    r = _row("NOTREND", price=93.0, sma50=70.0, sma200=75.0)   # 50 under 200
    assert scanners.run(_ranking([r]), "pullback")["matched"] == 0


def test_steady_rejects_a_stock_that_gapped_and_stopped():
    """The FBRX case, kept as a test because the filter looked correct.

    Tiny average true range plus a huge one-month gain is a stock that leapt
    once and then went quiet — the opposite of a steady trend, and it sorted to
    the top because it had the smallest ATR in the universe.
    """
    gapped = _row("GAP", price=100.0, atr_pct=0.26, roc20=57.0)
    steady = _row("CALM", price=100.0, atr_pct=1.2, roc20=3.0)
    got = scanners.run(_ranking([gapped, steady]), "steady")
    assert [r["symbol"] for r in got["rows"]] == ["CALM"]


def test_steady_shows_the_column_it_filters_on():
    """A reader must be able to see the constraint that admitted a row."""
    keys = [c["key"] for c in scanners.run(_ranking([_row()]), "steady")["columns"]]
    assert "roc20" in keys and "atr_pct" in keys


def test_downtrend_is_the_mirror_of_momentum():
    weak = _row("WEAK", price=70.0, sma50=75.0, sma200=80.0)
    strong = _row("STRONG", price=100.0)
    got = scanners.run(_ranking([weak, strong]), "downtrend")
    assert [r["symbol"] for r in got["rows"]] == ["WEAK"]


def test_volume_scan_needs_a_real_expansion():
    normal = _row("NORM", volume_expansion=1.2)
    surging = _row("SURGE", volume_expansion=2.4)
    got = scanners.run(_ranking([normal, surging]), "volume")
    assert [r["symbol"] for r in got["rows"]] == ["SURGE"]


# --------------------------------------------------------------- plumbing

def test_derived_columns_are_computed_not_looked_up():
    """pct_from_* fields do not exist on a ranking row."""
    got = scanners.run(_ranking([_row("DIP", price=93.0)]), "pullback")
    row = got["rows"][0]
    assert row["pct_from_sma20"] == pytest.approx((93.0 / 95.0 - 1) * 100, abs=0.01)
    assert row["pct_from_sma50"] == pytest.approx((93.0 / 90.0 - 1) * 100, abs=0.01)


def test_limit_is_respected_and_match_count_is_the_truth():
    """'Showing the first 25' must not be confused with 'only 25 matched'."""
    rows = [_row("S%d" % i, score=float(i)) for i in range(60)]
    got = scanners.run(_ranking(rows), "momentum", limit=10)
    assert got["shown"] == 10
    assert got["matched"] == 60
    assert got["considered"] == 60


def test_momentum_sorts_by_score_descending():
    rows = [_row("LOW", score=10.0), _row("HIGH", score=90.0), _row("MID", score=50.0)]
    got = scanners.run(_ranking(rows), "momentum")
    assert [r["symbol"] for r in got["rows"]] == ["HIGH", "MID", "LOW"]


def test_stale_ranking_is_flagged_rather_than_served_silently():
    fresh = scanners.run(_ranking([_row()], age_hours=2), "momentum")
    old = scanners.run(_ranking([_row()], age_hours=scanners.STALE_AFTER_HOURS + 5),
                       "momentum")
    assert fresh["stale"] is False
    assert old["stale"] is True


def test_missing_ranking_explains_itself():
    got = scanners.run(None, "momentum")
    assert got["available"] is False
    assert "background" in got["reason"]
    got_empty = scanners.run({"ranked": []}, "momentum")
    assert got_empty["available"] is False


def test_unknown_scan_is_rejected():
    assert scanners.run(_ranking([_row()]), "nonsense")["available"] is False


def test_rows_with_missing_metrics_do_not_crash_a_scan():
    """A ranking row is not guaranteed to carry every field."""
    broken = {"symbol": "PARTIAL", "price": 10.0}
    for scan in scanners.SCANS:
        got = scanners.run(_ranking([broken]), scan["id"])
        assert got["available"] is True, scan["id"]


def test_method_note_states_the_scan_is_not_a_conclusion():
    note = scanners.run(_ranking([_row()]), "momentum")["method"]
    assert "never a conclusion" in note
    assert "no options data" in note
