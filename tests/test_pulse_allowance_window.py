"""Pulse's allowance says when the next message comes back.

The window rolls: each message comes back 24 hours after it was sent. The note
above the box said "left today", which has a midnight the allowance does not,
and a reader who had spent it all learned when it returns only from the 429
after trying again ("The allowance resets 24 hours after each message").
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app import db
from app.auth import ratelimit

ROOT = Path(__file__).resolve().parent.parent
APP = (ROOT / "static/app.js").read_text()
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc"


def _stamp(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def test_next_at_is_when_the_oldest_use_leaves_the_window():
    db.migrate()
    bucket = "k:allowance-window-test-%s" % os.getpid()
    db.execute("DELETE FROM auth_attempts WHERE bucket = ?", (ratelimit._bucket(bucket),))
    assert ratelimit.allowance("ai_day", bucket, 3, 86400)["next_at"] is None, "nothing used"
    now = datetime.now(timezone.utc).replace(microsecond=0)
    for hours_ago in (5, 2):
        db.execute("INSERT INTO auth_attempts (id,bucket,kind,created_at) VALUES (?,?,?,?)",
                   (db.new_id(), ratelimit._bucket(bucket), "ai_day",
                    _stamp(now - timedelta(hours=hours_ago))))
    state = ratelimit.allowance("ai_day", bucket, 3, 86400)
    assert state["used"] == 2 and state["left"] == 1
    assert state["next_at"] == _stamp(now - timedelta(hours=5) + timedelta(days=1))


def _fn(name):
    return re.search(r"^function " + name + r"\([^\n]*\) \{.*?^\}", APP, re.M | re.S).group()


def _note(state):
    exe = JSC if os.path.exists(JSC) else shutil.which("jsc")
    if not exe:
        pytest.skip("no JavaScriptCore on this machine")
    src = "\n".join([
        "var host = { id: 'chat-allow', innerHTML: '', classList: { toggle: function () {} } };",
        "function $(s) { return s === '#chat-allow' ? host : null; }",
        "var ACCOUNT = { allowance: %s };" % json.dumps(state),
        "function esc(v) { return String(v); }",
        "function cap(v) { return v ? v[0].toUpperCase() + v.slice(1) : v; }",
        "function activeZone() { return 'America/New_York'; }",
        "function timeIn(iso, zone) { return 'TIME(' + iso + ')'; }",
        _fn("renderAllowanceNote"),
        "renderAllowanceNote(); print(host.innerHTML.replace(/\\s+/g, ' '));",
    ])
    return subprocess.run([exe, "-e", src], capture_output=True, text=True, timeout=30).stdout


def test_a_spent_account_is_told_when_the_next_message_is_back():
    # Twenty-four hours on is always another date, in any zone.
    back = _stamp(datetime.now(timezone.utc) + timedelta(days=1))
    out = _note({"scope": "account", "allowed": 3, "used": 3, "left": 0, "plan": "free",
                 "plan_label": "Free", "next_at": back})
    assert "All 3 of the Free plan's messages are used." in out, out
    assert "The next one is back at TIME(%s) tomorrow." % back in out, out
    assert "today" not in out


def test_one_left_says_the_window_rather_than_a_day():
    out = _note({"scope": "account", "allowed": 3, "used": 2, "left": 1, "plan": "free",
                 "plan_label": "Free", "next_at": "2026-10-08T12:00:00Z"})
    assert "1 of 3 messages left in the last 24 hours on the Free plan." in out, out
    assert "free plan" not in out, "the plan by its id"
