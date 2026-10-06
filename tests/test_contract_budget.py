"""The cost limit on the Options tab: finding what fits, not only hiding what does not.

Asked for as "for the options tab, allow the user to filter their capital, for
example how much the user is willing to risk in premium per contract. keep in
mind that not everyone has $3,000/contract of capital to work with".

A limit existed. It sat in the twelfth panel, collapsed, and three things kept
it from doing what was asked. Measured on the live chains, 2026-10-05:

* **It could only hide.** The ranker keeps its top six, and the limit was
  applied to those six. At $500 on META all six cost $2,430 to $3,272, so the
  panel said nothing fits; on NVDA it said the same while the chain held a $405
  call that suits the setup.
* **The headline lost its first half.** With nothing left, the plan's headline
  was the trigger clause on its own: "but only on a pullback in the stock to
  $719.56 – $725.05."
* **Nothing else on the tab listened.** The Setup at the top quoted "about
  30.00 per share", and the call/put and strategy cards ignored the limit and
  printed per-share figures as dollar amounts: "Max loss $659.20" on a
  cash-secured put whose most it can lose is $65,920 for one contract.
"""

from __future__ import annotations

import json
import math
import os
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from app.analytics import entry
from app.analytics import swing
from app.analytics.greeks import bs_price

ROOT = Path(__file__).resolve().parent.parent
APP = (ROOT / "static/app.js").read_text(encoding="utf-8")
MAIN = (ROOT / "app/main.py").read_text(encoding="utf-8")


# ------------------------------------------------------------- the chain

def _ncdf(x):
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def chain(spot=740.0, iv=0.35, step=5.0, expiries=(("2026-11-20", 46),),
          rate=0.04, spread_pct=2.0, oi=1500):
    """A priced chain: Black-Scholes mids and deltas, liquid, both sides.

    Priced rather than invented, so the ranker's repricing at the target agrees
    with the quotes the way it does on a real chain, and costs fall away from
    the money the way a reader's limit meets them."""
    rows = []
    for expiry, dte in expiries:
        tau = dte / 365.0
        k = math.floor(spot * 0.70 / step) * step
        while k <= spot * 1.35:
            for is_call in (True, False):
                price = float(bs_price(spot, np.array([k]), np.array([tau]),
                                       np.array([iv]), rate, 0.0, is_call)[0])
                d1 = (math.log(spot / k) + (rate + iv * iv / 2.0) * tau) / (iv * math.sqrt(tau))
                delta = _ncdf(d1) if is_call else _ncdf(d1) - 1.0
                mid = round(price, 2)
                if mid <= 0.05:
                    continue
                half = mid * spread_pct / 200.0
                rows.append({
                    "contract": "T%s%s%g" % (expiry, "C" if is_call else "P", k),
                    "expiry": expiry, "dte": dte, "tau": tau,
                    "strike": float(k), "is_call": is_call,
                    "bid": round(mid - half, 2), "ask": round(mid + half, 2), "mid": mid,
                    "spread_pct": spread_pct, "volume": 300, "open_interest": oi,
                    "iv": iv, "delta": delta, "gamma": 0.004, "theta": -0.3, "vega": 0.8,
                })
            k += step
    return pd.DataFrame(rows)


TARGET = {"available": True, "target_price": 780.0, "estimated_calendar_days": 14}


def cost(row):
    return row["entry_mid"] * 100.0


# -------------------------------------------------- the ranker and the limit

def test_without_a_limit_nothing_changes():
    """The default, and it stays the default."""
    frame = chain()
    plain = entry.rank_strikes(frame, 740.0, "up", TARGET)
    again = entry.rank_strikes(frame, 740.0, "up", TARGET, budget=None)
    assert [r["strike"] for r in plain] == [r["strike"] for r in again]
    assert all(entry.MIN_DELTA <= abs(r["delta"]) <= entry.MAX_DELTA for r in plain)
    assert not any(r["outside_band"] for r in plain)


