"""The Home block of scan alerts shows what each alert says.

Reproduced before the fix: an alert row has a title and a body (app/alerts.py),
and the block rendered `message || text || reason`, none of which a row has, so
every row on Home was a symbol beside an empty line. It was also headed "Your
alerts" over Optic's own scan of its positions and the ranked universe, and
counted "All N" from a payload capped at four.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc"


def test_each_row_carries_its_title():
    exe = JSC if os.path.exists(JSC) else shutil.which("jsc")
    if not exe:
        pytest.skip("no JavaScriptCore on this machine")
    src = """
      load('tests/support/browser_stubs.js');
      try { load('static/charts.js'); load('static/app.js'); } catch (e) {}
      var rows = [{id: 1, kind: 'pattern', ticker: 'NVDA', title: 'Bull flag confirmed on NVDA', body: 'b'},
                  {id: 2, kind: 'risk', ticker: null, title: 'The book reached its position cap', body: ''}];
      print('RESULT:' + JSON.stringify(homeAlerts({alerts: rows})));
    """
    out = subprocess.run([exe, "-e", src], capture_output=True, text=True, timeout=120, cwd=str(ROOT))
    html = json.loads(out.stdout.split("RESULT:", 1)[1].split("\n")[0])
    assert '<span class="hm-alert-text">Bull flag confirmed on NVDA</span>' in html
    assert '<span class="hm-alert-text">The book reached its position cap</span>' in html
    assert "Latest scan alerts" in html and "Your alerts" not in html
    assert "All alerts &rarr;" in html and "All 2" not in html
    assert "—" not in html, "no placeholder dash for an alert without a symbol"
