"""Each facet says what it thinks.

Options opens with a swing verdict, Investing with a conviction score and a
sentence on whether the name suits a core holding, News with net sentiment
across the headlines it read. Two facets did not.

Financials opened on short interest -- a real number, and a narrow one -- and
then listed tables, so the one tab whose whole subject is "is this a good
business" was the one tab that never answered. It now opens with readings
derived from figures already on the page: no new request, no forecast, and
every number it quotes is rendered in full below it.

Earnings opened with the pre-earnings brief, whose own degraded copy reads
"every figure it would discuss is on the panel above" -- written for a position
it was not in. On a deployment with no assistant key, which is what
theopticterminal.com runs, that absence was also the first thing on the tab:
Earnings led by explaining what it could not tell you.

The readings are measured, not asserted. AAPL: margins widening on +6.4%
revenue against +19.5% earnings, beat 8 of 8, short interest negligible at
0.96% of float. GME on the same code: margins widening on -5.0% revenue
against +218.7% earnings, short interest crowded at 13.91%, insiders net
buying 2.2M shares. SPY renders no panel at all, which is right -- an ETF
files no statements.
"""

from __future__ import annotations

import re

APP = open("static/app.js", encoding="utf-8").read()


def _code():
    src = re.sub(r"/\*.*?\*/", "", APP, flags=re.S)
    return re.sub(r"(?m)^\s*//.*$", "", src)


def _fn(name, src):
    start = src.index("function %s(" % name)
    nxt = src.find("\nfunction ", start + 1)
    return src[start:nxt if nxt > 0 else len(src)]


def test_financials_opens_with_a_reading():
    code = _code()
    assert "function financialsReadings(" in code
    assert "function renderFinancialsLead(" in code
    view = _fn("renderFinancialsView", code)
    assert "renderFinancialsLead(co)" in view
    # Before the statements, not after them.
    assert view.index("renderFinancialsLead(co)") < view.index("renderCompany(co)")


def test_an_empty_reading_renders_no_panel():
    """SPY files no statements. A heading with nothing under it is worse than
    no heading, and the fallback copy below it already explains ETFs."""
    fn = _fn("renderFinancialsLead", _code())
    assert "if (!rows.length) return ''" in fn


def test_every_reading_comes_off_the_payload_already_on_the_page():
    """The rule this facet is held to: derived, never fetched. A reading that
    needed its own request would be a second source of truth for numbers the
    page is already showing."""
    fn = _fn("financialsReadings", _code())
    for banned in ("fetch(", "getJSON(", "await "):
        assert banned not in fn, "the readings must not make a request: " + banned
    for field in ("financials", "earnings_history", "ownership", "short_interest"):
        assert field in fn, "reading dropped: " + field


def test_a_small_margin_gap_is_not_called_a_trend():
    """Revenue and earnings growth differing by a point is a rounding
    difference. The band is named so it can be argued with rather than tuned
    quietly."""
    code = _code()
    assert "const FIN_MARGIN_BAND" in code
    fn = _fn("financialsReadings", code)
    assert "FIN_MARGIN_BAND" in fn
    assert "moving together" in fn, "inside the band it has to say so"


def test_insider_direction_is_weighed_against_what_changed_hands():
    """AAPL reports `insider_signal: "selling"` on 403,303 bought against
    406,507 sold -- a net of 3,204 shares, under one percent of the volume,
    which is a payroll event and not a view. Echoing the label would have made
    the panel's most confident sentence its least true one."""
    fn = _fn("financialsReadings", _code())
    assert "purchase_shares" in fn and "sale_shares" in fn
    assert "no net direction" in fn
    assert re.search(r"share\s*>=\s*0\.1|>=\s*0\.1", fn), \
        "the net has to clear a share of gross activity to count"


def test_the_earnings_brief_sits_below_the_report():
    """Its own copy says "on the panel above", and it was the first panel."""
    code = _code()
    fn = _fn("renderEarnings", code) if "function renderEarnings(" in code else code
    body = fn[fn.index("views.earnings.innerHTML"):]
    brief = body.index('id="earnBriefHost"')
    report = body.index("Next report")
    assert report < brief, \
        "the brief renders before the report it says is above it"
