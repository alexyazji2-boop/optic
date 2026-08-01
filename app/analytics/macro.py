"""Macro regime panel: volatility, dollar, rates, commodities, credit, crypto.

The point isn't a wall of quotes — it's a single risk-on / risk-off read that
tells you whether to press directional swing trades or stand down, assembled
from the cross-asset signals that actually lead equities.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np

from .series_stats import _f, snapshot

# Yahoo symbols for the macro complex. Grouped so the UI can lay them out.
INSTRUMENTS: List[Dict[str, str]] = [
    {"symbol": "^VIX", "label": "VIX", "group": "volatility", "note": "S&P 30-day implied vol"},
    {"symbol": "^VVIX", "label": "VVIX", "group": "volatility", "note": "vol of vol"},
    {"symbol": "DX-Y.NYB", "label": "DXY", "group": "fx", "note": "US dollar index"},
    {"symbol": "USDJPY=X", "label": "USD/JPY", "group": "fx", "note": "yen carry proxy"},
    {"symbol": "EURUSD=X", "label": "EUR/USD", "group": "fx", "note": "euro"},
    {"symbol": "^TNX", "label": "US 10Y", "group": "rates", "note": "10-year yield"},
    {"symbol": "^FVX", "label": "US 5Y", "group": "rates", "note": "5-year yield"},
    {"symbol": "^IRX", "label": "US 3M", "group": "rates", "note": "13-week bill"},
    {"symbol": "CL=F", "label": "WTI Crude", "group": "commodities", "note": "oil"},
    {"symbol": "NG=F", "label": "Nat Gas", "group": "commodities", "note": "natural gas"},
    {"symbol": "GC=F", "label": "Gold", "group": "commodities", "note": "gold"},
    {"symbol": "HG=F", "label": "Copper", "group": "commodities", "note": "growth bellwether"},
    {"symbol": "HYG", "label": "HYG", "group": "credit", "note": "high-yield credit"},
    {"symbol": "LQD", "label": "LQD", "group": "credit", "note": "investment grade"},
    {"symbol": "TLT", "label": "TLT", "group": "credit", "note": "20y+ treasuries"},
    {"symbol": "BTC-USD", "label": "Bitcoin", "group": "crypto", "note": "risk appetite proxy"},
    {"symbol": "^GSPC", "label": "S&P 500", "group": "equity", "note": "benchmark"},
    {"symbol": "^NDX", "label": "Nasdaq 100", "group": "equity", "note": "growth"},
    {"symbol": "^RUT", "label": "Russell 2000", "group": "equity", "note": "small caps"},
]

# Cross-asset ratios. Each carries the direction that means risk-on so the
# scorer doesn't need a special case per pair.
RATIOS: List[Dict[str, Any]] = [
    {
        "name": "Copper / Gold",
        "numer": "HG=F",
        "denom": "GC=F",
        "risk_on_when": "rising",
        "reads": "industrial demand vs safety bid — a growth thermometer",
    },
    {
        "name": "HYG / TLT",
        "numer": "HYG",
        "denom": "TLT",
        "risk_on_when": "rising",
        "reads": "credit appetite vs duration safety; equities rarely rally against falling credit",
    },
    {
        "name": "Russell / S&P",
        "numer": "^RUT",
        "denom": "^GSPC",
        "risk_on_when": "rising",
        "reads": "small-cap participation — breadth confirmation",
    },
    {
        "name": "Nasdaq / S&P",
        "numer": "^NDX",
        "denom": "^GSPC",
        "risk_on_when": "rising",
        "reads": "growth vs broad market leadership",
    },
]


def _score_component(name: str, value: Optional[float], weight: float, invert: bool = False):
    """Convert a percent move into a bounded contribution."""
    if value is None:
        return 0.0, None
    signed = -value if invert else value
    contribution = float(np.clip(signed * weight, -weight * 5, weight * 5))
    return contribution, {
        "factor": name,
        "value": value,
        "contribution": round(contribution, 2),
    }


def analyse(provider) -> Dict[str, Any]:
    """Full macro panel + risk regime verdict."""
    symbols = [item["symbol"] for item in INSTRUMENTS]
    frames = provider.batch_history(symbols, period="1y", interval="1d")

    snaps: Dict[str, Dict[str, Any]] = {}
    for item in INSTRUMENTS:
        frame = frames.get(item["symbol"])
        snap = snapshot(frame, item["label"]) if frame is not None else {"label": item["label"], "error": "no data"}
        snap["symbol"] = item["symbol"]
        snap["group"] = item["group"]
        snap["note"] = item["note"]
        snaps[item["symbol"]] = snap

    # ---------------------------------------------------------- ratios
    ratio_rows: List[Dict[str, Any]] = []
    for spec in RATIOS:
        a, b = frames.get(spec["numer"]), frames.get(spec["denom"])
        if a is None or b is None or a.empty or b.empty:
            continue
        import pandas as pd

        joined = pd.concat([a["Close"].rename("a"), b["Close"].rename("b")], axis=1).dropna()
        if len(joined) < 30:
            continue
        line = joined["a"] / joined["b"]

        def chg(bars: int) -> Optional[float]:
            if len(line) <= bars or line.iloc[-1 - bars] == 0:
                return None
            return _f((line.iloc[-1] / line.iloc[-1 - bars] - 1.0) * 100.0, 3)

        chg_20 = chg(20)
        trend = None
        if chg_20 is not None:
            rising = chg_20 > 0
            risk_on = rising if spec["risk_on_when"] == "rising" else not rising
            trend = "risk-on" if risk_on else "risk-off"

        ratio_rows.append(
            {
                "name": spec["name"],
                "reads": spec["reads"],
                "level": _f(line.iloc[-1], 6),
                "chg_5d": chg(5),
                "chg_20d": chg_20,
                "chg_60d": chg(60),
                "signal": trend,
                "series": [_f(v, 6) for v in line.tail(90)],
                "dates": [str(i.date()) for i in line.tail(90).index],
            }
        )

    # ------------------------------------------------------ regime score
    score = 0.0
    factors: List[Dict[str, Any]] = []
    notes: List[str] = []

    vix = snaps.get("^VIX", {})
    vix_level = vix.get("last")
    if vix_level is not None:
        if vix_level < 14:
            score += 18
            notes.append("VIX {:.1f} — complacent tape, trend-following works, hedges are cheap".format(vix_level))
        elif vix_level < 18:
            score += 10
            notes.append("VIX {:.1f} — normal vol regime".format(vix_level))
        elif vix_level < 25:
            score -= 8
            notes.append("VIX {:.1f} — elevated; size down and widen stops".format(vix_level))
        elif vix_level < 32:
            score -= 20
            notes.append("VIX {:.1f} — stressed; premium selling favored over directional longs".format(vix_level))
        else:
            score -= 30
            notes.append("VIX {:.1f} — panic regime; mean-reversion bounces are violent both ways".format(vix_level))

    contrib, row = _score_component("VIX 5-day change", vix.get("chg_5d"), 1.2, invert=True)
    score += contrib
    if row:
        factors.append(row)

    for symbol, name, weight, invert in (
        ("^GSPC", "S&P 500 20-day", 2.0, False),
        ("DX-Y.NYB", "Dollar 20-day", 1.5, True),
        ("^TNX", "10-year yield 20-day", 0.8, True),
        ("HYG", "High-yield credit 20-day", 2.5, False),
        ("HG=F", "Copper 20-day", 1.0, False),
        ("BTC-USD", "Bitcoin 20-day", 0.4, False),
        ("^RUT", "Russell 2000 20-day", 1.0, False),
    ):
        contrib, row = _score_component(name, snaps.get(symbol, {}).get("chg_20d"), weight, invert)
        score += contrib
        if row:
            factors.append(row)

    # USD/JPY is two-sided: orderly strength is carry-on, a fast drop is a
    # carry unwind and historically drags global risk with it.
    jpy = snaps.get("USDJPY=X", {})
    jpy_5d = jpy.get("chg_5d")
    if jpy_5d is not None:
        if jpy_5d < -2.0:
            score -= 15
            notes.append(
                "USD/JPY down {:.1f}% in a week — yen-carry unwind risk, historically drags risk assets".format(abs(jpy_5d))
            )
        elif jpy_5d > 1.5:
            score += 6
            notes.append("USD/JPY up {:.1f}% — carry trade supportive".format(jpy_5d))
        factors.append({"factor": "USD/JPY 5-day", "value": jpy_5d, "contribution": None})

    # Crude: moderate strength is demand, a spike is a cost shock.
    oil_20 = snaps.get("CL=F", {}).get("chg_20d")
    if oil_20 is not None:
        if oil_20 > 15:
            score -= 10
            notes.append("Crude +{:.0f}% in a month — inflation/cost-shock headwind".format(oil_20))
        elif oil_20 > 3:
            score += 4
            notes.append("Crude firm — consistent with demand growth")
        elif oil_20 < -15:
            score -= 5
            notes.append("Crude -{:.0f}% — demand-destruction signal".format(abs(oil_20)))

    # Curve shape from the yield proxies we have.
    y10 = snaps.get("^TNX", {}).get("last")
    y3m = snaps.get("^IRX", {}).get("last")
    curve = None
    if y10 is not None and y3m is not None:
        curve = round(y10 - y3m, 3)
        if curve < 0:
            score -= 6
            notes.append("3m/10y curve inverted ({:.2f}) — late-cycle backdrop".format(curve))
        else:
            notes.append("3m/10y curve positive ({:.2f})".format(curve))

    breadth_ratio = next((r for r in ratio_rows if r["name"] == "Russell / S&P"), None)
    if breadth_ratio and breadth_ratio.get("chg_20d") is not None:
        if breadth_ratio["chg_20d"] < -3:
            notes.append("Small caps lagging badly — rally is narrow, be selective")
        elif breadth_ratio["chg_20d"] > 3:
            notes.append("Small caps leading — broad participation supports breakouts")

    score = float(np.clip(score, -100, 100))
    if score >= 35:
        regime, stance = "risk-on", "Favor long-delta swings and breakout continuation."
    elif score >= 12:
        regime, stance = "mildly risk-on", "Long bias, but demand confirmation before sizing up."
    elif score <= -35:
        regime, stance = "risk-off", "Favor puts, hedges, and premium selling into fear; avoid breakout chasing."
    elif score <= -12:
        regime, stance = "mildly risk-off", "Defensive lean; take profits faster and cut size."
    else:
        regime, stance = "neutral / mixed", "No macro edge — trade the setup, not the market."

    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for item in INSTRUMENTS:
        grouped.setdefault(item["group"], []).append(snaps[item["symbol"]])

    return {
        "regime": regime,
        "risk_score": round(score, 1),
        "stance": stance,
        "notes": notes,
        "factors": factors,
        "curve_3m10y": curve,
        "instruments": snaps,
        "groups": grouped,
        "ratios": ratio_rows,
    }
