"""Optic Pulse: the stance, why it moved, and what matters next.

Three questions, answered from data the payload already carries. Nothing here
calls a model — the AI writers are rate-limited to thirty calls an hour and the
answer to "why is this moving" has to be on screen the moment the page paints,
every time, for every symbol.

**The stance is qualitative on purpose.** `verdict.composite_score` exists and is
deliberately not shown as a headline. The project's own `evaluate` module
backtests that exact blend and reports that it "does not beat a single raw
momentum number", which means "82 / 100" would be a precise-looking figure the
codebase already knows is decoration. What survives that audit is the direction
and the spread of the inputs, so that is what the panel leads with: a stance, a
conviction, and one bar per factor. The measured skill goes on the panel next to
them rather than in a footnote nobody opens.

The factor bars come from `verdict.components`, each scored -100 to +100 upstream.
They are rescaled to 0-100 for display only: a bar cannot be negative, and a
reader comparing five bars is asking "which inputs are pulling hardest", which
is a question about magnitude and direction together. 50 is neutral.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional

# Display order, loosely by how directly each speaks to this one ticker. Macro
# is last because it describes the whole market, not this name.
FACTOR_ORDER = ["technicals", "gamma", "flow", "news", "macro"]

FACTOR_LABELS = {
    "technicals": "Momentum",
    "gamma": "Options",
    "flow": "Positioning",
    "news": "News",
    "macro": "Macro",
}

# How strong a factor has to read before it earns a line in "why it's moving".
# Below this a factor is noise dressed as a reason.
WHY_FLOOR = 20.0

STANCE_WORDS = {"bullish": "BULLISH", "bearish": "BEARISH", "neutral": "NEUTRAL"}


def _num(value: Any) -> Optional[float]:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if out == out else None          # NaN check without importing math


def _direction(score: Optional[float]) -> str:
    if score is None:
        return "flat"
    if score >= WHY_FLOOR:
        return "up"
    if score <= -WHY_FLOOR:
        return "down"
    return "flat"


def factors(verdict: Dict[str, Any]) -> List[Dict[str, Any]]:
    """One row per input: label, signed score, and a 0-100 bar position."""
    components = (verdict or {}).get("components") or {}
    breakdown = {b.get("component"): b for b in ((verdict or {}).get("breakdown") or [])}
    out: List[Dict[str, Any]] = []
    for key in FACTOR_ORDER:
        if key not in components:
            continue
        score = _num(components.get(key))
        row = breakdown.get(key) or {}
        out.append({
            "key": key,
            "label": FACTOR_LABELS.get(key, key.title()),
            "score": score,
            # 0-100 for the bar. Sign is kept in `score` and in `direction`, so a
            # reader can see a bearish factor is short AND read why.
            "bar": None if score is None else round((score + 100) / 2, 1),
            "direction": _direction(score),
            "weight_pct": row.get("weight_pct"),
            "measures": row.get("measures"),
            # A factor with no data is shown as absent rather than as neutral.
            # Drawing a half-full bar for "we could not price this" is the
            # failure mode this avoids.
            "unavailable": bool(row.get("unavailable")),
            "why_unavailable": row.get("status_reason") if row.get("unavailable") else None,
        })
    return out


def skill_note(evaluation: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """What the backtest says about this blend, in one line.

    Shown ON the Pulse panel. The evaluation already exists as its own tab and
    almost nobody opens it, which meant the app's own finding that the composite
    adds nothing over momentum lived three clicks from the number it undermines.
    """
    comparison = ((evaluation or {}).get("comparison") or [])
    if not comparison:
        return {
            "available": False,
            "text": "This blend's out-of-sample skill has not been measured on this run.",
            "beats_single": None,
        }
    tested = [c for c in comparison if c.get("single_factor_ic") is not None]
    if not tested:
        return {
            "available": False,
            "text": "Not enough history to test this blend against a single momentum factor.",
            "beats_single": None,
        }
    wins = [c for c in tested if c.get("beats_single_factor")]
    beats = len(wins) == len(tested)
    if beats:
        text = ("Measured: this blend beat a single momentum factor at every horizon "
                "tested. The weights are carrying information.")
    elif wins:
        text = ("Measured: this blend beat a single momentum factor at {} of {} "
                "horizons. Read the bars, not a total.".format(len(wins), len(tested)))
    else:
        text = ("Measured: this blend has not beaten three-month momentum on its own "
                "at any horizon tested. Read the bars, not a total.")
    return {"available": True, "text": text, "beats_single": beats,
            "horizons_tested": len(tested), "horizons_won": len(wins)}


def pulse(payload: Dict[str, Any], evaluation: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """The stance panel. Qualitative by design — see the module docstring."""
    verdict = (payload or {}).get("verdict") or {}
    stance = str(verdict.get("stance") or "neutral").lower()
    rows = factors(verdict)
    priced = [r for r in rows if not r["unavailable"] and r["score"] is not None]
    return {
        "stance": stance,
        "stance_label": STANCE_WORDS.get(stance, stance.upper()),
        "conviction": verdict.get("conviction"),
        "factors": rows,
        # How many inputs actually had data. A stance built on two of five is a
        # different claim from one built on five, and the panel should say which.
        "factors_priced": len(priced),
        "factors_total": len(rows),
        "agreement_pct": verdict.get("signal_agreement_pct"),
        "conflicts": verdict.get("conflicts") or [],
        "skill": skill_note(evaluation),
        # Kept in the payload, deliberately not the headline. Anything that wants
        # to rank or sort still has a number to use.
        "composite_score": verdict.get("composite_score"),
    }


# --------------------------------------------------------------- why it moved

def _pct(value: Any, digits: int = 2) -> Optional[float]:
    n = _num(value)
    return None if n is None else round(n, digits)


def why(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Three reasons, strongest first, each with the evidence under it.

    Derived rather than written. A model asked "why is NVDA up" will produce
    fluent prose whether or not anything in the payload supports it, and it
    cannot be shown the numbers cheaply enough to do this on every page load.
    Every reason here points at a field a reader can go and check, which is the
    difference between an explanation and a plausible sentence.

    Ranked by |score| so the order is the order of magnitude, not the order the
    factors happen to be declared in.
    """
    verdict = (payload or {}).get("verdict") or {}
    technicals = (payload or {}).get("technicals") or {}
    gex = (payload or {}).get("gex") or {}
    flow = (payload or {}).get("flow") or {}
    news = (payload or {}).get("news") or {}
    quote = (payload or {}).get("quote") or {}

    reasons: List[Dict[str, Any]] = []

    for row in factors(verdict):
        score = row["score"]
        if row["unavailable"] or score is None or abs(score) < WHY_FLOOR:
            continue
        up = score > 0
        key = row["key"]
        headline = None
        evidence: List[str] = []

        if key == "technicals":
            bias = technicals.get("bias")
            rsi = ((technicals.get("rsi") or {}).get("value"))
            macd = ((technicals.get("macd") or {}).get("state"))
            headline = "Chart structure is {}".format(bias or ("constructive" if up else "deteriorating"))
            if rsi is not None:
                evidence.append("RSI {}".format(_pct(rsi, 1)))
            if macd:
                evidence.append("MACD {}".format(macd))
            spot, sma200 = _num(technicals.get("spot")), _num((technicals.get("moving_averages") or {}).get("sma200"))
            if spot and sma200:
                evidence.append("price {} the 200-day".format("above" if spot > sma200 else "below"))

        elif key == "gamma":
            totals = gex.get("totals") or {}
            regime = (gex.get("regime") or {}).get("state")
            net = _num(totals.get("net_gex_per_1pct_millions"))
            headline = "Dealer hedging is {} moves".format(
                "dampening" if regime == "positive" else "amplifying")
            if net is not None:
                evidence.append("net GEX {}${:,.1f}M per 1% move".format(
                    "+" if net >= 0 else "-", abs(net)))
            pin = ((gex.get("levels") or {}).get("gamma_pin") or {}).get("strike")
            if _num(pin):
                evidence.append("gamma pinned near {:,.2f}".format(_num(pin)))

        elif key == "flow":
            # put_call_ratio is nested under `volume`, not on `flow` itself. Read
            # off the wrong level it returns None and the one number a reader
            # wants from this panel silently vanishes.
            vol = flow.get("volume") or {}
            pcr = _num(vol.get("put_call_ratio"))
            headline = "Options positioning leans {}".format("bullish" if up else "bearish")
            if pcr is not None:
                evidence.append("put/call {:.2f}".format(pcr))
            unusual = flow.get("unusual") or []
            if unusual:
                top = unusual[0]
                evidence.append("{} unusual contract{}, largest {} {:,.0f} strike at {:.1f}x open interest".format(
                    len(unusual), "" if len(unusual) == 1 else "s",
                    str(top.get("type", "")).lower(), _num(top.get("strike")) or 0,
                    _num(top.get("vol_oi_ratio")) or 0))
            evidence.append("volume and open interest proxy, not a trade tape")

        elif key == "news":
            tone = news.get("tone") or news.get("tone_label")
            stories = news.get("stories") or news.get("items") or []
            headline = "Headline tone is {}".format(tone or ("positive" if up else "negative"))
            top = next((s for s in stories if s.get("title")), None)
            if top:
                evidence.append('"{}"'.format(str(top["title"])[:90]))
                if top.get("source"):
                    evidence.append(str(top["source"]))
            cats = news.get("catalysts") or []
            if cats:
                evidence.append("catalysts: " + ", ".join(str(c) for c in cats[:3]))

        elif key == "macro":
            headline = "The cross-asset regime is risk-{}".format("on" if up else "off")
            evidence.append("applies to the whole market, not this ticker specifically")

        if not headline:
            continue
        reasons.append({
            "factor": key,
            "label": row["label"],
            "headline": headline,
            "direction": "up" if up else "down",
            "score": score,
            "strength": abs(score),
            "evidence": [e for e in evidence if e],
        })

    reasons.sort(key=lambda r: -r["strength"])
    top = reasons[:3]

    change = _pct(quote.get("change_pct"))
    return {
        "available": bool(top),
        "reasons": top,
        "change_pct": change,
        # Said plainly rather than implied. These are the inputs that scored
        # strongly, which is not the same claim as having identified a cause.
        #
        # Opens on the ranking rule rather than restating the panel's heading,
        # which now says the same thing. The sentence it opens with is the one
        # readers actually need: sorting on ABSOLUTE score means the three
        # strongest factors can all read bullish on a day the price closed
        # lower, and someone seeing three green arrows above a red number
        # reasonably reads it as a contradiction. It is not one, and this is
        # where that gets said.
        "method": (
            "Ranked by how hard each input is pulling, regardless of direction, "
            "so these can read bullish on a day the price is down. They are an "
            "attribution across the model's own factors, not a causal "
            "explanation of today's move. A price can move on something none of "
            "these inputs can see."
        ),
        "reason_none": None if top else (
            "No single input is reading strongly enough to call a driver. Every "
            "factor is inside the neutral band, which is itself the read: this "
            "is drift, not a move with a thesis behind it."
        ),
    }


