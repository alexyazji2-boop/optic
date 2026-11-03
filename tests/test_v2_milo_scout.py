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
ACT = (V2 / "js/ui/milo-activity.js").read_text()
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
    """The classic panel drove a bust from Milo's events. v2 drives one companion in the header from the same
    events, through the activity reducer (tests/test_milo_activity.py). What is checked here is that the two
    panels still agree about when he looks around, and that v2 has exactly one figure doing it."""
    classic = set(re.search(r"const PULSE_SEARCH_STATES = new Set\(\[([^\]]+)\]\);", CLASSIC).group(1).replace("'", "").split(", "))
    ours = set(re.search(r"export const SEARCH_STEPS = new Set\(\[([^\]]+)\]\);", ACT).group(1).replace("'", "").split(", "))
    assert classic <= ours, "every search the classic panel reports still makes him look up from the page"
    assert "paintCompanion(S.live.act, 'nod');" in MILO, "a question in: one nod, then Thinking"
    assert MILO.count("O.attach(el, { slot: 'companion' })") == 1, "one figure, attached in one place"
    for gone in ("slot: 'welcome'", "slot: 'reply'", "slot: 'activity'"):
        assert gone not in MILO, "the old %s figure is gone" % gone
    assert "setTimeout(() => { if (c.state === 'listening') c.set('idle'); }, 2500);" in MILO \
        and "quiet = setTimeout(() => { if (c.state === 'listening') c.set('idle'); }, 2500);" in CLASSIC
    assert "c.set(pose, via)" in MILO, "a gesture leads into the new pose, as it did"
    # a press plays at most one gesture, and never over a state the reader needs
    assert "if (c && !S.busy && Date.now() - SC.lastPress > 900)" in MILO


def test_the_guide_menu_rides_on_the_companion():
    """The welcome screen used to carry a large figure with his guide menu on it. The figure is now the
    companion in the header for the whole conversation, so the menu went with it rather than being lost."""
    assert "const fig = '';" in MILO, "no second large animated Milo on the empty screen"
    assert "label: 'Milo guide: what to ask, examples and animation'" in MILO
    assert "const root = coEl(); const btn = root && $('.scout-btn', root); if (btn) btn.focus({ preventScroll: true });" in MILO
    assert 'aria-haspopup="menu"' in SCOUT, "the figure is the menu's button, as before"
    assert "const btn = $('.scout-btn', root); if (btn) btn.setAttribute('aria-expanded', String(SC.menu));" in MILO


def test_the_companion_in_the_header_and_the_head_on_the_button():
    # The header is him since 2026-11-03: his figure, his name, one status, outside the scrolling log.
    assert "head: html`${raw(companionHTML({" in MILO
    assert ".milo-panel .drawer-head { position: relative; justify-content: center;" in CSS, "centred, as the brief's references are"
    assert ".milo-panel .drawer-acts { position: absolute; top: 8px; right: 8px; }" in CSS, "history, new and close stay reachable"
    assert 'aria-label="Ask Milo"><span class="scout-badge" aria-hidden="true"><span class="scout-badge-fig"></span></span>' in SHELL
    assert ":root[data-scout-motion=\"still\"] .scout-badge-fig, :root[data-motion=\"reduce\"] .scout-badge-fig { animation: none; }" in CSS and "@media (prefers-reduced-motion: reduce) { .scout-badge-fig { animation: none; } }" in CSS
    assert ".topbar-milo .scout-badge { width: 26px; height: 26px; }" in PAGES


def test_short_screens_and_the_picker():
    assert "@media (max-width: 640px), (max-height: 760px) { .milo-hello { flex-wrap: wrap; } .scout-menu { position: static;" in CSS, "the menu is never cut off at the log's edge"
    # what Milo receives is a menu in the context bar now; its name shortens rather than running under the buttons
    assert ".milo-ctx-now { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }" in CSS and ".milo-ctx-l { min-width: 0;" in CSS
    assert "min-height: var(--tap)" in CSS[CSS.index(".scout-mi {"):CSS.index(".scout-mi:hover")], "44 px targets"
