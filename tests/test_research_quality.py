"""Business quality, valuation and long-term conviction, on synthetic filings.

The fixtures are shaped like `app/valuation/inputs.gather`: newest year first,
each with `flows`, `balance` and `derived`, every figure a fact dict."""

from __future__ import annotations

import pytest

from app.research import policy, quality

VALUES = policy.current()["values"]


def fact(v, filed="2026-02-01", end=None):
    return None if v is None else {"value": v, "filed": filed, "end": end, "url": "https://www.sec.gov/x",
                                   "form": "10-K", "tag": "Tag"}


def year(fy, rev, ebit, ni, cfo, capex, sbc=0.02, shares=1000.0, gp=None, da=None, interest=None,
         equity=500.0, debt=200.0, cash=100.0, roic=None, ic=600.0, tax=0.2, change_nwc=0.0, roe=None,
         filed=None, ca=None, cl=None):
    return {"fy_end": "{}-12-31".format(fy),
            "flows": {"revenue": fact(rev), "operating_income": fact(ebit), "net_income": fact(ni),
                      "cfo": fact(cfo), "capex": fact(capex), "sbc": fact(rev * sbc),
                      "diluted_shares_avg": fact(shares, filed=filed or "{}-02-01".format(fy + 1)),
                      "gross_profit": fact(gp), "da": fact(da if da is not None else rev * 0.04),
                      "interest_expense": fact(interest)},
            "balance": {"equity": fact(equity), "debt": fact(debt), "cash": fact(cash),
                        "assets_current": fact(ca), "liabilities_current": fact(cl)},
            "derived": {"ebit_margin": ebit / rev, "roic": roic, "invested_capital": ic,
                        "effective_tax_rate": tax, "sbc_pct": sbc, "revenue_growth": None,
                        "change_nwc": change_nwc, "roe": roe, "fcff": None}}


def strong_company():
    hist = []
    rev = 1000.0
    for i, fy in enumerate(range(2025, 2020, -1)):
        r = rev / (1.12 ** i)
        hist.append(year(fy, r, r * 0.30, r * 0.24, r * 0.30, r * 0.05, shares=1000 * (1.02 ** i),
                         gp=r * 0.62, interest=r * 0.01, roic=0.32))
    for i in range(len(hist) - 1):
        hist[i]["derived"]["revenue_growth"] = hist[i]["flows"]["revenue"]["value"] / hist[i + 1]["flows"]["revenue"]["value"] - 1
    return {"history": hist, "balance": hist[0]["balance"], "quote": {"market_cap": 20000.0},
            "risk_free": {"value": 0.042}}


def test_a_strong_company_grades_a_with_every_component_scored():
    q = quality.business_quality(strong_company(), "operating", 0.09, None, VALUES)
    assert q["status"] == "scored" and q["grade"] == "A"
    ids = {c["id"]: c for c in q["components"]}
    assert all(c["status"] == "scored" for c in ids.values())
    assert ids["returns"]["figures"]["spread"] == pytest.approx(0.32 - 0.09)
    # Every component carries its rubric and a source link where it read a filing.
    assert all(c["rubric"] for c in ids.values())
    assert ids["returns"]["sources"][0]["url"].startswith("https://www.sec.gov")


def test_missing_data_is_insufficient_not_a_low_grade():
    data = {"history": [year(2025, 1000, 200, 150, None, None, shares=None)],
            "balance": {}, "quote": {}, "risk_free": {}}
    q = quality.business_quality(data, "operating", None, None, VALUES)
    assert q["status"] == "insufficient" and q["grade"] is None
    assert "not a low grade" in q["reason"]
    assert quality.conviction(q, {"status": "insufficient"}, {"state": "intact"}, VALUES)["label"] == "Insufficient Data"


def test_negative_earnings_measure_runway_not_coverage():
    hist = [year(2025, 1000, -300, -350, -200, 100, cash=900, debt=100),
            year(2024, 800, -400, -420, -300, 120)]
    c = quality.health_component(hist, hist[0]["balance"], "operating", VALUES)
    assert c["status"] == "scored"
    assert c["figures"]["runway_years"] == pytest.approx(900 / 300)
    assert "undefined" in " ".join(c["evidence"])


