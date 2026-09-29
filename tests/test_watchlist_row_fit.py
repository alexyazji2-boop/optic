"""The watchlist row says what pressing it does, and fits the card it is in.

Two reports on the home page's watchlist. "make this button clearer to
analyze AMD", pointing at a cell reading "q..": the what-changed column's
placeholder, "quiet", cut to two letters, which looked like a control. And
"fix this last column of the watchlist when pulse is open": the signal ran off
the card's right edge and under the Pulse panel.

The second was the layout reading the window rather than the card. With Pulse
open a 1280px window still took the desktop layouts, the home board kept its
two-thirds split, and its rail came out 219px wide against a row of five fixed
columns totalling 340px. Measured in a browser after the fix: at 1280 the
board splits in two with Pulse shut exactly as before (650/325) and evenly
with it open (328/328); at 940 it is two columns shut and one open; no row
runs past its card at any of them, or at 375.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
RAW = (ROOT / "static/app.js").read_text()
CSS = (ROOT / "static/styles.css").read_text()
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc"


def _raw_fn(name):
    return re.search(r"^(?:async )?function " + name + r"\([^\n]*\) \{.*?^\}",
                     RAW, re.M | re.S).group()


def _js(prelude, names, scenario):
    exe = JSC if os.path.exists(JSC) else shutil.which("jsc")
    if not exe:
        pytest.skip("no JavaScriptCore on this machine")
    src = ("function assert(v, m) { if (!v) throw new Error(m); }\n" + prelude + "\n"
           + "\n".join(_raw_fn(n) for n in names)
           + "\n(function () {\n" + scenario + "\n})(); print('TEST_OK');")
    out = subprocess.run([exe, "-e", src], capture_output=True, text=True, timeout=30)
    assert "TEST_OK" in out.stdout, out.stdout + out.stderr


ROW = r"""
function esc(s) { return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/"/g, '&quot;'); }
function fmt(v, d) { return Number(v).toFixed(d); }
function fmtPct(v, d) { return (v >= 0 ? '+' : '') + Number(v).toFixed(d) + '%'; }
function signClass(v) { return v >= 0 ? 'up' : 'down'; }
function watchRemoveBtn(s) { return '<button data-watch-remove="' + s + '">x</button>'; }
var AMD = { available: true, symbol: 'AMD', price: 607.87, change_pct: -3.61, signal: 'bullish', changed: null };
"""


def test_the_row_says_analyze_and_the_placeholder_says_no_change():
    _js(ROW, ["watchRow"], """
      var html = watchRow(AMD, {});
      assert(html.indexOf('>quiet<') < 0, 'still says quiet');
      assert(html.indexOf('class="wl-quiet">No change<') >= 0, 'no No change');
      assert(/class="wl-go"[^>]*><span class="wl-go-word">Analyze<\\/span> \\u203a<\\/span>/.test(html),
             'no Analyze on the row: ' + html);
      assert(html.indexOf('aria-label="Analyze AMD: 607.87, -3.61% today, no change, bullish"') >= 0,
             'the row does not say what pressing it does to a screen reader');
      assert(html.indexOf('data-watch-open="AMD"') >= 0, 'the row no longer opens AMD');
    """)


def _block(start, css=CSS):
    i = css.index(start)
    depth, j = 0, css.index("{", i)
    while True:
        if css[j] == "{":
            depth += 1
        elif css[j] == "}":
            depth -= 1
            if depth == 0:
                return css[i:j + 1]
        j += 1


def test_the_row_layout_follows_the_card_not_the_window():
    assert "#hm-watch, .wv-panel { container-type: inline-size; }" in CSS
    narrow = _block("@container (max-width: 559px) {")
    assert "'sym price chg go' 'sym changed signal go'" in narrow
    assert ".wl-go { grid-area: go;" in narrow
    # The window-width version survives only where container queries do not
    # exist. Beside them it came later in the file, and its grid has no `go`
    # area, so it put the chevron on a line of its own.
    fallback = _block("@supports not (container-type: inline-size) {\n  @media (max-width: 559px)")
    assert ".wl-open" in fallback
    stray = re.findall(r"@media \(max-width: 559px\) \{\s*\.wl-open", CSS)
    assert len(stray) == 1, "a second, unguarded phone rule for the row"


def test_the_columns_and_the_header_agree():
    cols = re.search(r"--wl-cols: ([^;]+);", CSS).group(1).split()
    header = re.search(r'<div class="wv-cols" aria-hidden="true">(.*?)</div>', RAW, re.S).group(1)
    assert len(cols) == 6 and header.count("<span") == 6, (cols, header)
    assert '<section class="panel wv-panel">' in RAW


def test_the_home_board_splits_on_its_own_width():
    assert "#hm-market { container-type: inline-size; container-name: hm-market; }" in CSS
    assert "@container hm-market (min-width: 672px)" in CSS
    assert "@container hm-market (min-width: 1012px)" in CSS
    guarded = _block("@supports not (container-type: inline-size) {\n  @media (min-width: 940px)")
    assert "@media (min-width: 1280px)" in guarded
    loose = re.findall(r"^@media \(min-width: (?:940|1280)px\) \{\s*\.hm-board", CSS, re.M)
    assert not loose, "the window-width split still runs beside the container one"
