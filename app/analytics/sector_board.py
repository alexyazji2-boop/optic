"""The sector board: where each SPDR sector sits against its overnight levels.

Eleven sectors, one row each, answering three questions a reader actually asks
before choosing where to look: is this sector's short-term trend up, down or
undecided; how far is it from the level that would change that; and is money
moving into it or out of it relative to the market.

**The levels are the prior completed session's high and low.** That is the whole
definition, and it is deliberately a simple one. Those two prices are what the
overnight and pre-market session traded against, so trading above yesterday's
high means buyers took control while most people were asleep, and below
yesterday's low means the opposite. No smoothing, no bands, no parameters to
tune — the reader can check both numbers on any chart.

**Which session is "prior", and which price is compared, depend on the clock.**
The levels are the most recent regular session that has *closed*: yesterday's
while today's is trading, today's once the bell has gone, Friday's all weekend.
The price is today's regular-session price in the session, and outside it the
newest extended-hours print struck since that close: after hours, overnight
where a venue has printed tonight, pre-market. Where nothing has printed since
the close, the price is the close itself, which sits inside its own session's
range by definition, so the row reads neutral and says why rather than
inventing a print. This used to be positional (`iloc[-1]` against `iloc[-2]`),
which is right only while today's bar exists: before the open it compared the
last close with the range of the session before it.

Two more things this is careful about.

**"Overnight" here does not mean futures.** There is no futures feed behind this;
the levels come from regular-session daily bars. The label describes what the
level *is* — the boundary the overnight session traded around — not a claim to
have watched the globex tape.

**Trend and rotation are different questions and are reported separately.** A
sector can be above yesterday's high while still losing ground to the index all
month; that is a sector rising in a market rising faster, which is not where
money is going. Merging the two into one verdict would hide exactly the case
worth seeing, so trend is absolute and rotation is relative, side by side.
"""

from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from .. import session as session_mod
from ..providers import overnight as overnight_mod
from .sectors import SECTORS

# The market a sector is measured against for rotation. SPY rather than an
# equal-weight index on purpose: it is what "the market" means to most readers
# and what the rest of the terminal compares against.
BENCHMARK = "SPY"

# The major index ETFs. Same board, same definition of a level: the Indices tab
# asks the identical question of SPY that the Macro tab asks of XLE, so it runs
# through the same code rather than a parallel copy that would drift.
INDEX_ETFS: List[Dict[str, str]] = [
    {"symbol": "SPY", "name": "S&P 500"},
    {"symbol": "QQQ", "name": "Nasdaq 100"},
    {"symbol": "IWM", "name": "Russell 2000"},
    {"symbol": "DIA", "name": "Dow 30"},
]

# Every ETF either board draws. The session quotes are asked for all of them
# whichever board is being built, so the Indices tab, the Macro tab and Home
# share one cached request (one call, fifteen symbols, 0.32s on 2026-10-14)
# rather than three overlapping ones.
QUOTE_SYMBOLS: List[str] = list(dict.fromkeys(
    [e["symbol"] for e in INDEX_ETFS] + [e["symbol"] for e in SECTORS]))

# What a row's price is, in the words the board prints and the client
# compares against ('last close', 'regular session'), written down because a
# string compared in two files is a vocabulary. "last close" is the honest
# absence of a print since the levels were set: see _session_price.
PRICE_KINDS = ("regular session", "pre-market", "after hours", "overnight", "last close")

# Look-backs for rotation, in sessions. A week catches the current push; a month
# says whether it is a real reallocation or a couple of good days.
ROTATION_FAST, ROTATION_SLOW = 5, 20

# How much a sector has to beat or trail the index by before it counts as
# rotation rather than noise. Sector ETFs routinely diverge from SPY by a few
# tenths of a percent over a week without anything happening.
ROTATION_BAND_PCT = 1.0


def _num(value: Any) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return None if out != out or out in (float("inf"), float("-inf")) else out


