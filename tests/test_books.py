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


# ------------------------------------------- one book's limits are its own


def _fake_capacity(monkeypatch, state):
    """`state` maps a book id to (slots_left, risk_left)."""
    monkeypatch.setattr(paper, "equity_for", lambda book=None: 100000.0)
    monkeypatch.setattr(paper, "_capacity", lambda equity, book=None: {
        "book": book,
        "open_positions": 0,
        "position_slots_left": state[book][0],
        "open_risk": 0.0,
        "open_risk_pct": 0.0,
        "risk_budget_left": state[book][1],
    })


def test_a_full_balanced_book_does_not_starve_the_others(monkeypatch):
    """The bug this names emptied a whole book for twelve scans.

    `run_scan` checked capacity once per candidate as `_capacity(equity)` with
    no book argument, which resolves to the balanced book, and then `break` out
    of the candidate loop for everyone. So when balanced filled its 15% risk
    budget the next ten scans stopped on their first candidate: considered
    counts ran [4, 0, 0, 0, 0, 0, 2, 0, 0, 0, 0, 0]. Conservative holds nothing,
    had its entire 6% budget free, and was never offered a single name. Its
    0.00% return read as a risk tolerance earning nothing rather than as a book
    that had not been asked.
    """
    _fake_capacity(monkeypatch, {
        "conservative": (5, 4000.0),
        "balanced": (0, 0.0),          # full on both counts
        "aggressive": (14, 3300.0),
    })
    live, reason = paper._books_with_room()
    assert "conservative" in live and "aggressive" in live
    assert "balanced" not in live
    assert reason is None, "the pass continues while any book can act"


def test_the_pass_stops_only_when_no_book_can_act(monkeypatch):
    _fake_capacity(monkeypatch, {b: (0, 0.0) for b in paper.BOOK_IDS})
    live, reason = paper._books_with_room()
    assert live == []
    assert reason
    # Named per book. "The budget is used up" without saying whose is what let
    # this go unnoticed for twelve scans.
    for label in ("conservative", "balanced", "aggressive"):
        assert label in reason


def test_a_books_per_scan_limit_is_its_own(monkeypatch):
    """The loop used the global MAX_NEW_PER_SCAN and counted it against the
    default book only, so the three books' own 3, 6 and 8 never applied."""
    _fake_capacity(monkeypatch, {b: (10, 5000.0) for b in paper.BOOK_IDS})
    taken = {"conservative": paper.book_config("conservative")["max_new_per_scan"]}
    live, reason = paper._books_with_room(taken)
    assert "conservative" not in live, "it has taken its limit for this scan"
    assert "balanced" in live and "aggressive" in live
    assert reason is None


def test_every_book_has_its_own_per_scan_limit():
    limits = [paper.book_config(b)["max_new_per_scan"] for b in paper.BOOK_IDS]
    assert limits == sorted(limits), "a riskier book may open more per scan"
    assert len(set(limits)) == 3


def test_the_scan_loop_no_longer_asks_only_the_default_book():
    """Read from source, because the failure was a control-flow one: the gates
    ran before the `for book_id` line that gives every book its look."""
    import re
    src = open("app/paper.py").read()
    loop = src[src.index("def run_scan"):]
    loop = loop[:loop.index("\ndef ", 10)]
    code = re.sub(r"#.*$", "", loop, flags=re.M)
    assert "_books_with_room(opened_by_book)" in code
    assert "_capacity(equity)" not in code, \
        "a bookless capacity call is the balanced book wearing everyone's name"
    assert "for book_id in live:" in code, "only books with room see the candidate"


# ----------------------------------------------------------- the book cards

import re as _re

APP_JS = open("static/app.js").read()
CSS = open("static/styles.css").read()


def _code(text):
    text = _re.sub(r"/\*.*?\*/", " ", text, flags=_re.S)
    return _re.sub(r"^\s*//.*$", " ", text, flags=_re.M)


def _selector():
    fn = APP_JS[APP_JS.index("function renderBookSelector("):]
    return fn[:fn.index("\nfunction renderTracker")]


def test_an_untraded_book_says_so_rather_than_returning_nothing():
    """"$100.0K / 0.00% / 0 / 0" looks like a flat month. It was a book the scan
    loop had stopped offering candidates to, and the display is the half of that
    bug that made it invisible. A return needs a trade behind it."""
    fn = _code(_selector())
    assert "No trades yet" in fn
    assert "(su.open_count || 0) + (su.closed_count || 0) === 0" in fn


def test_a_traded_book_still_shows_its_record():
    fn = _code(_selector())
    assert "su.open_count" in fn and "su.closed_count" in fn
    assert "Return" in fn and "signClass(ret)" in fn


def test_the_risk_taglines_carry_no_directional_colour():
    """They were `flat`, `up` and `warn`: `up` is `--pos`, the green that means
    the price rose on every other percentage here, and `warn` has no rule at all
    so it fell back to the default. The scheme was really "the middle one is
    good", which is an editorial judgement in the app's directional vocabulary.
    A risk tolerance is not good or bad, and the words say low, medium, high."""
    code = _code(APP_JS)
    assert "BOOK_TONE" not in code, "the tone map is gone"
    fn = _code(_selector())
    assert 'class="cat-tag flat"' in fn, "one neutral treatment for all three"
    assert ".cat-tag.warn" not in CSS, "and the dead class stays dead"


def test_the_card_figures_are_centred_and_share_a_baseline():
    """Same treatment as `.tile`, and safe for the same reason: the values are
    tabular, so a figure does not shift sideways as it ticks."""
    rule = CSS[CSS.index(".bk-figs > span {"):]
    rule = rule[:rule.index("}")]
    assert "text-align: center" in rule
    label = CSS[CSS.index(".bk-figs i {"):]
    label = label[:label.index("}")]
    assert "min-height" in label, "a wrapped caption must not drop its value"
    assert "font-variant-numeric: tabular-nums" in CSS[CSS.index(".bk-figs b,"):][:120]


def test_the_untraded_card_does_not_stretch_across_four_columns():
    assert ".bk-figs-empty { grid-template-columns: max-content max-content; }" in CSS
