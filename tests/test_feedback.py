"""Reader-reported problems.

The defect this replaced was not a bug in the code, it was the code working as
designed: the "Report an issue" button opened a prefilled GitHub issue, so a
reader who had just watched a chart draw the wrong average had to hold a GitHub
account and sign in to it before they could say so.

The argument recorded for that design was that there was no mail sender in this
build and that a feedback table would be an unauthenticated free-text write with
no rate limiting. The first half was wrong: `app/auth/mailer.py` has sent the
verification and reset mail all along. The second half was real, and these tests
hold the answers to it: a length cap, ten reports an hour, and a row no reader
can read back.
"""
from __future__ import annotations

import asyncio
import re

import pytest
from fastapi.testclient import TestClient

import app.main as main
from app import feedback as fb
from app.auth import mailer, ratelimit

APP_JS = open("static/app.js").read()
INDEX = open("static/index.html").read()
CSS = open("static/styles.css").read()
MAIN = open("app/main.py").read()


def _code(text: str) -> str:
    """Comments stripped. A comment recording a removal names the thing removed,
    which is how a naive search finds `REPORT_REPO` in the paragraph explaining
    that it is gone."""
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.S)
    return re.sub(r"^\s*//.*$", " ", text, flags=re.M)


# --------------------------------------------------------------- storage


def test_an_empty_report_is_not_stored(accounts):
    assert fb.store("") is None
    assert fb.store("   \n  ") is None
    assert fb.unsent() == []


def test_a_report_is_stored_with_its_context(accounts):
    row = fb.store("The weekly average is cut off.", page="view-long",
                   reply_to="reader@example.com", user_agent="Mozilla/5.0")
    assert row is not None
    kept = fb.unsent()
    assert len(kept) == 1
    assert kept[0]["message"] == "The weekly average is cut off."
    assert kept[0]["page"] == "view-long"
    assert kept[0]["reply_to"] == "reader@example.com"
    assert kept[0]["user_agent"] == "Mozilla/5.0"


@pytest.mark.parametrize("field,limit", [
    ("message", fb.MAX_MESSAGE), ("page", fb.MAX_PAGE),
    ("reply_to", fb.MAX_REPLY_TO), ("user_agent", fb.MAX_USER_AGENT),
])
def test_every_field_is_clipped_rather_than_rejected(accounts, field, limit):
    """A report with an odd User-Agent is still a report. Failing the whole
    submission over a context field would lose the part that matters."""
    kwargs = {"message": "real problem", "page": "p", "reply_to": "r",
              "user_agent": "u"}
    kwargs[field] = "x" * (limit + 500)
    row = fb.store(**kwargs)
    assert row is not None
    assert len(fb.unsent()[0][field]) == limit


# ------------------------------------------------------------ configuration


def test_no_address_is_reported_as_not_configured(accounts, monkeypatch):
    monkeypatch.setattr(fb, "FEEDBACK_TO", "")
    status = fb.configured()
    assert status["available"] is False
    assert "FEEDBACK_EMAIL_TO" in status["reason"]


def test_an_address_with_no_mail_backend_reports_the_mailer_reason(accounts, monkeypatch):
    """Two independent reasons with two different fixes, so they are reported
    separately rather than collapsed into "not configured"."""
    monkeypatch.setattr(fb, "FEEDBACK_TO", "owner@example.com")
    monkeypatch.setattr(mailer, "available",
                        lambda: {"available": False, "backend": "log",
                                 "reason": "No SMTP_HOST is set."})
    status = fb.configured()
    assert status["available"] is False
    assert "SMTP_HOST" in status["reason"]


def test_the_destination_is_never_a_literal_in_the_source():
    """The repository is public and this is a personal address."""
    source = open("app/feedback.py").read()
    assert "os.environ.get(\"FEEDBACK_EMAIL_TO\")" in source
    assert "@gmail" not in source and "@northeastern" not in source


# ----------------------------------------------------------------- submit


