"""Options and the position builder (backlog task 6, 2026-10-20).

The server side runs on the fake Black-Scholes chain of test_options_research_api, with stale quotes added
where a case needs them; the page's wiring is read as text. The page itself was driven in headless Chrome at
360, 390, 430, 844x390, 768 and 1440 px against the Friday 2026-10-09 AAPL chain
(~/Optic/work/v2-backlog/opt_check.py: templates, the stepper, Add from the chain, a visit away and back,
an expiry change, stale and missing quotes).
"""
import datetime as dt

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

import app.main as m
from app import rates
from app.analytics import liquidity, position, vol_surface as vs
from tests.test_frontend_v2_stage0 import V2
from tests.test_options_research_api import FakeProvider, _chain, R, SPOT

PAGE = (V2 / "js/pages/options.js").read_text()


class StaleProvider(FakeProvider):
    """The fake chain with the 80 call quoted far under what exercising it pays, as the free feed serves
    overnight (the AAPL 105 call at a mid of 163 with the stock at 343, 2026-10-20)."""

    def options_chain(self, t, expiries=None, max_expiries=4):
        ch = _chain(expiries or self.listed[:max_expiries])
        k = (ch.strike == 80.0) & ch.is_call
        ch.loc[k, "bid"] = 4.0
        ch.loc[k, "ask"] = 4.5
        return ch


@pytest.fixture
def client(monkeypatch):
    today = pd.Timestamp.now(tz="America/New_York").normalize()
    listed = [str((today + pd.Timedelta(days=d)).date()) for d in (3, 10, 31, 66)]
    fake = StaleProvider(listed)
    monkeypatch.setattr(m, "PROVIDER", fake)
    monkeypatch.setattr(m, "YF_PROVIDER", fake)
    monkeypatch.setenv("RISK_FREE_RATE", str(R))
    rates.reset_cache()
    yield TestClient(m.app), listed
    rates.reset_cache()


# ---------------- quotes ----------------

def test_a_quote_under_intrinsic_is_stale_not_a_market():
    exp = str((pd.Timestamp.now(tz="America/New_York").normalize() + pd.Timedelta(days=31)).date())
    ch = _chain([exp])
    k = (ch.strike == 80.0) & ch.is_call
    ch.loc[k, "bid"], ch.loc[k, "ask"] = 4.0, 4.5
    out = vs.resolve_surface(ch, SPOT, R, 0.0)
    row = out[k].iloc[0]
    assert row["quote_state"] == "below_intrinsic"
    assert np.isnan(row["quote_mid"]) and np.isnan(row["spread_pct"])
    fine = out[(out.strike == 100.0) & out.is_call].iloc[0]
    assert fine["quote_state"] == "two_sided" and fine["quote_mid"] > 0
    g = liquidity.grade_row(row.to_dict())
    assert g["grade"] == "not_tradable" and "exercising" in g["reasons"][0]


def test_research_gives_a_stale_contract_no_mid_and_calls_it_untradable(client):
    c, listed = client
    got = c.get("/api/options/TEST/research", params={"include_unquoted": True, "expiry": listed[2]}).json()
    row = next(r for r in got["table"]["rows"] if r["strike"] == 80.0)
    assert row["mid"] is None and row["liquidity"]["grade"] == "not_tradable"
    assert got["fetched_at"], "the page says when the quotes were read"


def test_a_two_sided_quote_too_wide_to_cross_is_called_that():
    g = liquidity.grade_row({"quote_state": "two_sided", "spread_pct": 60.0, "spread_abs": 0.6, "quote_mid": 1.0,
                             "open_interest": 5000, "volume": 100})
    assert g["grade"] == "not_tradable" and g["label"] == "Too wide to trade"
    assert liquidity.grade_row({"quote_state": "no_quote"})["label"] == "No usable quote"


# ---------------- the position's figures ----------------

def _leg(kind, side, k, tau, mid, qty=1):
    return {"type": kind, "side": side, "qty": qty, "strike": float(k), "expiry": "x%.3f" % tau, "tau": tau,
            "iv": 0.3, "mid": mid, "bid": mid - 0.05, "ask": mid + 0.05}


def test_a_breakeven_is_where_the_payoff_crosses_not_every_point_at_zero():
    x = np.linspace(90, 110, 21)
    y = np.array([-2.0] * 5 + [0.0] * 11 + [3.0] * 5)
    got = position._roots(x, y)
    assert got == [pytest.approx(100.0)], got
    assert position._roots(x, np.where(x < 100, -1.0, 1.0)) == [pytest.approx(99.5)]
    assert position._roots(x, np.abs(x - 100) + 1) == []


def test_two_short_near_calls_against_one_long_far_call_lose_without_limit():
    legs = [_leg("call", "short", 100, 30 / 365, 3.0, qty=2), _leg("call", "long", 100, 90 / 365, 6.0)]
    out = position.analyse(legs, SPOT, R, 0.0)
    assert out["max_loss_unbounded"] is True and out["max_loss"] is None
    assert out["calendar"] is True


def test_an_ordinary_calendar_is_still_bounded():
    legs = [_leg("call", "short", 100, 30 / 365, 3.0), _leg("call", "long", 100, 90 / 365, 6.0)]
    out = position.analyse(legs, SPOT, R, 0.0)
    assert out["max_loss_unbounded"] is False and out["max_profit_unbounded"] is False
    assert out["bounds_note"], "a calendar's extremes are within the drawn prices"


