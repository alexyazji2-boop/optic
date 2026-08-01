"""US equity trading sessions.

A price means different things at different hours, and "the market is closed"
covers four very different states. Between the 4pm bell and the next 9:30am open
a stock can trade in three separate venues, on wildly different liquidity, and a
quote from any of them looks identical in a JSON payload.

The phases, all in New York time:

* **Regular** 9:30am–4:00pm — the session everything else is measured against.
* **After hours** 4:00pm–8:00pm — where earnings reactions actually happen.
* **Overnight** 8:00pm–4:00am — thin, and *not carried by this data feed*
  (yfinance has no Blue Ocean / overnight tape), so the module says so rather
  than passing off an 8pm print as a current price.
* **Pre-market** 4:00am–9:30am — liquidity builds toward the open.

Holidays aren't modelled. On a market holiday the feed simply repeats the prior
close, so a caller sees an unchanged price rather than a wrong one — but this
module will still call it a regular session, which is the one case where it
knowingly overstates what's happening.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")

OVERNIGHT_START = 20 * 60          # 8:00pm
OVERNIGHT_END = 4 * 60             # 4:00am (next day)
PRE_START = 4 * 60                 # 4:00am
REGULAR_START = 9 * 60 + 30        # 9:30am
REGULAR_END = 16 * 60             # 4:00pm
AFTER_END = 20 * 60                # 8:00pm

# The strip the UI draws, laid out across one 24-hour clock. The overnight session
# is split in two because it straddles midnight: leaving out the 00:00–04:00 half
# left a dead band on the left of the strip and put the "now" marker outside any
# highlighted segment for the four hours after midnight.
SEGMENTS = [
    {"phase": "overnight", "label": "Overnight", "start": 0, "end": OVERNIGHT_END},
    {"phase": "pre", "label": "Pre-market", "start": PRE_START, "end": REGULAR_START},
    {"phase": "regular", "label": "Regular", "start": REGULAR_START, "end": REGULAR_END},
    {"phase": "after", "label": "After hours", "start": REGULAR_END, "end": AFTER_END},
    {"phase": "overnight", "label": "Overnight", "start": OVERNIGHT_START, "end": 24 * 60},
]

DESCRIPTIONS = {
    "regular": "The main session. Liquidity is deepest here, and this is the close every "
               "other price gets compared against.",
    "after": "Post-market trading. This is where a company that reports after the bell gets "
             "its first verdict, on a fraction of regular-session volume.",
    "overnight": "The overnight session. Extremely thin, and this data feed does not carry it — "
                 "the price shown is the last print from the after-hours session, not a live "
                 "overnight quote.",
    "pre": "Pre-market trading. Volume builds toward the open, and levels set here often move "
           "again once the bell brings real liquidity.",
    "closed": "The market is shut for the weekend. Nothing trades until the overnight session "
              "reopens on Sunday evening.",
}


def _minutes(when: datetime) -> int:
    return when.hour * 60 + when.minute


def _weekend(when: datetime) -> bool:
    """Saturday, plus the gap between Friday's 8pm close and Sunday's 8pm reopen."""
    weekday = when.weekday()          # Mon=0 .. Sun=6
    minutes = _minutes(when)
    if weekday == 5:                                        # Saturday
        return True
    if weekday == 4 and minutes >= AFTER_END:               # Friday after 8pm
        return True
    if weekday == 6 and minutes < OVERNIGHT_START:          # Sunday before 8pm
        return True
    return False


def _phase(when: datetime) -> str:
    if _weekend(when):
        return "closed"
    minutes = _minutes(when)
    if minutes < OVERNIGHT_END:
        return "overnight"                                  # small hours
    if minutes < REGULAR_START:
        return "pre"
    if minutes < REGULAR_END:
        return "regular"
    if minutes < AFTER_END:
        return "after"
    return "overnight"


def _at(when: datetime, minutes: int, day_offset: int = 0) -> datetime:
    base = (when + timedelta(days=day_offset)).replace(
        hour=0, minute=0, second=0, microsecond=0)
    return base + timedelta(minutes=minutes)


def _next_change(when: datetime) -> Dict[str, Any]:
    """When the current phase ends and what follows. Walks forward in minutes
    rather than reasoning about cases, which is slower and much harder to get
    wrong around midnight and the weekend."""
    current = _phase(when)
    probe = when.replace(second=0, microsecond=0)
    for _ in range(60 * 24 * 4):                            # up to four days out
        probe += timedelta(minutes=1)
        nxt = _phase(probe)
        if nxt != current:
            return {
                "phase": nxt,
                "label": LABELS[nxt],
                "starts_at": probe.isoformat(),
                "minutes_away": int((probe - when).total_seconds() // 60),
            }
    return {}


LABELS = {
    "regular": "Regular session",
    "after": "After hours",
    "overnight": "Overnight",
    "pre": "Pre-market",
    "closed": "Weekend — closed",
}


def state(now: Optional[datetime] = None) -> Dict[str, Any]:
    """The current session, what's next, and the strip the UI draws."""
    when = (now or datetime.now(timezone.utc)).astimezone(ET)
    phase = _phase(when)

    segments: List[Dict[str, Any]] = []
    for seg in SEGMENTS:
        # Absolute timestamps as well as ET clock minutes. Market hours are defined
        # in New York time and always will be, but a reader in London or Mumbai
        # needs to know when that is for *them* — and converting a bare "9:30am"
        # client-side means reimplementing US daylight-saving rules in JavaScript.
        # An ISO instant with its offset converts correctly anywhere.
        starts = _at(when, min(seg["start"], 24 * 60 - 1))
        ends = _at(when, min(seg["end"], 24 * 60 - 1))
        segments.append({
            **seg,
            "active": seg["phase"] == phase,
            # Fraction of the 24h strip, so the UI doesn't repeat the arithmetic.
            "start_pct": round(seg["start"] / (24 * 60) * 100, 2),
            "width_pct": round((seg["end"] - seg["start"]) / (24 * 60) * 100, 2),
            "start_at": starts.isoformat(),
            "end_at": ends.isoformat(),
        })

    return {
        "phase": phase,
        "label": LABELS[phase],
        "description": DESCRIPTIONS[phase],
        "is_regular": phase == "regular",
        "is_open": phase in ("regular", "after", "pre", "overnight"),
        "now_et": when.isoformat(),
        "now_et_label": when.strftime("%-I:%M %p"),
        "weekday": when.strftime("%a"),
        "timezone": "America/New_York (ET)",
        "timezone_label": "ET",
        # Stated outright because every hour in this payload is an Eastern time.
        # A visitor in another zone reading "9:30am" would otherwise reasonably
        # assume it meant 9:30am where they are.
        "clock_note": (
            "US market hours are defined in Eastern Time. Times here are converted to your "
            "selected zone; the ET equivalent is shown alongside."
        ),
        "day_pct": round(_minutes(when) / (24 * 60) * 100, 2),
        "segments": segments,
        "next": _next_change(when),
        # The one thing a reader has to know before trusting an off-hours price.
        "feed_covers_phase": phase != "overnight",
    }