def test_a_report_is_kept_even_when_it_cannot_be_sent(accounts, monkeypatch):
    """The whole point of the table. For any window where no address is set the
    choice is between losing the reports and keeping them."""
    monkeypatch.setattr(fb, "FEEDBACK_TO", "")
    out = fb.submit("Fib levels look wrong.", page="view-long")
    assert out["stored"] is True
    assert out["emailed"] is False
    assert out["reason"]
    assert len(fb.unsent()) == 1


def test_a_sent_report_is_marked_and_leaves_the_backlog(accounts, monkeypatch):
    sent = []
    monkeypatch.setattr(fb, "FEEDBACK_TO", "owner@example.com")
    monkeypatch.setattr(mailer, "available", lambda: {"available": True, "backend": "smtp"})
    monkeypatch.setattr(mailer, "send",
                        lambda to, subject, body, link=None: sent.append((to, body)) or True)
    out = fb.submit("Chart draws the wrong average.")
    assert out == {"stored": True, "emailed": True, "id": out["id"]}
    assert fb.unsent() == []
    assert sent and sent[0][0] == "owner@example.com"
    assert "Chart draws the wrong average." in sent[0][1]


def test_a_failed_send_keeps_the_row_for_the_next_batch(accounts, monkeypatch):
    monkeypatch.setattr(fb, "FEEDBACK_TO", "owner@example.com")
    monkeypatch.setattr(mailer, "available", lambda: {"available": True, "backend": "smtp"})
    monkeypatch.setattr(mailer, "send", lambda *a, **k: False)
    out = fb.submit("Relay is down.")
    assert out["stored"] is True and out["emailed"] is False
    assert len(fb.unsent()) == 1, "nothing may be lost to a send failure"


def test_an_empty_submit_reports_nothing_stored(accounts):
    out = fb.submit("   ")
    assert out["stored"] is False and out["emailed"] is False


def test_the_email_body_carries_what_makes_a_report_reproducible(accounts, monkeypatch):
    row = fb.store("Something broke.", page="view-swing",
                   reply_to="reader@example.com", user_agent="Firefox/1")
    body = fb._body(row)
    for expected in ("Something broke.", "view-swing", "reader@example.com",
                     "Firefox/1", row["id"]):
        assert expected in body


# ------------------------------------------------------------------ flush


def test_flush_sends_the_backlog_once_an_address_exists(accounts, monkeypatch):
    monkeypatch.setattr(fb, "FEEDBACK_TO", "")
    for i in range(3):
        fb.submit("report {}".format(i))
    assert len(fb.unsent()) == 3

    monkeypatch.setattr(fb, "FEEDBACK_TO", "owner@example.com")
    monkeypatch.setattr(mailer, "available", lambda: {"available": True, "backend": "smtp"})
    monkeypatch.setattr(mailer, "send", lambda *a, **k: True)
    assert fb.flush() == {"sent": 3, "pending": 0}


def test_flush_stops_on_the_first_failure(accounts, monkeypatch):
    """Rather than hammering a broken relay through the whole backlog."""
    monkeypatch.setattr(fb, "FEEDBACK_TO", "")
    for i in range(3):
        fb.submit("report {}".format(i))
    monkeypatch.setattr(fb, "FEEDBACK_TO", "owner@example.com")
    monkeypatch.setattr(mailer, "available", lambda: {"available": True, "backend": "smtp"})
    calls = []
    monkeypatch.setattr(mailer, "send",
                        lambda *a, **k: (calls.append(1), len(calls) == 1)[1])
    out = fb.flush()
    assert out["sent"] == 1 and out["pending"] == 2
    assert len(calls) == 2, "one success, one failure, then it stops"


def test_flush_without_an_address_reports_the_backlog(accounts, monkeypatch):
    monkeypatch.setattr(fb, "FEEDBACK_TO", "")
    fb.submit("held")
    out = fb.flush()
    assert out["sent"] == 0 and out["pending"] == 1 and out["reason"]


# ------------------------------------------------------------- rate limiting


def test_the_rate_limit_exists_and_is_named_for_a_reader():
    """The real objection to a free-text write, answered rather than dodged."""
    assert "feedback" in ratelimit.LIMITS
    allowed, window = ratelimit.LIMITS["feedback"]
    assert allowed == 10 and window == 3600
    assert ratelimit.FRIENDLY["feedback"] == "problem reports"


