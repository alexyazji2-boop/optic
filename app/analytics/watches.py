"""User-defined watches: "tell me when something worth knowing happens".

The alerts this app already had are all book-driven — a scan opened a position,
a holding hit its stop, the portfolio reached a cap. Useful, and none of them
answer "let me know if NVDA does something". That is what this adds.

**Where a watch lives, and why that matters.** There is no sign-in: anyone can
open this terminal, so there is no user to own a row in a table. Watch
definitions therefore live in the browser, like the watchlist and the thesis,
and this module is a stateless evaluator — the client posts what it is watching
and gets back what has tripped, with the evidence. Nothing is stored here.

The honest consequence, stated in the UI rather than buried: a watch is checked
while the page is open. It is not a push notification, because a push
notification needs an account to push to.

**Every condition names the number that tripped it.** A notification that says
"something happened" is worse than none, because it costs a page load to find
out it was nothing.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Callable, Dict, List, Optional

# The catalogue. `needs` documents which panel each one reads, so a condition
# cannot be added without saying where its evidence comes from.
CONDITIONS: Dict[str, Dict[str, Any]] = {
    "price_above": {
        "label": "Price rises above",
        "param": {"key": "level", "kind": "price", "label": "Level"},
        "needs": "quote",
        "why": "A level you have decided matters. The plainest watch there is.",
    },
    "price_below": {
        "label": "Price falls below",
        "param": {"key": "level", "kind": "price", "label": "Level"},
        "needs": "quote",
        "why": "Usually an invalidation level — the price at which a case stops "
               "being true.",
    },
    "move_pct": {
        "label": "Moves more than",
        "param": {"key": "pct", "kind": "percent", "label": "Percent", "default": 4},
        "needs": "quote",
        "why": "A day out of the ordinary, in either direction.",
    },
    "breakout": {
        "label": "Breaks its 20-day range",
        "param": None,
        "needs": "technicals",
        "why": "A close beyond the prior 20 sessions' high or low. A change of "
               "state rather than a level.",
    },
    "unusual_options": {
        "label": "Unusual options activity",
        "param": {"key": "min_ratio", "kind": "number", "label": "Vol / OI at least",
                  "default": 2},
        "needs": "flow",
        "why": "A contract trading far above its own open interest. A positioning "
               "proxy: free data carries no trade tape, so this shows size, not "
               "who initiated it.",
    },
    "signal_flip": {
        "label": "Optic stance changes",
        "param": {"key": "to", "kind": "stance", "label": "To", "default": "any"},
        "needs": "verdict",
        "why": "The composite's direction changed. Worth knowing precisely "
               "because you are told when it stops agreeing with you.",
    },
    "earnings_near": {
        "label": "Earnings within",
        "param": {"key": "days", "kind": "days", "label": "Days", "default": 7},
        "needs": "next_earnings_date",
        "why": "The largest scheduled risk a holder carries, and the one that is "
               "knowable in advance.",
    },
    "analyst_revisions": {
        "label": "Analyst estimates revised",
        "param": {"key": "direction", "kind": "direction", "label": "Direction",
                  "default": "any"},
        "needs": "earnings_momentum",
        "why": "Forward estimates moving is a slower signal than price and often "
               "leads it.",
    },
    "insider_activity": {
        "label": "Insider transactions filed",
        "param": {"key": "side", "kind": "side", "label": "Side", "default": "any"},
        "needs": "company.ownership",
        "why": "Form 4 filings. The filer's own classification, not an "
               "interpretation of it.",
    },
    "short_interest": {
        "label": "Short interest changes by",
        "param": {"key": "pct", "kind": "percent", "label": "Percent", "default": 15},
        "needs": "company.short_interest",
        "why": "Reported twice a month, so this moves in steps rather than "
               "continuously. Dated in the evidence.",
    },
}


def _num(value: Any) -> Optional[float]:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if out == out else None


def _iso_date(value: Any) -> Optional[date]:
    text = str(value or "")[:10]
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


# --------------------------------------------------------------- evaluators
#
# Each returns None when the condition is not met, or a dict carrying the
# evidence when it is. One function per condition means adding one is a function
# plus a catalogue entry, and the dispatcher never grows a branch.


def _price_above(d, p):
    level = _num(p.get("level"))
    price = _num((d.get("quote") or {}).get("price"))
    if level is None or price is None or price <= level:
        return None
    return {"evidence": "last {:,.2f}, above {:,.2f}".format(price, level)}


def _price_below(d, p):
    level = _num(p.get("level"))
    price = _num((d.get("quote") or {}).get("price"))
    if level is None or price is None or price >= level:
        return None
    return {"evidence": "last {:,.2f}, below {:,.2f}".format(price, level)}


def _move_pct(d, p):
    want = _num(p.get("pct")) or 4.0
    chg = _num((d.get("quote") or {}).get("change_pct"))
    if chg is None or abs(chg) < want:
        return None
    return {"evidence": "{:+.2f}% today, past the {:.1f}% you set".format(chg, want)}


def _breakout(d, p):
    """The nearest level either side, from the support/resistance panel.

    Read off technicals rather than recomputed here. That panel already knows
    where the recent extremes are, and a second version over a different window
    is how two parts of one app come to disagree about whether a name broke out.
    """
    tech = d.get("technicals") or {}
    spot = _num(tech.get("spot")) or _num((d.get("quote") or {}).get("price"))
    if spot is None:
        return None
    levels = [_num(l.get("price")) for l in (tech.get("support_resistance") or [])]
    levels = [x for x in levels if x is not None]
    if not levels:
        return None
    above = [x for x in levels if x > spot]
    below = [x for x in levels if x < spot]
    # Price beyond every known level on one side is the break. Between two of
    # them it has not broken either, which is the common case.
    if not above and below:
        return {"evidence": "{:,.2f} is above every mapped level, the highest "
                            "being {:,.2f}".format(spot, max(below))}
    if not below and above:
        return {"evidence": "{:,.2f} is below every mapped level, the lowest "
                            "being {:,.2f}".format(spot, min(above))}
    return None


def _unusual_options(d, p):
    want = _num(p.get("min_ratio")) or 2.0
    rows = (d.get("flow") or {}).get("unusual") or []
    hits = [r for r in rows if (_num(r.get("vol_oi_ratio")) or 0) >= want]
    if not hits:
        return None
    top = max(hits, key=lambda r: _num(r.get("vol_oi_ratio")) or 0)
    return {"evidence": "{} contract{} at or above {:.1f}x open interest; the "
                        "largest is the {:,.0f} {} at {:.1f}x".format(
                            len(hits), "" if len(hits) == 1 else "s", want,
                            _num(top.get("strike")) or 0,
                            str(top.get("type", "")).lower(),
                            _num(top.get("vol_oi_ratio")) or 0)}


def _signal_flip(d, p):
    """Reports a STATE, not a transition.

    This evaluator is stateless — it has no memory of the previous check — so
    it cannot see a change. It returns the current stance and the client
    compares it with what it last recorded. Claiming to detect the flip here
    would mean firing on every poll.
    """
    want = str(p.get("to") or "any").lower()
    stance = str(((d.get("verdict") or {}).get("stance") or "")).lower()
    if not stance:
        return None
    if want != "any" and stance != want:
        return None
    conviction = (d.get("verdict") or {}).get("conviction")
    return {"state": stance,
            "evidence": "stance reads {}{}".format(
                stance, ", {} conviction".format(conviction) if conviction else "")}


def _earnings_near(d, p):
    within = int(_num(p.get("days")) or 7)
    when = _iso_date(d.get("next_earnings_date"))
    if not when:
        return None
    days = (when - datetime.now(timezone.utc).date()).days
    if days < 0 or days > within:
        return None
    return {"evidence": "reports {} \u2014 {}".format(
        when.isoformat(),
        "today" if days == 0 else "in {} day{}".format(days, "" if days == 1 else "s"))}


def _analyst_revisions(d, p):
    want = str(p.get("direction") or "any").lower()
    em = d.get("earnings_momentum") or {}
    direction = str(em.get("revision_direction") or "").lower()
    if not direction or direction in ("flat", "unchanged", "none"):
        return None
    if want != "any" and direction != want:
        return None
    detail = ""
    for sig in em.get("signals") or []:
        if str(sig.get("label", "")).lower().startswith("estimate"):
            detail = str(sig.get("detail") or "")[:120]
            break
    return {"state": direction,
            "evidence": "estimates {}{}".format(direction, ". " + detail if detail else "")}


def _insider_activity(d, p):
    want = str(p.get("side") or "any").lower()
    own = ((d.get("company") or {}).get("ownership")) or {}
    rows = own.get("recent_transactions") or []
    if want != "any":
        rows = [r for r in rows
                if want in str(r.get("kind") or r.get("type") or "").lower()]
    if not rows:
        return None
    signal = own.get("insider_signal")
    return {"evidence": "{} recent form 4 filing{}{}".format(
        len(rows), "" if len(rows) == 1 else "s",
        ", read as {}".format(signal) if signal else "")}


def _short_interest(d, p):
    want = _num(p.get("pct")) or 15.0
    si = ((d.get("company") or {}).get("short_interest")) or {}
    change = _num(si.get("change_vs_prior_pct"))
    if change is None or abs(change) < want:
        return None
    return {"evidence": "shares short {:+.1f}% versus the prior report, "
                        "{:.1f}% of float".format(
                            change, _num(si.get("percent_of_float")) or 0)}


EVALUATORS = {
    "price_above": _price_above,
    "price_below": _price_below,
    "move_pct": _move_pct,
    "breakout": _breakout,
    "unusual_options": _unusual_options,
    "signal_flip": _signal_flip,
    "earnings_near": _earnings_near,
    "analyst_revisions": _analyst_revisions,
    "insider_activity": _insider_activity,
    "short_interest": _short_interest,
}


def check(payload, watches):
    """Evaluate every watch for one symbol against its finished payload.

    Returns one row per watch, met or not, rather than only the hits. "This was
    checked and did not fire" is what makes an empty result trustworthy instead
    of ambiguous — the same reason every scan in this app states what it did not
    find.
    """
    out = []
    for w in (watches or []):
        kind = str(w.get("kind") or "")
        meta = CONDITIONS.get(kind)
        fn = EVALUATORS.get(kind)
        if not meta or not fn:
            out.append({"id": w.get("id"), "kind": kind, "met": False,
                        "reason": "Unknown condition. It may have been removed "
                                  "since this watch was created."})
            continue
        try:
            hit = fn(payload, w.get("params") or {})
        except Exception as exc:               # a bad parameter must not 500
            out.append({"id": w.get("id"), "kind": kind, "met": False,
                        "reason": "Could not evaluate: {}".format(exc)})
            continue
        row = {"id": w.get("id"), "kind": kind, "label": meta["label"],
               "met": hit is not None, "why": meta["why"]}
        if hit:
            row.update(hit)
        out.append(row)
    return out


def catalogue():
    """The conditions a client may offer, and what each one reads."""
    return {
        "conditions": [dict(id=k, **v) for k, v in CONDITIONS.items()],
        "method": (
            "A watch is evaluated against the same panels the analysis page "
            "shows, at the moment it is checked. Definitions live in your "
            "browser because this terminal has no sign-in, which means a watch "
            "is checked while the page is open rather than pushed to you."
        ),
    }
