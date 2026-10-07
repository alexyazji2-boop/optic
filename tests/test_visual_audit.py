"""The terminal-wide visualization audit: what each chart now guarantees.

Asked for as "review every chart, graph, heatmap, visual score, sparkline,
timeline, and data visualization across Optic Terminal ... every visual must
earn its place", with every final visual keeping its exact values reachable
(tooltips, accessible labels, tables) and staying keyboard accessible. The
route-by-route fixes each have their own test file; this one holds the rules
that cut across routes.
"""
from __future__ import annotations

from tests.test_visual_primitives import _jsc as _prim

SHIMS = """
  El.prototype.querySelectorAll = function (sel) { var self = this, out = []; walk(this, function (n) { if (n !== self && n.tag === sel) out.push(n); }); return out; };
  El.prototype.querySelector = function (sel) { return this.querySelectorAll(sel)[0] || null; };
  El.prototype.insertBefore = function (c) { this.children.unshift(c); return c; };
  El.prototype.removeChild = function (c) { this.children = this.children.filter(function (x) { return x !== c; }); return c; };
"""


def test_a_chart_marker_is_reached_from_the_keyboard_not_only_by_a_pointer():
    """An earnings date marked on a price chart said what it was in a native
    <title>, which a pointer can show and a keyboard cannot reach."""
    out = _prim(SHIMS + """
      var root = lineChart({ width: 500, height: 200, labels: ['a', 'b', 'c', 'd'],
        series: [{ name: 'Close', values: [1, 2, 3, 4], color: C.pos }],
        vMarkers: [{ index: 1, label: 'E', detail: 'Earnings report 2026-07-28: beat by 4%' }, { index: 2, label: 'X' }] });
      var marks = all(root, function (n) { return n.attrs && n.attrs.tabindex === '0' && n.attrs.role === 'img'; });
      R.labels = marks.map(function (n) { return n.attrs['aria-label']; });
      R.focus = marks.length ? !!marks[0].listeners.focus && !!marks[0].listeners.blur : false;
      R.hover = marks.length ? !!marks[0].listeners.pointermove || !!marks[0].listeners.mousemove : true;
    """)
    assert out["labels"] == ["Earnings report 2026-07-28: beat by 4%"], "a marker with nothing to say is not a stop"
    assert out["focus"] is True
    assert out["hover"] is False, "no hover binding to fight the crosshair"


def test_a_line_chart_is_read_point_by_point_from_the_keyboard():
    """A chart's figures were reachable only by pointing at them. The plot is a
    slider over its bars now: one stop, the arrow keys move a bar, Shift ten,
    Home and End the ends, and the value is the slider's text."""
    out = _prim(SHIMS + """
      var root = lineChart({ width: 500, height: 200, labels: ['2026-10-01', '2026-10-02', '2026-10-05'],
        series: [{ name: 'Close', values: [101.5, 102.25, 99.75], color: C.pos }], yFormat: function (v) { return v.toFixed(2); } });
      var slider = all(root, function (n) { return n.attrs && n.attrs.role === 'slider'; })[0];
      R.label = slider.attrs['aria-label']; R.max = slider.attrs['aria-valuemax']; R.tab = slider.attrs.tabindex;
      slider.listeners.focus[0]();
      R.atFocus = slider.attrs['aria-valuetext'];
      var key = function (k, shift) { slider.listeners.keydown[0]({ key: k, shiftKey: !!shift, preventDefault: function () {} }); return slider.attrs['aria-valuetext']; };
      R.left = key('ArrowLeft'); R.home = key('Home'); R.end = key('End'); R.past = key('ArrowRight', true);
      R.now = slider.attrs['aria-valuenow'];
    """)
    assert out["label"] == "Close, point by point" and out["max"] == "3" and out["tab"] == "0"
    assert out["atFocus"].endswith(": Close 99.75"), "focus starts at the latest point"
    assert out["left"].endswith(": Close 102.25") and out["home"].endswith(": Close 101.50")
    assert out["end"] == out["past"] and out["now"] == "3", "a step past the end stays on it"


def test_a_chart_is_a_group_its_marks_can_be_announced_in_and_decoration_is_hidden():
    """Every chart root was role="img", and ARIA makes an image's children
    presentational: the focusable marks inside were reached and not read."""
    out = _prim("""
      R.root = divergingBars({ width: 400, rows: [{ label: 'A', value: 2 }, { label: 'B', value: -1 }] }).attrs.role;
      R.bar = inlineBar(3, 5).attrs['aria-hidden'];
      R.spark = sparkline([1, 2, 3]).attrs['aria-hidden'];
    """)
    assert out == {"root": "group", "bar": "true", "spark": "true"}


