"""Reading valuation inputs from XBRL facts: periods, tags, and no double counts."""

import pytest

from app.valuation import inputs


def fact(val, end, start=None, form="10-K", filed="2026-02-10", fp="FY", accn="0000000001-26-000001"):
    r = {"val": val, "end": end, "form": form, "filed": filed, "fp": fp, "accn": accn, "fy": 2025}
    if start:
        r["start"] = start
    return r


def filings(gaap, dei=None):
    blob = {"entityName": "Test Co", "facts": {"us-gaap": {
        tag: {"units": {unit: rows}} for tag, (unit, rows) in gaap.items()}}}
    if dei:
        blob["facts"]["dei"] = {tag: {"units": {"shares": rows}} for tag, rows in dei.items()}
    return inputs.Filings(blob, "0000000001", "2026-10-01T00:00:00+00:00")


USD = "USD"


def test_an_instant_on_the_exact_date_is_found():
    """Regression: a zero-day gap must count as a match (0 is falsy)."""
    fl = filings({"Assets": (USD, [fact(100.0, "2025-12-31")])})
    assert fl.instant("assets", "2025-12-31")["value"] == 100.0
    assert fl.instant("assets", "2025-12-25") is None


def test_an_annual_flow_needs_an_annual_duration():
    fl = filings({"Revenues": (USD, [fact(90.0, "2025-12-31", "2025-10-01", form="10-K"),
                                     fact(400.0, "2025-12-31", "2025-01-01")])})
    assert fl.flow("revenue", "2025-12-31")["value"] == 400.0


def test_a_restated_year_takes_the_latest_filing_and_says_so():
    fl = filings({"Revenues": (USD, [fact(400.0, "2025-12-31", "2025-01-01", filed="2026-02-10"),
                                     fact(390.0, "2025-12-31", "2025-01-01", filed="2027-02-10",
                                          accn="0000000001-27-000001")])})
    f = fl.flow("revenue", "2025-12-31")
    assert f["value"] == 390.0 and f["restated"] and f["first_filed"] == "2026-02-10"
    assert f["url"].endswith("/000000000127000001/")


def test_fiscal_year_ends_cluster_52_53_week_years():
    rows = [fact(1.0, "2025-09-27", "2024-09-29"), fact(1.0, "2024-09-28", "2023-10-01"),
            fact(1.0, "2023-09-30", "2022-09-25")]
    fl = filings({"Revenues": (USD, rows)})
    assert fl.fiscal_year_ends() == ["2025-09-27", "2024-09-28", "2023-09-30"]


def test_priority_tag_wins_when_two_report_the_same_year():
    fl = filings({"Revenues": (USD, [fact(500.0, "2025-12-31", "2025-01-01")]),
                  "RevenueFromContractWithCustomerExcludingAssessedTax": (USD, [fact(450.0, "2025-12-31", "2025-01-01")])})
    assert fl.flow("revenue", "2025-12-31")["tag"] == "Revenues"


# ------------------------------------------------------------------ debt

D = "2026-06-30"


def test_debt_reported_with_finance_leases_does_not_add_leases_again():
    fl = filings({"LongTermDebtAndCapitalLeaseObligationsIncludingCurrentMaturities": (USD, [fact(136.0, D, form="10-Q")]),
                  "FinanceLeaseLiability": (USD, [fact(1.4, D, form="10-Q")]),
                  "CommercialPaper": (USD, [fact(2.0, D, form="10-Q")])})
    bs = inputs.balance_sheet(fl, D)
    assert bs["debt"]["value"] == 138.0
    assert bs["debt_includes_finance_leases"]
    assert bs["finance_leases"]["value"] == 0.0 and bs["finance_leases"]["kind"] == "included_elsewhere"


def test_pure_debt_leaves_finance_leases_to_be_added():
    fl = filings({"LongTermDebt": (USD, [fact(40.0, D)]),
                  "FinanceLeaseLiability": (USD, [fact(66.0, D)])})
    bs = inputs.balance_sheet(fl, D)
    assert bs["debt"]["value"] == 40.0 and bs["finance_leases"]["value"] == 66.0


def test_debt_current_already_holds_short_term_borrowings():
    fl = filings({"LongTermDebtAndCapitalLeaseObligations": (USD, [fact(134.6, D, form="10-Q")]),
                  "DebtCurrent": (USD, [fact(9.3, D, form="10-Q")]),
                  "ShortTermBorrowings": (USD, [fact(5.0, D, form="10-Q")])})
    debt = inputs.debt_on(fl, D)
    assert debt["value"] == pytest.approx(143.9)
    assert debt["includes_finance_leases"]


