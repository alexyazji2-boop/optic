"""The classic panel's personalities in v2's Milo (owner, 2026-10-19: "include the personalities here that used to
be in the classic version of optic").

The classic panel shows its three answer settings in the open: the level, the Optic Persona (a menu of each
personality with what it is, and what choosing one changes and never changes) and the timeframe as one row of four.
v2 had folded them into "Answer settings" as plain selects. Now they are on show, from the same /api/personas, in
the same keys, so a choice made in either app holds in the other. The classic glyphs are emoji, which v2 draws
nowhere, so they are left out. Checked in a browser at 1440 and 390: the five personalities, the footer, a pick
remembered and the menu shut, the timeframe and its line.
"""
from tests.test_frontend_v2_stage0 import V2

ROOT = V2.parent.parent
CLASSIC = (ROOT / "static/app.js").read_text()
MILO = (V2 / "js/ui/milo.js").read_text()
CSS = (V2 / "css/components.css").read_text()


def test_the_settings_are_on_show_not_folded():
    assert "settingsHTML" not in MILO and "milo-settings" not in MILO and "Answer settings" not in MILO
    assert "${S.showHistory ? historyHTML() : ''}${lensHTML()}" in MILO
    lens = MILO[MILO.index("function lensHTML() {"):MILO.index("function chromeHTML() {")]
    order = [lens.index(x) for x in ('class="select milo-level"', 'class="menu milo-pp"', "data-v2-milo-hz=")]
    assert order == sorted(order), "the classic order: the level, then the persona, then the timeframe"


def test_the_persona_menu_is_the_classic_one():
    assert '<span class="pp-eyebrow">Optic Persona</span>' in CLASSIC
    lens = MILO[MILO.index("function lensHTML() {"):MILO.index("function chromeHTML() {")]
    assert 'aria-label="Optic Persona"><span class="t-label">Optic Persona</span>' in lens, "the classic name for the control"
    assert "x.blurb" in lens and "list(pp.changes, 'Changes')" in lens and "list(pp.never_changes, 'Never changes')" in lens
    assert "glyph" not in lens, "the classic glyphs are emoji; v2 draws none"
    assert "const PULSE_PERSONA_KEY = 'optic.pulse.persona.v1';" in CLASSIC and "PERSONA_KEY = 'optic.pulse.persona.v1'" in MILO
    assert "setPref(PERSONA_KEY, b.dataset.v2MiloPp)" in MILO and "if (d) d.open = false; paintChrome();" in MILO


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
    assert "max-height: min(70vh, 560px); overflow-y: auto;" in CSS, "the menu scrolls rather than running off the screen"
    assert ".milo-lens-blurb { display: none; }" in CSS, "on a phone, as the classic panel does: the controls stay, the lines go"
