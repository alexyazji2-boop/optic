"""v2 data and state correctness (owner's overnight brief, 2026-10-19, priority 1).

Pure functions run in JavaScriptCore, as in test_frontend_v2_stage0.py, and the wiring that keeps them
in force read from the page modules as text, which is this project's pattern for client contracts. The
races themselves are exercised in a browser by ~/Optic/work/v2-overnight/race_check.py (MSFT's answers
slowed by 3 s, every Dossier view switched to AAPL at once, and the owner's Home reproduction sampled
every 100 ms).
"""
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from tests.test_frontend_v2_stage0 import JSC, STUBS, V2

JS = V2 / "js"


def _run(tmp_path, body):
    exe = JSC if os.path.exists(JSC) else shutil.which("jsc")
    if not exe:
        pytest.skip("jsc not available")
    script = tmp_path / "check.mjs"
    script.write_text(STUBS + body)
    out = subprocess.run([exe, "-m", str(script)], capture_output=True, text=True, timeout=30)
    assert out.returncode == 0, out.stderr + out.stdout
    return json.loads(out.stdout.strip().splitlines()[-1])


def _src(rel):
    return (JS / rel).read_text()


# ------------------------------------------------------------ instrument policy

def test_the_instrument_policy_tells_a_fund_from_a_company_and_remembers_it(tmp_path):
    got = _run(tmp_path, f"""
      const m = await import('{(JS / "core/instrument.js").as_posix()}');
      const fundSession = {{ profile: {{ is_fund: true, kind: 'ETF' }} }};
      const coSession = {{ profile: {{ is_company: true, kind: 'EQUITY' }} }};
      const before = m.kindOf('SPY');
      m.learn('SPY', {{ session: fundSession }});
      print(JSON.stringify({{
        before, after: m.kindOf('SPY'), co: m.kindOf('AAPL', {{ session: coSession }}),
        byQuote: m.kindOf('QQQ', {{ quote: {{ quote_type: 'ETF' }} }}), index: m.kindOf('^GSPC'),
        fundCan: m.can('fund'), coCan: m.can('company'), unknownCan: m.can('unknown'),
      }}));
    """)
    assert got["before"] == "unknown" and got["after"] == "fund"
    assert got["co"] == "company" and got["byQuote"] == "fund" and got["index"] == "index"
    assert got["fundCan"]["financials"] is False and got["fundCan"]["fundProfile"] is True
    assert got["coCan"]["financials"] is True
    assert got["unknownCan"]["financials"] is True     # the common case until the profile says otherwise


def test_every_dossier_view_takes_its_tabs_from_the_one_policy():
    """SPY's Financials tab showed on Chart and not on the other views: each page passed its own idea of
    "fund" from data it might not have loaded yet."""
    frame = _src("pages/dossier-frame.js")
    assert "can(k).financials" in frame and "onLearn(" in frame and "learn(sym, out)" in frame
    for page in ("dossier.js", "chart.js", "options.js", "investing.js", "earnings.js", "financials.js", "news.js"):
        body = _src("pages/" + page)
        assert re.search(r"\btabs\(|frameTabs\(", body), page
        assert '<nav class="tabs"' not in body, page + " draws its own tab list"


def test_a_funds_financials_link_explains_rather_than_bouncing():
    fin = _src("pages/financials.js")
    assert "Financials do not apply to" in fin
    assert "go(`#/${sym}`)" not in fin


# ------------------------------------------------------------ cross-ticker races

def test_linked_panels_never_paint_data_fetched_for_another_ticker():
    ws = _src("pages/workspace.js")
    assert "DLINK[id] !== S.link" in ws, "a linked panel must not draw another ticker's data under the link"
    assert "DLINK[id] = linkAt" in ws
    assert "p.body(d, P, forLink)" in ws, "labels come from the ticker the data is for"


def test_options_answers_are_dropped_when_the_page_has_moved_on():
    op = _src("pages/options.js")
    for fn in ("async function loadTicker", "async function loadResearch", "async function loadExtra",
               "async function analyze", "async function template"):
        i = op.index(fn)
        body = op[i:op.index("\n}\n", i)]
        assert "stillHere(g)" in body, fn


def test_a_slower_bar_load_never_replaces_the_newer_one():
    ch = _src("pages/chart.js")
    i = ch.index("async function loadBars")
    body = ch[i:ch.index("\n}\n", i)]
    assert "D.barSeq" in body and "if (!current()) return;" in body


# ------------------------------------------------------------ times and errors

def test_a_price_says_its_session_and_when_it_was_struck(tmp_path):
    got = _run(tmp_path, f"""
      const m = await import('{(JS / "core/marketTime.js").as_posix()}');
      print(JSON.stringify({{
        friday: m.etStamp('2026-10-16T23:59:44+00:00'), day: m.etDay('2026-10-16'),
        word: [m.sessionWord('after hours'), m.sessionWord('overnight'), m.sessionWord('pre')],
      }}));
    """)
    assert got["friday"] == "Fri 7:59 PM ET"
    assert got["day"] == "Fri Oct 16", "a bare date is that calendar day, not the evening before"
    assert got["word"] == ["After hours", "Overnight", "Pre-market"]


