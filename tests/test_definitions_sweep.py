"""The terminal-wide definitions pass: headings, labels and table columns.

Asked for as "add definitions all over the terminal for complex terminology
wherever applicable". Three tables carry them:

* HEADER_DEFS, for a heading as a whole (Vanna, Implied correlation,
  Seasonality, Fair value), through hg();
* LABEL_DEFS, for a label that means the same in every table (RS 1m, vs 200d,
  Worst drawdown), through statLabel() and the column pass;
* TABLE_DEFS, for a column whose meaning belongs to its table, chosen by the
  table's data-defs. Found starting it: the sector rotation table's "Strength"
  and the sector ranking's "Strength" were both being explained as a support
  level's 0 to 100 score, the same leak that once put a moving average's
  "Value" on an insider table.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
APP = (ROOT / "static/app.js").read_text()
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc"
BANNED = ("you should", "you want", "look for a", "buy when", "sell when", "a good sign that you")


def _jsc(script):
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
      var R = {};
    """ + script + "\nprint('RESULT:' + JSON.stringify(R));"
    out = subprocess.run([exe, "-e", src], capture_output=True, text=True, timeout=60, cwd=str(ROOT))
    blob = out.stdout + out.stderr
    assert "RESULT:" in blob, blob[-2000:]
    return json.loads(blob.split("RESULT:", 1)[1].split("\n")[0])


def _pass_heading_keys():
    block = APP[APP.index("// ---- the terminal-wide pass"):]
    block = block[:block.index("\n};")]
    return re.findall(r"^\s*'([^']+)':", block, re.M)


@pytest.fixture(scope="module")
def defs():
    return _jsc("""
      R.header = HEADER_DEF_INDEX; R.label = LABEL_DEFS; R.table = TABLE_DEFS;
    """)


def test_every_new_definition_keeps_the_house_rules(defs):
    bodies = [("heading " + k, defs["header"][k]) for k in _pass_heading_keys()]
    bodies += [("label " + k, v) for k, v in defs["label"].items()]
    bodies += [(f"{t}.{k}", v) for t, cols in defs["table"].items() for k, v in cols.items()]
    assert len(bodies) > 120
    for key, body in bodies:
        assert body.count(".") >= 2 and len(body) >= 110, (key, body)
        assert "—" not in body, key
        for phrase in BANNED:
            assert phrase not in body.lower(), (key, phrase)


@pytest.mark.parametrize("title", ["Vanna", "Charm", "Implied correlation", "Seasonality", "Fair value",
                                   "Off-exchange short volume", "Sector rotation", "Relative performance",
                                   "Congressional disclosures", "Expected S&P move", "Dividend score", "ATR"])
def test_a_heading_a_reader_stalls_on_is_defined(title):
    out = _jsc("R.html = hg(%s);" % json.dumps(title))
    assert "data-def=" in out["html"], title


def test_every_table_that_asks_for_definitions_has_them(defs):
    used = set(re.findall(r'data-defs="([a-z0-9-]+)"', APP))
    assert used == set(defs["table"]), (used ^ set(defs["table"]))


def test_every_column_definition_names_a_header_of_its_table(defs):
    """A key that matches no header of its table is a definition nobody sees."""
    for name, cols in defs["table"].items():
        heads = set()
        for m in re.finditer(r'data-defs="%s"' % re.escape(name), APP):
            thead = APP[m.end():m.end() + 1500]
            thead = thead[:thead.index("</thead>")]
            heads |= {re.sub(r"\s+", " ", t.strip().lower()) for t in re.findall(r"<th[^>]*>((?:(?!\$\{)[^<])+)</th>", thead)}
            heads |= set(re.findall(r'data-def-key="([^"]+)"', thead))
        missing = sorted(set(cols) - {h.replace("&amp;", "&") for h in heads})
        assert missing == [], (name, missing)


def test_a_tables_own_definition_wins_and_others_keep_theirs():
    out = _jsc("""
      function TH(text, table, key) {
        this.textContent = text; this.innerHTML = text; this._t = table;
        this.dataset = key ? { defKey: key } : {};
      }
      TH.prototype.querySelector = function () { return this.innerHTML.indexOf('gloss-term') >= 0 ? {} : null; };
      TH.prototype.closest = function () { return this._t && this._t.dataset.defs ? this._t : null; };
      var rot = { dataset: { defs: 'rotation' } }, levels = { dataset: {} }, seas = { dataset: { defs: 'seasonality' } };
      var ths = [new TH('Strength', rot), new TH('Strength', levels), new TH('vs QQQ', seas, 'vs-bench'),
                 new TH('RS 3m', levels)];
      glossHeaders({ querySelectorAll: function () { return ths; } });
      var def = function (th) { var m = /data-def="([^"]*)"/.exec(th.innerHTML); return m ? m[1] : null; };
      R.rot = def(ths[0]); R.levels = def(ths[1]); R.bench = def(ths[2]); R.rs = def(ths[3]);
      R.want = { rot: esc(TABLE_DEFS.rotation.strength), levels: esc(TH_HINTS.strength),
                 bench: esc(TABLE_DEFS.seasonality['vs-bench']), rs: esc(LABEL_DEFS['rs 3m']) };
    """)
    for k in ("rot", "levels", "bench", "rs"):
        assert out[k] == out["want"][k], k
    assert out["rot"] != out["levels"], "the rotation table's Strength is not a support level's"


def test_the_sector_heatmap_says_what_its_figure_is():
    """The RS columns are the change in the price ratio to SPY, not a return
    difference, and the caption said "return minus SPY's, in percentage points"."""
    i = APP.index("function sectorHeatHTML(s) {")
    body = APP[i:APP.index("\n}\n", i)]
    assert "the ratio of the two), in percent" in body and "in percentage points" not in body
