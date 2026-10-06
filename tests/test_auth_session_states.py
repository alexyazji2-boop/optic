"""A sign-in check that failed is not a sign-out, and a sign-out that failed
is not one either.

Reproduced from the code before the fix:

* any error from /api/auth/me set the state to `guest`, and the page took that
  for a sign-out: the device session put the account's things away and
  reloaded into the guest's, and the next good read reloaded back;
* signing out said "Signed out" even when the logout request never reached the
  server, whose httpOnly session cookie then stayed valid;
* a brand-new account adopted the starter watchlist (SPY, QQQ, NVDA, AMD) as
  the reader's own, because an empty browser reads as that starter set.

These run the real static/auth.js in JavaScriptCore with fetch stubbed.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
APP = (ROOT / "static/app.js").read_text()
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc"


def run_auth(fetch_js, scenario):
    exe = JSC if os.path.exists(JSC) else shutil.which("jsc")
    if not exe:
        pytest.skip("no JavaScriptCore on this machine")
    src = """
      load('tests/support/browser_stubs.js');
      var timers = [];
      setTimeout = function (fn, ms) { timers.push(ms); return timers.length; };
      var toasts = [];
      fetch = window.fetch = %s;
      load('static/auth.js');
      window.OpticAuth.toast = function (m, k) { toasts.push([m, k || '']); };
      var R = {};
      (async function () { %s })().then(function () {
        print('RESULT:' + JSON.stringify(R));
      }, function (e) { print('RESULT:' + JSON.stringify({error: String(e)})); });
    """ % (fetch_js, scenario)
    out = subprocess.run([exe, "-e", src], capture_output=True, text=True, timeout=60, cwd=str(ROOT))
    blob = out.stdout + out.stderr
    assert "RESULT:" in blob, blob[-2000:]
    return json.loads(blob.split("RESULT:", 1)[1].split("\n")[0])


DOWN = "function () { return Promise.reject(new TypeError('Failed to fetch')); }"


def test_a_failed_check_is_unknown_not_guest_and_is_retried():
    out = run_auth(DOWN, """
      await window.OpticAuth.load();
      var st = window.OpticAuth.state();
      R.status = st.status; R.error = st.error; R.retries = timers.slice();
    """)
    assert out["status"] == "unknown"
    assert "connection dropped" in out["error"].lower()
    assert 15000 in out["retries"]


ME_THEN_DOWN = """function (path) {
  if (String(path).indexOf('/api/auth/me') >= 0) {
    return Promise.resolve({ok: true, status: 200, json: function () {
      return Promise.resolve({authenticated: true, user: {id: 'u1', email: 'a@example.com'}}); }});
  }
  return Promise.reject(new TypeError('Failed to fetch'));
}"""


def test_a_logout_that_failed_leaves_the_reader_signed_in():
    out = run_auth(ME_THEN_DOWN, """
      await window.OpticAuth.load();
      R.before = window.OpticAuth.state().status;
      await window.OpticAuth.signOut();
      R.after = window.OpticAuth.state().status;
    """)
    assert out == {"before": "user", "after": "user"}
    src = (ROOT / "static/auth.js").read_text()
    block = src.split("async function signOut() {", 1)[1].split("\n  }\n", 1)[0]
    assert "Could not sign out" in block and "still signed in" in block


def test_the_page_moves_nobodys_data_on_an_unknown_state():
    block = APP.split("window.OpticAuth.on((state) => {", 1)[1][:400]
    assert "state.status === 'unknown'" in block.split("keepDeviceSession(state)", 1)[0]


def test_only_a_stored_watchlist_is_adopted_into_a_new_account():
    block = APP.split("async function accountLoad() {", 1)[1].split("\n}\n", 1)[0]
    adopt = block[:block.index("/api/watchlists/adopt")]
    assert "localStorage.getItem(WATCH_KEY) !== null" in adopt
    assert "const local = stored ? localWatchList() : [];" in adopt
