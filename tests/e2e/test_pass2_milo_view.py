"""Pass 2, item 3 in a real browser (gauntlet round one, D1): Milo is told the chart the reader pressed on Financials.

The order the gauntlet found broken: the reader presses a chart first, then opens Milo from the top bar, then asks.
Opening the panel narrows the page and moves the chart, and the page redraws as its figures arrive, so the press was
lost and Milo was told the chart that slid under the header ("Revenue and profit"). The statements come from a fixture
below (invented values in AAPL's shape, labelled as test data), with quarters, so "Cash flow by quarter" is drawn.
"""
from __future__ import annotations

import json
import re

from tests.e2e.conftest import make_account
from tests.e2e.fixtures import QUOTES, ticker_payload
from tests.e2e.test_pass1_journeys import DESKTOP, open_page

PERIOD_KEY = "optic.v2.financials.period.v1"


def statements_payload():
    """Four fiscal years and eight quarters, invented, with the quarterly cash flow and balance lines."""
    p = ticker_payload("AAPL")
    years = ["2026-09-30", "2025-09-30", "2024-09-30", "2023-09-30"]
    quarters = ["2026-09-30", "2026-06-30", "2026-03-31", "2025-12-31", "2025-09-30", "2025-06-30", "2025-03-31", "2024-12-31"]
    yr = lambda *v: [x * 1e9 for x in v]
    p["company"]["financials"] = {
        "available": True, "source": "Invented statements for a browser test.",
        "annual_periods": years, "annual_fiscal": ["FY26", "FY25", "FY24", "FY23"], "fiscal_year_end": "2026-09-30",
        "annual": {"revenue": yr(479, 416, 391, 383), "gross_profit": yr(230, 195, 180, 170), "operating_income": yr(158, 133, 123, 114),
                   "net_income": yr(132, 112, 94, 97), "operating_cash_flow": yr(140, 118, 110, 111),
                   "capital_expenditure": yr(-12, -11, -9, -11), "free_cash_flow": yr(128, 107, 101, 100),
                   "diluted_eps": [8.8, 7.4, 6.1, 6.1], "diluted_shares": [15.0e9, 15.2e9, 15.4e9, 15.8e9]},
        "quarterly_periods": quarters,
        "quarterly": {"revenue": yr(110, 98, 105, 166, 102, 94, 95, 124), "gross_profit": yr(52, 46, 50, 80, 48, 44, 45, 58),
                      "operating_income": yr(35, 30, 32, 60, 32, 28, 29, 42), "net_income": yr(29, 25, 27, 51, 27, 23, 24, 36),
                      "diluted_eps": [1.95, 1.68, 1.82, 3.4, 1.8, 1.55, 1.6, 2.4]},
        "quarterly_cash": {"operating_cash_flow": yr(32, 27, 24, 54, 29, 28, 24, 30), "capital_expenditure": yr(-3, -3, -3, -3, -3, -3, -2, -3),
                           "free_cash_flow": yr(29, 24, 21, 51, 26, 25, 22, 27)},
        "quarterly_balance": {"cash": yr(30, 28, 29, 41, 36, 30, 28, 30), "total_debt": yr(99, 101, 98, 97, 101, 99, 98, 97)},
        "balance_history": {"cash": yr(30, 36, 30, 30), "total_debt": yr(99, 101, 107, 111)},
        "margins": {"gross_pct": 48.0, "operating_pct": 33.0, "net_pct": 27.6}, "growth": {"revenue_yoy_pct": 15.1},
        "balance_sheet": {"cash": 30e9, "total_debt": 99e9}}
    return p


def route_statements(page, held):
    """The statements from the fixture; the insider history is held until the test lets it go, as the live copy's
    EDGAR fill answers while the reader is already on the page and redraws it."""
    page.route(re.compile(r".*/api/insiders/AAPL/history.*"), lambda route: held.append(route))

    def ticker(route):
        if "/api/ticker/AAPL" not in route.request.url:
            return route.fallback()
        route.fulfill(status=200, content_type="application/json", body=json.dumps(statements_payload()))
    page.route(re.compile(r".*/api/ticker/[A-Za-z0-9.^=-]+(\?.*)?$"), ticker)


