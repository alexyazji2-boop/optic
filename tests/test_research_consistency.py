"""Research consistency on the stock Overview (interface audit, 2026-10-24).

NVIDIA's Overview said, at once, that its usual valuation range was too wide to
place the price in, that its valuation was Attractive, and that the long-term case
was Constructive. Traced, two things were wrong and one was legitimate:

1. A calculation fault. SEC EPS values sit on the share count of the filing they
   came from. Fourth quarters were derived as "annual minus three quarters" across
   a split, came out negative and were skipped; the trailing P/E then ran on 2022
   earnings for two years, the five-year 75th percentile read 286x, and the range
   was "too wide". The same fault hit every recent splitter (AVGO, WMT, CMG, NFLX,
   GOOGL, AMZN, TSLA, LRCX, SMCI).
2. Presentation. The framework's history measure said "five-year range" while
   using a few fiscal years. (The Overview summary's half of this fix, saying when
   the range cannot be read, stayed on polish-rebased: the post-demo overhaul
   replaced that summary with the Simple and Advanced analyses.)
3. Legitimate: the framework's valuation weighs more than the P/E history, so it
   can grade a price that the range cannot place. That difference is kept and said.
"""
import datetime as dt

import pandas as pd
import pytest

from app.analytics import fair_value, pe_history, sec_facts
from app.research import quality
from tests.test_pe_history import _Provider, _install_facts, _quarters


def _pt(start, end, val, filed):
    return {"start": start, "end": end, "val": val, "filed": filed, "form": "10-Q"}


def _facts_from(points):
    gaap = {"EarningsPerShareDiluted": {"units": {"USD/shares": points}}}
    q = sec_facts._merge_periods(gaap, sec_facts.EPS_TAGS, "USD/shares", sec_facts.Q_MIN_DAYS, sec_facts.Q_MAX_DAYS)
    y = sec_facts._merge_periods(gaap, sec_facts.EPS_TAGS, "USD/shares", sec_facts.Y_MIN_DAYS, sec_facts.Y_MAX_DAYS)
    return {"eps_points": {"quarters": q, "years": y}}, q, y


SPLIT = [(dt.date(2023, 6, 10), 10.0)]
after = lambda d: pe_history._cumulative_after(SPLIT, d)


# ------------------------------------------------------------ 1. the share basis

def test_a_fourth_quarter_is_derived_on_one_share_basis():
    """NVIDIA's shape: three quarters filed before a ten-for-one split, the annual
    figure last filed after it. Unrestated, 0.44 minus 3.0 is negative and the
    quarter was dropped."""
    facts, q, y = _facts_from([
        _pt("2022-01-01", "2022-03-31", 1.0, "2022-04-25"),
        _pt("2022-04-01", "2022-06-30", 1.0, "2022-07-25"),
        _pt("2022-07-01", "2022-09-30", 1.0, "2022-10-25"),
        _pt("2022-01-01", "2022-12-31", 4.4, "2023-02-20"),
        _pt("2022-01-01", "2022-12-31", 0.44, "2024-02-20"),   # the same year, restated after the split
    ])
    assert sec_facts._fill_fourth_quarters(dict(q), dict(y)) == 0, "the old order loses the quarter"
    rows = {r["period_end"]: r for r in sec_facts.eps_quarters_restated(facts, after)}
    assert rows["2022-12-31"]["value"] == pytest.approx(0.14)
    assert rows["2022-12-31"]["derived"] is True
    assert rows["2022-03-31"]["value"] == pytest.approx(0.1)
    # still public from the original 10-K, not from the restatement
    assert rows["2022-12-31"]["available_from"] == "2023-02-20"


def test_a_value_restated_after_a_split_is_not_divided_again():
    """The July 2023 quarter came back restated in an August 2024 10-Q, already on
    the new count. Keyed on its first filing it was divided by ten a second time."""
    facts, _, _ = _facts_from([
        _pt("2023-04-01", "2023-06-30", 2.5, "2023-07-25"),
        _pt("2023-04-01", "2023-06-30", 0.25, "2024-08-28"),
    ])
    (row,) = sec_facts.eps_quarters_restated(facts, after)
    assert row["value"] == pytest.approx(0.25)
    assert row["available_from"] == "2023-07-25"