def _ret_pct(closes, bars: int) -> Optional[float]:
    """Percentage return over `bars` sessions."""
    if closes is None or len(closes) <= bars:
        return None
    prev, last = _num(closes.iloc[-1 - bars]), _num(closes.iloc[-1])
    if prev is None or last is None or prev <= 0:
        return None
    return (last / prev - 1.0) * 100.0


def _classify(price: float, bull_above: float, bear_below: float) -> str:
    """Which side of the prior session's range price is on."""
    if price > bull_above:
        return "uptrend"
    if price < bear_below:
        return "downtrend"
    return "neutral"


def _rotation(spread_fast: Optional[float],
              spread_slow: Optional[float]) -> Dict[str, Any]:
    """Is money moving into this sector, out of it, or neither?

    Both windows have to agree before this says anything. One week of
    outperformance is a move; a week that contradicts the month is a bounce, and
    calling that "rotating in" is how a reader ends up buying the top of a
    counter-trend rally.
    """
    if spread_fast is None and spread_slow is None:
        return {"state": "unknown", "label": "—",
                "note": "Not enough history to compare against the index."}

    fast = spread_fast if spread_fast is not None else 0.0
    slow = spread_slow if spread_slow is not None else 0.0
    band = ROTATION_BAND_PCT

    if fast >= band and slow >= band:
        state, label = "in", "Rotating in"
        note = ("Ahead of the index over both the past week and the past month . "
                "Money has been moving here, not just visiting.")
    elif fast <= -band and slow <= -band:
        state, label = "out", "Rotating out"
        note = ("Behind the index over both windows, which is money leaving rather "
                "than a single bad session.")
    elif fast >= band > slow and slow <= -band:
        state, label = "turning", "Turning up"
        note = ("Ahead this week after trailing over the month. That is either the "
                "start of a rotation or a bounce inside a losing trend, and one "
                "week cannot tell those apart.")
    elif fast <= -band and slow >= band:
        state, label = "turning", "Turning down"
        note = ("Behind this week after leading over the month. Leadership may be "
                "handing over, or this may be an ordinary pause.")
    else:
        state, label = "neutral", "In line"
        note = ("Tracking the index within about {:.0f}%, which is the normal drift "
                "of a sector fund and not a reallocation.".format(band))

    return {"state": state, "label": label, "note": note}


def _summary(trend: str, bull_above: float, bear_below: float) -> str:
    """One sentence saying where price sits and what it has to do.

    Deliberately mechanical. It is always available, costs nothing, and cannot
    be wrong about the arithmetic — which is what a card needs while the written
    read is still loading, or when the assistant is switched off entirely.
    """
    if trend == "uptrend":
        return ("Above prior session high. Bulls want price to hold above "
                "{:,.2f}.".format(bull_above))
    if trend == "downtrend":
        return ("Below prior session low. Bears want price to stay under "
                "{:,.2f}.".format(bear_below))
    return "Inside prior session range ({:,.2f} – {:,.2f}).".format(bear_below, bull_above)


def _money(value: float) -> str:
    return "${:,.2f}".format(value)


def _vs_level(trend: str, to_break_pct: float, to_breakdown_pct: float) -> Tuple[float, str]:
    """The card's middle line: how far price is from the level that matters now.

    Each state is measured from its own level, as the reference board does it:
    a downtrend from the low it broke, an uptrend from the high it cleared, an
    undecided name from the high it has yet to clear. One figure per state
    rather than both on every card, because the second answers a question the
    state has already answered."""
    if trend == "downtrend":
        return to_breakdown_pct, "{:+.2f}% vs prior session low".format(to_breakdown_pct)
    if trend == "uptrend":
        return to_break_pct, "{:+.2f}% vs prior session high".format(to_break_pct)
    return to_break_pct, "{:+.2f}% to prior high".format(to_break_pct)


