"""Execute the client loaders against deferred responses, without a network.

Source contracts could not catch AAPL finishing after MSFT, or a swallowed
first-load failure. These tests control response order and inspect the result.
"""

import re
import shutil
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parent.parent
APP = (ROOT / "static/app.js").read_text()
JSC = Path("/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc")


def function(name):
    return re.search(r"^(?:async )?function " + name + r"\([^\n]*\) \{.*?^\}",
                     APP, re.M | re.S).group()


def declaration(name):
    return re.search(r"^(?:let|const) " + name + r" = .*?;", APP, re.M | re.S).group()


STUBS = """
var STATE = {ticker: 'AAPL', view: 'overview', swing: null};
var views = {swing: {innerHTML: ''}, overview: {innerHTML: ''},
  news: {innerHTML: ''}, financials: {innerHTML: ''}};
var pending = [], painted = [], warnings = [], refreshed = [], preserved = 0;
var phase = 'regular';
var document = {hidden: false};
var console = {warn: function() { warnings.push(Array.from(arguments)); }};
function assert(value, message) { if (!value) throw new Error(message); }
function getJSON(url) {
  return new Promise(function(resolve, reject) { pending.push({url, resolve, reject}); });
}
function entryBudget() { return null; }
function securityHeader() { return STATE.ticker; }
function esc(value) { return String(value); }
function cap(value) { return value.charAt(0).toUpperCase() + value.slice(1); }
// Stages off, so loadChartWorkspace asks for no stage reading beside the chart:
// these scenarios count the chart's own requests.
function wsOverlayDrawn() { return false; }
/* errorHTML is NOT stubbed. It was, returning a bare sentence, and that is
 * how `loadSecurityFacet` came to append a Try again button of its own: the
 * stub showed no control, so one was added beside the call, and the real page
 * rendered two. The stub hid the duplicate from the very tests written to
 * check the failure offers a way out.
 *
 * The real function is pulled in below. Only its two environment reads are
 * stubbed -- the origin poller and the hostname test. */
function startOriginWatch() {}
function originIsEphemeral() { return false; }
function priorSnapshot() { return null; }
function snapshotOf() { return {}; }
function marketSessionET() { return phase; }
function marketHolidayName() { return null; }
function isTapeLiveET() { return ['regular', 'pre', 'after'].includes(phase); }
function hasPendingDraws() { return false; }
function requestAnimationFrame() {}
function preserveUI(host, render) { preserved++; render(); }
function paintFacet() {
  painted.push({header: STATE.ticker, payload: STATE.swing && STATE.swing.ticker});
  views[STATE.view].innerHTML = 'loaded ' + (STATE.swing && STATE.swing.ticker);
}
var renderOverviewView = paintFacet, renderNewsView = paintFacet, renderFinancialsView = paintFacet;
function loadHomeMarket() { refreshed.push('home'); return Promise.resolve(); }
function loadMarket() { refreshed.push('market'); return Promise.resolve(); }
function renderChartWorkspace(data) { painted.push({header: STATE.chartSymbol, payload: data && data.ticker}); }
function syncTabTitle() {}   // the browser tab's title; tests/test_chart_tab_title.py
var wsDockOpen = [], showTrends = false, showAccum = false;
function wsPriceIndicatorIds() { return []; }
"""

# Counted rather than a bare no-op. chromeView('swing') -- collapsing, the mode
# filter and the jump index -- is bolted onto renderSwing by the wrapper at the
# foot of app.js, so "how many times did renderSwing run" is also "did the
# Options tab get its chrome, and did it get it twice".
STUBS += "var rendered = 0;\nfunction renderSwing() { rendered++; }\n"

for name in ["beginLoad", "endLoad", "revealPanels", "writeSnapshot", "setChartLive",
             "setChartAnimation", "loadPatternRates", "loadIndicators",
             "loadSeasonality", "loadSetups", "loadExtras", "loadRelPerf", "mountRelativeChart",
             "updateStatus", "updateChatContext", "wsMountChart", "wsEnsureIntraday"]:
    STUBS += "function " + name + "() {}\n"


