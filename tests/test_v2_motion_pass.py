"""The motion pass of 2026-10-24 (the owner's go on the motion proposal), held in place.

- Indicator colours: the owner's mapping, VWAP the one cool hue, EMA 50 red and dashed, EMA 21 green, EMA 9 the ink,
  each line named at its right end so none is told apart by colour alone.
- Tabs answer the press in the same frame (a first visit showed nothing for up to 300 ms), on every strip, and the
  content fades on phones too; the same page drawn again plays no entrance.
- The chart draw-on is 400 ms (--m-reveal) and never holds a redraw back (it made redraws wait up to 620 ms). A
  bar-size change keeps the chart on screen, dimmed and marked, until the new bars replace it.
- Settings has Motion: Follow system or Reduce, read by the CSS, by reducedMotion() and by Scout.
- Milo: a notice after 30 s with nothing from the server, the attached parts listed and removable, and a report on
  one answer that says it does not train the model.
- The watchlist refreshes, holds its order until the reader asks for Re-sort, and marks prices that moved.

Measured in headless Chromium with real frames by ~/Optic/work/motion-pass-2026-10-24/check.mjs (fake answers for
Milo, no model called); the wiring is read as text here, as the other v2 contract tests do.
"""
import re

from tests.test_frontend_v2_stage0 import V2

JS = V2 / "js"
TOK = (V2 / "css/tokens.css").read_text()
BASE = (V2 / "css/base.css").read_text()
COMP = (V2 / "css/components.css").read_text()
PAGES = (V2 / "css/pages.css").read_text()
PC = (JS / "ui/pricechart.js").read_text()
DRAWON = (JS / "ui/drawon.js").read_text()
MOTION = (JS / "ui/motion.js").read_text()
APP = (JS / "app.js").read_text()
DOM = (JS / "core/dom.js").read_text()
PREFS = (JS / "core/prefs.js").read_text()
SETTINGS = (JS / "pages/settings.js").read_text()
CHART = (JS / "pages/chart.js").read_text()
MILO = (JS / "ui/milo.js").read_text()
WL = (JS / "pages/watchlist.js").read_text()
FRAME = (JS / "pages/dossier-frame.js").read_text()
SCOUT = (V2.parent / "components/scout.js").read_text()


def _hex(name, block):
    m = re.search(r"--%s:\s*(#[0-9a-f]{6}|var\(--c-ink\))" % re.escape(name), block, re.I)
    return m and m.group(1).lower()


