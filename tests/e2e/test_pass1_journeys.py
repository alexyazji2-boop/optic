"""Pass 1 in a real browser (2026-11-09): the level matrix on Home and the stock page, Show more, the level kept
across reloads and devices, the five old levels read as three, figures the same at every level, the two Milo prompts
with their context and their fallbacks, sign-in from a prompt, Anthropic down, the first signal recorded, the
accessibility scan and the keyboard. Route-level checks of the same features are in tests/test_pass1_*.py."""
from __future__ import annotations

import json
import re
import time

import pytest

from tests.e2e.conftest import PASSWORD, make_account, usage_rows
from tests.e2e.fixtures import route_fixtures, route_price_history

DESKTOP = {"width": 1440, "height": 900}
PHONE = {"width": 390, "height": 844}
LEVELS = ["beginner", "intermediate", "advanced"]
MARKET = ["indices", "regime", "expected", "sectors", "quote", "watch", "calendar", "earnings", "priority", "news", "desk", "movers"]


def open_page(chrome, server, *, level=None, viewport=DESKTOP, cookies=None, store=None, onboarded=True):
    """A fresh browser (its own storage), with the level and any stored values set once, before the first load only, so
    a reload sees what the page itself wrote."""
    ctx = chrome.new_context(viewport=viewport)
    if cookies:
        ctx.add_cookies(cookies)
    seed = dict(store or {})
    if level:
        seed.setdefault("optic.knowledge.v1", level)
        seed.setdefault("optic.knowledge.asked.v1", "1")
    if onboarded:
        seed.setdefault("optic.v2.onboard.v1", "done")
    ctx.add_init_script("""(() => { try { if (sessionStorage.getItem('e2e.seeded')) return; sessionStorage.setItem('e2e.seeded', '1');
      const s = %s; for (const k in s) localStorage.setItem(k, s[k]); } catch (e) {} })();""" % json.dumps(seed))
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.errors = errors
    route_fixtures(page)
    # hermetic: nothing leaves this machine (the web fonts' CDN included); the page falls back to system fonts
    base = server["base"]
    ctx.route(lambda url: not url.startswith(base), lambda route: route.abort())
    return ctx, page


def home(page, server):
    page.goto(server["base"] + "/#/", wait_until="domcontentloaded")
    page.wait_for_selector("[data-v2-lc] [aria-pressed='true']")
    page.wait_for_selector("[data-ws-panel]")
    # Your portfolio is drawn until the brokerage answers that nothing is linked, then hidden (folded on a phone, it never asks)
    page.wait_for_function("() => { const p = document.querySelector('[data-ws-panel=\"portfolio\"]'); return !p || p.hidden || !!p.querySelector('.ws-body[hidden]'); }")
    return page


def stock(page, server, sym="AAPL"):
    page.goto(server["base"] + "/#/" + sym, wait_until="domcontentloaded")
    page.wait_for_selector("#ov-analysis")
    page.wait_for_function("() => !!document.querySelector('.dhead .dh-px')")
    return page


def shown_panels(page):
    return page.eval_on_selector_all("[data-ws-panel]:not([hidden])", "els => els.map(e => e.dataset.wsPanel)")


def stubs(page):
    return page.eval_on_selector_all("[data-v2-sm-stub]", "els => els.map(e => e.dataset.v2SmStub)")


def pressed(page):
    return page.eval_on_selector("[data-v2-lc] [aria-pressed='true']", "e => e.dataset.v2Level")


# ------------------------------------------------------------------ the level matrix, Home

def test_home_at_beginner_shows_the_beginner_panels_only(chrome, server):
    ctx, page = open_page(chrome, server, level="beginner")
    home(page, server)
    assert shown_panels(page) == ["indices", "priority", "watch", "desk"]
    assert page.locator("[data-ws-edit]").count() == 0, "no layouts or Customize at Beginner"
    assert page.locator(".ws-linkrow").count() == 0
    left = stubs(page)
    assert {"regime", "quote", "contracts", "gex"} <= set(left) and "indices" not in left
    assert page.errors == []
    ctx.close()


