"""Overnight single-stock prints, from the one keyless source that has them.

Reported on a Sunday night: COIN traded at $187.74 overnight while the terminal
showed Friday's $183.00 close. Six keyless sources were tried live during the
session and every one agreed with Yahoo -- Nasdaq, CNBC, Webull (with an
explicit `"overnight": 0`), Cboe, Stocktwits, and Robinhood on its default
bounds. Robinhood with `bounds=24_5` returned a moving overnight tape, naming
the venue that printed it. See app/providers/overnight.py for the survey.

These tests run without a network. The fixtures are the endpoint's real record
shape, captured during the session.
"""

from __future__ import annotations

import asyncio
import datetime as dt
from zoneinfo import ZoneInfo

import pytest

from app import main, session
from app.providers import overnight

ET = ZoneInfo("America/New_York")

# A record exactly as the endpoint returned it for COIN at Sun 21:30 ET, with
# the regular-session fields still describing Friday.
COIN_ROW = {
    "ask_price": "187.130000", "bid_price": "186.900000",
    "last_trade_price": "183.000000",
    "venue_last_trade_time": "2026-10-02T19:59:59.916598066Z",
    "last_extended_hours_trade_price": "186.990000",
    "last_non_reg_trade_price": "186.990000",
    "venue_last_non_reg_trade_time": "2026-10-05T01:30:14.864Z",
    "previous_close": "183.000000",
    "symbol": "COIN", "trading_halted": False,
    "last_non_reg_trade_price_source": "boats",
    "updated_at": "2026-10-05T01:30:16Z",
}

SUN_2130 = dt.datetime(2026, 10, 4, 21, 30, tzinfo=ET)


# ------------------------------------------------------------ the timestamps


def test_a_nanosecond_venue_time_parses():
    """The venue reports nine fractional digits and a trailing Z, and Python
    3.9's `fromisoformat` accepts neither. Measured: `.043708867Z`."""
    got = overnight.parse_time("2026-10-05T01:33:21.043708867Z")
    assert got == dt.datetime(2026, 10, 5, 1, 33, 21, 43708, tzinfo=dt.timezone.utc)


@pytest.mark.parametrize("raw", [None, "", "not a time", 12345, "2026-13-45T99:00:00Z"])
def test_an_unparseable_time_is_absent_not_current(raw):
    """A print whose time cannot be read is one whose session cannot be
    checked, and must not be shown as tonight's."""
    assert overnight.parse_time(raw) is None


# ------------------------------------------------------------ the record


def test_the_trade_time_is_used_not_the_quote_touch_time():
    """`updated_at` advances on every bid change, so a quiet name would read as
    trading now on a price set hours ago. The venue time is when it printed."""
    got = overnight.parse(COIN_ROW)
    assert got["time"].startswith("2026-10-05T01:30:14")
    assert got["price"] == 186.99
    assert got["venue"] == "Blue Ocean ATS"


def test_both_venues_seen_are_named_and_an_unknown_one_is_not_guessed():
    """Twenty names surveyed split 10/10 between Blue Ocean and Bruce. The first
    version knew one and called it "the overnight venue"."""
    bruce = dict(COIN_ROW, last_non_reg_trade_price_source="bruce")
    assert overnight.parse(bruce)["venue"] == "Bruce ATS"
    odd = dict(COIN_ROW, last_non_reg_trade_price_source="nightowl")
    assert overnight.parse(odd)["venue"] == "nightowl"


def test_a_halted_name_has_no_tradeable_print():
    assert overnight.parse(dict(COIN_ROW, trading_halted=True)) is None


def test_a_null_slot_in_a_batch_is_skipped():
    """An unknown symbol inside a batch comes back as `null` in a 200 --
    measured, `COIN,ZZZZ,NVDA` -> [COIN, None, NVDA]. It must not break the
    other names."""
    assert overnight.parse(None) is None
    assert overnight.parse("garbage") is None


# ------------------------------------------------------------ the window


@pytest.mark.parametrize("label,when,expected", [
    ("Sun evening", dt.datetime(2026, 10, 4, 21, 30, tzinfo=ET), "Sun 20:00"),
    ("past midnight", dt.datetime(2026, 10, 5, 0, 5, tzinfo=ET), "Sun 20:00"),
    ("last minute", dt.datetime(2026, 10, 5, 3, 59, tzinfo=ET), "Sun 20:00"),
    ("pre-market", dt.datetime(2026, 10, 5, 4, 1, tzinfo=ET), None),
    ("Friday night", dt.datetime(2026, 10, 2, 21, 30, tzinfo=ET), None),
    ("Monday noon", dt.datetime(2026, 10, 5, 12, 0, tzinfo=ET), None),
])
def test_the_overnight_window_crosses_midnight(label, when, expected):
    """The reason the client's calendar-date rule could not be reused: a trade
    at 23:59 Sunday and a reading at 00:05 Monday are one session on two
    dates. Friday night is not an overnight session at all."""
    got = session.overnight_started_at(when)
    assert (got.strftime("%a %H:%M") if got else None) == expected, label


# ------------------------------------------------------------ attaching


def test_tonights_print_is_attached_against_the_regular_close():
    quote = {"price": 183.0}
    found = overnight.parse(COIN_ROW)
    assert overnight.attach(quote, session.overnight_started_at(SUN_2130), found)
    assert quote["overnight_price"] == 186.99
    # Against the 4pm close, as the after-hours line is ("vs the close").
    assert quote["overnight_change_pct"] == pytest.approx(2.1803, abs=1e-3)
    assert quote["overnight_venue"] == "Blue Ocean ATS"


