"""Regression tests for the issues reproduced in the 2026-10-22 audit and motion session.

Each test names the reproduction: the ticker or fixture that showed it, and what the page said.
Findings and evidence: ~/Optic/work/audit-motion-2026-10-22/COVERAGE.md.
"""
from __future__ import annotations

import pandas as pd
import pytest

from app.analytics import earnings as E
from app.analytics import fundamentals as F


# ------------------------------------------------------------------ Financials and Earnings

def test_an_estimate_with_no_analysts_is_no_estimate_and_growth_from_a_negative_base_is_none():
    # SIEB: a 0.0 revenue average with nobody behind it read "Analysts expect about $0 of revenue"
    # RIVN: -2.43 for the year read "+20.8% EPS growth" from Yahoo's growth on a negative base
    g = E._growth({}, {"eps_estimate": {"0q": {"avg": -0.72, "growth": 0.25, "numberOfAnalysts": 11, "yearAgoEps": -0.96},
                                         "0y": {"avg": 1.5, "growth": 0.2, "numberOfAnalysts": 15, "yearAgoEps": 1.25},
                                         "+1y": {"avg": 0.4, "growth": 0.3, "numberOfAnalysts": 0}},
                       "revenue_estimate": {"0q": {"avg": 0.0, "numberOfAnalysts": 0}}})
    by = {f["period"]: f for f in g["forward"]}
    assert by["0q"]["eps_growth_pct"] is None and by["0q"]["revenue_avg"] is None and by["0q"]["revenue_label"] is None
    assert by["0y"]["eps_growth_pct"] == 20.0
    assert "+1y" not in by, "no analysts and no revenue: nothing to show"
    assert not any("EPS growth" in n for n in g["notes"]) or by["0y"]["eps_growth_pct"] is not None


def test_two_consensus_figures_for_one_quarter_are_named_and_one_analyst_is_not_agreement():
    nr = {"eps_consensus": -0.65, "eps_low": -0.81, "eps_high": -0.55, "dispersion_note": "Analysts disagree widely.", "eps_dispersion_pct": 40.1}
    E._reconcile_consensus(nr, {"forward": [{"period": "0q", "eps_avg": -0.72, "eps_analysts": 11}]})
    assert "-0.65" in nr["consensus_note"] and "-0.72" in nr["consensus_note"]
    assert nr["dispersion_note"] == "Analysts disagree widely.", "eleven analysts can disagree"
    one = {"eps_consensus": 0.91, "eps_low": 0.91, "eps_high": 0.91, "dispersion_note": "Analysts are tightly clustered.", "eps_dispersion_pct": 0.0}
    E._reconcile_consensus(one, {"forward": [{"period": "0q", "eps_avg": 0.91, "eps_analysts": 1}]})
    assert "consensus_note" not in one and one["eps_dispersion_pct"] is None
    assert one["dispersion_note"].startswith("Only 1 analyst estimate ")


def test_the_average_surprise_leaves_out_quarters_with_an_estimate_at_or_below_zero():
    # CRCL: an estimate of -0.16 made one quarter +813.9% and the average +249%
    rows = [{"date": "2026-08-12", "eps_estimate": -0.16, "eps_reported": 1.14, "surprise_pct": 813.92},
            {"date": "2026-05-12", "eps_estimate": 0.20, "eps_reported": 0.23, "surprise_pct": 15.0},
            {"date": "2026-02-12", "eps_estimate": 0.25, "eps_reported": 0.27, "surprise_pct": 8.0}]
    out = F.analyse_earnings_history(rows)
    assert "average surprise +11.5% over the 2 with a positive estimate" in out["notes"][0]
    assert "GAAP" in out["eps_basis"], "the track record says which basis it is on"


def test_a_record_with_misses_is_not_called_a_consistent_large_beat():
    rows = [{"date": f"2026-0{m}-10", "eps_estimate": 1.0, "eps_reported": r, "surprise_pct": (r - 1) * 100}
            for m, r in ((9, 1.3), (6, 0.8), (3, 1.25), (1, 0.85))]
    notes = F.analyse_earnings_history(rows)["notes"]
    assert any("not dependable" in n for n in notes)
    assert not any("already in the price" in n for n in notes), "RIVN said both at once"