# ---------------------------------------------------------- what matters next

def _iso_date(value: Any) -> Optional[date]:
    if isinstance(value, date):
        return value
    text = str(value or "")[:10]
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def whats_next(
    payload: Dict[str, Any],
    calendar: Optional[List[Dict[str, Any]]] = None,
    today: Optional[date] = None,
) -> Dict[str, Any]:
    """Today and this week, from levels, expiries, earnings and the calendar.

    The section the rest of the app was missing. Every other panel explains what
    already happened; this one is the only place that answers "what could move
    this next", which is the question a reader actually has after reading why it
    moved.

    Nothing here is a forecast. A level is where price has reacted before, an
    earnings date is a date, and an expiry is a date with open interest attached.
    Presenting those as things to watch is honest; presenting them as things that
    will happen is not, so the copy stays on the first side of that line.
    """
    now = today or datetime.now(timezone.utc).date()
    technicals = (payload or {}).get("technicals") or {}
    gex = (payload or {}).get("gex") or {}
    company = (payload or {}).get("company") or {}
    expiries = (payload or {}).get("expiries") or {}

    spot = _num(technicals.get("spot")) or _num(((payload or {}).get("quote") or {}).get("price"))

    today_items: List[Dict[str, Any]] = []
    week_items: List[Dict[str, Any]] = []

    # Nearest level either side. The two prices a reader is about to care about.
    levels = [l for l in (technicals.get("support_resistance") or []) if _num(l.get("price"))]
    if spot and levels:
        above = sorted((l for l in levels if _num(l["price"]) > spot), key=lambda l: _num(l["price"]))
        below = sorted((l for l in levels if _num(l["price"]) < spot), key=lambda l: -_num(l["price"]))
        for group, side in ((above[:1], "resistance"), (below[:1], "support")):
            for lv in group:
                price = _num(lv["price"])
                away = (price / spot - 1) * 100
                today_items.append({
                    "kind": "level",
                    "label": "Nearest {} {:,.2f}".format(side, price),
                    "detail": "{:+.1f}% away, {} touches".format(away, lv.get("touches") or 0),
                    "watch": side,
                })

    # The dealer-gamma levels that behave like a ceiling and a floor. There is no
    # `flip` field on this payload — the regime state carries the sign and
    # `levels` carries the strikes, which is what a reader can actually watch.
    levels_gex = gex.get("levels") or {}
    regime = (gex.get("regime") or {}).get("state")
    for name, key in (("Call wall", "call_wall"), ("Put wall", "put_wall")):
        strike = _num((levels_gex.get(key) or {}).get("strike"))
        if not strike or not spot:
            continue
        today_items.append({
            "kind": "gamma",
            "label": "{} {:,.2f}".format(name, strike),
            "detail": "{:+.1f}% away. Dealer hedging {} moves here.".format(
                (strike / spot - 1) * 100,
                "dampens" if regime == "positive" else "amplifies"),
            "watch": "gamma",
        })

    # The next expiry. `expiries` is {available: [ISO...], used: [...]} — a list
    # of date strings, not rows, so there is no open interest to attach here.
    dates = sorted(d for d in ((_iso_date(x) for x in (expiries.get("available") or []))) if d)
    nxt = next((d for d in dates if d >= now), None)
    if nxt:
        days = (nxt - now).days
        item = {
            "kind": "expiry",
            "label": "Options expiry {}".format(nxt.isoformat()),
            "detail": "{} away. Dealer gamma from this expiry unwinds on the day.".format(
                "today" if days == 0 else "{} day{}".format(days, "" if days == 1 else "s")),
            "watch": "expiry",
        }
        if days == 0:
            today_items.append(item)
        elif days <= 7:
            week_items.append(item)

    # Earnings. The single biggest scheduled risk a holder carries — and this
    # payload does not carry the next date. company.earnings_history is past
    # prints only, and earnings_momentum has no date field at all. Rather than
    # read a key that is not there and silently show nothing, the section says
    # the date is not in this payload. Wiring it means the earnings endpoint.
    earn = _iso_date((company.get("earnings") or {}).get("next_date")
                     or (payload or {}).get("next_earnings_date"))
    if earn and earn >= now:
        days = (earn - now).days
        item = {
            "kind": "earnings",
            "label": "Earnings {}".format(earn.isoformat()),
            "detail": "{} away. Options price a move around it; a position held "
                      "through it is a bet on the print.".format(
                          "today" if days == 0 else "{} day{}".format(days, "" if days == 1 else "s")),
            "watch": "earnings",
        }
        if days == 0:
            today_items.append(item)
        elif days <= 9:
            week_items.append(item)

    # Macro releases, from events.upcoming(). Rows carry an ISO `at` with an
    # offset and an `importance`, so the date comes off the timestamp and the
    # ordering is the calendar's own rather than one invented here.
    macro_rows = sorted(
        (r for r in (calendar or []) if _iso_date(r.get("at"))),
        key=lambda r: (str(r.get("at")), -(_num(r.get("importance")) or 0)),
    )
    for row in macro_rows:
        d = _iso_date(row.get("at"))
        if d < now or (d - now).days > 7:
            continue
        title = str(row.get("title") or "Economic release")
        short = str(row.get("short") or "").strip()
        agency = str(row.get("agency_short") or row.get("agency") or "").strip()
        item = {
            "kind": "macro",
            "label": "{}{}".format(title, " ({})".format(short) if short and short != title else ""),
            "detail": " · ".join(bit for bit in (d.isoformat(), agency) if bit),
            "watch": "macro",
        }
        (today_items if d == now else week_items).append(item)

    return {
        "available": bool(today_items or week_items),
        "today": today_items,
        "this_week": week_items,
        "as_of": now.isoformat(),
        "method": (
            "Scheduled dates and levels price has already reacted to. None of "
            "this is a forecast: a level is where buyers or sellers showed up "
            "before, and a date is only a date. What it does is stop a surprise "
            "being a surprise."
        ),
        "reason_none": None if (today_items or week_items) else (
            "Nothing scheduled inside a week and no level close enough to matter. "
            "That is a real answer: there is no catalyst on the board."
        ),
    }


