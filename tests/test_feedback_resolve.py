"""Resolving a problem report, and the page it happens on.

Asked for as "a clear button to the reports page, or a resolved button for
each report". Both, and neither deletes anything: a report is what a reader
said, so resolving takes it off the list the page opens on and keeps it, and
Reopen puts one back. Resolve all is the clear, behind a second press.

Then asked for as "two different tabs here, one for open and one for resolved
report tickets", in place of the Show resolved toggle. A tab each, each with
its count, and each its own list from the server (`status=open|resolved`), so
fifty open reports cannot push the resolved ones past the page's limit.

Also asked: the line "No FEEDBACK_EMAIL_TO is set, so reports are stored on
the server and not emailed." is gone from the page. The endpoint still carries
`delivery` for anyone reading it directly, and each report still says whether
it was emailed or stored.
"""
from __future__ import annotations

import os
import re
import shutil
import sqlite3
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import app.main as main
from app import db as accounts_db
from app import feedback as fb

client = TestClient(main.app)
TOKEN = {"X-Optic-Token": "test-write-token"}
ROOT = Path(__file__).resolve().parent.parent
RAW = (ROOT / "static/app.js").read_text()
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc"


@pytest.fixture
def token(monkeypatch):
    monkeypatch.setattr(main, "WRITE_TOKEN", "test-write-token")


def _count():
    with accounts_db.cursor() as conn:
        return conn.execute("SELECT COUNT(*) AS n FROM feedback").fetchone()["n"]


# ------------------------------------------------------------ the store


def test_a_resolved_report_leaves_the_list_and_is_kept(accounts):
    a = fb.store("first")
    fb.store("second")
    assert fb.resolve(a["id"])["resolved_at"]
    out = fb.log()
    assert [r["message"] for r in out["reports"]] == ["second"]
    assert (out["open"], out["resolved"], out["total"]) == (1, 1, 1)
    assert _count() == 2, "resolving deleted a report"
    every = fb.log(include_resolved=True)
    assert {r["message"] for r in every["reports"]} == {"first", "second"}
    assert every["total"] == 2


def _stamp(report_id, when):
    with accounts_db.cursor(write=True) as conn:
        conn.execute("UPDATE feedback SET resolved_at = ? WHERE id = ?", (when, report_id))


def test_the_resolved_list_is_resolved_reports_most_recently_resolved_first(accounts):
    a = fb.store("filed first, resolved last")
    b = fb.store("still open")
    c = fb.store("filed last, resolved first")
    _stamp(c["id"], "2026-09-29T10:00:00+00:00")
    _stamp(a["id"], "2026-09-29T11:00:00+00:00")
    out = fb.log(status="resolved")
    assert [r["message"] for r in out["reports"]] == [
        "filed first, resolved last", "filed last, resolved first"]
    assert (out["status"], out["total"], out["open"], out["resolved"]) == ("resolved", 2, 1, 2)
    assert out["include_resolved"] is False
    opened = fb.log(status="open")
    assert [r["id"] for r in opened["reports"]] == [b["id"]] and opened["total"] == 1


def test_reports_resolved_together_fall_back_to_newest_filed_first(accounts):
    for i in range(3):
        fb.store("report %d" % i)
    fb.resolve_open()
    assert [r["message"] for r in fb.log(status="resolved")["reports"]] == [
        "report 2", "report 1", "report 0"]


def test_open_is_the_default_and_include_resolved_still_means_all(accounts):
    a = fb.store("first")
    fb.store("second")
    fb.resolve(a["id"])
    assert fb.log()["status"] == "open"
    every = fb.log(include_resolved=True)
    assert every["status"] == "all" and every["include_resolved"] is True and every["total"] == 2
    assert fb.log(status="all")["reports"] == every["reports"]
    assert fb.log(status="nonsense")["status"] == "open"


def test_reopening_puts_it_back(accounts):
    a = fb.store("first")
    fb.resolve(a["id"])
    assert fb.resolve(a["id"], resolved=False) == {"id": a["id"], "resolved_at": None}
    assert [r["message"] for r in fb.log()["reports"]] == ["first"]


