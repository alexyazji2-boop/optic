"""News: the headlines in time, about the company above the market's.

Asked for as "News: a timeline with tags". The feed carried every headline's
publish time and the page never drew it, so a dozen stories this evening read
the same as a dozen over a week. One lane per group the page already lists
(about the company, market context), each headline a mark at its publish time:
shaped and coloured by the tone of its wording, sized by its tier, readable
by hover or focus with its source, tier, tone and tags. A headline with no
publish time is listed but not drawn, and the caption says how many.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
import shutil
import subprocess
from pathlib import Path

import pytest

from tests.test_visual_primitives import _jsc as _prim

ROOT = Path(__file__).resolve().parent.parent
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc"

NEWS = {"tiers": [{"id": "breaking", "label": "Breaking"}, {"id": "notable", "label": "Notable"}],
        "articles": [
            {"title": "NVDA <b>wins</b> deal", "published": "2026-10-07T01:35:02+00:00", "about_company": True,
             "tone": "bullish", "tier": "breaking", "publisher": "Wire", "catalysts": [{"type": "partnership"}]},
            {"title": "NVDA cut by analyst", "published": "2026-10-06T23:39:04+00:00", "about_company": True,
             "tone": "mildly bearish", "tier": "notable", "publisher": "Desk"},
            {"title": "Stocks drift", "published": "2026-10-06T14:00:00+00:00", "about_company": False,
             "tone": "neutral", "tier": "background"},
            {"title": "Undated", "published": "", "about_company": True, "tone": "neutral"}]}


def _app(script):
    exe = JSC if os.path.exists(JSC) else shutil.which("jsc")
    if not exe:
        pytest.skip("no JavaScriptCore on this machine")
    src = """
      load('tests/support/browser_stubs.js');
      document.documentElement.style = document.documentElement.style || {};
      document.documentElement.style.setProperty = function () {};
      document.documentElement.style.removeProperty = function () {};
      try { load('static/charts.js'); load('static/app.js'); } catch (e) {}
      explainPolicy = function () { return 'on_demand'; };
      STATE.ticker = 'NVDA';
      var NEWS = %s, R = {}, BUILT = {}, CAPT = {};
      vizMount = function (id, build, none) { BUILT[id] = { build: build, none: none }; };
      eventTimeline = function (o) { (CAPT.t = CAPT.t || []).push(o); return { chart: 'timeline' }; };
      function build(id) { var b = BUILT[id]; return b ? b.build(600) : 'not mounted'; }
    """ % json.dumps(NEWS) + script + "\nprint('RESULT:' + JSON.stringify(R));"
    out = subprocess.run([exe, "-e", src], capture_output=True, text=True, timeout=60, cwd=str(ROOT))
    blob = out.stdout + out.stderr
    assert "RESULT:" in blob, blob[-2000:]
    return json.loads(blob.split("RESULT:", 1)[1].split("\n")[0])


def test_the_headlines_are_placed_by_publish_time_in_two_lanes():
    out = _app("""
      NEWS.held = { fetched_at: '2026-10-07T03:51:00+00:00' };
      R.html = newsTimelineHTML(NEWS, NEWS.articles);
      mountNewsTimeline(NEWS, NEWS.articles);
      build('viz-news-time');
      var o = CAPT.t[0];
      R.lanes = o.lanes.map(function (l) { return [l.name, l.items.map(function (i) { return [i.lean, i.weight]; })]; });
      R.end = o.end; R.start = o.start; R.now = o.nowLabel;
      R.detail = o.lanes[0].items[0].detail;
    """)
    html = out["html"]
    assert "2 of 2 headlines about NVDA arrived in the last 24 hours" in html
    assert "1 without a publish time is listed below but not drawn." in html
    assert "read from its wording by a word list" in html and "up to when they were fetched" in html
    assert out["lanes"] == [["About NVDA", [["up", 3], ["down", 2]]], ["Market context", [["flat", 1]]]]
    fetched = datetime(2026, 10, 7, 3, 51, tzinfo=timezone.utc).timestamp() * 1000
    oldest = datetime(2026, 10, 6, 14, 0, tzinfo=timezone.utc).timestamp() * 1000
    assert out["now"] == "fetched" and out["end"] == fetched, "a held feed ends when it was fetched"
    assert out["start"] < oldest, "the window reaches back past the oldest headline"
    detail = dict(out["detail"])
    assert detail["Tier"] == "Breaking" and detail["Tags"] == "Partnership" and detail["Source"] == "Wire"


def test_a_feed_with_one_dated_headline_draws_no_timeline():
    out = _app("""
      R.html = newsTimelineHTML(NEWS, [NEWS.articles[0], NEWS.articles[3]]);
    """)
    assert out["html"] == ""


def test_marks_carry_their_lean_in_shape_and_read_out_their_headline():
    out = _prim("""
      var t0 = Date.parse('2026-10-06T12:00:00Z');
      var root = eventTimeline({ width: 600, start: t0, end: t0 + 12 * 3600000, now: t0 + 12 * 3600000, lanes: [
        { name: 'About NVDA', items: [{ t: t0 + 3600000, label: 'Up <i>story</i>', lean: 'up', weight: 3 },
                                      { t: t0 + 3700000, label: 'Down story', lean: 'down', weight: 1 },
                                      { t: t0 + 7200000, label: 'Flat story', lean: 'flat' }] },
        { name: 'Market context', items: [] } ] });
      R.paths = all(root, function (n) { return n.tag === 'path'; }).map(function (n) { return n.attrs.fill; });
      R.dots = all(root, function (n) { return n.tag === 'circle'; }).length;
      R.marks = all(root, function (n) { return n.attrs && n.attrs.tabindex === '0'; }).map(function (n) { return n.attrs['aria-label']; });
      R.labels = texts(root);
      R.pos = C.pos; R.neg = C.neg;
      var ys = all(root, function (n) { return n.tag === 'path'; }).map(function (n) { return n.attrs.d; });
      R.apart = ys[0] !== ys[1];
      R.none = eventTimeline({ start: 1, end: 2, lanes: [{ name: 'x', items: [] }] });
    """)
    assert out["paths"] == [out["pos"], out["neg"]] and out["dots"] == 1, "triangles for a lean, a dot for neither"
    assert "About NVDA: Up <i>story</i>" in out["marks"], "the label rides as an attribute, not markup"
    assert "Market context" not in out["labels"], "an empty lane is left out"
    assert "now" in out["labels"] and out["apart"]
    assert out["none"] is None


def test_day_ticks_fall_on_new_york_midnight():
    out = _prim("""
      var t0 = Date.parse('2026-10-03T16:00:00Z');
      var root = eventTimeline({ width: 900, start: t0, end: t0 + 3 * 86400000, lanes: [
        { name: 'A', items: [{ t: t0 + 86400000, label: 'x', lean: 'flat' }] }] });
      var lines = all(root, function (n) { return n.tag === 'line' && n.attrs.stroke === C.grid; });
      var X = function (t) { return 128 + (t - t0) / (3 * 86400000) * (900 - 128 - 16); };
      R.first = Number(lines[0].attrs.x1);
      R.want = X(Date.parse('2026-10-04T04:00:00Z'));
      R.labels = texts(root);
    """)
    assert out["first"] == pytest.approx(out["want"], abs=0.01), "midnight in New York is 04:00 UTC in October"
    assert "Oct 4" in out["labels"]


def test_a_marks_size_is_keyed_and_net_sentiment_carries_its_scale():
    """The caption said "size is its tier" and nothing said which size was
    which; the net sentiment figure gave no scale to read it against."""
    out = _app("""
      R.key = newsSizeKey({ tiers: [{ id: 'breaking', label: 'Breaking' }, { id: 'major', label: 'Major' },
        { id: 'notable', label: 'Notable' }, { id: 'background', label: 'Background' }] });
      R.none = newsSizeKey({});
      R.html = newsTimelineHTML(NEWS, NEWS.articles);
      R.def = GLOSSARY['net sentiment'];
    """)
    key = out["key"]
    assert key.index("Breaking or major") < key.index("Notable") < key.index("Background")
    assert 'width:13.8px;height:13.8px' in key and 'width:8.6px;height:8.6px' in key, "the timeline's own radii"
    assert out["none"] == ""
    assert "Notable" in out["html"], "the key rides in the timeline's legend"
    assert "past 0.5 either way" in out["def"] and "past 2" in out["def"]
    src = (ROOT / "static/app.js").read_text()
    body = src[src.index("function renderNewsView() {"):]
    assert "${gloss('net sentiment')}" in body and "(it leans past \\u00b10.5 and reads bullish or bearish past \\u00b12)" in body
