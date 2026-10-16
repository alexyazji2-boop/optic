"""The research framework's Overview panel (static/research.js), under
JavaScriptCore, fed two real payloads captured on 2026-10-14: NVDA before its
release and JPM the morning after its own."""

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc"
APP = (ROOT / "static/app.js").read_text(encoding="utf-8")
RJS = (ROOT / "static/research.js").read_text(encoding="utf-8")
HTML = (ROOT / "static/index.html").read_text(encoding="utf-8")
PRE = json.loads((ROOT / "tests/fixtures/framework_nvda_pre.json").read_text())
POST = json.loads((ROOT / "tests/fixtures/framework_jpm_post.json").read_text())


def _render(payload):
    exe = JSC if os.path.exists(JSC) else shutil.which("jsc")
    if not exe:
        pytest.skip("no JavaScriptCore on this machine")
    src = """
      load('tests/support/browser_stubs.js');
      document.documentElement.style = document.documentElement.style || {};
      document.documentElement.style.setProperty = function () {};
      document.documentElement.style.removeProperty = function () {};
      try { load('static/charts.js'); load('static/app.js'); } catch (e) { }
      try { load('static/research.js'); } catch (e) { print('LOADFAIL:' + e + ' ' + e.stack); }
      var html = window.OpticFramework.render(%s);
      print('RESULT:' + JSON.stringify({html: html, keys: Object.keys(window.OpticFramework).sort()}));
    """ % json.dumps(payload)
    out = subprocess.run([exe, "-e", src], capture_output=True, text=True, timeout=120, cwd=str(ROOT))
    blob = out.stdout + out.stderr
    assert "LOADFAIL" not in blob, blob[-2000:]
    assert "RESULT:" in blob, blob[-2000:]
    return json.loads(blob.split("RESULT:", 1)[1].split("\n")[0])


def test_four_questions_render_from_a_pre_earnings_payload():
    out = _render(PRE)
    html = out["html"]
    assert {"hostHTML", "load", "render"} <= set(out["keys"])
    for q in ("Is it a strong business?", "Is the price attractive?", "Is there a trade?", "What about earnings?"):
        assert q in html
    assert "My best-supported pre-earnings view is" in html
    assert "Reasons to skip it, most damaging first" in html
    assert "none has been shown to predict returns" in html
    assert "undefined" not in html and "NaN" not in html


def test_a_post_earnings_payload_grades_the_report_apart_from_the_reaction():
    html = _render(POST)["html"]
    assert "Report quality" in html and "The reaction" in html
    assert "undefined" not in html and "NaN" not in html


def test_a_failed_read_says_so():
    """And keeps the four questions on the page: since 2026-10-16 each tile
    carries the plain answer too, so a failed grade costs the grades only."""
    html = _render({"available": False, "reason": "no filings"})["html"]
    assert "grades are not available" in html and "no filings" in html
    assert "Is it a strong business?" in html and "Not graded" in html


def test_the_takeaways_are_said_inside_the_four_questions():
    """One set of answers on the Overview (2026-10-16): the takeaways'
    sentences are routed into the tiles, and a company no longer gets the
    separate takeaways section; a fund, which the four do not grade, does."""
    assert "data-rf-plain" in RJS and "window.ovPlainHTML" in RJS
    assert "window.ovPlainHTML = ovPlainHTML" in APP
    render = APP[APP.index("function renderOverviewView() {"):]
    render = render[:render.index("\n}\n")]
    assert "framed ? window.OpticFramework.hostHTML()" in render
    assert "<div id=\"ov-takeaways\">${ovTakeawaysHTML(" in render


def test_wired_into_the_overview_and_loaded_after_app_js():
    assert HTML.index('src="app.js') < HTML.index('src="research.js')
    assert "window.OpticFramework.hostHTML()" in APP and "window.OpticFramework.load(STATE.ticker)" in APP
    # Funds have no business to grade: the host is not drawn for them.
    assert "window.OpticFramework && !symbolIsFund(STATE.ticker)" in APP


def test_house_style():
    assert "—" not in RJS.replace("'—'", "")
    assert "--pos" not in RJS and "--neg" not in RJS
