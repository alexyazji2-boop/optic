"""Exit-rule and sizing tests for Optic's Positions (app/paper.py).

These are here because of one specific bug: a long put stores `direction =
"long"` (the premium is owned), and the underlying-stop check read that field
instead of the contract type, so every put closed on the same tick it opened.
Nothing raised, nothing logged — the ledger just quietly showed a 0-day exit.
That class of error is invisible in the UI, so the exit table gets pinned down
here.

Run with:  .venv/bin/python -m pytest tests/ -q
"""

from __future__ import annotations

import pytest
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import paper  # noqa: E402


def _pos(**over):
    base = {
        "instrument": "shares",
        "direction": "long",
        "option_type": None,
        "strike": None,
        "expiry": None,
        "qty": 100,
        "entry_price": 100.0,
        "entry_spot": 100.0,
        "entry_at": datetime.now(timezone.utc).isoformat(),
        "stop": 95.0,
        "target": 110.0,
    }
    base.update(over)
    return base


def _future(days: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=days)).strftime("%Y-%m-%d")


# ------------------------------------------------------------------- options


def _option(**over):
    base = _pos(instrument="option", direction="long", option_type="call",
                strike=100.0, expiry=_future(30), qty=2, entry_price=5.0)
    base.update(over)
    return base


def test_fresh_put_survives_its_own_stop():
    """The regression. A bearish put's stop sits *above* spot; reading the
    position's `direction` ("long", meaning long premium) inverted the test."""
    pos = _option(option_type="put", stop=110.0)
    assert paper._exit_check(pos, 5.0, spot=100.0, bar_high=101.0, bar_low=99.0) is None


def test_put_closes_when_underlying_rallies_through_the_stop():
    pos = _option(option_type="put", stop=110.0)
    assert paper._exit_check(pos, 5.0, 111.0, 111.0, 108.0) == "Underlying broke the stop level"


def test_fresh_call_survives_its_own_stop():
    pos = _option(option_type="call", stop=95.0)
    assert paper._exit_check(pos, 5.0, 100.0, 101.0, 99.0) is None


def test_call_closes_when_underlying_breaks_the_stop():
    pos = _option(option_type="call", stop=95.0)
    assert paper._exit_check(pos, 3.0, 94.0, 96.0, 94.0) == "Underlying broke the stop level"


def test_premium_stop_and_target():
    pos = _option()
    assert paper._exit_check(pos, 2.5, 100.0, 100.0, 100.0) == "Premium stop (-50%)"
    assert paper._exit_check(pos, 10.0, 100.0, 100.0, 100.0) == "Premium target (+100%)"


def test_expiry_closes_regardless_of_price():
    pos = _option(expiry=_future(-1))
    assert paper._exit_check(pos, 5.0, 100.0, 100.0, 100.0) == "Expiry reached"


# -------------------------------------------------------------------- shares


def test_long_shares_stop_uses_the_day_low():
    """A level touched intraday counts even if price closed back above it —
    otherwise the record flatters itself."""
    pos = _pos()
    assert paper._exit_check(pos, 100.0, 100.0, 101.0, 94.0) == "Stop hit"


def test_long_shares_target_uses_the_day_high():
    pos = _pos()
    assert paper._exit_check(pos, 100.0, 100.0, 111.0, 99.0) == "Target hit"


def test_short_shares_stop_is_above_entry():
    pos = _pos(direction="short", stop=105.0, target=90.0)
    assert paper._exit_check(pos, 100.0, 100.0, 106.0, 99.0) == "Stop hit"
    assert paper._exit_check(pos, 100.0, 100.0, 101.0, 89.0) == "Target hit"


def test_time_stop():
    old = (datetime.now(timezone.utc) - timedelta(days=paper.MAX_HOLD_DAYS + 1)).isoformat()
    pos = _pos(entry_at=old)
    assert "Time stop" in paper._exit_check(pos, 100.0, 100.0, 100.5, 99.5)


# -------------------------------------------------------------------- sizing


def test_share_size_risks_the_budget_not_the_notional():
    out = paper.size_shares(entry=100.0, stop=95.0, equity=100_000)
    assert out["qty"] == 200                      # $1,000 risk / $5 per share
    assert out["risk_dollars"] == 1000.0


def test_wider_stop_buys_fewer_shares():
    tight = paper.size_shares(100.0, 99.0, 100_000)["qty"]
    wide = paper.size_shares(100.0, 90.0, 100_000)["qty"]
    assert wide < tight


def test_share_notional_is_capped():
    # A 10-cent stop would otherwise buy 10,000 shares of a $100 stock.
    out = paper.size_shares(100.0, 99.9, 100_000)
    assert out["qty"] * 100.0 <= 100_000 * 0.25 + 100.0


def test_option_size_budgets_the_whole_premium():
    out = paper.size_option(premium=5.0, equity=100_000)
    assert out["qty"] == 4                        # $2,000 budget / $500 a contract
    assert out["risk_dollars"] == 2000.0


