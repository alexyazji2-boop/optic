"""Pass 2 round three (gauntlet D4, 2026-11-18): the research sheet printed from a desktop-width window.

The print block hid the rail but left the shell its two columns (the 256 px rail, then the page), so a print from any
window wider than the 860 px breakpoint laid the whole sheet into the rail's column: on the live copy `.sheet` measured
256 px wide at x 0 in print media at 1280 px, and the operator's PDF ran to four Letter pages of a narrow column with
one paragraph printed over another. The suite's export journey printed at the paper's own width, under the breakpoint,
where the shell is one column anyway, so it passed. This journey measures from a 1280 px window.
"""
from __future__ import annotations

import io

import pytest

from tests.e2e.fixtures import route_price_history
from tests.e2e.test_pass1_journeys import open_page, stock

WIDE = {"width": 1280, "height": 900}


def _pages(pdf: bytes) -> int:
    from pypdf import PdfReader
    return len(PdfReader(io.BytesIO(pdf)).pages)


@pytest.mark.parametrize("paper", ["Letter", "A4"])
def test_the_research_sheet_prints_at_full_width_from_a_wide_window(chrome, server, paper):
    ctx, page = open_page(chrome, server, level="advanced", viewport=WIDE)
    route_price_history(page)
    try:
        stock(page, server)
        page.goto(server["base"] + "/#/AAPL/sheet", wait_until="domcontentloaded")
        page.wait_for_selector("#main [data-sheet-print]:not([disabled])", timeout=60000)
        page.locator("#main article.sheet").wait_for(timeout=30000)
        page.wait_for_load_state("networkidle")
        page.emulate_media(media="print")
        box = page.evaluate("""() => { const s = document.querySelector('#main article.sheet').getBoundingClientRect();
          return {x: Math.round(s.x), w: Math.round(s.width), shell: getComputedStyle(document.querySelector('.shell')).display}; }""")
        assert box["w"] >= 600, "the sheet prints in the rail's column: {}".format(box)
        assert box["x"] < 40 and box["shell"] == "block", box
        # the paged output: no part of the sheet laid out wider than the page, and no more pages than the live sheet's two
        pdf = page.pdf(format=paper, print_background=True)
        assert pdf[:5] == b"%PDF-"
        assert _pages(pdf) <= 2, "the sheet ran to {} {} pages".format(_pages(pdf), paper)
        assert not page.errors
    finally:
        ctx.close()
