"""Scout, Pulse's mascot: the contracts the browser cannot be trusted to keep.

Asked for on 2026-10-11 with the user's own concept sheet (concept 03,
"Scout") as a 3D character, then reworked the same day: higher-resolution
renders, a bigger welcome figure, and motion tied to Pulse's real events
(the panel opening, typing, a question sent, a search the server reports,
the answer streaming, its end, an error) instead of a loop of its own. Then:
larger hands and his scarf in the wind (the Pulse mark was tried as his face
and set aside for the two eyes).
Presentation only: nothing here may touch what Pulse sends, streams or costs.

The renders are committed sprites (static/scout/) made by
optic-brand/scout/render_scout.py, which writes frames.json; the frame
order there is a contract with FRAME in components/scout.js.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
APP = (ROOT / "static/app.js").read_text(encoding="utf-8")
CSS = (ROOT / "static/styles.css").read_text(encoding="utf-8")
HTML = (ROOT / "static/index.html").read_text(encoding="utf-8")
SCOUT = (ROOT / "static/components/scout.js").read_text(encoding="utf-8")
MANIFEST = json.loads((ROOT / "static/scout/frames.json").read_text(encoding="utf-8"))
FRAMES = MANIFEST["frames"]


def _fn(name, src=APP):
    start = src.index("function %s(" % name)
    return src[start:src.index("\n}", start)]


def _proto(name):
    start = SCOUT.index("Ctl.prototype.%s = function" % name)
    return SCOUT[start:SCOUT.index("\n  };", start)]


def _block(start_marker):
    start = CSS.index(start_marker)
    return CSS[start:CSS.index("\n}", start)]


def test_the_component_loads_before_app_js():
    assert HTML.index('src="components/scout.js?v=') < HTML.index('src="app.js?v=')


def test_the_frame_order_matches_the_renders():
    """FRAME in scout.js is the order the renderer wrote. One frame out of
    place and a blink shows the arm, or a wave shows the concerned face."""
    order = re.findall(r"'([a-z0-9-]+)': (\d+)", SCOUT[SCOUT.index("var FRAME = {"):SCOUT.index("var COUNT")])
    assert [n for n, _ in order] == FRAMES
    assert [int(i) for _, i in order] == list(range(len(FRAMES)))
    assert "var COUNT = %d;" % len(FRAMES) in SCOUT


def test_the_sprites_are_transparent_strips_at_two_densities():
    """Transparent, or a box shows round him on the dark panel; every frame
    one size, or a frame position lands between two pictures. The 3x frame
    covers the welcome figure's largest size (84px x the 1.15 UI scale). The
    scarf's tail is its own strip of wind phases, the same frame size."""
    for kind in ("full", "compact"):
        for dens in ("2x", "3x"):
            w, h = MANIFEST[kind][dens]
            for layer, count in (("", len(FRAMES)), ("-tail", MANIFEST["wind"])):
                name = "scout-%s%s@%s.webp" % (kind, layer, dens)
                im = Image.open(ROOT / "static/scout" / name)
                assert im.mode == "RGBA", name
                assert im.size == (w * count, h), (name, im.size)
                alpha = im.getchannel("A")
                for x in range(count):
                    assert alpha.getpixel((x * w + 1, 1)) == 0, "frame %d of %s has a background" % (x, name)
                assert alpha.getextrema()[0] == 0 and alpha.getextrema()[1] >= 250, name
    assert MANIFEST["full"]["3x"][0] >= 84 * 1.15 * 3 - 2
    assert MANIFEST["compact"]["3x"][0] >= 40 * 1.15 * 3 - 2
    hero = Image.open(ROOT / "static/scout/scout.png")
    assert hero.mode == "RGBA" and hero.getpixel((0, 0))[3] == 0


def test_the_box_holds_its_space_and_picks_a_density():
    base = _block("\n.scout {")
    full_w, full_h = MANIFEST["full"]["3x"]
    assert "aspect-ratio: %d / %d" % (full_w, full_h) in base
    pose = _block("}\n.scout::after {")
    assert "background-size: %d00%% 100%%" % len(FRAMES) in pose
    assert "background-position-x: var(--scout-x);" in pose
    assert "--scout-x: 0%;" in base
    assert 'image-set(url("scout/scout-full@2x.webp") 2x, url("scout/scout-full@3x.webp") 3x)' in pose
    tail = _block("\n.scout::before {")
    assert "background-size: %d00%% 100%%" % MANIFEST["wind"] in tail
    assert "scout-full-tail@3x.webp" in tail
    cw, ch = MANIFEST["compact"]["3x"]
    assert "aspect-ratio: %d / %d" % (cw, ch) in CSS
    assert "scout-compact@3x.webp" in _block("\n.scout-compact::after {")
    assert "scout-compact-tail@3x.webp" in _block("\n.scout-compact::before {")
    # The sequencer owns the poses; the CSS loops are the scarf, only while
    # scout.js marks the figure windy, and the Pulse button's blinking badge.
    foot = CSS[CSS.index("==== Scout ==="):]
    assert sorted(re.findall(r"@keyframes (scout-[a-z-]+)", foot)) == ["scout-badge-blink", "scout-wind"]
    assert ".scout.is-windy::before { animation: scout-wind 1200ms steps(%d, jump-none) infinite; }" \
        % MANIFEST["wind"] in foot
    assert "animation" not in _block("\n.scout::before {")