def run_js(scenario):
    exe = str(JSC) if JSC.exists() else shutil.which("jsc")
    if not exe:
        pytest.skip("JavaScriptCore is unavailable")
    setup = "\n".join(declaration(name) for name in [
        "ORIGIN_DOWN_RE",
        "swingRequestId", "swingLoading", "swingInFlight", "chartRequestId",
        "SESSION_LABEL", "AUTO_REFRESH_VIEWS", "autoRefreshPending", "REFRESH_HEALTH",
        # liveIndicatorHTML asks whether the loaded name has an overnight print.
        "TICKER_VIEWS"])
    loaders = "\n".join(function(name) for name in [
        "errorHTML",
        "loadSwing", "loadSecurityFacet", "loadChartWorkspace", "tickAutoRefresh", "refreshTarget",
        "overnightPrint", "liveIndicatorHTML", "trimPhase"])
    script = STUBS + setup + loaders + "\n(async function() {\n" + scenario + """
    })().then(function() { print('TEST_OK'); }, function(err) { print(err.stack); });
    """
    result = subprocess.run([exe, "-e", script], capture_output=True, text=True,
                            timeout=15, cwd=ROOT)
    assert "TEST_OK" in result.stdout, result.stdout + result.stderr


@pytest.mark.parametrize("older_fails", [False, True])
def test_old_symbol_cannot_replace_new_symbol_or_its_error(older_fails):
    finish_old = "reject(new Error('old failure'))" if older_fails else "resolve({ticker: 'AAPL'})"
    run_js("""
      var old = loadSecurityFacet('overview', true);
      STATE.ticker = 'MSFT';
      var current = loadSecurityFacet('overview', true);
      pending[1].resolve({ticker: 'MSFT'}); await current;
      pending[0].%s; await old;
      assert(STATE.swing.ticker === 'MSFT', 'stale data replaced MSFT');
      assert(painted.length === 1 && painted[0].payload === 'MSFT', 'stale response painted');
      assert(views.overview.innerHTML === 'loaded MSFT', 'stale error replaced the view');
    """ % finish_old)


def test_newer_request_wins_even_when_symbol_is_the_same():
    """Two live requests for one symbol, and the older one must not land last.

    The scenario used to be two plain forced loads. It cannot be any more:
    those share one request now, which is a stronger guarantee than this test
    was asking for and is asserted separately below. Same symbol, two genuinely
    different requests, is still reachable through the cost limit -- `budget`
    rides on the URL, so changing it while a load is open starts a second one.
    That is the case `swingRequestId` still exists for.
    """
    run_js("""
      var old = loadSwing(true, {silent: true});
      entryBudget = function() { return 500; };  // the reader moved the cost limit
      var current = loadSwing(true, {silent: true});
      assert(pending.length === 2, 'a changed cost limit reused the open request');
      pending[1].resolve({ticker: 'AAPL', revision: 2}); await current;
      pending[0].resolve({ticker: 'AAPL', revision: 1}); await old;
      assert(STATE.swing.revision === 2, 'older same-symbol response won');
      assert(!swingLoading, 'loader stayed busy');
    """)


@pytest.mark.parametrize("view", ["overview", "news", "financials"])
def test_first_load_failure_is_visible_and_retry_recovers(view):
    run_js("""
      STATE.view = '%s';
      var first = loadSecurityFacet(STATE.view, true);
      pending[0].reject(new Error('HTTP 503')); await first;
      assert(!painted.length, 'failed data rendered as an empty successful response');
      assert(views[STATE.view].innerHTML.includes('HTTP 503'), 'error missing');
      assert(views[STATE.view].innerHTML.includes('data-view-retry'), 'retry missing');
      assert((views[STATE.view].innerHTML.match(/Try again/g) || []).length === 1,
             'the same recovery was offered twice');
      var retry = loadSecurityFacet(STATE.view, true);
      pending[1].resolve({ticker: 'AAPL'}); await retry;
      assert(views[STATE.view].innerHTML === 'loaded AAPL', 'retry did not recover');
    """ % view)