def price_view(quote: Dict[str, Any], now: Optional[datetime] = None) -> Dict[str, Any]:
    """Close versus current, labelled by which session each came from.

    The pairing is the point: outside regular hours, one number is the settled
    close everyone quotes and the other is where it's actually trading. Showing
    only one of them is how an after-hours gap goes unnoticed.
    """
    sess = state(now)
    phase = sess["phase"]

    regular_close = quote.get("price")
    post_pct = quote.get("post_market_change_pct")
    pre_pct = quote.get("pre_market_change_pct")

    extended: Optional[Dict[str, Any]] = None
    if pre_pct is not None and phase == "pre":
        extended = {"kind": "pre-market", "price": quote.get("pre_market_price"),
                    "change_pct": pre_pct, "as_of": quote.get("pre_market_time")}
    elif post_pct is not None:
        extended = {"kind": "after hours", "price": quote.get("post_market_price"),
                    "change_pct": post_pct, "as_of": quote.get("post_market_time")}
    elif pre_pct is not None:
        extended = {"kind": "pre-market", "price": quote.get("pre_market_price"),
                    "change_pct": pre_pct, "as_of": quote.get("pre_market_time")}

    out: Dict[str, Any] = {
        "phase": phase,
        "phase_label": sess["label"],
        "regular_close": regular_close,
        "regular_close_label": "last close" if phase != "regular" else "current",
        "regular_change_pct": quote.get("change_pct"),
        "extended": extended,
        "current": regular_close,
        "current_kind": "regular session",
        "change_from_close_pct": None,
    }

    if phase != "regular" and extended and extended.get("price"):
        out["current"] = extended["price"]
        out["current_kind"] = extended["kind"]
        out["change_from_close_pct"] = extended["change_pct"]

        # An overnight or weekend request gets the last after-hours print, hours or
        # days old. Calling that "current" without the qualifier is the whole
        # thing this function exists to prevent.
        if phase == "overnight":
            out["stale_note"] = (
                "This is the last print from the after-hours session, not a live overnight "
                "quote — the free feed doesn't carry the overnight tape. It's the most recent "
                "price that exists here, and it may be several hours old."
            )
        elif phase == "closed":
            out["stale_note"] = (
                "The market is closed for the weekend, so this is Friday's final "
                "extended-hours print. Nothing has traded since, and it won't change until the "
                "overnight session reopens on Sunday evening."
            )
        elif phase == "pre" and extended["kind"] == "after hours":
            out["stale_note"] = (
                "No pre-market print yet, so this is the last after-hours price from "
                "yesterday evening."
            )

    elif phase == "closed":
        out["stale_note"] = (
            "The market is closed for the weekend. This is Friday's closing price and it "
            "won't change until the overnight session reopens Sunday evening."
        )

    return out
