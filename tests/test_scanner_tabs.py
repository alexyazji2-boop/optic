"""A scan opens as a tab, the way a chart page's sections do.

Asked with a screenshot of the Scanners page, its results panel headed "Market
movers" crossed out: "make this a sub tab similar to the charts instead of
another dropdown". The question's scans were a row of pills, and each result
was a panel of its own under them, with a reading of the rows in another panel
between, both collapsible. The scans are the chart pages' tab strip
(`sec-tabs`) now, and the open tab's results are drawn under it in the same
panel, with the reading of the rows after them.
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


def _render(result):
    exe = JSC if os.path.exists(JSC) else shutil.which("jsc")
    if not exe:
        pytest.skip("no JavaScriptCore on this machine")
    script = """
      load('tests/support/browser_stubs.js');
      document.documentElement.style = document.documentElement.style || {};
      document.documentElement.style.setProperty = function () {};
      document.documentElement.style.removeProperty = function () {};
      try { load('static/charts.js'); load('static/app.js'); } catch (e) {}
      STATE.scanMode = 'named';
      STATE.scanId = 'gainers-volume';
      STATE.scanGroups = [{ id: 'movers', name: 'Market movers', count: 3, blurb: 'Liquid names.',
        scans: [{ id: 'movers', name: 'Market movers', looks_for: 'Moves.' },
                { id: 'gainers-volume', name: 'Top gainers with volume', looks_for: 'Gains.' },
                { id: 'decliners-volume', name: 'Top decliners with volume', looks_for: 'Falls.' }] }];
      var cat = { considered: 484, universe_size: 2975, scans: [] };
      print('RESULT:' + JSON.stringify({ html: renderScan(cat, %s) }));
    """ % json.dumps(result)
    out = subprocess.run([exe, "-e", script], capture_output=True, text=True,
                         timeout=120, cwd=str(ROOT))
    assert "RESULT:" in out.stdout, (out.stdout + out.stderr)[-2000:]
    return json.loads(out.stdout.split("RESULT:", 1)[1].split("\n")[0])["html"]


RESULT = {"available": True, "name": "Top gainers with volume", "looks_for": "Up on heavy volume.",
          "matched": 30, "shown": 2, "age_hours": 9.5, "stale": False,
          "columns": [{"key": "roc20", "label": "1-month", "kind": "pct"}],
          "rows": [{"symbol": "FORM", "price": 149.71, "roc20": 56.9},
                   {"symbol": "MXL", "price": 89.12, "roc20": -4.2}],
          "blind_spot": "Only the ranking.", "method": "From the ranking."}


def _between(html, start, end):
    return html[html.index(start):html.index(end, html.index(start))]


def _scanner_panels(html):
    """Panels on the page other than Find stocks, the request box above the
    scans (see tests/test_scan_request.py), which is a feature of its own."""
    return html.count('<div class="panel') - html.count('<div class="panel span-all sc-ask">')


def test_the_scans_are_the_chart_pages_tab_strip():
    html = _render(RESULT)
    strip = _between(html, '<nav class="sec-tabs scan-tabs" role="tablist"', "</nav>")
    assert strip.count('role="tab" class="sec-tab') == 3
    assert ('class="sec-tab on"\n      data-scan="gainers-volume" aria-selected="true"') in strip
    assert strip.count('aria-selected="false"') == 2
    assert "scan-pill" not in html, "the pills are gone"


def test_the_open_tabs_results_are_under_it_in_the_same_panel():
    html = _render(RESULT)
    panel = _between(html, "<h2>", '<div id="eval-host"')
    tabpanel = panel[panel.index('<div class="scan-result" role="tabpanel">'):]
    assert "Up on heavy volume." in tabpanel and ">FORM</button>" in tabpanel
    assert "30 matched, showing the first 2" in tabpanel
    # No second panel headed with the scan's name, and no separate panel for
    # the reading of its rows: one panel, the Scanners one.
    assert _scanner_panels(html) == 1
    assert "<h2>Top gainers with volume</h2>" not in html
    assert '<h3 class="scan-reads-h">What this screen returned</h3>' in tabpanel
    assert "A reading of the rows above" in tabpanel
    assert tabpanel.index("</table>") < tabpanel.index("What this screen returned")
    assert '<div class="table-scroll"><table class="data">' in tabpanel


def test_waiting_and_failing_are_shown_in_the_tab_too():
    loading = _render("loading")
    assert '<div class="scan-result" role="tabpanel"><p class="sub">Running the scan' in loading
    failed = _render({"available": False, "reason": "The ranking is being built."})
    tabpanel = failed[failed.index('role="tabpanel"'):]
    assert "The ranking is being built." in tabpanel
    assert _scanner_panels(loading) == 1 and _scanner_panels(failed) == 1


def test_the_tabs_look_like_the_chart_pages_and_wrap_rather_than_hide():
    css = (ROOT / "static/styles.css").read_text()
    rule = css[css.index(".scan-tabs {"):]
    rule = rule[:rule.index("}")]
    assert "flex-wrap: wrap;" in rule and "border-bottom: 1px solid var(--border);" in rule
    assert ".sec-tab.on { color: var(--ink); border-bottom-color: var(--btn-primary); }" in css
    assert ".scan-pill" not in css
