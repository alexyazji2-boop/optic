"""Every figure on the Earnings tab says what it is, and three were wrong.

Asked for after Financials: "add definitions to the Earnings tab stats too".
The tiles and figure columns there are each explained as a whole label, by the
reader's knowledge mode, the way the key stats and the Financials tab are.

Working the definitions out from app/analytics/earnings.py found three figures
that were not what they would be defined as, fixed here:

* the move after a report measured the day after the reaction for every
  company reporting before the open: daily bars are stamped at midnight, so
  "the first session after the date" was the next day whenever the report
  came out. Checked on 2026-10-06 against JPM, which reports at 06:00: July's
  +2.50% report-day move showed as +1.17%, January's -4.19% as -0.97%;
* estimate revisions ran backwards for a company expected to lose money: an
  estimate improving from -0.50 to -0.40 read as a 20% cut;
* year-over-year growth from a loss had the wrong sign, as on Financials.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from app.analytics import earnings as E
from app.providers.yf import _report_timing

ROOT = Path(__file__).resolve().parent.parent
APP = (ROOT / "static/app.js").read_text()
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc"

D = {
    "ticker": "JPM",
    "next_report": {"date": "2026-10-14", "days_away": 8, "confirmed": True, "eps_consensus": 4.8,
                    "eps_low": 4.5, "eps_high": 5.1, "revenue_consensus": 4.5e10,
                    "revenue_consensus_label": "$45B", "revenue_low": 4.4e10, "revenue_high": 4.6e10},
    "surprise": {"available": True, "quarters": 4, "beat_rate_pct": 75, "avg_surprise_pct": 6.1,
                 "avg_abs_move_pct": 2.4, "avg_move_on_beat_pct": 1.1, "avg_move_on_miss_pct": -2.0,
                 "notes": [], "rows": [{"date": "2026-07-14", "eps_estimate": 4.5, "eps_reported": 5.0,
                                        "surprise_pct": 11.1, "next_day_move_pct": 2.5}]},
    "revisions": {"available": True, "direction": "rising", "note": "n", "caveat": "c",
                  "rows": [{"label": "Current quarter", "current": 4.8, "chg_30d_pct": 1.0,
                            "chg_90d_pct": 3.0, "analysts_up_30d": 4, "analysts_down_30d": 1}]},
    "growth": {"notes": [],
               "quarterly": [{"period": "2026-06-30", "revenue": 4.5e10, "revenue_yoy_pct": 5.0,
                              "net_income": 1.4e10, "net_income_yoy_pct": 8.0, "gross_margin_pct": 60,
                              "operating_margin_pct": 40}],
               "annual": [{"period": "2025", "revenue": 1.7e11, "revenue_yoy_pct": 4.0,
                           "net_income": 5.5e10, "net_income_yoy_pct": 6.0, "gross_margin_pct": 60,
                           "operating_margin_pct": 40}],
               "forward": [{"label": "Current quarter", "eps_avg": 4.8, "eps_growth_pct": 7,
                            "revenue_label": "$45B", "revenue_growth_pct": 5, "eps_analysts": 18}]},
    "implied": {"available": True, "implied_move_pct": 3.1, "dte": 10, "strike": 300, "atm_iv_pct": 24.0,
                "expiry": "2026-10-16"},
    "pricing": {"available": True, "stance": "fair", "implied_move_pct": 3.1, "baseline_move_pct": 3.0,
                "baseline_kind": "same-tenor", "baseline_sessions": 7, "ratio": 1.03, "note": "n",
                "caveat": "c"},
    "analyst": {"target_mean": 320, "target_low": 260, "target_high": 380, "upside_pct": 8,
                "buy_share_pct": 60, "analyst_count": 20, "buys": 12, "holds": 7, "sells": 1, "notes": [],
                "ratings": [{"period": "0m", "strong_buy": 5, "buy": 7, "hold": 7, "sell": 1, "strong_sell": 0}]},
    "verdict": {"headline": "h", "reasons": []},
    "latest_result": {"available": True, "just_reported": False},
    "extended_hours": {"available": False},
}

UPCOMING = ["EPS consensus", "Revenue consensus", "Implied move", "Beat rate", "Options imply",
            "Stock actually moves", "Ratio", "ATM implied vol", "EPS est.", "30d", "90d", "Analysts",
            "Average surprise", "Avg move after report", "Avg move on a beat", "Avg move on a miss",
            "EPS reported", "Surprise", "Move after", "Revenue", "YoY", "Net income", "Gross margin",
            "Op margin", "EPS growth", "Revenue est.", "Rev growth", "Mean analyst target",
            "Implied upside", "Buy share", "Split", "Period"]


def _jsc(script):
    exe = JSC if os.path.exists(JSC) else shutil.which("jsc")
    if not exe:
        pytest.skip("no JavaScriptCore on this machine")
    src = """
      load('tests/support/browser_stubs.js');
      document.documentElement.style = document.documentElement.style || {};
      document.documentElement.style.setProperty = function () {};
      document.documentElement.style.removeProperty = function () {};
      try { load('static/charts.js'); load('static/app.js'); } catch (e) {}
      var D = %s, R = {};
      STATE.ticker = 'JPM'; STATE.swing = {};
      securityHeader = function () { return ''; };
      keyStatsHost = function () { return ''; };
      hideTip = function () {};                 // the chart tooltip the stub page lacks
      views.earnings = { innerHTML: '' };
    """ % json.dumps(D) + script + "\nprint('RESULT:' + JSON.stringify(R));"
    out = subprocess.run([exe, "-e", src], capture_output=True, text=True, timeout=60, cwd=str(ROOT))
    blob = out.stdout + out.stderr
    assert "RESULT:" in blob, blob[-1500:]
    return json.loads(blob.split("RESULT:", 1)[1].split("\n")[0])


def _terms(html):
    found = re.findall(r'<dfn class="gloss-term" tabindex="0" data-def="([^"]*)">([^<]*)</dfn>', html)
    return [(label, d) for d, label in found]


def _render(patch="", policy="on_demand"):
    return _jsc("""
      explainPolicy = function () { return '%s'; };
      %s
      renderEarnings(D);
      R.html = views.earnings.innerHTML;
      R.defs = EARN_DEFS;
    """ % (policy, patch))


def test_every_figure_on_the_tab_explains_itself():
    out = _render()
    labels = [label for label, _ in _terms(out["html"])]
    for label in UPCOMING:
        assert label in labels, label
    assert ">Next session<" not in out["html"]


def test_a_fresh_result_explains_its_own_figures():
    out = _render("D.latest_result = {available: true, just_reported: true, beat: true, surprise_pct: 9,"
                  " eps_reported: 5, eps_estimate: 4.6, date: '2026-10-14', age_days: 0,"
                  " next_day_move_pct: null};"
                  " D.extended_hours = {available: true, kind: 'pre-market', move_pct: 2.1, price: 310};")
    labels = [label for label, _ in _terms(out["html"])]
    assert "Surprise" in labels and "Reaction" in labels


def test_the_figures_that_share_a_label_each_mean_their_own():
    """Two YoY columns per table, three tables with "EPS est."."""
    out = _render()
    terms = _terms(out["html"])
    yoy = {d for label, d in terms if label == "YoY"}
    assert len(yoy) == 4, "quarterly and annual, revenue and net income"
    est = {d for label, d in terms if label == "EPS est."}
    assert len(est) == 3, "revisions, history and forward each say which estimate"


def test_the_definitions_keep_the_glossarys_rules():
    banned = ("you should", "you want", "look for a", "buy when", "sell when", "a good sign that you")
    for key, body in _render()["defs"].items():
        assert body.count(".") >= 2 and len(body) >= 110, (key, body)
        assert "—" not in body, key
        for phrase in banned:
            assert phrase not in body.lower(), (key, phrase)


def test_the_definitions_say_how_each_figure_is_built():
    d = _render()["defs"]
    assert "before the open" in d["move_after"] and "after the close" in d["move_after"]
    assert "breakeven" in d["implied_move"] and "first expiry after" in d["implied_move"]
    assert "1.25" in d["pricing_ratio"] and "0.85" in d["pricing_ratio"]
    assert "within a week" in d["actual_move"] and "two years" in d["actual_move"]
    assert "exactly in line counts against it" in d["beat_rate"]
    assert "missed or only matched" in d["avg_move_miss"]
    assert "five quarters" in d["q_rev_yoy"] and "loss" in d["q_ni_yoy"]


def test_professional_leaves_them_plain():
    out = _render(policy="off")
    assert "data-def" not in out["html"]


# ------------------------------------------------------- the reaction session

def _bars(rows):
    idx = pd.to_datetime([d for d, _ in rows]).tz_localize("America/New_York")
    return pd.DataFrame({"Close": [c for _, c in rows]}, index=idx)


AFTER_HOURS = pd.Timestamp("2026-10-06 20:00", tz="America/New_York")   # sessions all closed
BARS = _bars([("2026-07-10", 100.0), ("2026-07-13", 100.0), ("2026-07-14", 102.5), ("2026-07-15", 103.7)])


def test_a_report_before_the_open_is_measured_on_its_own_day():
    """JPM, 14 July 2026, 06:00: +2.50% that day, shown as the next day's."""
    early = E._reaction_map(BARS, ["2026-07-14"], before_open={"2026-07-14"}, now=AFTER_HOURS)
    late = E._reaction_map(BARS, ["2026-07-14"], now=AFTER_HOURS)
    assert early["2026-07-14"] == pytest.approx(2.5)
    assert late["2026-07-14"] == pytest.approx(1.17, abs=0.01), "after the close is the next day, as before"


