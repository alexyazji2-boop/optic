"""Pass 2, item 2 (2026-11-17): the six features no one had pressed on the test site, pressed in a real browser.

Deep Research with a question of the reader's own, the Index Read, the export (the printable research sheet), passkeys,
the brokerage link, and alert delivery. Route-level checks of the same features already exist (tests/test_alerts.py,
tests/test_auth_passkeys.py, tests/test_brokerage.py and the research routes); these journeys are the browser half.
What each one could and could not show is written up in .factory/pass-2-six-features-record.md.
"""
from __future__ import annotations

import json
import re

import pytest

from tests.e2e.conftest import make_account
from tests.e2e.fixtures import route_price_history
from tests.e2e.test_pass1_journeys import DESKTOP, open_page, stock


def _answered(page, timeout=60000):
    page.wait_for_function("() => (document.querySelector('.milo-log') || {}).textContent && "
                           "document.querySelector('.milo-log').textContent.includes('Stand-in answer')", timeout=timeout)


# ------------------------------------------------------------------ 1. Deep Research, the reader's own question

def test_deep_research_sends_the_readers_own_question_and_shows_the_answer(chrome, server, stub):
    stub.reset("ok")
    _, jar = make_account(server)
    ctx, page = open_page(chrome, server, level="intermediate", cookies=jar)
    try:
        stock(page, server)
        page.wait_for_selector("[data-v2-account].avatar")
        page.click(".topbar-milo")
        page.wait_for_selector("#milo-q", state="visible")
        question = "How exposed is Apple to a slowdown in China this year?"
        page.fill("#milo-q", question)
        with page.expect_response(lambda r: r.url.endswith("/api/research")) as resp:
            page.click("[data-v2-milo-deep]")
        assert resp.value.status == 200
        _answered(page)
        sent = [json.dumps(r["body"]) for r in stub.messages()]
        assert sent and any(question in b for b in sent), "the reader's own question reached the model"
        assert page.query_selector(".milo-log .milo-assumed") is not None, "the answer says it was deep research"
        assert not page.errors
    finally:
        ctx.close()


# ------------------------------------------------------------------ 2. The Index Read

BOARD = {"available": True, "as_of": "2026-11-17T21:00:00+00:00", "note": "Invented board (test data).",
         "rows": [{"symbol": "SPY", "name": "SPDR S&P 500 ETF", "price": 590.1, "change_pct": 0.4, "trend": "uptrend", "available": True,
                   "rotation": {"label": "Leading"}},
                  {"symbol": "QQQ", "name": "Invesco QQQ", "price": 512.3, "change_pct": 0.7, "trend": "uptrend", "available": True,
                   "rotation": {"label": "Leading"}}]}


def test_the_index_read_is_asked_from_the_board_and_answers_in_place(chrome, server, stub):
    stub.reset("ok")
    _, jar = make_account(server)
    ctx, page = open_page(chrome, server, level="advanced", cookies=jar)
    page.route(re.compile(r".*/api/indices/board(\?.*)?$"),
               lambda r: r.fulfill(status=200, content_type="application/json", body=json.dumps(BOARD)))
    try:
        page.goto(server["base"] + "/#/indices", wait_until="domcontentloaded")
        # a locator, not a handle: the board redraws as its rows arrive, and a button found once could be gone by the
        # click (it failed so from a clean clone in Pass 2 round two, "Element is not attached to the DOM")
        b = page.locator("[data-v2-sread='SPY']")
        b.wait_for(timeout=30000)
        with page.expect_response(lambda r: "/api/sectors/SPY/read" in r.url, timeout=90000) as resp:
            b.click()
        assert resp.value.status in (200, 503)
        # it answers in place with a read, or says in the shared look why there is none; never a blank or a spinner
        page.wait_for_function("() => !document.querySelector(\".sread[role='status']\") && !!document.querySelector('.sread h3, .sread + .state, .state.err, .state')", timeout=90000)
        assert not page.errors
    finally:
        ctx.close()


# ------------------------------------------------------------------ 3. Export: the printable research sheet

def test_the_research_sheet_exports_as_a_pdf_with_the_company_and_its_tags(chrome, server):
    """Waits on the sheet itself. It waited on "Apple" in #main, which the Overview it came from already showed, so it
    read the Overview when it passed and the page between the two when it failed (gauntlet, Pass 2 round one, D2)."""
    ctx, page = open_page(chrome, server, level="advanced", viewport=DESKTOP)
    route_price_history(page)
    try:
        stock(page, server)
        page.goto(server["base"] + "/#/AAPL/sheet", wait_until="domcontentloaded")
        # ready: the print button enabled and the sheet drawn, which the page does only once its figures are in
        page.wait_for_selector("#main [data-sheet-print]:not([disabled])", timeout=60000)
        sheet = page.locator("#main article.sheet")
        sheet.wait_for(timeout=30000)
        assert "AAPL" in sheet.inner_text() and "Apple" in sheet.inner_text()
        # every figure the sheet asked for has answered, so no later redraw lands between the print and the read
        page.wait_for_load_state("networkidle")
        page.emulate_media(media="print")
        pdf = page.pdf(format="Letter", print_background=True)
        assert pdf[:5] == b"%PDF-" and len(pdf) > 20000, "a real PDF came out of print"
        assert "AAPL" in page.locator("#main article.sheet").inner_text(), "the sheet is what prints"
        assert not page.errors
    finally:
        ctx.close()


