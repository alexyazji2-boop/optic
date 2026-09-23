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
function errorHTML(value) { return 'Could not load: ' + value; }
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
var wsDockOpen = [], showTrends = false, showAccum = false;
function wsPriceIndicatorIds() { return []; }
"""

for name in ["beginLoad", "endLoad", "revealPanels", "writeSnapshot", "setChartLive",
             "setChartAnimation", "renderSwing", "loadPatternRates", "loadIndicators",
             "loadSeasonality", "loadExtras", "loadRelPerf", "mountRelativeChart",
             "updateStatus", "updateChatContext", "wsMountChart", "wsEnsureIntraday"]:
    STUBS += "function " + name + "() {}\n"


def run_js(scenario):
    exe = str(JSC) if JSC.exists() else shutil.which("jsc")
    if not exe:
        pytest.skip("JavaScriptCore is unavailable")
    setup = "\n".join(declaration(name) for name in [
        "swingRequestId", "swingLoading", "chartRequestId", "SESSION_LABEL",
        "AUTO_REFRESH_VIEWS", "autoRefreshPending"])
    loaders = "\n".join(function(name) for name in [
        "loadSwing", "loadSecurityFacet", "loadChartWorkspace", "tickAutoRefresh",
        "liveIndicatorHTML"])
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
    run_js("""
      var old = loadSwing(true, {silent: true});
      var current = loadSwing(true, {silent: true});
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
      assert(views[STATE.view].innerHTML.includes('data-retry-security'), 'retry missing');
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
