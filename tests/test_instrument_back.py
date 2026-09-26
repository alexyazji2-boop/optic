"""Getting out of an instrument chart.

The chart is opened by clicking a row on the home strip, on Macro or on
Indices, and `openInstrument` has always recorded the exact view it came from.
The only control that used that was a 14px multiplication sign inside the
rail's dropdown, marked `aria-hidden`, which a reader had to open a menu to
find and a keyboard could not reach at all.

Driven in a browser: opened from Macro the button reads "Back to Macro" and
lands on Macro; opened from the home strip it reads "Back to Home" and lands on
Home. Both clear the chart on the way out.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP = (ROOT / "static/app.js").read_text()
CSS = (ROOT / "static/styles.css").read_text()


def function(name):
    return re.search(r"^(?:async )?function " + name + r"\([^\n]*\) \{.*?^\}",
                     APP, re.M | re.S).group()


def test_the_chart_offers_a_way_back():
    assert "function instrumentBackHTML(" in APP
    assert "instrumentBackHTML()" in function("renderInstrument")


def test_it_goes_back_through_the_control_that_already_existed():
    """There was a handler with no reachable control. Adding a second
    implementation of "close this chart" beside it would be two things to keep
    in step -- and the existing one already restores the exact view rather than
    the group's first tab, which is a distinction it was written to fix."""
    assert "data-close-instrument" in function("instrumentBackHTML")
    # One handler, still.
    assert APP.count("closest('[data-close-instrument]')") == 1
    handler = APP[APP.index("closest('[data-close-instrument]')"):][:600]
    assert "STATE.instrumentBack" in handler
    assert "switchView(back" in handler


def test_the_button_names_where_it_goes():
    """This chart is reachable from the home strip, Macro and Indices. "Back"
    on a page with three possible origins is a question rather than a label."""
    fn = function("instrumentBackHTML")
    assert "Back to ${esc(label)}" in fn


def test_the_name_comes_from_the_navigations_own_maps():
    """So the button and the rail menu call the same page the same thing."""
    fn = function("instrumentBackLabel")
    assert "SUB_LABELS[back]" in fn
    assert "VIEW_NAMES[back]" in fn


def test_an_unknown_origin_renders_no_button_rather_than_a_raw_id():
    """Falling through to the view id would print "market" in lowercase, which
    is the bug this file has already shipped twice in the rail menu. And a
    button promising to go "back" to a page the reader was never on -- after a
    reload, or a restored view -- is worse than no button."""
    label = function("instrumentBackLabel")
    assert label.rstrip().endswith("|| null;\n}"), label[-60:]
    html = function("instrumentBackHTML")
    assert "if (!label) return '';" in html


def test_the_control_is_reachable_by_keyboard():
    """The one it replaces was an `<i>` marked aria-hidden inside a menu."""
    fn = function("instrumentBackHTML")
    assert "<button type=\"button\"" in fn
    assert "aria-hidden" not in fn.split("inst-back-arrow", 1)[0], \
        "the button itself must not be hidden from assistive tech"
    # The arrow glyph is decorative and is hidden; the label is not.
    assert 'class="inst-back-arrow" aria-hidden="true"' in fn
    assert ".inst-back:focus-visible" in CSS


def test_the_hover_moves_the_arrow_not_the_button():
    """Moving the control itself makes the label jump under a cursor that is
    already on it."""
    rule = CSS.split(".inst-back:hover .inst-back-arrow {", 1)[1]
    rule = rule[:rule.index("}")]
    assert "translateX" in rule
    hover = CSS.split(".inst-back:hover {", 1)[1]
    hover = hover[:hover.index("}")]
    assert "transform" not in hover
