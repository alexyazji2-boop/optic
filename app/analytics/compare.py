"""Side-by-side comparison of two to four tickers.

Every number here already exists per-ticker. What the terminal could not do was
answer "which of these two" — and that is a different question from "is this one
good", because it needs the same metrics computed the same way at the same moment
for every name. Loading two tabs and eyeballing them invites exactly the mistake
this avoids: comparing a figure from one lookback against the same-named figure
from another.

**Three horizons, ranked separately.** A name can be the best swing setup and the
worst multi-year hold — those are not contradictions, they are different
questions, and collapsing them into one "winner" would hide the only interesting
case. Each horizon states which windows it used, because a comparison whose
lookbacks are invisible is not checkable.

**Today's move deliberately does not drive the position or long-term ranks.**
It is shown as context because a reader wants to see it, but letting a single
session reorder a multi-year assessment is how a comparison becomes a momentum
screen wearing a longer label.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)

MIN_TICKERS, MAX_TICKERS = 2, 4

# What each horizon is scored from, stated so the panel can show it.
HORIZONS = [
    {
        "id": "swing",
        "name": "Swing setup",
        "horizon": "1–8 weeks",
        "basis": ("14-session RSI, implied against 20-session realised volatility, "
                  "21-session relative strength versus SPY, and where price sits "
                  "against its 20- and 50-day averages. Today's tape is context "
                  "only."),
    },
    {
        "id": "position",
        "name": "Position setup",
        "horizon": "several weeks to several months",
        "basis": ("Price against its 50- and 200-day averages, 21-session relative "
                  "strength, and valuation against the company's own history. "
                  "Today's change does not materially influence this."),
    },
    {
        "id": "longterm",
        "name": "Long-term trend",
        "horizon": "multi-year",
        "basis": ("Five-year annualised return and that rate per unit of "
                  "volatility, current drawdown from the all-time high, the "
                  "worst historical drawdown, position against the 200-day "
                  "average, and valuation against the company's own multi-year "
                  "range. Not driven by today's move."),
    },
]


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


def _scaled(value: Optional[float], lo: float, hi: float,
            invert: bool = False) -> Optional[float]:
    """Map a value onto 0-100 across an explicit band."""
    if value is None or hi == lo:
        return None
    pct = (value - lo) / (hi - lo) * 100.0
    return _clip(100.0 - pct if invert else pct)


def _ratio(top: Optional[float], bottom: Optional[float]) -> Optional[float]:
    if top is None or not bottom:
        return None
    return round(top / bottom, 2)


def _mean(parts: List[Optional[float]]) -> Optional[float]:
    usable = [p for p in parts if p is not None]
    return round(sum(usable) / len(usable), 1) if usable else None


def _metrics(payload: Dict[str, Any], longterm: Dict[str, Any]) -> Dict[str, Any]:
    """Pull the comparable figures out of the per-ticker payloads.

    The key paths here were all verified against live payloads rather than
    guessed. Three of them were wrong on the first pass and the metric simply
    rendered as "—" instead of failing, which is the failure mode worth naming:
    a silent None reads as "no data for this name" when it actually means
    "wrong key". Anything read here is read from a shape that was printed first.
    """
    tech = payload.get("technicals") or {}
    mas = tech.get("moving_averages") or {}
    vol = tech.get("volatility") or {}
    quote = payload.get("quote") or {}
    entry = payload.get("entry_plan") or {}
    sc = payload.get("sector_confirm") or {}
    holding = (longterm or {}).get("holding") or {}
    vh = holding.get("valuation_history") or {}
    hz = holding.get("horizons") or {}
    risk = holding.get("risk") or {}
    trend = holding.get("long_trend") or {}
    val = holding.get("valuation") or {}
    draw = holding.get("drawdown") or {}

    def ma_dist(key: str) -> Optional[float]:
        return _num((mas.get(key) or {}).get("distance_pct"))

    return {
        "price": _num(quote.get("price")),
        "change_pct": _num(quote.get("change_pct")),
        # technicals.rsi is an object — the number is under .value.
        "rsi": _num((tech.get("rsi") or {}).get("value")),
        "atr_pct": _num(vol.get("atr_pct")),
        "iv_pct": _num((entry.get("iv_context") or {}).get("atm_iv_pct")),
        "hv_pct": _num(vol.get("realised_vol_20d")),
        "rs_vs_spy": _num(sc.get("rs_vs_spy_pct")),
        "vs_sma20": ma_dist("sma20"),
        "vs_sma50": ma_dist("sma50"),
        "vs_sma200": ma_dist("sma200"),
        "composite": _num((payload.get("verdict") or {}).get("composite_score")),
        "pe_percentile": _num(vh.get("percentile")),
        "pe_read": vh.get("read"),
        "forward_pe": _num(val.get("forward_pe")),
        # Current distance from the all-time high, not the worst historical one.
        "drawdown_pct": _num(draw.get("current_drawdown_pct")),
        # Annualised over five years, so it is comparable between names with
        # different listing histories. Total return would flatter the older one.
        "cagr_5y_pct": _num(hz.get("cagr_5y_pct")),
        "excess_cagr_5y_pct": _num(holding.get("excess_cagr_5y_pct")),
        "beta_vs_spy": _num(risk.get("beta_vs_spy")),
        "annual_vol_pct": _num(risk.get("annualised_vol_pct")),
        "max_drawdown_pct": _num(draw.get("max_drawdown_pct")),
        # Derived here rather than taken from holding.sharpe_proxy, which divides
        # a trailing one-year return by a multi-year volatility. Mixing windows
        # inside one ratio is the exact error this tab exists to avoid, so the
        # five-year rate is divided by the volatility over the same kind of span.
        "cagr_per_vol_5y": _ratio(_num(hz.get("cagr_5y_pct")),
                                  _num(risk.get("annualised_vol_pct"))),
        "vs_sma40w": _num(trend.get("vs_40w_sma")),
        "trend_phase": trend.get("phase"),
        "sector": sc.get("sector") or (holding.get("fundamentals") or {}).get("sector"),
        "name": holding.get("name") or payload.get("ticker"),
    }


def _score_swing(m: Dict[str, Any]) -> Optional[float]:
    """Momentum without being extended, and options not overpriced."""
    # RSI is best in the upper-middle: 50-70 is trending, above 75 is stretched.
    rsi = m.get("rsi")
    rsi_score = None
    if rsi is not None:
        rsi_score = _scaled(rsi, 30, 65) if rsi <= 65 else _scaled(rsi, 65, 90, invert=True)
    iv, hv = m.get("iv_pct"), m.get("hv_pct")
    # Cheap implied vol relative to what the stock actually does is a better entry.
    vol_score = _scaled(iv / hv, 0.7, 1.6, invert=True) if iv and hv else None
    return _mean([
        rsi_score,
        _scaled(m.get("rs_vs_spy"), -10, 15),
        _scaled(m.get("vs_sma20"), -8, 8),
        _scaled(m.get("vs_sma50"), -12, 12),
        vol_score,
    ])


def _score_position(m: Dict[str, Any]) -> Optional[float]:
    """Trend intact over months, and not paying a record multiple for it."""
    return _mean([
        _scaled(m.get("vs_sma50"), -12, 12),
        _scaled(m.get("vs_sma200"), -20, 25),
        _scaled(m.get("rs_vs_spy"), -10, 15),
        # A low percentile means cheap against its own history.
        _scaled(m.get("pe_percentile"), 0, 100, invert=True),
    ])


def _score_longterm(m: Dict[str, Any]) -> Optional[float]:
    """Multi-year trend, how far off the high, and valuation against its range."""
    return _mean([
        # A five-year CAGR, so the band is annual-return sized. Scoring a total
        # return on this band would put every large-cap winner at 100.
        _scaled(m.get("cagr_5y_pct"), -5, 35),
        # A shallow current drawdown is a healthier long-term chart.
        _scaled(m.get("drawdown_pct"), -40, 0),
        _scaled(m.get("vs_sma200"), -20, 25),
        _scaled(m.get("pe_percentile"), 0, 100, invert=True),
        # Return per unit of volatility — two names can compound at the same
        # rate with very different holding experiences. SPY sits near 0.65 on
        # this ratio, so the band is set either side of that.
        _scaled(m.get("cagr_per_vol_5y"), -0.2, 1.2),
        # The worst peak-to-trough this name has actually put a holder through.
        _scaled(m.get("max_drawdown_pct"), -75, -20),
    ])


SCORERS = {"swing": _score_swing, "position": _score_position, "longterm": _score_longterm}


def build(snapshot_fn, longterm_fn, tickers: List[str]) -> Dict[str, Any]:
    """Compare tickers across the three horizons.

    `snapshot_fn` and `longterm_fn` are injected so this module never touches a
    provider directly — the same reason the scoring is pure: it can be tested
    without a network.
    """
    clean: List[str] = []
    for raw in tickers or []:
        sym = str(raw or "").upper().strip()
        if sym and sym not in clean:
            clean.append(sym)
    if len(clean) < MIN_TICKERS:
        return {"available": False,
                "reason": "Give at least {} tickers to compare.".format(MIN_TICKERS)}
    clean = clean[:MAX_TICKERS]

    rows: List[Dict[str, Any]] = []
    failed: List[Dict[str, str]] = []
    for sym in clean:
        try:
            payload = snapshot_fn(sym)
        except Exception as exc:
            failed.append({"ticker": sym, "reason": str(exc)[:120]})
            continue
        if not payload or payload.get("error"):
            failed.append({"ticker": sym,
                           "reason": (payload or {}).get("error") or "no data"})
            continue
        try:
            lt = longterm_fn(sym)
        except Exception as exc:
            log.info("compare: long-term unavailable for %s: %s", sym, exc)
            lt = {}
        m = _metrics(payload, lt or {})
        m["ticker"] = sym
        m["scores"] = {k: fn(m) for k, fn in SCORERS.items()}
        rows.append(m)

    if len(rows) < MIN_TICKERS:
        return {"available": False,
                "reason": "Only {} of {} tickers returned data.".format(len(rows), len(clean)),
                "failed": failed}

    # Rank within each horizon. Ties share a rank rather than being ordered by
    # something arbitrary like alphabetical position.
    ranks: Dict[str, List[Dict[str, Any]]] = {}
    for hid in SCORERS:
        scored = [r for r in rows if r["scores"].get(hid) is not None]
        scored.sort(key=lambda r: -r["scores"][hid])
        out = []
        for i, r in enumerate(scored):
            prev = scored[i - 1] if i else None
            rank = i + 1
            if prev is not None and prev["scores"][hid] == r["scores"][hid]:
                rank = out[-1]["rank"]
            out.append({"ticker": r["ticker"], "score": r["scores"][hid], "rank": rank})
        ranks[hid] = out

    return {
        "available": True,
        "tickers": [r["ticker"] for r in rows],
        "rows": rows,
        "ranks": ranks,
        "horizons": HORIZONS,
        "failed": failed,
        "method": (
            "Every figure is computed the same way at the same moment for each "
            "name, which is the point. Comparing a number from one tab against a "
            "same-named number from another risks comparing different lookbacks. "
            "The three horizons are ranked separately because a name can be the "
            "best swing setup and the worst multi-year hold; that is not a "
            "contradiction. Today's price change is shown as context and "
            "deliberately does not drive the position or long-term ranks. Research "
            "context, not instructions to buy or sell."
        ),
    }
