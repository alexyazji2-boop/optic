"""User-defined watches: "tell me when something worth knowing happens".

The alerts this app already had are all book-driven — a scan opened a position,
a holding hit its stop, the portfolio reached a cap. Useful, and none of them
answer "let me know if NVDA does something". That is what this adds.

**Where a watch lives, and why this module still stores nothing.** Definitions
are stored per account in the `watches` table (see `app/account.py`), or in
localStorage for a guest. This module is deliberately not part of that: it is a
stateless evaluator that takes the conditions it is handed and reports which
have tripped. Evaluation reads live market panels and must not care whose watch
it is; storage cares about nothing else. Keeping them apart is what lets a guest
and an account holder share one evaluator.

The honest consequence, stated in the UI rather than buried: a watch is checked
while the page is open, on whatever symbol is being checked. It is not a push
notification. A push notification needs somewhere to push to — a device token
or a verified mailbox and a mail sender — and neither is configured here. An
alert that silently misses the move it was created for is worse than no alert,
which is the same argument `app/alerts.py` makes about delivery.

**Every condition names the number that tripped it.** A notification that says
"something happened" is worse than none, because it costs a page load to find
out it was nothing.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from . import setups as setups_mod

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
        "why": "Usually an invalidation level: the price at which a case stops "
               "being true.",
    },
    "move_pct": {
        "label": "Moves more than",
        "param": {"key": "pct", "kind": "percent", "label": "Percent", "default": 4},
        "needs": "quote",
        "why": "A day out of the ordinary, in either direction.",
    },
    # The two a reader new to this asks for by name. RSI is the first indicator
    # anybody learns and the first one they want told about, and the request
    # that prompted these was literally "if the RSI goes over 50 on NVDA".
    #
    # Defaults are 70 and 30 because those are the lines the indicator is drawn
    # with, not because they are better numbers than 50. The level is the
    # parameter precisely so nobody has to accept a convention they did not
    # choose.
    "rsi_above": {
        "label": "RSI rises above",
        "param": {"key": "level", "kind": "number", "label": "RSI level", "default": 70},
        "needs": "technicals",
        "why": "A crossing: it fires when RSI moves from at or under the line to "
               "above it, once, and again only after it has dropped back.",
    },
    "rsi_below": {
        "label": "RSI falls below",
        "param": {"key": "level", "kind": "number", "label": "RSI level", "default": 30},
        "needs": "technicals",
        "why": "The other end of the same reading. Low RSI is not a buy signal: "
               "a name in a real downtrend can sit under 30 for weeks.",
    },
    "macd_cross": {
        "label": "MACD turns",
        # Same reason `signal_flip` carries choices: the evaluator compares the
        # stored value against what the technicals panel publishes, and a UI
        # offering "up" where the data says "bullish" produces a watch that
        # never fires and looks broken rather than mismatched.
        "param": {"key": "to", "kind": "stance", "label": "To", "default": "any",
                  "choices": [
                      {"value": "any", "label": "Either direction"},
                      {"value": "bullish", "label": "Bullish"},
                      {"value": "bearish", "label": "Bearish"},
                  ]},
        "needs": "technicals",
        "why": "The MACD line relative to its signal line. Widely followed, and "
               "late by construction: it is built from averages, so it confirms "
               "a move rather than anticipating one.",
    },
    "breakout": {
        "label": "Breaks past every mapped level",
        "param": None,
        "needs": "technicals",
        "why": "The price moving above every support and resistance level Optic maps "
               "from the past year of swings, or below all of them. A change of state "
               "rather than a level you set.",
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
        # `choices` exists because the evaluators below compare the stored
        # parameter against a value produced elsewhere in the app. Without the
        # vocabulary written down, a UI offers "up" where the data says "rising"
        # and the watch never fires — which looks like a broken watch rather
        # than a mismatch, because "did not fire" is also the correct answer
        # most of the time.
        "param": {"key": "to", "kind": "stance", "label": "To", "default": "any",
                  "choices": [
                      {"value": "any", "label": "Any change"},
                      {"value": "bullish", "label": "Bullish (incl. leaning)"},
                      {"value": "leaning bullish", "label": "Leaning bullish only"},
                      {"value": "neutral", "label": "Neutral"},
                      {"value": "leaning bearish", "label": "Leaning bearish only"},
                      {"value": "bearish", "label": "Bearish (incl. leaning)"},
                  ]},
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
        # rising / falling, not up / down. `app/analytics/earnings.py` produces
        # those two words and the evaluator compares strings.
        "param": {"key": "direction", "kind": "direction", "label": "Direction",
                  "default": "any",
                  "choices": [
                      {"value": "any", "label": "Either direction"},
                      {"value": "rising", "label": "Revised up"},
                      {"value": "falling", "label": "Revised down"},
                  ]},
        "needs": "earnings_momentum",
        "why": "Forward estimates moving is a slower signal than price and often "
               "leads it.",
    },
    "insider_activity": {
        "label": "Insider transactions filed",
        # purchase / sale, which is what `action` holds on each row.
        "param": {"key": "side", "kind": "side", "label": "Side", "default": "any",
                  "choices": [
                      {"value": "any", "label": "Any filing"},
                      {"value": "purchase", "label": "Purchases"},
                      {"value": "sale", "label": "Sales"},
                  ]},
        "needs": "company.ownership",
        "why": "Form 4 filings. The filer's own classification, not an "
               "interpretation of it.",
    },
    # Swing setups, as an alert. The choices are the presets themselves, so a
    # watch can only name a rule that exists; the evaluator reads the rows the
    # snapshot attaches (see main._attach_setups), built with each preset's
    # default settings.
    "swing_setup": {
        "label": "A swing setup triggers",
        "param": {"key": "preset", "kind": "setup", "label": "Setup", "default": "any",
                  "choices": [{"value": "any", "label": "Any setup"}] + [
                      {"value": p["id"], "label": p["label"]} for p in setups_mod.PRESETS]},
        "needs": "setups",
        "why": "A Swing setups rule fired on a completed daily candle, with its "
               "default settings. Completed candles only, so it arrives after the "
               "close that triggered it; a candle still forming never raises one. "
               "For review: nothing is traded.",
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
    want = _num(p.get("pct")) if _num(p.get("pct")) is not None else 4.0
    chg = _num((d.get("quote") or {}).get("change_pct"))
    if chg is None or abs(chg) < want:
        return None
    return {"evidence": "{:+.2f}% today, past the {:.1f}% you set".format(chg, want)}


def _rsi(d):
    return _num(((d.get("technicals") or {}).get("rsi") or {}).get("value"))


def _rsi_above(d, p):
    level = _num(p.get("level"))
    value = _rsi(d)
    if level is None or value is None or value <= level:
        return None
    return {"evidence": "RSI {:.1f}, above {:.0f}".format(value, level)}


def _rsi_below(d, p):
    level = _num(p.get("level"))
    value = _rsi(d)
    if level is None or value is None or value >= level:
        return None
    return {"evidence": "RSI {:.1f}, below {:.0f}".format(value, level)}


def _macd_cross(d, p):
    macd = (d.get("technicals") or {}).get("macd") or {}
    state = str(macd.get("state") or "").strip().lower()
    if state not in ("bullish", "bearish"):
        return None
    want = str(p.get("to") or "any").strip().lower()
    if want != "any" and want != state:
        return None
    line, signal = _num(macd.get("macd")), _num(macd.get("signal"))
    if line is None or signal is None:
        return {"evidence": "MACD is {}".format(state)}
    return {"evidence": "MACD {:.2f} against its signal {:.2f}, {}".format(
        line, signal, state)}


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
    want = _num(p.get("min_ratio")) if _num(p.get("min_ratio")) is not None else 2.0
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


# The composite produces five stances (see swing.verdict): bullish, leaning
# bullish, neutral, leaning bearish, bearish. A reader asking to be told when it
# "turns bearish" means the family, not the exact string — an exact match would
# stay silent through "leaning bearish", which is the first thing that happens.
# The narrow options are still selectable and still match only themselves.
STANCE_FAMILIES: Dict[str, tuple] = {
    "bullish": ("bullish", "leaning bullish"),
    "bearish": ("bearish", "leaning bearish"),
}


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
    if want != "any" and stance not in STANCE_FAMILIES.get(want, (want,)):
        return None
    conviction = (d.get("verdict") or {}).get("conviction")
    return {"state": stance,
            "evidence": "stance reads {}{}".format(
                stance, ", {} conviction".format(conviction) if conviction else "")}


def _earnings_near(d, p):
    within = int(_num(p.get("days")) if _num(p.get("days")) is not None else 7)
    when = _iso_date(d.get("next_earnings_date"))
    if not when:
        return None
    # the runner's clock when it passes one (d["_now"]), so a test and a late pass agree with the schedule
    today = (d.get("_now") or datetime.now(timezone.utc)).date()
    days = (when - today).days
    if days < 0 or days > within:
        return None
    return {"evidence": "reports {}, {}".format(
        when.isoformat(),
        "today" if days == 0 else "in {} day{}".format(days, "" if days == 1 else "s"))}


def _analyst_revisions(d, p):
    want = str(p.get("direction") or "any").lower()
    em = d.get("earnings_momentum") or {}
    direction = str(em.get("revision_direction") or "").lower()
    # "unknown" belongs on this list. earnings.py uses it for "no
    # estimate-revision history available for this ticker", and firing a watch
    # on missing data is the worst kind of false positive: it reports an event
    # where there is not even an observation.
    if not direction or direction in ("flat", "unchanged", "none", "unknown"):
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


# The filings an insider watch reads: the latest 12, all the payload carried until it kept two years
# (2026-10-19). A watch on purchases means a recent purchase, not one from last year.
RECENT_FILINGS = 12


def _insider_activity(d, p):
    want = str(p.get("side") or "any").lower()
    own = ((d.get("company") or {}).get("ownership")) or {}
    rows = (own.get("recent_transactions") or [])[:RECENT_FILINGS]
    if want != "any":
        # `action`, not `kind` or `type`. The provider labels each row
        # purchase / sale / other (see providers/yf.py:insiders), and filtering
        # on a field that is never present emptied the list every time — so a
        # side-specific insider watch could not fire at all. The two older names
        # are kept as a fallback rather than removed, in case another provider
        # is added that uses them.
        rows = [r for r in rows
                if want in str(r.get("action") or r.get("kind")
                               or r.get("type") or "").lower()]
    if not rows:
        return None
    signal = own.get("insider_signal")
    return {"evidence": "{} recent form 4 filing{}{}".format(
        len(rows), "" if len(rows) == 1 else "s",
        ", read as {}".format(signal) if signal else "")}


def _short_interest(d, p):
    want = _num(p.get("pct")) if _num(p.get("pct")) is not None else 15.0
    si = ((d.get("company") or {}).get("short_interest")) or {}
    change = _num(si.get("change_vs_prior_pct"))
    if change is None or abs(change) < want:
        return None
    return {"evidence": "shares short {:+.1f}% versus the prior report, "
                        "{:.1f}% of float".format(
                            change, _num(si.get("percent_of_float")) or 0)}


def _swing_setup(d, p):
    """One hit per trigger, not per day.

    `state` and `dedupe` are the trigger's own key (symbol, preset, side,
    candle), so the browser-side check announces it once and the scheduled
    runner stores it once, however many days it stays fresh."""
    want = str(p.get("preset") or "any").lower()
    hits = setups_mod.fresh_triggers(d.get("setups") or {}, want)
    if not hits:
        return None
    hit = max(hits, key=lambda r: r["trigger"]["stamp"])
    side = "Bullish" if hit["direction"] == "bull" else "Bearish"
    # The row as the engine reported it, and what it read, for the signal
    # history to record exactly (app/signal_history.py). The watch evaluates
    # every preset at its defaults, so those are the parameters it ran with.
    return {"state": hit["key"], "dedupe": hit["key"],
            "evidence": "{} {}. {}".format(side, hit["label"].lower(), hit["explanation"]),
            "setup_row": hit,
            "setup_as_of": (d.get("setups") or {}).get("as_of"),
            "setup_params": setups_mod.resolve_params(hit["preset"], {})}


# ------------------------------------------------------------------ states
#
# What a check records, met or not. A watch fires when its state CHANGES into the
# met one, never because it is still met: "price above 350" fires once when the
# price crosses 350, and again only after it has fallen back and crossed again.
# Before this (the 2026-10-20 alerts audit) a level that was already crossed when
# the alert was made fired on the first check and then every trading day.
#
# Two families. A CROSSING needs a state to change from: the first check of a new
# or resumed alert only arms it (or the price the reader saw when they made it,
# `ref_price`, stands in). An EVENT carries its own identity in the state (the
# session, the report, the trigger), so the first sighting of a new one fires.

def _quote(d):
    q = d.get("quote") or {}
    return q, _num(q.get("price"))


def _session_of(d):
    q = d.get("quote") or {}
    stamp = str(q.get("market_time") or q.get("as_of") or "")[:10]
    return stamp or (d.get("_now") or datetime.now(timezone.utc)).date().isoformat()


def _st_level(value, level, word):
    if value is None or level is None:
        return None
    if word == "above":
        return "above" if value > level else "not above"
    return "below" if value < level else "not below"


def _st_insider(d, p):
    want = str(p.get("side") or "any").lower()
    own = ((d.get("company") or {}).get("ownership")) or {}
    rows = (own.get("recent_transactions") or [])[:RECENT_FILINGS]
    if want != "any":
        rows = [r for r in rows if want in str(r.get("action") or r.get("kind") or r.get("type") or "").lower()]
    if not rows:
        return "none"
    top = max(rows, key=lambda r: str(r.get("date") or ""))
    return "filing:{}:{}:{}".format(top.get("date") or "", str(top.get("insider") or "")[:40], top.get("shares") or "")


def state_of(kind, d, p, hit):
    """The condition's state on this check. None when the figures it needs are missing."""
    p = p or {}
    if kind == "price_above":
        return _st_level(_quote(d)[1], _num(p.get("level")), "above")
    if kind == "price_below":
        return _st_level(_quote(d)[1], _num(p.get("level")), "below")
    if kind == "rsi_above":
        return _st_level(_rsi(d), _num(p.get("level")), "above")
    if kind == "rsi_below":
        return _st_level(_rsi(d), _num(p.get("level")), "below")
    if kind == "macd_cross":
        s = str(((d.get("technicals") or {}).get("macd") or {}).get("state") or "").strip().lower()
        return s or None
    if kind == "breakout":
        return "broken" if hit else ("inside" if (d.get("technicals") or {}).get("support_resistance") else None)
    if kind == "signal_flip":
        s = str(((d.get("verdict") or {}).get("stance") or "")).lower()
        return s or None
    if kind == "analyst_revisions":
        s = str((d.get("earnings_momentum") or {}).get("revision_direction") or "").lower()
        return s or None
    if kind == "insider_activity":
        return _st_insider(d, p)
    if kind == "move_pct":
        return "{}:{}".format("moved" if hit else "quiet", _session_of(d))
    if kind == "unusual_options":
        return "{}:{}".format("hit" if hit else "none", (d.get("_now") or datetime.now(timezone.utc)).date().isoformat())
    if kind == "earnings_near":
        when = d.get("next_earnings_date")
        return "{}:{}".format("near" if hit else "far", str(when)[:10]) if when else None
    if kind == "short_interest":
        si = ((d.get("company") or {}).get("short_interest")) or {}
        rep = si.get("settlement_date")
        return "{}:{}".format("changed" if hit else "steady", rep) if rep else ("changed" if hit else None)
    if kind == "swing_setup":
        return (hit or {}).get("state") or "none"
    return None