def test_the_limit_is_a_filter_before_ranking_not_after():
    """The best contract the limit can place, ranked over the whole pool.

    Equivalent to ranking every contract without a limit and taking the first
    one that fits, which is what the old code could not do once the first six
    were all too dear."""
    frame = chain(spot=240.0, step=2.5)
    target = {"available": True, "target_price": 252.0, "estimated_calendar_days": 14}
    everything = entry.rank_strikes(frame, 240.0, "up", target, top_n=10_000)
    top_six = everything[:6]
    limit = min(cost(r) for r in top_six) - 1.0      # every one of the six too dear
    fits = [r for r in everything if cost(r) <= limit and (r["return_at_target_pct"] or 0) > 0]
    got = entry.rank_strikes(frame, 240.0, "up", target, budget=limit)
    assert all(cost(r) > limit for r in top_six), "the scenario needs the six all over"
    assert got, "the chain holds contracts under the limit and none was offered"
    assert all(cost(r) <= limit for r in got)
    if fits:
        assert got[0]["strike"] == fits[0]["strike"], "not the best of what fits"


def test_a_limit_below_the_band_stretches_to_the_floor_and_no_further():
    frame = chain()
    pool = entry._contract_pool(frame, "up", TARGET)
    d = pool["delta"].abs()
    in_band = pool[(d >= entry.MIN_DELTA) & (d <= entry.MAX_DELTA)]
    stretch = pool[(d >= entry.BUDGET_MIN_DELTA) & (d < entry.MIN_DELTA)]
    limit = (in_band["mid"].min() * 100.0 + stretch["mid"].min() * 100.0) / 2.0
    got = entry.rank_strikes(frame, 740.0, "up", TARGET, budget=limit)
    assert got, "contracts between the floor and the band fit and none was offered"
    assert all(entry.BUDGET_MIN_DELTA <= abs(r["delta"]) < entry.MIN_DELTA for r in got)
    assert all(r["outside_band"] for r in got), "each row has to say it is further out"
    cheaper_still = pool[(d < entry.BUDGET_MIN_DELTA) & (pool["mid"] * 100.0 <= limit)]
    assert not cheaper_still.empty, "the scenario needs lottery tickets under the limit"


def test_nothing_under_the_floor_is_offered_however_low_the_limit():
    frame = chain()
    pool = entry._contract_pool(frame, "up", TARGET)
    floor_cost = pool[pool["delta"].abs() >= entry.BUDGET_MIN_DELTA]["mid"].min() * 100.0
    assert entry.rank_strikes(frame, 740.0, "up", TARGET, budget=floor_cost - 1.0) == []


def test_a_limit_never_buys_a_contract_that_loses_at_the_target():
    """Cheap because it is far out, and far enough out that reaching the target
    still loses money. Not an entry at any price."""
    frame = chain()
    near = {"available": True, "target_price": 744.0, "estimated_calendar_days": 30}
    got = entry.rank_strikes(frame, 740.0, "up", near, budget=2_000.0)
    assert all((r["return_at_target_pct"] or 0) > 0 for r in got)


def test_cheapest_in_reach_is_measured_over_the_whole_pool():
    frame = chain()
    pool = entry._contract_pool(frame, "up", TARGET)
    d = pool["delta"].abs()
    want = pool[(d >= entry.BUDGET_MIN_DELTA) & (d <= entry.MAX_DELTA)]["mid"].min() * 100.0
    assert entry.cheapest_in_reach(frame, "up", TARGET) == pytest.approx(round(want), abs=1)


# ------------------------------------------------------------ the notes

def report(*costs, budget):
    return entry._apply_budget([{"strike": 100 + i, "cost_per_contract": c}
                                for i, c in enumerate(costs)], budget)


