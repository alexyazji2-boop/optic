"""The overnight board's session rule, its action lines, and Home's cards.

**What was wrong.** `sector_board.build` took the price from the last daily
bar and the levels from the bar before it. That is right only while today's
bar exists. Before the open the last bar is the last *completed* session, so
the board compared Tuesday's close with Monday's range and called that the
overnight trend; after the bell it compared today's close with yesterday's
range, when the overnight question is the after-hours print against *today's*.
The levels are now the session that closed last (`session.last_regular_close`)
and the price is the newest print since that close, or the close itself, which
reads neutral and says why.

Every frame here is synthetic and dated, and every quote is injected, so no
test reaches a network: a provider whose `session_quotes` raises is used where
a test must prove it was not asked.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from datetime import date, datetime, timedelta, timezone

import pandas as pd
import pytest

from app import session as session_mod
from app.analytics import sector_board as sb

ET = session_mod.ET
XLK = [{"symbol": "XLK", "name": "Technology"}]
APP_JS = open("static/app.js", encoding="utf-8").read()
CSS = open("static/styles.css", encoding="utf-8").read()
MAIN = open("app/main.py", encoding="utf-8").read()


# ------------------------------------------------------------------ helpers

def et(y, m, d, hh=12, mm=0):
    return datetime(y, m, d, hh, mm, tzinfo=ET)


def iso(dt_):
    return dt_.astimezone(timezone.utc).isoformat()


def sessions_until(last: date, n: int):
    """The n trading days ending at `last`, by the exchange's calendar."""
    out, day = [], last
    while len(out) < n:
        if session_mod.regular_close(day) is not None:
            out.append(day)
        day -= timedelta(days=1)
    return list(reversed(out))


def frame(days, tail):
    """Flat 100s for the history, then `tail`: [(high, low, close)] for the
    last len(tail) of `days`, oldest first."""
    rows = [(100.0, 100.0, 100.0)] * (len(days) - len(tail)) + list(tail)
    return pd.DataFrame({
        "Open": [r[2] for r in rows], "High": [r[0] for r in rows],
        "Low": [r[1] for r in rows], "Close": [r[2] for r in rows],
        "Volume": [1_000_000] * len(rows),
    }, index=pd.DatetimeIndex([pd.Timestamp(d) for d in days]))


class Provider:
    """Daily bars only. `session_quotes` raises, so a test that injects
    quotes proves build() did not go looking for more."""

    def __init__(self, frames):
        self.frames = frames

    def batch_history(self, symbols, period="3mo", interval="1d"):
        return {s: self.frames[s] for s in symbols if s in self.frames}

    def session_quotes(self, tickers):
        raise AssertionError("build() fetched quotes it was handed")


def board(days, tail, now, quotes=None, provider=None):
    frames = {"XLK": frame(days, tail), "SPY": frame(days, tail)}
    return sb.build(provider or Provider(frames), XLK, now=now,
                    quotes={} if quotes is None else quotes)


def row(b):
    return b["rows"][0]


def quote(price=100.0, at=None, pre=None, pre_at=None, post=None, post_at=None):
    return {"XLK": {
        "price": price, "change_pct": 0.0,
        "regular_market_time": iso(at) if at else None,
        "pre_market_price": pre, "pre_market_change_pct": 1.0 if pre else None,
        "pre_market_time": iso(pre_at) if pre_at else None,
        "post_market_price": post, "post_market_change_pct": 1.0 if post else None,
        "post_market_time": iso(post_at) if post_at else None,
        "delayed_minutes": 0,
    }}


# Wednesday 2026-10-14. Monday's range 99.5 / 98, Tuesday's 101 / 99 with a
# close of 100: above Monday's high, inside its own range.
MON_TUE = [(99.5, 98.0, 99.0), (101.0, 99.0, 100.0)]
TO_TUE = sessions_until(date(2026, 10, 13), 25)
TO_WED = sessions_until(date(2026, 10, 14), 25)


# ------------------------------------------------------- the regular session