def test_home_at_intermediate_adds_the_quote_and_market_panels_with_layouts_behind_customize(chrome, server):
    ctx, page = open_page(chrome, server, level="intermediate")
    home(page, server)
    assert shown_panels(page) == MARKET
    assert page.locator("[data-ws-preset]").count() == 0, "the layouts are behind Customize, not on the page"
    assert page.locator(".ws-linkrow").count() == 0, "the linked ticker is Advanced's"
    assert {"contracts", "gex", "vol"} <= set(stubs(page))
    page.click("[data-ws-edit]")
    assert page.locator("[data-ws-preset='options']").is_visible(), "the layouts are behind Customize"
    ctx.close()


def test_home_at_advanced_is_everything_home_has(chrome, server):
    ctx, page = open_page(chrome, server, level="advanced")
    home(page, server)
    assert shown_panels(page) == MARKET
    assert page.locator("[data-ws-preset='options']").count() == 1 and page.locator(".ws-linkrow").count() == 1
    assert stubs(page) == [], "nothing is left out at Advanced"
    page.click("[data-ws-preset='options']")
    page.wait_for_selector("[data-ws-panel='gex']")
    assert {"contracts", "vol", "gex"} <= set(shown_panels(page))
    ctx.close()


# ------------------------------------------------------------------ the level matrix, the stock page

def actions(page):
    # the header's own buttons, not the ⋯ menu's items
    return page.eval_on_selector_all(".dhead .acts a, .dhead .acts button", "els => els.filter(e => !e.closest('details')).map(e => (e.textContent || '').trim()).filter(Boolean)")


def test_stock_page_at_beginner(chrome, server):
    ctx, page = open_page(chrome, server, level="beginner")
    stock(page, server)
    acts = " ".join(actions(page))
    assert "Watch" in acts and "Ask about AAPL" in acts
    for gone in ("Alert", "Compare", "Export", "Save"):
        assert gone not in acts, gone
    assert page.get_attribute("#ov-analysis", "data-v2-analysis") == "simple"
    assert page.locator("[data-v2-ov-panel='cases']").count() == 0 and page.locator("#ov-thesis").count() == 0
    assert page.locator(".dchart").count() == 1
    assert set(stubs(page)) == {"advanced", "cases", "thesis", "investigate", "timeline"}
    ctx.close()


def test_stock_page_at_intermediate(chrome, server):
    ctx, page = open_page(chrome, server, level="intermediate")
    stock(page, server)
    acts = " ".join(actions(page))
    assert "Alert" in acts and "Compare" in acts and "Export" not in acts
    assert page.get_attribute("#ov-analysis", "data-v2-analysis") == "simple"
    assert page.locator("[data-v2-ov-panel='cases']").count() == 1
    page.wait_for_selector("#ov-thesis")
    assert page.locator("#ov-thesis [data-tc-start], #ov-thesis [data-tc-edit]").count() == 0, "writing it is Advanced's"
    assert page.locator("#ov-thesis [data-v2-show-more='thesis:edit']").count() == 1
    assert set(stubs(page)) == {"advanced", "investigate", "timeline"}
    ctx.close()


def test_stock_page_at_advanced(chrome, server):
    ctx, page = open_page(chrome, server, level="advanced")
    stock(page, server)
    acts = " ".join(actions(page))
    assert all(w in acts for w in ("Alert", "Compare", "Export", "Watch"))
    assert page.get_attribute("#ov-analysis", "data-v2-analysis") == "advanced"
    page.wait_for_selector("#ov-thesis [data-tc-start], #ov-thesis [data-tc-edit]")
    assert page.locator("#gi-entry-h").count() == 1 and page.locator("[data-tl-slot], #ov-events").count() == 1
    assert stubs(page) == []
    ctx.close()


# ------------------------------------------------------------------ Show more

def test_show_more_on_home_opens_that_panel_only_and_keeps_the_level(chrome, server):
    ctx, page = open_page(chrome, server, level="beginner")
    home(page, server)
    before = shown_panels(page)
    page.click("[data-v2-show-more='regime']")
    page.wait_for_selector("[data-ws-panel='regime']")
    assert shown_panels(page) == before + ["regime"]
    assert "regime" not in stubs(page)
    assert pressed(page) == "beginner" and page.evaluate("localStorage.getItem('optic.knowledge.v1')") == "beginner"
    ctx.close()


