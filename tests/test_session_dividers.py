"""Period dividers on the charts.

Source-contract tests, the same pattern as tests/test_ui_refactor.py — there is
no JS runner here, and the granularity logic was verified against synthetic
label arrays in a real browser. What is asserted is the set of properties that
stop the feature becoming what it was: 42 dashed verticals across a 126-bar
chart, drawn in the same colour as the axis line.
"""

import re

CHARTS = open("static/charts.js", encoding="utf-8").read()
CSS = open("static/styles.css", encoding="utf-8").read()
NO_COMMENTS = re.sub(r"/\*.*?\*/", "", CSS, flags=re.S)


def _fn(name):
    start = CHARTS.index("function %s(" % name)
    return CHARTS[start:CHARTS.index("\n}", start)]


def test_the_granularity_is_read_from_the_bars_not_passed_in():
    """The old version always divided on the calendar day, which is right
    intraday and absurd on a daily chart where every bar is a new day."""
    fn = _fn("periodDividers")
    assert "gaps.sort" in fn, "the bar spacing has to be measured"
    for grain in ("'day'", "'month'", "'quarter'", "'year'"):
        assert grain in fn, grain


def test_every_granularity_branch_is_reachable():
    """Asserting the grain names exist is not enough: replacing a branch's
    condition with `false` leaves the string in the source and the branch dead.
    A mutation doing exactly that passed the first version of these tests.

    The thresholds are the reachability, so they are what is checked — and in
    ascending order, because two branches in the wrong order means the first
    swallows the second."""
    fn = _fn("periodDividers")
    cuts = [float(m) for m in re.findall(r"step < ([\d.]+)", fn)]
    assert cuts == sorted(cuts), cuts
    assert cuts == [0.9, 5, 45], cuts


def test_the_median_gap_is_used_not_the_mean():
    """Weekends and holidays leave holes. A mean over a daily series lands
    between one and three days and would pick the wrong granularity."""
    fn = _fn("periodDividers")
    assert "gaps[Math.floor(gaps.length / 2)]" in fn


def test_a_boundary_is_a_key_change_at_every_granularity():
    """One test for all four grains. A per-grain comparison is four chances to
    get an off-by-one wrong."""
    fn = _fn("periodDividers")
    # Every returned spec carries a key, and the grains are what matter rather
    # than the count: 'year' legitimately appears twice — once for weekly bars
    # spanning more than three years, once as the fallback for anything coarser.
    grains = re.findall(r"grain: '(\w+)'", fn)
    assert set(grains) == {"day", "month", "quarter", "year"}, grains
    assert len(re.findall(r"key: \(d\)", fn)) == len(grains)


def test_the_marks_are_counted_before_anything_is_drawn():
    """The old loop decided per line and capped mid-way, so it painted a fence
    and then stopped. 126 daily bars produced 42 verticals. The marks are
    collected whole and checked before any is drawn."""
    fn = _fn("dividerMarks")
    assert "const marks = [];" in fn and "marks.push(i);" in fn
    assert fn.index("marks.push(i);") < fn.index("marks.length <= Math.max(2, Math.floor(n / 4))")
    assert "appendChild" not in fn, "counting draws nothing"

def test_it_stands_down_rather_than_capping():
    """If the chosen granularity still yields a line every few bars the feature
    is adding noise, not orientation."""
    fn = _fn("dividerMarks")
    assert "return marks.length <= Math.max(2, Math.floor(n / 4)) ? marks : [];" in fn
    assert "drawn > n / 3" not in CHARTS, "the old capping guard must be gone"

def test_dividers_are_not_drawn_in_the_axis_colour():
    """C.baseline is the axis line. A time boundary painted in it is
    indistinguishable from chart furniture, which is what "make it distinct"
    was about."""
    fn = _fn("drawDividers")
    assert "stroke: C.refSession" in fn
    assert "C.baseline" not in fn

def test_the_divider_colour_is_a_theme_token_in_both_themes():
    """A hardcoded hex would not follow a theme switch, and the light theme
    needs a darker cyan than the dark one."""
    assert "refSession: '--ref-session'" in CHARTS
    hits = re.findall(r"--ref-session:\s*(#[0-9a-fA-F]{6})", NO_COMMENTS)
    assert len(hits) == 2, hits
    assert hits[0] != hits[1], "both themes cannot use the same cyan"


def test_the_date_axis_names_the_boundaries_not_a_caption_on_each_line():
    """Asked for with a reference chart: "this is how the session dividers
    should look like", a dashed line the height of the chart and nothing else.
    Each line used to carry its own caption at the foot of the price, saying
    again what the date axis under it already says."""
    assert "s('text'" not in _fn("drawDividers")
    assert "label:" not in _fn("periodDividers"), "nothing reads a caption now"
    assert "footLabels" not in CHARTS