def _top(page, title):
    return page.evaluate("t => { const f = [...document.querySelectorAll('#main figure[data-v2-metric]')].find(e => (e.querySelector('h3') || {}).textContent === t); return f ? Math.round(f.getBoundingClientRect().top) : null; }", title)


def test_a_chart_pressed_before_milo_opens_from_the_top_bar_is_the_one_milo_is_told(chrome, server, stub):
    assert "AAPL" in QUOTES
    stub.reset("ok")
    _, jar = make_account(server)
    ctx, page = open_page(chrome, server, level="advanced", viewport=DESKTOP, cookies=jar, store={PERIOD_KEY: "quarter"})
    held = []
    route_statements(page, held)
    try:
        page.goto(server["base"] + "/#/AAPL/financials", wait_until="domcontentloaded")
        page.wait_for_selector("[data-v2-account].avatar")
        fig = page.locator("#main figure[data-v2-metric]", has=page.locator("h3", has_text=re.compile(r"^Cash flow by quarter$")))
        fig.wait_for(timeout=30000)
        page.wait_for_selector("#main .chart-slot[data-chart='qcash'] svg")
        # the reader scrolls the chart up under the header, as the gauntlet did, and presses it
        page.evaluate("y => window.scrollBy(0, y)", _top(page, "Cash flow by quarter") - 290)
        page.wait_for_function("() => { const f = [...document.querySelectorAll('#main figure[data-v2-metric] h3')].find(h => h.textContent === 'Cash flow by quarter'); const t = f && f.closest('figure').getBoundingClientRect().top; return t > 200 && t < 400; }")
        before = _top(page, "Cash flow by quarter")
        fig.locator("figcaption h3").click()
        # then opens Milo from the top bar, which narrows the page and moves the chart
        page.click(".topbar-milo")
        page.wait_for_selector("#milo-q")
        page.wait_for_function("t0 => { const f = [...document.querySelectorAll('#main figure[data-v2-metric] h3')].find(h => h.textContent === 'Cash flow by quarter'); return f && Math.abs(f.closest('figure').getBoundingClientRect().top - t0) > 40; }", arg=before, timeout=15000)
        # the insider history arrives now and the page redraws every chart; the press must outlive that
        page.wait_for_function("() => !!document.querySelector('#fin-ih')")
        for _ in range(200):             # the page asked for it at its first paint; give the route's event a turn
            if held:
                break
            page.wait_for_timeout(50)
        assert held, "the insider history was asked for"
        page.evaluate("() => { window.__qcash = document.querySelector(\"#main .chart-slot[data-chart='qcash']\"); }")
        held.pop().fulfill(status=200, content_type="application/json", body=json.dumps({"available": True, "rows": [], "coverage": {"sec_unread": 0, "yahoo_rows": 0, "sec_rows": 0}}))
        page.wait_for_function("() => !window.__qcash.isConnected", timeout=15000)
        page.fill("#milo-q", "Explain this chart")
        with page.expect_request(lambda r: r.url.endswith("/api/chat") and r.method == "POST", timeout=30000) as req:
            page.press("#milo-q", "Enter")
        body = json.loads(req.value.post_data or "{}")
        focus = ((body.get("context") or {}).get("focus") or {})
        assert focus.get("in_view") == {"metric": "Cash flow by quarter", "period": "quarters"}, focus.get("in_view")
        page.wait_for_function("() => (document.querySelector('.milo-log') || {}).textContent.includes('Stand-in answer')", timeout=60000)
        # a wheel scroll afterwards hands the choice back to what is in view
        page.mouse.move(300, 500)
        page.mouse.wheel(0, -6000)
        page.wait_for_function("() => window.scrollY < 50")
        page.fill("#milo-q", "And this one?")
        with page.expect_request(lambda r: r.url.endswith("/api/chat") and r.method == "POST", timeout=30000) as req2:
            page.press("#milo-q", "Enter")
        again = ((json.loads(req2.value.post_data or "{}").get("context") or {}).get("focus") or {}).get("in_view") or {}
        assert again.get("metric") != "Cash flow by quarter", again
        assert not page.errors
    finally:
        ctx.close()
