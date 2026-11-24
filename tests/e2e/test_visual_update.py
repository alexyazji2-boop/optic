"""The visual update in a real browser (2026-11-11): Home and the company Overview drawn with figures, from invented
market and company figures served at the page's own API boundary (tests/e2e/visual_fixtures.py).

Each figure the update adds is drawn and named; every move carries an arrow and a sign; nothing on screen is under
13px; nothing scrolls sideways at 390; axe finds no WCAG A or AA violation with the figures drawn; a feed that refuses
leaves its panel's failed or empty state, never a blank or a crash; and the words on screen fall by at least 40% at
Beginner and Intermediate against the delivered build (f7f249c), counted with the same fixtures."""
from __future__ import annotations

import json

import pytest

from tests.e2e.test_pass1_journeys import DESKTOP, PHONE, LEVELS, open_page, home, stock, shown_panels, stubs
from tests.e2e.visual_fixtures import WATCH, refuse, route_company, route_home

NAMES = json.dumps([w[0] for w in WATCH])
# what the browser shows to the eye: text a screen reader alone hears (.sr, the level's unsaid preview) is left out
WORDS = """() => { const s = document.createElement('style'); s.textContent = '.sr, .lc:not(.is-said) .lc-says { display: none !important; }';
  document.head.appendChild(s); const n = document.querySelector('#main').innerText.split(/\\s+/).filter((w) => /[A-Za-z0-9]/.test(w)).length;
  s.remove(); return n; }"""


def with_figures(chrome, server, level, viewport=DESKTOP, screen="home", watch=True):
    ctx, page = open_page(chrome, server, level=level, viewport=viewport, store={"optic.chart.watch.v1": NAMES} if watch else None)
    route_home(page)
    route_company(page)
    if screen == "home":
        home(page, server)
        page.wait_for_selector("#hm-feature svg.chart")
        page.wait_for_selector("[data-ws-panel='indices'] .ws-cell .spark")
    else:
        stock(page, server)
        page.wait_for_selector(".chart-slot[data-chart='price'] svg.chart")
        page.wait_for_selector(".ov-figs .ov-fig")
    page.wait_for_timeout(600)
    return ctx, page


# ------------------------------------------------------------------ Home's figures

@pytest.mark.parametrize("level", ["beginner", "intermediate"])
def test_home_draws_its_figures(chrome, server, level):
    ctx, page = with_figures(chrome, server, level)
    # the headline line by its span, the start dashed, with a text alternative
    svg = page.locator("#hm-feature svg.chart")
    assert "tone-up" in svg.get_attribute("class") and page.locator("#hm-feature svg.chart line.base").count() == 1
    assert (svg.get_attribute("aria-label") or "").startswith("AAPL daily closes, past 6 months")
    assert page.locator("#hm-feature [data-hm-span]").all_inner_texts() == ["3M", "6M", "1Y"], "no 1-day line on Home"
    # 3M asks take-chart for its own span, nothing intraday
    with page.expect_request(lambda r: "/api/take-chart/" in r.url and "span=3m" in r.url):
        page.click("[data-hm-span='3m']")
    page.wait_for_selector("#hm-feature [data-hm-span='3m'][aria-pressed='true']")
    # eight tiles, each with its 90-session line and no unit line
    assert page.locator("[data-ws-panel='indices'] .ws-cell").count() == 8
    assert page.locator("[data-ws-panel='indices'] .ws-cell .spark").count() == 8
    assert "Index points" not in page.inner_text("[data-ws-panel='indices']")
    # the heat map, strongest first, no fund codes on the face
    tiles = page.locator("[data-ws-panel='sectors'] .ws-heat-t")
    assert tiles.count() == 11
    faces = tiles.all_inner_texts()
    assert faces[0].startswith("Technology") and faces[-1].startswith("Health Care")
    assert not any(code in " ".join(faces).split() for code in ("XLK", "XLV", "XLE"))
    # the Desk: its bottom line, with The whole desk opening the rest
    assert page.locator("[data-ws-panel='desk'] .desk-glance").count() == 1
    assert page.locator("[data-ws-panel='desk'] [data-v2-show-more='desk:full']").inner_text() == "The whole desk"
    if level == "intermediate":
        assert shown_panels(page) == ["indices", "regime", "sentiment", "expected", "sectors", "watch", "desk"]
        assert page.locator("[data-ws-panel='regime'] .gauge[role='img']").count() == 1
        assert page.locator("[data-ws-panel='regime'] .dbars li").count() == 6
        assert page.locator("[data-ws-panel='sentiment'] .gauge[role='img']").count() == 1
        assert page.locator("[data-ws-panel='sentiment'] .dbars li").count() == 6
        assert page.locator("[data-ws-panel='expected'] .pbars li").count() == 2
        assert page.locator("[data-ws-panel='watch'] tbody .spark[role='img']").count() == len(WATCH)
    else:
        assert shown_panels(page) == ["indices", "sectors", "desk"]
        assert {"priority", "watch", "regime"} <= set(stubs(page)), "What matters today and the watchlist are one row away"
    assert page.locator("#legal-footer").is_visible() and "Not financial advice" in page.inner_text("#legal-footer"), "the footer stays"
    assert page.errors == []
    ctx.close()