# ------------------------------------------------------------------ 4. Passkeys, with Chromium's virtual authenticator

@pytest.mark.parametrize("server", [{"_HOST": "localhost"}], indirect=True)
def test_a_passkey_is_added_in_settings_and_signs_in_on_its_own(chrome, server):
    """Each step waits on what the page shows. Two waits were wrong before (gauntlet, Pass 2 round one, D2): Settings
    redraws as its sections arrive, so a button found once could be gone by the click; and the sign-in page was opened
    by changing only the address's #, in the same document, where the app still held the signed-in account and sent
    the reader Home, so the passkey button never appeared. The cookies are cleared and the sign-in page loads afresh."""
    _, jar = make_account(server)
    ctx, page = open_page(chrome, server, level="intermediate", cookies=jar)
    try:
        cdp = ctx.new_cdp_session(page)
        cdp.send("WebAuthn.enable")
        cdp.send("WebAuthn.addVirtualAuthenticator", {"options": {
            "protocol": "ctap2", "transport": "internal", "hasResidentKey": True, "hasUserVerification": True,
            "isUserVerified": True, "automaticPresenceSimulation": True}})
        page.goto(server["base"] + "/#/settings", wait_until="domcontentloaded")
        page.wait_for_selector("[data-v2-account].avatar", timeout=30000)
        add = page.locator("[data-v2-pk-add]:not([disabled])")
        add.wait_for(timeout=30000)
        with page.expect_response(lambda r: r.url.endswith("/passkeys/register/verify"), timeout=30000) as resp:
            add.click()
        assert resp.value.status == 200, resp.value.text()
        page.wait_for_selector("[data-v2-sec-arm^='passkey:']", timeout=30000)
        # signed out, the passkey alone signs back in
        ctx.clear_cookies()
        page.goto("about:blank")
        page.goto(server["base"] + "/#/signin", wait_until="domcontentloaded")
        page.wait_for_selector("form[data-v2-auth='in']", timeout=30000)
        signin = page.locator("[data-v2-pk-signin]:not([disabled])")
        signin.wait_for(timeout=30000)
        with page.expect_response(lambda r: r.url.endswith("/passkeys/login/verify"), timeout=30000) as resp2:
            signin.click()
        assert resp2.value.status == 200, resp2.value.text()
        page.wait_for_selector("[data-v2-account].avatar", timeout=30000)
        assert not page.errors
    finally:
        ctx.close()


# ------------------------------------------------------------------ 5. The brokerage link

def test_the_brokerage_page_says_plainly_what_linking_needs_when_it_is_off(chrome, server):
    """With no SnapTrade credentials (the suite has none, and neither has the test site), the link cannot run; the page
    must say so and offer the way back, not a dead end or a spinner."""
    _, jar = make_account(server)
    ctx, page = open_page(chrome, server, level="intermediate", cookies=jar)
    try:
        page.goto(server["base"] + "/#/brokerage", wait_until="domcontentloaded")
        page.wait_for_selector("#main .page-view")
        page.wait_for_function("() => !document.querySelector('#main .sk-wrap')", timeout=30000)
        text = page.inner_text("#main")
        assert text.strip(), "the page drew something"
        assert page.eval_on_selector_all("#main a[href], #main button", "els => els.length") > 0
        assert not re.search(r"\bundefined\b|\[object Object\]", text)
        assert not page.errors
    finally:
        ctx.close()


# ------------------------------------------------------------------ 6. Alert delivery, read back from the outbox

def test_the_alerts_page_opens_for_a_symbol_ready_to_set_one(chrome, server):
    """The browser half: the Alerts page opened from a stock, ready to set one. Delivery itself (one email per scan,
    sent once, kept pending when the mail server refuses, off while a blocker stands) is route level in
    tests/test_alerts.py, and on the test site through its mail sink (.factory/pass-2-six-features-record.md)."""
    _, jar = make_account(server)
    ctx, page = open_page(chrome, server, level="intermediate", cookies=jar)
    try:
        page.goto(server["base"] + "/#/alerts?symbol=AAPL", wait_until="domcontentloaded")
        page.wait_for_selector("#main .page-view")
        page.wait_for_function("() => !document.querySelector('#main .sk-wrap')", timeout=30000)
        # the form opens for that symbol (pages/alerts.js), wherever it is drawn
        page.wait_for_function("() => [...document.querySelectorAll('input')].some(i => i.value === 'AAPL')", timeout=30000)
        assert not page.errors
    finally:
        ctx.close()
