"""Free-form screening over the ranking the scanners already share.

The terminal had thirteen curated screens and no way to ask a question that was
not one of them. This is that: a reader picks fields, sets bounds, and gets the
names that clear them.

**It runs over the cached ranking and never builds one.** `screen.run` downloads
and scores roughly three thousand symbols; that is a background job measured in
minutes, and a screener that triggered it would be a page that hangs. So this is
a filter and a sort over rows that already exist, exactly as `scanners.run` is.
With no ranking on disk it says so and points at the thing that builds one,
rather than returning an empty result that reads as "nothing matches".

**The field list is published, not duplicated.** `app/analytics/watches.py` has
the same shape and CLAUDE.md records why: three watch conditions once compared a
stored parameter against a vocabulary produced elsewhere in the app, stored
fine, evaluated fine and never fired. The UI here is generated from FIELDS, so
there is one spelling of every id and one set of bounds.

**What it cannot see.** The ranking is a price-and-volume prefilter. There are no
fundamentals in it, no options positioning, no news and no sector. A screen for
"cheap profitable companies" cannot be expressed here and the endpoint says so
rather than quietly screening on something else.
"""

from __future__ import annotations

import time
from typing import Any, Callable, Dict, List, Optional

# Anything older than this is still served, and still labelled. A ranking from
# yesterday is a usable prefilter; one presented as today's is a lie.
STALE_AFTER_HOURS = 18.0

DEFAULT_LIMIT = 50
MAX_FILTERS = 8


def _pct_from(row: Dict[str, Any], key: str) -> Optional[float]:
    """Distance from a moving average, in percent. None when either side is."""
    price = row.get("price")
    level = row.get(key)
    if price is None or not level:
        return None
    try:
        return round((float(price) / float(level) - 1.0) * 100.0, 2)
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def _plain(key: str) -> Callable[[Dict[str, Any]], Optional[float]]:
    def get(row: Dict[str, Any]) -> Optional[float]:
        value = row.get(key)
        try:
            return None if value is None else float(value)
        except (TypeError, ValueError):
            return None
    return get


def _scaled(key: str, factor: float) -> Callable[[Dict[str, Any]], Optional[float]]:
    inner = _plain(key)

    def get(row: Dict[str, Any]) -> Optional[float]:
        value = inner(row)
        return None if value is None else round(value * factor, 2)
    return get


# The vocabulary. `id` is what crosses the wire; nothing else in the app spells
# these, because the UI is generated from this list.
FIELDS: List[Dict[str, Any]] = [
    {"id": "price", "label": "Price", "unit": "$", "decimals": 2,
     "get": _plain("price"),
     "help": "Last close."},
    {"id": "dollar_volume", "label": "Dollar volume", "unit": "$", "decimals": 0,
     "get": _plain("dollar_volume"),
     "help": "Twenty-day average of price times volume. The liquidity floor for "
             "the ranking itself is already applied before this."},
    {"id": "roc20", "label": "1-month return", "unit": "%", "decimals": 1,
     "get": _plain("roc20"),
     "help": "Close against the close 21 sessions ago."},
    {"id": "roc60", "label": "3-month return", "unit": "%", "decimals": 1,
     "get": _plain("roc60"),
     "help": "Close against the close 61 sessions ago. The single number the "
             "composite score does not beat, which is why it is offered plainly."},
    {"id": "range_position", "label": "Position in 52-week range", "unit": "%",
     "decimals": 0, "get": _scaled("range_position", 100.0),
     "help": "0% sits on the 52-week low, 100% on the high."},
    {"id": "atr_pct", "label": "Daily range (ATR)", "unit": "%", "decimals": 2,
     "get": _plain("atr_pct"),
     "help": "Average true range over 14 days, as a percentage of price. How "
             "much this name moves on an ordinary day."},
    {"id": "volume_expansion", "label": "Volume vs 3-month average", "unit": "x",
     "decimals": 2, "get": _plain("volume_expansion"),
     "help": "Twenty-day average volume over sixty-day. Above 1 is participation."},
    {"id": "score", "label": "Trend score", "unit": "", "decimals": 1,
     "get": _plain("score"),
     "help": "The ranking's own signed trend and momentum score. Its weights are "
             "judgement rather than a fit, and the scan panel breaks them out."},
    {"id": "pct_from_sma20", "label": "Distance from 20-day average", "unit": "%",
     "decimals": 2, "get": lambda r: _pct_from(r, "sma20"),
     "help": "Negative is below the average."},
    {"id": "pct_from_sma50", "label": "Distance from 50-day average", "unit": "%",
     "decimals": 2, "get": lambda r: _pct_from(r, "sma50"),
     "help": "Negative is below the average."},
    {"id": "pct_from_sma200", "label": "Distance from 200-day average", "unit": "%",
     "decimals": 2, "get": lambda r: _pct_from(r, "sma200"),
     "help": "Negative is below the average."},
]

