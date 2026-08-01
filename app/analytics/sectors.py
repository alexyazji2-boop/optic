"""Sector and theme rotation: relative strength ranking, breakout screening,
and ratio pair trades.

Ranking is done on the ratio line against SPY rather than raw return — that's
what separates genuine leadership from high-beta drift.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from .series_stats import _f, relative_strength, snapshot

BENCHMARK = "SPY"

SECTORS: List[Dict[str, str]] = [
    {"symbol": "XLK", "name": "Technology"},
    {"symbol": "XLF", "name": "Financials"},
    {"symbol": "XLV", "name": "Health Care"},
    {"symbol": "XLY", "name": "Consumer Discretionary"},
    {"symbol": "XLP", "name": "Consumer Staples"},
    {"symbol": "XLE", "name": "Energy"},
    {"symbol": "XLI", "name": "Industrials"},
    {"symbol": "XLB", "name": "Materials"},
    {"symbol": "XLU", "name": "Utilities"},
    {"symbol": "XLRE", "name": "Real Estate"},
    {"symbol": "XLC", "name": "Communication Services"},
]

THEMES: List[Dict[str, str]] = [
    {"symbol": "SMH", "name": "Semiconductors"},
    {"symbol": "XBI", "name": "Biotech"},
    {"symbol": "KRE", "name": "Regional Banks"},
    {"symbol": "XRT", "name": "Retail"},
    {"symbol": "ITB", "name": "Homebuilders"},
    {"symbol": "GDX", "name": "Gold Miners"},
    {"symbol": "JETS", "name": "Airlines"},
    {"symbol": "IGV", "name": "Software"},
    {"symbol": "XOP", "name": "Oil & Gas E&P"},
    {"symbol": "ARKK", "name": "Disruptive Growth"},
]

# One level narrower than THEMES — single sub-industries and thematic baskets
# that don't have a broad-sector or even a "theme ETF" home of their own.
# Rotation often shows up here first, before it's visible in the 11 SPDR
# sectors. Every symbol below is verified to resolve on the data provider.
NICHE: List[Dict[str, str]] = [
    {"symbol": "SOXX", "name": "Semiconductors (broad)"},
    {"symbol": "DRAM", "name": "Memory Chips"},
    {"symbol": "CIBR", "name": "Cybersecurity"},
    {"symbol": "SKYY", "name": "Cloud Computing"},
    {"symbol": "FINX", "name": "Fintech"},
    {"symbol": "DRIV", "name": "EV & Autonomous Driving"},
    {"symbol": "URA", "name": "Uranium & Nuclear"},
    {"symbol": "LIT", "name": "Lithium & Battery Tech"},
    {"symbol": "BOTZ", "name": "Robotics & AI"},
    {"symbol": "REMX", "name": "Rare Earth & Strategic Metals"},
    {"symbol": "TAN", "name": "Solar"},
    {"symbol": "ITA", "name": "Aerospace & Defense"},
    {"symbol": "KWEB", "name": "China Internet"},
    {"symbol": "MOO", "name": "Agribusiness"},
]

# Classic macro-expression pairs. Each is a ratio whose z-score gives both a
# regime read and a mean-reversion entry.
PAIRS: List[Dict[str, str]] = [
    {"long": "XLY", "short": "XLP", "thesis": "Discretionary over staples — consumer risk appetite"},
    {"long": "SMH", "short": "SPY", "thesis": "Semis over market — the classic tech-cycle tell"},
    {"long": "XLF", "short": "XLU", "thesis": "Financials over utilities — rising-rate / cyclical bet"},
    {"long": "IWM", "short": "SPY", "thesis": "Small over large — breadth and domestic growth"},
    {"long": "XLE", "short": "XLK", "thesis": "Energy over tech — inflation / value rotation"},
    {"long": "XLI", "short": "XLP", "thesis": "Industrials over staples — cyclical expansion"},
    {"long": "GDX", "short": "SPY", "thesis": "Miners over market — debasement / fear hedge"},
    {"long": "IGV", "short": "XLF", "thesis": "Software over banks — duration / disinflation bet"},
]


def _composite(snap: Dict[str, Any], rs: Dict[str, Any]) -> Optional[float]:
    """Blend relative strength across horizons with trend confirmation.

    Weighted toward 1-3 month RS: that's the horizon a swing trade actually
    lives on, while 6-month RS just tells you what already happened.
    """
    parts: List[float] = []
    weights: List[float] = []

    for key, weight in (("rs_1w", 1.0), ("rs_1m", 3.0), ("rs_3m", 2.5), ("rs_6m", 1.0)):
        value = rs.get(key)
        if value is not None:
            parts.append(float(np.clip(value, -25, 25)))
            weights.append(weight)

    if not parts:
        return None

    rs_score = float(np.average(parts, weights=weights))
    trend_bonus = 0.0
    if snap.get("above_sma50"):
        trend_bonus += 2.0
    if snap.get("above_sma200"):
        trend_bonus += 2.0
    if rs.get("ratio_above_sma50"):
        trend_bonus += 2.0
    if rs.get("ratio_above_sma20"):
        trend_bonus += 1.0

    return round(rs_score + trend_bonus, 3)


def _breakout_read(snap: Dict[str, Any]) -> Dict[str, Any]:
    """Score how close an instrument is to a tradable breakout.

    Requires three things together: price coiled near a range high, a
    volatility squeeze, and momentum in the constructive band. Any one alone
    is noise.
    """
    reasons: List[str] = []
    score = 0.0

    d20 = snap.get("dist_to_20d_high")
    d60 = snap.get("dist_to_60d_high")
    squeeze = snap.get("squeeze_percentile")
    rsi_v = snap.get("rsi")
    vol_ratio = snap.get("volume_ratio_5d_60d")

    if d20 is not None and d20 >= -1.5:
        score += 30
        reasons.append("within {:.1f}% of the 20-day high".format(abs(d20)))
    elif d20 is not None and d20 >= -4:
        score += 15
        reasons.append("coiling {:.1f}% under the 20-day high".format(abs(d20)))

    if d60 is not None and d60 >= -3:
        score += 20
        reasons.append("pressing the 3-month high")

    if squeeze is not None and squeeze <= 25:
        score += 25
        reasons.append("Bollinger bandwidth in the {:.0f}th percentile — coiled".format(squeeze))
    elif squeeze is not None and squeeze <= 45:
        score += 10

    if rsi_v is not None and 52 <= rsi_v <= 68:
        score += 15
        reasons.append("RSI {:.0f} — momentum without exhaustion".format(rsi_v))
    elif rsi_v is not None and rsi_v > 75:
        score -= 15
        reasons.append("RSI {:.0f} already extended — chase risk".format(rsi_v))

    if vol_ratio is not None and vol_ratio > 1.25:
        score += 10
        reasons.append("volume running {:.0f}% of its 3-month average".format(vol_ratio * 100))

    if snap.get("above_sma50"):
        score += 5

    return {
        "breakout_score": round(float(np.clip(score, 0, 100)), 1),
        "breakout_reasons": reasons,
        "breakout_ready": bool(score >= 60),
    }


def _rank_universe(
    universe: List[Dict[str, str]],
    frames: Dict[str, pd.DataFrame],
    bench: pd.DataFrame,
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for entry in universe:
        frame = frames.get(entry["symbol"])
        if frame is None or frame.empty:
            continue
        snap = snapshot(frame, entry["name"])
        if snap.get("error"):
            continue
        rs = relative_strength(frame, bench)
        row: Dict[str, Any] = {"symbol": entry["symbol"], "name": entry["name"]}
        row.update(snap)
        row["rs"] = rs
        row["composite"] = _composite(snap, rs)
        row.update(_breakout_read(snap))
        rows.append(row)

    rows.sort(key=lambda r: (r["composite"] is None, -(r["composite"] or -999)))
    for idx, row in enumerate(rows, start=1):
        row["rank"] = idx
        composite = row.get("composite")
        if composite is None:
            row["strength"] = "unknown"
        elif composite >= 8:
            row["strength"] = "strong"
        elif composite >= 2:
            row["strength"] = "improving"
        elif composite <= -8:
            row["strength"] = "weak"
        elif composite <= -2:
            row["strength"] = "deteriorating"
        else:
            row["strength"] = "neutral"
    return rows


def _pair_rows(frames: Dict[str, pd.DataFrame]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for spec in PAIRS:
        a, b = frames.get(spec["long"]), frames.get(spec["short"])
        if a is None or b is None or a.empty or b.empty:
            continue
        joined = pd.concat(
            [a["Close"].rename("a"), b["Close"].rename("b")], axis=1
        ).dropna()
        if len(joined) < 70:
            continue

        line = joined["a"] / joined["b"]
        mean60 = line.tail(60).mean()
        std60 = line.tail(60).std(ddof=0)
        z = float((line.iloc[-1] - mean60) / std60) if std60 and std60 > 0 else 0.0

        def chg(bars: int) -> Optional[float]:
            if len(line) <= bars or line.iloc[-1 - bars] == 0:
                return None
            return _f((line.iloc[-1] / line.iloc[-1 - bars] - 1.0) * 100.0, 3)

        trend_20 = chg(20)
        sma50 = line.rolling(50, min_periods=50).mean()
        above_50 = (
            bool(line.iloc[-1] > sma50.dropna().iloc[-1]) if not sma50.dropna().empty else None
        )

        # Two honest ways to trade a ratio: ride the trend, or fade a stretch.
        # Say which one the current reading supports instead of picking one.
        if z >= 2:
            setup = "stretched — mean-reversion short of the ratio (fade {} vs {})".format(
                spec["long"], spec["short"]
            )
        elif z <= -2:
            setup = "stretched — mean-reversion long of the ratio (buy {} vs {})".format(
                spec["long"], spec["short"]
            )
        elif above_50 and (trend_20 or 0) > 1:
            setup = "trending — momentum long {} / short {}".format(spec["long"], spec["short"])
        elif above_50 is False and (trend_20 or 0) < -1:
            setup = "trending — momentum long {} / short {}".format(spec["short"], spec["long"])
        else:
            setup = "no edge — ratio is range-bound near its mean"

        rows.append(
            {
                "pair": "{} / {}".format(spec["long"], spec["short"]),
                "long": spec["long"],
                "short": spec["short"],
                "thesis": spec["thesis"],
                "ratio": _f(line.iloc[-1], 6),
                "zscore_60d": round(z, 2),
                "chg_5d": chg(5),
                "chg_20d": chg(20),
                "chg_60d": chg(60),
                "ratio_above_sma50": above_50,
                "setup": setup,
                "series": [_f(v, 6) for v in line.tail(90)],
            }
        )

    rows.sort(key=lambda r: -abs(r["zscore_60d"]))
    return rows


def _equal_weight_breadth(provider) -> Dict[str, Any]:
    """Equal-weight versus cap-weight (RSP / SPY).

    The cleanest single read on whether an advance is broad or being carried by a
    handful of megacaps, so it sits with the other breadth measures rather than in
    the long-cycle index view. Fetched on its own two-year window because the
    one-year change needs more than a year of history, and widening the main
    ~35-symbol pull to two years just for this would be wasteful.
    """
    frames = provider.batch_history(["RSP", BENCHMARK], period="2y", interval="1d")
    rsp, spy = frames.get("RSP"), frames.get(BENCHMARK)
    if rsp is None or spy is None or rsp.empty or spy.empty:
        return {}

    joined = pd.concat(
        [rsp["Close"].rename("rsp"), spy["Close"].rename("spy")], axis=1
    ).dropna()
    if len(joined) <= 130:
        return {}

    line = joined["rsp"] / joined["spy"]
    chg_63 = _f((line.iloc[-1] / line.iloc[-64] - 1.0) * 100.0, 2)
    chg_252 = _f((line.iloc[-1] / line.iloc[-253] - 1.0) * 100.0, 2) if len(line) > 253 else None

    if chg_63 is not None and chg_63 < -2:
        note = (
            "Equal-weight lagging cap-weight by {:.1f}% over 3 months — the index is being carried "
            "by its largest names. Concentration risk.".format(abs(chg_63))
        )
    elif chg_63 is not None and chg_63 > 2:
        note = (
            "Equal-weight outperforming by {:.1f}% over 3 months — broad participation, "
            "a healthier advance.".format(chg_63)
        )
    else:
        note = "Equal-weight roughly tracking cap-weight — no unusual concentration."

    return {
        "rsp_spy_ratio": _f(line.iloc[-1], 5),
        "chg_3m_pct": chg_63,
        "chg_1y_pct": chg_252,
        "note": note,
        "series": [_f(v, 5) for v in line.tail(260)],
        "dates": [str(i.date()) for i in line.tail(260).index],
    }


def analyse(provider) -> Dict[str, Any]:
    symbols = (
        [BENCHMARK, "IWM"]
        + [s["symbol"] for s in SECTORS]
        + [t["symbol"] for t in THEMES]
        + [n["symbol"] for n in NICHE]
    )
    frames = provider.batch_history(sorted(set(symbols)), period="1y", interval="1d")
    bench = frames.get(BENCHMARK)
    if bench is None or bench.empty:
        return {"error": "benchmark data unavailable"}

    sector_rows = _rank_universe(SECTORS, frames, bench)
    theme_rows = _rank_universe(THEMES, frames, bench)
    niche_rows = _rank_universe(NICHE, frames, bench)
    pairs = _pair_rows(frames)

    # Breadth proxy: how much of the sector complex is above its own 200-day.
    above_200 = [r for r in sector_rows if r.get("above_sma200")]
    above_50 = [r for r in sector_rows if r.get("above_sma50")]
    breadth_200 = round(len(above_200) / max(len(sector_rows), 1) * 100.0, 1)
    breadth_50 = round(len(above_50) / max(len(sector_rows), 1) * 100.0, 1)

    if breadth_200 >= 70:
        breadth_note = "Broad participation — {:.0f}% of sectors above their 200-day. Breakouts have follow-through.".format(breadth_200)
    elif breadth_200 >= 45:
        breadth_note = "Mixed participation ({:.0f}% above 200-day) — leadership is narrowing, be selective.".format(breadth_200)
    else:
        breadth_note = "Narrow tape — only {:.0f}% of sectors above their 200-day. Long setups are fighting the current.".format(breadth_200)

    breakouts = sorted(
        [r for r in sector_rows + theme_rows + niche_rows if r["breakout_score"] >= 45],
        key=lambda r: -r["breakout_score"],
    )[:8]

    strongest = sector_rows[:3]
    weakest = sector_rows[-3:][::-1]

    rotation = None
    if strongest and weakest:
        rotation = "Money is rotating into {} and out of {}.".format(
            ", ".join(r["name"] for r in strongest),
            ", ".join(r["name"] for r in weakest),
        )

    return {
        "benchmark": BENCHMARK,
        "sectors": sector_rows,
        "themes": theme_rows,
        "niche": niche_rows,
        "pairs": pairs,
        "breakout_candidates": breakouts,
        "breadth": {
            "pct_sectors_above_200sma": breadth_200,
            "pct_sectors_above_50sma": breadth_50,
            "note": breadth_note,
            "equal_vs_cap": _equal_weight_breadth(provider),
        },
        "leaders": [{"symbol": r["symbol"], "name": r["name"], "composite": r["composite"]} for r in strongest],
        "laggards": [{"symbol": r["symbol"], "name": r["name"], "composite": r["composite"]} for r in weakest],
        "rotation_note": rotation,
        "suggested_pair": (
            {
                "long": strongest[0]["symbol"],
                "short": weakest[0]["symbol"],
                "note": "Highest-RS sector against the lowest — the cleanest expression of the current rotation.",
            }
            if strongest and weakest
            else None
        ),
    }