def test_show_more_on_the_stock_page_opens_that_panel_only_and_keeps_the_level(chrome, server):
    ctx, page = open_page(chrome, server, level="beginner")
    stock(page, server)
    page.click("[data-v2-show-more='cases']")
    page.wait_for_selector("[data-v2-ov-panel='cases']", state="attached")
    assert page.get_attribute("#ov-analysis", "data-v2-analysis") == "simple", "the advanced analysis stays folded"
    assert page.locator("#ov-thesis").count() == 0
    assert set(stubs(page)) == {"advanced", "thesis", "investigate", "timeline"}
    assert pressed(page) == "beginner"
    page.click("[data-v2-show-more='advanced']")
    page.wait_for_function("() => document.querySelector('#ov-analysis').dataset.v2Analysis === 'advanced'")
    assert pressed(page) == "beginner" and page.evaluate("localStorage.getItem('optic.knowledge.v1')") == "beginner"
    ctx.close()


def test_changing_the_level_closes_what_show_more_opened(chrome, server):
    ctx, page = open_page(chrome, server, level="beginner")
    home(page, server)
    page.click("[data-v2-show-more='regime']")
    page.wait_for_selector("[data-ws-panel='regime']")
    page.click("[data-v2-lc] [data-v2-level='intermediate']")
    page.wait_for_function("() => document.querySelector('[data-v2-level-now]').dataset.v2LevelNow === 'intermediate'")
    page.click("[data-v2-lc] [data-v2-level='beginner']")
    page.wait_for_function("() => document.querySelector('[data-v2-level-now]').dataset.v2LevelNow === 'beginner'")
    assert shown_panels(page) == ["indices", "priority", "watch", "desk"]
    ctx.close()


# ------------------------------------------------------------------ the level is kept

def test_the_level_survives_a_reload_signed_out(chrome, server):
    ctx, page = open_page(chrome, server)
    home(page, server)
    assert pressed(page) == "intermediate", "a first visit opens at Intermediate in this round"
    page.click("[data-v2-lc] [data-v2-level='advanced']")
    page.wait_for_function("() => document.querySelector('[data-v2-level-now]').dataset.v2LevelNow === 'advanced'")
    page.reload()
    page.wait_for_selector("[data-v2-lc] [aria-pressed='true']")
    assert pressed(page) == "advanced"
    stock(page, server)
    assert pressed(page) == "advanced", "the same one value on the stock page"
    ctx.close()


def test_the_level_follows_the_account_to_another_device(chrome, server):
    email, jar = make_account(server)
    a, pa = open_page(chrome, server, cookies=jar)
    home(pa, server)
    pa.wait_for_selector("[data-v2-account].avatar")
    with pa.expect_response(lambda r: "/api/auth/preferences" in r.url and r.request.method == "PATCH"):
        pa.click("[data-v2-lc] [data-v2-level='beginner']")
    # another device: its own storage, nothing in it, the same account
    b, pb = open_page(chrome, server, cookies=jar)
    home(pb, server)
    pb.wait_for_function("() => document.querySelector('[data-v2-lc] [aria-pressed=\"true\"]').dataset.v2Level === 'beginner'")
    assert pb.evaluate("localStorage.getItem('optic.knowledge.v1')") == "beginner"
    a.close(); b.close()


@pytest.mark.parametrize("stored,expected", [("new", "beginner"), ("beginner", "beginner"), ("intermediate", "intermediate"),
                                             ("advanced", "advanced"), ("expert", "advanced")])
def test_a_stored_five_level_value_opens_at_its_three_level_name(chrome, server, stored, expected):
    ctx, page = open_page(chrome, server, level=stored)
    home(page, server)
    assert pressed(page) == expected
    assert page.evaluate("localStorage.getItem('optic.knowledge.v1')") == expected, "rewritten once as one of the three"
    ctx.close()


# ------------------------------------------------------------------ the level never changes a figure