def test_regular_session_compares_todays_price_with_yesterdays_range():
    """Today's bar exists: the levels are Tuesday's, the price today's."""
    b = board(TO_WED, MON_TUE + [(999.0, 1.0, 98.0)], et(2026, 10, 14, 12, 40),
              quote(price=98.5, at=et(2026, 10, 14, 12, 39)))
    r = row(b)
    assert (r["bull_above"], r["bear_below"]) == (101.0, 99.0)
    assert r["levels_session"] == "2026-10-13"
    assert r["price"] == 98.5 and r["price_kind"] == "regular session"
    assert r["trend"] == "downtrend"
    assert b["basis"]["levels_label"] == "Tuesday's session"


def test_regular_session_without_a_quote_reads_todays_bar():
    """A quote that failed is the board's old behaviour, not an empty row."""
    r = row(board(TO_WED, MON_TUE + [(999.0, 1.0, 102.0)], et(2026, 10, 14, 12, 40)))
    assert r["price"] == 102.0 and r["price_kind"] == "regular session"
    assert r["price_as_of"] is None
    assert r["trend"] == "uptrend"


def test_a_quote_from_before_the_open_is_not_todays_price():
    """At 9:30:05 the quote can still carry yesterday's 4pm print. With no bar
    for today either, the price is Tuesday's close, and it says so."""
    r = row(board(TO_TUE, MON_TUE, et(2026, 10, 14, 9, 31),
                  quote(price=100.0, at=et(2026, 10, 13, 16, 0))))
    assert r["price_kind"] == "last close"
    assert r["trend"] == "neutral"
    assert "No trade from today's session" in r["note"]


# --------------------------------------------------------------- pre-market

def test_pre_market_without_any_print_is_the_close_and_reads_neutral():
    """The bug, pinned. At 8am the last bar is Tuesday's. Its close (100) is
    above Monday's high (99.5), so the positional read called XLK an
    overnight uptrend; it is Tuesday's close inside Tuesday's own range."""
    r = row(board(TO_TUE, MON_TUE, et(2026, 10, 14, 8, 0)))
    assert r["levels_session"] == "2026-10-13"
    assert (r["bull_above"], r["bear_below"]) == (101.0, 99.0)
    assert r["price"] == 100.0 and r["price_kind"] == "last close"
    assert r["trend"] == "neutral"
    assert "Nothing has printed since Tuesday's close" in r["note"]
    assert "by definition" in r["note"]


def test_pre_market_print_is_compared_with_the_last_completed_session():
    r = row(board(TO_TUE, MON_TUE, et(2026, 10, 14, 8, 0),
                  quote(pre=101.6, pre_at=et(2026, 10, 14, 7, 55))))
    assert r["price"] == 101.6 and r["price_kind"] == "pre-market"
    assert r["trend"] == "uptrend"
    assert r["price_as_of"] == iso(et(2026, 10, 14, 7, 55))
    assert r["note"] is None


def test_pre_market_with_no_pre_print_uses_last_nights_after_hours():
    """At 5am nobody has traded yet today, and last night's after-hours print
    is still a trade since Tuesday's close."""
    r = row(board(TO_TUE, MON_TUE, et(2026, 10, 14, 5, 0),
                  quote(post=98.4, post_at=et(2026, 10, 13, 19, 30))))
    assert r["price_kind"] == "after hours" and r["price"] == 98.4
    assert r["trend"] == "downtrend"


def test_a_pre_market_print_from_before_the_close_is_not_used():
    """Yahoo keeps yesterday morning's pre-market print on the quote. It was
    struck before the levels were set, inside the range it would be measured
    against, so it says nothing about leaving it."""
    r = row(board(TO_TUE, MON_TUE, et(2026, 10, 14, 6, 0),
                  quote(pre=104.0, pre_at=et(2026, 10, 13, 9, 0))))
    assert r["price_kind"] == "last close"
    assert r["trend"] == "neutral"


# --------------------------------------------------------------- after hours

