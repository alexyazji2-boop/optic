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
