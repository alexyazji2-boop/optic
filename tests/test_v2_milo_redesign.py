"""Milo's panel, redesigned (owner's brief, 2026-10-20, from an approved sketch), in Optic's own components.

A compact header: Milo beside his name, history, a new conversation and close as named line icons. Under it what
Milo receives ("NVDA / Chart", a menu of the page, the market only or nothing), the data's freshness and the
disclosure with details on demand, and Response settings (Level and Timeframe). The five personas always on show.
The conversation takes the rest of the height and scrolls on its own: a new one opens with the larger Scout, one
heading, a line about the page and three starters that send; answers sit on the panel's surface with their
sources and actions after them. The composer is pinned at the foot, the send control inside the field. On a phone
the panel is the whole screen inside its safe areas.

Starter selection, the context's short name and the renderer's tables and numbered lists run in JavaScriptCore;
the wiring is read as text. Driven in headless Chrome against the STAND-IN model (simulated answers: interface
and request checks only, never answer quality) at 360, 390, 430, 844 by 390, 720 by 450 and 1440 px
(~/Optic/work/milo-redesign/milo_verify.py, 103 checks; milo_check.py's 19 integration checks also pass).
"""
from tests.test_frontend_v2_stage0 import V2, _run

JS = V2 / "js"
MILO = (JS / "ui/milo.js").read_text()
DRAWER = (JS / "ui/drawer.js").read_text()
CSS = (V2 / "css/components.css").read_text()
ICONS = (JS / "ui/icons.js").read_text()


def js(tmp_path, body):
    return _run(tmp_path, f"""
      const M = await import('{(JS / "ui/milo.js").as_posix()}');
      const T = await import('{(JS / "core/milo-text.js").as_posix()}');
      {body}
    """)


def test_the_header_is_milo_by_his_name_with_three_named_icons():
    opener = MILO[MILO.index("export async function openMilo("):MILO.index("// Milo's panel is as wide")]
    assert "kicker: 'Ask Milo'" not in opener, "no Ask Milo above Milo"
    assert '<div class="milo-id">${figure(\'compact\')}<div><h2 id="milo-title" tabindex="-1">Milo</h2><p class="milo-sub">Research assistant</p></div></div>' in opener
    for label, ic in (("Conversation history", "history"), ("New conversation", "compose")):
        assert f'aria-label="{label}" title="{label}">${{icon(\'{ic}\')}}' in opener, label
    assert "head = null, actions = null" in DRAWER and '<div class="drawer-acts">${actions}${shut}</div>' in DRAWER
    assert "${head || html`<div><p class=\"drawer-kicker\">${kicker}</p>" in DRAWER, "every other drawer keeps its kicker and title"
    for name in ("history", "compose", "sliders", "link", "info", "send", "stop", "check", "copy", "retry", "arrowDown"):
        assert f"  {name}: '<" in ICONS, name


def test_the_context_bar_names_what_milo_receives_and_lets_it_change(tmp_path):
    got = js(tmp_path, """
      print(JSON.stringify({ chart: M.contextShort('auto', { view: 'chart', symbol: 'NVDA' }), over: M.contextShort('auto', { view: 'overview', symbol: 'AAPL' }),
        market: M.contextShort('market', { view: 'chart', symbol: 'NVDA' }), none: M.contextShort('none') }));
    """)
    assert got == {"chart": "NVDA / Chart", "over": "AAPL / Overview", "market": "Market only", "none": "No page context"}
    ctx = MILO[MILO.index("function ctxHTML() {"):MILO.index("// The page open is another symbol's")]
    assert 'data-v2-milo-scope="${k}"' in ctx and "['auto', `This page: ${contextLabel('auto')}`" in ctx
    assert "${freshness()} Not financial advice." in ctx and 'aria-controls="milo-info"' in ctx and "${miloNotice()}" in ctx
    assert "S.health && S.health.realtime_chain" in MILO, "freshness from the server's state, not a fixed claim"
    assert 'data-v2-milo-settings aria-expanded=' in ctx and "Response settings</span>" in ctx


def test_another_symbol_is_said_before_the_next_question():
    moved = MILO[MILO.index("function movedHTML() {"):MILO.index("function chromeHTML() {")]
    assert "This conversation is about ${S.conv.lastTicker}. Your next question will be about ${now}, and Milo is told the change." in moved
    assert 'data-v2-milo-new>Start a new conversation</button>' in moved