def test_after_the_bell_the_levels_are_todays_session():
    wed = MON_TUE + [(103.0, 100.5, 102.0)]
    r = row(board(TO_WED, wed, et(2026, 10, 14, 17, 30),
                  quote(price=102.0, post=100.2, post_at=et(2026, 10, 14, 17, 20))))
    assert r["levels_session"] == "2026-10-14"
    assert (r["bull_above"], r["bear_below"]) == (103.0, 100.5)
    assert r["price_kind"] == "after hours"
    assert r["trend"] == "downtrend"
    assert r["action"]["text"] == "Reclaim $100.50 to turn neutral"


def test_after_hours_without_a_print_since_the_bell_is_todays_close():
    """Yesterday evening's after-hours print is not tonight's."""
    wed = MON_TUE + [(103.0, 100.5, 102.0)]
    b = board(TO_WED, wed, et(2026, 10, 14, 16, 5),
              quote(price=102.0, post=98.0, post_at=et(2026, 10, 13, 19, 59)))
    r = row(b)
    assert r["price"] == 102.0 and r["price_kind"] == "last close"
    assert r["trend"] == "neutral"
    assert "today's close" in r["note"]
    assert b["basis"]["levels_label"] == "today's session"


def test_a_half_day_closes_at_one():
    """The day after Thanksgiving: by 2pm the regular session is over, so the
    levels are that day's own, read from the exchange's calendar."""
    days = sessions_until(date(2026, 11, 27), 25)
    r = row(board(days, [(99.5, 98.0, 99.0), (101.0, 99.0, 100.0)], et(2026, 11, 27, 14, 0)))
    assert r["levels_session"] == "2026-11-27"


# ------------------------------------------------------ weekend and holiday

def test_the_weekend_compares_fridays_after_hours_with_fridays_range():
    fri = sessions_until(date(2026, 10, 16), 25)
    b = board(fri, MON_TUE, et(2026, 10, 17, 12, 0),
              quote(post=101.5, post_at=et(2026, 10, 16, 19, 50)))
    r = row(b)
    assert r["levels_session"] == "2026-10-16"
    assert r["price_kind"] == "after hours" and r["trend"] == "uptrend"
    assert b["basis"]["levels_label"] == "Friday's session"
    assert b["basis"]["phase"] == "closed"


def test_the_weekend_without_a_print_says_so():
    fri = sessions_until(date(2026, 10, 16), 25)
    r = row(board(fri, MON_TUE, et(2026, 10, 18, 10, 0)))
    assert r["price_kind"] == "last close" and r["trend"] == "neutral"
    assert "Friday's close" in r["note"]


def test_a_holiday_reads_the_session_before_it():
    """Thanksgiving: the market is shut all day and the levels are Wednesday's.
    A bar some feed dates on the holiday itself is ignored, not read as one."""
    wed = sessions_until(date(2026, 11, 25), 25)
    frames = frame(wed, MON_TUE)
    stray = pd.DataFrame({"Open": [100.0], "High": [120.0], "Low": [80.0], "Close": [119.0],
                          "Volume": [1]}, index=pd.DatetimeIndex([pd.Timestamp("2026-11-26")]))
    frames = pd.concat([frames, stray])
    b = sb.build(Provider({"XLK": frames, "SPY": frames}), XLK,
                 now=et(2026, 11, 26, 11, 0), quotes={})
    r = row(b)
    assert b["basis"]["phase"] == "holiday"
    assert r["levels_session"] == "2026-11-25"
    assert (r["bull_above"], r["bear_below"]) == (101.0, 99.0)
    assert r["price"] == 100.0 and r["trend"] == "neutral"


# ------------------------------------------------------------------ overnight

