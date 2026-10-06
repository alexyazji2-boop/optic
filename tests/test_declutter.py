"""Contracts from the 2026-10-04 clutter pass.

The report was that every page felt like too much competing for attention.
Most of the fixes are asserted next to the older tests they changed; these
are the ones with no older test to live beside.
"""
from __future__ import annotations

import re

APP = open("static/app.js", encoding="utf-8").read()
INDEX = open("static/index.html", encoding="utf-8").read()
CSS = open("static/styles.css", encoding="utf-8").read()


def _open_by_default(view):
    block = APP.split("const PANELS_OPEN_BY_DEFAULT = {", 1)[1].split("\n};", 1)[0]
    block = re.sub(r"/\*.*?\*/", " ", block, flags=re.S)
    m = re.search(r"\n  %s: \[(.*?)\]" % view, block, re.S)
    return set(re.findall(r"'([^']+)'", m.group(1)))


def test_reference_tables_do_not_open_by_default():
    """Currencies was 5,696px, 48% of Macro; the congressional list was
    longer than the statements Financials is named for."""
    assert "currencies" not in _open_by_default("market")
    assert "congressional disclosures" not in _open_by_default("financials")
    # And what each tab is for still opens.
    assert {"macro regime", "economic data"} <= _open_by_default("market")
    assert "financials" in _open_by_default("financials")


def test_prose_clamps_on_pages_outside_the_render_pass():
    """Insiders, Analysts, Overview and the rest fill in after switchView, so
    a clamp that ran only from the render pass never reached them."""
    fn = APP.split("(function watchProseForClamp() {", 1)[1].split("}());", 1)[0]
    assert "markClampedCaveats(views[STATE.view])" in fn
    assert "subtree: true" in fn
    assert "requestAnimationFrame" not in re.sub(r"/\*.*?\*/", "", fn, flags=re.S), \
        "a frame never comes in a background tab"


def test_the_status_line_names_the_feed_not_the_phase_twice():
    for fn_name in ("function updateStatus()",):
        body = APP.split(fn_name, 1)[1].split("\nfunction ", 1)[0]
        assert "liveIndicatorHTML()" not in body
        assert "statusFeedChip()" in body


def test_the_footer_line_is_short_and_the_full_text_is_one_press_away():
    line = INDEX.split('<p class="legal-line">', 1)[1].split("</p>", 1)[0]
    text = re.sub(r"<[^>]+>", "", line)
    assert "Not financial advice." in text
    assert "broker-dealer" in text and "risk of loss" in text
    assert len(" ".join(text.split())) < 260, "the five-line paragraph is back"
    assert 'id="legal-more"' in line and 'id="legal-full"' in INDEX
    full = APP.split("const LEGAL = {", 1)[1].split("areas:", 1)[0]
    for claim in ("broker-dealer", "solicitation", "personalised", "Past performance",
                  "licensed financial professional"):
        assert claim in full, claim


def test_settings_lights_no_rail_group():
    fn = APP.split("function groupForView(view) {", 1)[1].split("\n}", 1)[0]
    assert "if (view === 'settings') return 'settings';" in fn


def _code(css):
    return re.sub(r"/\*.*?\*/", " ", css, flags=re.S)


def test_the_section_tabs_sit_beside_the_search_not_after_pulse():
    """Below 1410px the old `nav.tabs { order: 3 }` still reached this strip,
    which is also a `nav.tabs`, and on the live site signed in the tabs
    rendered to the right of Pulse. Above the phone breakpoint the strip
    takes its DOM place again, between the search and the account control."""
    code = _code(CSS)
    m = re.search(r"@media \(min-width: 720px\) \{\s*nav\.tabs-sub#subnav \{([^}]*)\}", code)
    assert m, "the desktop placement rule is gone"
    assert "order: 0" in m.group(1)
    assert "flex: 1 1 0" in m.group(1), "a content basis lets the strip wrap Pulse"
    # In the DOM, the strip comes before the account slot and Pulse.
    assert INDEX.index('id="subnav"') < INDEX.index('id="account-slot"') \
        < INDEX.index('id="chat-toggle"')


def test_a_narrow_bar_gives_the_tabs_a_row_rather_than_clipping_them():
    """At 1024 the Discover tabs needed 326px and got 246, and "Analysts"
    rendered as "Analys". Measured on the bar, so docking Pulse counts."""
    code = _code(CSS)
    bar = re.search(r"\nheader\.topbar \{([^}]*container-type[^}]*)\}", code)
    assert bar and "container-name: topbar" in bar.group(1)
    assert "flex-wrap: wrap" in bar.group(1), "the row has nowhere to go"
    m = re.search(r"@container topbar \(max-width: [\d.]+rem\) \{\s*nav\.tabs-sub#subnav \{([^}]*)\}", code)
    assert m, "the narrow-bar rule is gone or no longer in rem"
    assert "order: 3" in m.group(1) and "flex: 1 0 100%" in m.group(1)
    # Later than the desktop rule, which it has to beat on source order.
    assert code.index("@container topbar") > code.index("@media (min-width: 720px) {\n  nav.tabs-sub#subnav")
