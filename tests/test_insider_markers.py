"""Insider trades that can be seen on the chart, and opened from it.

Asked for with a screenshot of NVDA's chart: "make these insider trades more
visible on the chart". The triangles were 10px with a hairline stem, and the
labels coloured text on a dark box, three at most; on a green area fill the red
marks were easy to miss. Then: "whenever i click in the insider trades, take me
to a sub-tab of the insider buys/sells for that specific stock".

Checked in a browser on NVDA: the five September sales drew as four markers
with four badges at 10px a session ("2 sells · $306.9M" for the two a session
apart), the readout on Sep 2 named STEVENS MARK A and the $410.8M sale, and a
click on the marker opened Discover's Insiders page on NVDA, Buys and sells,
scrolled to the company's 25 Form 4 rows. Panned back to July, none of the
September sales were drawn on July 31, where all five had been.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
APP = (ROOT / "static/app.js").read_text()
CHARTS = (ROOT / "static/charts.js").read_text()
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc"


def _run(prelude, script):
    exe = JSC if os.path.exists(JSC) else shutil.which("jsc")
    if not exe:
        pytest.skip("no JavaScriptCore on this machine")
    out = subprocess.run([exe, "-e", prelude + script], capture_output=True, text=True,
                         timeout=120, cwd=str(ROOT))
    assert "RESULT:" in out.stdout, (out.stdout + out.stderr)[-2000:]
    return json.loads(out.stdout.split("RESULT:", 1)[1].split("\n")[0])


def _charts(script):
    return _run((ROOT / "tests/support/recording_dom.js").read_text() + CHARTS + """
      function days(n) { var o = []; for (var i = 0; i < n; i += 1) o.push(new Date(Date.UTC(2026, 6, 1) + i * 86400000).toISOString().slice(0, 10)); return o; }
      function boxes(tag, pred) { return NODES.filter(function (x) { return x.tag === tag && pred(x); }); }
    """, script)


def _app(script):
    return _run("""
      load('tests/support/browser_stubs.js');
      document.documentElement.style = document.documentElement.style || {};
      document.documentElement.style.setProperty = function () {};
      document.documentElement.style.removeProperty = function () {};
      try { load('static/charts.js'); load('static/app.js'); } catch (e) {}
    """, script)


_CHART = """
  var n = 60, labels = days(n), close = [];
  for (var i = 0; i < n; i += 1) close.push(100 + Math.sin(i / 6) * 8);
  function chart(events, extra) {
    NODES.length = 0;
    var opts = { width: 900, height: 420, labels: labels, events: events,
      series: [{ name: 'Close', values: close }] };
    for (var k in (extra || {})) opts[k] = extra[k];
    return lineChart(opts);
  }
  function badges() {
    return NODES.filter(function (x) { return x.tag === 'text' && /Sell|Buy|sells|buys/.test(x.children[0] || x.textContent || ''); })
      .map(function (x) { return x.children[0] || x.textContent; });
  }
  function textOf(x) { return String(x.textContent || ''); }
