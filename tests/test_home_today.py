"""The Today digest on the home page.

Measured at 880x965 before it existed: 364px of chrome before `.home` begins,
then the brand lockup, the search field and the quick picks taking 320px of the
601 left above the fold. The first thing a reader saw on the landing page was
the product's own name. The highest-value thing the terminal knows -- the next
five days of scheduled releases, which watchlist names report this week, and
which sectors changed state overnight -- was on a different tab, eight thousand
pixels down Optic's Read.

Same endpoint and the same rows as that panel, three columns deep instead of
four, two rows deep instead of all of them, linking through rather than
restating it.

**Executed, not grepped**, for the parts that are decisions: whether an empty
or degraded payload produces nothing at all rather than a band announcing that
it has nothing. The harness is the one tests/test_js_parses.py uses.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess

import pytest

JSC = ("/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/"
       "Helpers/jsc")

APP = open("static/app.js", encoding="utf-8").read()
CSS = open("static/styles.css", encoding="utf-8").read()


def _row(title, impact="medium", when="Fri Sep 25", why="because", short=""):
    return {"kind": "event", "impact": impact, "title": title, "short": short,
            "when": when, "time": "", "days_away": 3, "why": why, "agency": "BLS"}


def _col(cid, name, rows, total=None):
    return {"id": cid, "name": name, "blurb": cid + " blurb", "rows": rows,
            "total": total if total is not None else len(rows), "preview": rows[:3]}


CASES = {
    "full": {"available": True, "horizon_days": 5, "columns": [
        # Four events, two shown, two behind the button. `total` is not passed
        # because app/priority.py:181 sets it to `len(rows)` -- the two cannot
        # differ, and a fixture that made them differ was testing a payload the
        # server cannot produce. It mattered: the count is now taken from the
        # rows in hand, because that is how many the button can actually
        # reveal, and against a `total` of 4 with 3 rows sent it would have
        # promised two and opened onto one.
        _col("events", "Market-moving events",
             [_row("CFTC Commitments of Traders"), _row("Employee Tenure", "low"),
              _row("Third thing", "low"), _row("Fourth thing", "low")]),
        _col("earnings", "Earnings this week",
             [_row("COST reports Thursday", "high", "Thursday")]),
        _col("sectors", "Sector read-through",
             [_row("XLY - Consumer Discretionary", "high", "")])]},

    # Every column present and every one of them empty. A band that says
    # "nothing scheduled" on a quiet day is worse than no band.
    "all_columns_empty": {"available": True, "horizon_days": 5, "columns": [
        _col("events", "Market-moving events", []),
        _col("earnings", "Earnings this week", []),
        _col("sectors", "Sector read-through", [])]},

    "unavailable": {"available": False, "reason": "upstream refused"},
    "nothing": None,

    # The endpoint publishes a fourth column this digest does not show.
    "extra_column": {"available": True, "horizon_days": 5, "columns": [
        _col("events", "Market-moving events", [_row("A thing")]),
        _col("macro", "Macro regime", [_row("Should not appear")])]},

    # A row with no `when` at all, which is most sector rows.
    "row_without_when": {"available": True, "horizon_days": 5, "columns": [
        _col("sectors", "Sector read-through",
             [_row("XLE - Energy", "high", when="")])]},
}


@pytest.fixture(scope="module")
def rendered():
    exe = JSC if os.path.exists(JSC) else shutil.which("jsc")
    if not exe:
        pytest.skip("no JavaScriptCore on this machine")
    script = """
      load('tests/support/browser_stubs.js');
      try { load('static/charts.js'); load('static/app.js'); } catch (e) {}
      if (typeof homeTodayHTML !== 'function') {
        print('RESULT:' + JSON.stringify({error: 'homeTodayHTML is not defined'}));
      } else {
        var cases = %s, out = {};
        for (var key in cases) {
          var html = homeTodayHTML(cases[key]) || '';
          out[key] = {html: html, text: html.replace(/<[^>]*>/g, ' ')
            .replace(/&amp;/g, '&').replace(/\\s+/g, ' ').trim()};
        }
        print('RESULT:' + JSON.stringify(out));
      }
    """ % json.dumps(CASES)
    proc = subprocess.run([exe, "-e", script], capture_output=True, text=True,
                          timeout=180)
    blob = proc.stdout + proc.stderr
    assert "RESULT:" in blob, blob[-1500:]
    body = json.loads(blob.split("RESULT:", 1)[1].split("\n")[0])
    assert "error" not in body, body
    return body


# ------------------------------------------------------------- what it draws


def test_it_shows_the_three_columns_a_home_page_needs(rendered):
    """What is scheduled, who reports, what already moved -- in that order."""
    html = rendered["full"]["html"]
    for name in ("Market-moving events", "Earnings this week", "Sector read-through"):
        assert name in html, name
    assert html.index("Market-moving") < html.index("Earnings this") \
        < html.index("Sector read"), "columns are out of reading order"


def test_it_is_a_digest_and_stops_at_two_rows(rendered):
    """Four events exist; two are shown and the rest is counted. A digest that
    grows with the feed is a table."""
    html = rendered["full"]["html"]
    assert html.count('class="ht-row"') == 4, "two rows per column, three columns"
    assert "2 more" in html, "the remainder is counted, not dropped silently"
    assert "Third thing" not in html
    assert "Fourth thing" not in html


def test_a_column_the_digest_does_not_carry_is_left_out(rendered):
    """/api/priority publishes four columns. Showing whatever arrives would
    make the band's height a function of the feed."""
    assert "Should not appear" not in rendered["extra_column"]["html"]
    assert "Macro regime" not in rendered["extra_column"]["html"]


