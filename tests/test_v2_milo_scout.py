"""Scout, Milo's mascot, in v2 (2026-10-19), as the classic panel has him.

The classic figure and sprites (static/components/scout.js, static/scout/), loaded before the app as the classic
page loads them. In v2's Milo: the welcome figure beside the greeting, a button that opens the classic guide menu
(what I can ask, example questions, Full, Subtle or Still in the classic key); the bust beside each answer, only the
newest one moving; his head on the Ask Milo button. He moves on Milo's own events, as in the classic panel: the
panel opening, typing, a question sent, a search the server reports, the first words, the end, a failure, a stop.

Checked in a headless browser signed in to the local demo account on the stand-in model, at 1440, 390 and 375 by
549 (~/Optic/work/v2-overnight/scout/milo_scout_check.py): the wave on opening, the menu by mouse and keyboard
(Escape closes the menu, not the panel), a drafted example making him listen, the motion setting, and a question
through acknowledging wave, thinking, streaming and the nod.
"""
import re

from tests.test_frontend_v2_stage0 import V2

ROOT = V2.parent.parent
CLASSIC = (ROOT / "static/app.js").read_text()
SCOUT = (ROOT / "static/components/scout.js").read_text()
INDEX = (V2 / "index.html").read_text()
MILO = (V2 / "js/ui/milo.js").read_text()
SHELL = (V2 / "js/ui/shell.js").read_text()
CSS = (V2 / "css/components.css").read_text()
PAGES = (V2 / "css/pages.css").read_text()


def test_the_classic_figure_is_loaded_before_the_app():
    i, j = INDEX.index('<script src="/components/scout.js"></script>'), INDEX.index('<script type="module" src="js/app.js"></script>')
    assert i < j, "window.OpticScout exists before Milo draws"
    assert "global.OpticScout = {" in SCOUT and "var STORE = 'optic.scout.motion.v1';" in SCOUT
    for f in re.findall(r'url\("/scout/([^"]+)"\)', CSS):
        assert (ROOT / "static/scout" / f).exists(), f
    assert {"scout-full@2x.webp", "scout-full@3x.webp", "scout-compact@2x.webp", "scout-full-tail@2x.webp", "scout-compact-tail@3x.webp"} <= set(re.findall(r'url\("/scout/([^"]+)"\)', CSS))


def test_he_moves_on_milos_events_as_in_the_classic_panel():
    classic = set(re.search(r"const PULSE_SEARCH_STATES = new Set\(\[([^\]]+)\]\);", CLASSIC).group(1).replace("'", "").split(", "))
    ours = set(re.search(r"const SEARCHING = new Set\(\[([^\]]+)\]\);", MILO).group(1).replace("'", "").split(", "))
    assert ours == classic, "only a search the server reports makes him look around"
    assert "scoutTo(ai, 'thinking', 'ack');" in MILO, "a question in: one acknowledging wave, then thinking"
    assert "scoutTo(ai, SEARCHING.has(String(p.state || '')) ? 'searching' : 'thinking')" in MILO
    assert "if (SC.i === ai && SC.state !== 'streaming') scoutTo(ai, 'streaming');" in MILO, "the first words: stillness"
    end = MILO[MILO.index("const reply = S.live ? S.live.text : '';"):MILO.index("export function stop()")]
    assert "if (failed || ended === 'cut') Object.assign(SC, { i: ai, state: 'error', via: null });" in end, "a concerned face, as the classic panel's"
    assert "else if (ended === 'stopped') Object.assign(SC, { i: ai, state: 'idle', via: 'look' });" in end
    assert "via: reply.trim() ? 'nod' : null" in end, "a nod for an answer, nothing for an empty one"
    assert "c.gesture('wave')" in MILO and "Date.now() - SC.lastWave > 20000" in MILO
    assert "now && !open && Date.now() - scoutLastWave > 20000" in CLASSIC, "the same 20 s between waves as the classic panel"
    assert "setTimeout(() => { if (c.state === 'listening') c.set('idle'); }, 2500);" in MILO and "quiet = setTimeout(() => { if (c.state === 'listening') c.set('idle'); }, 2500);" in CLASSIC
    assert "O.attach(el, { slot: 'reply' })" in MILO, "one moving bust at a time, the newest"


def test_the_welcome_figure_and_its_menu():
    assert "figure('full', 'Milo guide: what to ask, examples and animation')" in MILO
    assert "Hi, I'm Milo. What would you like to explore?" in MILO and "Hi, I'm ${esc(ASSISTANT_NAME)}. What would you like to explore?" in CLASSIC
    for item in ("What can I ask?", "Show example questions", "radio('full', 'Full')", "radio('subtle', 'Subtle')", "radio('still', 'Still')"):
        assert item in MILO, item
    assert "if (OS()) OS().setMotion(v);" in MILO, "the classic key, through the classic setter"
    assert "if (e.key === 'Escape') { e.preventDefault(); e.stopPropagation(); setMenu(false, true); }" in MILO, "Escape closes the menu, not the panel"
    # the classic starters, word for word
    i = CLASSIC.index("const PULSE_STARTERS = [")
    classic = re.findall(r"text: '((?:[^'\\]|\\.)*)'", CLASSIC[i:CLASSIC.index("];", i)])
    ours = re.findall(r"\[(?:'ticker'|null), '((?:[^'\\]|\\.)*)'\]", MILO[MILO.index("const EXAMPLES = ["):MILO.index("export const examples")])
    assert ours == classic and len(ours) == 12
    assert "Deep research" not in MILO[MILO.index("const CAN_ASK"):MILO.index("const EXAMPLES")], "v2's Milo has no web research switch or attachments, so its sentence does not offer them"


def test_the_bust_beside_an_answer_and_the_head_on_the_button():
    assert '<p class="milo-who">${figure(\'compact\')}<span>Milo</span></p>' in MILO, "the name stays readable beside him"
    assert 'aria-label="Ask Milo"><span class="scout-badge" aria-hidden="true"><span class="scout-badge-fig"></span></span>' in SHELL
    assert ":root[data-scout-motion=\"still\"] .scout-badge-fig { animation: none; }" in CSS and "@media (prefers-reduced-motion: reduce) { .scout-badge-fig { animation: none; } }" in CSS
    assert ".topbar-milo .scout-badge { width: 26px; height: 26px; }" in PAGES


def test_short_screens_and_the_picker():
    assert "@media (max-width: 640px), (max-height: 760px) { .milo-hello { flex-wrap: wrap; } .scout-menu { position: static;" in CSS, "the menu is never cut off at the log's edge"
    assert ".milo-top .milo-scope { display: flex;" in CSS and ".milo-top .milo-scope select { flex: 1; width: 100%; min-width: 0; }" in CSS
    assert "min-height: var(--tap)" in CSS[CSS.index(".scout-mi {"):CSS.index(".scout-mi:hover")], "44 px targets"