def test_an_overnight_print_is_compared_with_todays_range():
    wed = MON_TUE + [(103.0, 100.5, 102.0)]
    q = quote(price=102.0, post=102.2, post_at=et(2026, 10, 14, 19, 59))
    q["XLK"].update({"overnight_price": 103.4, "overnight_time": iso(et(2026, 10, 14, 21, 55)),
                     "overnight_venue": "Blue Ocean ATS", "overnight_change_pct": 1.4})
    r = row(board(TO_WED, wed, et(2026, 10, 14, 22, 0), q))
    assert r["levels_session"] == "2026-10-14"
    assert r["price_kind"] == "overnight" and r["price"] == 103.4
    assert r["price_venue"] == "Blue Ocean ATS"
    assert r["trend"] == "uptrend"
    assert r["action"]["text"] == "Hold $103.00, else neutral"


def test_after_midnight_the_levels_are_still_the_last_close():
    """00:00 to 04:00 is the same overnight session on the next date."""
    wed = MON_TUE + [(103.0, 100.5, 102.0)]
    r = row(board(TO_WED, wed, et(2026, 10, 15, 1, 0),
                  quote(price=102.0, post=100.0, post_at=et(2026, 10, 14, 19, 0))))
    assert r["levels_session"] == "2026-10-14"
    assert r["price_kind"] == "after hours" and r["trend"] == "downtrend"


def test_build_attaches_tonights_overnight_prints_itself(monkeypatch):
    """Left to fetch, build() asks the provider once for every board ETF and
    attaches the overnight venue's prints only inside the overnight window."""
    asked = []

    class Live(Provider):
        def session_quotes(self, tickers):
            asked.append(list(tickers))
            return {s: {"price": 102.0, "change_pct": 0.0} for s in tickers}

    found = {"XLK": {"symbol": "XLK", "price": 99.0, "time": iso(et(2026, 10, 14, 21, 0)),
                     "venue": "Bruce ATS", "bid": None, "ask": None, "previous_close": 102.0}}
    monkeypatch.setattr(sb.overnight_mod, "quotes", lambda symbols: found)
    wed = frame(TO_WED, MON_TUE + [(103.0, 100.5, 102.0)])
    b = sb.build(Live({"XLK": wed, "SPY": wed}), XLK, now=et(2026, 10, 14, 22, 0))
    assert asked == [sb.QUOTE_SYMBOLS], "one request, every board ETF"
    r = row(b)
    assert r["price_kind"] == "overnight" and r["price"] == 99.0
    assert r["trend"] == "downtrend"


def test_a_quote_failure_falls_back_rather_than_failing():
    class Broken(Provider):
        def session_quotes(self, tickers):
            raise RuntimeError("Yahoo said 401")

    wed = frame(TO_WED, MON_TUE + [(999.0, 1.0, 102.0)])
    b = sb.build(Broken({"XLK": wed, "SPY": wed}), XLK, now=et(2026, 10, 14, 12, 0))
    assert row(b)["price"] == 102.0 and row(b)["trend"] == "uptrend"


def test_the_levels_say_which_session_when_the_feed_is_behind():
    """After the bell with no bar for today yet: the levels are Tuesday's and
    the row says so rather than labelling them today's."""
    r = row(board(TO_TUE, MON_TUE, et(2026, 10, 14, 16, 30),
                  quote(post=98.0, post_at=et(2026, 10, 14, 16, 20))))
    assert r["levels_session"] == "2026-10-13"
    assert "no bar for today's session yet" in r["note"]
    assert "Tuesday's session" in r["note"]


def test_a_tz_aware_index_is_read_in_new_york():
    """Midnight ET is 04:00 UTC the same day; truncating a UTC stamp would put
    every bar on the right day only by luck."""
    f = frame(TO_TUE, MON_TUE)
    f.index = f.index.tz_localize(ET)
    b = sb.build(Provider({"XLK": f, "SPY": f}), XLK, now=et(2026, 10, 14, 8, 0), quotes={})
    assert row(b)["levels_session"] == "2026-10-13"


def test_plain_frames_keep_the_positional_read_and_ask_for_nothing():
    """The frames test_sector_board builds have no dates. They keep the old
    read, and build() does not reach for quotes it could not place."""
    plain = frame(TO_WED, MON_TUE + [(999.0, 1.0, 102.0)]).reset_index(drop=True)
    b = sb.build(Provider({"XLK": plain, "SPY": plain}), XLK)
    r = row(b)
    assert r["price"] == 102.0 and r["levels_session"] is None and r["price_kind"] is None
    assert (r["bull_above"], r["bear_below"]) == (101.0, 99.0)


