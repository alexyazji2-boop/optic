"""A frozen overnight chain is no chain.

Measured on AAPL at 3am ET on 2026-10-07: Yahoo served 379 contracts, 167 of
them within 15% of the $333.63 price, and not one of those 167 had a bid, an
ask or any open interest; their implied volatilities were placeholders. Read as
a chain it gave a put wall at $20 "94% away", a gamma pin at $110, a $110 call
recommended at $21,185 a contract and a skew from placeholder volatilities.
The live site, whose feed served nothing at that hour, said "No options chain
available". Now both say there is nothing to read, and the local one says why.
"""
from __future__ import annotations

import pandas as pd

from app.analytics import pulse as pulse_mod
from app.main import _chain_unusable

SPOT = 333.63


def _chain(rows):
    return pd.DataFrame(rows, columns=["strike", "bid", "ask", "open_interest"])


def test_a_chain_quoted_near_the_price_is_read():
    chain = _chain([[300, 0, 0, 0], [335, 1.2, 1.3, 0], [360, 0, 0, 0]])
    assert _chain_unusable(chain, SPOT) is None
    held = _chain([[330, 0, 0, 12], [600, 0, 0, 0]])
    assert _chain_unusable(held, SPOT) is None, "open interest alone is enough"


def test_a_frozen_chain_is_not():
    chain = _chain([[300, 0, 0, 0], [330, 0, 0, 0], [335, 0, 0, 0], [20, 300.0, 302.0, 3101]])
    why = _chain_unusable(chain, SPOT)
    assert why and "no quotes and no open interest near the price" in why
    assert "3 contracts within 15% of $333.63" in why


def test_a_chain_with_nothing_near_the_price_is_not():
    chain = _chain([[5, 320, 330, 10], [110, 220, 224, 523]])
    why = _chain_unusable(chain, SPOT)
    assert why and "no strikes near the price" in why and "$5.00 to $110.00" in why


def test_a_cheap_stock_counts_a_dollar_as_near():
    chain = _chain([[1.0, 0.2, 0.25, 10], [2.0, 0.05, 0.06, 4]])
    assert _chain_unusable(chain, 1.2) is None


def test_no_chain_is_not_this_functions_business():
    assert _chain_unusable(None, SPOT) is None
    assert _chain_unusable(pd.DataFrame(), SPOT) is None


def test_the_options_brief_says_nothing_about_a_chain_it_does_not_have():
    out = pulse_mod.options_brief({"flow": {"error": "No options chain available for X."}})
    assert out == {"available": False, "reason": "No options chain available for X."}


def test_an_unusual_contract_on_no_open_interest_is_said_so():
    out = pulse_mod.options_brief({"flow": {"unusual": [
        {"strike": 140, "type": "CALL", "expiry": "2026-12-18", "volume": 150,
         "open_interest": 0, "vol_oi_ratio": None}]}})
    note = [i for i in out["items"] if i["label"] == "Unusual"][0]["note"]
    assert note.startswith("150 traded on no open interest"), note
    assert "0.0x" not in note
