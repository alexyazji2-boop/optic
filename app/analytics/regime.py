"""Index regime score: one number for "what kind of tape is this".

The terminal scores individual names but never scored the market itself, so a
reader could see a +48 setup with no indication that the index behind it was
rolling over. A good setup in a bad tape is a worse setup, and that context was
only available by reading four panels and doing the synthesis by eye.

Built from the daily brief's own overview — index levels, sector performance and
breadth — so it costs no extra data. That is a deliberate boundary: this is an
*index* regime read, from index and breadth behaviour. The Macro tab's risk score
is a different instrument, built from credit, rates, the dollar and commodities,
and the two are meant to be read together rather than merged. When they disagree,
that disagreement is information.

Scored the same way as the ticker composite: each input lands on -100..+100,
weights are renormalised over whatever is available, and a missing input
redistributes rather than counting as zero.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

# Weights. Trend leads because it is the thing being asked about; breadth is next
# because an index carried by five names is a different regime from the same index
# carried by four hundred.
WEIGHTS = {
    "trend": 0.30,
    "breadth": 0.25,
    "volatility": 0.20,
    "participation": 0.15,
    "leadership": 0.10,
}

# Regime bands on the composite. Wider than the ticker bands: an index moves less
# than a single stock, so ±30 on this scale is already a decided tape.
#
# The labels avoid "risk-on / risk-off". That pair is desk shorthand and means
# nothing to a reader who has not met it, while "supportive" and "defensive" say
# the same thing in words that describe the effect on a position: is the tape
# helping a long, or working against it. The method note still names the jargon
# once, so anyone who knows the term can map across.
VERY_SUPPORTIVE, SUPPORTIVE, DEFENSIVE, VERY_DEFENSIVE = 40.0, 12.0, -12.0, -40.0

# VIX levels that bracket "calm" and "stressed". 20 is the long-run median-ish
# line traders actually use; 30 is where hedging demand stops being routine.
VIX_CALM, VIX_STRESSED = 16.0, 30.0

# Share of sectors above their 200-day that counts as healthy participation.
BREADTH_HEALTHY, BREADTH_WEAK = 65.0, 35.0


def _num(value: Any) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return None if out != out or out in (float("inf"), float("-inf")) else out


def _clip(value: float) -> float:
    return max(-100.0, min(100.0, value))


def _by_symbol(rows: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    return {(r.get("symbol") or "").upper(): r for r in (rows or []) if isinstance(r, dict)}


def score(overview: Dict[str, Any]) -> Dict[str, Any]:
    """An index regime read from the brief's overview block."""
    groups = (overview or {}).get("groups") or {}
    indices = _by_symbol(groups.get("indices") or [])
    sectors = groups.get("sectors") or []
    if not indices:
        return {"available": False}

    spy = indices.get("SPY") or {}
    qqq = indices.get("QQQ") or {}
    iwm = indices.get("IWM") or {}
    vix = indices.get("^VIX") or indices.get("VIX") or {}

    components: Dict[str, Optional[float]] = {}
    notes: List[str] = []

    # -- trend: where the index has been over a week and a month ---------------
    spy_week, spy_month = _num(spy.get("week")), _num(spy.get("month"))
    if spy_week is not None or spy_month is not None:
        parts = [p for p in (spy_week, spy_month) if p is not None]
        # A month is the anchor; 5% over a month is a strong trend, so scale to that.
        raw = sum(parts) / len(parts)
        components["trend"] = _clip(raw / 5.0 * 100.0)
        notes.append("S&P {:+.1f}% over a month and {:+.1f}% over a week".format(
            spy_month if spy_month is not None else 0.0,
            spy_week if spy_week is not None else 0.0))

    # -- breadth: how many sectors are participating --------------------------
    breadth = _num((overview or {}).get("sector_breadth_pct"))
    if breadth is not None:
        # Map the healthy/weak band onto the score linearly around the midpoint.
        mid = (BREADTH_HEALTHY + BREADTH_WEAK) / 2.0
        span = (BREADTH_HEALTHY - BREADTH_WEAK) / 2.0
        components["breadth"] = _clip((breadth - mid) / span * 100.0)
        notes.append("{:.0f}% of sectors above their 200-day".format(breadth))

    # -- volatility: level, and which way it moved today ----------------------
    vix_last, vix_day = _num(vix.get("last")), _num(vix.get("day"))
    if vix_last is not None:
        # Low VIX is risk-on. Invert and scale across the calm..stressed band.
        mid = (VIX_CALM + VIX_STRESSED) / 2.0
        span = (VIX_STRESSED - VIX_CALM) / 2.0
        level = _clip((mid - vix_last) / span * 100.0)
        # A sharp rise matters even from a low base, so nudge on the day move.
        if vix_day is not None:
            level = _clip(level - vix_day * 1.5)
        components["volatility"] = level
        notes.append("VIX {:.1f}{}".format(
            vix_last, " ({:+.1f}% today)".format(vix_day) if vix_day is not None else ""))

    # -- participation: are small caps confirming? ----------------------------
    iwm_month, spy_m = _num(iwm.get("month")), spy_month
    if iwm_month is not None and spy_m is not None:
        spread = iwm_month - spy_m
        # Small caps leading is a genuine risk-on tell; lagging badly is a warning.
        components["participation"] = _clip(spread / 4.0 * 100.0)
        notes.append("small caps {} the S&P by {:.1f} points over a month".format(
            "leading" if spread >= 0 else "lagging", abs(spread)))

    # -- leadership: is the advance broad or concentrated? --------------------
    day_moves = [_num(r.get("day")) for r in sectors]
    day_moves = [d for d in day_moves if d is not None]
    if len(day_moves) >= 5:
        up = sum(1 for d in day_moves if d > 0)
        share = up / len(day_moves) * 100.0
        components["leadership"] = _clip((share - 50.0) * 2.0)
        notes.append("{} of {} sectors higher today".format(up, len(day_moves)))

    usable = {k: v for k, v in components.items() if v is not None}
    if not usable:
        return {"available": False}

    total_weight = sum(WEIGHTS[k] for k in usable)
    composite = sum(usable[k] * WEIGHTS[k] for k in usable) / total_weight

    # The plain line describes the TAPE, not the reader's relationship to it.
    # It used to say "the market is behind you", which reads two opposite ways —
    # behind you as in supporting you, or behind you as in trailing — and
    # addresses a position the terminal knows nothing about. Saying what the
    # market is actually doing is both clearer and a claim this module can
    # support; what it means for any given setup is the next line's job.
    if composite >= VERY_SUPPORTIVE:
        label, stance = "supportive", "strongly supportive"
        plain = "Broad uptrend, and most of the market is taking part"
        effect = ("Conditions favour buyers: the trend, the breadth and the "
                  "volatility reading all point the same way.")
    elif composite >= SUPPORTIVE:
        label, stance = "supportive", "leaning supportive"
        plain = "Drifting higher, without much conviction behind it"
        effect = ("Mildly favours buyers, but not enough to carry a weak setup on "
                  "its own.")
    elif composite <= VERY_DEFENSIVE:
        label, stance = "defensive", "strongly defensive"
        plain = "Broad downtrend, and most of the market is falling with it"
        effect = ("Conditions favour sellers. A long setup here is going against "
                  "the trend, the breadth and the volatility reading at once.")
    elif composite <= DEFENSIVE:
        label, stance = "defensive", "leaning defensive"
        plain = "Drifting lower, without much conviction behind it"
        effect = ("Mildly favours sellers. A long setup needs to be strong on its "
                  "own merits.")
    else:
        label, stance = "mixed", "mixed"
        plain = "Going sideways — no clear direction either way"
        effect = ("Neither side has the tape. Individual setups have to stand on "
                  "their own rather than on the market's direction.")

    # Which inputs disagree with the headline. This is the useful part: a +20 with
    # breadth at -60 is a very different tape from a +20 with everything at +20.
    conflicts = []
    for key, value in usable.items():
        if composite > SUPPORTIVE and value <= -25:
            conflicts.append("{} disagrees at {:+.0f}".format(key, value))
        elif composite < DEFENSIVE and value >= 25:
            conflicts.append("{} disagrees at {:+.0f}".format(key, value))

    agree = sum(1 for v in usable.values()
                if (v > 0) == (composite > 0) or abs(v) < 10)
    return {
        "available": True,
        "score": round(composite, 1),
        "regime": label,
        "stance": stance,
        "plain": plain,
        "effect": effect,
        "components": {k: round(v, 1) for k, v in usable.items()},
        "weights": {k: round(WEIGHTS[k] * 100 / total_weight, 1) for k in usable},
        "agreement_pct": round(agree / len(usable) * 100.0, 0),
        "conflicts": conflicts,
        "notes": notes,
        "scale_note": (
            "Supportive above +12, strongly so above +40, and the mirror image below. "
            "An index moves less than a single stock, so these bands are wider than "
            "the per-ticker composite's."
        ),
        "method": (
            "Index trend, sector breadth, the VIX level and its move, whether small "
            "caps are confirming, and how many sectors are participating today — each "
            "scored -100 to +100 and weighted. Weights renormalise over whatever is "
            "available, so a missing input redistributes rather than counting as zero. "
            "This is an index and breadth read; the Macro tab's risk score is a "
            "separate cross-asset instrument built from credit, rates, the dollar and "
            "commodities. Where the two disagree, that is worth knowing rather than "
            "averaging away. \"Supportive\" and \"defensive\" are what a desk would call "
            "risk-on and risk-off."
        ),
    }
