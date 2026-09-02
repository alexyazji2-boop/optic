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

Two things this is careful about.

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

from typing import Any, Dict, List, Optional

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
        note = ("Ahead of the index over both the past week and the past month — "
                "money has been moving here, not just visiting.")
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
        note = ("Behind this week after leading over the month — leadership may be "
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
        return ("Above prior session high — bulls want price to hold above "
                "{:,.2f}.".format(bull_above))
    if trend == "downtrend":
        return ("Below prior session low — bears want price to stay under "
                "{:,.2f}.".format(bear_below))
    return "Inside prior session range ({:,.2f} – {:,.2f}).".format(bear_below, bull_above)


def build(provider, entries: Optional[List[Dict[str, str]]] = None) -> Dict[str, Any]:
    """One row per instrument, against its own overnight levels."""
    entries = entries or SECTORS
    symbols = [s["symbol"] for s in entries] + [BENCHMARK]
    try:
        frames = provider.batch_history(symbols, period="3mo", interval="1d") or {}
    except Exception as exc:                     # noqa: BLE001 - provider-agnostic
        return {"available": False,
                "reason": "Sector history unavailable: {}: {}".format(
                    type(exc).__name__, str(exc)[:120])}

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

        closes = frame["Close"].dropna()
        price = _num(closes.iloc[-1])
        # The prior *completed* session — index -2, because -1 is today's bar and
        # a level taken from the bar price is currently inside is not a level.
        bull_above = _num(frame["High"].iloc[-2])
        bear_below = _num(frame["Low"].iloc[-2])
        if price is None or bull_above is None or bear_below is None or price <= 0:
            rows.append({"symbol": symbol, "name": entry["name"], "available": False,
                         "reason": "Incomplete bars."})
            continue

        trend = _classify(price, bull_above, bear_below)

        # Was the same state true a session ago? A trend that has held is a
        # different piece of information from one that flipped this morning.
        prior_state = None
        if len(frame) >= 4:
            prev_close = _num(closes.iloc[-2])
            prev_high, prev_low = _num(frame["High"].iloc[-3]), _num(frame["Low"].iloc[-3])
            if prev_close is not None and prev_high is not None and prev_low is not None:
                prior_state = _classify(prev_close, prev_high, prev_low)

        sec_fast, sec_slow = _ret_pct(closes, ROTATION_FAST), _ret_pct(closes, ROTATION_SLOW)
        spread_fast = (sec_fast - bench_fast) if (sec_fast is not None and bench_fast is not None) else None
        spread_slow = (sec_slow - bench_slow) if (sec_slow is not None and bench_slow is not None) else None

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
            "to_break_pct": round((price / bull_above - 1.0) * 100.0, 2),
            "to_breakdown_pct": round((price / bear_below - 1.0) * 100.0, 2),
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
        "method": (
            "Bull above and bear below are the prior completed session's high and "
            "low — the two prices the overnight and pre-market session traded "
            "against. Above the high is an overnight uptrend, below the low a "
            "downtrend, between them undecided. There is no futures feed behind "
            "this: the levels come from regular-session daily bars, and the label "
            "describes what the level is rather than claiming to have watched the "
            "overnight tape. Rotation is separate and relative — the sector's "
            "return against {}'s over {} and {} sessions, needing both windows to "
            "agree before it counts as anything.".format(
                BENCHMARK, ROTATION_FAST, ROTATION_SLOW)
        ),
    }

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
