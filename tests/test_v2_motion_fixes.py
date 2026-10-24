"""Three things the motion check of 2026-10-24 found moving that should not have, held fixed.

1. Every page load jumped. The legal footer sat under the top bar while #main was empty and was pushed away when the
   page drew (layout shift 0.14 to 0.22 on desktop, 0.58 to 0.63 on phones from it alone), and the phone bar grew
   54 px upward when its buttons arrived. After: SPY's Overview 0.000 at 1440 and 390, Home 0.012 and 0.063.
2. The drawer's close was not animated. close() hid it in the same moment it took is-open away, so the --m-exit
   transition never ran and the panel was gone in the next painted frame. Its owner's teardown (Milo's full-screen
   class) now waits until it has left: run at once it dropped the phone panel into the generic sheet mid-exit.
3. On a phone, the first move of a pan unhid Reset zoom on a toolbar row of its own and pushed the plot 38 px down
   under the finger. It sits over the plot there now, above the chart's own buttons, clear of the volume pane's.
   Which one shows is the width's, by CSS: chosen in JS when the chart was made, a resize past 860px showed both.

Measured in headless Chrome with the frame-stepped recorder and Chrome's screencast, and with drawer_edges.mjs and
reset_zoom.mjs (~/Optic/work/motion-check-2026-10-24); the wiring is read as text here.
"""
from tests.test_frontend_v2_stage0 import V2

JS = V2 / "js"
DRAWER = (JS / "ui/drawer.js").read_text()
PC = (JS / "ui/pricechart.js").read_text()
CH = (JS / "pages/chart.js").read_text()
COMP = (V2 / "css/components.css").read_text()
PAGES = (V2 / "css/pages.css").read_text()


def test_the_footer_waits_for_the_first_page():
    assert "#main:empty + .legal { display: none; }" in COMP


def test_the_phone_bar_has_its_height_before_its_buttons():
    bar = COMP[COMP.index("  .tabbar { display: grid;"):]
    bar = bar[:bar.index("}") + 1]
    assert "min-height: calc(55px + 4px + max(8px, env(safe-area-inset-bottom)))" in bar


def test_the_drawer_plays_its_exit_before_it_hides():
    close = DRAWER[DRAWER.index("export function close("):DRAWER.index("export const isOpen")]
    assert "root.hidden = true" not in close.split("leaving = () =>")[0], "nothing hides the drawer before its exit has run"
    assert "hideT = setTimeout(leaving, ms + 20)" in close and "root.inert = true" in close
    assert "if (done) done();" in close.split("leaving = () =>")[1], "the owner's teardown runs once the panel has left"
    assert "export const isOpen = () => !!root && shown;" in DRAWER, "closed at once for every caller"
    assert "if (leaving) { clearTimeout(hideT); leaving(); }" in DRAWER, "a reopen finishes the last close first"
    # the exit is the CSS's to time: --m-exit, and nothing under reduced motion (base.css zeroes transitions)
    assert ".drawer:not(.is-open) .drawer-panel, .drawer:not(.is-open) .drawer-scrim { transition-duration: var(--m-exit); pointer-events: none; }" in COMP


def test_a_phone_reset_zoom_moves_nothing():
    assert "homeButton: true," in CH and '<button type="button" class="btn btn-sm ch-home" data-v2-ch-home' in CH
    assert "${isPhone() ? '' : html`<button type=\"button\" class=\"btn btn-sm ch-home\"" not in CH, "both are drawn; the width picks one"
    # one Reset zoom at any width, by CSS, so a resize past 860px never shows both (the chart is not rebuilt on resize)
    assert "@media (max-width: 860px) { .ctools .ch-home { display: none; } }" in PAGES
    assert "@media not all and (max-width: 860px) { .pc-cb.pc-home { display: none; } }" in PAGES
    assert "(S.homeButton ? '<button type=\"button\" class=\"pc-cb pc-home\" data-pc-home hidden" in PC
    assert "if (zoomed !== zoomedWas && homeEl) homeEl.hidden = !zoomed;" in PC
    assert "if (b.hasAttribute('data-pc-home')) { home(); return; }" in PC
    assert ".pc-cb.pc-home { position: absolute;" in PAGES and ".pc-cb.pc-home[hidden] { display: none; }" in PAGES
