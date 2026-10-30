"""WaveTrend in the v2 chart: ui/wavetrend.js lays an /api/indicators/wavetrend answer on the chart's bars and draws
the pane and the block under the chart, ui/pricechart.js gives it a pane among the others (so it pans, zooms and
reads at the crosshair with the candles), pages/chart-studies.js fetches it only while the pane is on, and
pages/chart.js lists it in the Panes menu, off by default.

The drawing runs in JavaScriptCore, on an answer the server module builds here from a fixed series and on marks
placed by hand where a count or a position is the point; the wiring is read as text. The page itself was checked
in a browser at 1440 and 390 px.
"""
import json
import re

import numpy as np
import pandas as pd

from app.analytics import wavetrend as wt
from tests.test_frontend_v2_stage0 import V2
from tests.test_v2_p3 import _run

JS = V2 / "js"
WTJS = (JS / "ui/wavetrend.js").as_posix()
DOM = (JS / "core/dom.js").as_posix()
PC = (JS / "ui/pricechart.js").read_text()
CS = (JS / "pages/chart-studies.js").read_text()
CH = (JS / "pages/chart.js").read_text()
CSS = (V2 / "css/pages.css").read_text()
TOKENS = (V2 / "css/tokens.css").read_text()
MINUS = "−"


def _answer(n=300):
    rng = np.random.default_rng(5)
    close = 100 * np.exp(np.cumsum(rng.normal(0, 0.015, n)))
    idx = pd.date_range("2025-08-01", periods=n, freq="B", tz="America/New_York")
    out = wt.build(pd.DataFrame({"Open": close, "High": close * 1.01, "Low": close * 0.99, "Close": close}, index=idx))
    out["interval"] = "1d"
    return out


# marks placed by hand: a bearish cross on bar 3, a strong bullish one on bar 4, a bearish divergence from 2 to 4
HAND = {"wt1": [None, None, 10, -20, 30, -40, 50], "wt2": [None, None, 5, -10, 20, -30, 40],
        "crosses": [{"at": 3, "type": "bearish", "strong": False}, {"at": 4, "type": "bullish", "strong": True}],
        "divs": [{"type": "bearish", "a": 2, "b": 4, "known": 6}],
        "levels": {"overbought": [53, 60], "oversold": [-53, -60]}, "params": {"channel_len": 9, "avg_len": 12, "ma_len": 3}}


def _y(v, y0=100, y1=200, mx=60 * 1.08):
    """Where the pane puts a value: a scale symmetric about zero, wide enough for the outer level (60) and 8% more."""
    return "{:.1f}".format(y0 + (1 - (v + mx) / (2 * mx)) * (y1 - y0))


def _pane(tmp_path, wt_, **opts):
    view = {"from": 0, "to": 6, "right": 70, "cross": -1, "clip": "c1", **opts}
    return _run(tmp_path, f"""
      const m = await import('{WTJS}');
      const v = {json.dumps(view)};
      print(JSON.stringify(m.paneSvg({{ y0: 100, y1: 200 }}, {json.dumps(wt_)}, Object.assign(v, {{ X: (i) => i * 10 }}))));
    """)