def test_the_endpoint_rate_limits_and_does_not_require_the_write_token():
    """`_write_guard` protects the terminal's own state. Putting the report
    button behind it would leave it doing nothing for every actual reader,
    which is the failure this endpoint exists to fix."""
    route = MAIN[MAIN.index('@app.post("/api/feedback")'):]
    route = route[:route.index("\n@app.")]
    # The docstring explains *why* there is no `_write_guard` here and so names
    # it. Python triple-quotes go before the search, for the same reason the JS
    # comments do: CLAUDE.md records a test that grepped for a `return` and
    # matched the word inside that branch's own comment.
    code = _code(re.sub(r'"""".*?"""|""".*?"""', " ", route, flags=re.S))
    assert 'ratelimit.guard(request, "feedback"' in code
    assert "_write_guard" not in code
    assert "request.headers.get(\"user-agent\")" in code, \
        "the agent comes from the request, not from the body"


# ----------------------------------------------------------- client wiring


def test_the_github_issue_route_is_gone():
    code = _code(APP_JS)
    assert "REPORT_REPO" not in code
    assert "reportIssueUrl" not in code
    assert "github.com" not in code.lower().replace("claude.com", ""), \
        "no reader should need a GitHub account to report a problem"


def test_the_panel_is_mounted_once_and_on_every_view():
    """Fixed chrome in index.html rather than rendered per view: the reader who
    has just hit something wrong is not going to go looking for Settings."""
    assert INDEX.count('id="rp-open"') == 1
    assert INDEX.count('id="rp-panel"') == 1
    assert "Report a Problem" in INDEX
    assert ".rp {" in CSS and "position: fixed" in CSS[CSS.index(".rp {"):]


def test_the_hidden_panel_has_its_hidden_pair():
    """CLAUDE.md: an author `display` beats the UA stylesheet's [hidden]
    whatever the specificity. `.set-pw` shipped without this pair and rendered
    its password form open on every visit to Settings."""
    assert ".rp-panel[hidden] { display: none; }" in CSS


def test_the_panel_stands_out_of_pulses_way():
    assert "body.chat-open .rp" in CSS
    assert "body.chat-full .rp" in CSS


def test_every_report_entry_point_opens_the_one_form():
    """Three entry points, one form, so they cannot drift into three."""
    code = _code(APP_JS)
    assert code.count("data-open-report") >= 2, "Settings and the footer"
    assert "if (evt.target.closest('[data-open-report]')) openReportPanel();" in code, \
        "delegated, because Settings and the footer are re-rendered"
    assert "function openReportPanel()" in code


def test_the_send_path_reports_stored_and_emailed_differently():
    """"Thanks, we got it" over a report that went nowhere is the same lie the
    mailer refuses to tell about a verification link."""
    fn = APP_JS[APP_JS.index("async function sendReport()"):]
    fn = fn[:fn.index("\nfunction installReportPanel")]
    assert "data.emailed" in fn
    assert "Sent. Thank you." in fn
    assert "Saved. It is on the server" in fn


def test_the_context_line_is_in_the_message_the_reader_can_see():
    """Rather than a hidden payload attached to something they wrote."""
    code = _code(APP_JS)
    assert "function reportContextLine()" in code
    assert "reportContextLine()" in code[code.index("async function sendReport()"):]


def test_the_panel_is_installed_at_startup():
    code = _code(APP_JS)
    assert "installReportPanel();" in code[code.index("function installFixedChrome()"):]


# ------------------------------------------------- where a report goes
#
# The defect: the POST was relative, so it followed the *build* rather than the
# product. A report filed from a laptop dev server was written to that laptop's
# SQLite and read by nobody; one filed from a tunnel preview died with the
# tunnel. Nothing looked wrong from either side. The button worked, the reader
# was thanked, and the report never left the machine.
#
# Sending to the live site from anywhere else makes that a cross-origin POST,
# and a JSON content type makes it a preflighted one, which is what the CORS
# tests below are about. The allow-list is deliberately not `*`: this endpoint
# takes anonymous text and a per-address rate limit is its only defence, so a
# wildcard would let any site on the web spend a visitor's address against that
# limit from a page the visitor thought was unrelated.

