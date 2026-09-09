"""The colour of the price mark, and the attribute collision it walked into.

Client contracts, read as text: there is no JS runner here, and every silent
client failure in this codebase has been a wiring failure rather than a logic
one. See tests/test_ui_refactor.py for the pattern.

The test worth reading first is the namespace one. `data-ws-color` was already
taken by the indicator style editor, so the first version of this feature
rendered swatches that the *overlay* handler matched: it called
`setOverlayStyle(undefined, ...)`, which rejects an unknown id, and returned.
Nothing threw, nothing was corrupted, the menu closed and no colour changed.
That is the exact shape of a dead control, and only driving it found it.
"""

from __future__ import annotations

import re

APP_JS = open("static/app.js").read()
CHARTS_JS = open("static/charts.js").read()
CSS = open("static/styles.css").read()
HTML = open("static/index.html").read()


def _fn(src: str, name: str) -> str:
    """The source of one top-level function, up to the next one."""
    start = src.index("function %s(" % name)
    nxt = src.find("\nfunction ", start + 1)
    return src[start:nxt if nxt > 0 else len(src)]


# ------------------------------------------------------- the collision itself


def test_the_price_mark_controls_do_not_reuse_data_ws_color():
    """`data-ws-color` belongs to the overlay style editor, and its handler sits
    earlier in the same click listener. A second feature emitting that attribute
    is not a conflict the browser reports; it is a control that takes the click
    and does nothing."""
    emitted = re.findall(r'data-ws-color="([^"]*)"', APP_JS)
    assert emitted == ["${tok}"], emitted        # the overlay editor, and only it

    for attr in ("data-ws-mark", "data-ws-mark-value", "data-ws-mark-clear",
                 "data-ws-mark-pick", "data-ws-mark-reset", "data-ws-mark-warn"):
        assert attr in APP_JS, attr


def test_every_price_mark_attribute_has_a_handler():
    """Every control needs a handler. A dead control does not error: it takes
    the click and nothing happens, which reads as a slow app."""
    emitted = set(re.findall(r'(data-ws-mark[a-z-]*)=', APP_JS))
    assert emitted, "no price-mark controls found at all"
    for attr in emitted:
        if attr in ("data-ws-mark-value", "data-ws-mark-warn"):
            continue          # read from / written to, not matched on
        assert "closest('[%s]')" % attr in APP_JS, attr


def test_no_handler_claims_an_attribute_nothing_renders():
    """The other direction, for this feature's namespace."""
    claimed = set(re.findall(r"closest\('\[(data-ws-mark[a-z-]*)\]'\)", APP_JS))
    assert claimed
    for attr in claimed:
        assert '%s="' % attr in APP_JS or "%s\n" % attr in APP_JS, attr


# ---------------------------------------------------------------- the defaults


def test_the_defaults_are_the_slots_each_mark_already_used():
    """Candles have always been s3/s8 and the line s1. Changing any of these
    would restyle every chart in the app on the way to making them
    configurable, for readers who never asked for a colour."""
    fn = _fn(APP_JS, "chartColorDefault")
    assert "C.s3" in fn and "C.s8" in fn and "C.s1" in fn


def test_charts_js_falls_back_to_the_same_slots():
    """app.js always passes an explicit value, so this is a safety net for other
    callers. If the two disagreed, the picker's idea of "default" and the
    chart's would drift apart silently."""
    assert "candleUp || C.s3" in CHARTS_JS
    assert "candleDown || C.s8" in CHARTS_JS


def test_volume_keeps_its_own_pair_unless_a_colour_was_chosen():
    """The volume strip is pos/neg and the candles are s3/s8: they were never
    the same pair. Passing chartColor() for volume would move every
    deployment's volume bars off pos/neg the moment this shipped."""
    assert APP_JS.count("volUp: chartColors.up || null") == 2      # both charts
    assert APP_JS.count("volDown: chartColors.down || null") == 2
    assert "volUp: chartColor(" not in APP_JS
    assert "volUp || C.pos" in CHARTS_JS
    assert "volDown || C.neg" in CHARTS_JS


