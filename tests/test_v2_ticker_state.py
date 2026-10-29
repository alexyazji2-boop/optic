"""Which symbol a page shows when the reader has not named one, and how typed text becomes a page (Phase 03).

Post-demo overhaul, directive 03 (search, ticker state, SPY default, "Follows <ticker>" removed). The precedence,
everywhere a page needs a symbol (core/store.js DEFAULT_SYMBOL): the address's symbol; the company opened on this
visit (the palette and the Dossier link); the reader's saved choice where a page keeps one (Home's linked panels);
then SPY. Never the Recent list or the watchlist on their own, which made Home quietly follow whatever was opened
last ("Follows INTC" at the investor demo, BUG-003).

The JavaScript runs in JavaScriptCore against the modules themselves; the interactions (20 sequential and 10 rapid
ticker changes, invalid symbols, refresh and history, keyboard only, a slow and a failing search provider) were run
in headless Chrome by ~/Optic/work/post-demo-ultra-2026-10-29/tools/phase03_scenarios.py (TEST_RESULTS, Phase 03).
"""
import json

from tests.test_frontend_v2_stage0 import V2, _run

JS = V2 / "js"
WS = (JS / "pages/workspace.js").read_text()
PALETTE = (JS / "ui/palette.js").read_text()


def home_link(tmp_path, stored=None, recent=None, lists=None):
    return _run(tmp_path, f"""
      localStorage.setItem('optic.session.holder.v1', 'guest');
      {f"localStorage.setItem('optic.v2.workspace.v1', {json.dumps(json.dumps(stored))});" if stored is not None else ''}
      {f"localStorage.setItem('optic.recent.v1', {json.dumps(json.dumps(recent))});" if recent is not None else ''}
      {f"localStorage.setItem('optic.watchlists.v1', {json.dumps(json.dumps(lists))});" if lists is not None else ''}
      const w = await import('{(JS / "pages/workspace.js").as_posix()}');
      const S = w._test.load();
      print(JSON.stringify({{ link: S.link, chosen: S.linkChosen }}));
    """)


def test_a_first_visit_shows_spy_whatever_was_opened_before(tmp_path):
    assert home_link(tmp_path) == {"link": "SPY", "chosen": False}
    # the Recent list and a watchlist no longer pick Home's ticker
    got = home_link(tmp_path, recent=["INTC", "AMD"], lists={"v": 1, "active": "a", "lists": [{"id": "a", "name": "Main", "symbols": ["TSLA"]}]})
    assert got == {"link": "SPY", "chosen": False}


def test_an_old_saved_ticker_nobody_chose_gives_way_to_spy(tmp_path):
    got = home_link(tmp_path, stored={"v": 5, "preset": "market", "link": "INTC", "layouts": {}})
    assert got == {"link": "SPY", "chosen": False}


def test_a_ticker_the_reader_chose_is_kept_between_visits(tmp_path):
    got = home_link(tmp_path, stored={"v": 5, "preset": "market", "link": "NVDA", "linkChosen": True, "layouts": {}})
    assert got == {"link": "NVDA", "chosen": True}


def test_choosing_marks_the_choice_and_show_on_home_does_too():
    set_link = WS[WS.index("function setLink(sym)"):WS.index("function setLink(sym)") + 600]
    assert "S.link = sym; S.linkChosen = true; save();" in set_link
    home = (JS / "core/homelink.js").read_text()
    assert "{ link: sym, linkChosen: true }" in home
    assert "if (!S.link) S.link = store.DEFAULT_SYMBOL;" in WS
    assert "store.recent()[0] || 'SPY'" not in WS


def test_the_follows_marker_is_gone_and_a_panel_still_names_its_ticker():
    assert "Follows ${" not in WS and "ws-linkchip" not in WS and "function linkChip" not in WS
    assert "const linkLabel = (id) =>" in WS and "${p.linked ? linkLabel(x.id) :" in WS
    assert "data-ws-pin=\"${x.id}\"" in WS, "keeping a panel on its own ticker stays in the panel's menu"
    css = (V2 / "css/pages.css").read_text()
    assert ".ws-linkchip" not in css