def test_a_session_still_trading_is_not_a_reaction_yet():
    bars = _bars([("2026-10-05", 100.0), ("2026-10-06", 101.0)])
    during = pd.Timestamp("2026-10-06 11:00", tz="America/New_York")
    after = pd.Timestamp("2026-10-06 16:30", tz="America/New_York")
    assert E._reaction_map(bars, ["2026-10-06"], before_open={"2026-10-06"}, now=during)["2026-10-06"] is None
    assert E._reaction_map(bars, ["2026-10-06"], before_open={"2026-10-06"}, now=after)["2026-10-06"] == 1.0
    assert E._reaction_map(bars, ["2026-10-05"], now=during)["2026-10-05"] is None


def test_the_feed_time_says_which_session_reacted():
    assert _report_timing(pd.Timestamp("2026-07-14 06:00", tz="America/New_York")) == "before_open"
    assert _report_timing(pd.Timestamp("2026-07-30 16:00", tz="America/New_York")) == "after_close"
    assert _report_timing(pd.Timestamp("2026-07-30 21:00", tz="UTC")) == "after_close"
    assert _report_timing(pd.Timestamp("2026-07-30 00:00", tz="America/New_York")) is None
    assert _report_timing("not a time") is None


def test_the_history_uses_the_timing():
    rows = [{"date": "2026-07-14", "timing": "before_open", "eps_estimate": 4.5, "eps_reported": 5.0,
             "surprise_pct": 11.1}]
    out = E._surprise_history(rows, BARS)
    assert out["rows"][0]["next_day_move_pct"] == pytest.approx(2.5)