def test_expensive_contract_still_gets_one_and_says_so():
    out = paper.size_option(premium=31.8, equity=100_000)   # $3,180 a contract
    assert out["qty"] == 1
    assert "above the usual" in out["note"]


def test_contract_past_the_ceiling_is_refused():
    out = paper.size_option(premium=80.0, equity=100_000)   # $8,000, past 5%
    assert out["qty"] == 0
    assert "ceiling" in out["reason"]


# ---------------------------------------------------------------------- pnl


def test_option_pnl_uses_the_hundred_multiplier():
    pos = _option(qty=2, entry_price=5.0)
    assert paper._pnl(pos, 6.0)["pnl"] == 200.0


def test_short_share_pnl_is_inverted():
    pos = _pos(direction="short", qty=100, entry_price=100.0)
    assert paper._pnl(pos, 90.0)["pnl"] == 1000.0


# ------------------------------------------------------- the market session
#
# Both of these fabricate history rather than erroring, which is why they get
# tests: a bad number in the ledger looks exactly like a real result.


def test_session_hours():
    from datetime import datetime as dt
    from zoneinfo import ZoneInfo
    et = ZoneInfo("America/New_York")

    def at(y, m, d, hh, mm):
        return dt(y, m, d, hh, mm, tzinfo=et)

    # 2026-07-30 is a Thursday, 2026-08-01 a Saturday.
    assert paper.market_open_et(at(2026, 7, 30, 10, 0)) is True
    assert paper.market_open_et(at(2026, 7, 30, 9, 29)) is False    # pre-market
    assert paper.market_open_et(at(2026, 7, 30, 16, 0)) is False    # the bell
    assert paper.market_open_et(at(2026, 7, 30, 20, 0)) is False    # after hours
    assert paper.market_open_et(at(2026, 8, 1, 12, 0)) is False     # Saturday


def test_a_position_opened_today_is_not_stopped_by_this_mornings_low():
    """The regression. A long opened at today's close was closed instantly by a
    low that had been set hours *before* the entry — an exit off a bar that
    predates the trade."""
    pos = _pos(entry_at=datetime.now(timezone.utc).isoformat(), stop=97.0)
    assert paper._entered_this_session(pos) is True
    # mark_open_positions blanks the session extremes for a same-session entry.
    assert paper._exit_check(pos, 100.0, 100.0, None, None) is None


def test_yesterdays_position_still_uses_the_session_low():
    old = (datetime.now(timezone.utc) - timedelta(days=3)).isoformat()
    pos = _pos(entry_at=old, stop=97.0)
    assert paper._entered_this_session(pos) is False
    assert paper._exit_check(pos, 100.0, 100.0, 101.0, 94.0) == "Stop hit"


# ------------------------------------------------- three-book regressions
#
# Both of these shipped and were invisible. The books sat at exactly their
# starting equity with no positions and no errors, which is indistinguishable
# from a selective strategy that found nothing.

def test_every_function_that_reads_book_declares_it():
    """A guard for the class of bug, not just the one instance.

    `consider_ticker` used `book` throughout its body while its signature took
    only (snapshot, equity), and the scan loop passed three arguments. Every call
    raised TypeError, the scan swallowed it and recorded "opened 0", and the two
    new books never opened a position. `_capacity` and `open_risk` had the same
    bug earlier; this catches the next one.
    """
    import ast

    with open("app/paper.py", encoding="utf-8") as fh:
        tree = ast.parse(fh.read())

    broken = []
    for fn in [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]:
        params = {a.arg for a in fn.args.args} | {a.arg for a in fn.args.kwonlyargs}
        loads = {n.id for n in ast.walk(fn)
                 if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)}
        assigned = {t.id for n in ast.walk(fn) if isinstance(n, ast.Assign)
                    for t in n.targets if isinstance(t, ast.Name)}
        if "book" in loads and "book" not in params and "book" not in assigned:
            broken.append("%s (line %d)" % (fn.name, fn.lineno))
    assert not broken, "read 'book' without declaring it: " + ", ".join(broken)


def test_consider_ticker_accepts_a_book():
    """The exact call the scan loop makes."""
    snapshot = {"ticker": "T", "verdict": {"composite_score": 10.0},
                "quote": {"price": 100.0}}
    for book in paper.BOOK_IDS:
        found, notes = paper.consider_ticker(snapshot, 100_000.0, book)
        assert isinstance(found, list) and isinstance(notes, list)


def test_the_books_take_different_sizes_on_the_same_candidate():
    """The point of three books.

    A single 25%-of-equity concentration cap bound on all three at once, so every
    book took the same size on any tight-stop name — and the aggressive book
    risked LESS than the balanced one purely because it had less equity. The cap
    is right; one constant across books with a fourfold spread in risk appetite
    was not.
    """
    entry, stop, equity = 100.0, 99.0, 100_000.0   # a deliberately tight stop
    sizes = {b: paper.size_shares(entry, stop, equity, b)["qty"]
             for b in ("conservative", "balanced", "aggressive")}
    assert sizes["conservative"] < sizes["balanced"] < sizes["aggressive"], sizes


