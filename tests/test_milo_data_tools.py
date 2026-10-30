"""Milo's data tools (app/milo_data.py) and the freshness envelope on every tool (2026-10-25; brought into the
post-demo overhaul in Phase 08, 2026-10-29, from the milo-upgrade branch at 55721f6, with the portfolio tool's
privacy rule of this tree: offered only from the Brokerage page or for a question about the reader's own holdings).

What is checked: each new tool validates its input before anything runs; a good answer carries its source,
the time it describes, its units and the four flags (delayed, stale, partial, unavailable); the arithmetic
is code and matches a hand calculation; a provider failure is reported as a failure with no figures; a quote
or a bar series that is behind the session is called stale; and the two reader-specific tools return only
the asking reader's data, with no input that could name another reader.
"""
from __future__ import annotations

import asyncio
import json
import math
import types
from datetime import datetime, timezone

import pandas as pd
import pytest

from app import ai, milo_data, milo_tools


def run(coro):
    return asyncio.run(coro)


def frame(closes, start="2026-07-01", freq="B"):
    idx = pd.date_range(start, periods=len(closes), freq=freq)
    return pd.DataFrame({"Open": closes, "High": [c + 1 for c in closes], "Low": [c - 1 for c in closes],
                         "Close": closes, "Volume": [1000] * len(closes)}, index=idx)


def box(**runners):
    return milo_tools.Toolbox(runners=runners)


# ------------------------------------------------------------------------------------------ input

def test_new_tools_are_typed_and_validated_before_anything_runs():
    v = milo_tools.validate
    assert v("lookup_company", {"query": "  berkshire   hathaway "}) == {"query": "berkshire hathaway"}
    assert v("get_price_history", {"ticker": "msft", "period": "3m"}) == {"ticker": "MSFT", "period": "3m",
                                                                          "interval": "daily"}
    assert v("get_price_history", {"ticker": "MSFT", "period": "5y"})["interval"] == "weekly"
    assert v("get_filings", {"ticker": "aapl"}) == {"ticker": "AAPL", "limit": 10}
    assert v("get_financials", {"ticker": "^GSPC"}) == {"ticker": "^GSPC"}, "index symbols pass"
    bad = [("lookup_company", {"query": ""}), ("lookup_company", {"query": "x" * 61}),
           ("get_price_history", {"ticker": "MSFT", "period": "forever"}),
           ("get_price_history", {"ticker": "MSFT", "period": "1y", "interval": "hourly"}),
           ("get_filings", {"ticker": "AAPL", "limit": 0}), ("get_filings", {"ticker": "AAPL", "limit": True}),
           ("get_filings", {"ticker": "AAPL", "limit": 50}), ("get_financials", {"ticker": "DROP TABLE"}),
           ("get_financials", {"ticker": "AAPL", "user_id": "someone"})]
    for name, args in bad:
        with pytest.raises(milo_tools.InvalidInput):
            v(name, args)
    for spec in milo_tools.SPECS:
        assert spec["input_schema"]["additionalProperties"] is False
        assert not set(spec["input_schema"]["properties"]) & {"user", "user_id", "account", "account_id", "email"}


# ------------------------------------------------------------------------------------------ arithmetic

def test_window_statistics_are_computed_by_code_and_match_a_hand_calculation():
    closes = [100.0, 110.0, 99.0, 121.0]
    stats = milo_data.history_stats(closes, ["d1", "d2", "d3", "d4"], 252)
    assert stats["change_pct"] == 21.0 and stats["change"] == 21.0
    assert stats["high_close"] == {"date": "d4", "close": 121.0} and stats["low_close"]["date"] == "d3"
    assert stats["max_drawdown_pct"] == -10.0 and (stats["max_drawdown_from"], stats["max_drawdown_to"]) == ("d2", "d3")
    rets = [math.log(110 / 100), math.log(99 / 110), math.log(121 / 99)]
    mean = sum(rets) / 3
    vol = math.sqrt(sum((x - mean) ** 2 for x in rets) / 2) * math.sqrt(252) * 100
    assert stats["realised_vol_annualised_pct"] == round(vol, 2)
    assert milo_data.history_stats([100.0], ["d1"], 252) == {"bars": 1}


