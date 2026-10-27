"""The portfolio briefing: what changed, what drove it, what is coming.

Two kinds of statement are kept apart on purpose:

- **Measured.** A holding's contribution to today's move is its quantity times
  the change in its price since the previous close, from the quote Optic
  shows (with that quote's time). Since the last sync, the change in value is
  split into the price effect on positions held at both syncs and everything
  else (trades, deposits, new positions), from the stored snapshots. These are
  arithmetic, and the page says which prices they used.
- **Possibly related.** Headlines about a holding published around the move.
  Timing is the only link Optic has checked; the briefing never says a
  headline caused a move, and a large move with no headline is said to have
  none. This is the rule `app/digest.py` already follows for a single name.

Nothing here calls a model. The optional written briefing (`workspace.py`)
is built from this output only, on request, metered and cached.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, Iterable, List, Optional

from .. import news as news_mod

VERSION = "briefing-2026-10-27.1"
MAX_HEADLINE_NAMES = 4
HEADLINE_WINDOW_HOURS = 36
BIG_MOVE_PCT = 3.0


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse(v: Any) -> Optional[datetime]:
    if not v:
        return None
    try:
        d = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    except ValueError:
        return None
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def today_moves(holdings: Iterable[Dict[str, Any]], quotes: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """Contribution of each holding to the move since the previous close.

    `quotes[sym] = {"price", "prev_close", "as_of", "market_time", "delayed_minutes", "source"}`.
    Uses today's quantities: a position bought today shows a full-day
    contribution it did not earn, which the limitations say."""
    rows, missing = [], []
    start = end = 0.0
    times: List[str] = []
    for h in holdings:
        sym = str(h.get("symbol") or "").upper()
        if not sym or h.get("kind") not in ("equity", "etf", "fund", "crypto"):
            continue
        q = quotes.get(sym) or {}
        price, prev, qty = q.get("price"), q.get("prev_close"), h.get("quantity")
        if price is None or prev in (None, 0) or qty is None or (h.get("currency") or "USD") != "USD":
            missing.append(sym)
            continue
        contrib = float(qty) * (float(price) - float(prev))
        start += float(qty) * float(prev)
        end += float(qty) * float(price)
        if q.get("as_of"):
            times.append(str(q["as_of"]))
        rows.append({"symbol": sym, "quantity": qty, "price": price, "prev_close": prev,
                     "change_pct": round(100.0 * (float(price) / float(prev) - 1.0), 2),
                     "contribution": round(contrib, 2), "quote_as_of": q.get("as_of"),
                     "market_time": q.get("market_time"), "delayed_minutes": q.get("delayed_minutes"),
                     "source": q.get("source")})
    rows.sort(key=lambda r: -abs(r["contribution"]))
    total = end - start
    return {
        "available": bool(rows),
        "rows": rows,
        "total": round(total, 2),
        "total_pct": round(100.0 * total / start, 2) if start else None,
        "covered_value_at_prev_close": round(start, 2),
        "not_priced": missing,
        "quotes_oldest": min(times) if times else None,
        "quotes_newest": max(times) if times else None,
    }


def since_sync(changes: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """The overview's `changes` (portfolio.diff), restated as measured parts."""
    if not changes:
        return {"available": False,
                "reason": "There is no earlier sync to compare with yet. After the next sync this shows what "
                          "changed between the two."}
    out = {"available": True, "since": changes.get("since"), "same_accounts": changes.get("same_accounts"),
           "value_change_by_currency": changes.get("value_change_by_currency") or {},
           "price_effect_by_currency": changes.get("price_effect_by_currency") or {},
           "added": changes.get("added") or [], "removed": changes.get("removed") or [],
           "quantity_changed": changes.get("quantity_changed") or [], "note": changes.get("note")}
    other = {}
    for ccy, total in out["value_change_by_currency"].items():
        other[ccy] = round(float(total or 0) - float(out["price_effect_by_currency"].get(ccy) or 0), 2)
    out["other_change_by_currency"] = other
    return out


