"""A server restart is waited out, not reported as an outage.

Reported from VST's Overview during the 2026-10-06 deploy: "The server is not
reachable. the connection dropped after 5 attempts", with the chip beside it
still saying "Market open · refreshing every 20s". A deploy here stops the old
server before the new one is up (one replica on a volume), and each request
retried on its own for fifteen seconds and then painted that box into its
panel, usually seconds before the server came back, and then reloaded the page.

Run against a fake clock and a server that is away for a set time: the page
waits once for all its requests, says so in one line, and carries on when the
server answers, with no reload. Only an outage past the two-minute wait is
reported as one.
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


HARNESS = r"""
function assert(value, message) { if (!value) throw new Error(message); }

// A clock the test moves. Timers run in the order they fall due, and the
// clock jumps to each one, so two minutes of waiting take no time at all.
var now = 0;
Date.now = function () { return now; };
var timers = [];
function setTimeout(fn, ms) { timers.push({ at: now + (ms || 0), fn: fn }); return timers.length; }
function clearTimeout() {}
async function settle() { for (var k = 0; k < 60; k++) await Promise.resolve(); }
async function step() {
  await settle();
  if (!timers.length) return false;
  timers.sort(function (a, b) { return a.at - b.at; });
  var t = timers.shift();
  now = Math.max(now, t.at);
  t.fn();
  await settle();
  return true;
}
async function runUntil(done) {
  for (var n = 0; n < 2000 && !done(); n++) { if (!(await step())) break; }
}

// The server: away until `downUntil`, then answering everything.
var downUntil = 0, healthChecks = 0, calls = [];
function fetch(url, opts) {
  if (url === '/healthz') healthChecks++;
  else calls.push({ url: url, at: now, method: (opts && opts.method) || 'GET' });
  if (now < downUntil) return Promise.reject(new TypeError('Load failed'));
  return Promise.resolve({ ok: true, status: 200,
    json: function () { return Promise.resolve({ url: url }); } });
}
function tries(url) { return calls.filter(function (c) { return c.url === url; }).length; }

// Just enough page for the one line at the top.
var body = { kids: [], appendChild: function (el) { this.kids.push(el); } };
var document = {
  body: body,
  createElement: function (tag) {
    return { tag: tag, id: '', className: '', dataset: {}, attrs: {}, innerHTML: '',
      setAttribute: function (k, v) { this.attrs[k] = v; },
      remove: function () { var i = body.kids.indexOf(this); if (i >= 0) body.kids.splice(i, 1); } };
  },
  getElementById: function (id) {
    return body.kids.filter(function (k) { return k.id === id; })[0] || null;
  },
};
function banner() { return document.getElementById('origin-banner'); }
var statusPaints = 0;
function updateStatus() { statusPaints++; }
var reloads = 0;
var window = { location: { reload: function () { reloads++; } }, OpticAuth: null };
function writeToken() { return ''; }
function setWriteToken() {}
function originIsEphemeral() { return false; }