# ------------------------------------------------------------------------------------------ success

def test_price_history_returns_the_window_its_units_and_freshness():
    df = frame([100.0 + i for i in range(60)])
    out = milo_data.price_history(lambda t, period, interval: df, lambda t: {"currency": "USD"}, "MSFT", "3m", "daily")
    assert out["status"] == "ok" and out["currency"] == "USD" and out["as_of"] == df.index[-1].strftime("%Y-%m-%d")
    assert out["window"]["bars"] == 60 and out["window"]["change_pct"] == round((159 / 100 - 1) * 100, 2)
    assert len(out["recent_bars"]) == milo_data.BARS_SHOWN and "last 40 bars of 60" in out["bars_note"]
    tb = box(get_price_history=lambda ticker, period, interval: out)
    content, is_error, _ = run(tb.run("get_price_history", {"ticker": "MSFT", "period": "3m"}))
    meta = json.loads(content)["meta"]
    assert not is_error and meta["source"].startswith("Yahoo Finance daily bars") and meta["as_of"] == out["as_of"]
    assert meta["units"]["prices"].startswith("the quote currency") and meta["delayed"] is True
    assert meta["unavailable"] is False and meta["partial"] is False and isinstance(meta["stale"], bool)


def test_a_frame_wider_than_the_window_is_cut_to_it_and_one_inside_it_is_used_as_it_came():
    # a year of bars for a "3m" question (the eval's fixture did this until Phase 08): the window's figures cover
    # the three months, and the result says what was left out
    year = frame([100.0 + i for i in range(260)], start="2025-10-27")
    out = milo_data.price_history(lambda t, period, interval: year, lambda t: {}, "MSFT", "3m", "daily")
    first = year.index[-1] - pd.Timedelta(days=milo_data.SPAN_DAYS["3m"])
    kept = year[year.index >= first]
    assert out["window"]["bars"] == len(kept) < 70
    assert out["window"]["change_pct"] == round((kept["Close"].iloc[-1] / kept["Close"].iloc[0] - 1) * 100, 2)
    assert "{} earlier bars the feed sent were outside the window".format(260 - len(kept)) in out["bars_note"]
    # Yahoo counts "3mo" from today, so its first bar can sit a few days before the last bar's three months
    edge = frame([100.0 + i for i in range(66)], start="2026-07-20")
    same = milo_data.price_history(lambda t, period, interval: edge, lambda t: {}, "MSFT", "3m", "daily")
    assert same["window"]["bars"] == 66 and "outside the window" not in same["bars_note"]
    ytd = frame([100.0 + i for i in range(300)], start="2025-09-01")
    got = milo_data.price_history(lambda t, period, interval: ytd, lambda t: {}, "MSFT", "ytd", "daily")
    assert got["window"]["bars"] == int((ytd.index >= "2026-01-01").sum())


def test_company_lookup_ranks_like_the_search_box_and_says_when_it_is_unsure():
    found = {"available": True, "stale": False, "results": [
        {"symbol": "BRK-B", "name": "Berkshire Hathaway Inc.", "kind": "stock", "etf": False, "match": "alias"}]}
    out = milo_data.lookup_company(lambda q, limit: found, "berkshire")
    assert out["status"] == "ok" and out["matches"][0]["symbol"] == "BRK-B" and "Nasdaq Trader" in out["source"]
    none = milo_data.lookup_company(lambda q, limit: {"available": True, "results": []}, "zzqx")
    assert none["status"] == "not_found" and none["matches"] == []
    old = milo_data.lookup_company(lambda q, limit: dict(found, stale=True), "berkshire")
    assert old["stale"] is True
    down = milo_data.lookup_company(lambda q, limit: {"available": False, "results": [], "reason": "x"}, "apple")
    assert down["status"] == "unavailable" and "matches" not in down


