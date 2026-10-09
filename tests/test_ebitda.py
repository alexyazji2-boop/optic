"""EBITDA on the Financials facet.

Asked for as "when looking at financials add a companies EBITDA metric as
well". The statement's own EBITDA line, as Yahoo carries it (Apple's FY2025
reads $144.7B), its margin, and a plain "Not reported" for the banks and
insurers that file none (JPM has no EBITDA row at all).
"""
from pathlib import Path

from app.analytics.fundamentals import analyse_financials

APP = (Path(__file__).resolve().parent.parent / "static/app.js").read_text()


def _income(rows):
    return {"periods": ["2025-09-30", "2024-09-30"], "rows": rows}


def test_the_ebitda_line_and_its_margin_come_through():
    out = analyse_financials({"income_annual": _income({
        "Total Revenue": [400.0, 380.0],
        "Operating Income": [120.0, 110.0],
        "EBITDA": [140.0, 130.0],
        "Normalized EBITDA": [150.0, 135.0],
        "Net Income": [100.0, 90.0],
    })})
    assert out["annual"]["ebitda"] == [140.0, 130.0], "the EBITDA line, not the normalized one"
    assert out["margins"]["ebitda_pct"] == 35.0
    assert out["margins"]["operating_pct"] == 30.0


def test_a_bank_with_no_ebitda_line_has_none_rather_than_a_built_one():
    out = analyse_financials({"income_annual": _income({
        "Total Revenue": [180.0, 160.0],
        "Net Income": [58.0, 49.0],
        "Reconciled Depreciation": [8.0, 7.0],
    })})
    assert out["annual"]["ebitda"] is None
    assert out["margins"]["ebitda_pct"] is None


def test_the_financials_facet_shows_it_and_says_when_it_is_not_filed():
    assert "finRow('EBITDA', an.ebitda, true, FIN_DEFS.ebitda)" in APP
    assert "['EBITDA', Number.isFinite((an.ebitda || [])[0]) ? usdCompact(an.ebitda[0]) : 'Not reported'" in APP
    assert "['EBITDA margin', Number.isFinite((fn.margins || {}).ebitda_pct)" in APP
    assert "ebitda: GLOSSARY.ebitda + " in APP and "ebitda_margin: \"EBITDA as a percentage of revenue" in APP


def test_a_missing_margin_is_a_dash_not_a_dash_percent():
    """Found beside it: JPM's operating margin read "\u2014%"."""
    assert "const finPct = (v) => (Number.isFinite(v) ? fmt(v, 1) + '%' : '\\u2014');" in APP
    assert "['Operating margin', finPct((fn.margins || {}).operating_pct)" in APP
    assert "fmt((fn.margins || {}).operating_pct, 1) + '%'" not in APP