# ------------------------------------------------------ the defend lines

@pytest.mark.parametrize("trend,text", [
    ("downtrend", "Reclaim $99.00 to turn neutral"),
    ("uptrend", "Hold $101.00, else neutral"),
    ("neutral", "Above $101.00 turns bullish, below $99.00 bearish"),
])
def test_the_action_names_the_level_that_changes_the_state(trend, text):
    act = sb._action(trend, 101.0, 99.0)
    assert act["text"] == text
    assert act["kind"] == {"downtrend": "reclaim", "uptrend": "hold", "neutral": "range"}[trend]


def test_the_action_prints_prices_as_money():
    assert sb._action("downtrend", 2000.0, 1234.5)["text"] == "Reclaim $1,234.50 to turn neutral"


@pytest.mark.parametrize("trend,text", [
    ("downtrend", "-1.46% vs prior session low"),
    ("uptrend", "+0.24% vs prior session high"),
    ("neutral", "-1.11% to prior high"),
])
def test_each_state_is_measured_from_its_own_level(trend, text):
    up = {"downtrend": -3.0, "uptrend": 0.24, "neutral": -1.11}[trend]
    down = {"downtrend": -1.46, "uptrend": 2.0, "neutral": 0.5}[trend]
    pct, line = sb._vs_level(trend, up, down)
    assert line == text
    assert pct == float(text.split("%")[0])


def test_every_row_carries_the_new_fields():
    r = row(board(TO_WED, MON_TUE + [(999.0, 1.0, 98.0)], et(2026, 10, 14, 12, 40)))
    for key in ("vs_level_pct", "vs_level_text", "action", "levels_session", "price_kind",
                "price_as_of", "note", "to_break_pct", "to_breakdown_pct", "summary"):
        assert key in r, key
    assert r["price_kind"] in sb.PRICE_KINDS
    for kind in ("'last close'", "'regular session'"):
        assert kind in APP_JS, "the client compares against the server's vocabulary"
    assert all(k.strip("'") in sb.PRICE_KINDS for k in ("'last close'", "'regular session'"))


# --------------------------------------------------------------- the basis

def test_the_basis_names_each_delayed_symbol_and_the_span_of_prints():
    frames = {s: frame(TO_WED, MON_TUE + [(999.0, 1.0, 98.0)]) for s in ("XLK", "QQQ", "SPY")}
    q = {"XLK": quote(98.0, et(2026, 10, 14, 12, 30))["XLK"],
         "QQQ": dict(quote(98.0, et(2026, 10, 14, 12, 38))["XLK"], delayed_minutes=15)}
    b = sb.build(Provider(frames), [{"symbol": "XLK", "name": "Technology"},
                                    {"symbol": "QQQ", "name": "Nasdaq 100"}],
                 now=et(2026, 10, 14, 12, 40), quotes=q)
    basis = b["basis"]
    assert basis["delayed"] == [{"symbol": "QQQ", "minutes": 15}]
    assert basis["price_as_of_from"] == iso(et(2026, 10, 14, 12, 30))
    assert basis["price_as_of"] == iso(et(2026, 10, 14, 12, 38))
    assert basis["price_kinds"] == {"regular session": 2}


def test_trends_is_both_boards_with_the_three_index_cards_and_one_basis():
    days = TO_WED
    tail = MON_TUE + [(999.0, 1.0, 98.0)]
    frames = {e["symbol"]: frame(days, tail) for e in sb.INDEX_ETFS + sb.SECTORS}
    out = sb.trends(Provider(frames), now=et(2026, 10, 14, 12, 40), quotes={})
    assert [r["symbol"] for r in out["indices"]] == ["SPY", "QQQ", "IWM"]
    assert len(out["sectors"]) == 11
    assert sum(out["basis"]["price_kinds"].values()) == 14, "DIA is not counted"
    assert "Rotation" not in out["method"], "Home shows no rotation"


