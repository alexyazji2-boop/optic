"""The session bar's disclosure is named for what it opens.

Reported from Home with no symbol loaded: "Hours & company with no company
loaded, fix this title and make it suitable for this feature". The button
opens the company block and the trading hours, and the company block is only
drawn for a loaded symbol on one of its own pages. Without it the panel is
the four sessions, the time zone and what this session means, so the button
says Market hours; with it, Hours & company, as before.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP = (ROOT / "static/app.js").read_text()


def test_the_label_follows_whether_the_company_is_in_the_panel():
    at = APP.index('id="ses-detail-btn"')
    button = APP[at:APP.index("</button>", at)]
    assert "${companyBlock ? 'Hours &amp; company' : 'Market hours'}" in button
    assert re.search(r">\s*Hours &amp; company\s*$", button) is None, "a fixed label is back"


def test_the_company_block_is_the_one_the_panel_draws():
    """The label reads the same variable the panel renders, so the two cannot
    disagree about whether a company is in it."""
    start = APP.index("const companyBlock = (tickerRelevant && (prof.name || prof.summary))")
    panel = APP[APP.index('<div class="ses-detail'):]
    assert start < APP.index('id="ses-detail-btn"')
    assert "${companyBlock}" in panel[:panel.index("</div>`;")]
