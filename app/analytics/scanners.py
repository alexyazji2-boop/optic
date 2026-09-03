"""Named scans over the already-ranked universe.

The terminal already screens the whole NASDAQ down to the few hundred names that
clear price, liquidity, history and volatility gates, and scores each one. That
ranking is cached on disk and rebuilt periodically, which means a scan over it
costs a file read rather than three thousand downloads — the difference between a
feature that answers instantly and one nobody waits for.

So a scanner here is not a data-fetching operation. It is a question asked of
rows that already exist: *which of these are pressed against a 52-week high on
expanding volume*, *which are holding a long-term uptrend but have pulled back to
their 20-day*. Every scan is a filter and a sort over the same metrics, and any
scan that would need a metric the ranking does not carry is not implemented
rather than approximated.

Two deliberate boundaries.

**A scan is a shortlist, not a verdict.** These are price-and-volume patterns.
They carry no options data, no fundamentals, no news and no earnings date, so a
name at the top of a scan can still be rejected outright by the full analysis on
the Swing tab. Every scan states what it cannot see.

**Every scan names its own failure mode.** A breakout scan finds breakouts, and
breakouts fail; a pullback scan cannot tell a pullback from the start of a
decline, because at the moment of scanning those are the same shape. Saying so
next to the results is the difference between a screen and an implied tip.
"""

from __future__ import annotations

import time
from typing import Any, Callable, Dict, List, Optional

# A ranking older than this is reported as stale rather than served silently. The
# metrics are daily bars, so a few hours is fine and a couple of days is not —
# "near its 52-week high" is a claim about now, not about Tuesday.
STALE_AFTER_HOURS = 30.0

# Rows returned per scan. Enough to choose from, few enough to actually read.
DEFAULT_LIMIT = 25


def _num(value: Any) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return None if out != out or out in (float("inf"), float("-inf")) else out


def _above(row: Dict[str, Any], key: str) -> Optional[bool]:
    """Is price above this moving average? None when the average is missing."""
    price, avg = _num(row.get("price")), _num(row.get(key))
    if price is None or avg is None or avg <= 0:
        return None
    return price > avg


def _pct_from(row: Dict[str, Any], key: str) -> Optional[float]:
    price, avg = _num(row.get("price")), _num(row.get(key))
    if price is None or avg is None or avg <= 0:
        return None
    return (price / avg - 1.0) * 100.0


# --------------------------------------------------------------- the scans

def _f_breakout(r: Dict[str, Any]) -> bool:
    """Pressed against the top of the 52-week range, with volume confirming."""
    pos, vol = _num(r.get("range_position")), _num(r.get("volume_expansion"))
    return (pos is not None and pos >= 0.95
            and vol is not None and vol >= 1.15
            and _above(r, "sma50") is True)


def _f_pullback(r: Dict[str, Any]) -> bool:
    """Long-term uptrend intact, but price has come back to the 20-day."""
    if _above(r, "sma200") is not True:
        return False
    sma50, sma200 = _num(r.get("sma50")), _num(r.get("sma200"))
    if sma50 is None or sma200 is None or sma50 <= sma200:
        return False
    # Below the 20-day but not collapsing: still above the 50-day.
    return _above(r, "sma20") is False and _above(r, "sma50") is True


def _f_volume(r: Dict[str, Any]) -> bool:
    """Trading far more than its own recent normal."""
    vol = _num(r.get("volume_expansion"))
    return vol is not None and vol >= 1.6


def _f_downtrend(r: Dict[str, Any]) -> bool:
    """Below a falling long-term average — the mirror of the momentum scan."""
    sma50, sma200 = _num(r.get("sma50")), _num(r.get("sma200"))
    if sma50 is None or sma200 is None:
        return False
    return _above(r, "sma200") is False and sma50 < sma200


# A "steady" trend has to be steady in its returns as well as in its daily range.
# Filtering on ATR alone put FBRX at the top of this scan: up 57% in a month with
# the smallest average true range in the whole universe, because it gapped once
# and then went flat. Both numbers were correct and the combination was absurd —
# a stock that leapt and stopped is the opposite of what this scan is for.
STEADY_MAX_ATR_PCT = 3.0
STEADY_MAX_ROC20_PCT = 20.0


def _f_steady(r: Dict[str, Any]) -> bool:
    """An uptrend that is not lurching: above every average, low daily range."""
    atr, roc = _num(r.get("atr_pct")), _num(r.get("roc20"))
    return (atr is not None and atr <= STEADY_MAX_ATR_PCT
            and roc is not None and abs(roc) <= STEADY_MAX_ROC20_PCT
            and _above(r, "sma20") is True
            and _above(r, "sma50") is True
            and _above(r, "sma200") is True)