client = TestClient(main.app)


@pytest.mark.parametrize("origin", [
    "http://localhost:8000", "http://localhost:5173", "http://127.0.0.1:8000",
    "http://[::1]:8000", "https://shy-pond-1234.trycloudflare.com",
])
def test_a_build_optic_runs_on_may_post_a_report_to_the_live_site(origin):
    assert fb.cors_origin(origin) == origin


@pytest.mark.parametrize("origin", [
    "https://evil.example", "http://evil.example:8000", "",
    "null", "file://", "https://theopticterminal.com.evil.example",
])
def test_no_other_origin_may(origin):
    assert fb.cors_origin(origin) == ""


@pytest.mark.parametrize("origin", [
    # The hole an `endswith` over the raw header falls into, three ways.
    "https://evil.example/#.trycloudflare.com",
    "https://evil.example/?x=.trycloudflare.com",
    "https://evil.example/localhost",
    # Userinfo puts an arbitrary prefix in front of the real host, so a reader
    # of the string takes the wrong part of it for the host.
    "https://localhost@evil.example",
    "https://user:localhost@evil.example",
])
def test_an_origin_is_parsed_rather_than_matched_as_a_substring(origin):
    assert fb.cors_origin(origin) == ""


def test_the_live_site_is_not_granted_a_cross_origin_exception():
    """It never needs one: the client posts a relative path there, which is
    same-origin, so no allow header is consulted at all. Granting it anyway
    would widen the list for nothing."""
    for host in fb.CANONICAL_HOSTS:
        assert fb.cors_origin("https://" + host) == ""


def test_the_preflight_is_answered_for_a_build_optic_runs_on(accounts):
    """Without this OPTIONS 405s and no cross-origin report is ever sent: the
    browser never gets as far as the POST."""
    res = client.options("/api/feedback", headers={
        "Origin": "http://localhost:5173",
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "content-type",
    })
    assert res.status_code == 204
    assert res.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert "POST" in res.headers["access-control-allow-methods"]
    assert "content-type" in res.headers["access-control-allow-headers"].lower()


def test_the_preflight_refuses_a_stranger(accounts):
    res = client.options("/api/feedback", headers={
        "Origin": "https://evil.example",
        "Access-Control-Request-Method": "POST",
    })
    assert "access-control-allow-origin" not in res.headers


def test_a_cross_origin_report_is_accepted_and_stored(accounts):
    res = client.post("/api/feedback", json={"message": "The chart is blank."},
                      headers={"Origin": "http://localhost:5173"})
    assert res.status_code == 200
    assert res.json()["stored"] is True
    assert res.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert [r["message"] for r in fb.unsent()] == ["The chart is blank."]


def test_a_refused_report_still_carries_the_allow_header(accounts):
    """The subtle one, and the reason this route renders its own responses.

    An HTTPException is rendered by Starlette's own handler, which never sees
    the route's response object. Raised, a 400 or a 429 reaches a cross-origin
    caller stripped of its allow header, the browser reports an opaque CORS
    failure, and the reader is told the report did not send rather than why."""
    res = client.post("/api/feedback", json={"message": "   "},
                      headers={"Origin": "http://localhost:5173"})
    assert res.status_code == 400
    assert res.json()["detail"] == "A report needs a message."
    assert res.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_the_rate_limit_refusal_also_carries_it(accounts):
    """The same hazard on the path a reader is most likely to actually meet."""
    for i in range(10):
        client.post("/api/feedback", json={"message": "report {}".format(i)},
                    headers={"Origin": "http://localhost:5173"})
    res = client.post("/api/feedback", json={"message": "one too many"},
                      headers={"Origin": "http://localhost:5173"})
    assert res.status_code == 429
    assert res.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_the_response_varies_on_origin(accounts):
    """The body is identical for every origin but the allow header is not, and
    a cache that missed that would hand one origin a decision about another."""
    res = client.post("/api/feedback", json={"message": "vary"},
                      headers={"Origin": "https://evil.example"})
    assert res.headers["vary"] == "Origin"
    assert "access-control-allow-origin" not in res.headers