def test_an_unknown_report_is_none(accounts):
    assert fb.resolve("0" * 32) is None


def test_resolve_all_resolves_the_open_ones_and_leaves_the_rest_as_they_were(accounts):
    done = fb.store("already done")
    stamp = fb.resolve(done["id"])["resolved_at"]
    for i in range(3):
        fb.store("open %d" % i)
    out = fb.resolve_open()
    assert out["resolved"] == 3
    assert fb.log()["reports"] == []
    kept = {r["message"]: r["resolved_at"] for r in fb.log(include_resolved=True)["reports"]}
    assert kept["already done"] == stamp, "an earlier resolution was overwritten"
    assert _count() == 4
    assert fb.resolve_open() == {"resolved": 0, "resolved_at": None}


def test_an_existing_database_gains_the_column_with_every_report_open(tmp_path, monkeypatch):
    # The live accounts database is at migration 6 with reports in it.
    monkeypatch.setattr(accounts_db, "DB_PATH", str(tmp_path / "accounts.db"))
    before = [m for m in accounts_db.MIGRATIONS if m[0] <= 6]
    monkeypatch.setattr(accounts_db, "MIGRATIONS", before)
    accounts_db.migrate()
    fb.store("filed before this shipped")
    monkeypatch.undo()
    monkeypatch.setattr(accounts_db, "DB_PATH", str(tmp_path / "accounts.db"))
    assert 7 in accounts_db.migrate()
    assert [r["message"] for r in fb.log()["reports"]] == ["filed before this shipped"]


# ------------------------------------------------------------ the routes


def test_the_routes_resolve_and_reopen(accounts, token):
    a = fb.store("first")
    res = client.post("/api/feedback/%s/resolve" % a["id"], json={"resolved": True}, headers=TOKEN)
    assert res.status_code == 200 and res.json()["resolved_at"]
    assert client.get("/api/feedback", headers=TOKEN).json()["reports"] == []
    listed = client.get("/api/feedback?resolved=true", headers=TOKEN).json()
    assert [r["message"] for r in listed["reports"]] == ["first"]
    res = client.post("/api/feedback/%s/resolve" % a["id"], json={"resolved": False}, headers=TOKEN)
    assert res.json()["resolved_at"] is None


def test_the_route_serves_each_tab_its_own_list(accounts, token):
    a = fb.store("done")
    fb.store("open")
    fb.resolve(a["id"])
    resolved = client.get("/api/feedback?status=resolved", headers=TOKEN).json()
    assert [r["message"] for r in resolved["reports"]] == ["done"]
    assert resolved["status"] == "resolved" and (resolved["open"], resolved["resolved"]) == (1, 1)
    opened = client.get("/api/feedback?status=open", headers=TOKEN).json()
    assert [r["message"] for r in opened["reports"]] == ["open"]


def test_a_bad_status_is_refused_but_only_after_the_guard(accounts, token):
    assert client.get("/api/feedback?status=closed", headers=TOKEN).status_code == 400
    assert client.get("/api/feedback?status=closed").status_code == 401


def test_resolve_all_route(accounts, token):
    for i in range(2):
        fb.store("open %d" % i)
    assert client.post("/api/feedback/resolve-all", headers=TOKEN).json()["resolved"] == 2


def test_nobody_else_may_resolve(accounts, token):
    a = fb.store("a reader's words")
    for headers in ({}, {"X-Optic-Token": "wrong"}):
        assert client.post("/api/feedback/%s/resolve" % a["id"], json={},
                           headers=headers).status_code == 401
        assert client.post("/api/feedback/resolve-all", headers=headers).status_code == 401
    assert fb.log()["open"] == 1


def test_an_unknown_report_or_a_bad_value_is_refused(accounts, token):
    assert client.post("/api/feedback/%s/resolve" % ("0" * 32), json={},
                       headers=TOKEN).status_code == 404
    a = fb.store("first")
    assert client.post("/api/feedback/%s/resolve" % a["id"], json={"resolved": "yes"},
                       headers=TOKEN).status_code == 400


