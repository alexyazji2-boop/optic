"""Portfolio scenarios (roadmap stage 6, 2026-10-22).

One engine (app/analytics/scenarios.py) revalues every position in full under each scenario, for the Optic
Portfolio books and a linked brokerage alike. Exposures are kept apart (premium at risk, notional,
delta-adjusted, concentration, correlation, convexity); multipliers are the position's own; a position that
cannot be priced is listed and left out, never guessed; a stale price is flagged; every figure is called
hypothetical and is never mixed with recorded performance.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app import main
from app.analytics import scenarios as SC
from app.analytics.position import _leg_value_model
from tests.test_frontend_v2_stage0 import V2, _run

NOW = datetime(2026, 10, 22, 17, 0, tzinfo=timezone.utc)      # 1pm ET, a Thursday
SPOT = {"AAA": {"price": 100.0, "as_of": NOW.isoformat()}, "BBB": {"price": 50.0, "as_of": NOW.isoformat()}}


def _closes(beta_b=2.0, n=300, seed=4):
    i = pd.bdate_range(end="2026-10-22", periods=n)
    rng = np.random.default_rng(seed)
    m = rng.normal(0, 0.01, n)
    spy = 500 * np.exp(np.cumsum(m))
    a = 100 * np.exp(np.cumsum(m + rng.normal(0, 0.012, n)))
    b = 50 * np.exp(np.cumsum(beta_b * m + rng.normal(0, 0.0005, n)))
    return {"SPY": pd.Series(spy, i), "AAA": pd.Series(a, i), "BBB": pd.Series(b, i)}


def _call(**kw):
    return {"symbol": "AAA", "kind": "option", "qty": 2, "option_type": "call", "strike": 100.0, "expiry": "2026-12-18",
            "price": 5.0, "multiplier": 100, "price_as_of": NOW.isoformat(), **kw}


def _group(out, gid):
    return {r["id"]: r for r in next(g for g in out["groups"] if g["id"] == gid)["rows"]}


def test_shares_move_one_for_one_and_the_market_moves_them_by_beta():
    out = SC.build([{"symbol": "AAA", "kind": "stock", "qty": 10, "price": 100.0},
                    {"symbol": "BBB", "kind": "stock", "qty": 20, "price": 50.0}], SPOT, _closes(), 0.04, NOW)
    t = _group(out, "together")
    assert t["all-10"]["pnl"] == -200.0 and t["all-10"]["option_pnl"] is None
    beta = {b["symbol"]: b["beta"] for b in next(g for g in out["groups"] if g["id"] == "market")["betas"]}
    assert beta["BBB"] == pytest.approx(2.0, abs=0.05)
    m = _group(out, "market")["spx-10"]
    assert m["pnl"] == pytest.approx(-(1000 * 0.1 * beta["AAA"]) - (1000 * 0.1 * beta["BBB"]), abs=0.05)
    assert "volatility" not in [g["id"] for g in out["groups"]], "no option, no volatility scenario"
    assert out["hypothetical"].startswith("Hypothetical") and "not recorded performance" in out["hypothetical"].lower()


def test_an_option_is_revalued_in_full_with_the_shared_pricer_and_its_convexity_shows():
    out = SC.build([_call()], SPOT, _closes(), 0.04, NOW)
    leg = SC._prepare(_call(), SPOT, 0.04, NOW)
    model = leg["model"]
    up = float(_leg_value_model(model, np.array([110.0]), leg["tau"], 0.04, 0.0)[0])
    base = float(_leg_value_model(model, np.array([100.0]), leg["tau"], 0.04, 0.0)[0])
    t = _group(out, "together")
    assert t["all+10"]["pnl"] == pytest.approx((up - base) * 200, abs=0.01)
    # a long call is long gamma: full revaluation beats the delta line both ways
    assert t["all+10"]["pnl"] > t["all+10"]["delta_estimate"] and t["all-10"]["pnl"] > t["all-10"]["delta_estimate"]
    assert _group(out, "volatility")["iv+5"]["pnl"] > 0 and _group(out, "time")["t1"]["pnl"] < 0
    assert model["american"] is True, "an equity option is priced American"
    assert out["exposure"]["premium_at_risk"] == 1000.0 and out["exposure"]["nonlinear"]["gamma_1pct"] > 0


def test_the_positions_own_multiplier_is_used_and_an_assumed_one_is_said():
    ten = SC.build([_call(multiplier=10)], SPOT, _closes(), 0.04, NOW)
    hundred = SC.build([_call()], SPOT, _closes(), 0.04, NOW)
    assert _group(ten, "together")["all+10"]["pnl"] == pytest.approx(_group(hundred, "together")["all+10"]["pnl"] / 10, abs=0.01)
    assumed = SC.build([_call(multiplier=None)], SPOT, _closes(), 0.04, NOW)
    assert assumed["coverage"]["multiplier_assumed"] == ["Long 2 AAA 100 calls 2026-12-18"]


def test_what_cannot_be_priced_is_listed_and_left_out_never_guessed():
    legs = [{"symbol": "BBB", "kind": "stock", "qty": 10, "price": 50.0},
            _call(price=None, label="no price"), _call(price=0.5, strike=80.0, label="below intrinsic"),
            _call(expiry="2026-10-16", label="expired"), _call(adjusted=True, adjusted_reason="Adjusted root AAA1.", label="adjusted"),
            _call(symbol="CCC", label="no quote")]
    out = SC.build(legs, SPOT, _closes(), 0.04, NOW)
    why = {u["label"]: u["reason"] for u in out["coverage"]["unpriced"]}
    assert set(why) == {"no price", "below intrinsic", "expired", "adjusted", "no quote"}
    assert "No implied volatility" in why["below intrinsic"] and why["adjusted"] == "Adjusted root AAA1."
    assert _group(out, "together")["all-10"]["pnl"] == -50.0, "only the shares are in the sums"
    assert out["coverage"]["priced"] == 1 and out["coverage"]["value_covered_pct"] < 100


def test_prices_from_different_times_are_flagged():
    old = (NOW - timedelta(days=3)).isoformat()
    out = SC.build([_call(price_as_of=old)], SPOT, _closes(), 0.04, NOW)
    assert out["coverage"]["stale"] and "an hour of trading apart" in out["coverage"]["stale"][0]["reason"]
    spots = {"AAA": {"price": 100.0, "as_of": (NOW - timedelta(days=5)).isoformat()}}
    out = SC.build([{"symbol": "AAA", "kind": "stock", "qty": 1, "price": 100.0}], spots, _closes(), 0.04, NOW)
    assert "more than a session old" in out["coverage"]["stale"][0]["reason"]


def test_premium_notional_and_delta_are_kept_apart_and_an_uncovered_call_is_named():
    legs = [{"symbol": "AAA", "kind": "stock", "qty": 50, "price": 100.0},
            _call(qty=-1, strike=110.0, price=1.5), _call(qty=1, option_type="put", strike=90.0, price=1.2)]
    e = SC.build(legs, SPOT, _closes(), 0.04, NOW)["exposure"]
    assert e["premium_at_risk"] == 120.0 and e["short_premium"] == 150.0
    assert e["uncovered_short_calls"] == [{"symbol": "AAA", "shares_uncovered": 50.0}]
    assert e["gross_notional"] == 5000 + 10000 + 10000
    assert e["net_notional"] == 5000 - 10000 - 10000, "a short call and a long put both count against the stock"
    assert 0 < e["delta_adjusted_net"] < 5000, "the short call and the put take delta off the shares"
    covered = SC.build(legs[:1] + [dict(legs[0], qty=60)] + legs[1:], SPOT, _closes(), 0.04, NOW)["exposure"]
    assert covered["uncovered_short_calls"] == []


def test_a_report_ahead_is_a_scenario_with_its_own_move_and_a_volatility_crush():
    earn = {"AAA": {"date": "2026-10-29", "move_pct": 6.0, "basis": "the median of its last 8 report-day moves"},
            "BBB": {"date": "2026-11-02"}}
    legs = [_call(), {"symbol": "BBB", "kind": "stock", "qty": 10, "price": 50.0}]
    out = SC.build(legs, SPOT, _closes(), 0.04, NOW, earnings=earn)
    rows = {r["symbol"]: r for r in next(g for g in out["groups"] if g["id"] == "earnings")["rows"]}
    assert rows["AAA"]["move_pct"] == 6.0 and rows["AAA"]["up"]["pnl"] > rows["AAA"]["down"]["pnl"]
    plain = SC.build(legs, SPOT, _closes(), 0.04, NOW, earnings={"AAA": dict(earn["AAA"], date="2027-01-30")})
    assert "earnings" not in [g["id"] for g in plain["groups"]], "a report outside the window is not a scenario"
    assert "Too few past reports" in rows["BBB"]["unavailable"]
    # the crush: an up move smaller than the volatility it takes out can lose money on a long call
    leg = SC._prepare(_call(), SPOT, 0.04, NOW)
    no_crush = SC._value(leg, 106.0, 8, 0, 1.0, 0.04, NOW) - leg["value"]
    assert rows["AAA"]["up"]["pnl"] < no_crush


def test_names_that_move_together_are_one_group_and_calm_correlation_is_not_protection():
    c = _closes()
    c["CCC"] = c["AAA"] * (1 + np.random.default_rng(9).normal(0, 0.0003, len(c["AAA"])))
    spots = dict(SPOT, CCC={"price": float(c["CCC"].iloc[-1]), "as_of": NOW.isoformat()})
    out = SC.build([{"symbol": s, "kind": "stock", "qty": 10, "price": 100.0} for s in ("AAA", "BBB", "CCC")], spots, c, 0.04, NOW)
    groups = out["exposure"]["correlated"]
    assert groups and groups[0]["names"] == ["AAA", "CCC"] and groups[0]["avg_correlation"] > 0.95
    assert "not protection" in out["exposure"]["correlated_note"]


def test_report_move_is_the_median_of_the_stocks_own_report_days():
    i = pd.bdate_range("2025-01-02", periods=300)
    s = pd.Series(100.0, i)
    jumps = {i[50]: 1.05, i[110]: 0.96, i[170]: 1.03, i[230]: 0.90}
    for d, f in jumps.items():
        s[s.index >= d] *= f
    dates = [str((d - pd.Timedelta(days=1)).date()) if d.dayofweek else str((d - pd.Timedelta(days=3)).date()) for d in jumps]
    got = SC.report_move(s, dates)
    assert got["reports"] == 4 and got["move_pct"] == pytest.approx(4.5, abs=0.1)
    assert SC.report_move(s, dates[:2]) is None, "two reports are too few to size a move"


def test_the_paper_endpoint_revalues_the_open_book(monkeypatch):
    from app import paper
    opens = [{"ticker": "AAA", "instrument": "shares", "direction": "long", "qty": 10, "entry_price": 95, "mark_price": 100},
             {"ticker": "AAA", "instrument": "option", "direction": "long", "qty": 2, "option_type": "call", "strike": 100,
              "expiry": "2026-12-18", "entry_price": 4, "mark_price": 5, "marked_at": datetime.now(timezone.utc).isoformat()}]
    monkeypatch.setattr(paper, "state", lambda *a, **k: {"open": opens})
    monkeypatch.setattr(main, "_scenario_market", lambda syms: (_closes(), {"AAA": {"price": 100.0, "as_of": datetime.now(timezone.utc).isoformat()}}, {}))
    monkeypatch.setattr(main.YF_PROVIDER, "profile", lambda s: {"sector": "Technology"})
    monkeypatch.setattr(main.rates_mod, "risk_free", lambda p: {"rate": 0.04})
    body = TestClient(main.app).get("/api/portfolio-scenarios?book=aggressive").json()
    assert body["available"] and body["coverage"]["priced"] == 2 and body["coverage"]["multiplier_assumed"] == []
    assert body["exposure"]["premium_at_risk"] == 1000.0 and body["version"] == SC.VERSION
    monkeypatch.setattr(paper, "state", lambda *a, **k: {"open": []})
    assert TestClient(main.app).get("/api/portfolio-scenarios").json()["available"] is False


def test_the_section_leads_with_the_answer_and_says_what_it_left_out(tmp_path):
    legs = [{"symbol": "AAA", "kind": "stock", "qty": 50, "price": 100.0}, _call(qty=-2, strike=110.0, price=1.5),
            _call(price=None, option_type="put", label="Long 2 AAA 100 puts (no price)")]
    out = SC.build(legs, SPOT, _closes(), 0.04, NOW)
    got = _run(tmp_path, f"""
      const S = await import('{(V2 / "js/ui/scenarios.js").as_posix()}');
      const D = await import('{(V2 / "js/core/dom.js").as_posix()}');
      print(JSON.stringify({{ full: D.toString(S.scenariosSection({json.dumps(out)})), loading: D.toString(S.scenariosSection(undefined)),
        none: D.toString(S.scenariosSection({{ available: false, reason: 'No open positions.' }})),
        err: D.toString(S.scenariosSection({{ error: 'That did not load.' }}, {{ retry: 'scenarios' }})) }}));
    """)
    f = got["full"]
    assert f.index("If every holding fell 10% together") < f.index("Delta-adjusted, net") < f.index("<table")
    for s in ("Hypothetical:", "the loss has no ceiling", "Left out of every figure", "no price", "Every holding −10%",
              "Options alone", "Delta alone says", "How this works", SC.VERSION):
        assert s in f, s
    assert "Revaluing every position" in got["loading"] and "No open positions." in got["none"]
    assert 'data-v2-retry="scenarios"' in got["err"]
    for page in ("pages/tracker.js", "pages/brokerage.js"):
        src = (V2 / "js" / page).read_text()
        assert "scenariosSection(" in src and "retry = {" in src