def test_provider_exceptions_never_reach_a_reader(tmp_path):
    got = _run(tmp_path, f"""
      const f = await import('{(JS / "core/format.js").as_posix()}');
      print(JSON.stringify({{
        xbrl: f.clean('No fair value range to rate the price against. SEC XBRL unavailable: HTTP Error 404: Not Found'),
        conn: f.clean("HTTPSConnectionPool(host='query2.finance.yahoo.com', port=443): Read timed out."),
        plain: f.clean('Earnings on Nov 2, in 15 days.'),
      }}));
    """)
    assert "HTTP Error" not in got["xbrl"] and "XBRL" not in got["xbrl"]
    assert got["xbrl"].startswith("No fair value range to rate the price against.")
    assert "HTTPSConnectionPool" not in got["conn"]
    assert got["plain"] == "Earnings on Nov 2, in 15 days."


def test_axis_labels_get_the_decimals_their_range_needs(tmp_path):
    """A ratio near 0.26 printed "0 / 0 / 0" on its axis."""
    got = _run(tmp_path, f"""
      const c = await import('{(JS / "ui/chart.js").as_posix()}');
      const pts = Array.from({{ length: 40 }}, (_, i) => ({{ d: '2026-0' + (1 + (i % 9)) + '-1' + (i % 9), c: 0.2550 + i * 0.0002 }}));
      const out = c.lineChart(pts, {{ w: 400, h: 200, label: 'ratio' }});
      const ticks = [...out.html.matchAll(/<text class="ax" x="[^"]+" y="[^"]+">([^<]+)<\\/text>/g)].map((m) => m[1]);
      print(JSON.stringify({{ ticks }}));
    """)
    ticks = got["ticks"][:3]
    assert len(set(ticks)) == 3, ticks


# ------------------------------------------------------------ analysis wording

def test_a_worst_week_headline_does_not_score_bullish():
    from app import news
    score, hits = news._score_text("Nasdaq 100 Records Worst Week In 18 Months As Investors Steer Clear Of Chipmakers")
    assert score < 0 and "+record" not in hits
    assert news._score_text("Apple hits record high")[0] > 0


def test_holder_counts_carry_their_scope_and_threshold():
    from app.analytics import fundamentals
    src = Path(fundamentals.__file__).read_text()
    assert '"holders_counted"' in src and '"holder_change_threshold_pct"' in src
    assert "raised and {} cut their stake by more than" in src


def test_an_unknown_session_is_never_called_closed():
    """Real Safari, 9:58 AM ET on a trading day (2026-10-19): the session read timed out on a cold server and
    the header said "Closed. Price is the close of the last session.\""""
    frame = _src("pages/dossier-frame.js")
    fn = frame[frame.index("export function stateLine"):frame.index("\n}\n", frame.index("export function stateLine"))]
    assert "QUOTE_PHASE[String(q.market_state" in fn, "the quote's own market state is used when the session has not answered"
    assert "else if (!phase) base = `Delayed about 15 minutes${last}.`;" in fn
    assert "|| 'Closed'" not in fn


def test_the_offline_notice_gives_way_when_the_server_answers():
    """iOS Safari (the simulator) said navigator.onLine was false while every request succeeded."""
    api = _src("core/api.js")
    assert "reachedAt = Date.now();" in api and "optic:reached" in api and "export const lastReached" in api
    st = _src("core/status.js")
    assert "Date.now() - api.lastReached() < 30000" in st and "addEventListener('optic:reached', offline)" in st


def test_a_reader_is_not_shown_the_operators_billing_setup(tmp_path):
    """Settings showed every reader "Billing is off: set STRIPE_SECRET_KEY, STRIPE_PRICE_ID, ...\""""
    got = _run(tmp_path, f"""
      const f = await import('{(JS / "core/format.js").as_posix()}');
      const r = 'Billing is off: set STRIPE_SECRET_KEY, STRIPE_PRICE_ID, STRIPE_WEBHOOK_SECRET.';
      print(JSON.stringify({{ reader: f.billingOff(r, false), owner: f.billingOff(r, true), none: f.billingOff('', false), plain: f.billingOff('Pro is sold out this week.', false) }}));
    """)
    assert got["reader"] == "Plans are not on sale yet. Every account is on Free."
    assert "STRIPE_SECRET_KEY" in got["owner"] and got["owner"].startswith("Plans are not on sale yet.")
    assert got["none"] == got["reader"] and got["plain"] == "Pro is sold out this week."
    for page in ("pages/settings.js", "pages/brokerage.js"):
        assert "billingOff(" in _src(page), page


def test_a_redraw_keeps_an_open_menu_open():
    """iOS Safari: a Dossier's ⋯ menu closed under the finger when the page's data arrived and redrew it."""
    dom = _src("core/dom.js")
    assert "details.menu[open]" in dom and "if (open.includes(menuKey(d))) d.open = true;" in dom
    ws = _src("pages/workspace.js")
    assert "matchMedia('(pointer: fine)').matches) again.focus()" in ws, "iOS reopens a select's menu when it is focused"
