"""Desktop and mobile have to describe the same product.

Found by auditing the running app at 1512px: the only routes to Watchlist or
Alerts anywhere in the document were the two buttons inside `#mtabs`, the
mobile bottom bar, which is `display: none` at that width. So on a desktop
those two views were reachable through the command palette and through nothing
else -- a reader had to already know they existed and press Cmd-K.

They are simultaneously two of the five things the phone puts one tap away,
which is the other half of it: the two navigations were not describing the
same application. The same audit found the phone calling the Dossier
"Analyse" and Pulse "Ask", so three of its five tabs used a name the desktop
does not use.
"""

from __future__ import annotations

import re

APP = open("static/app.js", encoding="utf-8").read()
CSS = open("static/styles.css", encoding="utf-8").read()


def _block(name):
    body = APP.split("const {} = [".format(name), 1)[1]
    return body[:body.index("\n];")]


NAV_GROUPS = _block("NAV_GROUPS")
MOBILE_TABS = _block("MOBILE_TABS")


def _mobile_tabs():
    return re.findall(r"\{\s*view:\s*'([a-z]+)',\s*label:\s*'([^']+)'", MOBILE_TABS)


# ------------------------------------------------------------- reachability


def test_every_nav_group_is_on_the_strip():
    """`offStrip` is how Watchlist and Alerts became unreachable on a desktop.

    The flag existed so `groupForView` had something to resolve for views with
    no tab, and the render filtered those groups out. That is fine for a view
    reached from inside another page; it is not fine for two top-level
    destinations the phone treats as primary."""
    assert "offStrip" not in NAV_GROUPS, \
        "a group the strip does not render needs another visible route"


def test_watchlist_and_alerts_have_a_desktop_home():
    group = [ln for ln in NAV_GROUPS.splitlines() if "'follow'" in ln]
    assert group, "the follow group is gone; where did Watchlist go?"
    assert "'watchlist'" in group[0] and "'alerts'" in group[0]


def test_the_palette_is_not_the_only_way_to_reach_a_view():
    """The command palette lists every destination, which is what made this
    survivable and also what hid it: a view can be in the palette and have no
    button anywhere, and nothing about the app says so."""
    places = APP.split("const PALETTE_PLACES = [", 1)[1]
    places = places[:places.index("\n];")]
    in_palette = set(re.findall(r"view:\s*'([a-z]+)'", places))
    on_strip = set(re.findall(r"'([a-z]+)'", NAV_GROUPS))
    in_dossier = set(re.findall(r"'([a-z]+)'", APP.split(
        "const SECURITY_VIEWS = [", 1)[1].split("]", 1)[0]))
    on_mobile = {v for v, _ in _mobile_tabs()}
    # 'settings' is the gear, which is a button in the header rather than a
    # nav entry, and 'instrument' is a transient page opened from a link.
    exempt = {"settings", "instrument"}
    orphans = in_palette - on_strip - in_dossier - on_mobile - exempt
    assert not orphans, "reachable only from the palette: {}".format(sorted(orphans))


# ------------------------------------------------------------------- naming


def test_the_phone_uses_the_desktop_words():
    """One name per destination. The phone said "Analyse" for what the strip
    calls "Dossier" and "Ask" for what the header button calls "Pulse", so a
    reader moving between a laptop and a phone learned the product twice.

    This is the same rule the NAV_GROUPS comment already applies to "Optic's
    Positions", which was renamed away from "Portfolio" for it."""
    labels = dict(_mobile_tabs())
    assert labels.get("overview") == "Dossier", \
        "the strip calls this group Dossier"
    assert labels.get("ask") == "Pulse", \
        "the header button calls this Pulse"
    assert "Analyse" not in MOBILE_TABS


def test_the_phones_tabs_all_exist_on_the_desktop_too():
    """Not the same *set* -- a phone shows fewer -- but nothing on it should be
    a destination the desktop has no concept of."""
    on_strip = set(re.findall(r"'([a-z]+)'", NAV_GROUPS))
    in_dossier = set(re.findall(r"'([a-z]+)'", APP.split(
        "const SECURITY_VIEWS = [", 1)[1].split("]", 1)[0]))
    for view, label in _mobile_tabs():
        if view == "ask":
            continue          # the assistant, which is a panel rather than a view
        assert view in on_strip or view in in_dossier, \
            "{} ({}) is a phone-only destination".format(view, label)


# ------------------------------------------- what an eighth group cost

def test_the_strip_may_wrap_only_between_the_two_breakpoints():
    """Three arrangements, and the middle one is the new case.

    Inline (above 1410) it must not wrap: a shrinkable box whose content can
    wrap always wraps before anything else on the row gives up a pixel, which
    is what keeps the strip honest about its width. On a phone (below 560) it
    must not wrap either: there it is a one-row horizontal scroller.

    In between it has a full row and no escape valve -- it cannot scroll,
    because the unconditional `nav.tabs-group { overflow: visible }` beats the
    phone block's `overflow-x: auto` on source order. Measured at 771 once
    Watchlist made eight groups: the last tab ran 784 to 876 against a 771px
    window, off screen and unreachable.

    Written without the lower bound it also applied at 375, beat the phone's
    nowrap on specificity, and turned the scroller into three wrapped rows and
    a 288px header on an 812px screen. Both bounds are load-bearing."""
    assert "@media (min-width: 560px) and (max-width: 1410px)" in CSS
    band = CSS.split("@media (min-width: 560px) and (max-width: 1410px)", 1)[1]
    band = band[:band.index("\n}")]
    assert "flex-wrap: wrap;" in band
    # And the two arrangements either side of it still refuse to wrap.
    assert "flex-wrap: nowrap;" in CSS


def test_a_menu_near_the_right_edge_opens_leftwards():
    """`left: 0` anchors a 190px dropdown to its tab's left edge, which is
    fine until that tab is near the right edge. Measured at 900px once
    Watchlist became the eighth group: the menu ran 781 to 971 against a 900px
    window, and nothing could scroll to it.

    It did not happen before because the rightmost group was Optic's
    Positions, which held one view and rendered as a plain button with no menu
    at all. Giving the Roth planner a home in that group gave it a caret, and
    the answer stopped being `:last-child` -- see test_roth_view, where the
    strip wrapped and the last group became the first item on the second row.
    The rule is the same rule; what decides which tabs get it is measured now."""
    assert "nav.tabs-group > .nav-item.menu-right .nav-menu" in CSS
    rule = CSS.split("nav.tabs-group > .nav-item.menu-right .nav-menu", 1)[1]
    rule = rule[:rule.index("}")]
    assert "right: 0" in rule and "left: auto" in rule
