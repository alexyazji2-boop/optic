"""Financials and Earnings (backlog task 8, 2026-10-20): one set of statement lines, fiscal names for every
period, rows matched by date, one beat rule, honest labels.

Server functions run on built statements; the pages' wiring is read as text and the fiscal-name helper runs
in JavaScriptCore against the Python one. The pages were driven in headless Chrome at 360, 390, 430,
844x390, 768 and 1440 px (~/Optic/work/v2-backlog/fin_check.py).
"""
import json

import pytest

from app.analytics import earnings, fundamentals as F, segments
from tests.test_frontend_v2_stage0 import V2, _run

FIN = (V2 / "js/pages/financials.js").read_text()
EARN = (V2 / "js/pages/earnings.js").read_text()

CASES = [
    # (period end, a fiscal year end, annual, expected)
    ("2025-09-30", "2026-06-30", False, "Q1 FY26"),     # Microsoft: the year to June
    ("2026-03-31", "2026-06-30", False, "Q3 FY26"),
    ("2026-06-30", "2026-06-30", True, "FY26"),
    ("2025-06-28", "2025-09-27", False, "Q3 FY25"),     # Apple: 52 or 53 weeks to late September
    ("2025-12-27", "2025-09-27", False, "Q1 FY26"),
    ("2026-07-27", "2026-01-25", False, "Q2 FY27"),     # NVIDIA: the year to late January
    ("2026-06-30", "2025-12-31", False, "Q2 2026"),     # a calendar year
    ("2025-12-31", "2025-12-31", True, "2025"),
    ("2026-01-02", "2026-01-02", True, "2025"),          # a 52-week year ending 2 January is 2025's
]


@pytest.mark.parametrize("end,fy,annual,want", CASES)
def test_a_period_is_named_as_the_company_names_it(end, fy, annual, want):
    assert F.fiscal_label(end, fy, annual=annual) == want


def test_the_page_names_periods_the_same_way(tmp_path):
    got = _run(tmp_path, f"""
      const f = await import('{(V2 / "js/pages/financials.js").as_posix()}');
      print(JSON.stringify({json.dumps([c[:3] for c in CASES])}.map(([e, fy, a]) => f.fiscalLabel(e, fy, a))));
    """)
    assert got == [c[3] for c in CASES]


def test_a_report_is_named_for_the_quarter_it_covers():
    assert F.reported_quarter("2026-07-29", "2026-06-30") == "Q4 FY26"      # Microsoft's July report
    assert F.reported_quarter("2026-04-29", "2026-06-30") == "Q3 FY26"
    assert F.reported_quarter("2026-01-29", "2025-09-27") == "Q1 FY26"      # Apple's January report
    assert F.reported_quarter("2026-10-14", "2025-12-31") == "Q3 2026"      # a bank, two weeks after the quarter
    assert F.reported_quarter("2026-08-27", "2026-01-25") == "Q2 FY27"


def test_free_cash_flow_sits_under_its_own_fiscal_year():
    raw = {
        "income_annual": {"periods": ["2026-06-30", "2025-06-30", "2024-06-30"],
                          "rows": {"Total Revenue": [300.0, 250.0, 200.0], "Net Income": [90.0, 80.0, 70.0]}},
        # the cash-flow statement carries an extra, newer-ordered set of columns
        "cashflow_annual": {"periods": ["2027-06-30", "2026-06-30", "2025-06-30", "2024-06-30"],
                            "rows": {"Free Cash Flow": [99.0, 66.0, 71.0, 74.0]}},
    }
    out = F.analyse_financials(raw)
    assert out["annual"]["free_cash_flow"] == [66.0, 71.0, 74.0]
    assert out["annual_fiscal"] == ["FY26", "FY25", "FY24"]
    assert F._aligned(["2025-06-28"], [5.0], ["2025-06-30", "2024-06-30"]) == [5.0, None], "a few days apart is the same year"


def test_quarters_carry_every_income_line_and_say_their_source():
    raw = {"income_annual": {"periods": ["2026-06-30"], "rows": {"Total Revenue": [300.0]}},
           "income_quarterly": {"periods": ["2026-06-30", "2026-03-31"],
                                "rows": {"Total Revenue": [80.0, 75.0], "Gross Profit": [55.0, 50.0],
                                         "Operating Income": [40.0, 37.0], "EBITDA": [45.0, 41.0]}}}
    out = F.analyse_financials(raw)
    q = out["quarterly"]
    assert q["gross_profit"] == [55.0, 50.0] and q["operating_income"] == [40.0, 37.0] and q["ebitda"] == [45.0, 41.0]
    assert out["quarterly_fiscal"] == ["Q4 FY26", "Q3 FY26"]
    assert "Yahoo Finance" in out["source"] and "GAAP" in out["eps_basis"]