def test_reit_style_instruments_are_summed_and_flagged():
    fl = filings({"NotesPayable": (USD, [fact(25.0, D)]), "SecuredDebt": (USD, [fact(0.5, D)]),
                  "CommercialPaper": (USD, [fact(0.5, D)])})
    debt = inputs.debt_on(fl, D)
    assert debt["value"] == pytest.approx(26.0)
    assert "summed" in debt["rule"] and debt["fact"]["note"]


def test_no_debt_tagged_reads_as_none_and_says_so():
    fl = filings({"Assets": (USD, [fact(10.0, D)])})
    debt = inputs.debt_on(fl, D)
    assert debt["value"] == 0.0 and debt["fact"]["kind"] == "not_reported" and debt["fact"]["note"]


# ------------------------------------------------------------------ balance sheet

def test_working_capital_excludes_cash_investments_debt_and_leases():
    fl = filings({"AssetsCurrent": (USD, [fact(100.0, D)]), "LiabilitiesCurrent": (USD, [fact(80.0, D)]),
                  "CashAndCashEquivalentsAtCarryingValue": (USD, [fact(20.0, D)]),
                  "ShortTermInvestments": (USD, [fact(10.0, D)]),
                  "LongTermDebtNoncurrent": (USD, [fact(50.0, D)]), "LongTermDebtCurrent": (USD, [fact(5.0, D)]),
                  "OperatingLeaseLiabilityCurrent": (USD, [fact(3.0, D)])})
    bs = inputs.balance_sheet(fl, D)
    assert bs["nwc"]["value"] == pytest.approx((100 - 20 - 10) - (80 - 5 - 3))


def test_an_unclassified_balance_sheet_has_no_working_capital():
    fl = filings({"CashAndCashEquivalentsAtCarryingValue": (USD, [fact(20.0, D)])})
    bs = inputs.balance_sheet(fl, D)
    assert bs["nwc"]["value"] is None and bs["nwc"]["reason"]


def test_equity_method_stakes_inside_long_term_investments_are_not_added_twice():
    fl = filings({"LongTermInvestments": (USD, [fact(36.0, D)]), "EquityMethodInvestments": (USD, [fact(12.0, D)])})
    assert inputs.investments_on(fl, D)["value"] == 36.0
    fl2 = filings({"MarketableSecuritiesNoncurrent": (USD, [fact(10.0, D)]),
                   "EquityMethodInvestments": (USD, [fact(12.0, D)])})
    assert inputs.investments_on(fl2, D)["value"] == 22.0


def test_a_pension_surplus_is_not_added_and_a_deficit_is_a_claim():
    deficit = filings({"DefinedBenefitPlanFundedStatusOfPlan": (USD, [fact(-4.0, "2025-12-31")])})
    assert inputs.balance_sheet(deficit, D)["pension_deficit"]["value"] == 4.0
    surplus = filings({"DefinedBenefitPlanFundedStatusOfPlan": (USD, [fact(8.0, "2025-12-31")])})
    assert inputs.balance_sheet(surplus, D)["pension_deficit"]["value"] == 0.0


# ------------------------------------------------------------------ shares

def _dil(diluted, basic, end=D, start="2026-04-01"):
    return {"WeightedAverageNumberOfDilutedSharesOutstanding": ("shares", [fact(diluted, end, start, form="10-Q")]),
            "WeightedAverageNumberOfSharesOutstandingBasic": ("shares", [fact(basic, end, start, form="10-Q")])}


def test_shares_are_the_cover_count_plus_the_reported_dilution():
    fl = filings({**_dil(103.0, 100.0), "Assets": (USD, [fact(1.0, D, form="10-Q")])},
                 dei={"EntityCommonStockSharesOutstanding": [fact(99.0, "2026-07-20", form="10-Q")]})
    s = inputs.shares(fl, {"price": 10.0, "market_cap": 990.0}, None)
    assert s["value"] == 102.0 and s["increment"] == 3.0
    assert "cross_check" not in s


def test_several_share_classes_fall_back_to_the_balance_sheet_count():
    fl = filings({**_dil(12.38, 12.23), "Assets": (USD, [fact(1.0, D, form="10-Q")]),
                  "CommonStockSharesOutstanding": ("shares", [fact(12.23, D, form="10-Q")])})
    s = inputs.shares(fl, {}, None)
    assert s["value"] == pytest.approx(12.38) and "balance-sheet" in s["method"]


