"""Fixes from the 2026-10-12 mobile audit: Mobile Safari on iOS 27 simulators
(iPhone SE 3rd gen, 13 mini, 17e, 17, Air, 18 Pro Max) and headless Chromium
emulation (320-480, landscape, Large text). Each test names what was measured.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CSS = re.sub(r"/\*.*?\*/", "", (ROOT / "static/styles.css").read_text(), flags=re.S)


def _media(query: str) -> str:
    """Every block with exactly this media query, joined."""
    out = []
    for m in re.finditer(r"@media " + re.escape(query) + r" \{", CSS):
        depth, i = 1, m.end()
        while depth:
            depth += {"{": 1, "}": -1}.get(CSS[i], 0)
            i += 1
        out.append(CSS[m.end():i - 1])
    return "\n".join(out)


def test_the_ticker_action_row_wraps_instead_of_running_off_screen():
    """Alert and Ask Milo sat past the right edge on every ticker page."""
    assert re.search(r"\n\.sec-actions \{ display: flex; flex-wrap: wrap;", CSS)
    assert ".sec-actions .adv-toggle { flex: 1 0 100%; margin-right: 0; }" in CSS


def test_the_disclaimer_and_milo_clear_the_bottom_bar_correctly():
    """"Full disclaimer" was under the bar; Milo kept a 52px dead band under Send."""
    phone = _media("(max-width: 559px)")
    assert "footer.legal { padding-bottom: calc(var(--space-5) + 52px + env(safe-area-inset-bottom)); }" in phone
    assert "aside#chat { padding-bottom: env(safe-area-inset-bottom); }" in phone
    assert "main { min-height: calc(100dvh - var(--topbar-h, 64px)); }" in phone
    assert ".scroll-y { max-height: none; }" in phone


def test_touch_fields_are_at_least_16px_so_ios_does_not_zoom():
    coarse = _media("(pointer: coarse)")
    assert "input:not([type=checkbox]):not([type=radio]):not([type=range]), select, textarea {\n    font-size: max(16px, 1em) !important;" in coarse
    for sel in ("#chat-close::after", "#legal-more::after", ".cs-note-btn::after", "td .tkr::after"):
        assert sel in coarse, sel


def test_the_short_window_block_is_landscape_only():
    """An SE is 549px tall in Safari portrait; the block drew the search icon
    over the typed symbol and unstuck the bar there."""
    assert "@media (max-height: 560px) {" not in CSS
    land = _media("(max-height: 560px) and (orientation: landscape)")
    assert ".search input { padding-top: var(--space-1); padding-bottom: var(--space-1); }" in land
    assert ".sec-head { position: static; }" in land


def test_milo_fits_320_and_keeps_room_on_short_phones():
    phone = _media("(max-width: 640px)")
    assert "#chat .chat-actions { flex-wrap: wrap; gap: var(--space-1); }" in phone
    assert "flex-wrap: nowrap" not in phone.split("#chat .chat-actions {")[1].split("}")[0]
    short = _media("(max-width: 640px) and (max-height: 720px)")
    assert ".chat-desc { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }" in short
    assert ".pulse-persona-blurb, .pulse-modes-h { display: none; }" in short


def test_touch_screens_get_chart_zoom_buttons_beside_explain_chart():
    """Only Safari pinches a chart; on Android a pinch did nothing. Measured in
    Chromium touch emulation at 402px: + took 78 bars to 52, - back to 78, and
    the buttons sit clear of Explain chart and full screen."""
    app = (ROOT / "static/app.js").read_text()
    assert "${wsZoomButtons()}\n        ${chartPulse(STATE.chartSymbol)}" in app
    step = app[app.index("function wsZoomStep(dir) {"):]
    step = step[:step.index("\n}\n")]
    assert "CHART_ZOOM.get('ws-chart')" in step and "zoomedWindow(cur, Math.max(0, span - 1), want)" in step
    assert "Math.max(WS_MIN_BARS, Math.min(cur.total," in step
    assert ".ws-zoom-btns { display: none; }" in CSS
    assert ".ws-zoom-btns { display: flex;" in _media("(pointer: coarse)")