def test_refit_when_every_top_pick_was_over_says_the_plan_uses_what_fits():
    fitted = [{"strike": 120, "cost_per_contract": 450, "outside_band": False}]
    out = entry._refit_to_budget(report(900, 1200, budget=500), fitted, 500, 450)
    assert out["candidates"] == fitted and out["refit"] is True
    assert "best that cost $500 or less" in out["note"]


def test_refit_when_some_were_over_counts_them():
    fitted = [{"strike": 120, "cost_per_contract": 450, "outside_band": False}]
    out = entry._refit_to_budget(report(400, 900, 1200, budget=500), fitted, 500, 400)
    assert "2 of the 3 top picks" in out["note"]


def test_a_stretched_refit_says_why_it_is_cheaper():
    fitted = [{"strike": 130, "cost_per_contract": 300, "outside_band": True}]
    out = entry._refit_to_budget(report(900, budget=500), fitted, 500, 300)
    assert "further out" in out["note"] and "move further" in out["note"]


def test_nothing_fits_names_the_cheapest_and_the_gap():
    out = entry._refit_to_budget(report(2430, 3272, budget=500), [], 500, 1562)
    assert out["candidates"] == [] and out["cheapest"] == 1562
    assert "$500" in out["note"] and "$1,562" in out["note"]


def test_nothing_fits_with_cheap_contracts_says_why_instead_of_a_smaller_number():
    """Contracts under the limit exist and all lose at the target. "The
    cheapest is $405" under a $500 limit would read as the filter failing."""
    out = entry._refit_to_budget(report(900, budget=500), [], 500, 405)
    assert "$405" not in out["note"]
    assert "lose money even if the stock reached the target" in out["note"]


# ------------------------------------------------------------ the plan

def _history(n=320, spot=740.0):
    idx = pd.date_range("2025-01-01", periods=n, freq="B")
    close = np.linspace(spot * 0.8, spot, n) * (1 + 0.01 * np.sin(np.arange(n) / 5.0))
    close[-1] = spot
    return pd.DataFrame({"Close": close, "High": close * 1.012, "Low": close * 0.988,
                         "Open": close, "Volume": [2e6] * n}, index=idx)


def _plan(budget, spot=740.0, frame=None):
    from app.analytics import technicals as tech_mod
    hist = _history(spot=spot)
    return entry.build_plan(
        frame if frame is not None else chain(spot=spot), spot,
        {"stance": "bullish", "conviction": "moderate"}, tech_mod.analyse(hist), {},
        {"days_to_earnings": 60, "net_sentiment": 0.0, "articles": []},
        rate=0.04, div=0.0, history=hist, budget=budget)


def test_with_nothing_to_buy_the_headline_is_a_sentence():
    """The reported fragment: the trigger clause printed as the whole headline."""
    plan = _plan(1.0)
    assert plan["actionable"] and plan["recommended"] is None
    assert not plan["headline"].lower().startswith("but")
    assert plan["headline"] == plan["affordability"]["note"]


def test_with_a_contract_the_headline_still_carries_its_trigger():
    plan = _plan(None)
    assert plan["headline"].startswith("Buy the $")
    assert "but only on" in plan["headline"]


def test_the_plan_recommends_what_fits_when_its_top_picks_do_not():
    """The reported failure end to end: six top picks over the limit, a chain
    with contracts under it, and a plan that said nothing fits."""
    unlimited = _plan(None)
    top = unlimited["candidates"]
    assert len(top) >= 2
    limit = min(c["cost_per_contract"] for c in top) - 1.0
    plan = _plan(limit)
    best = plan["recommended"]
    assert best is not None, plan["affordability"]["note"]
    assert best["cost_per_contract"] <= limit
    assert plan["affordability"]["refit"] is True
    assert plan["headline"].startswith("Buy the $")


