"""Every open-by-default key has to name a panel that exists.

This has been the same bug four times, and it never looks like one. Matching
is `title.toLowerCase().includes(key)`, so a key that names nothing does not
raise, does not warn and does not log -- the panel simply opens closed, which
is indistinguishable from someone having chosen to close it.

The four:

  tracker   'the record' and 'how the ledger works' were renamed to "Optic
            Portfolio" and "How these positions are taken", so the view opened
            with the reader's own portfolio shut.
  brief     'morning desk' outlived the panel; the read moved into the hero.
  long      'close defence' is a panel on the Options tab, so on Investing it
            opened nothing.
  earnings  'earnings verdict' named no panel anywhere, on any tab.

This test is file-wide rather than per view, and that is a real limit worth
stating: it catches a key that matches no heading in the app at all, which is
three of those four. It cannot catch `close defence` -- a key naming a real
panel on the wrong tab -- because which headings a view renders is not
decidable from this file. Several views mount panels asynchronously into hosts
filled by other functions, so slicing per render function would fail honest
code rather than catch dishonest keys.

The per-view check is a browser run: switch to each view with a ticker loaded,
read `headingName` off every `.panel[data-panel-id] > h2`, and compare. That is
how all four of these were found.
"""

from __future__ import annotations

import re

APP = open("static/app.js", encoding="utf-8").read()


def _code():
    src = re.sub(r"/\*.*?\*/", " ", APP, flags=re.S)
    return re.sub(r"(?m)^\s*//.*$", " ", src)


def _defaults():
    code = _code()
    block = code[code.index("const PANELS_OPEN_BY_DEFAULT"):]
    block = block[:block.index("\n};")]
    out = {}
    for m in re.finditer(r"(\w+):\s*\[([^\]]*)\]", block):
        # Both quote styles. `"today's priority"` is double-quoted precisely
        # because it contains an apostrophe, and a single-quote-only pattern
        # tears it into fragments that then fail to match any heading -- which
        # is a false failure dressed as the exact bug this file is about.
        out[m.group(1)] = re.findall(r"'([^']*)'|\"([^\"]*)\"", m.group(2))
        out[m.group(1)] = [a or b for a, b in out[m.group(1)]]
    return out


def _headings():
    """Every string this app renders into a panel heading.

    Two shapes: `hg('Name')`, the glossary-wrapping helper most panels use, and
    a bare `<h2>Name` for the handful that do not. Lowercased once here so the
    comparison matches the runtime's own `includes` on a lowercased title."""
    code = _code()
    # Quote-aware, for the same reason the key reader is: `hg("Today's
    # priority")` is double-quoted around an apostrophe, and a pattern whose
    # character class excludes both quote marks stops dead at the apostrophe
    # and captures "Today". That produced a false failure naming the one key
    # that was fine.
    found = set()
    for a, b in re.findall(r"hg\(\s*'([^']*)'|hg\(\s*\"([^\"]*)\"", code):
        found.add(a or b)
    found |= set(re.findall(r"<h2[^>]*>([A-Z][^<${]{2,44})", code))
    return {h.strip().lower() for h in found if h.strip()}


def test_every_default_key_names_a_panel_the_app_renders():
    heads = _headings()
    assert len(heads) > 40, "heading extraction broke, not the keys"
    dead = {}
    for view, keys in _defaults().items():
        missing = [k for k in keys if not any(k in h for h in heads)]
        if missing:
            dead[view] = missing
    assert not dead, "open-by-default keys naming no panel: {}".format(dead)


def test_the_two_keys_that_were_dead_are_not_back():
    """Named, because a generic check that goes green on an empty list is not
    evidence that these two specifically were fixed."""
    defaults = _defaults()
    assert "earnings verdict" not in defaults.get("earnings", [])
    assert "close defence" not in defaults.get("long", [])


def test_a_view_that_opens_nothing_says_so_with_an_empty_list():
    """`roth: []` is a decision -- that page is a form, and a form whose
    sections are all open is a wall. An absent key would be the same thing by
    accident, so the entry exists and is empty."""
    assert "roth" in _defaults()
    assert _defaults()["roth"] == []