def test_more_on_home_opens_a_panel_in_place_with_show_less_and_focus_back(chrome, server):
    ctx, page = with_figures(chrome, server, "beginner")
    rows = page.locator("[data-v2-sm='home'] .sm-stub")
    assert rows.count() >= 20 and page.locator("[data-v2-sm='home'] .sm-stub p").count() == 0, "rows, not cards"
    assert page.inner_text("[data-v2-show-more='regime']") == "Open"
    page.click("[data-v2-show-more='regime']")
    page.wait_for_selector("[data-ws-panel='regime'] .gauge")
    assert "regime" not in stubs(page)
    page.click("[data-v2-show-less='regime']")
    page.wait_for_selector("[data-ws-panel='regime']", state="detached")
    page.wait_for_function("() => document.activeElement && document.activeElement.dataset.v2ShowMore === 'regime'")
    # the Desk's rest opens in place and closes back to its bottom line
    page.click("[data-v2-show-more='desk:full']")
    page.wait_for_selector("[data-v2-show-less='desk:full']")
    assert page.locator("[data-ws-panel='desk'] .desk-glance").count() == 0
    page.click("[data-v2-show-less='desk:full']")
    page.wait_for_selector("[data-ws-panel='desk'] .desk-glance")
    ctx.close()


def test_the_first_visit_card_stays_smaller_with_its_follow_buttons(chrome, server):
    ctx, page = open_page(chrome, server, level="beginner", onboarded=False)
    route_home(page)
    home(page, server)
    card = page.locator("#ws-new.is-compact")
    assert card.count() == 1 and page.locator("#ws-new [data-v2-watch]").count() == 4
    assert card.bounding_box()["height"] < 260, card.bounding_box()
    ctx.close()


# ------------------------------------------------------------------ the Overview's figures

@pytest.mark.parametrize("level", LEVELS)
def test_the_overview_draws_its_figures(chrome, server, level):
    ctx, page = with_figures(chrome, server, level, screen="stock")
    chg = page.inner_text(".dhead .dh-chg")
    assert "▲" in chg and "+" in chg, chg
    chart = page.locator(".chart-slot[data-chart='price'] svg.chart")
    assert "tone-up" in chart.get_attribute("class") and page.locator(".chart-slot[data-chart='price'] line.base").count() == 1
    assert page.locator(".chart-slot[data-chart='price'] .ev-mark").count() >= 1, "the event marks stay"
    assert page.locator(".dchart .dchart-cap").count() == 1 and page.locator(".dchart .section-sub").count() == 0, "one line of caption"
    figs = page.locator(".ov-figs .ov-fig")
    assert figs.count() == 4
    heads = figs.locator(".ov-fig-h").all_inner_texts()
    assert heads[0] == "Revenue grew 15%" and heads[1].startswith("Net margin") and heads[2] == "P/E above its usual" and heads[3] == "Next report"
    for key in ("of-rev", "of-margin"):
        page.wait_for_selector(f".chart-slot[data-chart='{key}'] svg[role='img']")
    assert page.locator(".ov-fig .pbars li").count() == 2
    assert page.locator(".about .donut svg[role='img']").count() == 1
    assert "iPhone" in page.get_attribute(".about .donut svg", "aria-label")
    page.wait_for_selector(".chart-slot[data-chart='of-eps'] svg[role='img']")
    if level == "beginner":
        assert page.locator(".chart-slot[data-chart='of-react']").count() == 0
        assert "words" in stubs(page) and "cases" in stubs(page)
    else:
        page.wait_for_selector(".chart-slot[data-chart='of-react'] svg[role='img']")
        assert page.locator(".chart-slot[data-chart='of-react'] rect.gbar.downb").count() >= 1, "the falls in red"
        assert page.locator(".ov-row3 .pbars li").count() == 2, "who owns it"
    if level == "intermediate":
        lines = page.locator("[data-v2-ov-panel='cases'] .cs-glance li")
        assert lines.count() >= 2 and page.locator("[data-v2-ov-panel='cases'] .cs-glance .mv-a").count() == lines.count()
    if level == "advanced":
        assert page.get_attribute("#ov-analysis", "data-v2-analysis") == "advanced" and stubs(page) == []
    assert page.errors == []
    ctx.close()


