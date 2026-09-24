"""Staying under the rate limit instead of discovering it.

Everything here used to be reactive. `note_throttle` records a 429 after Yahoo
has already refused us; nothing slowed the requests going out, and nothing
waited when the feed had said stop. Two measured consequences on the scheduled
scan:

  the rate         A snapshot was 16 fetches and a thirty-name scan 480,
                   issued back-to-back through _NET_LOCK at about 4.5 a
                   second. That is the rate that earns the limit.

  the compounding  With no gate, a request fired during a backoff returns
                   another 429, and every note_throttle pushes `until` out a
                   further 60s. The scan's own cool-off is capped at 90s, so
                   once this started the feed could not come back inside one
                   scan -- the backoff grew faster than the wait.

Three fixes, and the first is the largest: the scan was fetching a block it
never read. `consider_ticker` opens verdict, technicals, quote, entry_plan and
ticker. `fundamentals.analyse` is five fetches and 1.8s a ticker -- short
interest, statements, earnings history, insider and institutional holdings --
which over thirty names is 150 requests and ~54 seconds spent on a panel the
ledger does not look at. Measured after: 10 fetches a name, 300 a scan.

Then a token bucket rather than a flat interval, because one Dossier page and a
thirty-name scan are not the same problem. Measured: 16 fetches in 2.0s for a
page, 300 held at 2.1/s for a scan.
"""

from __future__ import annotations

import inspect
import time

import pytest

from app.providers import yf as Y


@pytest.fixture(autouse=True)
def _reset():
    """Each test gets a full bucket and no backoff."""
    Y._BUCKET.update(tokens=Y.YF_BURST, rate=Y.YF_RATE, last=time.time())
    Y._THROTTLE["until"] = 0.0
    Y._CACHE.clear()
    yield
    Y._BUCKET.update(tokens=Y.YF_BURST, rate=Y.YF_RATE, last=time.time())
    Y._THROTTLE["until"] = 0.0


def _fetch(tag, producer=lambda: 1):
    return Y._cached("test:%s:%f" % (tag, time.time()), 0.0, producer)


class _RateLimit(Exception):
    pass


def test_a_burst_the_size_of_a_page_is_not_paced():
    """A Dossier page is 16 fetches and wants to feel instant. Charging it the
    sustained rate took it from 4.3s to 7.0s, which is the wrong trade to make
    while fixing a scan."""
    t0 = time.time()
    for i in range(int(Y.YF_BURST)):
        _fetch(i)
    assert time.time() - t0 < 1.0, "the burst allowance is not being spent"


def test_sustained_load_is_held_at_the_rate():
    """Past the bucket, callers wait. This is the number Yahoo cares about."""
    for i in range(int(Y.YF_BURST)):
        _fetch("drain%d" % i)
    n = 6
    t0 = time.time()
    for i in range(n):
        _fetch("sustained%d" % i)
    elapsed = time.time() - t0
    assert elapsed >= (n - 1) / Y.YF_RATE * 0.8, \
        "{} fetches in {:.2f}s is faster than {}/s".format(n, elapsed, Y.YF_RATE)


def test_a_rate_limit_halves_the_rate_and_surrenders_the_burst():
    """Whatever allowance is left is exactly what would be spent firing into a
    window that has just closed."""
    before = Y._BUCKET["rate"]
    with pytest.raises(_RateLimit):
        Y._cached("test:boom", 0.0,
                  lambda: (_ for _ in ()).throw(_RateLimit("429 Too Many Requests")))
    assert Y._BUCKET["rate"] == pytest.approx(before / 2.0)
    assert Y._BUCKET["tokens"] == 0.0


def test_the_rate_recovers_slowly_rather_than_resetting():
    """One success after a rate limit is not evidence the limit has lifted.
    Resetting on it is how a limiter oscillates between hammering and being
    refused."""
    Y._BUCKET["rate"] = Y.YF_RATE / 4.0
    Y._BUCKET["tokens"] = 50.0
    Y._cached("test:one", 0.0, lambda: 1)
    assert Y._BUCKET["rate"] < Y.YF_RATE, "a single call must not restore the rate"
    for i in range(80):
        Y._BUCKET["tokens"] = 50.0
        Y._cached("test:rec%d" % i, 0.0, lambda: 1)
    assert Y._BUCKET["rate"] == pytest.approx(Y.YF_RATE), "it has to get back eventually"


def test_a_call_during_a_backoff_waits_instead_of_firing_into_it():
    """The compounding bug. Without this the call returns another 429 and
    pushes `until` out a further 60s, so the backoff outruns any bounded wait
    the caller could make."""
    Y._THROTTLE["until"] = time.time() + 1.5
    t0 = time.time()
    _fetch("gated")
    assert time.time() - t0 >= 1.2, "the gate let a call through a live backoff"


def test_the_gate_gives_up_rather_than_hanging_a_page_forever():
    """A bounded wait, or one throttle stalls an interactive request for the
    whole backoff."""
    assert Y.MAX_GATE_WAIT < Y.THROTTLE_BACKOFF_SECONDS


def test_every_network_fetch_goes_through_the_gate():
    """One gate is only enough because `_cached` is the single path to the
    network in this module. A method that reached yfinance directly would
    bypass the limiter silently, and nothing about it would look wrong."""
    src = inspect.getsource(Y._cached)
    assert "_wait_turn()" in src
    # And the limiter reacts to what the call did.
    assert "_on_throttle()" in src and "_on_success()" in src


def test_the_scan_does_not_fetch_the_block_it_never_reads():
    """`consider_ticker` opens five fields and fundamentals is in none of
    them. This is the same argument the earnings-momentum skip already makes,
    applied to the larger block -- five fetches a ticker against three."""
    from app import main as M
    sig = inspect.signature(M._swing_snapshot)
    assert "include_company" in sig.parameters
    assert sig.parameters["include_company"].default is True, \
        "the Dossier path must keep its fundamentals"
    scan = inspect.getsource(M._tracker_snapshot)
    assert "include_company=False" in scan
    body = inspect.getsource(M._swing_snapshot)
    assert "if include_company:" in body


def test_the_limiter_reports_itself():
    state = Y.pace_state()
    for key in ("rate", "burst", "tokens", "base_rate"):
        assert key in state