def test_the_method_describes_the_session_rule():
    note = sb._method(sb.SECTORS)
    assert "no futures feed" in note.lower()
    assert "regular-session daily bars" in note
    assert "Outside it" in note and "extended-hours print since that close" in note
    assert "reads neutral" in note


def test_price_view_takes_the_state_it_was_handed():
    """The board reads the clock once for fifteen quotes."""
    when = et(2026, 10, 14, 8, 0)
    q = quote(pre=101.6, pre_at=et(2026, 10, 14, 7, 55))["XLK"]
    sess = session_mod.state(when)
    assert session_mod.price_view(q, when, sess) == session_mod.price_view(q, when)


def test_no_em_dash_in_what_the_board_says():
    rows = [row(board(TO_TUE, MON_TUE, et(2026, 10, 14, 8, 0))),
            row(board(TO_WED, MON_TUE + [(999.0, 1.0, 98.0)], et(2026, 10, 14, 12, 40)))]
    text = json.dumps(rows) + sb._method(sb.SECTORS)
    assert "—" not in text


# ------------------------------------------------------- the provider read

def test_session_quotes_is_one_request_for_every_symbol(monkeypatch):
    from app.providers import yf as yf_mod

    calls = []

    class Data:
        def get_raw_json(self, url, params=None, timeout=30):
            calls.append((url, dict(params or {})))
            return {"quoteResponse": {"result": [
                {"symbol": "SPY", "regularMarketPrice": 770.2, "regularMarketTime": 1792000000,
                 "postMarketPrice": 771.0, "postMarketChangePercent": 0.1,
                 "postMarketTime": 1792010000, "exchangeDataDelayedBy": 0},
                {"symbol": "QQQ", "regularMarketPrice": 731.4, "exchangeDataDelayedBy": 15},
            ]}}

    class Ticker:
        def __init__(self, symbol):
            self._data = Data()

    monkeypatch.setattr(yf_mod.yf, "Ticker", Ticker)
    yf_mod._CACHE.pop("sessq:QQQ,SPY", None)
    got = yf_mod.YFinanceProvider().session_quotes(["SPY", "QQQ", "SPY"])
    yf_mod._CACHE.pop("sessq:QQQ,SPY", None)
    assert len(calls) == 1 and calls[0][1]["symbols"] == "QQQ,SPY"
    assert calls[0][0].endswith("/v7/finance/quote")
    assert got["SPY"]["post_market_price"] == 771.0
    assert got["SPY"]["post_market_time"].startswith("2026-")
    assert got["QQQ"]["delayed_minutes"] == 15


def test_session_quotes_failure_is_empty(monkeypatch):
    from app.providers import yf as yf_mod

    class Ticker:
        def __init__(self, symbol):
            raise RuntimeError("no network in tests")

    monkeypatch.setattr(yf_mod.yf, "Ticker", Ticker)
    yf_mod._CACHE.pop("sessq:XLK", None)
    assert yf_mod.YFinanceProvider().session_quotes(["XLK"]) == {}


def test_the_route_serves_the_combined_board():
    assert '@app.get("/api/trends/board")' in MAIN
    route = MAIN[MAIN.index('@app.get("/api/trends/board")'):]
    route = route[:route.index("@app.get(", 10)]
    assert "sector_board_mod.trends(YF_PROVIDER)" in route


# ============================================================== the client

def _fn(name: str) -> str:
    start = APP_JS.index("function %s(" % name)
    nxt = APP_JS.find("\nfunction ", start + 1)
    nxt_async = APP_JS.find("\nasync function ", start + 1)
    ends = [i for i in (nxt, nxt_async) if i > 0]
    return APP_JS[start:min(ends) if ends else len(APP_JS)]