def headlines_for(rows: List[Dict[str, Any]], news_of: Optional[Callable[[str], List[Dict[str, Any]]]],
                  now: datetime,
                  company_of: Optional[Callable[[str], Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
    """For the biggest movers, headlines about the company published in the
    last HEADLINE_WINDOW_HOURS: candidates, never causes.

    The provider's feed for a symbol is not news about that company. On
    26 October 2026 NVDA's carried BlackBerry, Costco and Nike stories and
    NOW's carried gas prices, and all of them were listed as possibly related
    to the holding's move. So each item passes the News page's relevance test
    first (`app/news.py`, with the company's name from `company_of`): a story
    that names the company is a candidate, a market-wide story is kept apart
    as market context, and the rest is counted and left out."""
    out: List[Dict[str, Any]] = []
    if news_of is None:
        return out
    since = now - timedelta(hours=HEADLINE_WINDOW_HOURS)
    for r in rows[:MAX_HEADLINE_NAMES]:
        sym = r["symbol"]
        try:
            items = news_of(sym) or []
        except Exception:                                       # noqa: BLE001
            items = []
        try:
            co = (company_of(sym) if company_of else None) or {}
        except Exception:                                       # noqa: BLE001
            co = {}
        name, sector, industry = (str(co.get(k) or "") for k in ("name", "sector", "industry"))
        recent, market, set_aside = [], [], 0
        for n in items:
            at = _parse(n.get("published"))
            if not (at and since <= at <= now + timedelta(minutes=5)):
                continue
            kind, _why = news_mod.relevance(n, sym, name, sector, industry)
            row = {"title": n.get("title"), "publisher": n.get("publisher"),
                   "published": n.get("published"), "url": n.get("url")}
            if kind == "company":
                recent.append(row)
            elif kind == "market":
                market.append(row)
            else:
                set_aside += 1
        big = abs(r.get("change_pct") or 0) >= BIG_MOVE_PCT
        if recent:
            note = ("Published around the move. Optic matched these by timing only and has not established "
                    "that any of them caused it.")
        else:
            note = "No headline about {} in the last {} hours.".format(sym, HEADLINE_WINDOW_HOURS)
            if big:
                note = "A move of {:.1f}% with no headline about {} in the last {} hours.".format(
                    r.get("change_pct") or 0, sym, HEADLINE_WINDOW_HOURS)
        others = set_aside + len(market)
        if others and not recent:
            note += " The feed's other {} {} about other companies or the wider market.".format(
                others, "story was" if others == 1 else "stories were")
        out.append({
            "symbol": sym, "change_pct": r.get("change_pct"), "contribution": r.get("contribution"),
            "headlines": recent[:3],
            "market_context": market,
            "set_aside": set_aside,
            "status": "possibly_related" if recent else ("no_headline" if big else "quiet"),
            "note": note,
        })
    return out


def market_context(drivers: List[Dict[str, Any]], limit: int = 3) -> List[Dict[str, Any]]:
    """Market-wide stories that arrived under the holdings' feeds, once each
    and newest first, kept apart from any one holding's headlines."""
    seen: Dict[str, Dict[str, Any]] = {}
    for d in drivers:
        for h in d.pop("market_context", None) or []:
            key = str(h.get("url") or h.get("title") or "").strip().lower()
            if not key:
                continue
            if key in seen:
                seen[key]["under"].append(d["symbol"])
            else:
                seen[key] = dict(h, under=[d["symbol"]])
    rows = sorted(seen.values(), key=lambda h: str(h.get("published") or ""), reverse=True)
    return rows[:limit]


def observations(overview: Dict[str, Any], events: Dict[str, Any], moves: Dict[str, Any],
                 limit: int = 5) -> List[Dict[str, Any]]:
    """A few things that deserve attention, most important first. Each says
    where it came from so the page can link to the detail."""
    obs: List[Dict[str, Any]] = []
    for flag in ((overview.get("concentration") or {}).get("flags") or [])[:2]:
        obs.append({"kind": "concentration", "text": flag, "section": "holdings", "source": "Optic calculation"})
    soon = [e for e in (events or {}).get("events") or [] if e.get("kind") == "earnings" and e.get("days_away", 99) <= 7]
    if soon:
        names = ", ".join("{} ({})".format(e["symbol"], "confirmed" if e.get("confirmed") else "estimated")
                          for e in soon[:4])
        share = round(sum(e.get("weight_pct") or 0 for e in soon), 1)
        obs.append({"kind": "earnings", "section": "events", "source": "Yahoo earnings calendar",
                    "text": "Reporting within a week: {}, together {}% of your portfolio.".format(names, share)})
    expiring = [e for e in (events or {}).get("events") or [] if e.get("kind") == "option_expiry"
                and e.get("days_away", 99) <= 7]
    if expiring:
        obs.append({"kind": "options", "section": "holdings", "source": "Your option positions",
                    "text": "{} option position{} expire{} within a week.".format(
                        len(expiring), "" if len(expiring) == 1 else "s", "s" if len(expiring) == 1 else "")})
    if moves.get("available") and moves["rows"]:
        top = moves["rows"][0]
        obs.append({"kind": "move", "section": "overview", "source": "Market quotes",
                    "text": "{} moved {:+.2f}% today, the largest contribution to your portfolio's move "
                            "({:+,.2f}).".format(top["symbol"], top["change_pct"], top["contribution"])})
    problems = [a for a in overview.get("accounts") or [] if a.get("selected")
                and a.get("sync_state") not in (None, "ok")]
    if problems:
        obs.append({"kind": "data", "section": "connections", "source": "Your connection",
                    "text": "{} counted account{} did not sync fully; figures for {} are partial.".format(
                        len(problems), "" if len(problems) == 1 else "s", "it" if len(problems) == 1 else "them")})
    if overview.get("unsupported"):
        obs.append({"kind": "data", "section": "holdings", "source": "Your broker",
                    "text": "{} holding{} could not be valued and {} left out of every figure.".format(
                        len(overview["unsupported"]), "" if len(overview["unsupported"]) == 1 else "s",
                        "is" if len(overview["unsupported"]) == 1 else "are")})
    # Incomplete data first: it qualifies every other line on the page (the
    # first browser run cut a partial sync's warning off below a price move).
    order = {"data": 0, "concentration": 1, "earnings": 2, "options": 3, "move": 4}
    obs.sort(key=lambda o: order.get(o["kind"], 5))
    return obs[:limit]


def build(overview: Dict[str, Any], events: Dict[str, Any], quotes: Dict[str, Dict[str, Any]],
          news_of: Optional[Callable[[str], List[Dict[str, Any]]]] = None,
          now: Optional[datetime] = None,
          company_of: Optional[Callable[[str], Dict[str, Any]]] = None) -> Dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    moves = today_moves(overview.get("holdings") or [], quotes or {})
    drivers = headlines_for(moves.get("rows") or [], news_of, now, company_of)
    return {
        "version": VERSION,
        "generated_at": _iso(now),
        "today": moves,
        "since_sync": since_sync(overview.get("changes")),
        "drivers": drivers,
        "market_context": market_context(drivers),
        "upcoming": [e for e in (events or {}).get("events") or [] if e.get("days_away", 99) <= 14][:8],
        "observations": observations(overview, events, moves),
        "limitations": [
            "Today's contributions use today's quantities and the quotes shown with their times; a position "
            "bought or sold today is not separated out, and options are not included.",
            "Headlines are matched to a move by when they were published. That is not evidence of cause. "
            "Only stories that name the company are listed under it; market-wide stories are listed apart.",
            "Since-last-sync figures compare two stored snapshots; deposits, withdrawals and trades sit in "
            "the part that is not price effect.",
        ],
    }
