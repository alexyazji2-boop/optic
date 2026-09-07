"""Relative Performance: where a symbol's return ranks against its peers.

Not the same thing as the relative-strength ratio line in extras.py, and the
difference is the whole point of having both. A ratio line answers "is this
beating SPY", which is one comparison against one index. RP answers "how many
of its peers is it beating", which is a rank: 97 means it has outrun 97% of the
universe over the window, and 4 means almost everything has outrun it.

The rank is what makes rotation legible. A stock up 3% in a month sounds dull
until you know the median name was down 4%, and a ratio against SPY will not
tell you that when SPY itself was flat.

Peers, not the index
--------------------
The universe is the 143 names behind the sector-fund holdings map in
stockmaps.py: liquid, balanced across all eleven sectors, and already fetched
in one batch elsewhere in this app. That balance matters more than size here.
Ranking against "the market" using a cap-weighted index means ranking against
whatever five megacaps are doing, and in 2024-2026 that produced a reading
about one sector wearing the name of the whole market.

It is a sample, and a small one. 143 names cannot resolve a percentile more
finely than about 0.7 points, so the output is rounded to whole numbers and the
thresholds below are deliberately coarse.

Thresholds
----------
95 and 5 mark the extremes. 80 and 20 are the crossing lines, because the
interesting moment is usually not the extreme itself but the entry into it: a
name crossing up through 80 is starting to lead, and one crossing down through
20 is starting to lag. Crosses are reported with the date and the direction.
"""

from __future__ import annotations

import threading
import time
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from .stockmaps import SECTOR_HOLDINGS

# Windows in trading days. 21 is about a month, 63 a quarter, 126 half a year.
# Two are charted at once, the way the reference does it, so a reader can see a
# short-window turn before the long window confirms it.
WINDOWS = {"1m": 21, "3m": 63, "6m": 126}
DEFAULT_FAST = "1m"
DEFAULT_SLOW = "3m"

TOP = 95.0
BOTTOM = 5.0
CROSS_UP = 80.0
CROSS_DOWN = 20.0

# One batch pull of 143 symbols is the expensive part; the ranks derived from it
# are cheap. Cached for the same 90 minutes the screener uses, because the
# universe's returns only matter to the nearest session.
_TTL = 90 * 60
_cache: Dict[str, Any] = {}
_lock = threading.RLock()


def universe() -> List[str]:
    """The peer set: every distinct holding across the mapped funds."""
    out = {h["symbol"] for rows in SECTOR_HOLDINGS.values() for h in rows}
    return sorted(out)


def _closes(provider, symbols: List[str], period: str = "1y") -> pd.DataFrame:
    frames = provider.batch_history(symbols, period=period, interval="1d")
    cols = {}
    for sym, df in (frames or {}).items():
        if df is None or df.empty or "Close" not in df:
            continue
        s = df["Close"].astype(float).dropna()
        if s.empty:
            continue
        s.index = pd.to_datetime(s.index).tz_localize(None)
        cols[sym] = s
    if not cols:
        return pd.DataFrame()
    return pd.DataFrame(cols).sort_index()


def _peer_closes(provider) -> pd.DataFrame:
    with _lock:
        hit = _cache.get("closes")
        if hit and (time.time() - hit["at"]) < _TTL:
            return hit["df"]
    df = _closes(provider, universe())
    with _lock:
        _cache["closes"] = {"at": time.time(), "df": df}
    return df


def _rolling_rank(target: pd.Series, peers: pd.DataFrame, window: int) -> pd.Series:
    """Percentile of the target's window return against the peers', per day.

    Returns are point-to-point over the window rather than cumulative daily
    products: the two agree, and the former survives a gap in one peer's history
    without poisoning every later value.
    """
    tgt_ret = target / target.shift(window) - 1.0
    peer_ret = peers / peers.shift(window) - 1.0
    # Align once, then compare row by row. `rank(pct=True)` on the combined row
    # is the definition of the percentile, and it handles ties the same way for
    # every day.
    joined = peer_ret.copy()
    joined["__target__"] = tgt_ret
    ranks = joined.rank(axis=1, pct=True, na_option="keep")["__target__"] * 100.0
    return ranks.dropna()


def _crosses(series: pd.Series) -> List[Dict[str, Any]]:
    """Where the rank moved through 80 upward or 20 downward.

    A true crossing only: the previous value must sit on the other side. A
    series that hovers on the line would otherwise report a cross every day it
    wobbled, which is the failure mode that makes threshold alerts useless.
    """
    out: List[Dict[str, Any]] = []
    prev = None
    for date, val in series.items():
        if prev is not None:
            if prev < CROSS_UP <= val:
                out.append({"date": str(date.date()), "level": CROSS_UP,
                            "direction": "up", "rank": round(float(val), 1)})
            elif prev > CROSS_DOWN >= val:
                out.append({"date": str(date.date()), "level": CROSS_DOWN,
                            "direction": "down", "rank": round(float(val), 1)})
        prev = val
    return out[-8:]


