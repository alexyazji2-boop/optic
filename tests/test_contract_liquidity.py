"""Contract selection never relaxes its liquidity test.

`rank_strikes` built a liquid pool and then, when fewer than four contracts
passed, ranked the whole side of the chain instead: a thin chain was answered
with the contracts the test had just excluded, and the plan's headline told a
reader to buy one. The ideas did the same through `_pick`. Now there is one
screen (app/analytics/quotes.py) and it only ever removes: fewer passing means
fewer candidates, none means an explicit "no contracts meet the liquidity
criteria", and a quote that cannot be traded at (missing, non-finite, zero or
negative, crossed) is never a candidate however active the contract.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from app import session as session_mod
from app.analytics import entry, quotes, setups, swing

ROOT = Path(__file__).resolve().parent.parent
ET = session_mod.ET
TARGET = {"available": True, "target_price": 110.0, "estimated_calendar_days": 14}


def chain(rows):
    """Calls on one expiry, with whatever quote each row is given."""
    out = []
    for i, r in enumerate(rows):
        base = {"contract": "ABC261120C%08d" % int(r.get("strike", 100 + i) * 1000),
                "expiry": "2026-11-20", "dte": 46, "tau": 46 / 365.0,
                "strike": float(r.get("strike", 100 + i)), "is_call": True,
                "bid": 2.0, "ask": 2.2, "last": 2.1, "volume": 500.0, "open_interest": 1000.0,
                "iv": 0.3, "delta": r.get("delta", 0.5), "gamma": 0.02, "theta": -0.03, "vega": 0.1}
        base.update(r)
        out.append(base)
    df = pd.DataFrame(out)
    df["mid"] = np.where((df["bid"] > 0) & (df["ask"] > 0), (df["bid"] + df["ask"]) / 2.0, df["last"])
    df["spread_pct"] = (df["ask"] - df["bid"]) / df["mid"] * 100.0
    return df


# ======================================================== the screen itself

def test_the_thresholds_are_the_ones_the_code_had():
    """Preserved, not re-tuned: the plan's 50 and 15%, the ideas' 20."""
    assert quotes.PLAN_MIN_ACTIVITY == 50 and quotes.MAX_SPREAD_PCT == 15.0
    assert quotes.IDEA_MIN_ACTIVITY == 20


@pytest.mark.parametrize("bid,ask,why", [
    (np.nan, 2.2, "no usable bid or ask"),
    (2.0, np.nan, "no usable bid or ask"),
    (0.0, 2.2, "no usable bid or ask"),
    (-1.0, 2.2, "no usable bid or ask"),
    (2.0, np.inf, "no usable bid or ask"),
    (2.5, 2.2, "a crossed market (bid above ask)"),
])
def test_an_untradeable_quote_is_never_a_candidate(bid, ask, why):
    df = chain([{"bid": bid, "ask": ask}, {"strike": 101.0}])
    pool, report = quotes.screen(df)
    assert list(pool["strike"]) == [101.0]
    assert report["dropped"][why] == 1


def test_mid_and_spread_come_from_the_bid_and_ask_not_the_last_trade():
    """The chain builders fall back to the last trade for the midpoint when a
    side is missing. A last price is a time in the past, not a market."""
    df = chain([{"bid": 1.0, "ask": 1.4, "last": 9.0}])
    df.loc[0, "mid"] = 9.0
    df.loc[0, "spread_pct"] = 1.0
    pool, _ = quotes.usable(df)
    assert pool["mid"].iloc[0] == pytest.approx(1.2)
    assert pool["spread_pct"].iloc[0] == pytest.approx(0.4 / 1.2 * 100.0)


def test_a_locked_market_is_usable_and_a_crossed_one_is_not():
    pool, _ = quotes.usable(chain([{"bid": 2.0, "ask": 2.0}, {"strike": 101.0, "bid": 2.1, "ask": 2.0}]))
    assert list(pool["strike"]) == [100.0]


def test_only_a_contract_known_to_be_100_shares_is_a_candidate():
    df = chain([{"strike": 100.0}, {"strike": 101.0, "contract": "ABC1261120C00101000"}])
    pool, report = quotes.usable(df)
    assert list(pool["strike"]) == [100.0]
    assert report["dropped"]["an adjusted contract whose size is not stated"] == 1
    stated = df.assign(multiplier=[100.0, 100.0])
    pool2, _ = quotes.usable(stated)
    assert list(pool2["strike"]) == [100.0, 101.0], "a stated 100 is a standard contract"
    odd = df.assign(multiplier=[100.0, 150.0])
    pool3, report3 = quotes.usable(odd)
    assert list(pool3["strike"]) == [100.0]
    assert report3["dropped"]["a non-standard contract size"] == 1


def test_quote_age_is_checked_only_where_the_feed_dates_quotes():
    df = chain([{"strike": 100.0}, {"strike": 101.0}])
    _, plain = quotes.usable(df)
    assert "not provided by this feed" in plain["quote_times"]
    noon = datetime(2026, 10, 6, 12, 0, tzinfo=ET)            # a Tuesday session
    fresh = pd.Timestamp(noon) - pd.Timedelta(minutes=2)
    stale = pd.Timestamp(noon) - pd.Timedelta(minutes=45)
    dated = df.assign(bid_time=[fresh, stale], ask_time=[fresh, fresh])
    pool, report = quotes.usable(dated, now=noon)
    assert list(pool["strike"]) == [100.0]
    assert report["dropped"]["a quote older than 20 minutes"] == 1
    evening = datetime(2026, 10, 6, 19, 0, tzinfo=ET)
    pool2, report2 = quotes.usable(dated, now=evening)
    assert len(pool2) == 2 and "last session's quotes" in report2["quote_times"]


def test_the_screen_says_what_it_cannot_promise():
    _, report = quotes.screen(chain([{}]))
    joined = " ".join(report["notes"])
    assert "estimate" in joined and "not a price anybody has offered" in joined
    assert "not that an order will fill" in joined


# ============================================== the ranked plan, never relaxed

def test_two_liquid_contracts_mean_two_candidates_not_the_whole_chain():
    rows = [{"strike": 100.0 + i, "delta": 0.5 - 0.02 * i,
             "open_interest": 1000.0 if i < 2 else 5.0, "volume": 1000.0 if i < 2 else 5.0}
            for i in range(8)]
    df = chain(rows)
    got = entry.rank_strikes(df, 100.0, "up", TARGET)
    assert {r["strike"] for r in got} <= {100.0, 101.0}
    assert got, "the two that pass are still ranked"


def test_none_liquid_is_an_explicit_state_and_nothing_is_recommended():
    from app.analytics import technicals as tech_mod
    rows = [{"strike": 100.0 + i, "delta": 0.5, "open_interest": 3.0, "volume": 2.0}
            for i in range(6)]
    df = chain(rows)
    idx = pd.date_range("2025-01-01", periods=320, freq="B")
    close = np.linspace(80, 100, 320)
    hist = pd.DataFrame({"Close": close, "High": close * 1.01, "Low": close * 0.99,
                         "Open": close, "Volume": [1e6] * 320}, index=idx)
    plan = entry.build_plan(df, 100.0, {"stance": "bullish", "conviction": "moderate"},
                            tech_mod.analyse(hist), {}, {"days_to_earnings": 60, "articles": []},
                            rate=0.04, div=0.0, history=hist)
    assert plan["recommended"] is None and plan["candidates"] == []
    assert plan["liquidity"]["reason"] == "illiquid"
    assert plan["headline"].startswith("No contracts meet the liquidity criteria")
    assert "6 calls considered" in plan["headline"]
    assert plan["order_guidance"] == {}


def test_the_ideas_do_not_borrow_an_excluded_leg():
    rows = [{"strike": 100.0, "delta": 0.5, "open_interest": 3.0, "volume": 2.0}]
    assert swing._pick(chain(rows), True, "2026-11-20", 0.5) is None
    good = chain([{"strike": 100.0, "delta": 0.5}])
    leg = swing._pick(good, True, "2026-11-20", 0.5)
    assert leg is not None and leg["mid"] == pytest.approx(2.1)


def test_the_setups_contract_list_counts_crossed_quotes():
    df = chain([{"strike": 100.0, "bid": 2.3, "ask": 2.2}, {"strike": 101.0}])
    out = setups.contracts_for(df, 100.0, True, {"min_oi": 0, "min_volume": 0}, None,
                               now=datetime(2026, 10, 6, 20, 0, tzinfo=timezone.utc))
    assert out["dropped"]["a crossed market (bid above ask)"] == 1
    assert [c["strike"] for c in out["contracts"]] == [101.0]
    assert "not provided by this feed" in out["quote_times"]


# ================================================================ the page

JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc"


def _run(script):
    exe = JSC if os.path.exists(JSC) else shutil.which("jsc")
    if not exe:
        pytest.skip("no JavaScriptCore on this machine")
    src = """
      load('tests/support/browser_stubs.js');
      try { load('static/charts.js'); load('static/app.js'); } catch (e) {}
      var R = {};
    """ + script + "\nprint('RESULT:' + JSON.stringify(R));"
    out = subprocess.run([exe, "-e", src], capture_output=True, text=True, timeout=120, cwd=str(ROOT))
    blob = out.stdout + out.stderr
    assert "RESULT:" in blob, blob[-2000:]
    return json.loads(blob.split("RESULT:", 1)[1].split("\n")[0])


def test_an_empty_plan_renders_its_reason_and_no_order_ticket():
    out = _run("""
      var p = {actionable: true, stance: 'bullish', conviction: 'moderate', direction: 'long',
        headline: 'No contracts meet the liquidity criteria: none of the 6 calls considered has x.',
        recommended: null, candidates: [], target: {}, order_guidance: {}, risk: {}, entry_options: [],
        entry_zone: {}, warnings: [], assumptions: [], iv_context: {},
        liquidity: {reason: 'illiquid', considered: 6, passed: 0, criteria: 'x',
                    dropped: {'open interest and volume both under 50': 6}, quote_times: 'not provided by this feed'},
        liquidity_notes: ['The midpoint is an estimate.']};
      var html = renderEntryPlan(p, {budget: null});
      R.reason = html.indexOf('No contracts meet the liquidity criteria') >= 0;
      R.noTicket = html.indexOf('Limit price') < 0 && html.indexOf('Candidate strikes, ranked') < 0;
      R.removed = html.indexOf('open interest and volume both under 50 (6)') >= 0;
      R.estimate = html.indexOf('The midpoint is an estimate.') >= 0;
    """)
    assert out["reason"] and out["noTicket"] and out["removed"] and out["estimate"]


def test_the_ranked_table_labels_its_midpoint_an_estimate():
    app = (ROOT / "static/app.js").read_text(encoding="utf-8")
    assert "<th>Mid, est. ($)</th>" in app
    assert "<th>Mid ($)</th>" not in app[app.index("function renderEntryPlan("):][:12000]