def test_the_rotation_and_bubble_charts_are_read_from_the_keyboard():
    """Both said their figures on mouseenter only: eleven sectors on the
    rotation chart and every name on a stock map's bubble chart were
    pointer-only, and their names went into the tooltip unescaped."""
    out = _prim("""
      var rot = rotationChart([{ symbol: 'XLK', name: 'Tech & <b>Co</b>', quadrant: 'leading', d_strength: 0.4, d_momentum: 0.2,
        path: [{ strength: 101, momentum: 100.5, date: '2026-09-25' }, { strength: 102, momentum: 101, date: '2026-10-02' }] }],
        { width: 500, height: 400 });
      var bub = bubbleChart([{ label: 'AAA', name: 'A & B', x: 1, y: 2, size: 5 }, { label: 'BBB', x: 2, y: 1, size: 3 }],
        { width: 500, height: 300, xLabel: 'P/E', yLabel: 'Growth', yUnit: '%' });
      var marks = function (root) { return all(root, function (n) { return n.attrs && n.attrs.tabindex === '0'; }); };
      R.rot = marks(rot).map(function (n) { return n.attrs['aria-label']; });
      R.bub = marks(bub).map(function (n) { return n.attrs['aria-label']; });
      marks(rot)[0].listeners.focus[0]();
      R.tip = TIPS[TIPS.length - 1];
    """)
    assert out["rot"] == ["XLK Tech & <b>Co</b>: leading, strength 102.00, momentum 101.00"]
    assert sorted(out["bub"]) == ["AAA: P/E 1.00, Growth 2.00%", "BBB: P/E 2.00, Growth 1.00%"]
    assert "&lt;b&gt;" in out["tip"] and "<b>Co</b>" not in out["tip"], "a name is text, not markup"


def _app(script):
    import json
    import os
    import shutil
    import subprocess
    from pathlib import Path

    import pytest

    root = Path(__file__).resolve().parent.parent
    jsc = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc"
    exe = jsc if os.path.exists(jsc) else shutil.which("jsc")
    if not exe:
        pytest.skip("no JavaScriptCore on this machine")
    src = """
      load('tests/support/browser_stubs.js');
      document.documentElement.style = document.documentElement.style || {};
      document.documentElement.style.setProperty = function () {};
      document.documentElement.style.removeProperty = function () {};
      try { load('static/charts.js'); load('static/app.js'); } catch (e) {}
      var R = {};
    """ + script + "\nprint('RESULT:' + JSON.stringify(R));"
    out = subprocess.run([exe, "-e", src], capture_output=True, text=True, timeout=60, cwd=str(root))
    blob = out.stdout + out.stderr
    assert "RESULT:" in blob, blob[-2000:]
    return json.loads(blob.split("RESULT:", 1)[1].split("\n")[0])


def test_a_chart_with_nothing_to_draw_leaves_no_empty_box():
    out = _app("""
      var host = { clientWidth: 480, style: { minHeight: '160px' }, innerHTML: 'old', appendChild: function () {} };
      R.done = buildChartNow(host, function () { return null; });
      R.min = host.style.minHeight; R.html = host.innerHTML;
    """)
    assert out["done"] is True and out["min"] == "", "the 160px held open for a redraw is given back"


# ------------------------------------------------------------ per-route findings

def test_an_area_is_filled_only_down_to_a_zero_the_axis_shows():
    """Filled to the plot's floor, a ratio near 1.0 shaded a block whose size
    meant nothing. A change series that crosses zero keeps its fill."""
    out = _prim(SHIMS + """
      function fills(values) {
        var root = lineChart({ width: 400, height: 160, labels: values.map(function (v, i) { return 'd' + i; }),
          series: [{ name: 'S', values: values, color: C.brand, fill: true }] });
        return all(root, function (n) { return n.tag === 'path' && n.attrs.opacity === '0.1'; }).length;
      }
      R.level = fills([1.02, 1.05, 1.04, 1.08]); R.change = fills([-2, 1, 3, -1]);
    """)
    assert out["level"] == 0 and out["change"] == 1


def test_a_resumed_pulse_answer_is_painted_as_a_live_one():
    app = __import__("pathlib").Path(__file__).resolve().parent.parent.joinpath("static/app.js").read_text()
    body = app[app.index("function pulseResume(id) {"):]
    body = body[:body.index("\n}\n")]
    assert "addMsg('assistant', m.content)" in body and "? 'user' : 'bot'" not in body
    assert "addReplyActions(node, m.content || '', asked)" in body