def test_background_failure_keeps_last_useful_view():
    run_js("""
      STATE.swing = {ticker: 'AAPL', revision: 1};
      views.overview.innerHTML = 'useful existing reading';
      var refresh = loadSecurityFacet('overview', true, {silent: true});
      assert(views.overview.innerHTML === 'useful existing reading', 'refresh blanked the screen');
      pending[0].reject(new Error('offline')); await refresh;
      assert(STATE.swing.revision === 1, 'refresh lost cached data');
      assert(views.overview.innerHTML === 'useful existing reading', 'failure erased the reading');
    """)


def test_refreshes_home_and_overview_without_overlapping_requests():
    run_js("""
      STATE.view = 'home'; await tickAutoRefresh();
      assert(refreshed.join() === 'home', 'home did not refresh');
      STATE.view = 'overview'; STATE.swing = {ticker: 'AAPL'};
      var refresh = tickAutoRefresh();
      await tickAutoRefresh();
      assert(pending.length === 1, 'overlapping refresh requests');
      pending[0].resolve({ticker: 'AAPL', revision: 2}); await refresh;
      assert(STATE.swing.revision === 2 && preserved === 1, 'overview did not preserve and update UI');
      document.hidden = true; await tickAutoRefresh();
      document.hidden = false; phase = 'closed'; await tickAutoRefresh();
      assert(pending.length === 1, 'hidden or closed market fetched again');
    """)


def test_a_failed_refresh_is_said_on_the_chip_and_a_good_one_clears_it():
    """Reproduced before the fix: the loaders keep the last reading when a
    refresh fails, and the chip went on pulsing "refreshing every 20s" over
    numbers that had stopped moving."""
    run_js("""
      STATE.view = 'overview'; STATE.swing = {ticker: 'AAPL', revision: 1};
      var tick = tickAutoRefresh();
      pending[0].reject(new Error('offline')); await tick;
      var chip = liveIndicatorHTML();
      assert(chip.includes('refresh failed') && !chip.includes('pulse-beat'), 'failure not shown: ' + chip);
      assert(chip.includes('showing the last data loaded'), 'no word on what is shown: ' + chip);
      tick = tickAutoRefresh();
      pending[1].resolve({ticker: 'AAPL', revision: 2}); await tick;
      chip = liveIndicatorHTML();
      assert(chip.includes('refreshing every 20s'), 'a good refresh did not clear it: ' + chip);
    """)


def test_status_only_claims_auto_refresh_for_views_that_refresh():
    run_js("""
      for (var view of ['home', 'overview', 'swing', 'market']) {
        STATE.view = view;
        assert(liveIndicatorHTML().includes('refreshing every 20s'), view + ' missing refresh label');
      }
      for (var view of ['compare', 'news', 'financials', 'long']) {
        STATE.view = view;
        var html = liveIndicatorHTML();
        assert(html.includes('snapshot') && !html.includes('pulse-beat'), view + ' claims live prices');
      }
      phase = 'overnight';
      assert(!liveIndicatorHTML().includes('refreshing'), 'overnight refresh claim');
    """)


def test_the_status_chip_drops_the_phase_the_session_strip_already_names():
    """The strip under the status line prints OVERNIGHT; the chip beside it
    said "Overnight · index futures are live..." The chip keeps only its half."""
    run_js("""
      phase = 'overnight';
      var full = liveIndicatorHTML(), trimmed = liveIndicatorHTML({ phaseShown: true });
      assert(full.includes('Overnight'), 'the unqualified chip lost its phase');
      assert(!trimmed.includes('Overnight') && trimmed.includes('Index futures are live'),
             'the phase is still repeated: ' + trimmed);
    """)


