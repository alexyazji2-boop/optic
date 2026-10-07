"""The chart workspace's two rails: drawn marks, names, and room for the chart.

Measured 2026-10-06 at 1440x900 and 375x812:
- The widget rail's sixteen buttons were Unicode glyphs, and two pairs were the
  same character (Watch and Key levels a trigram, Insiders and Pulse a fisheye),
  under 9px labels the Text size setting could not reach.
- The drawing tools had no accessible names, so a screen reader read the glyph
  ("box drawings light diagonal"), and Delete was a colour emoji.
- A widget's close button was opacity 0 until hovered, and display:none with
  Pulse open, where the rail's own toggle is disabled too.
- On a phone the drawing tools were a two-wide column, 77px of a 338px
  workspace, and the chart drew in 261px.
- On a phone opened with Notes left open on a laptop, the rail lit Notes over a
  dock the narrow layout hides, and pressing it closed what was not showing.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP = (ROOT / "static/app.js").read_text()
CSS = (ROOT / "static/styles.css").read_text()


def _block(head, end="\n];"):
    body = APP.split(head, 1)[1]
    return body[:body.index(end)]


def _fn(head):
    at = APP.index(head)
    return APP[at:APP.index("\n}\n", at) + 3]


def test_every_widget_wears_a_mark_of_its_own():
    widgets = _block("const WS_WIDGETS = [")
    icons = re.findall(r"icon: '([^']+)'", widgets)
    ids = re.findall(r"\{ id: '([a-z]+)'", widgets)
    assert len(icons) == len(ids) == 15
    assert len(set(icons)) == len(icons), "two widgets share a mark"
    assert "&#" not in widgets, "a Unicode glyph is back"
    assert all("<path" in i or "<circle" in i or "<rect" in i for i in icons)
    rail = _fn("function wsWidgetRail() {")
    assert "${wsWidgetIcon(w.icon)}" in rail
    assert "pulseMarkHTML('pulse-glyph-sm')" in rail, "Pulse wears its own mark, not a fisheye"
    assert "&#9673;" not in rail


def test_the_rail_labels_follow_the_type_scale_and_fit_on_one_line():
    assert ".ws-wrail-lab { font-size: var(--t-micro); white-space: nowrap;" in CSS
    assert "short: 'Levels'" in _block("const WS_WIDGETS = [")
    assert "${esc(w.short || w.label)}" in _fn("function wsWidgetRail() {")


def test_every_drawing_tool_has_a_name_and_a_drawn_mark():
    tools = _block("const WS_TOOLS = [")
    assert "glyph:" not in tools
    assert len(re.findall(r"icon: '", tools)) == len(re.findall(r"\{ id: '", tools)) == 15
    rail = _fn("function wsToolRail() {")
    assert 'aria-label="${esc(t.label)}"' in rail and "${wsWidgetIcon(t.icon)}" in rail
    for name in ('aria-label="Undo"', 'aria-label="Redo"', 'aria-label="Snap to candles"',
                 'aria-label="Delete every drawing on this symbol"'):
        assert name in rail, name
    assert "&#128465;" not in rail, "the colour-emoji bin"


def test_a_widget_can_always_be_closed_from_its_own_head():
    rule = CSS.split(".ws-widget .ws-widget-head .ws-leg-btn {", 1)[1].split("}", 1)[0]
    assert "opacity: 1;" in rule and "display: inline-flex;" in rule
    assert "min-width: 24px;" in rule and "min-height: 24px;" in rule
    # More specific than the rule that hides the legend's buttons with Pulse open.
    assert "body.chat-open .ws-leg-btn" in CSS
    assert ".ws-leg-row:focus-within .ws-leg-btn { opacity: 1; }" in CSS
    assert "@media (hover: none) {\n  .ws-leg-btn { opacity: 1; }\n}" in CSS


def test_a_phone_draws_the_tools_as_a_row_and_the_chart_full_width():
    block = CSS.split("The drawing tools on a phone: one row above the chart", 1)[1]
    block = block[:block.index("\n}\n", block.index("@media (max-width: 559px) {")) + 2]
    assert "grid-template-columns: minmax(0, 1fr);" in block
    assert "body.chat-open .ws-body" in block and ".ws-body.narrow" in block
    assert "flex-direction: row;" in block and "overflow-x: auto;" in block


def test_the_widget_rail_is_redrawn_when_the_layout_crosses_narrow():
    fn = _fn("function wsSyncNarrow() {")
    assert "const was = body.classList.contains('narrow');" in fn
    assert "if (was !== body.classList.contains('narrow')) {" in fn
    assert "rail.outerHTML = wsWidgetRail();" in fn