def _state(rank: Optional[float]) -> str:
    if rank is None:
        return "unknown"
    if rank >= TOP:
        return "leader"
    if rank <= BOTTOM:
        return "laggard"
    if rank >= CROSS_UP:
        return "outperforming"
    if rank <= CROSS_DOWN:
        return "underperforming"
    return "in line"


def analyse(provider, ticker: str, fast: str = DEFAULT_FAST,
            slow: str = DEFAULT_SLOW) -> Dict[str, Any]:
    """RP for one symbol: two windows, their history, and any recent crosses."""
    sym = (ticker or "").strip().upper()
    if not sym:
        return {"available": False, "reason": "No symbol given."}

    peers = _peer_closes(provider)
    if peers.empty:
        return {"available": False,
                "reason": "Peer history unavailable, so there is nothing to rank against."}

    if sym in peers.columns:
        target = peers[sym].dropna()
        # A symbol cannot be its own peer: leaving it in the comparison set
        # shifts every rank by one place and guarantees it never reads 100.
        peer_frame = peers.drop(columns=[sym])
    else:
        got = _closes(provider, [sym])
        if got.empty:
            return {"available": False, "reason": "No history for {}.".format(sym)}
        target = got[sym].dropna()
        peer_frame = peers

    out: Dict[str, Any] = {"available": True, "ticker": sym,
                           "universe_size": int(peer_frame.shape[1]),
                           "windows": {}}
    for key in (fast, slow):
        window = WINDOWS.get(key)
        if not window:
            continue
        ranks = _rolling_rank(target, peer_frame, window)
        if ranks.empty:
            out["windows"][key] = {"available": False,
                                   "reason": "Not enough overlapping history."}
            continue
        latest = float(ranks.iloc[-1])
        prior = float(ranks.iloc[-2]) if len(ranks) > 1 else latest
        tail = ranks.tail(252)
        out["windows"][key] = {
            "available": True,
            "window_days": window,
            "rank": round(latest, 1),
            "change": round(latest - prior, 1),
            "state": _state(latest),
            "dates": [str(d.date()) for d in tail.index],
            "series": [round(float(v), 1) for v in tail.values],
            "crosses": _crosses(tail),
        }

    fast_block = out["windows"].get(fast) or {}
    out["headline"] = _headline(sym, fast_block, out["windows"].get(slow) or {})
    out["method"] = (
        "Percentile rank of the {}-day return against {} liquid peers balanced "
        "across the eleven sectors, not against a cap-weighted index. 97 means "
        "it outran 97% of them. A sample this size resolves to about 0.7 of a "
        "point, so ranks are whole numbers."
        .format(WINDOWS.get(fast, 21), int(peer_frame.shape[1])))
    return out


def _headline(sym: str, fast: Dict[str, Any], slow: Dict[str, Any]) -> str:
    if not fast.get("available"):
        return "{}: not enough history to rank.".format(sym)
    r = fast["rank"]
    s = slow.get("rank")
    lead = "{} ranks {:.0f} of 100 against its peers over {} days".format(
        sym, r, fast["window_days"])
    if s is None:
        return lead + "."
    # The divergence is the signal worth stating: a short window ahead of a long
    # one is a turn, the reverse is fading leadership.
    gap = r - s
    if gap >= 15:
        return lead + ", well above its {:.0f} over the longer window. Turning up.".format(s)
    if gap <= -15:
        return lead + ", below its {:.0f} over the longer window. Leadership fading.".format(s)
    return lead + ", broadly in line with its {:.0f} over the longer window.".format(s)


def scan(provider, kind: str = "leaders", limit: int = 20) -> Dict[str, Any]:
    """The four scans the reference ships: top, bottom, and the two crosses."""
    peers = _peer_closes(provider)
    if peers.empty:
        return {"available": False, "reason": "Peer history unavailable."}

    window = WINDOWS[DEFAULT_FAST]
    ret = peers / peers.shift(window) - 1.0
    ranks = ret.rank(axis=1, pct=True, na_option="keep") * 100.0
    if ranks.empty or len(ranks) < 2:
        return {"available": False, "reason": "Not enough history to rank."}

    latest, prior = ranks.iloc[-1], ranks.iloc[-2]
    rows: List[Dict[str, Any]] = []
    for sym in ranks.columns:
        now, was = latest.get(sym), prior.get(sym)
        if now is None or (isinstance(now, float) and np.isnan(now)):
            continue
        hit = False
        if kind == "leaders":
            hit = now >= TOP
        elif kind == "laggards":
            hit = now <= BOTTOM
        elif kind == "cross_up":
            hit = was is not None and was < CROSS_UP <= now
        elif kind == "cross_down":
            hit = was is not None and was > CROSS_DOWN >= now
        if hit:
            rows.append({"symbol": sym, "rank": round(float(now), 1),
                         "prior": round(float(was), 1) if was is not None else None,
                         "state": _state(float(now))})
    rows.sort(key=lambda r: r["rank"], reverse=(kind != "laggards"))
    return {
        "available": True, "kind": kind, "rows": rows[:limit],
        "universe_size": int(ranks.shape[1]),
        "as_of": str(ranks.index[-1].date()),
        "caveat": ("Ranked within a 143-name liquid universe balanced across the "
                   "sectors, not the whole market. A name absent from that list "
                   "cannot appear here however it is performing."),
    }