def test_the_answer_is_laid_on_the_charts_bars(tmp_path):
    """By time, as the other panes are: the chart here shows the answer's last 200 days and one day more that the
    answer does not have (a bar still forming), which gets no reading; marks before the first bar are left out."""
    ans = _answer()
    got = _run(tmp_path, f"""
      const m = await import('{WTJS}');
      const ans = {json.dumps(ans)};
      const days = ans.timestamps.slice(-200).concat(['2099-01-02']);
      const w = m.onBars(ans, days.map((d) => ({{ t: Date.parse(d + 'T00:00:00Z'), o: 1, h: 1, l: 1, c: 1 }})));
      print(JSON.stringify({{ n: w.wt1.length, first: [w.wt1[0], w.wt2[0]], last: [w.wt1[199], w.wt2[199]],
        extra: [w.wt1[200], w.wt2[200]], crosses: w.crosses, divs: w.divs, levels: w.levels, params: w.params }}));
    """)
    off = len(ans["timestamps"]) - 200
    assert got["n"] == 201 and got["extra"] == [None, None]
    assert got["first"] == [ans["wt1"][off], ans["wt2"][off]] and got["last"] == [ans["wt1"][-1], ans["wt2"][-1]]
    want = [{"at": x["i"] - off, "type": x["type"], "strong": x["strong"]} for x in ans["crosses"] if x["i"] >= off]
    assert want and got["crosses"] == want
    assert got["divs"] == [{"type": d["type"], "a": d["from"]["i"] - off, "b": d["to"]["i"] - off,
                            "known": d["confirmed"]["i"] - off} for d in ans["divergences"] if d["from"]["i"] >= off]
    assert got["levels"] == ans["levels"] and got["params"] == ans["params"]


def test_the_pane_draws_each_mark(tmp_path):
    svg = _pane(tmp_path, HAND)
    # zero solid and the four levels dashed, labelled where a label clears the one before (60 sits 5 px from 53)
    assert svg.count('class="g wt-z"') == 1 and svg.count('class="g wt-lv"') == 4
    assert re.findall(r'<text class="ax"[^>]*>([^<]+)</text>', svg) == ["0", "53", MINUS + "53"]
    # WT1 against zero from its first reading to the last bar, its edge, and WT2
    area = re.findall(r'<path class="wt-a" d="([^"]+)"', svg)
    assert area == ["M20.0 {z}L20.0 {a}L30.0 {b}L40.0 {c}L50.0 {d}L60.0 {e}L60.0 {z}Z".format(
        z=_y(0), a=_y(10), b=_y(-20), c=_y(30), d=_y(-40), e=_y(50))]
    assert 'class="ov wt1" d="M20.0 {}'.format(_y(10)) in svg and 'class="ov wt2" d="M20.0 {}'.format(_y(5)) in svg
    # a dot on WT2 at each cross, larger when strong
    assert re.findall(r'<circle class="([^"]+)" cx="([^"]+)" cy="([^"]+)" r="([^"]+)"/>', svg) == [
        ("wt-x d", "30.0", _y(-10), "2.2"), ("wt-x u big", "40.0", _y(20), "4")]
    # the divergence between its two WT2 pivots, dotted on to the bar where it became known, with a tick there
    assert '<line class="wt-dv d" x1="20.0" y1="{}" x2="40.0" y2="{}"/>'.format(_y(5), _y(20)) in svg
    assert '<line class="wt-dv wt-dk d" x1="40.0" y1="{0}" x2="60.0" y2="{0}"/>'.format(_y(20)) in svg
    assert '<line class="wt-dv d" x1="60.0"' in svg
    # inside the pane only, and named with its lengths and its values on the last bar in view
    assert '<clipPath id="c1">' in svg and 'clip-path="url(#c1)"' in svg
    assert svg.endswith('<text class="pane-t" x="6" y="112">WaveTrend 9, 12, 3: WT1 50.0, WT2 40.0</text>')


def test_the_title_reads_the_crosshairs_bar(tmp_path):
    svg = _pane(tmp_path, HAND, cross=3)
    assert ">WaveTrend 9, 12, 3: WT1 {m}20.0, WT2 {m}10.0</text>".format(m=MINUS) in svg
    none = _pane(tmp_path, HAND, cross=1)
    assert none.endswith(">WaveTrend 9, 12, 3</text>")


def test_marks_outside_the_view_are_not_drawn(tmp_path):
    svg = _pane(tmp_path, HAND, **{"from": 4})
    assert re.findall(r'<circle class="([^"]+)"', svg) == ["wt-x u big"]
    assert svg.count('class="wt-dv d"') == 2   # the divergence ends in view, so it is drawn (and clipped)
    assert _pane(tmp_path, dict(HAND, divs=[{"type": "bullish", "a": 0, "b": 2, "known": 3}]), **{"from": 4}).count("wt-dv") == 0