def test_filings_and_financials_pass_through_edgar_with_dates_and_links():
    rows = [{"form": "10-Q", "filed": "2026-10-01", "what": "Quarterly report", "url": "https://www.sec.gov/x"},
            {"form": "8-K", "filed": "2026-09-01", "what": "Current report", "items": "2.02", "url": "https://www.sec.gov/y"}]
    out = milo_data.filings(lambda t, limit: {"available": True, "cik": "1", "company": "Co", "filings": rows}, "CO", 10)
    assert out["status"] == "ok" and out["as_of"] == "2026-10-01" and out["filings"][1]["items"] == "2.02"
    trust = milo_data.filings(lambda t, limit: {"available": False, "filings": rows, "reason": "old"}, "TR", 10)
    assert trust["status"] == "ok" and trust["stale"] is True
    gone = milo_data.filings(lambda t, limit: {"available": False, "reason": "not in EDGAR"}, "ZZ", 10)
    assert gone["status"] == "unavailable" and gone["filings"] == []
    facts = {"available": True, "cik": "1", "revenue_quarters": [{"period_end": "2026-06-30", "value": 5.0}] * 20,
             "eps_quarters": [{"period_end": "2026-06-30", "value": 1.0}], "revenue_ttm": [], "revenue_yoy": [],
             "eps_ttm": [], "counts": {}, "notes": [], "stale": True}
    fin = milo_data.financials(lambda t: facts, "CO")
    assert fin["status"] == "ok" and len(fin["revenue_quarters"]) == 12 and fin["as_of"] == "2026-06-30"
    assert fin["stale"] is True and "XBRL" in fin["source"]
    assert milo_data.financials(lambda t: {"available": False, "reason": "no"}, "ZZ")["status"] == "unavailable"


# ------------------------------------------------------------------------------------------ failures

def test_a_provider_failure_is_a_failure_with_no_figures():
    def boom(**kw):
        raise ConnectionError("upstream said 503 with key=abc123")
    tb = box(get_financials=boom)
    content, is_error, _ = run(tb.run("get_financials", {"ticker": "AAPL"}))
    body = json.loads(content)
    assert is_error and body["status"] == "unavailable" and body["meta"]["unavailable"] is True
    assert "do not guess" in body["error"] and "abc123" not in content, "no exception text reaches the model"
    empty = milo_data.price_history(lambda t, period, interval: pd.DataFrame(), lambda t: {}, "ZZZZ", "1y", "daily")
    tb = box(get_price_history=lambda ticker, period, interval: empty)
    content, is_error, _ = run(tb.run("get_price_history", {"ticker": "ZZZZ", "period": "1y"}))
    meta = json.loads(content)["meta"]
    assert is_error and meta["unavailable"] is True and meta["delayed"] is None and "window" not in content


def test_a_slow_source_times_out_and_says_so():
    import time as _t
    tb = milo_tools.Toolbox(runners={"get_filings": lambda ticker, limit: _t.sleep(2) or {}}, call_timeout=0.2)
    content, is_error, _ = run(tb.run("get_filings", {"ticker": "AAPL"}))
    assert is_error and json.loads(content)["meta"]["unavailable"] is True


# ------------------------------------------------------------------------------------------ freshness

REGULAR = {"is_regular": True, "last_close": {"at": "2026-10-23T16:00:00-04:00"}}
CLOSED = {"is_regular": False, "last_close": {"at": "2026-10-23T16:00:00-04:00"}}