# ------------------------------------------------------ scan-tab integration
#
# These four appear on the Scan tab beside the screener's own scans, and they
# do NOT run over the same thing. The screener's scans filter a cached ranking
# of roughly three thousand symbols; these rank 143. Presenting them under the
# same "names that cleared the screen's gates" copy would be a quiet lie about
# what was searched, so each carries its own method line and the group blurb
# says so on the card.
SCAN_DEFS = [
    {
        "id": "rp-leaders",
        "kind": "leaders",
        "name": "RP > 95",
        "looks_for": "Names in the top 5% of their peer group by 21-day return. A rank, "
                     "not a return: 97 means it outran 97% of the peer set, which is a "
                     "different claim from being up a lot.",
        "blind_spot": "A rank says nothing about why, or about valuation, and the top of "
                      "a rank distribution is where crowded trades live. It is also "
                      "backward-looking by exactly one window.",
    },
    {
        "id": "rp-laggards",
        "kind": "laggards",
        "name": "RP < 5",
        "looks_for": "The weakest 5% of the peer group over 21 days. Useful as the short "
                     "side of a pair, or as a list of what a rotation is leaving behind.",
        "blind_spot": "Cheap and weak are not the same thing, and a name can sit at the "
                      "bottom of this list for a year. Nothing here indicates a turn.",
    },
    {
        "id": "rp-cross-up",
        "kind": "cross_up",
        "name": "RP 80 cross",
        "looks_for": "Crossed up through the 80th percentile since the previous session. "
                     "The entry into leadership rather than the leadership itself, which "
                     "is usually the part worth catching.",
        "blind_spot": "One session's crossing. A name that oscillates around 80 will "
                      "appear repeatedly without anything having changed.",
    },
    {
        "id": "rp-cross-down",
        "kind": "cross_down",
        "name": "RP 20 cross",
        "looks_for": "Crossed down through the 20th percentile since the previous "
                     "session. Leadership fading, or a name entering the weak tail.",
        "blind_spot": "Same as the upward cross: a single session's transition, and a "
                      "name hovering on the line reappears without news.",
    },
]

SCAN_GROUP = {
    "id": "relperf",
    "name": "Relative performance",
    "blurb": "Ranked within 143 liquid names balanced across the sectors, not the "
             "screener's universe.",
    "scans": [d["id"] for d in SCAN_DEFS],
}

COLUMNS = [
    {"key": "rank", "label": "RP rank", "kind": "num"},
    {"key": "prior", "label": "Prior", "kind": "num"},
    {"key": "state", "label": "State", "kind": "text"},
]


def scan_by_id(scan_id: str) -> Optional[Dict[str, Any]]:
    for d in SCAN_DEFS:
        if d["id"] == scan_id:
            return d
    return None


def run_scan(provider, scan_id: str, limit: int = 20) -> Dict[str, Any]:
    """One RP scan, shaped like a screener scan so the Scan tab renders it."""
    spec = scan_by_id(scan_id)
    if not spec:
        return {"available": False, "reason": "No scan called {!r}.".format(scan_id)}
    res = scan(provider, spec["kind"], limit=limit)
    if not res.get("available"):
        return {"available": False, "id": scan_id, "name": spec["name"],
                "reason": res.get("reason", "Unavailable.")}
    return {
        "available": True,
        "id": scan_id,
        "name": spec["name"],
        "looks_for": spec["looks_for"],
        "blind_spot": spec["blind_spot"],
        "columns": COLUMNS,
        "rows": res["rows"],
        "matched": len(res["rows"]),
        "considered": res["universe_size"],
        "universe_size": res["universe_size"],
        "shown": len(res["rows"]),
        "stale": False,
        "method": (
            "Percentile rank of the 21-day return within {} liquid names balanced "
            "across the eleven sectors. This is NOT the screener's universe: a "
            "symbol outside that peer set cannot appear here however it is "
            "performing. As of {}."
            .format(res["universe_size"], res.get("as_of", "the last session"))),
    }