# ------------------------------------------------------------ the page


def _raw_fn(name):
    return re.search(r"^(?:async )?function " + name + r"\([^\n]*\) \{.*?^\}",
                     RAW, re.M | re.S).group()


def _js(prelude, names, scenario):
    exe = JSC if os.path.exists(JSC) else shutil.which("jsc")
    if not exe:
        pytest.skip("no JavaScriptCore on this machine")
    src = ("function assert(v, m) { if (!v) throw new Error(m); }\n" + prelude + "\n"
           + "\n".join(_raw_fn(n) for n in names)
           + "\n(async function () {\n" + scenario + "\n})().then(function () { print('TEST_OK'); },"
           " function (e) { print('FAIL ' + e + '\\n' + e.stack); });")
    out = subprocess.run([exe, "-e", src], capture_output=True, text=True, timeout=30)
    assert "TEST_OK" in out.stdout, out.stdout + out.stderr


PAGE = r"""
function esc(s) { return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/"/g, '&quot;'); }
function emptyHTML(t, b) { return '<empty>' + t + ' | ' + b + '</empty>'; }
var OPEN = { id: 'aaa', message: 'chart froze', emailed: 0, created_at: '2026-09-28T10:00:00Z', resolved_at: null };
var DONE = { id: 'bbb', message: 'typo', emailed: 0, created_at: '2026-09-27T10:00:00Z', resolved_at: '2026-09-28T11:00:00Z' };
var NOTICE = { available: false, reason: 'No FEEDBACK_EMAIL_TO is set, so reports are stored on the server and not emailed.' };
"""
# The tabs as the page defines them, not a copy that could drift from it.
PAGE += re.search(r"^const REPORT_TABS = \[.*?^\];", RAW, re.M | re.S).group() + "\n"


def test_the_open_tab_offers_each_action_and_both_counts():
    _js(PAGE, ["reportStamp", "reportRowHTML", "reportsTabsHTML", "reportsHTML"], """
      var html = reportsHTML({ reports: [OPEN], total: 1, open: 1, resolved: 1,
                               status: 'open', delivery: NOTICE });
      assert(html.indexOf('FEEDBACK_EMAIL_TO') < 0, 'the notice is back on the page');
      assert(html.indexOf('data-report-resolve="aaa"') >= 0 && html.indexOf('>Mark resolved<') >= 0,
             'no button on the report');
      assert(html.indexOf('data-reports-resolve-all>Resolve all 1<') >= 0, 'no Resolve all');
      assert(/data-reports-tab="open" aria-selected="true"[\\s\\S]*?>Open <span\\s+class="rp-tab-n">1</.test(html),
             'the Open tab, selected, with its count');
      assert(/data-reports-tab="resolved" aria-selected="false"[\\s\\S]*?>Resolved <span\\s+class="rp-tab-n">1</.test(html),
             'the Resolved tab, with its count');
      assert(html.indexOf('role="tabpanel"') >= 0 && html.indexOf('aria-labelledby="rp-tab-open"') >= 0,
             'the list is not in the Open panel');
      assert(html.indexOf('Show resolved') < 0 && html.indexOf('data-reports-toggle-resolved') < 0,
             'the old toggle is still there');
    """)


def test_the_resolved_tab_lists_them_with_reopen_and_when():
    _js(PAGE, ["reportStamp", "reportRowHTML", "reportsTabsHTML", "reportsHTML"], """
      var html = reportsHTML({ reports: [DONE], total: 1, open: 1, resolved: 1,
                               status: 'resolved', delivery: NOTICE });
      assert(html.indexOf('data-report-resolve="bbb"') >= 0, 'no button on the resolved one');
      assert(/data-report-resolve="bbb"\\s+data-report-to="open"/.test(html), 'it would resolve it again');
      assert(html.indexOf('>Reopen<') >= 0 && html.indexOf('class="rp-item-resolved">Resolved ') >= 0,
             'reopen, and when');
      assert(/data-reports-tab="resolved" aria-selected="true"/.test(html), 'the Resolved tab is not selected');
      assert(html.indexOf('data-reports-resolve-all') < 0, 'Resolve all has nothing to do here');
      assert(html.indexOf('aria-labelledby="rp-tab-resolved"') >= 0);
    """)