"""


# ------------------------------------------------------------------ the marks


def test_a_trade_is_a_ringed_triangle_on_a_stem_from_a_dot_on_the_price():
    out = _charts(_CHART + """
      // The light theme's red and green, set as syncChartTheme would after load:
      // a colour held in a constant from load kept the dark ones.
      C.neg = '#d13200'; C.s3 = '#1baf7a'; C.surface = '#fffdfb';
      var svg = chart([{ index: 20, kind: 'sell', value: 410.8e6, label: 'Sell $410.8M', detail: 'Insider sell' },
                       { index: 45, kind: 'buy', value: 2e6, label: 'Buy $2.0M', detail: 'Insider buy' }]);
      var f = svg.chartFrame;
      var tri = boxes('path', function (x) { return x.attrs['stroke-linejoin'] === 'round' && /^M [\\d.]+ [\\d.]+ L/.test(x.attrs.d); });
      var dots = boxes('circle', function (x) { return x.attrs.r === '3.5'; });
      print('RESULT:' + JSON.stringify({ tri: tri.map(function (t) { return [t.attrs.d, t.attrs.fill, t.attrs.stroke]; }),
        dots: dots.map(function (d) { return [Number(d.attrs.cy), Number(d.attrs.cx)]; }),
        priceY: [f.yOf(close[20]), f.yOf(close[45])], x: [f.xOf(20), f.xOf(45)], surface: C.surface, neg: C.neg, s3: C.s3 }));
    """)
    assert len(out["tri"]) == 2
    sell, buy = out["tri"]
    xs = [float(v) for v in sell[0].replace("M", "").replace("L", "").replace("Z", "").split()[::2]]
    assert max(xs) - min(xs) == pytest.approx(14), "14px wide, from 10"
    assert sell[1] == out["neg"] and buy[1] == out["s3"], "the trade's colour, read when drawn"
    assert sell[2] == buy[2] == out["surface"], "ringed in the surface colour"
    assert out["dots"][0] == pytest.approx([out["priceY"][0], out["x"][0]]), "a dot where the trade sits"
    tip_y = float(sell[0].split()[2])
    assert tip_y == pytest.approx(out["priceY"][0] - 10), "a sell's tip 10px above the price"
    buy_tip = float(buy[0].split()[2])
    assert buy_tip == pytest.approx(out["priceY"][1] + 10), "a buy's below it"


def test_badges_are_solid_in_the_trades_colour_and_as_many_as_fit():
    out = _charts(_CHART + """
      chart([0, 12, 24, 36, 48].map(function (i, k) { return { index: i, kind: 'sell', value: (5 - k) * 1e8,
        label: 'Sell $' + (5 - k) + '00.0M', detail: 'Insider sell' }; }));
      var pills = boxes('rect', function (x) { return x.attrs.rx === '8.5'; });
      print('RESULT:' + JSON.stringify({ badges: badges(), fills: pills.map(function (p) { return p.attrs.fill; }),
        ink: inkOn(C.neg), neg: C.neg, surface: C.surface,
        rects: pills.map(function (p) { return [Number(p.attrs.x), Number(p.attrs.y), Number(p.attrs.width), Number(p.attrs.height)]; }) }));
    """)
    assert len(out["badges"]) == 5, "five fit across 900px, where three was the rule"
    assert set(out["fills"]) == {out["neg"]}
    assert out["ink"] == out["surface"], "the dark surface reads on the dark theme's red"
    rects = out["rects"]
    for a in range(len(rects)):
        for b in range(a + 1, len(rects)):
            ax, ay, aw, ah = rects[a]
            bx, by, bw, bh = rects[b]
            assert not (ax < bx + bw and bx < ax + aw and ay < by + bh and by < ay + ah), "no two overlap"


def test_neighbouring_badges_find_room_rather_than_overlap():
    """Two sales two sessions apart at the same price: badged in the same
    place above each, the second would sit on the first."""
    out = _charts(_CHART + """
      for (var i = 0; i < n; i += 1) close[i] = 100 + (i % 7) * 0.4;
      close[28] = close[30] = close[32] = 101;
      chart([{ index: 28, kind: 'sell', value: 3e8, label: 'Sell $300.0M' },
             { index: 30, kind: 'sell', value: 2e8, label: 'Sell $200.0M' },
             { index: 32, kind: 'sell', value: 1e8, label: 'Sell $100.0M' }]);
      var pills = boxes('rect', function (x) { return x.attrs.rx === '8.5'; })
        .map(function (p) { return [Number(p.attrs.x), Number(p.attrs.y), Number(p.attrs.width), Number(p.attrs.height)]; });
      var tris = boxes('path', function (x) { return x.attrs['stroke-linejoin'] === 'round'; }).map(function (t) {
        var v = t.attrs.d.replace(/[MLZ]/g, ' ').trim().split(/\\s+/).map(Number);
        return [Math.min(v[0], v[2], v[4]), Math.min(v[1], v[3], v[5]), 14, Math.abs(v[3] - v[1])]; });
      print('RESULT:' + JSON.stringify({ pills: pills, tris: tris }));
    """)
    hit = lambda a, b: a[0] < b[0] + b[2] and b[0] < a[0] + a[2] and a[1] < b[1] + b[3] and b[1] < a[1] + a[3]
    pills, tris = out["pills"], out["tris"]
    assert pills, "at least the largest is named"
    for a in range(len(pills)):
        for b in range(a + 1, len(pills)):
            assert not hit(pills[a], pills[b]), "two badges overlap"
    for pill in pills:
        assert sum(1 for t in tris if hit(pill, t)) == 0, "a badge covers a marker"


def test_the_badge_count_follows_the_plot_width():
    out = _charts(_CHART + """
      var ev = [0, 6, 12, 18, 24, 30, 36, 42, 48, 54].map(function (i) { return { index: i, kind: 'sell', value: 1e8 + i,
        label: 'Sell $100.0M' }; });
      NODES.length = 0;
      lineChart({ width: 380, height: 420, labels: labels, events: ev, series: [{ name: 'Close', values: close }] });
      var narrow = badges().length;
      print('RESULT:' + JSON.stringify({ narrow: narrow }));
    """)
    assert out["narrow"] <= 2, "one a 150px of plot, two at least"


def test_trades_a_marker_apart_are_one_marker_with_their_count_and_total():
    out = _charts(_CHART + """
      var svg = chart([
        { index: 30, kind: 'sell', value: 300.1e6, label: 'Sell $300.1M', detail: 'Insider sell · $300.1M · STEVENS' },
        { index: 31, kind: 'sell', value: 6.8e6, label: 'Sell $6.8M', detail: 'Insider sell · $6.8M · TETER' },
        { index: 31, kind: 'buy', value: 1e6, label: 'Buy $1.0M', detail: 'Insider buy · $1.0M' }]);
      var tri = boxes('path', function (x) { return x.attrs['stroke-linejoin'] === 'round'; });
      var titles = NODES.filter(function (x) { return x.tag === 'title'; }).map(textOf);
      var small = boxes('circle', function (x) { return x.attrs.r === '2.5'; });
      print('RESULT:' + JSON.stringify({ tri: tri.length, badges: badges(), titles: titles, small: small.length,
        gap: svg.chartFrame.xOf(31) - svg.chartFrame.xOf(30) }));
    """)
    assert out["gap"] < 16, "closer than a marker is wide"
    assert out["tri"] == 2, "the two sells are one marker, and the buy is its own"
    assert "2 sells · $306.9M" in out["badges"] and "Buy $1.0M" in out["badges"]
    assert out["small"] == 1, "the smaller sale a dot on its own bar"
    assert any(t.startswith("2 insider sells\n") and "STEVENS" in t and "TETER" in t for t in out["titles"])


def test_a_sale_at_the_top_of_the_range_gets_room_above_it():
    out = _charts(_CHART + """
      var top = close.indexOf(Math.max.apply(null, close));
      var plain = chart(null).chartFrame;
      var f = chart([{ index: top, kind: 'sell', value: 1e8, label: 'Sell $100.0M' }]).chartFrame;
      var pill = boxes('rect', function (x) { return x.attrs.rx === '8.5'; })[0];
      var tri = boxes('path', function (x) { return x.attrs['stroke-linejoin'] === 'round'; })[0];
      print('RESULT:' + JSON.stringify({ plainHi: plain.hi, hi: f.hi, lo: f.lo, plainLo: plain.lo,
        pillBottom: Number(pill.attrs.y) + Number(pill.attrs.height), base: Number(tri.attrs.d.split(' ')[5]), top: f.margin.t }));
    """)
    assert out["hi"] > out["plainHi"], "the range grows above"
    assert out["lo"] == out["plainLo"], "and only above"
    assert out["pillBottom"] <= out["base"] - 3, "the badge directly over its triangle"


def test_nothing_moves_the_range_without_a_trade_near_an_edge():
    out = _charts(_CHART + """
      var plain = chart(null).chartFrame;
      var low = close.indexOf(Math.min.apply(null, close));
      var f = chart([{ index: low, kind: 'sell', value: 1e8, label: 'Sell $100.0M' }]).chartFrame;
      print('RESULT:' + JSON.stringify([plain.hi, f.hi, plain.lo, f.lo]));
    """)
    assert out[0] == out[1] and out[2] == out[3], "a sale at the low has all the room above it it needs"


def test_on_candles_a_sale_stands_over_the_high_and_a_buy_under_the_low():
    out = _charts(_CHART + """
      var high = close.map(function (c) { return c + 3; }), low = close.map(function (c) { return c - 3; });
      var svg = chart([{ index: 20, kind: 'sell', value: 1e8, label: 'Sell' }, { index: 40, kind: 'buy', value: 1e8, label: 'Buy' }],
        { candles: { open: close, high: high, low: low, close: close } });
      var f = svg.chartFrame;
      var dots = boxes('circle', function (x) { return x.attrs.r === '3.5'; }).map(function (d) { return Number(d.attrs.cy); });
      print('RESULT:' + JSON.stringify({ dots: dots, high: f.yOf(high[20]), low: f.yOf(low[40]) }));
    """)
    assert sorted(out["dots"]) == pytest.approx(sorted([out["high"], out["low"]]))


def test_the_readout_names_each_trade_on_its_bar_and_says_a_click_opens_them():
    hover = CHARTS[CHARTS.index("const traded = eventsAt.get(i) || [];"):]
    hover = hover[:hover.index("showTip(")]
    assert "traded.slice(0, 4).forEach((e) => {" in hover
    assert "escapeText(e.who || (buy ? 'Insider buy' : 'Insider sell'))" in hover, "who traded, escaped"
    assert "escapeText(e.label || (buy ? 'Buy' : 'Sell'))" in hover, "and how much"
    assert "if (traded.length && eventHint)" in hover
    events = APP[APP.index("function insiderEvents("):]
    assert "who: [t.insider, t.position].filter(Boolean).join(', ')," in events[:events.index("\n}\n")]


def test_a_click_on_a_marker_is_a_press_that_neither_moved_nor_held():
    block = CHARTS[CHARTS.index("  if (onEventClick) {\n    let pressed = null;"):]
    block = block[:block.index("  bindScrub(overlay")]
    assert "Math.abs(evt.clientX - p.x) > HOLD_SLOP || Math.abs(evt.clientY - p.y) > HOLD_SLOP" in block
    assert "|| Date.now() - p.t > HOLD_MS) return;" in block, "a hold is a measurement"
    assert "if (hit) onEventClick(hit.events, evt);" in block
    assert "overlay.style.cursor = eventAt(evt.clientX, evt.clientY) ? 'pointer' : 'crosshair';" in CHARTS
    assert CHARTS.index("const HOLD_SLOP = 4;") < CHARTS.index("  if (onEventClick) {\n    let pressed = null;")


def test_the_badge_ink_is_whichever_reads_better():
    out = _charts("""
      var dark = [inkOn(C.neg), inkOn(C.s3), C.surface];
      C.surface = '#fffdfb'; C.ink = '#14110e';
      var light = [inkOn('#d13200'), inkOn('#1baf7a'), inkOn('not a colour')];
      print('RESULT:' + JSON.stringify({ dark: dark, light: light }));
    """)
    assert out["dark"][0] == out["dark"][2] and out["dark"][1] == out["dark"][2], "surface on the dark theme's red and green"
    assert out["light"] == ["#fffdfb", "#14110e", "#14110e"], "white on light red, ink on light green"


# ------------------------------------------------------------------ the data


def test_a_trade_past_the_window_is_not_drawn_on_its_last_bar():
    out = _app("""
      var ps = { dates: ['2026-07-29', '2026-07-30', '2026-07-31'] };
      var tx = [{ date: '2026-07-30', action: 'sale', value: 6.5e6, insider: 'TETER TIMOTHY S', position: 'General Counsel' },
                { date: '2026-09-02', action: 'sale', value: 410.8e6, insider: 'STEVENS MARK A', position: 'Director' },
                { date: '2026-08-03', action: 'purchase', value: 1e6 }];
      var panned = insiderEvents(ps, tx, '2026-08-03');
      var newest = insiderEvents(ps, tx, '');
      var after = barAfterWindow({ dates: ['a', 'b', 'c', 'd'] }, { from: 0, to: 2 });
      var none = barAfterWindow({ dates: ['a', 'b', 'c', 'd'] }, { from: 1, to: 4 });
      print('RESULT:' + JSON.stringify({ panned: panned.map(function (e) { return [e.index, e.label, e.who]; }),
        newest: newest.map(function (e) { return [e.index, e.label]; }), after: after, none: none }));
    """)
    assert out["panned"] == [[1, "Sell $6.5M", "TETER TIMOTHY S, General Counsel"]]
    assert out["newest"] == [[1, "Sell $6.5M"], [2, "Sell $410.8M"], [2, "Buy $1.0M"]], (
        "on the newest bar, a later trade is that bar's, as it was")
    assert out["after"] == "c" and out["none"] == ""


def test_both_charts_pass_the_window_and_open_the_insiders_page():
    for host in ("swingPriceBlock", "wsMountChart"):
        body = APP[APP.index("function %s(" % host):]
        body = body[:body.index("\n}\n")]
        assert "barAfterWindow(" in body, host
        assert "onEventClick: showInsiders ? () => openInsidersFor(d.ticker) : null," in body, host
        assert "eventHint: showInsiders ? insiderClickHint(d.ticker) : ''," in body, host
    assert "barAfterWindow(swingBaseSeries(d), swingWindowNow(d))" in APP
    assert "barAfterWindow(wsBaseSeries(d), wsWindowNow(d))" in APP


def test_a_marker_opens_the_symbols_buys_and_sells():
    out = _app("""
      var went = [];
      switchView = function (v) { went.push(v); STATE.view = v; };
      insiderShow = 'all'; insiderTicker = 'HOOD'; STATE.insiders = { rows: [] };
      congressQuery = Object.assign({}, CONGRESS_BLANK, { ticker: 'HOOD', member: 'X', days: 90 });
      openInsidersFor('nvda');
      print('RESULT:' + JSON.stringify({ went: went, ticker: insiderTicker, show: insiderShow, feed: STATE.insiders,
        congress: congressQuery, pending: insidersScrollPending, hint: insiderClickHint('NVDA') }));
    """)
    assert out["went"] == ["insiders"]
    assert out["ticker"] == "NVDA" and out["show"] == "trades", "buys and sells, as asked"
    assert out["feed"] is None, "read again for the new symbol"
    assert out["congress"]["ticker"] == "NVDA" and out["congress"]["member"] == "", "as its Symbol box sets it"
    assert out["congress"]["days"] == 90, "the window the reader chose stays"
    assert out["pending"] is True
    assert out["hint"] == "Click the marker for NVDA's insider buys and sells"
    feed = APP[APP.index("async function loadInsiderFeed("):]
    assert "if (insidersScrollPending) showInsiderFilings(true);" in feed[:feed.index("\n}\n")]
    assert APP.count('id="ins-filings"') == 3, "the panel has the id in every state"


# ------------------------------------------------------------------ home card


def test_the_home_card_leads_with_prose_not_the_briefs_markdown():
    out = _app("""
      var got = readLead(['## What happened, and what it means',
        'Tech **held** the index up while *almost* everything else slipped.', 'More.']);
      var list = readLead(['## Heading', '- a list item', 'Prose after the list.']);
      var html = homeRead({ read: { summary: { headline: 'Tech holds the index up while almost everything else slips',
        paragraphs: ['## What happened, and what it means', 'Tech held the index up.'] } } });
      print('RESULT:' + JSON.stringify({ got: got, list: list, html: html, none: readLead(['## Only a heading']) }))
    """)
    assert out["got"] == "Tech held the index up while almost everything else slipped."
    assert out["list"] == "Prose after the list."
    assert "##" not in out["html"] and "What happened, and what it means" not in out["html"]
    assert "Tech held the index up." in out["html"]
    assert out["none"] == ""