def test_an_empty_or_broken_feed_draws_nothing_at_all(rendered):
    """Not an empty state -- nothing. This band sits above the search on the
    first screen, and a bordered box saying it has no news costs the reader
    the same 179px as one with news in it."""
    for case in ("all_columns_empty", "unavailable", "nothing"):
        assert rendered[case]["html"] == "", case


def test_a_row_with_no_date_does_not_draw_an_empty_cell(rendered):
    """Most sector rows have no `when`. An empty span reads as a fault."""
    html = rendered["row_without_when"]["html"]
    assert "XLE - Energy" in html
    assert "ht-when" not in html


def test_it_reuses_the_impact_vocabulary_the_app_already_has(rendered):
    """`.cal-impact` with high/medium/low is on the calendar, the catalyst rows
    and the priority panel. A fourth way to say "high impact" is a fourth thing
    to keep in step."""
    html = rendered["full"]["html"]
    assert 'class="cal-impact high"' in html
    assert 'class="cal-impact low"' in html
    assert ".cal-impact.high" in CSS


# ------------------------------------------------------------- how it loads


def test_the_host_sits_below_the_search_not_above_it():
    """This asserted the opposite, and the opposite put the search out of
    reach.

    The digest is 366px. With it and the knowledge card above the brand
    lockup, the home search sat at y=1060 in an 835px viewport -- measured,
    with the onboarding card already dismissed -- so the page's primary action
    was below the fold on every visit. It was reported as missing.

    What the original rule was protecting is the market coming first, and that
    still holds: `#cc-strip` is the live index row and is still the first thing
    under the session bar. The digest is a read of the day rather than the
    market itself, so it is the piece that moves."""
    home = APP.split("function renderHome() {", 1)[1].split("\nasync function", 1)[0]
    assert 'id="hm-today"' in home
    assert home.index('id="cc-strip"') < home.index('class="home-brand"') \
        < home.index('id="hm-today"'), \
        "the index strip leads, then the search, then the digest"


def test_it_starts_hidden_so_a_quiet_day_reserves_no_height():
    home = APP.split("function renderHome() {", 1)[1].split("\nasync function", 1)[0]
    assert re.search(r'id="hm-today"[^>]*\shidden', home)
    fn = APP.split("async function loadHomeToday() {", 1)[1].split("\n}", 1)[0]
    assert "live.hidden = !html;" in fn, "and it un-hides only when it has rows"


def test_it_does_not_hold_the_rest_of_the_page_behind_it():
    home = APP.split("function renderHome() {", 1)[1].split("\nasync function", 1)[0]
    assert "loadHomeToday();" in home
    assert "await loadHomeToday" not in home


