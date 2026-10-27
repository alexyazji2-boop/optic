"""A refused options read is a failed read, not a symbol without options.

Seen on a local copy of production during the investor audit (2026-10-27):
NVDA's Options tab said "The contracts did not load. No options chain for
'NVDA'." Yahoo was answering some requests with 401 "Invalid Crumb", and
yfinance turns that refusal into an empty expiry list or a chain with
calls=None, without raising. Optic cached those as facts: thirty minutes of
"No listed options" for the expiries, a minute of "No options chain" for the
chain, and a Try again inside that minute was answered from the cache.
"""
from __future__ import annotations

import time
import types

import pandas as pd
import pytest
from fastapi.testclient import TestClient

import app.main as m
from app.providers import yf as Y


@pytest.fixture(autouse=True)
def clean(monkeypatch):
    monkeypatch.setattr(Y, "_CACHE", {})
    monkeypatch.setattr(Y, "_BUCKET", {"tokens": 100.0, "rate": 100.0, "last": time.time()})
    monkeypatch.setattr(Y, "_THROTTLE", {"until": 0.0, "hits": 0, "last_seen": None})


def _fake_ticker(monkeypatch, listed, underlying, chain=None):
    """A yf.Ticker whose expiry read returns `listed`, with `underlying` set as
    yfinance sets it (only when Yahoo answered), counting the reads."""
    reads = {"expiries": 0, "chains": 0}

    class Ticker:
        def __init__(self, symbol):
            self._underlying = {}
            self._expirations = {}

        @property
        def options(self):
            # as yfinance does: a download only while no expiry is known
            if not self._expirations:
                reads["expiries"] += 1
                self._underlying = dict(underlying)
                self._expirations = {e: e for e in listed}
            return tuple(self._expirations)

        def option_chain(self, exp):
            reads["chains"] += 1
            if chain is None:
                return types.SimpleNamespace(calls=None, puts=None, underlying=None)
            return chain

    monkeypatch.setattr(Y.yf, "Ticker", Ticker)
    return reads


def test_a_refused_expiry_read_is_marked_and_not_kept(monkeypatch):
    reads = _fake_ticker(monkeypatch, [], {})
    p = Y.YFinanceProvider()
    got = p.expirations("NVDA")
    assert not got and getattr(got, "unread", False), "empty, and said to be a failed read"
    first = reads["expiries"]
    p.expirations("NVDA")
    assert reads["expiries"] > first, "the next read asks again instead of answering from a cached refusal"


def test_a_symbol_yahoo_answered_with_no_options_is_kept_as_none(monkeypatch):
    reads = _fake_ticker(monkeypatch, [], {"symbol": "^TNX", "quoteType": "INDEX"})
    p = Y.YFinanceProvider()
    got = p.expirations("^TNX")
    assert got == [] and not getattr(got, "unread", False)
    first = reads["expiries"]
    p.expirations("^TNX")
    assert reads["expiries"] == first, "a real answer is cached as before"


def test_listed_expiries_with_no_contracts_is_a_failed_chain_and_not_kept(monkeypatch):
    reads = _fake_ticker(monkeypatch, ["2026-11-20"], {"symbol": "NVDA"})
    p = Y.YFinanceProvider()
    chain = p.options_chain("NVDA", ["2026-11-20"])
    assert chain.empty and chain.attrs.get("unread") is True
    p.options_chain("NVDA", ["2026-11-20"])
    assert reads["chains"] == 2, "Try again reaches the feed"


class _Provider:
    name = "fake"

    def __init__(self, listed):
        self.listed = listed

    def quote(self, t):
        return {"price": 100.0, "dividend_yield": 0.0}

    def expirations(self, t):
        return self.listed

    def options_chain(self, t, expiries=None, max_expiries=4):
        return Y._unread_frame()

    def earnings_date(self, t):
        return None


@pytest.mark.parametrize("path", ["/api/options/NVDA/research", "/api/options/NVDA/picker"])
def test_the_endpoints_say_the_feed_failed_not_that_there_are_no_options(monkeypatch, path):
    monkeypatch.setattr(m, "PROVIDER", _Provider(Y.Unread()))
    r = TestClient(m.app).get(path)
    assert r.status_code == 503, r.text
    assert "did not come back from the data source" in r.json()["detail"]
    assert "No listed options" not in r.json()["detail"]


def test_a_symbol_with_no_options_still_says_so(monkeypatch):
    monkeypatch.setattr(m, "PROVIDER", _Provider([]))
    r = TestClient(m.app).get("/api/options/TNX/research")
    assert r.status_code == 404 and r.json()["detail"] == "No listed options for 'TNX'."


def test_listed_expiries_and_a_refused_chain_is_a_503(monkeypatch):
    monkeypatch.setattr(m, "PROVIDER", _Provider(["2026-11-20", "2026-12-18"]))
    r = TestClient(m.app).get("/api/options/NVDA/research")
    assert r.status_code == 503, r.text
    assert "did not come back from the data source" in r.json()["detail"]
