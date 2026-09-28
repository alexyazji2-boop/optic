"""The ticker build says where its time went, in a Server-Timing header.

Asked for after the live site's first loads measured 4.2s to 8.8s against
about 2.2s locally for the same build, with nothing on the server to say why.
The header is readable from outside: the browser's network panel draws it, and
`curl -D -` prints it. On a server still warming up, the first reading found
a cold PANW spending up to 8.2s of its 9.6s held at the rate limiter.

Each leg's row separates the three things a slow leg can be doing: held at the
gate, inside its fetches, or neither (waiting on a fetch another leg started,
or computing).
"""
from __future__ import annotations

import re
import threading
import time

import pytest
from fastapi.testclient import TestClient

import app.main as main
from app.providers import yf as Y

METRIC = re.compile(r'^([!#$%&\'*+.^_`|~0-9A-Za-z-]+);dur=([0-9]+(?:\.[0-9]+)?)(?:;desc="([^"\\]*)")?$')


@pytest.fixture(autouse=True)
def clean(monkeypatch):
    monkeypatch.setattr(Y, "_CACHE", {})
    monkeypatch.setattr(Y, "_BUCKET", {"tokens": 100.0, "rate": 100.0, "last": time.time()})
    monkeypatch.setattr(Y, "_THROTTLE", {"until": 0.0, "hits": 0, "last_seen": None})


def _rows(header):
    out = {}
    for part in header.split(", "):
        m = METRIC.match(part)
        assert m, "not Server-Timing syntax: %r" % part
        out[m.group(1)] = (float(m.group(2)), m.group(3))
    return out


def _desc(desc):
    at, gate, lock, fetch, req = re.match(
        r"at (\d+) ms / gate (\d+) ms / lock (\d+) ms / fetch (\d+) ms / (\d+) req$",
        desc).groups()
    return int(at), int(gate), int(fetch), int(req)


def _lock(desc):
    return int(re.search(r"lock (\d+) ms", desc).group(1))


def test_the_ticker_route_sends_the_header(monkeypatch):
    def build(ticker, expiries, max_expiries, include_macro, *, include_earnings=True,
              include_company=True, budget=None, parallel=False, timings=None):
        timings.begin()
        legs = main._Legs(parallel, timings)
        legs.start("quote", lambda: Y._cached("t:q", 60, lambda: time.sleep(0.05) or 1))
        legs.start("chain", lambda: time.sleep(0.1))
        legs.get("quote"), legs.get("chain")
        spin = time.perf_counter() + 0.05                 # the build's own work
        while time.perf_counter() < spin:
            pass
        return {"ticker": ticker}

    monkeypatch.setattr(main, "_swing_snapshot", build)
    res = TestClient(main.app).get("/api/ticker/ABC")
    assert res.status_code == 200
    rows = _rows(res.headers["server-timing"])
    assert {"queue", "build", "compute", "cpu", "quote", "chain"} <= set(rows), sorted(rows)
    assert rows["cpu"][0] >= 40, "the 0.05s of busy work was not counted: %r" % (rows["cpu"],)
    assert rows["build"][0] >= 150, "the build took at least its two legs and its work"
    assert 40 <= rows["compute"][0] < rows["build"][0] - 80, \
        "compute is the build less its waits: %r" % (rows["compute"],)
    at, gate, fetch, req = _desc(rows["quote"][1])
    assert req == 1 and fetch >= 45, rows["quote"]
    assert _desc(rows["chain"][1])[3] == 0, "no request, so no request counted"


def test_the_quick_quote_sends_it_too(monkeypatch):
    monkeypatch.setattr(main.PROVIDER, "quote", lambda sym: Y._cached(
        "t:qq", 60, lambda: {"ticker": sym, "price": 1.0}))
    res = TestClient(main.app).get("/api/quote/ABC")
    rows = _rows(res.headers["server-timing"])
    assert {"queue", "build", "compute", "quote"} <= set(rows)
    assert _desc(rows["quote"][1])[3] == 1


