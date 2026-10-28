"""The valuation formulas against independently calculated reference cases.

Each reference value below is worked out by hand (or by a closed-form identity
that the forecast must reduce to), not by calling the code under test.
"""

import copy
import math

import pytest

from app.valuation import analysis, engine


def approx(x, rel=1e-9, abs_=1e-6):
    return pytest.approx(x, rel=rel, abs=abs_)


def base_case(**over):
    """A company whose base year ends on the valuation date, so discount
    times are whole years and the stub is a full year."""
    b = {
        "fy0_end": "2025-12-31", "balance_date": "2025-12-31", "valuation_date": "2025-12-31",
        "revenue": 1000.0, "ppe": None, "nwc": 0.0, "invested_capital": 500.0, "da_pct": 0.05,
        "nol": 0.0, "shares": 100.0, "price": 10.0, "risk_free": 0.04,
        "bridge": {"cash": 50.0, "short_term_investments": 0.0, "long_term_investments": 0.0,
                   "debt": 150.0, "finance_leases": 0.0, "preferred": 0.0,
                   "noncontrolling_interests": 0.0, "pension_deficit": 0.0},
    }
    b.update(over)
    return b


def drivers_case(g=0.03, margin=0.20, tax=0.25, n=5, method="fcf_growth", ronic=0.15,
                 convention="end_year", capex=0.05, da=0.05, nwc=0.0):
    return {
        "horizon": n, "convention": convention,
        "growth": {"y1": g, "y2": None},
        "margin": {"start": margin, "target": margin, "years": 1},
        "capex_pct": {"start": capex, "target": capex, "years": 1},
        "dep_rate": None, "da_pct": da, "nwc_pct": nwc,
        "tax": {"start": tax, "terminal": tax, "years": 1},
        "terminal": {"method": method, "growth": g, "ronic": ronic},
        "exit_multiple": None, "overrides": {},
    }


# ------------------------------------------------------------ closed forms

def test_constant_growth_reduces_to_the_gordon_formula():
    """Revenue, margin and reinvestment all constant: FCFF grows at g from
    year 1 forever, so EV must equal FCFF1 / (WACC - g) exactly, whatever the
    horizon."""
    b, w, g = base_case(), 0.09, 0.03
    fcff1 = 1000 * 1.03 * 0.20 * (1 - 0.25)          # capex = D&A, no working capital
    expected = fcff1 / (w - g)                        # 154.5 / 0.06 = 2575
    for n in (3, 5, 10, 15):
        r = engine.run_dcf(b, drivers_case(g=g, n=n), w)
        assert r["enterprise_value"] == approx(expected, rel=1e-10)
    assert expected == approx(2575.0)


def test_value_driver_terminal_value_matches_the_formula():
    """TV = NOPAT(N+1) x (1 - g / RONIC) / (WACC - g), by hand."""
    b, w = base_case(), 0.09
    d = drivers_case(g=0.03, method="value_driver", ronic=0.15)
    r = engine.run_dcf(b, d, w)
    rev5 = 1000 * 1.03 ** 5
    nopat6 = rev5 * 1.03 * 0.20 * 0.75
    assert r["terminal"]["nopat_next"] == approx(nopat6)
    assert r["terminal"]["value"] == approx(nopat6 * (1 - 0.03 / 0.15) / 0.06)
    assert r["terminal"]["pv"] == approx(r["terminal"]["value"] / 1.09 ** 5)


def test_growth_at_the_cost_of_capital_adds_no_value():
    """With RONIC = WACC the terminal value is NOPAT(N+1) / WACC whatever g is
    (growth earning exactly its cost creates nothing)."""
    b, w = base_case(), 0.09
    values = []
    for g in (0.0, 0.02, 0.04):
        d = drivers_case(g=0.03, method="value_driver", ronic=w)
        d["terminal"]["growth"] = g
        values.append(engine.terminal_value(engine.run_dcf(b, d, w)["rows"][-1], d, w))
    nopat_next = [v["nopat_next"] for v in values]
    for v, nn in zip(values, nopat_next):
        assert v["value"] == approx(nn / w)


