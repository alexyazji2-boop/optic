"""Macro regime panel: volatility, dollar, rates, commodities, credit, crypto.

The point isn't a wall of quotes — it's a single risk-on / risk-off read that
tells you whether to press directional swing trades or stand down, assembled
from the cross-asset signals that actually lead equities.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from .. import fred
from .series_stats import _f, apply_quote, live_quotes, snapshot
from .technicals import atr

# The rule of 16. The VIX is the S&P's implied volatility for a year, and a year
# has about 252 trading days, whose square root (15.9) is close to 16: so the
# VIX over 16 is the one-standard-deviation daily move the options price.
# Asked for as "calculating VIX/16 for expected S&P volatility being price from
# its options", beside the ATR.
RULE_OF_16 = 16.0
# A day's true range runs wider than its close-to-close move. For a random walk
# the expected high-to-low range is sqrt(8/pi), about 1.6 standard deviations
# (Parkinson, 1980), so the ATR over 1.6 puts the index's own days on the
# footing VIX/16 is on. Without it a 0.9% ATR beside a 1.0% VIX/16 reads as
# options pricing what the tape delivers, when they are pricing nearly twice.
RANGE_PER_SIGMA = 1.6

# Yahoo symbols for the macro complex. Grouped so the UI can lay them out.
#
# `name` and `about` are for an instrument's own page, which headed DXY "DXY"
# over "US dollar index" in small type and was asked to make "clearer that this
# subchart for the ticker DXY is for the US dollar index", and then to do the
# same for VIX, HYG, LQD, TLT and VVIX. The heading is the name with the label
# after it, and `about` says what the thing measures and how to read a move in
# it.
# The tables and the strip keep the short label and the note.
INSTRUMENTS: List[Dict[str, str]] = [
    {"symbol": "^VIX", "label": "VIX", "group": "volatility", "note": "S&P 30-day implied vol",
     "name": "Cboe Volatility Index",
     "about": "The 30-day volatility that S&P 500 options are pricing, as an annual "
              "percentage. A rising VIX means investors are paying more for "
              "protection, which usually happens when stocks fall."},
    {"symbol": "^VVIX", "label": "VVIX", "group": "volatility", "note": "vol of vol",
     "name": "Cboe VIX of VIX Index",
     "about": "The 30-day volatility that the VIX's own options are pricing, so how "
              "far the VIX itself is expected to move. A rising VVIX means investors "
              "are paying more to hedge a jump in volatility."},
    {"symbol": "DX-Y.NYB", "label": "DXY", "group": "fx", "note": "US dollar index",
     "name": "US Dollar Index",
     "about": "The US dollar against a basket of six major currencies: the euro "
              "(about 58%), Japanese yen, British pound, Canadian dollar, Swedish "
              "krona and Swiss franc. A rising index means a stronger dollar."},
    {"symbol": "USDJPY=X", "label": "USD/JPY", "group": "fx", "note": "yen carry proxy"},
    {"symbol": "EURUSD=X", "label": "EUR/USD", "group": "fx", "note": "euro"},
    {"symbol": "^TNX", "label": "US 10Y", "group": "rates", "note": "10-year yield"},
    {"symbol": "^FVX", "label": "US 5Y", "group": "rates", "note": "5-year yield"},
    {"symbol": "^IRX", "label": "US 3M", "group": "rates", "note": "13-week bill"},
    {"symbol": "CL=F", "label": "WTI Crude", "group": "commodities", "note": "oil"},
    {"symbol": "NG=F", "label": "Nat Gas", "group": "commodities", "note": "natural gas"},
    {"symbol": "GC=F", "label": "Gold", "group": "commodities", "note": "gold"},
    {"symbol": "HG=F", "label": "Copper", "group": "commodities", "note": "growth bellwether"},
    {"symbol": "HYG", "label": "HYG", "group": "credit", "note": "high-yield credit",
     "name": "iShares iBoxx $ High Yield Corporate Bond ETF",
     "about": "A fund of US dollar corporate bonds rated below investment grade, so "
              "its price carries default risk as well as interest rates. It is read "
              "as credit appetite, and equities rarely rally against falling credit."},
    {"symbol": "LQD", "label": "LQD", "group": "credit", "note": "investment grade",
     "name": "iShares iBoxx $ Investment Grade Corporate Bond ETF",
     "about": "A fund of US dollar investment-grade corporate bonds. Defaults are "
              "rare at that grade, so it moves mostly with Treasury yields, falling "
              "when they rise."},
    {"symbol": "TLT", "label": "TLT", "group": "credit", "note": "20y+ treasuries",
     "name": "iShares 20+ Year Treasury Bond ETF",
     "about": "A fund of US Treasury bonds with more than 20 years left to maturity. "
              "Its price moves opposite to long-term yields, and further than a "
              "shorter bond's would."},
    {"symbol": "BTC-USD", "label": "Bitcoin", "group": "crypto", "note": "risk appetite proxy"},
    {"symbol": "^GSPC", "label": "S&P 500", "group": "equity", "note": "benchmark"},
    {"symbol": "^NDX", "label": "Nasdaq 100", "group": "equity", "note": "growth"},
    {"symbol": "^RUT", "label": "Russell 2000", "group": "equity", "note": "small caps"},
    # The index futures, which is the answer to "what is the market doing right
    # now" for the sixteen hours a day the cash indices above are not answering
    # it. Measured on a Sunday at 21:18 ET, with the overnight session open:
    # ^GSPC's last print was Friday 19:59 and ES=F's was 21:08, ten minutes old.
    #
    # Their own group rather than folded into `equity`, because they are a
    # different instrument and not a better quote for the same one. A future
    # carries basis and its own expiry, so ES at 7,622 is not the S&P at 7,622,
    # and a strip that quietly swapped one for the other would be publishing a
    # number under a label that does not describe it.
    {"symbol": "ES=F", "label": "S&P 500 futures", "group": "futures",
     "note": "E-mini S&P, trades overnight"},
    {"symbol": "NQ=F", "label": "Nasdaq 100 futures", "group": "futures",
     "note": "E-mini Nasdaq, trades overnight"},
    {"symbol": "RTY=F", "label": "Russell 2000 futures", "group": "futures",
     "note": "E-mini Russell, trades overnight"},
]

# Cross-asset ratios. Each carries the direction that means risk-on so the
# scorer doesn't need a special case per pair.
RATIOS: List[Dict[str, Any]] = [
    {
        "name": "Copper / Gold",
        "numer": "HG=F",
        "denom": "GC=F",
        "risk_on_when": "rising",
        "reads": "industrial demand vs safety bid. A growth thermometer",
    },
    {
        "name": "HYG / TLT",
        "numer": "HYG",
        "denom": "TLT",
        "risk_on_when": "rising",
        "reads": "credit appetite vs duration safety; equities rarely rally against falling credit",
        # TLT is twenty-year Treasuries and HYG is short-dated junk, so a move in
        # rates moves TLT several times as far. See `_rates_led`.
        "duration_leg": "denom",
    },
    {
        "name": "Russell / S&P",
        "numer": "^RUT",
        "denom": "^GSPC",
        "risk_on_when": "rising",
        "reads": "small-cap participation. Breadth confirmation",
    },
    {
        "name": "Nasdaq / S&P",
        "numer": "^NDX",
        "denom": "^GSPC",
        "risk_on_when": "rising",
        "reads": "growth vs broad market leadership",
    },
]


def _expected_move(snaps: Dict[str, Dict[str, Any]], frames: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """The S&P's daily move as its options price it (VIX / 16), against the
    index's own average day (ATR 14), on one footing. None without the VIX, the
    S&P or a month of its bars."""
    vix = (snaps.get("^VIX") or {}).get("last")
    spot = (snaps.get("^GSPC") or {}).get("last")
    frame = frames.get("^GSPC")
    if not vix or not spot or frame is None or len(frame) < 30:
        return None
    try:
        range_now = float(atr(frame, 14).iloc[-1])
        close = float(frame["Close"].iloc[-1])
    except (KeyError, IndexError, TypeError, ValueError):
        return None
    if not np.isfinite(range_now) or not close:
        return None
    implied_pct = vix / RULE_OF_16
    atr_pct = range_now / close * 100.0
    realized_pct = atr_pct / RANGE_PER_SIGMA
    ratio = implied_pct / realized_pct if realized_pct else None
    if ratio is None:
        reading = "The index has not moved enough lately to compare."
    elif ratio > 1.25:
        reading = ("Options are pricing about {:.1f} times the movement the index has been "
                   "delivering. Protection is dear against what the tape is doing.".format(ratio))
    elif ratio < 0.8:
        reading = ("Options are pricing less movement than the index has been delivering. "
                   "Protection is cheap against what the tape is doing.")
    else:
        reading = "Options are pricing about the movement the index has been delivering."
    return {
        "vix": _f(vix, 2),
        "spot": _f(spot, 2),
        "implied_pct": _f(implied_pct, 3),
        "implied_points": _f(spot * implied_pct / 100.0, 1),
        "atr14": _f(range_now, 2),
        "atr_pct": _f(atr_pct, 3),
        "realized_pct": _f(realized_pct, 3),
        "ratio": _f(ratio, 2) if ratio is not None else None,
        "reading": reading,
    }


# ------------------------------------------------------------------ bonds
#
# Asked "does the macro tab take into account whats going on with the bond
# markets right now?" on 1 October 2026, with the 10-year at 5.29%, up half a
# point in September, the 2-year up as much and the high-yield spread 46bp
# wider. The bonds were most of a -12.2 score and still undercounted: the
# 10-year term was scored on the yield's percent change and capped at -4, which
# a quarter point reaches, so half the month went uncounted; the credit term was
# HYG's price, which moves with Treasury yields as well as with default risk;
# HYG / TLT read "risk-on" because Treasuries fell faster than junk bonds; and
# the notes said nothing about bonds.
#
# So the 10-year is scored in basis points, credit on the spread itself where
# FRED has it, the ratio says when its move is rates, and a move this size is
# written into the notes.

YIELD_SESSIONS = 20
# Per basis point of the 10-year's move over YIELD_SESSIONS. A rise counts in
# full and a fall counts half: a fast fall in yields is as often a flight to
# safety as relief, and the VIX and the spread carry which of the two it is.
YIELD_RISE_PER_BP, YIELD_RISE_CAP = 0.2, 10.0      # a half-point month reaches it
YIELD_FALL_PER_BP, YIELD_FALL_CAP = 0.1, 5.0
# A move the notes mention, and how close to its 52-week high the yield has to
# be for them to say "near its 52-week high", both in basis points.
YIELD_NOTE_BP, YIELD_NEAR_HIGH_BP = 25.0, 10.0

# ICE BofA US High Yield option-adjusted spread, daily, in percent: the yield
# junk bonds pay over Treasuries, so default risk without the rates in HYG.
HY_SPREAD_SERIES = "BAMLH0A0HYM2"
SPREAD_PER_BP, SPREAD_CAP = 0.1, 12.5              # the cap is HYG's, reached at 125bp
SPREAD_NOTE_BP = 25.0
# Read on every macro load. FRED's copy is cached for six hours, but a miss
# waits on the network, so it gets a short timeout and, after a failure,
# fifteen minutes before it is tried again; HYG stands in meanwhile.
HY_TIMEOUT_SECONDS = 4.0
HY_RETRY_SECONDS = 15 * 60
_HY_FAILED_AT = [0.0]


def _hy_spread_rows() -> List[Tuple[str, float]]:
    """The high-yield spread's daily values from FRED, or [] while it is out."""
    now = time.time()
    if now - _HY_FAILED_AT[0] < HY_RETRY_SECONDS:
        return []
    rows = fred.observations(HY_SPREAD_SERIES, timeout=HY_TIMEOUT_SECONDS)
    if not rows:
        _HY_FAILED_AT[0] = now
    return rows