CROSSINGS = {"price_above", "price_below", "rsi_above", "rsi_below", "macd_cross", "breakout",
             "signal_flip", "analyst_revisions", "insider_activity"}


def fires(kind, previous, current, met):
    """Whether this check is news: met, and a state different from the last one recorded.
    A crossing with nothing recorded before only arms (it fires on the next change)."""
    if not met or current is None:
        return False
    if kind in CROSSINGS and previous is None:
        return False
    return previous != current


def ref_state(kind, params, ref_price):
    """The state the reader saw when they made a price alert, from the price on their screen."""
    if ref_price is None or kind not in ("price_above", "price_below"):
        return None
    return _st_level(_num(ref_price), _num((params or {}).get("level")), "above" if kind == "price_above" else "below")


def observed(kind, d, p, now=None):
    """The figures a fired alert is explained by: what was read, what it was compared with, when."""
    q, price = _quote(d)
    out = {"price": price, "quote_time": q.get("market_time") or q.get("as_of"),
           "source": q.get("source") or "Yahoo Finance",
           "delay": "Prices from the free feed are about 15 minutes behind the exchange."}
    if kind in ("price_above", "price_below"):
        out["level"] = _num((p or {}).get("level"))
    elif kind in ("rsi_above", "rsi_below"):
        out.update(value=_rsi(d), level=_num((p or {}).get("level")))
    elif kind == "move_pct":
        out.update(value=_num(q.get("change_pct")), level=_num((p or {}).get("pct")))
    return {k: v for k, v in out.items() if v is not None}