def test_an_empty_tab_says_so_in_its_own_words():
    _js(PAGE, ["reportStamp", "reportRowHTML", "reportsTabsHTML", "reportsHTML"], """
      var html = reportsHTML({ reports: [], total: 0, open: 0, resolved: 3, status: 'open' });
      assert(html.indexOf('<empty>') < 0, 'said there were no reports when three are kept');
      assert(html.indexOf('>Nothing open.<') >= 0, html);
      assert(/>Resolved <span\\s+class="rp-tab-n">3</.test(html), 'no way to see there are three');
      var none = reportsHTML({ reports: [], total: 0, open: 2, resolved: 0, status: 'resolved' });
      assert(none.indexOf('>Nothing resolved yet.<') >= 0, none);
      assert(reportsHTML({ reports: [], open: 0, resolved: 0 }).indexOf('No problem reports yet') >= 0);
    """)


def test_a_page_of_a_longer_list_says_which_part_it_is():
    _js(PAGE, ["reportStamp", "reportRowHTML", "reportsTabsHTML", "reportsHTML"], """
      var open = reportsHTML({ reports: [OPEN], total: 60, open: 60, resolved: 0, status: 'open' });
      assert(open.indexOf('Showing the newest 1 of 60.') >= 0, open);
      var done = reportsHTML({ reports: [DONE], total: 70, open: 0, resolved: 70, status: 'resolved' });
      assert(done.indexOf('Showing the 1 most recently resolved of 70.') >= 0, done);
    """)


def test_the_fetch_asks_for_one_tabs_list():
    _js("""
      var urls = [];
      var RETRY_DELAYS_MS = [];
      var window = { OpticAuth: { csrf: function () { return 'c'; } } };
      function fetch(url) { urls.push(url); return Promise.resolve({ ok: true, json: function () { return Promise.resolve({}); } }); }
    """, ["fetchReports"], """
      await fetchReports(50, 'resolved');
      await fetchReports(50);
      assert(urls[0] === '/api/feedback?limit=50&status=resolved', urls[0]);
      assert(urls[1] === '/api/feedback?limit=50', urls[1]);
    """)


LOAD = r"""
var STATE = { view: 'reports', reportsTab: 'open', reportsLoaded: true };
function isOwner() { return true; }
function reportsHTML(data) { return 'drawn:' + data.status; }
function reportsForOwnerHTML() { return 'not yours'; }
function errorHTML(m) { return 'error:' + m; }
function emptyHTML(t) { return 'empty:' + t; }
var drawnPanel = { id: 'rp-tabpanel' };
var views = { reports: { innerHTML: 'the page with its tabs',
  querySelector: function (sel) { return sel === '#rp-tabpanel' ? drawnPanel : null; } } };
var pending = [];
var reportsSeq = 0;   // module state beside loadReports
function fetchReports(limit, status) {
  var d = {};
  d.promise = new Promise(function (resolve) { d.resolve = function () { resolve({ status: status }); }; });
  d.status = status;
  pending.push(d);
  return d.promise;
}
"""


def test_quick_presses_end_on_the_last_tab_pressed():
    """Open, Resolved and Open again, faster than the server answers: the
    Resolved answer arriving last must not be the list left on screen."""
    _js(LOAD, ["loadReports"], """
      STATE.reportsTab = 'resolved'; var first = loadReports(true, { inPlace: true });
      STATE.reportsTab = 'open';     var second = loadReports(true, { inPlace: true });
      assert(pending[0].status === 'resolved' && pending[1].status === 'open', 'asked for each tab');
      assert(views.reports.innerHTML === 'the page with its tabs', 'in place: the page was blanked');
      pending[1].resolve(); await second;
      pending[0].resolve(); await first;
      assert(views.reports.innerHTML === 'drawn:open', views.reports.innerHTML);
    """)


