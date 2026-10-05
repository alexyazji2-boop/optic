"""An extended-hours print is only shown for the session it belongs to.

Reported on a Sunday night: COIN's page read "AFTER HOURS 183.24 +0.13% vs the
close" under a session strip reading OVERNIGHT, and the status strip's top line
said "after hrs 183.24 +0.13%". Both were Friday 19:59 ET, rendered 73 hours
later as if they were happening.

Nothing was stale. `TTL_QUOTE` is 30 seconds and the quote had just been
fetched; the payload carried `post_market_time: 2026-10-02T23:59:50Z` and
`as_of: 2026-10-05T01:19:52Z` together. The newest print this feed holds for a
single stock *is* Friday's, because it carries no overnight tape -- the session
description already said so. The server published the timestamp and the client
never read it: measured, zero occurrences of `post_market_time` in app.js.

**Executed, not grepped.** The rule is a date comparison across a timezone, and
a regex cannot tell a correct comparison from an inverted one. Driven under
JavaScriptCore like the other executed client tests here, with the clock
pinned so the fixtures mean the same thing in any month.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess

import pytest

JSC = ("/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/"
       "Helpers/jsc")

APP = open("static/app.js", encoding="utf-8").read()


def _jsc():
    return JSC if os.path.exists(JSC) else shutil.which("jsc")


# "Now" for every case below: Sunday 2026-10-04 21:19 ET, the moment reported.
NOW = "2026-10-05T01:19:52Z"

CASES = {
    # The report, exactly as production served it.
    "sunday_night_friday_print": {
        "post_market_price": 183.2397, "post_market_change_pct": 0.13098378,
        "post_market_time": "2026-10-02T23:59:50+00:00",
        "pre_market_price": None, "pre_market_change_pct": None,
        "pre_market_time": None,
    },
    # The same print, seen during the session it belongs to (Friday 20:30 ET).
    # Covered by moving the clock, not the fixture -- see `rendered`.
    "same_day_after_hours": {
        "post_market_price": 183.2397, "post_market_change_pct": 0.13098378,
        "post_market_time": "2026-10-05T00:30:00+00:00",   # Sun 20:30 ET
    },
    # Pre-market on the day it happens.
    "same_day_pre_market": {
        "post_market_price": None, "post_market_change_pct": None,
        "post_market_time": None,
        "pre_market_price": 190.1, "pre_market_change_pct": 1.4,
        "pre_market_time": "2026-10-04T12:00:00+00:00",    # Sun 08:00 ET
    },
    # Yesterday's pre-market print, which is not this session's.
    "stale_pre_market": {
        "pre_market_price": 190.1, "pre_market_change_pct": 1.4,
        "pre_market_time": "2026-10-01T12:00:00+00:00",
    },
    # A provider that dropped the timestamp. Showing it is the lesser failure.
    "no_timestamp": {
        "post_market_price": 183.24, "post_market_change_pct": 0.13,
    },
    # Nothing to show at all.
    "no_extended_print": {
        "post_market_price": None, "post_market_change_pct": None,
        "pre_market_price": None, "pre_market_change_pct": None,
    },
    # A zero change is a real reading, not an absent one.
    "flat_same_day": {
        "post_market_price": 183.0, "post_market_change_pct": 0.0,
        "post_market_time": "2026-10-05T00:30:00+00:00",
    },
}


@pytest.fixture(scope="module")
def rendered():
    """`{case: result-or-None}` from the real `freshExtended`.

    `Date.now` is pinned rather than the fixtures being written relative to the
    real clock, so these cases keep meaning the same thing when they are read
    back in a year."""
    exe = _jsc()
    if not exe:
        pytest.skip("no JavaScriptCore on this machine")
    script = """
      load('tests/support/browser_stubs.js');
      try { load('static/charts.js'); load('static/app.js'); } catch (e) {}
      if (typeof freshExtended !== 'function') {
        print('RESULT:' + JSON.stringify({error: 'freshExtended is not defined'}));
      } else {
        var pinned = new Date(%s).getTime();
        Date.now = function () { return pinned; };
        var cases = %s, out = {};
        for (var key in cases) { out[key] = freshExtended(cases[key]) || null; }
        out['__etDate'] = etDate('2026-10-02T23:59:50+00:00');
        out['__etDateNow'] = etDate(Date.now());
        print('RESULT:' + JSON.stringify(out));
      }
    """ % (json.dumps(NOW), json.dumps(CASES))
    proc = subprocess.run([exe, "-e", script], capture_output=True, text=True,
                          timeout=180)
    blob = proc.stdout + proc.stderr
    assert "RESULT:" in blob, blob[-1500:]
    body = json.loads(blob.split("RESULT:", 1)[1].split("\n")[0])
    assert "error" not in body, body
    return body


# ------------------------------------------------------------- the report


def test_fridays_print_is_not_shown_on_sunday_night(rendered):
    """The whole of the bug. 73 hours, labelled as the current session."""
    assert rendered["sunday_night_friday_print"] is None


def test_the_dates_it_is_comparing_are_the_ones_intended(rendered):
    """A timezone off by one turns 19:59 Friday ET into Saturday and makes
    every case below pass for the wrong reason."""
    assert rendered["__etDate"] == "2026-10-02", "Fri 19:59 ET, not Sat UTC"
    assert rendered["__etDateNow"] == "2026-10-04", "Sun 21:19 ET, not Mon UTC"


# --------------------------------------------- and what must still show


def test_a_print_from_today_is_shown(rendered):
    """The guard must not cost a live after-hours quote during after hours."""
    out = rendered["same_day_after_hours"]
    assert out and out["kind"] == "After hours"
    assert out["price"] == 183.2397


def test_pre_market_is_shown_on_its_own_day_and_not_after(rendered):
    today = rendered["same_day_pre_market"]
    assert today and today["kind"] == "Pre-market" and today["price"] == 190.1
    assert rendered["stale_pre_market"] is None


def test_a_missing_timestamp_still_shows_the_price(rendered):
    """Refusing to render a live quote because one field was dropped is a
    worse failure than the one being fixed."""
    out = rendered["no_timestamp"]
    assert out and out["price"] == 183.24


def test_a_flat_print_is_a_reading_not_an_absence(rendered):
    """0.0 is falsy. A guard written with a truthiness check loses the one
    case where the price did not move."""
    out = rendered["flat_same_day"]
    assert out is not None and out["pct"] == 0.0


def test_nothing_to_show_shows_nothing(rendered):
    assert rendered["no_extended_print"] is None


# ------------------------------------------------------------ both surfaces


def test_the_strip_and_the_header_share_one_rule():
    """They sit two inches apart. The report had the header saying AFTER HOURS
    and the strip saying "after hrs" on its top line, so a fix to one of them
    would have left the page still contradicting itself."""
    assert APP.count("function freshExtended(quote)") == 1

    head = APP.split("const extQ = (() => {", 1)[1].split("})();", 1)[0]
    assert "freshExtended(q)" in head
    assert "post_market_change_pct" not in head, \
        "the header must not re-derive the rule"

    status = APP.split("function updateStatus()", 1)[1].split("\nfunction ", 1)[0]
    assert "freshExtended(quote)" in status
    assert "quote.post_market_price || quote.pre_market_price" not in status, \
        "the strip must not re-derive the rule either"
