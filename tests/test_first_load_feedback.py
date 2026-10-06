"""A first load says it is working, and the reports list survives a drop.

Two reports from the live site. "Loading HOOD..." sat on the Overview long
enough (first loads measured 9.4s, 10.3s and 58.1s) that the reader pressed
Load again; the panel now says a first look takes several seconds and counts
them. And the Problem Reports page printed Chrome's "Failed to fetch" after one
dropped connection, while the endpoint itself answered in 159ms: it was the one
read in the app that did not retry the way getJSON does.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
RAW = (ROOT / "static/app.js").read_text()
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc"


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


# ------------------------------------------------------------ the clock


FACET = r"""
var timers = [], cleared = [];
function setInterval(fn, ms) { timers.push(fn); return timers.length; }
function clearInterval(id) { cleared.push(id); }
var clock = { textContent: '', isConnected: true };
var host = { innerHTML: '', querySelector: function (sel) { return sel === '[data-load-elapsed]' ? clock : null; } };
var views = { overview: host };
var STATE = { ticker: 'HOOD', view: 'overview', swing: null };
function esc(s) { return String(s); }
function securityHeader() { return '<header>'; }
function emptyHTML() { return 'empty'; }
function errorHTML(m) { return 'error ' + m; }
function preserveUI(h, f) { f(); }
var rendered = 0;
function renderOverviewView() { rendered++; host.innerHTML = 'overview'; }
function renderNewsView() {} function renderFinancialsView() {}
var release;
function loadSwing() { return new Promise(function (r) { release = r; }); }
"""


def test_the_panel_counts_while_it_waits_and_stops_when_it_lands():
    _js(FACET, ["loadSecurityFacet"], """
      var p = loadSecurityFacet('overview', true);
      assert(host.innerHTML.indexOf('Loading HOOD') >= 0, 'the loading line');
      assert(host.innerHTML.indexOf('The first look at a symbol') >= 0, 'what it is waiting on');
      assert(timers.length === 1, 'one clock');
      var t0 = Date.now(); while (Date.now() - t0 < 1100) {}   // a second passes
      timers[0]();
      assert(/^[0-9]+s$/.test(clock.textContent) && clock.textContent !== '0s', 'counted ' + clock.textContent);
      STATE.swing = { ticker: 'HOOD' };
      release({ ticker: 'HOOD' }); await p;
      assert(cleared.indexOf(1) >= 0, 'stopped when it landed');
      assert(rendered === 1 && host.innerHTML === 'overview', 'and drew the page');
    """)


def test_a_clock_whose_panel_was_replaced_stops_itself():
    _js(FACET, ["loadSecurityFacet"], """
      var p = loadSecurityFacet('overview', true);
      clock.isConnected = false;          // a second load rewrote the panel
      timers[0]();
      assert(cleared.indexOf(1) >= 0, 'it stopped rather than write into the new one');
      release(null); await p;
    """)


def test_it_stops_on_a_failure_too():
    _js(FACET.replace("return new Promise(function (r) { release = r; });",
                      "return Promise.reject(new Error('HTTP 503'));"),
        ["loadSecurityFacet"], """
      await loadSecurityFacet('overview', true);
      assert(cleared.indexOf(1) >= 0, 'stopped');
      assert(host.innerHTML.indexOf('error HTTP 503') >= 0, 'and said why');
    """)


# ------------------------------------------------------------ the reports


REPORTS = r"""
var RETRY_DELAYS_MS = [1, 1, 1, 1];
function setTimeout(fn) { fn(); return 0; }
function writeToken() { return ''; }
function setWriteToken() {}
var window = { OpticAuth: { csrf: function () { return 'c'; }, state: function () { return { admin: true }; } },
               prompt: function () { return null; } };
var attempts = 0, failFirst = 0;
// The page's wait for the server (tests/test_restart_wait.py has it for real).
var originGate = null, waits = 0, serverBack = false;
function waitForOrigin() { waits++; return Promise.resolve(serverBack); }
function fetch(url, opts) {
  attempts++;
  if (attempts <= failFirst) return Promise.reject(new TypeError('Failed to fetch'));
  return Promise.resolve({ ok: true, status: 200, json: function () { return Promise.resolve({ reports: [] }); } });
}
"""


def test_a_dropped_connection_is_retried_before_anything_is_said():
    _js(REPORTS, ["retryAfter", "fetchReports"], """
      failFirst = 2;
      var data = await fetchReports(50);
      assert(Array.isArray(data.reports), 'answered');
      assert(attempts === 3, 'two drops, then the answer: ' + attempts);
    """)


def test_a_connection_that_never_comes_back_is_a_marked_error_not_the_browsers_words():
    _js(REPORTS, ["retryAfter", "fetchReports"], """
      failFirst = 99;
      var caught = null;
      try { await fetchReports(50); } catch (e) { caught = e; }
      assert(caught && caught.originUnreachable === true, 'marked');
      assert(caught.message === 'the connection dropped after 5 attempts', caught && caught.message);
      assert(attempts === 5, 'the same five tries getJSON makes');
      assert(waits === 1, 'and the same wait for the server, once');
    """)


def test_a_server_back_from_a_restart_is_asked_once_more():
    _js(REPORTS, ["retryAfter", "fetchReports"], """
      failFirst = 5; serverBack = true;
      var data = await fetchReports(50);
      assert(Array.isArray(data.reports), 'answered after the wait');
      assert(attempts === 6 && waits === 1, attempts + ' tries, ' + waits + ' waits');
    """)


def test_a_read_made_during_the_wait_joins_it():
    _js(REPORTS, ["retryAfter", "fetchReports"], """
      originGate = {}; failFirst = 1; serverBack = true;
      var data = await fetchReports(50);
      assert(attempts === 2 && waits === 1, 'no quick retries of its own: ' + attempts);
    """)


def test_the_page_offers_recovery_for_it():
    fn = RAW[RAW.index("async function loadReports("):]
    fn = fn[:fn.index("\n}\n")]
    assert "err.originUnreachable\n      ? errorHTML(err.message, { originUnreachable: true })" in fn