def test_the_ticket_never_walks_past_the_limit():
    """The contract was chosen because its mid fits. The order ticket works the
    price up toward the ask, and must stop at the reader's own figure.

    The limit is set a dollar above the chosen contract's mid, so the usual
    ceiling (halfway to the ask) is over it and the cap has to bind."""
    first = _plan(None)
    best = first["recommended"]
    limit = best["entry_mid"] * 100.0 + 1.0
    assert (best["entry_mid"] + (best["ask"] - best["entry_mid"]) * 0.5) * 100.0 > limit, \
        "the scenario needs the uncapped ceiling over the limit"
    plan = _plan(limit)
    order = plan["order_guidance"]
    assert plan["recommended"]["strike"] == best["strike"]
    assert order["never_pay_more_than"] * 100.0 <= limit + 1e-6
    assert order["limit_price"] <= order["never_pay_more_than"]
    assert order["never_pay_more_than"] >= plan["recommended"]["entry_mid"]
    assert "for about $" in plan["headline"]
    quoted = float(plan["headline"].split("(")[1].split(" for one")[0].replace("$", "").replace(",", ""))
    assert quoted <= limit, "the headline quotes more than the reader said they can spend"


# -------------------------------------------------------------- the ideas

def test_every_idea_carries_dollars_for_one_contract():
    csp = swing._for_one({"name": "Cash-secured put", "net_credit": 10.8,
                          "max_profit": 10.8, "max_loss": 659.2}, None)
    assert csp["risk_for_one"] == 65_920 and csp["credit_for_one"] == 1_080
    assert csp["fits_budget"] is None, "no limit, no verdict"
    call = swing._for_one({"name": "Long call", "net_debit": 35.83,
                           "max_profit": "unlimited", "max_loss": 35.83}, 500)
    assert call["cost_for_one"] == 3_583 and call["profit_for_one"] == "unlimited"
    assert call["fits_budget"] is False


def test_the_single_option_moves_out_to_what_the_limit_buys():
    frame = chain()
    expiry = "2026-11-20"
    atm = swing._single_idea(frame, 740.0, expiry, True, 0.50, "Long call (at-the-money)", "x")
    limit = atm["net_debit"] * 100.0 / 2.0
    got = swing._fit_single(atm, frame, 740.0, expiry, True, limit)
    assert got is not atm and got["sized_to_budget"] is True
    assert got["net_debit"] * 100.0 <= limit
    pool = swing._tradable(frame, True, expiry)
    near = pool["delta"].abs()
    fits = pool[(near >= entry.BUDGET_MIN_DELTA) & (pool["mid"] * 100.0 <= limit)]
    assert abs(got["net_delta"]) == pytest.approx(fits["delta"].abs().max(), abs=1e-3), \
        "not the one nearest the money that fits"
    assert "$" in got["rationale"] and "limit" in got["rationale"]


def test_a_single_option_that_fits_is_left_alone():
    frame = chain()
    atm = swing._single_idea(frame, 740.0, "2026-11-20", True, 0.50, "Long call", "x")
    assert swing._fit_single(atm, frame, 740.0, "2026-11-20", True, 1e9) is atm


def test_a_single_option_nothing_can_replace_is_kept_for_the_panel_to_report():
    frame = chain()
    atm = swing._single_idea(frame, 740.0, "2026-11-20", True, 0.50, "Long call", "x")
    assert swing._fit_single(atm, frame, 740.0, "2026-11-20", True, 1.0) is atm


