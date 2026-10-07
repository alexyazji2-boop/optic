"""A different account signed in on the same browser starts a new session.

Reported from a shared computer: "When I switched from my account to yours,
the question in the report the problem was still there and the searches I did
on my account were on yours." The server kept every account's rows apart. The
browser did not. Signing out and in never reloaded the page, so the Report a
problem box kept its text, and the recent symbols, Pulse conversations,
drawings and the rest live in localStorage, which is the browser's rather than
anybody's.

Now the browser notes whose things it holds. When somebody else signs in, or
the account signs out, the page reloads, and at the top of the new load, before
any store is read, the last person's keys go on a shelf of their own and the
new person's come back. Tested here with a fake storage and the real functions:

* sign out, and the next person sees none of it; sign back in, and it is back;
* a guest's work goes with the first account signed in over it, so the
  watchlist and theses a new account adopts are still there to adopt;
* a failed write never loses a value and never loops the page.

Checked in a browser against the local server with two throwaway accounts: a
report typed, a symbol opened and a chart note written as one were gone after
signing out and signing in as the other, and the symbols and note were back
after signing in as the first again. A second tab open as the first account
reloaded as a guest when the first tab signed out.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
RAW = (ROOT / "static/app.js").read_text()
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc"

A = "0b7c1f9e-0000-4000-8000-00000000000a"
B = "0b7c1f9e-0000-4000-8000-00000000000b"


def _raw_fn(name):
    return re.search(r"^function %s\([^\n]*\) \{.*?^\}" % name, RAW, re.M | re.S).group()


def _section():
    """The device session block, from its constants to the storage listener."""
    start = RAW.index("const SESSION_HOLDER_KEY = ")
    end = RAW.index("/* Views that render without a loaded symbol.")
    return RAW[start:end]


HARNESS = """
function assert(v, m) { if (!v) throw new Error(m); }
function Store(quota) {
  this.data = {}; this.quota = quota || Infinity; this.writes = 0;
}
Store.prototype.getItem = function (k) { return k in this.data ? this.data[k] : null; };
Store.prototype.setItem = function (k, v) {
  v = String(v);
  var size = 0, d = this.data;
  Object.keys(d).forEach(function (x) { if (x !== k) size += x.length + d[x].length; });
  if (size + k.length + v.length > this.quota) throw new Error('QuotaExceededError');
  d[k] = v; this.writes++;
};
Store.prototype.removeItem = function (k) { delete this.data[k]; };
var localStorage = new Store();
var sessionStorage = new Store();
var reloads = 0;
var location = { reload: function () { reloads++; } };
var listeners = {};
var window = { addEventListener: function (type, fn) { listeners[type] = fn; } };
var FIELDS = {};
var document = { getElementById: function (id) { return FIELDS[id] || null; } };
"""


def _run(scenario, boot=True):
    """The section as a page runs it, with `newPage()` standing in for a reload:
    a fresh evaluation over the same storage, as the browser gives it."""
    exe = JSC if os.path.exists(JSC) else shutil.which("jsc")
    if not exe:
        pytest.skip("no JavaScriptCore on this machine")
    section = _section()
    src = HARNESS + """
      var SECTION = %s;
      var page = null;
      function newPage() {
        var run = new Function('localStorage', 'sessionStorage', 'location', 'window', 'document',
          SECTION + '\\nreturn { keep: keepDeviceSession, toGuest: handDeviceSessionToGuest,' +
          ' swap: swapDeviceSession, keys: PERSONAL_KEYS,' +
          ' bring: bringGuestThings, keepOut: keepGuestThingsOut,' +
          ' asked: function () { return sessionAskPending; },' +
          ' said: function () { return sessionSaid; }, ending: function () { return sessionEnding; },' +
          ' stuck: function () { return sessionStuck; } };');
        page = run(localStorage, sessionStorage, location, window, document);
        return page;
      }
      function user(id, email) { return { status: 'user', user: { id: id, email: email || 'x@example.test' } }; }
      var GUEST = { status: 'guest', user: null };
      var A = %s, B = %s;
    """ % (json.dumps(section), json.dumps(A), json.dumps(B))
    if boot:
        src += "newPage();\n"
    out = subprocess.run([exe, "-e", src + scenario + "\nprint('TEST_OK');"],
                         capture_output=True, text=True, timeout=60)
    assert "TEST_OK" in out.stdout, out.stdout + out.stderr


# ------------------------------------------------------------- the report


def test_signing_out_puts_the_accounts_things_away_and_reloads():
    _run("""
      page.keep(user(A));
      localStorage.setItem('optic.recent.v1', '["NVDA","TSLA"]');
      localStorage.setItem('optic.pulse.history.v1', '[{"id":"c1"}]');
      localStorage.setItem('optic.theme', 'dark');
      assert(page.keep(GUEST) === true && reloads === 1, 'signing out reloads');
      assert(localStorage.getItem('optic.recent.v1') === '["NVDA","TSLA"]',
        'nothing moves under the old page');
      newPage();
      assert(localStorage.getItem('optic.recent.v1') === null, 'the searches are put away');
      assert(localStorage.getItem('optic.pulse.history.v1') === null, 'and the conversations');
      assert(localStorage.getItem('optic.theme') === 'dark', 'the theme is the browser\\'s');
      assert(page.keep(GUEST) === false && reloads === 1, 'and the new page stays');
    """)


def test_the_next_account_sees_none_of_it_and_the_first_gets_it_back():
    _run("""
      page.keep(user(A));
      localStorage.setItem('optic.recent.v1', '["NVDA"]');
      localStorage.setItem('optic.chart.drawings.v1', '{"NVDA":[1]}');
      page.keep(GUEST); newPage(); page.keep(GUEST);
      // B has never been here: signs in over an empty guest session, no reload.
      assert(page.keep(user(B)) === false && reloads === 1, 'a first sign-in keeps the page');
      assert(localStorage.getItem('optic.recent.v1') === null, 'none of A\\'s searches');
      assert(localStorage.getItem('optic.chart.drawings.v1') === null, 'none of A\\'s drawings');
      localStorage.setItem('optic.recent.v1', '["AAPL"]');
      page.keep(GUEST); newPage(); page.keep(GUEST);
      assert(localStorage.getItem('optic.recent.v1') === null, 'B\\'s go away as well');
      // A comes back: this browser has held A, so A's things return.
      assert(page.keep(user(A)) === true && reloads === 3, 'a returning account reloads');
      newPage();
      assert(localStorage.getItem('optic.recent.v1') === '["NVDA"]', 'A\\'s searches are back');
      assert(localStorage.getItem('optic.chart.drawings.v1') === '{"NVDA":[1]}', 'and drawings');
      assert(page.keep(user(A)) === false, 'settled');
      page.keep(GUEST); newPage(); page.keep(user(B)); newPage();
      assert(localStorage.getItem('optic.recent.v1') === '["AAPL"]', 'and B\\'s are B\\'s');
    """)


def test_the_typed_fields_are_emptied_on_the_new_page():
    """Chrome drops a textarea's text on reload and Firefox puts it back, so
    the new page empties the three fields that are in the HTML itself."""
    _run("""
      page.keep(user(A));
      page.keep(GUEST);
      FIELDS['rp-text'] = { value: 'The chart froze on TSLA' };
      FIELDS['chat-input'] = { value: 'what about my puts' };
      FIELDS['ticker-input'] = { value: 'NV' };
      newPage();
      assert(FIELDS['rp-text'].value === '', 'the report is empty');
      assert(FIELDS['chat-input'].value === '' && FIELDS['ticker-input'].value === '', 'and the rest');
    """)


def test_an_ordinary_reload_leaves_the_fields_alone():
    _run("""
      page.keep(user(A));
      FIELDS['rp-text'] = { value: 'half a report' };
      newPage();
      assert(FIELDS['rp-text'].value === 'half a report', 'no switch, nothing emptied');
    """)


def test_the_new_page_says_what_happened_once():
    _run("""
      page.keep(user(A));
      page.keep(GUEST);
      newPage();
      assert(page.said() === 'out', 'signed out');
      page.keep(GUEST);
      page.keep(user(B));
      page.keep(GUEST);
      newPage();
      page.keep(GUEST);
      page.keep(user(B));
      newPage();
      assert(page.said() === 'in', 'signed in to an account with things here');
    """)


def test_a_switch_found_on_load_says_nothing():
    """A session that ended elsewhere, or expired, is found when the page
    settles. Nobody pressed anything on this page, so there is nothing to say."""
    _run("""
      page.keep(user(A));
      newPage();
      page.keep(GUEST);
      newPage();
      assert(page.said() === '', 'quiet');
      assert(localStorage.getItem('optic.session.holder.v1') === 'guest', 'but switched');
    """)


# --------------------------------------------------------- guest and account


def test_a_guest_signing_up_is_asked_and_brought_in_keeps_their_work():
    """The watchlist and theses a guest built are what accountLoad adopts into
    a new account, so brought in they must still be in the browser when it
    runs. Asked first: on a shared computer the next person's account would
    otherwise take a stranger's things (asked for 2026-10-06)."""
    _run("""
      page.keep(GUEST);
      localStorage.setItem('optic.chart.watch.v1', '["NVDA","AMD"]');
      localStorage.setItem('optic.thesis.v1', '{"NVDA":{"bull":"data centres"}}');
      assert(page.keep(user(A)) === true && reloads === 0, 'asked, and nothing loads meanwhile');
      assert(page.asked().things.join() === 'a watchlist,theses', 'named: ' + page.asked().things);
      assert(localStorage.getItem('optic.session.holder.v1') === 'guest', 'not A\\'s until answered');
      assert(page.keep(user(A)) === true, 'still waiting, asked once');
      assert(page.bring() === true, 'brought in');
      assert(localStorage.getItem('optic.chart.watch.v1') === '["NVDA","AMD"]', 'watchlist kept');
      assert(localStorage.getItem('optic.thesis.v1') === '{"NVDA":{"bull":"data centres"}}', 'theses kept');
      assert(localStorage.getItem('optic.session.holder.v1') === A, 'and now A\\'s');
      assert(page.keep(user(A)) === false, 'and the next settle goes on');
    """)


def test_kept_out_the_guests_things_wait_for_the_next_guest():
    _run("""
      page.keep(GUEST);
      localStorage.setItem('optic.chart.watch.v1', '["GME"]');
      localStorage.setItem('optic.recent.v1', '["GME"]');
      page.keep(user(A));
      assert(page.keepOut() === true && reloads === 1, 'a fresh page for A');
      newPage();
      assert(localStorage.getItem('optic.chart.watch.v1') === null, 'A starts with none of it');
      assert(localStorage.getItem('optic.recent.v1') === null, 'not even the searches');
      assert(localStorage.getItem('optic.session.holder.v1') === A, 'and is A\\'s');
      assert(page.keep(user(A)) === false, 'nothing more to ask');
      page.keep(GUEST); newPage(); page.keep(GUEST);
      assert(localStorage.getItem('optic.chart.watch.v1') === '["GME"]', 'the guest\\'s are back');
    """)


def test_nothing_worth_asking_about_is_not_asked():
    """An empty list, a book with nothing open and the settings are not a
    guest's things."""
    _run("""
      page.keep(GUEST);
      localStorage.setItem('optic.chart.watch.v1', '[]');
      localStorage.setItem('optic.paper.v1', '{"open":[],"closed":[]}');
      localStorage.setItem('optic.thesis.v1', '{"NVDA":{"bull":"","bear":""}}');
      localStorage.setItem('optic.screener.v1', '{"filters":[],"states":[],"sort":"score","direction":"desc"}');
      localStorage.setItem('optic.theme', 'dark');
      assert(page.keep(user(A)) === false && page.asked() === null, 'no question');
      assert(localStorage.getItem('optic.session.holder.v1') === A, 'A\\'s');
    """)


def test_a_returning_account_does_not_take_a_guests_work():
    _run("""
      page.keep(user(A));
      localStorage.setItem('optic.recent.v1', '["NVDA"]');
      page.keep(GUEST); newPage(); page.keep(GUEST);
      localStorage.setItem('optic.recent.v1', '["GME"]');
      page.keep(user(A)); newPage();
      assert(localStorage.getItem('optic.recent.v1') === '["NVDA"]', 'A gets A\\'s');
      page.keep(user(A));
      page.keep(GUEST); newPage();
      assert(localStorage.getItem('optic.recent.v1') === '["GME"]', 'the guest\\'s waited');
    """)


def test_an_account_with_nothing_here_is_still_known():
    """A shelf is written even when empty, so an account that kept nothing
    local still gets its own session back rather than a guest's."""
    _run("""
      page.keep(user(A));
      page.keep(GUEST); newPage(); page.keep(GUEST);
      localStorage.setItem('optic.recent.v1', '["GME"]');
      assert(page.keep(user(A)) === true, 'known, so a switch');
      newPage();
      assert(localStorage.getItem('optic.recent.v1') === null, 'not the guest\\'s');
    """)


def test_a_browser_from_before_this_asks_too():
    """Its things could be anybody's: the same question, the same answers."""
    _run("""
      localStorage.setItem('optic.recent.v1', '["NVDA"]');
      newPage();
      assert(page.keep(user(A)) === true && reloads === 0, 'asked');
      page.bring();
      assert(localStorage.getItem('optic.session.holder.v1') === A, 'noted');
      assert(localStorage.getItem('optic.recent.v1') === '["NVDA"]', 'and kept');
    """)


def test_a_deleted_account_leaves_its_things_to_the_guest_as_before():
    _run("""
      page.keep(user(A));
      localStorage.setItem('optic.paper.v1', '{"open":[],"closed":[]}');
      page.toGuest();
      assert(page.keep(GUEST) === false && reloads === 0, 'no switch');
      assert(localStorage.getItem('optic.paper.v1') === '{"open":[],"closed":[]}', 'kept live');
      assert(localStorage.getItem('optic.session.shelf.' + A) === null, 'no orphaned shelf');
    """)


def test_a_repeat_of_the_same_account_does_nothing():
    _run("""
      page.keep(user(A));
      var writes = localStorage.writes;
      page.keep(user(A)); page.keep(user(A));
      assert(localStorage.writes === writes && reloads === 0, 'a refresh is not a switch');
    """)


# ------------------------------------------------------------------ other tabs


def test_another_tab_switching_reloads_this_one():
    _run("""
      page.keep(user(A));
      listeners.storage({ key: 'optic.session.holder.v1', newValue: 'guest' });
      assert(reloads === 1 && page.ending(), 'this tab was still A\\'s page');
    """)


def test_other_keys_and_the_same_holder_do_not():
    _run("""
      page.keep(user(A));
      listeners.storage({ key: 'optic.recent.v1', newValue: '[]' });
      listeners.storage({ key: 'optic.session.holder.v1', newValue: A });
      listeners.storage({ key: null, newValue: null });
      assert(reloads === 0, 'nothing to start again for');
    """)


def test_a_switch_another_tab_made_first_is_not_made_twice():
    _run("""
      page.keep(user(A));
      localStorage.setItem('optic.recent.v1', '["NVDA"]');
      page.keep(GUEST);
      // The other tab reloaded first and made the switch.
      page.swap(A, 'guest');
      localStorage.setItem('optic.recent.v1', '["GME"]');
      newPage();
      assert(localStorage.getItem('optic.recent.v1') === '["GME"]', 'the guest\\'s own, untouched');
      assert(JSON.parse(localStorage.getItem('optic.session.shelf.' + A))['optic.recent.v1']
        === '["NVDA"]', 'A\\'s shelved once');
    """)


# ---------------------------------------------------------- failure is safe


def test_a_full_quota_moves_nothing_and_does_not_loop():
    _run("""
      page.keep(user(A));
      localStorage.setItem('optic.recent.v1', '["NVDA"]');
      localStorage.quota = 0;           // every write refused from here on
      page.keep(GUEST);
      newPage();
      assert(page.stuck(), 'the switch did not take');
      assert(localStorage.getItem('optic.recent.v1') === '["NVDA"]', 'nothing lost');
      assert(page.keep(GUEST) === false && reloads === 1, 'and no second reload');
    """)


def test_a_shelf_that_cannot_be_written_leaves_the_live_keys_where_they_are():
    _run("""
      localStorage.setItem('optic.recent.v1', '["NVDA"]');
      localStorage.setItem('optic.chart.notes.v1', '{"NVDA":"why"}');
      localStorage.quota = 80;          // room for the keys, not for a shelf beside them
      var threw = false;
      try { page.swap(A, 'guest'); } catch (e) { threw = true; }
      assert(threw, 'it says so');
      assert(localStorage.getItem('optic.recent.v1') === '["NVDA"]', 'recents where they were');
      assert(localStorage.getItem('optic.chart.notes.v1') === '{"NVDA":"why"}', 'notes too');
      assert(localStorage.getItem('optic.session.holder.v1') === null, 'and nobody switched');
    """)


def test_a_shelf_that_cannot_all_come_back_stays_until_it_can():
    _run("""
      var note = '{"NVDA":"a long note about why"}';
      localStorage.setItem('optic.session.holder.v1', 'guest');
      localStorage.setItem('optic.session.shelf.' + A,
        JSON.stringify({ 'optic.recent.v1': '["NVDA"]', 'optic.chart.notes.v1': note }));
      var used = 0;
      Object.keys(localStorage.data).forEach(function (k) { used += k.length + localStorage.data[k].length; });
      // The guest's empty shelf, the longer holder, and the recents: not the note.
      localStorage.quota = used + ('optic.session.shelf.guest{}').length + (A.length - 5)
        + ('optic.recent.v1["NVDA"]').length + 10;
      page.swap('guest', A);
      assert(localStorage.getItem('optic.recent.v1') === '["NVDA"]', 'what fitted came back');
      assert(localStorage.getItem('optic.chart.notes.v1') === null, 'the note did not fit');
      assert(localStorage.getItem('optic.session.shelf.' + A) !== null, 'so the shelf is kept');
      localStorage.quota = Infinity;
      localStorage.setItem('optic.recent.v1', '["NVDA","AMD"]');
      page.swap(A, 'guest');
      var shelf = JSON.parse(localStorage.getItem('optic.session.shelf.' + A));
      assert(shelf['optic.chart.notes.v1'] === note, 'nothing lost');
      assert(shelf['optic.recent.v1'] === '["NVDA","AMD"]', 'and the newer value wins');
    """)


def test_no_storage_at_all_is_a_page_that_works():
    _run("""
      localStorage.getItem = function () { throw new Error('SecurityError'); };
      newPage();
      assert(page.keep(user(A)) === false && page.keep(GUEST) === false, 'no switch');
      assert(reloads === 0, 'and no reload');
    """)


def test_a_shelf_only_brings_back_personal_keys():
    _run("""
      page.keep(user(A));
      page.keep(GUEST); newPage(); page.keep(GUEST);
      localStorage.setItem('optic.session.shelf.' + A,
        JSON.stringify({ 'optic.recent.v1': '["NVDA"]', 'optic.theme': 'light' }));
      page.keep(user(A)); newPage();
      assert(localStorage.getItem('optic.recent.v1') === '["NVDA"]', 'personal, restored');
      assert(localStorage.getItem('optic.theme') === null, 'a setting is not the shelf\\'s to write');
    """)


# ----------------------------------------------------------------- wiring


def test_it_runs_before_any_store_is_read():
    """The drawings and the paper book are read once, while app.js loads. A
    swap after that would leave the old person's copy in memory, to be saved
    over the new person's on the next edit."""
    begin = RAW.index("(function beginDeviceSession() {")
    for read in ("localStorage.getItem(WS_DRAW_KEY)", "localStorage.getItem(PAPER_KEY)",
                 "localStorage.getItem(LT_MODE_KEY)", "localStorage.getItem(IND_STATE_KEY)"):
        assert begin < RAW.index(read), read
    assert begin < RAW.index("(async function boot() {")


def test_the_auth_listener_switches_before_it_loads_the_account():
    """accountLoad adopts the browser's watchlist and theses into an account
    that has none. Run first, it would adopt the last person's."""
    after = RAW[RAW.index("const afterSessionKept = (state) => {"):]
    after = after[:after.index("\n  };")]
    assert "accountLoad()" in after and "if (sessionSaid) {" in after
    assert "'Signed out. The terminal stays open.'" in after
    wiring = RAW[RAW.index("window.OpticAuth.on((state) => {"):]
    wiring = wiring[:wiring.index("\n  });\n}")]
    assert wiring.index("if (keepDeviceSession(state)) return;") < wiring.index("afterSessionKept(state);")
    assert "accountLoad()" not in wiring, "only after the session is settled"


def test_the_question_has_both_answers_wired():
    ask = RAW[RAW.index("window.onGuestThings = (ask) => {"):]
    ask = ask[:ask.index("window.OpticAuth.on((state) => {")]
    assert "data-ds-bring" in ask and "data-ds-keep" in ask
    assert "if (bring && bringGuestThings()) afterSessionKept(window.OpticAuth.state());" in ask
    assert "if (keep) keepGuestThingsOut();" in ask


def test_sign_out_does_not_repaint_a_page_that_is_reloading():
    signout = RAW[RAW.index("window.OpticAuth.onSignOut = () => {"):]
    signout = signout[:signout.index("\n  };")]
    assert signout.index("if (sessionEnding) return;") < signout.index("ACCOUNT.ready = false;")


def test_deleting_the_account_hands_the_browser_to_the_guest_first():
    block = RAW[RAW.index("if (target.closest('[data-acct-delete]')) {"):]
    block = block[:block.index("\n    return;\n  }")]
    assert block.index("handDeviceSessionToGuest();") < block.index("await window.OpticAuth.refresh();")


def test_settings_says_what_signing_out_does():
    assert ("Recent symbols, Pulse chats, drawings and notes stay in this browser, kept apart "
            "for each account, and signing out puts yours away until you sign in here again.") in RAW


# ------------------------------------------------------- every key is decided

# The browser's, not the person's: how the screen looks and where things are.
SETTINGS = {
    "optic.theme", "optic.timezone", "optic.ui.scale.v1", "optic.mode.v1",
    "optic.rail.tight", "optic.rail.tight.v2", "optic.panels.open", "optic.panels.hidden.v1",
    "optic.notices.dismissed", "optic.session.desc", "optic.session.detail.v1",
    "optic.chat.width.v1", "optic.chat.width.v2",
    "optic.knowledge.v1", "optic.knowledge.asked.v1", "optic.pulse.persona.v1",
    "optic.indicators.v2", "optic.ws.panes",
    "optic.lt.mode", "optic.lt.range", "optic.lt.interval",
    "optic.chart.style.v1", "optic.chart.colors.v1", "optic.chart.mode", "optic.chart.range",
    "optic.chart.interval", "optic.chart.session", "optic.chart.hidden.v1",
    "optic.chart.legend.v1", "optic.chart.dock.v1", "optic.chart.sessions.v1",
    "optic.chart.stages.v1", "optic.chart.trends.v1", "optic.chart.earnmarks.v1",
    "optic.chart.accum.v1", "optic.chart.cloud921.v1", "optic.chart.cloud2150.v1",
    "optic.chart.zones.v2", "optic.chart.vol.v2", "optic.chart.vbp.v2", "optic.chart.sr.v2",
    "optic.chart.ma.v2", "optic.chart.ema.v2", "optic.chart.fib.v2", "optic.chart.insiders.v2",
    # Whether drawing points snap to a candle's O/H/L/C. A preference about the
    # tool, like the chart style beside it, not anything the reader made.
    "optic.chart.snap.v1",
    # Swing setups: the panel's filters, and the rule parameters a reader
    # changed. Preferences about the tool, like the chart's beside them.
    "optic.setups.view.v1", "optic.setups.params.v1",
    # A fact about this browser's authenticator, needed before anyone signs in.
    "optic.auth.passkeyMade",
    # The session machinery itself.
    "optic.session.holder.v1", "optic.session.next",
    # Where a reload from "Optic has been updated" returns to: this tab only,
    # in sessionStorage, and removed when the next load reads it.
    "optic.reload.place",
}


def _personal():
    block = RAW[RAW.index("const PERSONAL_KEYS = ["):]
    return set(re.findall(r"'(optic\.[^']+)'", block[:block.index("];")]))


def _keys_in_use():
    found = set()
    for path in ("static/app.js", "static/auth.js", "static/components/knowledge.js",
                 "static/charts.js", "static/index.html"):
        text = (ROOT / path).read_text()
        found |= set(re.findall(r"""['"](optic\.[A-Za-z0-9_.-]+)['"]""", text))
    return found


def test_every_stored_key_is_personal_or_a_setting():
    """A new store has to be put on one side or the other. Left off both, it
    would carry from one account to the next, which is the bug reported."""
    undecided = _keys_in_use() - _personal() - SETTINGS
    undecided = {k for k in undecided if not k.startswith("optic.session.shelf.")}
    assert not undecided, "decide whose these are: %s" % sorted(undecided)


def test_no_key_is_both():
    assert not (_personal() & SETTINGS)


def test_what_the_report_named_is_personal():
    personal = _personal()
    assert {"optic.recent.v1", "optic.pulse.history.v1", "optic.research.v1"} <= personal
    assert {"optic.chart.drawings.v1", "optic.paper.v1", "optic.roth.inputs"} <= personal
    # The time-anchored store holds the same drawings as the one it replaced,
    # so it is wiped on the same change of reader. Missing it here would leave
    # one person's trend lines on the next person's chart.
    assert "optic.chart.drawings.v2" in personal
