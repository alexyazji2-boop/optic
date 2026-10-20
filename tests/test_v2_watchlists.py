"""Watchlists as a daily workflow (backlog task 2, 2026-10-20).

Server: the feed's volume context and bar date, the next-earnings lookup, one company per share class,
and a guest's lists brought into an account as lists. Client: the sorts (missing figures last, ties in
list order), the share-class rule, and a guest browser that refuses to save. The page itself was
checked in headless Chrome at 360, 390, 430, 768 and 1440 px, signed in and as a guest
(~/Optic/work/v2-backlog/wl_check.py: add, duplicate, remove and Undo in place, My order across a
reload, the sort across a reload, the feed failing, the row's detail, Escape, Show on Home).
"""
from datetime import date, datetime, timezone

import numpy as np
import pandas as pd
import pytest

from app.analytics import watchlist
from tests.test_account_data import client, post, signed_in  # noqa: F401  (the fixture)
from tests.test_frontend_v2_stage0 import V2, _run

JS = V2 / "js"


class _Provider:
    def __init__(self, frames, earn=None):
        self.frames, self.earn = frames, earn or {}

    def batch_history(self, tickers, period="1y", interval="1d"):
        return {t: self.frames[t] for t in tickers if t in self.frames}

    def earnings_date(self, sym):
        if self.earn.get(sym) == "boom":
            raise RuntimeError("provider down")
        return self.earn.get(sym)


def _frame(n, last_day, vol_last=2_000_000.0):
    idx = pd.bdate_range(end=last_day, periods=n)
    vols = np.full(n, 1_000_000.0); vols[-1] = vol_last
    return pd.DataFrame({"Close": np.linspace(100, 110, n), "Volume": vols}, index=idx)


@pytest.fixture(autouse=True)
def _clear(accounts):
    # an empty accounts database and no cookies for every test, as test_account_data does
    client.cookies.clear()
    watchlist._cache.clear()
    yield
    watchlist._cache.clear()


def test_a_row_carries_volume_against_its_average_and_its_bar_date():
    p = _Provider({"AAPL": _frame(80, "2026-10-16"), "SPY": _frame(80, "2026-10-16")})
    # a Monday evening: the Friday bar is a full session
    row = watchlist.build(p, ["AAPL"], now=datetime(2026, 10, 19, 22, 0, tzinfo=timezone.utc))["rows"][0]
    assert row["as_of"] == "2026-10-16"
    assert row["volume"] == 2_000_000 and row["avg_volume_20d"] == 1_000_000
    assert row["volume_ratio"] == 2.0 and row["volume_partial"] is False


def test_volume_during_the_session_is_said_to_be_part_of_a_day():
    p = _Provider({"AAPL": _frame(80, "2026-10-20", 400_000.0), "SPY": _frame(80, "2026-10-20")})
    # 11:00 ET on Tuesday 20 October: the last bar is today's, still trading
    row = watchlist.build(p, ["AAPL"], now=datetime(2026, 10, 20, 15, 0, tzinfo=timezone.utc))["rows"][0]
    assert row["volume_partial"] is True and row["volume_ratio"] == 0.4


def test_too_little_history_gives_no_volume_figure_rather_than_a_guess():
    p = _Provider({"NEW": _frame(4, "2026-10-16"), "SPY": _frame(80, "2026-10-16")})
    row = watchlist.build(p, ["NEW"], now=datetime(2026, 10, 19, 22, 0, tzinfo=timezone.utc))["rows"][0]
    assert row["volume_ratio"] is None and row["avg_volume_20d"] is None


def test_next_earnings_is_a_future_date_or_none_never_a_past_one():
    p = _Provider({}, earn={"AAPL": "2026-11-02", "OLD": "2026-07-30", "SPY": None, "BAD": "boom"})
    got = watchlist.earnings_dates(p, ["AAPL", "OLD", "SPY", "BAD"], today=date(2026, 10, 20))["dates"]
    assert got["AAPL"] == {"date": "2026-11-02", "days": 13}
    assert got["OLD"] == {"date": None, "days": None}       # already reported: not "next"
    assert got["SPY"]["date"] is None and got["BAD"]["date"] is None   # a fund, a failed lookup


def test_a_share_class_is_one_entry_however_it_is_typed(signed_in):  # noqa: F811
    csrf = signed_in["csrf"]
    wid = post("/api/watchlists", csrf, name="Classes").json()["watchlist"]["id"]
    for typed in ("BRK.B", "brk-b", "BRK B"):
        post("/api/watchlists/{}/items".format(wid), csrf, symbol=typed)
    post("/api/watchlists/{}/items".format(wid), csrf, symbol="VOD.L")   # an exchange suffix is left alone
    syms = [w for w in client.get("/api/watchlists").json()["watchlists"] if w["id"] == wid][0]["symbols"]
    assert syms == ["BRK-B", "VOD.L"]
    gone = client.delete("/api/watchlists/{}/items/BRK.B".format(wid), headers={"X-Optic-CSRF": csrf})
    assert gone.json()["watchlist"]["symbols"] == ["VOD.L"]


