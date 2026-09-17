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

import re

import pytest

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
