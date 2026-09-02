"""A fear-and-greed reading, built from prices this terminal already fetches.

CNN's index is the well-known one, and this is deliberately *not* a claim to
reproduce it. Three of its seven inputs — the McClellan volume summation, NYSE
52-week highs against lows, and a market-wide equity put/call ratio — need
exchange breadth and options data that free sources do not carry. Publishing a
number under the same name while quietly substituting different inputs would be
the worst of both worlds: familiar enough to be trusted, different enough to be
wrong. So this is Optic's own reading, it says so, and it lists every input.

Five components, each scored 0–100 where 50 is neutral, then averaged over
whichever ones are available:

  momentum      SPY against its own 125-day average.
  volatility    VIX against its 50-day average, inverted — calm is greed.
  breadth       How many sector ETFs are above their 200-day.
  safe_haven    Stocks against long bonds over a month. Money leaving Treasuries
                for equities is the classic risk-appetite tell.
  junk_demand   High-yield against investment-grade credit. When buyers reach
                for the riskier coupon, that is greed showing up in a market
                that is usually less sentimental than equities.

**The history is computed, not stored.** Every input is derived from a daily
price series, so the same formulas evaluated on a series truncated to a week ago
give the reading as it stood a week ago. That matters: the alternative is a
database that only starts the day the feature ships, and a "vs last month"
figure that is blank until a month has passed or, worse, invented.

**Each component is scored against its own recent history, not against a
hand-picked constant.** The first version mapped each raw metric onto 0-100
through a fixed saturation width I chose by eye — "SPY 10% above its 125-day
average is maximum greed" and so on. Measured over two years, that gauge had a
median of 64 and sat in Greed or Extreme Greed 69% of the time, which makes the
midpoint meaningless: if the needle is almost always right of centre, being
right of centre says nothing. Every component is now scored by where today's
reading falls within its own two-year distribution, so 50 is genuinely the
middle of this market's behaviour and an extreme reading is extreme by
construction rather than by my guess at a constant.

The tradeoff is explicit: this measures sentiment *relative to the last two
years*, so a market that spent the whole window elevated will still print
readings around 50. That is a real limitation and the panel says so.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .sectors import SECTORS

# Everything this needs, in one batch.
SPY, VIX, TLT, HYG, LQD = "SPY", "^VIX", "TLT", "HYG", "LQD"
IWM, XLK, XLU, XLY, XLP = "IWM", "XLK", "XLU", "XLY", "XLP"

# Offense-versus-defence pairs. Each is a ratio the market itself prices, and
# together they answer a question none of the other inputs do: not whether
# equities are being bought, but WHICH equities. A tape where technology beats
# utilities and small caps beat the index is risk-seeking in a way a rising
# index alone does not establish.
RISK_PAIRS = [(XLK, XLU), (XLY, XLP), (IWM, SPY)]

SYMBOLS = list(dict.fromkeys(
    [SPY, VIX, TLT, HYG, LQD, IWM, XLK, XLU, XLY, XLP]
    + [s["symbol"] for s in SECTORS]))

# Look-backs, in sessions.
MOMENTUM_WINDOW = 125
VIX_WINDOW = 50
BREADTH_WINDOW = 200
CREDIT_WINDOW = 21

# How far back the calibration window reaches, and the fewest observations a
# percentile needs before it means anything. Two years is long enough to contain
# both a drawdown and a rally, short enough to describe the current regime.
CALIBRATION_DAYS = 504
MIN_HISTORY = 120

# Where each component saturates. Now only used for the raw-value helpers; the
# published score comes from the percentile of the raw value, not from these. A component that pegs at 0 or 100 for ordinary
# market moves carries no information, so these are set wide enough that the
# middle of the range is where readings normally sit.
MOMENTUM_FULL_PCT = 10.0      # SPY this far above its 125-day average is max greed
VIX_FULL_PCT = 35.0           # VIX this far from its 50-day average saturates
SAFE_HAVEN_FULL_PCT = 8.0     # stocks beating bonds by this much over a month
JUNK_FULL_PCT = 3.0           # high-yield beating investment-grade by this much

# Labels. The bands are CNN's, which are widely enough known that using different
# ones would be gratuitous.
BANDS = [
    (25.0, "Extreme Fear"),
    (45.0, "Fear"),
    (55.0, "Neutral"),
    (75.0, "Greed"),
    (100.1, "Extreme Greed"),
]

# Weights. Not flat, and the ordering is the argument: momentum is the thing
# being asked about, breadth decides whether to believe it, volatility is how
# much the market is paying to hedge it. Risk appetite and the two credit legs
# are corroborating evidence — genuinely informative, but a sentiment gauge that
# let the high-yield spread outvote the index would be measuring the wrong thing.
WEIGHTS = {
    "momentum": 25.0,
    "breadth": 20.0,
    "volatility": 20.0,
    "risk_appetite": 15.0,
    "safe_haven": 10.0,
    "junk_demand": 10.0,
}

COMPONENT_LABELS = {
    "momentum": "Market momentum",
    "breadth": "Market breadth",
    "volatility": "Market volatility",
    "risk_appetite": "Risk appetite",
    "safe_haven": "Safe-haven demand",
    "junk_demand": "Junk-bond demand",
}

# The question each input answers, in the words a reader would use. A component
# labelled only "junk-bond demand" tells someone who already knows what it means
# what it means.
COMPONENT_QUESTIONS = {
    "momentum": "Is the overall market trending up or down right now?",
    "breadth": "How much of the market is joining the move?",
    "volatility": "How calm or nervous is the market?",
    "risk_appetite": "Are investors buying aggressive assets or defensive ones?",
    "safe_haven": "Is money moving into stocks or into government bonds?",
    "junk_demand": "Are credit buyers reaching for risk or backing away from it?",
}

# What a high, middling or low reading on each input actually means. Written per
# component rather than generically, because "high" means something different
# for volatility (calm) than for momentum (trending).
COMPONENT_READINGS = {
    "momentum": ("Index is trending above its recent averages — uptrend intact.",
                 "Index is near its own averages — no strong trend either way.",
                 "Index is below its recent averages — the trend is against buyers."),
    "breadth": ("Most sectors are above trend — broad support behind the move.",
                "Participation is mixed — the move is not fully confirmed.",
                "Few sectors are above trend — the market is being carried by a minority."),
    "volatility": ("Volatility is low relative to its own recent norm — the market is calm.",
                   "Volatility is near typical levels.",
                   "Volatility is elevated against its own norm — hedging demand has picked up."),
    "risk_appetite": ("Offensive assets are leading defensive ones — investors are reaching for risk.",
                      "No clear leadership between offense and defense.",
                      "Defensive assets are leading — investors are protecting rather than reaching."),
    "safe_haven": ("Stocks are well ahead of long bonds — money is leaving safety.",
                   "Stocks and bonds are close — no strong preference.",
                   "Long bonds are outpacing stocks — money is moving toward safety."),
    "junk_demand": ("High-yield is beating investment-grade — credit buyers are reaching for risk.",
                    "Credit spreads are behaving normally.",
                    "Investment-grade is beating high-yield — credit is backing away from risk."),
}

COMPONENT_NOTES = {
    "momentum": "The S&P 500 against its own 125-day average. Well above it is greed; "
                "below it is fear.",
    "volatility": "The VIX against its 50-day average, inverted. A calm market that has "
                  "become calmer is greed; a sudden jump in hedging demand is fear.",
    "breadth": "How many of the eleven sector funds are above their 200-day average. A "
               "rally the whole market joins is different from one five names carry.",
    "safe_haven": "Stocks against long-dated Treasuries over the past month. Money "
                  "leaving bonds for equities is the classic risk-appetite tell.",
    "junk_demand": "High-yield credit against investment-grade. When buyers reach for "
                   "the riskier coupon, that is greed appearing in a market usually "
                   "less sentimental than equities.",
    "risk_appetite": "Three offense-versus-defence pairs — technology against utilities, "
                     "discretionary against staples, small caps against the index. Which "
                     "kind of equity is being bought, rather than whether equities are.",
}

# Bumped whenever the inputs or the scoring change, so a reading can be placed
# against the method that produced it. v1 used fixed saturation widths and had a
# median of 64; v2 scores each input against its own two-year distribution.
METHODOLOGY_VERSION = "v2"


def _num(value: Any) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return None if out != out or out in (float("inf"), float("-inf")) else out


def _clip(value: float) -> float:
    return max(0.0, min(100.0, value))


def _scale(spread_pct: Optional[float], full: float) -> Optional[float]:
    """Map a percentage spread onto 0-100 with 50 as neutral.

    Retained for the raw-to-bounded conversion used where a component has a
    natural scale, but no longer the primary path — see _percentile.
    """
    if spread_pct is None:
        return None
    return _clip(50.0 + (spread_pct / full) * 50.0)


def _percentile(value: Optional[float], history: List[float]) -> Optional[float]:
    """Where `value` sits within its own history, as 0-100.

    This is what makes 50 mean something. A fixed saturation width encodes a
    guess about how far a metric "should" travel; a percentile encodes what it
    has actually done, so the midpoint is the median of real behaviour rather
    than the middle of a range I invented.
    """
    if value is None:
        return None
    sample = [h for h in history if h is not None]
    if len(sample) < MIN_HISTORY:
        return None
    below = sum(1 for h in sample if h < value)
    ties = sum(1 for h in sample if h == value)
    return _clip((below + 0.5 * ties) / len(sample) * 100.0)


def _closes(frames: Dict[str, Any], symbol: str, offset: int):
    """Close series for `symbol`, truncated `offset` sessions back."""
    frame = frames.get(symbol)
    if frame is None or getattr(frame, "empty", True):
        return None
    series = frame["Close"].dropna()
    if offset:
        series = series.iloc[:-offset] if offset < len(series) else None
    return series if series is not None and len(series) else None


def _vs_average(series, window: int) -> Optional[float]:
    if series is None or len(series) < window:
        return None
    last, avg = _num(series.iloc[-1]), _num(series.rolling(window).mean().iloc[-1])
    if last is None or avg is None or avg <= 0:
        return None
    return (last / avg - 1.0) * 100.0


def _return_pct(series, bars: int) -> Optional[float]:
    if series is None or len(series) <= bars:
        return None
    prev, last = _num(series.iloc[-1 - bars]), _num(series.iloc[-1])
    if prev is None or last is None or prev <= 0:
        return None
    return (last / prev - 1.0) * 100.0


def _raw_series(frames: Dict[str, Any]) -> Dict[str, Any]:
    """Every component's raw metric as a full series, computed once.

    Vectorised deliberately. The percentile of today's reading needs the whole
    distribution behind it, and recomputing that per look-back would do the same
    arithmetic four times over.
    """
    out: Dict[str, Any] = {}

    spy = _closes(frames, SPY, 0)
    if spy is not None and len(spy) > MOMENTUM_WINDOW:
        out["momentum"] = spy / spy.rolling(MOMENTUM_WINDOW).mean() - 1.0

    vix = _closes(frames, VIX, 0)
    if vix is not None and len(vix) > VIX_WINDOW:
        # Inverted at source: a VIX below its own average is greed, so the raw
        # metric is negated here and every downstream percentile reads correctly.
        out["volatility"] = -(vix / vix.rolling(VIX_WINDOW).mean() - 1.0)

    # Breadth: share of sector funds above their 200-day, as a series.
    flags = []
    for entry in SECTORS:
        series = _closes(frames, entry["symbol"], 0)
        if series is None or len(series) <= BREADTH_WINDOW:
            continue
        flags.append((series > series.rolling(BREADTH_WINDOW).mean()).astype(float))
    if flags:
        import pandas as pd
        out["breadth"] = pd.concat(flags, axis=1).mean(axis=1) * 100.0

    def _spread(a_sym, b_sym):
        a, b = _closes(frames, a_sym, 0), _closes(frames, b_sym, 0)
        if a is None or b is None:
            return None
        ar = a / a.shift(CREDIT_WINDOW) - 1.0
        br = b / b.shift(CREDIT_WINDOW) - 1.0
        joined = (ar - br).dropna()
        return joined * 100.0 if len(joined) else None

    # Risk appetite: the mean of three offense/defence ratio returns. Averaged
    # rather than summed so a missing pair does not read as zero appetite.
    pair_series = []
    for offense, defence in RISK_PAIRS:
        spread = _spread(offense, defence)
        if spread is not None:
            pair_series.append(spread)
    if pair_series:
        import pandas as pd
        out["risk_appetite"] = pd.concat(pair_series, axis=1).mean(axis=1)

    sh = _spread(SPY, TLT)
    if sh is not None:
        out["safe_haven"] = sh
    jd = _spread(HYG, LQD)
    if jd is not None:
        out["junk_demand"] = jd
    return out


def _at(series, offset: int) -> Optional[float]:
    """The series value `offset` sessions back."""
    if series is None:
        return None
    clean = series.dropna()
    if len(clean) <= offset:
        return None
    return _num(clean.iloc[-1 - offset])


def _window(series, offset: int) -> List[float]:
    """The calibration window ending `offset` sessions back."""
    if series is None:
        return []
    clean = series.dropna()
    if len(clean) <= offset:
        return []
    upto = clean.iloc[:len(clean) - offset] if offset else clean
    return [float(x) for x in upto.tail(CALIBRATION_DAYS)]


def _score_at(frames_or_raw: Dict[str, Any], offset: int = 0) -> Optional[Dict[str, Any]]:
    """The reading as it stood `offset` sessions ago.

    Accepts either the frames dict or a precomputed raw-series dict, so callers
    that score several look-backs can build the series once.
    """
    raw = frames_or_raw
    if raw and any(k in raw for k in (SPY, VIX)):     # looks like frames
        raw = _raw_series(frames_or_raw)

    components: Dict[str, Optional[float]] = {}
    detail: Dict[str, Any] = {}

    for key in WEIGHTS:
        series = raw.get(key)
        value = _at(series, offset)
        components[key] = _percentile(value, _window(series, offset))
        if value is None:
            continue
        if key == "momentum":
            detail[key] = "S&P {:+.1f}% vs its 125-day average".format(value * 100.0)
        elif key == "volatility":
            detail[key] = "VIX {:+.1f}% vs its 50-day average (inverted)".format(-value * 100.0)
        elif key == "breadth":
            detail[key] = "{:.0f}% of sectors above their 200-day".format(value)
        elif key == "safe_haven":
            detail[key] = "Stocks {:+.1f} points vs long Treasuries over a month".format(value)
        elif key == "risk_appetite":
            detail[key] = ("Offensive pairs {:+.1f} points vs defensive over a month "
                           "(tech/utilities, discretionary/staples, small caps/index)"
                           .format(value))
        elif key == "junk_demand":
            detail[key] = "High-yield {:+.1f} points vs investment-grade over a month".format(value)

    usable = {k: v for k, v in components.items() if v is not None}
    if not usable:
        return None
    total_weight = sum(WEIGHTS[k] for k in usable)
    score = sum(usable[k] * WEIGHTS[k] for k in usable) / total_weight
    return {"score": round(score, 1), "components": components, "detail": detail,
            "inputs_used": len(usable)}


def _label(score: float) -> str:
    for ceiling, name in BANDS:
        if score < ceiling:
            return name
    return "Extreme Greed"


def build(provider) -> Dict[str, Any]:
    """Today's reading, plus what it was yesterday, a week and a month ago."""
    try:
        frames = provider.batch_history(SYMBOLS, period="2y", interval="1d") or {}
    except Exception as exc:                     # noqa: BLE001 - provider-agnostic
        return {"available": False,
                "reason": "Sentiment inputs unavailable: {}: {}".format(
                    type(exc).__name__, str(exc)[:120])}

    raw = _raw_series(frames)
    now = _score_at(raw, 0)
    if not now:
        return {"available": False,
                "reason": "None of the sentiment inputs had enough history to score."}

    history = {}
    for key, offset in (("prev_close", 1), ("week", 5), ("month", 21)):
        past = _score_at(raw, offset)
        if past:
            history[key] = {"score": past["score"], "label": _label(past["score"]),
                            "change": round(now["score"] - past["score"], 1)}

    score = now["score"]
    total_weight = sum(WEIGHTS[k] for k, v in now["components"].items() if v is not None) or 1.0

    def _reading(key: str, value: Optional[float]) -> Optional[str]:
        if value is None:
            return None
        high, mid, low = COMPONENT_READINGS[key]
        return high if value >= 60 else low if value <= 40 else mid

    components = [
        {"key": k, "label": COMPONENT_LABELS[k], "score": v,
         "label_text": _label(v) if v is not None else None,
         "question": COMPONENT_QUESTIONS[k],
         "reading": _reading(k, v),
         # Weight as actually applied: a missing input redistributes, so the
         # printed percentage has to reflect the blend that produced the score,
         # not the nominal table.
         "weight_pct": round(WEIGHTS[k] / total_weight * 100.0, 1) if v is not None else 0.0,
         "note": COMPONENT_NOTES[k], "detail": now["detail"].get(k)}
        for k, v in now["components"].items()
    ]
    components.sort(key=lambda c: -c["weight_pct"])

    return {
        "available": True,
        "score": score,
        "label": _label(score),
        "components": components,
        "history": history,
        "inputs_used": now["inputs_used"],
        "inputs_total": len(WEIGHTS),
        "methodology": METHODOLOGY_VERSION,
        # Says plainly whether the reading rests on the full set. A composite
        # built from three of six inputs is not wrong, but it is a weaker claim
        # and the reader should not have to count the rows to notice.
        "data_quality": (
            "healthy" if now["inputs_used"] == len(WEIGHTS)
            else "partial" if now["inputs_used"] >= 4 else "thin"
        ),
        "method": (
            "Optic's own reading, not CNN's. Three of CNN's seven inputs — the "
            "McClellan volume summation, NYSE 52-week highs against lows, and a "
            "market-wide equity put/call ratio — need exchange breadth and options "
            "data free sources do not carry, so this uses five inputs it can "
            "actually compute and names all of them. The band labels are CNN's, "
            "which are widely enough understood that inventing new ones would "
            "help nobody. Each input is scored by where it sits in its own "
            "two-year distribution rather than against a fixed width, so 50 is "
            "the middle of this market's actual behaviour — an earlier version "
            "used constants picked by eye and sat in Greed or Extreme Greed 69% "
            "of the time, which made the midpoint meaningless. The tradeoff is "
            "that this reads sentiment relative to the last two years: a market "
            "elevated for the whole window still prints near 50. Earlier "
            "readings are recomputed from the same formulas on truncated history "
            "rather than read from a stored log, so the comparisons are real "
            "from the first day."
        ),
        "caveat": (
            "A sentiment gauge describes positioning, not value. Extreme greed has "
            "preceded both tops and long continuations, and extreme fear marks "
            "bottoms only in hindsight — this says where the crowd is, never what "
            "happens next."
        ),
    }
