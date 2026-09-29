"""Settings on a phone: every control inside its box, and only the times scroll.

Reported from an iPhone with two screenshots of the Time zone panel: the whole
box scrolled sideways, and the picker ran out of its row. Measured at 390x844:
the picker was 401px wide in a 314px row, because a select's automatic minimum
width is its longest option, and the market hours table was 458px wide in a
panel whose content box is 351px. The panel carries `overflow-x: auto`, so
both made the whole panel scroll.

Measured the same way at 320, 360, 375, 390, 414 and 430 wide in all three
text sizes: nothing runs past its row, and no panel scrolls. The one control
that does not fit anywhere is Text size at 320 in Large, which now scrolls
inside itself rather than cut "Large" off. At 1280 the page matches the live
one: the picker is the same width to the pixel, and so are the controls.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
JS = (ROOT / "static/app.js").read_text()
CSS = (ROOT / "static/styles.css").read_text()


def rule(selector):
    """The declarations of every top-level rule whose selector is exactly this."""
    found = re.findall(r"(?m)^" + re.escape(selector) + r" \{([^}]*)\}", CSS)
    assert found, selector
    return "\n".join(found)


def test_the_times_scroll_on_their_own():
    settings = JS[JS.index("function renderSettings() {"):]
    settings = settings[:settings.index("\nfunction ")]
    hours = settings[settings.index("${hg('Market hours')}"):]
    assert hours.index('<div class="table-scroll"><table class="data narrow">') < 80
    assert "</table></div>" in hours[:400]


def test_the_picker_is_never_wider_than_its_row():
    """max-width caps a flex item's automatic minimum as well, so the phone
    gets a picker the width of its row. min-width: 0 would have done that too,
    and also shrunk the desktop picker from its longest option to 340px."""
    decls = rule(".settings-select")
    assert "max-width: 100%;" in decls
    assert "min-width" not in decls


def test_a_setting_name_is_never_wider_than_its_row():
    assert "min-width: min(220px, 100%);" in rule(".settings-label")


def test_a_segmented_setting_narrows_then_scrolls_rather_than_clip():
    """`.seg` is overflow: hidden, which is also what let it shrink below its
    buttons and cut the last one off. The threshold is in em so that it moves
    with the text size, and a scroller is the last resort."""
    assert "container-type: inline-size;" in rule(".settings-row")
    assert "overflow-x: auto;" in rule(".settings-row .seg")
    block = re.search(r"@container \(max-width: 14em\) \{(.*?)\n\}", CSS, re.S)
    assert block, "no em-based container query for the settings row"
    assert re.search(r"\.settings-row \.seg button \{ padding-left: var\(--space-2\); "
                     r"padding-right: var\(--space-2\); \}", block.group(1))


def test_account_buttons_wrap_inside_their_panel():
    assert "flex-wrap: wrap;" in rule(".set-row-act")