def _action(trend: str, bull_above: float, bear_below: float) -> Dict[str, Any]:
    """What would change the state, as a price the reader can watch for.

    A downtrend turns neutral by getting back above the low it broke; an
    uptrend stays one by holding above the high it cleared; an undecided name
    is decided by whichever side of the range it leaves first. "neutral" is
    lower case because it is a word in a sentence here, where the chip beside
    it is a label."""
    if trend == "downtrend":
        return {"kind": "reclaim", "level": round(bear_below, 2),
                "text": "Reclaim {} to turn neutral".format(_money(bear_below))}
    if trend == "uptrend":
        return {"kind": "hold", "level": round(bull_above, 2),
                "text": "Hold {}, else neutral".format(_money(bull_above))}
    return {"kind": "range", "above": round(bull_above, 2), "below": round(bear_below, 2),
            "text": "Above {} turns bullish, below {} bearish".format(
                _money(bull_above), _money(bear_below))}


def _method(entries: List[Dict[str, str]]) -> str:
    """How the board reads, for the board it is printed under.

    The Indices page draws these levels for SPY, QQQ, IWM and DIA and prints
    this beside them; the rotation half described "the sector's return against
    SPY's", on a page with no rotation column, about a board whose first row
    is SPY. Rotation is only described where it is shown."""
    levels = (
        "Bull above and bear below are the prior completed session's high and "
        "low, from regular-session daily bars. In the regular session that is "
        "yesterday's range against today's price. Outside it, the levels are "
        "the last session to close (today's, after the bell) and the price is "
        "the newest extended-hours print since that close: after hours, "
        "overnight where a venue has printed tonight, or pre-market. Where "
        "nothing has printed since, the price is that close, which sits inside "
        "its own range by definition, so the row reads neutral and says so. "
        "Above the high is an overnight uptrend, below the low a downtrend, "
        "between them neutral. There is no futures feed behind this: the label "
        "describes what the level is rather than claiming to have watched the "
        "futures tape.")
    if entries is INDEX_ETFS:
        return levels
    return levels + (
        " Rotation is separate and relative. The sector's return against {}'s "
        "over {} and {} sessions, needing both windows to agree before it counts "
        "as anything.".format(BENCHMARK, ROTATION_FAST, ROTATION_SLOW))


# ------------------------------------------------------------ the session rule

def _plan(when: datetime) -> Dict[str, Any]:
    """Which session's range is the level, read once for the whole board.

    The levels are always the most recent regular session that has *closed*,
    which `session.last_regular_close` names from the exchange's calendar:
    yesterday's during today's session, today's after the bell, Friday's all
    weekend, and on a holiday the session before it. Only the price changes
    with the phase."""
    et = when.astimezone(session_mod.ET)
    sess = session_mod.state(et)
    closed = session_mod.last_regular_close(et)
    return {"when": et, "sess": sess, "phase": sess["phase"], "today": et.date(),
            "levels_date": closed.date() if closed else None}


def _bar_dates(frame) -> Optional[List[date]]:
    """Each daily bar's session date in New York, or None if the frame has none.

    yfinance's daily index is a naive midnight per session (checked
    2026-10-14); a tz-aware one is converted rather than truncated, so a bar
    stamped midnight ET is not read as the UTC day before. A frame without
    dates keeps the positional read the board always had."""
    idx = getattr(frame, "index", None)
    if not isinstance(idx, pd.DatetimeIndex):
        return None
    if idx.tz is not None:
        idx = idx.tz_convert(session_mod.ET)
    return [ts.date() for ts in idx]


def _instant(value: Any) -> Optional[datetime]:
    if not value:
        return None
    try:
        stamp = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return stamp if stamp.tzinfo else stamp.replace(tzinfo=timezone.utc)


def _close_of(day: date) -> datetime:
    """When `day`'s regular session closed: 1:00pm on a half day."""
    return (session_mod.regular_close(day)
            or datetime(day.year, day.month, day.day, 16, 0, tzinfo=session_mod.ET))


