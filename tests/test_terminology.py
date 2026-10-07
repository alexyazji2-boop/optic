"""The definition tables themselves: one entry per key, and every key reachable.

Found starting the terminal-wide definitions pass:

* three heading definitions were never shown: their keys carried capitals
  ('GEX. Dealer gamma exposure' and its vanna and charm siblings) and hg()
  lowercases the title before it looks;
* 'liquidity' was in GLOSSARY twice and 'next report' in HEADER_DEFS twice,
  and an object literal keeps only the later, so the earlier was dead text.

LABEL_DEFS, the whole-label definitions for a figure that means the same
wherever it appears, must not hold a generic label: "Value" means something
different in every panel, which is how a moving average's definition ended up
on an insider table.
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


def _keys(name):
    block = re.search(r"^const " + name + r" = \{(.*?)^\};", APP, re.M | re.S).group(1)
    return re.findall(r"^\s*(['\"])((?:(?!\1).)+)\1\s*:", block, re.M)


@pytest.mark.parametrize("table", ["GLOSSARY", "HEADER_DEFS", "TH_HINTS", "LABEL_DEFS"])
def test_one_entry_per_key(table):
    keys = [k for _, k in _keys(table)]
    dupes = sorted({k for k in keys if keys.count(k) > 1})
    assert dupes == [], dupes


@pytest.mark.parametrize("table", ["GLOSSARY", "HEADER_DEFS", "TH_HINTS", "LABEL_DEFS"])
def test_keys_are_written_as_they_are_looked_up(table):
    bad = [k for _, k in _keys(table) if k != k.lower() or "  " in k or k != k.strip()]
    assert bad == [], bad


GENERIC = {"value", "change", "latest", "total", "average", "level", "ratio", "score", "signal",
           "rank", "type", "last", "date", "price", "period", "name", "status", "count", "amount",
           "high", "low", "open", "close", "volume", "shares", "yoy", "30d", "90d"}


# Column hints that were global before this rule, moved to their own tables
# (TABLE_DEFS). They leaked: "Last" was a level's age on three price tables,
# "Value" a moving average on the insider feed, "Level" a Fibonacci ratio on
# three others and "Type" a call or put on the long-term factors.
LEGACY_TH = set()


def test_no_generic_label_has_a_terminal_wide_definition():
    assert not ({k for _, k in _keys("LABEL_DEFS")} & GENERIC)
    th = {k for _, k in _keys("TH_HINTS")} & GENERIC
    assert th <= LEGACY_TH, sorted(th - LEGACY_TH)


def test_every_heading_definition_reaches_its_heading():
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
      R.gex = hg('GEX. Dealer gamma exposure');
      R.vex = hg('VEX. Dealer vanna exposure');
      R.missing = Object.keys(HEADER_DEFS).filter(function (k) { return hg(k) === esc(k); });
      print('RESULT:' + JSON.stringify(R));
    """
    out = subprocess.run([exe, "-e", src], capture_output=True, text=True, timeout=60, cwd=str(ROOT))
    blob = out.stdout + out.stderr
    assert "RESULT:" in blob, blob[-1500:]
    r = json.loads(blob.split("RESULT:", 1)[1].split("\n")[0])
    assert "data-def=" in r["gex"] and "data-def=" in r["vex"], "never shown before"
    assert r["missing"] == [], r["missing"]