var got = [], failed = [];
function ask(url) {
  return getJSON(url).then(function (v) { got.push(v.url); return v; },
                           function (e) { failed.push(e); throw e; });
}
"""


def run_js(scenario):
    exe = str(JSC) if JSC.exists() else shutil.which("jsc")
    if not exe:
        pytest.skip("JavaScriptCore is unavailable")
    setup = "\n".join(declaration(name) for name in [
        "RETRY_DELAYS_MS", "ORIGIN_WAIT_MS", "originGate", "originAwaySince"])
    code = "\n".join(function(name) for name in [
        "worthRetrying", "waitForOrigin", "pollOrigin", "paintOriginBanner",
        "retryAfter", "getJSON", "postJSON"])
    script = HARNESS + setup + "\n" + code + "\n(async function() {\n" + scenario + """
    })().then(function() { print('TEST_OK'); }, function(err) { print('FAIL ' + err + '\\n' + err.stack); });
    """
    result = subprocess.run([exe, "-e", script], capture_output=True, text=True,
                            timeout=30, cwd=ROOT)
    assert "TEST_OK" in result.stdout, result.stdout + result.stderr


def test_a_restart_is_waited_out_and_the_page_carries_on_without_a_reload():
    run_js("""
      downUntil = 75000;                 // a deploy's worth of nothing
      var ticker = ask('/api/ticker/VST').catch(function () {});
      await runUntil(function () { return originGate !== null; });
      assert(tries('/api/ticker/VST') === 5, 'the quick retries come first: ' + tries('/api/ticker/VST'));
      assert(now === 15000, 'and take fifteen seconds: ' + now);
      var bar = banner();
      assert(bar && bar.innerHTML.indexOf('Reconnecting to the server.') >= 0, 'the line says so');
      assert(bar.innerHTML.indexOf('restarting for an update') >= 0, bar.innerHTML);
      assert(bar.attrs.role === 'status', 'and is announced, not shouted');
      assert(statusPaints === 1, 'the chip was told once: ' + statusPaints);

      // Asked while the page waits: one try, then the same wait.
      var quote = ask('/api/quote/VST').catch(function () {});
      await settle();
      assert(tries('/api/quote/VST') === 1, 'no retries of its own: ' + tries('/api/quote/VST'));

      await runUntil(function () { return got.length === 2 || failed.length > 0; });
      assert(failed.length === 0, 'nothing failed: ' + failed.map(String));
      assert(got.indexOf('/api/ticker/VST') >= 0 && got.indexOf('/api/quote/VST') >= 0, got);
      assert(now >= downUntil && now - downUntil <= 5000, 'carried on within a check of the return: ' + now);
      assert(originGate === null && !banner(), 'the line is gone with the wait');
      assert(reloads === 0, 'and nothing reloaded');
      assert(healthChecks > 1 && healthChecks < 20, 'one poll for the page: ' + healthChecks);
      assert(tries('/api/quote/VST') === 2, 'the late one tried before the wait and after it, '
             + 'and not in between: ' + tries('/api/quote/VST'));
    """)


def test_a_request_that_still_fails_after_the_wait_stops():
    """/healthz answering does not mean every endpoint does: a proxy can still
    give one of them a 502. Each request waits once, or that request and the
    poll would chase each other for as long as the tab stayed open."""
    run_js("""
      fetch = function (url) {
        if (url === '/healthz') { healthChecks++; return Promise.resolve({ ok: true, status: 200 }); }
        calls.push({ url: url, at: now });
        return Promise.resolve({ ok: false, status: 502, statusText: '',
          json: function () { return Promise.reject(new Error('an HTML error page')); } });
      };
      var caught = null;
      getJSON('/api/ticker/VST').catch(function (e) { caught = e; });
      await runUntil(function () { return caught !== null; });
      assert(caught && caught.originUnreachable === true, 'gave up, marked: ' + caught);
      assert(caught.message === 'the server is unreachable (HTTP 502) after 6 attempts', caught.message);
      // Five quick tries, the wait, one more: then it says so.
      assert(healthChecks === 1, 'one wait: ' + healthChecks);
    """)


def test_one_poll_for_the_page_however_many_requests_wait():
    run_js("""
      downUntil = 40000;
      var urls = ['/api/ticker/VST', '/api/quote/VST', '/api/home', '/api/market'];
      urls.forEach(function (u) { ask(u).catch(function () {}); });
      await runUntil(function () { return got.length === urls.length || failed.length > 0; });
      assert(failed.length === 0 && got.length === urls.length, 'all four carried on: ' + got);
      // 15s of quick retries, then checks 1, 2, 4, 6, 9, 12, 16, 20 and 25s into
      // the wait: the ninth, at 40s, finds it back. Nine, not thirty-six.
      assert(healthChecks === 9, 'checks: ' + healthChecks);
    """)


def test_an_outage_past_the_wait_is_reported_as_one():
    run_js("""
      downUntil = Infinity;
      var caught = null;
      var p = getJSON('/api/ticker/VST').catch(function (e) { caught = e; });
      await runUntil(function () { return originGate !== null; });
      var opened = now;
      await runUntil(function () { return caught !== null; });
      assert(caught && caught.originUnreachable === true, 'marked for the error box');
      assert(caught.message === 'the connection dropped after 5 attempts', caught.message);
      assert(now - opened === 120000, 'after two minutes of waiting: ' + (now - opened));
      assert(healthChecks === ORIGIN_WAIT_MS.length, 'checked ' + healthChecks + ' times');
      assert(!banner(), 'the panel says it now, not the line');
      assert(reloads === 0, 'nothing reloaded either');
    """)


def test_a_wait_that_runs_on_says_for_how_long():
    run_js("""
      downUntil = Infinity;
      var first = null;
      getJSON('/api/ticker/VST').catch(function (e) { first = e; });
      await runUntil(function () { return first !== null; });
      // The next refresh finds it still away and waits again.
      getJSON('/api/ticker/VST').catch(function () {});
      await runUntil(function () { return originGate !== null; });
      assert(banner().innerHTML.indexOf('It has not answered for 2 minutes.') >= 0, banner().innerHTML);
      assert(banner().innerHTML.indexOf('restarting') < 0, 'no longer guessed at');
      // And it keeps count while it waits: first missed at 15s, so 3 minutes at 195s.
      await runUntil(function () { return now >= 195000; });
      assert(banner().innerHTML.indexOf('It has not answered for 3 minutes.') >= 0, banner().innerHTML);
    """)


def test_the_server_answering_resets_the_count():
    run_js("""
      downUntil = 30000;
      ask('/api/ticker/VST');
      await runUntil(function () { return got.length === 1; });
      assert(originAwaySince === null, 'forgotten once it answered');
      downUntil = now + 30000;
      ask('/api/ticker/VST').catch(function () {});
      await runUntil(function () { return originGate !== null; });
      assert(banner().innerHTML.indexOf('restarting for an update') >= 0, 'a new restart, not a long one');
    """)


def test_an_answer_from_the_app_is_not_waited_on():
    """A 404 with a reason, or a 500, is the app answering. Waiting for the
    server to come back would hold an answer that has already arrived."""
    run_js("""
      fetch = function (url) {
        calls.push({ url: url });
        if (url === '/api/ticker/ZZZZ') return Promise.resolve({ ok: false, status: 404, statusText: '',
          json: function () { return Promise.resolve({ detail: 'No data for ZZZZ.' }); } });
        return Promise.resolve({ ok: false, status: 500, statusText: '',
          json: function () { return Promise.reject(new Error('not JSON')); } });
      };
      var a = null, b = null;
      await getJSON('/api/ticker/ZZZZ').catch(function (e) { a = e; });
      await getJSON('/api/home').catch(function (e) { b = e; });
      assert(a && a.message === 'No data for ZZZZ.', a && a.message);
      assert(b && b.message === 'request failed (HTTP 500)', b && b.message);
      assert(originGate === null && !banner() && timers.length === 0, 'no wait was started');
      assert(calls.length === 2, 'asked once each');
    """)


def test_a_post_asked_for_during_the_wait_goes_once_when_the_server_is_back():
    """POSTs are never retried, because "run a scan" is not to be fired twice.
    One asked for while the page is already waiting has not been sent at all,
    so it is held and sent once, instead of failing into the outage."""
    run_js("""
      downUntil = 45000;
      ask('/api/ticker/VST').catch(function () {});
      await runUntil(function () { return originGate !== null; });
      var answered = null;
      postJSON('/api/briefing', { symbols: ['VST'] }).then(function (v) { answered = v; });
      await settle();
      assert(tries('/api/briefing') === 0, 'not sent into the outage');
      await runUntil(function () { return answered !== null; });
      assert(tries('/api/briefing') === 1, 'sent once: ' + tries('/api/briefing'));
      assert(calls.filter(function (c) { return c.url === '/api/briefing'; })[0].at >= downUntil, 'after the return');
      assert(answered.url === '/api/briefing');
    """)


def test_the_wait_is_two_minutes_checked_often_at_first():
    run_js("""
      var total = ORIGIN_WAIT_MS.reduce(function (a, b) { return a + b; }, 0);
      assert(total === 120000, 'two minutes: ' + total);
      assert(ORIGIN_WAIT_MS[0] === 1000 && Math.max.apply(null, ORIGIN_WAIT_MS) === 5000, ORIGIN_WAIT_MS);
    """)


def test_the_line_is_styled_from_tokens():
    css = (ROOT / "static/styles.css").read_text()
    block = css[css.index(".origin-banner {"):]
    block = block[:block.index(".origin-banner strong")]
    assert "#" not in block, "a colour that is not a token"
    assert "var(--warn)" in block and "var(--surface)" in block
    # A fixed box at left: 50% has half the viewport to shrink into; without
    # its own width the line wrapped onto five rows.
    assert "width: max-content;" in block
