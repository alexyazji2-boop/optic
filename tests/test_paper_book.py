"""A hand-entered paper book: marked on demand, stored nowhere.

Separate from app/paper.py, which is the terminal's own automated record. That
one's entire value is that nobody has touched it -- a track record a reader can
edit is not a track record -- so a hand-entered trade must never reach it.

Driven against the live provider while it was built: long 100 NVDA at 200
marked +$2,507, the same position short 50 marked -$1,253.50, and two calls
bought at 2.94 marked at the live chain mid for +$147.
"""

from __future__ import annotations

from pathlib import Path

from app import papertrade

ROOT = Path(__file__).resolve().parent.parent
MAIN = (ROOT / "app/main.py").read_text()
SRC = (ROOT / "app/papertrade.py").read_text()


class FakeProvider:
    """Enough of a provider to mark a book, and no network."""

    def __init__(self, quotes=None, chain_price=None, raises=False):
        self.quotes = quotes if quotes is not None else {"NVDA": 225.0}
        self.chain_price = chain_price
        self.raises = raises
        self.quote_calls = 0

    def batch_quote(self, tickers):
        self.quote_calls += 1
        if self.raises:
            raise RuntimeError("feed down")
        return {t: {"last": self.quotes.get(t), "prev_close": 1.0} for t in tickers}


def _shares(**over):
    row = {"id": "a", "ticker": "NVDA", "instrument": "shares", "direction": "long",
           "qty": 100, "entry_price": 200.0, "entry_spot": 200.0,
           "entry_at": "2026-09-01T14:00:00Z"}
    row.update(over)
    return row


# ------------------------------------------------- it is not the other ledger


def test_it_cannot_write_to_the_terminals_own_record():
    """Optic Portfolio's credibility is that it was not edited. A hand-entered
    trade reaching that ledger would end it, and the failure would be invisible
    -- the numbers would still add up."""
    for banned in ("open_position", "close_position", "init_db", "_connect",
                   "DB_PATH", "sqlite3"):
        assert banned not in SRC, "%s would put a hand-entered trade in the ledger" % banned
    # What it DOES borrow is arithmetic, which has no storage in it.
    assert "paper.mark_option" in SRC
    assert "paper._pnl" in SRC


def test_the_endpoint_stores_nothing():
    """No sign-in, so a server-side book would be one book shared by every
    visitor -- your trades in a stranger's list. Same shape /api/retirement
    already uses for holdings, and for the same reason."""
    fn = MAIN[MAIN.index('@app.post("/api/paper/mark")'):]
    fn = fn[:fn.index("\n@app.")]
    assert "Body(default={})" in fn
    assert "Nothing is stored" in fn
    for banned in ("_CACHE[", "open(", "INSERT", "conn.execute"):
        assert banned not in fn, banned


# ------------------------------------------------- the arithmetic


def test_a_long_position_gains_when_price_rises():
    out = papertrade.mark_book(FakeProvider(), [_shares()])
    m = out["marks"][0]
    assert m["mark_price"] == 225.0
    assert m["mark_source"] == "Last trade"
    assert m["pnl"] == 2500.0
    assert m["pnl_pct"] == 12.5


def test_a_short_position_loses_when_price_rises():
    """The sign flip is the whole reason short is a separate direction rather
    than a negative quantity -- a negative qty would invert the cost basis too
    and report the percentage backwards."""
    out = papertrade.mark_book(FakeProvider(), [_shares(direction="short", qty=50)])
    m = out["marks"][0]
    assert m["pnl"] == -1250.0
    assert m["pnl_pct"] == -12.5


def test_a_short_position_gains_when_price_falls():
    out = papertrade.mark_book(FakeProvider(quotes={"NVDA": 180.0}),
                               [_shares(direction="short", qty=50)])
    assert out["marks"][0]["pnl"] == 1000.0