def test_a_leg_held_at_the_gate_says_so():
    # Two booked turns ahead at 10/s: this fetch waits about 0.3s for its own.
    Y._BUCKET.update(tokens=-2.0, rate=10.0, last=time.time())
    timings = main._Timings()
    timings.wrap("chain", lambda: Y._cached("t:gate", 60, lambda: 1))()
    at, gate, fetch, req = _desc(_rows(timings.header())["chain"][1])
    assert 250 <= gate < 1000 and req == 1, (gate, req)


def test_the_meter_is_per_thread():
    Y._BUCKET.update(tokens=-2.0, rate=10.0, last=time.time())
    got = {}

    def held():
        Y.meter_reset()
        Y._cached("t:held", 60, lambda: 1)
        got["held"] = Y.meter_read()

    def free():
        Y.meter_reset()
        time.sleep(0.05)
        got["free"] = Y.meter_read()

    threads = [threading.Thread(target=held), threading.Thread(target=free)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(5)
    assert got["held"][0] >= 0.25 and got["held"][3] == 1
    assert got["free"] == (0.0, 0.0, 0.0, 0), "another thread's wait was counted here"


def test_a_fetch_inside_a_fetch_is_counted_once():
    def outer():
        time.sleep(0.05)
        return Y._cached("t:inner", 60, lambda: time.sleep(0.1) or 1)

    Y.meter_reset()
    Y._cached("t:outer", 60, outer)
    gated, locked, fetching, requests = Y.meter_read()
    assert requests == 2
    assert 0.14 <= fetching < 0.25, "the inner 0.1s was counted twice: %.3f" % fetching


def test_a_failed_fetch_still_counts_its_time():
    Y.meter_reset()
    with pytest.raises(ValueError):
        Y._cached("t:bad", 60, lambda: time.sleep(0.05) or (_ for _ in ()).throw(ValueError()))
    assert Y.meter_read()[2] >= 0.045
    Y.meter_reset()
    Y._cached("t:after", 60, lambda: time.sleep(0.02) or 1)
    assert Y.meter_read()[2] >= 0.015, \
        "the failure left the depth raised, so the next fetch went uncounted"


def test_each_leg_reads_only_its_own_requests():
    # Sequential legs share the caller's thread, which is where a meter that
    # was never reset would carry one leg's requests into the next.
    timings = main._Timings()
    legs = main._Legs(False, timings)
    legs.start("first", lambda: Y._cached("t:first", 60, lambda: 1))
    legs.start("second", lambda: None)
    legs.get("first"), legs.get("second")
    rows = _rows(timings.header())
    assert _desc(rows["first"][1])[3] == 1 and _desc(rows["second"][1])[3] == 0, rows


def test_a_scan_pays_nothing_for_it(monkeypatch):
    # No timings passed, nothing wrapped: the scans build this sequentially
    # thirty names at a time and have no header to fill.
    legs = main._Legs(False)
    marker = object()
    fn = lambda: marker                                   # noqa: E731
    legs.start("x", fn)
    assert legs._legs["x"][0] is fn
    assert legs.get("x") is marker


def test_a_leg_waiting_on_another_legs_fetch_says_so():
    # The sector check waits on the history leg's fetch of the same series;
    # before this row existed, that read as a slow request it never made.
    release = threading.Event()
    t = threading.Thread(target=lambda: Y._cached("t:shared", 60,
                                                  lambda: release.wait(2) and 1))
    t.start()
    time.sleep(0.05)
    timings = main._Timings()
    threading.Timer(0.2, release.set).start()
    timings.wrap("sector", lambda: Y._cached("t:shared", 60, lambda: 2))()
    t.join(5)
    desc = _rows(timings.header())["sector"][1]
    assert _lock(desc) >= 150 and _desc(desc)[3] == 0, desc
