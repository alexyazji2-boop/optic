"""Option money is counted on time value, not on the whole price.

Measured on COIN at $179.52 on 2026-10-07: "Net premium by strike" was led by
the $10 and $20 calls, 90 contracts at about $150 each, nearly all intrinsic
value, then by puts struck at $370 to $790, $190 to $610 in the money, while
the strikes around the price, where thousands of contracts traded, came below
them. Of $9.36M of put "premium", $8.57M was in the money. A deep in-the-money
contract is the stock bought another way; the bet on the option is what was
paid above intrinsic value.
"""
from __future__ import annotations

import pandas as pd

from app.analytics import flow, gex

SPOT = 179.52


def _row(strike, is_call, price, volume, oi=100, bid=None, iv=0.55):
    bid = price * 0.98 if bid is None else bid
    return {"strike": strike, "is_call": is_call, "mid": price, "last": price,
            "bid": bid, "ask": price * 1.02 if bid else 0.0, "volume": volume,
            "open_interest": oi, "iv": iv, "expiry": "2026-12-18", "dte": 72,
            "contract": "COIN261218{}{:08d}".format("C" if is_call else "P", int(strike * 1000))}


def _chain():
    return pd.DataFrame([
        _row(10, True, 169.6, 60),        # deep in the money: $169.52 of it intrinsic
        _row(20, True, 159.6, 30),
        _row(780, False, 600.6, 5),       # $600.48 intrinsic
        _row(180, True, 7.10, 578),       # at the money: all of it time value
        _row(185, False, 10.4, 337),      # $5.48 intrinsic, $4.92 time value
        _row(175, False, 4.45, 386),
        _row(200, True, 2.69, 811),
    ])


def test_the_strikes_are_ranked_by_time_value_bought():
    out = flow.analyse(_chain(), SPOT, top_n=4)
    strikes = [r["strike"] for r in out["by_strike"]]
    assert 10.0 not in strikes and 20.0 not in strikes and 780.0 not in strikes, strikes
    assert set(strikes) == {175.0, 180.0, 185.0, 200.0}


def test_the_call_share_is_of_time_value_and_the_whole_price_is_kept():
    out = flow.analyse(_chain(), SPOT)
    prem = out["premium"]
    assert prem["basis"] == "time value"
    # The deep calls' whole price is still on the record, for reference.
    assert prem["total_paid"]["calls"] > prem["calls"] + 1_000_000
    assert abs(prem["calls"] - (578 * 100 * 7.10 + 811 * 100 * 2.69
                                + 60 * 100 * (169.6 - 169.52) + 30 * 100 * (159.6 - 159.52))) < 1


def test_a_notable_contract_is_one_with_time_value_bought():
    out = flow.analyse(_chain(), SPOT)
    assert all(u["strike"] not in (10.0, 20.0) for u in out["unusual"])
    top = out["unusual"][0]
    assert top["premium_total"] >= top["premium"]


def test_the_skew_reads_quoted_contracts_only():
    chain = pd.DataFrame([_row(190, True, 3.0, 100, bid=0.0, iv=0.125),
                          _row(170, False, 3.0, 100, bid=0.0, iv=0.125)])
    out = flow.analyse(chain, SPOT)
    assert out["iv_skew"]["put_minus_call_vol_pts"] is None, "placeholders are not a skew"


def test_a_wall_carries_a_real_share_of_the_exposure():
    """AAPL's "put wall" at 9:36am was the $20 strike, -$5.8k of gamma against
    $24M at the pin."""
    assert gex.WALL_MIN_SHARE == 0.05
    src = open(gex.__file__).read()
    assert 'by_strike["net_gex"] < -floor' in src and 'by_strike["net_gex"] > floor' in src