def test_an_option_carries_the_contract_multiplier():
    """A contract is a hundred shares. Marking one like a share understates
    every option P&L in the book by two orders of magnitude."""
    import types
    prov = FakeProvider()
    # mark_option is exercised for real elsewhere; here the point is the 100x.
    out = papertrade.mark_book(prov, [_shares(
        instrument="option", option_type="call", strike=225.0,
        expiry="2099-01-15", qty=2, entry_price=3.0)])
    m = out["marks"][0]
    assert m["mark_price"] is not None
    # Two contracts: the P&L is 200x the per-share move, not 2x.
    per_share = m["mark_price"] - 3.0
    assert abs(m["pnl"] - per_share * 200.0) < 0.02, m


# ------------------------------------------------- one bad row is one bad row


def test_a_symbol_with_no_quote_costs_that_row_only():
    """A book that refuses to show eleven positions because the twelfth is a
    delisted ticker is a book nobody can use to close the twelfth."""
    out = papertrade.mark_book(FakeProvider(quotes={"NVDA": 225.0, "DEAD": None}), [
        _shares(), _shares(id="b", ticker="DEAD")])
    by_id = {m["id"]: m for m in out["marks"]}
    assert by_id["a"]["pnl"] == 2500.0
    assert "reason" in by_id["b"] and "DEAD" in by_id["b"]["reason"]
    assert "pnl" not in by_id["b"], "a row with no mark must not report a P&L"


def test_the_whole_feed_being_down_is_not_an_exception():
    """Every leg of this app reports its own absence rather than 500ing. A book
    is the last place to break that: the reader's positions are still theirs
    and the page has to draw them."""
    out = papertrade.mark_book(FakeProvider(raises=True), [_shares()])
    assert out["available"] is True
    assert "reason" in out["marks"][0]


# ------------------------------------------------- what is refused


def test_a_position_that_cannot_be_marked_is_dropped_not_repaired():
    """Guessing an entry price would put a number in front of a reader that
    nothing in the request supports."""
    bad = [
        {"ticker": "NVDA", "instrument": "shares", "direction": "long", "qty": 10},
        _shares(entry_price=0),
        _shares(qty=0),
        _shares(ticker=""),
        _shares(instrument="futures"),
        _shares(direction="sideways"),
        _shares(instrument="option", option_type="call", strike=None, expiry="2099-01-15"),
        _shares(instrument="option", option_type="banana", strike=1.0, expiry="2099-01-15"),
    ]
    out = papertrade.mark_book(FakeProvider(), bad)
    assert out["counted"] == 0, [m for m in out["marks"]]
    assert out["dropped"] == len(bad)


def test_a_nan_never_reaches_the_chain_lookup():
    """NaN compares false against everything, so a NaN strike matches no
    contract and the position marks as modelled forever without ever saying
    why."""
    out = papertrade.mark_book(FakeProvider(), [_shares(entry_price=float("nan"))])
    assert out["counted"] == 0


def test_the_book_is_capped_and_says_so():
    """A book at the cap would otherwise show its first fifty marked and the
    rest blank forever, which reads as the marking being broken."""
    out = papertrade.mark_book(FakeProvider(), [_shares(id=str(i))
                                                for i in range(papertrade.MAX_POSITIONS + 5)])
    assert out["capped"] is True
    assert len(out["marks"]) == papertrade.MAX_POSITIONS


# ------------------------------------------------- cost


def test_one_quote_call_for_the_whole_book():
    """Twelve positions across four symbols is four quotes, not twelve."""
    prov = FakeProvider(quotes={"NVDA": 225.0, "AAPL": 100.0})
    papertrade.mark_book(prov, [_shares(id=str(i), ticker=("NVDA" if i % 2 else "AAPL"))
                                for i in range(12)])
    assert prov.quote_calls == 1


def test_yesterdays_close_is_never_used_as_a_mark():
    """It is a day old, and a book marked at it would show a P&L that is a day
    old without saying so."""
    out = papertrade.mark_book(
        FakeProvider(quotes={"NVDA": None}), [_shares()])
    assert "reason" in out["marks"][0]
    assert "prev_close" not in SRC.split("_num(row.get", 1)[1][:60]
