"""A symbol's first load runs its independent fetches side by side.

Reported as "I need to change the ticker with two inputs, not one". The first
Load did work, but first loads measured 9.4s, 10.3s and 58.1s on the live
site, and a reader who watched "Loading HOOD..." that long pressed Load again,
which then came back quickly because the first press had filled the caches.
The build ran its fetches one after another, though none of them waits on
another's answer except fundamentals on the quote. Measured locally on cold
symbols, parallel took TTD from 13.4s to 7.3s and ZM from 9.2s to 7.4s; a lock
inside yfinance (the shared crumb) holds some of the rest in a queue.

The scans keep the old order. A scan builds this for thirty names, and eight
requests at once per name is the traffic that earns a rate limit.
"""
from __future__ import annotations

import inspect
import threading
import time

import pytest
from fastapi import HTTPException

import app.main as main


# ------------------------------------------------------------------ the legs


def test_sequential_legs_run_where_they_are_read_and_in_that_order():
    calls = []
    legs = main._Legs(False)
    legs.start("a", lambda: calls.append("a") or 1)
    legs.start("b", lambda: calls.append("b") or 2)
    assert calls == [], "nothing may run before it is read"
    assert legs.get("b") == 2 and legs.get("a") == 1
    assert calls == ["b", "a"]


def test_a_legs_error_surfaces_where_it_is_read_either_way():
    for parallel in (False, True):
        legs = main._Legs(parallel)

        def boom():
            raise RuntimeError("feed down")

        legs.start("x", boom)
        with pytest.raises(RuntimeError, match="feed down"):
            legs.get("x")


def test_parallel_legs_overlap():
    legs = main._Legs(True)
    t0 = time.time()
    for name in "abcdef":
        legs.start(name, time.sleep, 0.2)
    for name in "abcdef":
        legs.get(name)
    assert time.time() - t0 < 0.6, "six 0.2s legs took %.2fs" % (time.time() - t0)


# ------------------------------------------------------------ the build


@pytest.fixture
def fetches(monkeypatch):
    """Every network leg of the build, recorded, with an empty history so the
    build stops at its 404 straight after reading the quote and the history."""
    seen = []
    lock = threading.Lock()

    def rec(name, value=None):
        def fn(*a, **k):
            with lock:
                seen.append(name)
            return value
        return fn

    P, Y = main.PROVIDER, main.YF_PROVIDER
    monkeypatch.setattr(P, "quote", rec("quote", {"price": 10.0}))
    import pandas as pd
    monkeypatch.setattr(P, "history", rec("history", pd.DataFrame()))
    monkeypatch.setattr(P, "expirations", rec("expirations", []))
    monkeypatch.setattr(P, "options_chain", rec("chain", None))
    monkeypatch.setattr(main.news_mod, "analyse", rec("news", {}))
    monkeypatch.setattr(main.macro_mod, "analyse", rec("macro", {}))
    monkeypatch.setattr(main.earnings_mod, "momentum", rec("earnings", {}))
    monkeypatch.setattr(main.filings_mod, "recent", rec("filings", []))
    monkeypatch.setattr(main, "_sector_confirm", rec("sector", {}))
    monkeypatch.setattr(Y, "earnings_date", rec("earnings_date", None))
    monkeypatch.setattr(main.fundamentals_mod, "analyse", rec("fundamentals", {}))
    # The company and earnings blocks' own fetches, which a parallel build
    # starts up front (see test_company_prefetch.py).
    for name in ("short_interest", "insiders", "institutions", "financials",
                 "earnings_history", "estimates"):
        monkeypatch.setattr(Y, name, rec(name, {}))
    monkeypatch.setattr(main, "_macro_calendar_rows", rec("calendar", []))
    return seen


def test_parallel_starts_every_independent_fetch_before_reading_any(fetches):
    with pytest.raises(HTTPException):
        main._swing_snapshot("ZZZZ", None, 4, True, include_earnings=True, parallel=True)
    deadline = time.time() + 5
    want = {"quote", "history", "news", "expirations", "chain", "macro", "earnings",
            "filings", "sector", "earnings_date", "fundamentals",
            "short_interest", "insiders", "institutions", "financials",
            "earnings_history", "estimates", "calendar"}
    while time.time() < deadline and not want <= set(fetches):
        time.sleep(0.02)
    assert want <= set(fetches), sorted(want - set(fetches))


def test_sequential_fetches_nothing_the_build_did_not_reach(fetches):
    """The old behaviour exactly: the 404 comes after the quote and the history,
    so nothing else was ever asked for."""
    with pytest.raises(HTTPException):
        main._swing_snapshot("ZZZZ", None, 4, True, include_earnings=True)
    assert sorted(fetches) == ["history", "quote"]


# ------------------------------------------------------------ who asks


def test_only_the_interactive_route_asks_for_parallel():
    src = inspect.getsource(main)
    route = src[src.index("_run(_swing_snapshot, ticker, wanted"):][:220]
    assert "parallel=True" in route
    others = [m.start() for m in __import__("re").finditer(r"_swing_snapshot\(", src)]
    calls = [src[i:i + 160] for i in others if not src[i - 4:i].startswith("def ")]
    assert calls and all("parallel=True" not in c for c in calls), "a scan went parallel"
    sig = inspect.signature(main._swing_snapshot)
    assert sig.parameters["parallel"].default is False
    assert sig.parameters["parallel"].kind is inspect.Parameter.KEYWORD_ONLY