def _f_extended(r: Dict[str, Any]) -> bool:
    """Very large one-month move and at the top of the range.

    Included because it is the honest counterpart to the momentum scan: the same
    names, framed as a risk rather than an opportunity.
    """
    roc, pos = _num(r.get("roc20")), _num(r.get("range_position"))
    return (roc is not None and roc >= 30.0
            and pos is not None and pos >= 0.9)


# --------------------------------------------- movers, volume and risk scans
#
# Added as named presets so the Scan tab can group by the question being asked
# rather than presenting one flat list of seven. Each still runs over the same
# ranked universe and each still declares what it cannot see.

# What counts as "a meaningful move" over a month. Below this a name is drifting,
# and a movers list full of 3% moves is a liquidity list wearing a different hat.
MOVER_MIN_ABS_ROC20 = 8.0

# Dollar volume that marks a name as genuinely heavily traded rather than merely
# liquid enough to pass the screen's gate.
HEAVY_DOLLAR_VOLUME = 150_000_000.0

# ATR above which a name is a high-risk swing: the daily range alone can take out
# an ordinary stop.
HIGH_RISK_MIN_ATR_PCT = 6.0


def _f_movers(r: Dict[str, Any]) -> bool:
    """Liquid names that have actually moved over the past month, either way."""
    roc = _num(r.get("roc20"))
    return roc is not None and abs(roc) >= MOVER_MIN_ABS_ROC20


def _f_gainers_volume(r: Dict[str, Any]) -> bool:
    """Up on the month with participation behind it."""
    roc, vol = _num(r.get("roc20")), _num(r.get("volume_expansion"))
    return (roc is not None and roc >= MOVER_MIN_ABS_ROC20
            and vol is not None and vol >= 1.1)


def _f_decliners_volume(r: Dict[str, Any]) -> bool:
    """Down on the month with participation behind it.

    The mirror of the gainers scan and deliberately kept: a terminal that only
    lists what is going up is a terminal that cannot see half the market.
    """
    roc, vol = _num(r.get("roc20")), _num(r.get("volume_expansion"))
    return (roc is not None and roc <= -MOVER_MIN_ABS_ROC20
            and vol is not None and vol >= 1.1)


def _f_volume_leaders(r: Dict[str, Any]) -> bool:
    """The heaviest dollar volume in the universe, move or no move.

    Distinct from the unusual-volume scan: that one asks whether a name is busy
    RELATIVE TO ITSELF, this one asks which names the market's money is actually
    in. A mega-cap is always here and never unusual; a small cap can be wildly
    unusual and still trade nothing.
    """
    dv = _num(r.get("dollar_volume"))
    return dv is not None and dv >= HEAVY_DOLLAR_VOLUME


def _f_high_risk_up(r: Dict[str, Any]) -> bool:
    """Bullish structure with a daily range wide enough to hurt."""
    atr = _num(r.get("atr_pct"))
    return (atr is not None and atr >= HIGH_RISK_MIN_ATR_PCT
            and _above(r, "sma50") is True
            and (_num(r.get("score")) or 0) > 0)


def _f_high_risk_down(r: Dict[str, Any]) -> bool:
    """Bearish structure with a daily range wide enough to hurt."""
    atr = _num(r.get("atr_pct"))
    return (atr is not None and atr >= HIGH_RISK_MIN_ATR_PCT
            and _above(r, "sma50") is False
            and (_num(r.get("score")) or 0) < 0)


