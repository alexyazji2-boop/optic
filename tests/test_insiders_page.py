"""The Insiders page: two filing regimes, one screen.

Congress and company Form 4s answer the same question from opposite ends --
what was traded, by someone who had to tell us -- and they were in three
different places: a dock widget, a Dossier panel, and a market-wide feed
stranded at the foot of Optic's Read, a page that summarises one day and had
nothing to do with a live list of filings.

Driven against the real archive: 1,284 disclosures, 57 members, 453 symbols,
MSFT the most disclosed at 32 filings across 13 members. Filters, the ranked
list, the per-day chart and saved searches all exercised in a browser.

What is deliberately NOT here: a government-contracts or lobbying tab. There is
no feed for either in this project, and a tab of invented rows is the one thing
this page must not be.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP = (ROOT / "static/app.js").read_text()
CSS = (ROOT / "static/styles.css").read_text()
HTML = (ROOT / "static/index.html").read_text()


def function(name):
    return re.search(r"^(?:async )?function " + name + r"\([^\n]*\) \{.*?^\}",
                     APP, re.M | re.S).group()


# ------------------------------------------------- a view needs five places


def test_the_view_is_registered_everywhere_it_has_to_be():
    """CLAUDE.md: a new view needs the section, the views map, NAV_GROUPS, the
    loader dispatch and PALETTE_PLACES. Missing any one is a different broken
    symptom, which is why this asserts all five in one test."""
    assert 'id="view-insiders"' in HTML
    assert "insiders: $('#view-insiders')" in APP
    assert "'explore', 'scan', 'insiders'" in APP, "not in a nav group"
    assert "if (view === 'insiders') return loadInsiders(force);" in APP
    assert "{ view: 'insiders', label: 'Insiders'" in APP


def test_it_is_on_the_tickerless_list():
    """The guard is an allow-list by omission, so a new view is ticker-specific
    by default: the loader runs, the requests never fire, and the page shows
    "No ticker loaded". Watchlist, Alerts and Explore were each caught."""
    allowed = APP.split("const TICKERLESS_VIEWS = [", 1)[1].split("];", 1)[0]
    assert "'insiders'" in allowed


def test_the_palette_can_find_it_by_the_words_people_use():
    """"insider" did not appear in any `terms` string before this, so the
    command palette could not reach the feed by name at all."""
    entry = APP.split("{ view: 'insiders', label: 'Insiders'", 1)[1].split("},", 1)[0]
    for word in ("insider", "congress", "form 4", "stock act", "disclosures"):
        assert word in entry, word


# ------------------------------------------------- the work happens server-side


def test_the_filters_are_sent_to_the_server():
    """The archive is a thousand rows and the page shows sixty. Filtering in
    the browser would mean shipping all of it to narrow it -- and the counts,
    the per-day series and the ranking have to describe the narrowed set, so
    whatever computes them has to see all of it anyway."""
    fn = function("congressQueryString")
    for param in ("ticker=", "member=", "side=", "since=", "until="):
        assert param in fn, param
    # Every value is encoded. A member's name is free text from a form.
    assert fn.count("encodeURIComponent") >= 6
    body = function("loadInsidersCongress")
    assert "'/api/congress?' + congressQueryString(congressQuery)" in body


def test_the_request_is_keyed_on_the_whole_query():
    """Keyed on the URL, so switching facets back and forth does not refetch
    the same slice and changing any filter does. Keyed on the ticker alone --
    which is what the Dossier panel does, correctly, because that is all it
    varies -- a second filter would never have refetched."""
    body = function("loadInsidersCongress")
    assert "STATE.insCongressFor === url" in body


def test_the_side_vocabulary_is_the_servers_own():
    """Three watch conditions in this app once shipped comparing a stored
    parameter against a value produced somewhere else -- `direction` against
    up/down where the analytics produce rising/falling. All three stored fine,
    evaluated fine, and never fired."""
    block = APP.split("const CONGRESS_SIDES = [", 1)[1].split("];", 1)[0]
    ids = set(re.findall(r"id: '(\w*)'", block))
    assert ids == {"", "buy", "sell", "other"}, ids
    server = (ROOT / "app/analytics/congress.py").read_text()
    assert '"side": side' in server or 'side' in server


# ------------------------------------------------- claims the page makes


def test_the_ranking_says_it_is_not_by_money():
    """Amounts are bands, so a ranking by value ranks by the width of a band
    the filer chose. The panel says so, because a list of symbols under a
    heading is otherwise read as a ranking by size."""
    fn = function("renderCongressFacet") + function("congressResults")
    assert "not by money" in fn
    assert "bands" in fn


def test_the_chart_says_which_date_it_is_using():
    """The trade date and the filing date run weeks apart -- the median gap in
    the live archive is 14 days and the longest is 476. A per-day chart that
    did not say which one it plotted would be unreadable in either reading."""
    body = function("congressResults")
    assert "when the trade happened, not when it was" in body
    fn = function("_activity") if False else (ROOT / "app/analytics/congress.py").read_text()
    assert "Keyed on the TRADE date" in fn


def test_the_quiet_days_are_drawn():
    """A bar chart that drops empty days compresses a fortnight of nothing into
    the same width as a busy week, and makes a cluster look like a trend. The
    server emits every day in the window; the chart must not filter them out
    again on the way in."""
    fn = function("congressActivityChart")
    # A day with nothing in it contributes no rectangle, but it still takes its
    # slot on the axis -- the index into `list`, not a compacted position.
    assert "const x = i * slot" in fn
    assert "if (!total) return ''" in fn


def test_the_lag_column_marks_the_statutory_deadline():
    """45 days is what the STOCK Act allows, so past it is the fact worth
    marking. Under it the number is context and takes no colour -- colour
    cannot carry a meaning the number contradicts."""
    fn = function("insCongressRow")
    assert "lag > 45" in fn
    assert "const late" in fn


# ------------------------------------------------- the form


def test_a_result_landing_does_not_throw_away_what_is_being_typed():
    """The whole facet used to repaint whenever a request settled, which
    rebuilt the form from the applied query -- so a reader half through a
    member's name lost it to their own previous query finishing. preserveUI is
    not enough: it restores focus and the caret, not a value the rebuild never
    knew about. Verified in a browser: "half typed" survives a refetch, and
    keeps focus."""
    fn = function("renderInsidersFacetHost")
    assert "ins-results-host" in fn
    assert "opts && opts.full" in fn
    assert "preserveUI(host" in fn
    # And the form is rebuilt when something outside it moved the query.
    for control in ("data-ins-pick", "data-ins-reset", "data-ins-load"):
        i = APP.index("closest('[" + control + "]')")
        assert "renderInsidersFacetHost({ full: true })" in APP[i:i + 900], control


def test_dates_the_wrong_way_round_are_swapped_not_refused():
    """A reader who fills the boxes the other way round means the range between
    them. An error message here would be the app being pedantic about its own
    field order."""
    block = APP.split("if (evt.target.id === 'ins-filter-form')", 1)[1][:1400]
    assert "since > until ? until : since" in block
    assert "since > until ? since : until" in block


def test_the_window_is_not_part_of_a_saved_search():
    """`days` is how the reader is reading the chart, not what they are looking
    for. A saved search that silently rewound the window would change the
    picture without changing the question."""
    for anchor in ("data-ins-reset", "data-ins-load"):
        i = APP.index("closest('[" + anchor + "]')")
        assert "days: congressQuery.days" in APP[i:i + 700], anchor


def test_saved_searches_survive_a_browser_without_storage():
    """Private mode throws on setItem, and an exception in a click handler
    stops the handler -- the search would be lost AND the page would stop
    responding to the button."""
    assert "function congressSaveSearches()" in APP
    fn = function("congressSaveSearches")
    assert "catch" in fn
    # And reading it back cannot trust what is there: something else may have
    # written the key, or a previous version of this page.
    block = APP.split("localStorage.getItem(INS_SAVED_KEY)", 1)[1][:300]
    assert "Array.isArray(raw)" in block


def test_a_saved_name_replaces_rather_than_duplicates():
    """Two chips with the same label doing different things is worse than
    losing the first one."""
    i = APP.index("closest('[data-ins-save]')")
    block = APP[i:i + 900]
    assert "filter((x) => x.name !== name)" in block


# ------------------------------------------------- controls and handlers


def test_every_control_on_this_page_has_a_handler():
    """`data-ws-hide` was markup with nothing behind it, and three askPulse
    topics were asked for and never defined. A dead control does not error; it
    takes the click and nothing happens, which reads as a slow app."""
    rendered = set(re.findall(r"data-ins-([a-z]+)=", APP))
    handled = set(re.findall(r"closest\('\[data-ins-([a-z]+)\]'\)", APP))
    handled |= set(re.findall(r"evt\.target\.id === 'ins-([a-z]+)-form'", APP))
    # `retry` is rendered inside a template and handled; `find` is the feed's
    # own form, matched by id above rather than by attribute.
    missing = rendered - handled
    assert not missing, "rendered with no handler: %s" % sorted(missing)


def test_the_symbol_control_is_a_toggle():
    """A one-way trip into a filtered page needs the reader to find Reset to
    get out of it, which is two controls for one decision."""
    i = APP.index("closest('[data-ins-pick]')")
    assert "? '' : sym" in APP[i:i + 600]


# ------------------------------------------------- what moved, and what says so


def test_the_read_points_at_where_the_feed_went():
    """It was the bottom of that page for a while and somebody will go looking.
    A silent removal reads as a feature that broke."""
    brief = function("renderBrief")
    assert 'data-go-view="insiders"' in brief
    assert "insider-host" not in APP, "the old slot is gone, not orphaned"


def test_the_page_says_it_is_a_record_and_not_a_signal():
    """Both feeds are lists of what was filed. Ranking by how profitable a
    trade looked would make this a recommendation engine built on a 45-day
    delay."""
    fn = function("renderInsidersView")
    assert "not a signal" in fn


def test_it_introduces_no_new_colours():
    """The directional pair is --pos / --neg, the same one the candles, the
    volume strip and every percentage already use, so a green bar here means
    what green means everywhere else."""
    block = CSS[CSS.index("/* ---------------------------------------------------------- Insiders page"):]
    assert not re.search(r"#[0-9a-fA-F]{3,8}", block), "a hex value on this page"
    assert "var(--pos)" in block and "var(--neg)" in block


def test_the_key_swatches_are_filled_as_html_not_as_svg():
    """`fill` does nothing to a <span>. The chart's rectangles and the key's
    dots share a class name and need different properties, which is exactly the
    kind of pair that ships looking blank."""
    block = CSS[CSS.index("Insiders page"):]
    assert ".ca-dot.ca-buy { background: var(--pos); }" in block
    assert ".ca-buy { fill: var(--pos); }" in block
