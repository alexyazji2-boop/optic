"""Pass 2, item 6 (2026-11-17): Financials as charts, with the series the free update held back.

Already drawn before this pass (2026-10-20 and the visual update): revenue and profit, margins, cash flow by year with
its bridge, cash and debt by year, EPS and the share count. New: the balance sheet's shape (liabilities and equity,
stacked to total assets), cash flow and cash and debt by quarter where the feed carries the quarterly statements, and
the analysts' price targets drawn as a range.
"""
from __future__ import annotations

from app.analytics import fundamentals
from tests.test_frontend_v2_stage0 import V2, _run

Y = ["2025-09-30", "2024-09-30"]
Q = ["2025-09-30", "2025-06-30"]


def raw(with_quarters=True):
    out = {
        "income_annual": {"periods": Y, "rows": {"Total Revenue": [400.0, 380.0], "Net Income": [100.0, 90.0]}},
        "income_quarterly": {"periods": Q, "rows": {"Total Revenue": [110.0, 95.0]}},
        "balance_annual": {"periods": Y, "rows": {"Total Assets": [350.0, 340.0], "Total Liabilities Net Minority Interest": [280.0, 270.0],
                                                  "Stockholders Equity": [70.0, 70.0], "Cash And Cash Equivalents": [30.0, 29.0], "Total Debt": [100.0, 105.0]}},
        "cashflow_annual": {"periods": Y, "rows": {"Operating Cash Flow": [120.0, 110.0]}},
    }
    if with_quarters:
        out["balance_quarterly"] = {"periods": Q, "rows": {"Cash And Cash Equivalents": [30.0, 28.0], "Total Debt": [100.0, 101.0]}}
        out["cashflow_quarterly"] = {"periods": Q, "rows": {"Operating Cash Flow": [32.0, 27.0], "Capital Expenditure": [-3.0, -3.5], "Free Cash Flow": [29.0, 23.5]}}
    return out


def test_the_balance_sheets_shape_is_read_from_the_statement_on_the_fiscal_years():
    f = fundamentals.analyse_financials(raw())
    bh = f["balance_history"]
    assert bh["total_assets"] == [350.0, 340.0] and bh["total_liabilities"] == [280.0, 270.0] and bh["total_equity"] == [70.0, 70.0]


def test_quarterly_cash_flow_and_balance_lines_sit_on_the_income_statements_quarters():
    f = fundamentals.analyse_financials(raw())
    assert f["quarterly_cash"]["operating_cash_flow"] == [32.0, 27.0] and f["quarterly_cash"]["free_cash_flow"] == [29.0, 23.5]
    assert f["quarterly_balance"]["cash"] == [30.0, 28.0] and f["quarterly_balance"]["total_assets"] is None
    none = fundamentals.analyse_financials(raw(with_quarters=False))
    assert none["quarterly_cash"]["operating_cash_flow"] is None, "no quarterly statement: no line, never a guess"


def test_the_quarterly_statements_never_fail_the_four_the_page_needs():
    src = (V2.parent.parent / "app" / "providers" / "yf.py").read_text()
    assert '("balance_quarterly", "quarterly_balance_sheet")' in src and "frames[:required]" in src


def test_financials_draws_the_shape_and_the_quarters_and_earnings_draws_the_target_range():
    fin = (V2 / "js" / "pages" / "financials.js").read_text()
    assert 'data-chart="shape"' in fin and 'data-chart="qcash"' in fin and 'data-chart="qbal"' in fin
    assert "v < 0" in fin.split("const shapeOk")[1].split("\n")[0], "a deficit is never stacked from zero"
    earn = (V2 / "js" / "pages" / "earnings.js").read_text()
    assert "targetRange({ lo: a.target_low, mid: a.target_mean, hi: a.target_high" in earn


def test_the_target_range_draws_the_analysts_figures_and_says_them(tmp_path):
    got = _run(tmp_path, f"""
      const c = await import('{(V2 / "js/ui/chart.js").as_posix()}');
      print(JSON.stringify({{ ok: c.targetRange({{ lo: 180, mid: 240, hi: 300, price: 248.21 }}), none: c.targetRange({{ lo: 200, hi: 200 }}) }}));
    """)
    assert 'aria-label="Analysts&#39; price targets from 180.00 to 300.00, averaging 240.00; the price now is 248.21"' in got["ok"]
    assert got["none"] == ""