def test_the_home_block_is_rendered_inside_the_market_screen_and_loaded():
    market = _fn("loadHomeMarket")
    assert "${homeTrendsHTML()}" in market
    board = market[market.index('<div class="hm-board">'):]
    assert board.index("${homeTrendsHTML()}") < board.index('<div class="hm-main">'), \
        "the trends row is the board's own child, across both columns"
    assert "loadHomeTrends();" in market
    assert "homeTrendsPayload().catch(() => {});" in _fn("renderHome"), "the head start"


def test_the_loader_fetches_one_endpoint_and_reads_its_host_after_the_await():
    assert "getJSON('/api/trends/board')" in _fn("homeTrendsPayload")
    fn = _fn("loadHomeTrends")
    after = fn[fn.index("await homeTrendsPayload()"):]
    assert "document.getElementById('hm-trends')" in after
    assert "if (!host || STATE.view !== 'home') return;" in after


def test_the_three_surfaces_share_one_vocabulary():
    card = _fn("trendCardHTML")
    for name in ("trendCardHTML", "renderIndexBoard", "renderSectorBoard"):
        body = _fn(name)
        assert "SECTOR_TREND_LABEL[r.trend]" in body, name
        assert "SECTOR_TREND_CLASS[r.trend]" in body, name
        assert "(r.action || {}).text" in body, name
    assert "r.vs_level_text" in card and "r.vs_level_text" in _fn("renderIndexBoard")
    # The table carries it under the trend chip, not as an eleventh column.
    assert '<span class="sec-action">' in _fn("renderSectorBoard")
    assert ".sector-board .sec-action[hidden]" in CSS
    for name in ("homeTrendsInner", "renderIndexBoard", "renderSectorBoard"):
        assert "trendBasisLine(" in _fn(name), name


def test_the_label_maps_are_declared_before_anything_reads_them():
    """A const read before its line has run is a temporal dead zone, and the
    jsc harness stops part-way through the file."""
    decl = APP_JS.index("const SECTOR_TREND_LABEL = {")
    assert APP_JS.count("const SECTOR_TREND_LABEL = {") == 1
    assert decl < APP_JS.index("function trendCardHTML(")
    assert decl < APP_JS.index("function renderSectorBoard(")


def test_a_card_opens_its_etf_through_the_existing_handler():
    assert 'data-analyse="${esc(r.symbol)}"' in _fn("trendCardHTML")
    assert "closest('[data-analyse]')" in APP_JS


def test_the_heading_is_not_the_assistants_old_name():
    inner = _fn("homeTrendsInner")
    assert '<h2 class="hm-h">Index and sector trends</h2>' in inner
    assert "Pulse" not in inner and "Pulse" not in _fn("trendCardHTML")
    assert 'data-go-view="market"' in inner and "closest('[data-go-view]')" in APP_JS


def test_every_class_the_block_draws_has_a_rule():
    used = set()
    for name in ("homeTrendsInner", "trendCardHTML", "homeTrendsHTML"):
        for attr in re.findall(r'class="([^"$]*)', _fn(name)):
            used.update(t for t in attr.split() if t.startswith("tr-"))
    assert {"tr-card", "tr-top", "tr-sym", "tr-price", "tr-name", "tr-vs", "tr-act",
            "tr-grid", "tr-basis", "tr-group", "tr-kind", "tr-skel"} <= used, used
    for cls in used:
        assert re.search(r"\.%s\b" % re.escape(cls), CSS), cls


def _trend_css():
    start = CSS.index("Home: index and sector trends")
    return CSS[start:CSS.index("/* ===", start)]


def test_the_block_s_css_keeps_the_house_rules():
    block = _trend_css()
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", block), "a hex colour"
    for sel in re.findall(r"\n(\.[\w-]+(?:\.[\w-]+)?) \{[^}]*display:", block):
        assert "%s[hidden]" % sel in block, sel
    hovers = [m.start() for m in re.finditer(r":hover", block)]
    media = block.find("@media (hover: hover)")
    assert hovers and media >= 0 and all(h > media for h in hovers)
    assert block.index("@media (max-width: 559px)") > block.index(".tr-grid {"), \
        "the phone override comes after the rule it overrides"
    assert "hover-gold" not in block, "the gold pill is the sidebar's alone"