def test_banks_use_return_on_equity_and_skip_operating_measures():
    hist = []
    for i, fy in enumerate(range(2025, 2020, -1)):
        hist.append(year(fy, 100.0 / (1.05 ** i), 40, 30, 500, 0, roe=0.15, shares=1000 * (0.98 ** -i)))
    data = {"history": hist, "balance": hist[0]["balance"], "quote": {}, "risk_free": {}}
    q = quality.business_quality(data, "bank", None, 0.10, VALUES)
    ids = {c["id"]: c for c in q["components"]}
    assert ids["returns"]["status"] == "scored" and ids["returns"]["figures"]["cost_equity"] == 0.10
    for cid in ("margins", "cash", "health"):
        assert ids[cid]["status"] == "not_applicable" and ids[cid]["reason"]


def test_reit_is_insufficient_rather_than_graded_on_the_wrong_measures():
    hist = [year(fy, 100.0 * (1.1 ** (2025 - fy)), 30, 20, 60, 10) for fy in range(2025, 2020, -1)]
    data = {"history": hist, "balance": hist[0]["balance"], "quote": {}, "risk_free": {}}
    q = quality.business_quality(data, "reit", 0.08, 0.09, VALUES)
    ids = {c["id"]: c for c in q["components"]}
    assert ids["returns"]["status"] == "not_applicable" and ids["health"]["status"] == "not_applicable"
    assert q["status"] == "insufficient"


def test_split_adjusts_share_counts_filed_before_the_split():
    # NVIDIA-shaped: the oldest year's count was filed before a 10-for-1.
    hist = [year(2025, 1000, 300, 250, 300, 50, shares=24500, filed="2026-02-25"),
            year(2024, 900, 270, 220, 270, 45, shares=24800, filed="2026-02-25"),
            year(2023, 800, 240, 200, 240, 40, shares=2500, filed="2024-02-21")]
    raw = quality.dilution_component(hist, "operating")
    adj = quality.dilution_component(hist, "operating", [{"date": "2024-06-10", "ratio": 10.0}])
    assert raw["figures"]["share_change_a_year"] > 1.0          # the bug: "rose 213% a year"
    assert adj["figures"]["share_change_a_year"] == pytest.approx((24500 / 25000) ** 0.5 - 1, abs=1e-6)
    assert adj["figures"]["split_adjusted"] is True


def test_launch_years_with_tiny_revenue_are_left_out():
    hist = [year(2025, 5000, -3000, -3500, -2000, 500), year(2024, 4000, -4000, -4500, -3000, 600),
            year(2023, 1600, -6000, -6500, -4000, 800), year(2022, 55, -4200, -4700, -2600, 600)]
    m = quality.margins_component(hist, "operating")
    assert m["figures"]["years"] == 3                          # FY2022's -7,600% margin is excluded


def test_cash_below_profit_one_year_is_a_question_not_a_finding():
    hist = [year(2025, 1000, 300, 250, 150, 50, change_nwc=90), year(2024, 900, 270, 220, 260, 45),
            year(2023, 800, 240, 200, 240, 40)]
    c = quality.cash_component(hist, "operating", 3)
    text = " ".join(c["evidence"])
    assert "question to follow up" in text and "Working capital absorbed" in text