def test_quotes_that_cannot_lose_are_said_to_be_stale():
    # a bull call spread opened for a credit: no real market offers that
    legs = [_leg("call", "long", 90, 30 / 365, 1.0), _leg("call", "short", 100, 30 / 365, 3.0)]
    out = position.analyse(legs, SPOT, R, 0.0)
    assert out["cannot_lose_at_quotes"] is True and "stale" in out["quotes_note"]
    ok = position.analyse([_leg("call", "long", 100, 30 / 365, 3.0)], SPOT, R, 0.0)
    assert ok["cannot_lose_at_quotes"] is False and ok["quotes_note"] is None


def test_the_same_contract_bought_and_sold_is_refused(client):
    c, listed = client
    leg = {"type": "call", "strike": 100, "expiry": listed[2], "qty": 1}
    r = c.post("/api/options/TEST/analyze", json={"legs": [dict(leg, side="long"), dict(leg, side="short")]})
    assert r.status_code == 422 and "both bought and sold" in r.json()["detail"]


def test_analysis_says_when_its_quotes_were_read(client):
    c, listed = client
    got = c.post("/api/options/TEST/analyze", json={"legs": [{"type": "call", "side": "long", "strike": 100, "expiry": listed[2], "qty": 1}]}).json()
    assert got["fetched_at"] and got["cannot_lose_at_quotes"] is False


def test_an_ex_dividend_date_already_past_is_no_assignment_warning(client, monkeypatch):
    c, listed = client
    body = {"legs": [{"type": "call", "side": "short", "strike": 90, "expiry": listed[2], "qty": 1}]}
    gone = (dt.date.today() - dt.timedelta(days=3)).isoformat()
    monkeypatch.setattr(m, "_ex_dividend", lambda sym: gone)
    flags = c.post("/api/options/TEST/analyze", json=body).json()["flags"]
    assert not any("ex-dividend" in f for f in flags)
    soon = (dt.date.today() + dt.timedelta(days=5)).isoformat()
    monkeypatch.setattr(m, "_ex_dividend", lambda sym: soon)
    flags = c.post("/api/options/TEST/analyze", json=body).json()["flags"]
    assert any("ex-dividend" in f for f in flags)


# ---------------- the page ----------------

def test_templates_pick_only_tradable_contracts_near_the_delta_with_strikes_in_order():
    assert "(r.liquidity || {}).grade !== 'not_tradable'" in PAGE.split("const usable")[1].split("\n")[0]
    assert "<= 0.15" in PAGE.split("const nearest")[1].split("\n")[0]
    rules = PAGE.split("const RULES")[1].split("\n")[0]
    assert "bull_call: ([a, b]) => a < b" in rules and "bear_put: ([a, b]) => a > b" in rules
    assert "a < b && b < c2 && c2 < d" in rules
    assert "puts.filter(usable).find" in PAGE and "back.filter(usable).find" in PAGE


def test_no_quotes_turns_the_templates_off_and_says_why():
    assert "noQuotes() ? html`<p class=\"stale\">" in PAGE
    assert "R.expiry && !noQuotes() ? '' : 'disabled'" in PAGE
    assert "(r.liquidity || {}).grade !== 'not_tradable' ? html`<button" in PAGE


def test_the_figures_name_their_basis_and_stale_quotes():
    assert "Most it can make at expiry, from the mid" in PAGE and "Most it can lose at expiry, from the mid" in PAGE
    assert "a.cannot_lose_at_quotes ? 'Nothing, at these quotes'" in PAGE
    assert "Math.abs(a.max_loss)" not in PAGE, "a sign flip hid a credit as a loss"
    assert "a short call has no ceiling" not in PAGE, "a put or a calendar can lose without limit too"
    assert "quotedAt(a.fetched_at)" in PAGE and "quotedAt(d.fetched_at)" in PAGE


def test_add_stays_on_the_chain_and_a_repeat_adds_to_the_leg():
    add = PAGE.split("if ((b = t('[data-v2-add-leg]')))")[1].split("\n    if ((b = t('[data-v2-opg]')))")[0]
    assert "scrollIntoView" not in add
    assert "b.focus({ preventScroll: true })" in add
    assert "same.qty = Math.min(100, same.qty + 1)" in add
    assert "action: 'See the position'" in add


def test_an_expiry_change_clears_the_option_legs_and_says_so():
    ch = PAGE.split("if (el.matches('[data-v2-op-expiry]'))")[1].split("return; }")[0]
    assert "B.legs = B.legs.filter((l) => l.type === 'stock')" in ch and "position was cleared" in ch


def test_the_position_is_kept_for_the_visit_in_memory_only():
    assert "const KEPT = new Map();" in PAGE
    assert "sessionStorage.setItem(STATE_KEY" not in PAGE and "optic.v2.options.state" not in PAGE
    assert "!listed.includes(l.expiry)" in PAGE, "legs on an expiry no longer listed are dropped"


def test_in_session_the_contracts_and_the_position_are_priced_again():
    tick = PAGE.split("refresh = setInterval(")[1].split("}, 60000);")[0]
    assert "loadResearch({ quiet: true })" in tick and "analyze()" in tick


def test_a_phone_folds_the_wide_columns_into_a_row_detail():
    css = (V2 / "css/pages.css").read_text()
    assert "table.contracts .op-wide" in css and ".op-rowbtn { display: inline-grid; width: var(--tap); height: var(--tap)" in css
    assert 'aria-controls="op-rd-${n}"' in PAGE and 'class="op-detail" id="op-rd-${n}" hidden' in PAGE
    assert "data-v2-leg-step" in PAGE and 'inputmode="numeric"' in PAGE