def test_mid_year_convention_is_half_a_year_less_discounting():
    """Every flow and the perpetuity arrive half a year earlier, so with a
    full-year stub EV(mid) = EV(end) x (1 + WACC)^0.5 exactly."""
    b, w = base_case(), 0.08
    end = engine.run_dcf(b, drivers_case(convention="end_year", method="value_driver"), w)
    mid = engine.run_dcf(b, drivers_case(convention="mid_year", method="value_driver"), w)
    assert mid["enterprise_value"] == approx(end["enterprise_value"] * 1.08 ** 0.5, rel=1e-12)
    assert [r["discount_time"] for r in mid["rows"]] == approx([0.5, 1.5, 2.5, 3.5, 4.5])


def test_three_year_case_worked_by_hand():
    """Growth 10%, 5%, 0% (overridden per year), margin 20%, tax 25%, capex
    6%, D&A 4%, working capital 10% of revenue, end-of-year discounting at
    10%, terminal growth 0 with the growing-perpetuity form."""
    b = base_case(nwc=100.0)                          # 10% of revenue already
    d = drivers_case(g=0.0, n=3, capex=0.06, da=0.04, nwc=0.10)
    d["overrides"] = {"revenue_growth": {"1": 0.10, "2": 0.05, "3": 0.0}}
    r = engine.run_dcf(b, d, 0.10)
    revs = [1100.0, 1155.0, 1155.0]
    fcff = []
    prev_nwc = 100.0
    for rev in revs:
        nopat = rev * 0.20 * 0.75
        nwc = rev * 0.10
        fcff.append(nopat + rev * 0.04 - rev * 0.06 - (nwc - prev_nwc))
        prev_nwc = nwc
    assert fcff == approx([133.0, 144.65, 150.15])
    assert [x["fcff"] for x in r["rows"]] == approx(fcff)
    pv = 133.0 / 1.1 + 144.65 / 1.21 + 150.15 / 1.331
    tv = 150.15 / 0.10
    assert r["pv_forecast"] == approx(pv)
    assert r["enterprise_value"] == approx(pv + tv / 1.331)
    equity = pv + tv / 1.331 + 50.0 - 150.0
    assert r["per_share"] == approx(equity / 100.0)


def test_stub_counts_only_the_part_of_the_year_after_the_balance_sheet():
    b = base_case(balance_date="2026-06-30", valuation_date="2026-06-30")
    r = engine.run_dcf(b, drivers_case(convention="end_year"), 0.09)
    tm = r["timing"]
    assert tm["stub_fraction"] == approx(184 / 365)
    assert r["rows"][0]["fcff_counted"] == approx(r["rows"][0]["fcff"] * 184 / 365)
    assert r["rows"][0]["discount_time"] == approx(184 / 365)
    assert r["rows"][1]["discount_time"] == approx(1 + 184 / 365)


def test_flows_before_the_valuation_date_are_not_compounded_forward():
    b = base_case(balance_date="2025-12-31", valuation_date="2026-11-30")
    r = engine.run_dcf(b, drivers_case(convention="mid_year"), 0.09)
    assert r["rows"][0]["discount_time"] == 0.0


# ------------------------------------------------------------ bridge

def test_bridge_adds_non_operating_assets_and_subtracts_every_claim():
    items = {"cash": 10, "short_term_investments": 5, "long_term_investments": 7, "debt": 40,
             "finance_leases": 3, "preferred": 2, "noncontrolling_interests": 4, "pension_deficit": 1}
    br = engine.bridge(100.0, items)
    assert br["equity_value"] == approx(100 + 10 + 5 + 7 - 40 - 3 - 2 - 4 - 1)
    assert br["missing"] == []


def test_a_missing_claim_is_listed_not_zeroed_quietly():
    br = engine.bridge(100.0, {"cash": 10, "debt": None})
    assert "debt" in br["missing"]
    line = next(l for l in br["lines"] if l["key"] == "debt")
    assert line["value"] is None and line["included"] is False


