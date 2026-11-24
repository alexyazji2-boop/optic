"""Pass 2, item 8 in a real browser: link groups, a named layout carried to another browser, and Home's grid on the
stock page. Route-level and source checks are in tests/test_pass2_layouts.py."""
from __future__ import annotations

import re

from tests.e2e.conftest import make_account
from tests.e2e.test_pass1_journeys import DESKTOP, home, open_page


def scope(page, pid):
    return page.inner_text(f"[data-ws-panel='{pid}'] [data-ws-sym]").strip()


def test_a_panel_moved_to_gold_keeps_its_ticker_when_blue_changes(chrome, server):
    ctx, page = open_page(chrome, server, level="advanced", viewport=DESKTOP)
    try:
        home(page, server)
        page.click("[data-ws-preset='options']")   # a layout with more than one linked panel
        page.wait_for_selector("[data-ws-grp='cnews']")
        assert "is-blue" in page.get_attribute("[data-ws-grp='cnews']", "class")
        page.click("[data-ws-grp='cnews']")
        page.wait_for_selector("[data-ws-grp='cnews'].is-gold")
        before = scope(page, "cnews")
        page.fill("#ws-link", "MSFT")
        page.press("#ws-link", "Enter")
        page.wait_for_function("() => (document.querySelector(\"[data-ws-panel='quote'] [data-ws-sym]\") || {}).textContent.includes('MSFT')", timeout=20000)
        assert scope(page, "cnews") == before, "the Gold panel stays on its own ticker"
        # and the group is kept between visits
        page.reload(wait_until="domcontentloaded")
        page.wait_for_selector("[data-ws-grp='cnews'].is-gold")
        assert not page.errors
    finally:
        ctx.close()


def test_a_named_layout_saved_in_one_browser_opens_in_another(chrome, server):
    """The name is typed the moment Customize opens, before the saved list has arrived; the list is then let through.
    That list's arrival used to redraw the bar and wipe the name (gauntlet, Pass 2 round one, D2), so the save sent
    nothing and no confirmation came. Every wait is on what the page shows or asks for, never on time."""
    _, jar = make_account(server)
    ctx, page = open_page(chrome, server, level="advanced", viewport=DESKTOP, cookies=jar)
    held = []
    page.route(re.compile(r".*/api/layouts(\?.*)?$"), lambda route: held.append(route) if route.request.method == "GET" else route.fallback())
    try:
        home(page, server)
        page.wait_for_selector("[data-v2-account].avatar")
        page.click("[data-ws-edit]")
        page.wait_for_selector("#ws-named-name")
        page.click("#ws-named-name")
        page.keyboard.type("Earnings week")
        for _ in range(200):             # Customize asked for the saved list as it opened; give the route's event a turn
            if held:
                break
            page.wait_for_timeout(50)
        assert held, "Customize asked for the saved layouts"
        with page.expect_response(lambda r: r.url.endswith("/api/layouts") and r.request.method == "GET", timeout=15000):
            held.pop().fallback()
        # the answer's handlers run before the next frame is drawn
        page.evaluate("() => new Promise((ok) => requestAnimationFrame(() => requestAnimationFrame(ok)))")
        assert page.input_value("#ws-named-name") == "Earnings week", "the saved list's arrival kept the typed name"
        assert page.evaluate("() => document.activeElement && document.activeElement.id") == "ws-named-name"
        with page.expect_response(lambda r: "/api/layouts/" in r.url and r.request.method == "PUT", timeout=15000) as put:
            page.click("[data-ws-named] button[type=submit]")
        assert put.value.status == 200, put.value.text()
        page.wait_for_selector("text=Earnings week is saved on your account", timeout=15000)
    finally:
        ctx.close()
    ctx2, page2 = open_page(chrome, server, level="advanced", viewport=DESKTOP, cookies=jar)
    try:
        home(page2, server)
        page2.wait_for_selector("[data-v2-account].avatar")
        page2.click("[data-ws-edit]")
        page2.wait_for_selector("text=Saved layouts (1)", timeout=15000)
        page2.click("text=Saved layouts (1)")
        page2.click("[data-ws-open-named='Earnings week']")
        page2.wait_for_selector("text=Earnings week is open as My Desk")
        assert not page2.errors
    finally:
        ctx2.close()


def test_the_stock_page_opens_homes_grid_for_its_company_and_home_keeps_its_own(chrome, server):
    ctx, page = open_page(chrome, server, level="advanced", viewport=DESKTOP)
    try:
        page.goto(server["base"] + "/#/AAPL/workspace", wait_until="domcontentloaded")
        page.wait_for_selector("h1:has-text('AAPL panels')")
        page.wait_for_selector("[data-ws-panel='quote'] [data-ws-sym]")
        assert "AAPL" in scope(page, "quote")
        assert page.query_selector("[data-ws-panel='indices']") is None, "only panels about the company"
        home(page, server)
        assert page.input_value("#ws-link") != "AAPL", "Home's own linked ticker is unchanged"
        assert not page.errors
    finally:
        ctx.close()
