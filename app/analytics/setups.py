"""Swing setups: explainable entry rules on completed candles, and their lifecycle.

Asked for as a "swing-trade setup scanner and entry-alert system" that finds
bullish and bearish entry setups it can explain, and raises alerts for review
rather than placing anything. Every rule here is a hypothesis to test. None of
them is a strategy shown to make money, and nothing in this module says one is.

**One engine, many presets.** A preset is a family of rule (trend pullback,
Donchian breakout and so on) with its parameters filled in. Every preset is
evaluated the same way, in four parts that are kept apart so a reader can check
each one:

* **Context**: is the backdrop right? The higher-timeframe trend, the market
  regime and relative strength against a benchmark, each optional.
* **Setup**: the pullback, consolidation, retracement or level test that makes
  a trigger worth waiting for. A setup ARMS; it never triggers anything.
* **Trigger**: the exact event on a completed candle that turns an armed setup
  into a signal.
* **Invalidation**: the price, checked on completed closes, that cancels it.

**States.** Watching (context holds, no setup), Armed (setup present, waiting
for its trigger), Triggered (the trigger fired on a completed candle),
Invalidated (a close beyond the invalidation level) and Expired (an armed setup
that never triggered, or a signal past the bars it stays on the list for).

**Information only from before the signal.** Every indicator here is causal:
its value at a bar uses that bar and earlier ones, nothing after. The forming
candle is left out unless a caller asks for a provisional read, which is marked
as such and never alerts. A swing pivot becomes usable only once its
confirmation bars have printed, so a Fibonacci grid or an anchored VWAP never
starts from a low nobody could have known was the low. A higher-timeframe
filter reads completed weekly (or daily) candles only.

**Bearish rules are the bullish rules on a mirrored chart.** Negate every price
(the high becomes the negated low, and so on) and a pullback to a rising average
becomes a rally to a falling one, an oversold RSI becomes an overbought one, a
breakout above the channel becomes a break below it. Running one set of rules
on the mirrored bars is how the two sides are guaranteed to be each other's
mirror image rather than two implementations that drift apart. The written
rules for each side are spelled out in PRESETS all the same, so nobody has to
take the mirror on trust.

**No score dressed as a probability.** What a row reports is "conditions met":
how many of the listed conditions hold, counted once each. RSI, MACD and the
stochastics measure the same thing, momentum, so where a rule uses more than
one they count as one condition. The count is never a chance of success.
"""

from __future__ import annotations

import bisect
import math
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from .. import session as session_mod

ET = session_mod.ET

STATES = ("watching", "armed", "triggered", "invalidated", "expired", "inactive")
DIRECTIONS = ("bull", "bear")
TIMEFRAMES = ("daily", "4h")
KINDS = ("continuation", "reversal")

# Bars of history the lifecycle walks for a scan. A year of daily candles is
# enough to establish what state a preset is in now; the historical evaluation
# walks everything it is given.
SCAN_BARS = 260

# How long after it resolves an invalidated or expired setup still shows as
# such, rather than going back to Watching. Long enough to be seen on a review
# the next morning.
RECENT_BARS = 5

np.seterr(invalid="ignore", divide="ignore")


# ====================================================================== params
#
# Every parameter a rule uses is listed with its range, so the page can build a
# form for it and the server can refuse a value no rule was written for. A
# value outside the range is clamped, not rejected: a slider dragged past its
# end should mean "the end", not a 400.

def _p(key, label, kind, default, lo=None, hi=None, step=None, help_text="", choices=None):
    out = {"key": key, "label": label, "type": kind, "default": default, "help": help_text}
    if lo is not None:
        out["min"] = lo
    if hi is not None:
        out["max"] = hi
    if step is not None:
        out["step"] = step
    if choices is not None:
        out["choices"] = choices
    return out


CONTEXT_PARAMS = [
    _p("htf_filter", "Higher-timeframe trend filter", "bool", True,
       help_text="Daily setups read completed weekly candles; 4-hour setups read "
                 "completed daily candles. Bullish needs the close above a rising "
                 "average, bearish below a falling one."),
    _p("htf_len", "Weekly average length (weeks)", "int", 30, 5, 60, 1,
       "The weekly simple moving average a daily setup's trend is read from."),
    _p("htf_len_4h", "Daily average length (days)", "int", 50, 10, 200, 1,
       "The daily simple moving average a 4-hour setup's trend is read from."),
    _p("htf_slope", "Rising or falling over (higher-timeframe bars)", "int", 4, 1, 20, 1,
       "The average has to be higher (bullish) or lower (bearish) than this many "
       "higher-timeframe bars ago."),
    _p("regime_filter", "Market regime filter", "bool", False,
       help_text="Bullish needs the benchmark above its long average, bearish below."),
    _p("regime_len", "Benchmark average length (days)", "int", 200, 50, 300, 10),
    _p("rs_filter", "Relative strength filter", "bool", False,
       help_text="Bullish needs the stock to have beaten the benchmark over the "
                 "window, bearish to have lagged it."),
    _p("rs_len", "Relative strength window (bars)", "int", 63, 10, 252, 1),
    _p("benchmark", "Benchmark", "symbol", "SPY",
       help_text="The index fund context is measured against."),
]

LIFECYCLE_PARAMS = [
    _p("arm_expiry", "Armed setup waits (bars)", "int", 5, 1, 30, 1,
       "How long an armed setup waits for its trigger before it expires."),
    _p("signal_ttl", "Signal stays listed (bars)", "int", 10, 1, 60, 1,
       "How long a triggered signal stays on the list before it expires."),
    _p("cooldown", "Repeat-alert cooldown (bars)", "int", 5, 0, 60, 1,
       "Bars after a trigger before the same setup may trigger again."),
    _p("stop_buffer_atr", "Invalidation buffer (ATR)", "float", 0.25, 0.0, 2.0, 0.05,
       "Distance beyond the structural level, in average true ranges, at which "
       "the setup is invalidated."),
]


# --------------------------------------------------------------------- presets

def _rules(bull: str, bear: str) -> Dict[str, str]:
    return {"bull": bull, "bear": bear}


