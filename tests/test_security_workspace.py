"""The security workspace: seven facets of one company, under one header.

Before this, everything about a single security was four unrelated top-level
pages that happened to share a symbol — and the Analysis page carried twenty-four
panels including, at the very bottom, the company's financials and its
headlines. The two most-asked questions about a stock were the hardest things on
the terminal to reach.

Nothing here is new data. Overview composes readings the /api/ticker payload
already carries, Financials and News are the same renderers moved to the facet a
reader would look for them on, and /api/news/{ticker} was a working endpoint with
no caller at all.

Read as text, per this repo's convention: every client failure here has been a
wiring failure, and the five-place registration is the wiring most likely to be
half-done.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
APP_JS = (ROOT / "static" / "app.js").read_text()
INDEX = (ROOT / "static" / "index.html").read_text()
STYLES = (ROOT / "static" / "styles.css").read_text()

FACETS = ["overview", "chart", "swing", "earnings", "financials", "news", "long"]
NEW_VIEWS = ["overview", "financials", "news"]


def _facet_list() -> list:
    block = APP_JS.split("const SECURITY_VIEWS = [", 1)[1].split("];", 1)[0]
    return re.findall(r"'(\w+)'", block)


# ------------------------------------------------- the five-place registration

def test_the_facet_list_is_what_it_says():
    assert _facet_list() == FACETS


def test_every_new_view_has_a_section():
    for v in NEW_VIEWS:
        assert f'id="view-{v}"' in INDEX, f"no <section> for {v}"


def test_every_new_view_is_in_the_views_map():
    block = APP_JS.split("const views = {", 1)[1].split("\n};", 1)[0]
    for v in NEW_VIEWS:
        assert re.search(rf"\b{v}: \$\('#view-{v}'\)", block), f"{v} missing from views"


def test_the_nav_group_reuses_the_facet_list_rather_than_repeating_it():
    """Two hand-maintained copies of the same seven names would drift, and the
    symptom is a tab in the strip that the nav menu cannot reach."""
    assert "{ id: 'security', label: 'Security', views: SECURITY_VIEWS }" in APP_JS


def test_every_new_view_reaches_a_loader():
    block = APP_JS.split("function loadView(view, force) {", 1)[1].split("\nfunction ", 1)[0]
    for v in NEW_VIEWS:
        assert f"'{v}'" in block, f"loadView never dispatches {v}"
    assert "loadSecurityFacet(view, force)" in block


def test_every_new_view_is_in_the_command_palette():
    block = APP_JS.split("const PALETTE_PLACES = [", 1)[1].split("\n];", 1)[0]
    for v in NEW_VIEWS:
        assert f"view: '{v}'" in block, f"{v} is unreachable from the command bar"


def test_the_no_ticker_guard_lists_the_new_views():
    """The allow-list-by-omission trap, which has now caught Watchlist, Alerts,
    Explore and would have caught all three of these. These facets ARE about a
    loaded symbol, but they render their own picker under the workspace header
    so the reader keeps the tab strip instead of hitting a bare dead end."""
    block = APP_JS.split("function loadView(view, force) {", 1)[1].split("&& !STATE.ticker", 1)[0]
    for v in NEW_VIEWS:
        assert f"'{v}'" in block, f"{v} will render 'No ticker loaded' instead of itself"


def test_every_facet_has_a_label_and_a_title():
    labels = APP_JS.split("const SUB_LABELS = {", 1)[1].split("\n};", 1)[0]
    titles = APP_JS.split("const SUB_TITLES = {", 1)[1].split("\n};", 1)[0]
    # Not anchored to the line start: these maps pack several keys onto one
    # line, so `chart:` is the second entry on its own. An earlier version of
    # this test failed for that reason rather than for a missing label.
    for v in FACETS:
        assert re.search(rf"(^|[{{\s]){v}:", labels, re.M), f"{v} has no tab label"
        assert re.search(rf"(^|[{{\s]){v}:", titles, re.M), f"{v} has no tooltip"


# ---------------------------------------------------------------- the header

def test_the_header_renders_on_every_facet():
    """Six write their own markup and one is the chart. Missing it on any of
    them is how the workspace stops reading as one workspace."""
    for call in ("securityHeader('swing')", "securityHeader('earnings')",
                 "securityHeader('long')", "securityHeader('overview')",
                 "securityHeader('financials')", "securityHeader('news')"):
        assert call in APP_JS, f"missing {call}"
    assert "securityHeader('chart', { symbol: STATE.chartSymbol, compact: true })" in APP_JS, \
        "Charting has no strip, so entering it is a one-way door out of the workspace"


def test_the_chart_facet_falls_back_to_the_loaded_security():
    """Charting keeps its own symbol deliberately, but "nothing charted yet" is
    not a choice. Reaching Chart from the nav menu with a symbol loaded landed
    on the empty ticker prompt, which inside a workspace reads as a broken tab."""
    block = APP_JS.split("function loadView(view, force) {", 1)[1].split("\nfunction ", 1)[0]
    assert "loadChartWorkspace(STATE.chartSymbol || STATE.ticker, force)" in block


def test_the_chart_facet_names_the_symbol_it_is_actually_showing():
    """STATE.chartSymbol is deliberately independent of STATE.ticker. A strip on
    Charting that read STATE.ticker would name one company over another's
    candles — the exact bug that independence exists to prevent."""
    body = APP_JS.split("function securityHeader(", 1)[1].split("\nfunction ", 1)[0]
    assert "opts.symbol !== undefined ? opts.symbol : STATE.ticker" in body


def test_the_price_is_only_shown_when_it_belongs_to_that_symbol():
    """STATE.swing holds the loaded ticker's quote. Printing it beside a
    different charted symbol would be a wrong number, not a missing one."""
    body = APP_JS.split("function securityHeader(", 1)[1].split("\nfunction ", 1)[0]
    assert "sym === STATE.ticker ? ((STATE.swing || {}).quote) : null" in body


def test_compare_is_not_a_facet():
    """It is about two to four securities, so a header naming one is a lie."""
    assert "compare" not in _facet_list()


# ------------------------------------------------------------- the wiring

def test_the_strip_has_a_handler():
    """Every control needs a handler. These buttons live inside the views, not
    inside nav.tabs, so the scoped `nav.tabs [data-view]` rule cannot see them —
    they would render perfectly and take clicks that do nothing."""
    assert "closest('[data-sec-view]')" in APP_JS
    assert 'data-sec-view="${esc(v)}"' in APP_JS


def test_leaving_the_chart_facet_carries_its_symbol_with_it():
    """Clicking Financials under TSLA candles means TSLA, not whatever was last
    analysed."""
    block = APP_JS.split("closest('[data-sec-view]')", 1)[1][:700]
    assert "loadTicker(sym, to)" in block
    assert "SECURITY_OWN_SYMBOL.has(to)" in block
    assert "loadChartWorkspace(sym)" in block


def test_opening_a_symbol_lands_on_the_workspace_front_door():
    block = APP_JS.split("function loadTicker(", 1)[1].split("\nfunction ", 1)[0]
    assert "STATE.view === 'home' ? 'overview' : STATE.view" in block


# ------------------------------------------- nothing was duplicated, only moved

def test_the_company_and_news_panels_left_the_analysis_page():
    """The point of a workspace is that each thing has one home. Rendering these
    on Analysis as well would be two copies to keep in step."""
    body = APP_JS.split("function renderSwing(d) {", 1)[1].split("\nfunction ", 1)[0]
    assert "renderCompany(" not in body, "the company panel is still on Analysis"
    assert "News & catalysts" not in body, "the news panel is still on Analysis"


def test_the_facets_render_them_instead():
    fin = APP_JS.split("function renderFinancialsView(", 1)[1].split("\nfunction ", 1)[0]
    assert "renderCompany(co)" in fin and "renderExtras(" in fin
    news = APP_JS.split("function renderNewsView(", 1)[1].split("\nfunction ", 1)[0]
    assert "News & catalysts" in news and "newsArticleRow" in news


def test_the_facets_share_one_request():
    """/api/ticker carries quote, company and news together. A per-facet fetch
    would make every tab a two-second wait for a payload already in memory."""
    body = APP_JS.split("async function loadSecurityFacet(", 1)[1].split("\nfunction ", 1)[0]
    assert "STATE.swing && STATE.swing.ticker === STATE.ticker" in body, \
        "the freshness test must match loadSwing's own guard, not a second field"
    assert "loadSwing(force, { silent: true })" in body
    assert "if (STATE.view !== view) return;" in body, \
        "no guard against the reader switching tabs mid-load"


# ------------------------------------------------------------------- overview

def test_every_overview_card_navigates():
    body = APP_JS.split("function overviewCard(", 1)[1].split("\nfunction ", 1)[0]
    assert "data-sec-view=" in body and "data-sec-sym=" in body


def test_a_missing_reading_is_said_in_words():
    """An empty card reads as a rendering fault. The facet is not absent because
    today's number is."""
    body = APP_JS.split("function overviewCard(", 1)[1].split("\nfunction ", 1)[0]
    assert "'not available'" in body
    assert re.search(r"^\.ov-card-val\.none\s*\{", STYLES, re.M)


