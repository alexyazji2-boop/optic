"""The classic panel's personalities in v2's Milo (owner, 2026-10-19: "include the personalities here that used to
be in the classic version of optic"), as the 2026-10-20 redesign shows them (owner's brief, from an approved
sketch: "Keep personality selection directly visible below the context bar").

The Optic Persona is a row of its five personalities under the context bar, always on show, a radio group with the
chosen one marked by a check and heavier type as well as its fill. The Level and the Timeframe moved into Response
settings, every option kept, with what a persona changes and never changes. All from the same /api/personas and
/api/knowledge/modes, in the classic keys, so a choice made in either app holds in the other. The classic glyphs
are emoji, which v2 draws nowhere, so they are left out. Driven in headless Chrome at 360, 390, 430, 844 by 390,
720 by 450 and 1440 (~/Optic/work/milo-redesign/milo_verify.py): the five names, one chosen, the arrows moving the
choice, the choice sent with the next question and an earlier answer left as it was.
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
    assert 'role="radio"' in row and "aria-checked=" in row and "x.id === cur.id ? icon('check') : ''" in row, "chosen: a check, not only a colour"
    assert "x.blurb" in row and "glyph" not in row, "the classic glyphs are emoji; v2 draws none"
    sheet = MILO[MILO.index("function settingsHTML() {"):MILO.index("// What Milo receives")]
    assert "list(pp.changes, 'Changes')" in sheet and "list(pp.never_changes, 'Never changes')" in sheet
    assert "const PULSE_PERSONA_KEY = 'optic.pulse.persona.v1';" in CLASSIC and "PERSONA_KEY = 'optic.pulse.persona.v1'" in MILO
    assert "setPref(PERSONA_KEY, id); paintChrome();" in MILO
    keys = MILO[MILO.index("// the personas are a radio group"):MILO.index("// inside the guide menu")]
    assert all(k in keys for k in ("ArrowRight", "ArrowLeft", "Home", "End")), "the arrows move the choice"
    assert '.milo-pp-opt[aria-checked="true"] { background: var(--c-active); color: var(--c-ink); font-weight: 600;' in CSS, "the active fill, never gold"


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
