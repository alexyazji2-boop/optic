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

Holidays and early closes ARE modelled, from the NYSE rules rather than a
hardcoded table. A per-year list is the obvious approach and it silently goes
wrong the first January nobody updates it — the module would keep answering
confidently with last year's calendar. Every one of the ten closures is a rule
("first Monday in September", "the Friday before Easter"), so the rules are
what is written down and any year can be computed.

Observance follows the exchange, not the federal calendar: a holiday landing on
Saturday is taken on the preceding Friday and one landing on Sunday on the
following Monday, with the documented exception that New Year's Day on a
Saturday closes nothing — the exchange does not reach back into December.

Early closes are 1:00pm, with after-hours to 5:00pm: the day after
Thanksgiving, Christmas Eve, and July 3rd when Independence Day falls on a
weekday.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
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
    "overnight": "The overnight session. Extremely thin, and this data feed does not carry it . "
                 "The price shown is the last print from the after-hours session, not a live "
                 "overnight quote.",
    "pre": "Pre-market trading. Volume builds toward the open, and levels set here often move "
           "again once the bell brings real liquidity.",
    "holiday": "A market holiday. US equities do not trade at all today, in any session, and "
               "the last price shown is the previous session's close.",
    "closed": "The market is shut for the weekend. Nothing trades until the overnight session "
              "reopens on Sunday evening.",
}


EARLY_REGULAR_END = 13 * 60        # 1:00pm on a half day
EARLY_AFTER_END = 17 * 60          # 5:00pm on a half day


def _easter(year: int) -> date:
    """Gregorian Easter Sunday. Needed only for Good Friday, the one closure
    that is not a fixed date or an nth-weekday rule."""
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    g = (8 * b + 13) // 25
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 19 * l) // 432
    month = (h + l - 7 * m + 90) // 25
    day = (h + l - 7 * m + 33 * month + 19) % 32
    return date(year, month, day)


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    """The nth given weekday of a month. n = -1 for the last one."""
    if n > 0:
        first = date(year, month, 1)
        offset = (weekday - first.weekday()) % 7
        return first + timedelta(days=offset + 7 * (n - 1))
    nxt = date(year + (month == 12), (month % 12) + 1, 1)
    last = nxt - timedelta(days=1)
    return last - timedelta(days=(last.weekday() - weekday) % 7)


def _observed(day: date) -> Optional[date]:
    """Shift a fixed-date holiday onto a trading day, exchange-style."""
    if day.weekday() == 5:              # Saturday -> the Friday before
        return day - timedelta(days=1)
    if day.weekday() == 6:              # Sunday -> the Monday after
        return day + timedelta(days=1)
    return day


def market_holidays(year: int) -> Dict[date, str]:
    """Every full NYSE/Nasdaq closure in a year, computed from the rules."""
    out: Dict[date, str] = {}

    # New Year's Day. The one case where a Saturday date closes nothing: the
    # exchange does not observe it on the preceding 31 December.
    ny = date(year, 1, 1)
    if ny.weekday() != 5:
        out[_observed(ny)] = "New Year's Day"

    out[_nth_weekday(year, 1, 0, 3)] = "Martin Luther King, Jr. Day"
    out[_nth_weekday(year, 2, 0, 3)] = "Washington's Birthday"
    out[_easter(year) - timedelta(days=2)] = "Good Friday"
    out[_nth_weekday(year, 5, 0, -1)] = "Memorial Day"
    # A market holiday only from 2022, when it became a federal holiday.
    if year >= 2022:
        out[_observed(date(year, 6, 19))] = "Juneteenth"
    out[_observed(date(year, 7, 4))] = "Independence Day"
    out[_nth_weekday(year, 9, 0, 1)] = "Labor Day"
    out[_nth_weekday(year, 11, 3, 4)] = "Thanksgiving Day"
    out[_observed(date(year, 12, 25))] = "Christmas Day"
    return out


def early_closes(year: int) -> Dict[date, str]:
    """Days the regular session ends at 1:00pm."""
    out: Dict[date, str] = {}
    out[_nth_weekday(year, 11, 3, 4) + timedelta(days=1)] = "the day after Thanksgiving"

    # July 3rd, but only when the 4th is itself a weekday. When the 4th falls on
    # a weekend the exchange shifts the full closure instead and there is no half
    # day at all.
    july4 = date(year, 7, 4)
    if july4.weekday() < 5:
        third = date(year, 7, 3)
        if third.weekday() < 5:
            out[third] = "the day before Independence Day"

    eve = date(year, 12, 24)
    if eve.weekday() < 5:
        out[eve] = "Christmas Eve"
    # A holiday closure outranks a half day: Christmas Eve on a Friday when the
    # 25th is a Saturday is the observed Christmas, fully shut.
    holidays = market_holidays(year)
    return {d: name for d, name in out.items() if d not in holidays}


def holiday_name(when: datetime) -> Optional[str]:
    """The closure covering this instant's Eastern date, if any."""
    return market_holidays(when.year).get(when.date())


def early_close_name(when: datetime) -> Optional[str]:
    return early_closes(when.year).get(when.date())


def _regular_end(when: datetime) -> int:
    return EARLY_REGULAR_END if early_close_name(when) else REGULAR_END


def _after_end(when: datetime) -> int:
    return EARLY_AFTER_END if early_close_name(when) else AFTER_END


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


def _closed_evening(when: datetime) -> bool:
    """After 8pm on the eve of a full closure.

    The overnight session runs from 8pm into the next morning, so it only exists
    if there is a next morning to run into. On the Sunday before a Monday
    holiday the strip would otherwise light Overnight at 8pm for a session that
    never opens.
    """
    if _minutes(when) < OVERNIGHT_START:
        return False
    nxt = (when + timedelta(days=1)).date()
    return nxt in market_holidays(nxt.year)


def _phase(when: datetime) -> str:
    # Checked before the clock. A holiday is closed at 10am as surely as at 3am,
    # and this is the case the module used to get wrong: on Labor Day it read the
    # clock, found 12:05pm, and reported a regular session in progress.
    if holiday_name(when):
        return "holiday"
    if _weekend(when) or _closed_evening(when):
        return "closed"
    minutes = _minutes(when)
    if minutes < OVERNIGHT_END:
        return "overnight"                                  # small hours
    if minutes < REGULAR_START:
        return "pre"
    if minutes < _regular_end(when):
        return "regular"
    if minutes < _after_end(when):
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
    "closed": "Weekend. Closed",
    "holiday": "Market holiday. Closed",
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

    holiday = holiday_name(when)
    early = early_close_name(when)
    return {
        "phase": phase,
        # The holiday's own name, so the strip reads "Labor Day" rather than
        # asking the reader to work out which one it is.
        "label": (f"{holiday}. Closed" if holiday else LABELS[phase]),
        "description": DESCRIPTIONS[phase],
        "is_regular": phase == "regular",
        "is_open": phase in ("regular", "after", "pre", "overnight"),
        "holiday": holiday,
        # Named whether or not it is in effect yet, because "the market shuts at
        # 1pm today" is worth knowing at 9:30am.
        "early_close": early,
        "early_close_note": (
            f"Half day for {early}: the regular session ends at 1:00pm ET and "
            "after-hours trading at 5:00pm."
        ) if early else None,
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
                "quote. The free feed doesn't carry the overnight tape. It's the most recent "
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
