"""Clicking a sector tile opens the names inside that sector.

The holdings are curated, not fetched. A real constituent list with real
weights needs a licensed file, so these are the LARGEST holdings and every map
built from them says so on screen. correlation.py carries the same caveat for
the same reason.
"""

import pytest

from app.analytics import stockmaps as sm


def test_every_sector_etf_is_drillable():
    """A tile a reader can click must have somewhere to go."""
    for row in sm.SECTORS:
        assert sm.drillable(row["symbol"]), row["symbol"]


def test_an_individual_stock_is_not_drillable():
    """Otherwise a click on AAPL would try to open its constituents."""
    assert not sm.drillable("AAPL")
    assert not sm.drillable("")


def test_holdings_lookup_is_case_insensitive():
    assert sm.holdings_for("xle") == sm.holdings_for("XLE")


def test_every_holding_has_a_symbol_and_a_name():
    """A tile with no name has nothing to show in its tooltip."""
    for fund, rows in sm.SECTOR_HOLDINGS.items():
        assert rows, fund
        for r in rows:
            assert r.get("symbol"), fund
            assert r.get("name"), (fund, r)


def test_no_fund_lists_itself():
    """A self-reference would drill from XLE to XLE forever."""
    for fund, rows in sm.SECTOR_HOLDINGS.items():
        assert fund not in {r["symbol"] for r in rows}, fund


def test_holdings_are_unique_within_a_fund():
    for fund, rows in sm.SECTOR_HOLDINGS.items():
        syms = [r["symbol"] for r in rows]
        assert len(syms) == len(set(syms)), fund


def test_an_unmapped_sector_says_so_instead_of_showing_the_sector_map():
    """Silently falling back would look like the click did nothing."""
    out = sm.build(None, "sector-month", sector="NOTAFUND")
    assert out["tiles"] == []
    assert "NOTAFUND" in out["error"]
    assert "Only the sector and theme funds" in out["error"]


def test_no_em_dashes_in_the_drill_copy():
    """The terminal's punctuation is full stops, commas and colons."""
    out = sm.build(None, "sector-month", sector="NOTAFUND")
    assert "—" not in out["error"]
