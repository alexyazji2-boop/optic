"""Every route composes from the same parts.

Audited in a browser at 1440x950 across all nineteen views. Two routes did not
compose like the others: Watchlist and Alerts rendered into `section.wv`, which
carried a padding and nothing else -- no surface, no border, no radius. They
were the only places in the product where a table of numbers sat directly on
the page background with its column headers floating above it, against Scan,
Explore, the Optic Portfolio and all seven security facets, every one of which
puts its content in a `.panel`.

Measured after: Watchlist one panel, Alerts three, all at 23px/27.6px padding,
14px radius and the same border and surface as every other route, with headings
at 20.7px/600 like every other panel heading. On a phone, 338px wide inside a
375px viewport with nothing overflowing.

The other findings in that audit were single rules losing a cascade, and each
has its own test below.
"""

from __future__ import annotations

import re

APP = open("static/app.js", encoding="utf-8").read()
CSS = open("static/styles.css", encoding="utf-8").read()
# Declarations only. A comment explaining why a rule was removed quotes the
# rule, and a bare substring check cannot tell those apart.
CSS_CODE = re.sub(r"/\*.*?\*/", "", CSS, flags=re.S)


# ------------------------------------------------- the panel is the container


def test_no_route_renders_onto_the_bare_page():
    """`section.wv` was the marker for content with no card around it."""
    assert 'class="wv"' not in APP
    assert 'class="wv ' not in APP
    assert "\n.wv {" not in CSS_CODE, "the class is gone; its rule should be too"


def test_watchlist_and_alerts_are_panels():
    fn = APP.split("function renderWatchlist() {", 1)[1]
    fn = fn[:fn.index("\nfunction ")]
    assert '<section class="panel">' in fn
    # And the list selector stays OUTSIDE it: it chooses which list the card is
    # showing, the same job `.scan-modes` does above the Scan results.
    assert fn.index("watchListsBar()") < fn.index('<section class="panel">')
    for marker in ('${loadingHTML(\'scan alerts\')}', '${errorHTML(data.error)}'):
        assert '<section class="panel">' + marker in APP, marker
    assert APP.count('<section class="panel" aria-label="Watches that fired">') == 4
    assert '<section class="panel" aria-label="Your watches">' in APP


def test_the_row_header_title_is_a_panel_heading():
    """`.panel > h2` is a child combinator and this title is not a child: the
    header is a row, with the title and its action ("Add a symbol", "Clear
    all") on one line, so the h2 sits inside `.wv-head`.

    Without a rule it fell through to `main h2` at `--t-d3` -- a 27.6px display
    title on a card whose neighbours all use 20.7px."""
    block = CSS_CODE.split(".panel > .wv-head h2 {", 1)[1]
    block = block[:block.index("}")]
    assert "font-size: var(--t-heading)" in block
    assert "font-weight: 600" in block
    assert "font-family: var(--display)" in block
    # And the page-title class is gone from those headings, or it would win.
    fn = APP.split("function renderWatchlist() {", 1)[1]
    assert 'class="hm-h"' not in fn[:fn.index("\nfunction ")]


def test_the_phone_heading_rule_reaches_it_too():
    """That selector is (0,2,1) and outranks `.panel > h2`, so leaving it out
    of the phone list held these two titles at 20.7px while every other panel
    heading on the same page went to 21px."""
    phone = CSS_CODE.split("@media (max-width: 559px) {", 1)[1]
    line = [ln for ln in phone.splitlines() if "font-size: 21px" in ln and ".panel > h2" in ln]
    assert line, "the phone heading rule is gone"
    assert ".panel > .wv-head h2" in line[0]


def test_the_alert_blocks_are_spaced_by_the_panel_and_not_by_themselves():
    """`.wd-block` carried a margin-bottom, which was the only separation these
    blocks had as bare sections. As panels it made the gap under "Your watches"
    27.6px against 23px under the block above. Measured after: 23 and 23."""
    assert ".wd-block" not in CSS_CODE
    assert "wd-block" not in APP, "a class with no rule is a hook with nothing behind it"
    assert "wh-block" not in APP, "this one never had a rule at all"


# ------------------------------------------------------ cascades that lost


def test_the_explore_group_label_wins_its_own_size():
    """Written as a `--t-micro` label and rendered as neither. `.panel h3` is
    (0,1,1) and sets `font-size: var(--t-base)`, so it beat `.ex-group-h`
    (0,1,0) and the label drew at 17.25px. The `font` shorthand did win for the
    family, and it names `--sans`, so these six were the only headings in the
    product not in the display face. Measured after: 11.5px, uppercase."""
    block = CSS_CODE.split(".ex-group-h {", 1)[1]
    block = block[:block.index("}")]
    assert "font-size: var(--t-micro)" in block
    assert "text-transform: uppercase" in block
    # The selector list has to out-rank `.panel h3`, which is (0,1,1).
    head = CSS_CODE[:CSS_CODE.index(".ex-group-h {")]
    assert head.rstrip().endswith(".panel .ex-group-h,"), \
        "a bare .ex-group-h is (0,1,0) and loses to .panel h3"


def test_a_numeric_first_column_keeps_its_lining_figures():
    """`td.name` opts a TEXT column out of tabular figures, which is right for
    company names. Three columns in the product hold numbers there: the chart
    dock's Key levels (nine prices), the Fibonacci table (0.0% / 23.6% /
    38.2%) and the contract table's strike. Their decimal points did not line
    up under each other."""
    assert "table.data td.name.num { font-variant-numeric: tabular-nums; }" in CSS_CODE
    # And the cells that need it say so.
    assert '<td class="name num">${fmt(l.price, 2)}</td>' in APP, "Key levels"
    assert '<td class="name num">${usd(l.price)}' in APP, "support and resistance"
    assert '<td class="name num">${esc(l.label)}${l.is_golden' in APP, "Fibonacci"
    assert '<td class="name num">${fmt(c.strike, 1)}' in APP, "contract strikes"


def test_the_opt_out_it_modifies_still_exists():
    """Both directions: `.num` here only means anything against a rule that
    turns lining figures off. If that rule goes, this modifier is noise."""
    assert "table.data td.name { color: var(--ink); font-variant-numeric: normal; }" in CSS_CODE
    assert "font-variant-numeric: tabular-nums" in CSS_CODE.split("table.data td {", 1)[1][:600]