SCANS: List[Dict[str, Any]] = [
    {
        "id": "movers",
        "name": "Market movers",
        "looks_for": "Liquid names that have made a meaningful move over the past "
                     "month, in either direction. The broadest of these lists and the "
                     "one to open first: it asks only whether something happened, not "
                     "whether the shape of it is good.",
        "blind_spot": "A move is not a reason. This cannot tell an earnings gap from a "
                      "sector rotation from a takeover rumour, and the biggest movers "
                      "are frequently the ones where the news is already known to "
                      "everyone but the reader.",
        "filter": _f_movers,
        "sort": lambda r: -abs(_num(r.get("roc20")) or 0),
        "columns": ["roc20", "roc60", "volume_expansion", "dollar_volume"],
    },
    {
        "id": "gainers-volume",
        "name": "Top gainers with volume",
        "looks_for": "Up meaningfully over the month with volume running above its own "
                     "recent normal. The volume condition is the point. A rise nobody "
                     "traded is a different event from one the market showed up for.",
        "blind_spot": "Volume confirms that participation was real, not that it was "
                      "informed. A crowded move is still a crowded move, and this "
                      "ranks by size of gain, which is exactly how a reader ends up "
                      "buying the most extended name on the list.",
        "filter": _f_gainers_volume,
        "sort": lambda r: -(_num(r.get("roc20")) or 0),
        "columns": ["roc20", "volume_expansion", "range_position", "score"],
    },
    {
        "id": "decliners-volume",
        "name": "Top decliners with volume",
        "looks_for": "Down meaningfully over the month on above-average volume. The "
                     "mirror of the gainers list, kept because a terminal that only "
                     "shows what is rising can only see half the market.",
        "blind_spot": "A falling name on heavy volume is where both bargain hunters "
                      "and forced sellers are, and price alone cannot distinguish "
                      "them. Nothing here says the decline is finished.",
        "filter": _f_decliners_volume,
        "sort": lambda r: (_num(r.get("roc20")) or 0),
        "columns": ["roc20", "volume_expansion", "range_position", "score"],
    },
    {
        "id": "volume-leaders",
        "name": "Volume leaders",
        "looks_for": "The heaviest dollar volume in the universe, whether or not the "
                     "price has moved. Where the market's money actually is.",
        "blind_spot": "Different question from unusual volume: a mega-cap is always "
                      "here and never unusual, while a small cap can be trading five "
                      "times its normal and still not appear. Heavy volume is a "
                      "statement about size, not about interest.",
        "filter": _f_volume_leaders,
        "sort": lambda r: -(_num(r.get("dollar_volume")) or 0),
        "columns": ["dollar_volume", "volume_expansion", "roc20", "score"],
    },
    {
        "id": "high-risk-up",
        "name": "High-risk swings, upside",
        "looks_for": "Bullish structure in names whose ordinary daily range is wide "
                     "enough to take out a normal stop. Labelled as risk rather than "
                     "opportunity because that is the honest framing: the setup and "
                     "the danger are the same property.",
        "blind_spot": "A wide average range means position sizing matters more than "
                      "the setup does. These names can be right about direction and "
                      "still stop you out on the way.",
        "filter": _f_high_risk_up,
        "sort": lambda r: -(_num(r.get("score")) or 0),
        "columns": ["atr_pct", "score", "roc20", "range_position"],
    },
    {
        "id": "high-risk-down",
        "name": "High-risk swings, downside",
        "looks_for": "Bearish structure in names with a wide daily range. The short "
                     "side of the same list.",
        "blind_spot": "Everything true of the upside version, plus the asymmetry of "
                      "being short: a squeeze in a high-ATR name moves faster against "
                      "you than the trend ever moved for you.",
        "filter": _f_high_risk_down,
        "sort": lambda r: (_num(r.get("score")) or 0),
        "columns": ["atr_pct", "score", "roc20", "range_position"],
    },
    {
        "id": "momentum",
        "name": "Momentum leaders",
        "looks_for": "The highest-scoring names on the screen's own trend and momentum "
                     "score. Above their averages, with those averages stacked in "
                     "order, and returns to match.",
        "blind_spot": "Momentum scores describe what has already happened. A name is "
                      "here because it has been strong, which is not the same as a "
                      "claim it will continue, and the highest scores are often the "
                      "most extended.",
        "filter": None,
        "sort": lambda r: -(_num(r.get("score")) or -999),
        "columns": ["score", "roc20", "roc60", "range_position"],
    },
    {
        "id": "breakout",
        "name": "At 52-week highs",
        "looks_for": "Price within 5% of the top of its own 52-week range, with volume "
                     "running above its recent average and the 50-day average beneath "
                     "it. Volume matters here: a high on quiet trade is a different "
                     "event from a high the market showed up for.",
        "blind_spot": "This finds the shape of a breakout, and cannot tell a breakout "
                      "from a false one. That distinction only exists afterwards. It "
                      "also has no idea whether the move is earnings, a takeover "
                      "rumour or a short squeeze.",
        "filter": _f_breakout,
        "sort": lambda r: -(_num(r.get("range_position")) or 0),
        "columns": ["range_position", "volume_expansion", "roc20", "score"],
    },
    {
        "id": "pullback",
        "name": "Pullback in an uptrend",
        "looks_for": "The long-term trend still intact. Price above a rising 200-day, "
                     "50-day above the 200-day. But price has slipped below its "
                     "20-day while holding the 50-day. The shape of a pause inside a "
                     "trend rather than a break of one.",
        "blind_spot": "A pullback and the first leg of a real decline look identical "
                      "at the moment they are scanned. That is not a limitation of "
                      "this scan; it is the nature of the pattern, and it is why the "
                      "50-day is the line being watched.",
        "filter": _f_pullback,
        "sort": lambda r: -(_num(r.get("score")) or -999),
        "columns": ["pct_from_sma20", "pct_from_sma50", "roc60", "score"],
    },
    {
        "id": "volume",
        "name": "Unusual volume",
        "looks_for": "Twenty-day average volume running at least 60% above the "
                     "sixty-day average. The market paying markedly more attention "
                     "to this name than it recently has.",
        "blind_spot": "Volume says something is happening; it never says what, or in "
                      "which direction. An index-inclusion, a secondary offering and a "
                      "takeover approach all look the same here.",
        "filter": _f_volume,
        "sort": lambda r: -(_num(r.get("volume_expansion")) or 0),
        "columns": ["volume_expansion", "roc20", "range_position", "score"],
    },
    {
        "id": "steady",
        "name": "Steady uptrends",
        "looks_for": "Above the 20-, 50- and 200-day averages with an average true "
                     "range under 3% of price. Trends that have been grinding rather "
                     "than lurching.",
        "blind_spot": "Low past volatility is not a promise of low future volatility. "
                      "A quiet chart going into a catalyst is quiet right up until it "
                      "is not, and this scan cannot see the calendar.",
        "filter": _f_steady,
        "sort": lambda r: (_num(r.get("atr_pct")) or 99),
        "columns": ["atr_pct", "roc20", "roc60", "score"],
    },
    {
        "id": "extended",
        "name": "Extended. Stretched from the mean",
        "looks_for": "A one-month gain of 30% or more with price near the top of the "
                     "52-week range. The same names momentum finds, asked about from "
                     "the other side.",
        "blind_spot": "Extended is a description, not a timing signal. Things that are "
                      "stretched routinely stretch further, and 'due for a pullback' "
                      "has no basis in this data.",
        "filter": _f_extended,
        "sort": lambda r: -(_num(r.get("roc20")) or 0),
        "columns": ["roc20", "range_position", "atr_pct", "score"],
    },
    {
        "id": "downtrend",
        "name": "Below a falling 200-day",
        "looks_for": "Price under its 200-day average with the 50-day also under the "
                     "200-day. The mirror image of the momentum scan, for names in "
                     "established downtrends.",
        "blind_spot": "This is a list of weak charts, not short candidates. It carries "
                      "no borrow cost, no short interest and no view on why the name "
                      "is falling, and the cheapest-looking of these are often "
                      "cheap for a reason the price already knows.",
        "filter": _f_downtrend,
        "sort": lambda r: (_num(r.get("roc60")) or 999),
        "columns": ["roc20", "roc60", "pct_from_sma200", "score"],
    },
]