def _lum(h):
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (1, 3, 5))
    f = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def _contrast(a, b):
    hi, lo = sorted((_lum(a), _lum(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


# ------------------------------------------------------------ indicator colours

def test_the_owners_indicator_mapping():
    assert ".pc .e1 { stroke: var(--c-ind-ema9); }" in PAGES
    assert ".pc .e2 { stroke: var(--c-ind-ema21); }" in PAGES
    assert ".pc .e3 { stroke: var(--c-ind-ema50); stroke-dasharray: 6 3; }" in PAGES, "EMA 50 is dashed"
    assert ".pc .sl.vw { stroke: var(--c-ind-vwap);" in PAGES
    assert ".pc-leg i.kvw { border-top-color: var(--c-ind-vwap); }" in PAGES
    # EMA 9 is the ink: white on charcoal, dark on ivory, never a white line on the light theme
    assert "--c-ind-ema9: var(--c-ink);" in TOK


def test_indicator_colours_read_as_text_and_differ_from_the_candles():
    light = TOK[:TOK.index(':root[data-theme="charcoal"]')]
    dark = TOK[TOK.index(':root[data-theme="charcoal"]'):TOK.index("@media (prefers-color-scheme: dark)")]
    for block, panel, pos, neg in ((light, "#fffcf6", "#0d7a42", "#b43a25"), (dark, "#161614", "#4cc38a", "#f07a66")):
        for name in ("c-ind-ema21", "c-ind-ema50", "c-ind-vwap"):
            h = _hex(name, block)
            assert h and h.startswith("#"), name
            assert _contrast(h, panel) >= 4.5, (name, h)
        assert _hex("c-ind-ema21", block) != pos and _hex("c-ind-ema50", block) != neg, "an average must not read as a candle"
    # the follow-system dark block carries the same three
    sysdark = TOK[TOK.index("@media (prefers-color-scheme: dark)"):]
    assert all(_hex(n, sysdark) == _hex(n, dark) for n in ("c-ind-ema21", "c-ind-ema50", "c-ind-vwap"))


def test_each_indicator_is_named_at_its_right_end():
    assert "[['ema9', 'e1', 'EMA 9'], ['ema21', 'e2', 'EMA 21'], ['ema50', 'e3', 'EMA 50']]" in PC
    assert "c: 'vw', t: 'VWAP'" in PC
    assert '<text class="endl ${e.c}"' in PC and 'text-anchor="end"' in PC
    assert "last + 13" in PC, "labels that would overlap step apart"


# ------------------------------------------------------------ tabs

def test_a_tab_is_selected_on_the_press():
    assert "motion.tabPressed(b)" in APP and "nav.tabs a[href^=\"#\"]" in APP
    pressed = MOTION[MOTION.index("export function tabPressed"):]
    assert "a.setAttribute('aria-current', 'page')" in pressed


def test_tab_motion_covers_every_strip_and_phones():
    assert "view.querySelector('nav.tabs[data-v2-dtabs]') || view.querySelector('nav.tabs')" in MOTION
    before = MOTION[MOTION.index("export function tabsBefore"):MOTION.index("export function tabsAfter")]
    assert "left: vis ? cur.offsetLeft : null" in before, "a phone (no visible tab) still gets the content fade"
    assert "whenDrawn(view, 'nav.tabs'," in APP


def test_the_same_page_drawn_again_plays_no_entrance():
    assert "const tabsWere = again ? null : motion.tabsBefore(" in APP


# ------------------------------------------------------------ charts

def test_the_draw_on_is_the_token_and_never_holds_a_redraw():
    assert "--m-reveal: 400ms" in TOK and "--m-stagger: 24ms" in TOK and "--m-hover: 120ms" in TOK
    assert "tok('--m-reveal', 400)" in DRAWON
    assert "620" not in DRAWON.split("export function drawOn")[1]
    assert "anim.busy()) { if (!holdT)" not in PC, "no redraw waits for the draw-on"
    assert "anim.carry(); else { anim.finish(); anim = null; }" in PC
    assert "['pointerdown', 'keydown', 'wheel'].forEach((ev) => svg.addEventListener(ev, finish" in DRAWON
    assert "import { reducedMotion as reduced } from '../core/dom.js';" in DRAWON


def test_a_bar_size_change_keeps_the_chart_dimmed_until_the_new_bars():
    assert "D.pending = chart ? `Loading ${iv.label} bars` : '';" in CHART
    assert "if (chart && D.pending && !D.bars) {" in CHART
    assert "#ch-body.is-pending > .pc-host" in PAGES and "pointer-events: none" in PAGES
    assert "data-v2-ch-rebars" in CHART and "if (t('[data-v2-ch-rebars]')) { loadBars(); return; }" in CHART


# ------------------------------------------------------------ the Motion setting

def test_settings_offers_motion_and_everything_reads_it():
    assert "const MOTION_KEY = 'optic.v2.motion.v1';" in PREFS
    assert "row('Motion'," in SETTINGS and "[['system', 'Follow system'], ['reduce', 'Reduce']]" in SETTINGS
    assert "prefs.applyMotion()" in APP
    assert "getAttribute('data-motion') === 'reduce'" in DOM
    assert ':root[data-motion="reduce"] *' in BASE
    assert ":root[data-motion=\"reduce\"] .page-line::before" in COMP
    assert "document.documentElement.getAttribute('data-motion') === 'reduce'" in SCOUT
    # no script asks the media query on its own any more
    for name, src in (("milo", MILO), ("motion", MOTION), ("drawon", DRAWON)):
        assert "matchMedia('(prefers-reduced-motion" not in src, name


# ------------------------------------------------------------ Milo

def test_milo_says_when_the_server_has_gone_quiet():
    assert "const QUIET_MS = 30000;" in MILO
    assert "No reply from the server for 30 seconds" in MILO
    assert "clearInterval(quietT);" in MILO, "the timer stops with the answer"
    assert "buf += dec.decode(step.value, { stream: true }); heard();" in MILO


def test_milo_lists_and_drops_the_attached_parts():
    assert "if (scope === 'auto') S.dropped.forEach((k) => { delete ctx[k]; });" in MILO
    assert "S.dropped.clear();" in MILO.split("export function resetContext")[1].split("\n}")[0]
    assert "data-v2-milo-drop" in MILO and "data-v2-milo-undrop" in MILO


def test_a_report_on_an_answer_goes_to_a_person_and_says_so():
    assert "api.post('/api/feedback'" in MILO
    assert "It does not train or change Milo." in MILO
    assert "1990 - head.length" in MILO, "the report stays inside the server's 2,000 characters"


def test_phone_milo_rises_opaque_rather_than_fading():
    phone = COMP[COMP.index("  .drawer-panel.milo-panel { top: var(--vvt, 0px);"):]
    phone = phone[:phone.index("}") + 1]
    assert "transform: translateY(16px); opacity: 1;" in phone


# ------------------------------------------------------------ the watchlist

def test_the_watchlist_refreshes_without_moving_rows():
    assert "refresh = poll((current) => quietRefresh(main, current), { every: EVERY, closed: CLOSED });" in WL
    assert "const EVERY = 60000, CLOSED = 300000;" in WL
    assert "if (S.sort !== 'custom' && !S.hold) S.hold = S.shown.slice();" in WL
    assert "data-v2-wl-resort" in WL and "S.hold = null" in WL
    assert "if (refresh) { refresh.stop(); refresh = null; }" in WL


def test_moved_prices_hold_their_colour_without_a_flash():
    for src in (WL, FRAME):
        assert "is-tick-up" in src and "setTimeout(" in src
    assert ".wl-price.is-tick-up, .dh-px.is-tick-up" in PAGES
    assert "background" not in PAGES[PAGES.index(".wl-price, .dh-px"):PAGES.index(".wl-resort")]
