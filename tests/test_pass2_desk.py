"""Pass 2, item 7 (2026-11-17): the Optic Desk's right side for sources, saved research and Milo follow-ups.

Beside the edition on a wide screen and under it on a narrow one, so Home scrolls less: what the edition is built
from (each source named, the stories linked), the reader's three latest saved items, and questions about this edition
pressed into Milo's box (nothing is sent until Send).
"""
from __future__ import annotations

from tests.test_frontend_v2_stage0 import V2

WS = (V2 / "js" / "pages" / "workspace.js").read_text()
CSS = (V2 / "css" / "pages.css").read_text()


def test_the_desk_panel_draws_the_edition_with_its_right_side():
    assert 'html`<div class="desk-grid"><div class="desk-main">${deskBody(md)}</div>${deskSide(md, d)}</div>`' in WS
    side = WS[WS.index("function deskSide(md, d) {"):WS.index("/* ---------------- the Milo prompt (2026-11-09)")]
    assert 'aria-label="Sources, saved research and questions for Milo"' in side
    assert "Built from" in side and "Your saved research" in side and "Ask Milo" in side
    assert 'target="_blank" rel="noopener"' in side, "a story opens at its publisher"


def test_saved_research_is_read_once_in_five_minutes_and_only_signed_in():
    load = WS[WS.index("function loadDeskSaved() {"):WS.index("function deskQuestions(md) {")]
    assert "!store.signedIn()" in load and "300000" in load and "/api/library?limit=3" in load
    assert "Sign in to keep research on your account." in WS


def test_milo_questions_are_about_this_edition_and_wait_for_send():
    q = WS[WS.index("function deskQuestions(md) {"):WS.index("function deskSide(md, d) {")]
    assert "What would change today\\'s bottom line?" in q and ".slice(0, 3)" in q
    assert "miloButton(q, { ask: q" in WS


def test_on_a_wide_screen_the_side_sits_beside_the_edition_not_under_it():
    assert "@media (min-width: 1200px)" in CSS and "grid-template-columns: minmax(0, 1fr) minmax(200px, 34%)" in CSS