def test_both_charts_get_the_same_colours():
    """The Charting tab and the Swing chart draw the same instrument. WS_FLAGS
    already shares the overlay toggles for this reason."""
    assert APP_JS.count("candleUp: chartColor('up')") == 2
    assert APP_JS.count("candleDown: chartColor('down')") == 2
    # Both `Close` series, by name. A global count of chartColor('line') was the
    # wrong shape: it is legitimately read by chartBaseColors and by the Swing
    # tab's line-mode legend key as well, so the number moved for good reasons.
    assert APP_JS.count("color: wsCandles(ps) ? C.ink : chartColor('line')") == 1
    assert APP_JS.count("color: candleMode ? C.ink : chartColor('line')") == 1


# ------------------------------------------------------------------ the store


def test_only_the_three_known_slots_are_read_back():
    """A bad value reaches an SVG `fill`, where it fails silently."""
    assert "CHART_COLOR_SLOTS = ['up', 'down', 'line']" in APP_JS
    load = APP_JS[APP_JS.index("CHART_COLORS_KEY = "):APP_JS.index("function isColor")]
    assert "CHART_COLOR_SLOTS.forEach" in load
    assert "isColor(raw[k])" in load


def test_null_means_the_theme_not_a_frozen_copy_of_it():
    """The app has a light and a dark theme and syncChartTheme() swaps C when
    the OS flips. Storing the theme's current value would pin a reader who never
    chose anything to whichever theme they first loaded."""
    assert "chartColors[slot] || chartColorDefault(slot)" in _fn(APP_JS, "chartColor")


def test_a_junk_value_clears_the_slot_rather_than_storing_it():
    fn = _fn(APP_JS, "setChartColor")
    assert "isColor(value)" in fn
    assert "delete chartColors[slot]" in fn


def test_hexish_rejects_what_it_cannot_parse():
    """A probe given an unparseable value does not fail, it inherits, so this
    answered "#f5f1ec" (--ink) for the input "nonsense". Measured."""
    assert "if (!isColor(value)) return '#000000';" in _fn(APP_JS, "hexish")


def test_the_preset_labels_name_the_colour_they_show():
    """The first pass labelled s5 Violet (it is pink, hue 338), s6 Pink (lime,
    90), s7 Cyan (violet, 247) and s8 Rust (coral, hue 0). A tooltip that
    misnames the swatch under the cursor is worse than no tooltip."""
    block = APP_JS[APP_JS.index("CHART_COLOR_PRESETS = ["):]
    block = block[:block.index("];")]
    for slot, label in (("s5", "Pink"), ("s6", "Lime"),
                        ("s7", "Violet"), ("s8", "Coral")):
        assert "{ slot: '%s', label: '%s' }" % (slot, label) in block, slot


def test_the_presets_are_tokens_that_exist():
    block = APP_JS[APP_JS.index("CHART_COLOR_PRESETS = ["):]
    block = block[:block.index("];")]
    slots = re.findall(r"slot: '([a-z0-9]+)'", block)
    assert len(slots) == 12
    # Every one has to be a slot charts.js actually syncs, or C[slot] is
    # undefined and the swatch renders as a transparent gap.
    for slot in slots:
        assert "%s: '--" % slot in CHARTS_JS, slot


# ------------------------------------------------------------------ the wheel


def test_the_wheel_does_not_rebuild_the_toolbar():
    """`<input type="color">` opens the OS picker, and that picker belongs to
    this input element. Replacing the toolbar's HTML while it is open destroys
    the element and the picker shuts with it."""
    assert "wsRedrawChart({ keepToolbar: true })" in APP_JS
    assert "if (!(opts && opts.keepToolbar))" in _fn(APP_JS, "wsRedrawChart")


def test_the_wheel_redraw_is_coalesced():
    """`input` fires on every movement of the wheel, and a redraw is the whole
    chart."""
    assert "cancelAnimationFrame(wsColorFrame)" in APP_JS
    assert "wsColorFrame = requestAnimationFrame" in APP_JS