def facts(page):
    return page.evaluate("""() => {
      const t = (s) => [...document.querySelectorAll(s)].map(e => e.textContent.replace(/\\s+/g, ' ').trim());
      return { price: t('.dhead .dh-px'), change: t('.dhead .dh-chg'), when: t('.dhead .dh-ext'), about: t('.about-kv'),
               disclaimer: t('.disclaimer'), notice: t('.legal-area'), footer: t('.legal-line') };
    }""")


def test_figures_caveats_and_disclosures_are_the_same_at_every_level(chrome, server):
    seen = {}
    for lv in LEVELS:
        ctx, page = open_page(chrome, server, level=lv)
        stock(page, server)
        page.wait_for_selector(".about-kv")
        seen[lv] = facts(page)
        ctx.close()
    assert seen["beginner"]["price"] == ["248.21"]
    assert seen["beginner"] == seen["intermediate"] == seen["advanced"], json.dumps(seen, indent=1)


# ------------------------------------------------------------------ the Milo prompts

def prompt_text(page, screen):
    return page.text_content("[data-v2-mp='{}'] [data-v2-mp-text]".format(screen)).strip()


def test_home_prompt_without_holdings_or_names_asks_about_the_market(chrome, server):
    ctx, page = open_page(chrome, server, level="beginner")
    home(page, server)
    assert prompt_text(page, "home") == "Why did the market move today?"
    ctx.close()


def test_home_prompt_with_followed_names_asks_about_them(chrome, server):
    ctx, page = open_page(chrome, server, level="beginner")
    home(page, server)
    page.click("[data-ws-panel='watch'] [data-v2-watch='AAPL']")
    page.wait_for_function("() => document.querySelector('[data-v2-mp=\"home\"] [data-v2-mp-text]').textContent.includes('names I follow')")
    assert prompt_text(page, "home") == "Why did the names I follow move today?"
    ctx.close()


def test_home_prompt_with_holdings_asks_about_them(chrome, server):
    ctx, page = open_page(chrome, server, level="beginner", store={"optic.paper.v1": json.dumps({"open": [{"ticker": "NVDA"}]})})
    home(page, server)
    assert prompt_text(page, "home") == "Why did my holdings move today?"
    ctx.close()


def test_stock_prompt_names_the_company_or_falls_back_to_the_ticker(chrome, server):
    ctx, page = open_page(chrome, server, level="beginner")
    stock(page, server, "AAPL")
    assert prompt_text(page, "overview") == "Why is Apple moving today?"
    stock(page, server, "QQQX")
    assert prompt_text(page, "overview") == "Why is QQQX moving today?"
    ctx.close()


def milo_requests(stub):
    return [json.dumps(r["body"]) for r in stub.messages()]


def test_signed_in_the_stock_prompt_asks_milo_with_the_symbol_figures_and_level(chrome, server, stub):
    from app import knowledge
    stub.reset("ok")
    email, jar = make_account(server)
    ctx, page = open_page(chrome, server, level="beginner", cookies=jar)
    stock(page, server)
    page.wait_for_selector("[data-v2-account].avatar")
    page.click("[data-v2-mp='overview'] [data-v2-mp-ask]")
    page.wait_for_selector(".milo-log .milo-gen, .milo-log article", timeout=20000)
    page.wait_for_function("() => (document.querySelector('.milo-log') || {}).textContent && document.querySelector('.milo-log').textContent.includes('Stand-in answer')", timeout=60000)
    sent = milo_requests(stub)
    assert sent, "Milo's request never reached the stub"
    body = sent[-1]
    assert "Why is Apple moving today?" in body and "AAPL" in body and "248.21" in body
    assert json.dumps(knowledge.MODES["beginner"]["prompt"][:60])[1:-1] in body, "the request carries the reader's level"
    rows = usage_rows(server, "milo_question")
    assert rows and rows[-1]["source_screen"] == "overview" and rows[-1]["symbol"] == "AAPL" and rows[-1]["level"] == "beginner"
    ctx.close()


def test_signed_in_the_home_prompt_asks_milo_with_the_screens_figures(chrome, server, stub):
    stub.reset("ok")
    email, jar = make_account(server)
    ctx, page = open_page(chrome, server, level="intermediate", cookies=jar)
    home(page, server)
    page.wait_for_selector("[data-v2-account].avatar")
    page.click("[data-v2-mp='home'] [data-v2-mp-ask]")
    page.wait_for_function("() => (document.querySelector('.milo-log') || {}).textContent && document.querySelector('.milo-log').textContent.includes('Stand-in answer')", timeout=60000)
    body = milo_requests(stub)[-1]
    assert "Why did the market move today?" in body and "Markets at a glance, today" in body
    ctx.close()