def test_the_blink_runs_open_half_closed_half_open():
    blink = _proto("blink")
    assert "[[f[1], 35], [f[2], 50], [f[1], 40]]" in blink, "half, closed, half (quickened 2026-10-12)"
    assert "self.rest()" in blink, "and back to open"
    for pose in ("idle", "tilt", "curious", "concerned"):
        assert "%s: ['%s', '%s-half', '%s-closed']" % (pose, pose, pose, pose) in SCOUT


def test_pauses_are_five_to_ten_seconds_and_nothing_runs_hidden():
    assert "rand(2500, 5000)" in SCOUT and "rand(2000, 4000)" in SCOUT
    running = _proto("running")
    for cond in ("this.visible", "!document.hidden", "motion() !== 'still'", "this.alive()"):
        assert cond in running, cond
    assert "IntersectionObserver" in SCOUT and "io.observe(el)" in SCOUT
    assert "visibilitychange" in SCOUT
    # A removed figure stops itself: no timers left on a detached node.
    alive = _proto("alive")
    assert "isConnected" in alive and "this.stop()" in alive
    stop = _proto("stop")
    assert "clearTimeout(this.idleT)" in stop and "io.unobserve(this.el)" in stop
    # The scarf loops only while he is running at Full; asleep or stopped, it is still.
    assert "this.windy(this.running() && motion() === 'full');" in _proto("wake")
    assert "this.windy(false);" in _proto("sleep") and "this.windy(false);" in stop


def test_motion_setting_full_subtle_still_remembered_and_reduced_by_default():
    assert "var STORE = 'optic.scout.motion.v1';" in SCOUT
    assert "v === 'full' || v === 'subtle' || v === 'still'" in SCOUT
    assert "reduceQuery && reduceQuery.matches ? 'still' : 'full'" in SCOUT
    # Gestures belong to full alone; subtle keeps poses and single blinks.
    assert "if (motion() !== 'full') { done(); return; }" in _proto("gesture")
    menu = _fn("scoutMenuHTML")
    for v in ("full", "subtle", "still"):
        assert "radio('%s'," % v in menu
    assert 'role="menuitemradio"' in menu


def test_the_welcome_wave_belongs_to_the_panel_opening():
    """Not to a render: renderPulseEmpty attaches without a gesture, and the
    wave comes from the body's chat-open class turning on, at most once a
    minute."""
    empty = _fn("renderPulseEmpty")
    assert "attach(log.querySelector('.pulse-hello-row .scout'), { slot: 'welcome' })" in empty
    assert "gesture(" not in empty
    events = _fn("installScoutEvents")
    assert "attributeFilter: ['class']" in events
    assert "now && !open && Date.now() - scoutLastWave > 20000" in events
    assert "c.gesture('wave')" in events
    assert "\n  installScoutEvents();" in APP


def test_typing_tilts_once_not_per_key():
    events = _fn("installScoutEvents")
    assert "if (c.state === 'idle') c.set('listening');" in events
    assert "2500" in events
    # The same state again restarts nothing.
    assert "if (state === this.state && !via) return;" in _proto("set")


def test_a_question_gets_one_wave_then_thinking():
    reply = _fn("pulseReplyScout")
    assert "c.set('thinking', 'ack');" in reply, "thinking, entered by one wave"
    st = _proto("set")
    assert st.index("this.state = state;") < st.index("this.gesture(via)"), \
        "state first, so it holds even when the wave cannot play"
    for name in ("sendChat", "runResearch"):
        body = APP[APP.index("async function %s(" % name):]
        body = body[:body.index("\n}\n")]
        assert "const scout = pulseReplyScout(node, true);" in body, name
        fin = body[body.index("} finally {"):]
        assert "pulseReplyScoutDone(scout, node);" in fin, name


def test_searching_only_when_the_server_says_so():
    """Pulse's own status events (app/ai.py): web search in chat, search and
    source reading in deep research. Anything else is thinking, and the box
    says "Checking sources…" only for these."""
    assert "new Set(['searching the web', 'searching', 'reading and weighing sources'])" in APP
    ai = (ROOT / "app/ai.py").read_text(encoding="utf-8")
    for state in ("searching the web", "searching", "reading and weighing sources"):
        assert '"state": "%s"' % state in ai, state
    status = _fn("pulseScoutStatus")
    assert "searching ? 'Checking sources…' : 'Working'" in status
    stream = APP[APP.index("async function streamTo("):]
    stream = stream[:stream.index("\n}\n")]
    assert "pulseScoutStatus(node, state);" in stream
    assert "if (!acc) pulseScoutStreaming(node);" in stream, "stillness from the first words"