FIELD_BY_ID = {f["id"]: f for f in FIELDS}

# Two-state filters, which a min/max cannot express: "is the 50 above the 200"
# is a relationship, not a bound.
STATES: List[Dict[str, Any]] = [
    {"id": "above_sma200", "label": "Above its 200-day average",
     "test": lambda r: (r.get("sma200") is not None and r.get("price") is not None
                        and float(r["price"]) > float(r["sma200"]))},
    {"id": "above_sma50", "label": "Above its 50-day average",
     "test": lambda r: (r.get("sma50") is not None and r.get("price") is not None
                        and float(r["price"]) > float(r["sma50"]))},
    {"id": "golden", "label": "50-day average above the 200-day",
     "test": lambda r: (r.get("sma50") is not None and r.get("sma200") is not None
                        and float(r["sma50"]) > float(r["sma200"]))},
]

STATE_BY_ID = {s["id"]: s for s in STATES}

# What this screen provably cannot ask about, named rather than left to be
# discovered. Every panel in this app states what it cannot tell you.
BLIND = ("No fundamentals, no options positioning, no news and no sector: the "
         "ranking behind this is a price-and-volume prefilter over daily bars. "
         "A screen for cheap, profitable or heavily shorted companies cannot be "
         "expressed here, and guessing at one from price would be worse than "
         "saying so.")


def _num(value: Any) -> Optional[float]:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if out == out and out not in (float("inf"), float("-inf")) else None


def parse_filters(raw: Any) -> List[Dict[str, Any]]:
    """Reader-supplied bounds, validated against FIELDS.

    Unknown ids are dropped rather than raising: a filter the server does not
    recognise is a stale tab, and losing the request entirely would be a worse
    answer than running the rest. The response reports what it used.
    """
    out: List[Dict[str, Any]] = []
    if not isinstance(raw, list):
        return out
    for item in raw[:MAX_FILTERS]:
        if not isinstance(item, dict):
            continue
        field = FIELD_BY_ID.get(str(item.get("field") or ""))
        if not field:
            continue
        low, high = _num(item.get("min")), _num(item.get("max"))
        if low is None and high is None:
            continue                       # an empty bound is not a filter
        if low is not None and high is not None and low > high:
            low, high = high, low          # a reversed pair is a typo, not an error
        out.append({"field": field["id"], "min": low, "max": high})
    return out


def parse_states(raw: Any) -> List[str]:
    if not isinstance(raw, list):
        return []
    seen: List[str] = []
    for item in raw[:len(STATES)]:
        key = str(item)
        if key in STATE_BY_ID and key not in seen:
            seen.append(key)
    return seen


def describe() -> Dict[str, Any]:
    """The catalogue the UI is generated from."""
    return {
        "fields": [{k: v for k, v in f.items() if k != "get"} for f in FIELDS],
        "states": [{"id": s["id"], "label": s["label"]} for s in STATES],
        "max_filters": MAX_FILTERS,
        "blind_spot": BLIND,
    }