def test_the_words_open_from_more_and_close_back(chrome, server):
    ctx, page = with_figures(chrome, server, "beginner", screen="stock")
    page.click("[data-v2-show-more='words']")
    page.wait_for_selector("[data-v2-ov-panel='words'] .ov-simple")
    assert "What's happening?" in page.inner_text("[data-v2-ov-panel='words']")
    page.click("[data-v2-show-less='words']")
    page.wait_for_selector("[data-v2-ov-panel='words']", state="detached")
    page.wait_for_function("() => document.activeElement && document.activeElement.dataset.v2ShowMore === 'words'")
    ctx.close()


# ------------------------------------------------------------------ an arrow and a sign; 13px; no sideways scroll

ARROWS = """() => [...document.querySelectorAll('#main .mv.up, #main .mv.down, #main .dh-chg.up, #main .dh-chg.down')]
  .filter((e) => /\\d/.test(e.textContent)).map((e) => e.textContent.trim()).filter((t) => !(/[▲▼]/.test(t) && /[+\\u2212]/.test(t)))"""
SMALL = """() => { const out = []; const w = document.createTreeWalker(document.querySelector('#main'), NodeFilter.SHOW_TEXT);
  for (let n = w.nextNode(); n; n = w.nextNode()) { if (!n.textContent.trim()) continue; const el = n.parentElement;
    if (!el || !el.getClientRects().length || el.closest('.sr, [hidden], details:not([open]) > :not(summary), .chart-tip')) continue;
    const cs = getComputedStyle(el); if (cs.visibility === 'hidden' || cs.display === 'none' || cs.clipPath === 'inset(50%)') continue;
    const px = parseFloat(cs.fontSize); if (px < 13) out.push([el.tagName, el.getAttribute('class'), n.textContent.trim().slice(0, 30), px]); }
  return out; }"""


@pytest.mark.parametrize("viewport", [DESKTOP, PHONE], ids=["desktop", "phone"])
@pytest.mark.parametrize("level", ["beginner", "intermediate"])
@pytest.mark.parametrize("screen", ["home", "stock"])
def test_every_move_has_its_arrow_and_sign_nothing_is_under_13px_and_nothing_scrolls_sideways(chrome, server, screen, level, viewport):
    ctx, page = with_figures(chrome, server, level, viewport=viewport, screen=screen)
    page.wait_for_timeout(800)
    assert page.evaluate(ARROWS) == []
    assert page.locator("#main .mv-a").count() >= (8 if screen == "home" else 1)
    assert page.evaluate(SMALL) == []
    assert page.evaluate("document.documentElement.scrollWidth") <= viewport["width"], "no sideways scroll"
    ctx.close()


# ------------------------------------------------------------------ accessibility with the figures drawn