def test_overnight_says_live_only_for_a_name_a_venue_has_printed():
    """It read "Overnight · index futures are live, single stocks are not" for
    every stock. Single stocks do trade overnight, on alternative venues, and
    app/providers/overnight.py now carries those prints -- so whether a name is
    live overnight is a fact about that name, and the label says it per name.

    The dot pulses only where prices are arriving, which is the argument
    setChartLive's own comment makes: a pulse on a price that is not moving
    tells the reader something untrue."""
    run_js("""
      phase = 'overnight';
      STATE.view = 'swing'; STATE.ticker = 'COIN';
      STATE.swing = {ticker: 'COIN', quote: {ticker: 'COIN', price: 183.0}};
      STATE.session = {ticker: 'COIN', session: {phase: 'overnight'},
        prices: {extended: {kind: 'overnight', price: 186.42, change_pct: 1.87,
                            as_of: '2026-10-05T01:31:25Z', venue: 'Bruce ATS'}}};
      var live = liveIndicatorHTML();
      assert(live.includes('Bruce ATS'), 'venue not named: ' + live);
      assert(live.includes('updates every minute'), 'cadence not stated: ' + live);
      assert(live.includes('pulse-beat'), 'a moving price did not pulse');
      // Beside a session strip that already says OVERNIGHT, the chip drops the
      // phase (trimPhase, added upstream in the same release) and keeps the
      // venue and cadence -- the per-name half is the part only it knows.
      var beside = liveIndicatorHTML({ phaseShown: true });
      assert(!beside.includes('Overnight'), 'phase repeated: ' + beside);
      assert(beside.includes('Bruce ATS') && beside.includes('updates every minute'),
             'the per-name half was trimmed away: ' + beside);

      STATE.session = {ticker: 'COIN', session: {phase: 'overnight'}, prices: {}};
      var none = liveIndicatorHTML();
      assert(none.includes('no venue has printed this name tonight'), 'no-print label: ' + none);
      assert(!none.includes('pulse-beat'), 'pulsed with nothing arriving');

      STATE.view = 'home';
      var home = liveIndicatorHTML();
      assert(home.includes('index futures are live'), 'home lost the futures note: ' + home);
      assert(!home.includes('single stocks are not'), 'the false claim is back');
    """)


def test_chart_ignores_old_responses_and_cached_data_for_another_symbol():
    run_js("""
      STATE.view = 'chart';
      var old = loadChartWorkspace('AAPL', true);
      var current = loadChartWorkspace('MSFT', true);
      pending[1].resolve({ticker: 'MSFT'}); await current;
      pending[0].resolve({ticker: 'AAPL'}); await old;
      assert(STATE.chartData.ticker === 'MSFT', 'chart accepted stale data');
      assert(painted[painted.length - 1].payload === 'MSFT', 'chart rendered stale data');
      STATE.chartSymbol = 'AAPL'; // the header search sets this before the loader
      var changed = loadChartWorkspace('AAPL');
      assert(pending.length === 3, 'old cached chart was reused for a new symbol');
      pending[2].resolve({ticker: 'AAPL'}); await changed;
      assert(STATE.chartData.ticker === 'AAPL', 'new chart did not load');
    """)


def test_one_request_serves_every_facet_that_asks_while_it_is_open():
    """A tab change costs one request even when the last one has not landed.

    Measured in a browser at 880px, NVDA, with the response held open: loading
    the symbol and then clicking News, Financials and Options fired four
    identical `GET /api/ticker/NVDA?max_expiries=4&macro=true`, 70.1 KB each,
    all four in flight at once. One per click, because `loadSecurityFacet`
    tests freshness with `STATE.swing.ticker === STATE.ticker` and that is
    still false while the first request is in the air. Same run after the fix:
    one request.

    The reported diagnosis was overlapping refresh timers. It was not -- the
    interval is registered once and fires once every 20 seconds, measured over
    eleven facet switches. The spacing that looked like a timer was the
    reader's own click cadence.
    """
    run_js("""
      STATE.view = 'overview'; var overview = loadSecurityFacet('overview', false);
      STATE.view = 'news';     var news = loadSecurityFacet('news', false);
      STATE.view = 'swing';    var swing = loadSwing(false);
      // A forced load joins too: a response still in the air cannot be staler
      // than one started now.
      var forced = loadSwing(true, {silent: true});
      STATE.view = 'financials'; var financials = loadSecurityFacet('financials', false);
      assert(pending.length === 1, 'one payload, ' + pending.length + ' requests');
      pending[0].resolve({ticker: 'AAPL'});
      await Promise.all([overview, news, swing, forced, financials]);
      assert(STATE.swing.ticker === 'AAPL', 'the shared payload never reached STATE');
      assert(views.financials.innerHTML === 'loaded AAPL', 'the facet on screen did not paint');
      // chromeView('swing') rides on renderSwing. Once, not five times and not
      // never: the Options tab's jump index is rebuilt from that pass.
      assert(rendered === 1, 'renderSwing ran ' + rendered + ' times for one payload');
      assert(!swingLoading && swingInFlight === null, 'the shared request was never released');
    """)