def _bp_move(values: List[float], sessions: int) -> Optional[float]:
    """The change over `sessions` observations, in basis points of a percent."""
    if len(values) <= sessions:
        return None
    return round((float(values[-1]) - float(values[-1 - sessions])) * 100.0, 1)


def _yield_factor(bp: float) -> Tuple[float, str]:
    if bp > 0:
        contribution = -min(bp * YIELD_RISE_PER_BP, YIELD_RISE_CAP)
    else:
        contribution = min(-bp * YIELD_FALL_PER_BP, YIELD_FALL_CAP)
    rule = "{} {:.0f}bp in {} sessions; -{:.1f} per bp up, capped at -{:.0f}, " \
           "+{:.1f} per bp down, capped at +{:.0f}".format(
               "up" if bp > 0 else "down", abs(bp), YIELD_SESSIONS, YIELD_RISE_PER_BP,
               YIELD_RISE_CAP, YIELD_FALL_PER_BP, YIELD_FALL_CAP)
    return contribution, rule


def _rates_led(spec: Dict[str, Any], a_chg: Optional[float], b_chg: Optional[float]) -> Optional[str]:
    """Why a credit-versus-duration ratio's move is rates, or None.

    When both legs move the same way and the duration leg moves further, the
    ratio moves because of rates. On 1 October HYG was down 2.8% over twenty
    sessions and TLT down 5.2%, so HYG / TLT rose 2.5% and read "risk-on": junk
    bonds were not in demand, Treasuries were falling faster.
    """
    if spec.get("duration_leg") != "denom" or a_chg is None or b_chg is None:
        return None
    if a_chg < 0 and b_chg < 0 and b_chg < a_chg:
        return ("Both fell over 20 sessions and Treasuries fell further, so the "
                "ratio's rise is rates, not credit appetite.")
    if a_chg > 0 and b_chg > 0 and b_chg > a_chg:
        return ("Both rose over 20 sessions and Treasuries rose further, so the "
                "ratio's fall is rates, not a move to safety.")
    return None


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
        "rule": "{:+.1f} per 1% move, capped at {:+.0f}".format(
            -weight if invert else weight, weight * 5),
        "kind": "scaled",
    }


