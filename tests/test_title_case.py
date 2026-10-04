"""Every heading in title case.

Asked for as "capitalize all titles across the terminal", over "Claude usage"
and "Latest calls". Headings are written about three hundred ways, so each
h1, h2 and h3 is recased as it reaches the page rather than at each source.

Checked in a browser: Home read "What Matters Now", "Moved Most This Month";
Macro "Equal-Weight vs Cap-Weight (RSP / SPY)" with its muted "daily bars" left
alone; Settings "How Much to Show", "Report a Problem"; with the pane hidden,
where an animation frame never comes. A full pass over the page took 3ms.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
APP = (ROOT / "static/app.js").read_text()
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc"


def _fn(head):
    at = APP.index(head)
    return APP[at:APP.index("\n}\n", at) + 3]


def _cased(titles):
    exe = JSC if os.path.exists(JSC) else shutil.which("jsc")
    if not exe:
        pytest.skip("no JavaScriptCore on this machine")
    prelude = APP[APP.index("const TITLE_SMALL"):APP.index("function titleCase(")] + _fn("function titleCase(text) {")
    script = prelude + "print('RESULT:' + JSON.stringify(%s.map(titleCase)));" % json.dumps(titles)
    out = subprocess.run([exe, "-e", script], capture_output=True, text=True, timeout=60)
    assert "RESULT:" in out.stdout, (out.stdout + out.stderr)[-1500:]
    return json.loads(out.stdout.split("RESULT:", 1)[1].split("\n")[0])


def test_words_are_capitalised_and_small_ones_are_not():
    cases = {
        "Claude usage": "Claude Usage",
        "Latest calls": "Latest Calls",
        "Report a problem": "Report a Problem",
        "How much to show": "How Much to Show",
        "What's pulling hardest": "What's Pulling Hardest",
        "Valuation vs its own history": "Valuation vs Its Own History",
        "the read: what to do": "The Read: What to Do",
        "Options: a primer": "Options: A Primer",
    }
    assert _cased(list(cases)) == list(cases.values())


def test_hyphens_acronyms_symbols_and_numbers_are_kept():
    cases = {
        "Equal-weight vs cap-weight (RSP / SPY)": "Equal-Weight vs Cap-Weight (RSP / SPY)",
        "From 52-week high": "From 52-Week High",
        "Side-by-side": "Side-by-Side",
        "iShares 20+ Year Treasury Bond ETF (TLT)": "iShares 20+ Year Treasury Bond ETF (TLT)",
        "GEX. Dealer gamma exposure": "GEX. Dealer Gamma Exposure",
        "3m/10y curve": "3m/10y Curve",
        "P/E vs $SPY": "P/E vs $SPY",
    }
    assert _cased(list(cases)) == list(cases.values())


def test_every_heading_is_recased_as_it_arrives_and_not_on_a_frame():
    watch = APP[APP.index("(function watchHeadings() {"):]
    watch = watch[:watch.index("}());")]
    assert ".observe(document.body, { childList: true, subtree: true });" in watch
    assert "el.closest('h1, h2, h3')) || el" in watch, "a term or text put inside a heading recases it"
    assert "requestAnimationFrame" not in watch, "a background tab never gets one"
    walk = _fn("function titleCaseIn(root) {")
    assert "root.querySelectorAll('h1, h2, h3').forEach(titleCaseHeading);" in walk


def test_buttons_and_qualifiers_inside_a_heading_are_not_titles():
    skip = APP[APP.index("const TITLE_SKIP = "):].split("\n", 1)[0]
    for sel in ("button:not(.gloss-term)", ".th-plain", ".ask-pulse", "time"):
        assert sel in skip, sel