def test_a_quote_behind_the_session_is_stale_and_its_time_is_the_trades():
    q = {"ticker": "AMD", "price": 1.0, "trade_time": "2026-10-26T14:00:00+00:00",
         "as_of": "2026-10-26T15:30:00+00:00", "delayed_minutes": 15, "currency": "USD"}
    out = milo_tools.compact_quote(q)
    assert out["as_of_utc"] == q["trade_time"] and out["as_of_is"] == "the trade's time" and out["delayed_minutes"] == 15
    now = datetime(2026, 10, 26, 15, 30, tzinfo=timezone.utc)                  # 11:30 ET, session open
    meta = milo_tools.describe("get_quote", dict(out, status="ok"), False, now=now, session_state=REGULAR)
    assert meta["stale"] is True and meta["delayed"] is True and "15 minutes" in meta["delay"]
    fresh = dict(out, as_of_utc="2026-10-26T15:10:00+00:00", status="ok")
    assert milo_tools.describe("get_quote", fresh, False, now=now, session_state=REGULAR)["stale"] is False
    weekend = datetime(2026, 10, 25, 15, 0, tzinfo=timezone.utc)
    friday = dict(out, as_of_utc="2026-10-23T20:00:00+00:00", status="ok")
    assert milo_tools.describe("get_quote", friday, False, now=weekend, session_state=CLOSED)["stale"] is False
    thursday = dict(out, as_of_utc="2026-10-22T20:00:00+00:00", status="ok")
    assert milo_tools.describe("get_quote", thursday, False, now=weekend, session_state=CLOSED)["stale"] is True
    rt = milo_tools.compact_quote(dict(q, quote_source="tradier (real-time)"))
    assert rt["as_of_utc"] == q["as_of"], "Tradier's price keeps Yahoo's trade_time: use its own fetch time"
    assert milo_tools.describe("get_quote", dict(rt, status="ok"), False, now=now,
                               session_state=REGULAR)["delayed"] is False


def test_bars_that_end_before_the_last_close_are_stale():
    now = datetime(2026, 10, 25, 15, 0, tzinfo=timezone.utc)
    ok = {"status": "ok", "as_of": "2026-10-23", "interval": "daily", "source": "Yahoo Finance daily bars"}
    assert milo_tools.describe("get_price_history", ok, False, now=now, session_state=CLOSED)["stale"] is False
    behind = dict(ok, as_of="2026-10-21")
    assert milo_tools.describe("get_price_history", behind, False, now=now, session_state=CLOSED)["stale"] is True


def test_flags_that_do_not_apply_say_none_and_a_trimmed_result_is_partial():
    meta = milo_tools.describe("get_filings", {"status": "ok", "source": "SEC EDGAR"}, False, session_state=CLOSED)
    assert meta["delayed"] is None and meta["stale"] is False and meta["partial"] is False, "a fresh copy is not stale"
    assert milo_tools.describe("get_news", {"status": "ok"}, False, session_state=CLOSED)["stale"] is None
    cut = milo_tools.describe("get_my_portfolio", {"status": "ok", "left_out_to_fit": ["data.series"]}, False,
                              session_state=CLOSED)
    assert cut["partial"] is True and "data.series" in cut["notes"][0]


def test_every_tool_result_carries_the_envelope():
    tb = box(get_quote=lambda ticker: {"status": "ok", "source": "Yahoo Finance quote (delayed)"},
             get_news=lambda ticker: {"status": "ok", "items": []})
    for name in ("get_quote", "get_news"):
        meta = json.loads(run(tb.run(name, {"ticker": "AMD"}))[0])["meta"]
        assert set(meta) >= {"source", "as_of", "retrieved_at", "units", "delayed", "stale", "partial", "unavailable"}
    assert set(milo_tools.UNITS) == set(milo_tools.TOOL_NAMES)


# ------------------------------------------------------------------------------------------ the reader's data

