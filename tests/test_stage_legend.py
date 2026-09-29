"""What stages 1 to 4 mean, under a chart coloured by them; the chip moved up.

Asked for with a screenshot of the Nasdaq 100 futures chart: "move this up,
and include a legend of what stages 1-4 is when it is selected". The chip sat
between the chart's controls and its key, where it read as one more key entry;
it is under the instrument's name now. The chart's key named the stages on
screen as colours and said nothing of what they meant, so while Stages is on a
legend under the chart defines all four, from the server, with the current
one marked. Checked in a browser at 375px and 600px on the instrument page and
the Options chart: shown under the chart with Stages on, gone with it off.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from app.analytics import stage

ROOT = Path(__file__).resolve().parent.parent
RAW = (ROOT / "static/app.js").read_text()
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc"


def test_every_stage_has_a_definition_in_the_terms_the_rule_uses():
    assert sorted(stage.MEANINGS) == [1, 2, 3, 4] == sorted(stage.NAMES)
    ten, pct = "ten weeks", "{:g}%".format(stage.FLAT_PCT)
    assert stage.SLOPE_WEEKS == 10 and stage.SMA_WEEKS == 30
    assert "above" in stage.MEANINGS[2] and "risen more than " + pct in stage.MEANINGS[2]
    assert "below" in stage.MEANINGS[4] and "fallen more than " + pct in stage.MEANINGS[4]
    assert all(ten in stage.MEANINGS[n] for n in (2, 4))
    assert "After a decline" in stage.MEANINGS[1] and "After an advance" in stage.MEANINGS[3]
    assert all("30-week" in m for m in stage.MEANINGS.values())


def test_the_reading_carries_them(monkeypatch):
    import pandas as pd

    idx = pd.date_range("2016-01-04", periods=520, freq="W-FRI")
    closes = [100 + i * 0.5 for i in range(520)]
    frame = pd.DataFrame({"Close": closes}, index=idx)

    class Provider:
        def history(self, symbol, period="10y", interval="1wk"):
            return frame

    out = stage.for_symbol(Provider(), "ABC")
    assert out["available"] is True and out["stage"] == 2
    assert out["meanings"] == {str(k): v for k, v in stage.MEANINGS.items()}


def _raw_fn(name):
    return re.search(r"^(?:async )?function " + name + r"\([^\n]*\) \{.*?^\}",
                     RAW, re.M | re.S).group()


def _js(prelude, names, scenario):
    exe = JSC if os.path.exists(JSC) else shutil.which("jsc")
    if not exe:
        pytest.skip("no JavaScriptCore on this machine")
    src = ("function assert(v, m) { if (!v) throw new Error(m); }\n" + prelude + "\n"
           + "\n".join(_raw_fn(n) for n in names)
           + "\n(async function () {\n" + scenario + "\n})().then(function () { print('TEST_OK'); },"
           " function (e) { print('FAIL ' + e + '\\n' + e.stack); });")
    out = subprocess.run([exe, "-e", src], capture_output=True, text=True, timeout=30)
    assert "TEST_OK" in out.stdout, out.stdout + out.stderr


LEGEND = r"""
function esc(s) { return String(s); }
var R = { available: true, stage: 2,
  names: { 1: 'Basing', 2: 'Advancing', 3: 'Topping', 4: 'Declining' },
  meanings: { 1: 'base', 2: 'uptrend', 3: 'top', 4: 'downtrend' } };
var drawn = true;
function wsOverlayDrawn(id) { return id === 'stages' && drawn; }
function fetchStage() { return Promise.resolve(R); }
var host = { hidden: true, innerHTML: '' };
var document = { getElementById: function () { return host; } };
"""


def test_the_legend_names_all_four_and_marks_the_current_one():
    _js(LEGEND, ["stageLegendHTML"], """
      var html = stageLegendHTML(R);
      [1, 2, 3, 4].forEach(function (n) {
        assert(html.indexOf('stage-legend-item stage-' + n) >= 0, 'no stage ' + n);
        assert(html.indexOf(R.meanings[n]) >= 0, 'no meaning for ' + n);
      });
      assert((html.match(/is-now/g) || []).length === 1 && /stage-2 is-now/.test(html), 'the current one');
      assert(html.indexOf('Stage 2 \\u00b7 Advancing <span class="stage-legend-now">now</span>') >= 0, html);
    """)


def test_the_legend_follows_the_stages_switch():
    _js(LEGEND, ["stageLegendHTML", "paintStageLegend"], """
      await paintStageLegend('stage-inst-legend', 'NQ=F');
      assert(host.hidden === false && host.innerHTML.indexOf('What the stages mean') >= 0, 'not shown with Stages on');
      drawn = false;
      await paintStageLegend('stage-inst-legend', 'NQ=F');
      assert(host.hidden === true && host.innerHTML === '', 'still shown with Stages off');
      drawn = true; R = { available: false };
      await paintStageLegend('stage-inst-legend', 'NQ=F');
      assert(host.hidden === true, 'shown for a symbol with no reading');
    """)


def test_the_chip_is_under_the_name_and_the_legends_are_under_their_charts():
    page = RAW[RAW.index('<h2 class="weekly-title">${esc(d.label)}${askPulse(\'instrument\')}</h2>'):]
    page = page[:page.index("reference series, not a price you could deal at")]
    chip = page.index('id="stage-inst"')
    assert chip < page.index("chart-toolbar"), "the chip is below the chart's controls again"
    assert page.index('id="chart-inst"') < page.index('id="stage-inst-legend"')
    assert RAW.index('<div id="chart-price"></div>') < RAW.index('id="stage-price-legend"')
    for host in ("stage-inst-legend", "stage-price-legend"):
        assert "paintStageLegend('%s'" % host in RAW, host
