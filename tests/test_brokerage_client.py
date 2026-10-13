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
    groups = APP.split("const NAV_GROUPS = [", 1)[1].split("];", 1)[0]
    assert "'brokerage'" not in groups, "joins at runtime via brokerageNavJoin, never statically"
    probe = APP.split("async function brokerageProbe()", 1)[1][:300]
    assert "r.data.available" in probe and "brokerageNavJoin()" in probe
    assert "brokerageProbe();" in APP


def test_every_control_has_a_handler():
    for attr in ("data-bk-connect", "data-bk-reconnect", "data-bk-sync", "data-bk-disconnect",
                 "data-bk-disarm", "data-bk-delete-all", "data-bk-reload", "data-bk-select",
                 "data-billing-checkout", "data-billing-portal"):
        rendered = len(re.findall(attr + r'[=>\s"]', APP))
        handled = APP.count("[{}]".format(attr))
        assert rendered and handled, attr


def test_disconnect_and_delete_are_two_step():
    handler = APP.split("async function brokerageAction(evt)", 1)[1].split("\nasync function", 1)[0]
    assert "if (!t.dataset.confirm) { BROKER.armed = id;" in handler
    assert "if (t.dataset.bkDeleteAll !== 'confirm') { BROKER.armed = 'all';" in handler


def test_missing_cost_basis_reads_not_supplied_never_zero():
    block = APP.split("function bkPortfolioHtml(p, conns)", 1)[1].split("\nfunction ", 1)[0]
    assert "h.cost_basis === null ? '<span class=\"bk-na\">Not supplied</span>'" in block


def test_classes_it_renders_have_rules():
    block = APP.split("/* ============================================================ BROKERAGE ===", 1)[1]
    block = block.split("const NAV_GROUPS = [", 1)[0]
    used = set(re.findall(r'class="([^"$]*)"', block))
    names = {n for group in used for n in group.split() if n.startswith("bk-")}
    missing = sorted(n for n in names if "." + n not in CSS)
    assert not missing, missing


def test_no_em_dashes_in_the_copy():
    block = APP.split("/* ============================================================ BROKERAGE ===", 1)[1]
    block = block.split("const NAV_GROUPS = [", 1)[0]
    assert "—" not in block


def test_paper_trades_no_longer_claim_optic_has_no_brokerage():
    assert "Optic has no brokerage connection.'" not in APP
