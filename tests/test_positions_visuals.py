"""Positions, drawn: the book's money against its risk, the open trades, the record.

Asked for as "Positions: allocation, P&L contribution, health categories". Drawn
from what the Optic Portfolio and the Paper Desk already load:

* book-level risk: each name's share of the money beside its share of the risk,
  the pairs that move alike, and the sectors as shares of the whole book. The
  sectors were a bar centred on 50%, so a sector under half the book drew red
  and leftward, as if negative;
* the open trades' profit and loss, largest first;
* the monthly record, which was all three books pooled against one start under
  whichever book was selected (tests/test_books.py has the server half);
* the Paper Desk's record in R, oldest first.

Found doing it: an option marked from the model was never labelled "estimated"
(the server writes "Modelled (no live quote)", the page looked for "model"), and
the sector warning named "Unclassified", missing data, as a concentration.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from app.analytics import portfolio_risk
from tests.test_visual_primitives import _jsc as _prim

ROOT = Path(__file__).resolve().parent.parent
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc"

RISK = {"available": True, "names": 4, "gross_exposure": 40000, "window_sessions": 63, "option_positions": 1,
        "diversification_ratio": 1.3, "portfolio_vol_pct": 40, "weighted_avg_vol_pct": 52,
        "effective_positions": 3.6, "largest_weight_pct": 35, "top3_weight_pct": 90, "verdict": "x",
        "positions": [
            {"symbol": "TECL", "sector": "Technology", "weight_pct": 35.0, "risk_contribution_pct": 48.0},
            {"symbol": "AMD", "sector": "Technology", "weight_pct": 30.0, "risk_contribution_pct": 32.0},
            {"symbol": "XLU", "sector": "Utilities", "weight_pct": -25.0, "risk_contribution_pct": -4.0},
            {"symbol": "NEW", "sector": "Unclassified", "weight_pct": 10.0}],
        "top_pairs": [{"a": "TECL", "b": "AMD", "correlation": 0.81}, {"a": "AMD", "b": "XLU", "correlation": -0.2}],
        "sectors": [{"sector": "Utilities", "weight_pct": 25.0}, {"sector": "Technology", "weight_pct": 65.0},
                    {"sector": "Unclassified", "weight_pct": 10.0}]}

OPEN = [
    {"ticker": "AMD", "instrument": "option", "pnl": 463, "pnl_pct": 15.5, "mark_source": "Live chain mid",
     "entry_price": 29.77, "mark_price": 34.4},
    {"ticker": "PANW", "instrument": "option", "pnl": -268, "pnl_pct": -9, "mark_source": "Modelled (no live quote)",
     "entry_price": 29.88, "mark_price": 27.2},
    {"ticker": "TECL", "instrument": "shares", "pnl": -55, "pnl_pct": -0.8, "mark_source": "Last quote",
     "entry_price": 257, "mark_price": 254.95},
    {"ticker": "AMD", "instrument": "shares", "pnl": 35, "pnl_pct": 0.5, "mark_source": "Entry price",
     "entry_price": 646, "mark_price": 646},
]

MONTHS = [{"key": "2026-08", "realised_pnl": 1200, "return_pct": 1.2, "closed_count": 4},
          {"key": "2026-09", "realised_pnl": -300, "return_pct": -0.3, "closed_count": 3},
          {"key": "2026-10", "realised_pnl": 0, "return_pct": 0, "closed_count": 0}]


def _app(script):
    exe = JSC if os.path.exists(JSC) else shutil.which("jsc")
    if not exe:
        pytest.skip("no JavaScriptCore on this machine")
    src = """
      load('tests/support/browser_stubs.js');
      document.documentElement.style = document.documentElement.style || {};
      document.documentElement.style.setProperty = function () {};
      document.documentElement.style.removeProperty = function () {};
      try { load('static/charts.js'); load('static/app.js'); } catch (e) {}
      explainPolicy = function () { return 'on_demand'; };
      var RISK = %s, OPEN = %s, MONTHS = %s, R = {}, BUILT = {}, CAPT = {};
      vizMount = function (id, build, none) { BUILT[id] = { build: build, none: none }; };
      ['butterflyBars', 'rankBars', 'divergingBars', 'columnChart'].forEach(function (name) {
        this[name] = function (o) { (CAPT[name] = CAPT[name] || []).push(o); return { chart: name }; };
      });
      function build(id) { var b = BUILT[id]; return b ? b.build(600) : 'not mounted'; }
    """ % (json.dumps(RISK), json.dumps(OPEN), json.dumps(MONTHS)) + script + "\nprint('RESULT:' + JSON.stringify(R));"
    out = subprocess.run([exe, "-e", src], capture_output=True, text=True, timeout=60, cwd=str(ROOT))
    blob = out.stdout + out.stderr
    assert "RESULT:" in blob, blob[-2000:]
    return json.loads(blob.split("RESULT:", 1)[1].split("\n")[0])


# ------------------------------------------------------------ book-level risk

def test_the_money_and_the_risk_are_drawn_side_by_side():
    out = _app("""
      R.html = renderPortfolioRisk(RISK);
      mountBookRiskVisuals(RISK);
      build('viz-risk-split'); build('viz-risk-pairs'); build('viz-risk-sectors');
      R.split = CAPT.butterflyBars[0]; R.pairs = CAPT.rankBars[0]; R.sectors = CAPT.rankBars[1];
      R.brand = C.brand; R.s7 = C.s7;
    """)
    html, split = out["html"], out["split"]
    assert "TECL carries 48% of the risk on 35% of the money" in html
    assert "1 name without enough history is left out" in html
    assert "An option counts as one share of its stock per contract" in html
    assert [r["label"] for r in split["rows"]] == ["TECL", "AMD", "XLU"]
    xlu = split["rows"][2]
    assert xlu["left"] == 25.0 and xlu["right"] == 0, "a short's money is its size; a hedge offsets, drawn as none"
    assert dict(xlu["detail"])["Share of risk"] == "-4.0%, offsetting the rest"
    assert split["showValues"] is True and split["leftColor"] == out["brand"] and split["rightColor"] == out["s7"]
    assert out["pairs"]["max"] == 1 and out["pairs"]["rows"][0]["highlight"] is True
    assert "TECL and AMD move most alike: +0.81 over 63 sessions" in html


def test_sectors_are_shares_of_the_whole_book_not_a_bar_centred_on_half():
    out = _app("""
      R.html = renderPortfolioRisk(RISK);
      mountBookRiskVisuals(RISK);
      build('viz-risk-sectors');
      R.sectors = CAPT.rankBars[CAPT.rankBars.length - 1];
      R.src = renderPortfolioRisk.toString();
    """)
    assert "regimeBar" not in out["src"]
    rows = out["sectors"]["rows"]
    assert out["sectors"]["max"] == 100
    assert [r["label"] for r in rows] == ["Technology", "Utilities", "Unclassified"], "largest first"
    assert rows[0]["highlight"] is True and "Technology is 65% of the book" in out["html"]


def test_a_book_with_no_sector_data_says_so():
    out = _app("""
      RISK.sectors = [{ sector: 'Unclassified', weight_pct: 100 }];
      R.html = renderPortfolioRisk(RISK);
    """)
    assert "The data provider gives no sector for these names." in out["html"]
    assert 'id="viz-risk-sectors"' not in out["html"]


class _Provider:
    def __init__(self, n=120):
        rng = np.random.default_rng(7)
        idx = pd.date_range("2026-04-01", periods=n, freq="B")
        self.frames = {s: pd.DataFrame({"Close": 100 * np.cumprod(1 + rng.normal(0, 0.02, n))}, index=idx)
                       for s in ("AAA", "BBB")}

    def batch_history(self, symbols, period="6mo", interval="1d"):
        return {s: self.frames[s] for s in symbols if s in self.frames}

    def profile(self, symbol):
        return {}


def test_missing_sectors_are_not_a_concentration_and_options_are_counted():
    got = portfolio_risk.build(_Provider(), [
        {"ticker": "AAA", "qty": 10, "entry_price": 100, "instrument": "shares"},
        {"ticker": "BBB", "qty": 10, "entry_price": 100, "instrument": "shares"},
        {"ticker": "BBB", "qty": 1, "entry_price": 5, "instrument": "option"}])
    assert got["available"] and got["sectors"][0]["sector"] == "Unclassified"
    assert got["sector_warning"] is None, "missing data is not a sector a shock could hit"
    assert got["option_positions"] == 1


# ------------------------------------------------------------ open trades

def test_an_estimated_mark_says_so():
    out = _app("""
      R.notes = ['Modelled (no live quote)', 'Live chain mid', 'Entry price (chain mid)', 'Expired (intrinsic value)', null]
        .map(markNote);
      R.html = openPositionsPanel(OPEN);
    """)
    assert out["notes"] == [" · estimated", "", " · not yet marked", " · at expiry", ""]
    assert "now 27.20 · estimated" in " ".join(out["html"].split())


def test_open_trades_are_drawn_largest_gain_first():
    out = _app("""
      R.html = openPositionsPanel(OPEN);
      mountOpenPnl(OPEN);
      build('viz-trk-open');
      R.rows = CAPT.divergingBars[0].rows.map(function (r) { return [r.label, r.value]; });
      R.one = (function () { BUILT = {}; mountOpenPnl(OPEN.slice(0, 1)); return build('viz-trk-open'); })();
    """)
    assert "Up $175 across 4 open trades; AMD (option) is the largest at $463" in out["html"]
    assert out["rows"] == [["AMD opt", 463], ["AMD", 35], ["TECL", -55], ["PANW opt", -268]]
    assert out["one"] is None, "one trade is not a comparison"


# ------------------------------------------------------------ the record

def test_the_months_are_drawn_and_the_month_in_progress_is_not_counted():
    out = _app("""
      R.title = monthsTitle(MONTHS);
      mountTrackerMonths(MONTHS);
      build('viz-trk-months');
      var c = CAPT.columnChart[0];
      R.items = c.items.map(function (i) { return [i.label, i.value]; });
      R.last = c.items[2].detail; R.highlight = c.highlightLast; R.color = c.color; R.pos = C.pos;
    """)
    assert out["title"] == "1 of 2 finished months closed with a gain"
    assert out["items"] == [["Aug '26", 1200], ["Sep '26", -300], ["Oct '26", 0]]
    assert ["Status", "In progress"] in out["last"] and out["highlight"] is False
    assert out["color"] == out["pos"]


def test_the_paper_record_is_the_latest_thirty_oldest_first():
    out = _app("""
      paperBook = { open: [], closed: [] };
      for (var i = 0; i < 35; i++) paperBook.closed.push({ ticker: 'T' + i, r: i % 3 ? 1.5 : -1, pnl: 10, closed_at: null });
      paperBook.closed.push({ ticker: 'NOSTOP', r: null, pnl: 5 });
      mountPaperR();
      build('viz-paper-r');
      R.labels = CAPT.columnChart[0].items.map(function (x) { return x.label; });
      R.html = paperStatsHTML();
    """)
    assert len(out["labels"]) == 30 and out["labels"][0] == "T29" and out["labels"][-1] == "T0"
    assert "of 35 trades with a stop made more than they risked to lose; the latest 30 drawn" in out["html"]


# ------------------------------------------------------------ the primitives

def test_a_share_is_drawn_against_its_whole():
    out = _prim("""
      var root = rankBars({ width: 400, labelWidth: 90, max: 100, rows: [{ label: 'Tech', value: 50 }] });
      var bar = all(root, function (n) { return n.tag === 'rect' && n.attrs.fill !== 'transparent'; })[0];
      R.w = Number(bar.attrs.width);
      var free = rankBars({ width: 400, labelWidth: 90, rows: [{ label: 'Tech', value: 50 }] });
      R.free = Number(all(free, function (n) { return n.tag === 'rect' && n.attrs.fill !== 'transparent'; })[0].attrs.width);
    """)
    plot = 400 - 90 - 64
    assert out["w"] == pytest.approx(plot / 2) and out["free"] == pytest.approx(plot)


def test_a_short_list_of_two_sided_bars_prints_its_figures():
    out = _prim("""
      var root = butterflyBars({ width: 500, showValues: true, format: function (v) { return v + '%'; },
        rows: [{ label: 'A', left: 30, right: 45 }, { label: 'B', left: 70, right: 55 }] });
      R.labels = texts(root);
    """)
    for want in ("30%", "45%", "70%", "55%"):
        assert want in out["labels"], want
