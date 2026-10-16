"""The Brokerage page's wiring in static/app.js, read as text.

CLAUDE.md: a new view needs registering in five places, and every silent
client failure here has been a wiring failure. This one also has to stay out
of the menu until the server says the feature is live.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "static" / "app.js").read_text()
WS = (ROOT / "static" / "brokerage.js").read_text()
HTML = (ROOT / "static" / "index.html").read_text()
CSS = (ROOT / "static" / "styles.css").read_text()


def test_registered_everywhere_a_view_has_to_be():
    assert 'id="view-brokerage"' in HTML
    assert "brokerage: $('#view-brokerage')" in APP
    assert "if (view === 'brokerage') return loadBrokerage(force);" in APP
    assert "{ view: 'brokerage', label: 'Brokerage', feature: 'brokerage'" in APP
    tickerless = APP.split("const TICKERLESS_VIEWS = [", 1)[1].split("];", 1)[0]
    assert "'brokerage'" in tickerless
    assert "brokerage: 'brokerage'" in APP.split("const ROUTE_SLUGS = {", 1)[1].split("};", 1)[0]


def test_not_in_the_menu_until_the_server_says_so():
    """Its own sidebar destination since 2026-10-15, but still hidden until the
    server says linking is open to this reader: the group carries a feature
    flag, the nav filters on it, and only the status probe turns it on."""
    groups = APP.split("const NAV_GROUPS = [", 1)[1].split("];", 1)[0]
    assert "{ id: 'brokerage', label: 'Brokerage', views: ['brokerage'], feature: 'brokerage' }" in groups
    visible = APP.split("function navVisibleGroups()", 1)[1].split("\n}", 1)[0]
    assert "navFeatureOn(g.feature)" in visible
    gate = APP.split("function navFeatureOn(feature)", 1)[1].split("\n}", 1)[0]
    assert "BROKER_ON" in gate and "return false;" in gate
    assert "let BROKER_ON = false;" in APP
    assert APP.count("BROKER_ON = true;") == 1, "only the probe's join may open it"
    probe = APP.split("async function brokerageProbe()", 1)[1][:500]
    assert "r.data.available" in probe and "brokerageNavJoin()" in probe and "BROKER_ON = false;" in probe
    assert "brokerageProbe();" in APP
    # Not a fourth tab under Positions any more: one version of the page.
    assert "{ id: 'portfolio', label: 'Positions', views: ['tracker', 'paper', 'roth'] }" in groups
    assert "group.views.push('brokerage')" not in APP


def test_every_control_has_a_handler():
    for attr in ("data-bk-connect", "data-bk-reconnect", "data-bk-sync", "data-bk-disconnect",
                 "data-bk-disarm", "data-bk-delete-all", "data-bk-reload", "data-bk-select", "data-bk-consent",
                 "data-billing-checkout", "data-billing-portal"):
        rendered = len(re.findall(attr + r'[=>\s"$]', APP))
        handled = APP.count("[{}]".format(attr))
        assert rendered and handled, attr


def test_disconnect_and_delete_are_two_step():
    handler = APP.split("async function brokerageAction(evt)", 1)[1].split("\nasync function", 1)[0]
    assert "if (!t.dataset.confirm) { BROKER.armed = id;" in handler
    assert "if (t.dataset.bkDeleteAll !== 'confirm') { BROKER.armed = 'all';" in handler


def test_missing_cost_basis_reads_not_supplied_never_zero():
    block = WS.split("function bkwHoldingsHTML(d)", 1)[1].split("\nfunction ", 1)[0]
    assert "h.cost_basis === null ? '<span class=\"bk-na\">Not supplied</span>'" in block


def test_classes_it_renders_have_rules():
    block = APP.split("/* ============================================================ BROKERAGE ===", 1)[1]
    block = block.split("const NAV_GROUPS = [", 1)[0] + WS
    used = set(re.findall(r'class="([^"$]*)"', block))
    names = {n for group in used for n in group.split() if n.startswith(("bk-", "bkw-"))}
    missing = sorted(n for n in names if "." + n not in CSS)
    assert not missing, missing


def test_no_em_dashes_in_the_copy():
    block = APP.split("/* ============================================================ BROKERAGE ===", 1)[1]
    block = block.split("const NAV_GROUPS = [", 1)[0]
    assert "—" not in block and "—" not in WS


# ------------------------------------------------------------- the workspace


def test_the_workspace_loads_after_app_and_is_handed_the_linked_page():
    assert HTML.index('src="app.js') < HTML.index('src="brokerage.js')
    render = APP.split("function renderBrokerage()", 1)[1].split("\n}", 1)[0]
    assert "conns.length && typeof bkWorkspaceRender === 'function'" in render
    assert "bkConnectionsHTML()" in WS, "the Connections tab reuses the one connections builder"


def test_every_section_is_an_address_the_router_knows():
    ids = re.findall(r"\{ id: '([a-z]+)', label: ", WS.split("const BKW_SECTIONS = [", 1)[1].split("];", 1)[0])
    assert ids == ["overview", "holdings", "performance", "events", "scenarios", "connections"]
    parse = APP.split("function parseRoute(hash)", 1)[1].split("\n}", 1)[0]
    assert "['overview', 'holdings', 'performance', 'events', 'scenarios', 'connections']" in parse
    route = APP.split("function routeFor(view)", 1)[1].split("\n}", 1)[0]
    assert "`#/brokerage/${sec}`" in route and "typeof BROKER !== 'undefined'" in route
    apply = APP.split("function applyRoute(hash)", 1)[1].split("\n}", 1)[0]
    assert "bkSetSection(route.section || null, true)" in apply


def test_every_workspace_control_has_a_handler():
    rendered = set(re.findall(r"data-bkw-([a-z-]+)", WS))
    for name in rendered:
        attr = "data-bkw-" + name
        camel = "bkw" + "".join(p.capitalize() for p in name.split("-"))
        handled = ("[{}]".format(attr) in WS or "[{}=".format(attr) in WS or "dataset.{}".format(camel) in WS)
        assert handled, attr
    assert "[data-bk-section]" in WS and 'data-bk-section="connections"' in APP


def test_the_workspace_has_no_trading_control():
    words = re.findall(r">([^<>{}$]{2,60})</button>", WS)
    for w in words:
        assert not re.search(r"\b(buy|sell|trade|order|transfer|withdraw|deposit)\b", w, re.I), w
    assert "Nothing is traded" in WS


def test_ask_milo_is_the_approved_button_with_milos_head():
    ask = WS.split("function bkwAskButton(text, label)", 1)[1].split("\n}", 1)[0]
    assert 'class="btn milo-btn bkw-ask"' in ask and "scout-badge-fig" in ask and "data-ask-text" in ask


def test_the_workspace_tells_milo_which_section_and_account():
    focus = APP.split("function chatFocus()", 1)[1].split("\n}", 1)[0]
    assert "bkViewLabel()" in focus
    assert "ctx.brokerage_scope = ids;" in APP
    assert "'optic.brokerage.scope.v1'" in APP.split("const PERSONAL_KEYS = [", 1)[1].split("];", 1)[0]


def test_paper_trades_no_longer_claim_optic_has_no_brokerage():
    assert "Optic has no brokerage connection.'" not in APP
