"""Controls that took the click, or the change, and did nothing.

Found by an audit that clicked every visible control on every page at 1280 and
checked that something happened, and by the check at the bottom of this file:
every `data-*` attribute on a button, input, select or textarea has to be read
by some script, or the control carrying it cannot be doing anything with it.

Three were real, and all three were confirmed on the live site first:

* The indicator manager's Width, Length, Offset and Price source. The select
  and the number boxes carried `data-ws-width` and `data-ws-param` and nothing
  read either. Picking width 1 showed 1, the stored width stayed 1.5, and the
  next repaint put 1.5 back.
* The chart checklist. `wsSaveCheck` existed and nothing called it, so a tick
  lasted until the widget repainted and "0 of 7 for AAPL" never moved.
* The Watchlist page for anyone who had not yet saved a list. `localLists`
  minted a new id on every call, so the bar read the lists under one id and
  the active one under another: the only chip never showed as selected, a
  click on it switched to a list that did not exist, and Rename found no
  active list and returned without asking for a name.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
JS = (ROOT / "static/app.js").read_text()
# Every script the page loads, for the question "does anything read this".
SCRIPTS = "\n".join(p.read_text() for p in sorted((ROOT / "static").rglob("*.js"))
                    if "__" not in p.name)
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc"


def _fn(name):
    return re.search(r"^(?:async )?function " + name + r"\([^\n]*\) \{.*?^\}", JS, re.M | re.S).group()


def _line(pattern):
    return re.search(pattern, JS, re.M).group()


def _jsc(src):
    exe = JSC if os.path.exists(JSC) else shutil.which("jsc")
    if not exe:
        pytest.skip("no JavaScriptCore on this machine")
    out = subprocess.run([exe, "-e", src + "\nprint('TEST_OK');"], capture_output=True, text=True, timeout=30)
    assert "TEST_OK" in out.stdout, out.stdout + out.stderr


def _change_handler_branch(attr):
    """The branch of a document-level change handler that starts at `attr`."""
    start = JS.index("evt.target.closest('[" + attr + "]')")
    return JS[start:start + 1600]


# ------------------------------------------------------------ the watchlist

def test_a_new_visitor_has_one_list_and_it_is_the_active_one():
    store = {}
    _jsc("\n".join([
        "function assert(v, m) { if (!v) throw new Error(m); }",
        "var localStorage = { getItem: function (k) { return k in store ? store[k] : null; },"
        " setItem: function (k, v) { store[k] = String(v); } };",
        "var store = {};",
        "function signedIn() { return false; }",
        "var ACCOUNT = { watchlists: null };",
        _line(r"^const WATCH_KEY = .*$"),
        _line(r"^const WATCH_DEFAULT = .*$"),
        _line(r"^const WATCHLISTS_KEY = .*$"),
        _line(r"^let firstListId = .*$"),
        _fn("esc"), _fn("newListId"), _fn("localWatchList"), _fn("localLists"),
        _fn("watchAllLists"), _fn("watchActiveId"), _fn("watchActiveList"), _fn("watchListsBar"),
        """
        var a = localLists(), b = localLists();
        assert(a.lists[0].id === b.lists[0].id, 'a fresh id on every read');
        assert(watchAllLists()[0].id === watchActiveId(), 'the lists and the active id disagree');
        assert(watchActiveList() && watchActiveList().name === 'Watchlist', 'no active list, so Rename returns');
        var bar = watchListsBar();
        assert(/class="wl-chip on"/.test(bar) && /aria-selected="true"/.test(bar), 'the only list is not selected');
        assert(!('optic.watchlists.v1' in store), 'reading the lists wrote them; nothing is saved until a change');
        """,
    ]))


# ------------------------------------------------------- the chart workspace

def test_the_indicator_managers_width_and_parameters_are_saved():
    branch = _change_handler_branch("data-ws-width")
    assert "setOverlayStyle(id, { width: el.value });" in branch
    assert "setOverlayStyle(id, { params: { source: el.value } });" in branch
    assert "setOverlayStyle(id, { params: { [key]: v } });" in branch
    # Typed numbers are not held to min and max by the browser.
    assert "Number(el.min)" in branch and "Number(el.max)" in branch
    assert re.search(r"const v = Math\.min\([^;]*hi[^;]*Math\.max\([^;]*lo[^;]*n\)\);", branch), \
        "a typed length of 999 should be clamped to the field's 400"
    assert branch.index("wsRefresh();") > branch.index("setOverlayStyle(")
    assert "renderSwing(STATE.swing)" in branch, "the Swing chart shares these styles"
    assert "again.focus(" in branch, "the repaint replaces the control, so focus goes back"


def test_the_manager_writes_the_patches_it_is_handed():
    body = _fn("setOverlayStyle")
    assert "if (patch.width !== undefined) next.width = Number(patch.width);" in body
    assert "next.params = { ...(next.params || {}), ...patch.params };" in body


def test_a_checklist_tick_is_saved_and_counted():
    branch = _change_handler_branch("data-ws-check")
    assert "wsSaveCheck(STATE.chartSymbol || '', idx, wsCheck.checked);" in branch
    assert "wsRepaintWidget('checklist');" in branch
    widget = JS[JS.index("if (id === 'checklist') {"):][:600]
    assert "wsChecks()[sym]" in widget and "const sym = STATE.chartSymbol || '';" in _fn("wsWidgetBody")


# ------------------------------------------ every control's attribute is read

# Attributes on elements that are not controls, or that are read under another
# spelling on purpose. Each needs its reason.
NOT_HANDLERS = {
    "nav-edge": "an SVG rect in the chart navigator, drawn and never clicked",
    "pch": "the panel chooser dialog's own marker, not a control",
    "sc-row": "a filter row's index on its container div",
}


def _read_somewhere(name):
    camel = re.sub(r"-([a-z0-9])", lambda m: m.group(1).upper(), name)
    return bool(re.search(r"\[data-" + re.escape(name) + r"[\]=~^$*|]", SCRIPTS)
                or "dataset." + camel in SCRIPTS
                or re.search(r"(get|has|remove|toggle)Attribute\(\s*['\"`]data-" + re.escape(name) + r"['\"`]", SCRIPTS))


def test_every_data_attribute_on_a_control_is_read_by_something():
    controls = re.findall(r"<(?:button|input|select|textarea)\b[^>]*", SCRIPTS
                          + (ROOT / "static/index.html").read_text())
    names = set()
    for tag in controls:
        names.update(re.findall(r"\sdata-([a-z0-9][a-z0-9-]*)", tag))
    unread = sorted(n for n in names if n not in NOT_HANDLERS and not _read_somewhere(n))
    assert not unread, "controls carry attributes nothing reads: " + ", ".join("data-" + n for n in unread)


def test_full_screen_charting_takes_the_report_pill_down_with_the_chrome():
    """It covered the widget rail's Pulse button in a mode that cannot scroll."""
    css = (ROOT / "static/styles.css").read_text()
    start = css.index("body.ws-max[data-view=\"chart\"] .rail,")
    block = css[start:css.index("/* ---------------------------------------------------------- Insiders page")]
    assert 'body.ws-max[data-view="chart"] .rp { display: none; }' in block