def _step(name: str, value: Optional[float], contribution: float,
          rule: str) -> Dict[str, Any]:
    """Record a threshold rule as a factor, so the decomposition is complete.

    The score is a mix of two kinds of rule: continuous components scaled by a
    weight, and threshold steps like "VIX under 18 adds 10". Only the continuous
    ones were being recorded, so `factors` summed to 14.2 against a headline score
    of 24.2 — the missing 10 was the VIX level step, and crude and the curve were
    absent entirely.

    That gap is worse than untidy. The panel is supposed to let a reader audit the
    number, and a decomposition that does not add up to the thing it decomposes
    invites the reasonable conclusion that one of them is wrong. `rule` carries the
    threshold that fired, because for a step the band matters more than the value.
    """
    return {"factor": name, "value": value,
            "contribution": round(float(contribution), 2), "rule": rule,
            "kind": "step"}


def analyse(provider) -> Dict[str, Any]:
    """Full macro panel + risk regime verdict."""
    symbols = [item["symbol"] for item in INSTRUMENTS]
    frames = provider.batch_history(symbols, period="1y", interval="1d")

    # Half this strip trades around the clock, and for those rows a daily frame
    # cannot produce the session's change on its own — see `apply_quote`. Rows
    # the quote feed does not cover keep the bar arithmetic.
    quotes = live_quotes(provider, symbols)

    snaps: Dict[str, Dict[str, Any]] = {}
    for item in INSTRUMENTS:
        frame = frames.get(item["symbol"])
        if frame is None:
            snaps[item["symbol"]] = dict(item, error="no data")
            continue
        snap = apply_quote(snapshot(frame, item["label"]),
                           quotes.get(item["symbol"]))
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

        def leg_chg(col: str) -> Optional[float]:
            leg = joined[col]
            if len(leg) <= 20 or leg.iloc[-21] == 0:
                return None
            return float((leg.iloc[-1] / leg.iloc[-21] - 1.0) * 100.0)

        why_rates = _rates_led(spec, leg_chg("a"), leg_chg("b")) if trend else None
        if why_rates:
            trend = "rates-led"

        ratio_rows.append(
            {
                "name": spec["name"],
                "reads": spec["reads"],
                "level": _f(line.iloc[-1], 6),
                "chg_5d": chg(5),
                "chg_20d": chg_20,
                "chg_60d": chg(60),
                "signal": trend,
                "signal_note": why_rates,
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
            adj, band = 18, "below 14"
            notes.append("VIX {:.1f}. Complacent tape, trend-following works, hedges are cheap".format(vix_level))
        elif vix_level < 18:
            adj, band = 10, "14 to 18"
            notes.append("VIX {:.1f}. Normal vol regime".format(vix_level))
        elif vix_level < 25:
            adj, band = -8, "18 to 25"
            notes.append("VIX {:.1f}. Elevated; size down and widen stops".format(vix_level))
        elif vix_level < 32:
            adj, band = -20, "25 to 32"
            notes.append("VIX {:.1f}. Stressed; premium selling favored over directional longs".format(vix_level))
        else:
            adj, band = -30, "above 32"
            notes.append("VIX {:.1f}. Panic regime; mean-reversion bounces are violent both ways".format(vix_level))
        score += adj
        # The single largest term in the score, and it was missing from the
        # decomposition entirely.
        factors.append(_step("VIX level", vix_level, adj, "in the " + band + " band"))

    contrib, row = _score_component("VIX 5-day change", vix.get("chg_5d"), 1.2, invert=True)
    score += contrib
    if row:
        factors.append(row)

    for symbol, name, weight, invert in (
        ("^GSPC", "S&P 500 20-day", 2.0, False),
        ("DX-Y.NYB", "Dollar 20-day", 1.5, True),
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
            adj, band = -15, "a fall steeper than 2% in a week"
            notes.append(
                "USD/JPY down {:.1f}% in a week. Yen-carry unwind risk, historically drags risk assets".format(abs(jpy_5d))
            )
        elif jpy_5d > 1.5:
            adj, band = 6, "a rise above 1.5%"
            notes.append("USD/JPY up {:.1f}%. Carry trade supportive".format(jpy_5d))
        else:
            adj, band = 0, "inside the -2% to +1.5% band, so no adjustment"
        score += adj
        factors.append(_step("USD/JPY 5-day", jpy_5d, adj, band))

    # Crude: moderate strength is demand, a spike is a cost shock.
    oil_20 = snaps.get("CL=F", {}).get("chg_20d")
    if oil_20 is not None:
        if oil_20 > 15:
            adj, band = -10, "up more than 15% in a month"
            notes.append("Crude +{:.0f}% in a month. Inflation/cost-shock headwind".format(oil_20))
        elif oil_20 > 3:
            adj, band = 4, "up 3% to 15%"
            notes.append("Crude firm. Consistent with demand growth")
        elif oil_20 < -15:
            adj, band = -5, "down more than 15%"
            notes.append("Crude -{:.0f}%. Demand-destruction signal".format(abs(oil_20)))
        else:
            adj, band = 0, "inside the -15% to +3% band, so no adjustment"
        score += adj
        factors.append(_step("Crude 20-day", oil_20, adj, band))

    # The 10-year, in basis points. See YIELD_RISE_PER_BP.
    tnx_frame = frames.get("^TNX")
    tnx_bars = ([float(v) for v in tnx_frame["Close"].dropna()]
                if tnx_frame is not None and not tnx_frame.empty else [])
    y10_bp = _bp_move(tnx_bars, YIELD_SESSIONS)
    if y10_bp is not None:
        adj, rule = _yield_factor(y10_bp)
        score += adj
        factors.append({"factor": "10-year yield 20-day", "value": y10_bp, "unit": "bp",
                        "contribution": round(adj, 2), "rule": rule, "kind": "scaled"})
        tnx = snaps.get("^TNX", {})
        if abs(y10_bp) >= YIELD_NOTE_BP and tnx.get("last") is not None:
            high = tnx.get("high_52w")
            near_high = (y10_bp > 0 and high is not None
                         and (high - tnx_bars[-1]) * 100.0 <= YIELD_NEAR_HIGH_BP)
            notes.append("10-year yield {:.2f}%, {} {:.0f}bp in {} sessions{}. {}".format(
                tnx["last"], "up" if y10_bp > 0 else "down", abs(y10_bp), YIELD_SESSIONS,
                ", near its 52-week high" if near_high else "",
                "Bonds are selling off" if y10_bp > 0 else "Bonds are rallying"))

    # Credit: the high-yield spread where FRED has it, HYG's price where not.
    spread_rows = _hy_spread_rows()
    spread_bp = _bp_move([v for _, v in spread_rows], YIELD_SESSIONS)
    if spread_bp is not None:
        level, as_of = spread_rows[-1][1], spread_rows[-1][0]
        adj = float(np.clip(-spread_bp * SPREAD_PER_BP, -SPREAD_CAP, SPREAD_CAP))
        score += adj
        factors.append({
            "factor": "High-yield spread 20-day", "value": spread_bp, "unit": "bp",
            "contribution": round(adj, 2), "level": level, "as_of": as_of,
            "rule": "{:.2f}% on {}, {:.0f}bp {} in {} sessions; -{:.1f} per bp wider, "
                    "capped at {:.1f} either way".format(
                        level, as_of, abs(spread_bp),
                        "wider" if spread_bp > 0 else "tighter", YIELD_SESSIONS,
                        SPREAD_PER_BP, SPREAD_CAP),
            "kind": "scaled"})
        if abs(spread_bp) >= SPREAD_NOTE_BP:
            notes.append("High-yield spread {:.2f}%, {:.0f}bp {} in {} sessions. {}".format(
                level, abs(spread_bp), "wider" if spread_bp > 0 else "tighter", YIELD_SESSIONS,
                "Credit is pricing more default risk" if spread_bp > 0
                else "Credit appetite is strong"))
    else:
        contrib, row = _score_component("High-yield credit 20-day",
                                        snaps.get("HYG", {}).get("chg_20d"), 2.5)
        score += contrib
        if row:
            factors.append(row)

    # Curve shape from the yield proxies we have.
    y10 = snaps.get("^TNX", {}).get("last")
    y3m = snaps.get("^IRX", {}).get("last")
    curve = None
    if y10 is not None and y3m is not None:
        curve = round(y10 - y3m, 3)
        if curve < 0:
            adj, band = -6, "inverted"
            notes.append("3m/10y curve inverted ({:.2f}). Late-cycle backdrop".format(curve))
        else:
            adj, band = 0, "positive, so no adjustment"
            notes.append("3m/10y curve positive ({:.2f})".format(curve))
        score += adj
        factors.append(_step("3m/10y curve", curve, adj, band))

    breadth_ratio = next((r for r in ratio_rows if r["name"] == "Russell / S&P"), None)
    if breadth_ratio and breadth_ratio.get("chg_20d") is not None:
        if breadth_ratio["chg_20d"] < -3:
            notes.append("Small caps lagging badly. Rally is narrow, be selective")
        elif breadth_ratio["chg_20d"] > 3:
            notes.append("Small caps leading. Broad participation supports breakouts")

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
        regime, stance = "neutral / mixed", "No macro edge. Trade the setup, not the market."

    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for item in INSTRUMENTS:
        grouped.setdefault(item["group"], []).append(snaps[item["symbol"]])

    attributed = sum(f["contribution"] for f in factors
                     if f.get("contribution") is not None)
    return {
        "regime": regime,
        "risk_score": round(score, 1),
        "stance": stance,
        "notes": notes,
        "factors": factors,
        # The decomposition must add up to the number it decomposes. Carried on
        # the payload rather than trusted, because it silently stopped adding up
        # once and nothing surfaced it: `factors` summed to 14.2 beside a score of
        # 24.2 for as long as the step rules went unrecorded. `unattributed` is
        # non-zero only if the score is clipped at its bounds or a rule is added
        # without a factor, and the panel says so instead of quietly disagreeing
        # with itself.
        "score_attributed": round(attributed, 1),
        "score_unattributed": round(score - attributed, 1),
        "curve_3m10y": curve,
        "expected_move": _expected_move(snaps, frames),
        "instruments": snaps,
        "groups": grouped,
        "ratios": ratio_rows,
    }