# ------------------------------------------------- reading the reports


def test_the_reports_are_readable_without_a_mail_relay(accounts, monkeypatch):
    """Emailing a report needs FEEDBACK_EMAIL_TO *and* SMTP_HOST *and*
    EMAIL_FROM. Until all three exist every report is in SQLite, and before
    this endpoint the only way to read one was a Python shell on the server."""
    monkeypatch.setattr(main, "WRITE_TOKEN", "test-write-token")
    fb.store("first problem", page="view-chart")
    fb.store("second problem", page="view-insiders")

    res = client.get("/api/feedback", headers={"X-Optic-Token": "test-write-token"})
    assert res.status_code == 200
    out = res.json()
    assert out["total"] == 2
    assert {r["message"] for r in out["reports"]} == {"first problem", "second problem"}
    assert {r["page"] for r in out["reports"]} == {"view-chart", "view-insiders"}
    # Why nothing has been emailed arrives with the reports rather than having
    # to be gone looking for.
    assert out["delivery"]["available"] is False
    assert "FEEDBACK_EMAIL_TO" in out["delivery"]["reason"]


def test_the_reports_are_not_readable_by_anybody_else(accounts, monkeypatch):
    """What this protects is other people's words. A reader filing a problem is
    writing to the operator, not to the web."""
    monkeypatch.setattr(main, "WRITE_TOKEN", "test-write-token")
    fb.store("a reader's words")
    assert client.get("/api/feedback").status_code == 401
    assert client.get("/api/feedback",
                      headers={"X-Optic-Token": "wrong"}).status_code == 401


def test_the_log_says_which_reports_went_out(accounts, monkeypatch):
    monkeypatch.setattr(fb, "FEEDBACK_TO", "operator@example.com")
    monkeypatch.setattr(mailer, "available", lambda: {"available": True})
    monkeypatch.setattr(mailer, "send", lambda *a, **k: True)
    fb.submit("emailed one")
    monkeypatch.setattr(mailer, "send", lambda *a, **k: False)
    fb.submit("stuck one")

    out = fb.log()
    assert out["total"] == 2
    by_message = {r["message"]: r["emailed"] for r in out["reports"]}
    assert by_message == {"emailed one": 1, "stuck one": 0}


def test_the_log_is_newest_first_and_is_not_the_email_backlog(accounts, monkeypatch):
    """`unsent()` drops a report the moment it is sent, which is the wrong list
    for someone trying to find out what readers have been saying."""
    monkeypatch.setattr(fb, "FEEDBACK_TO", "operator@example.com")
    monkeypatch.setattr(mailer, "available", lambda: {"available": True})
    monkeypatch.setattr(mailer, "send", lambda *a, **k: True)
    for i in range(3):
        fb.store("report {}".format(i))
    fb.flush()

    assert fb.unsent() == [], "sanity: the backlog is empty once they are sent"
    assert [r["message"] for r in fb.log()["reports"]] == \
        ["report 2", "report 1", "report 0"]


def test_the_log_limit_is_bounded(accounts):
    for i in range(5):
        fb.store("report {}".format(i))
    assert len(fb.log(limit=2)["reports"]) == 2
    assert fb.log(limit=2)["total"] == 5, "the count is of everything, not the page"


# ------------------------------------------------- client wiring, routing


def test_a_report_is_sent_to_the_live_site_from_any_other_build():
    code = _code(APP_JS)
    fn = code[code.index("function reportTargets()"):]
    fn = fn[:fn.index("\nfunction openReportPanel")]
    assert "REPORT_HOME + '/api/feedback'" in fn
    assert "https://theopticterminal.com" in _code(APP_JS[:APP_JS.index("function reportTargets()")]) \
        or "REPORT_HOME = 'https://theopticterminal.com'" in code


def test_the_live_site_posts_to_itself(accounts):
    """Relative there: same-origin, so no preflight and no dependence on the
    allow-list being right on the one build that matters most."""
    code = _code(APP_JS)
    fn = code[code.index("function reportTargets()"):]
    fn = fn[:fn.index("\nfunction openReportPanel")]
    assert "location.hostname" in fn
    assert "REPORT_HOME_HOSTS" in fn
    assert "return ['/api/feedback']" in fn
    for host in fb.CANONICAL_HOSTS:
        assert "'{}'".format(host) in code, \
            "the client and the server must agree on what the live site is"