def test_retirement_draws_drift_without_a_side_and_shares_from_zero():
    out = _app("""
      var calls = [];
      inlineBar = function (v, max, w, h, opts) { calls.push([v, max, opts || {}]); return { tag: 'svg' }; };
      var hosts = [{ dataset: { bar: '-6', barMax: '25' }, appendChild: function () {} },
                   { dataset: { bar: '100', barMax: '100', barKind: 'share' }, appendChild: function () {} }];
      rothHost = function () { return { querySelectorAll: function () { return hosts; } }; };
      var src = renderRoth.toString();
      R.drift = src.indexOf("share ? { oneSided: true } : { neutral: true }") > 0;
      R.share = src.indexOf('data-bar-kind="share"') > 0;
      R.dashed = (src.match(/dash: '5 4'/g) || []).length;
      R.window = src.indexOf('years every one of these funds has traded through') > 0 && src.indexOf('over ten years') < 0;
    """)
    assert out["drift"] and out["share"] and out["dashed"] == 3 and out["window"]


def test_the_retirement_correlation_window_is_published():
    import pandas as pd
    from app.analytics import retirement
    idx = pd.bdate_range("2024-01-01", periods=300)
    frames = {s: pd.DataFrame({"Close": [100 + i * (k + 1) * 0.1 for i in range(300)]}, index=idx)
              for k, s in enumerate(("AAA", "BBB"))}
    frames["BBB"] = frames["BBB"].iloc[100:]                    # the younger fund sets the window
    got = retirement._correlations(frames, ["AAA", "BBB"])
    assert got["sessions"] == 199 and got["start"] == str(idx[101].date()) and got["end"] == str(idx[-1].date())


def test_the_paper_desk_names_every_segment_and_says_which_marks_are_a_models():
    out = _app("""
      paperBook = { open: [], closed: [] };
      ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H'].forEach(function (t, i) {
        paperBook.open.push({ id: 'p' + i, ticker: t, direction: t === 'B' ? 'short' : 'long', instrument: 'shares' });
      });
      var h = { total: 100, ranked: [['A', 30], ['B', 20], ['C', 15], ['D', 10], ['E', 10], ['F', 5], ['G', 6], ['H', 4]],
                open: paperBook.open, marked: 8 };
      R.parts = paperExposureParts(h).map(function (x) { return [x.name, Math.round(x.share * 100)]; });
      paperMarks = { p0: { mark_source: 'Modelled (no live quote)' }, p1: { mark_source: 'Live chain mid' } };
      STATE.health = { realtime_chain: true };
      R.chip = paperMarkStateHTML(h);
    """)
    assert out["parts"] == [["A", 30], ["B short", 20], ["C", 15], ["D", 10], ["E", 10], ["F", 5], ["2 others", 10]]
    assert "1 option estimated by a model" in out["chip"] and "is-delayed" in out["chip"]


def test_a_scan_ratio_is_drawn_against_its_whole_and_the_evaluation_says_its_span():
    out = _app("""
      var calls = [];
      inlineBar = function (v, max, w, h, opts) { calls.push(max); return { tag: 'svg' }; };
      function cell(v) { return { dataset: { scanBar: String(v), kind: 'ratio' }, appendChild: function () {} }; }
      var set = [cell(0.4), cell(0.2)];
      fillScanBars({ querySelectorAll: function () { return set; } });
      R.max = calls; R.span = [evalPeriod({ period: '2y' }), evalPeriod({ period: '6mo' }), evalPeriod({})];
    """)
    assert out["max"] == [1, 1], "a share of the 52-week range is out of 1, not the list's largest"
    assert out["span"] == ["two years", "6 months", ""]


def test_the_watchlist_line_is_said_in_words_and_its_column_counts_sessions():
    out = _app("""
      R.row = watchRow({ symbol: 'AAA', available: true, price: 10, change_pct: -1, spark: [100, 104, 110], signal: 'bullish' }, {});
      R.slot = sparkSlot([100, 110]);
    """)
    assert "-1.00% today, +10.0% over 3 sessions" in out["row"]
    assert 'title="Last 2 sessions, +10.0%"' in out["slot"]
    app = __import__("pathlib").Path(__file__).resolve().parent.parent.joinpath("static/app.js").read_text()
    assert "<span>30 sessions</span>" in app and "<span>30 days</span>" not in app


def test_the_trades_per_day_chart_says_its_window_scale_and_figures():
    out = _app("""
      R.html = congressActivityChart([{ date: '2026-09-01', buys: 2, sells: 1, other: 0 },
        { date: '2026-09-02', buys: 0, sells: 4, other: 1 }], 30);
    """)
    assert "the busiest day, Sep 2, had 5." in out["html"] and "2 bought, 5 sold, 1 other" in out["html"]
    assert "tallest bar 5 on Sep 2" in out["html"]


# ------------------------------------------------------------ Markets and the Read

