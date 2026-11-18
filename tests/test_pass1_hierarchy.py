"""The visual hierarchy round of Pass 1 (review of 2026-11-10): the contracts that keep its three rules in the source.

1. One headline figure: the company page's price is set by the display-size token, about twice the next tier.
2. One primary action per screen: the Milo bar's button is the design system's gold .btn-primary, and nothing else on
   Home or the Overview's header draws one (the browser count is in tests/e2e/test_pass1_journeys.py).
3. The level control is a setting in the second tier: 14px labels on 36px buttons, and its pressed level marked by a
   gold bar, not by a fill of 1.37:1 against its own track.

Read as text, as this project reads client contracts (tests/test_ui_refactor.py); each was checked against a mutation
of the line it names."""
from __future__ import annotations

import re

import app.main as main

V2 = main.STATIC_DIR / "v2"
JS = V2 / "js"
TOKENS = (V2 / "css" / "tokens.css").read_text()
COMPONENTS = (V2 / "css" / "components.css").read_text()
PAGES = (V2 / "css" / "pages.css").read_text()


def _rule(css: str, selector: str) -> str:
    """The declarations of the last rule whose selector is exactly `selector` (a later rule wins in the cascade)."""
    found = re.findall(r"(?m)^" + re.escape(selector) + r" \{([^}]*)\}", css)
    assert found, selector
    return found[-1]


# ------------------------------------------------------------------ one headline figure

def test_the_display_size_price_token_exists_and_is_about_twice_the_heading_tier():
    m = re.search(r"--t-figure: clamp\((\d+)px, [\d.]+vw, (\d+)px\);", TOKENS)
    assert m, "the headline figure's token"
    low, high = int(m.group(1)), int(m.group(2))
    assert low >= 34 and high >= 40, "34px on a phone, at least 40px wide: twice the 18px section heading tier"


def test_the_company_pages_price_uses_the_display_size_token():
    assert "font-size: var(--t-figure)" in _rule(PAGES, ".dhead.bar.dhead-overview .dh-px")
    assert "font-size: var(--t-lead)" in _rule(PAGES, ".dhead.bar.dhead-overview .dh-chg"), "the move beside it, at the lead size"
    frame = (JS / "pages" / "dossier-frame.js").read_text()
    assert "${view === 'overview' ? ' dhead-overview' : ''}" in frame, "the Overview's header carries the class"


def test_homes_one_figure_uses_the_same_token_and_the_greeting_steps_down():
    assert "var(--t-figure)" in _rule(PAGES, ".hm-feat-v")
    assert "font-size: var(--t-lead)" in _rule(PAGES, ".ws-pagehead h1")
    ws = (JS / "pages" / "workspace.js").read_text()
    assert "${featureBlock()}\n    ${miloPrompt(homeAsk())}" in ws, "the figure comes before the Milo bar"


# ------------------------------------------------------------------ one primary action per screen

def test_the_milo_bars_button_is_the_gold_primary():
    mp = (JS / "ui" / "miloprompt.js").read_text()
    assert '<button type="button" class="btn btn-primary mp-go" data-v2-mp-ask>' in mp
    assert ".btn-primary { background: var(--c-gold);" in COMPONENTS


def test_nothing_else_on_home_or_the_overview_header_is_primary():
    frame = (JS / "pages" / "dossier-frame.js").read_text()
    head = frame[frame.index("function overviewActions("):frame.index("/* The Weinstein stage")]
    assert "btn-primary" not in head and "miloButton(" not in head, "Watch and More; the bar is the one Milo entry"
    ws = (JS / "pages" / "workspace.js").read_text()
    paint = ws[ws.index("function paintAll() {"):ws.index("// The Desk at Beginner")]
    assert "btn-primary" not in paint
    # Customize is primary only while customizing, where Done is the view's action
    assert "${EDIT ? 'btn-primary' : ''}" in ws


# ------------------------------------------------------------------ the level control's tier

def test_the_level_control_is_in_the_second_tier():
    b = _rule(COMPONENTS, ".lc-b")
    assert "min-height: var(--ctl-sm)" in b and "var(--t-md)" in b, "14px labels on 36px buttons"
    assert "font-size: var(--t-sm)" in _rule(COMPONENTS, ".lc-q"), "the question is a 13px label"
    pressed = _rule(COMPONENTS, '.lc-b[aria-pressed="true"]')
    assert "border-bottom-color: var(--c-gold-ink)" in pressed, "the pressed level is marked by a gold bar"
    assert "--ctl-sm: 36px;" in TOKENS


def test_the_preview_sentence_is_kept_as_the_description_and_shown_after_a_change():
    lc = (JS / "ui" / "levelcontrol.js").read_text()
    assert 'aria-describedby="${id}-says" title="${SAYS[now] || \'\'}"' in lc
    assert "syncControls(); sayFor();" in lc
    assert ".lc.is-said .lc-says {" in COMPONENTS


def test_the_level_control_is_off_the_milo_bars_row():
    ov = (JS / "pages" / "dossier.js").read_text()
    assert "${frameTabs(sym, 'overview', { fund: isFund(D) })}${levelControl({ id: 'ov-lc' })}</div>" in ov, "on the tabs row"
    assert "${miloPrompt(stockAsk(sym))}${levelControl(" not in ov
    ws = (JS / "pages" / "workspace.js").read_text()
    assert '<div class="ws-dateline">' in ws and "${levelControl({ id: 'home-lc' })}</div></header>" in ws, "on the date line"


# ------------------------------------------------------------------ the chart's tools, in view at every level

def test_the_chart_tools_are_in_view_at_every_level_and_the_title_line_stays():
    """Hierarchy change 11 hid the drawing tools and the widget rail behind a Tools button below Advanced; it was
    reverted in the round-one corrections of 2026-11-10. The one title line from Chart read is not part of the revert."""
    ch = (JS / "pages" / "chart.js").read_text()
    assert "data-v2-ch-toolsopen" not in ch and "ch-toolsbtn" not in ch and "toolsOpen" not in ch, "no Tools button"
    assert "const drawOpen = () => !isPhone() || !!D.drawOpen || V.tool !== 'select';" in ch, "the rail is out on a wide screen"
    assert '<div class="ch-wrail" id="ch-wrail">' in ch and "railOpen" not in ch, "the widget rail is never hidden by the level"
    assert "prefs.level()" not in ch, "the chart page does not read the level"
    assert '<p class="ch-title" id="ch-title">${chartTitle()}</p>' in ch and "chartReadModel(D.t)" in ch
    assert ".ch-title { margin: 12px 0 8px;" in PAGES and "ch-toolsbtn" not in PAGES