def test_signed_out_the_prompt_leads_to_sign_in_and_milo_asks_it_after(chrome, server, stub):
    """The one journey that drives sign-in through the form, because sign-in is the behaviour under test."""
    stub.reset("ok")
    email, _ = make_account(server)
    ctx, page = open_page(chrome, server, level="beginner")
    stock(page, server)
    assert page.text_content("[data-v2-mp='overview'] [data-v2-mp-ask]").strip() == "Sign in to ask"
    page.click("[data-v2-mp='overview'] [data-v2-mp-ask]")
    page.wait_for_url(re.compile(r".*#/signin\?next=.*"))
    assert stub.messages() == [], "nothing is asked before sign-in"
    page.fill("form[data-v2-auth] input[name=email]", email)
    page.fill("form[data-v2-auth] input[name=password]", PASSWORD)
    page.click("form[data-v2-auth] button[type=submit]")
    page.wait_for_url(re.compile(r".*#/AAPL$"))
    page.wait_for_function("() => (document.querySelector('.milo-log') || {}).textContent && document.querySelector('.milo-log').textContent.includes('Stand-in answer')", timeout=60000)
    assert "Why is Apple moving today?" in milo_requests(stub)[-1]
    ctx.close()


@pytest.mark.parametrize("mode", ["timeout", "error"])
def test_anthropic_down_shows_the_failure_and_leaves_no_half_written_conversation(chrome, server, stub, mode):
    stub.reset(mode)
    stub.hold = 8.0
    email, jar = make_account(server)
    ctx, page = open_page(chrome, server, level="beginner", cookies=jar)
    stock(page, server)
    page.wait_for_selector("[data-v2-account].avatar")
    page.click("[data-v2-mp='overview'] [data-v2-mp-ask]")
    # the failure, said in the conversation; the question back in the box; no answer kept
    page.wait_for_function("() => { const b = document.querySelector('#milo-q'); return b && b.value.includes('Why is Apple moving today?'); }", timeout=30000)
    log = page.text_content(".milo-log")
    assert "Stand-in answer" not in log
    saved = page.evaluate("JSON.stringify(Object.keys(localStorage).filter(k => k.includes('milo') || k.includes('pulse')).map(k => [k, localStorage.getItem(k)]))")
    assert "Stand-in answer" not in saved and "[Cut off" not in saved
    stub.reset("ok")
    ctx.close()


# ------------------------------------------------------------------ the first signal

def test_opening_a_stock_from_home_is_recorded_once_with_nothing_personal(chrome, server):
    before = len(usage_rows(server, "home_stock_open"))
    ctx, page = open_page(chrome, server, level="beginner")
    home(page, server)
    page.click("[data-ws-panel='watch'] [data-v2-watch='MSFT']")
    page.wait_for_selector("[data-ws-panel='watch'] a.ws-tick[href='#/MSFT']")
    page.click("[data-ws-panel='watch'] a.ws-tick[href='#/MSFT']")
    page.wait_for_selector("#ov-analysis")
    deadline = time.time() + 10
    while time.time() < deadline and len(usage_rows(server, "home_stock_open")) == before:
        time.sleep(0.2)
    rows = usage_rows(server, "home_stock_open")
    assert len(rows) == before + 1
    r = rows[-1]
    assert (r["symbol"], r["source_screen"], r["actor_kind"], r["level"]) == ("MSFT", "home", "visitor", "beginner")
    assert re.match(r"^v-[0-9a-f]{32}$", r["actor_ref"])
    # and a visit for the day
    assert any(v["actor_ref"] == r["actor_ref"] for v in usage_rows(server, "visit"))
    ctx.close()


# ------------------------------------------------------------------ accessibility and the keyboard