def test_endings_nod_concern_or_idle_never_stuck():
    done = _fn("pulseReplyScoutDone")
    assert "node.classList.contains('err')" in done and "c.set('error')" in done
    assert "c.set('idle', 'nod')" in done
    assert "else c.set('idle');" in done, "an empty ending: idle, no nod"
    assert "error: 'concerned'" in SCOUT
    # No celebration exists to be played (the comments may say so; the code
    # has no such gesture).
    code = re.sub(r"/\*.*?\*/|//[^\n]*", "", SCOUT.lower(), flags=re.S)
    for word in ("celebrat", "jump", "cheer", "thumb"):
        assert word not in code


def test_the_menu_sends_nothing_and_is_a_real_menu():
    act = _fn("scoutMenuAction")
    for banned in ("sendChat(", "runResearch(", "streamTo(", "fetch(", "draftPulse("):
        assert banned not in act, banned
    menu = _fn("scoutMenuHTML")
    assert 'role="menu"' in menu and menu.count('role="menuitem"') == 2
    assert "What can I ask?" in menu and "Show example questions" in menu
    events = _fn("installScoutEvents")
    for key in ("Escape", "ArrowDown", "ArrowUp", "Home", "End", "Tab"):
        assert "'%s'" % key in events, key
    html = SCOUT[SCOUT.index("function html("):SCOUT.index("\n  }", SCOUT.index("function html("))]
    assert 'aria-haspopup="menu"' in html and 'aria-expanded="false"' in html
    assert "esc(label)" in _fn("scoutHTML"), "the label is escaped"


def test_decorative_figures_are_hidden_and_the_reply_keeps_its_name():
    assert '<span class="\' + cls + \'" aria-hidden="true"' in SCOUT
    reply = _fn("pulseReplyScout")
    assert '<span class="sr-only">${esc(ASSISTANT_NAME)}</span>' in reply


def test_the_capability_sentence_is_shared():
    assert "addMsg('assistant', PULSE_CAN_ASK)" in APP
    assert "mdLite(PULSE_CAN_ASK)" in _fn("pulseStarters")


def test_presentation_only():
    for banned in ("fetch(", "XMLHttpRequest", "/api/", "sessionStorage", "http://", "https://"):
        assert banned not in SCOUT, banned
    foot = CSS[CSS.index("==== Scout ==="):]
    assert "http" not in foot, "the sprites are this site's files"
    for name in ("sendChat", "runResearch"):
        body = APP[APP.index("async function %s(" % name):]
        body = body[:body.index("\n}\n")]
        assert body.count("streamTo(") == 1


def test_the_expressions_carry_no_market_meaning():
    code = re.sub(r"/\*.*?\*/|//[^\n]*", "", SCOUT.lower(), flags=re.S)
    for state in ("bull", "bear", "confident", "happy", "sad", "excited", "worried"):
        assert not re.search(r"\b%s" % state, code), state


def test_the_pulse_button_wears_scout_blinking():
    """Asked for on 2026-10-12: "change this to the snowman blinking while
    keeping the color scheme visible". The Pulse button's mark is Scout's head
    from the bust sprite on a dark disc; the panel header keeps the reduced
    mark. The blink steps through the sprite's own lid frames (1 half, 2
    closed) and stops under reduced motion or with Scout's motion set to Still."""
    mount = APP[APP.index("function mountPulseMarks() {"):]
    mount = mount[:mount.index("\n}\n")]
    assert "id === 'pulse-mark-btn'" in mount and 'class="scout-badge"' in mount
    assert "pulseMarkHTML('pulse-glyph-sm')" in mount, "the panel header keeps the mark"
    badge = _block("\n.scout-badge {")
    assert "border-radius: 50%" in badge and "background: var(--asset-brand-ink)" in badge
    fig = _block("\n.scout-badge-fig {")
    assert "scout-compact@3x.webp" in fig and "background-size: %d00%% 100%%" % len(FRAMES) in fig
    assert "animation: scout-badge-blink 11s step-end infinite;" in fig
    step = 100 / (len(FRAMES) - 1)
    assert FRAMES.index("idle-half") == 1 and FRAMES.index("idle-closed") == 2
    blink = CSS[CSS.index("@keyframes scout-badge-blink"):]
    blink = blink[:blink.index("\n}")]
    assert "%.4f%%" % step in blink and "%.4f%%" % (2 * step) in blink
    assert ':root[data-scout-motion="still"] .scout-badge-fig { animation: none; }' in CSS
    reduced = CSS[CSS.index(':root[data-scout-motion="still"] .scout-badge-fig'):]
    assert "@media (prefers-reduced-motion: reduce)" in reduced[:300]
    assert "setAttribute('data-scout-motion', motion())" in SCOUT


def test_he_blinks_and_waves_more_often():
    """Asked for on 2026-10-12: "have him blink and wave in shorter intervals
    to make it more frequent". A beat every 2.5-5 s; the welcome figure waves
    on his own at most every 20 s, at Full motion only."""
    sched = SCOUT[SCOUT.index("Ctl.prototype.schedule = function () {"):]
    sched = sched[:sched.index("\n  };")]
    assert "rand(2500, 5000)" in sched
    assert "var WAVE_GAP_MS = 20000;" in SCOUT
    assert "full && self.state === 'idle' && self.slot === 'welcome'" in sched
    assert "self.gesture('wave');" in sched
