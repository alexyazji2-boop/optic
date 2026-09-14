"""One number that scales the whole interface.

Reported three times, each time as the UI not fitting or looking shrunk, and
three times I changed a width and measured the wrong axis. The complaint was
never the column: it was that 13px table body and 15px prose, written when 1280
was a big screen, read as a small page inside a large window.

So the absolute size is a control now rather than a value I guess at. The ratios
between elements are the design and do not move; the size is a viewing
preference, and a 13px table on a 27-inch monitor and the same table on a
13-inch laptop are different readings of one stylesheet.
"""

import os
import re
import shutil
import subprocess

import pytest

JSC = ("/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/"
       "Helpers/jsc")

CSS = open("static/styles.css", encoding="utf-8").read()
APP_JS = open("static/app.js", encoding="utf-8").read()
INDEX = open("static/index.html", encoding="utf-8").read()


def inline_table():
    """The `{ compact: 1, large: 1.3 }` literal, and nothing around it.

    Sliced by its braces rather than by a character window: the first attempt
    took 200 characters before the key and caught the word "default" out of the
    comment above, which is a test matching its own explanation."""
    at = INDEX.index("optic.ui.scale.v1")
    open_at = INDEX.rindex("{", 0, at)
    return INDEX[open_at:INDEX.index("}", open_at) + 1]


def token_block():
    start = CSS.index("--ui-scale:")
    return CSS[start:CSS.index("--r-xs:", start)]


def test_there_is_one_knob():
    assert re.search(r"--ui-scale: [\d.]+;", CSS)


def test_every_spacing_step_is_on_it():
    """The 4px grid survives as a 4.6px grid: still one rhythm, still nine
    steps. A step left as a literal would drift out of the rhythm the moment
    the scale changed, and the rhythm is the ratio between them rather than the
    numbers themselves."""
    block = token_block()
    for n in range(10):
        line = re.search(r"--space-%d: ([^;]+);" % n, block)
        assert line, "--space-%d missing" % n
        assert "var(--ui-scale)" in line.group(1), "--space-%d is a literal" % n


def test_every_type_step_is_on_it():
    """Type and spacing have to move together or the design changes rather than
    the size: larger text in the same boxes is a different layout, not a zoom."""
    block = token_block()
    names = ["micro", "caption", "small", "body", "base", "lead", "heading",
             "d3", "d2", "d1"]
    for name in names:
        line = re.search(r"--t-%s: ([^;]+);" % name, CSS)
        assert line, "--t-%s missing" % name
        assert "var(--ui-scale)" in line.group(1), "--t-%s is a literal" % name


def test_the_scales_bracket_the_original_density():
    """Compact has to be the density the terminal shipped with, or a reader who
    preferred it has nowhere to go back to."""
    block = APP_JS[APP_JS.index("const UI_SCALES = ["):]
    block = block[:block.index("];")]
    assert "value: 1," in block, "no scale returns to the original"
    values = [float(v) for v in re.findall(r"value: ([\d.]+)", block)]
    assert values == sorted(values), values
    assert max(values) <= 1.5, "past this the app is a magnifier, not a preference"


@pytest.fixture(scope="module")
def ran():
    """Drive applyUiScale for real, under JavaScriptCore.

    A source check cannot tell a guard from a guard wrapped in `if (false)`,
    which is how the first version of the next test passed a mutation. These
    call the function against a fake root and report which of setProperty and
    removeProperty it reached."""
    exe = JSC if os.path.exists(JSC) else shutil.which("jsc")
    if not exe:
        pytest.skip("no JavaScriptCore on this machine")
    script = r"""
      load('tests/support/browser_stubs.js');
      try { load('static/charts.js'); load('static/app.js'); } catch (e) { }

      var calls = [];
      document.documentElement.style.setProperty =
        function (k, v) { calls.push('set:' + k + '=' + v); };
      document.documentElement.style.removeProperty =
        function (k) { calls.push('remove:' + k); };
      var stored = null;
      localStorage.getItem = function () { return stored; };
      localStorage.setItem = function (k, v) { stored = v; };

      function run(pref) { stored = pref; calls = []; applyUiScale(); return calls.join('|'); }
      print('DEFAULT:' + run('default'));
      print('UNSET:' + run(null));
      print('LARGE:' + run('large'));
      print('COMPACT:' + run('compact'));
      print('JUNK:' + run('enormous'));
    """
    proc = subprocess.run([exe, "-e", script], capture_output=True, text=True, timeout=120)
    return proc.stdout + proc.stderr


def line(ran, key):
    assert key in ran, ran[-900:]
    return ran.split(key)[1].split("\n")[0].strip()


def test_the_default_writes_nothing(ran):
    """The shipped size is the stylesheet's own value, so a reader inspecting
    the page sees a stylesheet rather than an inline override to unpick."""
    assert line(ran, "DEFAULT:") == "remove:--ui-scale"
    assert line(ran, "UNSET:") == "remove:--ui-scale"


def test_the_other_sizes_do_write(ran):
    assert line(ran, "LARGE:") == "set:--ui-scale=1.3"
    assert line(ran, "COMPACT:") == "set:--ui-scale=1"


def test_a_value_that_is_not_one_of_the_three_falls_back(ran):
    """A stale key from an older build, or a hand-edited one, must not leave the
    app on an undefined scale. localStorage is reader-writable by definition."""
    assert line(ran, "JUNK:") == "remove:--ui-scale"


def test_the_topbar_is_remeasured_when_the_size_changes():
    """--topbar-h is published by a ResizeObserver and the bar is one, two or
    three rows depending on width. The rows just changed height, and everything
    that positions against the bar reads that variable."""
    fn = APP_JS[APP_JS.index("function applyUiScale()"):]
    fn = fn[:fn.index("\nfunction ")]
    assert "trackTopbarHeight" in fn


def test_the_preference_is_applied_before_the_first_paint():
    """app.js loads at the end of the body, so anything done there runs after
    the page has been laid out once. A reader on Compact or Large would watch
    the whole interface resize in front of them on every load."""
    head = INDEX[:INDEX.index("</head>")]
    assert "optic.ui.scale.v1" in head, "the preference is read after the paint"
    assert head.index("optic.ui.scale.v1") > head.index("styles.css"), (
        "it has to run after the stylesheet it overrides")


def test_the_inline_boot_and_the_module_agree_on_the_numbers():
    """Two copies of the same table, in two languages, in two files. They drift
    the moment one is edited, and the symptom is a flash of the wrong size on
    every load rather than anything that fails."""
    head = INDEX[:INDEX.index("</head>")]
    inline = dict((k, float(v)) for k, v in re.findall(r"(\w+): ([\d.]+)", inline_table()))
    block = APP_JS[APP_JS.index("const UI_SCALES = ["):]
    block = block[:block.index("];")]
    module = dict((i, float(v)) for i, v in
                  re.findall(r"id: '(\w+)', value: ([\d.]+)", block))
    for name, value in inline.items():
        assert module.get(name) == value, "%s: %s inline, %s in app.js" % (
            name, value, module.get(name))


def test_the_default_is_not_in_the_inline_table():
    """It writes nothing, so listing it would be a third place the shipped
    value is recorded and a third place it can disagree with the other two."""
    assert "default" not in inline_table()