SCAN_BY_ID = {s["id"]: s for s in SCANS}

# What each column means, in the reader's terms rather than the field name's.
COLUMN_LABELS = {
    "score": "Score",
    "roc20": "1-month",
    "roc60": "3-month",
    "range_position": "52-wk range",
    "volume_expansion": "Volume vs normal",
    "atr_pct": "Daily range",
    "pct_from_sma20": "vs 20-day",
    "pct_from_sma50": "vs 50-day",
    "pct_from_sma200": "vs 200-day",
    "dollar_volume": "Dollar volume",
}

COLUMN_KINDS = {
    "score": "score",
    "roc20": "pct",
    "roc60": "pct",
    "range_position": "ratio",
    "volume_expansion": "mult",
    "atr_pct": "pct_plain",
    "pct_from_sma20": "pct",
    "pct_from_sma50": "pct",
    "pct_from_sma200": "pct",
    # Its own kind: a dollar figure in the hundreds of millions needs compacting,
    # which none of the existing formatters do.
    "dollar_volume": "usd",
}


def catalogue() -> List[Dict[str, Any]]:
    """The scans on offer, without running any of them."""
    return [{"id": s["id"], "name": s["name"], "looks_for": s["looks_for"],
             "blind_spot": s["blind_spot"]} for s in SCANS]