def test_a_debit_spread_narrows_to_fit():
    frame = chain()
    expiry = "2026-11-20"
    wide = swing._spread_idea(frame, expiry, True, 0.55, 0.25, "Bull call spread", "why")
    pool = swing._tradable(frame, True, expiry)
    k = wide["legs"][0]["strike"]
    width = wide["legs"][1]["strike"] - k
    long_row = pool[pool["strike"] == k].iloc[0]
    # What each width from the same long leg costs, narrowest first. The limit
    # sits between the second narrowest and the original, so several widths fit
    # and "the widest that fits" is a real choice rather than the only one.
    widths = sorted(
        (float(r["strike"]) - k, (float(long_row["mid"]) - float(r["mid"])) * 100.0)
        for _, r in pool[(pool["strike"] > k) & (pool["strike"] <= k + width)].iterrows())
    assert len(widths) >= 3
    limit = (widths[1][1] + wide["net_debit"] * 100.0) / 2.0
    assert wide["net_debit"] * 100.0 > limit, "the scenario needs a spread over the limit"
    got = swing._fit_spread(wide, frame, expiry, True, limit)
    assert got is not wide and got["sized_to_budget"] is True
    assert got["net_debit"] * 100.0 <= limit
    long_leg, short_leg = got["legs"]
    assert long_leg["strike"] == k, "the long leg moved although spreads from it fit"
    want = max(w for w, c in widths if 0 < c <= limit)
    assert short_leg["strike"] - long_leg["strike"] == pytest.approx(want), \
        "not the widest spread the limit can buy"
    assert got["rationale"].startswith("Narrowed to fit your $%s limit" % format(limit, ",.0f"))


def test_a_debit_spread_moves_out_only_when_no_width_fits():
    frame = chain()
    expiry = "2026-11-20"
    wide = swing._spread_idea(frame, expiry, True, 0.55, 0.25, "Bull call spread", "why")
    pool = swing._tradable(frame, True, expiry)
    k = wide["legs"][0]["strike"]
    long_row = pool[pool["strike"] == k].iloc[0]
    nearest = pool[pool["strike"] > k].nsmallest(1, "strike").iloc[0]
    limit = (float(long_row["mid"]) - float(nearest["mid"])) * 100.0 - 1.0
    got = swing._fit_spread(wide, frame, expiry, True, limit)
    if got is wide:
        pytest.skip("nothing on this chain fits that low a limit")
    assert got["legs"][0]["strike"] > k and got["net_debit"] * 100.0 <= limit


def _wing_pairs(frame, expiry, sc, sp, lc, lp):
    calls, puts = swing._tradable(frame, True, expiry), swing._tradable(frame, False, expiry)
    taken = sc["mid"] + sp["mid"]
    out = []
    for _, cc in calls[(calls["strike"] > sc["strike"]) & (calls["strike"] <= lc["strike"])].iterrows():
        for _, pp in puts[(puts["strike"] < sp["strike"]) & (puts["strike"] >= lp["strike"])].iterrows():
            credit = taken - cc["mid"] - pp["mid"]
            loss = max(cc["strike"] - sc["strike"], sp["strike"] - pp["strike"]) - credit
            if credit > 0:
                out.append((credit, loss * 100.0))
    return out