def test_a_net_cash_company_is_worth_more_than_its_operations():
    b = base_case()
    b["bridge"] = dict(b["bridge"], cash=900.0, debt=0.0)
    r = engine.run_dcf(b, drivers_case(), 0.09)
    assert r["equity_value"] == approx(r["enterprise_value"] + 900.0)


def test_excluding_a_bridge_item_changes_equity_by_exactly_that_item():
    b = base_case()
    d = drivers_case()
    with_all = engine.run_dcf(b, d, 0.09)["equity_value"]
    d2 = dict(d, bridge_include={"debt": False})
    assert engine.run_dcf(b, d2, 0.09)["equity_value"] == approx(with_all + 150.0)


# ------------------------------------------------------------ discount rate

def test_wacc_by_hand():
    w = engine.wacc(0.10, 0.05, 0.25, 800.0, 200.0)
    assert w["wacc"] == approx(0.8 * 0.10 + 0.2 * 0.05 * 0.75)
    assert w["weight_debt"] == approx(0.2)


def test_cost_of_equity_is_capm():
    assert engine.cost_of_equity(0.04, 1.2, 0.05) == approx(0.10)


@pytest.mark.parametrize("coverage,rating,spread", [
    (100.0, "AAA", 0.0040), (8.5, "AAA", 0.0040), (8.49, "AA", 0.0055), (3.0, "A-", 0.0089),
    (2.6, "BBB", 0.0111), (1.0, "CCC", 0.0885), (0.1, "D", 0.19),
])
def test_synthetic_rating_thresholds(coverage, rating, spread):
    r = engine.synthetic_rating(coverage * 10.0, 10.0)
    assert (r["rating"], r["spread"]) == (rating, spread)


def test_no_interest_expense_reads_as_top_rated_and_says_so():
    r = engine.synthetic_rating(100.0, None)
    assert r["rating"] == "AAA" and r["note"]


# ------------------------------------------------------------ invalid inputs

def test_terminal_growth_at_or_above_the_discount_rate_is_refused():
    for g in (0.09, 0.10):
        d = drivers_case(g=0.03)
        d["terminal"]["growth"] = g
        with pytest.raises(engine.ModelError, match="below the discount rate"):
            engine.run_dcf(base_case(), d, 0.09)


def test_growth_needing_more_than_all_profit_reinvested_is_refused():
    d = drivers_case(method="value_driver", ronic=0.02)
    with pytest.raises(engine.ModelError, match="reinvested"):
        engine.run_dcf(base_case(), d, 0.09)


@pytest.mark.parametrize("over,match", [
    ({"shares": 0}, "share count"), ({"revenue": 0.0}, "positive revenue"),
])
def test_impossible_bases_are_refused(over, match):
    with pytest.raises(engine.ModelError, match=match):
        engine.run_dcf(base_case(**over), drivers_case(), 0.09)


def test_horizon_bounds():
    for n in (2, 16):
        with pytest.raises(engine.ModelError, match="horizon"):
            engine.run_dcf(base_case(), drivers_case(n=n), 0.09)


def test_depreciation_is_never_assumed_to_be_zero():
    d = drivers_case()
    d["da_pct"] = None
    with pytest.raises(engine.ModelError, match="not assumed"):
        engine.run_dcf(base_case(da_pct=None), d, 0.09)


def test_a_business_still_losing_money_at_the_end_is_flagged_not_meaningful():
    d = drivers_case(margin=-0.05)
    r = engine.run_dcf(base_case(), d, 0.09)
    assert any(c["code"] == "terminal_loss" and c["level"] == "error" for c in r["checks"])


def test_terminal_growth_above_the_risk_free_rate_is_flagged():
    d = drivers_case(g=0.03)
    d["terminal"]["growth"] = 0.05
    r = engine.run_dcf(base_case(risk_free=0.04), d, 0.09)
    codes = {c["code"] for c in r["checks"]}
    assert {"growth_above_rf", "growth_high"} <= codes


