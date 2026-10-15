"""The fair-value model reaches Milo when the reader is looking at it.

`valuation` arrived with the fair-value workspace but was never added to the context order
(`_ORDER_BASE`), so `budget_context` appended it after every other section and the 60,000-character
budget cut it whenever a ticker was loaded. Measured 2026-10-15 at c2abae3: Investing-tab questions
on TSLA, BAC, AAPL, KO and MSFT all went to the model without it (3,300 to 14,400 characters), while
the prompt's fair-value section told Milo to answer from it.
"""
from __future__ import annotations

from app import ai


def _filler(n, label):
    """A section of about n x 100 characters that slimming cannot shrink (no lists, no long strings),
    so the budget has to drop whole sections rather than trim them."""
    return {"%s_%d" % (label, i): "x" * 90 for i in range(n)}


def _investing_snapshot():
    """A loaded ticker as the Investing tab sends it, with sections large enough to fill the budget."""
    return {
        "active_view": "long",
        "focus": {"scope": "auto", "view": "long", "view_label": "Investing", "ticker": "TSLA"},
        "ticker": "TSLA",
        "quote": {"ticker": "TSLA", "price": 367.16},
        "research": _filler(125, "research"),
        "framework": _filler(125, "framework"),
        "technicals": _filler(120, "technicals"),
        "long_term": _filler(120, "long_term"),
        "company": _filler(80, "company"),
        "news": _filler(100, "news"),
        "macro": _filler(120, "macro"),
        "valuation": dict(_filler(70, "valuation"), base_case={"value_per_share": 21.47, "price_vs_value": 16.1}),
    }


def test_valuation_is_in_the_context_order():
    assert "valuation" in ai._ORDER_BASE


def test_on_the_investing_tab_the_model_survives_the_budget():
    body, meta = ai.budget_context(_investing_snapshot(), "Is it worth owning at this price?", "auto")
    assert meta["dropped"], "the snapshot must be big enough to force cuts, or this proves nothing"
    assert "valuation" in meta["kept"], meta
    assert '"valuation":' in body


def test_a_value_question_lifts_it_from_any_page():
    snap = _investing_snapshot()
    snap["active_view"] = "overview"
    snap["focus"]["view"] = "overview"
    _, meta = ai.budget_context(snap, "Why is Optic's fair value different from the price?", "auto")
    assert "valuation" in meta["kept"], meta


def test_it_follows_the_quote_when_lifted_with_the_valuation_history_beside_it():
    order = ai._section_order("Is TSLA undervalued?", "auto", "overview")
    assert order.index("valuation") == order.index("quote") + 1
    assert order.index("long_term") == order.index("valuation") + 1


def test_a_does_it_work_question_lifts_the_track_record():
    """The same mechanism threatened `track_record` (the valuation session's stress case, 2026-10-15:
    market, compare and pulse at about 11K each dropped it). A question about whether Optic's reads work
    lifts it to the quote."""
    order = ai._section_order("Do Optic's swing grades actually work?", "auto", "chart")
    assert order.index("track_record") == order.index("quote") + 1
    snap = _investing_snapshot()
    snap["active_view"] = "chart"
    snap["focus"]["view"] = "chart"
    for k in ("market", "compare", "pulse"):
        snap[k] = _filler(110, k)
    snap["track_record"] = {"swing_grade": {"status": "tested", "verdict": "no reliable effect"}}
    _, meta = ai.budget_context(snap, "Do Optic's swing grades actually work?", "auto")
    assert meta["dropped"] and "track_record" in meta["kept"], meta
