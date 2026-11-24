"""Pass 2, item 1 (2026-11-17): one look for loading, empty, stale and failed, held by a test.

ui/states.js draws the four states. Before this pass, eleven places wrote the failed block by hand (`<div class="state
err" role="alert">...`), each with its own heading, its own retry wiring or none, and in two cases the raw error
message of the browser. Read as text, the way the suite reads the front end's other contracts (CLAUDE.md): every page
and component draws a failed block through states.failed, and says "did not load" in the house words.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "static" / "v2" / "js"
SOURCES = sorted(p for p in ROOT.rglob("*.js") if p.name != "states.js")


def _rel(p: Path) -> str:
    return str(p.relative_to(ROOT))


def test_no_page_writes_the_failed_block_by_hand():
    offenders = [(_rel(p), i + 1) for p in SOURCES for i, line in enumerate(p.read_text().splitlines())
                 if re.search(r"class=\"state err\"", line)]
    assert not offenders, "draw it with states.failed: " + ", ".join("{}:{}".format(f, n) for f, n in offenders)


def test_could_not_load_is_said_in_the_house_words():
    offenders = [(_rel(p), i + 1) for p in SOURCES for i, line in enumerate(p.read_text().splitlines())
                 if re.search(r"[`'\"]Could not load", line)]
    assert not offenders, "say 'did not load': " + ", ".join("{}:{}".format(f, n) for f, n in offenders)


def test_every_page_that_draws_a_failed_block_takes_it_from_states():
    missing = []
    for p in SOURCES:
        s = p.read_text()
        if re.search(r"\bfailed\(", s) and "states.js" not in s and not re.search(r"(function|const|let)\s+failed\b", s):
            missing.append(_rel(p))
    assert not missing, "import failed from ui/states.js: " + ", ".join(missing)


def test_the_failed_block_can_carry_its_own_heading_and_a_retry():
    s = (ROOT / "ui" / "states.js").read_text()
    assert re.search(r"export const failed = \(what, err, \{[^}]*retry[^}]*title[^}]*\}", s) or \
        re.search(r"export const failed = \(what, err, \{[^}]*title[^}]*retry[^}]*\}", s)