def _src(name):
    app = __import__("pathlib").Path(__file__).resolve().parent.parent.joinpath("static/app.js").read_text()
    i = app.index(name)
    return app[i:app.index("\n}\n", i)]


def test_the_economic_series_and_bubble_map_survive_a_re_render():
    """renderMarket rebuilds their hosts on every 20-second refresh, resize and
    return to the tab, and only their loaders drew them, which return early from
    cache: both charts went empty. The loaders also wrote into the host captured
    before the request, which a re-render had replaced."""
    body = _src("function renderMarket(d) {")
    assert "mountEconChart();" in body and "mountStockMapChart();" in body
    for loader, host in (("async function loadEcon(", "econ-host"), ("async function loadStockMap(", "stockmap-host")):
        src = _src(loader)
        after = src[src.index("await getJSON"):]
        assert f"document.getElementById('{host}')" in after, loader


def test_the_economic_chart_says_its_unit():
    out = _app("""
      var got = null;
      mount = function (id, build) { got = build(500); };
      lineChart = function (o) { return o; };
      STATE.econ = { values: [3.1, 3.4], dates: ['2026-08-01', '2026-09-01'], unit: '%', label: 'CPI', form_label: 'year on year', min: 3.1 };
      mountEconChart();
      R.y = got.yFormat(3.4); R.v = got.valueFormat(3.4); R.aria = got.ariaLabel;
    """)
    assert out == {"y": "3.4%", "v": "3.40%", "aria": "CPI, year on year"}


def test_the_fear_and_greed_marker_and_band_names_sit_where_they_mean():
    css = __import__("pathlib").Path(__file__).resolve().parent.parent.joinpath("static/styles.css").read_text()
    rule = css[css.index(".fg-marker {"):]
    rule = rule[:rule.index("}")]
    assert rule.count("transform:") == 1 and "translate(-50%, -50%)" in rule, "a second transform replaced the first"
    body = _src("function renderSentiment(f) {")
    for at, name in (("12.5", "Extreme fear"), ("35", "Fear"), ("50", "Neutral"), ("65", "Greed"), ("87.5", "Extreme greed")):
        assert f'<span style="left:{at}%">{name}</span>' in body, name
    assert "[25, 45, 55, 75]" in body, "a tick where each band starts"


def test_the_regime_says_each_inputs_scale_and_does_not_overstate_agreement():
    from app.analytics import regime
    got = regime.score({"groups": {
        "indices": [{"symbol": "SPY", "week": 3.0, "month": 11.0}, {"symbol": "IWM", "month": 1.0},
                    {"symbol": "^VIX", "last": 22.0, "day": 0.0}],
        "sectors": [{"day": 0.5}, {"day": -0.4}, {"day": 0.2}, {"day": -0.1}, {"day": 0.3}]},
        "sector_breadth_pct": 50.0})
    assert got["clipped"] == ["participation", "trend"], "a 7% average is past the 5% limit; small caps 10 points behind past 4"
    assert set(got["scales"]) == set(got["components"])
    out = _app("""
      R.mixed = briefRegime({ available: true, score: 5, components: { trend: 40, breadth: -30, volatility: 5 },
        weights: { trend: 40, breadth: 30, volatility: 30 }, agreement_pct: 67, conflicts: [],
        scales: { trend: '0 when flat' }, clipped: ['trend'] });
      R.all = briefRegime({ available: true, score: 30, components: { trend: 40, breadth: 30 },
        weights: { trend: 50, breadth: 50 }, agreement_pct: 100, conflicts: [] });
    """)
    assert "2 of 3 inputs point the same way" in out["mixed"] and "All 3" not in out["mixed"]
    assert "Scored 0 when flat." in out["mixed"] and "at the limit" in out["mixed"]
    assert "All 2 inputs point the same way as the composite." in out["all"]


def test_a_rise_is_never_painted_red_and_the_map_is_reached_from_the_keyboard():
    out = _app("""
      var dom = { min: 1, max: 9, higher_is_better: true };
      R.rise = mapColour(2, dom, '%'); R.pos = C.pos;
      R.pe = mapColour(30, { min: 10, max: 40, higher_is_better: false }, 'x'); R.neg = C.neg;
      R.html = renderStockMap({ template: { shape: 'tile', label: 'Sectors this month', color: 'chg_20d', size: 'market_cap' },
        measures: { chg_20d: { label: '20-day change', unit: '%' }, market_cap: { label: 'Market cap', unit: '$' } },
        colour_domain: dom, drillable: ['XLK'], templates: [],
        layout: [{ symbol: 'XLK', name: 'Technology', x: 0, y: 0, w: 50, h: 50, values: { chg_20d: 2, market_cap: 1e12 } }] });
    """)
    assert out["pos"] in out["rise"], "a 2% rise in a month when everything rose is green, not red"
    assert out["neg"] in out["pe"], "a multiple still diverges around the middle of its range"
    html = out["html"]
    assert 'role="group"' in html and 'role="img"' not in html
    assert 'tabindex="0" role="button" aria-label="Technology (XLK): 20-day change +2.0%, Market cap' in html
    assert "Opens its holdings" in html and "Green above zero and red below" in html