def test_conviction_rules():
    good_q = {"status": "scored", "grade": "A", "components": []}
    b_q = {"status": "scored", "grade": "B", "components": []}
    c_q = {"status": "scored", "grade": "C", "components": []}
    d_q = {"status": "scored", "grade": "D", "components": []}
    attractive = {"status": "scored", "label": "Attractive"}
    stretched = {"status": "scored", "label": "Stretched"}
    intact, broken = {"state": "intact"}, {"state": "broken"}
    assert quality.conviction(good_q, attractive, intact, VALUES)["label"] == "High Conviction"
    assert quality.conviction(b_q, attractive, intact, VALUES)["label"] == "Constructive"
    assert quality.conviction(good_q, stretched, intact, VALUES)["label"] == "Neutral"
    # Below the cap grade: Neutral at best, whatever the price, and the rule is named.
    out = quality.conviction(c_q, attractive, intact, VALUES)
    assert out["label"] == "Neutral" and out["rules"][0]["rule"] == "quality_cap_grade"
    assert quality.conviction(c_q, attractive, broken, VALUES)["label"] == "Weak Structure"
    assert quality.conviction(d_q, attractive, intact, VALUES)["label"] == "Not Investable"
    # A good business with a broken chart is a technical problem, said as one.
    out = quality.conviction(good_q, attractive, broken, VALUES)
    assert out["label"] == "Weak Structure" and "not by itself a failed business thesis" in out["why"]


def test_the_cap_grade_is_configurable():
    v = policy.current({"quality_cap_grade": "C"})["values"]
    c_q = {"status": "scored", "grade": "C", "components": []}
    assert quality.conviction(c_q, {"status": "scored", "label": "Attractive"}, {"state": "intact"},
                              v)["label"] == "Constructive"


def test_valuation_matches_cash_flow_to_value():
    data = strong_company()
    val = {"market": {"price": 100.0}, "classification": {"models": {"dcf": {"fit": "primary", "name": "DCF"}},
                                                           "confidence": "normal"},
           "dcf": {"per_share": 140.0}, "scenarios": {"bear": {"per_share": 90.0}, "bull": {"per_share": 190.0}},
           "reverse": {"solves": [{"implied_cagr": 0.06}]}}
    lt = {"valuation_history": {"percentile": 30, "median_pe": 25, "premium_to_median_pct": -8}}
    out = quality.valuation_grade(val, data, lt, None, "operating", 0.12)
    ids = {c["id"]: c for c in out["components"]}
    assert ids["intrinsic"]["score"] == 4 and ids["own_history"]["score"] == 3
    cy = ids["cash_yield"]["figures"]
    # Free cash flow to equity over market value; FCFF over EV reported beside it.
    assert cy["fcfe_yield"] == pytest.approx((300 - 50) / 20000.0)
    assert "enterprise value" in " ".join(ids["cash_yield"]["evidence"])
    assert out["status"] == "scored" and out["label"] in ("Attractive", "Fair")


def test_a_limited_fit_model_is_shown_not_graded():
    val = {"market": {"price": 100.0}, "classification": {"models": {"dcf": {"fit": "limited"}}, "confidence": "low"},
           "dcf": {"per_share": 300.0}}
    out = quality.valuation_grade(val, {"history": [], "quote": {}}, {}, None, "unprofitable", None)
    ids = {c["id"]: c for c in out["components"]}
    assert ids["intrinsic"]["status"] == "not_applicable" and out["status"] == "insufficient"


def test_zones_only_when_conviction_allows_and_never_an_allocation():
    q = {"status": "scored", "grade": "A", "weakest": "growth", "components": [{"id": "growth", "label": "Revenue growth"}]}
    lt = {"price": 100.0, "long_trend": {"sma_40w": 92.0, "sma_200w": 70.0}, "levels": {"support_resistance": []}}
    z = quality.accumulation_zones(lt, q, {"components": []}, {"label": "Neutral"})
    assert z["offered"] is False
    z = quality.accumulation_zones(lt, q, {"components": []}, {"label": "Constructive"})
    assert z["offered"] and z["zones"][0]["price"] == 92.0
    assert "no allocation" in z["condition"]


def test_two_loss_paths_with_numbers():
    data = strong_company()
    lt = {"valuation_history": {"premium_to_median_pct": 40}, "drawdown": {"max_drawdown_pct": -45,
                                                                           "max_drawdown_date": "2022-10-14"}}
    paths = quality.loss_paths(data, {"components": []}, {"components": []}, lt)
    assert len(paths) == 2 and paths[0]["risk"] == "Multiple compression"
    assert "29%" in paths[0]["text"]                            # 1 - 1/1.4