@pytest.mark.parametrize("viewport", [DESKTOP, PHONE], ids=["desktop", "phone"])
@pytest.mark.parametrize("level", LEVELS)
@pytest.mark.parametrize("screen", ["home", "stock"])
def test_axe_finds_no_wcag_a_or_aa_violation(chrome, server, screen, level, viewport):
    from axe_playwright_python.sync_playwright import Axe
    ctx, page = open_page(chrome, server, level=level, viewport=viewport)
    (home if screen == "home" else stock)(page, server)
    page.wait_for_timeout(1500)   # the panels that answer quickly have drawn
    result = Axe().run(page, options={"runOnly": {"type": "tag", "values": ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]}})
    violations = result.response.get("violations", [])
    assert violations == [], json.dumps([{"id": v["id"], "nodes": [n["target"] for n in v["nodes"]][:4], "help": v["help"]} for v in violations], indent=1)
    ctx.close()


FOCUS_LOG = """(() => { if (window.__focusLog) return; window.__focusLog = [];
  document.addEventListener('focusin', (e) => { const t = e.target; window.__focusLog.push({ level: (t.dataset || {}).v2Level || '',
    panel: (t.closest && t.closest('[data-ws-panel]') || { dataset: {} }).dataset.wsPanel || '' }); }, true); })()"""


def _focus_reached(page, what, value, since):
    """Wait on the focus move itself: a focusin event on the element named, recorded in the page, after entry `since`.
    No time budget of its own (Playwright's default applies): the journey failed once in three suite runs while it
    waited 5 s on a reading of activeElement under load (gauntlet D2, 2026-11-10)."""
    page.wait_for_function("([k, v, n]) => window.__focusLog.slice(n).some((f) => f[k] === v)", arg=[what, value, since])


def _settled(page):
    """Two animation frames, so anything the page deferred to a frame has run before focus is read."""
    page.evaluate("() => new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(() => r())))")


def test_the_level_control_and_show_more_work_from_the_keyboard(chrome, server):
    ctx, page = open_page(chrome, server, level="beginner")
    home(page, server)
    page.evaluate(FOCUS_LOG)
    page.focus("[data-v2-lc] [data-v2-level='beginner']")
    page.keyboard.press("Tab")
    assert page.evaluate("document.activeElement.dataset.v2Level") == "intermediate"
    n = page.evaluate("window.__focusLog.length")
    page.keyboard.press("Space")
    page.wait_for_function("() => document.querySelector('[data-v2-level-now]').dataset.v2LevelNow === 'intermediate'")
    # the page redraws for the new level, which drops the button that had focus; focus goes back to the new pressed one
    _focus_reached(page, "level", "intermediate", n)
    _settled(page)
    assert page.evaluate("document.activeElement.dataset.v2Level") == "intermediate"
    page.keyboard.press("Shift+Tab")
    page.keyboard.press("Enter")
    page.wait_for_function("() => document.querySelector('[data-v2-level-now]').dataset.v2LevelNow === 'beginner'")
    page.focus("[data-v2-show-more='regime']")
    n = page.evaluate("window.__focusLog.length")
    page.keyboard.press("Enter")
    page.wait_for_selector("[data-ws-panel='regime']")
    # focus moves to what opened (the panel's body), and nothing deferred from the level change takes it back
    _focus_reached(page, "panel", "regime", n)
    _settled(page)
    assert page.evaluate("!!(document.activeElement && document.activeElement.closest('[data-ws-panel=\"regime\"]'))"), \
        page.evaluate("JSON.stringify(window.__focusLog)")
    ctx.close()


# ------------------------------------------------------------------ the past-year chart, drawn (gauntlet D1, 2026-11-10)

def stock_with_chart(chrome, server, level, viewport=DESKTOP, sym="AAPL"):
    ctx, page = open_page(chrome, server, level=level, viewport=viewport)
    route_price_history(page)
    stock(page, server, sym)
    page.wait_for_selector(".chart-slot[data-chart='price'] svg.chart")
    return ctx, page