def test_a_panel_loaded_once_says_when():
    out = _app("""
      var x = stampFetched({ a: 1 });
      R.keys = Object.keys(x); R.line = fetchedLine(x); R.none = fetchedLine({});
    """)
    assert out["keys"] == ["a"], "the stamp is not part of the payload"
    assert "Fetched at" in out["line"] and "does not refresh on its own" in out["line"] and out["none"] == ""
    for name in ("function renderCorrelation(", "function renderSentiment(", "function renderSectorBoard(",
                 "function renderForex(", "function renderStockMap(", "function renderEcon("):
        assert "fetchedLine(" in _src(name), name


def test_the_rotation_chart_names_its_axes_and_draws_nothing_without_tracks():
    out = _prim("""
      var root = rotationChart([{ symbol: 'XLK', name: 'Tech', quadrant: 'leading', d_strength: 0, d_momentum: 0,
        path: [{ strength: 101, momentum: 100.5, date: '2026-09-25' }, { strength: 102, momentum: 101, date: '2026-10-02' }] }],
        { width: 600, height: 420, asOf: '2026-10-02' });
      R.labels = texts(root); R.aria = root.attrs['aria-label'];
      R.none = rotationChart([], { width: 600 });
    """)
    assert "Relative strength, 100 is its own norm →" in out["labels"] and "Relative momentum →" in out["labels"]
    assert "to 2026-10-02" in out["aria"] and out["none"] is None


def test_the_sector_table_lost_its_decoration_and_pairs_do_not_call_a_reversal():
    body = _src("function renderMarket(d) {")
    assert "<th>Composite</th><th></th>" not in body and "data-bar=\"${r.composite}\"" not in body
    assert "'z-stretched'" in body and "signClass(-p.zscore_60d)" not in body
    assert "<th>90 sessions</th>" in body


# ------------------------------------------------------------ Options, the Chart, the Dossier

def test_a_strike_is_not_read_as_a_year():
    """The gamma profile's spot prices went to new Date(): its axis read
    "Jan, 1973 ... 1989" for an $80 stock. A strike is a category."""
    out = _prim(SHIMS + """
      R.num = parseBarDate('185'); R.date = !!parseBarDate('2026-10-07'); R.stamp = !!parseBarDate('2026-10-07T14:30:00');
      var root = lineChart({ width: 500, height: 160, labels: ['80', '85', '90', '95', '100'],
        series: [{ name: 'Net GEX', values: [-2, -1, 0, 1, 2], color: C.brand }] });
      R.labels = texts(root);
    """)
    assert out["num"] is None and out["date"] and out["stamp"]
    assert "80" in out["labels"] and "90" in out["labels"] and "100" in out["labels"]
    assert not any(l.startswith(("Jan", "1973")) for l in out["labels"])


def test_the_rsi_axis_reads_the_lines_it_draws_and_price_axes_carry_their_decimals():
    out = _prim(SHIMS + """
      var rsi = lineChart({ width: 400, height: 200, labels: ['a', 'b', 'c'], yDomain: [10, 90], yTicks: [30, 50, 70],
        series: [{ name: 'RSI', values: [40, 55, 62], color: C.brand }], yFormat: function (v) { return String(Math.round(v)); } });
      R.rsi = texts(rsi);
      var steps = [];
      lineChart({ width: 400, height: 300, labels: ['a', 'b', 'c', 'd'], series: [{ name: 'P', values: [3.1, 3.6, 4.4, 3.9], color: C.brand }],
        yFormat: function (v, step) { steps.push(step); return v.toFixed(2); } });
      R.steps = steps.filter(function (x) { return x !== undefined; });
    """)
    assert "30" in out["rsi"] and "70" in out["rsi"] and "25" not in out["rsi"] and "75" not in out["rsi"]
    assert out["steps"] and all(abs(x - out["steps"][0]) < 1e-9 for x in out["steps"]), "the step goes to the formatter"
    got = _app("R.a = priceAxisLabel(3.5, 0.5); R.b = priceAxisLabel(182, 5); R.c = priceAxisLabel(3.55, 0.05);")
    assert got == {"a": "3.5", "b": "182", "c": "3.55"}