# ------------------------------------------------------------ losses and taxes

def test_losses_carry_forward_and_shelter_later_profit():
    d = drivers_case(n=3)
    d["overrides"] = {"ebit_margin": {"1": -0.10, "2": 0.05, "3": 0.20}}
    rows = engine.run_dcf(base_case(), d, 0.09)["rows"]
    ebit = [r["ebit"] for r in rows]
    assert rows[0]["taxes"] == 0.0
    loss = -ebit[0]
    assert rows[1]["taxes"] == 0.0 and rows[1]["nol_remaining"] == approx(loss - ebit[1])
    assert rows[2]["taxes"] == approx((ebit[2] - (loss - ebit[1])) * 0.25)


def test_ppe_roll_forward_drives_depreciation():
    b = base_case(ppe=400.0)
    d = drivers_case(n=3, capex=0.10)
    d["da_pct"], d["dep_rate"] = None, 0.10
    rows = engine.run_dcf(b, d, 0.09)["rows"]
    assert rows[0]["da"] == approx(40.0)
    assert rows[0]["ppe"] == approx(400 + 103 - 40)
    assert rows[1]["da"] == approx(0.10 * rows[0]["ppe"])


# ------------------------------------------------------------ other models

def test_two_stage_ddm_worked_by_hand():
    """D0 = 2, 10% growth for 3 years, 4% after, 10% cost of equity:
    each of the three dividends is worth exactly 2 today; the perpetuity is
    2.662 x 1.04 / 0.06 / 1.331."""
    r = engine.run_ddm(2.0, 0.10, 3, 0.04, 0.10)
    assert r["pv_dividends"] == approx(6.0)
    assert r["terminal_pv"] == approx(2.662 * 1.04 / 0.06 / 1.331)
    assert r["per_share"] == approx(6.0 + 34.66666666666667)


def test_residual_income_equals_single_stage_justified_price_to_book():
    """Constant 15% ROE, 10% cost of equity, retention giving 5% growth:
    value = BV x (ROE - g) / (r - g) = 10 x 0.10 / 0.05 = 20."""
    r = engine.run_residual_income(10.0, 0.15, 0.15, 0.10, 0.05, 0.05, years=10)
    assert all(row["payout"] == approx(2.0 / 3.0) for row in r["rows"])
    assert r["per_share"] == approx(20.0, rel=1e-9)
    assert engine.justified_pb(0.15, 0.10, 0.05) == approx(2.0)


def test_fcfe_equals_fcff_for_a_company_without_debt():
    b = base_case()
    b["bridge"] = dict(b["bridge"], debt=0.0)
    d = drivers_case(method="value_driver")
    firm = engine.run_dcf(b, d, 0.09)
    eq = engine.run_fcfe(b, d, 0.09, 0.05, 0.25, 0.0)
    assert eq["per_share"] == approx(firm["per_share"])


def test_comps_percentiles_and_the_bridge():
    val = engine.comps_value(100.0, [8, 10, 12, 14, 30], False, {"cash": 50.0, "debt": 150.0}, 10.0)
    assert val["mid"]["multiple"] == 12
    assert val["mid"]["per_share"] == approx((1200 + 50 - 150) / 10)
    assert engine.comps_value(100.0, [8, 10], False, {}, 10.0) is None
    assert engine.comps_value(-5.0, [8, 10, 12], True, {}, 1.0) is None


def test_sum_of_the_parts():
    r = engine.sotp([{"name": "A", "operating_income": 10, "multiple": 12},
                     {"name": "B", "operating_income": 5, "multiple": 20}], -2.0, 10.0,
                    {"cash": 5.0, "debt": 25.0}, 10.0)
    assert r["enterprise_value"] == approx(120 + 100 - 20)
    assert r["per_share"] == approx((200 + 5 - 25) / 10)