def test_starters_fit_the_page_and_the_context(tmp_path):
    got = js(tmp_path, """
      print(JSON.stringify({ chart: M.starters({ view: 'chart', symbol: 'NVDA' }, 'auto'), fin: M.starters({ view: 'financials', symbol: 'AAPL' }, 'auto'),
        home: M.starters({ view: 'home' }, 'auto'), cmp: M.starters({ view: 'compare' }, 'auto'), none: M.starters({ view: 'chart', symbol: 'NVDA' }, 'none'),
        inst: M.starters({ view: 'instrument', symbol: 'SPY' }, 'auto') }));
    """)
    assert len(got["chart"]) == 3 and all("NVDA" in q or "chart" in q for q in got["chart"])
    assert all("AAPL" in q for q in got["fin"]) and "revenue" in got["fin"][0]
    assert got["home"][0] == "Summarise what happened in the market since the last close.", "classic's words, kept"
    assert got["cmp"][0] == "How do these names compare on the figures on screen?"
    assert got["none"] == got["home"], "no page context: questions that need none"
    assert all("SPY" in q for q in got["inst"]) and not any("{T}" in q for v in got.values() for q in v)
    assert "if ((b = t('[data-v2-milo-start]'))) { send(b.dataset.v2MiloStart); return; }" in MILO, "a starter sends; it is not decoration"
    assert "Example questions: pressing one puts it in the box" in MILO, "the classic examples still only draft"


def test_the_welcome_is_one_heading_and_goes_once_a_conversation_starts():
    opening = MILO[MILO.index("function openingHTML() {"):MILO.index("export function button(")]
    assert '<h3 class="milo-hello-h">What would you like to understand?</h3>' in opening
    # the owner's ask (2026-10-20): a friendly hello from under Scout, then the question
    assert opening.index('<div class="milo-hello">') < opening.index('<p class="milo-hi">Hey, I\'m Milo!</p>') < opening.index('class="milo-hello-h"')
    assert "figure('full', 'Milo guide: what to ask, examples and animation')" in opening
    assert 'class="milo-starters"' in opening and "starters().map(" in opening
    log = MILO[MILO.index("function logHTML() {"):MILO.index("function paintChrome()")]
    assert "if (!S.items.length) return openingHTML();" in log and "if (S.showHistory) return historyHTML();" in log


def test_answers_sit_on_the_surface_with_sources_and_actions_after():
    msg = MILO[MILO.index("function msgHTML(it) {"):MILO.index("// What an answer was about")]
    assert '<article class="milo-msg milo-bot"' in msg and '<p class="milo-who">Milo</p>' in msg
    assert '<div class="milo-foot">${sourceLists(info)}<div class="milo-acts">' in msg
    assert "data-v2-milo-copy" in msg and "data-v2-milo-again" in msg
    src = MILO[MILO.index("function sourceLists(info) {"):MILO.index("// History takes")]
    assert '<summary>Sources (${n})</summary>' in src
    assert ".milo-bot .milo-bubble { min-width: 0;" in CSS and "border-left: 2px solid var(--c-gold-light)" not in CSS[CSS.index("/* ---------- Milo"):CSS.index("/* ---------- states")], "no gold rule beside every answer"
    assert ".milo-src { display: inline-flex; align-items: center; min-height: 24px; padding: 0 7px; margin: 0 2px; border-radius: var(--r-xs);" in CSS, "a source tag is squared, not a pill"


def test_tables_numbered_steps_and_code_render(tmp_path):
    got = js(tmp_path, r"""
      const out = T.mdLite("Levels:\n\n| Level | Price |\n|---|---:|\n| Support | 205.10 |\n| Resistance | <b>228</b> |\n\n1. First\n2. Second\n\n```\nx < y\n```");
      print(JSON.stringify({ out }));
    """)["out"]
    assert '<div class="milo-tbl"><table><thead><tr><th>Level</th><th>Price</th></tr></thead>' in got
    assert '<td class="n">205.10</td>' in got and "&lt;b&gt;228&lt;/b&gt;" in got, "figures right-aligned; markup in a cell escaped"
    assert got.count('class="milo-li milo-oli"') == 2 and '<span class="milo-n">1.</span>' in got
    assert '<pre class="milo-code">\nx &lt; y\n</pre>' in got
    assert ".milo-tbl { margin: 2px 0 10px; overflow-x: auto;" in CSS, "a wide table scrolls inside the answer, never the page"