def test_the_linked_box_takes_a_name_and_says_when_nothing_matches():
    sub = WS[WS.index("// the box takes a ticker or a name"):]
    sub = sub[:sub.index("\n  });")]
    assert "const r = await resolve(q);" in sub and "setLink(r.hit.symbol)" in sub
    assert 'No company, fund or index matches "${q}".' in sub


def test_one_resolver_picks_the_listing_the_palette_would(tmp_path):
    got = _run(tmp_path, f"""
      const r = await import('{(JS / "core/resolve.js").as_posix()}');
      const res = (rows) => rows.map((x) => Object.assign({{ name: '', match: 'name' }}, x));
      print(JSON.stringify({{
        exact: (r.pick('nvda', res([{{ symbol: 'NVDA', match: 'symbol' }}])) || {{}}).symbol,
        share: (r.pick('brk.b', res([{{ symbol: 'BRK-A' }}, {{ symbol: 'BRK-B', match: 'symbol' }}])) || {{}}).symbol,
        alias: (r.pick('google', res([{{ symbol: 'GOOGL', match: 'alias', name: 'Alphabet Inc.' }}])) || {{}}).symbol,
        word: (r.pick('apple', res([{{ symbol: 'AAPL', name: 'Apple Inc.' }}])) || {{}}).symbol,
        inside: r.pick('ple', res([{{ symbol: 'AAPL', name: 'Apple Inc.' }}])),
        none: r.pick('zzzz', []),
        idx: r.openHref('^GSPC', 'index'), stock: r.openHref('NVDA', 'stock'), guess: r.openHref('BTC-USD'),
      }}));
    """)
    assert got["exact"] == "NVDA" and got["share"] == "BRK-B" and got["alias"] == "GOOGL" and got["word"] == "AAPL"
    assert got["inside"] is None and got["none"] is None, "a name is chosen only when a word of it starts with the text"
    assert got["idx"] == "#/instrument/%5EGSPC" and got["guess"] == "#/instrument/BTC-USD" and got["stock"] == "#/NVDA"


def test_the_dossier_start_uses_it_and_never_moves_a_reader_who_left():
    start = (JS / "pages/dossierstart.js").read_text()
    assert "const t = ticket(), r = await resolve(q);" in start and "if (!t.stillHere()) return;" in start
    assert "if (r.hit) t.go(r.hit.href); else palette.open(" in start
    assert "location.hash = `#/" not in start
    # Home's search is the top bar's palette: the search box this test also checked lived in a Home page that had not
    # been routed since the workspace became Home, and was removed in Phase 04 (registry B X-2)
    home = (JS / "pages/home.js").read_text()
    assert "data-v2-search-form" not in home and "export async function render" not in home
    app = (JS / "app.js").read_text()
    assert "home: P.workspace" in app
    resolve = (JS / "core/resolve.js").read_text()
    assert "return { stillHere: () => location.hash === at && mine === tickets," in resolve


def test_a_failed_search_is_never_cached_as_an_answer():
    api = (JS / "core/api.js").read_text()
    assert "if ((d && d.building) || (keep && !keep(d))) cache.delete(path);" in api
    resolve = (JS / "core/resolve.js").read_text()
    assert "keep: (d) => !(d && d.available === false)" in resolve


def test_the_palette_starts_from_this_visit_or_spy_and_enter_on_an_empty_box_opens_nothing():
    assert "const symFor = () => ctxSym || store.openedNow() || null;" in PALETTE
    assert "store.recent().find(" not in PALETTE
    assert "(placeSym(p) ? hrefFor(p.view, placeSym(p)) : '#/dossier')" in PALETTE
    assert "sel = keep >= 0 ? keep : out.findIndex((r) => r.tag === 'enter');" in PALETTE
    assert "const it = i >= 0 ? items[i] : null; if (!it) return;" in PALETTE
    assert "input.setAttribute('aria-expanded', String(out.length > 0));" in PALETTE
    assert "window.addEventListener('v2:research-saved', () => { research = null; });" in PALETTE
    assert "label: \"This week's earnings\", href: '#/earnings'" in PALETTE


