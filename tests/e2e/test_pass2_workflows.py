"""Pass 2, item 1 (2026-11-17): the eight workflows agreed on 2026-11-07, walked end to end in a real browser.

Each journey walks its screens in order, as a reader would, and every screen is held to the same five rules:
* no uncaught error in the page;
* no raw machine text on screen (undefined, NaN, [object Object], a stack line);
* no block left loading once its requests have settled: a block either draws, or says it is empty, stale or failed;
* every block that could not load says so in the one shared look (ui/states.js: `.state.err` with "did not load",
  or the stale line), never a page's own red text;
* a way forward from every screen (the rail is there and the page has at least one link or button of its own).

The feeds are refused at the closed port (tests/e2e/conftest.py), so this is the outage case for every market panel:
the hardest case for the four states, and the one his round-one review named ("features not always working").
The loaded case for the stock page uses the recorded fixtures. Route-level checks of the same pages live in
tests/test_pass2_states_contract.py.
"""
from __future__ import annotations

import re
import time

import pytest

from tests.e2e.conftest import make_account
from tests.e2e.fixtures import route_intraday, route_price_history
from tests.e2e.test_pass1_journeys import DESKTOP, open_page

SETTLE = 30.0          # seconds a screen may take to settle with every feed refused
RAW = re.compile(r"\bundefined\b|\bNaN\b|\[object Object\]|Traceback|TypeError|at [A-Za-z_$][\w$]*\s\(")

# The eight workflows of workflow-map-2026-11-06.md, section B, screen by screen.
WORKFLOWS = {
    "research a company": ["#/AAPL", "#/AAPL/chart", "#/AAPL/investing", "#/AAPL/earnings", "#/AAPL/financials",
                           "#/AAPL/news", "#/AAPL/options", "#/AAPL/sheet"],
    "what moved today": ["#/", "#/read", "#/macro", "#/indices", "#/instrument/%5EGSPC", "#/earnings"],
    "watch names": ["#/watchlist", "#/alerts"],
    "screen for candidates": ["#/explore", "#/scan", "#/insiders", "#/analysts"],
    "practise or model": ["#/paper", "#/portfolio", "#/retirement", "#/compare"],
    "brokerage": ["#/brokerage"],
    "account": ["#/settings", "#/research", "#/signin"],
}


def settle(page, timeout=SETTLE):
    """Wait until the page has no loading placeholder left, or the time is up; return the placeholders still showing."""
    deadline = time.time() + timeout
    left = []
    while time.time() < deadline:
        left = page.eval_on_selector_all(
            "#main .sk-wrap, #main [aria-busy='true']",
            # a board the server says it is still building is a settled state: the page says so and asks again
            "els => els.filter(e => e.offsetParent !== null && !/^Building/.test(e.getAttribute('aria-label') || '') && !(e.getAttribute('aria-busy') === 'true' && e.querySelector('[role=status]:not(.sk-wrap)'))).map(e => (e.getAttribute('aria-label') || e.closest('[data-ws-panel],section,[id]')?.id || e.className))")
        if not left:
            # a quiet moment, so a block that starts loading after another answers is caught
            page.wait_for_timeout(400)
            again = page.eval_on_selector_all("#main .sk-wrap, #main [aria-busy='true']", "els => els.filter(e => e.offsetParent !== null && !/^Building/.test(e.getAttribute('aria-label') || '') && !(e.getAttribute('aria-busy') === 'true' && e.querySelector('[role=status]:not(.sk-wrap)'))).length")
            if not again:
                return []
        page.wait_for_timeout(300)
    return left


def screen_findings(page):
    """What on this screen breaks the five rules, as short sentences."""
    out = []
    text = page.inner_text("#main")
    m = RAW.search(text)
    if m:
        start = max(0, m.start() - 40)
        out.append("raw text on screen: ..." + text[start:m.end() + 40].replace("\n", " ") + "...")
    # a page's own red error text outside the shared states
    own = page.eval_on_selector_all(
        "#main .err, #main .error, #main [role='alert']",
        "els => els.filter(e => e.offsetParent !== null && !e.closest('.state') && !e.classList.contains('toast')).map(e => e.className + ': ' + e.textContent.trim().slice(0, 80))")
    out += ["error outside the shared states: " + o for o in own]
    if not page.query_selector(".rail-nav a, nav.tabbar a"):
        out.append("no rail on screen")
    if not page.eval_on_selector_all("#main a[href], #main button", "els => els.filter(e => e.offsetParent !== null).length"):
        out.append("no way forward from the page itself")
    return out


