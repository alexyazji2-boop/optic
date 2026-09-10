"""Every CSS variable used without a fallback must actually resolve.

`background: var(--bg)` where nothing defines `--bg` is not an error anywhere:
the declaration is dropped, the element gets no background, and the page looks
almost right. It shipped that way on the dossier header, which is
`position: sticky` — so the panels scrolled straight through it and the company
name sat on top of the table underneath.

A `var(--x, fallback)` is deliberate and exempt: several rules here offer an
optional override with a sensible default. What this catches is the one without
a safety net.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _no_comments(text: str) -> str:
    """Comments removed.

    Not optional. The rule this file was written for now carries a comment
    naming the broken variable so nobody reintroduces it, and the first version
    of the check read that comment as a use and flagged itself. That is the
    fourth time in this codebase a source-reading test has matched its own
    explanation — CLAUDE.md records the first, in _spend_guard.
    """
    return re.sub(r"/\*.*?\*/", " ", text, flags=re.S)


STYLES = _no_comments((ROOT / "static" / "styles.css").read_text())
SCRIPTS = _no_comments("\n".join((ROOT / "static" / name).read_text()
                                 for name in ("app.js", "charts.js", "auth.js")))
INDEX = (ROOT / "static" / "index.html").read_text()


def _declared() -> set:
    """Every custom property this stylesheet assigns, wherever it sits.

    Not anchored to the line start: `.p-regular { --ses-hue: var(--s1); }` is a
    single line, and an earlier version of this check called five live variables
    orphans for that reason alone.
    """
    return set(re.findall(r"(--[a-z0-9-]+)\s*:", STYLES))


def _set_from_script() -> set:
    """Variables a script or an inline style provides at runtime.

    --topbar-h and --sechead-h are measured heights; --co-hue and --co-size are
    written into inline styles by the colour picker. None can be a static token.
    """
    return (set(re.findall(r"setProperty\(\s*['\"](--[a-z0-9-]+)", SCRIPTS))
            | set(re.findall(r"(--[a-z0-9-]+)\s*:", SCRIPTS))
            | set(re.findall(r"(--[a-z0-9-]+)\s*:", INDEX)))


def _used_without_fallback() -> set:
    """`var(--x)` with nothing after the name. `var(--x, y)` is exempt."""
    return set(re.findall(r"var\(\s*(--[a-z0-9-]+)\s*\)", STYLES))


def test_every_bare_variable_resolves():
    known = _declared() | _set_from_script()
    orphans = sorted(_used_without_fallback() - known)
    assert orphans == [], (
        "used with no fallback and never set, so the declaration is silently "
        "dropped: {}".format(orphans))


def test_the_sticky_dossier_header_is_opaque():
    """The specific failure this file was written for. A transparent sticky
    header is worse than none: the content underneath scrolls through it."""
    rule = STYLES.split(".sec-head {", 1)[1].split("}", 1)[0]
    assert "position: sticky" in rule
    background = re.search(r"background:\s*([^;]+);", rule)
    assert background, ".sec-head has no background at all"
    value = background.group(1).strip()
    assert value not in ("none", "transparent"), value
    name = re.match(r"var\(\s*(--[a-z0-9-]+)", value)
    if name:
        assert name.group(1) in (_declared() | _set_from_script()), name.group(1)


def test_the_check_would_have_caught_it():
    """A guard against the guard: if the extraction stops finding bare `var()`
    uses at all, this file passes for the wrong reason and forever."""
    assert len(_used_without_fallback()) > 30
    assert len(_declared()) > 50
