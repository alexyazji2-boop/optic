"""A searched symbol opens its Overview.

Reported: typing a ticker opened the Options tab. Two separate causes, and the
second is the one that would have survived fixing the first.

Three palette rows passed `'swing'` outright -- the exact-match "Analyse this
symbol" row, the recents, and the symbol results -- so the ⌘K search always
landed on a twenty-four panel options page.

The rest passed no destination at all, and `loadTicker` falls back to
`STATE.view === 'home' ? 'overview' : STATE.view`. So the top bar kept you on
whatever tab you were already on: searching a name from Earnings opened that
name's earnings, and searching one from Options opened its options. Neither is
wrong exactly, and neither answers a question the reader has asked yet.

Overview is the workspace's front door and the only destination that assumes
nothing. Verified in a browser on all seven routes: the top bar form, the home
form, the home typeahead (which fires on `mousedown`, not click), the palette's
exact-match row, its recents, its symbol results, and the home quick-picks.

A watchlist row and a holding in the ledger were left opening the swing read,
on the grounds that clicking one meant "show me why". Reported later as
"whenever i click on a ticker, it goes straight to the options tab. change it.
take it straight to the overview tab in the dossier", so every click on a
ticker lands on the Overview now as well.
"""

from __future__ import annotations

import re

APP = open("static/app.js", encoding="utf-8").read()


def _code():
    src = re.sub(r"/\*.*?\*/", " ", APP, flags=re.S)
    return re.sub(r"(?m)^\s*//.*$", " ", src)


def test_the_landing_view_is_named_once():
    """Seven call sites. A literal at each is seven chances to disagree, and
    three of them already did."""
    code = _code()
    assert "const SEARCH_LANDING = 'overview';" in code
    assert code.count("SEARCH_LANDING") >= 8, "one definition and every search route"


def test_no_search_route_still_opens_the_options_tab():
    """The palette's three rows were the loud half of this."""
    code = _code()
    for dead in ("loadTicker(sym, 'swing')",
                 "loadTicker(upper, 'swing')",
                 "loadTicker(r.symbol, 'swing')"):
        assert dead not in code, dead + " still sends a search to Options"


def test_every_way_of_typing_a_ticker_passes_a_destination():
    """The quiet half: passing nothing means "stay where you are", which is a
    different answer on every tab and reads as the app having a mind of its
    own."""
    code = _code()
    for call in ("loadTicker($('#ticker-input').value, SEARCH_LANDING)",
                 "loadTicker($('#home-input').value, SEARCH_LANDING)",
                 "loadTicker(pick.symbol, SEARCH_LANDING)",
                 "loadTicker(pick.dataset.pick, SEARCH_LANDING)"):
        assert call in code, call


def test_every_click_on_a_ticker_lands_on_the_overview_too():
    """A ticker button in any table (scans, analysts, the ledger's holdings),
    a watchlist or alert row, and a saved question re-asked."""
    code = _code()
    assert "loadTicker(analyse.dataset.analyse, SEARCH_LANDING)" in code, "a ticker in a table"
    assert "loadTicker(open.dataset.watchOpen, SEARCH_LANDING)" in code, "a watchlist row"
    assert "loadTicker(row.ticker, SEARCH_LANDING)" in code, "a saved question"
    assert not re.search(r"loadTicker\([^)]*'swing'\)", code), "nothing opens Options"


def test_the_fallback_still_exists_for_callers_that_pass_nothing():
    """`loadTicker` is the one door every route goes through, and it is called
    from places that are not a search."""
    code = _code()
    fn = code[code.index("function loadTicker(raw, destination) {"):]
    assert "const target = landing || (STATE.view === 'home' ? 'overview' : STATE.view);" in fn[:3000]


def test_a_search_from_the_chart_stays_on_the_chart():
    """Asked for as searching from the Chart tab keeping you on it. Checked in a
    browser: MSFT searched on AAPL's chart charted MSFT, NVDA searched from
    Earnings opened its Overview."""
    code = open("static/app.js").read()
    assert ("const landing = destination === SEARCH_LANDING && STATE.view === 'chart' ? 'chart' : destination;"
            in code)
    assert "const target = landing || (STATE.view === 'home' ? 'overview' : STATE.view);" in code
    assert code.index("const landing =") < code.index("if (target === 'chart') STATE.chartSymbol = next;")