# ------------------------------------------------------- the revisions' sign

def test_an_improving_loss_estimate_is_a_rise():
    est = {"eps_trend": {"0y": {"current": -0.40, "30daysAgo": -0.45, "90daysAgo": -0.50},
                         "+1y": {"current": -0.10, "30daysAgo": -0.12, "90daysAgo": -0.20}},
           "eps_revisions": {}}
    out = E._revisions(est)
    row = out["rows"][0]
    assert row["chg_90d_pct"] == pytest.approx(20.0), "-0.50 to -0.40 read as a 20% cut"
    assert out["direction"] == "rising"
    gain = E._revisions({"eps_trend": {"0y": {"current": 1.1, "30daysAgo": 1.0, "90daysAgo": 1.0}}, "eps_revisions": {}})
    assert gain["rows"][0]["chg_90d_pct"] == pytest.approx(10.0), "a positive estimate reads as before"


# ------------------------------------------------------- growth from a loss

def test_year_over_year_from_a_loss_is_not_a_percentage():
    fin = {"income_quarterly": {"periods": ["q5", "q4", "q3", "q2", "q1"],
                                "rows": {"Total Revenue": [110.0, 100, 100, 100, 100.0],
                                         "Net Income": [50.0, 10, 10, 10, -100.0]}},
           "income_annual": {"periods": ["2025", "2024"],
                             "rows": {"Total Revenue": [400.0, 380.0], "Net Income": [-20.0, 30.0]}}}
    out = E._growth(fin, {})
    q0 = out["quarterly"][0]
    assert q0["revenue_yoy_pct"] == pytest.approx(10.0)
    assert "net_income_yoy_pct" not in q0, "a loss of 100 becoming a profit of 50 read as -150%"
    a0 = out["annual"][0]
    assert a0["net_income_yoy_pct"] == pytest.approx(-166.7, abs=0.1), "a profit turning into a loss is a real fall"


def test_the_provider_keeps_when_each_report_came_out(monkeypatch):
    from app.providers import yf as yfmod
    p = yfmod.YFinanceProvider()
    frame = pd.DataFrame(
        {"EPS Estimate": [4.5, 2.6], "Reported EPS": [5.0, 2.8], "Surprise(%)": [11.1, 7.7]},
        index=pd.DatetimeIndex([pd.Timestamp("2026-07-14 06:00", tz="America/New_York"),
                                pd.Timestamp("2026-07-30 16:00", tz="America/New_York")]))
    monkeypatch.setattr(p, "_earnings_dates", lambda ticker: frame)
    rows = p.earnings_history("ZZTIME")
    assert [(r["date"], r["timing"]) for r in rows] == [("2026-07-14", "before_open"),
                                                         ("2026-07-30", "after_close")]


def test_each_tile_carries_its_own_definition_not_a_glossary_word():
    """"Beat rate" is also a glossary word, so a tile that lost its own
    definition would still be marked, with the general one."""
    out = _render()
    unescape = lambda s: s.replace("&#39;", "'").replace("&quot;", '"').replace("&amp;", "&")
    by_label = {}
    for label, d in _terms(out["html"]):
        by_label.setdefault(label, unescape(d))
    for label, key in (("Beat rate", "beat_rate"), ("Implied move", "implied_move"),
                       ("Ratio", "pricing_ratio"), ("Move after", "move_after"),
                       ("EPS consensus", "eps_consensus"), ("Buy share", "buy_share")):
        assert by_label[label] == out["defs"][key], label
