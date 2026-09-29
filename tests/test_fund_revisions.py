"""A fund has no analyst estimates, and the page said "Revisions: Unknown".

Asked as "why does it say this for QQQ", with a screenshot of the Charting
tab's Analysts widget. `_revisions` reports "unknown" for a symbol with no
estimate-revision history at all, and `momentum` read any direction that was
not rising or falling as "no clear revision trend": so QQQ, a fund with no
estimates to revise, came back available with a neutral revisions signal and
a "flat" read, and the widget printed the word. No history is now no signal,
which leaves QQQ's earnings momentum unavailable with its own reason, and the
widget says why a fund has nothing here.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from app.analytics import earnings as earnings_mod

ROOT = Path(__file__).resolve().parent.parent
RAW = (ROOT / "static/app.js").read_text()
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc"


class _Provider:
    def __init__(self, est=None):
        self.est = est or {}

    def estimates(self, ticker):
        return self.est

    def earnings_history(self, ticker, limit=10):
        return []

    def financials(self, ticker):
        return {}


def test_a_symbol_with_no_estimates_has_no_revisions_reading():
    out = earnings_mod.momentum(_Provider(), "QQQ")
    assert out["available"] is False, out
    assert "revision_direction" not in out


def test_a_flat_trend_is_still_a_reading():
    flat = {"eps_trend": {"0y": {"current": 5.0, "30daysAgo": 5.0, "90daysAgo": 5.0},
                          "+1y": {"current": 6.0, "30daysAgo": 6.0, "90daysAgo": 6.0}}}
    out = earnings_mod.momentum(_Provider(flat), "ABC")
    assert out["available"] is True and out["revision_direction"] == "flat"
    assert [s["read"] for s in out["signals"]] == ["flat"]


def _widget():
    start = RAW.index("function wsWidgetBody(id) {")
    end = RAW.index("\n}\n", start) + 2
    return RAW[start:end]


def _run(scenario):
    exe = JSC if os.path.exists(JSC) else shutil.which("jsc")
    if not exe:
        pytest.skip("no JavaScriptCore on this machine")
    prelude = r"""
function assert(v, m) { if (!v) throw new Error(m); }
function esc(s) { return String(s); }
function cap(s) { s = String(s); return s.charAt(0).toUpperCase() + s.slice(1); }
function fmt(v, d) { return Number(v).toFixed(d); }
function fmtPct(v, d) { return Number(v).toFixed(d) + '%'; }
function money(v, d) { return '$' + Number(v).toFixed(d); }
var STATE = { chartSymbol: 'QQQ', chartData: null };
"""
    src = prelude + _widget() + "\n(function () {\n" + scenario + "\n})(); print('TEST_OK');"
    out = subprocess.run([exe, "-e", src], capture_output=True, text=True, timeout=30)
    assert "TEST_OK" in out.stdout, out.stdout + out.stderr


def test_the_widget_explains_a_fund_and_never_prints_unknown():
    _run("""
      STATE.chartData = { quote: { quote_type: 'ETF' },
                          earnings_momentum: { revision_direction: 'unknown' } };
      var html = wsWidgetBody('analysts');
      assert(html.indexOf('Unknown') < 0, 'still prints Unknown: ' + html);
      assert(html.indexOf('A fund has no earnings') >= 0, 'says nothing about why: ' + html);
      STATE.chartData = { quote: { quote_type: 'EQUITY' }, earnings_momentum: {} };
      assert(wsWidgetBody('analysts').indexOf('No analyst data for this symbol.') >= 0);
      STATE.chartData = { quote: { quote_type: 'EQUITY', analyst_target: 200, price: 180 },
                          earnings_momentum: { revision_direction: 'rising' } };
      var stock = wsWidgetBody('analysts');
      assert(stock.indexOf('Revisions') >= 0 && stock.indexOf('Rising') >= 0, 'a real reading lost');
    """)
