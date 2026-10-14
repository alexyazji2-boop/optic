"""Asset and watchlist digests: what changed, what may explain it, what to look at.

Asked for 2026-10-12 ("concise, sourced summaries ... separate observed facts
from possible explanations ... timestamps and clickable evidence ... reuse
suitable shared summaries rather than regenerating identical research for each
viewer"), with Robinhood's Cortex Digests as the reference pattern.

Built from what Optic already computes, by fixed rules, with no model call:

- **What changed** is the daily briefing's own checks (app/briefing.py): the
  latest completed session against the one before, from dated candles and
  saved readings. Observed, so stated as fact.
- **What may explain it** is the company's own headlines published around that
  session (app/news.py's ranked feed), each with its publisher, time and link.
  Labelled as possible explanations: a story printed the same day is not shown
  to have caused a move, and the digest says so rather than implying it.
- **Worth a closer look** is what the facts leave open: earnings coming up, a
  large move with no company headline, checks that could not run.

The same symbol and session give the same digest to every reader, so it is
cached and shared (see main.py), and Milo can be handed it instead of being
asked to research the same thing again.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

METHOD = ("Written by fixed rules from Optic's own data, not by an AI model. What changed comes "
          "from the completed daily candles of the two sessions compared and from readings saved "
          "once a session. Headlines are the company's own news feed around those sessions: "
          "published near a move, not shown to have caused it.")

# How far either side of the latest session a headline counts as "around" it.
NEWS_WINDOW_HOURS = 72
MAX_EXPLANATIONS = 4
# A move this large with no company headline is worth saying out loud.
QUIET_MOVE_PCT = 3.0


def _parse(ts: Any) -> Optional[datetime]:
    if not ts:
        return None
    try:
        when = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    except ValueError:
        return None
    return when if when.tzinfo else when.replace(tzinfo=timezone.utc)


def describes(per: Dict[str, Any]) -> str:
    """The digest's period as a sentence a reader (or Milo) cannot misread as
    today's trading."""
    latest, previous = per.get("latest"), per.get("previous")
    if not latest:
        return "The period this digest covers is not known."
    span = "from the close of {} to the close of {}".format(previous, latest) if previous else "to the close of {}".format(latest)
    return ("A completed session, {}: each close and change here is that session's, not today's "
            "trading. Today's price and move are in the quote.".format(span))


def compose(symbol: str, briefing: Optional[Dict[str, Any]], news: Optional[Dict[str, Any]],
            now: Optional[datetime] = None) -> Dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    briefing = briefing or {}
    news = news or {}
    name = next((n for n in briefing.get("names") or [] if n.get("symbol") == symbol), None)
    changed = [it for it in briefing.get("items") or [] if it.get("symbol") == symbol]

    facts: List[Dict[str, Any]] = []
    for it in changed:
        facts.append({"text": it.get("headline") or it.get("text") or "",
                      "detail": it.get("detail"), "kind": it.get("kind")})
    if name and not facts:
        facts.append({"text": name.get("summary") or "No meaningful change.", "kind": "summary"})

    latest = (briefing.get("period") or {}).get("latest")
    anchor = _parse(latest + "T20:00:00+00:00") if latest else now
    lo, hi = anchor - timedelta(hours=NEWS_WINDOW_HOURS), anchor + timedelta(hours=NEWS_WINDOW_HOURS)
    explanations: List[Dict[str, Any]] = []
    for a in news.get("articles") or []:
        if not a.get("about_company") or not a.get("url"):
            continue
        when = _parse(a.get("published"))
        if when is None or not (lo <= when <= hi):
            continue
        explanations.append({
            "headline": a.get("title"), "publisher": a.get("publisher"),
            "published": when.isoformat(), "url": a.get("url"),
            "tone": a.get("tone"), "catalysts": a.get("catalysts") or [],
        })
        if len(explanations) >= MAX_EXPLANATIONS:
            break

    look: List[str] = []
    move = (name or {}).get("change_pct")
    if isinstance(move, (int, float)) and abs(move) >= QUIET_MOVE_PCT and not explanations:
        look.append("It moved {:+.1f}% with no company headline in the feed around the session. "
                    "Check the sector and the market that day.".format(move))
    days = news.get("days_to_earnings")
    if isinstance(days, (int, float)) and 0 <= days <= 14:
        look.append("Earnings are due in {} day{} ({}).".format(
            int(days), "" if int(days) == 1 else "s", news.get("earnings_date") or "date on file"))
    for gap in (name or {}).get("not_checked") or []:
        look.append("Not checked: {}.".format(gap))
    if news.get("held"):
        look.append(news["held"].get("note") or "The headline feed was empty just now.")

    state = (name or {}).get("state") or ("unavailable" if not briefing.get("available") else "unknown")
    per = briefing.get("period") or {}
    return {
        "available": bool(name) or bool(explanations),
        "symbol": symbol,
        "state": state,
        "as_of": now.isoformat(),
        "period": briefing.get("period"),
        # Which session `close` and `change_pct` belong to, said in words. The
        # digest is written once a session closes and served all the next
        # day, and `as_of` is when it was served, so Milo read Tuesday's close
        # and move ("rose 1% to $228.52") as Wednesday's while NVDA traded at
        # $221 (reported 2026-10-14).
        "session_date": per.get("latest"),
        "describes": describes(per),
        "close": (name or {}).get("close"),
        "change_pct": move,
        "changed": facts,
        "explanations": explanations,
        "explanations_note": ("Published around the session. Optic does not know whether any of "
                              "these caused the move.") if explanations else
                             "No company headline in the feed around the session.",
        "look_closer": look,
        "method": METHOD,
        "sources": [s for s in (briefing.get("source"), "Yahoo Finance news feed") if s],
    }


def compose_list(symbols: List[str], briefing: Optional[Dict[str, Any]],
                 news_for: Dict[str, Dict[str, Any]], now: Optional[datetime] = None) -> Dict[str, Any]:
    """One digest per name, the changed names first; headlines only where read."""
    now = now or datetime.now(timezone.utc)
    rows = [compose(s, briefing, news_for.get(s), now) for s in symbols]
    order = {"changed": 0, "stale": 1, "missing": 2, "unchanged": 3}
    rows.sort(key=lambda r: (order.get(r["state"], 4), r["symbol"]))
    per = (briefing or {}).get("period") or {}
    return {"available": bool(rows), "as_of": now.isoformat(),
            "period": per, "session_date": per.get("latest"), "describes": describes(per),
            "summary": (briefing or {}).get("summary"),
            "names": rows, "method": METHOD}