@pytest.mark.parametrize("viewport", [DESKTOP, PHONE], ids=["desktop", "phone"])
@pytest.mark.parametrize("level", LEVELS)
def test_axe_finds_no_violation_on_the_stock_page_with_its_chart_drawn(chrome, server, level, viewport):
    """The scans above never drew the chart (the feeds are refused, so no price history arrives); the live copy failed
    axe's nested-interactive on it at every level. Here the history and four earnings reports come from a fixture."""
    from axe_playwright_python.sync_playwright import Axe
    ctx, page = stock_with_chart(chrome, server, level, viewport)
    marks = page.locator(".chart-slot[data-chart='price'] svg.chart .ev-mark[role='button']")
    assert marks.count() == 4, "the four reports are drawn as buttons"
    page.wait_for_timeout(1500)
    result = Axe().run(page, options={"runOnly": {"type": "tag", "values": ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]}})
    violations = result.response.get("violations", [])
    assert violations == [], json.dumps([{"id": v["id"], "nodes": [n["target"] for n in v["nodes"]][:4], "help": v["help"]} for v in violations], indent=1)
    assert page.errors == []
    ctx.close()


def test_the_charts_marks_are_named_buttons_and_open_from_the_keyboard(chrome, server):
    ctx, page = stock_with_chart(chrome, server, "beginner")
    svg = page.locator(".chart-slot[data-chart='price'] svg.chart")
    assert svg.get_attribute("role") == "group" and svg.get_attribute("aria-roledescription") == "chart"
    assert svg.get_attribute("aria-label").startswith("AAPL closing price: from ")
    names = page.eval_on_selector_all(".chart-slot[data-chart='price'] .ev-mark", "els => els.map(e => e.getAttribute('aria-label'))")
    assert names[-1] == "Earnings report, Oct 30, 2026", names
    # the chart itself still takes focus for the crosshair, and the next Tab reaches the first mark; read once the page
    # has stopped repainting as its other reads land (each paint draws the chart anew, and focus with it)
    page.wait_for_load_state("networkidle")
    svg.focus()
    page.keyboard.press("End")
    assert page.locator(".chart-wrap .chart-tip").is_visible()
    page.keyboard.press("Tab")
    assert page.evaluate("document.activeElement.classList.contains('ev-mark')")
    page.keyboard.press("Enter")
    page.wait_for_selector(".drawer.is-open")
    assert "earnings" in page.text_content(".drawer.is-open").lower()
    ctx.close()


# ------------------------------------------------------------------ the phone bar takes the rail's names (gauntlet L3, 2026-11-10)

def bar(page):
    return page.eval_on_selector_all(".tabbar > a, .tabbar > button", """els => els.map(e => ({ name: e.textContent.trim(),
      href: e.getAttribute('href'), current: e.getAttribute('aria-current') === 'page',
      fits: e.querySelector('span').scrollWidth <= e.clientWidth, lines: Math.round(e.querySelector('span').getBoundingClientRect().height),
      left: e.querySelector('span').getBoundingClientRect().left, right: e.querySelector('span').getBoundingClientRect().right }))""")


def rail(page):
    return page.eval_on_selector_all(".rail-nav a.rail-row", "els => Object.fromEntries(els.map(e => [e.textContent.trim(), e.getAttribute('href')]))")


@pytest.mark.parametrize("width", [390, 360, 340, 320])
def test_the_phone_bar_has_the_rails_names_and_opens_what_the_rail_opens(chrome, server, width):
    ctx, page = open_page(chrome, server, level="beginner", viewport={"width": width, "height": 844})
    home(page, server)
    tabs = bar(page)
    assert [t["name"] for t in tabs] == ["Home", "Research", "Markets", "Discover", "Portfolio", "Lists", "More"]
    # The suite blocks the web fonts, so labels are measured in whatever fallback face the machine has: on the ops Mac
    # every label fits its own column at every width; on GitHub's macOS runner "Research" ran a pixel or two past its
    # column at 320 px. What a reader would see go wrong is a label that wraps, overlaps its neighbour or leaves the
    # screen, so those are asserted at every width, and fitting its own column at 390 px, the phone of record.
    if width >= 390:
        assert all(t["fits"] for t in tabs), tabs
    assert len({t["lines"] for t in tabs}) == 1, "every label on one line"
    assert all(a["right"] <= b["left"] for a, b in zip(tabs, tabs[1:])), [(t["name"], round(t["left"]), round(t["right"])) for t in tabs]
    assert tabs[0]["left"] >= 0 and tabs[-1]["right"] <= width
    assert page.evaluate("(() => { const b = document.querySelector('.tabbar'); return b.scrollWidth <= b.clientWidth && b.getBoundingClientRect().right <= window.innerWidth; })()"), "the bar fits the screen"
    r = rail(page)
    by = {t["name"]: t for t in tabs}
    assert by["Home"]["href"] == "#/" and by["Home"]["current"]
    assert by["Research"]["href"] == r["Company Overview"] == "#/dossier", "no company open yet: the company search, as the rail"
    for name in ("Markets", "Discover", "Portfolio"):
        assert by[name]["href"] == r[name], name
    assert by["Lists"]["href"] == r["Watchlist"] == "#/watchlist"
    ctx.close()


