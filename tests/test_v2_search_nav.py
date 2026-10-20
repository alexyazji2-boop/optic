"""Search and navigation (backlog task 1, 2026-10-20).

The symbol directory's ranking runs against a small directory built here; the palette's helpers and
the scroll memory run in JavaScriptCore. The palette's behaviour end to end (Enter on 14 queries, a
fast Enter, a failed search, Back closing the palette and Back after a result, the journey from a
search to the chart, the options and back) was checked in headless Chrome at 360, 390, 430, 768 and
1440 px with ~/Optic/work/v2-backlog/search_check.py and nav_check.py.
"""
import pytest

from app import universe
from tests.test_frontend_v2_stage0 import V2, _run

JS = V2 / "js"


@pytest.fixture
def directory(monkeypatch):
    # alphabetical, like the real one, with enough names containing "T" ahead of the symbol T
    # that the old cap (stop after 4000 matches) never reached it
    rows = [{"symbol": "A%04d" % i, "name": "Tech Holding %d" % i, "etf": False} for i in range(4200)]
    rows += [
        {"symbol": "AAPL", "name": "Apple Inc", "etf": False},
        {"symbol": "APLE", "name": "Apple Hospitality REIT, Inc", "etf": False},
        {"symbol": "BRK.B", "name": "Berkshire Hathaway Inc. New", "etf": False},
        {"symbol": "GOOGL", "name": "Alphabet Inc. Class A", "etf": False},
        {"symbol": "DEPW", "name": "Google DeepMind Thematic ETF", "etf": True},
        {"symbol": "SPY", "name": "SPDR S&P 500 ETF Trust", "etf": True},
        {"symbol": "SPXC", "name": "SPX Technologies, Inc", "etf": False},
        {"symbol": "T", "name": "AT&T Inc", "etf": False},
        {"symbol": "VIXM", "name": "ProShares VIX Mid-Term Futures ETF", "etf": True},
    ]
    rows.sort(key=lambda r: r["symbol"])
    idx = {"rows": rows, "fetched_on": "2026-10-20"}
    monkeypatch.setattr(universe, "_rows_today", lambda: idx)
    monkeypatch.setattr(universe, "_prominence", lambda: {})
    return idx


def first(q):
    r = universe.search(q, 5)
    return (r[0]["symbol"], r[0]["kind"], r[0]["match"]) if r else None


def test_an_exact_one_letter_symbol_is_found_however_many_names_match(directory):
    assert first("T") == ("T", "stock", "symbol")      # T opened Cooper Companies before


def test_names_people_type_reach_the_company(directory):
    assert first("google")[:2] == ("GOOGL", "stock")   # not the Google-themed fund
    assert first("apple")[0] == "AAPL"


def test_indices_rates_and_crypto_are_found_and_say_what_they_are(directory):
    assert first("VIX") == ("^VIX", "index", "symbol")  # not VIXM
    assert first("spx")[:2] == ("^GSPC", "index")       # not SPX Technologies
    assert first("10 year")[:2] == ("^TNX", "rate")
    assert first("bitcoin")[:2] == ("BTC-USD", "crypto")


def test_share_classes_answer_in_the_dashed_form_from_any_spelling(directory):
    for q in ("BRK.B", "BRK-B", "brk b", "brk/b"):
        assert first(q) == ("BRK-B", "stock", "symbol"), q


def test_an_exact_fund_symbol_is_not_demoted(directory):
    assert first("SPY") == ("SPY", "etf", "symbol")


def test_the_search_says_when_the_directory_could_not_be_read(monkeypatch):
    monkeypatch.setattr(universe, "_rows_today", lambda: {"rows": [], "fetched_on": None, "error": "timed out"})
    out = universe.search_with_status("aapl", 5)
    assert out["available"] is False and "reason" in out
    # the instruments do not need the directory
    assert universe.search_with_status("vix", 5)["results"][0]["symbol"] == "^VIX"


def test_the_palette_routes_instruments_to_their_page_and_encodes_symbols(tmp_path):
    got = _run(tmp_path, f"""
      const p = await import('{(JS / "ui/palette.js").as_posix()}');
      print(JSON.stringify({{
        inst: [p.openHref('^TNX', 'rate'), p.openHref('BTC-USD', 'crypto'), p.openHref('^VIX')],
        co: [p.openHref('AAPL', 'stock'), p.openHref('BRK-B', 'stock'), p.openHref('SPY', 'etf')],
        is: ['^GSPC', 'ES=F', 'DX-Y.NYB', 'AAPL', 'BRK-B'].map((s) => p.isInstrument(s)),
      }}));
    """)
    assert got["inst"] == ["#/instrument/%5ETNX", "#/instrument/BTC-USD", "#/instrument/%5EVIX"]
    assert got["co"] == ["#/AAPL", "#/BRK-B", "#/SPY"]
    assert got["is"] == [True, True, True, False, False]


def test_the_palette_offers_options_and_waits_for_the_search_on_enter():
    src = (JS / "ui/palette.js").read_text()
    assert "['Options', 'The chain, positioning and the position builder', 'swing']" in src
    assert "fund ? null : ['Earnings'" in src                        # a fund has no earnings
    assert "q === settledFor" in src and "pending" in src             # a fast Enter never opens a guess
    assert "history.pushState" in src and "popstate" in src           # Back closes the palette
    assert "location.replace(" in src                                 # a result replaces the palette's step
    assert 'enterkeyhint="go"' in src and 'autocapitalize="none"' in src


def test_recent_symbols_clear_and_a_missing_symbol_is_forgotten(tmp_path):
    got = _run(tmp_path, f"""
      const s = await import('{(JS / "core/store.js").as_posix()}');
      localStorage.setItem('optic.session.holder.v1', 'guest');
      s.pushRecent('AAPL'); s.pushRecent('ZZZZQQ'); s.pushRecent('MSFT');
      const before = s.recent();
      s.forgetRecent('zzzzqq');
      const after = s.recent();
      s.clearRecent();
      print(JSON.stringify({{ before, after, cleared: s.recent(), raw: localStorage.getItem('optic.recent.v1') }}));
    """)
    assert got["before"] == ["MSFT", "ZZZZQQ", "AAPL"]
    assert got["after"] == ["MSFT", "AAPL"]
    assert got["cleared"] == [] and got["raw"] == "[]"   # the classic key, its plain-string shape
    assert "store.forgetRecent(sym)" in (JS / "pages/dossier.js").read_text()


def test_back_forward_and_refresh_keep_the_place_on_the_page():
    src = (JS / "core/scrollmem.js").read_text()
    app = (JS / "app.js").read_text()
    assert "history.scrollRestoration = 'manual'" in src and "sessionStorage" in src
    assert "scrollmem.arrive();" in app and "window.scrollTo(0, 0);\n  Promise.resolve(page.render" not in app


def test_a_malformed_address_still_renders(tmp_path):
    got = _run(tmp_path, f"""
      const r = await import('{(JS / "core/router.js").as_posix()}');
      print(JSON.stringify([r.parse('#/%'), r.parse('#/instrument/%5ETNX'), r.parse('#/BRK-B/options')]));
    """)
    assert got[0]["view"] == "notfound"
    assert got[1] == {"view": "instrument", "symbol": "^TNX", "params": {}}
    assert got[2]["symbol"] == "BRK-B" and got[2]["view"] == "swing"


def test_the_instrument_page_paints_only_its_newest_answer():
    src = (JS / "pages/instrument.js").read_text()
    assert "if (my !== gen || !live || D.sym !== sym) return;" in src
