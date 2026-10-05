"""The UX pass's own contracts: the Dossier header's actions and data state,
Pulse's research modes, Portfolio health, the watchlist summary, and the
stylesheet layer they are drawn with.

Measured before it, at 1440x900: the Dossier header named a symbol and gave
no way to watch it, set an alert on it or ask about it; nothing said whether
its price was live, delayed or Friday's close; the Paper Desk had no reading
of the book above its table; and a Pulse panel opened onto a blank box. Each
test below names the failure it guards, because each of these fails silently:
a dead button takes the click and nothing happens, and a wrong label reads as
a true one.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import app.main as main
from app.providers.tradier import TradierProvider

ROOT = Path(__file__).resolve().parents[1]
RAW = (ROOT / "static/app.js").read_text()
CSS = (ROOT / "static/styles.css").read_text()
HTML = (ROOT / "static/index.html").read_text()
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc"


def _fn(name):
    return re.search(r"^(?:async )?function " + name + r"\([^\n]*\) \{.*?^\}",
                     RAW, re.M | re.S).group()


def _js(prelude, names, scenario):
    exe = JSC if os.path.exists(JSC) else shutil.which("jsc")
    if not exe:
        pytest.skip("no JavaScriptCore on this machine")
    src = ("function assert(v, m) { if (!v) throw new Error(m); }\n" + prelude + "\n"
           + "\n".join(_fn(n) for n in names)
           + "\ntry {\n" + scenario + "\nprint('TEST_OK'); } catch (e) { print('FAIL ' + e); }")
    out = subprocess.run([exe, "-e", src], capture_output=True, text=True, timeout=30)
    assert "TEST_OK" in out.stdout, out.stdout + out.stderr


# ------------------------------------------------------- the Dossier header


def test_every_header_action_has_a_handler():
    """Watch, Alert and Ask Pulse are markup in secActionsHTML and behaviour in
    one click listener. Either half alone is a dead control."""
    actions = _fn("secActionsHTML")
    for attr in ("data-sec-watch", "data-sec-alert", "data-sec-pulse"):
        assert attr + '="' in actions, attr
        assert "closest('[" + attr + "]')" in RAW, attr + " has no handler"
        # Grep before inventing (CLAUDE.md): one markup site, no other owner.
        assert RAW.count(attr + '="') == 1, attr + " is rendered somewhere else too"


def test_the_watch_toggle_says_its_state_to_a_screen_reader():
    assert 'aria-pressed="${watched}"' in _fn("secActionsHTML")


def test_watching_updates_every_copy_of_the_header():
    """Each Dossier section keeps its own header, and the hidden ones went on
    saying "Watch" for a name that was now on the list."""
    handler = RAW[RAW.index("closest('[data-sec-watch]')"):][:1400]
    assert "document.querySelectorAll('[data-sec-watch]')" in handler
    assert ".sec-act-label" in handler, "the label is its own element, not the last text node"


def test_alert_opens_the_watch_builder_on_this_symbol():
    """The builder defaults to `watchDraft.symbol`. Setting it is what makes
    Alert land on the symbol the header names, not the last one typed."""
    handler = RAW[RAW.index("closest('[data-sec-alert]')"):][:600]
    assert "watchDraft.symbol = a.dataset.secAlert;" in handler
    assert "switchView('alerts');" in handler
    assert "watchDraft.symbol" in _fn("renderWatchesBlock")


def test_charting_keeps_its_rows_for_the_chart():
    """The workspace is sized to the viewport, so every row above it comes off
    the plot. The actions are on every other facet, compact Options included."""
    assert "${view === 'chart' ? '' : secActionsHTML(sym)}" in _fn("securityHeader")


DATA_STATE = r"""
var session = 'regular';
function marketSessionET() { return session; }
var STATE = { health: null };
function esc(s) { return String(s); }
function activeZone() { return 'America/New_York'; }
function timeIn(iso) { return '2:05 pm'; }
function label(q) { return secDataStateHTML(q || { as_of: '2026-10-05T18:05:00Z' }); }
"""


def test_the_data_state_says_what_the_number_is():
    """During the session the chip names the feed; outside it, the figure is
    the close on the free feed, and a close read on a Sunday is not "delayed
    ~15 min". Real-time only when the deployment's feed is and this quote came
    from it: Tradier falls back to yfinance per quote and says so in
    `quote_source`."""
    _js(DATA_STATE, ["secDataStateHTML"], """
      var h = label();
      assert(h.indexOf('Delayed ~15 min') >= 0 && h.indexOf('is-delayed') >= 0, 'free feed: ' + h);
      assert(h.indexOf('2:05 pm') >= 0, 'with the time it was fetched');
      STATE.health = { realtime_chain: true };
      h = label();
      assert(h.indexOf('Live') >= 0 && h.indexOf('is-live') >= 0, 'real-time feed: ' + h);
      h = label({ as_of: 'x', quote_source: 'yfinance (Tradier quote unavailable)' });
      assert(h.indexOf('Delayed ~15 min') >= 0, 'a fallen-back quote is not live: ' + h);
      STATE.health = null; session = 'after';
      h = label();
      assert(h.indexOf('At the close') >= 0 && h.indexOf('is-closed') >= 0, 'after hours: ' + h);
      assert(h.indexOf('2:05 pm') < 0, 'no fetch time beside a close');
      STATE.health = { realtime_chain: true };
      assert(label().indexOf('Last trade') >= 0, 'Tradier last can be an extended-hours trade');
      session = 'closed'; STATE.health = null;
      assert(label().indexOf('At the close') >= 0, 'a weekend');
    """)


def test_every_data_state_tone_has_a_colour():
    for tone in ("is-live", "is-delayed", "is-closed", "is-unavailable"):
        assert ".data-state." + tone + " {" in CSS, tone + " has no colour"


def test_a_tradier_sandbox_is_not_reported_as_real_time(monkeypatch):
    """The sandbox serves the same API fifteen minutes late. A sandbox token
    made /api/health say real-time, and the header would have said Live."""
    client = TestClient(main.app)
    monkeypatch.setattr(main, "PROVIDER", TradierProvider(token="t", sandbox=True))
    assert client.get("/api/health").json()["realtime_chain"] is False
    monkeypatch.setattr(main, "PROVIDER", TradierProvider(token="t", sandbox=False))
    assert client.get("/api/health").json()["realtime_chain"] is True


# -------------------------------------------------------------------- Pulse


def test_every_research_mode_drafts_and_none_sends():
    """A press must never spend a call the reader has not seen."""
    assert 'data-q="${esc(m.text)}"' in _fn("pulseModesHTML")
    assert 'id="pulse-modes"' in HTML
    handler = _fn("onPulseSuggestion")
    assert "draftPulse(" in handler and "sendChat" not in handler and "runResearch" not in handler


def test_the_modes_follow_the_page():
    assert "updateChatContext();" in _fn("switchView")
    assert "pulseModesHTML()" in _fn("updateChatContext")


MODES = r"""
var STATE = { view: 'overview', ticker: 'NVDA', chartSymbol: '' };
var SECURITY_VIEWS = ['overview', 'chart', 'swing', 'long', 'earnings', 'financials', 'news'];
var SUB_LABELS = { overview: 'Overview', swing: 'Options' };
var VIEW_NAMES = { paper: 'Paper Desk', scan: 'Scan' };
function ids() { return pulseModes().map(function (m) { return m.id; }).join(','); }
"""


def test_the_modes_are_about_what_is_on_screen():
    _js(MODES, ["pulseSubject", "pulseModes"], """
      assert(pulseSubject().label === 'NVDA \\u00b7 Overview', pulseSubject().label);
      assert(ids() === 'quick,catalyst,thesis,risk,deep', 'a security: ' + ids());
      assert(pulseModes()[0].text.indexOf('NVDA') >= 0, 'names the symbol');
      STATE.view = 'chart'; STATE.chartSymbol = 'TSLA';
      assert(pulseSubject().sym === 'TSLA', 'Charting asks about its own symbol');
      STATE.view = 'paper';
      assert(pulseSubject().kind === 'portfolio' && ids().indexOf('risk') === 0, 'positions: ' + ids());
      STATE.view = 'scan';
      assert(pulseSubject().kind === 'screen', 'a screen');
      STATE.view = 'home';
      assert(pulseSubject().kind === 'market', 'Home is the market');
    """)


# --------------------------------------------------------- portfolio health


PAPER = r"""
var PAPER_EXPIRY_DAYS = 7, PAPER_CONCENTRATED = 0.4;
function fmt(v, d) { return Number(v).toFixed(d); }
var paperBook = { open: [], closed: [] };
var paperMarks = {};
function etDate(value) {
  return new Date(value).toLocaleDateString('en-CA', { timeZone: 'America/New_York' });
}
function inDays(n) { return etDate(Date.now() + n * 864e5); }
"""


def test_portfolio_health_reads_concentration_and_what_needs_review():
    _js(PAPER, ["paperCost", "paperRisk", "paperR", "paperRText", "paperHealth"], """
      assert(paperHealth() === null, 'an empty book has no health to read');
      paperBook.open = [
        { id: 'a', ticker: 'NVDA', instrument: 'stock', direction: 'long', qty: 20, entry_price: 200, stop: 180 },
        { id: 'b', ticker: 'AAPL', instrument: 'stock', direction: 'short', qty: 10, entry_price: 100, stop: 110 },
        { id: 'c', ticker: 'TSLA', instrument: 'option', direction: 'long', qty: 1, entry_price: 5,
          stop: 2, strike: 300, option_type: 'call', expiry: inDays(3) },
        { id: 'd', ticker: 'AMD', instrument: 'option', direction: 'long', qty: 1, entry_price: 2,
          stop: 1, strike: 150, option_type: 'put', expiry: inDays(-2) },
      ];
      // NVDA lost 340 against a 400 risk: -0.85R, inside a quarter of its stop.
      // TSLA lost 290 of a 300 risk AND expires in three days: one row, both.
      paperMarks = { a: { pnl: -340 }, b: { pnl: 50 }, c: { pnl: -290 } };
      var h = paperHealth();
      assert(h.total === 4000 + 1000 + 500 + 200, 'exposure is cost: ' + h.total);
      assert(h.top[0] === 'NVDA', 'largest name');
      assert(h.short === 1000 && h.long === 4700, 'direction is kept apart');
      assert(h.marked === 3 && h.pnl === -580, 'only marked rows count toward P&L');
      var rows = {};
      h.review.forEach(function (x) { rows[x.pos.id] = x.why; });
      assert(rows.a && rows.a.indexOf('within a quarter of its stop') >= 0, 'near its stop: ' + rows.a);
      assert(rows.c === '-0.97R, within a quarter of its stop; expires in 3 days', 'one row, both reasons: ' + rows.c);
      assert(rows.d === 'expired and still open', 'an expired option still open: ' + rows.d);
      assert(!rows.b, 'a winner needs no review');
      assert(h.review.length === 3, 'one row per position');
    """)


def test_portfolio_health_says_what_it_cannot_see():
    """Every panel states what it cannot tell you (CLAUDE.md), and a missing
    mark is counted rather than summed as zero."""
    assert "does not see sectors" in _fn("paperHealthHTML")
    assert "not marked" in _fn("paperMarkStateHTML")


# ------------------------------------------------------ the watchlist summary


WATCH = r"""
function fmt(v, d) { return Number(v).toFixed(d); }
function fmtPct(v, d) { return (v >= 0 ? '+' : '') + Number(v).toFixed(d) + '%'; }
function esc(s) { return String(s); }
function signClass(v) { return v > 0 ? 'up' : v < 0 ? 'down' : 'flat'; }
"""


def test_the_watchlist_summary_counts_the_whole_list():
    _js(WATCH, ["watchPulseHTML"], """
      assert(watchPulseHTML([]) === '', 'nothing priced, nothing said');
      var html = watchPulseHTML([
        { symbol: 'NVDA', change_pct: 1.09, changed: '20-day breakout', signal: 'bullish' },
        { symbol: 'AMD', change_pct: -2.4, changed: null, signal: 'bearish' },
        { symbol: 'SPY', change_pct: 0.0, changed: null, signal: 'neutral' },
      ]);
      assert(html.indexOf('1 <span class="wv-pulse-of">/</span> 1') >= 0, 'up / down: ' + html);
      assert(html.indexOf('AMD -2.40%') >= 0, 'the biggest move by size, either way');
      assert(html.indexOf('1 name') >= 0, 'one changed');
      assert(html.indexOf('1 bullish') >= 0 && html.indexOf('1 bearish') >= 0, 'signal split');
    """)


# ------------------------------------------------- the system layer's reach


def test_the_system_layer_does_not_restyle_bases_from_the_foot():
    """The first draft put `.btn {...}`, `.panel {...}` and `.up {...}` at the
    foot of the stylesheet. Equal specificity and later source order beat
    every single-class rule written for one button or one panel: `.pt-danger`
    lost its red, `.auth-submit` its 44px touch target, `.catmode` and
    `.sector-read` their accent edges, and direction chips their ink. A base
    class is restyled where it is declared, so the rules after it still win."""
    start = CSS.index("the Optic system ====")
    foot = re.sub(r"/\*.*?\*/", "", CSS[start:], flags=re.S)
    for base in (".btn", ".panel", ".chip", ".up", ".down", ".pos", ".neg"):
        assert not re.search(r"(^|\})\s*" + re.escape(base) + r"\s*[,{]", foot), \
            base + " is restyled from the foot of the stylesheet"
    btn = CSS.index(".btn {\n  display: inline-flex;")
    for later in (".pt-danger {", ".auth-submit {", ".acct-signin {", ".pt-close {", ".wd-check {"):
        assert btn < CSS.index(later), later + " no longer comes after .btn"


def test_direction_colour_yields_to_any_specific_rule():
    """`pos` and `neg` had no colour outside six component rules, so the Paper
    Desk's P&L cells rendered in plain ink. They get one at zero specificity:
    a rule that colours a particular `pos` element still wins."""
    assert ":where(.pos) { color: var(--pos); }" in CSS
    assert ":where(.neg) { color: var(--neg); }" in CSS


# ------------------------------------------------------- the day's change


from app.providers import yf as Y  # noqa: E402


def _quote_from(info, monkeypatch):
    monkeypatch.setattr(Y, "_CACHE", {})
    provider = Y.YFinanceProvider()
    monkeypatch.setattr(provider, "_info", lambda ticker: dict(info))
    return provider.quote("NVDA")


def test_a_missing_change_is_derived_from_price_and_previous_close(monkeypatch):
    """Measured 2026-10-05, 1pm ET: NVDA came back with a price and a previous
    close and no change, so the Dossier showed none and Optic's read said
    NVIDIA "has not printed a change today" while it was up 1.36%."""
    q = _quote_from({"regularMarketPrice": 237.13, "regularMarketPreviousClose": 233.95,
                     "longName": "NVIDIA Corporation"}, monkeypatch)
    assert q["change"] == pytest.approx(3.18)
    assert q["change_pct"] == pytest.approx((237.13 / 233.95 - 1) * 100)


def test_yahoos_own_change_wins_when_it_is_there(monkeypatch):
    q = _quote_from({"regularMarketPrice": 237.13, "regularMarketPreviousClose": 233.95,
                     "regularMarketChange": 3.0, "regularMarketChangePercent": 1.3},
                    monkeypatch)
    assert q["change"] == 3.0 and q["change_pct"] == 1.3


def test_no_previous_close_means_no_invented_change(monkeypatch):
    q = _quote_from({"regularMarketPrice": 237.13}, monkeypatch)
    assert q["change"] is None and q["change_pct"] is None


def test_an_empty_change_is_not_drawn_as_a_pill():
    """With no change figure the element is empty, and the pill styling drew
    it as a grey lozenge beside the price (seen on a phone, 2026-10-05)."""
    assert ".sec-chg:empty { display: none; }" in CSS


def test_alert_focuses_the_builder_after_each_render_until_the_reader_acts():
    """A timer fired before the form existed: loadAlertsFeed renders only
    after the catalogue and the fired watches load, then again when
    /api/alerts lands, and each render replaces the form."""
    fn = _fn("focusWatchBuilderSoon")
    assert "new MutationObserver(apply)" in fn
    assert "addEventListener('pointerdown', stop, true)" in fn
    assert "addEventListener('keydown', stop, true)" in fn
    assert "setTimeout(stop, WATCH_FOCUS_MS)" in fn
    handler = RAW[RAW.index("closest('[data-sec-alert]')"):][:400]
    assert "focusWatchBuilderSoon();" in handler