def test_the_portfolio_tool_returns_only_the_asking_readers_accounts(monkeypatch):
    import app.main as m
    users = {"a": {"id": "user-a"}, "b": {"id": "user-b"}}
    holdings = {"user-a": ["AAA"], "user-b": ["BBB"]}
    monkeypatch.setattr(m.brokerage_service, "open_to", lambda user: True)
    monkeypatch.setattr(m.brokerage_store, "link", lambda uid: {"id": "l-" + uid})
    monkeypatch.setattr(m.brokerage_store, "accounts", lambda uid: [{"id": "acct-" + uid}])
    monkeypatch.setattr(m.brokerage_service, "milo_context",
                        lambda user, account_ids=None, **kw: {"facts": {"holdings": holdings[user["id"]]}})
    for who, mine, theirs in (("a", "AAA", "BBB"), ("b", "BBB", "AAA")):
        monkeypatch.setattr(m.auth_deps, "current_user", lambda request, who=who: users[who])
        tb = m._milo_toolbox(types.SimpleNamespace(), {"focus": {"scope": "auto", "view": "brokerage"}})
        content, is_error, _ = run(tb.run("get_my_portfolio", {"part": "summary"}))
        assert not is_error and mine in content and theirs not in content
        with pytest.raises(milo_tools.InvalidInput):
            milo_tools.validate("get_my_portfolio", {"part": "summary", "user_id": "user-" + ("b" if who == "a" else "a")})
    monkeypatch.setattr(m.auth_deps, "current_user", lambda request: None)
    body = json.loads(run(m._milo_toolbox(types.SimpleNamespace(), {"focus": {"scope": "auto", "view": "brokerage"}})
                          .run("get_my_portfolio", {"part": "summary"}))[0])
    assert body["signed_in"] is False and "AAA" not in json.dumps(body) and "BBB" not in json.dumps(body)


def test_a_browser_cannot_send_a_portfolio_or_widen_the_scope(monkeypatch):
    """The linked portfolio and the guide are server-owned keys; a browser copy never reaches Milo."""
    import app.main as m
    forged = {"brokerage_portfolio": {"facts": {"holdings": ["FORGED"]}}, "brokerage_linked": True,
              "focus": {"scope": "auto"}}
    assert "brokerage_portfolio" not in m._without_linked_keys(forged)
    tb = m._milo_toolbox(types.SimpleNamespace(), {"focus": {"scope": "market"}})
    assert "get_my_portfolio" not in tb.runners, "scoped to the market: no holdings tool"


def test_the_new_tools_read_no_reader_data_and_hold_no_credentials():
    import inspect
    src = inspect.getsource(milo_data)
    for word in ("current_user", "auth_deps", "brokerage_store", "account_mod", "os.environ", "TOKEN", "API_KEY"):
        assert word not in src, word


# ------------------------------------------------------------------------------------------ instructions and wiring

def test_milo_is_told_to_fetch_current_facts_and_to_read_the_flags():
    sp = " ".join(ai.SYSTEM_PROMPT.split())
    for phrase in ("**Current facts first.**", "Never answer it from memory",
                   "A company named without a ticker goes through lookup_company first",
                   "goes through get_price_history, whose window figures you quote rather than recompute",
                   "Every tool result has `meta`", "When `delayed` is true say the price is delayed",
                   "when `unavailable` is true say the figure could not be retrieved this time"):
        assert phrase in sp, phrase
    for name in ("lookup_company", "get_price_history", "get_filings", "get_financials"):
        assert name in sp


def test_the_chat_route_offers_the_new_tools(monkeypatch):
    import app.main as m
    monkeypatch.setattr(m.auth_deps, "current_user", lambda request: None)
    tb = m._milo_toolbox(types.SimpleNamespace(), {"focus": {"scope": "auto"}})
    assert {"lookup_company", "get_price_history", "get_filings", "get_financials"} <= set(tb.runners)
    # every tool, the portfolio aside: it is offered from the Brokerage page or for the reader's own holdings
    assert set(tb.runners) == set(milo_tools.TOOL_NAMES) - {"get_my_portfolio"}
    tb = m._milo_toolbox(types.SimpleNamespace(), {"focus": {"scope": "auto", "view": "brokerage"}})
    assert set(tb.runners) == set(milo_tools.TOOL_NAMES)
