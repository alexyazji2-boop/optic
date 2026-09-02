"""The three books.

They run the same scan under different rules, so these tests care most about the
things that would silently destroy the comparison: shared equity, a shared
ledger, or one book's rules leaking into another's.
"""
from __future__ import annotations

import pytest

from app import paper


def test_three_books_with_distinct_rules():
    assert paper.BOOK_IDS == ["conservative", "balanced", "aggressive"]
    risks = [paper.book_config(b)["risk_per_trade"] for b in paper.BOOK_IDS]
    assert risks == sorted(risks), "risk per trade must increase across the books"
    assert len(set(risks)) == 3, "three books with the same risk is one book"


def test_conservative_refuses_options():
    """The defining difference: premium that can expire worthless."""
    assert paper.book_config("conservative")["allow_options"] is False
    assert paper.book_config("balanced")["allow_options"] is True
    assert paper.book_config("aggressive")["allow_options"] is True


def test_entry_bar_is_strictest_on_the_conservative_book():
    bars = {b: paper.book_config(b)["min_composite"] for b in paper.BOOK_IDS}
    assert bars["conservative"] > bars["balanced"]


def test_volatility_ceiling_widens_with_risk():
    caps = [paper.book_config(b)["max_atr_pct"] for b in paper.BOOK_IDS]
    assert caps == sorted(caps)


def test_unknown_book_falls_back_rather_than_raising():
    """A bad book id in a query string must not take the ledger down."""
    assert paper.book_config("nonsense")["id"] == paper.DEFAULT_BOOK
    assert paper.book_config(None)["id"] == paper.DEFAULT_BOOK
    assert paper.book_config("")["id"] == paper.DEFAULT_BOOK


def test_default_book_is_the_one_the_record_belongs_to():
    """Existing trades were backfilled to balanced because those were its rules."""
    assert paper.DEFAULT_BOOK == "balanced"


def test_capacity_is_per_book():
    """Shared capacity would let one book's positions fill another's slots."""
    cons = paper._capacity(100000.0, "conservative")
    aggr = paper._capacity(100000.0, "aggressive")
    assert cons["book"] == "conservative"
    assert aggr["book"] == "aggressive"
    # On the ceilings, not on what is left of them. `position_slots_left`
    # subtracts today's open positions, so comparing those two would invert the
    # moment the aggressive book fills up — the same latent flake that broke the
    # risk-budget test once the first real scan landed.
    assert (paper.book_config("aggressive")["max_positions"]
            > paper.book_config("conservative")["max_positions"])
    for book, cap in (("conservative", cons), ("aggressive", aggr)):
        ceiling = paper.book_config(book)["max_positions"]
        assert cap["position_slots_left"] == ceiling - cap["open_positions"], book


def test_risk_budget_scales_with_the_book():
    """Compare the budgets, not what is left of them.

    This asserted on `risk_budget_left`, which subtracts risk already on the
    books — so it only held while both books were empty. The first real scan put
    the aggressive book at 99% of its allowance and the assertion inverted, with
    nothing wrong in the code. A test that depends on today's open positions is
    testing the ledger, not the configuration.
    """
    cons_cfg = paper.book_config("conservative")
    aggr_cfg = paper.book_config("aggressive")
    equity = 100000.0
    assert (aggr_cfg["max_portfolio_risk"] * equity
            > cons_cfg["max_portfolio_risk"] * equity)
    # And the derived field agrees, once open risk is held equal at zero.
    for book in ("conservative", "aggressive"):
        cap = paper._capacity(equity, book)
        budget = paper.book_config(book)["max_portfolio_risk"] * equity
        assert cap["risk_budget_left"] == pytest.approx(
            budget - cap["open_risk"], rel=1e-6), book


def test_sizing_respects_the_book():
    """Half the risk must buy roughly half the shares on the same stop."""
    cons = paper.size_shares(100.0, 95.0, 100000.0, "conservative")
    bal = paper.size_shares(100.0, 95.0, 100000.0, "balanced")
    aggr = paper.size_shares(100.0, 95.0, 100000.0, "aggressive")
    assert cons["qty"] < bal["qty"] < aggr["qty"]
    assert cons["qty"] == pytest.approx(bal["qty"] / 2, rel=0.02)


def test_option_sizing_respects_the_book():
    bal = paper.size_option(5.0, 100000.0, "balanced")
    aggr = paper.size_option(5.0, 100000.0, "aggressive")
    assert aggr["qty"] >= bal["qty"]


def test_equity_is_not_shared_between_books():
    """The whole comparison rests on this.

    If the books shared a pool, the aggressive book's losses would shrink the
    conservative book's position sizes and the three records would no longer be
    independent.
    """
    paper.init_db()
    per_book = {b: paper.equity_for(b) for b in paper.BOOK_IDS}
    combined = paper.equity_for()
    # Each book starts from the same capital; only realised P&L differs.
    for b, eq in per_book.items():
        assert eq >= 0
    # The combined figure counts every book's realised P&L, so it cannot equal a
    # single empty book's starting equity unless nothing has ever closed.
    closed_any = any(eq != paper.START_EQUITY for eq in per_book.values())
    if closed_any:
        assert combined != min(per_book.values())


def test_every_book_declares_what_it_is_for():
    for b in paper.BOOK_IDS:
        cfg = paper.book_config(b)
        assert cfg["label"] and cfg["tagline"] and cfg["blurb"]
        assert "risk" in cfg["tagline"].lower()