def test_a_bar_without_a_reading_ends_the_area(tmp_path):
    svg = _pane(tmp_path, dict(HAND, wt1=[1, 2, None, 3, 4, None, None], wt2=[None] * 7, crosses=[], divs=[]))
    assert len(re.findall(r'<path class="wt-a"', svg)) == 2
    assert 'class="ov wt1" d="M0.0 {}L10.0 {}M30.0 {}'.format(_y(1), _y(2), _y(3)) in svg


def test_the_accessible_summary_says_what_is_in_view(tmp_path):
    got = _run(tmp_path, f"""
      const m = await import('{WTJS}');
      print(JSON.stringify([m.summaryLine({json.dumps(HAND)}, 0, 6), m.summaryLine({json.dumps(HAND)}, 5, 6)]))
    """)
    assert got[0] == " WaveTrend 9, 12, 3: WT1 50.0 and WT2 40.0 on the last bar shown; 2 crosses in view, 1 strong, and 1 divergence."
    assert got[1].endswith("0 crosses in view, 0 strong, and 0 divergences.")


EV = {"interval": "1d", "evidence": {
    "horizons": [5, 10, 20], "window": {"from": "2016-12-12", "to": "2026-10-30", "bars": 2491},
    "finding": "10 bars on, strong bullish crosses did better than 71% of random draws. <b>None</b> cleared 95%.",
    "method": "Each signal is entered at the close of the bar where it became known.",
    "signals": [
        {"id": "strong_bullish_cross", "label": "Strong bullish crosses", "direction": "up", "count": 74,
         "by_horizon": {h: {"n": 74, "too_few": False, "hit_rate_pct": 54.1, "mean_pct": 0.02, "baseline_hit_rate_pct": 48.3,
                            "baseline_mean_pct": -0.08, "edge_pct": 0.1, "beats_random_pct": 55.8} for h in ("5", "10", "20")}},
        {"id": "bearish_divergence", "label": "Bearish divergences", "direction": "down", "count": 23,
         "by_horizon": {"5": {"n": 23, "too_few": False, "hit_rate_pct": 47.8, "mean_pct": 0.31, "baseline_hit_rate_pct": 51.7,
                              "baseline_mean_pct": -0.08, "edge_pct": 0.39, "beats_random_pct": 22.4},
                        "10": {"n": 21, "too_few": False, "hit_rate_pct": 52.4, "mean_pct": -0.4, "baseline_hit_rate_pct": 51.0,
                               "baseline_mean_pct": -0.15, "edge_pct": -0.25, "beats_random_pct": 70.2},
                        "20": {"n": 16, "too_few": True, "hit_rate_pct": None, "mean_pct": None, "baseline_hit_rate_pct": None,
                               "baseline_mean_pct": None, "edge_pct": None, "beats_random_pct": None}}},
    ]}}


def test_the_block_under_the_chart(tmp_path):
    got = _run(tmp_path, f"""
      const m = await import('{WTJS}'); const d = await import('{DOM}');
      print(JSON.stringify([d.toString(m.evidenceBlock({json.dumps(EV)})), d.toString(m.evidenceBlock({{ available: true }}))]));
    """)
    s, none = got
    assert none == ""
    assert s.startswith('<section class="ch-wt" aria-labelledby="ch-wt-h">')
    assert '<h3 class="t-h3 ch-wt-h" id="ch-wt-h">What followed WaveTrend\'s signals</h3>' in s
    assert [h for h in re.findall(r'<th scope="col"[^>]*>([^<]+)</th>', s)] == ["Signal", "Count", "5 bars on", "10 bars on", "20 bars on"]
    assert re.findall(r'<th scope="row">([^<]+)</th>', s) == ["Strong bullish crosses", "Bearish divergences"]
    assert s.count("<b>+0.02%</b>, 54% rose<small>Random {}0.08%, 48%</small><small>Beat 56% of draws</small>".format(MINUS)) == 3
    assert "<b>{}0.40%</b>, 52% fell<small>Random {}0.15%, 51%</small><small>Beat 70% of draws</small>".format(MINUS, MINUS) in s
    assert '<td class="num t-muted">Too few (16)</td>' in s
    assert "On 2,491 daily bars, Dec 12, 2016 to Oct 30, 2026." in s
    assert "<b>None</b>" not in s and "&lt;b&gt;None&lt;/b&gt;" in s   # the server's text is text
    assert "How this works" in s and "Each signal is entered at the close" in s
    assert "\u2014" not in s


