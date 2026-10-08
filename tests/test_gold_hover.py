"""The gold hover pill, on the controls that need it.

Asked for on 2026-10-08 as "from now on, every time you hover over a button,
use [the 'Why the gap?' chip] as a reference, but change the color scheme to
the gold in the optic logo", then narrowed the same day: "dont do this for
every button, do it only for the ones necessary".
"""
from pathlib import Path

CSS = (Path(__file__).resolve().parent.parent / "static/styles.css").read_text()

HEAD = '  summary:not(:disabled):not([aria-disabled="true"]):hover,'


def _block(head):
    at = CSS.index(head)
    return CSS[at:CSS.index("}", at)]


def test_the_hover_is_opt_in_for_quiet_controls_and_skips_disabled_ones():
    rule = _block(HEAD)
    for sel in (".ask-pulse", ".pill", ".sec-chip", ".btn:not(.primary)", ".hm-more",
                ".rail nav.tabs-group .nav-top", ".brand"):
        assert "  %s:not(:disabled)" % sel in rule, sel
    assert "border-radius: var(--r-pill);" in rule
    assert "var(--hover-gold)" in rule and "color: var(--ink);" in rule
    assert "@media (hover: hover) {\n" + HEAD in CSS, "no sticky hover after a tap"


def test_not_every_button_takes_it():
    """The solid gold button, cards, tabs and toolbar glyphs keep their own hover."""
    rule = _block(HEAD)
    assert "\n  button:not(" not in rule and "[role=\"button\"]" not in rule
    for sel in (".btn.primary", ".ov-card", ".pulse-card", ".sec-tab", ".panel-toggle"):
        assert sel + ":not(" not in rule, sel
    assert '.btn.primary:not(:disabled):not([aria-disabled="true"]):hover {' not in CSS


def test_the_gold_is_the_marks_gold_and_holds_up_on_white():
    assert "--hover-gold: var(--asset-brand);" in CSS
    assert "--hover-gold: color-mix(in srgb, var(--asset-brand) 72%, var(--ink));" in CSS
    assert "--asset-brand: #d4b144;" in CSS


def test_nothing_moves_when_the_pointer_arrives():
    rule = _block(HEAD)
    assert "padding" not in rule and "border-width" not in rule and "margin" not in rule
    assert "box-shadow:" in rule


def test_bare_links_get_room():
    assert ":where(summary, .hm-more, .ht-more, .ht-rest, .foot-link, .cs-note-btn) {" in CSS


def test_the_hover_is_a_plain_fade_not_a_morph():
    """Asked for as "use a simpler animation when hovering over the text": the
    corners and the outline's spread do not animate. Only colour, wash and
    edge ease."""
    rule = _block(HEAD)
    eased = rule.split("transition:", 1)[1]
    assert "box-shadow" not in eased and "border-radius" not in eased
    base = _block('button, summary, [role="button"] {')
    assert "box-shadow" not in base and "border-radius" not in base


def test_a_one_line_disclosures_caret_sits_on_the_text_centre():
    assert "details.ind-explain > summary .cal-caret { align-self: center; margin-top: 0; }" in CSS


def test_the_rails_menu_arrows_sit_on_their_rows_centre():
    """Pinned 4px from the row's top, the arrow sat above "Markets" and the
    hover pill's outline made it plain: "center these arrows"."""
    assert ".rail nav.tabs-group .nav-caret { top: calc(50% - 2px);" in CSS


APP = (Path(__file__).resolve().parent.parent / "static/app.js").read_text()


def test_the_rails_rows_are_one_system():
    """Reported as "ALOT of inconsistencies": footer rows 38px against 42,
    18px glyphs against 16, a 14px gap where every other pair had 1px, the
    flyout's pages at 16.7px under 14.4px labels, and the current section a
    square box with a blue edge beside a gold hover pill."""
    assert ".rail .rail-foot .icon-btn > svg { width: 16px; height: 16px; }" in CSS
    assert "  height: auto;\n  min-height: 38px;" in CSS
    assert ".rail-toggle { position: relative; margin-top: 0; }" in CSS
    assert ".rail nav.tabs-group .nav-page { font-size: var(--t-body); color: var(--rail-ink); }" in CSS
    assert "background: var(--hover-gold, var(--accent));" in CSS, "one colour for 'you are here'"


def test_rail_tooltips_only_when_the_labels_are_hidden():
    fn = APP[APP.index("function syncRailTitles() {"):]
    fn = fn[:fn.index("\n}\n")]
    assert "if (tight && el.dataset.railTitle) el.setAttribute('title', el.dataset.railTitle);" in fn
    assert "else el.removeAttribute('title');" in fn
    assert "  labelNavSections(nav);\n  syncRailTitles();" in APP, "re-run after every nav paint"
    assert "gear.dataset.railTitle = open" in APP


def test_the_brand_sits_in_the_middle_of_its_hover_oval():
    """ "make sure the text is always in the center of the oval": the brand hugs
    its mark and wordmark with one padding on all four sides, and the rule under
    it is the nav's edge, so the hover cannot turn it gold or bend it."""
    rule = _block(".rail > .brand {\n  margin: 0;")
    assert "padding: calc(8px * var(--ui-scale));" in rule and "width: fit-content;" in rule
    assert "border-bottom" not in rule
    assert ".rail > .brand + nav.tabs-group {\n  border-top: 1px solid var(--ws-line);" in CSS
    assert "body.rail-tight .rail > .brand { width: 100%; }" in CSS