def test_sendreport_uses_the_targets_rather_than_a_relative_path():
    """The defect was the relative path. A second one left behind in the send
    path would restore it for every reader."""
    fn = _code(APP_JS[APP_JS.index("async function sendReport()"):])
    fn = fn[:fn.index("\nfunction installReportPanel")]
    assert "reportTargets()" in fn
    assert "fetch('/api/feedback'" not in fn, "the relative path is back"


def test_a_report_that_cannot_reach_the_live_site_is_not_lost_or_called_sent():
    """Both halves matter. Falling back keeps the report; saying so keeps the
    reader from believing it arrived when it is sitting on their own machine,
    which is why the text is left in the box on that path alone."""
    fn = APP_JS[APP_JS.index("async function sendReport()"):]
    fn = fn[:fn.index("\nfunction installReportPanel")]
    code = _code(fn)
    assert "for (let i = 0; i < targets.length; i++)" in code, "no fallback loop"
    assert "is-warn" in code
    assert "Could not reach theopticterminal.com" in fn
    # `box.value = ''` must not run on the fallback branch: it is the reader's
    # only remaining copy of what they wrote.
    warn = code[code.index("is-warn"):]
    assert warn.index("return;") < warn.index("box.value = ''"), \
        "the fallback branch clears the reader's text"


def test_the_warn_state_has_a_colour():
    """A class the send path sets and the stylesheet has never heard of renders
    as unstyled body text, which reads as success."""
    assert ".rp-note.is-warn" in CSS


# ------------------------------------------------- the backlog at boot
#
# A report is stored first and emailed second, and the email is allowed to
# fail. `submit` only ever sends the report in its own hand, so any window
# where FEEDBACK_EMAIL_TO or the SMTP settings were missing leaves a backlog
# that nothing retries. Boot is the natural moment to clear it: setting those
# variables on this platform *is* a restart, so the backlog goes out as a
# consequence of configuring the thing that was missing.


def _flush_now(monkeypatch):
    """Run the startup flush without its thirty-second wait."""
    async def no_wait(_seconds):
        return None
    monkeypatch.setattr(main.asyncio, "sleep", no_wait)
    asyncio.run(main._flush_feedback())


def test_the_backlog_goes_out_at_boot(accounts, monkeypatch):
    sent = []
    monkeypatch.setattr(fb, "FEEDBACK_TO", "operator@example.com")
    monkeypatch.setattr(mailer, "available", lambda: {"available": True})
    monkeypatch.setattr(mailer, "send", lambda to, subject, body: sent.append(to) or True)
    for i in range(3):
        fb.store("filed before there was an address {}".format(i))
    assert len(fb.unsent()) == 3, "sanity: a backlog exists"

    _flush_now(monkeypatch)

    assert len(sent) == 3
    assert fb.unsent() == []


def test_boot_sends_nothing_when_there_is_still_no_address(accounts, monkeypatch):
    """The normal state of this deployment. The backlog has to survive it:
    these are the only copies of what those readers said."""
    sent = []
    monkeypatch.setattr(fb, "FEEDBACK_TO", "")
    monkeypatch.setattr(mailer, "send", lambda *a, **k: sent.append(a) or True)
    fb.store("still waiting for an address")

    _flush_now(monkeypatch)

    assert sent == []
    assert len(fb.unsent()) == 1, "the report must still be there"


def test_a_dead_relay_at_boot_does_not_take_the_terminal_down(accounts, monkeypatch):
    """Mail that cannot go out must not stop the server serving. The whole
    point of storing first is that delivery is allowed to fail."""
    monkeypatch.setattr(fb, "FEEDBACK_TO", "operator@example.com")
    monkeypatch.setattr(mailer, "available", lambda: {"available": True})

    def explode(*a, **k):
        raise OSError("connection refused")
    monkeypatch.setattr(mailer, "send", explode)
    fb.store("filed while the relay was down")

    _flush_now(monkeypatch)  # must not raise

    assert len(fb.unsent()) == 1, "kept for the next boot"


