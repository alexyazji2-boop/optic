"""Pass 2 round two (gauntlet D3): axe on the two screens round 2 delivers, with their figures drawn and their tables
long enough to scroll, at desktop and phone widths.

The live copy failed two serious rules the suite's scans never met, because the suite's pages drew no figures: the
company grid's Earnings panel put a note beside its dt and dd inside a dl group (definition-list), and Financials'
tables scrolled inside their boxes with no way to reach them from the keyboard (scrollable-region-focusable). Here
the statements, the earnings record and the congressional trades come from fixtures (invented values, labelled as test
data), so the tables overflow as the live ones do.
"""
from __future__ import annotations

import json
import re

import pytest

from tests.e2e.test_pass1_journeys import DESKTOP, PHONE, open_page
from tests.e2e.test_pass2_milo_view import PERIOD_KEY, statements_payload
from tests.e2e.visual_fixtures import route_company

TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]


def _axe(page):
    from axe_playwright_python.sync_playwright import Axe
    result = Axe().run(page, options={"runOnly": {"type": "tag", "values": TAGS}})
    return [{"id": v["id"], "impact": v["impact"], "nodes": [n["target"] for n in v["nodes"]][:4]} for v in result.response.get("violations", [])]


def congress_payload(n=15):
    trades = [{"traded_iso": "2026-%02d-%02d" % (1 + i % 10, 1 + i), "member": "Member %d (test data)" % (i + 1), "district": "XX%02d" % i,
               "transaction": "purchase" if i % 3 else "sale", "amount_low": 1001, "amount_high": 15000, "disclosure_lag_days": 20 + i}
              for i in range(n)]
    return {"available": True, "count": n, "members": n, "buys": 10, "sells": 5, "amount_low": 15015, "amount_high": 225000, "lag_median": 27,
            "trades": trades, "caveat": "Invented trades for a browser test.", "complete": True}


def financials_payload():
    p = statements_payload()
    p["company"]["earnings_history"] = {"available": True, "quarters": [
        {"date": d, "eps_estimate": e - 0.05, "eps_reported": e, "surprise_pct": 2.8}
        for d, e in (("2026-10-30", 1.85), ("2026-07-30", 1.57), ("2026-04-30", 1.65), ("2026-01-29", 2.40),
                     ("2025-10-30", 1.64), ("2025-07-31", 1.40), ("2025-05-01", 1.53), ("2025-01-30", 2.40))]}
    return p


def route_financials(page):
    def ticker(route):
        if "/api/ticker/AAPL" not in route.request.url:
            return route.fallback()
        route.fulfill(status=200, content_type="application/json", body=json.dumps(financials_payload()))
    page.route(re.compile(r".*/api/ticker/[A-Za-z0-9.^=-]+(\?.*)?$"), ticker)
    page.route(re.compile(r".*/api/congress\?.*"), lambda r: r.fulfill(status=200, content_type="application/json", body=json.dumps(congress_payload())))


@pytest.mark.parametrize("viewport", [DESKTOP, PHONE], ids=["desktop", "phone"])
def test_financials_drawn_with_tables_that_scroll_has_no_axe_violation(chrome, server, viewport):
    ctx, page = open_page(chrome, server, level="advanced", viewport=viewport, store={PERIOD_KEY: "quarter"})
    route_financials(page)
    try:
        page.goto(server["base"] + "/#/AAPL/financials", wait_until="domcontentloaded")
        page.wait_for_selector("#fin-congress .tscroll table tbody tr")
        page.wait_for_selector("#fin-earnings .tscroll table tbody tr")
        page.wait_for_selector("#main .chart-slot[data-chart='qcash'] svg")
        page.wait_for_selector("#fin-ih")
        # the congress box scrolls down inside itself, as the live one did, and is now a named stop on the keyboard
        page.wait_for_function("() => { const b = document.querySelector('#fin-congress .tscroll'); return b && b.scrollHeight > b.clientHeight + 4 && b.getAttribute('tabindex') === '0'; }", timeout=15000)
        label = page.get_attribute("#fin-congress .tscroll", "aria-label")
        assert label and label.startswith("Congressional disclosures"), label
        page.wait_for_load_state("networkidle")
        violations = _axe(page)
        assert violations == [], json.dumps(violations, indent=1)
        assert not page.errors
    finally:
        ctx.close()


@pytest.mark.parametrize("viewport", [DESKTOP, PHONE], ids=["desktop", "phone"])
def test_the_company_grid_with_its_earnings_panel_drawn_has_no_axe_violation(chrome, server, viewport):
    ctx, page = open_page(chrome, server, level="advanced", viewport=viewport)
    route_company(page)
    try:
        page.goto(server["base"] + "/#/AAPL/workspace", wait_until="domcontentloaded")
        page.wait_for_selector("h1:has-text('AAPL panels')")
        page.wait_for_selector("[data-ws-panel='tearn'] dl.ws-kv dd")
        # a dl's groups hold only dt and dd
        stray = page.evaluate("() => [...document.querySelectorAll('#main dl > div > :not(dt):not(dd)')].map(e => e.tagName)")
        assert stray == [], stray
        page.wait_for_load_state("networkidle")
        violations = _axe(page)
        assert violations == [], json.dumps(violations, indent=1)
        assert not page.errors
    finally:
        ctx.close()