def test_a_typed_name_picks_by_the_start_of_a_word(tmp_path):
    got = _run(tmp_path, f"""
      const t = await import('{(JS / "ui/typeahead.js").as_posix()}');
      const items = [{{ symbol: 'SNPL', name: 'Snapple Group' }}, {{ symbol: 'AAPL', name: 'Apple Inc.' }}];
      print(JSON.stringify([t.typedNamePick(items, 'app', 'app'), t.typedNamePick(items, 'AAPL', 'AAPL'), t.typedNamePick(items, 'x', 'app')]));
    """)
    assert got == [1, -1, -1]


def test_late_answers_land_nowhere():
    sheet = (JS / "pages/sheet.js").read_text()
    assert "const box = D, enc = encodeURIComponent(sym), step = (p, k) => p.then((d) => { box[k] = d; }" in sheet
    assert ".finally(() => { if (D === box) paint(); });" in sheet
    assert "if (!live || mine !== SEQ[id] || (p.linked && linkAt !== symOf(id))) return;" in WS
    macro = (JS / "pages/macro.js").read_text()
    assert "return live && D === box && mine === LATEST[key] ? out : null;" in macro and macro.count("await newest(") == 6
    read = (JS / "pages/read.js").read_text()
    assert "if (mine !== catSeq || D !== box) return;" in read
    chart = (JS / "pages/chart.js").read_text()
    assert "D.intra = iv.intraday ? intra : null;" in chart


def test_the_skip_link_and_the_sector_board_link_go_where_they_say():
    app = (JS / "app.js").read_text()
    assert "if (t('a.skip')) { e.preventDefault(); const m = $('#main');" in app
    home = (JS / "pages/home.js").read_text()
    assert 'href="#/macro">The full sector board' in home and 'href="#/market"' not in home


def test_symbol_boxes_offer_suggestions_and_take_a_name():
    for page, marker in (("pages/chart.js", 'placeholder="Add a symbol, such as SPY" data-v2-ta="submit"'),
                         ("pages/insiders.js", 'placeholder="NVDA, or blank for everything" data-v2-ta="submit" maxlength="40"'),
                         ("pages/paper.js", 'placeholder="NVDA" data-v2-ta maxlength="40"'),
                         ("pages/watchlist.js", 'maxlength="40" enterkeyhint="done"'),
                         ("pages/alerts.js", 'placeholder="Symbol, such as AAPL" maxlength="40"')):
        assert marker in (JS / page).read_text(), page


def test_with_search_down_a_typed_symbol_keeps_enter_and_a_name_opens_the_search(tmp_path):
    got = _run(tmp_path, f"""
      const r = await import('{(JS / "core/resolve.js").as_posix()}');
      print(JSON.stringify(['KO', 'SPY', 'BRK.B', 'brk-b', '^GSPC', 'ES=F', 'BTC-USD', 'nvidia', 'abcdef', 'scan it'].map(r.symbolShaped)));
    """)
    assert got == [True, True, True, True, True, True, True, False, False, False]
    resolve = (JS / "core/resolve.js").read_text()
    assert "if (failed && symbolShaped(q)) {" in resolve
    # scenario S5: "ko" opened Scan ("breakout"), "dis" Explore, "spy" Indices when the search request failed
    assert "const typedWins = failed && symbolShaped(q) && !byLabel;" in PALETTE
    assert "if (typedWins) rows.forEach((r) => { if (r.tag === 'enter') r.tag = ''; });" in PALETTE
    assert "const matched = places.filter((p) => wordStart(p.label) || wordStart(p.terms));" in PALETTE
