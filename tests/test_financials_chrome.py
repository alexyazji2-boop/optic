"""The Financials facet, and where a jump index goes on a page that has one.

Measured on NVDA at 1440x900: 6,261px and seven sections -- short interest,
the earnings record, the statements, recent filings, insider and institutional
activity, corporate actions, and segments and geography -- with no index, no
collapse and no panel chooser. The second-longest page in the Dossier after
Options, which has ten chips. Same omission as Read: `renderFinancialsView`
was not in the render pass.

With it: 3,300px, seven chips, and the two sections the tab is named for open.

Wiring it in found the ordering bug underneath. `afterOpticLoop` returns
`host.firstChild` on a view with no Optic loop, and until now every view with
an index had one, so the index landed below the ticker header by luck rather
than by rule. Financials has a header and no loop. Measured by swapping the
old function back in and rebuilding: Earnings and Investing were both putting
the index ABOVE `.sec-head` too -- the page named its sections before it said
which company they belonged to.
"""

from __future__ import annotations

import re

APP = open("static/app.js", encoding="utf-8").read()


def _chromed():
    body = APP.split("const CHROMED_VIEWS = [", 1)[1]
    return re.findall(r"'([a-z]+)'", body[:body.index("];")])


# ------------------------------------------------------------- the facet


def test_financials_is_in_the_render_pass():
    assert "financials" in _chromed()
    assert "['financials', () => renderFinancialsView]" in APP
    assert "case 'financials': renderFinancialsView = wrapped; break;" in APP


def test_it_opens_on_what_the_tab_is_named_for():
    body = APP.split("const PANELS_OPEN_BY_DEFAULT = {", 1)[1]
    body = body[:body.index("\n};")]
    m = re.search(r"financials:\s*\[(.*?)\]", body, re.S)
    assert m, "no financials entry"
    keys = re.findall(r"'([^']+)'", m.group(1))
    assert "financials" in keys, "the statements are the reason you are here"
    assert "segments and geography" in keys
    # And the reference sections are one click, not five screens.
    for shut in ("short interest", "recent sec filings", "corporate actions"):
        assert shut not in keys


def test_it_hides_nothing_by_mode():
    """Being in the pass runs `applyUiMode` on it for the first time. All three
    tables are empty, so Simple mode removes nothing from a page of published
    company facts and only the reader's own choice in the chooser can."""
    for table in ("PANELS_ADVANCED", "PANELS_DENSE", "PANELS_SIMPLE_HIDES"):
        body = APP.split("const {} = {{".format(table), 1)[1]
        body = body[:body.index("\n};")]
        m = re.search(r"financials:\s*\[(.*?)\]", body, re.S)
        assert m and not m.group(1).strip(), table


def test_its_late_sections_are_covered_by_the_observer():
    """`#fin-extras-host` and `#seg-host` are both filled by their own
    requests -- corporate actions from `loadExtras`, the segment tables from
    `loadSegments`, which reads SEC filings and is the slowest thing on the
    page. An index built at render time would name five of seven."""
    fn = APP.split("function renderFinancialsView(force) {", 1)[1].split("\n}\n", 1)[0]
    assert "fin-extras-host" in fn and "seg-host" in fn
    assert "financials" in _chromed(), "which is what puts it under the observer"


# --------------------------------------------------- where the index goes


def test_the_ticker_header_stays_above_the_index():
    """`.sec-head` names the company. Chrome that sorts above it reads as
    belonging to the application rather than to the security on screen."""
    fn = APP.split("function afterOpticLoop(host) {", 1)[1].split("\n}", 1)[0]
    assert "':scope > .sec-head'" in fn
    assert "head ? head.nextSibling : host.firstChild" in fn


def test_the_loop_still_wins_where_there_is_one():
    """The original rule and the reason for it are unchanged: on a view that
    leads with Optic's answer, the index is chrome for the evidence below it,
    not something to put above the answer."""
    fn = APP.split("function afterOpticLoop(host) {", 1)[1].split("\n}", 1)[0]
    assert "':scope > .pl-hero, :scope > .pl-block'" in fn
    assert fn.index(".pl-hero") < fn.index(".sec-head"), \
        "the loop is asked first or the header would displace it"
    assert "if (last) return last.nextSibling;" in fn
