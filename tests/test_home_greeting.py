"""The home page greets a signed-in reader by first name.

Asked for with a screenshot of "Good evening." and "Overnight" beside it:
"when logged in, say "good evening, 'users first name'"". The account's own
first name, so a sign-in that never gave one is greeted as a guest is, and
nothing is made up from an email address. The name is written as text, and it
updates when the sign-in answer lands after the page has drawn.
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


def _hello(state):
    exe = JSC if os.path.exists(JSC) else shutil.which("jsc")
    if not exe:
        pytest.skip("no JavaScriptCore on this machine")
    script = """
      load('tests/support/browser_stubs.js');
      document.documentElement.style = document.documentElement.style || {};
      document.documentElement.style.setProperty = function () {};
      document.documentElement.style.removeProperty = function () {};
      try { load('static/charts.js'); load('static/app.js'); } catch (e) {}
      window.OpticAuth = { state: function () { return %s; } };
      print('RESULT:' + JSON.stringify({ hello: homeHello(), plain: homeGreeting() }));
    """ % json.dumps(state)
    out = subprocess.run([exe, "-e", script], capture_output=True, text=True,
                         timeout=120, cwd=str(ROOT))
    assert "RESULT:" in out.stdout, (out.stdout + out.stderr)[-2000:]
    return json.loads(out.stdout.split("RESULT:", 1)[1].split("\n")[0])


def test_a_signed_in_reader_is_greeted_by_first_name():
    got = _hello({"status": "user", "user": {"first_name": " Sam ", "email": "sam@example.test"}})
    assert re.fullmatch(r"Good (morning|afternoon|evening), Sam\.", got["hello"]), got
    assert got["hello"].startswith(got["plain"])


def test_a_guest_and_a_nameless_account_are_greeted_plainly():
    for state in ({"status": "guest", "user": None},
                  {"status": "user", "user": {"first_name": "", "email": "sam@example.test"}},
                  {"status": "loading", "user": None}):
        got = _hello(state)
        assert got["hello"] == got["plain"] + ".", state
    # Nothing taken from the address.
    assert "sam" not in _hello({"status": "user", "user": {"email": "sam@example.test"}})["hello"].lower()


def test_the_name_is_written_as_text_and_follows_the_sign_in():
    assert '<h2 class="hm-hello">${esc(homeHello())}</h2>' in APP
    sub = APP[APP.index("window.OpticAuth.on(() => {\n    paintNav(STATE.view || 'home');"):][:400]
    assert "hello.textContent = homeHello();" in sub
