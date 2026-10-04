"""Key stats on a stock's Overview.

The numbers a reader looks for first on any quote page: market cap, P/E both
ways, EPS both ways, dividend yield, the 52-week and day ranges, beta, volume.
All from the quote the page already loads; a figure the quote lacks is left
out rather than shown as a dash, so a fund's list is shorter than a company's.

Checked in a browser: AAPL listed thirteen, $4.87T and a 38.3 P/E among them;
SPY six, with no EPS or beta; both below Optic's read.
"""
from __future__ import annotations

from pathlib import Path

from app.providers import yf

ROOT = Path(__file__).resolve().parent.parent
APP = (ROOT / "static/app.js").read_text()
CSS = (ROOT / "static/styles.css").read_text()


def _fn(head):
    at = APP.index(head)
    return APP[at:APP.index("\n}\n", at) + 3]


def test_the_quote_carries_eps_both_ways():
    src = Path(yf.__file__).read_text()
    assert '"trailing_eps": _f(info.get("trailingEps")),' in src
    assert '"forward_eps": _f(info.get("forwardEps")),' in src


def test_the_panel_lists_only_what_the_quote_has():
    ks = _fn("function keyStatsHTML(q) {")
    for label in ("Market cap", "P/E (trailing)", "P/E (forward)", "EPS (trailing)", "EPS (forward)",
                  "Dividend yield", "52-week range", "Beta", "Volume"):
        assert f"['{label}'" in ks, label
    assert ".filter((r) => r[1] !== null);" in ks
    assert "if (!rows.length) return '';" in ks


def test_it_sits_below_optics_read():
    assert "    ${renderOpticPulse(d)}\n    ${keyStatsHTML(q)}\n" in APP
    assert ".ks-grid {" in CSS