@pytest.mark.parametrize("viewport", [DESKTOP, PHONE], ids=["desktop", "phone"])
@pytest.mark.parametrize("level", LEVELS)
@pytest.mark.parametrize("screen", ["home", "stock"])
def test_axe_finds_no_violation_with_the_figures_drawn(chrome, server, screen, level, viewport):
    from axe_playwright_python.sync_playwright import Axe
    ctx, page = with_figures(chrome, server, level, viewport=viewport, screen=screen)
    page.wait_for_timeout(1000)
    result = Axe().run(page, options={"runOnly": {"type": "tag", "values": ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]}})
    violations = result.response.get("violations", [])
    assert violations == [], json.dumps([{"id": v["id"], "nodes": [n["target"] for n in v["nodes"]][:4], "help": v["help"]} for v in violations], indent=1)
    # every figure has a text alternative: a named image, or its values as text beside it
    unnamed = page.evaluate("""() => [...document.querySelectorAll('#main svg')].filter((s) => s.closest('[aria-hidden="true"]') === null
      && s.getAttribute('aria-hidden') !== 'true' && !(s.getAttribute('aria-label') || '').trim() && !s.closest('button, a')).map((s) => s.getAttribute('class'))""")
    assert unnamed == [], unnamed
    ctx.close()


# ------------------------------------------------------------------ a feed that refuses (as the copy saw on 2026-11-10 and 11)

@pytest.mark.parametrize("level", ["beginner", "intermediate"])
def test_home_with_its_feeds_refusing_shows_each_panels_failed_state(chrome, server, level):
    ctx, page = open_page(chrome, server, level=level, store={"optic.chart.watch.v1": NAMES})
    route_home(page)
    refuse(page, "home", "sentiment", "market", "take-chart", "watchlist")
    home(page, server)
    for pid in (["indices", "sectors", "desk"] + (["regime", "sentiment", "expected", "watch"] if level == "intermediate" else [])):
        page.wait_for_function("(id) => { const b = document.querySelector(`#wsb-${id}`); return b && !b.querySelector('.sk, [aria-busy=\"true\"]') && b.innerText.trim().length > 10; }", arg=pid, timeout=40000)
    assert page.locator("#main .spark, #main .gauge, #main .ws-heat-t").count() == 0, "nothing drawn from a series that did not come"
    page.wait_for_function("() => /did not load|not available|did not come back|No index readings/i.test(document.querySelector('#hm-feature').innerText)", timeout=40000)
    assert page.errors == []
    ctx.close()


@pytest.mark.parametrize("level", ["beginner", "intermediate"])
def test_the_overview_with_its_feeds_refusing_says_what_is_missing(chrome, server, level):
    ctx, page = open_page(chrome, server, level=level)
    route_company(page)
    refuse(page, "earnings", "segments", "longterm")
    stock(page, server)
    page.wait_for_selector(".ov-figs .ov-fig", timeout=40000)
    text = page.inner_text("#ov-analysis")
    assert "No reported quarters came back for it." in text or "The earnings history did not load." in text
    assert page.locator(".about .donut").count() == 0, "no mix without its filings"
    assert "No P/E history came back for it." in text or "×" in text
    assert page.errors == []
    ctx.close()
    # and with the statements themselves refused, the figures give way to the delivered failed state
    ctx, page = open_page(chrome, server, level=level)
    refuse(page, "ticker")
    stock(page, server)
    page.wait_for_selector(".dchart .state, .dchart [role='alert'], #ov-analysis .ov-simple", timeout=40000)
    assert page.locator(".ov-figs .ov-fig").count() == 0 and page.errors == []
    ctx.close()


# ------------------------------------------------------------------ fewer words (counted against f7f249c, same fixtures)

# Measured on 2026-11-11 with this file's WORDS count, the fixtures in visual_fixtures.py, a five-name watchlist and a
# 1440 x 900 window, against the delivered build at f7f249c served the same way. Advanced is not cut: it shows every
# panel as delivered, with the figures added above its analysis.
BEFORE = {("home", "beginner"): 583, ("home", "intermediate"): 861, ("stock", "beginner"): 673, ("stock", "intermediate"): 708}


@pytest.mark.parametrize("level", ["beginner", "intermediate"])
@pytest.mark.parametrize("screen", ["home", "stock"])
def test_at_least_40_percent_fewer_words_than_the_delivered_screen(chrome, server, screen, level):
    ctx, page = with_figures(chrome, server, level, screen=screen)
    page.wait_for_timeout(4000)   # every panel that will answer has answered
    n = page.evaluate(WORDS)
    before = BEFORE[(screen, level)]
    assert n <= before * 0.6, f"{screen} at {level}: {n} words against {before} before ({100 - 100 * n / before:.0f}% fewer)"
    ctx.close()