def test_margins_keep_four_places_so_every_display_rounds_once():
    raw = {"income_annual": {"periods": ["2025", "2024"], "rows": {"Total Revenue": [1000.0, 900.0], "Operating Income": [-665.49, -600.0], "Net Income": [-700.0, -650.0]}}}
    m = F.analyse_financials(raw)["margins"]
    assert m["operating_pct"] == pytest.approx(-66.549, abs=1e-3)


def test_reports_more_than_three_years_before_the_newest_are_not_the_last_eight():
    # ESP: "the last 8 reports" ran from 2026 back to 2013
    hist = [{"date": d, "eps_estimate": 0.5, "eps_reported": 0.6} for d in ("2026-09-23", "2026-06-20", "2025-12-10", "2016-03-01", "2013-11-14")]
    out = E._surprise_history(hist, pd.DataFrame())
    assert [r["date"] for r in out["rows"]] == ["2026-09-23", "2026-06-20", "2025-12-10"]


def test_estimate_revisions_make_no_unmeasured_historical_claim():
    # RIVN, CRCL, NVDA and MSFT all read "which historically precedes beats more often than misses"
    for d in ("rising", "falling"):
        v = E._verdict({"date": "2026-11-20", "days_away": 30}, {}, {"direction": d}, {}, {})
        text = " ".join(str(x) for x in (v.get("reasons") or []) + [v.get("headline") or ""])
        assert "historically" not in text and "deteriorating guidance" not in text, text
        assert ("not measured" in text) if d == "rising" else ("not in this data" in text)


# ------------------------------------------------------------------ Portfolio scenarios (stage 6 code)

from datetime import datetime, timezone  # noqa: E402

from app.analytics import scenarios as SC  # noqa: E402

_NOW = datetime(2026, 10, 22, 17, 0, tzinfo=timezone.utc)


def test_coverage_is_a_share_of_everything_held_not_of_what_was_priced():
    # edge sandbox: one of five positions priced read value_covered_pct 100.0
    legs = [{"symbol": "AAA", "kind": "stock", "qty": 10, "price": 100.0},
            {"symbol": "BTC", "label": "Bitcoin", "kind": "stock", "qty": 1, "price": 3000.0, "not_modelled": "Not a stock or fund."},
            {"symbol": "SHOP.TO", "kind": "stock", "qty": 5, "price": 80.0, "ref_value": None, "not_modelled": "Priced in CAD."}]
    out = SC.build(legs, {"AAA": {"price": 100.0, "as_of": _NOW.isoformat()}}, {}, 0.04, _NOW)
    c = out["coverage"]
    assert c["priced"] == 1 and c["positions"] == 3
    assert c["value_covered_pct"] == 25.0, "1,000 of 4,000 with a known dollar value"
    assert {u["label"] for u in c["unpriced"]} == {"Bitcoin", "Long 5 SHOP.TO shares"}


def test_a_name_with_nothing_priced_is_unknown_not_zero_and_a_missing_quote_is_said():
    legs = [{"symbol": "AAA", "kind": "stock", "qty": 10, "price": 100.0},
            {"symbol": "MMM", "kind": "option", "qty": 2, "option_type": "call", "strike": 420, "expiry": "2026-11-20", "price": None},
            {"symbol": "ZZZ", "kind": "stock", "qty": 10, "price": 50.0, "price_basis": "the broker's price at its last sync"}]
    out = SC.build(legs, {"AAA": {"price": 100.0, "as_of": _NOW.isoformat()}, "MMM": {"price": 400.0, "as_of": _NOW.isoformat()}}, {}, 0.04, _NOW)
    row = {r["symbol"]: r for r in out["exposure"]["by_underlying"]}
    assert row["MMM"]["delta_adjusted"] is None and row["MMM"]["share_pct"] is None and "Not valued" in row["MMM"]["note"]
    assert any("No current quote for ZZZ" in s["reason"] and "broker's price" in s["reason"] for s in out["coverage"]["stale"])