def test_the_dash_pattern_is_its_own():
    """Three level families, three patterns: fine dots for ratios, medium dashes
    for structure, and this. Sharing one makes them one family visually."""
    assert "'stroke-dasharray': '4 4'" in _fn("drawDividers")
    assert CHARTS.count("'4 4'") == 1, "no other line is dashed this way"
    assert "'6 4'" in CHARTS and "'2 6'" not in CHARTS

def test_the_month_names_went_with_the_captions():
    """They were the captions' only reader."""
    assert "const MONTHS = [" not in CHARTS


# ------------------------------------------------- drawn, and measured


def _drawn(script):
    import json
    import os
    import shutil
    import subprocess
    import pytest
    jsc = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc"
    exe = jsc if os.path.exists(jsc) else shutil.which("jsc")
    if not exe:
        pytest.skip("no JavaScriptCore on this machine")
    src = (open("tests/support/recording_dom.js", encoding="utf-8").read() + CHARTS + """
      var days = [], d = new Date(Date.UTC(2026, 6, 1));
      while (days.length < 65) {
        if (d.getUTCDay() % 6) days.push(d.toISOString().slice(0, 10));
        d = new Date(d.getTime() + 86400000);
      }
      var closes = days.map(function (_, i) { return 100 + Math.sin(i / 5) * 4; });
      var dividers = function (from) {
        return NODES.slice(from).filter(function (n) {
          return n.tag === 'line' && n.attrs['stroke-dasharray'] === '4 4';
        }).map(function (n) {
          return { x: +n.attrs.x1, y1: +n.attrs.y1, y2: +n.attrs.y2, stroke: n.attrs.stroke };
        });
      };
    """ + script)
    out = subprocess.run([exe, "-e", src], capture_output=True, text=True, timeout=30)
    assert "RESULT:" in out.stdout, (out.stdout + out.stderr)[-2000:]
    return json.loads(out.stdout.split("RESULT:", 1)[1].strip().splitlines()[0])


def test_a_divider_runs_the_full_height_and_through_the_panes_at_one_x():
    """Three months of daily bars, July to September: two month lines. On the
    price chart they run from the top of the plot through the volume strip,
    with no caption beside them, and the MACD pane under it draws them at the
    same x when it is given the chart's gutter."""
    got = _drawn("""
      var vols = days.map(function () { return 1000000; });
      var svg = lineChart({ width: 900, height: 420, labels: days, valueTags: true,
        series: [{ name: 'Close', values: closes }], volume: vols, sessions: days });
      var f = svg.chartFrame;
      var price = dividers(0);
      // A caption was text in the dividers' own colour; the date axis's
      // labels are in the axis ink and stay.
      var stroke = price.length ? price[0].stroke : null;
      var texts = NODES.filter(function (n) { return n.tag === 'text' && n.attrs.fill === stroke; })
        .map(function (n) { return n.textContent; });
      var axis = NODES.filter(function (n) { return n.tag === 'text'; })
        .map(function (n) { return n.textContent; });
      var mark = NODES.length;
      macdChart(closes, closes, closes.map(function () { return 0; }), days, 900,
        { height: 132, sessions: true, marginRight: 74 });
      var macd = dividers(mark);
      print('RESULT:' + JSON.stringify({ price: price, macd: macd, top: f.margin.t,
        plotBottom: f.height - f.margin.b, priceBottom: f.margin.t + f.priceH, texts: texts,
        axis: axis }));
    """)
    assert len(got["price"]) == 2 and len(got["macd"]) == 2
    for line in got["price"]:
        assert line["y1"] == got["top"]
        assert line["y2"] == got["plotBottom"] > got["priceBottom"], "through the volume strip"
    assert [round(l["x"], 1) for l in got["price"]] == [round(l["x"], 1) for l in got["macd"]]
    assert got["texts"] == [], "no caption on the line"
    assert "Aug" in got["axis"] and "Sep" in got["axis"], "the date axis names them"


def test_with_dividers_off_nothing_is_drawn():
    got = _drawn("""
      lineChart({ width: 900, height: 300, labels: days, series: [{ name: 'Close', values: closes }] });
      var mark = NODES.length;
      macdChart(closes, closes, closes.map(function () { return 0; }), days, 900, { height: 132 });
      print('RESULT:' + JSON.stringify({ all: dividers(0).length }));
    """)
    assert got["all"] == 0


def test_the_panes_are_given_the_dividers_and_the_charts_gutter():
    app = open("static/app.js", encoding="utf-8").read()
    fn = app[app.index("function wsMountPanes(ps) {"):]
    fn = fn[:fn.index("\nfunction ")]
    assert "sessions: showSessions ? dates : null," in fn
    assert "{ cross, unit, height: 132, sessions: showSessions, marginRight: 74 }" in fn