def test_a_print_from_before_tonights_session_is_not_attached():
    """The venue keeps its last print through the day, so on a Monday afternoon
    the endpoint still reports Sunday night's trade. And on Sunday night the
    regular fields still describe Friday. Either way: older than the window
    start, so not tonight's, so not shown."""
    friday = dict(COIN_ROW, venue_last_non_reg_trade_time="2026-10-02T23:59:50Z")
    quote = {"price": 183.0}
    assert not overnight.attach(quote, session.overnight_started_at(SUN_2130),
                                overnight.parse(friday))
    assert "overnight_price" not in quote


def test_outside_the_session_nothing_is_attached():
    quote = {"price": 183.0}
    assert not overnight.attach(quote, None, overnight.parse(COIN_ROW))
    assert "overnight_price" not in quote


# ------------------------------------------------------------ never in the way


def test_a_failing_source_returns_nothing_and_does_not_raise(monkeypatch):
    """It is a supplement, never a dependency. Down overnight is weather."""
    overnight._cache.clear()

    def down(*_a, **_k):
        raise OSError("connection reset by peer")
    monkeypatch.setattr(overnight.feeds, "_fetch", down)
    assert overnight.quotes(["COIN", "NVDA"]) == {}


def test_symbols_are_validated_and_deduplicated(monkeypatch):
    overnight._cache.clear()
    asked = []

    def fake(url, *_a, **_k):
        asked.append(url)
        return b'{"results": []}'
    monkeypatch.setattr(overnight.feeds, "_fetch", fake)
    overnight.quotes(["coin", "COIN", "", "bad symbol!", "../etc"])
    assert len(asked) == 1
    assert "symbols=COIN&" in asked[0], asked[0]


# ------------------------------------------------------- the cached quote


def test_attaching_never_writes_into_the_providers_cached_quote(monkeypatch):
    """`_cached` returns the stored object, not a copy, and the swing payload's
    `quote` is that object. Attaching in place would freeze tonight's price
    into a cache other requests read. Found by reading the cache layer before
    shipping, not by a failure -- which is why it is pinned here."""
    cached = {"price": 183.0, "ticker": "COIN"}
    payload = {"ticker": "COIN", "quote": cached}
    monkeypatch.setattr(session, "overnight_started_at",
                        lambda now=None: SUN_2130.replace(hour=20, minute=0))
    monkeypatch.setattr(overnight, "quotes",
                        lambda syms: {"COIN": overnight.parse(COIN_ROW)})
    main._with_overnight(payload)
    assert payload["quote"] is not cached, "the cached object was reused"
    assert payload["quote"]["overnight_price"] == 186.99
    assert "overnight_price" not in cached, "tonight's price leaked into the cache"


def test_outside_the_session_no_request_is_made(monkeypatch):
    """The window check comes first and costs nothing in daytime."""
    monkeypatch.setattr(session, "overnight_started_at", lambda now=None: None)

    def must_not_run(_syms):
        raise AssertionError("fetched outside the overnight session")
    monkeypatch.setattr(overnight, "quotes", must_not_run)
    payload = {"ticker": "COIN", "quote": {"price": 183.0}}
    main._with_overnight(payload)
    assert "overnight_price" not in payload["quote"]


# ------------------------------------------------------------ the session bar


def test_the_session_bar_prefers_tonights_print_and_drops_the_stale_note():
    """The third surface that showed Friday's print as current. `price_view`
    draws the "AT THE CLOSE / AFTER HOURS" block, and had a stale note that sat
    inside a collapsed disclosure where nobody saw it."""
    quote = {"price": 183.0, "change_pct": -3.32,
             "post_market_price": 183.24, "post_market_change_pct": 0.13,
             "post_market_time": "2026-10-02T23:59:50+00:00"}
    overnight.attach(quote, session.overnight_started_at(SUN_2130),
                     overnight.parse(COIN_ROW))
    view = session.price_view(quote, now=SUN_2130)
    assert view["current"] == 186.99
    assert view["current_kind"] == "overnight"
    assert view["extended"]["venue"] == "Blue Ocean ATS"
    assert not view.get("stale_note"), "a live print needs no staleness warning"


def test_without_a_print_the_session_bar_still_says_it_is_stale():
    quote = {"price": 183.0, "post_market_price": 183.24,
             "post_market_change_pct": 0.13,
             "post_market_time": "2026-10-02T23:59:50+00:00"}
    view = session.price_view(quote, now=SUN_2130)
    assert view["current_kind"] == "after hours"
    assert "not a live overnight quote" in view["stale_note"]
    assert "No overnight venue has printed" in view["stale_note"], \
        "the note must not name one venue -- there are two"


def test_the_session_endpoint_carries_the_print(monkeypatch):
    """The cheap endpoint every tab polls once a minute, which is what keeps
    the overnight line moving without refetching the whole analysis."""
    monkeypatch.setattr(session, "overnight_started_at",
                        lambda now=None: SUN_2130.replace(hour=20, minute=0))
    monkeypatch.setattr(overnight, "quotes",
                        lambda syms: {"COIN": overnight.parse(COIN_ROW)})
    monkeypatch.setattr(main.PROVIDER, "quote",
                        lambda sym: {"price": 183.0, "ticker": "COIN"})
    monkeypatch.setattr(main.YF_PROVIDER, "profile", lambda sym: {})
    monkeypatch.setattr(session, "state", lambda now=None: {
        "phase": "overnight", "label": "Overnight", "is_regular": False})
    out = asyncio.run(main.session_prices("COIN"))
    assert out["prices"]["current"] == 186.99
    assert out["prices"]["current_kind"] == "overnight"
