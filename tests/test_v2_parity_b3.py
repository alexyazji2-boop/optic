"""Classic parity, batch B3 (2026-10-21): long-page navigation (ui/sections.js) and sideways strips (ui/strips.js).
The identity, level and current-section rules run in JavaScriptCore, and the saved-data formats are checked against
Classic's; the rest are source checks. The interactions were driven in headless Chrome at 1440, 390 and 360
(~/Optic/work/classic-parity/b3_check.py, touch emulated). These tests are not interaction evidence. Ledger:
docs/frontend-v2/CLASSIC-PARITY.md, B3.
"""
from tests.test_frontend_v2_stage0 import V2, _run

JS = V2 / "js"
SEC = (JS / "ui/sections.js").read_text()
STR = (JS / "ui/strips.js").read_text()
CSS = (V2 / "css/components.css").read_text()
CLASSIC = (V2.parent / "app.js").read_text()


def test_a_sections_identity_and_its_default_are_classics(tmp_path):
    got = _run(tmp_path, f"""
      globalThis.localStorage = {{ getItem: () => null, setItem: () => {{}} }};
      const S = await import('{(JS / "ui/sections.js").as_posix()}');
      const lv = {{ 'the multiple against its own history': 2, 'valuation and accumulation levels': 2 }};
      print(JSON.stringify({{
        id: S.panelId('long', '  The Multiple  against its own   history '), long: S.panelId('x', 'a'.repeat(60)).length,
        adv: S.levelOf(lv, 'The multiple against its own history'), plain: S.levelOf(lv, 'Return and risk'),
        lit: S.startsOpen({{}}, 'long|x', 2, 1), adv2: S.startsOpen({{}}, 'long|x', 2, 2), chose: S.startsOpen({{ 'long|x': true }}, 'long|x', 3, 0), shut: S.startsOpen({{ 'long|x': false }}, 'long|x', 0, 3),
        cur: [S.currentOf([-900, -200, 150, 700], 200), S.currentOf([300, 900], 200), S.currentOf([-50, 211], 200)] }}));
    """)
    assert got["id"] == "long|the multiple against its own history", "Classic's panelId: view, lower case, spaces collapsed"
    assert got["long"] == 2 + 48, "48 characters of heading, as Classic keeps"
    assert got["adv"] == 2 and got["plain"] == 0
    assert got["lit"] is False and got["adv2"] is True, "a section above the reader's rung starts folded"
    assert got["chose"] is True and got["shut"] is False, "what the reader chose wins over the default either way"
    assert got["cur"] == [2, 0, 1], "the last section whose top has reached the sticky stack; the first before any has"


def test_strips_show_arrows_only_while_there_is_more(tmp_path):
    got = _run(tmp_path, f"""
      const S = await import('{(JS / "ui/strips.js").as_posix()}');
      print(JSON.stringify({{ fits: S.moreWays(0, 300, 300), start: S.moreWays(0, 300, 900), mid: S.moreWays(200, 300, 900), end: S.moreWays(600, 300, 900) }}));
    """)
    assert got == {"fits": {"start": False, "end": False}, "start": {"start": False, "end": True}, "mid": {"start": True, "end": True}, "end": {"start": True, "end": False}}


def test_the_saved_data_is_classics_keys_and_shapes():
    assert "const OPEN_KEY = 'optic.panels.open', HIDDEN_KEY = 'optic.panels.hidden.v1';" in SEC
    assert "const COLLAPSE_KEY = 'optic.panels.open';" in CLASSIC and "const PANEL_HIDDEN_KEY = 'optic.panels.hidden.v1';" in CLASSIC
    # Classic stores {id: bool} for folds and {id: true}, deleting on show, for hidden; v2 writes the same
    assert "all[id] = open;" in SEC and "if (on) delete all[id]; else all[id] = true;" in SEC
    assert "return view + '|' + title.toLowerCase().replace(/\\s+/g, ' ').trim().slice(0, 48);" in CLASSIC
    assert "`${view}|${String(title).toLowerCase().replace(/\\s+/g, ' ').trim().slice(0, 48)}`" in SEC
    # the page names are Classic's, so a choice made there holds here
    pages = {"dossier.js": "sections(main, 'overview'", "investing.js": "sections(main, 'long'", "earnings.js": "sections(main, 'earnings'",
             "financials.js": "sections(main, 'financials'", "options.js": "sections(h, 'swing'"}
    for page, needle in pages.items():
        assert needle in (JS / "pages" / page).read_text(), page


def test_refreshing_never_resets_what_the_reader_folded_hid_or_jumped_to():
    assert "conf.mo = new MutationObserver(" in SEC and "apply(root); measure(root);" in SEC, "applied again after every redraw"
    assert "onPrefs((what) => { if (what === 'knowledge'" in SEC, "the level set elsewhere in this tab"
    assert "const open = nav ? !!nav.querySelector('details.sec-panels[open]') : false;" in SEC, "an open Panels menu stays open"


def test_the_strip_and_folds_follow_the_design_standard():
    assert "@media (min-width: 641px) and (min-height: 561px) { .sec-index:not(.sec-only-bulk) { position: sticky;" in CSS, "sticky only where B1's header is"
    assert "var(--secidx-h, 0px)" in CSS.split("html { scroll-padding-top:")[1].split("}")[0], "jumps land below the strip"
    assert ".sec-chip[aria-current=\"location\"] { color: var(--c-ink); border-bottom-color: var(--c-gold); }" in CSS, "lit as the tabs are"
    assert "@media (pointer: coarse) { .sec-fold { width: var(--tap); height: var(--tap);" in CSS
    # no fades: an edge arrow instead (the gradient budget is the rail's divider and the shimmer)
    assert "gradient(" not in STR and "gradient(" not in SEC and "mask-image" not in CSS.split("long pages (ui/sections.js")[1]
    assert ".strip-edge.strip-start { left: calc(0px - var(--strip-pl, 0px));" in CSS
    # the wheel takes the strip only while it can move that way, for a gesture that began on it
    assert "if (next === el.scrollLeft) return;   // at the end that way: the page's" in STR
    assert "if (!el || !fresh || e.ctrlKey || Math.abs(e.deltaX) > Math.abs(e.deltaY)) return;" in STR
    assert "if (d.moved) {" in STR and "ev.preventDefault(); ev.stopPropagation();" in STR, "a drag that ends on an item does not click it"
    assert "startStrips();" in (JS / "app.js").read_text()


def test_the_shell_measures_the_page_header_where_it_is():
    shell = (JS / "ui/shell.js").read_text()
    assert "main.querySelector(':scope > .page-view > .dstick')" in shell and "{ childList: true, subtree: true }" in shell


def test_insider_tables_are_capped_with_their_header_in_view():
    assert "#fin-ownership .tscroll, #fin-congress .tscroll, .ins-page .tscroll { max-height: min(62vh, 560px); overflow: auto; }" in CSS
    assert "position: sticky; top: 0; z-index: 1; background: var(--c-raised);" in CSS
    assert "mainEl.classList.add('ins-page');" in (JS / "pages/insiders.js").read_text()