def test_a_candles_prices_are_read_at_the_readouts_precision():
    src = __import__("pathlib").Path(__file__).resolve().parent.parent.joinpath("static/charts.js").read_text()
    assert "rows.push(['Open', (valueFormat || yFormat)(o)]);" in src


def test_the_macd_pane_is_read_from_the_keyboard_and_takes_the_theme():
    out = _prim(SHIMS + """
      var root = macdChart([0.1, 0.3, -0.2], [0.05, 0.2, 0.0], [0.05, 0.1, -0.2], ['2026-10-01', '2026-10-02', '2026-10-05'], 500);
      var slider = all(root, function (n) { return n.attrs && n.attrs.role === 'slider'; })[0];
      slider.listeners.focus[0]();
      R.text = slider.attrs['aria-valuetext'];
      var before = C.s3; C.s3 = '#123456';
      var again = macdChart([0.1, 0.3], [0.05, 0.2], [0.05, 0.1], ['2026-10-01', '2026-10-02'], 500);
      R.fills = all(again, function (n) { return n.tag === 'rect' && n.attrs.fill === '#123456'; }).length;
      C.s3 = before;
    """)
    assert out["text"].endswith("MACD -0.200, signal 0.000, histogram -0.200")
    assert out["fills"] >= 1, "the histogram reads the theme when it is drawn"


def test_the_options_charts_say_which_strikes_and_expiries_they_are_drawn_from():
    out = _app("""
      R.scope = chainScope({ expiries: { used: ['2026-10-16', '2026-10-23', '2026-11-20'] } });
      R.one = chainScope({ expiries: { used: ['2026-10-16'] } });
      R.none = chainScope({});
      R.k = [strikeLabel(185), strikeLabel(182.5), strikeLabel(7.25)];
    """)
    assert out["scope"] == "3 expiries, Oct 16 to Nov 20" and out["one"] == "the Oct 16 expiry" and out["none"] == ""
    assert out["k"] == ["$185", "$182.50", "$7.25"], "two half-dollar strikes no longer share a label"
    swing = _src("function renderSwing(d) {")
    # Time value bought, not the whole price (tests/test_flow_time_value.py).
    assert "strikes with the most dealer" in swing and "strikes with the most time value bought" in swing
    assert "No strike carries gamma in the expiries used." in swing
    vis = _src("function mountOptionsVisuals(d) {")
    assert "max: 100, format: (v) => fmt(v, 1) + '%', ariaLabel: expiryGammaTitle(gk)" in vis
    assert "highlightLast: false" in vis and "unit: 'contracts'" in vis
    assert "label: fmt(r.strike, 0)" not in swing + vis


def test_the_price_charts_key_and_captions_say_what_is_drawn():
    block = _src("function swingPriceBlock(d, ps, ctx) {")
    assert "{ name: 'Fibonacci level', color: C.refFib }" in block
    assert "{ name: 'Support band', color: C.pos, boxed: true }" in block
    assert "name: 'Support / resistance'" not in block
    swing = _src("function renderSwing(d) {")
    assert "are left off rather than redrawn" not in swing and "is computed from these same bars" in swing


def test_panels_draw_only_the_stock_on_screen():
    swing = _src("function renderSwing(d) {")
    assert "STATE.seasonalityFor === STATE.ticker ? STATE.seasonality : null" in swing
    assert "STATE.relperfKey === STATE.ticker ? STATE.relperf : null" in swing
    assert "mountRelPerfChart();" in swing, "the chart is drawn again on each render, which rebuilds its host"
    for loader, guard in (("async function loadSeasonality(", "if (STATE.seasonalityFor !== sym) return;"),
                          ("async function loadRelPerf(", "if (STATE.relperfKey !== sym) return;"),
                          ("async function loadAccumZones(", "if (STATE.accumZonesFor !== sym) return;")):
        assert guard in _src(loader), loader


def test_seasonality_colours_only_what_clears_the_bar():
    out = _app("R.sig = seasBar(0.4, 1, 'significant'); R.noise = seasBar(0.4, 1, 'noise');")
    assert 'class="up"' in out["sig"] and 'class="faint"' in out["noise"]


def test_the_revenue_and_multiple_panel_has_no_second_axis():
    out = _app("""
      R.html = renderRevenueMultiple({ available: true, revenue_cagr_pct: 9, method: 'm',
        years: [{ label: '2024', revenue: 100e9, pe: 30 }, { label: '2025', revenue: 120e9, pe: 25 }] });
    """)
    html = out["html"]
    assert "rm-chart" not in html and 'id="viz-rm-rev"' in html and 'id="viz-rm-pe"' in html
    assert "multiple compressed from 30.0 to 25.0" in html and "Exact figures" in html
    assert "renderRevenueMultiple(" in _src("function renderLong(d) {"), "the Investing tab still draws it"