def test_the_flush_runs_off_the_event_loop():
    """`flush` opens SMTP connections. Run inline it would block every other
    request on the server for as long as the relay took to answer."""
    fn = MAIN[MAIN.index("async def _flush_feedback()"):]
    fn = fn[:fn.index("\n@app.on_event")]
    code = re.sub(r'""".*?"""', " ", fn, flags=re.S)
    assert "_run(feedback_mod.flush)" in code
    assert "feedback_mod.flush()" not in code, "called inline, not off the loop"


def test_boot_does_not_count_the_backlog_when_there_is_no_address(accounts, monkeypatch):
    """Unconfigured is the normal state, and `flush` would otherwise read the
    table on every boot to report a number that goes nowhere."""
    calls = []
    monkeypatch.setattr(fb, "FEEDBACK_TO", "")
    monkeypatch.setattr(fb, "flush", lambda *a, **k: calls.append(a) or {"sent": 0})

    _flush_now(monkeypatch)

    assert calls == [], "flush was called despite there being no address"


def test_the_flush_is_started_at_boot_and_held(accounts):
    """A bare create_task is garbage-collected mid-flight: asyncio keeps only a
    weak reference to it. The warm-up task is held on app.state for exactly
    this reason and this one sleeps fifteen times longer."""
    fn = MAIN[MAIN.index("async def _start_tracker()"):]
    fn = fn[:fn.index("\n@app.on_event(\"shutdown\")")]
    assert "app.state.feedback_task = asyncio.create_task(_flush_feedback())" in fn


def test_the_flush_is_cancelled_at_shutdown(accounts):
    """It sleeps thirty seconds. Left running, it keeps the loop alive past the
    stop and logs a "task was destroyed but it is pending" on the way out."""
    fn = MAIN[MAIN.index("async def _stop_tracker()"):]
    fn = fn[:fn.index("\n\n\n")]
    assert "feedback_task" in fn


def test_the_manual_flush_instruction_is_not_left_behind(accounts):
    """.env.example told the operator to run `feedback.flush()` by hand once
    the address was set. Boot does it now, and an instruction that describes
    the old behaviour is worse than none: it is followed."""
    env = open(".env.example").read()
    assert "python -c" not in env or "feedback; print(feedback.flush())" not in env


def test_a_refused_read_is_not_told_it_tried_to_write(accounts, monkeypatch):
    """`_write_guard` phrases every refusal as being about changing the ledger,
    because until this route existed every caller it turned away was. Shipped
    unchanged, a reader asking for the reports on a deployment with no token
    was told "Writes are disabled... it refuses to let anonymous callers change
    the ledger", and went looking for a write they never made."""
    # No token and no admin: the fail-closed branch a fresh deployment hits.
    monkeypatch.setattr(main, "WRITE_TOKEN", "")
    monkeypatch.setattr(main, "is_hosted", lambda: True)
    res = client.get("/api/feedback")
    assert res.status_code == 503
    detail = res.json()["detail"]
    assert "OPTIC_WRITE_TOKEN" in detail, "it still has to say what to set"
    assert "write" not in detail.lower().replace("optic_write_token", ""), \
        "the reader asked to read"
    assert "ledger" not in detail.lower()


def test_a_refused_read_still_says_what_would_let_it_through(accounts, monkeypatch):
    monkeypatch.setattr(main, "WRITE_TOKEN", "test-write-token")
    res = client.get("/api/feedback", headers={"X-Optic-Token": "wrong"})
    assert res.status_code == 401
    assert "write token" in res.json()["detail"].lower()


def test_the_read_copy_does_not_change_the_guards_verdict(accounts, monkeypatch):
    """Only the wording is this route's. Rewriting a status as well would make
    two answers to "is this the operator" that could drift apart."""
    monkeypatch.setattr(main, "WRITE_TOKEN", "test-write-token")
    fb.store("a reader's words")
    assert client.get("/api/feedback").status_code == 401
    ok = client.get("/api/feedback", headers={"X-Optic-Token": "test-write-token"})
    assert ok.status_code == 200 and ok.json()["total"] == 1
