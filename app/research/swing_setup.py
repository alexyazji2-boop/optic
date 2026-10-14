"""Disciplined swing-trade analysis: setup, confirmation, invalidation, grade.

The order is deliberate. The reasons to skip the trade are listed before the
grade, and the grade is then decided by named rules in `policy`, so an
attractive chart cannot argue its way past a poor reward-to-risk ratio or an
earnings release inside the holding window.

Readings are computed from completed daily bars (the forming bar is dropped by
the caller) and completed weekly bars resampled from them. Relative strength
here means the stock's return minus the benchmark's over the same sessions; it
is a different thing from RSI, which measures a stock's own recent up-moves
against its down-moves and says nothing about the market.

Grades are framework rules, not probabilities: an S is a setup that meets every
stated criterion, not a trade that is likely to work.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from ..analytics.technicals import atr as atr_series, ema, macd, rsi, sma, support_resistance_levels
from . import trade_math

GRADES = ["S", "A", "B", "Avoid"]


def _f(x: Any, d: int = 2) -> Optional[float]:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return round(v, d) if np.isfinite(v) else None


def _ret(close: pd.Series, n: int) -> Optional[float]:
    if len(close) <= n:
        return None
    a, b = float(close.iloc[-1 - n]), float(close.iloc[-1])
    return (b / a - 1.0) if a > 0 else None


def weekly_bars(daily: pd.DataFrame) -> pd.DataFrame:
    agg = {"Open": "first", "High": "max", "Low": "min", "Close": "last"}
    if "Volume" in daily:
        agg["Volume"] = "sum"
    w = daily.resample("W-FRI").agg(agg).dropna(subset=["Close"])
    # The last week is incomplete unless the daily series ends on its Friday
    # (or the week's last session); a half-built week is dropped, not graded.
    if len(w) and len(daily):
        last_day = daily.index[-1]
        if w.index[-1] > last_day and last_day.weekday() < 4:
            w = w.iloc[:-1]
    return w


def readings(daily: pd.DataFrame, bench: Optional[pd.DataFrame], sector: Optional[pd.DataFrame] = None,
             sector_symbol: Optional[str] = None) -> Dict[str, Any]:
    close = daily["Close"].astype(float)
    spot = float(close.iloc[-1])
    e20, e50, s200 = ema(close, 20), ema(close, 50), sma(close, 200)
    r = rsi(close, 14)
    m = macd(close)
    a = atr_series(daily, 14)
    vol = daily["Volume"].astype(float) if "Volume" in daily else None
    rel_vol = None
    if vol is not None and len(vol) > 21:
        avg = float(vol.iloc[-21:-1].mean())
        rel_vol = float(vol.iloc[-1]) / avg if avg > 0 else None
    out: Dict[str, Any] = {
        "spot": _f(spot), "as_of": str(daily.index[-1].date()),
        "ema20": _f(e20.iloc[-1]), "ema50": _f(e50.iloc[-1]), "sma200": _f(s200.iloc[-1]),
        "ema20_slope_5d_pct": _f((e20.iloc[-1] / e20.iloc[-6] - 1) * 100) if len(e20) > 6 else None,
        "sma200_slope_20d_pct": _f((s200.iloc[-1] / s200.iloc[-21] - 1) * 100) if s200.dropna().size > 21 else None,
        "rsi14": _f(r.iloc[-1], 1),
        "macd": _f(m["macd"].iloc[-1], 3), "macd_signal": _f(m["signal"].iloc[-1], 3),
        "macd_hist": _f(m["hist"].iloc[-1], 3),
        "macd_hist_rising": bool(m["hist"].iloc[-1] > m["hist"].iloc[-3]) if len(m["hist"]) > 3 else None,
        "atr14": _f(a.iloc[-1], 3), "atr_pct": _f(a.iloc[-1] / spot * 100, 2) if spot else None,
        "relative_volume": _f(rel_vol, 2),
        "high_20d": _f(daily["High"].tail(20).max()), "low_20d": _f(daily["Low"].tail(20).min()),
        "low_10d": _f(daily["Low"].tail(10).min()), "high_10d": _f(daily["High"].tail(10).max()),
        "low_5d": _f(daily["Low"].tail(5).min()), "high_5d": _f(daily["High"].tail(5).max()),
        "high_252": _f(daily["High"].tail(252).max()), "low_252": _f(daily["Low"].tail(252).min()),
    }
    # Daily trend by the averages' order, not by one crossing.
    c, a20, a50, a200 = spot, out["ema20"], out["ema50"], out["sma200"]
    if None in (a20, a50, a200):
        daily_trend = "unknown"
    elif c > a200 and a50 > a200:
        daily_trend = "up"
    elif c < a200 and a50 < a200:
        daily_trend = "down"
    else:
        daily_trend = "mixed"
    out["daily_trend"] = daily_trend
    w = weekly_bars(daily)
    wc = w["Close"]
    w10, w40 = sma(wc, 10), sma(wc, 40)
    if len(wc) >= 42 and w40.notna().iloc[-1]:
        up = wc.iloc[-1] > w10.iloc[-1] and w10.iloc[-1] > w10.iloc[-3] and wc.iloc[-1] > w40.iloc[-1]
        down = wc.iloc[-1] < w10.iloc[-1] and w10.iloc[-1] < w10.iloc[-3] and wc.iloc[-1] < w40.iloc[-1]
        weekly_trend = "up" if up else "down" if down else "mixed"
    else:
        weekly_trend = "unknown"
    out.update({"weekly_trend": weekly_trend, "weekly_close": _f(wc.iloc[-1]) if len(wc) else None,
                "weekly_sma10": _f(w10.iloc[-1]) if len(w10) else None,
                "weekly_sma40": _f(w40.iloc[-1]) if len(w40) else None,
                "weekly_as_of": str(w.index[-1].date()) if len(w) else None,
                "aligned": daily_trend in ("up", "down") and daily_trend == weekly_trend})
    # Relative strength: return minus the benchmark's, same sessions.
    rs: Dict[str, Any] = {}
    for name, frame in (("SPY", bench), (sector_symbol, sector)):
        if frame is None or name is None or frame.empty:
            continue
        bc = frame["Close"].astype(float).reindex(close.index).ffill()
        for n, label in ((21, "1m"), (63, "3m")):
            s, b = _ret(close, n), _ret(bc.dropna(), n)
            if s is not None and b is not None:
                rs["{}_{}".format(name, label)] = {"stock": _f(s * 100), "benchmark": _f(b * 100),
                                                    "excess_pct": _f((s - b) * 100)}
    out["relative_strength"] = rs
    if bench is not None and not bench.empty:
        bcl = bench["Close"].astype(float)
        b50, b200 = sma(bcl, 50).iloc[-1], sma(bcl, 200).iloc[-1]
        bl = float(bcl.iloc[-1])
        state = ("risk-on" if bl > b50 and bl > b200 else "risk-off" if bl < b50 and bl < b200 else "mixed")
        out["benchmark"] = {"symbol": "SPY", "close": _f(bl), "sma50": _f(b50), "sma200": _f(b200), "state": state,
                            "as_of": str(bench.index[-1].date())}
    out["levels"] = support_resistance_levels(daily, spot, lookback=252)
    return out


# A target is a level the move has to reach, so it has to be both meaningful
# (strength 40 or more on the 0-100 level score, or the 52-week extreme) and at
# least one daily ATR beyond entry. The first live run (2026-10-14) took the
# nearest level of any strength as the target: NVDA, AAPL, XOM and KO all sat
# just under their 52-week highs, so every "target" was 0.3 to 1.3 ATRs away
# and every setup graded Avoid on arithmetic that described an obstacle, not a
# destination. Closer levels are reported as obstacles instead.
TARGET_MIN_STRENGTH = 40.0
TARGET_MIN_ATR = 1.0


def _targets(rd: Dict[str, Any], entry: float, side: str, atr: float, kind: str,
             level: Optional[float] = None) -> Dict[str, Any]:
    sign = 1.0 if side == "long" else -1.0
    levels = rd.get("levels") or []
    cands: List[Dict[str, Any]] = []
    obstacles: List[Dict[str, Any]] = []
    for lv in levels:
        p = lv.get("price")
        if not p:
            continue
        dist = (p - entry) * sign
        if dist >= TARGET_MIN_ATR * atr and (lv.get("strength") or 0) >= TARGET_MIN_STRENGTH:
            cands.append({"price": p, "basis": "{} ({} touches)".format(
                "resistance" if side == "long" else "support", lv.get("touches"))})
        elif 0 < dist < TARGET_MIN_ATR * atr:
            obstacles.append(lv)
    ext = rd.get("high_252") if side == "long" else rd.get("low_252")
    if ext and (ext - entry) * sign >= TARGET_MIN_ATR * atr:
        cands.append({"price": ext, "basis": "the 52-week {}".format("high" if side == "long" else "low")})
    elif ext and 0 < (ext - entry) * sign < TARGET_MIN_ATR * atr:
        obstacles.append({"price": ext, "touches": None, "strength": None, "kind": "52-week extreme"})
    cands.sort(key=lambda c: (c["price"] - entry) * sign)
    dedup: List[Dict[str, Any]] = []
    for c in cands:
        if not dedup or abs(c["price"] - dedup[-1]["price"]) > 0.5 * atr:
            dedup.append(c)
    if dedup:
        return {"targets": dedup[:2], "basis": "the next meaningful {} levels at least one ATR away".format(
            "resistance" if side == "long" else "support"), "obstacles": obstacles, "projected": False}
    if kind == "breakout" and level is not None and rd.get("high_20d") and rd.get("low_20d"):
        height = rd["high_20d"] - rd["low_20d"]
        t = level + sign * max(height, 2.0 * atr)
        return {"targets": [{"price": t, "basis": "measured move"}], "obstacles": obstacles, "projected": True,
                "basis": "a measured move: the 20-session range ({:.2f}) added to the breakout level, because "
                         "there is no {} level beyond it. A projection, not a level the chart has shown.".format(
                             height, "resistance" if side == "long" else "support")}
    t = entry + sign * 3.0 * atr
    return {"targets": [{"price": t, "basis": "three-ATR projection"}], "obstacles": obstacles, "projected": True,
            "basis": "a three-ATR projection, because no meaningful {} level sits beyond entry. A projection, "
                     "not a level the chart has shown.".format("resistance" if side == "long" else "support")}


def _support_below(levels: List[Dict[str, Any]], price: float, side: str) -> Optional[Dict[str, Any]]:
    if side == "long":
        c = [lv for lv in levels if lv.get("band_low") and lv["price"] < price]
        return max(c, key=lambda lv: lv["price"]) if c else None
    c = [lv for lv in levels if lv.get("band_high") and lv["price"] > price]
    return min(c, key=lambda lv: lv["price"]) if c else None


def detect_setup(rd: Dict[str, Any]) -> Dict[str, Any]:
    """Which defined setup, if any, the readings describe."""
    spot, atr = rd["spot"], rd["atr14"]
    trend = rd["daily_trend"]
    if trend not in ("up", "down") or not atr:
        return {"kind": None, "why": "The daily trend is {}: price and the 50-day are not on the same side of "
                                     "the 200-day, so there is no trend to trade with.".format(trend)}
    side = "long" if trend == "up" else "short"
    sign = 1.0 if side == "long" else -1.0
    e20, e50 = rd["ema20"], rd["ema50"]
    ext = (spot - e20) * sign / atr
    r = rd["rsi14"] or 50.0
    if ext > 2.5 or (side == "long" and r > 75) or (side == "short" and r < 25):
        return {"kind": None, "side": side, "extended": True,
                "why": "Price is {:.1f} ATRs {} the 20-day EMA with RSI {:.0f}: extended. Entering here puts the "
                       "stop far away or inside the noise.".format(abs(ext), "above" if side == "long" else "below", r)}
    levels = rd.get("levels") or []
    # Breakout: within half an ATR of a strong level in the trend's direction,
    # or closed through one in the last few sessions.
    near = [lv for lv in levels if (lv.get("strength") or 0) >= 40 and lv.get("price")
            and 0 <= (lv["price"] - spot) * sign <= 0.5 * atr]
    if near:
        lv = min(near, key=lambda x: abs(x["price"] - spot))
        return {"kind": "breakout", "side": side, "level": lv["price"],
                "why": "Price is testing a {}-touch {} at {:.2f}.".format(
                    lv.get("touches"), "resistance" if side == "long" else "support", lv["price"])}
    # Pullback: back to the 20- or 50-day EMA, momentum reset.
    for name, ma in (("20-day EMA", e20), ("50-day EMA", e50)):
        if ma and -0.5 <= (spot - ma) * sign / atr <= 1.0 and (35 <= r <= 62 if side == "long" else 38 <= r <= 65):
            return {"kind": "pullback", "side": side, "anchor": name, "anchor_price": ma,
                    "why": "A pullback to the {} at {:.2f} in an {}trend, RSI {:.0f}.".format(
                        name, ma, "up" if side == "long" else "down", r)}
    return {"kind": None, "side": side,
            "why": "The trend is {} but price is neither at a level nor back at its averages: no defined "
                   "entry.".format("up" if side == "long" else "down")}


def _earnings_exposure(earn: Dict[str, Any], as_of: str, hold_days: Optional[int]) -> Dict[str, Any]:
    d = earn.get("date") if earn else None
    if not d:
        return {"known": False, "in_window": None,
                "text": "No earnings date was found, so earnings exposure is unknown; check the company's "
                        "investor-relations calendar before relying on the window."}
    try:
        day = date.fromisoformat(str(d)[:10])
        start = date.fromisoformat(as_of[:10])
    except ValueError:
        return {"known": False, "in_window": None, "text": "The earnings date could not be read."}
    days = hold_days or 20
    end = start + timedelta(days=int(np.ceil(days * 7 / 5)) + 1)
    inside = start <= day <= end
    confirmed = earn.get("confirmed")
    return {"known": True, "date": day.isoformat(), "confirmed": confirmed, "timing": earn.get("timing"),
            "in_window": inside, "window_end": end.isoformat(),
            "text": "Earnings {} {} ({}), {} the holding window to {}.".format(
                "are" if confirmed else "are estimated for", day.isoformat(),
                "confirmed" if confirmed else "date not confirmed by the company",
                "inside" if inside else "outside", end.isoformat())}


def assess(daily: pd.DataFrame, bench: Optional[pd.DataFrame], values: Dict[str, Any], *,
           earnings: Optional[Dict[str, Any]] = None, freshness: Optional[Dict[str, Any]] = None,
           sector: Optional[pd.DataFrame] = None, sector_symbol: Optional[str] = None,
           spread: Optional[float] = None, event_strategy: bool = False) -> Dict[str, Any]:
    """The swing assessment: readings, setup, plan, objections, grade."""
    need = int(values["swing_min_bars"])
    if daily is None or len(daily) < need or bench is None or bench.empty:
        return {"grade": "Insufficient Data", "readings": None,
                "why": "Needs {} completed daily bars and a benchmark series; had {}{}.".format(
                    need, 0 if daily is None else len(daily), "" if bench is not None and not bench.empty
                    else " and no benchmark"),
                "objections": [], "plan": None}
    rd = readings(daily, bench, sector, sector_symbol)
    if not rd.get("atr14"):
        return {"grade": "Insufficient Data", "readings": rd, "why": "No ATR could be computed.",
                "objections": [], "plan": None}
    setup = detect_setup(rd)
    atr = rd["atr14"]
    spot = rd["spot"]
    hold_max = int(values["swing_holding_days_max"])
    objections: List[Dict[str, Any]] = []

    def obj(text: str, severity: int, kind: str) -> None:
        objections.append({"text": text, "severity": severity, "kind": kind})

    if freshness and freshness.get("state") == "stale":
        obj("The quote is stale ({}); levels are measured from the last completed bar.".format(
            freshness.get("text")), 2, "data")
    if not setup.get("kind"):
        reassess = _reassess_when(rd, setup)
        return {"grade": "No Setup", "readings": rd, "setup": setup, "why": setup["why"],
                "reassess_when": reassess, "objections": objections, "plan": None,
                "rules": [], "framework_note": FRAMEWORK_NOTE}
    side = setup["side"]
    sign = 1.0 if side == "long" else -1.0
    levels = rd.get("levels") or []
    # Entry, confirmation and the structural invalidation for each kind.
    if setup["kind"] == "breakout":
        lvl = setup["level"]
        # Levels stacked within half an ATR are one ceiling: XOM tested 175.65
        # with its 52-week high at 176.41, and an entry between the two starts
        # the trade underneath the level that actually matters.
        ext = rd.get("high_252") if side == "long" else rd.get("low_252")
        stacked = [lv["price"] for lv in levels if lv.get("price") and 0 < (lv["price"] - lvl) * sign <= 0.5 * atr]
        if ext and 0 < (ext - lvl) * sign <= 0.5 * atr:
            stacked.append(ext)
        if stacked:
            lvl = max(stacked) if side == "long" else min(stacked)
        entry = lvl + sign * 0.1 * atr
        zone = sorted([lvl, lvl + sign * 0.35 * atr])
        confirmation = ("A daily close {} {:.2f} on volume at least 1.5x its 20-day average. A close back "
                        "{} the level the next session voids it.".format(
                            "above" if side == "long" else "below", lvl, "under" if side == "long" else "over"))
        # A failed breakout is a close back inside the base, half an ATR
        # through the level; the ATR floor below usually widens it.
        structural = lvl - sign * 0.5 * atr
        struct_text = "a close back {} the {:.2f} level, inside the base".format(
            "below" if side == "long" else "above", lvl)
    else:
        anchor = setup["anchor_price"]
        entry = spot if abs(spot - anchor) <= 0.5 * atr else anchor + sign * 0.25 * atr
        zone = sorted([anchor - sign * 0.25 * atr, anchor + sign * 0.5 * atr])
        confirmation = ("A daily close back {} the prior session's {} while holding the {}; RSI turning {} "
                        "from its reset.".format("above" if side == "long" else "below",
                                                 "high" if side == "long" else "low", setup["anchor"],
                                                 "up" if side == "long" else "down"))
        # The pullback is wrong once price breaks the low it made on the way
        # down (the last five sessions) or the support band under the anchor,
        # whichever comes first. Chosen by what defines the setup, not by what
        # flatters the ratio; the ATR floor then widens it if it is too close.
        swing_extreme = rd["low_5d"] if side == "long" else rd["high_5d"]
        sup = _support_below(levels, entry, side)
        lv_edge = (sup["band_low"] if side == "long" else sup["band_high"]) if sup else None
        if lv_edge is not None and (entry - lv_edge) * sign > 0 and (lv_edge - swing_extreme) * sign > 0:
            structural = lv_edge - sign * 0.1 * atr
            struct_text = "a close through the {:.2f} {} band".format(
                sup["price"], "support" if side == "long" else "resistance")
        else:
            structural = swing_extreme - sign * 0.1 * atr
            struct_text = "the pullback's {} at {:.2f}".format("low" if side == "long" else "high", swing_extreme)
    stop = trade_math.place_stop(entry, structural, atr, float(values["atr_stop_multiple"]), side)
    tg = _targets(rd, entry, side, atr, setup["kind"], setup.get("level"))
    targets = [t["price"] for t in tg["targets"]]
    target_basis = tg["basis"]
    t1 = targets[0]
    t2 = targets[1] if len(targets) > 1 else None
    rr = trade_math.reward_to_risk(entry, stop["stop"], t1, side) if stop.get("stop") is not None else None
    rr2 = trade_math.reward_to_risk(entry, stop["stop"], t2, side) if (t2 and stop.get("stop") is not None) else None
    hold = trade_math.holding_estimate(entry, t1, atr, hold_max)
    exposure = _earnings_exposure(earnings or {}, rd["as_of"], hold.get("days"))
    sens = (trade_math.sensitivity(entry, stop["stop"], t1, side, zone_low=zone[0], zone_high=zone[1],
                                   spread=spread, slippage_bps=float(values["slippage_bps"]))
            if stop.get("stop") is not None else None)

    # ------------------------------------------------ the case against first
    if not rd["aligned"]:
        obj("The weekly trend is {} while the daily trend is {}: the two timeframes disagree.".format(
            rd["weekly_trend"], rd["daily_trend"]), 2, "alignment")
    if rr is None:
        obj("No valid reward-to-risk: the stop or the target is on the wrong side of entry.", 3, "rr")
    elif rr < values["rr_avoid_below"]:
        obj("Reward-to-risk is {:.2f} to the first target, below the {:g} minimum.".format(
            rr, values["rr_avoid_below"]), 3, "rr")
    elif rr < values["rr_cap_b_below"]:
        obj("Reward-to-risk is only {:.2f} to the first target.".format(rr), 2, "rr")
    elif rr < values["rr_s_min"]:
        obj("Reward-to-risk is {:.2f}, short of the {:g} an S needs.".format(rr, values["rr_s_min"]), 1, "rr")
    if exposure.get("in_window"):
        obj("Earnings on {} fall inside the holding window: a gap through the stop is possible, and no "
            "level protects against it.".format(exposure["date"]), 3, "earnings")
    elif exposure.get("known") is False:
        obj(exposure["text"], 1, "earnings")
    elif exposure.get("confirmed") is False:
        obj("The earnings date ({}) is an estimate; if it moves earlier it could land in the window.".format(
            exposure["date"]), 1, "earnings")
    rs = rd.get("relative_strength") or {}
    m1, m3 = (rs.get("SPY_1m") or {}).get("excess_pct"), (rs.get("SPY_3m") or {}).get("excess_pct")
    outperform = None
    if m1 is not None and m3 is not None:
        lagging = [lbl for lbl, x in (("one month", m1), ("three months", m3)) if (x or 0) * sign < 0]
        outperform = not lagging
        if len(lagging) == 2:
            obj("{} the S&P 500 over both one month ({:+.1f} points) and three months ({:+.1f} points).".format(
                "Lagging" if side == "long" else "Beating", m1, m3), 2, "relative")
        elif lagging:
            obj("{} the S&P 500 over {}.".format("Lagging" if side == "long" else "Beating", lagging[0]), 1, "relative")
    bm = (rd.get("benchmark") or {}).get("state")
    if (bm == "risk-off" and side == "long") or (bm == "risk-on" and side == "short"):
        obj("The market is {} (SPY {} its 50- and 200-day averages), against a {}.".format(
            bm, "below" if bm == "risk-off" else "above", side), 2, "benchmark")
    if tg["obstacles"]:
        near_lv = min(tg["obstacles"], key=lambda lv: abs(lv["price"] - entry))
        strong = (near_lv.get("strength") or 0) >= TARGET_MIN_STRENGTH or near_lv.get("kind") == "52-week extreme"
        obj("A {} at {:.2f} sits less than one ATR beyond entry, so the trade starts into it.".format(
            "52-week extreme" if near_lv.get("kind") == "52-week extreme" else
            ("resistance" if side == "long" else "support"), near_lv["price"]), 2 if strong else 1, "levels")
    if tg["projected"]:
        obj("The target is a projection, not a level on the chart: {}".format(tg["basis"]), 1, "target")
    r14 = rd.get("rsi14") or 50
    if (side == "long" and r14 > 70) or (side == "short" and r14 < 30):
        obj("RSI {:.0f} is stretched; momentum readings at that level often pause.".format(r14), 1, "momentum")
    if rd.get("macd_hist_rising") is not None and rd["macd_hist_rising"] != (side == "long"):
        obj("MACD momentum is fading against the trade.", 1, "momentum")
    if setup["kind"] == "breakout" and (rd.get("relative_volume") or 0) < 1.0:
        obj("Volume today is {:.2f}x its average: a breakout without volume is unconfirmed.".format(
            rd.get("relative_volume") or 0), 1, "volume")
    if stop.get("stop") is not None and abs(entry - stop["stop"]) > 3.0 * atr:
        obj("The structural stop is {:.1f} ATRs away, a wide risk per share.".format(
            abs(entry - stop["stop"]) / atr), 1, "stop")
    if (rd.get("atr_pct") or 0) > 5:
        obj("Daily range is {:.1f}% of price: high volatility makes gaps and slippage larger.".format(
            rd["atr_pct"]), 1, "volatility")

    # ----------------------------------------------------------- the grade
    criteria = {
        "daily_weekly_aligned": bool(rd["aligned"]),
        "reward_to_risk_ok": rr is not None and rr >= values["rr_s_min"],
        "no_earnings_in_window": exposure.get("in_window") is False,
        "clear_invalidation": stop.get("basis") in ("structure", "atr") and stop.get("structural") is not None,
        "outperforms_benchmark": bool(outperform),
        "sufficient_data": True,
    }
    grade, rules = decide_grade(criteria, objections, rr, bool(exposure.get("in_window")), values, event_strategy)
    meaningful = [o for o in objections if o["severity"] >= 2 and o["kind"] not in ("rr", "earnings")]
    worst = max(objections, key=lambda o: o["severity"]) if objections else None
    plan = {
        "side": side, "kind": setup["kind"],
        "entry": _f(entry), "entry_zone": [_f(zone[0]), _f(zone[1])],
        "confirmation": confirmation,
        "invalidation": {"price": _f(stop.get("stop")), "structural": _f(stop.get("structural")),
                         "basis": stop.get("basis"), "widened": stop.get("widened"),
                         "structure": struct_text, "note": stop.get("note"),
                         "atr_floor": _f(stop.get("atr_floor"))},
        "targets": [_f(t1)] + ([_f(t2)] if t2 else []), "target_basis": target_basis,
        "target_detail": tg["targets"], "obstacles": [_f(o.get("price")) for o in tg["obstacles"]],
        "reward_to_risk": _f(rr), "reward_to_risk_t2": _f(rr2),
        "rr_formula": ("(target - entry) / (entry - stop)" if side == "long"
                       else "(entry - target) / (stop - entry)"),
        "sensitivity": _round_sens(sens),
        "holding": hold, "earnings": exposure,
        "reassess": ("If neither the first target nor the stop has been reached within about {} trading days, "
                     "reassess: the setup assumed a move at roughly that pace, and a trade that goes nowhere "
                     "ties up risk.".format(hold.get("days") or hold_max)),
    }
    if stop.get("stop") is not None:
        gap = (stop["stop"] - sign * 1.0 * atr)
        plan["sizing_example"] = trade_math.sizing_example(10000.0, 1.0, entry, stop["stop"], gap_price=gap, side=side)
        plan["sizing_example"]["label"] = ("Illustration only: a 10,000 account risking 1%. Your own account "
                                           "size and risk tolerance replace both numbers.")
    return {"grade": grade, "readings": rd, "setup": setup, "plan": plan, "objections": objections,
            "most_damaging": worst, "criteria": criteria, "rules": rules,
            "why": _grade_why(grade, criteria, meaningful, rr, rules),
            "framework_note": FRAMEWORK_NOTE}


def decide_grade(criteria: Dict[str, bool], objections: List[Dict[str, Any]], rr: Optional[float],
                 earnings_in_window: bool, values: Dict[str, Any],
                 event_strategy: bool = False) -> "tuple":
    """The grade from the criteria and the objections, then the policy caps.
    Returns (grade, rules applied). Pure, so each rule is tested on its own.

    Order matters: the minimums first (Avoid), then the S/A/B ladder, then the
    caps, which can only lower a grade. An objection about reward-to-risk or
    earnings is not also counted as a "meaningful caveat", because each has
    its own rule and counting it twice would punish it twice."""
    rules: List[Dict[str, Any]] = []
    meaningful = [o for o in objections if o["severity"] >= 2 and o["kind"] not in ("rr", "earnings")]
    severe = [o for o in objections if o["severity"] >= 2]
    if rr is None or rr < values["rr_avoid_below"]:
        rules.append({"rule": "rr_avoid_below", "value": values["rr_avoid_below"],
                      "text": "Reward-to-risk below {:g} is Avoid.".format(values["rr_avoid_below"])})
        return "Avoid", rules
    if len(severe) >= 3:
        rules.append({"rule": "opposing_evidence", "value": len(severe),
                      "text": "Three or more serious objections: the evidence against outweighs the setup."})
        return "Avoid", rules
    if all(criteria.values()) and not meaningful:
        grade = "S"
    elif len(meaningful) <= 1 and rr >= values["rr_cap_b_below"]:
        grade = "A"
    else:
        grade = "B"
    if grade in ("S", "A") and rr < values["rr_cap_b_below"]:
        grade = "B"
        rules.append({"rule": "rr_cap_b_below", "value": values["rr_cap_b_below"],
                      "text": "Reward-to-risk from {:g} to below {:g} caps the grade at B.".format(
                          values["rr_avoid_below"], values["rr_cap_b_below"])})
    if earnings_in_window and grade in ("S", "A") and not event_strategy:
        grade = values["earnings_in_window_cap"]
        rules.append({"rule": "earnings_in_window_cap", "value": values["earnings_in_window_cap"],
                      "text": "An earnings release inside the holding window caps an ordinary swing grade at {}. "
                              "An event trade would need its own evaluation (options pricing, the expected "
                              "move), which this grade is not.".format(values["earnings_in_window_cap"])})
    return grade, rules


FRAMEWORK_NOTE = ("Grades follow this framework's stated rules (S needs aligned timeframes, reward-to-risk of "
                  "2.5 or more, no earnings in the window, a clear invalidation and outperformance of the "
                  "market). They are not probabilities and have not been shown to predict returns.")


def _round_sens(sens: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not sens:
        return None
    return {"representative": _f(sens.get("representative")), "low": _f(sens.get("low")),
            "high": _f(sens.get("high")),
            "cases": [{"case": c["case"], "entry": _f(c["entry"]), "rr": _f(c["rr"])} for c in sens["cases"]]}


CRITERIA_TEXT = {
    "daily_weekly_aligned": "daily and weekly trends agreeing",
    "reward_to_risk_ok": "reward-to-risk of 2.5 or more",
    "no_earnings_in_window": "no earnings release in the window (or a known date)",
    "clear_invalidation": "a clear invalidation level",
    "outperforms_benchmark": "outperformance of the S&P 500 over one and three months",
    "sufficient_data": "sufficient data",
}


def _grade_why(grade: str, criteria: Dict[str, bool], meaningful: List[Dict[str, Any]], rr: Optional[float],
               rules: List[Dict[str, Any]]) -> str:
    missing = [CRITERIA_TEXT.get(k, k) for k, ok in criteria.items() if not ok]
    if grade == "S":
        return "Every S criterion holds and no serious objection was found."
    if grade == "Avoid":
        return rules[0]["text"] if rules else "Fails the framework's minimum requirements."
    base = {"A": "A strong setup with one meaningful caveat", "B": "Viable but materially flawed"}[grade]
    if rules:
        t = rules[-1]["text"]
        return "{}: {}".format(base, t[0].lower() + t[1:])
    return "{}{}.".format(base, "; an S would also need " + ", ".join(missing) if missing else "")


def _reassess_when(rd: Dict[str, Any], setup: Dict[str, Any]) -> str:
    atr = rd.get("atr14") or 0
    if setup.get("extended"):
        return ("A pullback toward the 20-day EMA (about {:.2f}) with RSI back under 60 would give a defined "
                "entry and a nearer invalidation.".format(rd["ema20"]))
    if setup.get("side") and setup.get("side") in ("long", "short"):
        lv = rd.get("high_20d") if setup["side"] == "long" else rd.get("low_20d")
        return ("A pullback to the 20-day EMA near {:.2f}, or a daily close {} the 20-day {} at {:.2f} on "
                "volume at least 1.5x average, would define a setup.".format(
                    rd["ema20"], "above" if setup["side"] == "long" else "below",
                    "high" if setup["side"] == "long" else "low", lv))
    return ("A daily close back above the 200-day average (about {:.2f}) with the 50-day turning up, or a clear "
            "break below it with the 50-day turning down, would give the trend a direction.".format(
                rd.get("sma200") or 0))
