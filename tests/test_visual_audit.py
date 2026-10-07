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