def test_the_composer_is_pinned_with_its_send_control_inside():
    opener = MILO[MILO.index("export async function openMilo("):MILO.index("// Milo's panel is as wide")]
    assert '<div class="milo-compose">' in opener and 'class="milo-send" data-v2-milo-send aria-label="Send"' in opener and 'class="milo-stop" data-v2-milo-stop aria-label="Stop the answer"' in opener
    assert "btn btn-primary\" data-v2-milo-send" not in MILO, "the separate yellow Send button is gone"
    assert "paperclip" not in MILO and "attachments: []" in MILO, "no attachment control: Milo takes no files"
    assert ".milo-compose textarea { flex: 1; min-width: 0; min-height: 34px; max-height: 160px;" in CSS and "function grow(ta)" in MILO
    assert "if (!text || S.busy || blocked()) return;" in MILO, "no second request while one is out"
    assert "f.dataset.state = !S.busy ? 'idle' : S.live && S.live.text ? 'streaming' : 'sending';" in MILO
    assert "if (S.busy && hadFocus === send && stop) stop.focus({ preventScroll: true });" in MILO, "focus follows Send turning into Stop"
    assert "e.key === 'Enter' && !e.shiftKey && !e.isComposing" in MILO, "Enter sends, Shift and Enter is a new line"


def test_the_conversation_scrolls_on_its_own_and_never_pulls_the_reader():
    assert "if (S.toEnd || (stick && pinned)) log.scrollTop = log.scrollHeight;" in MILO
    assert "b.hidden = !(S.items.length && !S.showHistory && log.scrollHeight - log.scrollTop - log.clientHeight > 160);" in MILO
    assert "behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth'" in MILO
    assert ".milo-panel .drawer-body { display: flex; flex-direction: column; min-height: 0; overflow: hidden; overflow: clip;" in CSS, "nothing scrolls the header away"
    assert ".milo-log { flex: 1; min-width: 0; min-height: 0; overflow-y: auto; overscroll-behavior: contain;" in CSS


def test_escape_closes_the_innermost_thing_first():
    esc = MILO[MILO.index("// Escape closes what is open inside the panel first"):MILO.index("// the personas are a radio group")]
    assert "details.menu[open]" in esc and "e.stopPropagation(); menu.open = false;" in esc and "if (S.showSettings) { e.preventDefault(); e.stopPropagation(); setSettings(false); }" in esc


def test_a_phone_gets_the_whole_screen_and_full_size_targets():
    phone = CSS[CSS.index("/* a phone: the whole screen"):CSS.index("/* a short screen")]
    assert ".drawer-panel.milo-panel { top: var(--vvt, 0px); bottom: auto; left: 0; width: 100%; height: var(--vvh, 100dvh);" in phone
    assert "env(safe-area-inset-top, 0px)" in phone and "env(safe-area-inset-bottom, 0px)" in phone
    assert ".milo-settings { position: fixed; z-index: 8; top: auto; left: 0; right: 0; bottom: 0;" in phone, "Response settings rise as a sheet"
    assert ".milo-pp-row[style*=\"--n: 5\"] .milo-pp-opt:nth-child(n+4) { grid-column: span 3; }" in phone, "three above, two below"
    assert ".milo-compose textarea { font-size: var(--t-lg); }" in phone, "16 px, so iOS does not zoom into the field"
    assert "panel.style.setProperty('--vvt', `${Math.round(vv.offsetTop)}px`)" in MILO, "the keyboard: the panel is what it leaves"
    coarse = CSS[CSS.index("@media (pointer: coarse) {\n  .milo-send"):CSS.index("/* a phone: the whole screen")]
    assert "min-height: var(--tap)" in coarse and ".milo-info-btn::after { content: \"\"; position: absolute; inset: -8px; }" in CSS
    short = CSS[CSS.index("/* a short screen"):CSS.index("/* ---------- states")]
    assert ".milo-pp-row, .milo-pp-row:not([style*=\"--n: 5\"]) { grid-template-columns: repeat(var(--n, 5), minmax(0, 1fr)); }" in short, "on its side: the personas stay, in one row"