PRESETS: List[Dict[str, Any]] = [
    {
        "id": "trend_pullback", "family": "trend", "kind": "continuation",
        "label": "Trend pullback to the 21 EMA",
        "params": [
            _p("ema_len", "Pullback average (EMA)", "int", 21, 5, 100, 1),
            _p("sma_len", "Trend average (SMA)", "int", 50, 20, 200, 1),
            _p("slope_bars", "Trend average rising over (bars)", "int", 10, 1, 60, 1),
            _p("touch_atr", "Counts as a touch within (ATR)", "float", 0.25, 0.0, 2.0, 0.05),
            _p("prior_bars", "Closed beyond the EMA within (bars)", "int", 10, 2, 40, 1,
               "The pullback has to come from the trend side of the average."),
            _p("candle", "Trigger candle must close in the trend's direction", "bool", True),
            _p("need_sma200", "Also require the 50 SMA beyond the 200 SMA", "bool", False),
        ],
        "rules": _rules(
            "Close above a rising 50-day SMA. Price pulls back to within 0.25 ATR of "
            "the 21 EMA after closing above it in the prior 10 bars (armed). A "
            "completed candle that traded at or below the EMA closes back above it, "
            "up on the day (triggered). Invalidated by a close below the pullback's "
            "low less the buffer.",
            "Close below a falling 50-day SMA. Price rallies to within 0.25 ATR of "
            "the 21 EMA after closing below it in the prior 10 bars (armed). A "
            "completed candle that traded at or above the EMA closes back below it, "
            "down on the day (triggered). Invalidated by a close above the rally's "
            "high plus the buffer."),
    },
    {
        "id": "ema_cross", "family": "crossover", "kind": "continuation",
        "label": "EMA 9 / 21 cross with the trend",
        "params": [
            _p("fast_type", "Fast average", "choice", "ema", choices=["ema", "sma"]),
            _p("fast_len", "Fast length", "int", 9, 2, 100, 1),
            _p("slow_type", "Slow average", "choice", "ema", choices=["ema", "sma"]),
            _p("slow_len", "Slow length", "int", 21, 5, 250, 1),
            _p("near_atr", "Armed when the gap is within (ATR)", "float", 0.5, 0.05, 3.0, 0.05),
            _p("swing_bars", "Invalidation from the low of (bars)", "int", 10, 3, 40, 1),
        ],
        "rules": _rules(
            "The fast average closes above the slow one on a completed bar, having "
            "been at or below it the bar before. Armed while the fast average is "
            "below and within 0.5 ATR of the slow one and closing the gap. "
            "Invalidated by a close below the lowest low of the last 10 bars less "
            "the buffer.",
            "The fast average closes below the slow one, having been at or above it "
            "the bar before. Armed while it is above, within 0.5 ATR and closing the "
            "gap. Invalidated by a close above the highest high of the last 10 bars "
            "plus the buffer."),
    },
    {
        "id": "golden_cross", "family": "crossover", "kind": "reversal",
        "label": "SMA 50 / 200 cross",
        "defaults": {"fast_type": "sma", "fast_len": 50, "slow_type": "sma",
                     "slow_len": 200, "near_atr": 1.0, "swing_bars": 20},
        "context": {"htf_filter": False},
        "params_from": "ema_cross",
        "rules": _rules(
            "The 50-day SMA closes above the 200-day SMA, a change in the long trend "
            "rather than a continuation of it, so no trend filter by default.",
            "The 50-day SMA closes below the 200-day SMA, the long trend turning down."),
    },
    {
        "id": "rsi_50", "family": "momentum", "kind": "continuation",
        "label": "RSI reclaims 50",
        "params": [
            _p("rsi_len", "RSI length", "int", 14, 2, 50, 1),
            _p("level", "Midline", "float", 50.0, 30.0, 70.0, 1.0),
            _p("swing_bars", "Invalidation from the low of (bars)", "int", 10, 3, 40, 1),
        ],
        "rules": _rules(
            "With the trend filter passing, RSI(14) dips to 50 or below (armed) and "
            "then closes above 50 on a completed bar (triggered).",
            "With the trend filter passing, RSI(14) rises to 50 or above (armed) and "
            "then closes below 50 (triggered)."),
    },
    {
        "id": "rsi_oversold", "family": "momentum", "kind": "reversal",
        "label": "RSI recovers from oversold",
        "context": {"htf_filter": False},
        "params": [
            _p("rsi_len", "RSI length", "int", 14, 2, 50, 1),
            _p("oversold", "Oversold at or below", "float", 30.0, 5.0, 45.0, 1.0,
               "The bearish version uses 100 minus this: 70 by default."),
            _p("recovery_window", "Recovery within (bars)", "int", 10, 1, 40, 1),
            _p("swing_bars", "Invalidation from the low of (bars)", "int", 10, 3, 40, 1),
        ],
        "rules": _rules(
            "RSI(14) at or below 30 arms the setup and never triggers it on its own. "
            "The trigger is RSI closing back above 30 within 10 bars of that reading. "
            "A reversal rule, so no trend filter by default.",
            "RSI(14) at or above 70 arms it. The trigger is RSI closing back below 70 "
            "within 10 bars. An overbought reading alone does nothing."),
    },
    {
        "id": "macd_cross", "family": "momentum", "kind": "continuation",
        "label": "MACD crosses its signal line",
        "params": [
            _p("macd_fast", "MACD fast", "int", 12, 2, 50, 1),
            _p("macd_slow", "MACD slow", "int", 26, 5, 100, 1),
            _p("macd_signal", "Signal", "int", 9, 2, 50, 1),
            _p("beyond_zero", "Only crosses on the far side of zero", "bool", False,
               "Bullish crosses below zero only, bearish above zero only."),
            _p("swing_bars", "Invalidation from the low of (bars)", "int", 10, 3, 40, 1),
        ],
        "rules": _rules(
            "MACD(12, 26, 9) below its signal line arms it; the MACD line closing "
            "above the signal line on a completed bar triggers it.",
            "MACD above its signal line arms it; the MACD line closing below the "
            "signal line triggers it."),
    },
    {
        "id": "momentum_confirm", "family": "momentum", "kind": "continuation",
        "label": "RSI and MACD agree",
        "params": [
            _p("use_rsi50", "RSI reclaims 50", "bool", True),
            _p("use_oversold", "RSI recovers from oversold", "bool", False),
            _p("use_macd", "MACD crosses its signal", "bool", True),
            _p("combine", "Combine", "choice", "all", choices=["all", "any"],
               help_text="All: every selected event within the window. Any: one is enough."),
            _p("window", "Events within (bars)", "int", 3, 1, 10, 1),
            _p("rsi_len", "RSI length", "int", 14, 2, 50, 1),
            _p("oversold", "Oversold at or below", "float", 30.0, 5.0, 45.0, 1.0),
            _p("swing_bars", "Invalidation from the low of (bars)", "int", 10, 3, 40, 1),
        ],
        "rules": _rules(
            "Each selected momentum event (RSI closing above 50, RSI closing back "
            "above 30 after an oversold reading, MACD closing above its signal) "
            "must happen within 3 bars of the others (all), or one is enough (any). "
            "The trigger bar is the bar the last required event happens on. RSI and "
            "MACD both measure momentum, so this is one condition, not two.",
            "The mirror: RSI closing below 50, RSI closing back below 70 after an "
            "overbought reading, MACD closing below its signal."),
    },
    {
        "id": "fib_zone", "family": "fibonacci", "kind": "continuation",
        "label": "Fibonacci golden-zone rejection",
        "params": [
            _p("pivot_left", "Swing pivot: bars before", "int", 5, 2, 20, 1),
            _p("pivot_right", "Swing pivot: bars after (confirmation)", "int", 5, 1, 20, 1,
               "A pivot is usable only once this many bars have printed after it."),
            _p("min_impulse_atr", "Smallest impulse (ATR)", "float", 3.0, 0.5, 20.0, 0.5),
            _p("zone_top", "Golden zone starts at", "float", 0.618, 0.382, 0.786, 0.001),
            _p("zone_bottom", "Golden zone ends at", "float", 0.65, 0.5, 0.886, 0.001),
            _p("trigger_mode", "Trigger", "choice", "either",
               choices=["reclaim", "break", "either"],
               help_text="Reclaim: a close back beyond the zone's edge. Break: a close "
                         "beyond the pullback's own high (low). Either: whichever comes first."),
            _p("confirm_window", "Trigger within (bars of the touch)", "int", 5, 1, 20, 1),
            _p("invalidate_at", "Invalidated beyond", "choice", "swing",
               choices=["swing", "0.786"],
               help_text="The swing the impulse started from, or the 0.786 retracement."),
            _p("anchor_low", "Manual swing low (date)", "date", "",
               help_text="Leave blank to use the confirmed pivots. Used for this "
                         "symbol's current read only."),
            _p("anchor_high", "Manual swing high (date)", "date", ""),
        ],
        "rules": _rules(
            "From the latest confirmed swing low to the confirmed swing high after it "
            "(an impulse of at least 3 ATR), retracements are drawn at 0.382, 0.5, "
            "0.618, 0.65 and 0.786. The 0.618 to 0.65 band is this app's "
            "configurable golden zone. Price trading down into it arms the setup; a "
            "touch alone never triggers. The trigger is a completed close back above "
            "the zone's top (a reclaim) or above the pullback's own high (a break), "
            "within 5 bars of the touch. Invalidated by a close below the swing low.",
            "From the latest confirmed swing high to the confirmed swing low after it, "
            "the same retracements upward. A rally into the zone arms it; a close "
            "back below the zone's bottom edge or below the rally's own low triggers "
            "it. Invalidated by a close above the swing high."),
    },
    {
        "id": "triple_stoch", "family": "stochastic", "kind": "continuation",
        "label": "Triple stochastic (experimental)",
        "experimental": True,
        "params": [
            _p("fast_len", "Fast: lookback", "int", 9, 3, 50, 1),
            _p("fast_k", "Fast: %K smoothing", "int", 3, 1, 10, 1),
            _p("fast_d", "Fast: %D smoothing", "int", 3, 1, 10, 1),
            _p("mid_len", "Middle: lookback", "int", 14, 3, 60, 1),
            _p("mid_k", "Middle: %K smoothing", "int", 3, 1, 10, 1),
            _p("mid_d", "Middle: %D smoothing", "int", 3, 1, 10, 1),
            _p("slow_len", "Slow: lookback", "int", 40, 10, 120, 1),
            _p("slow_k", "Slow: %K smoothing", "int", 4, 1, 10, 1),
            _p("slow_d", "Slow: %D smoothing", "int", 4, 1, 10, 1),
            _p("oversold", "Fast oversold at or below", "float", 20.0, 5.0, 40.0, 1.0),
            _p("slow_floor", "Slow above", "float", 50.0, 30.0, 70.0, 1.0),
            _p("window", "Oversold reading within (bars)", "int", 5, 1, 15, 1,
               "Counted back from the crossing bar, which is included."),
        ],
        "rules": _rules(
            "Three stochastics, each written (lookback, %K smoothing, %D smoothing): "
            "fast (9, 3, 3), middle (14, 3, 3), slow (40, 4, 4). Raw %K is 100 x "
            "(close - lowest low) / (highest high - lowest low) over the lookback, "
            "the current bar included; %K is its simple average over the %K "
            "smoothing, %D the average of %K over the %D smoothing. Bullish: slow %K "
            "above 50 and higher than a bar ago, middle %K higher than a bar ago, and "
            "fast %K closing above fast %D with a fast %K reading at or below 20 in "
            "the 5 bars ending at that cross. One way of combining three "
            "stochastics among several in use; there is no standard model.",
            "Bearish: slow %K below 50 and lower than a bar ago, middle %K lower, and "
            "fast %K closing below fast %D with a fast %K reading at or above 80 in "
            "the 5 bars ending at the cross."),
    },
    {
        "id": "donchian_20", "family": "donchian", "kind": "continuation",
        "label": "Donchian 20-bar breakout",
        "params": [
            _p("channel", "Channel (bars)", "int", 20, 5, 120, 1),
            _p("exit_len", "Invalidation channel (bars)", "int", 10, 2, 60, 1),
            _p("near_atr", "Armed within (ATR of the channel)", "float", 0.5, 0.05, 3.0, 0.05),
            _p("vol_mult", "Volume at least (x 20-bar average, 0 = off)", "float", 0.0, 0.0, 5.0, 0.1),
        ],
        "rules": _rules(
            "A completed close above the highest high of the preceding 20 bars, the "
            "current bar excluded. Armed within 0.5 ATR of that high. Invalidated by "
            "a close below the lowest low of the last 10 bars less the buffer.",
            "A completed close below the lowest low of the preceding 20 bars, the "
            "current bar excluded. Invalidated by a close above the highest high of "
            "the last 10 bars plus the buffer."),
    },
    {
        "id": "donchian_55", "family": "donchian", "kind": "continuation",
        "label": "Donchian 55-bar breakout",
        "params_from": "donchian_20",
        "defaults": {"channel": 55, "exit_len": 20},
        "rules": _rules(
            "As the 20-bar version on a 55-bar channel, invalidated beyond the "
            "20-bar extreme.",
            "As the 20-bar version on a 55-bar channel, downward."),
    },
    {
        "id": "donchian_retest", "family": "donchian", "kind": "continuation",
        "label": "Donchian breakout and retest",
        "params": [
            _p("channel", "Channel (bars)", "int", 20, 5, 120, 1),
            _p("retest_window", "Retest within (bars of the breakout)", "int", 10, 2, 30, 1),
            _p("touch_atr", "Retest counts within (ATR of the level)", "float", 0.25, 0.0, 2.0, 0.05),
            _p("tolerance_atr", "Fails beyond (ATR through the level)", "float", 0.5, 0.05, 3.0, 0.05),
        ],
        "rules": _rules(
            "After a 20-bar breakout, price comes back to within 0.25 ATR of the "
            "broken high without closing more than 0.5 ATR below it (armed), then a "
            "completed candle closes above the level and above the prior bar's high "
            "(triggered), within 10 bars of the breakout.",
            "After a 20-bar breakdown, price comes back up to the broken low without "
            "closing more than 0.5 ATR above it, then closes below the level and "
            "below the prior bar's low."),
    },
    {
        "id": "avwap_reclaim", "family": "avwap", "kind": "reversal",
        "label": "Anchored VWAP reclaim",
        "context": {"htf_filter": False},
        "params": [
            _p("anchor_date", "Anchor date", "date", "",
               help_text="An event you choose: earnings, a gap. Blank anchors to the "
                         "latest confirmed swing high (low, for the bearish side)."),
            _p("pivot_left", "Swing pivot: bars before", "int", 5, 2, 20, 1),
            _p("pivot_right", "Swing pivot: bars after (confirmation)", "int", 5, 1, 20, 1),
            _p("below_bars", "Was beyond the VWAP within (bars)", "int", 3, 1, 20, 1),
            _p("near_atr", "Armed within (ATR of the VWAP)", "float", 1.0, 0.1, 5.0, 0.1),
            _p("vol_mult", "Volume at least (x 20-bar average, 0 = off)", "float", 1.0, 0.0, 5.0, 0.1),
        ],
        "rules": _rules(
            "The VWAP anchored at the latest confirmed swing high, or a date you "
            "choose: the average price paid since then, weighted by volume, from "
            "daily typical prices. A close below it, within 1 ATR of it, arms the setup; a "
            "completed close back above it on volume at least the 20-bar average "
            "triggers it.",
            "Anchored at the latest confirmed swing low: a close above it, within 1 ATR, "
            "arms the setup, a close back below it on volume triggers it."),
    },
    {
        "id": "avwap_retest", "family": "avwap", "kind": "continuation",
        "label": "Anchored VWAP retest",
        "params": [
            _p("anchor_date", "Anchor date", "date", "",
               help_text="Blank anchors to the latest confirmed swing low (high, for "
                         "the bearish side)."),
            _p("pivot_left", "Swing pivot: bars before", "int", 5, 2, 20, 1),
            _p("pivot_right", "Swing pivot: bars after (confirmation)", "int", 5, 1, 20, 1),
            _p("touch_atr", "Retest counts within (ATR)", "float", 0.25, 0.0, 2.0, 0.05),
            _p("vol_mult", "Volume at least (x 20-bar average, 0 = off)", "float", 0.0, 0.0, 5.0, 0.1),
        ],
        "rules": _rules(
            "Anchored at the latest confirmed swing low. Price above the VWAP pulls "
            "back to within 0.25 ATR of it (armed), and a completed candle closes "
            "above it, up on the day (triggered).",
            "Anchored at the latest confirmed swing high. Price below it rallies to "
            "it, and a completed candle closes below it, down on the day."),
    },
    {
        "id": "sr_breakout", "family": "levels", "kind": "continuation",
        "label": "Resistance breakout",
        "params": [
            _p("pivot_left", "Swing pivot: bars before", "int", 5, 2, 20, 1),
            _p("pivot_right", "Swing pivot: bars after (confirmation)", "int", 5, 1, 20, 1),
            _p("lookback", "Levels from the last (bars)", "int", 120, 20, 500, 5),
            _p("break_atr", "Close beyond the level by (ATR)", "float", 0.1, 0.0, 2.0, 0.05),
            _p("near_atr", "Armed within (ATR of the level)", "float", 0.5, 0.05, 3.0, 0.05),
            _p("fail_atr", "Failed back through by (ATR)", "float", 0.5, 0.05, 3.0, 0.05),
            _p("vol_mult", "Volume at least (x 20-bar average, 0 = off)", "float", 0.0, 0.0, 5.0, 0.1),
        ],
        "rules": _rules(
            "The nearest confirmed swing high above the prior close that has not "
            "been closed above since it formed. Armed within 0.5 ATR of it; a "
            "completed close 0.1 ATR above it triggers. Invalidated by a close 0.5 "
            "ATR back below the level.",
            "The nearest confirmed swing low below the prior close, not yet closed "
            "below. A completed close 0.1 ATR below it triggers; a close 0.5 ATR "
            "back above invalidates."),
    },
    {
        "id": "sr_retest", "family": "levels", "kind": "continuation",
        "label": "Resistance breakout and retest",
        "params": [
            _p("pivot_left", "Swing pivot: bars before", "int", 5, 2, 20, 1),
            _p("pivot_right", "Swing pivot: bars after (confirmation)", "int", 5, 1, 20, 1),
            _p("lookback", "Levels from the last (bars)", "int", 120, 20, 500, 5),
            _p("break_atr", "Breakout close beyond the level by (ATR)", "float", 0.1, 0.0, 2.0, 0.05),
            _p("retest_window", "Retest within (bars of the breakout)", "int", 10, 2, 30, 1),
            _p("touch_atr", "Retest counts within (ATR of the level)", "float", 0.25, 0.0, 2.0, 0.05),
            _p("fail_atr", "Fails beyond (ATR through the level)", "float", 0.5, 0.05, 3.0, 0.05),
        ],
        "rules": _rules(
            "After a breakout above a confirmed swing high, price returns to within "
            "0.25 ATR of the level and holds (armed), then a completed candle closes "
            "above the level and above the prior bar's high (triggered).",
            "After a break below a confirmed swing low, price returns up to it and "
            "fails, then a completed candle closes below the level and below the "
            "prior bar's low."),
    },
    {
        "id": "squeeze", "family": "volatility", "kind": "continuation",
        "label": "Bollinger / Keltner squeeze release",
        "params": [
            _p("bb_len", "Bollinger length", "int", 20, 5, 60, 1),
            _p("bb_mult", "Bollinger width (standard deviations)", "float", 2.0, 0.5, 4.0, 0.1),
            _p("kc_len", "Keltner length", "int", 20, 5, 60, 1),
            _p("kc_mult", "Keltner width (ATR)", "float", 1.5, 0.5, 4.0, 0.1),
            _p("min_squeeze", "Squeeze lasts at least (bars)", "int", 5, 1, 40, 1),
            _p("confirm_window", "Direction confirmed within (bars of release)", "int", 3, 1, 10, 1),
            _p("direction_rule", "Direction from", "choice", "mid", choices=["mid", "range"],
               help_text="Mid: a close beyond the Keltner midline and the prior close. "
                         "Range: a close beyond the squeeze's own high (low)."),
            _p("vol_mult", "Volume at least (x 20-bar average, 0 = off)", "float", 1.0, 0.0, 5.0, 0.1),
        ],
        "rules": _rules(
            "Bollinger bands: 20-bar SMA of the close plus and minus 2 population "
            "standard deviations. Keltner channel: 20-bar EMA of the close plus and "
            "minus 1.5 x ATR(20), Wilder's smoothing. A squeeze is both Bollinger "
            "bands inside the Keltner channel; five bars of it arm the setup. The "
            "release is the first bar the bands come back out; a close above the "
            "Keltner midline and the prior close, on volume at least the 20-bar "
            "average, within 3 bars of the release triggers it. Invalidated below the "
            "squeeze's low.",
            "The same squeeze. Released downward: a close below the midline and the "
            "prior close on volume, invalidated above the squeeze's high."),
    },
]

PRESET_BY_ID: Dict[str, Dict[str, Any]] = {p["id"]: p for p in PRESETS}


def _preset_param_specs(preset: Dict[str, Any]) -> List[Dict[str, Any]]:
    """A preset's own parameter list, with any borrowed one's defaults moved."""
    if preset.get("params_from"):
        base = PRESET_BY_ID[preset["params_from"]]
        specs = [dict(s) for s in base["params"]]
    else:
        specs = [dict(s) for s in preset.get("params", [])]
    for spec in specs:
        if spec["key"] in (preset.get("defaults") or {}):
            spec["default"] = preset["defaults"][spec["key"]]
    return specs


def _context_specs(preset: Dict[str, Any]) -> List[Dict[str, Any]]:
    specs = [dict(s) for s in CONTEXT_PARAMS + LIFECYCLE_PARAMS]
    for spec in specs:
        if spec["key"] in (preset.get("context") or {}):
            spec["default"] = preset["context"][spec["key"]]
    return specs


def all_param_specs(preset: Dict[str, Any]) -> List[Dict[str, Any]]:
    return _preset_param_specs(preset) + _context_specs(preset)


_SYMBOL_RE = re.compile(r"^[A-Z0-9.\-^=]{1,12}$")


def _coerce(spec: Dict[str, Any], raw: Any) -> Any:
    kind = spec["type"]
    if raw is None:
        return spec["default"]
    if kind == "bool":
        if isinstance(raw, str):
            return raw.strip().lower() in ("1", "true", "yes", "on")
        return bool(raw)
    if kind in ("int", "float"):
        try:
            value = float(raw)
        except (TypeError, ValueError):
            return spec["default"]
        if not math.isfinite(value):
            return spec["default"]
        if "min" in spec:
            value = max(spec["min"], value)
        if "max" in spec:
            value = min(spec["max"], value)
        return int(round(value)) if kind == "int" else float(value)
    if kind == "choice":
        value = str(raw).strip().lower()
        return value if value in spec["choices"] else spec["default"]
    if kind == "symbol":
        value = str(raw).strip().upper()
        return value if _SYMBOL_RE.match(value) else spec["default"]
    if kind == "date":
        text = str(raw).strip()[:10]
        if not text:
            return ""
        try:
            return date.fromisoformat(text).isoformat()
        except ValueError:
            return ""
    return spec["default"]


