"""The global shell: the address bar, the one Cmd+K, and the market's phase.

Optic had no URL: every page lived at `/`, so Back left the app, a reload
landed on Home with the symbol gone, and nothing could be linked. Measured
2026-10-06, the history stack held one entry however many pages had been
visited. The page and the symbol are in the hash now, and these tests hold the
vocabulary of it: which hashes open which page, and which are not routes at
all (an in-page anchor must never be read as a ticker).

Checked in a browser at 1440x900: `#/MSFT/options` on a cold load opened MSFT
on Options; Overview, Read and Macro then Back three times walked
Macro > Read > MSFT > MSFT Options; a search for AAPL then Back returned to
MSFT; Home wrote a bare `/`.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
APP = (ROOT / "static/app.js").read_text()
CSS = (ROOT / "static/styles.css").read_text()
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc"


def _fn(head):
    at = APP.index(head)
    return APP[at:APP.index("\n}\n", at) + 3]


def _const(name):
    at = APP.index(f"const {name} = ")
    end = APP.index(";\n", at) + 2
    return APP[at:end]


def _run(script):
    exe = JSC if os.path.exists(JSC) else shutil.which("jsc")
    if not exe:
        pytest.skip("no JavaScriptCore on this machine")
    prelude = """
      var STATE = { view: 'home', ticker: null, chartSymbol: '' };
      const SECURITY_VIEWS = ['overview', 'chart', 'swing', 'long', 'earnings',
        'financials', 'news'];
    """ + _const("ROUTE_SLUGS") + _const("ROUTE_VIEWS") + _const("ROUTE_SYMBOL_RE") \
        + _fn("function routeFor(view) {") + _fn("function parseRoute(hash) {")
    out = subprocess.run([exe, "-e", prelude + script], capture_output=True, text=True,
                         timeout=60, cwd=str(ROOT))
    assert "RESULT:" in out.stdout, (out.stdout + out.stderr)[-2000:]
    return json.loads(out.stdout.split("RESULT:", 1)[1].split("\n")[0])


def test_hashes_name_pages_and_symbols():
    out = _run("""
      var hashes = ['', '#', '#/', '#/read', '#/macro', '#/scan', '#/SCAN', '#/nvda',
        '#/NVDA/options', '#/BRK-B/news', '#/%5EGSPC/chart', '#/instrument/%5EVIX',
        '#/MSFT/investing/'];
      print('RESULT:' + JSON.stringify(hashes.map(parseRoute)));
    """)
    assert out == [
        {"view": "home", "symbol": None},
        {"view": "home", "symbol": None},
        {"view": "home", "symbol": None},
        {"view": "brief", "symbol": None},
        {"view": "market", "symbol": None},
        {"view": "scan", "symbol": None},
        # Upper case is a ticker, lower case is the page.
        {"view": "overview", "symbol": "SCAN"},
        {"view": "overview", "symbol": "NVDA"},
        {"view": "swing", "symbol": "NVDA"},
        {"view": "news", "symbol": "BRK-B"},
        {"view": "chart", "symbol": "^GSPC"},
        {"view": "instrument", "symbol": "^VIX"},
        {"view": "long", "symbol": "MSFT"},
    ]


def test_what_is_not_a_route_opens_nothing():
    """`#read-desk-markets` is the Read's own desk index. Read as a route it
    would have loaded a ticker called READ-DESK-MARKETS."""
    out = _run("""
      print('RESULT:' + JSON.stringify(['#read-desk-markets', '#/NVDA/nonsense',
        '#/<script>', '#/AAAAAAAAAAAAAAAAAAAA'].map(parseRoute)));
    """)
    assert out == [None, None, None, None]


def test_each_page_writes_the_hash_that_reopens_it():
    out = _run("""
      var rows = [];
      function at(view, ticker, chart) {
        STATE.view = view; STATE.ticker = ticker; STATE.chartSymbol = chart || '';
        var h = routeFor(view); var back = h === null ? null : parseRoute(h || '');
        rows.push([view, h, back && back.view, back && back.symbol]);
      }
      at('home', 'NVDA'); at('overview', 'NVDA'); at('swing', 'NVDA');
      at('chart', 'NVDA', 'AMD'); at('chart', null, ''); at('earnings', null);
      at('brief', 'NVDA'); at('settings', null); at('overview', '^GSPC');
      print('RESULT:' + JSON.stringify(rows));
    """)
    assert out == [
        ["home", "", "home", None],
        ["overview", "#/NVDA", "overview", "NVDA"],
        ["swing", "#/NVDA/options", "swing", "NVDA"],
        # The chart writes its own symbol, which can differ from the Dossier's.
        ["chart", "#/AMD/chart", "chart", "AMD"],
        ["chart", "#/chart", "chart", None],
        # The week's earnings calendar, with nothing loaded.
        ["earnings", "#/earnings", "earnings", None],
        # A market-wide page does not carry the loaded symbol.
        ["brief", "#/read", "brief", None],
        ["settings", "#/settings", "settings", None],
        ["overview", "#/^GSPC", "overview", "^GSPC"],
    ]


def test_every_routed_page_is_a_view_and_every_reader_page_has_a_route():
    views = set(re.findall(r"^  (\w+): \$\('#view-", APP.split("const views = {", 1)[1]
                           .split("};", 1)[0], flags=re.M))
    views |= set(re.findall(r"(\w+): \$\('#view-[\w-]+'\)", APP.split("const views = {", 1)[1]
                            .split("};", 1)[0]))
    slugs = dict(re.findall(r"(\w+): '([\w-]+)'", _const("ROUTE_SLUGS")))
    assert set(slugs) <= views
    # Home has no slug (it is `/`) and the instrument chart is routed by symbol.
    assert views - set(slugs) == {"home", "instrument"}
    assert len(set(slugs.values())) == len(slugs), "two pages share a slug"


def test_switching_records_the_page_and_a_route_being_applied_does_not():
    sv = _fn("function switchView(view, force) {")
    assert sv.rstrip().endswith("routeRecord();\n}")
    rec = _fn("function routeRecord() {")
    assert "if (routeApplying" in rec
    apply = _fn("function applyRoute(hash) {")
    assert "routeApplying = true;" in apply and "routeApplying = false;" in apply
    assert "finally" in apply, "a throwing view must not leave recording switched off"
    assert "window.addEventListener('popstate', () => applyRoute(location.hash));" in APP
    # A reload, a shared link, or Back into the app from another site.
    assert "applyRoute(location.hash);" in _fn("function restoreReloadPlace() {")


def test_in_page_anchors_scroll_without_taking_the_address_bar():
    block = APP.split("/* In-page anchors scroll; they do not take the address bar.", 1)[1]
    block = block[:block.index("\n});") + 4]
    assert "href.startsWith('#/')" in block
    assert "evt.preventDefault();" in block and "scrollIntoView" in block


def test_cmd_k_is_the_palette_alone():
    """A second handler opened Pulse on the same keystroke, behind the
    palette, and left it open when the palette closed."""
    code = re.sub(r"/\*.*?\*/", "", APP, flags=re.S)
    binds = re.findall(r"\(evt\.metaKey \|\| evt\.ctrlKey\) && (?:evt\.)?key === 'k'", code)
    assert len(binds) == 1, binds
    assert "openPalette(seed);" in code


def test_escape_closes_pulse_from_inside_it_after_its_own_pickers():
    block = APP.split("$('#chat').addEventListener('keydown', (evt) => {", 1)[1]
    block = block[:block.index("\n});")]
    assert "evt.key !== 'Escape' || paletteOpen || kmOpen || ppOpen" in block
    assert "classList.remove('chat-open')" in block
    assert "$('#chat-toggle').focus();" in block


def test_a_new_symbol_keeps_the_market_phase():
    """`STATE.session = null` sent the strip to the client clock, which calls
    the overnight session "closed", for as long as the new symbol took."""
    fn = _fn("function loadTicker(raw, destination) {")
    code = re.sub(r"/\*.*?\*/", "", fn, flags=re.S)
    assert "STATE.session = null;" not in code
    assert "{ session: STATE.session.session }" in code
    load = _fn("async function loadSession(force) {")
    assert "if (asked !== STATE.ticker) return;" in load
    assert "const firstLoad = !STATE.session || !STATE.session.ticker;" in load


def test_home_keeps_its_status_row_for_a_warning():
    fn = _fn("function updateStatus() {")
    home = fn.split("if (STATE.view === 'home') {", 1)[1].split("return;", 1)[0]
    assert "Search a ticker or company name to begin." not in home
    assert "Pick a tab above" not in home
    assert 'class="chip warn"' in home
    assert "host.hidden = !parts.length;" in _fn("function setStatus(parts) {")
    assert ".statusline[hidden] { display: none; }" in CSS


def test_the_phone_bar_wears_the_rails_icons():
    tabs = APP.split("const MOBILE_TABS = [", 1)[1].split("\n];", 1)[0]
    navs = re.findall(r"nav: '(\w+)'", tabs)
    assert navs == ["home", "security", "market", "discover", "more"]
    icons = APP.split("const NAV_ICONS = {", 1)[1].split("\n};", 1)[0]
    for key in navs:
        assert re.search(rf"^\s+{key}: '", icons, flags=re.M), key
    assert "&#9683;" not in tabs, "the half-moon glyph"
    assert "${navIcon(t.nav)}" in _fn("function mountMobileTabs() {")


def test_a_tablet_opens_on_the_collapsed_rail_until_the_reader_chooses():
    """At 768px the expanded rail left 556px of page, measured 2026-10-07. The
    old key was written on every load, so it says nothing about a choice."""
    assert "const RAIL_AUTO_QUERY = '(min-width: 560px) and (max-width: 1023px)';" in APP
    init = _fn("function initRail() {")
    assert "applyRail(chosen === null ? railDefault() : chosen);" in init
    assert "localStorage.setItem(RAIL_CHOICE_KEY" in init, "the button records the choice"
    assert "mq.addEventListener('change', follow)" in init
    choice = _fn("function railChoice() {")
    assert "localStorage.getItem(RAIL_KEY) === '1'" in choice, "an old collapse was a choice"


def test_the_phone_search_hint_fits():
    assert "const PHONE_SEARCH_HINT = 'Ticker or company';" in APP


def test_the_first_tab_stop_skips_the_chrome():
    html = (ROOT / "static/index.html").read_text()
    body = html[html.index("<body"):]
    assert body.index('class="skip-link"') < body.index('<div class="app">')
    assert '<main id="main" tabindex="-1">' in html
    click = APP.split("const skip = evt.target && evt.target.closest && evt.target.closest('[data-skip-main]');", 1)[1]
    click = click[:click.index("\n});")]
    assert "views[STATE.view]" in click and "evt.preventDefault();" in click, "the route stays in the hash"
    assert ".skip-link:focus" in CSS


def test_home_is_dated_and_does_not_say_the_session_twice():
    home = APP[APP.index("async function loadHomeMarket(opts = {}) {"):]
    home = home[:home.index("\n}\n")]
    assert "hm-session" not in home
    assert 'class="hm-date">${esc(homeDateLine(session))}' in home
