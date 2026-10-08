"""The second audit of the workspace redesign (2026-10-08): what it repaired.

Four of the repairs are interaction defects in app.js and are driven here
under JavaScriptCore against the functions themselves, with the DOM stubbed:

* Pulse squeezing the page. Opening Pulse under 1280px left the page 276px
  or less beside an expanded rail; the rail now gives way while Pulse splits
  the screen and comes back when it closes, and a press of Collapse/Expand
  in between is the reader's and stands.
* A Pulse width nobody chose did not follow the window.
* Views drawn at an old width came back on screen with stale charts.
* Home's data-source chip said "Checking data source…" for the rest of the
  session after any return to Home.

The layout repairs are CSS and are asserted as rules, because the property
each holds is a rule: the content column is centred and capped, the Dossier
header does not pin a third of a phone's screen, section tabs wrap rather
than hide, a heading's controls cannot squeeze its title into a column.
"""
from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
JS = (ROOT / "static/app.js").read_text(encoding="utf-8")
CSS = (ROOT / "static/styles.css").read_text(encoding="utf-8")
CSS_NC = re.sub(r"/\*.*?\*/", " ", CSS, flags=re.S)
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc"
needs_jsc = pytest.mark.skipif(not os.path.exists(JSC), reason="JavaScriptCore not available")


def _block(src: str, start: str, open_ch: str = "{", close_ch: str = "}") -> str:
    i = src.index(start)
    j = src.index(open_ch, i)
    depth = 0
    for k in range(j, len(src)):
        if src[k] == open_ch:
            depth += 1
        elif src[k] == close_ch:
            depth -= 1
            if depth == 0:
                return src[i:k + 1]
    raise AssertionError("unbalanced: " + start)


def _fn(name: str) -> str:
    return _block(JS, "function %s(" % name)


def _run(tmp_path, script: str) -> list:
    path = tmp_path / "t.js"
    path.write_text(script)
    out = subprocess.run([JSC, str(path)], capture_output=True, text=True, timeout=30)
    assert out.returncode == 0, out.stderr + out.stdout
    return out.stdout.strip().splitlines()


# ------------------------------------------------------- the rail and Pulse

RAIL_HARNESS = """
var classes = {};
var document = { body: { classList: {
  contains: function (c) { return !!classes[c]; },
  toggle: function (c, on) { classes[c] = on === undefined ? !classes[c] : !!on; },
} } };
var width = 1024;
function matchMedia(q) {
  var lo = /min-width: (\\d+)px/.exec(q), hi = /max-width: (\\d+)px/.exec(q);
  return { matches: (!lo || width >= +lo[1]) && (!hi || width <= +hi[1]) };
}
var stored = null;
function railChoice() { return stored; }
function railDefault() { return matchMedia(RAIL_AUTO_QUERY).matches; }
function applyRail(tight) { document.body.classList.toggle('rail-tight', tight); }
%s
%s
function state(label) { print(label + ' ' + (classes['rail-tight'] ? 'icons' : 'labels')); }
"""


def _rail_script(body: str) -> str:
    consts = "\n".join([
        re.search(r"const RAIL_AUTO_QUERY = [^;]+;", JS).group(0),
        re.search(r"const RAIL_YIELD_QUERY = [^;]+;", JS).group(0),
        re.search(r"let railYielded = false;", JS).group(0),
        re.search(r"let railHeldByReader = false;", JS).group(0),
    ])
    return RAIL_HARNESS % (consts, _fn("syncRailWithChat")) + body


@needs_jsc
def test_the_rail_gives_way_to_pulse_and_comes_back(tmp_path):
    lines = _run(tmp_path, _rail_script("""
      applyRail(railDefault()); state('start');
      classes['chat-open'] = true; syncRailWithChat(); state('open');
      classes['chat-open'] = false; syncRailWithChat(); state('closed');
    """))
    assert lines == ["start labels", "open icons", "closed labels"]


@needs_jsc
def test_it_does_not_yield_where_there_is_room_or_when_pulse_covers(tmp_path):
    lines = _run(tmp_path, _rail_script("""
      width = 1440; applyRail(false);
      classes['chat-open'] = true; syncRailWithChat(); state('wide');
      classes['chat-open'] = false; syncRailWithChat();
      width = 1024; classes['chat-open'] = true; classes['chat-full'] = true;
      syncRailWithChat(); state('cover');
    """))
    assert lines == ["wide labels", "cover labels"]


@needs_jsc
def test_a_readers_press_while_pulse_is_open_stands(tmp_path):
    """The first draft re-collapsed the rail on the very class change that the
    reader's Expand caused, so Expand did nothing while Pulse was open."""
    click = re.search(r"btn\.addEventListener\('click', \(\) => \{(.*?)\n    \}\);", _fn("initRail"), re.S)
    assert click and "railHeldByReader = true" in click.group(1)
    lines = _run(tmp_path, _rail_script("""
      applyRail(false); classes['chat-open'] = true; syncRailWithChat(); state('open');
      // The reader presses Expand, exactly as the button's handler does.
      railYielded = false;
      if (document.body.classList.contains('chat-open')) railHeldByReader = true;
      applyRail(false); syncRailWithChat(); state('expanded');
      classes['chat-open'] = false; syncRailWithChat();
      classes['chat-open'] = true; syncRailWithChat(); state('next-open');
    """))
    assert lines == ["open icons", "expanded labels", "next-open icons"]


