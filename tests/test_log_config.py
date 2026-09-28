"""Anything this application logs has to actually come out.

The defect was silent by construction. `logging.basicConfig` exists in exactly
one place in the tree, inside `app/db.py`'s `if __name__ == "__main__"` block,
which uvicorn never reaches. Uvicorn configures its own three loggers and
leaves the root alone, so every `log.info` in this package propagated to a root
logger with no handler at the default WARNING and was dropped.

What that cost is not hypothetical. `app/auth/mailer.py` falls back to writing
a verification link to the log when no relay is configured, and the UI says so
to the reader: "Email is not configured on this deployment, so the link went to
the server log." DEPLOY.md and CLAUDE.md repeat the promise. The line was never
emitted -- so on a deployment with no SMTP an address could not be confirmed by
any route at all, and `ADMIN_EMAILS` could never take effect either, because
`is_admin` requires a *verified* address. Reported as "it does not recognize
the domain email".

Measured before the fix, on a local server with `--log-level info`: registering
an account produced zero `[mail:log]` lines.
"""
from __future__ import annotations

import logging

import pytest

import app.main  # noqa: F401  -- imported for its logging configuration
from app.auth import mailer

# The two trees this codebase actually uses. `uvicorn.error` is the third and
# needs nothing: it is uvicorn's own and has always been visible, which is
# what hid this for so long -- warm-up lines appeared, so the log looked fine.
OURS = ("app", "optic")


@pytest.mark.parametrize("name", OURS)
def test_our_loggers_have_somewhere_to_write(name):
    assert logging.getLogger(name).handlers, \
        "{} logs go nowhere: no handler, and root has none either".format(name)


@pytest.mark.parametrize("name", OURS)
def test_our_loggers_pass_info(name):
    """WARNING is the default and it is one step too coarse: the mailer's
    fallback is an `info`, and so is the feedback backlog's report."""
    assert logging.getLogger(name).getEffectiveLevel() <= logging.INFO


def test_the_mailers_own_logger_is_covered():
    """The specific one the first version of this fix missed. Modules here name
    loggers three ways, and the mailer does not use `__name__` -- it is
    `optic.mail`, so scoping the fix to the package tree left exactly the line
    it was written to rescue still invisible."""
    assert mailer.log.name == "optic.mail"
    assert mailer.log.getEffectiveLevel() <= logging.INFO


def test_a_link_with_no_relay_actually_reaches_the_log(monkeypatch):
    """The behaviour, not the wiring. Without a relay `send` returns False and
    writes the link instead; a caller who believed the return value and never
    checked the log is how this stayed hidden."""
    monkeypatch.setattr(mailer, "SMTP_HOST", "")
    records = []

    class Capture(logging.Handler):
        def emit(self, record):
            records.append(record.getMessage())

    handler = Capture()
    mailer.log.addHandler(handler)
    try:
        sent = mailer.send("reader@example.test", "Verify your email",
                           "body", "https://example.test/?verify=TOKEN")
    finally:
        mailer.log.removeHandler(handler)

    assert sent is False, "no relay, so nothing was sent"
    joined = "\n".join(records)
    assert "[mail:log]" in joined
    assert "https://example.test/?verify=TOKEN" in joined, \
        "the link is the only part anyone needs from the log"


def test_the_handler_is_not_attached_twice():
    """`app.main` is imported once per process, so counting handlers after a
    normal import proves nothing -- that was the first version of this test and
    it survived its mutation. The module body has to run a second time to
    exercise the guard, which is what uvicorn's `--reload` does.

    In a subprocess, because `importlib.reload` on this module rebuilds the
    FastAPI app and the module-level singletons around it: done in-process it
    took eleven unrelated tests down with it, which is a worse bug than the one
    being tested for.

    A second handler prints every line twice, which is how a log stops being
    read.
    """
    import subprocess
    import sys as _sys

    probe = (
        "import importlib, logging, app.main;"
        "names = ('app', 'optic');"
        "before = [len(logging.getLogger(n).handlers) for n in names];"
        "importlib.reload(app.main);"
        "after = [len(logging.getLogger(n).handlers) for n in names];"
        "print(before, after)"
    )
    out = subprocess.run([_sys.executable, "-c", probe],
                         capture_output=True, text=True, timeout=180)
    assert out.returncode == 0, out.stderr[-2000:]
    before, after = out.stdout.strip().splitlines()[-1].split("] [")
    assert before.strip("[ ") == after.strip("] "), \
        "re-running the module added handlers: {}".format(out.stdout.strip())
