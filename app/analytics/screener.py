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

**Two fundamentals, from SEC (Handoff 8).** Revenue growth and the debt ratio come
from SEC's XBRL frames for every filer at once (app/analytics/sec_frames.py) and
are merged into the ranking's rows for a screen that asks for them. Each says its
period wherever it is shown. A bound can be peer-relative ("below the universe's
median debt ratio"), resolved over the stocks in this universe that report the
figure, and said with the value it came to and how many stocks it was taken over.
A result carries what it was run on: the bars' date, the fundamentals' periods,
the sources, and a fingerprint of the filters and the data, so the same screen on
the same data is recognisably the same list.
"""

from __future__ import annotations

import hashlib
import json
import statistics
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
    {"id": "chg1d", "label": "1-day change", "unit": "%", "decimals": 2,
     "get": _plain("chg1d"),
     "help": "Last close against the close before it. Delayed daily bars, so "
             "during the session this is yesterday's move until the day closes."},
    {"id": "off_high", "label": "Below the 3-month high", "unit": "%", "decimals": 1,
     "get": _plain("off_high"),
     "help": "Last close against the highest close of the last three months. "
             "0 is at the high; -10 is a 10% pullback from it."},
    {"id": "rally", "label": "Rally into the 3-month high", "unit": "%", "decimals": 1,
     "get": _plain("rally"),
     "help": "How far the price rose into that high, from the lowest close of "
             "the six months before it. With the field above, a pullback after "
             "a rally."},
    {"id": "pct_from_sma20", "label": "Distance from 20-day average", "unit": "%",
     "decimals": 2, "get": lambda r: _pct_from(r, "sma20"),
     "help": "Negative is below the average."},
    {"id": "pct_from_sma50", "label": "Distance from 50-day average", "unit": "%",
     "decimals": 2, "get": lambda r: _pct_from(r, "sma50"),
     "help": "Negative is below the average."},
    {"id": "pct_from_sma200", "label": "Distance from 200-day average", "unit": "%",
     "decimals": 2, "get": lambda r: _pct_from(r, "sma200"),
     "help": "Negative is below the average."},
    # Handoff 8: from SEC's filings, not the bars (sec_frames.py); the period is said with every value
    {"id": "revenue_growth", "label": "Revenue growth", "unit": "%", "decimals": 1, "family": "fundamental",
     "get": _plain("revenue_growth"),
     "help": "Revenue in the latest fiscal year SEC's frames hold against the year before, from the same XBRL tag "
             "for both. From the company's filings, so it is a year's figure, not this quarter's."},
    {"id": "debt_ratio", "label": "Debt ratio", "unit": "%", "decimals": 1,
     "family": "fundamental", "get": _plain("debt_ratio"),
     "help": "Total liabilities as a share of total assets on the latest balance sheet every filer has had time to "
             "file. Higher means more of the company is financed by what it owes."},
]
FUNDAMENTAL = {f["id"] for f in FIELDS if f.get("family") == "fundamental"}
PEER_BASES = ("median", "mean")

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


def parse_filters(raw: Any, ignored: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
    """Reader-supplied bounds, validated against FIELDS.

    Unknown ids are dropped rather than raising: a filter the server does not
    recognise is a stale tab, and losing the request entirely would be a worse
    answer than running the rest. The response reports what it used, and
    `ignored` collects what it did not and why: a dropped "P/E below 15" that
    nobody is told about returns the whole market as if it had been applied.
    """
    out: List[Dict[str, Any]] = []
    skip = ignored if ignored is not None else []
    if not isinstance(raw, list):
        return out
    for item in raw[:MAX_FILTERS]:
        if not isinstance(item, dict):
            continue
        name = str(item.get("field") or "")
        field = FIELD_BY_ID.get(name)
        if not field:
            skip.append({"field": name[:40], "reason": "not a field this screen has"})
            continue
        low, high = _num(item.get("min")), _num(item.get("max"))
        # a bound against the universe itself, "below the median" (Handoff 8): resolved when the screen runs
        peer_min = item.get("min_peer") if item.get("min_peer") in PEER_BASES else None
        peer_max = item.get("max_peer") if item.get("max_peer") in PEER_BASES else None
        if peer_min or peer_max:
            out.append({"field": field["id"], "min": None, "max": None, "min_peer": peer_min, "max_peer": peer_max})
            continue
        if low is None and high is None:
            # An empty bound is not a filter, and is said not to be one.
            skip.append({"field": field["id"], "label": field["label"],
                         "reason": "no minimum or maximum, so nothing to apply"})
            continue
        if low is not None and high is not None and low > high:
            low, high = high, low          # a reversed pair is a typo, not an error
        out.append(dict({"field": field["id"], "min": low, "max": high},
                        **({"min_exclusive": True} if item.get("min_exclusive") is True else {}),
                        **({"max_exclusive": True} if item.get("max_exclusive") is True else {})))
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


# The period each fundamental is for, said with it (Handoff 8)
PERIOD_WORDS = {"revenue_growth": "the latest fiscal year in SEC's filings against the year before",
                "debt_ratio": "total liabilities over total assets, on the latest balance sheet in SEC's filings"}


def _amount(field: Dict[str, Any], v: float) -> str:
    n = "{:,.{}f}".format(v, field.get("decimals", 2))
    if "." in n:
        n = n.rstrip("0").rstrip(".")
    n = n.replace("-", "\u2212")   # the true minus the pages print (static/v2/js/core/format.js num)
    unit = field.get("unit") or ""
    return "${}".format(n) if unit == "$" else "{}%".format(n) if unit == "%" else "{}\u00d7".format(n) if unit == "x" else n


def plain(spec: Dict[str, Any]) -> str:
    """One filter in plain English: "Revenue growth above 0% (the latest fiscal year ... against the year before)"."""
    field = FIELD_BY_ID.get(str(spec.get("field") or ""))
    if not field:
        return ""
    label, low, high = field["label"], spec.get("min"), spec.get("max")
    if spec.get("min_peer") or spec.get("max_peer"):
        side = "above" if spec.get("min_peer") else "below"
        said = "{} {} the universe's {}".format(label, side, spec.get("min_peer") or spec.get("max_peer"))
    elif low is not None and high is not None:
        said = "{} between {} and {}".format(label, _amount(field, low), _amount(field, high))
    elif low is not None:
        said = "{} {} {}".format(label, "above" if spec.get("min_exclusive") else "at least", _amount(field, low))
    elif high is not None:
        said = "{} {} {}".format(label, "below" if spec.get("max_exclusive") else "at most", _amount(field, high))
    else:
        said = label
    return "{} ({})".format(said, PERIOD_WORDS[field["id"]]) if field["id"] in PERIOD_WORDS else said


def describe() -> Dict[str, Any]:
    """The catalogue the UI is generated from."""
    return {
        "fields": [dict({k: v for k, v in f.items() if k != "get"}, family=f.get("family", "price")) for f in FIELDS],
        "peer_bases": list(PEER_BASES),
        "period_words": PERIOD_WORDS,
        "states": [{"id": s["id"], "label": s["label"]} for s in STATES],
        "max_filters": MAX_FILTERS,
        "blind_spot": BLIND,
    }


LOOSEN_KEEP = 5


def _loosen(field: Dict[str, Any], spec: Dict[str, Any], reached: List[Dict[str, Any]]) -> Dict[str, Any]:
    """The filter that left nothing (Handoff 8), and a looser bound worked out from the stocks that reached it: the
    value that would let LOOSEN_KEEP of them through this filter. Only proposed: the reader runs it, or not."""
    out = {"field": field["id"], "label": field["label"], "reached": len(reached), "said": plain(spec), "suggest": None}
    vals = sorted(v for v in (field["get"](r) for r in reached) if v is not None)
    if not vals:
        out["why"] = "none of the {} stocks that reached it has this figure".format(len(reached))
        return out
    k = min(LOOSEN_KEEP, len(vals))
    if spec.get("min") is not None and spec.get("max") is None:
        new = {"field": field["id"], "min": vals[-k], "max": None}
    elif spec.get("max") is not None and spec.get("min") is None:
        new = {"field": field["id"], "min": None, "max": vals[k - 1]}
    else:
        return out
    out.update(suggest=new, keeps=k, suggest_said=plain(new))
    return out


def needs_fundamentals(filters: Any, sort: str = "") -> bool:
    """Whether a screen asks for a figure from SEC's filings."""
    return sort in FUNDAMENTAL or any(isinstance(f, dict) and f.get("field") in FUNDAMENTAL for f in filters or [])


def fingerprint(used: List[Dict[str, Any]], states: List[str], sort: str, direction: str,
                data: Dict[str, Any]) -> str:
    """The same filters on the same data, as one short id: the screen's results are reproducible against it."""
    blob = json.dumps({"f": used, "s": sorted(states), "o": sort, "d": direction, "data": data}, sort_keys=True)
    return hashlib.sha1(blob.encode("utf-8")).hexdigest()[:10]


def run(ranking: Optional[Dict[str, Any]], filters: Any = None, states: Any = None,
        sort: str = "score", direction: str = "desc",
        limit: int = DEFAULT_LIMIT, fundamentals: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Apply reader-supplied bounds to the cached ranking (with SEC's two fundamentals merged in, when given)."""
    ignored: List[Dict[str, Any]] = []
    used = parse_filters(filters, ignored)
    used_states = parse_states(states)
    rows = ((ranking or {}).get("ranked") or [])
    fund = (fundamentals or {}).get("by_ticker") or {}
    if fund:
        rows = [dict(r, **fund.get(str(r.get("symbol") or "").upper(), {})) for r in rows]
    if not rows:
        return {
            "available": False,
            "reason": ("The universe ranking has not been built yet. It scores "
                       "roughly three thousand symbols, so it runs in the "
                       "background rather than on page load. Run a scan once and "
                       "this fills in."),
            "filters": used, "ignored": ignored, "states": used_states, "blind_spot": BLIND,
        }

    ranked_at = _num((ranking or {}).get("ranked_at"))
    age_hours = ((time.time() - ranked_at) / 3600.0) if ranked_at else None

    sort_field = FIELD_BY_ID.get(sort) or FIELD_BY_ID["score"]
    descending = str(direction).lower() != "asc"

    # The funnel, per filter, so an empty result says which bound emptied it
    # rather than only that nothing matched.
    # A peer bound is the statistic of the whole universe's values, said with the value and the count it came from
    peers: List[Dict[str, Any]] = []
    for spec in used:
        for side in ("min", "max"):
            basis = spec.get(side + "_peer")
            if not basis:
                continue
            field = FIELD_BY_ID[spec["field"]]
            values = [v for v in (field["get"](r) for r in rows) if v is not None]
            if not values:
                spec[side] = None
                peers.append({"field": field["id"], "label": field["label"], "side": side, "basis": basis,
                              "value": None, "of": 0})
                continue
            level = statistics.median(values) if basis == "median" else statistics.fmean(values)
            spec[side] = round(level, 6)            # the bound as worked out; said to two decimals below
            spec[side + "_exclusive"] = True       # "below the median" is strictly below it
            peers.append({"field": field["id"], "label": field["label"], "side": side, "basis": basis,
                          "value": round(level, 2), "of": len(values)})

    survivors = list(rows)
    funnel: List[Dict[str, Any]] = []
    binding: Optional[Dict[str, Any]] = None
    for spec in used:
        field = FIELD_BY_ID[spec["field"]]
        before = len(survivors)
        reached = survivors
        kept = []
        for row in survivors:
            value = field["get"](row)
            if value is None:
                continue                   # unmeasurable is not "passes"
            if spec["min"] is not None and (value <= spec["min"] if spec.get("min_exclusive") else value < spec["min"]):
                continue
            if spec["max"] is not None and (value >= spec["max"] if spec.get("max_exclusive") else value > spec["max"]):
                continue
            kept.append(row)
        survivors = kept
        if not kept and reached and binding is None:
            binding = _loosen(field, spec, reached)
        funnel.append({"field": field["id"], "label": field["label"],
                       "min": spec["min"], "max": spec["max"],
                       "before": before, "after": len(survivors),
                       # stocks this filter could not judge because they have no figure for it (said, not hidden)
                       "unmeasured": sum(1 for r in rows if field["get"](r) is None)})

    for key in used_states:
        state = STATE_BY_ID[key]
        before = len(survivors)
        survivors = [r for r in survivors if state["test"](r)]
        if not survivors and before and binding is None:
            binding = {"field": key, "label": state["label"], "reached": before, "said": state["label"], "suggest": None,
                       "why": "a condition without a bound to loosen: take it off to see what it removed"}
        funnel.append({"field": key, "label": state["label"],
                       "before": before, "after": len(survivors)})

    def sort_key(row: Dict[str, Any]) -> float:
        value = sort_field["get"](row)
        # Unmeasurable rows sink whichever way the sort runs, rather than
        # arriving at the top of an ascending sort as if they were the smallest.
        if value is None:
            return float("inf") if not descending else float("-inf")
        return value

    survivors.sort(key=lambda r: str(r.get("symbol") or ""))
    survivors.sort(key=sort_key, reverse=descending)   # stable: equal values keep the symbol order, every run

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

    # What the screen was run on: the bars' date, the fundamentals' periods, the sources, and the fingerprint
    ranked_bars = (ranking or {}).get("bars_through")
    fund_meta = None
    if fund:
        fund_meta = {"periods": (fundamentals or {}).get("periods"), "source": (fundamentals or {}).get("source"),
                     "built_at": (fundamentals or {}).get("built_at"), "coverage": (fundamentals or {}).get("coverage")}
    as_of = {"bars_through": ranked_bars, "ranked_at": ranked_at, "fundamentals": fund_meta}
    data_id = {"ranked_at": ranked_at, "bars_through": ranked_bars,
               "fundamentals": (fund_meta or {}).get("periods"), "fund_built": (fund_meta or {}).get("built_at")}
    return {
        "available": True,
        "rows": out_rows,
        "as_of": as_of,
        "sources": {"price": "Yahoo Finance daily bars, through Optic's ranking",
                    **({"fundamental": (fund_meta or {}).get("source")} if fund_meta else {})},
        "peers": peers,
        "binding": binding,
        "filters_said": [plain(f) for f in used] + [STATE_BY_ID[k]["label"] for k in used_states],
        "fingerprint": fingerprint(used, used_states, sort_field["id"], "desc" if descending else "asc", data_id),
        "symbols": [r.get("symbol") for r in survivors],
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
        "ignored": ignored,
        "states": used_states,
        "funnel": funnel,
        "sort": sort_field["id"],
        "direction": "desc" if descending else "asc",
        "limit": len(shown),
        "ranking_age_hours": round(age_hours, 1) if age_hours is not None else None,
        "stale": bool(age_hours is not None and age_hours > STALE_AFTER_HOURS),
        "blind_spot": BLIND,
    }
