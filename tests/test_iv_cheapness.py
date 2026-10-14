"""Cheap or dear (app/analytics/iv_cheapness.py), the straddle calibration
(app/analytics/straddle_calibration.py) and the stock's own IV record."""
from __future__ import annotations

import json

import pytest

from app.analytics import iv_cheapness as ic
from app.analytics import straddle_calibration as sc


def test_a_low_rank_is_not_called_cheap():
    r = ic.read({"available": True, "rank": 8.0}, None)
    assert r["rank_bucket"]["moved_more_pct"] == 38.1
    assert "38% of the time" in r["text"] and "30% for all days" in r["text"]
    assert "cheap" not in r["text"].lower()
    assert "None of it makes buying options the better side" in r["finding"]


def test_iv_below_realised_reads_the_stronger_sign():
    hv = {"available": True, "iv30": 22.0, "hv30": 28.0, "iv_above_next_rv_pct": 64.0}
    r = ic.read({"available": False}, hv)
    assert r["iv_below_hv"] is True and "45% of the time" in r["text"]
    assert "64% of days" in r["text"]
    r2 = ic.read(None, dict(hv, iv30=30.0))
    assert r2["iv_below_hv"] is False and "22% of the time" in r2["text"]


def test_nothing_to_read():
    assert ic.read(None, None)["available"] is False


def test_the_bands_cover_every_rank():
    for rank in (0, 9.99, 10, 29.9, 30, 55, 89.9, 90, 100):
        assert ic.read({"available": True, "rank": rank}, None)["rank_bucket"] is not None


def _cal(tmp_path, monkeypatch, rows):
    p = tmp_path / "cal.json"
    p.write_text(json.dumps({"source": "Derived from DoltHub, CC BY-SA 4.0", "source_url": "u", "method": "m",
                             "symbols": rows}))
    monkeypatch.setattr(sc, "PATH", str(p))
    sc._cache.clear()


ROW = {"n": 99, "from": "2024-10-07", "to": "2026-08-31", "mean_ratio": 0.808, "ci95": [0.554, 1.061],
       "median_ratio": 0.71, "exceed_pct": 39.4, "implied_median_pct": 3.15, "days_median": 25}


def test_the_calibration_is_off_without_dolthub(tmp_path, monkeypatch):
    _cal(tmp_path, monkeypatch, {"SPY": ROW})
    monkeypatch.delenv("OPTIC_DOLTHUB", raising=False)
    assert sc.for_symbol("SPY")["available"] is False


def test_a_lean_only_when_the_interval_clears_one(tmp_path, monkeypatch):
    monkeypatch.setenv("OPTIC_DOLTHUB", "1")
    _cal(tmp_path, monkeypatch, {"SPY": ROW, "XYZ": dict(ROW, mean_ratio=0.7, ci95=[0.6, 0.8]),
                                 "ABC": dict(ROW, mean_ratio=1.3, ci95=[1.1, 1.5]), "TINY": dict(ROW, n=10)})
    assert "not clearly dearer or cheaper" in sc.for_symbol("spy")["text"]
    assert "0.81 times what it cost (95% interval 0.55 to 1.06" in sc.for_symbol("SPY")["text"]
    assert "was dearer than the moves" in sc.for_symbol("XYZ")["text"]
    assert "was cheaper than the moves" in sc.for_symbol("ABC")["text"]
    assert sc.for_symbol("TINY")["available"] is False
    assert sc.for_symbol("NONE")["available"] is False


def test_the_shipped_calibration_is_well_formed():
    data = json.load(open(sc.PATH))
    assert "CC BY-SA" in data["source"]
    for sym, r in data["symbols"].items():
        assert r["ci95"][0] < r["mean_ratio"] < r["ci95"][1]
        assert r["n"] >= sc.MIN_SAMPLES


def test_the_stock_record_of_implied_against_what_followed(tmp_path, monkeypatch):
    from datetime import date
    from app import dolthub_vol as dv
    from tests.test_dolthub_vol import _fake
    monkeypatch.setenv("TRACKER_DATA_DIR", str(tmp_path))
    days, d, k = {}, date(2025, 1, 6), 0
    while k < 120:
        if d.weekday() < 5:
            # IV 0.30 throughout; realised 0.20 for the first 60 days, 0.40 after.
            days[d.isoformat()] = [("XYZ", 0.30, 0.20 if k < 60 else 0.40)]
            k += 1
        d = date.fromordinal(d.toordinal() + 1)
    dv.sync(until=d, getter=_fake(days), pause=0)
    r = dv.iv_hv("XYZ")
    # Days 0..98 against hv 21 on: 0..38 see 0.20 (implied beat it), 39..98 see 0.40.
    assert r["next_rv_days"] == 99 and r["iv_above_next_rv_pct"] == pytest.approx(39 / 99 * 100, abs=0.1)


def test_figures_round_as_the_page_does():
    r = ic.read(None, {"available": True, "iv30": 12.35, "hv30": 9.85})
    assert "(12.4% against 9.9%)" in r["text"]