def test_the_fallback_path_keys_on_the_restatement_too(monkeypatch):
    """Facts without the raw points (a test double, or an older shape) adjust each
    quarter at the filing its value came from."""
    quarters = _quarters(24, value=1.0)
    split_day = quarters[12]["period_end"]
    for r in quarters[:12]:
        # restated onto the new count in a filing after the split
        r["value"], r["restated_on"] = 0.5, "2099-01-01"
    _install_facts(monkeypatch, quarters)
    out = pe_history.build(_Provider(splits=[{"date": split_day, "ratio": 2.0}]), "TEST")
    assert out["pe_series"][0]["pe"] == pytest.approx(100.0 / 2.0), "0.5 a quarter, not 0.25"


# ------------------------------------------------------------ 2. stale earnings

def test_weeks_on_stale_earnings_are_left_out_and_counted(monkeypatch):
    """A missing quarter used to let the last good trailing year price every week
    until the next one: two years of NVIDIA weeks on 2022 earnings."""
    quarters = _quarters(24, value=1.0)
    del quarters[10:14]
    _install_facts(monkeypatch, quarters)
    out = pe_history.build(_Provider(), "TEST")
    assert out["available"] is True and out["stale_weeks"] > 0
    for p in out["pe_series"]:
        age = (dt.date.fromisoformat(p["date"]) - dt.date.fromisoformat(p["eps_period"])).days
        assert age <= pe_history.MAX_EPS_AGE_DAYS
    assert "{} days".format(pe_history.MAX_EPS_AGE_DAYS) in out["method"]


def test_an_unbroken_record_loses_no_weeks(monkeypatch):
    _install_facts(monkeypatch, _quarters(24, value=1.0))
    assert pe_history.build(_Provider(), "TEST")["stale_weeks"] == 0


# ------------------------------------------------------------ 3. what the range then says

class _FlatProvider(_Provider):
    def history(self, ticker, period="10y", interval="1d"):
        idx = pd.date_range("2018-01-01", "2024-06-28", freq="B")
        return pd.DataFrame({"Close": [100.0] * len(idx)}, index=idx)


def test_a_split_no_longer_widens_the_range_into_no_verdict(monkeypatch):
    """End to end on one filer whose real earnings never change: every filing
    before a ten-for-one split says 1.0 a quarter, every one after says 0.1, and
    each pre-split year comes back restated in a later 10-K. The multiple is
    flat, so the range must be narrow; the old order lost every fourth quarter."""
    split = "2023-06-10"
    on = lambda v, filed: v if filed < split else v / 10.0
    pts = []
    for year in range(2018, 2024):
        for (s, e, m) in (("01-01", "03-31", 4), ("04-01", "06-30", 7), ("07-01", "09-30", 10)):
            filed = "{}-{:02d}-25".format(year, m)
            pts.append(_pt("{}-{}".format(year, s), "{}-{}".format(year, e), on(1.0, filed), filed))
        filed = "{}-02-20".format(year + 1)
        pts.append(_pt("{}-01-01".format(year), "{}-12-31".format(year), on(4.0, filed), filed))
        if year <= 2022:
            pts.append(_pt("{}-01-01".format(year), "{}-12-31".format(year), 0.4, "2024-02-20"))
    facts, _, _ = _facts_from(pts)
    facts.update({"available": True, "eps_quarters": [{}] * 20, "revenue_yoy": [], "revenue_ttm": [],
                  "counts": {}, "span": {}, "short_history": False, "notes": [], "source": "test"})
    monkeypatch.setattr(sec_facts, "history", lambda t, force=False: facts)
    out = pe_history.build(_FlatProvider(splits=[{"date": split, "ratio": 10.0}]), "TEST")
    assert out["stale_weeks"] == 0
    assert out["pe_bands"]["25"] == out["pe_bands"]["75"] == pytest.approx(250.0)
    fv = fair_value.fair_value(out, 100.0)
    assert fv["available"] and fv["wide"] is False and fv["position"] == fair_value.INSIDE


# ------------------------------------------------------------ 4. the framework says what it measures

def test_the_history_measure_names_the_fiscal_years_it_uses():
    val = {"market": {"price": 100.0}, "classification": {"models": {}}}
    data = {"history": [], "quote": {}}
    for pct, want in ((0, "below each of its last 4 fiscal years' P/E"),
                      (100, "above each of its last 4 fiscal years' P/E"),
                      (50, "50th percentile of its last 4 fiscal years' P/E")):
        lt = {"valuation_history": {"percentile": pct, "median_pe": 30, "premium_to_median_pct": 0, "usable_years": 4}}
        ids = {c["id"]: c for c in quality.valuation_grade(val, data, lt, None, "operating", 0.1)["components"]}
        assert want in ids["own_history"]["headline"]
        assert "five-year" not in ids["own_history"]["headline"]
    assert "five-year range" not in quality.VALUATION_RUBRICS["own_history"]