def resolve_params(preset_id: str, overrides: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Every parameter a preset reads, defaulted, coerced and clamped.

    Unknown keys are dropped rather than carried: a parameter no rule reads is a
    parameter the reader thinks is doing something."""
    preset = PRESET_BY_ID[preset_id]
    given = overrides or {}
    return {spec["key"]: _coerce(spec, given.get(spec["key"]))
            for spec in all_param_specs(preset)}


def catalogue() -> Dict[str, Any]:
    """What the page needs to offer the presets and build their forms."""
    return {
        "presets": [{
            "id": p["id"], "label": p["label"], "family": p["family"], "kind": p["kind"],
            "experimental": bool(p.get("experimental")),
            "rules": p["rules"],
            "params": _preset_param_specs(p),
            "context": _context_specs(p),
        } for p in PRESETS],
        "families": sorted({p["family"] for p in PRESETS}),
        "states": list(STATES),
        "method": METHOD,
    }


METHOD = (
    "Rules are evaluated on completed candles only, using only what was known at "
    "each candle's close. Swing pivots count once their confirmation bars have "
    "printed. The higher-timeframe filter reads completed weekly candles for daily "
    "setups and completed daily candles for 4-hour ones. Invalidation is checked "
    "on completed closes. Every preset is a hypothesis to test, not a strategy "
    "known to work; \"conditions met\" counts the listed conditions and is not a "
    "probability. Prices are split-adjusted and not dividend-adjusted, so an "
    "ex-dividend day can read as a small gap down."
)


# ======================================================================== bars

@dataclass
class Bars:
    """Candles in time order, oldest first, as plain arrays.

    `stamps` are what a reader is shown: an ISO date for a daily candle, an ISO
    datetime in New York time for a 4-hour one. `ends` are when each candle
    completed, which is what decides whether it existed at a given moment."""
    stamps: List[str]
    ends: List[datetime]
    o: np.ndarray
    h: np.ndarray
    l: np.ndarray
    c: np.ndarray
    v: np.ndarray
    timeframe: str = "daily"
    forming: Optional[Dict[str, Any]] = None
    gaps: int = 0

    def __len__(self) -> int:
        return len(self.c)

    def mirrored(self) -> "Bars":
        """The same candles upside down: how every bearish rule is evaluated."""
        return Bars(self.stamps, self.ends, -self.o, -self.l, -self.h, -self.c, self.v,
                    self.timeframe, self.forming, self.gaps)

    def with_forming(self) -> Optional["Bars"]:
        """These bars plus the candle still forming, for a provisional read."""
        f = self.forming
        if not f:
            return None
        return Bars(self.stamps + [f["stamp"]], self.ends + [f["end"]],
                    np.append(self.o, f["o"]), np.append(self.h, f["h"]),
                    np.append(self.l, f["l"]), np.append(self.c, f["c"]),
                    np.append(self.v, f["v"]), self.timeframe, None, self.gaps)

    def tail(self, n: int) -> "Bars":
        if n >= len(self):
            return self
        cut = slice(len(self) - n, None)
        return Bars(self.stamps[cut], self.ends[cut], self.o[cut], self.h[cut], self.l[cut],
                    self.c[cut], self.v[cut], self.timeframe, self.forming, self.gaps)


def _now_et(now: Optional[datetime]) -> datetime:
    return (now or datetime.now(timezone.utc)).astimezone(ET)


def _frame_dates(df: pd.DataFrame) -> List[date]:
    out = []
    for stamp in df.index:
        ts = pd.Timestamp(stamp)
        if ts.tzinfo is not None:
            ts = ts.tz_convert(ET)
        out.append(ts.date())
    return out


def _missing_sessions(days: Sequence[date]) -> int:
    """Trading sessions the calendar expected between consecutive candles that
    the feed does not have. Counted, not filled: an invented candle would be a
    price nobody traded at."""
    missing = 0
    for prev, cur in zip(days, days[1:]):
        probe = session_mod.next_trading_day(prev)
        steps = 0
        while probe < cur and steps < 40:
            missing += 1
            probe = session_mod.next_trading_day(probe)
            steps += 1
    return missing


def daily_bars(df: Optional[pd.DataFrame], now: Optional[datetime] = None) -> Optional[Bars]:
    """Completed daily candles, and the forming one kept to one side.

    A candle dated today is complete once today's regular session has closed:
    4:00pm, or 1:00pm on a half day. Before that it is the forming candle and
    nothing but a provisional read may use it. Works on both of the provider's
    index styles: the tz-aware frames `history` returns and the naive dates the
    batch download returns."""
    if df is None or len(df) == 0:
        return None
    frame = df.dropna(subset=["Close"])
    if frame.empty:
        return None
    days = _frame_dates(frame)
    # One candle per day, the later row winning, in date order.
    keep: Dict[date, int] = {}
    for i, d in enumerate(days):
        keep[d] = i
    order = sorted(keep)
    rows = [keep[d] for d in order]
    pick = frame.iloc[rows]
    o = pick["Open"].to_numpy(dtype=float)
    h = pick["High"].to_numpy(dtype=float)
    l = pick["Low"].to_numpy(dtype=float)
    c = pick["Close"].to_numpy(dtype=float)
    v = (pick["Volume"].to_numpy(dtype=float) if "Volume" in pick
         else np.zeros(len(pick)))
    v = np.where(np.isfinite(v), v, 0.0)
    # A candle with no open (rare, on a thin day) takes its close, so it is
    # neither up nor down rather than read as a large move from zero.
    o = np.where(np.isfinite(o), o, c)
    h = np.where(np.isfinite(h), np.maximum(h, np.maximum(o, c)), np.maximum(o, c))
    l = np.where(np.isfinite(l), np.minimum(l, np.minimum(o, c)), np.minimum(o, c))

    now_et = _now_et(now)
    ends = []
    for d in order:
        close_at = session_mod.regular_close(d)
        ends.append(close_at or datetime(d.year, d.month, d.day, 16, 0, tzinfo=ET))
    forming = None
    if order and ends[-1] > now_et:
        forming = {"stamp": order[-1].isoformat(), "end": ends[-1], "o": o[-1],
                   "h": h[-1], "l": l[-1], "c": c[-1], "v": v[-1]}
        order, ends = order[:-1], ends[:-1]
        o, h, l, c, v = o[:-1], h[:-1], l[:-1], c[:-1], v[:-1]
    if not order:
        return None
    return Bars([d.isoformat() for d in order], ends, o, h, l, c, v, "daily", forming,
                _missing_sessions(order[-SCAN_BARS:]))


def intraday_bars(df: Optional[pd.DataFrame], minutes: int = 240,
                  now: Optional[datetime] = None) -> Optional[Bars]:
    """Completed 4-hour candles, regular session only.

    The feed stamps a candle at its start and it covers `minutes` from there,
    cut short by the session's close: 9:30 to 13:30, then 13:30 to the close.
    It is complete once that end has passed, and it is stamped here with that
    end, which is the moment anything it triggers could be known."""
    if df is None or len(df) == 0:
        return None
    frame = df.dropna(subset=["Close"])
    if frame.empty:
        return None
    now_et = _now_et(now)
    stamps, ends, rows = [], [], []
    for i, stamp in enumerate(frame.index):
        ts = pd.Timestamp(stamp)
        ts = ts.tz_localize(ET) if ts.tzinfo is None else ts.tz_convert(ET)
        start = ts.to_pydatetime()
        close_at = session_mod.regular_close(start.date())
        if close_at is None or start >= close_at:
            continue
        end = min(start + timedelta(minutes=minutes), close_at)
        # Stamped with when it completed, not when it opened: a trigger on the
        # 9:30 candle happened at 1:30pm, and that is the time it is reported at.
        stamps.append(end.strftime("%Y-%m-%dT%H:%M"))
        ends.append(end)
        rows.append(i)
    if not rows:
        return None
    pick = frame.iloc[rows]
    o = pick["Open"].to_numpy(dtype=float)
    h = pick["High"].to_numpy(dtype=float)
    l = pick["Low"].to_numpy(dtype=float)
    c = pick["Close"].to_numpy(dtype=float)
    v = np.where(np.isfinite(pick["Volume"].to_numpy(dtype=float)),
                 pick["Volume"].to_numpy(dtype=float), 0.0)
    o = np.where(np.isfinite(o), o, c)
    forming = None
    if ends[-1] > now_et:
        forming = {"stamp": stamps[-1], "end": ends[-1], "o": o[-1], "h": h[-1],
                   "l": l[-1], "c": c[-1], "v": v[-1]}
        stamps, ends = stamps[:-1], ends[:-1]
        o, h, l, c, v = o[:-1], h[:-1], l[:-1], c[:-1], v[:-1]
    if not stamps:
        return None
    return Bars(stamps, ends, o, h, l, c, v, "4h", forming, 0)


# ====================================================== the higher timeframe

@dataclass
class HigherTimeframe:
    """Completed higher-timeframe closes, and which of them each bar may read.

    `latest[t]` is the index of the newest higher-timeframe candle complete at
    bar t's close, or -1. A week is complete when its last session has closed;
    the week still in progress at the end of the data is left out, because its
    "close" is only today's price."""
    closes: np.ndarray
    stamps: List[str]
    latest: np.ndarray
    unit: str


def weekly_context(bars: Bars) -> HigherTimeframe:
    days = [date.fromisoformat(s[:10]) for s in bars.stamps]
    week_of = [(d - timedelta(days=d.weekday())) for d in days]   # Monday of each week
    ends: List[int] = []
    for i in range(len(days)):
        if i + 1 < len(days):
            if week_of[i + 1] != week_of[i]:
                ends.append(i)
        else:
            # The last candle closes its week only if the next session falls
            # in a later week (a Friday, or a Thursday before a Friday holiday).
            nxt = session_mod.next_trading_day(days[i])
            if (nxt - timedelta(days=nxt.weekday())) != week_of[i]:
                ends.append(i)
    closes = np.array([bars.c[i] for i in ends], dtype=float)
    latest = np.full(len(bars), -1, dtype=int)
    j = -1
    for t in range(len(bars)):
        while j + 1 < len(ends) and ends[j + 1] <= t:
            j += 1
        latest[t] = j
    return HigherTimeframe(closes, [bars.stamps[i] for i in ends], latest, "week")


def daily_context_for(intraday: Bars, daily: Bars) -> HigherTimeframe:
    """Completed daily closes for a 4-hour series: a daily candle is readable by
    a 4-hour candle that ends at or after that day's close."""
    latest = np.full(len(intraday), -1, dtype=int)
    j = -1
    for t, end in enumerate(intraday.ends):
        while j + 1 < len(daily) and daily.ends[j + 1] <= end:
            j += 1
        latest[t] = j
    return HigherTimeframe(daily.c.copy(), list(daily.stamps), latest, "day")


# ================================================================== indicators
#
# Arrays in, arrays out, NaN until each has enough history. Every one is causal.

def _series(x: np.ndarray) -> pd.Series:
    return pd.Series(np.asarray(x, dtype=float))


def sma(x: np.ndarray, n: int) -> np.ndarray:
    return _series(x).rolling(n, min_periods=n).mean().to_numpy()


def ema(x: np.ndarray, n: int) -> np.ndarray:
    """The app's EMA (technicals.ema): seeded from the first value, NaN for the
    first n-1. The same line the charts draw, so "closed above the 21 EMA" is a
    claim about the line on screen."""
    return _series(x).ewm(span=n, adjust=False, min_periods=n).mean().to_numpy()


def shift(x: np.ndarray, k: int = 1) -> np.ndarray:
    out = np.full(len(x), np.nan)
    if k <= 0:
        return np.asarray(x, dtype=float).copy()
    if k < len(x):
        out[k:] = np.asarray(x, dtype=float)[:-k]
    return out


def rolling_max(x: np.ndarray, n: int) -> np.ndarray:
    return _series(x).rolling(n, min_periods=n).max().to_numpy()


def rolling_min(x: np.ndarray, n: int) -> np.ndarray:
    return _series(x).rolling(n, min_periods=n).min().to_numpy()


def any_within(flag: np.ndarray, n: int) -> np.ndarray:
    """True at t when `flag` was true on any of the n bars ending at t."""
    return _series(np.asarray(flag, dtype=float)).rolling(n, min_periods=1).max().to_numpy() > 0


def atr(h: np.ndarray, l: np.ndarray, c: np.ndarray, n: int = 14) -> np.ndarray:
    """Wilder's average true range, as technicals.atr computes it."""
    prev = shift(c, 1)
    tr = np.nanmax(np.vstack([h - l, np.abs(h - prev), np.abs(l - prev)]), axis=0)
    tr[0] = h[0] - l[0]
    return _series(tr).ewm(alpha=1.0 / n, adjust=False, min_periods=n).mean().to_numpy()


def rsi(c: np.ndarray, n: int = 14) -> np.ndarray:
    """Wilder's RSI with the classic seed: the first average is the simple mean
    of the first n changes, then each is (previous x (n - 1) + this) / n.

    NaN until then. technicals.rsi pins its warm-up to 50, which would read as
    "RSI just reclaimed 50" on the first real bar."""
    out = np.full(len(c), np.nan)
    if len(c) <= n:
        return out
    d = np.diff(c)
    gain = np.where(d > 0, d, 0.0)
    loss = np.where(d < 0, -d, 0.0)
    ag, al = float(np.mean(gain[:n])), float(np.mean(loss[:n]))

    def value(g, lo):
        if lo == 0:
            return 100.0 if g > 0 else 50.0
        return 100.0 - 100.0 / (1.0 + g / lo)

    out[n] = value(ag, al)
    for i in range(n + 1, len(c)):
        ag = (ag * (n - 1) + gain[i - 1]) / n
        al = (al * (n - 1) + loss[i - 1]) / n
        out[i] = value(ag, al)
    return out


def macd(c: np.ndarray, fast: int = 12, slow: int = 26, signal: int = 9):
    line = ema(c, fast) - ema(c, slow)
    sig = _series(line).ewm(span=signal, adjust=False, min_periods=signal).mean().to_numpy()
    return line, sig


def stochastic(h: np.ndarray, l: np.ndarray, c: np.ndarray, n: int, k: int, d: int):
    """(lookback, %K smoothing, %D smoothing). Raw %K over the last n bars, the
    current bar included; %K its k-bar simple average; %D the d-bar average of %K."""
    hh, ll = rolling_max(h, n), rolling_min(l, n)
    span = hh - ll
    raw = np.where(span > 0, 100.0 * (c - ll) / np.where(span > 0, span, 1.0), 50.0)
    raw = np.where(np.isfinite(hh) & np.isfinite(ll), raw, np.nan)
    kline = sma(raw, k) if k > 1 else raw
    dline = sma(kline, d) if d > 1 else kline
    return kline, dline


def prior_channel(h: np.ndarray, l: np.ndarray, n: int):
    """Donchian channel of the n bars BEFORE each bar, the bar itself excluded:
    a close is compared with the high it had to beat, not with itself."""
    return shift(rolling_max(h, n), 1), shift(rolling_min(l, n), 1)


def bollinger(c: np.ndarray, n: int = 20, mult: float = 2.0):
    mid = sma(c, n)
    sd = _series(c).rolling(n, min_periods=n).std(ddof=0).to_numpy()
    return mid + mult * sd, mid, mid - mult * sd


def keltner(h, l, c, n: int = 20, mult: float = 1.5, atr_len: int = 20):
    mid = ema(c, n)
    band = atr(h, l, c, atr_len) * mult
    return mid + band, mid, mid - band


def anchored_vwap(h, l, c, v, start: int) -> np.ndarray:
    """Typical price ((high + low + close) / 3) weighted by volume, from the
    anchor candle on. A daily-bar approximation of the session VWAP, which needs
    every trade."""
    out = np.full(len(c), np.nan)
    if start < 0 or start >= len(c):
        return out
    tp = (h + l + c) / 3.0
    pv = np.cumsum(tp[start:] * v[start:])
    vol = np.cumsum(v[start:])
    with np.errstate(invalid="ignore", divide="ignore"):
        out[start:] = np.where(vol > 0, pv / np.where(vol > 0, vol, 1.0), np.nan)
    return out


def confirmed_pivots(h: np.ndarray, l: np.ndarray, left: int, right: int):
    """Swing highs and lows, each usable from `index + right` and not before.

    A high is a bar above the `left` bars before it and at least as high as the
    `right` bars after it; a low the mirror. Strict on the left so the first bar
    of a flat top is the pivot. Returned as sorted lists of indices; a caller at
    bar t may only use those with index + right <= t, which is the whole point.
    """
    highs: List[int] = []
    lows: List[int] = []
    n = len(h)
    for i in range(left, n - right):
        hv, lv = h[i], l[i]
        if np.isfinite(hv) and np.all(hv > h[i - left:i]) and np.all(hv >= h[i + 1:i + right + 1]):
            highs.append(i)
        if np.isfinite(lv) and np.all(lv < l[i - left:i]) and np.all(lv <= l[i + 1:i + right + 1]):
            lows.append(i)
    return highs, lows


def cross_above(a: np.ndarray, b) -> np.ndarray:
    """True at t when a closes above b at t having been at or below it at t - 1.
    Equality at t is not a cross; equality at t - 1 counts as "at or below"."""
    b = np.broadcast_to(np.asarray(b, dtype=float), np.shape(a)) if np.ndim(b) == 0 else b
    pa, pb = shift(a, 1), shift(b, 1)
    return np.isfinite(a) & np.isfinite(b) & np.isfinite(pa) & np.isfinite(pb) & (a > b) & (pa <= pb)


class Indicators:
    """Per-direction indicator cache, so presets sharing an EMA compute it once."""

    def __init__(self, bars: Bars):
        self.b = bars
        self._memo: Dict[Tuple, Any] = {}

    def get(self, key: Tuple, build: Callable[[], Any]) -> Any:
        if key not in self._memo:
            self._memo[key] = build()
        return self._memo[key]

    def ema(self, n):
        return self.get(("ema", n), lambda: ema(self.b.c, n))

    def sma(self, n):
        return self.get(("sma", n), lambda: sma(self.b.c, n))

    def ma(self, kind, n):
        return self.ema(n) if kind == "ema" else self.sma(n)

    def atr(self, n=14):
        b = self.b
        return self.get(("atr", n), lambda: atr(b.h, b.l, b.c, n))

    def rsi(self, n=14):
        return self.get(("rsi", n), lambda: rsi(self.b.c, n))

    def macd(self, f, s, g):
        return self.get(("macd", f, s, g), lambda: macd(self.b.c, f, s, g))

    def stoch(self, n, k, d):
        b = self.b
        return self.get(("stoch", n, k, d), lambda: stochastic(b.h, b.l, b.c, n, k, d))

    def pivots(self, left, right):
        b = self.b
        return self.get(("piv", left, right), lambda: confirmed_pivots(b.h, b.l, left, right))

    def vol_avg(self, n=20):
        """Average volume of the n bars before each bar, the bar excluded."""
        return self.get(("vavg", n), lambda: shift(sma(self.b.v, n), 1))


# ================================================================== detection

@dataclass
class Detection:
    """What one preset sees at every bar, before the lifecycle runs.

    `trigger` must imply a setup that is present now or was within the bars the
    rule allows: the lifecycle arms on `arm | trigger`, so a trigger with no
    setup behind it would arm and fire on the same bar. Prices here are on the
    direction's own scale (negated for bearish) until reported."""
    ready: np.ndarray
    arm: np.ndarray
    trigger: np.ndarray
    trigger_level: np.ndarray
    stop: np.ndarray
    arm_stop: np.ndarray
    lines: Dict[str, np.ndarray] = field(default_factory=dict)
    anchors: Callable[[int], List[Dict[str, Any]]] = lambda t: []
    levels: Callable[[int], List[Dict[str, Any]]] = lambda t: []
    describe: Callable[[int], Dict[str, Any]] = lambda t: {"checks": [], "values": {}}


def _nan(n):
    return np.full(n, np.nan)


def _check(group: str, rule: str, passed: Optional[bool], value: Any = None,
           required: bool = True) -> Dict[str, Any]:
    return {"group": group, "rule": rule, "passed": None if passed is None else bool(passed),
            "value": value, "required": required}


def _fmt(x: Any, digits: int = 2) -> Optional[str]:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(v):
        return None
    return "{:,.{}f}".format(v, digits)


class Words:
    """The direction's vocabulary, so one rule describes both sides in English."""

    def __init__(self, bull: bool, timeframe: str = "daily"):
        self.bull = bull
        self.unit = "day" if timeframe == "daily" else "bar"
        self.above = "above" if bull else "below"
        self.below = "below" if bull else "above"
        self.rising = "rising" if bull else "falling"
        self.up = "up" if bull else "down"
        self.pullback = "pullback" if bull else "rally"
        self.low = "low" if bull else "high"
        self.high = "high" if bull else "low"
        self.oversold = "oversold" if bull else "overbought"
        self.resistance = "resistance" if bull else "support"
        self.reclaimed = "closed back above" if bull else "closed back below"
        self.sign = 1.0 if bull else -1.0

    def px(self, x: Any) -> Optional[float]:
        """A price on the real scale."""
        try:
            v = float(x) * self.sign
        except (TypeError, ValueError):
            return None
        return v if math.isfinite(v) else None


def _osc(x: float, bull: bool) -> Optional[float]:
    """An oscillator value back on its real scale: 100 - v on the mirrored side."""
    if x is None or not math.isfinite(float(x)):
        return None
    return float(x) if bull else 100.0 - float(x)


def _ready_from(n: int, start: int, *arrays: np.ndarray) -> np.ndarray:
    out = np.zeros(n, dtype=bool)
    if start < n:
        out[max(0, start):] = True
    for arr in arrays:
        out &= np.isfinite(arr)
    return out


def _bool(x) -> Optional[bool]:
    try:
        return bool(x)
    except (TypeError, ValueError):
        return None


def _vol_check(ind: Indicators, p: Dict[str, Any], t: int, group: str = "Confirmation"):
    """The volume condition, when the preset uses one."""
    mult = float(p.get("vol_mult") or 0.0)
    if mult <= 0:
        return None
    avg = ind.vol_avg(20)[t]
    ok = bool(np.isfinite(avg) and ind.b.v[t] >= mult * avg)
    ratio = ind.b.v[t] / avg if np.isfinite(avg) and avg > 0 else None
    return _check(group, "Volume at least {:g} x its 20-bar average".format(mult), ok,
                  "{:.2f}x".format(ratio) if ratio is not None else None)


def _vol_ok(ind: Indicators, p: Dict[str, Any]) -> np.ndarray:
    mult = float(p.get("vol_mult") or 0.0)
    if mult <= 0:
        return np.ones(len(ind.b), dtype=bool)
    avg = ind.vol_avg(20)
    return np.isfinite(avg) & (ind.b.v >= mult * avg)


# --------------------------------------------------------------- trend pullback

def detect_trend_pullback(ind: Indicators, p: Dict[str, Any], w: Words) -> Detection:
    b, n = ind.b, len(ind.b)
    el, sl, slope = p["ema_len"], p["sma_len"], p["slope_bars"]
    E, S, A, S200 = ind.ema(el), ind.sma(sl), ind.atr(14), ind.sma(200)
    trend = (b.c > S) & (S > shift(S, slope))
    if p["need_sma200"]:
        trend &= S > S200
    touch = b.l <= E + p["touch_atr"] * A
    beyond_before = any_within(np.nan_to_num(shift((b.c > E).astype(float), 1)) > 0, p["prior_bars"])
    setup = trend & touch & beyond_before
    span = p["arm_expiry"] + 1
    recent = any_within(setup, span)
    crossed = (b.c > E) & ((shift(b.c, 1) <= shift(E, 1)) | (b.l <= E))
    candle_ok = (b.c > b.o) if p["candle"] else np.ones(n, dtype=bool)
    trigger = crossed & candle_ok & trend & recent
    stop = rolling_min(b.l, span) - p["stop_buffer_atr"] * A
    warm = max(3 * el, sl + slope, 200 if p["need_sma200"] else 0, 42)

    def describe(t: int) -> Dict[str, Any]:
        checks = [
            _check("Trend", "Close {} the {}-{} SMA".format(w.above, sl, w.unit), b.c[t] > S[t],
                   _fmt(w.px(S[t]))),
            _check("Trend", "The {}-{} SMA {} over {} bars".format(sl, w.unit, w.rising, slope),
                   S[t] > S[t - slope] if t >= slope else None),
        ]
        if p["need_sma200"]:
            checks.append(_check("Trend", "The {}-{u} SMA {} the 200-{u} SMA".format(sl, w.above, u=w.unit),
                                 S[t] > S200[t], _fmt(w.px(S200[t]))))
        checks.append(_check("Setup", "A {} to within {:g} ATR of the {} EMA in the last {} bars".format(
            w.pullback, p["touch_atr"], el, span), recent[t], _fmt(w.px(E[t]))))
        checks.append(_check("Trigger", "Completed candle {} the {} EMA".format(w.reclaimed, el),
                             crossed[t], _fmt(w.px(b.c[t]))))
        if p["candle"]:
            checks.append(_check("Trigger", "Candle closed {} on the bar".format(w.up), b.c[t] > b.o[t]))
        return {
            "checks": checks,
            "values": {"EMA {}".format(el): _fmt(w.px(E[t])), "SMA {}".format(sl): _fmt(w.px(S[t])),
                       "ATR 14": _fmt(A[t])},
            "trigger_text": "price {} the {} EMA after a {} to it, {} a {} {}-{} SMA".format(
                w.reclaimed, el, w.pullback, w.above, w.rising, sl, w.unit),
            "setup_text": "a {} to the {} EMA".format(w.pullback, el),
            "waiting_text": "a completed close back {} the {} EMA, now {}".format(
                w.above, el, _fmt(w.px(E[t]))),
            "watching_text": "no {} to the {} EMA yet".format(w.pullback, el),
            "arm_stop_text": "a close {} the {}-{} SMA".format(w.below, sl, w.unit),
        }

    return Detection(_ready_from(n, warm, E, S, A), setup, trigger, E, stop, S,
                     {"EMA 9": ind.ema(9), "EMA {}".format(el): E, "SMA {}".format(sl): S,
                      "SMA 200": S200}, describe=describe)


# ------------------------------------------------------------------- crossover

def detect_ma_cross(ind: Indicators, p: Dict[str, Any], w: Words) -> Detection:
    b, n = ind.b, len(ind.b)
    ft, fl, st, sl = p["fast_type"], p["fast_len"], p["slow_type"], p["slow_len"]
    F, Sl, A = ind.ma(ft, fl), ind.ma(st, sl), ind.atr(14)
    gap = F - Sl
    cross = cross_above(F, Sl)
    near = (gap < 0) & (-gap <= p["near_atr"] * A) & (gap > shift(gap, 1))
    stop = rolling_min(b.l, p["swing_bars"]) - p["stop_buffer_atr"] * A
    warm = max(3 * sl if st == "ema" else sl + 1, 3 * fl if ft == "ema" else fl + 1, 42)
    fname, sname = "{} {}".format(ft.upper(), fl), "{} {}".format(st.upper(), sl)

    def describe(t: int) -> Dict[str, Any]:
        return {
            "checks": [
                _check("Setup", "{} {} and within {:g} ATR of {}, closing the gap".format(
                    fname, w.below, p["near_atr"], sname),
                    bool(near[t] or cross[t] or (t > 0 and near[t - 1]))),
                _check("Trigger", "{} closed {} {} on a completed bar".format(fname, w.above, sname),
                       cross[t], _fmt(w.px(F[t]))),
            ],
            "values": {fname: _fmt(w.px(F[t])), sname: _fmt(w.px(Sl[t])), "ATR 14": _fmt(A[t])},
            "trigger_text": "the {} crossed {} the {}".format(fname, w.above, sname),
            "setup_text": "the {} closing in on the {} from {}".format(fname, sname, w.below),
            "waiting_text": "the {} to close {} the {}, now {}".format(
                fname, w.above, sname, _fmt(w.px(Sl[t]))),
            "watching_text": "the averages are not converging",
            "arm_stop_text": "",
        }

    return Detection(_ready_from(n, warm, F, Sl, A), near, cross, Sl, stop, _nan(n),
                     {fname: F, sname: Sl}, describe=describe)


# -------------------------------------------------------------------- momentum

def detect_rsi50(ind: Indicators, p: Dict[str, Any], w: Words) -> Detection:
    b, n = ind.b, len(ind.b)
    R, A, lvl = ind.rsi(p["rsi_len"]), ind.atr(14), p["level"]
    arm = R <= lvl
    trigger = cross_above(R, lvl)
    stop = rolling_min(b.l, p["swing_bars"]) - p["stop_buffer_atr"] * A
    real = lvl if w.bull else 100.0 - lvl

    def describe(t: int) -> Dict[str, Any]:
        return {
            "checks": [
                _check("Setup", "RSI({}) at or {} {:g} on the bar before".format(
                    p["rsi_len"], "below" if w.bull else "above", real),
                    R[t - 1] <= lvl if t > 0 else None, _fmt(_osc(R[t - 1], w.bull), 1) if t > 0 else None),
                _check("Trigger", "RSI({}) closed {} {:g}".format(p["rsi_len"], w.above, real),
                       trigger[t], _fmt(_osc(R[t], w.bull), 1)),
            ],
            "values": {"RSI {}".format(p["rsi_len"]): _fmt(_osc(R[t], w.bull), 1)},
            "trigger_text": "RSI({}) crossed {} {:g}".format(p["rsi_len"], w.above, real),
            "setup_text": "RSI dipping to {:g}".format(real) if w.bull else "RSI rising to {:g}".format(real),
            "waiting_text": "RSI to close {} {:g}, now {}".format(w.above, real, _fmt(_osc(R[t], w.bull), 1)),
            "watching_text": "RSI is {} {:g} with no dip to it".format(w.above, real),
            "arm_stop_text": "",
        }

    return Detection(_ready_from(n, 3 * p["rsi_len"] + 1, R, A), arm, trigger,
                     b.c.copy(), stop, _nan(n), {}, describe=describe)


def detect_rsi_oversold(ind: Indicators, p: Dict[str, Any], w: Words) -> Detection:
    b, n = ind.b, len(ind.b)
    R, A, os_ = ind.rsi(p["rsi_len"]), ind.atr(14), p["oversold"]
    arm = R <= os_
    trigger = cross_above(R, os_)
    stop = rolling_min(b.l, p["swing_bars"]) - p["stop_buffer_atr"] * A
    real = os_ if w.bull else 100.0 - os_

    def describe(t: int) -> Dict[str, Any]:
        return {
            "checks": [
                _check("Setup", "An {} RSI reading (at or {} {:g}) on the bar before".format(
                    w.oversold, "below" if w.bull else "above", real),
                    R[t - 1] <= os_ if t > 0 else None,
                    _fmt(_osc(R[t - 1], w.bull), 1) if t > 0 else None),
                _check("Trigger", "RSI closed back {} {:g}".format(w.above, real), trigger[t],
                       _fmt(_osc(R[t], w.bull), 1)),
            ],
            "values": {"RSI {}".format(p["rsi_len"]): _fmt(_osc(R[t], w.bull), 1)},
            "trigger_text": "RSI recovered from {}, closing back {} {:g}".format(w.oversold, w.above, real),
            "setup_text": "an {} RSI reading".format(w.oversold),
            "waiting_text": "RSI to close back {} {:g}, now {}. The {} reading alone is not a signal".format(
                w.above, real, _fmt(_osc(R[t], w.bull), 1), w.oversold),
            "watching_text": "RSI is not {}".format(w.oversold),
            "arm_stop_text": "",
        }

    return Detection(_ready_from(n, 3 * p["rsi_len"] + 1, R, A), arm, trigger,
                     b.c.copy(), stop, _nan(n), {}, describe=describe)


def detect_macd_cross(ind: Indicators, p: Dict[str, Any], w: Words) -> Detection:
    b, n = ind.b, len(ind.b)
    M, G = ind.macd(p["macd_fast"], p["macd_slow"], p["macd_signal"])
    A = ind.atr(14)
    zone = (M < 0) if p["beyond_zero"] else np.ones(n, dtype=bool)
    arm = (M < G) & zone
    trigger = cross_above(M, G) & zone
    stop = rolling_min(b.l, p["swing_bars"]) - p["stop_buffer_atr"] * A
    label = "MACD({}, {}, {})".format(p["macd_fast"], p["macd_slow"], p["macd_signal"])
    warm = 3 * p["macd_slow"] + p["macd_signal"]

    def describe(t: int) -> Dict[str, Any]:
        checks = [
            _check("Setup", "{} {} its signal line on the bar before".format(label, w.below),
                   M[t - 1] <= G[t - 1] if t > 0 else None),
            _check("Trigger", "{} closed {} its signal line".format(label, w.above), trigger[t],
                   _fmt(w.px(M[t] - G[t]), 3)),
        ]
        if p["beyond_zero"]:
            checks.append(_check("Setup", "The cross happened {} zero".format(w.below), M[t] < 0,
                                 _fmt(w.px(M[t]), 3)))
        return {
            "checks": checks,
            "values": {"MACD": _fmt(w.px(M[t]), 3), "Signal": _fmt(w.px(G[t]), 3)},
            "trigger_text": "{} crossed {} its signal line".format(label, w.above),
            "setup_text": "MACD {} its signal line".format(w.below),
            "waiting_text": "MACD to close {} its signal line".format(w.above),
            "watching_text": "MACD is already {} its signal line".format(w.above),
            "arm_stop_text": "",
        }

    return Detection(_ready_from(n, warm, M, G, A), arm, trigger, b.c.copy(), stop, _nan(n),
                     {}, describe=describe)


def detect_momentum_confirm(ind: Indicators, p: Dict[str, Any], w: Words) -> Detection:
    b, n = ind.b, len(ind.b)
    R, A = ind.rsi(p["rsi_len"]), ind.atr(14)
    M, G = ind.macd(12, 26, 9)
    os_ = p["oversold"]
    picked: List[Tuple[str, np.ndarray, np.ndarray, str]] = []
    if p["use_rsi50"]:
        picked.append(("RSI closed {} 50".format(w.above), cross_above(R, 50.0), R <= 50.0,
                       "RSI to close {} 50".format(w.above)))
    if p["use_oversold"]:
        real = os_ if w.bull else 100.0 - os_
        picked.append(("RSI closed back {} {:g} after an {} reading".format(w.above, real, w.oversold),
                       cross_above(R, os_), R <= os_,
                       "RSI to close back {} {:g} after an {} reading".format(w.above, real, w.oversold)))
    if p["use_macd"]:
        picked.append(("MACD closed {} its signal line".format(w.above), cross_above(M, G), M < G,
                       "MACD to close {} its signal line".format(w.above)))
    win = p["window"]
    if not picked:
        trigger = np.zeros(n, dtype=bool)
        arm = np.zeros(n, dtype=bool)
    else:
        recent = [any_within(ev, win) for _, ev, _, _ in picked]
        now_ = np.zeros(n, dtype=bool)
        for _, ev, _, _ in picked:
            now_ |= ev
        if p["combine"] == "all":
            together = np.ones(n, dtype=bool)
            for r in recent:
                together &= r
            trigger = together & now_
        else:
            trigger = now_.copy()
        arm = np.zeros(n, dtype=bool)
        for (_, _, pre, _), r in zip(picked, recent):
            arm |= pre | r
    stop = rolling_min(b.l, p["swing_bars"]) - p["stop_buffer_atr"] * A

    def describe(t: int) -> Dict[str, Any]:
        checks = []
        for label, ev, _, _ in picked:
            hit = bool(any_within(ev, win)[t])
            checks.append(_check("Momentum", label + " within {} bars".format(win)
                                 if p["combine"] == "all" else label, hit))
        if not picked:
            checks.append(_check("Momentum", "No momentum condition is selected", False))
        glue = " and " if p["combine"] == "all" else " or "
        joined = glue.join(lbl for lbl, _, _, _ in picked)
        wanted = glue.join(fut for _, _, _, fut in picked)
        return {
            "checks": checks,
            "values": {"RSI {}".format(p["rsi_len"]): _fmt(_osc(R[t], w.bull), 1),
                       "MACD": _fmt(w.px(M[t]), 3), "Signal": _fmt(w.px(G[t]), 3)},
            "trigger_text": joined or "no condition selected",
            "setup_text": "momentum turning {}".format(w.up),
            "waiting_text": ("{} within {} bars of each other".format(wanted, win) if p["combine"] == "all"
                             else wanted) or "a momentum condition to be selected",
            "watching_text": "momentum has not turned {}".format(w.up),
            "arm_stop_text": "",
            "note": "RSI and MACD are both momentum readings, so together they count as one condition.",
        }

    return Detection(_ready_from(n, 87, R, M, G, A), arm, trigger, b.c.copy(), stop, _nan(n),
                     {}, describe=describe)


# ------------------------------------------------------------------- fibonacci

FIB_RATIOS = (0.382, 0.5, 0.618, 0.65, 0.786)


def _manual_index(stamps: List[str], when: str) -> Optional[int]:
    if not when:
        return None
    try:
        i = stamps.index(when)
    except ValueError:
        return None
    return i


def detect_fib(ind: Indicators, p: Dict[str, Any], w: Words) -> Detection:
    b, n = ind.b, len(ind.b)
    A = ind.atr(14)
    left, right = p["pivot_left"], p["pivot_right"]
    highs, lows = ind.pivots(left, right)
    conf_h = [i + right for i in highs]
    zt, zb = sorted((float(p["zone_top"]), float(p["zone_bottom"])))
    ratios = sorted(set(FIB_RATIOS) | {zt, zb})
    # Manual anchors are given in real terms: swing low then high for the
    # bullish side. On the mirrored chart the bearish impulse runs from the
    # real high (a low there) to the real low.
    lo_date, hi_date = (p["anchor_low"], p["anchor_high"]) if w.bull else (p["anchor_high"], p["anchor_low"])
    m_lo, m_hi = _manual_index(b.stamps, lo_date), _manual_index(b.stamps, hi_date)
    manual = (m_lo, m_hi) if (m_lo is not None and m_hi is not None and m_lo < m_hi) else None

    arm = np.zeros(n, dtype=bool)
    reclaim = np.zeros(n, dtype=bool)
    broke = np.zeros(n, dtype=bool)
    top = _nan(n)
    inval = _nan(n)
    impulse: List[Optional[Tuple[int, int]]] = [None] * n
    last_touch, seen_high, last_imp = -1, -np.inf, None
    for t in range(n):
        if manual and t >= manual[1]:
            lo, hi = manual
        else:
            k = bisect.bisect_right(conf_h, t) - 1
            if k < 0:
                continue
            hi = highs[k]
            j = bisect.bisect_left(lows, hi) - 1
            if j < 0:
                continue
            lo = lows[j]
        H, L = b.h[hi], b.l[lo]
        rng = H - L
        if not (np.isfinite(A[hi]) and rng >= p["min_impulse_atr"] * A[hi]):
            continue
        floor = L if p["invalidate_at"] == "swing" else H - 0.786 * rng
        since = b.c[hi + 1:t + 1]
        if since.size and (np.any(since > H) or np.any(since < floor)):
            # The high was exceeded, or the structure broke. On the bar it
            # breaks, the level stays, so an armed setup is invalidated there
            # rather than left to expire.
            if since[-1] < floor and not np.any(since[:-1] < floor) and not np.any(since > H):
                inval[t] = floor
            continue
        impulse[t] = (lo, hi)
        if last_imp != (lo, hi):
            last_touch, seen_high, last_imp = -1, -np.inf, (lo, hi)
        top[t] = H - zt * rng
        inval[t] = floor
        if b.l[t] <= top[t]:
            arm[t] = True
        # A break is a close beyond the pullback's own extreme since the touch,
        # the touch bar's included and this bar's excluded.
        if last_touch >= 0 and t > last_touch and b.c[t] > seen_high:
            broke[t] = True
        if arm[t]:
            if last_touch < 0:
                seen_high = b.h[t]
            last_touch = t
        if last_touch >= 0:
            seen_high = max(seen_high, b.h[t])
        reclaim[t] = b.c[t] > top[t] and b.c[t] > b.o[t] and (
            b.l[t] <= top[t] or (t > 0 and arm[t - 1]))
    recent = any_within(arm, p["confirm_window"])
    mode = p["trigger_mode"]
    fired = reclaim if mode == "reclaim" else broke if mode == "break" else (reclaim | broke)
    alive = np.isfinite(top)
    trigger = fired & recent & alive & (b.c > inval)
    stop = inval - p["stop_buffer_atr"] * A

    def grid(t: int) -> List[Dict[str, Any]]:
        if impulse[t] is None:
            return []
        lo, hi = impulse[t]
        H, L = b.h[hi], b.l[lo]
        out = []
        for r in ratios:
            out.append({"ratio": r, "price": w.px(H - r * (H - L)),
                        "label": "{:g}".format(r), "zone": zt <= r <= zb})
        return out

    def anchors(t: int) -> List[Dict[str, Any]]:
        if impulse[t] is None:
            return []
        lo, hi = impulse[t]
        man = manual is not None and (lo, hi) == manual
        return [
            {"role": "start", "index": lo, "stamp": b.stamps[lo], "price": w.px(b.l[lo]),
             "label": "swing " + w.low, "confirmed_at": None if man else b.stamps[min(n - 1, lo + right)],
             "manual": man},
            {"role": "end", "index": hi, "stamp": b.stamps[hi], "price": w.px(b.h[hi]),
             "label": "swing " + w.high, "confirmed_at": None if man else b.stamps[min(n - 1, hi + right)],
             "manual": man},
        ]

    def describe(t: int) -> Dict[str, Any]:
        has = impulse[t] is not None
        zone_px: Tuple[Optional[float], Optional[float]] = (None, None)
        if has:
            lo, hi = impulse[t]
            H, L = b.h[hi], b.l[lo]
            zone_px = (w.px(H - zt * (H - L)), w.px(H - zb * (H - L)))
        checks = [
            _check("Setup", "A confirmed impulse of at least {:g} ATR".format(p["min_impulse_atr"]), has),
            _check("Setup", "Price traded into the golden zone ({:g} to {:g}) in the last {} bars".format(
                zt, zb, p["confirm_window"]), bool(recent[t]) if has else False,
                "{} to {}".format(_fmt(zone_px[0]), _fmt(zone_px[1])) if has else None),
            _check("Trigger", "Completed close {} the zone's edge, or {} the {}'s own {}".format(
                w.above, w.above, w.pullback, w.high), bool(fired[t]), _fmt(w.px(b.c[t]))),
        ]
        return {
            "checks": checks,
            "values": {"Zone edge": _fmt(w.px(top[t])), "Invalidation": _fmt(w.px(inval[t]))},
            "trigger_text": ("price {} the golden zone after trading into it".format(w.reclaimed)
                             if reclaim[t] else "price broke the {}'s own {} after touching the golden zone".format(
                                 w.pullback, w.high)),
            "setup_text": "a {} into the golden zone".format(w.pullback),
            "waiting_text": ("a close back {} the zone's edge at {}, or {} the {}'s {}".format(
                w.above, _fmt(w.px(top[t])), w.above, w.pullback, w.high) if has else
                "a confirmed impulse to measure from"),
            "watching_text": ("no {} into the golden zone yet".format(w.pullback) if has
                              else "no confirmed impulse to measure from"),
            "arm_stop_text": "a close beyond the swing {}".format(w.low)
            if p["invalidate_at"] == "swing" else "a close beyond the 0.786 retracement",
            "zone": {"top": zone_px[0], "bottom": zone_px[1],
                     "label": "Golden zone, {:g} to {:g}: this app's convention, configurable".format(zt, zb)}
            if has else None,
        }

    return Detection(_ready_from(n, 42, A), arm, trigger, top, stop, inval, {},
                     anchors=anchors, levels=grid, describe=describe)


# -------------------------------------------------------------- triple stochastic

def detect_triple_stoch(ind: Indicators, p: Dict[str, Any], w: Words) -> Detection:
    b, n = ind.b, len(ind.b)
    A = ind.atr(14)
    fk, fd = ind.stoch(p["fast_len"], p["fast_k"], p["fast_d"])
    mk, _md = ind.stoch(p["mid_len"], p["mid_k"], p["mid_d"])
    sk, _sd = ind.stoch(p["slow_len"], p["slow_k"], p["slow_d"])
    floor, os_, win = p["slow_floor"], p["oversold"], p["window"]
    slow_ok = (sk > floor) & (sk > shift(sk, 1))
    mid_ok = mk > shift(mk, 1)
    os_recent = any_within(fk <= os_, win)
    cross = cross_above(fk, fd)
    arm = slow_ok & (fk <= os_)
    trigger = cross & slow_ok & mid_ok & os_recent
    stop = rolling_min(b.l, win) - p["stop_buffer_atr"] * A
    warm = p["slow_len"] + p["slow_k"] + p["slow_d"] + 2
    real_floor = floor if w.bull else 100.0 - floor
    real_os = os_ if w.bull else 100.0 - os_

    def tag(prefix, k):
        return "{} ({}, {}, {})".format(prefix, p[k + "_len"], p[k + "_k"], p[k + "_d"])

    def describe(t: int) -> Dict[str, Any]:
        return {
            "checks": [
                _check("Momentum", "{} %K {} {:g} and {} on the bar".format(
                    tag("Slow", "slow"), w.above, real_floor, "higher" if w.bull else "lower"),
                    slow_ok[t], _fmt(_osc(sk[t], w.bull), 1)),
                _check("Momentum", "{} %K {} on the bar".format(tag("Middle", "mid"),
                                                              "higher" if w.bull else "lower"),
                       mid_ok[t], _fmt(_osc(mk[t], w.bull), 1)),
                _check("Setup", "{} %K at or {} {:g} within the {} bars ending here".format(
                    tag("Fast", "fast"), "below" if w.bull else "above", real_os, win), os_recent[t]),
                _check("Trigger", "Fast %K closed {} fast %D".format(w.above), cross[t],
                       _fmt(_osc(fk[t], w.bull), 1)),
            ],
            "values": {"Fast %K": _fmt(_osc(fk[t], w.bull), 1), "Fast %D": _fmt(_osc(fd[t], w.bull), 1),
                       "Middle %K": _fmt(_osc(mk[t], w.bull), 1), "Slow %K": _fmt(_osc(sk[t], w.bull), 1)},
            "trigger_text": "fast %K crossed {} %D after an {} reading, with the slow stochastic {} {:g} "
                            "and the middle one turning {}".format(w.above, w.oversold, w.above,
                                                                   real_floor, w.up),
            "setup_text": "the fast stochastic {}".format(w.oversold),
            "waiting_text": "fast %K to cross {} %D while the slow one holds {} {:g}".format(
                w.above, w.above, real_floor),
            "watching_text": "the fast stochastic is not {}, or the slow one is not {} {:g}".format(
                w.oversold, w.above, real_floor),
            "arm_stop_text": "",
            "note": "Three stochastics are one momentum reading on three speeds, so they count as one condition.",
        }

    return Detection(_ready_from(n, warm, fk, fd, mk, sk, A), arm, trigger, b.c.copy(), stop,
                     _nan(n), {}, describe=describe)


# --------------------------------------------------------------------- donchian

def detect_donchian(ind: Indicators, p: Dict[str, Any], w: Words) -> Detection:
    b, n = ind.b, len(ind.b)
    A = ind.atr(14)
    N = p["channel"]
    top, bottom = prior_channel(b.h, b.l, N)
    breakout = b.c > top
    vol = _vol_ok(ind, p)
    arm = b.c >= top - p["near_atr"] * A
    trigger = breakout & vol
    stop = rolling_min(b.l, p["exit_len"]) - p["stop_buffer_atr"] * A

    def describe(t: int) -> Dict[str, Any]:
        checks = [
            _check("Setup", "Within {:g} ATR of the {}-bar {}".format(p["near_atr"], N, w.high),
                   bool(arm[t]), _fmt(w.px(top[t]))),
            _check("Trigger", "Completed close {} the {} of the preceding {} bars (this bar excluded)".format(
                w.above, "highest high" if w.bull else "lowest low", N), breakout[t], _fmt(w.px(b.c[t]))),
        ]
        vc = _vol_check(ind, p, t)
        if vc:
            checks.append(vc)
        return {
            "checks": checks,
            "values": {"{}-bar {}".format(N, w.high): _fmt(w.px(top[t])), "ATR 14": _fmt(A[t])},
            "trigger_text": "price closed {} the {}-bar {} at {}".format(w.above, N, w.high, _fmt(w.px(top[t]))),
            "setup_text": "price pressing the {}-bar {}".format(N, w.high),
            "waiting_text": "a completed close {} {}".format(w.above, _fmt(w.px(top[t]))),
            "watching_text": "price is more than {:g} ATR from the {}-bar {}".format(p["near_atr"], N, w.high),
            "arm_stop_text": "",
        }

    return Detection(_ready_from(n, N + 15, top, A), arm, trigger, top, stop, _nan(n),
                     {"{}-bar channel".format(N): top, "{}-bar channel, other side".format(N): bottom},
                     describe=describe)


def _retest(ind: Indicators, p: Dict[str, Any], level_at_break: np.ndarray,
            broke_at: np.ndarray):
    """The shared retest machine for a broken level, Donchian or swing.

    After a break at bar k at level L, for `retest_window` bars: a low back
    within `touch_atr` of L while closing no further than `tolerance` through it
    is a retest (armed); a close beyond L and beyond the prior bar's extreme
    after one triggers; a close more than `tolerance` through L ends it."""
    b, n = ind.b, len(ind.b)
    A = ind.atr(14)
    tol = p.get("tolerance_atr", p.get("fail_atr", 0.5))
    arm = np.zeros(n, dtype=bool)
    trigger = np.zeros(n, dtype=bool)
    level = _nan(n)
    fail = _nan(n)
    low_since = _nan(n)
    k, L, touched, low = -1, np.nan, False, np.inf
    for t in range(n):
        if broke_at[t]:
            k, L, touched, low = t, level_at_break[t], False, np.inf
            continue
        if k < 0 or t - k > p["retest_window"] or not np.isfinite(L) or not np.isfinite(A[t]):
            continue
        if b.c[t] < L - tol * A[t]:
            k = -1           # failed: closed through the level
            continue
        level[t] = L
        fail[t] = L - tol * A[t]
        if b.l[t] <= L + p["touch_atr"] * A[t]:
            arm[t] = True
            touched = True
        if touched:
            low = min(low, b.l[t])
            low_since[t] = low
            if b.c[t] > L and t > 0 and b.c[t] > b.h[t - 1]:
                trigger[t] = True
    return arm, trigger, level, fail, low_since


def detect_donchian_retest(ind: Indicators, p: Dict[str, Any], w: Words) -> Detection:
    b, n = ind.b, len(ind.b)
    A = ind.atr(14)
    N = p["channel"]
    top, _bottom = prior_channel(b.h, b.l, N)
    broke = b.c > top
    arm, trigger, level, fail, low_since = _retest(ind, p, top, broke)
    stop = low_since - p["stop_buffer_atr"] * A

    def describe(t: int) -> Dict[str, Any]:
        return {
            "checks": [
                _check("Setup", "A {}-bar breakout in the last {} bars".format(N, p["retest_window"]),
                       bool(np.isfinite(level[t]))),
                _check("Setup", "Retest: a {} back to within {:g} ATR of the broken level".format(
                    w.low, p["touch_atr"]), bool(any_within(arm, p["retest_window"])[t]),
                    _fmt(w.px(level[t]))),
                _check("Trigger", "Completed close {} the level and the prior bar's {}".format(
                    w.above, w.high), trigger[t], _fmt(w.px(b.c[t]))),
            ],
            "values": {"Broken level": _fmt(w.px(level[t])), "Fails beyond": _fmt(w.px(fail[t]))},
            "trigger_text": "price held the retest of the broken {}-bar {} at {} and closed {} the prior bar's {}".format(
                N, w.high, _fmt(w.px(level[t])), w.above, w.high),
            "setup_text": "a retest of the broken {}-bar {}".format(N, w.high),
            "waiting_text": "a close {} the prior bar's {} with the level holding at {}".format(
                w.above, w.high, _fmt(w.px(level[t]))),
            "watching_text": "no recent {}-bar breakout to retest".format(N),
            "arm_stop_text": "a close more than {:g} ATR back through the level".format(
                p["tolerance_atr"]),
        }

    return Detection(_ready_from(n, N + 15, A), arm, trigger, level, stop, fail,
                     {"{}-bar channel".format(N): top}, describe=describe)


# ----------------------------------------------------------------- anchored VWAP

def detect_avwap(ind: Indicators, p: Dict[str, Any], w: Words, mode: str) -> Detection:
    b, n = ind.b, len(ind.b)
    A = ind.atr(14)
    left, right = p["pivot_left"], p["pivot_right"]
    highs, lows = ind.pivots(left, right)
    # Reclaim anchors at a swing on the far side (a high, for the bullish side):
    # the average buyer since then is under water until price gets back over it.
    # Retest anchors at a swing on the near side: support being tested.
    pool = highs if mode == "reclaim" else lows
    conf = [i + right for i in pool]
    fixed = _manual_index(b.stamps, p["anchor_date"])
    curves: Dict[int, np.ndarray] = {}

    def curve(a: int) -> np.ndarray:
        if a not in curves:
            curves[a] = anchored_vwap(b.h, b.l, b.c, b.v, a)
        return curves[a]

    anchor_at = np.full(n, -1, dtype=int)
    AV = _nan(n)
    for t in range(n):
        if fixed is not None:
            a = fixed if t >= fixed else -1
        else:
            k = bisect.bisect_right(conf, t) - 1
            a = pool[k] if k >= 0 else -1
        if a < 0:
            continue
        anchor_at[t] = a
        AV[t] = curve(a)[t]
    vol = _vol_ok(ind, p)
    if mode == "reclaim":
        below = b.c < AV
        recent_below = np.zeros(n, dtype=bool)
        for t in range(1, n):
            a = anchor_at[t]
            if a < 0:
                continue
            s = max(a, t - p["below_bars"])
            av = curve(a)
            recent_below[t] = bool(np.any(b.c[s:t] < av[s:t]))
        arm = below & (AV - b.c <= p["near_atr"] * A)
        trigger = (b.c > AV) & recent_below & vol
        stop = rolling_min(b.l, p["below_bars"] + 1) - p["stop_buffer_atr"] * A
        arm_stop = _nan(n)
    else:
        near = (b.l <= AV + p["touch_atr"] * A) & (b.c >= AV - p["touch_atr"] * A)
        beyond_before = any_within(np.nan_to_num(shift((b.c > AV).astype(float), 1)) > 0, 10)
        arm = near & beyond_before
        recent = any_within(arm, p["arm_expiry"] + 1)
        trigger = (b.c > AV) & (b.c > b.o) & recent & vol
        stop = rolling_min(b.l, p["arm_expiry"] + 1) - p["stop_buffer_atr"] * A
        arm_stop = AV - 2.0 * p["touch_atr"] * A - p["stop_buffer_atr"] * A

    def anchors(t: int) -> List[Dict[str, Any]]:
        a = anchor_at[t]
        if a < 0:
            return []
        man = fixed is not None
        price = b.h[a] if (mode == "reclaim") else b.l[a]
        return [{"role": "anchor", "index": int(a), "stamp": b.stamps[a], "price": w.px(price),
                 "label": "anchor" if man else "swing {}".format(w.high if mode == "reclaim" else w.low),
                 "confirmed_at": None if man else b.stamps[min(n - 1, a + right)], "manual": man}]

    def describe(t: int) -> Dict[str, Any]:
        has = anchor_at[t] >= 0
        anchor_word = ("the anchor date" if fixed is not None else
                       "the swing {} of {}".format(w.high if mode == "reclaim" else w.low,
                                                   b.stamps[anchor_at[t]]) if has else "no anchor")
        checks = [_check("Setup", "An anchor: {}".format(anchor_word), has)]
        if mode == "reclaim":
            checks.append(_check("Setup", "Closed {} the anchored VWAP within the last {} bars".format(
                w.below, p["below_bars"]), bool(recent_below[t]) if has else False, _fmt(w.px(AV[t]))))
            checks.append(_check("Trigger", "Completed close back {} the anchored VWAP".format(w.above),
                                 bool(b.c[t] > AV[t]) if has else False, _fmt(w.px(b.c[t]))))
        else:
            checks.append(_check("Setup", "A {} to within {:g} ATR of the anchored VWAP".format(
                w.pullback, p["touch_atr"]), bool(any_within(arm, p["arm_expiry"] + 1)[t]),
                _fmt(w.px(AV[t]))))
            checks.append(_check("Trigger", "Completed close {} the anchored VWAP, {} on the bar".format(
                w.above, w.up), bool(b.c[t] > AV[t] and b.c[t] > b.o[t]) if has else False,
                _fmt(w.px(b.c[t]))))
        vc = _vol_check(ind, p, t)
        if vc:
            checks.append(vc)
        return {
            "checks": checks,
            "values": {"Anchored VWAP": _fmt(w.px(AV[t]))},
            "trigger_text": ("price {} the VWAP anchored at {}".format(w.reclaimed, anchor_word) if mode == "reclaim"
                             else "price held a retest of the VWAP anchored at {}".format(anchor_word)),
            "setup_text": ("a close {} the anchored VWAP".format(w.below) if mode == "reclaim"
                           else "a {} to the anchored VWAP".format(w.pullback)),
            "waiting_text": "a completed close {} the anchored VWAP at {}".format(w.above, _fmt(w.px(AV[t]))),
            "watching_text": ("price is {} the anchored VWAP".format(w.above) if mode == "reclaim"
                              else "no {} to the anchored VWAP".format(w.pullback)),
            "arm_stop_text": "" if mode == "reclaim" else "a decisive close {} the anchored VWAP".format(w.below),
            "note": "Computed from daily typical prices and volume, an approximation of a VWAP built from every trade.",
        }

    return Detection(_ready_from(n, 42, A), arm, trigger, AV, stop, arm_stop,
                     {"Anchored VWAP": AV}, anchors=anchors, describe=describe)


# ------------------------------------------------------------ support / resistance

def _sr_levels(ind: Indicators, p: Dict[str, Any]):
    """At each bar, the nearest confirmed swing high above the prior close that
    no close has gone through since it formed, or NaN."""
    b, n = ind.b, len(ind.b)
    A = ind.atr(14)
    left, right = p["pivot_left"], p["pivot_right"]
    highs, _lows = ind.pivots(left, right)
    level = _nan(n)
    source = np.full(n, -1, dtype=int)
    for t in range(1, n):
        best, best_i = np.inf, -1
        lo_bound = t - p["lookback"]
        for i in highs:
            if i + right > t:
                break
            if i < lo_bound:
                continue
            L = b.h[i]
            if not (L >= b.c[t - 1]):
                continue
            between = b.c[i + 1:t]
            buf = p["break_atr"] * (A[t - 1] if np.isfinite(A[t - 1]) else 0.0)
            if between.size and np.any(between > L + buf):
                continue
            if L < best:
                best, best_i = L, i
        if best_i >= 0:
            level[t], source[t] = best, best_i
    return level, source


def detect_sr(ind: Indicators, p: Dict[str, Any], w: Words, mode: str) -> Detection:
    b, n = ind.b, len(ind.b)
    A = ind.atr(14)
    level, source = _sr_levels(ind, p)
    broke = (b.c > level + p["break_atr"] * A)
    right = p["pivot_right"]
    if mode == "breakout":
        vol = _vol_ok(ind, p)
        arm = np.isfinite(level) & (b.c >= level - p["near_atr"] * A)
        trigger = broke & vol
        stop = level - p["fail_atr"] * A - p["stop_buffer_atr"] * A
        arm_stop = _nan(n)
        trig_level = level
        retest_level = None
    else:
        arm, trigger, retest_level, fail, low_since = _retest(ind, p, level, broke)
        stop = low_since - p["stop_buffer_atr"] * A
        arm_stop = fail
        trig_level = retest_level

    def anchors(t: int) -> List[Dict[str, Any]]:
        i = source[t] if mode == "breakout" else -1
        if mode != "breakout":
            # The swing behind the level being retested: the latest one whose
            # price matches it.
            want = retest_level[t] if retest_level is not None else np.nan
            if np.isfinite(want):
                for j in range(t, -1, -1):
                    if source[j] >= 0 and abs(level[j] - want) < 1e-9:
                        i = source[j]
                        break
        if i is None or i < 0:
            return []
        return [{"role": "level", "index": int(i), "stamp": b.stamps[i], "price": w.px(b.h[i]),
                 "label": "swing " + w.high, "confirmed_at": b.stamps[min(n - 1, i + right)],
                 "manual": False}]

    def describe(t: int) -> Dict[str, Any]:
        L = level[t] if mode == "breakout" else (retest_level[t] if retest_level is not None else np.nan)
        has = bool(np.isfinite(L))
        if mode == "breakout":
            checks = [
                _check("Setup", "A confirmed swing {} not yet closed through".format(w.high), has,
                       _fmt(w.px(L))),
                _check("Setup", "Within {:g} ATR of it".format(p["near_atr"]), bool(arm[t]) if has else False),
                _check("Trigger", "Completed close {:g} ATR {} it".format(p["break_atr"], w.above),
                       bool(broke[t]) if has else False, _fmt(w.px(b.c[t]))),
            ]
            vc = _vol_check(ind, p, t)
            if vc:
                checks.append(vc)
        else:
            checks = [
                _check("Setup", "A broken swing {} in the last {} bars".format(w.high, p["retest_window"]),
                       has, _fmt(w.px(L))),
                _check("Setup", "Retest: back to within {:g} ATR of it, holding".format(p["touch_atr"]),
                       bool(any_within(arm, p["retest_window"])[t])),
                _check("Trigger", "Completed close {} the level and the prior bar's {}".format(
                    w.above, w.high), bool(trigger[t]), _fmt(w.px(b.c[t]))),
            ]
        return {
            "checks": checks,
            "values": {"Level": _fmt(w.px(L)), "ATR 14": _fmt(A[t])},
            "trigger_text": ("price closed through the swing {} at {}".format(w.high, _fmt(w.px(L))) if mode == "breakout"
                             else "price held the retest of the broken swing {} at {}".format(w.high, _fmt(w.px(L)))),
            "setup_text": ("price pressing the swing {} at {}".format(w.high, _fmt(w.px(L))) if mode == "breakout"
                           else "a retest of the broken swing {}".format(w.high)),
            "waiting_text": ("a completed close {:g} ATR {} {}".format(p["break_atr"], w.above, _fmt(w.px(L)))
                             if mode == "breakout" else
                             "a close {} the prior bar's {} with {} holding".format(w.above, w.high, _fmt(w.px(L)))),
            "watching_text": ("no confirmed swing {} within reach".format(w.high) if mode == "breakout"
                              else "no recent breakout to retest"),
            "arm_stop_text": "" if mode == "breakout" else "a close more than {:g} ATR back through the level".format(
                p["fail_atr"]),
        }

    return Detection(_ready_from(n, 42, A), arm, trigger, trig_level, stop, arm_stop,
                     {}, anchors=anchors,
                     levels=lambda t: ([{"price": w.px(level[t]), "label": w.resistance, "ratio": None,
                                         "zone": False}] if np.isfinite(level[t]) else []),
                     describe=describe)


# ---------------------------------------------------------------------- squeeze

def detect_squeeze(ind: Indicators, p: Dict[str, Any], w: Words) -> Detection:
    b, n = ind.b, len(ind.b)
    A = ind.atr(14)
    bu, bm, bl = bollinger(b.c, p["bb_len"], p["bb_mult"])
    ku, km, kl = keltner(b.h, b.l, b.c, p["kc_len"], p["kc_mult"], p["kc_len"])
    on = (bu < ku) & (bl > kl)
    run = np.zeros(n, dtype=int)
    for t in range(n):
        run[t] = run[t - 1] + 1 if (on[t] and t > 0) else (1 if on[t] else 0)
    release = np.zeros(n, dtype=bool)
    rng_hi = _nan(n)
    rng_lo = _nan(n)
    last_hi, last_lo, live = np.nan, np.nan, -10 ** 9
    for t in range(1, n):
        if on[t - 1] and not on[t] and run[t - 1] >= p["min_squeeze"]:
            release[t] = True
            s = t - run[t - 1]
            last_hi, last_lo, live = np.max(b.h[s:t]), np.min(b.l[s:t]), t
        if t - live < p["confirm_window"]:
            rng_hi[t], rng_lo[t] = last_hi, last_lo
    recent = any_within(release, p["confirm_window"])
    if p["direction_rule"] == "range":
        direction = b.c > rng_hi
    else:
        direction = (b.c > km) & (b.c > shift(b.c, 1))
    vol = _vol_ok(ind, p)
    arm = (on & (run >= p["min_squeeze"])) | recent
    trigger = recent & ~on & direction & vol
    stop = rng_lo - p["stop_buffer_atr"] * A
    warm = max(p["bb_len"], p["kc_len"]) * 3

    def describe(t: int) -> Dict[str, Any]:
        checks = [
            _check("Setup", "Bollinger bands inside the Keltner channel for at least {} bars".format(
                p["min_squeeze"]), bool(recent[t]) or bool(on[t] and run[t] >= p["min_squeeze"]),
                "{} bars".format(int(run[t])) if on[t] else None),
            _check("Trigger", "Released within the last {} bars".format(p["confirm_window"]),
                   bool(recent[t] and not on[t])),
            _check("Trigger", ("Closed {} the Keltner midline and the prior close".format(w.above)
                               if p["direction_rule"] == "mid" else
                               "Closed {} the squeeze's {}".format(w.above, w.high)), bool(direction[t]),
                   _fmt(w.px(b.c[t]))),
        ]
        vc = _vol_check(ind, p, t)
        if vc:
            checks.append(vc)
        return {
            "checks": checks,
            "values": {"Bollinger upper": _fmt(w.px(bu[t])), "Keltner upper": _fmt(w.px(ku[t])),
                       "Keltner mid": _fmt(w.px(km[t])), "Squeeze bars": int(run[t])},
            "trigger_text": "the squeeze released {} after {} bars".format(
                "upward" if w.bull else "downward", int(run[t - 1]) if t > 0 else 0),
            "setup_text": "a volatility squeeze",
            "waiting_text": "the bands to come back out with a close {} the midline".format(w.above),
            "watching_text": "no squeeze: the Bollinger bands are outside the Keltner channel",
            "arm_stop_text": "",
        }

    return Detection(_ready_from(n, warm, bu, ku, A), arm, trigger, km, stop, _nan(n),
                     {"Bollinger upper": bu, "Bollinger lower": bl, "Keltner upper": ku,
                      "Keltner lower": kl}, describe=describe)


DETECTORS: Dict[str, Callable[[Indicators, Dict[str, Any], Words], Detection]] = {
    "trend_pullback": detect_trend_pullback,
    "ema_cross": detect_ma_cross,
    "golden_cross": detect_ma_cross,
    "rsi_50": detect_rsi50,
    "rsi_oversold": detect_rsi_oversold,
    "macd_cross": detect_macd_cross,
    "momentum_confirm": detect_momentum_confirm,
    "fib_zone": detect_fib,
    "triple_stoch": detect_triple_stoch,
    "donchian_20": detect_donchian,
    "donchian_55": detect_donchian,
    "donchian_retest": detect_donchian_retest,
    "avwap_reclaim": lambda i, p, w: detect_avwap(i, p, w, "reclaim"),
    "avwap_retest": lambda i, p, w: detect_avwap(i, p, w, "retest"),
    "sr_breakout": lambda i, p, w: detect_sr(i, p, w, "breakout"),
    "sr_retest": lambda i, p, w: detect_sr(i, p, w, "retest"),
    "squeeze": detect_squeeze,
}


# ===================================================================== context

@dataclass
class Context:
    ok: np.ndarray
    checks: Callable[[int], List[Dict[str, Any]]]
    passed_text: Callable[[int], List[str]]


def _align(bars: Bars, other: Optional[Bars]) -> np.ndarray:
    """`other`'s latest completed close at each of `bars`' candles, by time."""
    out = np.full(len(bars), np.nan)
    if other is None or not len(other):
        return out
    j = -1
    for t, end in enumerate(bars.ends):
        while j + 1 < len(other) and other.ends[j + 1] <= end:
            j += 1
        if j >= 0:
            out[t] = other.c[j]
    return out


def build_context(bars: Bars, htf: Optional[HigherTimeframe], bench: Optional[Bars],
                  p: Dict[str, Any], bull: bool, bench_name: str) -> Context:
    """The backdrop filters, each optional, all on completed candles.

    `bars` are the real (unmirrored) candles: relative strength is a ratio of
    two real prices and a negated one would cancel out."""
    n = len(bars)
    sign = 1.0 if bull else -1.0
    word_above, word_rising = ("above", "rising") if bull else ("below", "falling")

    # Higher-timeframe trend.
    htf_ok = np.zeros(n, dtype=bool)
    htf_vals: List[Tuple[Optional[float], Optional[float]]] = [(None, None)] * n
    unit = htf.unit if htf is not None else "week"
    length = p["htf_len"] if unit == "week" else p["htf_len_4h"]
    k = p["htf_slope"]
    if htf is not None and htf.closes.size:
        cl = sign * htf.closes
        ma = sma(cl, length)
        for t in range(n):
            j = htf.latest[t]
            if j < 0 or j - k < 0 or not np.isfinite(ma[j]) or not np.isfinite(ma[j - k]):
                continue
            htf_ok[t] = bool(cl[j] > ma[j] and ma[j] > ma[j - k])
            htf_vals[t] = (htf.closes[j], sign * ma[j])
    ready_htf = np.array([htf is not None and htf.latest[t] >= 0 and htf_vals[t][1] is not None
                          for t in range(n)])

    # Market regime: the benchmark against its long average.
    bc = _align(bars, bench)
    regime_ok = np.zeros(n, dtype=bool)
    regime_ma = np.full(n, np.nan)
    if bench is not None and len(bench):
        ma_b = sma(sign * bench.c, p["regime_len"])
        aligned = _align(bars, Bars(bench.stamps, bench.ends, ma_b, ma_b, ma_b, ma_b, bench.v))
        regime_ma = sign * aligned
        regime_ok = np.isfinite(aligned) & (sign * bc > aligned)

    # Relative strength: the stock's change against the benchmark's over the window.
    L = p["rs_len"]
    ratio = bars.c / bc
    rs = ratio / shift(ratio, L) - 1.0
    rs_ok = np.isfinite(rs) & ((rs > 0) if bull else (rs < 0))

    ok = np.ones(n, dtype=bool)
    if p["htf_filter"]:
        ok &= htf_ok
    if p["regime_filter"]:
        ok &= regime_ok
    if p["rs_filter"]:
        ok &= rs_ok

    unit_name = "weekly" if unit == "week" else "daily"
    tf_unit = "week" if unit == "week" else "day"

    def checks(t: int) -> List[Dict[str, Any]]:
        close_w, ma_w = htf_vals[t]
        out = [_check("Context", "The last completed {} close {} a {} {}-{} SMA".format(
            unit_name, word_above, word_rising, length, tf_unit),
            bool(htf_ok[t]) if ready_htf[t] else None,
            "{} vs {}".format(_fmt(close_w), _fmt(ma_w)) if close_w is not None else
            "not enough {} history".format(unit_name), required=bool(p["htf_filter"]))]
        out.append(_check("Context", "{} {} its {}-day SMA".format(bench_name, word_above, p["regime_len"]),
                          bool(regime_ok[t]) if np.isfinite(regime_ma[t]) else None,
                          "{} vs {}".format(_fmt(bc[t]), _fmt(regime_ma[t])) if np.isfinite(regime_ma[t])
                          else None, required=bool(p["regime_filter"])))
        out.append(_check("Context", "{} {} over {} bars".format(
            "Beat" if bull else "Lagged", bench_name, L),
            bool(rs_ok[t]) if np.isfinite(rs[t]) else None,
            "{:+.1f}% vs {}".format(rs[t] * 100.0, bench_name) if np.isfinite(rs[t]) else None,
            required=bool(p["rs_filter"])))
        return out

    def passed_text(t: int) -> List[str]:
        out = []
        if p["htf_filter"] and htf_ok[t]:
            out.append("{} trend filter passed".format(unit_name))
        if p["regime_filter"] and regime_ok[t]:
            out.append("{} {} its {}-day average".format(bench_name, word_above, p["regime_len"]))
        if p["rs_filter"] and rs_ok[t]:
            out.append("{} {} over {} bars".format("beat" if bull else "lagged", bench_name, L))
        return out

    return Context(ok, checks, passed_text)


# =================================================================== lifecycle

def lifecycle(bars: Bars, det: Detection, ctx_ok: np.ndarray, p: Dict[str, Any],
              start: int = 0) -> Tuple[List[Dict[str, Any]], str, Optional[Dict[str, Any]]]:
    """Walk the candles once and say what the preset did on each.

    Arms on a setup while the context holds. An armed setup triggers on its
    trigger event, needing the context again at that bar and the cooldown since
    the last trigger to have passed. It is invalidated by a completed close
    beyond its armed invalidation level, and expires `arm_expiry` bars after it
    armed. A triggered signal is invalidated by a completed close beyond the
    level fixed when it fired, and expires after `signal_ttl` bars. A bar that
    resolves a setup or a signal does not also start the next one.

    **Expiry counts from the bar it armed, and re-arming needs a fresh setup.**
    Counted from the last bar the setup was seen instead, a setup that is a
    state rather than an event (price sitting just above a VWAP) stayed armed
    for seven weeks on AAPL, which is not a setup anyone is waiting on. After
    one ends, the setup has to clear and come back before it arms again. A
    trigger is never lost to that rule: every trigger implies a setup within the
    rule's own window, so it arms and fires on its own bar.

    Prices are on the direction's own scale: "beyond" is always "below" here.
    """
    n = len(bars)
    arm = det.arm | det.trigger
    events: List[Dict[str, Any]] = []
    state, inst = "watching", None
    last_trigger = -10 ** 9
    blocked = False

    def event(kind: str, t: int, **extra) -> None:
        events.append({"type": kind, "index": t, "stamp": bars.stamps[t], **extra})

    def fire(t: int) -> None:
        nonlocal state, last_trigger
        stop = det.stop[t]
        if not np.isfinite(stop):
            stop = bars.l[t]
        inst.update(trigger_t=t, stop=float(stop), level=float(det.trigger_level[t])
                    if np.isfinite(det.trigger_level[t]) else float(bars.c[t]),
                    close=float(bars.c[t]))
        event("triggered", t, close=float(bars.c[t]), level=inst["level"], stop=inst["stop"])
        state, last_trigger = "triggered", t

    for t in range(max(0, start), n):
        if not det.ready[t]:
            continue
        ok = bool(ctx_ok[t])
        c = bars.c[t]
        cooled = t - last_trigger >= p["cooldown"]
        if state == "triggered":
            if c < inst["stop"]:
                event("invalidated", t, close=float(c), level=inst["stop"], of="signal")
                state, inst, blocked = "watching", None, True
            elif t - inst["trigger_t"] >= p["signal_ttl"]:
                event("expired", t, of="signal")
                state, inst, blocked = "watching", None, True
            continue
        if state == "armed":
            if det.trigger[t] and ok and cooled:
                fire(t)
                continue
            lvl = det.arm_stop[t]
            if np.isfinite(lvl) and c < lvl:
                event("invalidated", t, close=float(c), level=float(lvl), of="setup")
                state, inst, blocked = "watching", None, True
                continue
            if t - inst["arm_t"] >= p["arm_expiry"]:
                event("expired", t, of="setup")
                state, inst, blocked = "watching", None, True
            continue
        if blocked and not arm[t]:
            blocked = False
        if ok and det.trigger[t] and cooled:
            inst = {"arm_t": t}
            event("armed", t, close=float(c))
            state = "armed"
            fire(t)
        elif ok and arm[t] and not blocked:
            inst = {"arm_t": t}
            event("armed", t, close=float(c))
            state = "armed"
    return events, state, inst


# ===================================================================== a row

def _real(w: Words, x: Any) -> Optional[float]:
    v = w.px(x)
    return None if v is None else round(v, 4)


def _date_word(stamp: str) -> str:
    """"Oct 5" for a daily candle, "Oct 5 13:30" for a 4-hour one."""
    try:
        if "T" in stamp:
            dt = datetime.fromisoformat(stamp)
            return dt.strftime("%b %-d %H:%M")
        d = date.fromisoformat(stamp[:10])
        return d.strftime("%b %-d")
    except ValueError:
        return stamp


def _groups(checks: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Conditions met, one per group of required checks.

    A group passes when every required check in it passes. Checks that are
    listed for information (a filter switched off) are shown and not counted."""
    order: List[str] = []
    passed: Dict[str, bool] = {}
    for ch in checks:
        if not ch.get("required"):
            continue
        g = ch["group"]
        if g not in passed:
            order.append(g)
            passed[g] = True
        passed[g] = passed[g] and ch.get("passed") is True
    met = sum(1 for g in order if passed[g])
    return {"met": met, "of": len(order),
            "groups": [{"group": g, "passed": passed[g]} for g in order],
            "note": ("Counts each listed condition once, a group of checks passing "
                     "together as one. Momentum readings (RSI, MACD, stochastics) "
                     "count as one condition however many are used. Not a probability "
                     "of success.")}


def evaluate(bars: Bars, ind: Indicators, preset_id: str, p: Dict[str, Any], bull: bool,
             ctx: Context, start: int, symbol: str = "",
             real_bars: Optional[Bars] = None) -> Tuple[Dict[str, Any], Detection, List[Dict[str, Any]]]:
    """One preset, one direction: its state now and the words for it."""
    w = Words(bull, bars.timeframe)
    preset = PRESET_BY_ID[preset_id]
    det = DETECTORS[preset_id](ind, p, w)
    events, state, inst = lifecycle(bars, det, ctx.ok, p, start)
    n = len(bars)
    last = n - 1
    real = real_bars if real_bars is not None else bars
    candle = "Daily candle" if bars.timeframe == "daily" else "4-hour candle"

    status, at = "watching", last
    last_event = events[-1] if events else None
    if state == "triggered":
        status, at = "triggered", inst["trigger_t"]
    elif state == "armed":
        status, at = "armed", last
    elif last_event and last_event["type"] in ("invalidated", "expired") and last - last_event["index"] < RECENT_BARS:
        status, at = last_event["type"], last_event["index"]
    elif not (det.ready[last] and ctx.ok[last]):
        status = "inactive"

    eval_t = inst["trigger_t"] if state == "triggered" else last
    info = det.describe(eval_t)
    checks = ctx.checks(eval_t) + info["checks"]
    passed = ctx.passed_text(eval_t)

    trigger = None
    invalidation = None
    trigger_level = None
    if state == "triggered":
        trigger = {"stamp": bars.stamps[inst["trigger_t"]], "close": _real(w, inst["close"]),
                   "level": _real(w, inst["level"])}
        invalidation = _real(w, inst["stop"])
        trigger_level = trigger["level"]
    else:
        lvl = det.trigger_level[last]
        trigger_level = _real(w, lvl) if np.isfinite(lvl) else None
        stop_now = det.arm_stop[last] if np.isfinite(det.arm_stop[last]) else det.stop[last]
        invalidation = _real(w, stop_now) if np.isfinite(stop_now) else None

    if status in ("invalidated", "expired") and last_event and last_event.get("of") == "signal":
        # The signal that just resolved, so the row still says what it was.
        fired = next((e for e in reversed(events) if e["type"] == "triggered"), None)
        if fired:
            trigger = {"stamp": fired["stamp"], "close": _real(w, fired["close"]),
                       "level": _real(w, fired["level"])}
            trigger_level = trigger["level"]
            invalidation = _real(w, fired["stop"])

    def clause(text: str) -> str:
        return text[:1].upper() + text[1:] if text else text

    if status == "triggered":
        text = "{} {}: {}".format(candle, _date_word(bars.stamps[at]), clause(info["trigger_text"]))
        text += "".join("; " + s for s in passed)
        text += ". Invalidated by a completed close {} {}.".format(w.below, _fmt(invalidation))
    elif status == "armed":
        text = "Armed {}: {}. Waiting for {}.".format(
            _date_word(bars.stamps[inst["arm_t"]]), info["setup_text"], info["waiting_text"])
        if info.get("arm_stop_text"):
            text += " Ends on {}.".format(info["arm_stop_text"])
    elif status == "invalidated":
        text = "Invalidated {} by a completed close {} {}.".format(
            _date_word(bars.stamps[at]), w.below, _fmt(_real(w, last_event.get("level"))))
    elif status == "expired":
        text = ("The signal from {} has been listed for {} bars and has expired.".format(
            _date_word(next((e["stamp"] for e in reversed(events) if e["type"] == "triggered"), bars.stamps[at])),
            p["signal_ttl"]) if last_event.get("of") == "signal" else
            "Expired {}: no trigger within {} bars of the setup.".format(_date_word(bars.stamps[at]),
                                                                       p["arm_expiry"]))
    elif status == "inactive":
        if not det.ready[last]:
            text = "Not enough history for this rule yet."
        else:
            failed = [c["rule"] for c in ctx.checks(last) if c["required"] and c["passed"] is not True]
            text = "Context not met: {}.".format("; ".join(failed).lower() if failed else "a filter failed")
    else:
        text = "Context holds; {}.".format(info["watching_text"])

    vavg = ind.vol_avg(20)[eval_t]
    volume = {"last": float(real.v[eval_t]), "avg20": float(vavg) if np.isfinite(vavg) else None,
              "ratio": round(float(real.v[eval_t] / vavg), 2) if np.isfinite(vavg) and vavg > 0 else None}

    row = {
        "symbol": symbol,
        "preset": preset_id,
        "label": preset["label"],
        "family": preset["family"],
        "kind": preset["kind"],
        "experimental": bool(preset.get("experimental")),
        "direction": "bull" if bull else "bear",
        "timeframe": bars.timeframe,
        "status": status,
        "status_at": bars.stamps[at],
        "armed_at": bars.stamps[inst["arm_t"]] if inst and "arm_t" in inst else None,
        "trigger": trigger,
        "trigger_level": trigger_level,
        "invalidation": invalidation,
        "explanation": text,
        "conditions": _groups(checks),
        "checks": checks,
        "values": info.get("values", {}),
        "note": info.get("note"),
        "zone": info.get("zone"),
        "volume": volume,
        "as_of": bars.stamps[last],
        "key": ("setup:{}:{}:{}:{}:{}".format(symbol, preset_id, "bull" if bull else "bear",
                                             bars.timeframe, trigger["stamp"]) if trigger else None),
    }
    return row, det, events


# ================================================================== the chart

def chart_payload(real: Bars, det: Detection, events: List[Dict[str, Any]], bull: bool,
                  row: Dict[str, Any], window: int = 120) -> Dict[str, Any]:
    """What the page needs to draw this setup: the candles, the rule's own lines,
    the anchors it measured from and the bars where its state changed."""
    w = Words(bull)
    n = len(real)
    s = max(0, n - window)
    last = n - 1
    eval_t = next((e["index"] for e in reversed(events) if e["type"] == "triggered"), last) \
        if row["status"] == "triggered" else last

    def clip(arr: np.ndarray) -> List[Optional[float]]:
        return [None if not np.isfinite(x) else round(float(x) * w.sign, 4) for x in arr[s:]]

    marks = []
    for e in events:
        if e["index"] < s:
            continue
        marks.append({"index": e["index"] - s, "type": e["type"], "stamp": e["stamp"],
                      "price": _real(w, e.get("close")) if e.get("close") is not None else None,
                      "level": _real(w, e.get("level")) if e.get("level") is not None else None})
    anchors = []
    for a in det.anchors(eval_t):
        item = dict(a)
        item["index"] = a["index"] - s if a["index"] >= s else None
        anchors.append(item)
    return {
        "stamps": real.stamps[s:],
        "open": [round(float(x), 4) for x in real.o[s:]],
        "high": [round(float(x), 4) for x in real.h[s:]],
        "low": [round(float(x), 4) for x in real.l[s:]],
        "close": [round(float(x), 4) for x in real.c[s:]],
        "volume": [float(x) for x in real.v[s:]],
        "lines": {name: clip(arr) for name, arr in det.lines.items()},
        "marks": marks,
        "anchors": anchors,
        "levels": det.levels(eval_t),
        "trigger_level": row.get("trigger_level"),
        "invalidation": row.get("invalidation"),
    }


# ======================================================= historical evaluation

def history(real: Bars, bull: bool, events: List[Dict[str, Any]], opts: Dict[str, Any]) -> Dict[str, Any]:
    """How the rule's triggers would have played out on the stock, simulated.

    Entry at the open of the candle after the trigger, the first price that
    exists once the signal does, never the trigger candle's own close. Exit at
    the invalidation level (at the open instead when the price gaps through it),
    at a multiple of the risk, or at the close after a set number of bars,
    whichever comes first; when one candle reaches both the stop and the target
    it is counted as the stop. Slippage is charged on the way in and the way out.

    Stock prices only. There is no history of option prices here, so nothing
    below is an options return and none should be read as one."""
    s_dir = 1.0 if bull else -1.0
    slip = float(opts.get("slippage_bps", 5.0)) / 10000.0
    target_r = float(opts.get("target_r", 2.0))
    max_hold = int(opts.get("max_hold", 20))
    trades = []
    for e in events:
        if e["type"] != "triggered":
            continue
        t = e["index"]
        if t + 1 >= len(real):
            continue
        entry = real.o[t + 1] * (1.0 + s_dir * slip)
        stop = s_dir * e["stop"]
        risk = s_dir * (entry - stop)
        if not (np.isfinite(entry) and np.isfinite(stop)) or risk <= 0:
            continue                       # opened through the stop: no trade
        target = entry + s_dir * target_r * risk
        exit_px, exit_t, why = None, None, None
        for k in range(t + 1, min(len(real), t + 1 + max_hold)):
            o, h, l, c = real.o[k], real.h[k], real.l[k], real.c[k]
            hit_stop = (l <= stop) if bull else (h >= stop)
            hit_target = (h >= target) if bull else (l <= target)
            if hit_stop:
                gap = (o < stop) if bull else (o > stop)
                exit_px, exit_t, why = (o if gap else stop), k, "invalidation"
                break
            if hit_target:
                gap = (o > target) if bull else (o < target)
                exit_px, exit_t, why = (o if gap else target), k, "target"
                break
            if k == t + max_hold:
                exit_px, exit_t, why = c, k, "time"
        if exit_px is None:
            k = min(len(real) - 1, t + max_hold)
            if k <= t:
                continue
            exit_px, exit_t, why = real.c[k], k, "open" if k == len(real) - 1 else "time"
        exit_px = exit_px * (1.0 - s_dir * slip)
        pnl = s_dir * (exit_px - entry)
        trades.append({"signal": e["stamp"], "entry_at": real.stamps[t + 1], "entry": round(float(entry), 4),
                       "exit_at": real.stamps[exit_t], "exit": round(float(exit_px), 4), "why": why,
                       "r": round(float(pnl / risk), 3), "pct": round(float(pnl / entry * 100.0), 3),
                       "bars": int(exit_t - t)})

    def summary(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not rows:
            return {"n": 0}
        rs = np.array([r["r"] for r in rows])
        curve = np.cumsum(rs)
        peak = np.maximum.accumulate(np.concatenate([[0.0], curve]))[1:]
        return {"n": len(rows), "win_rate_pct": round(float(np.mean(rs > 0) * 100.0), 1),
                "avg_r": round(float(np.mean(rs)), 3), "median_r": round(float(np.median(rs)), 3),
                "total_r": round(float(np.sum(rs)), 2),
                "max_drawdown_r": round(float(np.max(peak - curve)) if len(curve) else 0.0, 2),
                "avg_bars": round(float(np.mean([r["bars"] for r in rows])), 1)}

    span_from, span_to = real.stamps[0], real.stamps[-1]
    split_i = int(len(real) * 0.7)
    split = real.stamps[min(split_i, len(real) - 1)]
    earlier = [r for r in trades if r["entry_at"] < split]
    later = [r for r in trades if r["entry_at"] >= split]
    out = {
        "from": span_from, "to": span_to, "split": split,
        "all": summary(trades), "earlier": summary(earlier), "held_out": summary(later),
        "trades": trades[-25:],
        "assumptions": {
            "entry": "the open of the candle after the trigger",
            "exits": "the invalidation level, {:g} times the risk, or the close after {} bars".format(
                target_r, max_hold),
            "slippage_bps_each_way": round(slip * 10000.0, 2),
            "fees": "none charged",
            "same_bar": "a candle reaching both the stop and the target counts as the stop",
        },
        "caveat": ("Stock prices only, not options returns: there is no history of option "
                   "prices here. The held-out part is the last 30% of the dates; if you tune "
                   "the parameters, tune them on the earlier part and read the held-out part "
                   "as the check."),
    }
    if trades and len(trades) < 20:
        out["small_sample"] = ("{} trade{} is too few to tell a rule from luck.".format(
            len(trades), "" if len(trades) == 1 else "s"))
    return out


# ============================================================ option contracts

OPTION_FILTER_DEFAULTS = {"dte_min": 21, "dte_max": 60, "min_oi": 100, "min_volume": 10,
                          "max_spread_pct": 10.0, "delta_min": 0.2, "delta_max": 0.8,
                          "hold_days": 30, "budget": None}


def contracts_for(chain: Optional[pd.DataFrame], spot: Optional[float], bull: bool,
                  filters: Dict[str, Any], earnings: Optional[str],
                  now: Optional[datetime] = None) -> Dict[str, Any]:
    """The contracts on one side that pass the reader's filters, listed, not ranked.

    The signal came from the stock; this is a separate question asked of the
    chain. Every filter is reported with how many contracts it removed, so a
    short list reads as the filters and not as a thin chain, and none of the
    survivors is called the best one."""
    f = {**OPTION_FILTER_DEFAULTS, **{k: v for k, v in (filters or {}).items() if v is not None}}
    side = "call" if bull else "put"
    today = _now_et(now).date()
    earn = None
    try:
        earn = date.fromisoformat(str(earnings)[:10]) if earnings else None
    except ValueError:
        earn = None
    hold_end = today + timedelta(days=int(f["hold_days"]))
    earnings_in_hold = bool(earn and today <= earn <= hold_end)
    notes = [
        "Open interest counts contracts still open after the last session. It says "
        "nothing about how easily one trades now; the bid-ask spread and today's volume "
        "are closer to that.",
        "The invalidation level is a stock price. It does not cap what an option can lose: "
        "time decay and a fall in implied volatility can cut its value while the stock "
        "holds, and a bought option can lose all of its premium.",
        "IV rank and percentile are not shown: they need a year of this stock's own "
        "implied volatility, which the free feed does not provide.",
    ]
    base = {"side": side, "filters": f, "earnings": earn.isoformat() if earn else None,
            "earnings_in_hold": earnings_in_hold, "hold_days": int(f["hold_days"]), "notes": notes}
    if chain is None or chain.empty or spot is None:
        return {**base, "available": False, "reason": "No option chain could be read for this symbol.",
                "considered": 0, "passed": 0, "dropped": {}, "contracts": []}
    pool = chain[chain["is_call"] == bull].copy()
    considered = int(len(pool))
    dropped: Dict[str, int] = {}

    def keep(mask, why):
        nonlocal pool
        mask = mask.fillna(False) if hasattr(mask, "fillna") else mask
        dropped[why] = int((~mask).sum())
        pool = pool[mask]

    keep((pool["dte"] >= f["dte_min"]) & (pool["dte"] <= f["dte_max"]),
         "{} to {} days to expiry".format(f["dte_min"], f["dte_max"]))
    keep(pool["open_interest"] >= f["min_oi"], "open interest at least {}".format(f["min_oi"]))
    keep(pool["volume"] >= f["min_volume"], "volume today at least {}".format(f["min_volume"]))
    keep((pool["spread_pct"] <= f["max_spread_pct"]) & (pool["bid"] > 0),
         "a bid, and a spread at most {:g}% of the mid".format(f["max_spread_pct"]))
    if "delta" in pool.columns:
        d = pool["delta"].abs()
        keep((d >= f["delta_min"]) & (d <= f["delta_max"]),
             "delta between {:g} and {:g}".format(f["delta_min"], f["delta_max"]))
    if f.get("budget"):
        keep(pool["mid"] * 100.0 <= float(f["budget"]),
             "costs at most ${:,.0f} for one".format(float(f["budget"])))
    pool = pool.sort_values(["expiry", "strike"])
    fetched = None
    if "fetched_at" in chain.columns and len(chain):
        fetched = str(chain["fetched_at"].iloc[0])

    def num(v, digits=4):
        try:
            x = float(v)
        except (TypeError, ValueError):
            return None
        return round(x, digits) if math.isfinite(x) else None

    rows = []
    for _, r in pool.head(40).iterrows():
        filled = bool(r.get("iv_filled")) if "iv_filled" in pool.columns else False
        last_trade = r.get("last_trade")
        try:
            last_trade = None if last_trade is None or pd.isna(last_trade) else pd.Timestamp(last_trade).isoformat()
        except (TypeError, ValueError):
            last_trade = None
        expiry = str(r["expiry"])
        rows.append({
            "contract": r.get("contract"), "expiry": expiry, "dte": int(r["dte"]),
            "strike": num(r["strike"], 2), "bid": num(r["bid"], 2), "ask": num(r["ask"], 2),
            "mid": num(r["mid"], 2), "spread_pct": num(r["spread_pct"], 1),
            "volume": int(r["volume"]) if num(r["volume"]) is not None else None,
            "open_interest": int(r["open_interest"]) if num(r["open_interest"]) is not None else None,
            # A filled-in IV is withheld, and so are the greeks built on it:
            # both would be the median of the neighbours shown as this
            # contract's own quote.
            "iv_pct": None if filled else num(float(r["iv"]) * 100.0, 1),
            "iv_note": "not quoted by the feed" if filled else None,
            "delta": None if filled else num(r.get("delta"), 3),
            "gamma": None if filled else num(r.get("gamma"), 5),
            "theta": None if filled else num(r.get("theta"), 3),
            "vega": None if filled else num(r.get("vega"), 3),
            "last_trade": last_trade,
            "cost_for_one": num(float(r["mid"]) * 100.0, 0),
            "breakeven": num(float(r["strike"]) + float(r["mid"]) if bull
                             else float(r["strike"]) - float(r["mid"]), 2),
            "through_earnings": bool(earn and date.fromisoformat(expiry[:10]) >= earn and earn >= today),
        })
    return {**base, "available": True, "considered": considered, "passed": int(len(pool)),
            "shown": len(rows), "dropped": dropped, "contracts": rows, "fetched_at": fetched,
            "order": "by expiry, then strike. Not ranked: no contract here is called the best."}


# ===================================================================== scanning

def _overrides_for(overrides: Optional[Dict[str, Any]], preset_id: str) -> Dict[str, Any]:
    o = overrides or {}
    return {**(o.get("*") or {}), **(o.get(preset_id) or {})}


def benchmark_of(overrides: Optional[Dict[str, Any]]) -> str:
    raw = ((overrides or {}).get("*") or {}).get("benchmark")
    spec = next(s for s in CONTEXT_PARAMS if s["key"] == "benchmark")
    return _coerce(spec, raw)


def analyse(symbol: str, daily: Optional[pd.DataFrame], bench_daily: Optional[pd.DataFrame],
            presets: Optional[Sequence[str]] = None, directions: Sequence[str] = DIRECTIONS,
            overrides: Optional[Dict[str, Any]] = None, timeframe: str = "daily",
            intraday: Optional[pd.DataFrame] = None, now: Optional[datetime] = None,
            provisional: bool = False, detail: Optional[Tuple[str, str]] = None,
            history_opts: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Every requested preset, both directions, on one symbol's completed candles.

    `detail` names one (preset, direction) to return the chart and, when
    `history_opts` is given, the historical evaluation for."""
    presets = [p for p in (presets or [p["id"] for p in PRESETS]) if p in PRESET_BY_ID]
    bench_name = benchmark_of(overrides)
    day_bars = daily_bars(daily, now)
    bench = daily_bars(bench_daily, now) if bench_daily is not None else None
    if timeframe == "4h":
        bars = intraday_bars(intraday, 240, now)
        htf = daily_context_for(bars, day_bars) if (bars is not None and day_bars is not None) else None
    else:
        bars = day_bars
        htf = weekly_context(bars) if bars is not None else None
    if bars is None or len(bars) < 30:
        return {"symbol": symbol, "available": False, "rows": [],
                "reason": "Not enough completed {} candles for {}.".format(
                    "4-hour" if timeframe == "4h" else "daily", symbol)}

    n = len(bars)
    start = max(0, n - SCAN_BARS)
    rows: List[Dict[str, Any]] = []
    detail_out: Dict[str, Any] = {}
    forming_bars = bars.with_forming() if provisional else None
    for direction in directions:
        bull = direction == "bull"
        b_dir = bars if bull else bars.mirrored()
        ind = Indicators(b_dir)
        f_dir = None
        if forming_bars is not None:
            f_dir = forming_bars if bull else forming_bars.mirrored()
            f_ind = Indicators(f_dir)
            if timeframe == "daily":
                f_htf = weekly_context(forming_bars)
            else:
                f_htf = daily_context_for(forming_bars, day_bars) if day_bars is not None else None
        for pid in presets:
            p = resolve_params(pid, _overrides_for(overrides, pid))
            ctx = build_context(bars, htf, bench, p, bull, bench_name)
            row, det, events = evaluate(b_dir, ind, pid, p, bull, ctx, start, symbol, bars)
            if f_dir is not None:
                f_ctx = build_context(forming_bars, f_htf, bench, p, bull, bench_name)
                _f_row, _f_det, f_events = evaluate(f_dir, f_ind, pid, p, bull, f_ctx, start,
                                                    symbol, forming_bars)
                fresh = [e for e in f_events if e["index"] == len(forming_bars) - 1]
                if fresh:
                    e = fresh[-1]
                    w = Words(bull)
                    row["provisional"] = {
                        "event": e["type"], "stamp": e["stamp"],
                        "close": round(float(forming_bars.c[-1]), 4),
                        "level": _real(w, e.get("level")) if e.get("level") is not None else None,
                        "text": ("Provisional: would {} if the candle closed at {}. The candle is still "
                                 "forming, so this is not a signal and raises no alert.".format(
                                     {"triggered": "trigger", "armed": "arm", "invalidated": "be invalidated",
                                      "expired": "expire"}.get(e["type"], e["type"]),
                                     _fmt(forming_bars.c[-1]))),
                    }
            rows.append(row)
            if detail and detail == (pid, direction):
                detail_out = {"chart": chart_payload(bars, det, events, bull, row),
                              "rules": PRESET_BY_ID[pid]["rules"][direction],
                              "params": p}
                if history_opts is not None:
                    manual = any(p.get(k) for k in ("anchor_low", "anchor_high", "anchor_date"))
                    if manual:
                        detail_out["history"] = {
                            "available": False,
                            "reason": "A manual anchor is chosen with hindsight, so the rule is "
                                      "not evaluated on past candles while one is set."}
                    else:
                        past, _state, _inst = lifecycle(b_dir, det, ctx.ok, p, 0)
                        detail_out["history"] = {"available": True,
                                                 **history(bars, bull, past, history_opts)}
    out = {"symbol": symbol, "available": True, "timeframe": timeframe, "rows": rows,
           "as_of": bars.stamps[-1], "benchmark": bench_name,
           "forming": ({"stamp": bars.forming["stamp"],
                        "note": "The {} candle is still forming and is left out of every rule.".format(
                            _date_word(bars.forming["stamp"]))} if bars.forming else None),
           "missing_sessions": bars.gaps,
           "recent_stamps": bars.stamps[-30:]}
    if detail:
        out["detail"] = detail_out
    return out


FRESH_BARS = 3


def fresh_triggers(result: Dict[str, Any], preset: str = "any",
                   within: int = FRESH_BARS) -> List[Dict[str, Any]]:
    """Triggered rows whose trigger is one of the last `within` completed candles.

    What an alert is raised from. A trigger from last month that is still on the
    list is not news; one from the last close is, and the window is three
    candles rather than one so a check that missed a day still finds it."""
    if not result or not result.get("available"):
        return []
    out = []
    as_of = result.get("as_of")
    for r in result["rows"]:
        if r["status"] != "triggered" or not r.get("trigger"):
            continue
        if preset not in ("any", "", None) and r["preset"] != preset:
            continue
        out.append(r)
    if not out or not as_of:
        return out
    # Distance in candles, measured on the symbol's own stamps.
    return [r for r in out if _bars_between(result, r["trigger"]["stamp"], as_of) < within]


def _bars_between(result: Dict[str, Any], a: str, b: str) -> int:
    order = result.get("recent_stamps")
    if order:
        try:
            return order.index(b) - order.index(a)
        except ValueError:
            return 10 ** 6
    # Without the stamp list, calendar sessions between the two daily dates.
    try:
        da, db = date.fromisoformat(a[:10]), date.fromisoformat(b[:10])
    except ValueError:
        return 10 ** 6
    count, probe = 0, da
    while probe < db and count < 400:
        probe = session_mod.next_trading_day(probe)
        count += 1
    return count
