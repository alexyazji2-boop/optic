"""Market Catalyst Mode: the release that just moved the tape, and how it moved it.

When a major number prints, the useful view is not the calendar row — it is what
the number was, what the tape did in the hours after, and which assets moved
together. This assembles that.

**There is no consensus column, and that is not an oversight.** A "consensus vs
actual" panel needs surveyed analyst estimates, which are a licensed product.
Every free copy is somebody's paid feed republished, usually undated. A consensus
figure that is quietly a week stale, sitting next to a real actual, produces a
"surprise" that is pure fiction — and a surprise is exactly the number a reader
would act on. So this shows what can be sourced: the release in the agency's own
words, and the market reaction computed from prices. If a consensus feed is ever
licensed, the field is here to fill.

The market reaction IS real and is the point. Cross-asset moves on the session of
a release are computed from bars: equities, duration, the dollar, gold, oil. That
is observation, not inference, and it is the half of the reference screenshot
that can be built honestly.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

from . import events, feeds

ET = ZoneInfo("America/New_York")
log = logging.getLogger(__name__)

# The cross-asset board. Each one answers a different question about the same
# print, which is why the set is fixed rather than configurable: equities for
# risk appetite, TLT for the rate path, UUP for the dollar, GLD and USO for the
# inflation/real-asset leg, HYG for credit.
REACTION_ASSETS = [
    {"symbol": "SPY", "name": "S&P 500", "reads": "broad risk appetite"},
    {"symbol": "QQQ", "name": "Nasdaq 100", "reads": "long-duration growth"},
    {"symbol": "IWM", "name": "Russell 2000", "reads": "domestic and cyclical exposure"},
    {"symbol": "TLT", "name": "20+ year Treasuries", "reads": "the rate path"},
    {"symbol": "UUP", "name": "US Dollar index fund", "reads": "the dollar"},
    {"symbol": "GLD", "name": "Gold", "reads": "real assets and hedging demand"},
    {"symbol": "USO", "name": "Crude oil", "reads": "energy and headline inflation"},
    {"symbol": "HYG", "name": "High-yield credit", "reads": "credit risk appetite"},
]

# A release older than this is no longer "the catalyst". Three days rather than
# one: a Wednesday CPI is still the thing the tape is trading on Friday, and a
# tighter window went blank over a weekend — which is exactly when a reader has
# time to read it.
MAX_AGE_HOURS = 72

# Releases worth putting in catalyst mode at all, by the calendar's own impact
# band. A county-wages print is not a catalyst however recently it landed.
CATALYST_IMPACTS = ("high", "medium")


def _num(value: Any) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return None if out != out or out in (float("inf"), float("-inf")) else out


def latest_release(hours: int = MAX_AGE_HOURS) -> Optional[Dict[str, Any]]:
    """The most recent macro release that counts as a catalyst.

    Taken from the statistical agencies' own feeds, so the headline carries the
    figure the agency published rather than a reporter's paraphrase of it.
    """
    try:
        entries, _status = feeds.load_kind("macro")
    except Exception as exc:
        log.warning("catalyst mode: macro feed unavailable: %s", exc)
        return None
    recent = feeds.within_hours(entries, hours)
    for e in recent:
        source = (e.get("source") or "").lower()
        # Statistical agencies only. Enforcement actions are published on the
        # same feeds and are not market catalysts.
        if any(k in source for k in ("labor statistics", "economic analysis",
                                     "federal reserve", "census")):
            title = (e.get("title") or "").lower()
            if "charges" in title or "enforcement" in title:
                continue
            return e
    return None


def _age(published: Optional[str]) -> Optional[Dict[str, Any]]:
    if not published:
        return None
    try:
        when = datetime.fromisoformat(str(published))
    except (ValueError, TypeError):
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    delta = datetime.now(timezone.utc) - when
    hours = delta.total_seconds() / 3600.0
    if hours < 1:
        label = "{:.0f} minutes ago".format(delta.total_seconds() / 60)
    elif hours < 48:
        label = "{:.0f} hours ago".format(hours)
    else:
        label = "{:.0f} days ago".format(hours / 24)
    return {"hours": round(hours, 1), "label": label,
            "at_et": when.astimezone(ET).strftime("%b %-d at %-I:%M %p ET")}


def market_reaction(provider) -> Dict[str, Any]:
    """How each asset moved on the session, computed from bars."""
    symbols = [a["symbol"] for a in REACTION_ASSETS]
    try:
        frames = provider.batch_history(symbols, period="1mo", interval="1d") or {}
    except Exception as exc:
        return {"available": False, "reason": "Price data unavailable: {}".format(exc)}

    rows = []
    for asset in REACTION_ASSETS:
        frame = frames.get(asset["symbol"])
        if frame is None or frame.empty or len(frame) < 2:
            continue
        closes = frame["Close"].dropna()
        last, prev = _num(closes.iloc[-1]), _num(closes.iloc[-2])
        if last is None or prev is None or prev <= 0:
            continue
        rows.append({
            "symbol": asset["symbol"], "name": asset["name"], "reads": asset["reads"],
            "price": round(last, 2),
            "change_pct": round((last / prev - 1.0) * 100.0, 2),
        })
    return {"available": bool(rows), "assets": rows,
            "basis": "Change on the latest completed session against the prior close."}


def build(provider, hours: int = MAX_AGE_HOURS) -> Dict[str, Any]:
    """Everything catalyst mode needs: the release, its context, the reaction."""
    release = latest_release(hours)
    if not release:
        return {"available": False,
                "reason": ("No major statistical release in the last {} hours. Catalyst "
                           "mode shows the print that is currently moving the tape; when "
                           "there is not one, it says so rather than promoting a minor "
                           "release to fill the space.".format(hours))}

    # The calendar's own impact band and explanation for this release type.
    impact, why = None, None
    try:
        cal = events.upcoming()
        title_low = (release.get("title") or "").lower()
        for e in cal.get("events", []):
            needle = (e.get("short") or e.get("title") or "").lower()
            if needle and needle.split()[0] in title_low:
                impact, why = e.get("impact"), e.get("why")
                break
        if why is None:
            why = events._why(release.get("title") or "", "BLS")
    except Exception as exc:
        log.warning("catalyst mode: calendar lookup failed: %s", exc)

    return {
        "available": True,
        "release": {
            "title": release.get("title"),
            "summary": (release.get("summary") or "")[:900],
            "source": release.get("source"),
            "source_detail": release.get("source_detail"),
            "url": release.get("url"),
            "published": release.get("published"),
            "age": _age(release.get("published")),
            "impact": impact,
            "why_it_matters": why,
        },
        "reaction": market_reaction(provider),
        "consensus": {
            "available": False,
            "reason": (
                "Surveyed analyst estimates are a licensed product. A consensus "
                "number quietly copied from a stale free mirror, sitting beside a "
                "real actual, manufactures a 'surprise' that never happened — and "
                "the surprise is the figure a reader would act on. The release's "
                "own headline carries the actual; the reaction below is measured."
            ),
        },
        "method": (
            "The release is the agency's own headline, not a paraphrase. The "
            "cross-asset reaction is computed from daily bars — the latest "
            "completed session against the prior close — so it describes what "
            "moved, never why. Attributing a day's move to one release is an "
            "inference, and a session contains more than one piece of news."
        ),
    }