def test_the_first_load_still_says_it_is_loading():
    _js(LOAD, ["loadReports"], """
      views.reports.querySelector = function () { return null; };   // nothing drawn yet
      var done = loadReports(true, { inPlace: true });
      assert(/Loading\\./.test(views.reports.innerHTML), views.reports.innerHTML);
      pending[0].resolve(); await done;
      assert(views.reports.innerHTML === 'drawn:open');
    """)


def test_the_tabs_move_with_the_arrow_keys():
    listener = RAW[RAW.index("closest('[data-reports-tab]') : null;"):][:500]
    assert "ArrowRight: at + 1, ArrowLeft: at - 1, Home: 0, End: ids.length - 1" in listener
    assert "evt.preventDefault();" in listener and "showReportsTab(" in listener
    fn = _raw_fn("showReportsTab")
    assert "btn.tabIndex = on ? 0 : -1;" in fn and "setAttribute('aria-selected'" in fn
    assert "loadReports(true, { inPlace: true })" in fn


ACTIONS = r"""
var posted = [], reloaded = 0, focused = null, toasts = [];
var reportsConfirmTimer = null;   // module state beside resolveAllReports
function postJSON(url, body) { posted.push([url, body]); return Promise.resolve({}); }
async function loadReports() { reloaded += 1; }
function refocusReports(at) { focused = at; }
function reportsToast(err) { toasts.push(err.message); }
function setTimeout(fn) { return 1; }
function clearTimeout() {}
function mkBtn(attrs) {
  return { dataset: attrs, disabled: false, textContent: 'Resolve all 3', isConnected: true };
}
var views = { reports: { querySelectorAll: function () { return [btnA, btnB]; } } };
var btnA = mkBtn({ reportResolve: 'aaa', reportTo: 'resolved' });
var btnB = mkBtn({ reportResolve: 'bbb', reportTo: 'open' });
"""


def test_a_report_button_posts_its_own_id_and_direction_then_redraws():
    _js(ACTIONS, ["resolveReport"], """
      await resolveReport(btnB);
      assert(posted.length === 1 && posted[0][0] === '/api/feedback/bbb/resolve', posted[0] && posted[0][0]);
      assert(posted[0][1].resolved === false, 'Reopen resolved it');
      assert(reloaded === 1 && focused === 1, 'redrawn with focus kept in place');
      await resolveReport(btnA);
      assert(posted[1][1].resolved === true);
    """)


def test_a_failure_is_said_and_the_button_comes_back():
    _js(ACTIONS.replace("return Promise.resolve({});", "return Promise.reject(new Error('HTTP 503'));"),
        ["resolveReport"], """
      await resolveReport(btnA);
      assert(toasts.length === 1 && toasts[0] === 'HTTP 503', 'said nothing');
      assert(btnA.disabled === false, 'left the button dead');
      assert(reloaded === 0);
    """)


def test_resolve_all_needs_a_second_press():
    _js(ACTIONS, ["resolveAllReports"], """
      var btn = mkBtn({});
      await resolveAllReports(btn);
      assert(posted.length === 0, 'resolved everything on one press');
      assert(/Press again to confirm/.test(btn.textContent), btn.textContent);
      await resolveAllReports(btn);
      assert(posted.length === 1 && posted[0][0] === '/api/feedback/resolve-all', 'the second press did nothing');
      assert(reloaded === 1);
    """)


def test_every_new_control_has_its_handler():
    listener = RAW[RAW.index("const reportBtn = evt.target.closest('[data-report-resolve]');"):][:600]
    for attr, fn in (("data-report-resolve", "resolveReport("),
                     ("data-reports-resolve-all", "resolveAllReports("),
                     ("data-reports-tab", "showReportsTab(")):
        assert "closest('[%s]')" % attr in listener and fn in listener, attr
