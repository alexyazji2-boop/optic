"""A futures day change says which settlement it is measured from.

At 7 PM ET on Tuesday 27 October 2026 the instrument page for WTI read "Last 99.88 -0.02%": Wednesday's session so
far, since Tuesday's 99.90 settle, which is the exchange's convention and what `apply_quote` deliberately keeps. Beside
it Home's stocks still showed Tuesday, and the chart's readout said -1.85% for a bar Yahoo had dated Oct 27 that was
really the evening session (the real Oct 27 bar was missing until after midnight). Crude had fallen 1.83% on Tuesday
(99.90 against Monday's 101.76). The figure stays; the page now says its base, and from the 6 PM reopen to the 9:30
stock open it also gives the session that settled (investor audit, 2026-10-27).
"""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

from app.analytics import series_stats as S

NY = ZoneInfo("America/New_York")


def at(text):
    return datetime.strptime(text, "%Y-%m-%d %H:%M").replace(tzinfo=NY)


@pytest.mark.parametrize("now, trade, settle, split", [
    ("2026-10-27 08:00", "2026-10-27", "2026-10-26", True),    # Tue before the stock open: Tue's futures session, stocks still Mon
    ("2026-10-27 10:00", "2026-10-27", "2026-10-26", False),   # Tue in the session: both on Tue
    ("2026-10-27 17:30", "2026-10-27", "2026-10-26", False),   # Tue in the daily break, before the reopen
    ("2026-10-27 19:00", "2026-10-28", "2026-10-27", True),    # Tue after the reopen: Wed's session since Tue's settle
    ("2026-10-28 01:00", "2026-10-28", "2026-10-27", True),    # Wed overnight
    ("2026-10-30 19:00", "2026-10-30", "2026-10-29", False),   # Fri evening: no reopen until Sunday
    ("2026-10-31 12:00", "2026-10-30", "2026-10-29", False),   # Saturday: Friday's session
    ("2026-11-01 19:00", "2026-11-02", "2026-10-30", True),    # Sunday after the reopen: Monday's session since Friday's settle
    ("2026-11-26 12:00", "2026-11-25", "2026-11-24", False),   # Thanksgiving: Wednesday's session
])
def test_the_settlement_a_futures_change_is_measured_from(now, trade, settle, split):
    b = S.futures_basis(at(now))
    assert (b["trade_date"].isoformat(), b["settle_date"].isoformat(), b["split"]) == (trade, settle, split)


def _evening_bars():
    """CL=F's daily bars as Yahoo served them at 7 PM on 27 Oct 2026: the evening session dated Oct 27."""
    idx = pd.to_datetime(["2026-10-22", "2026-10-23", "2026-10-26", "2026-10-27"]).tz_localize(NY)
    return pd.DataFrame({"Close": [99.47, 103.27, 101.76, 99.89], "Volume": [301805, 331867, 331867, 1768]}, index=idx)


def test_after_the_reopen_the_page_gets_the_base_and_the_session_that_settled():
    snap = S.apply_quote({"label": "WTI Crude", "chg_1d": -1.84}, {"last": 99.88, "prev_close": 99.90},
                         frame=_evening_bars(), symbol="CL=F", now=at("2026-10-27 19:00"))
    assert snap["chg_1d"] == pytest.approx(-0.02, abs=0.001), "the exchange's figure is kept"
    assert snap["chg_1d_basis"] == {"since": "settle", "settle_date": "2026-10-27", "settle_day": "Tue", "split": True}
    assert snap["session_chg"] == pytest.approx(-1.828, abs=0.001), "Tuesday's settle against Monday's, not the misdated bar"
    assert snap["session_date"] == "2026-10-27"


def test_in_the_session_only_the_base_is_said():
    snap = S.apply_quote({"label": "WTI Crude"}, {"last": 101.77, "prev_close": 99.90}, frame=_evening_bars(),
                         symbol="CL=F", now=at("2026-10-28 10:18"))
    assert snap["chg_1d_basis"]["split"] is False and snap["chg_1d_basis"]["settle_day"] == "Tue"
    assert "session_chg" not in snap


def test_a_cash_index_and_a_coin_are_unchanged():
    for sym in ("^GSPC", "BTC-USD"):
        snap = S.apply_quote({"label": sym}, {"last": 101.0, "prev_close": 100.0}, frame=_evening_bars(),
                             symbol=sym, now=at("2026-10-27 19:00"))
        assert "chg_1d_basis" not in snap and "session_chg" not in snap and snap["chg_1d"] == pytest.approx(1.0)


def test_no_session_figure_without_the_settlement_before():
    snap = S.apply_quote({"label": "WTI Crude"}, {"last": 99.88, "prev_close": 99.90}, frame=None,
                         symbol="CL=F", now=at("2026-10-27 19:00"))
    assert snap["chg_1d_basis"]["split"] is True and "session_chg" not in snap, "never a figure the feed did not give"