def _day_name(day: date, today: date) -> str:
    """"today's", "Tuesday's", or "the Oct 3" for a session a week or more ago."""
    if day == today:
        return "today's"
    if 0 < (today - day).days < 7:
        return day.strftime("%A") + "'s"
    return "the " + day.strftime("%b %-d").replace(" 0", " ")


def _session_quotes(provider, plan: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """Every board ETF's session quote, with tonight's overnight print attached.

    Never raises: a missing quote is "no print known", which the row answers
    with the last close. The overnight prints are a second request, made only
    inside the overnight window (`overnight_started_at` is None outside it),
    and attached to copies because the provider hands back its cached dicts."""
    fetch = getattr(provider, "session_quotes", None)
    if not callable(fetch):
        return {}
    try:
        got = fetch(QUOTE_SYMBOLS) or {}
    except Exception:                            # noqa: BLE001 - provider-agnostic
        return {}
    started = session_mod.overnight_started_at(plan["when"])
    if not started or not got:
        return got
    try:
        found = overnight_mod.quotes(list(got))
    except Exception:                            # noqa: BLE001
        found = {}
    out: Dict[str, Dict[str, Any]] = {}
    for sym, quote in got.items():
        own = dict(quote or {})
        overnight_mod.attach(own, started, found.get(sym))
        out[sym] = own
    return out


def _regular_print(quote: Optional[Dict[str, Any]], plan: Dict[str, Any]) -> Optional[Tuple[float, str]]:
    """Today's regular-session price from the quote, if it was struck today.

    At 9:30:05 the quote can still carry yesterday's 4pm print, and that is a
    price from inside the range it would be compared with."""
    if not quote:
        return None
    price, at = _num(quote.get("price")), _instant(quote.get("regular_market_time"))
    if not price or price <= 0 or at is None:
        return None
    day = plan["today"]
    if at < datetime(day.year, day.month, day.day, 9, 30, tzinfo=session_mod.ET):
        return None
    return price, at.isoformat()


def _extended_print(quote: Optional[Dict[str, Any]], plan: Dict[str, Any],
                    since: datetime) -> Optional[Dict[str, Any]]:
    """The extended-hours print to compare, struck after `since`, or None.

    `session.price_view` chooses which print the phase calls current, and its
    choice stands when it passes the one test this board adds: it was struck
    after the close of the session whose range it is measured against. Yahoo
    keeps a session's pre-market and after-hours prints on the quote after
    that session ends, so a choice by phase alone can hand back a print from
    before the levels were set. When the choice fails, the newest print that
    passes stands in: at 5:00am, with no pre-market trade yet, last night's
    after-hours print is still a trade since the close."""
    if not quote:
        return None
    view = session_mod.price_view(quote, plan["when"], plan["sess"])
    picked = view.get("extended") if view.get("current_kind") != "regular session" else None
    candidates = ([picked] if picked else []) + [
        {"kind": "overnight", "price": quote.get("overnight_price"),
         "as_of": quote.get("overnight_time"), "venue": quote.get("overnight_venue")},
        {"kind": "after hours", "price": quote.get("post_market_price"),
         "as_of": quote.get("post_market_time")},
        {"kind": "pre-market", "price": quote.get("pre_market_price"),
         "as_of": quote.get("pre_market_time")},
    ]
    valid = []
    for cand in candidates:
        price, at = _num(cand.get("price")), _instant(cand.get("as_of"))
        if price and price > 0 and at is not None and at > since:
            valid.append((cand, price, at))
    if not valid:
        return None
    chosen = valid[0] if (picked and valid[0][0] is picked) else max(valid, key=lambda v: v[2])
    cand, price, at = chosen
    return {"kind": cand["kind"], "price": price, "as_of": at.isoformat(),
            "venue": cand.get("venue")}


def _session_price(frame, dates: List[date], i_levels: int,
                   quote: Optional[Dict[str, Any]], plan: Dict[str, Any]) -> Dict[str, Any]:
    """`{price, kind, as_of, venue, note}` for one row under the session rule."""
    level_day = dates[i_levels]
    level_close = _num(frame["Close"].iloc[i_levels])
    whose = _day_name(level_day, plan["today"])
    if plan["phase"] == "regular":
        live = _regular_print(quote, plan)
        if live:
            return {"price": live[0], "kind": "regular session", "as_of": live[1],
                    "delayed": _num(quote.get("delayed_minutes"))}
        # Today's daily bar, which is what the board read before the quotes:
        # Yahoo's chart keeps its close moving through the session.
        last = len(dates) - 1
        if last > i_levels and dates[last] == plan["today"]:
            bar = _num(frame["Close"].iloc[last])
            if bar and bar > 0:
                return {"price": bar, "kind": "regular session", "as_of": None}
        return {"price": level_close, "kind": "last close", "as_of": None,
                "note": ("No trade from today's session has reached the feed yet, so "
                         "the price is {} close, which sits inside its own range by "
                         "definition.".format(whose))}
    ext = _extended_print(quote, plan, _close_of(level_day))
    if ext:
        # Yahoo's delay is the regular feed's; an overnight venue's print is
        # its own and carries its own time.
        return {"price": ext["price"], "kind": ext["kind"], "as_of": ext["as_of"],
                "venue": ext.get("venue"),
                "delayed": None if ext["kind"] == "overnight" else _num(quote.get("delayed_minutes"))}
    return {"price": level_close, "kind": "last close", "as_of": None,
            "note": ("Nothing has printed since {} close, so the price is that close, "
                     "which sits inside its own session's range by definition."
                     .format(whose))}


def build(provider, entries: Optional[List[Dict[str, str]]] = None,
          now: Optional[datetime] = None,
          quotes: Optional[Dict[str, Dict[str, Any]]] = None) -> Dict[str, Any]:
    """One row per instrument, against its own overnight levels.

    `now` and `quotes` are for tests: the instant the session rule is read at,
    and the session quotes in `provider.session_quotes`'s shape (overnight
    fields already attached). Left None, the clock is read and the quotes are
    fetched, once, for every board ETF."""
    entries = entries or SECTORS
    symbols = [s["symbol"] for s in entries] + [BENCHMARK]
    try:
        frames = provider.batch_history(symbols, period="3mo", interval="1d") or {}
    except Exception as exc:                     # noqa: BLE001 - provider-agnostic
        return {"available": False,
                "reason": "Sector history unavailable: {}: {}".format(
                    type(exc).__name__, str(exc)[:120])}

    plan = _plan(now or datetime.now(timezone.utc))
    # Asked for only when some frame carries dates, so a board built from the
    # tests' plain frames never reaches for the network.
    dated = any(_bar_dates(f) for f in frames.values() if f is not None)
    if quotes is None:
        quotes = _session_quotes(provider, plan) if dated and plan["levels_date"] else {}

    bench = frames.get(BENCHMARK)
    bench_closes = bench["Close"].dropna() if bench is not None and not bench.empty else None
    bench_fast = _ret_pct(bench_closes, ROTATION_FAST)
    bench_slow = _ret_pct(bench_closes, ROTATION_SLOW)

    rows: List[Dict[str, Any]] = []
    for entry in entries:
        symbol = entry["symbol"]
        frame = frames.get(symbol)
        if frame is None or frame.empty or len(frame) < 3:
            rows.append({"symbol": symbol, "name": entry["name"], "available": False,
                         "reason": "No usable history."})
            continue
        # Positions in the frame and in its closes must be the same bars.
        frame = frame[frame["Close"].notna()]
        if len(frame) < 3:
            rows.append({"symbol": symbol, "name": entry["name"], "available": False,
                         "reason": "No usable history."})
            continue
        closes = frame["Close"]

        dates = _bar_dates(frame)
        notes: List[str] = []
        if dates is None or plan["levels_date"] is None:
            # No dates to read a session from: the prior completed session is
            # the bar before the last, and the price the last bar's close.
            i_levels = len(frame) - 2
            priced: Dict[str, Any] = {"price": _num(closes.iloc[-1]), "kind": None, "as_of": None}
            level_day = None
        else:
            i_levels = max((i for i, d in enumerate(dates) if d <= plan["levels_date"]),
                           default=None)
            if i_levels is None:
                rows.append({"symbol": symbol, "name": entry["name"], "available": False,
                             "reason": "No completed session in the history."})
                continue
            level_day = dates[i_levels]
            if level_day != plan["levels_date"]:
                notes.append("The feed has no bar for {} session yet, so the levels "
                             "are {}.".format(_day_name(plan["levels_date"], plan["today"]),
                                              _day_name(level_day, plan["today"])
                                              + " session"))
            priced = _session_price(frame, dates, i_levels, (quotes or {}).get(symbol), plan)
            if priced.get("note"):
                notes.append(priced["note"])

        price = _num(priced["price"])
        bull_above = _num(frame["High"].iloc[i_levels])
        bear_below = _num(frame["Low"].iloc[i_levels])
        if price is None or bull_above is None or bear_below is None or price <= 0:
            rows.append({"symbol": symbol, "name": entry["name"], "available": False,
                         "reason": "Incomplete bars."})
            continue

        # A close compared with its own session's range is inside it by
        # definition; a bar whose close sits a cent outside its own high (an
        # auction print the bar's range missed) must not make it a trend.
        trend = ("neutral" if priced["kind"] == "last close"
                 else _classify(price, bull_above, bear_below))

        # Was the same state true at the levels session's close? A trend that
        # has held is a different piece of information from one that flipped.
        prior_state = None
        if i_levels >= 1:
            prev_close = _num(closes.iloc[i_levels])
            prev_high = _num(frame["High"].iloc[i_levels - 1])
            prev_low = _num(frame["Low"].iloc[i_levels - 1])
            if prev_close is not None and prev_high is not None and prev_low is not None:
                prior_state = _classify(prev_close, prev_high, prev_low)

        sec_fast, sec_slow = _ret_pct(closes, ROTATION_FAST), _ret_pct(closes, ROTATION_SLOW)
        spread_fast = (sec_fast - bench_fast) if (sec_fast is not None and bench_fast is not None) else None
        spread_slow = (sec_slow - bench_slow) if (sec_slow is not None and bench_slow is not None) else None

        to_break = round((price / bull_above - 1.0) * 100.0, 2)
        to_breakdown = round((price / bear_below - 1.0) * 100.0, 2)
        vs_pct, vs_text = _vs_level(trend, to_break, to_breakdown)
        rows.append({
            "available": True,
            "symbol": symbol,
            "name": entry["name"],
            "price": round(price, 2),
            "bull_above": round(bull_above, 2),
            "bear_below": round(bear_below, 2),
            "trend": trend,
            "summary": _summary(trend, bull_above, bear_below),
            # Signed distance from each level: negative to_break means price is
            # still under the level it has to clear.
            "to_break_pct": to_break,
            "to_breakdown_pct": to_breakdown,
            "vs_level_pct": vs_pct,
            "vs_level_text": vs_text,
            "action": _action(trend, bull_above, bear_below),
            "levels_session": level_day.isoformat() if level_day else None,
            "price_kind": priced["kind"],
            "price_as_of": priced.get("as_of"),
            "price_venue": priced.get("venue"),
            "price_delayed_minutes": priced.get("delayed"),
            "note": " ".join(notes) or None,
            "prior_trend": prior_state,
            "intact": (prior_state == trend and trend != "neutral") if prior_state else None,
            "changed": (prior_state is not None and prior_state != trend),
            "rotation": _rotation(spread_fast, spread_slow),
            "rel_week_pct": round(spread_fast, 2) if spread_fast is not None else None,
            "rel_month_pct": round(spread_slow, 2) if spread_slow is not None else None,
        })

    usable = [r for r in rows if r.get("available")]
    return {
        "available": bool(usable),
        "rows": rows,
        "benchmark": BENCHMARK,
        "counts": {
            "uptrend": sum(1 for r in usable if r["trend"] == "uptrend"),
            "downtrend": sum(1 for r in usable if r["trend"] == "downtrend"),
            "neutral": sum(1 for r in usable if r["trend"] == "neutral"),
            "rotating_in": sum(1 for r in usable if r["rotation"]["state"] == "in"),
            "rotating_out": sum(1 for r in usable if r["rotation"]["state"] == "out"),
        },
        "basis": _basis(usable, plan),
        "method": _method(entries),
    }


def _basis(usable: List[Dict[str, Any]], plan: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Which session the levels are from and which price is compared, for the
    line every surface prints above its cards. The most common answer across
    the rows, with the count of each, because one thin ETF without an
    after-hours print should not change what the board says of the other
    fourteen; that row carries its own note."""
    kinds = Counter(r["price_kind"] for r in usable if r.get("price_kind"))
    days = Counter(r["levels_session"] for r in usable if r.get("levels_session"))
    if not kinds or not days:
        return None
    kind = kinds.most_common(1)[0][0]
    day = date.fromisoformat(days.most_common(1)[0][0])
    stamps = sorted((_instant(r["price_as_of"]) for r in usable
                     if r.get("price_kind") == kind and _instant(r.get("price_as_of"))))
    return {
        "phase": plan["phase"],
        "phase_label": plan["sess"].get("label"),
        "levels_session": day.isoformat(),
        "levels_label": _day_name(day, plan["today"]) + " session",
        "price_kind": kind,
        "price_kinds": dict(kinds),
        # The newest and the oldest print of that kind. Either alone misleads
        # outside the session: SPY prints until 8pm and a thin sector fund's
        # last after-hours trade can be 4:30, so one time would overstate the
        # one or understate the other. The surfaces print a span when they
        # differ.
        "price_as_of": stamps[-1].isoformat() if stamps else None,
        "price_as_of_from": stamps[0].isoformat() if stamps else None,
        # Named per symbol rather than as one board-wide delay, because it is
        # not one: on 2026-10-14 Yahoo reported QQQ 15 minutes delayed and the
        # fourteen Arca-listed ETFs real time.
        "delayed": [{"symbol": r["symbol"], "minutes": int(r["price_delayed_minutes"])}
                    for r in usable if (r.get("price_delayed_minutes") or 0) > 0],
    }


# The index cards Home shows above the sectors: the three the request named.
# The Indices tab's board also carries DIA.
HOME_INDICES = ("SPY", "QQQ", "IWM")


def trends(provider, now: Optional[datetime] = None,
           quotes: Optional[Dict[str, Dict[str, Any]]] = None) -> Dict[str, Any]:
    """Home's card grid: SPY, QQQ and IWM over the eleven sectors, in one answer.

    The same two builds the Indices and Macro tabs draw, so a card on Home
    and a row on either tab are the same numbers, read at one instant against
    one set of quotes. One request for the page rather than two, and one
    `basis` over the fourteen cards it shows: built from the two boards' own,
    the line would count DIA, which Home leaves off, and name QQQ's delay only
    if it happened to read the index board's."""
    when = now or datetime.now(timezone.utc)
    plan = _plan(when)
    if quotes is None:
        quotes = _session_quotes(provider, plan) if plan["levels_date"] else {}
    idx = build(provider, INDEX_ETFS, now=when, quotes=quotes)
    sec = build(provider, SECTORS, now=when, quotes=quotes)
    index_rows = [r for r in idx.get("rows") or [] if r.get("symbol") in HOME_INDICES]
    sector_rows = list(sec.get("rows") or [])
    usable = [r for r in index_rows + sector_rows if r.get("available")]
    out: Dict[str, Any] = {
        "available": bool(usable),
        "indices": index_rows,
        "sectors": sector_rows,
        "counts": {k: sum(1 for r in usable if r["trend"] == k)
                   for k in ("uptrend", "downtrend", "neutral")},
        "basis": _basis(usable, plan),
        # The levels half only: Home shows no rotation, and describing a
        # column a page does not have is the fault _method's docstring records.
        "method": _method(INDEX_ETFS),
    }
    if not usable:
        out["reason"] = sec.get("reason") or idx.get("reason") or "No usable history."
    return out


def detail(provider, symbol: str) -> Dict[str, Any]:
    """One sector's row plus the context a written read needs.

    Built on top of build() rather than beside it, so the numbers in a sector
    read are the same numbers in the table above it. Two code paths computing
    "where is XLE trading" would eventually disagree, and the reader would have
    no way to know which one to believe.
    """
    symbol = (symbol or "").upper().strip()
    universe = SECTORS + INDEX_ETFS
    entries = [e for e in universe if e["symbol"] == symbol]
    if not entries:
        return {"available": False,
                "reason": "{} is not one of the sector or index ETFs on the board.".format(symbol)}
    is_index = any(e["symbol"] == symbol for e in INDEX_ETFS)

    board = build(provider, INDEX_ETFS if is_index else SECTORS)
    if not board.get("available"):
        return {"available": False, "reason": board.get("reason", "Sector data unavailable.")}

    row = next((r for r in board["rows"] if r["symbol"] == symbol), None)
    if not row or not row.get("available"):
        return {"available": False,
                "reason": (row or {}).get("reason", "No usable history for this sector.")}

    # Extra shape for the write-up: returns over several horizons and where price
    # sits against its own averages. Fetched once more rather than threaded
    # through build(), because the table does not need it and every sector row
    # would carry fields nothing renders.
    try:
        frames = provider.batch_history([symbol, BENCHMARK], period="1y", interval="1d") or {}
    except Exception:
        frames = {}

    frame = frames.get(symbol)
    context: Dict[str, Any] = {}
    if frame is not None and not frame.empty:
        closes = frame["Close"].dropna()
        context["returns_pct"] = {
            "day": _ret_pct(closes, 1), "week": _ret_pct(closes, 5),
            "month": _ret_pct(closes, 21), "quarter": _ret_pct(closes, 63),
        }
        last = _num(closes.iloc[-1])
        for window in (50, 200):
            if len(closes) >= window and last:
                avg = _num(closes.rolling(window).mean().iloc[-1])
                if avg:
                    context["vs_sma{}_pct".format(window)] = round((last / avg - 1.0) * 100.0, 2)
        if len(closes) >= 252:
            year = closes.tail(252)
            hi, lo = _num(year.max()), _num(year.min())
            if hi and lo and hi > lo and last:
                context["range_position_pct"] = round((last - lo) / (hi - lo) * 100.0, 1)
                context["fifty_two_week"] = {"high": round(hi, 2), "low": round(lo, 2)}

    bench = frames.get(BENCHMARK)
    if bench is not None and not bench.empty:
        bc = bench["Close"].dropna()
        context["benchmark_returns_pct"] = {
            "day": _ret_pct(bc, 1), "week": _ret_pct(bc, 5),
            "month": _ret_pct(bc, 21), "quarter": _ret_pct(bc, 63),
        }

    return {
        "available": True,
        "symbol": symbol,
        "name": row["name"],
        "row": row,
        "context": context,
        "benchmark": BENCHMARK,
        "peer_counts": board.get("counts"),
        "is_index": is_index,
        "method": board.get("method"),
    }
