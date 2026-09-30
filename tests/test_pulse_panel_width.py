"""Pulse opens wider, and its width is saved only once somebody chooses one.

Reported as "Pulse control panel should be wider, it's a clean and better look.
Better than condensing all the information in a thin frame", then "make pulse
larger as well when the button is clicked". It opened at 382px; now 520px, or
36% of a window too narrow for that. The width had been
saved on every first load, chosen or not, so an old 382 is read as the old
default rather than a choice. Checked in a browser at 1470x785 with 382 saved
under the old key: the panel opened wider and nothing was written on load.
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
RAW = (ROOT / "static/app.js").read_text()
CSS = (ROOT / "static/styles.css").read_text()
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc"


def _raw_fn(name):
    return re.search(r"^function %s\([^\n]*\) \{.*?^\}" % name, RAW, re.M | re.S).group()


def _run(width, stored):
    exe = JSC if os.path.exists(JSC) else shutil.which("jsc")
    if not exe:
        pytest.skip("no JavaScriptCore on this machine")
    consts = "\n".join(re.search(r"^const %s = [^\n]*;" % n, RAW, re.M).group()
                       for n in ("CHAT_W_KEY", "CHAT_W_OLD_KEY", "CHAT_W_OLD_DEFAULT",
                                 "CHAT_W_DEFAULT", "CHAT_W_MIN"))
    src = ("var window = { innerWidth: %d };\n" % width
           + "var STORE = %s;\n" % json.dumps(stored)
           + "var localStorage = { getItem: function (k) { return k in STORE ? STORE[k] : null; } };\n"
           + consts + "\n" + _raw_fn("defaultChatWidth") + "\n" + _raw_fn("storedChatWidth")
           + "\nprint('RESULT:' + JSON.stringify({ d: defaultChatWidth(), s: storedChatWidth() }));")
    out = subprocess.run([exe, "-e", src], capture_output=True, text=True, timeout=30)
    assert "RESULT:" in out.stdout, out.stdout + out.stderr
    return json.loads(out.stdout.split("RESULT:", 1)[1].strip())


def test_the_default_is_520_or_a_third_of_a_small_window():
    assert _run(1470, {})["d"] == 520
    assert _run(1920, {})["d"] == 520
    assert _run(1280, {})["d"] == 461
    assert _run(1024, {})["d"] == 369
    assert _run(700, {})["d"] == 320, "never below the minimum"


def test_an_old_382_is_the_old_default_and_anything_else_was_a_choice():
    assert _run(1470, {"optic.chat.width.v1": "382"})["s"] == 520
    assert _run(1470, {"optic.chat.width.v1": "520"})["s"] == 520
    assert _run(1470, {"optic.chat.width.v2": "400", "optic.chat.width.v1": "520"})["s"] == 400
    assert _run(1470, {"optic.chat.width.v2": "junk"})["s"] == 520


def test_the_width_is_saved_when_chosen_and_not_on_load():
    install = _raw_fn("installChatResize")
    assert "applyChatWidth(storedChatWidth(), { transient: true });" in install
    assert "grip.addEventListener('dblclick', () => applyChatWidth(defaultChatWidth()));" in install
    assert "CHAT_W_DEFAULT" not in install, "every fallback is the window-aware default"
    assert "  --chat-w: 520px;" in CSS