def test_a_guests_lists_come_into_the_account_as_lists(signed_in):  # noqa: F811
    csrf = signed_in["csrf"]
    post("/api/watchlists", csrf, name="Tech", symbols=["AAPL"])
    reply = post("/api/watchlists/adopt", csrf, lists=[
        {"name": "tech", "symbols": ["NVDA", "AAPL"]},     # the account has Tech: merged into it
        {"name": "Income", "symbols": ["O", "VZ"]},       # new: becomes a list
        {"name": "Empty", "symbols": []},                 # nothing to bring: skipped
    ]).json()
    lists = {w["name"]: w["symbols"] for w in reply["watchlists"]}
    assert lists["Tech"] == ["AAPL", "NVDA"] and lists["Income"] == ["O", "VZ"] and "Empty" not in lists
    assert reply["added"] == 3 and reply["created"] == ["Income"]
    again = post("/api/watchlists/adopt", csrf, lists=[{"name": "Income", "symbols": ["O", "VZ"]}]).json()
    assert again["added"] == 0 and again["created"] == []   # twice adds nothing


def test_past_the_plans_limit_a_list_merges_into_the_first_and_says_so(signed_in):  # noqa: F811
    from app.auth import store as auth_store
    csrf = signed_in["csrf"]
    limit = auth_store.PLANS["free"]["watchlists"]
    for i in range(limit):
        post("/api/watchlists", csrf, name="L{}".format(i), symbols=["SPY"])
    reply = post("/api/watchlists/adopt", csrf, lists=[{"name": "Overflow", "symbols": ["TSLA"]}]).json()
    assert reply["created"] == [] and reply["merged"] == [{"name": "Overflow", "into": "L0"}]
    assert "TSLA" in {w["name"]: w["symbols"] for w in reply["watchlists"]}["L0"]


def test_sorting_puts_missing_figures_last_and_keeps_list_order_on_ties(tmp_path):
    got = _run(tmp_path, f"""
      const w = await import('{(JS / "pages/watchlist.js").as_posix()}');
      const rows = [
        {{ symbol: 'A', available: true, change_pct: 1, volume_ratio: null }},
        {{ symbol: 'B', available: false }},
        {{ symbol: 'C', available: true, change_pct: null, volume_ratio: 2 }},
        {{ symbol: 'D', available: true, change_pct: -3, volume_ratio: 2 }},
        {{ symbol: 'E', available: true, change_pct: 1, volume_ratio: 0.5 }},
      ];
      const ids = (s) => w.sortRows(rows, s).map((r) => r.symbol).join('');
      print(JSON.stringify({{ gainers: ids('gainers'), losers: ids('losers'), movers: ids('movers'), volume: ids('volume'), alpha: ids('alpha'), custom: ids('custom') }}));
    """)
    assert got["gainers"] == "AEDCB"     # C has no change figure: after the figures, before the unpriced
    assert got["losers"] == "DAECB"
    assert got["movers"] == "DAECB"
    assert got["volume"] == "CDEAB"      # C and D tie at 2: list order
    assert got["alpha"] == "ABCDE" and got["custom"] == "ABCDE"   # these ignore availability


def test_the_share_class_rule_and_a_browser_that_will_not_save(tmp_path):
    got = _run(tmp_path, f"""
      const s = await import('{(JS / "core/store.js").as_posix()}');
      const canon = ['brk.b', 'BRK-B', 'brk b', 'BF/B', 'VOD.L', 'aapl', 'RDS.A'].map(s.canon);
      localStorage.setItem('optic.session.holder.v1', 'guest');
      await s.loadLists();
      await s.follow('AAPL');
      const real = localStorage.setItem;
      localStorage.setItem = (k, v) => {{ if (String(k).startsWith('optic.watchlists') || k === 'optic.chart.watch.v1') throw new Error('QuotaExceededError'); return real(k, v); }};
      let said = '';
      try {{ await s.follow('MSFT'); }} catch (e) {{ said = e.message; }}
      print(JSON.stringify({{ canon, syms: s.activeList().symbols, said }}));
    """)
    assert got["canon"] == ["BRK-B", "BRK-B", "BRK-B", "BF-B", "VOD.L", "AAPL", "RDS-A"]
    assert got["syms"] == ["AAPL"]                 # MSFT was put back off the list
    assert "would not save" in got["said"]


def test_the_page_says_where_lists_live_and_offers_undo_in_the_page():
    src = (JS / "pages/watchlist.js").read_text()
    assert "Only in this browser." in src and "On your account: saved as you change it" in src
    assert 'data-v2-wl-undo' in src and 'data-v2-wl-reorder' in src
    assert "store.follow(sym, id, { at })" in src          # Undo puts a removal back where it was
    company = (JS / "ui/company.js").read_text()
    assert "Show on Home" in company and "hrefFor('overview', sym)" in company
    assert "store.unfollow(sym, id)" in company              # Undo of an add takes it off that list only