def run(ranking: Optional[Dict[str, Any]], filters: Any = None, states: Any = None,
        sort: str = "score", direction: str = "desc",
        limit: int = DEFAULT_LIMIT) -> Dict[str, Any]:
    """Apply reader-supplied bounds to the cached ranking."""
    used = parse_filters(filters)
    used_states = parse_states(states)
    rows = ((ranking or {}).get("ranked") or [])
    if not rows:
        return {
            "available": False,
            "reason": ("The universe ranking has not been built yet. It scores "
                       "roughly three thousand symbols, so it runs in the "
                       "background rather than on page load. Run a scan once and "
                       "this fills in."),
            "filters": used, "states": used_states, "blind_spot": BLIND,
        }

    ranked_at = _num((ranking or {}).get("ranked_at"))
    age_hours = ((time.time() - ranked_at) / 3600.0) if ranked_at else None

    sort_field = FIELD_BY_ID.get(sort) or FIELD_BY_ID["score"]
    descending = str(direction).lower() != "asc"

    # The funnel, per filter, so an empty result says which bound emptied it
    # rather than only that nothing matched.
    survivors = list(rows)
    funnel: List[Dict[str, Any]] = []
    for spec in used:
        field = FIELD_BY_ID[spec["field"]]
        before = len(survivors)
        kept = []
        for row in survivors:
            value = field["get"](row)
            if value is None:
                continue                   # unmeasurable is not "passes"
            if spec["min"] is not None and value < spec["min"]:
                continue
            if spec["max"] is not None and value > spec["max"]:
                continue
            kept.append(row)
        survivors = kept
        funnel.append({"field": field["id"], "label": field["label"],
                       "min": spec["min"], "max": spec["max"],
                       "before": before, "after": len(survivors)})

    for key in used_states:
        state = STATE_BY_ID[key]
        before = len(survivors)
        survivors = [r for r in survivors if state["test"](r)]
        funnel.append({"field": key, "label": state["label"],
                       "before": before, "after": len(survivors)})

    def sort_key(row: Dict[str, Any]) -> float:
        value = sort_field["get"](row)
        # Unmeasurable rows sink whichever way the sort runs, rather than
        # arriving at the top of an ascending sort as if they were the smallest.
        if value is None:
            return float("inf") if not descending else float("-inf")
        return value

    survivors.sort(key=sort_key, reverse=descending)

    shown = survivors[:max(1, min(int(limit or DEFAULT_LIMIT), 200))]
    columns = [sort_field["id"]] + [f["field"] for f in used if f["field"] != sort_field["id"]]
    # Always worth seeing beside a screen, whatever was filtered on.
    for extra in ("price", "roc20", "score"):
        if extra not in columns:
            columns.append(extra)

    out_rows = []
    for row in shown:
        cell = {"symbol": row.get("symbol")}
        for col in columns:
            cell[col] = FIELD_BY_ID[col]["get"](row)
        out_rows.append(cell)

    return {
        "available": True,
        "rows": out_rows,
        "columns": [{"id": c, "label": FIELD_BY_ID[c]["label"],
                     "unit": FIELD_BY_ID[c]["unit"],
                     "decimals": FIELD_BY_ID[c]["decimals"]} for c in columns],
        "matched": len(survivors),
        "considered": len(rows),
        # The key is `universe_size`; `universe` returned None and the panel
        # would have said "of null symbols". The gates are carried too, because
        # the biggest cut here is one the reader never set: 1,930 of 2,951 names
        # are dropped as illiquid before any filter of theirs runs.
        "universe": (ranking or {}).get("universe_size"),
        "prefiltered": (ranking or {}).get("passed"),
        "gates": (ranking or {}).get("gates") or {},
        "filters": used,
        "states": used_states,
        "funnel": funnel,
        "sort": sort_field["id"],
        "direction": "desc" if descending else "asc",
        "limit": len(shown),
        "ranking_age_hours": round(age_hours, 1) if age_hours is not None else None,
        "stale": bool(age_hours is not None and age_hours > STALE_AFTER_HOURS),
        "blind_spot": BLIND,
    }
