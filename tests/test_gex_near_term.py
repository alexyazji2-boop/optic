"""O1 (Options audit): index GEX reads the 0-5 day expiries, separately.

The swing expiries start about a week out, so on SPY-like products the read
left out the expiries holding most of the open gamma. They are now read beside
the main total, with their share and the previous-session caveat."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

import app.main as m
from app.analytics import gex as gex_mod
from app.analytics import vol_surface as vs
from tests.test_options_research_api import FakeProvider, R, Q, SPOT, _chain

ROOT = Path(__file__).resolve().parents[1]


def _dates(*days):
    today = pd.Timestamp.now(tz="America/New_York").normalize()
    return [str((today + pd.Timedelta(days=d)).date()) for d in days]


def _read(chain):
    chain = vs.resolve_surface(vs.apply_quotes(vs.apply_clock(chain)), SPOT, R, Q)
    out = gex_mod.analyse(chain, SPOT, rate=R, div=Q, ticker="SPY")
    out.pop("_exposure_frame", None)
    return chain, out


def test_near_expiries_takes_zero_to_five_days_nearest_first():
    listed = _dates(31, 0, 9, 2, 5, 6, 1)
    assert m._near_expiries(listed) == _dates(0, 1, 2)
    assert m._near_expiries({"available": _dates(4, 12)}) == _dates(4)
    assert m._near_expiries(_dates(8, 30)) == []
    assert m._near_expiries(None) == []


def test_near_term_is_read_separately_with_its_share_of_gamma():
    swing, main_read = _read(_chain(_dates(10, 31)))
    near_chain = _chain(_dates(1, 3))
    got = m._near_term_gex("SPY", near_chain, swing, SPOT, R, Q, main_read)
    assert got["available"] is True
    assert got["expiries"] == _dates(1, 3)
    _, alone = _read(near_chain)
    # Same inputs; the clock moves a few seconds between the two reads.
    close = lambda a, b: abs(a - b) <= 1e-4 * max(abs(a), abs(b), 1.0)
    assert close(got["net_gex"], alone["totals"]["net_gex"])
    assert close(got["combined_net_gex"], main_read["totals"]["net_gex"] + alone["totals"]["net_gex"])
    share = alone["totals"]["gross_gex"] / (alone["totals"]["gross_gex"] + main_read["totals"]["gross_gex"]) * 100
    assert abs(got["share_of_gross_pct"] - share) < 0.1
    # Short-dated at-the-money gamma is larger per contract at equal OI.
    assert got["share_of_gross_pct"] > 50
    assert "previous session" in got["note"]
    # The main read is untouched: the near term sits beside it, not inside it.
    assert set(main_read["expiries_used"]) == set(_dates(10, 31))


def test_expiries_already_in_the_swing_read_are_not_counted_twice():
    swing, main_read = _read(_chain(_dates(3, 31)))
    got = m._near_term_gex("SPY", _chain(_dates(1, 3)), swing, SPOT, R, Q, main_read)
    assert got["expiries"] == _dates(1)
    none = m._near_term_gex("SPY", _chain(_dates(3)), swing, SPOT, R, Q, main_read)
    assert none["available"] is False and "beyond those already read" in none["reason"]


def test_empty_feed_says_so():
    swing, main_read = _read(_chain(_dates(10)))
    got = m._near_term_gex("SPY", pd.DataFrame(), swing, SPOT, R, Q, main_read)
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