def test_condor_wings_come_in_until_the_most_it_can_lose_fits():
    frame = chain()
    expiry = "2026-11-20"
    sc, lc = swing._pick(frame, True, expiry, 0.20), swing._pick(frame, True, expiry, 0.10)
    sp, lp = swing._pick(frame, False, expiry, 0.20), swing._pick(frame, False, expiry, 0.10)
    pairs = _wing_pairs(frame, expiry, sc, sp, lc, lp)
    losses = sorted(loss for _, loss in pairs)
    # Between the narrowest pair and the widest, so several pairs fit and the
    # one chosen has to be the one with the most credit.
    limit = losses[len(losses) // 2]
    assert sum(1 for _, loss in pairs if loss <= limit) >= 2
    out = swing._fit_wings(frame, expiry, sc, sp, lc, lp, limit)
    assert out is not None
    c, p, credit = out
    loss = max(c["strike"] - sc["strike"], sp["strike"] - p["strike"]) - credit
    assert loss * 100.0 <= limit and credit > 0
    assert sc["strike"] < c["strike"] <= lc["strike"] and lp["strike"] <= p["strike"] < sp["strike"]
    best = max(cr for cr, loss in pairs if loss <= limit)
    assert credit == pytest.approx(best), "not the largest credit that fits"


def test_the_strategy_list_marks_what_it_cannot_fit():
    frame = chain()
    ideas = swing.build_strategy_ideas(
        frame, 740.0, "bullish", {"regime": {"state": "positive"},
                                  "levels": {"put_wall": {"strike": 700.0}}},
        {"volatility": {"atr_pct": 2.0}}, budget=500.0)
    names = {i["name"]: i for i in ideas}
    assert names["Cash-secured put"]["fits_budget"] is False, "$70,000 of cash is not $500"
    assert names["Bull call spread"]["fits_budget"] is True
    assert names["Bull call spread"]["risk_for_one"] <= 500


def test_the_snapshot_hands_the_limit_to_every_builder():
    """Source contract, because the snapshot needs a live provider: the ideas
    used to be built with no limit at all, beside a plan that had one."""
    block = MAIN[MAIN.index("naked_ideas = swing.build_naked_ideas("):]
    block = block[:block.index("entry_plan = entry_mod.build_plan(")]
    assert block.count("budget=budget") == 2
    assert '"budget": budget if budget is not None and budget > 0 else None' in MAIN


# ------------------------------------------------------------- the page

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
    out = subprocess.run([exe, "-e", src], capture_output=True, text=True,
                         timeout=120, cwd=str(ROOT))
    blob = out.stdout + out.stderr
    assert "RESULT:" in blob, blob[-2000:]
    return json.loads(blob.split("RESULT:", 1)[1].split("\n")[0])


def test_a_typed_amount_is_read_the_way_people_write_it():
    out = _run("""
      ['$300', '300', '1,000', ' 250 ', '250.6', '', 'abc', '0', '-5', '2000000', '$']
        .forEach(function (t) { R[t] = parseBudgetInput(t); });
    """)
    assert out["$300"] == {"value": 300, "ok": True}
    assert out["1,000"]["value"] == 1000 and out[" 250 "]["value"] == 250
    assert out["250.6"]["value"] == 251, "whole dollars"
    assert out[""] == {"value": None, "ok": True}, "empty is how no limit is spelled"
    for bad in ("abc", "0", "-5", "2000000"):
        assert out[bad]["ok"] is False, bad
    assert out["$"] == {"value": None, "ok": True}


SETUP = """
  var d = {
    budget: 500, gex: {levels: {}},
    entry_plan: {actionable: true, stance: 'bullish', direction: 'long', conviction: 'moderate',
      recommended: {strike: 250, expiry: '2026-11-06', entry_mid: 4.05, capital_per_contract: 405},
      order_guidance: {limit_price: 4.06, never_pay_more_than: 4.07},
      affordability: {budget: 500, refit: true, note: 'The top picks cost more.'},
      entry_zone: {}, risk: {}, target: {}, headline: 'Buy the $250 call.', warnings: []},
    naked_ideas: [], strategy_ideas: []
  };
"""


def test_the_setup_carries_the_one_control_and_the_cost_for_one():
    out = _run(SETUP + """
      var html = renderSetup(d);
      R.control = html.indexOf('id="entry-budget"') >= 0;
      R.pills = (html.match(/data-entry-budget="/g) || []).length;
      R.on = /class="pill on"[^>]*data-entry-budget="500"/.test(html);
      R.forOne = html.indexOf('$406') >= 0;
      R.why = html.indexOf('The top picks cost more.') >= 0;
      d.gex = {error: 'No options chain available for X.'};
      R.noChain = renderSetup(d).indexOf('entry-budget') >= 0;
    """)
    assert out["control"] and out["pills"] == 6 and out["on"]
    assert out["forOne"], "one contract at the limit price is $406, not 4.06"
    assert out["why"], "a limit-chosen contract has to say why it was chosen"
    assert out["noChain"] is False, "no chain, nothing for the limit to act on"


def test_with_nothing_in_the_plan_the_setup_points_at_what_fits():
    out = _run(SETUP + """
      d.entry_plan.recommended = null;
      d.entry_plan.headline = 'Nothing that suits this setup costs $500 or less.';
      d.strategy_ideas = [{name: 'Bull call spread', fits_budget: true, risk_for_one: 465}];
      var html = renderSetup(d);
      R.points = html.indexOf('Bull call spread') >= 0 && html.indexOf('$465') >= 0;
      R.jump = html.indexOf('data-goto-panel="swing-ideas-multi"') >= 0;
      R.noCost = html.indexOf('Cost for one') < 0;
      d.strategy_ideas = [];
      R.none = renderSetup(d).indexOf('Nothing on this tab fits that limit') >= 0;
    """)
    assert out["points"] and out["jump"] and out["noCost"] and out["none"]


def test_the_limit_has_one_control_on_the_tab():
    """The strike panel used to carry the pills. It now carries the note and a
    way back to the control at the top, so the two cannot disagree."""
    out = _run(SETUP + """
      d.entry_plan.candidates = [];
      var html = renderEntryPlan(d.entry_plan, d);
      R.pills = (html.match(/data-entry-budget="/g) || []).length;
      R.back = html.indexOf('data-goto-budget') >= 0;
      R.note = html.indexOf('The top picks cost more.') >= 0;
    """)
    assert out["pills"] == 0 and out["back"] and out["note"]
    calls = [line for line in APP.splitlines()
             if "renderBudgetControl(" in line and "function renderBudgetControl" not in line]
    assert len(calls) == 1, calls


def test_cards_show_what_one_contract_puts_at_risk():
    out = _run("""
      var html = renderIdea({name: 'Cash-secured put', structure: 'short put (income)',
        expiry: '2026-11-20', dte: 46, rationale: 'r', legs: [],
        net_credit: 10.8, max_profit: 10.8, max_loss: 659.2, net_delta: 0.2,
        credit_for_one: 1080, profit_for_one: 1080, risk_for_one: 65920, cash_for_one: 67000});
      R.risk = html.indexOf('$65,920') >= 0;
      R.share = html.indexOf('$659.20 a share') >= 0;
      R.cash = html.indexOf('$67,000') >= 0;
      R.oldLabel = html.indexOf('Max loss') >= 0;
    """)
    assert out["risk"] and out["share"] and out["cash"]
    assert out["oldLabel"] is False


def test_ideas_over_the_limit_leave_the_cards_and_are_named():
    out = _run("""
      var d = {budget: 500};
      var ideas = [
        {name: 'Bull call spread', structure: 'vertical debit spread', expiry: 'x', dte: 1,
         rationale: '', legs: [], net_debit: 4.65, max_loss: 4.65, max_profit: 5.35,
         cost_for_one: 465, risk_for_one: 465, profit_for_one: 535, fits_budget: true, net_delta: 0.2},
        {name: 'Cash-secured put', fits_budget: false, risk_for_one: 65920}];
      var html = renderIdeaList(ideas, d, 'NONE');
      R.card = (html.match(/class="idea"/g) || []).length;
      R.named = html.indexOf('Cash-secured put ($65,920 at risk for one)') >= 0;
      ideas[0].fits_budget = false;
      R.empty = renderIdeaList(ideas, d, 'NONE').indexOf('Nothing here fits your $500 limit') >= 0;
      R.none = renderIdeaList([], d, 'NONE') === 'NONE';
    """)
    assert out["card"] == 1 and out["named"] and out["empty"] and out["none"]


def test_the_page_describes_the_limit_the_server_applied():
    """Changed while the request was in the air, the browser's figure is not the
    one the numbers on the page were built against."""
    out = _run("""
      R.server = appliedBudget({budget: 250});
      R.none = appliedBudget({budget: null});
      R.noPayload = appliedBudget(null);
    """)
    assert out["server"] == 250 and out["none"] is None and out["noPayload"] is None