def test_conviction_reads_as_english():
    """The backend's vocabulary includes the literal string "none", and three
    call sites interpolated it into "${conviction} conviction". A neutral stance
    rendered "none conviction" on the hero and again on the card below it."""
    assert "function convictionWords(" in APP_JS
    body = APP_JS.split("function convictionWords(", 1)[1].split("\nfunction ", 1)[0]
    assert "'no conviction'" in body
    assert not re.search(r"\$\{(?:p|ep|pulse)\.conviction\} conviction", APP_JS), \
        "a call site still interpolates conviction raw"


# --------------------------------------------------------------------- styling

def test_the_sticky_header_clears_the_top_bar():
    """header.topbar is sticky at z-index 50, so a header sticking at top: 0 is
    painted underneath it and looks like it never stuck at all. The bar is one
    row on a laptop and three at 645px — 83px against 197px, measured — so the
    offset cannot be a constant."""
    assert "syncTopbarOffset" in APP_JS
    assert "'--topbar-h'" in APP_JS
    assert "ResizeObserver" in APP_JS.split("function syncTopbarOffset", 1)[1][:700]
    rule = STYLES.split(".sec-head {", 1)[1].split("}", 1)[0]
    assert "var(--topbar-h" in rule


@pytest.mark.parametrize("cls", [".sec-head", ".sec-tabs", ".sec-tab", ".sec-sym",
                                 ".ov-cards", ".ov-card", ".nw-row", ".nw-title"])
def test_the_workspace_classes_are_styled(cls):
    """Markup with no rule renders at body size in the middle of a layout. This
    repo has shipped that twice."""
    assert re.search(re.escape(cls) + r"[\s,{:]", STYLES), f"{cls} has no rule"