def test_the_contrast_warning_updates_during_the_drag():
    """The moment it is worth having. It used to render only on a toolbar
    rebuild, which the wheel skips by design, so it was absent for the whole
    gesture and appeared afterwards."""
    handler = APP_JS[APP_JS.index("closest('[data-ws-mark-pick]')"):]
    handler = handler[:handler.index("const box = evt.target.closest")]
    assert "colorContrast(wheel.value)" in handler
    assert "warn.hidden = !poor" in handler
    assert "markWarnText(ratio)" in handler


def test_the_warning_sentence_has_one_source():
    """The popover renders it and the wheel rewrites it; two copies drift."""
    assert APP_JS.count("Hard to see against the chart background") == 1
    assert "function markWarnText(" in APP_JS


def test_the_warning_element_is_always_rendered():
    """Toggled by `hidden` rather than created on demand: inserting a node into
    the row mid-gesture moves the wheel out from under the cursor."""
    assert 'class="wc-warn" data-ws-mark-warn=' in APP_JS
    # And the [hidden] pair, per the house rule.
    assert ".wc-warn[hidden] { display: none; }" in CSS


def test_the_threshold_is_the_graphical_one_not_the_text_one():
    """A candle body is a graphical object: 3:1, not 4.5:1."""
    assert "ratio < 3" in APP_JS
    assert "contrast < 3" in APP_JS


# -------------------------------------------------------------------- styling


def test_every_wc_class_has_a_rule():
    """A class with no rule is an unstyled string in a popover."""
    used = set(re.findall(r'class="(wc-[a-z-]+)', APP_JS))
    assert {"wc-row", "wc-swatch", "wc-warn", "wc-now", "wc-wheel"} <= used, used
    for cls in used:
        assert ".%s" % cls in CSS, cls


def test_no_hex_colours_were_added_to_the_stylesheet():
    """Tokens only, per the design system. The reader's own colour is a runtime
    value on an element, never a declaration in here."""
    block = CSS[CSS.index(".ws-colors"):CSS.index(".ws-body")]
    assert not re.findall(r"#[0-9a-fA-F]{3,8}\b", block)


def test_the_selected_ring_does_not_shrink_the_swatch():
    """A border would eat 2px of the colour area, and the ring needs a gap so it
    reads against a swatch of any colour including one close to --ink."""
    block = CSS[CSS.index(".wc-swatch.on"):]
    assert "box-shadow" in block[:220]


# ------------------------------------------------------- the VIX pulse tile


def test_the_vix_inversion_never_comes_back():
    """A red "+2.16%" reads as a rendering fault, and was reported as one.

    The four-tile block this originally guarded was replaced by the market
    strip, which supersedes it: same instruments, more of them, one band. The
    invariant outlives the element, so it is asserted over the whole file now
    rather than inside one function."""
    # The exact expression the tile used, which negated VIX before toning it.
    assert "-m.chg_1d" not in APP_JS, "the inversion is back"
    # And the tile itself is gone rather than merely unrendered.
    assert "function homePulseStrip" not in APP_JS


def test_the_strip_still_says_the_direction_in_words():
    """`macroWord` was the fix for the red plus and it is still the only place
    that wording lives. The strip is now its caller."""
    fn = _fn(APP_JS, "macroWord")
    assert "hedging pricier" in fn and "hedging cheaper" in fn
    assert "yields up" in fn and "yields down" in fn
    # An unchanged number with a direction word beside it reads as a move.
    assert "Math.abs(change) < 0.05" in fn
    strip = _fn(APP_JS, "marketStripHTML")
    assert "macroWord(inst.symbol, chg)" in strip
    assert "'^VIX'" in strip and "'^TNX'" in strip


def test_the_strip_colours_every_cell_by_sign():
    """The opposite of what the tiles needed, and the reason is in the comment:
    a raw quote strip makes no claim for the colour to contradict, so red
    meaning "this went down" in every cell is the consistent choice."""
    strip = _fn(APP_JS, "marketStripHTML")
    assert "signClass(chg)" in strip


def test_no_em_dashes_in_the_copy_a_reader_sees():
    for text in re.findall(r"'([^'\n]{10,})'", _fn(APP_JS, "macroWord")):
        assert "—" not in text, text
    assert "—" not in _fn(APP_JS, "markWarnText")
