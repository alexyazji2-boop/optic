"""A hovered bar says when it was, in words.

The tooltip printed its label raw, so hovering an intraday bar headed two lines
of readable numbers with "2026-09-04T14:00:00-04:00". Reported as illegible,
which it is.

The part worth keeping is why this does not go through a Date. `new
Date("2026-09-04T14:00:00-04:00")` converts to whatever zone the browser is
in, so the same bar reads 2:00 pm in New York and 7:00 pm in London -- for a
bar whose identity IS its market time. Reading the digits straight out of the
string shows the time the exchange stamped it, wherever it is hovered from.

`parseBarDate` beside it converts on purpose and stays that way: an axis is
placing ticks along a line, not naming a moment.

Driven in a browser: hovering the AAPL chart headed the tooltip "Thu, Aug 20 ·
10:30 am" over "Close 317.22" and "Volume 2,996,499".
"""

from __future__ import annotations

import re
import subprocess

JSC = ("/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/"
       "Helpers/jsc")
SRC = open("static/charts.js", encoding="utf-8").read()


def _fn(name):
    start = SRC.index("function %s(" % name)
    return SRC[start:SRC.index("\n}", start) + 2]


def _run(label):
    """Evaluate the real function under JavaScriptCore.

    Source-level assertions cannot tell a correct formatter from one that
    returns the string unchanged, which is the failure being fixed."""
    script = _fn("barLabelText") + "\nprint(barLabelText(%s));" % _js(label)
    out = subprocess.run([JSC, "-e", script], capture_output=True, text=True)
    return out.stdout.strip()


def _js(value):
    return '"%s"' % value.replace('"', '\\"') if isinstance(value, str) else "null"


import pytest  # noqa: E402

jsc = pytest.mark.skipif(
    subprocess.run(["test", "-x", JSC]).returncode != 0,
    reason="JavaScriptCore not available",
)


@jsc
def test_an_intraday_bar_reads_as_a_day_and_a_time():
    assert _run("2026-09-04T14:00:00-04:00") == "Fri, Sep 4 · 2:00 pm"


@jsc
def test_the_time_is_the_one_in_the_stamp_not_the_browser_s():
    """Two bars an hour apart in the same offset stay an hour apart, and
    neither is shifted by where this runs. A Date round-trip would move both
    by the local offset."""
    assert _run("2026-12-31T09:30:00-05:00") == "Thu, Dec 31 · 9:30 am"
    assert _run("2026-12-31T10:30:00-05:00") == "Thu, Dec 31 · 10:30 am"


@jsc
def test_a_daily_bar_has_no_time_so_it_gets_the_year():
    assert _run("2026-03-09") == "Mon, Mar 9, 2026"


@jsc
def test_a_label_it_cannot_read_survives_unchanged():
    """Better a raw label than a wrong one, and better than an exception in a
    mousemove handler."""
    assert _run("Q3 2026") == "Q3 2026"
    assert _run("") == ""


def test_both_tooltips_use_it():
    """The MACD pane builds its own tooltip from the same labels, and was the
    second place showing a machine timestamp."""
    assert SRC.count("barLabelText(labels[i])") == 2


def test_the_axis_still_converts():
    """`parseBarDate` is not the same job and must not be swept into this:
    it places ticks, and its own comment records the month-boundary bug that
    the T00:00:00 suffix fixes."""
    fn = _fn("parseBarDate")
    assert "new Date(iso)" in fn
    assert "T00:00:00" in fn
