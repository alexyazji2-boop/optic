"""The insider filings widget, and the label that was wrong on every row.

`recent_transactions` carries `shares` as a positive magnitude and puts the
direction in a separate `action` field. The dock widget branched on
`shares > 0 ? 'Bought' : 'Sold'`, which is true for every row, so it rendered
six consecutive green "Bought" lines on TSLA where three were sales and three
were option conversions. Not one was a purchase.

The Analysis tab's table has always read `action`, with a three-way on
purchase / sale / other. `insiderEvents` drops `other` from the chart markers
and says why. The dock widget was the surface that never got either.
"""

from __future__ import annotations

import re

APP_JS = open("static/app.js").read()
CSS = open("static/styles.css").read()


def _fn(name: str) -> str:
    start = APP_JS.index("function %s(" % name)
    nxt = APP_JS.find("\nfunction ", start + 1)
    return APP_JS[start:nxt if nxt > 0 else len(APP_JS)]


def test_direction_comes_from_action_not_the_sign_of_shares():
    """The defect. `shares` is a magnitude, so its sign decided nothing.

    Asserted on the two lines that pick the word and the tone rather than on
    the absence of the string `shares > 0`: a first version of this test checked
    only for that literal, and a mutation written as
    `Number(t.shares || 0) > 0` reintroduced the bug and passed."""
    fn = _fn("insiderRow")
    assert "String(t.action || '').toLowerCase()" in fn
    decide = [line for line in fn.split("\n")
              if re.match(r"\s*(const (tone|word) =|\s*: action ===)", line)]
    assert decide, fn
    joined = " ".join(decide)
    assert "action ===" in joined
    assert "shares" not in joined, joined
    assert "'Bought'" in fn and "'Sold'" in fn


def test_an_exercise_is_neither_bought_nor_sold():
    """Musk's 304M-share conversion is not somebody buying stock. Colouring it
    green because the holding went up is the same error in a subtler form."""
    fn = _fn("insiderRow")
    assert "'Other'" in fn
    # Three-way, and the fallback tone is empty rather than a direction.
    assert "action === 'purchase' ? 'up' : action === 'sale' ? 'down' : ''" in fn


def test_it_agrees_with_the_analysis_tab_and_the_chart_markers():
    """Three surfaces read the same field; they used to give three answers."""
    # The Analysis table: three-way on action.
    assert "tx.action === 'purchase' ? 'up' : tx.action === 'sale' ? 'down' : ''" in APP_JS
    # The chart markers: `other` dropped, not drawn as a sell.
    events = _fn("insiderEvents")
    assert "if (action !== 'purchase' && action !== 'sale') return;" in events


def test_the_amounts_are_shown():
    """What was asked for. Shares always, value when the filing carries one."""
    fn = _fn("insiderRow")
    assert "insiderShares(t.shares)" in fn
    assert "t.value ? '$' + fmtCompact(t.value, 1) : ''" in fn
    assert "ws-ins-amt" in fn


def test_a_missing_value_is_omitted_rather_than_shown_as_zero():
    """Some filings carry shares and no value; one in the TSLA sample does."""
    fn = _fn("insiderRow")
    assert "[shares, value].filter(Boolean).join(' · ')" in fn
    assert "${amount ? " in fn


def test_small_share_counts_keep_their_digits():
    """2,605 and 2,900 are different facts and `2.6K` loses both. 303,960,630
    is not a number anyone reads, so the rule turns over at a million."""
    fn = _fn("insiderShares")
    assert ">= 1e6 ? fmtCompact(v, 1) : fmt(v, 0)" in fn


def test_the_hover_carries_what_the_row_truncates():
    """The name ellipses in a narrow dock, and a row reading "Other 304.0M sh"
    does not explain itself."""
    fn = _fn("insiderRow")
    assert "[t.insider, t.position, t.detail].filter(Boolean)" in fn


def test_the_widget_says_what_uncoloured_means():
    """Every panel states what it cannot tell you. A neutral row with no
    explanation reads as a rendering gap."""
    body = APP_JS[APP_JS.index("if (id === 'insiders') {"):]
    body = body[:body.index("if (id === 'reports')")]
    assert "neither a purchase nor a sale" in body


def test_the_helpers_are_at_module_level():
    """They were first written inside wsWidgetBody, which recreated them on
    every dock render and hid them from the parse check in
    tests/test_js_parses.py, whose lookup is global."""
    assert "\nfunction insiderRow(t) {" in APP_JS
    assert "\nfunction insiderShares(n) {" in APP_JS


def test_every_class_the_row_renders_has_a_rule():
    used = {tok for attr in re.findall(r'class="([^"]*)"', _fn("insiderRow"))
            for tok in attr.split() if tok.startswith("ws-ins")}
    assert {"ws-ins-act", "ws-ins-who", "ws-ins-amt"} <= used, used
    for cls in used | {"ws-ins"}:
        assert ".%s" % cls in CSS, cls


def test_the_amounts_are_tabular_so_the_column_compares():
    """Showing the numbers is the point; showing them unaligned wastes it."""
    block = CSS[CSS.index(".ws-ins-amt"):]
    assert "tabular-nums" in block[:200]


# ------------------------------------------------------- the one-item menu


def test_a_one_item_menu_is_a_button_not_a_dropdown():
    """Fibs held a single checkbox, so switching Fibonacci levels on took two
    clicks and a dropdown that existed to show one row."""
    toolbar = _fn("wsToolbar")
    assert "if (m.items.length === 1 && !m.manage) {" in toolbar
    assert 'data-ws-toggle="${esc(id)}"' in toolbar
    assert 'aria-pressed="${on}"' in toolbar


def test_the_toggle_has_a_click_handler_not_a_change_one():
    """`data-ws-opt` is handled in a `change` listener, which is right for a
    checkbox and never fires for a button: the first version reused that
    attribute and the Fibs button rendered perfectly and did nothing."""
    assert "closest('[data-ws-toggle]')" in APP_JS
    handler = APP_JS[APP_JS.index("closest('[data-ws-toggle]')"):]
    handler = handler[:handler.index("const wsMode")]
    assert "wsSetOverlay(id, !wsOverlayOn(id))" in handler
    assert "wsRedrawChart()" in handler
    # And the checkbox path is untouched: still reading `checked`.
    assert "wsSetOverlay(wsOpt.dataset.wsOpt, wsOpt.checked)" in APP_JS


def test_the_rule_is_about_the_item_count_not_about_fibs():
    """So a menu that loses its options becomes a button and one that gains a
    second becomes a dropdown again, with nothing to remember."""
    toolbar = _fn("wsToolbar")
    assert "'fibs'" not in toolbar and '"fibs"' not in toolbar
    # Fibs is still the only single-item menu, which is what makes this safe.
    menus = APP_JS[APP_JS.index("const WS_MENUS = ["):]
    menus = menus[:menus.index("\n];")]
    singles = re.findall(r"items: \['([a-z0-9]+)'\]", menus)
    assert singles == ["fib"], singles


def test_a_manage_menu_stays_a_dropdown():
    """The Indicators menu needs somewhere to put "Manage indicators…" even if
    it were down to one item."""
    assert "!m.manage" in _fn("wsToolbar")