def test_the_phone_bar_follows_the_page_and_more_holds_the_rest(chrome, server):
    ctx, page = open_page(chrome, server, level="beginner", viewport=PHONE)
    stock(page, server, "AAPL")
    by = {t["name"]: t for t in bar(page)}
    assert by["Research"]["current"] and by["Research"]["href"] == "#/AAPL", "Research opens the company open on this visit"
    for route, name in (("#/read", "Markets"), ("#/explore", "Discover"), ("#/portfolio", "Portfolio"), ("#/scan", "Lists"), ("#/watchlist", "Lists")):
        page.goto(server["base"] + "/" + route, wait_until="domcontentloaded")
        page.wait_for_function("(n) => [...document.querySelectorAll('.tabbar [aria-current=\"page\"]')].map(e => e.textContent.trim()).join() === n", arg=name)
    # More's Research entries follow the same company as the bar's Research tab, whether or not its quote has come:
    # they followed the visit's recents, which wait on the quote, and on the live copy More said the company search
    # while the bar said the company (round two, 2026-11-10). MSFT's quote is held back here so the two can differ.
    page.route(re.compile(r".*/api/quote/MSFT(\?.*)?$"), lambda route: route.abort())
    page.goto(server["base"] + "/#/MSFT", wait_until="domcontentloaded")
    page.wait_for_function("() => (document.querySelector('.tabbar [data-v2-tab=\"security\"]') || {}).getAttribute && document.querySelector('.tabbar [data-v2-tab=\"security\"]').getAttribute('href') === '#/MSFT'")
    page.click(".tabbar [data-v2-more]")
    page.wait_for_selector(".drawer.is-open .more-list")
    early = page.eval_on_selector_all(".drawer.is-open .more-row", "els => Object.fromEntries(els.map(e => [e.querySelector('.more-lab').firstChild.textContent.trim(), e.getAttribute('href')]))")
    assert early["Financials & Valuation"] == "#/MSFT/financials", early
    page.keyboard.press("Escape")
    page.goto(server["base"] + "/#/AAPL", wait_until="domcontentloaded")
    page.wait_for_selector("#ov-analysis")
    page.click(".tabbar [data-v2-more]")
    page.wait_for_selector(".drawer.is-open .more-list")
    groups = page.eval_on_selector_all(".drawer.is-open .more-glab", "els => els.map(e => e.textContent.trim())")
    assert groups == ["Research", "Lists", "More"]
    rows = page.eval_on_selector_all(".drawer.is-open .more-row .more-lab", "els => els.map(e => e.firstChild.textContent.trim())")
    for name in ("Company Overview", "Financials & Valuation", "Charts & Technicals", "Options & Derivatives", "Filings & Ownership",
                 "Watchlist", "Ideas", "Research", "Compare", "Alerts", "Settings", "Sign in"):
        assert name in rows, name
    hrefs = page.eval_on_selector_all(".drawer.is-open .more-row", "els => Object.fromEntries(els.map(e => [e.querySelector('.more-lab').firstChild.textContent.trim(), e.getAttribute('href')]))")
    assert hrefs["Financials & Valuation"] == "#/AAPL/financials" and hrefs["Filings & Ownership"] == "#/insiders?symbol=AAPL"
    assert hrefs["Ideas"] == "#/scan" and hrefs["Research"] == "#/research" and hrefs["Alerts"] == "#/alerts"
    ctx.close()
