"""The what-if lab (app/brokerage/scenarios.py): hypothetical changes worked
out by hand, for each funding rule, and the guards that keep it a model of a
real portfolio rather than of money that is not there.
"""

from __future__ import annotations

import pytest

from app.brokerage import scenarios as sc


def _h(sym, value, sector=None, kind="equity"):
    return {"symbol": sym, "kind": kind, "value_usd": value, "market_value": value, "quantity": value / 100.0,
            "price": 100.0, "sector": sector, "currency": "USD"}


H = [_h("AAA", 5000.0, "Technology"), _h("BBB", 3000.0, "Healthcare"), _h("FFF", 2000.0, kind="etf")]
SECTOR = {"AAA": "Technology", "BBB": "Healthcare", "NEW": "Energy"}.get


def _run(changes, funding="cash", cash=1000.0, price_of=lambda s: None):
    return sc.run(H, cash, changes, funding, price_of, SECTOR, {}, [], None)


def _w(out, sym):
    return next(w for w in out["weights"] if w["symbol"] == sym)


def test_a_buy_from_cash_moves_cash_into_the_holding():
    # Total 11,000 before and after. BBB 3,000 + 500 = 3,500: 27.27% to 31.82%.
    out = _run([{"symbol": "BBB", "action": "buy", "amount_type": "dollars", "amount": 500}])
    assert out["total"] == {"before": 11000.0, "after": 11000.0}
    assert out["cash"]["before"] == 1000.0 and out["cash"]["after"] == 500.0
    assert _w(out, "BBB")["before_pct"] == pytest.approx(27.27, abs=0.01)
    assert _w(out, "BBB")["after_pct"] == pytest.approx(31.82, abs=0.01)
    assert "No trades are placed" in out["method"]


def test_a_buy_bigger_than_the_cash_is_scaled_and_the_shortfall_shown():
    # 1,000 of cash against 3,000 of buys: every buy scaled to a third.
    out = _run([{"symbol": "BBB", "action": "buy", "amount_type": "dollars", "amount": 3000}])
    assert out["shortfall_usd"] == pytest.approx(2000.0)
    assert out["cash"]["after"] == pytest.approx(0.0)
    assert _w(out, "BBB")["value_after"] == pytest.approx(4000.0)
    assert out["warnings"]


def test_new_money_grows_the_total():
    out = _run([{"symbol": "BBB", "action": "buy", "amount_type": "dollars", "amount": 4000}], funding="new_money")
    assert out["total"]["after"] == pytest.approx(15000.0) and out["new_money_usd"] == pytest.approx(4000.0)
    assert out["cash"]["after"] == pytest.approx(1000.0)
    assert _w(out, "BBB")["after_pct"] == pytest.approx(100 * 7000 / 15000, abs=0.01)


def test_pro_rata_sells_the_rest_evenly_to_pay_for_a_buy():
    # Buy 1,000 of BBB funded by selling AAA and FFF in proportion (5:2), cash untouched.
    out = _run([{"symbol": "BBB", "action": "buy", "amount_type": "dollars", "amount": 1000}], funding="pro_rata")
    assert out["total"]["after"] == pytest.approx(11000.0)
    assert _w(out, "BBB")["value_after"] == pytest.approx(4000.0)
    assert _w(out, "AAA")["value_after"] == pytest.approx(5000.0 - 1000.0 * 5 / 7, abs=0.01)
    assert _w(out, "FFF")["value_after"] == pytest.approx(2000.0 - 1000.0 * 2 / 7, abs=0.01)


def test_a_sell_cannot_go_short():
    out = _run([{"symbol": "AAA", "action": "sell", "amount_type": "shares", "amount": 999}])
    assert _w(out, "AAA")["value_after"] == pytest.approx(0.0)
    assert out["cash"]["after"] == pytest.approx(6000.0)
    assert any("AAA" in w for w in out["warnings"])


def test_a_target_weight_is_a_share_of_the_total_after():
    out = _run([{"symbol": "AAA", "action": "target_weight", "amount_type": "weight_pct", "amount": 25}])
    assert _w(out, "AAA")["after_pct"] == pytest.approx(25.0, abs=0.05)


def test_an_unknown_symbol_is_refused_with_a_reason_and_a_known_one_is_priced():
    out = _run([{"symbol": "ZZZZ", "action": "buy", "amount_type": "dollars", "amount": 100}])
    refused = next(c for c in out["changes"] if c["symbol"] == "ZZZZ")
    assert refused["status"] != "applied" and refused["reason"]
    priced = _run([{"symbol": "NEW", "action": "buy", "amount_type": "dollars", "amount": 500}],
                  price_of=lambda s: {"price": 50.0, "as_of": "2026-10-16T15:00:00Z"} if s == "NEW" else None)
    assert _w(priced, "NEW")["value_after"] == pytest.approx(500.0)


def test_concentration_before_and_after_by_hand():
    # Invested holdings only, cash left out: before 5000/3000/2000 of 10000,
    # HHI 0.38, 1/HHI = 2.63; top1 50%.
    out = _run([])
    assert out["concentration"]["before"]["effective_holdings"] == pytest.approx(2.63, abs=0.01)
    assert out["concentration"]["before"]["top1_pct"] == pytest.approx(50.0)
