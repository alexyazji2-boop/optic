"""Classic parity, batch B4a (2026-10-21): Milo docked beside the page, its context and the panel's figures, and the
suggestions as quiet buttons. The docking rule and the example run in JavaScriptCore; the rest are source checks. The
interactions were driven in headless Chrome at 1440, 1200, 1316, 1160 and 390 (~/Optic/work/classic-parity/
b4a_check.py and b4a_widths.py, the stand-in model, touch emulated) and in Mobile Safari on the iOS simulator. These
tests are not interaction evidence. Ledger: docs/frontend-v2/CLASSIC-PARITY.md, B4a.
"""
from tests.test_frontend_v2_stage0 import V2, _run

JS = V2 / "js"
MILO = (JS / "ui/milo.js").read_text()
DRAWER = (JS / "ui/drawer.js").read_text()
CSS = (V2 / "css/components.css").read_text()
PAGES = (V2 / "css/pages.css").read_text()


def test_milo_docks_only_where_the_page_keeps_its_usable_width(tmp_path):
    got = _run(tmp_path, f"""
      globalThis.localStorage = {{ getItem: () => null, setItem: () => {{}}, removeItem: () => {{}} }};
      const M = await import('{(JS / "ui/milo.js").as_posix()}');
      print(JSON.stringify({{ min: M.CONTENT_MIN,
        wide: M.dockFit(1920, 236, 560), lap: M.dockFit(1440, 236, 560), edge: M.dockFit(1316, 236, 560), under: M.dockFit(1315, 236, 560),
        tight: M.dockFit(1160, 76, 560), chosen: M.dockFit(1920, 236, 400), phone: M.dockFit(1440, 0, 560, true) }}));
    """)
    assert got["min"] == 760
    assert got["wide"] == 560, "room for the width the reader chose"
    assert got["lap"] == 444, "a 1440 laptop: Milo narrows so the page keeps 760"
    assert got["edge"] == 320 and got["under"] == 0, "never narrower than Milo's own minimum; below it, over the page"
    assert got["tight"] == 324, "a folded rail leaves more room"
    assert got["chosen"] == 400 and got["phone"] == 0


def test_the_example_question_is_classics_and_tab_stays_tab(tmp_path):
    got = _run(tmp_path, f"""
      globalThis.localStorage = {{ getItem: () => null, setItem: () => {{}}, removeItem: () => {{}} }};
      const M = await import('{(JS / "ui/milo.js").as_posix()}');
      print(JSON.stringify({{ sym: M.exampleAsk({{ view: 'overview', symbol: 'AAPL' }}, 'auto'), bk: M.exampleAsk({{ view: 'brokerage' }}, 'auto'),
        wl: M.exampleAsk({{ view: 'watchlist' }}, 'auto'), scan: M.exampleAsk({{ view: 'scan' }}, 'auto'), none: M.exampleAsk({{ view: 'overview', symbol: 'AAPL' }}, 'none'), n: M.OPTIONS_FOLLOWUPS.length }}));
    """)
    assert got == {"sym": "What would change the picture for AAPL?", "bk": "Where am I concentrated?", "wl": "What changed this week?",
                   "scan": "What do they have in common?", "none": "What is moving the market today?", "n": 6}
    classic = (V2.parent / "app.js").read_text()
    for q in ("What would change the picture for ${sub.sym}?", "Where am I concentrated?", "What changed this week?", "What do they have in common?"):
        assert q in classic, q
    assert "'Tab'" not in MILO.split("function wire(root)")[1].split("function pickPersona")[0].replace("else if (e.key === 'Tab') setMenu(false);", ""), "no Tab-to-accept"
    assert 'data-v2-milo-follow="${eg}">Use this example</button>' in MILO
    assert 'class="btn btn-quiet btn-sm" data-v2-milo-follow="${q}"' in MILO, "follow-ups are quiet buttons, not chips"


def test_docked_milo_is_not_a_dialog_and_stays_across_pages():
    assert "export function makeDrawer(" in DRAWER and "const main = makeDrawer();" in DRAWER
    assert "panel.setAttribute('role', 'complementary'); panel.removeAttribute('aria-modal');" in DRAWER, "no trap, no aria-modal"
    assert "if ((sticky || docked) && route && !force) return;" in DRAWER
    assert "const drawer = makeDrawer({ cls: 'drawer-milo', titleId: 'milo-title' });" in MILO, "its own drawer and title id"
    assert "if (drawer.isOpen() && !drawer.isDocked()) drawer.close({ silent: true });" in MILO, "over the page, it closes with the page"
    assert ".drawer.drawer-milo { z-index: 59; }" in CSS and "html.milo-docked .stage { margin-right: var(--milo-dock-w, 0px); }" in CSS
    assert ".drawer.is-docked .drawer-scrim { display: none; }" in CSS


def test_the_page_lays_out_against_the_width_it_has():
    for rule in ("html.eff-1240 .wl-rows {", "html.eff-1100 .wl-rows {", "html.eff-1100 .vs-cases", "html.eff-1100 .ws-panel {", "html.eff-1100 .dhead.bar { flex-wrap: wrap; }"):
        assert rule in PAGES, rule
    for rule in ("html.eff-1100 .row-head, html.eff-1100 .row {", "html.eff-1100 .answers {", "html.eff-1100 .session-chip .sc-next"):
        assert rule in CSS, rule
    assert "@media (max-width: 1100px) { .wl-rows { --wl: minmax(90px, 1fr) 92px 88px minmax(120px, 1.6fr) 88px; }" in PAGES, "and a 1024 window"
    assert ".menu-body.menu-end { left: auto; right: 0; }" in PAGES and ".menu-body, .menu-body.menu-end { position: fixed;" in PAGES


def test_a_panels_ask_carries_its_figures():
    assert "export function panelFigures(el)" in MILO and "figures: panelFigures(b)" in (JS / "app.js").read_text()
    assert "const panel = scope === 'auto' && asked && asked.panel ? asked.panel : null;" in MILO
    assert "return panel && !S.dropped.has('panel') ? { ...ctx, panel, focus } : { ...ctx, focus };" in MILO, "removable like any attached part"
    assert "!n.closest('details:not([open]) > :not(summary)')" in MILO, "only what is on screen"