def test_a_share_count_far_from_the_market_value_is_flagged():
    fl = filings({**_dil(100.0, 100.0), "Assets": (USD, [fact(1.0, D, form="10-Q")])},
                 dei={"EntityCommonStockSharesOutstanding": [fact(100.0, "2026-07-20")]})
    s = inputs.shares(fl, {"price": 10.0, "market_cap": 1500.0}, None)
    assert "cross_check" in s


# ------------------------------------------------------------------ consensus

class Est:
    def __init__(self, ago):
        self.ago = ago

    def estimates(self, t):
        return {"revenue_estimate": {"0y": {"avg": 110.0, "yearAgoRevenue": self.ago, "numberOfAnalysts": 9},
                                     "+1y": {"avg": 121.0}}}


def test_consensus_is_used_only_when_its_base_year_matches_the_filings():
    ok = inputs.consensus(Est(100.0), "X", 100.5)
    assert ok["available"] and ok["growth_y1"] == pytest.approx(0.10) and ok["growth_y2"] == pytest.approx(0.10)
    off = inputs.consensus(Est(100.0), "X", 120.0)
    assert not off["available"] and "not used" in off["reason"]


# ------------------------------------------------------------------ gather

class Quote:
    def __init__(self, qtype="EQUITY"):
        self.qtype = qtype

    def quote(self, t):
        return {"price": 10.0, "quote_type": self.qtype, "currency": "USD", "as_of": "2026-10-13T20:00:00Z"}


def test_a_fund_is_not_valued_as_a_company():
    out = inputs.gather(Quote("ETF"), "SPY")
    assert not out["available"] and "not a company" in out["reason"]


def test_an_ifrs_filer_is_reported_as_not_covered(monkeypatch):
    fl = inputs.Filings({"facts": {"ifrs-full": {"Revenue": {}}}}, "1", None)
    monkeypatch.setattr(inputs, "load_filings", lambda t, force=False: (fl, "1", None))
    out = inputs.gather(Quote(), "TSM")
    assert not out["available"] and "IFRS" in out["reason"]


class Prices:
    """Monthly closes where the stock moves 1.5x the benchmark."""
    def __init__(self, months=60):
        import pandas as pd
        idx = pd.date_range("2021-10-31", periods=months, freq="M")
        bench = [100.0]
        for i in range(1, months):
            bench.append(bench[-1] * (1 + (0.03 if i % 3 else -0.04)))
        stock = [50.0]
        for i in range(1, months):
            stock.append(stock[-1] * (1 + 1.5 * (bench[i] / bench[i - 1] - 1)))
        self.frames = {"SPY": pd.DataFrame({"Close": bench}, index=idx), "X": pd.DataFrame({"Close": stock}, index=idx)}

    def history(self, sym, period=None, interval=None):
        return self.frames[sym]


def test_a_missing_beta_is_computed_from_prices_and_labelled():
    b = inputs.regression_beta(Prices(), "X")
    assert b["value"] == pytest.approx(1.5) and b["kind"] == "derived" and "Computed by Optic" in b["source"]
    short = inputs.regression_beta(Prices(months=20), "X")
    assert short["value"] is None and "36 months" in short["reason"]


def test_debt_securities_current_count_as_short_term_investments():
    """Regression (Nvidia, 2026): DebtSecuritiesCurrent replaced
    MarketableSecuritiesCurrent and was read as not reported."""
    fl = filings({"DebtSecuritiesCurrent": (USD, [fact(34.1, D, form="10-Q")]),
                  "CashAndCashEquivalentsAtCarryingValue": (USD, [fact(22.4, D, form="10-Q")]),
                  "AssetsCurrent": (USD, [fact(197.4, D, form="10-Q")]),
                  "LiabilitiesCurrent": (USD, [fact(60.0, D, form="10-Q")])})
    bs = inputs.balance_sheet(fl, D)
    assert bs["short_term_investments"]["value"] == 34.1
    assert bs["nwc"]["value"] == pytest.approx((197.4 - 22.4 - 34.1) - 60.0)


def test_equity_stakes_count_once():
    nvda = filings({"EquitySecuritiesFvNi": (USD, [fact(42.8, D, form="10-Q")]),
                    "EquitySecuritiesWithoutReadilyDeterminableFairValueAmount": (USD, [fact(47.9, D, form="10-Q")])})
    assert inputs.investments_on(nvda, D)["value"] == pytest.approx(90.7)
    googl = filings({"OtherLongTermInvestments": (USD, [fact(131.5, D, form="10-Q")]),
                     "EquitySecuritiesWithoutReadilyDeterminableFairValueAmount": (USD, [fact(124.3, D, form="10-Q")])})
    assert inputs.investments_on(googl, D)["value"] == pytest.approx(131.5)