def test_redundant_charts_are_gone_and_the_rest_say_their_source():
    assert "fv-split" not in _src("function renderAnalystsBlock(a) {")
    company = _src("function renderCompany(co) {")
    assert "vizBlock('viz-fin-insiders'" not in company
    app = __import__("pathlib").Path(__file__).resolve().parent.parent.joinpath("static/app.js").read_text()
    assert "vizMount('viz-fin-insiders'" not in app
    out = _app("""
      R.yahoo = priceSourceName({ data_source: 'yfinance' }); R.tradier = priceSourceName({ data_source: 'tradier' });
    """)
    assert out["yahoo"] == "Yahoo Finance" and out["tradier"].startswith("Tradier")
    assert 'role="group" aria-label="${esc(row.symbol)} with the ${' in app


def test_a_negative_dollar_figure_carries_its_sign_ahead_of_the_symbol():
    """'$' + fmtCompact printed a net gamma of minus 25 million as "$-25.0M"."""
    out = _prim("R.v = [usdCompact(-25e6), usdCompact(25e6), usdCompact(0), usdCompact(null), usdCompact(1.234e9, 2)];")
    assert out["v"] == ["-$25.0M", "$25.0M", "$0", "\u2014", "$1.23B"]
    # Where a figure can be negative. A trade's value cannot, and is left as it was.
    for fn in ("function renderSwing(d) {", "function renderCompany(co) {", "function mountEarningsVisuals(d) {"):
        assert "'$' + fmtCompact(" not in _src(fn), fn
    earnings = _src("function renderEarnings(d) {")
    assert "<td>${usdCompact(r.net_income)}</td>" in earnings and "$${fmtCompact(r.net_income)}" not in earnings
    assert "usdCompact((gex.totals || {}).net_gex)" in _src("function renderSwing(d) {")


def test_the_price_marker_on_a_bar_chart_has_a_row_of_its_own():
    """"spot 16" printed across the "$16" strike label above it, and rounded a
    $15.76 price to the strike it was drawn beside."""
    out = _prim(SHIMS + """
      var rows = [{ label: '$1,240', value: 4 }, { label: '$1,237.50', value: -2 }, { label: '$1,235', value: 1 }];
      var root = divergingBars({ width: 600, rows: rows, markerRow: 1, markerLabel: 'price $1,238.12' });
      var t = all(root, function (n) { return n.tag === 'text'; });
      var y = function (label) { return Number(t.filter(function (n) { return n.textContent === label; })[0].attrs.y); };
      var mark = t.filter(function (n) { return n.textContent === 'price $1,238.12'; })[0];
      var line = all(root, function (n) { return n.tag === 'line' && n.attrs['stroke-dasharray'] === '4 3'; })[0];
      R.gapAbove = Number(mark.attrs.y) - y('$1,240'); R.gapBelow = y('$1,237.50') - Number(mark.attrs.y);
      R.anchor = mark.attrs['text-anchor']; R.markX = Number(mark.attrs.x);
      R.lineEnd = Number(line.attrs.x2); R.labelLeft = 600 - 2 - textWidthGuess('price $1,238.12', CF.tick);
      R.labelX = t.filter(function (n) { return n.textContent === '$1,237.50'; })[0].attrs.x;
      R.labelRoom = textWidthGuess('$1,237.50', CF.tick);
    """)
    assert out["gapAbove"] >= 14 and out["gapBelow"] >= 14, "the marker's label clears the rows on both sides"
    assert out["anchor"] == "end" and out["markX"] == 598 and out["lineEnd"] < out["labelLeft"]
    assert float(out["labelX"]) - out["labelRoom"] >= 0, "the widest strike is not cut off at the left edge"
    swing = _src("function renderSwing(d) {")
    assert "markerLabel: `price ${usd(d.quote.price)}`" in swing and "spot ${fmt(d.quote.price, 0)}" not in swing


def test_the_workspace_rsi_axis_reads_whole_numbers():
    panes = _src("function wsMountPanes(ps) {")
    rsi = panes[panes.index("mount('ws-pane-rsi'"):panes.index("if (wsPaneOpen('macd')")]
    assert "yTicks: [30, 50, 70]" in rsi and "yFormat: (x) => fmt(x, 0)" in rsi and "valueFormat: (x) => fmt(x, 1)" in rsi


