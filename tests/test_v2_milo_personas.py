"""The classic panel's personalities in v2's Milo (owner, 2026-10-19: "include the personalities here that used to
be in the classic version of optic").

Since 2026-10-22 the Optic Persona is a menu under the context bar, like the context bar's own (owner: "the
personalities are very cluttered, fix it", choosing the menu over keeping the five on show): one line naming the
persona in use; pressed, it lists the five, each with what it does, a radio group with the chosen one ticked. From
2026-10-20 it had been a row of the five always on show, whose names did not fit the panel. The Level and the
Timeframe are in Response settings, every option kept, with what a persona changes and never changes. All from the
same /api/personas and /api/knowledge/modes, in the classic keys, so a choice made in either app holds in the other.
The classic glyphs are emoji, which v2 draws nowhere, so they are left out. The menu was driven in headless Chrome
(~/Optic/work/classic-parity/persona_menu_check.py); these tests are not interaction evidence.
"""
from tests.test_frontend_v2_stage0 import V2

ROOT = V2.parent.parent
CLASSIC = (ROOT / "static/app.js").read_text()
MILO = (V2 / "js/ui/milo.js").read_text()
CSS = (V2 / "css/components.css").read_text()


def test_the_personas_are_on_show_and_the_level_and_timeframe_in_response_settings():
    chrome = MILO[MILO.index("function chromeHTML() {"):MILO.index("function logHTML() {")]
    assert "${ctxHTML()}${movedHTML()}${personaHTML()}" in chrome, "under the context bar, always drawn"
    sheet = MILO[MILO.index("function settingsHTML() {"):MILO.index("// What Milo receives")]
    order = [sheet.index(x) for x in ('class="select milo-level"', "data-v2-milo-hz=")]
    assert order == sorted(order), "the classic order: the level, then the timeframe"
    assert 'aria-labelledby="milo-set-h"' in sheet and ">Response settings<" in sheet


def test_the_persona_row_is_the_classic_control():
    assert '<span class="pp-eyebrow">Optic Persona</span>' in CLASSIC
    row = MILO[MILO.index("function personaHTML() {"):MILO.index("function settingsHTML() {")]
    assert '>Optic Persona</p>' in row and 'role="radiogroup" aria-labelledby="milo-pp-lab"' in row, "the classic name for the control"
    assert 'role="radio"' in row and "aria-checked=" in row and "x.id === cur.id ? icon('check') : html`<span class=\"milo-ctx-gap\"></span>`" in row, "chosen: a check, not only a colour"
    assert '<details class="menu milo-pp-pick">' in row and '<span class="milo-ctx-now">${cur.label}</span>' in row, "a menu naming the persona in use"
    assert "${x.blurb ? html`<small>${x.blurb}</small>` : ''}" in row, "each persona with what it does"
    assert "x.blurb" in row and "glyph" not in row, "the classic glyphs are emoji; v2 draws none"
    sheet = MILO[MILO.index("function settingsHTML() {"):MILO.index("// What Milo receives")]
    assert "list(pp.changes, 'Changes')" in sheet and "list(pp.never_changes, 'Never changes')" in sheet
    assert "const PULSE_PERSONA_KEY = 'optic.pulse.persona.v1';" in CLASSIC and "PERSONA_KEY = 'optic.pulse.persona.v1'" in MILO
    assert "setPref(PERSONA_KEY, id); paintChrome();" in MILO
    keys = MILO[MILO.index("// the personas are a radio group"):MILO.index("// inside the guide menu")]
    assert all(k in keys for k in ("ArrowRight", "ArrowLeft", "Home", "End")), "the arrows move the choice"
    assert ".menu-body.milo-pp-menu { left: 12px; right: 12px;" in CSS and "milo-pp-row" not in CSS, "the menu spans the panel; the row is gone"
    assert "if (close && menu) { menu.open = false;" in MILO and "pickPersona(b.dataset.v2MiloPp, root, true)" in MILO, "a press closes the menu, back on its button"


def test_the_personas_come_from_the_server():
    from fastapi.testclient import TestClient
    import app.main as main
    d = TestClient(main.app).get("/api/personas").json()
    assert [p["id"] for p in d["personas"]] == ["neutral", "longterm", "stoic", "quant", "skeptic"]
    assert all(p.get("blurb") for p in d["personas"]) and d["changes"] and d["never_changes"]
    assert [h["id"] for h in d["horizons"]["horizons"]] == ["auto", "day", "swing", "long"]


def test_the_timeframe_row():
    assert "const MILO_HORIZON_KEY = 'optic.milo.horizon.v1';" in CLASSIC and "HORIZON_KEY = 'optic.milo.horizon.v1'" in MILO
    assert "const HZ_SHORT = { auto: 'Auto', day: 'Day', swing: 'Swing', long: 'Long term' };" in MILO
    assert "const short = { auto: 'Auto', day: 'Day', swing: 'Swing', long: 'Long term' };" in CLASSIC, "the classic row's words"
    assert "setPref(HORIZON_KEY, b.dataset.v2MiloHz)" in MILO
    assert "max-height: min(70vh, 520px); overflow-y: auto;" in CSS, "Response settings scroll rather than running off the screen"
    assert ".milo-lens-blurb { display: none; }" in CSS, "on a phone, as the classic panel does: the controls stay, the lines go"


def test_the_context_bar_gives_its_data_line_the_whole_width():
    # it was squeezed into the space beside Response settings (owner's screenshot, 2026-10-22)
    assert ".milo-ctx-l { min-width: 0; display: contents; }" in CSS and ".milo-ctx-meta { grid-column: 1 / -1; grid-row: 2; }" in CSS
    assert ".milo-ctx > .milo-set-btn { grid-column: 2; grid-row: 1; }" in CSS, "Response settings on the picker's line"
