"""An audit of the terminal for two controls doing one job, and what it found.

Swept all seventeen views in a browser, collecting every panel title and every
button label per view. Two things were checked: the same panel on more than one
view at once, and the same label twice inside one view.

**Panels: clean.** Zero titles on more than one view and zero twice in one view.
The earlier removals took care of that set: Corporate actions & flow was on
Options and Financials, Close defence was on Options and Investing.

**Controls: one real overlap.** The watchlist rendered two buttons both reading
"Something changed", one in WATCH_SORTS and one in WATCH_FILTERS. Everything
else that repeated was one control per row or per panel, which is the house
pattern: the per-indicator eye on the charting tab, the per-drawing close, one
"Sector Read" per sector row, one ticker button per position, and Ask Pulse once
per panel header.

**One thing that looked like a duplicate and was not.** "Relative performance"
was the title of a panel on Options and of a section on Financials, and they
measure different things: a percentile against a peer set, and excess return
against one benchmark. Removing either would have cost a real measurement, so
the second is renamed instead. That is worse than a duplicate while it lasts,
because one name over two measures is a claim that they are the same reading.

Not overlaps, and deliberately left alone: `data-open-palette` and
`data-watch-import` are handlers with no control anywhere in the app. Those are
lost features rather than duplicated ones, and deleting the handler would
finish removing something somebody meant to ship.
"""

import re

APP_JS = open("static/app.js", encoding="utf-8").read()


def strip_comments(js):
    """Comments out first. Every claim here is also explained in a comment
    beside the code, so a raw read would pass on the explanation of a line that
    had been put back."""
    js = re.sub(r"/\*.*?\*/", " ", js, flags=re.S)
    return re.sub(r"(?<!:)//[^\n]*", " ", js)


CODE = strip_comments(APP_JS)


def listing(name):
    """The entries of a top-level array constant."""
    start = CODE.index("const %s = [" % name)
    return CODE[start:CODE.index("\n];", start)]


# ------------------------------------------------ one control per question

def test_only_one_control_reads_something_changed():
    """Two buttons with one label, side by side, one sorting and one filtering.
    A reader cannot tell which is which from the name and both answer the same
    question."""
    assert CODE.count("'Something changed'") == 1, (
        "the label is back on a second control")


def test_the_sort_is_the_one_kept():
    """It is the default, and it is not destructive: changed rows go to the top
    and the rest stay on screen. The filter hid names the reader had explicitly
    chosen to watch, to answer a question the default ordering already
    answers."""
    assert "'Something changed'" in listing("WATCH_SORTS")
    assert "watchSort = 'changed'" in CODE
    filters = listing("WATCH_FILTERS")
    assert "changed" not in filters
    # The rest of the filter set is untouched.
    for kept in ("'all'", "'bullish'", "'bearish'", "'movers'"):
        assert kept in filters, kept


def test_a_stale_filter_id_degrades_to_all():
    """`watchFilter` is not persisted, but the lookup has to be total anyway:
    an id with no entry must fall back rather than return undefined and take
    the feed with it."""
    assert "WATCH_FILTERS.find((f) => f.id === watchFilter) || WATCH_FILTERS[0]" in CODE


# --------------------------------------- two measures may not share one name

def test_the_two_relative_readings_have_different_names():
    """One is a percentile against a peer set, from /api/relperf, answering how
    many peers the symbol is beating. The other is excess return and a ratio
    line against one benchmark, from /api/extras, answering whether it beats
    SPY. Both were titled "Relative performance"."""
    assert "hg('Versus the index')" in CODE
    # The Options panel keeps the name, which was asked for directly.
    assert "hg('Relative performance')" in CODE


def test_the_renamed_section_is_the_benchmark_one():
    """Renaming the other would have undone a title chosen on purpose. This one
    is identifiable by what it renders: excess-return tiles and the ratio chart
    host, both fed by /api/extras."""
    at = CODE.index("const relBlock =")
    block = CODE[at:CODE.index("return `<div class=\"panel span2 gap\">", at)]
    assert "hg('Versus the index')" in block
    assert "Relative performance" not in block
    assert "chart-relative" in block
    assert "rel.benchmark" in block, "the heading has to say which index"


def test_the_peer_percentile_panel_still_names_its_own_measure():
    """It keeps "Relative performance" and its own method line, so the two are
    told apart by what they say rather than only by where they sit."""
    at = CODE.index("function renderRelPerf(")
    fn = CODE[at:CODE.index("\nfunction ", at + 1)]
    # Both branches, counted. This function renders its heading twice, once for
    # the loading-or-error state and once populated, so asserting the substring
    # passed against a mutation that renamed only the populated one: the other
    # branch still supplied the string.
    assert fn.count("hg('Relative performance')") == 2, (
        fn.count("hg('Relative performance')"))
    assert "hg('Versus the index')" not in fn, "the wrong panel was renamed"
    # And the populated branch specifically, identified by its Ask Pulse hook.
    populated = fn[fn.index("askPulse('relperf')") - 200:]
    assert "hg('Relative performance')" in populated[:260]
    assert "rp.method" in fn


# ------------------------------------------- what the audit chose not to touch

def test_the_repeated_controls_that_are_one_per_row_are_left_alone():
    """Ask Pulse appears fourteen times on Options, once per panel header, and
    that is the house pattern rather than a duplicate: a control offered only
    in one place on a twenty-panel page is a control nobody finds."""
    assert CODE.count("askPulse('") > 10


def test_the_two_orphaned_handlers_are_still_there():
    """`data-open-palette` and `data-watch-import` are handlers with no control.
    They are lost features, not duplicated ones: the first even says in its own
    comment that it is meant to be the discoverable route beside the keyboard
    shortcut. Deleting either would finish removing something somebody meant to
    ship, so the audit reports them instead."""
    for attr in ("data-open-palette", "data-watch-import"):
        assert "closest('[%s]')" % attr in CODE, attr