def test_earnings_and_financials_read_the_same_statement_lines():
    fin = {"income_annual": {"periods": ["2026-12-31", "2025-12-31"],
                             "rows": {"Total Revenue": [100e9, 90e9], "Net Income Common Stockholders": [55.68e9, 50e9],
                                      "Net Income": [57.05e9, 51e9], "Total Operating Income As Reported": [4.22e9, 4e9],
                                      "Operating Income": [5.58e9, 5e9]}},
           "income_quarterly": None}
    g = earnings._growth(fin, {})
    a = F.analyse_financials(fin)["annual"]
    assert g["annual"][0]["net_income"] == pytest.approx(a["net_income"][0])
    assert g["annual"][0]["operating_income"] == pytest.approx(a["operating_income"][0])
    assert g["annual"][0]["fiscal"] == "2026"


def test_one_beat_rule_on_both_pages():
    c = F.surprise_counts([5.0, 0.0, 0.04, -2.0, None, 3.0])
    assert (c["beat_count"], c["miss_count"], c["in_line_count"], c["rate_quarters"]) == (2, 1, 2, 5)
    assert c["beat_rate_pct"] == 40.0
    rows = [{"date": d, "eps_reported": 1.0, "eps_estimate": 1.0, "surprise_pct": s}
            for d, s in zip(["2026-01-28", "2026-04-28", "2026-07-28", "2026-10-28"], [5.0, 0.0, -2.0, 3.0])]
    fin = F.analyse_earnings_history(rows)
    ern = earnings._surprise_history(rows, None, fy_end="2025-12-31")
    assert (fin["beat_count"], fin["in_line_count"], fin["sample_size"]) == (2, 1, 4)
    assert (ern["beat_count"], ern["in_line_count"], ern["rate_quarters"]) == (2, 1, 4)
    assert fin["beat_rate_pct"] == 50.0 and ern["beat_rate_pct"] == 50.0
    # newest first: the October report covers the quarter to September, January's the one to December
    assert ern["rows"][0]["fiscal"] == "Q3 2026" and ern["rows"][-1]["fiscal"] == "Q4 2025"


def test_revision_counts_keep_their_zeros():
    est = {"eps_trend": {"0y": {"current": 2.0, "7daysAgo": 2.0, "30daysAgo": 1.9, "60daysAgo": 1.9, "90daysAgo": 1.8}},
           "eps_revisions": {"0y": {"upLast30days": 4, "downLast30days": 0}}}
    r = earnings._revisions(est)
    if r["available"]:
        assert r["analysts_down_30d"] == 0 and r["analysts_up_30d"] == 4
        assert " . " not in r["note"]
    assert "${r.analysts_up_30d} analysts raised and ${r.analysts_down_30d} cut" not in EARN


def test_segments_flag_a_derived_fourth_quarter_and_name_countries():
    cells = {("rev|geo|US", "year", "2025-12-31"): 100.0,
             ("rev|geo|US", "quarter", "2025-03-31"): 20.0, ("rev|geo|US", "quarter", "2025-06-30"): 25.0,
             ("rev|geo|US", "quarter", "2025-09-30"): 25.0}
    made = set()
    out, n = segments._fill_fourth_quarters(dict(cells), made)
    assert n == 1 and ("rev|geo|US", "quarter", "2025-12-31") in made and out[("rev|geo|US", "quarter", "2025-12-31")] == 30.0
    assert segments._tidy("TW") == "Taiwan" and segments._tidy("SG") == "Singapore"


def test_the_pages_say_what_their_figures_are():
    assert "What the statements say" not in FIN and "What the figures say" in FIN
    assert "Annual figures from the company's filings" not in FIN
    assert "Diluted EPS (GAAP)" in FIN and "analysts' basis" in FIN
    assert "data-fin-period" in FIN and "'optic.v2.financials.period.v1'" in FIN
    assert "year less three quarters" in FIN and ".slice().reverse()" in FIN.split("function segments")[1]
    assert "Next day" not in EARN and "REACTION" in EARN and "reactionWhen" in EARN
    assert "num(x.gross_margin_pct, 1)}%" not in EARN and "const pct = " in EARN
    # every quarter is classified by one rule since 2026-10-20 (core/finviz.js surprise): beat, miss, in line, no estimate
    assert "FV.surprise(r.eps_estimate, r.eps_reported, r.surprise_pct)" in EARN and "im.priced_from === 'last_trades'" in EARN


def test_a_growth_column_with_no_figure_is_left_out(tmp_path):
    got = _run(tmp_path, f"""
      const e = await import('{(V2 / "js/pages/earnings.js").as_posix()}');
      const d = await import('{(V2 / "js/core/dom.js").as_posix()}');
      const h = d.toString(e.growthTable([{{ period: '2026-06-30', fiscal: 'Q4 FY26', revenue: 1e9, revenue_yoy_pct: 5, net_income: 2e8 }}]));
      print(JSON.stringify({{ margin: h.includes('Gross margin'), growth: (h.match(/Growth/g) || []).length, naPct: h.includes('n/a%'), fiscal: h.includes('Q4 FY26') }}));
    """)
    assert got == {"margin": False, "growth": 1, "naPct": False, "fiscal": True}
