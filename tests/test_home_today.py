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
        _col("events", "Market-moving events",
             [_row("CFTC Commitments of Traders"), _row("Employee Tenure", "low"),
              _row("Third thing", "low")], total=4),
        _col("earnings", "Earnings this week",
             [_row("COST reports Thursday", "high", "Thursday")]),
        _col("sectors", "Sector read-through",
             [_row("XLY - Consumer Discretionary", "high", "")], total=10)]},

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


def test_the_host_sits_above_the_search_not_below_it():
    home = APP.split("function renderHome() {", 1)[1].split("\nasync function", 1)[0]
    assert 'id="hm-today"' in home
    assert home.index('id="cc-strip"') < home.index('id="hm-today"') \
        < home.index('class="home-brand"'), \
        "the digest belongs between the market strip and the brand lockup"


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
    assert 'title="${esc(r.why || \'\')}"' in fn


def test_the_columns_collapse_rather_than_leaving_a_hole():
    """A degraded feed can return one or two columns. Three fixed tracks with a
    gap where the third should be reads as a missing panel."""
    block = CSS.split(".ht-cols {", 1)[1]
    block = block[:block.index("}")]
    assert "auto-fit" in block and "minmax(" in block