def run(ranking: Optional[Dict[str, Any]], scan_id: str,
        limit: int = DEFAULT_LIMIT) -> Dict[str, Any]:
    """Apply one scan to a cached ranking."""
    scan = SCAN_BY_ID.get(scan_id)
    if not scan:
        return {"available": False, "reason": "No scan called {!r}.".format(scan_id)}

    rows = ((ranking or {}).get("ranked") or [])
    if not rows:
        return {"available": False, "id": scan_id, "name": scan["name"],
                "reason": ("The universe ranking has not been built yet. It is a scan "
                           "of roughly three thousand symbols, so it runs in the "
                           "background rather than on page load.")}

    ranked_at = _num((ranking or {}).get("ranked_at"))
    age_hours = ((time.time() - ranked_at) / 3600.0) if ranked_at else None
    stale = age_hours is not None and age_hours > STALE_AFTER_HOURS

    predicate: Optional[Callable[[Dict[str, Any]], bool]] = scan["filter"]
    hits = [r for r in rows if predicate is None or predicate(r)]
    hits.sort(key=scan["sort"])

    out_rows = []
    for r in hits[:limit]:
        row = {
            "symbol": r.get("symbol"),
            "price": _num(r.get("price")),
            "score": _num(r.get("score")),
        }
        for col in scan["columns"]:
            if col.startswith("pct_from_"):
                row[col] = _pct_from(r, col.replace("pct_from_", ""))
            else:
                row[col] = _num(r.get(col))
        out_rows.append(row)

    return {
        "available": True,
        "id": scan_id,
        "name": scan["name"],
        "looks_for": scan["looks_for"],
        "blind_spot": scan["blind_spot"],
        "columns": [{"key": c, "label": COLUMN_LABELS.get(c, c),
                     "kind": COLUMN_KINDS.get(c, "num")} for c in scan["columns"]],
        "rows": out_rows,
        "matched": len(hits),
        "considered": len(rows),
        "universe_size": (ranking or {}).get("universe_size"),
        "shown": len(out_rows),
        "age_hours": round(age_hours, 1) if age_hours is not None else None,
        "stale": stale,
        "gates": (ranking or {}).get("gates"),
        "method": (
            "Run over the {} names that cleared the screen's price, liquidity, "
            "history and volatility gates out of a {}-symbol universe, not over "
            "the whole market. Everything here is computed from daily price and "
            "volume alone: no options data, no fundamentals, no news and no "
            "earnings dates. A row is a candidate for a closer look on the Swing "
            "tab, never a conclusion.".format(
                len(rows), (ranking or {}).get("universe_size") or "large")
        ),
    }

# --------------------------------------------------------------- the groups
#
# Fourteen scans in one flat list is a menu nobody reads. Grouped by the question
# being asked instead, which is also how a reader arrives: "what moved", "what is
# trending", "where is the volume", "what is risky".
#
# Deliberately NOT here: premarket movers, short-squeeze watch, and any
# quality-or-growth screen. Those need premarket quotes, short interest per name,
# and fundamentals across the whole universe respectively — three data sets this
# terminal does not have at 700-name scale. Listing them as empty tabs would
# promise something the data cannot deliver.
SCAN_GROUPS: List[Dict[str, Any]] = [
    {
        "id": "movers",
        "name": "Market movers",
        "blurb": "Liquid names making meaningful moves, and who showed up for them.",
        "scans": ["movers", "gainers-volume", "decliners-volume"],
    },
    {
        "id": "momentum",
        "name": "Momentum leaders",
        "blurb": "Confirmed directional trend, and the extended end of it.",
        "scans": ["momentum", "breakout", "extended"],
    },
    {
        "id": "volume",
        "name": "Volume",
        "blurb": "Unusual participation versus its own normal, and where the money is.",
        "scans": ["volume", "volume-leaders"],
    },
    {
        "id": "structure",
        "name": "Trend structure",
        "blurb": "The shape of a trend rather than the size of a move.",
        "scans": ["pullback", "steady", "downtrend"],
    },
    {
        "id": "risk",
        "name": "High risk",
        "blurb": "Wide daily ranges, both directions. Sizing matters more than the setup.",
        "scans": ["high-risk-up", "high-risk-down"],
    },
]


def groups() -> List[Dict[str, Any]]:
    """The scan groups, each with its scans resolved to name and description."""
    by_id = {s["id"]: s for s in SCANS}
    out = []
    for g in SCAN_GROUPS:
        members = [by_id[i] for i in g["scans"] if i in by_id]
        out.append({
            "id": g["id"], "name": g["name"], "blurb": g["blurb"],
            "count": len(members),
            "scans": [{"id": m["id"], "name": m["name"], "looks_for": m["looks_for"]}
                      for m in members],
        })
    return out