def test_it_re_reads_its_host_after_the_await():
    """The bug loadHomeMarket carries a comment about: a host captured before
    the await can be detached by the time the request lands, and filling it
    puts the answer in an element no longer on the page."""
    fn = APP.split("async function loadHomeToday() {", 1)[1].split("\n}", 1)[0]
    assert fn.count("getElementById('hm-today')") == 2, \
        "read once to bail early, once more after the await"
    assert "const live = document.getElementById('hm-today');" in fn


def test_it_does_not_go_through_mountPanel():
    """`mountPanel` re-renders Optic's Read when its host is missing, which is
    right for that tab's hosts and wrong here: leaving Home would repaint a tab
    the reader is not on."""
    fn = APP.split("async function loadHomeToday() {", 1)[1].split("\n}", 1)[0]
    assert "mountPanel" not in fn


def test_it_reuses_the_payload_the_read_tab_already_fetched():
    fn = APP.split("async function loadHomeToday() {", 1)[1].split("\n}", 1)[0]
    assert "if (!STATE.priority)" in fn, "one /api/priority per session, not per tab"


def test_a_failed_fetch_says_nothing_rather_than_apologising():
    """The band is supplementary. Home's market summary already explains its
    own failure; a second apology above it for a block the reader did not ask
    for is noise."""
    fn = APP.split("async function loadHomeToday() {", 1)[1].split("\n}", 1)[0]
    assert "return;" in fn.split("catch (err)", 1)[1][:120]
    assert "errorHTML" not in fn


def test_it_links_through_rather_than_restating_the_tab():
    fn = APP.split("function homeTodayHTML(p) {", 1)[1].split("\n}", 1)[0]
    assert 'data-goto-view="brief"' in fn


# --------------------------------------------------------------- how it reads


def test_a_long_title_truncates_rather_than_wrapping():
    """A two-line row breaks the scan down the column. The full text is in the
    title attribute."""
    block = CSS.split(".ht-what {", 1)[1]
    block = block[:block.index("}")]
    assert "text-overflow: ellipsis" in block and "white-space: nowrap" in block
    assert "min-width: 0" in block, "or the flex child refuses to shrink at all"
    fn = APP.split("function homeTodayRow(r) {", 1)[1].split("\n}", 1)[0]
    # The full TEXT, which is what this stylesheet comment has always claimed
    # and what the attribute has never held: it carried `r.why`, the
    # explanation, so a truncated title could not be read by hovering it
    # either. "Metropolitan Area Employment and Unemployment ..." was
    # unreadable at any width by any means.
    # Comments stripped first: this function now explains in prose what the
    # attribute used to hold, and the first version of this check found
    # `r.why` inside that explanation.
    code = re.sub(r"/\*.*?\*/", "", fn, flags=re.S)
    span = re.search(r'<span class="ht-what"[^>]*>', code).group()
    assert 'title="${esc(what)}"' in span, span
    assert "r.why" not in span, span


def test_the_columns_collapse_rather_than_leaving_a_hole():
    """A degraded feed can return one or two columns. Three fixed tracks with a
    gap where the third should be reads as a missing panel."""
    block = CSS.split(".ht-cols {", 1)[1]
    block = block[:block.index("}")]
    assert "auto-fit" in block and "minmax(" in block


# ------------------------------------------------------------ opening a row
#
# Reported with a screenshot of a narrow window: "Metropolitan Area Employment
# and Unemployment ..." cut off with no way to read the rest of it.


def test_a_truncated_row_can_be_opened(rendered):
    """The row stays one line -- a digest is scanned down a column and a
    wrapping row breaks that -- so the way to read the rest is to open it.

    A <details>, not a class toggle: the keyboard and a screen reader get it
    for free, `preserveUI` already restores open <details> keyed on their
    summary text so a row survives the twenty-second refresh, and the open
    state lives on the element rather than in a second store that could
    disagree with it."""
    html = rendered["full"]["html"]
    assert '<details class="ht-det">' in html
    assert '<summary class="ht-row">' in html
    assert 'class="ht-why"' in html


def test_the_title_is_allowed_to_wrap_once_it_is_open():
    """The thing being revealed is usually the end of the title, so leaving it
    clipped would open a row onto the same truncation."""
    block = CSS.split('.ht-det[open] > summary .ht-what {', 1)[1]
    block = block[:block.index("}")]
    assert "white-space: normal" in block
    assert "overflow: visible" in block


