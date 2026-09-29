"""Resolving a problem report, and the page it happens on.

Asked for as "a clear button to the reports page, or a resolved button for
each report". Both, and neither deletes anything: a report is what a reader
said, so resolving takes it off the list the page opens on and keeps it, and
Reopen puts one back. Resolve all is the clear, behind a second press.

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


def test_the_page_offers_each_action_and_no_longer_shows_the_notice():
    _js(PAGE, ["reportStamp", "reportRowHTML", "reportsHTML"], """
      var html = reportsHTML({ reports: [OPEN], total: 1, open: 1, resolved: 1,
                               include_resolved: false, delivery: NOTICE });
      assert(html.indexOf('FEEDBACK_EMAIL_TO') < 0, 'the notice is still on the page');
      assert(html.indexOf('data-report-resolve="aaa"') >= 0 && html.indexOf('>Mark resolved<') >= 0,
             'no button on the report');
      assert(html.indexOf('data-reports-resolve-all>Resolve all 1<') >= 0, 'no Resolve all');
      assert(html.indexOf('Show resolved (1)') >= 0, 'no way to see the resolved one');
      assert(html.indexOf('1 open, 1 resolved.') >= 0, 'the counts');
    """)


def test_a_resolved_report_offers_reopen_and_says_when():
    _js(PAGE, ["reportStamp", "reportRowHTML", "reportsHTML"], """
      var html = reportsHTML({ reports: [OPEN, DONE], total: 2, open: 1, resolved: 1,
                               include_resolved: true, delivery: NOTICE });
      assert(html.indexOf('data-report-resolve="bbb"') >= 0, 'no button on the resolved one');
      assert(/data-report-resolve="bbb"\\s+data-report-to="open"/.test(html), 'it would resolve it again');
      assert(html.indexOf('>Reopen<') >= 0 && html.indexOf('class="rp-item-resolved">Resolved ') >= 0,
             'reopen, and when');
      assert(html.indexOf('Hide resolved') >= 0, 'no way back to the open list');
    """)


def test_nothing_open_but_some_resolved_says_so_rather_than_no_reports_yet():
    _js(PAGE, ["reportStamp", "reportRowHTML", "reportsHTML"], """
      var html = reportsHTML({ reports: [], total: 0, open: 0, resolved: 3, include_resolved: false });
      assert(html.indexOf('<empty>') < 0, 'said there were no reports when three are kept');
      assert(html.indexOf('Nothing open. 3 resolved reports are kept') >= 0, html);
      assert(html.indexOf('Show resolved (3)') >= 0, 'no way to reach them');
      assert(reportsHTML({ reports: [], open: 0, resolved: 0 }).indexOf('No problem reports yet') >= 0);
    """)


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
                     ("data-reports-toggle-resolved", "STATE.reportsShowResolved")):
        assert "closest('[%s]')" % attr in listener and fn in listener, attr