def walk(page, server, screens):
    findings = {}
    for hash_ in screens:
        page.goto(server["base"] + "/" + hash_, wait_until="domcontentloaded")
        page.wait_for_selector("#main .page-view")
        left = settle(page)
        f = screen_findings(page)
        if left:
            f.append("still loading after {}s: {}".format(int(SETTLE), ", ".join(sorted(set(map(str, left)))[:6])))
        if page.errors:
            f += ["page error: " + e.splitlines()[0][:160] for e in page.errors]
            page.errors.clear()
        if f:
            findings[hash_] = f
    return findings


@pytest.mark.parametrize("workflow", list(WORKFLOWS))
def test_each_workflow_walks_end_to_end_with_the_feeds_refused(chrome, server, workflow):
    cookies = None
    if workflow in ("brokerage", "account", "watch names"):
        _, cookies = make_account(server)
    ctx, page = open_page(chrome, server, level="advanced", viewport=DESKTOP, cookies=cookies)
    try:
        findings = walk(page, server, WORKFLOWS[workflow])
    finally:
        ctx.close()
    assert not findings, "\n".join("{}: {}".format(k, "; ".join(v)) for k, v in findings.items())


def test_research_a_company_walks_end_to_end_with_its_figures(chrome, server):
    """The loaded case: the stock page's own figures from the fixtures, every tab walked."""
    ctx, page = open_page(chrome, server, level="advanced", viewport=DESKTOP)
    route_price_history(page)
    route_intraday(page)
    try:
        findings = walk(page, server, WORKFLOWS["research a company"])
    finally:
        ctx.close()
    assert not findings, "\n".join("{}: {}".format(k, "; ".join(v)) for k, v in findings.items())


def test_ask_milo_opens_from_every_screen_of_every_workflow(chrome, server, stub):
    """Workflow 7: Milo is reachable from each screen the other seven cross, signed in, and asks with that screen."""
    _, cookies = make_account(server)
    ctx, page = open_page(chrome, server, level="intermediate", viewport=DESKTOP, cookies=cookies)
    missing = []
    try:
        for screens in WORKFLOWS.values():
            for hash_ in screens:
                if hash_ in ("#/signin", "#/AAPL/sheet"):
                    continue          # the sign-in page and the printable sheet carry no Milo by design
                page.goto(server["base"] + "/" + hash_, wait_until="domcontentloaded")
                page.wait_for_selector("#main .page-view")
                b = page.query_selector(".topbar-milo")
                if not b or not b.is_visible():
                    missing.append(hash_ + " (no Ask Milo)")
                    continue
                b.click()
                try:
                    page.wait_for_selector("#milo-q", state="visible", timeout=5000)
                except Exception:                                   # noqa: BLE001 - recorded, not raised
                    missing.append(hash_ + " (Milo did not open)")
                page.keyboard.press("Escape")
    finally:
        ctx.close()
    assert not missing, "no way to Milo on: " + ", ".join(missing)


def test_an_unknown_address_says_what_was_tried_and_offers_the_way_back(chrome, server):
    ctx, page = open_page(chrome, server, level="beginner", viewport=DESKTOP)
    try:
        page.goto(server["base"] + "/#/not-a-page%25", wait_until="domcontentloaded")
        page.wait_for_selector("#main .page-view")
        text = page.inner_text("#main")
        assert "not-a-page" in text
        # the ways on from it (pages/notfound.js): the closest listings, Discover and the Read
        assert page.query_selector("#main a[href='#/explore']") and page.query_selector("#main a[href='#/read']")
    finally:
        ctx.close()
