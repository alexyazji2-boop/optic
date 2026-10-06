"""The catalyst card's "Released ... ago" is worked out when it is shown.

Reproduced from the code before the fix: the label was the server's, true when
built, and the card was fetched once per page, so a page left open all
afternoon still said "Released 12 minutes ago". A failed load left the card's
space empty, which reads as "no catalyst today".
"""

import json
import os
import shutil
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app import catalyst_live

ROOT = Path(__file__).resolve().parent.parent
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc"


def test_the_age_carries_the_instant():
    when = (datetime.now(timezone.utc) - timedelta(minutes=12)).isoformat()
    age = catalyst_live._age(when)
    assert age["published_utc"].startswith(when[:16]) and age["label"] == "12 minutes ago"


def test_the_page_counts_from_the_instant_not_the_label():
    exe = JSC if os.path.exists(JSC) else shutil.which("jsc")
    if not exe:
        pytest.skip("no JavaScriptCore on this machine")
    three_hours = (datetime.now(timezone.utc) - timedelta(hours=3, minutes=2)).isoformat()
    src = """
      load('tests/support/browser_stubs.js');
      document.documentElement.style = document.documentElement.style || {};
      document.documentElement.style.setProperty = function () {};
      document.documentElement.style.removeProperty = function () {};
      try { load('static/charts.js'); load('static/app.js'); } catch (e) {}
      print('RESULT:' + JSON.stringify([
        catalystAgeLabel({label: '12 minutes ago', published_utc: '%s'}),
        catalystAgeLabel({label: 'as built'}),
        catalystAgeLabel(null)]));
    """ % three_hours
    out = subprocess.run([exe, "-e", src], capture_output=True, text=True, timeout=60, cwd=str(ROOT))
    got = json.loads(out.stdout.split("RESULT:", 1)[1].split("\n")[0])
    assert got == ["3 hours ago", "as built", ""]


def test_a_failed_load_says_so_where_the_card_would_be():
    app = (ROOT / "static/app.js").read_text()
    block = app.split("async function loadCatalystMode() {", 1)[1].split("\n}\n", 1)[0]
    assert "could not be loaded just now" in block and "console.warn" not in block
