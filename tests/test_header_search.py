"""The header box is not a combobox, and said it was.

Focusing `#ticker-input` opens the command palette -- that is the design, and
the comment beside it says why: "typing into two different search fields that
behave differently is the confusion the palette exists to end". The
consequence was never followed through. The box kept `role="combobox"`,
`aria-autocomplete="list"` and `aria-controls="ticker-results"`, kept a
`<ul id="ticker-results" role="listbox">`, and kept `attachTypeahead` wired to
both.

Traced in a browser: click the box, `focusin` fires, `openPalette('')` runs,
focus lands on `#cp-input` one frame later, and every keystroke after that
goes to the palette. `#ticker-input.value` stays empty. So the listbox had no
path that could open it, and a screen reader was told to expect suggestions
that cannot arrive.

The home page's box is the real combobox and is untouched: the focusin
handover tests `box.id !== 'ticker-input'`, so nothing hijacks it.
"""

from __future__ import annotations

import re

APP = open("static/app.js", encoding="utf-8").read()
HTML = open("static/index.html", encoding="utf-8").read()

BOX = HTML.split('id="ticker-input"', 1)[1].split(">", 1)[0]


def test_the_box_no_longer_claims_to_be_a_combobox():
    for lie in ('role="combobox"', "aria-autocomplete", "aria-controls",
                "aria-expanded"):
        assert lie not in BOX, lie


def test_it_says_what_it_actually_does():
    assert 'aria-haspopup="dialog"' in BOX, "focusing it opens a modal palette"
    assert "aria-label" in BOX
    assert "palette" in BOX.lower(), "and the label names it"


def test_the_listbox_that_could_not_open_is_gone():
    assert 'id="ticker-results"' not in HTML
    assert "attachTypeahead('ticker-input'" not in APP


def test_the_home_page_keeps_its_typeahead():
    """The one that works. `attachTypeahead`, `tickerMark` and the logo
    cascade are all still live through it -- this removed a caller, not a
    feature."""
    assert "attachTypeahead('home-input', 'home-results')" in APP
    assert "function attachTypeahead(inputId, listId) {" in APP
    assert 'id="home-results"' in APP, "rendered by the home page, not index.html"


def test_nothing_hijacks_the_home_box():
    """The asymmetry is the whole reason one keeps its list and one does
    not."""
    fn = APP.split("document.addEventListener('focusin', (evt) => {\n  if (paletteOpen) return;", 1)[1]
    fn = fn[:fn.index("\n});")]
    assert "box.id !== 'ticker-input'" in fn
    assert "home-input" not in fn


def test_the_box_still_carries_and_reloads_the_symbol():
    """It is not decoration. `switchView` writes the loaded symbol back into
    it so the header and the status line cannot disagree, and Load resubmits
    whatever is in it."""
    assert "box.value = STATE.ticker" in APP
    form = HTML.split('id="ticker-form"', 1)[1].split("</form>", 1)[0]
    assert 'type="submit"' in form and "Load" in form