def test_three_statements_balance_and_reconcile_with_the_dcf():
    b = base_case(ppe=400.0, nwc=60.0)
    b["balance_sheet"] = {"cash": 80.0, "operating_current_assets": 160.0, "ppe": 400.0,
                          "investments": 20.0, "other_assets": 140.0,
                          "operating_current_liabilities": 100.0, "debt": 150.0,
                          "other_liabilities": 50.0, "equity": 500.0}
    assert 80 + 160 + 400 + 20 + 140 == 100 + 150 + 50 + 500
    d = drivers_case(n=5, capex=0.08, nwc=0.06)
    d["da_pct"], d["dep_rate"] = None, 0.10
    policy = {"interest_rate_debt": 0.05, "interest_rate_cash": 0.03, "payout_ratio": 0.4,
              "buyback_ratio": 0.3, "min_cash": 20.0}
    r = engine.three_statement(b, d, policy)
    assert r["balances"]
    for y in r["years"]:
        assert abs(y["balance_check"]) < 1e-9
        assert y["fcff_from_statements"] == approx(y["fcff_dcf"])
        assert y["change_cash"] == approx(y["cfo"] + y["cfi"] + y["cff"])


def test_payouts_give_way_before_the_cash_floor():
    b = base_case(ppe=400.0, nwc=60.0)
    b["balance_sheet"] = {"cash": 21.0, "operating_current_assets": 160.0, "ppe": 400.0,
                          "investments": 0.0, "other_assets": 0.0,
                          "operating_current_liabilities": 100.0, "debt": 150.0,
                          "other_liabilities": 0.0, "equity": 331.0}
    d = drivers_case(n=3, capex=0.30, nwc=0.06)
    d["da_pct"], d["dep_rate"] = None, 0.10
    policy = {"interest_rate_debt": 0.05, "interest_rate_cash": 0.0, "payout_ratio": 0.5,
              "buyback_ratio": 0.5, "min_cash": 20.0}
    r = engine.three_statement(b, d, policy)
    assert r["balances"]
    y1 = r["years"][0]
    assert y1["buybacks"] == 0.0 and y1["cash"] == approx(20.0)


# ------------------------------------------------------------ analysis

def test_sensitivity_centre_cell_is_the_base_value():
    b, d, w = base_case(), drivers_case(method="value_driver"), 0.09
    centre = engine.run_dcf(b, d, w)["per_share"]
    s = analysis.sensitivity(b, d, w)
    assert s["wacc_growth"]["values"][2][2] == approx(centre)
    assert s["margin_growth"]["values"][2][2] == approx(centre)
    # Higher discount rate, lower value; higher growth, higher value.
    col = [row[2] for row in s["wacc_growth"]["values"]]
    assert col == sorted(col, reverse=True)


def test_sensitivity_cells_that_break_the_model_are_empty():
    b, d = base_case(), drivers_case(method="value_driver")
    s = analysis.sensitivity(b, d, 0.04)              # 4% - 1pt vs growth 3% + 1pt
    assert s["wacc_growth"]["values"][0][4] is None


def test_tornado_is_ranked_by_swing():
    b, d, w = base_case(), drivers_case(method="value_driver"), 0.09
    bars = analysis.tornado(b, d, w, engine.run_dcf(b, d, w)["per_share"])
    swings = [x["swing"] for x in bars]
    assert swings == sorted(swings, reverse=True)
    assert {x["key"] for x in bars} >= {"wacc", "margin", "growth", "terminal_growth"}


def test_reverse_dcf_solutions_reproduce_the_price():
    b, d, w = base_case(price=30.0), drivers_case(method="value_driver"), 0.09
    rev = analysis.reverse_dcf(b, d, w)
    by = {s["key"]: s for s in rev["solves"]}
    g = copy.deepcopy(d)
    g["growth"]["y1"] = by["growth"]["value"]
    assert engine.run_dcf(b, g, w)["per_share"] == approx(30.0, rel=1e-5)
    m = copy.deepcopy(d)
    m["margin"]["target"] = by["margin"]["value"]
    assert engine.run_dcf(b, m, w)["per_share"] == approx(30.0, rel=1e-5)
    assert engine.run_dcf(b, d, by["wacc"]["value"])["per_share"] == approx(30.0, rel=1e-5)
    for s in rev["solves"]:
        assert s["held"]