def test_a_capped_size_says_it_was_capped():
    """A position risking a third of its allowance looks like a sizing bug unless
    the payload says the concentration cap decided it."""
    tight = paper.size_shares(100.0, 99.9, 100_000.0, "balanced")
    assert tight["capped"] is True
    wide = paper.size_shares(100.0, 50.0, 100_000.0, "balanced")
    assert wide["capped"] is False


def test_risk_per_trade_still_governs_when_the_cap_does_not_bind():
    """With a wide stop the risk budget is what sets the size, and then the books
    must line up with their stated risk per trade."""
    entry, stop, equity = 100.0, 60.0, 100_000.0
    per_share = entry - stop
    for book in ("conservative", "balanced", "aggressive"):
        cfg = paper.book_config(book)
        budget = equity * cfg["risk_per_trade"]
        out = paper.size_shares(entry, stop, equity, book)
        assert out["capped"] is False
        # Never over budget, and within one share of it. Shares are whole, so a
        # 12-share position rounds down to $480 against a $500 budget — that
        # shortfall is the rounding being on the right side, not a sizing error.
        assert out["risk_dollars"] <= budget + 1e-6, book
        assert budget - out["risk_dollars"] < per_share, book


def test_every_book_declares_a_notional_cap():
    for book in paper.BOOK_IDS:
        cfg = paper.book_config(book)
        assert 0 < cfg["max_notional_pct"] <= 1.0, book
    caps = [paper.book_config(b)["max_notional_pct"] for b in
            ("conservative", "balanced", "aggressive")]
    assert caps == sorted(caps), "concentration must widen with risk appetite"


def test_scan_reports_positions_opened_across_all_books():
    """`opened` doubles as the loop's stop condition and counted the default book
    only, so a scan that opened sixteen positions across three books recorded four
    — understating the ledger's own activity by the factor the split introduced.
    The tally is separate from the control-flow counter so widening it does not
    cut scans short."""
    import inspect
    src = inspect.getsource(paper.run_scan)
    assert "opened_by_book" in src
    # The stored figure must be the total, not the default book's counter.
    assert "sum(opened_by_book.values())" in src
    # And the cap must still be driven by the original per-default counter.
    assert "if opened >= MAX_NEW_PER_SCAN" in src


# --------------------------------------------- shorts with unreachable targets
#
# Found by drawing the stop-to-target gauge in the open-positions table: LMB was
# on the live ledger three times over, short at $42.60 with a stop at $71.41 and
# a target of -$15.02. A stock cannot trade through zero, so those positions
# could only ever have exited at the stop or the time stop — while the record
# counted them as 2:1 reward-to-risk setups and the risk column implied a reward
# on the other side of it that was not there.

def _short_with_a_wide_stop(spot=42.60, resistance=70.70, score=-40.0):
    """The LMB setup: a short whose nearest resistance is 66% above the price."""
    return {"ticker": "LMB", "verdict": {"composite_score": score},
            "quote": {"price": spot},
            "technicals": {"support_resistance": [{"price": resistance}]}}


def test_a_short_target_below_zero_is_declined():
    found, notes = paper.consider_ticker(_short_with_a_wide_stop(), 100_000.0, "balanced")
    assert found == [], "opened a short whose target sits below zero"
    assert notes and "unreachable" in notes[0], notes


def test_the_declined_note_names_the_stop_width_and_the_target():
    """A note saying only "declined" is why the original bug went unnoticed."""
    _, notes = paper.consider_ticker(_short_with_a_wide_stop(), 100_000.0, "aggressive")
    assert "68%" in notes[0], notes          # (71.41 - 42.60) / 42.60
    assert "-15.02" in notes[0], notes


def test_a_short_with_a_normal_stop_still_trades():
    """The guard has to be narrow. A short with a 10% stop targets 20% lower,
    which is reachable, and declining it would quietly halve the strategy."""
    found, _ = paper.consider_ticker(
        _short_with_a_wide_stop(spot=100.0, resistance=108.9), 100_000.0, "balanced")
    assert found, "declined a short with a perfectly reachable target"
    for leg in found:
        assert leg["target"] > 0
        assert leg["direction"] in ("short", "long")   # a long put is stored long


def test_no_open_position_can_carry_a_target_at_or_below_zero():
    """The invariant the gauge depends on, stated once for every future entry."""
    for book in paper.BOOK_IDS:
        found, _ = paper.consider_ticker(_short_with_a_wide_stop(), 100_000.0, book)
        assert all((leg.get("target") or 1) > 0 for leg in found)
