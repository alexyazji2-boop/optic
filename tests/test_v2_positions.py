"""Positions and paper portfolios (backlog task 13, 2026-10-20): marks say when they were taken, the realised
total says it covers every closed trade, and the model portfolio's book cards fit a phone on its side.

The Paper Desk was driven in headless Chrome at 360, 390, 430, 844x390, 768 and 1440 px with a TEST book written
to a throwaway browser profile (~/Optic/work/v2-backlog/paper_check.py): exposure and open P&L reconcile with the
rows, realised with the closed trades; the model portfolio and the brokerage view say what they are.
"""
from app import papertrade
from tests.test_frontend_v2_stage0 import V2

PAPER = (V2 / "js/pages/paper.js").read_text()
CSS = (V2 / "css/pages.css").read_text()


class _P:
    def quote(self, t):
        return {"price": 100.0}

    def batch_quotes(self, syms):
        return {s: {"price": 100.0} for s in syms}


def test_a_marked_book_says_when(monkeypatch):
    monkeypatch.setattr(papertrade, "_spot_map", lambda provider, syms: {s: 100.0 for s in syms})
    out = papertrade.mark_book(_P(), [{"id": "a", "ticker": "AAPL", "instrument": "shares", "direction": "long", "qty": 1, "entry_price": 90.0}])
    assert out["marked_at"] and out["marks"][0]["mark_price"] == 100.0


def test_the_page_says_how_old_its_marks_are_and_what_realised_covers():
    assert "markedAt = out.marked_at" in PAPER and "` at ${etStamp(markedAt)}`" in PAPER
    assert "Marks taken ${etStamp(markedAt)}; a mark is a quote, delayed about 15 minutes in session" in PAPER
    assert "all ${done.length} closed" in PAPER and "the table shows the newest 50" in PAPER


def test_book_cards_fit_a_phone_on_its_side():
    assert "@media (max-height: 500px) { .book-card { padding: 10px 14px; gap: 4px; } .book-card .bk-rules, .book-card .bk-blurb { display: none; } }" in CSS