EVALUATORS = {
    "price_above": _price_above,
    "price_below": _price_below,
    "move_pct": _move_pct,
    "rsi_above": _rsi_above,
    "rsi_below": _rsi_below,
    "macd_cross": _macd_cross,
    "breakout": _breakout,
    "unusual_options": _unusual_options,
    "signal_flip": _signal_flip,
    "earnings_near": _earnings_near,
    "analyst_revisions": _analyst_revisions,
    "insider_activity": _insider_activity,
    "short_interest": _short_interest,
    "swing_setup": _swing_setup,
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
        try:
            row["state"] = state_of(kind, payload, w.get("params") or {}, hit)
            row["observed"] = observed(kind, payload, w.get("params") or {})
        except Exception:                      # a state is extra: never what stops the check
            row.setdefault("state", None)
        out.append(row)
    return out


def catalogue():
    """The conditions a client may offer, and what each one reads."""
    return {
        "conditions": [dict(id=k, **v) for k, v in CONDITIONS.items()],
        "method": (
            "An alert is checked against the same figures the Dossier shows. It "
            "fires when its condition changes from not met to met, once, and again "
            "only after it has stopped being met: a price alert fires when the price "
            "crosses the level, not every day it stays past it. Signed in, Optic "
            "checks your alerts on market days about every 30 minutes from 9:30 to "
            "4:00 ET and once after the close, skipping exchange holidays, and keeps "
            "what fired for you here. As a guest, alerts live in this browser and are "
            "checked only while this page is open. Prices come from the free feed, "
            "about 15 minutes behind the exchange. Optic shows alerts here; it does "
            "not send email or push notifications."
        ),
        "schedule": {"every_minutes": 30, "hours": "Mon to Fri, 9:30 to 4:00 ET, and once after the close",
                     "holidays": "skipped", "delay_minutes": 15, "delivery": "In Optic only"},
    }