@needs_jsc
def test_a_rail_the_reader_collapsed_stays_collapsed_after_pulse(tmp_path):
    lines = _run(tmp_path, _rail_script("""
      stored = true; applyRail(true);
      classes['chat-open'] = true; syncRailWithChat();
      classes['chat-open'] = false; syncRailWithChat(); state('after');
    """))
    assert lines == ["after icons"]


def test_every_route_to_pulse_reaches_the_rail():
    """Opening, closing, Escape and the split/cover switch all change the
    body's class, so one observer on it is the single hook."""
    init = _fn("initRail")
    assert "new MutationObserver(syncRailWithChat)" in init
    assert "attributeFilter: ['class']" in init
    # Declared before initRail can run, which it does at load.
    assert JS.index("const RAIL_YIELD_QUERY") < JS.index("function initRail(")
    assert JS.index("let railYielded") < JS.index("function initRail(")


def test_an_unchosen_pulse_width_follows_the_window():
    install = _fn("installChatResize")
    resize = install[install.index("window.addEventListener('resize'"):]
    assert "storedChatWidth()" in resize[:400], \
        "the window-aware default, not the width computed for the window at load"


# ------------------------------------------------------ stale charts on return


@needs_jsc
def test_a_view_drawn_at_another_width_is_redrawn_when_shown(tmp_path):
    decl = re.search(r"const VIEWS_DRAWN_STALE = new Set\(\);", JS).group(0)
    script = """
    var resizeTimer = null, redrawn = 0;
    function rerenderActiveView() { redrawn++; }
    function setTimeout(fn) { fn(); return 1; }
    function clearTimeout() {}
    %s
    %s
    VIEWS_DRAWN_STALE.add('swing');
    redrawIfStale('swing'); redrawIfStale('swing'); redrawIfStale('market');
    print(redrawn);
    """ % (decl, _fn("redrawIfStale"))
    assert _run(tmp_path, script) == ["1"], "once for the stale view, never for a fresh one"


def test_a_width_change_marks_every_other_view_and_switching_checks():
    observer = JS[JS.index("const watchWidth = (el) =>"):JS.index("const VIEWS_DRAWN_STALE")]
    assert "VIEWS_DRAWN_STALE.add(k)" in observer
    assert "k !== STATE.view" in observer, "the view on screen is redrawn by the observer itself"
    switch = _fn("switchView")
    assert switch.index("loadView(view, !!force);") < switch.index("redrawIfStale(view);")


# ----------------------------------------------------------- Home's footer


def test_returning_home_draws_the_footer_from_the_answer_in_hand():
    home = _fn("renderHome")
    after = home[home.index("Checking data source…"):]
    assert "if (STATE.health) renderHomeStatus(STATE.health);" in after


# ------------------------------------------------------------ layout rules


def _rule(selector: str) -> str:
    m = re.search(re.escape(selector) + r"\s*\{([^}]*)\}", CSS_NC)
    assert m, selector
    return m.group(1)


def test_the_content_column_is_centred_and_capped():
    assert re.search(r"--ws-content-max:\s*1680px", CSS_NC)
    body = _rule("main > .view:not(.view-workspace),\nmain > .page-head")
    assert "max-width: var(--ws-content-max)" in body and "margin-inline: auto" in body


def test_homes_lockup_is_one_centred_group():
    m = re.search(r"@media \(min-width: 1100px\) \{\s*#view-home > \.home \{([^}]*)\}", CSS_NC)
    assert m, "the lockup grid"
    assert "minmax(0, 1fr) auto" in m.group(1) and m.group(1).rstrip().count("minmax(0, 1fr)") >= 2, \
        "equal flexible tracks either side, so the group sits in the middle"


def test_homes_band_holds_its_place_only_while_home_is_loading():
    assert ".home:has(#hm-market .hm-skel) > #cc-strip:empty" in CSS_NC


def test_the_dossier_header_does_not_pin_on_a_phone():
    block = CSS_NC
    m = re.search(r"@media \(max-width: 559px\) \{\s*\.sec-head \{ position: static; \}", block)
    assert m
    # And what sat under the pinned header now sits under the top bar alone.
    assert re.search(r"\.sec-index \{ top: calc\(var\(--topbar-h, 106px\) \+ var\(--space-1\)\); \}", block)


def test_section_tabs_wrap_rather_than_hide_below_1280():
    assert re.search(r"@media \(max-width: 1279px\) \{\s*\.sec-head \.sec-tabs \{ flex-wrap: wrap;", CSS_NC)


def test_a_headings_title_keeps_its_line():
    assert ".panel > h2.is-toggle > :first-child:not(.panel-toggle) { flex: 1 1 0; min-width: 0; }" in CSS_NC
    assert '.panel > h2.is-toggle::after { content: ""; order: 1; flex-basis: 100%; height: 0; }' in CSS_NC


def test_four_small_multiples_are_never_drawn_under_the_chart_floor():
    """buildChartNow never draws narrower than 320, so a column under 320 is a
    scaled-down drawing. Four across needs four times that plus the gaps."""
    assert "builder(Math.max(w, 320))" in JS
    assert "@container vizm (min-width: 1340px)" in CSS_NC
    assert "@container vizm (min-width: 600px)" in CSS_NC


def test_the_search_gives_way_when_pulse_shares_the_bar():
    assert "body.chat-open:not(.chat-full) header.topbar .search input" in CSS_NC