def test_the_disclosure_triangle_is_suppressed_both_ways():
    """A marker in front of the impact chip pushes the whole column in. Safari
    needs the webkit pseudo-element; everything else takes `list-style`."""
    assert ".ht-det > summary::-webkit-details-marker { display: none; }" in CSS
    assert "list-style: none" in CSS.split(".ht-det > summary {", 1)[1][:120]


def test_a_row_with_nothing_to_reveal_is_not_a_control():
    """A dead control does not error; it takes the click and does nothing,
    which reads as a slow app rather than a missing feature."""
    fn = APP.split("function homeTodayRow(r) {", 1)[1].split("\n}", 1)[0]
    assert "if (!why) return" in fn
    assert '<div class="ht-row">' in fn, "a plain row, not a summary"


# ------------------------------------------------------------ and the rest


def test_the_count_is_a_control_not_a_sentence(rendered):
    """It read "7 more" and was a <p>: a sentence telling the reader there were
    seven more and offering no way to see them, which is worse than not
    mentioning them."""
    html = rendered["full"]["html"]
    # The tag itself. The first version of this built a string and then
    # concatenated "<button" onto it before asserting "<button" was in it --
    # a tautology that passed with the element changed straight back to a <p>.
    # Caught by mutating it to exactly that.
    assert '<button type="button" class="ht-rest"' in html, \
        "the count must be a button, not a sentence"
    assert "<p class=\"ht-rest\"" not in html
    assert "data-ht-all=" in html
    assert 'aria-expanded="false"' in html


def test_the_count_says_what_the_button_can_actually_show(rendered):
    """`total` is `len(rows)` by construction -- app/priority.py:181 -- so the
    two can never disagree today. Counted against the rows in hand anyway,
    because if they ever did, "7 more" would open onto fewer than seven: a
    promise made by a button that cannot keep it."""
    fn = APP.split("function homeTodayHTML(p) {", 1)[1].split("\n}\n", 1)[0]
    assert "const rest = all.length - rows.length;" in fn
    assert "c.total" not in fn.split("const rest", 1)[1][:200]


def test_opening_a_column_repaints_from_the_payload_already_in_hand():
    """This opens rows that were fetched and withheld, not rows that need
    fetching. `loadHomeToday` would re-request /api/priority for the same
    answer."""
    i = APP.index("closest('[data-ht-all]')")
    # The handler's own body, to its `return;` -- a fixed window ran past it
    # into the next handler, which does fetch. Comments stripped too: this one
    # explains in prose why it does not call `loadHomeToday`.
    block = APP[i:APP.index("\n    return;\n  }", i)]
    block = re.sub(r"/\*.*?\*/", "", block, flags=re.S)
    assert "homeTodayHTML(STATE.priority)" in block
    assert "getJSON" not in block and "loadHomeToday" not in block
    # Scroll and focus survive: the button that was clicked is replaced by the
    # repaint, and losing focus mid-keyboard-navigation strands the reader.
    assert "preserveUI(" in block


def test_an_open_row_survives_the_refresh_tick():
    """This panel is repainted every twenty seconds. A bare `innerHTML =`
    closed every open row on a timer -- a reader part way through the sentence
    under one lost it with no idea why. Measured before the fix: two rows open,
    refresh, zero open.

    The columns were already safe, because `homeTodayOpen` is module state and
    the markup is rebuilt from it. That is what made this easy to miss."""
    fn = APP.split("async function loadHomeToday() {", 1)[1].split("\n}", 1)[0]
    assert "preserveUI(live, () => { live.innerHTML = html; });" in fn
    # preserveUI keys open <details> on their summary text, which is the right
    # key here: the feed re-sorts these rows, and an index-based key would
    # reopen whichever row had moved into that slot.
    pu = APP.split("function preserveUI(host, fn) {", 1)[1].split("\n}", 1)[0]
    assert "details[open]" in pu and "detailsKey" in pu


def test_the_open_columns_survive_the_refresh_tick():
    """This panel is rebuilt from scratch every twenty seconds. State kept on
    the markup would collapse every open column under a reader on a timer."""
    assert "const homeTodayOpen = new Set();" in APP
    fn = APP.split("function homeTodayHTML(p) {", 1)[1].split("\n}\n", 1)[0]
    assert "homeTodayOpen.has(c.id)" in fn