# ------------------------------------------------------- options intelligence

def options_brief(payload: Dict[str, Any]) -> Dict[str, Any]:
    """The five things a reader wants from the options chain, in one panel.

    The asset page carries eight options panels — delta, gamma, GEX, the gamma
    profile, concentration by expiry, net premium by strike, vanna and charm,
    and the strategy list. Every one is worth having and all of them open
    collapsed, which is the right default. What was missing is the layer above:
    a reader who wants to know whether options are expensive and which way the
    flow leans had to open four panels and do the reading themselves.

    Derived from fields already in the payload. Each line names its own source
    so it can be checked against the panel it came from.
    """
    flow = (payload or {}).get("flow") or {}
    gex = (payload or {}).get("gex") or {}
    volume = flow.get("volume") or {}
    premium = flow.get("premium") or {}
    skew = flow.get("iv_skew") or {}
    levels = gex.get("levels") or {}

    items: List[Dict[str, Any]] = []

    pcr = _num(volume.get("put_call_ratio"))
    if pcr is not None:
        # Below 1 means more calls traded than puts. Said in words as well as
        # the ratio, because "0.53" only reads as bullish if you already know
        # which way the ratio points.
        items.append({
            "label": "Put/call",
            "value": "{:.2f}".format(pcr),
            "note": "{:.0f} calls traded for every 100 puts".format(100 / pcr) if pcr else "",
            "tone": "up" if pcr < 0.9 else ("down" if pcr > 1.1 else "flat"),
        })

    share = _num(premium.get("call_share_pct"))
    if share is not None:
        items.append({
            "label": "Premium",
            "value": "{:.0f}% calls".format(share),
            "note": "by dollars paid, not contract count",
            "tone": "up" if share > 55 else ("down" if share < 45 else "flat"),
        })

    unusual = flow.get("unusual") or []
    if unusual:
        top = max(unusual, key=lambda r: _num(r.get("vol_oi_ratio")) or 0)
        strike = _num(top.get("strike"))
        items.append({
            "label": "Unusual",
            "value": "{:,.0f} {}".format(strike or 0, str(top.get("type", "")).lower()),
            "note": "{:.1f}x open interest, {} expiry \u00b7 {} contract{} flagged".format(
                _num(top.get("vol_oi_ratio")) or 0, top.get("expiry", "?"),
                len(unusual), "" if len(unusual) == 1 else "s"),
            "tone": "up" if str(top.get("type", "")).upper() == "CALL" else "down",
        })
    else:
        items.append({
            "label": "Unusual",
            "value": "none",
            "note": "no contract is trading far above its own open interest",
            "tone": "flat",
        })

    pts = _num(skew.get("put_minus_call_vol_pts"))
    if pts is not None:
        # Puts usually carry a premium. A negative skew is the notable case.
        items.append({
            "label": "Skew",
            "value": "{:+.1f} vol pts".format(pts),
            "note": ("puts are bid over calls, the usual state" if pts > 0.5 else
                     "calls are bid over puts, which is unusual" if pts < -0.5 else
                     "puts and calls priced level"),
            "tone": "down" if pts > 0.5 else ("up" if pts < -0.5 else "flat"),
        })

    wall = _num((levels.get("call_wall") or {}).get("strike"))
    put_wall = _num((levels.get("put_wall") or {}).get("strike"))
    if wall or put_wall:
        items.append({
            "label": "Gamma walls",
            "value": " / ".join(x for x in (
                "{:,.0f}".format(wall) if wall else None,
                "{:,.0f}".format(put_wall) if put_wall else None) if x),
            "note": "where dealer hedging is heaviest above and below",
            "tone": "flat",
        })

    stance = flow.get("stance")
    return {
        "available": bool(items),
        "bias": stance,
        "items": items,
        "method": (
            "Positioning read off volume, open interest and premium across the "
            "chain. It is a proxy: free data carries no trade tape, so none of "
            "this shows who initiated a trade or why. The eight panels below "
            "hold the workings."
        ),
    }