def test_upside_and_margin_of_safety_are_different_quantities():
    v = analysis.versus_price(125.0, 100.0)
    assert v["upside"] == approx(0.25) and v["margin_of_safety"] == approx(0.20)
    assert analysis.versus_price(-5.0, 100.0)["margin_of_safety"] is None


def test_growth_path_fades_to_terminal_and_overrides_win():
    p = engine.growth_path(0.20, 0.02, 4)
    assert p == approx([0.20, 0.155, 0.11, 0.065])
    p2 = engine.growth_path(0.20, 0.02, 4, 0.30)
    assert p2[:2] == [0.20, 0.30] and p2[-1] > 0.02
    assert engine.apply_overrides([1, 2, 3], {"2": 9, "x": 1, "7": 4}) == [1, 9, 3]


def test_fcfe_finances_reinvestment_at_the_target_ratio_and_not_losses():
    b = base_case(ppe=400.0)
    d = drivers_case(n=3, capex=0.10)
    d["da_pct"], d["dep_rate"] = None, 0.05
    d["overrides"] = {"ebit_margin": {"1": -0.10}}
    r = engine.run_fcfe(b, d, 0.10, 0.05, 0.25, 0.3)
    fc = engine.operating_forecast(b, d)["rows"]
    for row, f in zip(r["rows"], fc):
        assert row["net_borrowing"] == approx(0.3 * f["net_reinvestment"])
    with pytest.raises(engine.ModelError):
        engine.run_fcfe(b, d, 0.10, 0.05, 0.25, 1.0)


def test_incremental_return_measures_what_new_capital_earns():
    b = base_case(ppe=400.0)
    d = drivers_case(n=5, capex=0.60, g=0.01)
    d["da_pct"], d["dep_rate"] = None, 0.05
    r = engine.run_dcf(b, d, 0.09)
    inc = engine.incremental_return(r["rows"])
    rows = r["rows"]
    assert inc == approx((rows[-1]["nopat"] - rows[0]["nopat"]) / sum(x["net_reinvestment"] for x in rows[:-1]))
    assert inc < 0.045
    assert any(c["code"] == "low_incremental_return" for c in r["checks"])
    assert engine.incremental_return(engine.run_dcf(base_case(), drivers_case(), 0.09)["rows"]) is None


def test_growth_can_fade_faster_than_the_forecast():
    p = engine.growth_path(0.60, 0.02, 10, None, 6)
    assert p[0] == approx(0.60) and p[5] == approx(0.60 + (0.02 - 0.60) * 5 / 6)
    assert p[6:] == approx([0.02] * 4)
    assert engine.growth_path(0.2, 0.02, 4) == engine.growth_path(0.2, 0.02, 4, None, None)


def test_revenue_multiplying_is_flagged():
    d = drivers_case(g=0.03, n=10)
    d["growth"]["y1"] = 0.6
    r = engine.run_dcf(base_case(), d, 0.12)
    assert any(c["code"] == "revenue_multiplies" for c in r["checks"])


def test_the_data_notes_speak_in_words_and_dollars():
    """NVIDIA's DCF printed "Restated in a later filing: basic_shares_avg, diluted_shares_avg, dps, eps_diluted"
    and debt as "33,366,000,000" (investor audit, 2026-10-27)."""
    from app.valuation import inputs
    assert inputs._usd_short(33_366_000_000) == "$33.4B" and inputs._usd_short(-1_200_000) == "-$1.2M"
    assert not (inputs.FLOWS - set(inputs.FLOW_WORDS)), "every statement line has words"
    assert inputs.FLOW_WORDS["eps_diluted"] == "diluted EPS"
