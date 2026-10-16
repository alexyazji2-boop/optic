"""O1 (Options audit): index GEX reads the 0-5 day expiries, separately.

The swing expiries start about a week out, so on SPY-like products the read
left out the expiries holding most of the open gamma. They are now read beside
the main total, with their share and the previous-session caveat."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

import app.main as m
from app.analytics import gex as gex_mod
from app.analytics import vol_surface as vs
from tests.test_options_research_api import FakeProvider, R, Q, SPOT, _chain

ROOT = Path(__file__).resolve().parents[1]
ET = ZoneInfo("America/New_York")

# Every read here is on a fixed clock. On the real one the figures moved with
# the time of day: the fixture's short-dated net, priced from cent-rounded
# quotes, swings by tens of thousands over an evening, and the reads a test
# compared were taken a few milliseconds apart.
NOW = datetime(2026, 10, 14, 11, 0, tzinfo=ET)            # a Wednesday morning
INSTANTS = {
    "weekday-morning": NOW,
    # The short-dated net is close to zero.
    "near-net-near-zero": datetime(2026, 10, 15, 18, 52, tzinfo=ET),
    # The swing and short-dated nets all but cancel, after the UTC date has
    # rolled and before the ET one has: an unpinned run failed here
    # (2026-10-16 00:56 UTC).
    "combined-near-zero": datetime(2026, 10, 16, 0, 56, tzinfo=timezone.utc),
    "after-et-midnight": datetime(2026, 10, 16, 0, 30, tzinfo=ET),
}


def _dates(*days, now=NOW):
    today = pd.Timestamp(now).tz_convert(ET).normalize()
    return [str((today + pd.Timedelta(days=d)).date()) for d in days]


def _read(chain, now=NOW):
    chain = vs.resolve_surface(vs.apply_quotes(vs.apply_clock(chain, now), now), SPOT, R, Q, american=True)
    out = gex_mod.analyse(chain, SPOT, rate=R, div=Q, ticker="SPY")
    out.pop("_exposure_frame", None)
    return chain, out


def test_near_expiries_takes_zero_to_five_days_nearest_first():
    listed = _dates(31, 0, 9, 2, 5, 6, 1)
    assert m._near_expiries(listed, NOW) == _dates(0, 1, 2)
    assert m._near_expiries({"available": _dates(4, 12)}, NOW) == _dates(4)
    assert m._near_expiries(_dates(8, 30), NOW) == []
    assert m._near_expiries(None, NOW) == []


def test_an_expiry_leaves_the_near_term_at_its_4pm_close_not_at_midnight():
    listed = ["2026-10-16", "2026-10-19", "2026-10-20"]
    assert m._near_expiries(listed, datetime(2026, 10, 16, 15, 59, tzinfo=ET)) == listed
    assert m._near_expiries(listed, datetime(2026, 10, 16, 16, 0, tzinfo=ET)) == listed[1:]
    # 9pm ET: the UTC date has rolled, the ET one has not; settled either way.
    assert m._near_expiries(listed, datetime(2026, 10, 17, 1, 0, tzinfo=timezone.utc)) == listed[1:]


@pytest.mark.parametrize("now", list(INSTANTS.values()), ids=list(INSTANTS))
def test_near_term_is_read_separately_with_its_share_of_gamma(now):
    swing, main_read = _read(_chain(_dates(10, 31, now=now), now), now)
    near_chain = _chain(_dates(1, 3, now=now), now)
    got = m._near_term_gex("SPY", near_chain, swing, SPOT, R, Q, main_read, now=now)
    assert got["available"] is True
    assert got["expiries"] == _dates(1, 3, now=now)
    _, alone = _read(near_chain, now)
    main_net, near_net = main_read["totals"]["net_gex"], alone["totals"]["net_gex"]
    # Same inputs on the same clock. The combined total is held to the size of
    # its parts, not of the sum: the two nets can all but cancel, and a
    # tolerance taken from a sum near zero is no tolerance at all.
    assert got["net_gex"] == pytest.approx(near_net, rel=1e-9)
    assert abs(got["combined_net_gex"] - (main_net + near_net)) <= 1e-9 * (abs(main_net) + abs(near_net))
    share = alone["totals"]["gross_gex"] / (alone["totals"]["gross_gex"] + main_read["totals"]["gross_gex"]) * 100
    assert abs(got["share_of_gross_pct"] - share) < 0.1
    # Short-dated at-the-money gamma is larger per contract at equal OI.
    assert got["share_of_gross_pct"] > 50
    assert "previous session" in got["note"]
    # The main read is untouched: the near term sits beside it, not inside it.
    assert set(main_read["expiries_used"]) == set(_dates(10, 31, now=now))


def test_expiries_already_in_the_swing_read_are_not_counted_twice():
    swing, main_read = _read(_chain(_dates(3, 31), NOW))
    got = m._near_term_gex("SPY", _chain(_dates(1, 3), NOW), swing, SPOT, R, Q, main_read, now=NOW)
    assert got["expiries"] == _dates(1)
    none = m._near_term_gex("SPY", _chain(_dates(3), NOW), swing, SPOT, R, Q, main_read, now=NOW)
    assert none["available"] is False and "beyond those already read" in none["reason"]


def test_empty_feed_says_so():
    swing, main_read = _read(_chain(_dates(10), NOW))
    got = m._near_term_gex("SPY", pd.DataFrame(), swing, SPOT, R, Q, main_read, now=NOW)
    assert got["available"] is False and got["reason"]


def test_the_gex_panel_shows_the_short_dated_line():
    js = (ROOT / "static" / "app.js").read_text()
    assert "function gexNearTermHTML(nt)" in js
    assert "${gexNearTermHTML(gex.near_term)}" in js
    assert "Short-dated expiries" in js


def test_only_the_tabs_parallel_read_fetches_it():
    src = (ROOT / "app" / "main.py").read_text()
    assert 'if parallel and ticker in gex_mod.INDEX_LIKE:' in src
    assert 'legs.start("near_chain", PROVIDER.options_chain' in src
