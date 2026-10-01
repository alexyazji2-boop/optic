"""A page left open says when Optic has been updated, and reloads to where it was.

Optic is one page, and nothing in it reloads itself, so a tab opened before a
deploy keeps that deploy's code for as long as it stays open. Reported twice as
a change that had not happened: the Find stocks box ("wheres this?") and a
ticker that still opened the Options tab ("the issue is still occurring"), both
on a page opened before the deploy that changed it. Checked in a browser: a
newer stamp from the server showed the notice, and a reload from it came back
to the same view.
"""
from __future__ import annotations

import re
from pathlib import Path

from fastapi.testclient import TestClient

import app.main as main

ROOT = Path(__file__).resolve().parent.parent
APP = (ROOT / "static/app.js").read_text()


def _fn(name):
    return re.search(r"^(?:async )?function %s\([^\n]*\) \{.*?^\}" % name, APP, re.M | re.S).group()


def test_the_server_says_which_version_it_serves():
    out = TestClient(main.app).get("/api/build").json()
    assert out == {"build": main._asset_version()}


def test_the_stamp_is_the_one_the_page_was_loaded_with():
    """The page reads its own version off the tag that loaded it, which the
    index route stamps with the same `_asset_version`."""
    assert "document.querySelector('script[src*=\"app.js?v=\"]')" in APP
    assert 're.sub(r"\\?v=\\d+", "?v=" + _asset_version(), html)' in (ROOT / "app/main.py").read_text()


def test_a_different_version_shows_the_notice_once_and_never_reloads_by_itself():
    fn = _fn("checkForNewBuild")
    assert "fetch('/api/build', { cache: 'no-store', credentials: 'same-origin' })" in fn
    assert "if (!build || String(build) === OPTIC_BUILD) return;" in fn
    assert "buildNoticeShown = true;" in fn
    assert "Optic has been updated since this page was opened." in fn
    assert "location.reload" not in fn, "only the reader's press reloads"


def test_it_asks_when_the_tab_comes_back_and_every_ten_minutes():
    assert "if (document.visibilityState === 'visible') checkForNewBuild();" in APP
    assert "setInterval(checkForNewBuild, 10 * 60 * 1000);" in APP


def test_a_reload_from_the_notice_comes_back_to_the_same_place():
    reload = APP[APP.index("if (evt.target.closest('[data-build-reload]')) {"):][:400]
    assert "JSON.stringify({ view: STATE.view, ticker: STATE.ticker || null })" in reload
    restore = _fn("restoreReloadPlace")
    assert "sessionStorage.removeItem(RELOAD_PLACE_KEY);" in restore, "once, not on every load"
    assert "if (place.ticker) loadTicker(place.ticker, place.view);" in restore
    boot = APP[APP.index("(async function boot() {"):]
    assert "renderHome();\n  restoreReloadPlace();" in boot
