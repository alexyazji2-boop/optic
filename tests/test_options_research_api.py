"""The contract-research and position-analysis endpoints, on a fake chain.

The chain is priced by Black-Scholes at known inputs, so every figure the
endpoints return can be checked against arithmetic rather than a snapshot."""
from __future__ import annotations

import pandas as pd
import pytest
from fastapi.testclient import TestClient

import app.main as m
from app import rates
from app.analytics.position import _bs_vec
from app.analytics import vol_surface as vs

SPOT, R, Q = 100.0, 0.04, 0.0


def _chain(expiries, now=None):
    """Priced at `now` (the real clock when not given)."""
    stamp = pd.Timestamp(now).tz_convert("UTC") if now else pd.Timestamp.now(tz="UTC")
    rows = []
    for exp in expiries:
        tau = vs.expiry_tau(exp, now)
        for k in range(80, 125, 5):
            for is_call in (True, False):
                v = 0.25 + (100 - k) * 0.002
                px = float(_bs_vec([SPOT], float(k), tau, v, R, Q, is_call)[0])
                wide = k == 120
                rows.append({"contract": "TEST{}{}{}".format(exp.replace("-", ""), "C" if is_call else "P", k),
                             "expiry": exp, "strike": float(k), "is_call": is_call,
                             "bid": 0.0 if (wide and is_call) else round(px * 0.97, 2),
                             "ask": round(px * 1.03, 2) + 0.01, "last": px, "volume": 500.0,
                             "open_interest": 40.0 if k == 115 else 2000.0, "iv": 0.5, "iv_filled": False,
                             "last_trade": stamp, "dte": 0, "tau": tau,
                             "fetched_at": stamp.isoformat()})
    return pd.DataFrame(rows)


class FakeProvider:
    name = "fake"

    def __init__(self, listed):
        self.listed = listed

    def quote(self, t):
        return {"price": SPOT, "dividend_yield": Q}

    def expirations(self, t):
        return self.listed

    def options_chain(self, t, expiries=None, max_expiries=4):
        return _chain(expiries or self.listed[:max_expiries])

    def earnings_date(self, t):
        return None

    def history(self, *a, **k):
        return pd.DataFrame()

    def _info(self, t):
        return {}


@pytest.fixture
def client(monkeypatch):
    today = pd.Timestamp.now(tz="America/New_York").normalize()
    listed = [str((today + pd.Timedelta(days=d)).date()) for d in (3, 10, 31, 66)]
    fake = FakeProvider(listed)
    monkeypatch.setattr(m, "PROVIDER", fake)
    monkeypatch.setattr(m, "YF_PROVIDER", fake)
    monkeypatch.setenv("RISK_FREE_RATE", str(R))
    rates.reset_cache()
    yield TestClient(m.app), listed
    rates.reset_cache()


def test_research_defaults_to_about_a_month_and_filters_by_delta(client):
    c, listed = client
    got = c.get("/api/options/TEST/research", params={"delta_lo": 0.3, "delta_hi": 0.6}).json()
    assert got["expiry"] == listed[2], "nearest 30 days, at least a week out"
    rows = got["table"]["rows"]
    assert rows and all(0.3 <= abs(r["delta"]) <= 0.6 for r in rows)
    assert got["table"]["filtered_out"]["delta"] > 0
    atm = next(r for r in rows if r["strike"] == 100.0)
    # IV re-solved from the mid (~25%), not the feed's 50%.
    assert atm["iv_pct"] == pytest.approx(25.0, abs=1.0) and atm["iv_source"] == "otm_mid"
    assert atm["breakeven_ask"] == pytest.approx(100 + atm["ask"], abs=0.01)
    assert atm["cost_ask_contract"] == pytest.approx(atm["ask"] * 100, abs=1)
    assert 0 < atm["p_itm_model"] < abs(atm["delta"]), "N(d2) sits below a call's delta N(d1)"
    assert "not a forecast" in " ".join(got["notes"])


def test_research_drops_unquoted_and_thin_contracts_and_says_how_many(client):
    c, _ = client
    got = c.get("/api/options/TEST/research", params={"min_oi": 100}).json()
    strikes = [r["strike"] for r in got["table"]["rows"]]
    assert 115.0 not in strikes and 120.0 not in strikes
    assert got["table"]["filtered_out"]["open_interest"] >= 1
    assert got["table"]["filtered_out"]["unquoted"] >= 1
    allq = c.get("/api/options/TEST/research", params={"include_unquoted": True}).json()
    no_bid = next(r for r in allq["table"]["rows"] if r["strike"] == 120.0)
    assert no_bid["liquidity"]["grade"] == "not_tradable" and no_bid["mid"] is None


def test_research_lists_the_expiry_events(client):
    c, _ = client
    got = c.get("/api/options/TEST/research").json()
    kinds = [e["kind"] for e in got["events"]]
    assert "expiry" in kinds
    assert any("4:00pm ET" in e["text"] for e in got["events"])


def test_analyze_a_vertical_matches_the_chain_quotes(client):
    c, listed = client
    exp = listed[2]
    body = {"legs": [{"type": "call", "side": "long", "strike": 100, "expiry": exp, "qty": 1},
                     {"type": "call", "side": "short", "strike": 105, "expiry": exp, "qty": 1}],
            "slippage": 0.25, "fee_per_contract": 0.65}
    got = c.post("/api/options/TEST/analyze", json=body).json()
    ch = _chain([exp])
    long_ = ch[(ch.strike == 100) & ch.is_call].iloc[0]
    short = ch[(ch.strike == 105) & ch.is_call].iloc[0]
    natural = (long_.ask - short.bid) * 100
    assert got["entry"]["natural"] == pytest.approx(natural, abs=0.01)
    assert got["entry"]["fees"] == pytest.approx(1.30)
    debit = got["entry"]["mid"]
    assert got["max_profit"] == pytest.approx(500 - debit, abs=0.1)
    assert got["max_loss"] == pytest.approx(-debit, abs=0.1)
    assert got["multi_leg_note"] and "complex order book" in got["multi_leg_note"]
    assert any("margin" in a for a in got["assumptions"])


def test_analyze_refuses_a_leg_without_a_two_sided_quote(client):
    c, listed = client
    body = {"legs": [{"type": "call", "side": "long", "strike": 120, "expiry": listed[2], "qty": 1}]}
    r = c.post("/api/options/TEST/analyze", json=body)
    assert r.status_code == 422 and "no two-sided quote" in r.json()["detail"]


def test_analyze_flags_pin_risk_on_a_short_at_the_money_leg(client):
    c, listed = client
    body = {"legs": [{"type": "put", "side": "short", "strike": 100, "expiry": listed[2], "qty": 1}]}
    got = c.post("/api/options/TEST/analyze", json=body).json()
    assert any("pin risk" in f for f in got["flags"])
    assert got["max_loss_unbounded"] is False


def test_analyze_limits_the_legs(client):
    c, listed = client
    legs = [{"type": "call", "side": "long", "strike": 100, "expiry": listed[2], "qty": 1}] * 5
    assert c.post("/api/options/TEST/analyze", json={"legs": legs}).status_code == 400
