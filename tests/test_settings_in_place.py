"""A Settings change keeps the page where it was, and fades in.

Reported by a user as "When changing the Appearance, Text Size, etc, the
screen glitches and it scrolls the page down. It should be a nice and smooth
transition". Measured at 1470x785: Large moved the button under the cursor
144px down the screen and Default moved it 144px back, with the scroll
position unchanged. After: the pressed button stays within a pixel of where it
was through every text size and theme change, the page scrolling by the
difference instead, and the change crossfades where the browser can.
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
CSS = (ROOT / "static/styles.css").read_text()
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc"

HARNESS = """
function assert(v, m) { if (!v) throw new Error(m); }
var top = 300, scrolled = [], focusedNew = 0, transitions = 0, still = false;
var control = { matches: function (sel) { return sel === '#c'; },
  getBoundingClientRect: function () { return { top: top }; },
  focus: function () { focusedNew++; } };
var document = { activeElement: null,
  querySelector: function (sel) { return sel === '#c' ? control : null; } };
var window = { scrollY: 500,
  scrollTo: function (o) { scrolled.push(o.top); window.scrollY = o.top; },
  matchMedia: function () { return { matches: still }; } };
function withTransitions(on) {
  document.startViewTransition = on ? function (fn) { transitions++; fn(); } : undefined;
}
"""


def _run(scenario):
    exe = JSC if os.path.exists(JSC) else shutil.which("jsc")
    if not exe:
        pytest.skip("no JavaScriptCore on this machine")
    fn = re.search(r"^function applySettingInPlace\([^\n]*\) \{.*?^\}", RAW, re.M | re.S).group()
    out = subprocess.run([exe, "-e", HARNESS + fn + "\n" + scenario + "\nprint('TEST_OK');"],
                         capture_output=True, text=True, timeout=30)
    assert "TEST_OK" in out.stdout, out.stdout + out.stderr


def test_the_pressed_control_is_put_back_where_it_was():
    _run("""
      withTransitions(true);
      applySettingInPlace('#c', function () { top = 444; });
      assert(scrolled.length === 1 && scrolled[0] === 644, 'scrolled by the 144px it moved');
      assert(transitions === 1, 'faded in');
    """)


def test_nothing_scrolls_when_nothing_moved():
    _run("""
      withTransitions(true);
      applySettingInPlace('#c', function () { top = 300.4; });
      assert(scrolled.length === 0, 'under a pixel is not a move');
    """)


def test_less_motion_or_no_transitions_still_changes_in_place():
    _run("""
      still = true; withTransitions(true);
      applySettingInPlace('#c', function () { top = 200; });
      assert(transitions === 0 && scrolled[0] === 400, 'at once, and still in place');
      still = false; withTransitions(false); scrolled = []; top = 300;
      applySettingInPlace('#c', function () { top = 350; });
      assert(scrolled[0] === 450, 'without view transitions too');
    """)


def test_focus_stays_on_the_control_that_had_it():
    _run("""
      withTransitions(false);
      document.activeElement = control;
      applySettingInPlace('#c', function () {});
      assert(focusedNew === 1, 'refocused');
      document.activeElement = null; focusedNew = 0;
      applySettingInPlace('#c', function () {});
      assert(focusedNew === 0, 'not given focus it did not have');
    """)


def test_every_settings_control_goes_through_it():
    assert "applySettingInPlace(`[data-set-mode=\"${mode}\"]`, () => setUiMode(mode));" in RAW
    assert "applySettingInPlace(`[data-set-scale=\"${id}\"]`, () => setUiScale(id));" in RAW
    assert "applySettingInPlace(`[data-set-theme=\"${theme}\"]`, () => {" in RAW
    assert "applySettingInPlace('#tz-select', () => {" in RAW


def test_the_crossfade_is_slow_enough_to_read_as_a_fade():
    rule = CSS[CSS.index("::view-transition-old(root),\n::view-transition-new(root) {"):]
    rule = rule[:rule.index("}")]
    assert "animation-duration: 260ms;" in rule