def test_the_pane_is_listed_off_by_default_and_fetched_only_while_on():
    assert "['rs', 'Relative strength line'], ['wavetrend', 'WaveTrend']]" in CH
    assert "rs: false, wavetrend: false }" in CH
    # under the chart's notes and its gesture hint, so the hint stays with the chart and the block stands alone
    foot = CH[CH.index('<div class="ch-foot">'):]
    assert foot.index('id="ch-snote"') < foot.index("move one point.'}</p>") < foot.index('<div id="ch-wt"></div></div>')
    paint = CH[CH.index("function paintStudies()"):CH.index("function paintEvidence()")]
    assert "paintEvidence();" in paint and CH.count("paintEvidence();") == 2
    need = CS[CS.index("export function need"):CS.index("/* Laid on the current bars")]
    assert "if (on.wavetrend && P.bars() && S.wtKey !== barsQuery())" in need
    assert need.count("/api/indicators/wavetrend/") == 1
    assert "export function evidence(on)" in CS and "\n  wavetrend: 'LazyBear" in CS


def test_the_chart_gives_it_a_pane_among_the_others():
    layout = PC[PC.index("function computeLayout()"):PC.index("const span = Math.max(1, to - from + 1)")]
    assert "(S.panes.wavetrend ? 1 : 0)" in layout
    assert layout.index("SERVER_PANES.filter((k) => S.panes[k]).forEach") < layout.index("if (S.panes.wavetrend) { panes.push({ id: 'wavetrend'")
    assert "} else if (p.id === 'wavetrend') {" in PC and "wavetrend: 'WaveTrend' }, PANE_NAMES)" in PC
    assert "waveSummary(wt, from, to)" in PC


def test_every_mark_the_pane_draws_has_a_rule_and_its_colours_are_tokens():
    for sel in (".pc .wt-a", ".pc .ov.wt1", ".pc .ov.wt2", ".pc .g.wt-lv", ".pc .g.wt-z", ".pc .wt-x.u", ".pc .wt-x.d",
                ".pc .wt-x.big", ".pc .wt-dv", ".pc .wt-dv.u", ".pc .wt-dv.d", ".pc .wt-dk", "#ch-wt:empty", ".ch-wt-t td small"):
        assert sel + " {" in CSS, sel
    rules = CSS[CSS.index("/* WaveTrend (ui/wavetrend.js)"):CSS.index(".pc .pane-t {")]
    assert "#" not in rules.replace("#ch-wt", "")   # no colour literals: every one is a token
    assert TOKENS.count("--c-ind-wt1:") == 3 and TOKENS.count("--c-ind-wt2:") == 3   # ivory, charcoal, dark by default


def test_it_is_called_wavetrend_and_written_the_house_way():
    for f in list(V2.rglob("*.js")) + list(V2.rglob("*.css")) + list(V2.rglob("*.html")):
        assert "cipher" not in f.read_text().lower(), f
    said = json.dumps({**wt.describe(), "method": wt.evidence(pd.Series([1.0] * 40), {}, 0)["method"]})
    assert "cipher" not in said.lower()
    for text in ((JS / "ui/wavetrend.js").read_text(), CS, said):
        assert "\u2014" not in text