def test_the_one_column_order_places_the_block_after_the_market_moves():
    rules = CSS[CSS.index("@container hm-market (max-width: 671px)"):]
    rules = rules[:rules.index("\n}\n")]
    order = dict(re.findall(r"\.hm-board ([^{]+?) \{ order: (\d+); \}", rules))
    assert int(order["#hm-trends"]) == int(order[".cc-now"]) + 1
    assert int(order[".hm-block:has(#cc-movers)"]) > int(order["#hm-trends"])


def test_no_em_dash_in_the_new_client_copy():
    for name in ("homeTrendsInner", "trendCardHTML", "trendBasisLine"):
        body = re.sub(r"/\*.*?\*/", "", _fn(name), flags=re.S)
        assert "—" not in body, name


def _jsc():
    exe = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc"
    return exe if os.path.exists(exe) else shutil.which("jsc")


def _const(name):
    start = APP_JS.index("const %s = " % name)
    return APP_JS[start:APP_JS.index(";\n", start) + 2]


def test_a_card_renders_a_real_row_under_javascriptcore():
    """The renderer run on a row build() actually wrote, so a field the card
    names and the server does not write fails here instead of in a blank
    line on Home."""
    exe = _jsc()
    if not exe:
        pytest.skip("no JavaScriptCore on this machine")
    b = board(TO_WED, MON_TUE + [(999.0, 1.0, 98.0)], et(2026, 10, 14, 12, 40),
              quote(price=98.5, at=et(2026, 10, 14, 12, 39)))
    pre = row(board(TO_TUE, MON_TUE, et(2026, 10, 14, 8, 0)))
    src = "\n".join([
        "function esc(s) { return String(s == null ? '' : s).replace(/&/g,'&amp;')"
        ".replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/\"/g,'&quot;'); }",
        "function fmt(v, d) { return Number(v).toFixed(d); }",
        "function activeZone() { return 'America/New_York'; }",
        "function timeIn(iso) { return iso ? '12:39 pm' : ''; }",
        _const("SECTOR_TREND_LABEL"), _const("SECTOR_TREND_CLASS"), _const("SECTOR_TREND_ARROW"),
        _fn("trendCardHTML"), _fn("trendBasisLine"),
        "var row = %s; var pre = %s; var basis = %s;" % (
            json.dumps(row(b)), json.dumps(pre), json.dumps(b["basis"])),
        "var night = Object.assign({}, basis, {price_kind: 'after hours',"
        " price_as_of: '2026-10-13T23:40:00+00:00', price_as_of_from: '2026-10-13T23:40:00+00:00',"
        " price_kinds: {'after hours': 9, 'last close': 5}, delayed: []});",
        "print(JSON.stringify({card: trendCardHTML(row, basis.price_kind),"
        " pre: trendCardHTML(pre, 'regular session'), line: trendBasisLine(basis),"
        " night: trendBasisLine(night)}));",
    ])
    out = subprocess.run([exe, "-e", src], capture_output=True, text=True, timeout=30)
    got = json.loads(out.stdout.strip().splitlines()[-1])
    card = got["card"]
    assert "Overnight Downtrend" in card and "tr-card is-down" in card
    assert "Reclaim $99.00 to turn neutral" in card
    assert "vs prior session low" in card and "$98.50" in card
    assert 'data-analyse="XLK"' in card
    assert "Price: last close" in got["pre"], "a card priced off the board's kind says so"
    # Last night's print at 8am names its day, and the closes are counted.
    assert "Price: after hours, as of Tue 12:39 pm." in got["night"], got["night"]
    assert "5 of 14 have not traded since that close" in got["night"]
    # The weekday appears when the print is not from the day the test runs.
    assert re.fullmatch(r"Levels: Tuesday's session\. Price: regular session, as of "
                        r"(?:Wed )?12:39 pm\.", got["line"]), got["line"]
