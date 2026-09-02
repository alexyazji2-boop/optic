"""The bull case and the bear case for a loaded ticker.

Assembled mechanically from panels the app has already computed — not written by
a model. Every argument carries the number that triggered it, so a reader can
check the claim against the panel it came from rather than taking the sentence on
trust. That also makes it free and instant: no API call, no per-load cost, and
the same inputs always produce the same two lists.

The deliberate limitation: this summarises *what the data says today*. It has no
view on the business, the product, or anything not in a price series, a filing or
a chain. A real bull case for a company involves things this cannot see, and the
UI says so.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

# Strength ranks how much weight an argument carries in the summary. It orders
# the list and nothing else — there is no scoring here that feeds the composite.
STRONG, MEDIUM, LIGHT = 3, 2, 1

# A composite component is only worth citing once it is clearly off neutral.
# Below this it is noise dressed up as an argument.
COMPONENT_BAND = 25.0

# RSI regions. 50-70 is momentum with room; above 70 is extended and becomes a
# bear-side caution rather than a bull-side strength.
RSI_STRONG, RSI_OVERBOUGHT, RSI_OVERSOLD = 50.0, 70.0, 30.0

# Implied vs realized. Below 0.9 options are cheap against recent movement, above
# 1.35 they are rich — the same bands the entry plan already uses.
IV_CHEAP, IV_RICH = 0.9, 1.35

# Band width percentile above which price is stretched versus its own history.
BANDWIDTH_EXTENDED = 80.0

# Earnings inside this many days dominates a swing thesis regardless of setup.
EARNINGS_SOON_DAYS = 14


def _num(value: Any) -> Optional[float]:
    """Anything JSON-ish to a float, or None. Guards every threshold below."""
    if value is None or isinstance(value, bool):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if out == out and out not in (float("inf"), float("-inf")) else None


def _arg(claim: str, detail: str, strength: int, source: str) -> Dict[str, Any]:
    return {"claim": claim, "detail": detail, "strength": strength, "source": source}


def _pct(value: Optional[float], digits: int = 1) -> str:
    return "—" if value is None else f"{value:.{digits}f}%"


def _usd(value: Optional[float]) -> str:
    return "—" if value is None else f"${value:,.2f}"


# --------------------------------------------------------------- the two cases

def build(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Both sides of the argument for one ticker.

    Reads the assembled `/api/ticker` payload rather than recomputing anything,
    so the cases cannot drift from the panels they cite.
    """
    if not isinstance(payload, dict):
        return {"available": False}

    verdict = payload.get("verdict") or {}
    tech = payload.get("technicals") or {}
    struct = payload.get("structure") or {}
    gex = payload.get("gex") or {}
    flow = payload.get("flow") or {}
    news = payload.get("news") or {}
    company = payload.get("company") or {}
    em = payload.get("earnings_momentum") or {}
    iv = ((payload.get("entry_plan") or {}).get("iv_context")) or {}
    quote = payload.get("quote") or {}

    bull: List[Dict[str, Any]] = []
    bear: List[Dict[str, Any]] = []

    # -- the composite's own components ------------------------------------
    components = verdict.get("components") or {}
    labels = {
        "technicals": "Chart structure",
        "gamma": "Dealer positioning",
        "flow": "Options flow",
        "news": "News tone",
        "macro": "Macro backdrop",
    }
    for key, label in labels.items():
        score = _num(components.get(key))
        if score is None:
            continue
        if score >= COMPONENT_BAND:
            bull.append(_arg(
                f"{label} is constructive",
                f"Scores {score:+.0f} out of ±100 in the composite.",
                STRONG if score >= 60 else MEDIUM, "Composite"))
        elif score <= -COMPONENT_BAND:
            bear.append(_arg(
                f"{label} is working against it",
                f"Scores {score:+.0f} out of ±100 in the composite.",
                STRONG if score <= -60 else MEDIUM, "Composite"))

    # -- trend and moving averages -----------------------------------------
    spot = _num(tech.get("spot")) or _num(quote.get("price"))
    mas = tech.get("moving_averages") or {}
    # Each moving average is a dict — {value, distance_pct, position, slope} —
    # not a bare number. Reading it as a float returns None and the rule below
    # silently never fires, which is worse than an error because the case just
    # quietly omits an argument.
    sma200_block = mas.get("sma200") or {}
    sma200 = _num(sma200_block.get("value"))
    gap_pct = _num(sma200_block.get("distance_pct"))
    if spot is not None and sma200:
        gap = gap_pct if gap_pct is not None else (spot / sma200 - 1.0) * 100.0
        if gap > 0:
            bull.append(_arg(
                "Trading above the 200-day average",
                f"{_usd(spot)} is {_pct(gap)} above the 200-day at {_usd(sma200)} — "
                "the line most long-term trend followers watch.",
                MEDIUM, "Technicals"))
        else:
            bear.append(_arg(
                "Trading below the 200-day average",
                f"{_usd(spot)} is {_pct(abs(gap))} below the 200-day at {_usd(sma200)}.",
                MEDIUM, "Technicals"))

    stack = struct.get("ema_stack") or {}
    if stack.get("bullish_stack"):
        bull.append(_arg(
            "Fast averages are stacked bullish",
            f"Price above the 9, 21 and 50-day EMAs in order "
            f"({_usd(_num(stack.get('ema9')))} · {_usd(_num(stack.get('ema21')))} · "
            f"{_usd(_num(stack.get('ema50')))}) — every timeframe agrees on direction.",
            STRONG, "Structure"))
    elif stack.get("bearish_stack"):
        bear.append(_arg(
            "Fast averages are stacked bearish",
            f"Price below the 9, 21 and 50-day EMAs in order "
            f"({_usd(_num(stack.get('ema9')))} · {_usd(_num(stack.get('ema21')))} · "
            f"{_usd(_num(stack.get('ema50')))}).",
            STRONG, "Structure"))

    # -- momentum -----------------------------------------------------------
    rsi = _num((tech.get("rsi") or {}).get("value"))
    if rsi is not None:
        if RSI_STRONG <= rsi < RSI_OVERBOUGHT:
            bull.append(_arg(
                "Momentum is positive without being stretched",
                f"RSI {rsi:.0f} — above the midline with room before the "
                f"{RSI_OVERBOUGHT:.0f} overbought marker.",
                MEDIUM, "Technicals"))
        elif rsi >= RSI_OVERBOUGHT:
            bear.append(_arg(
                "Momentum is overbought",
                f"RSI {rsi:.0f} is above {RSI_OVERBOUGHT:.0f}, where advances more often "
                "pause or retrace.",
                MEDIUM, "Technicals"))
        elif rsi <= RSI_OVERSOLD:
            bull.append(_arg(
                "Oversold enough to bounce",
                f"RSI {rsi:.0f} is below {RSI_OVERSOLD:.0f} — stretched to the downside, "
                "which is where reversals start (and where falling knives also live).",
                LIGHT, "Technicals"))

    macd_state = (tech.get("macd") or {}).get("state")
    if isinstance(macd_state, str) and macd_state:
        if "bull" in macd_state.lower():
            bull.append(_arg("MACD is above its signal line",
                             f"Momentum read: {macd_state}.", LIGHT, "Technicals"))
        elif "bear" in macd_state.lower():
            bear.append(_arg("MACD is below its signal line",
                             f"Momentum read: {macd_state}.", LIGHT, "Technicals"))

    # -- where price sits versus traded volume ------------------------------
    vp = struct.get("volume_profile") or {}
    if vp.get("available"):
        location = vp.get("location")
        if location == "above value":
            bull.append(_arg(
                "Broken above the volume shelf",
                f"Price is above the value area "
                f"({_usd(_num(vp.get('val')))}–{_usd(_num(vp.get('vah')))}) — "
                "no overhead supply from recent trade.",
                MEDIUM, "Structure"))
        elif location == "below value":
            bear.append(_arg(
                "Sitting under the volume shelf",
                f"Price is below the value area "
                f"({_usd(_num(vp.get('val')))}–{_usd(_num(vp.get('vah')))}), "
                "which becomes overhead supply on any rally.",
                MEDIUM, "Structure"))

    # -- volatility ---------------------------------------------------------
    band = struct.get("bandwidth") or {}
    band_pct = _num(band.get("percentile"))
    if band_pct is not None and band_pct >= BANDWIDTH_EXTENDED:
        bear.append(_arg(
            "Already extended, not coiled",
            f"Band width sits in the {band_pct:.0f}th percentile of its own history — "
            "the easy part of the move has usually happened by here.",
            MEDIUM, "Structure"))

    ratio = _num(iv.get("iv_to_realised_ratio"))
    if ratio is not None:
        if ratio <= IV_CHEAP:
            bull.append(_arg(
                "Options are cheap against actual movement",
                f"Implied vol is {ratio:.2f}× realized — the market is pricing less "
                "movement than the stock has been delivering, which favours buying "
                "premium over selling it.",
                MEDIUM, "Volatility"))
        elif ratio >= IV_RICH:
            bear.append(_arg(
                "Options are expensive against actual movement",
                f"Implied vol is {ratio:.2f}× realized — you are paying up for movement "
                "the stock has not been delivering, and long premium decays if it "
                "does not arrive.",
                MEDIUM, "Volatility"))

    # -- dealer positioning --------------------------------------------------
    regime = (gex.get("regime") or {}).get("state")
    if regime == "positive":
        bear.append(_arg(
            "Dealer hedging dampens breakouts",
            "Net gamma is positive, so market makers hedge against direction — ranges "
            "hold and a breakout needs a catalyst to overcome the drag.",
            LIGHT, "Gamma"))
    elif regime == "negative":
        bull.append(_arg(
            "Dealer hedging amplifies moves",
            "Net gamma is negative, so market makers hedge with direction — moves "
            "extend rather than fade. It cuts both ways.",
            LIGHT, "Gamma"))

    # -- earnings ------------------------------------------------------------
    days = _num(news.get("days_to_earnings"))
    if days is not None and 0 <= days <= EARNINGS_SOON_DAYS:
        bear.append(_arg(
            "Earnings land inside the trade",
            f"Results are {days:.0f} days away. A single report can override every "
            "other input here, and implied vol usually collapses straight after it.",
            STRONG, "Earnings"))

    if em.get("available"):
        read = (em.get("read") or "").lower()
        if read == "improving":
            bull.append(_arg(
                "Fundamental momentum is improving",
                "Estimate revisions and surprise history are trending up. Not part of "
                "the composite, but it carries signal over a few weeks.",
                MEDIUM, "Fundamentals"))
        elif read == "deteriorating":
            bear.append(_arg(
                "Fundamental momentum is deteriorating",
                "Estimate revisions and surprise history are trending down.",
                MEDIUM, "Fundamentals"))

    # -- short interest ------------------------------------------------------
    si = company.get("short_interest") or {}
    if si.get("available"):
        float_pct = _num(si.get("percent_of_float"))
        cover = _num(si.get("days_to_cover"))
        if float_pct is not None and float_pct >= 0.10 and cover is not None and cover >= 3:
            bull.append(_arg(
                "Crowded short base could squeeze",
                f"{float_pct * 100:.1f}% of the float is short at {cover:.1f} days to "
                "cover — forced buying if it turns.",
                MEDIUM, "Short interest"))

    # -- the composite's own disagreements ----------------------------------
    # All of them, not a sample. These used to be repeated as callouts in the
    # verdict panel; that panel no longer shows them, so anything dropped here
    # is dropped from the page.
    for conflict in (verdict.get("conflicts") or []):
        if isinstance(conflict, str) and conflict.strip():
            bear.append(_arg("The inputs disagree", conflict.strip(), LIGHT, "Composite"))

    bull.sort(key=lambda a: -a["strength"])
    bear.sort(key=lambda a: -a["strength"])

    bull_weight = sum(a["strength"] for a in bull)
    bear_weight = sum(a["strength"] for a in bear)
    if bull_weight > bear_weight * 1.4:
        balance = "the bull case is better supported"
    elif bear_weight > bull_weight * 1.4:
        balance = "the bear case is better supported"
    else:
        balance = "the two sides are roughly balanced"

    return {
        "available": bool(bull or bear),
        "bull": bull,
        "bear": bear,
        "bull_weight": bull_weight,
        "bear_weight": bear_weight,
        "balance": balance,
        "method": (
            "Assembled from the panels on this page — each line cites the number that "
            "triggered it. Nothing here is written by a model, and nothing weighs the "
            "business itself: this is what the price, the chain and the filings say "
            "today, which is only part of any real argument for or against a company."
        ),
    }
