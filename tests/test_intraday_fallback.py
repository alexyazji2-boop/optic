"""An intraday range with no bars in hand is a normal state, not a crash.

Reported as `Could not load. Cannot read properties of null (reading
'intraday')` on a Dossier tab, with a Try again button that could not help
because nothing had failed.

`chartRange` is one variable shared by the Charting tab and the Dossier, it
holds a minute count when an interval rung is picked, and it is persisted to
localStorage. So picking 15m on Charting and coming back the next day put the
Dossier on an intraday range with no payload. `swingSeries` returned null there
and all three of its callers read a field off the result immediately.

Reproduced on a local server by setting `optic.chart.range` to `15`, reloading
and opening the Options tab: the error rendered verbatim.

The deeper half is that `loadIntraday` had exactly ONE caller -- the range
pill's click handler -- so nothing fetched the bars unless somebody pressed a
pill in that session. The crash was the visible symptom of a chart that could
never have filled in.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
APP = (ROOT / "static/app.js").read_text()
JSC = Path("/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/"
           "Helpers/jsc")


def function(name):
    return re.search(r"^(?:async )?function " + name + r"\([^\n]*\) \{.*?^\}",
                     APP, re.M | re.S).group()


def array_const(name):
    """Arrays end at a `];` in column zero. `.*?;` would stop at the first
    semicolon inside, which for CHART_INTERVALS is one in a comment."""
    return re.search(r"^const " + name + r" = \[.*?^\];", APP, re.M | re.S).group()


HARNESS = """
var chartRange = '6m';
var chartInterval = 'daily';
var STATE = {ticker: 'AAPL', intraday: null};
function assert(v, m) { if (!v) throw new Error(m); }
"""


def run_js(scenario):
    exe = str(JSC) if JSC.exists() else shutil.which("jsc")
    if not exe:
        pytest.skip("JavaScriptCore is unavailable")
    src = (HARNESS
           + array_const("CHART_RANGES") + "\n"
           + array_const("CHART_INTERVALS") + "\n"
           + "\n".join(function(n) for n in [
               "isIntradayRange", "chartIntervalSpec", "intradayMatches",
               "intradaySeries", "swingSeries", "swingBarCountText"])
           + "\n(function() {\n" + scenario + "\n})();\nprint('TEST_OK');")
    out = subprocess.run([exe, "-e", src], capture_output=True, text=True,
                         timeout=15, cwd=ROOT)
    assert "TEST_OK" in out.stdout, out.stdout + out.stderr


# ------------------------------------------------- the crash itself


@pytest.mark.parametrize("rung", ["1", "5", "15", "30", "60", "240", "1d", "5d"])
def test_no_intraday_payload_yields_a_series_rather_than_null(rung):
    """Every intraday key, because the ladder added six of them to a branch
    written when there were two.

    `.intraday` is the read that threw, so it is the read asserted here."""
    run_js("""
      chartRange = '%s';
      STATE.intraday = null;
      var ps = swingSeries({});
      assert(ps !== null, 'swingSeries returned null');
      assert(ps.intraday === true, 'the empty shape must still say intraday');
      assert(Array.isArray(ps.dates) && ps.dates.length === 0, 'dates');
      assert(ps.shown_bars === 0, 'shown_bars');
    """ % rung)


def test_a_payload_for_another_symbol_is_not_this_symbols_bars():
    """The one that silently drew the wrong company. Holding MSFT's bars while
    AAPL is loaded has to count as "we do not have them", or the chart shows one
    company's minute bars under another's name."""
    run_js("""
      chartRange = '15';
      STATE.ticker = 'AAPL';
      STATE.intraday = {ticker: 'MSFT', range: '15', available: true,
                        times: ['t'], closes: [1], volumes: [1], bars: 1};
      assert(intradayMatches() === false, 'another symbol counted as a match');
      var ps = swingSeries({});
      assert(ps.dates.length === 0, "MSFT's bars were served for AAPL");
      assert(ps.pending === true, 'a symbol we have not fetched is pending');
    """)


def test_a_payload_for_another_rung_does_not_answer_this_one():
    run_js("""
      chartRange = '15';
      STATE.intraday = {ticker: 'AAPL', range: '5', available: true,
                        times: ['t'], closes: [1], volumes: [1], bars: 1};
      assert(intradayMatches() === false, '5m answered a 15m question');
      assert(swingSeries({}).dates.length === 0, 'wrong-rung bars were drawn');
    """)


def test_real_bars_are_still_returned_unchanged():
    """The fallback must not shadow the working path."""
    run_js("""
      chartRange = '15';
      STATE.intraday = {ticker: 'AAPL', range: '15', available: true,
                        times: ['a', 'b'], closes: [1, 2], volumes: [9, 9],
                        bars: 2, interval: '15m'};
      var ps = swingSeries({});
      assert(ps.dates.length === 2, 'real bars were replaced by the fallback');
      assert(ps.pending === undefined, 'a delivered payload is not pending');
      assert(ps.interval === '15m', 'interval');
    """)


# ------------------------------------------------- waiting vs having none


def test_in_flight_is_pending_and_not_reported_as_an_empty_feed():
    """`loadIntraday` writes a `{ticker, range, loading: true}` placeholder
    before it fetches. That MATCHES the current question, so a check on the key
    alone reads it as a delivered payload with nothing in it and tells the
    reader the feed is empty while the request is still open."""
    run_js("""
      chartRange = '15';
      STATE.intraday = {ticker: 'AAPL', range: '15', loading: true};
      var ps = swingSeries({});
      assert(ps.pending === true, 'an open request reported itself as empty');
      assert(!ps.reason, 'a loading chart must not blame the feed');
      assert(/loading/.test(swingBarCountText(ps)), swingBarCountText(ps));
    """)


def test_an_unavailable_feed_says_so_in_the_feeds_own_words():
    """`/api/intraday` explains itself -- free intraday history is thin outside
    regular hours and absent for many symbols. That sentence is the whole answer
    and it should reach the reader rather than being replaced by a blank box."""
    run_js("""
      chartRange = '15';
      STATE.intraday = {ticker: 'AAPL', range: '15', available: false,
                        reason: 'No intraday bars came back.'};
      var ps = swingSeries({});
      assert(ps.pending === false, 'an answered request is not pending');
      assert(ps.reason === 'No intraday bars came back.', ps.reason);
      assert(/none available/.test(swingBarCountText(ps)), swingBarCountText(ps));
    """)


# ------------------------------------------------- the heading is a claim


def test_the_heading_names_the_window_each_rung_actually_covers():
    """This read `chartRange === '1d' ? 'today' : 'five sessions'`, from when
    1D and 5D were the only intraday ranges. The ladder added six rungs writing
    minute counts into the same variable, so a 15m chart -- fetched over a
    month -- was headed "five sessions", and so were 1m, 5m, 30m, 1h and 4h."""
    run_js("""
      var cases = {'1': '1 day', '5': '5 days', '15': '1 month',
                   '30': '1 month', '60': '3 months', '240': '1 year'};
      Object.keys(cases).forEach(function(key) {
        chartRange = key;
        STATE.intraday = {ticker: 'AAPL', range: key, available: true,
                          times: ['a'], closes: [1], volumes: [1], bars: 1,
                          interval: 'x'};
        var text = swingBarCountText(swingSeries({}));
        assert(text.indexOf(cases[key]) !== -1,
               key + ' reads "' + text + '", not ' + cases[key]);
        assert(text.indexOf('five sessions') === -1, key + ': ' + text);
      });
    """)


def test_the_two_legacy_keys_keep_their_words():
    """1d and 5d are not rungs on the ladder and have no window of their own,
    so `chartIntervalSpec` returns null for them and the sentence has to come
    from somewhere else."""
    run_js("""
      [['1d', 'today'], ['5d', 'five sessions']].forEach(function(pair) {
        chartRange = pair[0];
        STATE.intraday = {ticker: 'AAPL', range: pair[0], available: true,
                          times: ['a'], closes: [1], volumes: [1], bars: 1,
                          interval: 'x'};
        var text = swingBarCountText(swingSeries({}));
        assert(text.indexOf(pair[1]) !== -1, pair[0] + ' reads ' + text);
      });
    """)


def test_the_empty_shape_does_not_call_itself_daily():
    """`chartInterval` still holds `daily` on an intraday range -- the file says
    so in three places -- and this object is flagged `intraday: true`. Writing
    one into the other is the mislabelling those comments exist to prevent."""
    run_js("""
      chartRange = '15';
      chartInterval = 'daily';
      STATE.intraday = null;
      var ps = swingSeries({});
      assert(ps.interval === '15m', 'interval is ' + ps.interval);
      assert(ps.weekly === false, 'weekly');
    """)


# ------------------------------------------------- the bars get asked for


def test_the_swing_view_requests_bars_it_does_not_have():
    """`loadIntraday` had one caller: the range pill. Two ordinary routes reach
    an intraday `chartRange` without pressing one -- the range is restored from
    localStorage at boot, and it survives a ticker change. In both the chart
    drew empty and stayed empty.

    Asserted at source because `renderSwing` cannot be driven here. Verified in
    a browser: `optic.chart.range` set to 15, reload, load MSFT, open Options --
    572 real 15m bars, where before the fix the view threw."""
    fn = function("renderSwing")
    assert "loadIntraday(chartRange)" in fn, \
        "nothing on this path asks for the bars it is about to draw"
    assert "!intradayMatches()" in fn, \
        "the guard must be the payload's absence, not a flag beside it"


def test_the_request_guard_cannot_loop():
    """`loadIntraday` calls `renderSwing` on its way in, after writing a
    placeholder under the current ticker and range. That placeholder is what
    stops the repaint asking again -- so the guard has to be the same test the
    series builder uses, and there has to be exactly one of it."""
    assert APP.count("function intradayMatches(") == 1
    # Both users of it, and no hand-rolled second copy of the comparison.
    assert function("swingSeries").count("intradayMatches()") == 1
    assert function("renderSwing").count("intradayMatches()") == 2, \
        "the fetch guard and the template's own `intra` both go through it"
    # The helper's body is the only place those three comparisons are written.
    # `renderSwing` had its own copy, which is how a template could describe a
    # payload the series beside it was not built from.
    body = function("intradayMatches")
    pattern = "STATE.intraday.range === chartRange"
    assert APP.count(pattern) == body.count(pattern) == 1, \
        "the match test was written out again somewhere"


# ------------------------------------------------- nothing is a blank box


def test_no_bars_draws_a_sentence_rather_than_an_empty_chart():
    """Measured before this: a 9px-tall <svg> with two nodes in it, under a
    heading claiming bars. `swingPriceBlock` guards on `ps.close.length` and
    simply had no else, so the mount kept the empty chart it was built with."""
    fn = function("swingPriceBlock")
    tail = fn[fn.index("} else {"):]
    # Built AND mounted. An earlier version of this test asserted only that
    # `emptyHTML(` appeared in the function, and survived a mutation that
    # built the sentence and wrote '' to the host instead -- which is exactly
    # the blank box the branch exists to stop.
    # To the first semicolon, not the first one at end of line: a mutation
    # that wrote `host.innerHTML = ''; const unused = <the empty state>` put a
    # semicolon mid-line and the newline-anchored version read straight past
    # it, capturing the whole thing and passing.
    mount = re.search(r"host\.innerHTML = (.*?);", tail, re.S)
    assert mount, "the else branch writes nothing to the mount"
    assert "emptyHTML(" in mount.group(1), \
        "the empty state is built and never mounted"
    # The reserved height belongs to a chart that is coming; this box sizes
    # itself, and leaving 160px on it draws a gap under the sentence.
    assert "host.style.minHeight = ''" in tail
    # The off-scale note counts levels against a price range that is not there.
    assert "note.innerHTML = ''" in tail, "a stale note outlives its chart"


def test_the_way_out_is_offered_only_where_it_leads_somewhere():
    """"Show daily bars instead" is the recovery for an intraday range with no
    bars. On a daily range it is where the reader already is, and a button that
    changes nothing is worse than no button."""
    fn = function("swingPriceBlock")
    tail = fn[fn.index("} else {"):]
    assert "ps.intraday" in tail and "data-chart-range=" in tail
    # The attribute the existing delegated handler reads, so this is wired by
    # the same path as every range pill rather than needing its own.
    assert 'data-chart-range="6m"' in tail
    assert "[data-chart-range]" in APP, "the handler the button depends on"