def test_the_dock_seasonality_draws_a_loss_below_the_line_and_colours_only_a_finding():
    out = _app("""
      var sn = { years: 15, monthly: { rows: [
        { label: 'January', short: 'Jan', raw: { n: 15, mean: 3.95, hit_rate: 53.3, verdict: 'noise' } },
        { label: 'February', short: 'Feb', raw: { n: 15, mean: -2.1, hit_rate: 40, verdict: 'significant' } },
        { label: 'March', short: 'Mar', raw: { n: 15, mean: 1.2, hit_rate: 60, verdict: 'unproven' } } ] } };
      R.html = wsSeasonalityMini(sn);
    """)
    html = out["html"]
    cols = html.split('class="ws-seas-col"')[1:]
    assert '<span class="ws-seas-half up"><span class="ws-seas-bar faint"' in cols[0]
    assert '<span class="ws-seas-half up"></span>' in cols[1] and '<span class="ws-seas-half down"><span class="ws-seas-bar down"' in cols[1]
    assert "ws-seas-bar up" not in html, "a month that is noise or unproven is not drawn as a finding"
    assert 'role="img"' in html and "February: mean -2.10% over 15 years, up in 40% of them, significant" in html
    assert "Exact figures" in html and "<td>unproven</td>" in html
    assert "Swing tab" not in html and "the Options tab" in html


def test_an_open_indicator_pane_with_too_few_bars_says_so():
    out = _app("""
      var M = {}; wsPanesOpen = ['rsi', 'macd'];
      vizMount = function (id, build, none) { M[id] = build(600) || none; };
      wsPaneLegend = function () {};
      wsMountPanes({ dates: ['2026-10-06', '2026-10-07'], close: [1, 2] });
      R.m = M;
    """)
    assert out["m"] == {"ws-pane-rsi": "RSI is drawn from 30 bars up, and this range has fewer.",
                        "ws-pane-macd": "MACD is drawn from 30 bars up, and this range has fewer."}


def test_the_three_month_rank_is_drawn_on_its_own_dates():
    """The 3-month rank starts later than the 1-month one and both end today.
    Drawn by index against the 1-month dates, it ended two months early while
    its tag read today's rank."""
    out = _app("""
      var CAP = [];
      mount = function (id, build) { build(600); };
      lineChart = function (o) { CAP.push(o); return null; };
      STATE.ticker = 'NVDA';
      STATE.relperf = { available: true, ticker: 'NVDA', universe_size: 142, windows: {
        '1m': { available: true, window_days: 21, dates: ['2026-08-03', '2026-08-04', '2026-08-05', '2026-08-06'], series: [50, 60, 70, 83] },
        '3m': { available: true, window_days: 63, dates: ['2026-08-05', '2026-08-06'], series: [80, 87] } } };
      mountRelPerfChart();
      R.labels = CAP[0].labels; R.series = CAP[0].series.map(function (s) { return [s.name, s.values]; });
      R.head = relPerfChartHead(STATE.relperf);
    """)
    assert out["labels"] == ["2026-08-03", "2026-08-04", "2026-08-05", "2026-08-06"]
    assert out["series"] == [["1-month rank", [50, 60, 70, 83]], ["3-month rank", [None, None, 80, 87]]]
    head = out["head"]
    assert "Where NVDA has ranked against 142 peers each session, Aug '26 to Aug '26" in head
    assert "1-month rank, 21 sessions" in head and "3-month rank, 63 sessions" in head
    assert "Source: Yahoo Finance daily closes." in head


def test_a_wide_table_scrolls_on_its_own_not_the_panel_around_it():
    """At 375px the rotation table ran 774px and the stock map's 480px in a
    299px panel, and each panel scrolled sideways, prose and chart included."""
    import re
    for fn in ("function renderRotation(r) {", "function renderStockMap(sm) {"):
        body = _src(fn)
        tables = re.findall(r'(.{0,80})<table class="(data[^"]*)"', body)
        assert tables and all('<div class="table-scroll"' in pre for pre, _ in tables), fn
        # The name stays in view while the figures scroll under it.
        assert all("sticky-first" in cls for _, cls in tables), fn
        assert len(tables) == body.count("</table></div>"), fn


def test_the_base_rates_line_is_for_a_reader_not_the_operator():
    out = _app("""
      R.wait = baseRatesMissing(null);
      R.failed = baseRatesMissing({ available: false, reason: 'HTTP 504', failed: true });
      R.server = baseRatesMissing({ available: false, reason: 'Base rates have not been computed yet.' });
    """)
    assert "on their way" in out["wait"] and "fills in when they land" in out["wait"]
    assert out["failed"].startswith("Base rates could not be loaded") and "504" not in out["failed"]
    assert out["server"] == "Base rates have not been computed yet. The measured column stays empty until they are."
    assert "on this machine" not in _src("function renderPatterns(d) {")
    assert "failed: true" in _src("async function loadPatternRates() {")