def test_a_facet_that_joined_an_open_request_still_sees_its_failure():
    """Joining must carry the failure across, not just the payload.

    `propagateError` is per-caller: `loadSecurityFacet` passes it so a first
    load can say what went wrong, and the plain Options tab does not. The
    request is shared but that choice is not, so a joiner has to re-apply its
    own. Without it the facet the reader is actually looking at keeps its
    "Loading AAPL..." panel forever on a 503, which reads as a hung tab rather
    than a failed one.
    """
    run_js("""
      STATE.view = 'overview'; var overview = loadSecurityFacet('overview', false);
      STATE.view = 'news';     var news = loadSecurityFacet('news', false);
      assert(pending.length === 1, 'the second facet opened its own request');
      pending[0].reject(new Error('HTTP 503'));
      await Promise.all([overview, news]);
      assert(views.news.innerHTML.includes('HTTP 503'), 'the joined facet lost the failure');
      assert(views.news.innerHTML.includes('data-view-retry'), 'no way back from the failure');
      assert(!painted.length, 'a failed request painted a facet anyway');
    """)


def test_joining_a_request_that_a_new_symbol_supersedes_does_not_hang():
    """The shared promise settles even when its own request is abandoned.

    The owner returns early when a newer symbol has superseded it, and the
    tempting shape -- settle only while still the open request -- leaves every
    joiner awaiting a promise that nothing will ever resolve. The facet does
    not error and does not paint; it sits on its loading panel for the rest of
    the session. Settled unconditionally, released conditionally.
    """
    run_js("""
      STATE.view = 'overview'; var first = loadSecurityFacet('overview', false);
      STATE.view = 'news';     var joiner = loadSecurityFacet('news', false);
      assert(pending.length === 1, 'the joiner opened its own request');
      STATE.ticker = 'MSFT';
      STATE.view = 'overview'; var newer = loadSecurityFacet('overview', true);
      assert(pending.length === 2, 'a new symbol reused the open request');
      pending[1].resolve({ticker: 'MSFT'}); await newer;
      pending[0].resolve({ticker: 'AAPL'});
      await Promise.all([first, joiner]);
      assert(STATE.swing.ticker === 'MSFT', 'the abandoned response replaced MSFT');
    """)


def test_the_refresh_tick_still_fires_after_a_shared_load():
    """Sharing a request must not turn the 20-second refresh into a no-op.

    The point of the fix is that a tab change costs nothing extra, not that the
    tape stops arriving. Once the shared request is released the next tick has
    to open a genuinely new one, because by then the payload it would reuse is
    the thing being refreshed.
    """
    run_js("""
      STATE.view = 'swing';
      var load = loadSwing(false), joined = loadSwing(false);
      assert(pending.length === 1, 'the second caller opened its own request');
      pending[0].resolve({ticker: 'AAPL', revision: 1});
      await Promise.all([load, joined]);
      var tick = tickAutoRefresh();
      assert(pending.length === 2, 'the refresh tick was swallowed by the finished request');
      pending[1].resolve({ticker: 'AAPL', revision: 2}); await tick;
      assert(STATE.swing.revision === 2, 'the refresh never landed');
    """)
