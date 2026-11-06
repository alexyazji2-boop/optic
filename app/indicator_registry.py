"""What each chart indicator Milo can explain is, written once (owner's Handoff 7, 2026-11-03: Explain This Indicator).

A reader presses Explain on an indicator on the chart, and Milo is sent the indicator's name, its settings, the value
the chart computed and the bar it is for, with the ticker and the timeframe. This module is where Optic says what the
indicator is (at each of the reader's five knowledge levels), how it is worked out, what it cannot tell you, where
its definition comes from, and what a given reading describes, so that none of that is left to the model.

Built on the pattern of the figure registry (Handoff 1, app/figures/registry.py on its own branch): an entry is a
definition, never a number. Values are the chart's own: static/v2/js/ui/pricechart.js computes every one of these
on the chart's bars, and the reading it sends is checked here (`clean_reading`), never recomputed, so the number Milo
quotes is the number the chart draws. `describe` turns a reading into a sentence of what it describes, from that
reading alone.

Entries describe; they never judge. No sentence here calls a reading a signal, a buy or a sell, or a level a target,
and tests/test_explain_indicator.py holds every definition, limit and description to that over a grid of readings.

The first five, as the handoff asks: RSI, MACD, the simple and exponential averages, and Bollinger Bands. Another
indicator joins only with its definitions here and its tests.
"""

from __future__ import annotations

import math
import re
from typing import Any, Dict, List, Optional

LEVELS = ("new", "beginner", "intermediate", "advanced", "expert")
DEFAULT_LEVEL = "intermediate"
VERSION = "2026-11-04.1"

# Where the chart's bars come from (app/main.py: /api/ticker and /api/daily-bars, /api/weekly-bars, /api/intraday all
# read YF_PROVIDER), and how the chart treats them.
PRICE_SOURCE = "Optic's chart, computed on Yahoo Finance bars; daily and weekly bars are split-adjusted"

# The ids are the chart's (static/v2/js/pages/chart.js OVERLAYS and PANES); the labels are its STUDY_SPEC labels.
REGISTRY: Dict[str, Dict[str, Any]] = {
    "rsi": {
        "id": "rsi", "name": "Relative Strength Index", "short": "RSI 14", "settings": {"period": 14},
        "values": ["rsi"], "unit": "index from 0 to 100", "needs": 15,
        "formula": "100 minus 100 divided by one plus the average gain over the average loss of the last 14 bars, "
                   "each average smoothed the way Wilder set out (a running average that gives each new bar a "
                   "fourteenth of the weight)",
        "symbols": "RSI = 100 - 100 / (1 + G/L); G, L = Wilder averages of gains and losses over 14 closes",
        "source": "J. Welles Wilder Jr., New Concepts in Technical Trading Systems (1978)",
        "levels": {
            "new": "A score from 0 to 100 that compares how much the price rose on its up bars with how much it fell "
                   "on its down bars, over the last 14 bars. Near 50 the rises and falls were about the same size; "
                   "the higher it is, the bigger the rises were next to the falls.",
            "beginner": "The Relative Strength Index: the average gain on up bars against the average loss on down "
                        "bars over the last 14 bars, put on a scale from 0 to 100. Above 50, recent gains were "
                        "larger than recent losses; below 50, the reverse.",
            "intermediate": "Wilder's RSI over 14 bars: 100 minus 100 divided by one plus average gain over average "
                            "loss, with both averages smoothed so older bars fade out gradually. It measures how "
                            "strong recent moves were, up against down. Readings above 70 are often called "
                            "overbought and below 30 oversold; those words describe the size of recent moves, not "
                            "what comes next.",
            "advanced": "RSI(14) with Wilder's smoothing: the first averages are simple means of the first 14 gains "
                        "and losses, then each new bar updates them with a weight of 1/14. It is bounded at 0 and "
                        "100. In a strong trend it can stay above 70 or below 30 for weeks, and gaps between its "
                        "highs or lows and the price's are common and often end without a turn.",
            "expert": "Wilder's RSI, period 14, on closes: RS = SMMA14(gains) / SMMA14(losses), RSI = 100 - 100/(1 + "
                      "RS), seeded with simple means of the first 14 changes; the same as an exponential average with "
                      "alpha 1/14. Early values depend on that seed, so a short history reads slightly differently "
                      "from a long one.",
        },
        "limits": "It trails the price: it only reports moves that already happened. In a strong trend it can stay "
                  "above 70 or below 30 for a long time, so those levels are not turning points. It ignores volume "
                  "and says nothing about the company's business, and over few bars it is noisy.",
    },
    "macd": {
        "id": "macd", "name": "Moving Average Convergence Divergence", "short": "MACD 12, 26, 9",
        "settings": {"fast": 12, "slow": 26, "signal": 9}, "values": ["line", "signal", "hist"],
        "unit": "the stock's price units", "needs": 26,
        "formula": "the 12-bar exponential moving average of closes minus the 26-bar one (the MACD line); a 9-bar "
                   "exponential average of that line (the signal line); and the gap between the two (the histogram)",
        "symbols": "MACD = EMA12(close) - EMA26(close); signal = EMA9(MACD); histogram = MACD - signal",
        "source": "Gerald Appel, who devised MACD in the late 1970s",
        "levels": {
            "new": "Two lines that show whether the price's short-term average is above or below its longer-term "
                   "average, and whether the gap between them is growing or shrinking.",
            "beginner": "MACD subtracts the 26-bar average of closes from the 12-bar average, both weighted toward "
                        "recent bars. A 9-bar average of that difference is the signal line. Above zero, the "
                        "shorter average is above the longer one.",
            "intermediate": "The MACD line is the 12-bar exponential moving average of closes minus the 26-bar one, "
                            "in the stock's price units. The signal line is a 9-bar exponential average of the MACD "
                            "line, and the histogram is the gap between them. It describes momentum: whether the "
                            "shorter-term average is pulling away from the longer one or closing in on it.",
            "advanced": "MACD(12, 26, 9): EMA12 minus EMA26 of closes; signal = EMA9 of that line; histogram = line "
                        "minus signal. Because it is in price units its size grows with the share price, so values "
                        "cannot be compared across stocks or across a long price history. Crossings of the signal "
                        "line come late by construction.",
            "expert": "Appel's MACD on closes, each EMA seeded with a simple mean (EMA12 and EMA26, then a 9-period "
                      "EMA of the MACD line from its first value). Unbounded and in price units; dividing by price "
                      "(a percentage price oscillator) is needed to compare names or decades.",
        },
        "limits": "It trails the price, since it is built from moving averages. In sideways markets the lines cross "
                  "often without a lasting move. Its size depends on the share price, so it cannot be compared across "
                  "stocks, and it ignores volume and the company's business.",
    },
    "ma": {
        "id": "ma", "name": "Simple moving averages", "short": "MA 20, 50, 200",
        "settings": {"average": "simple", "periods": [20, 50, 200]}, "values": ["sma20", "sma50", "sma200"],
        "unit": "the stock's price units", "needs": 20,
        "formula": "the plain average of the last 20, 50 and 200 closes, worked out again at every bar",
        "symbols": "SMA(n) = (close_1 + ... + close_n) / n, for n = 20, 50, 200",
        "source": "The standard simple moving average",
        "levels": {
            "new": "Three lines showing the average closing price over the last 20, 50 and 200 bars. They smooth out "
                   "the bar-to-bar moves, so the general direction is easier to see.",
            "beginner": "Simple moving averages: each point is the plain average of the last 20, 50 or 200 closes. "
                        "The price above an average means it is higher than its average over that span.",
            "intermediate": "The simple average of the last 20, 50 and 200 closes, worked out again at every bar. "
                            "The 20-bar follows the price closely and the 200-bar describes the longer trend. Where "
                            "the price sits against each, and how the averages sit against each other, describe the "
                            "trend over those spans.",
            "advanced": "Arithmetic means of closes over 20, 50 and 200 bars, equally weighted, so a large move "
                        "leaving the window changes the average as much as one entering it. On daily bars 200 bars "
                        "is about 40 weeks of trading; on hourly bars it is a few weeks, so one setting describes "
                        "different spans at different bar sizes.",
            "expert": "SMA(n) = (1/n) times the sum of the last n closes, n = 20, 50, 200, undefined until n bars "
                      "exist. Its lag is (n - 1)/2 bars, and its equal weights make it respond to the bar leaving the "
                      "window as much as to the one entering.",
        },
        "limits": "They trail the price by design, and the longer the span the more they trail. A cross of the price "
                  "and an average, or of two averages, describes what already happened; in sideways markets crosses "
                  "come often and do not last. They say nothing about the business or why the price moved.",
    },
    "ema": {
        "id": "ema", "name": "Exponential moving averages", "short": "EMA 9, 21, 50",
        "settings": {"periods": [9, 21, 50]}, "values": ["ema9", "ema21", "ema50"],
        "unit": "the stock's price units", "needs": 9,
        "formula": "an average of the closes that gives the newest bars the most weight: each bar moves the average "
                   "toward its close by 2 / (n + 1), starting from the simple average of the first n closes",
        "symbols": "EMA_t = EMA_(t-1) + k (close_t - EMA_(t-1)), k = 2 / (n + 1), n = 9, 21, 50",
        "source": "The standard exponential moving average",
        "levels": {
            "new": "Three averages of the closing price, over about 9, 21 and 50 bars, that count the latest bars "
                   "most. They turn sooner than plain averages when the price changes direction.",
            "beginner": "Exponential moving averages: averages of the closes that give recent bars more weight, over "
                        "9, 21 and 50 bars. They follow the price more closely than simple averages of the same "
                        "length.",
            "intermediate": "Each bar moves the average a fixed share of the way toward the new close: 2/(n + 1), so "
                            "a fifth for the 9-bar, a little under a tenth for the 21-bar, under a twentieth for the "
                            "50-bar. Where the price sits against each, and how they sit against each other, describe "
                            "the trend over those spans, more quickly than simple averages do.",
            "advanced": "EMA with k = 2/(n + 1), n = 9, 21, 50, seeded with the simple mean of the first n closes. "
                        "Every past close keeps some weight, decaying geometrically, so a large old move fades out "
                        "rather than dropping out on one bar as it does from a simple average.",
            "expert": "EMA_t = k close_t + (1 - k) EMA_(t-1), k = 2/(n + 1), seeded at bar n with SMA(n). Its "
                      "centre of mass lags by (n - 1)/2 bars, the same as an SMA of the same n, but it reacts sooner "
                      "to new bars.",
        },
        "limits": "They still trail the price, only less than simple averages. Reacting sooner also means more "
                  "crossings that do not last, especially in sideways markets. They say nothing about the business "
                  "or why the price moved.",
    },
    "bb": {
        "id": "bb", "name": "Bollinger Bands", "short": "Bollinger 20, 2",
        "settings": {"period": 20, "deviations": 2}, "values": ["upper", "middle", "lower"],
        "unit": "the stock's price units", "needs": 20,
        "formula": "a 20-bar simple moving average of closes, with a band two standard deviations of the last 20 "
                   "closes above it and one two standard deviations below",
        "symbols": "middle = SMA20(close); upper, lower = middle +/- 2 sigma20 (population standard deviation)",
        "source": "John Bollinger, Bollinger on Bollinger Bands (2001)",
        "levels": {
            "new": "Two bands around a 20-bar average of the price. They spread apart when the price has been moving "
                   "a lot and come together when it has been calm, and most closes fall between them.",
            "beginner": "Bollinger Bands: a 20-bar simple average with a band two standard deviations above and below "
                        "it. How far apart the bands are shows how much the price has been varying lately.",
            "intermediate": "A 20-bar simple moving average with bands at plus and minus two standard deviations of "
                            "the last 20 closes. Where the close sits inside the bands describes how stretched it is "
                            "against its recent range; how far apart they are describes recent volatility.",
            "advanced": "SMA20 plus or minus 2 sigma, sigma the population standard deviation of the last 20 closes. "
                        "Closes outside the bands are not rare: returns have fatter tails than a normal distribution, "
                        "and in a strong trend closes can stay near one band for a long time.",
            "expert": "Middle = SMA(20) of closes; bands = middle +/- 2 sigma20, sigma dividing by n. %B = (close - "
                      "lower) / (upper - lower) places the close inside the bands; bandwidth = (upper - lower) / "
                      "middle measures their spread.",
        },
        "limits": "The bands describe recent volatility and nothing more: a close outside them is not a forecast "
                  "either way. In a strong trend closes can stay near one band for a long time. They use only "
                  "closing prices and say nothing about the business.",
    },
}
IDS = tuple(REGISTRY)

_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}(?:T\d{2}:\d{2})?$")
_SYMBOL = re.compile(r"^[A-Z0-9^][A-Z0-9.^=\-]{0,11}$")
_INTERVALS = ("1", "5", "15", "30", "60", "240", "daily", "weekly")


def settings_said(iid: str) -> str:
    """'period 14'; 'simple, periods 20, 50 and 200'; 'fast 12, slow 26, signal 9'."""
    out = []
    for k, v in REGISTRY[iid]["settings"].items():
        if isinstance(v, list):
            words = [str(x) for x in v]
            out.append("{} {}".format(k, words[0] if len(words) == 1 else "{} and {}".format(", ".join(words[:-1]), words[-1])))
        elif k == "average":
            out.append(str(v))
        else:
            out.append("{} {}".format(k.replace("_", " "), v))
    return ", ".join(out)


def definition(iid: str, level: str = DEFAULT_LEVEL) -> str:
    """What one indicator measures, at one knowledge level (an unknown level reads as the default)."""
    return REGISTRY[iid]["levels"][level if level in LEVELS else DEFAULT_LEVEL]


def public() -> Dict[str, Any]:
    """The registry as the client reads it (GET /api/indicator-registry)."""
    return {"version": VERSION, "levels": list(LEVELS), "default_level": DEFAULT_LEVEL, "price_source": PRICE_SOURCE,
            "indicators": {k: dict(v) for k, v in REGISTRY.items()}}


def _num(v: Any) -> Optional[float]:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def money(v: float) -> str:
    """Two decimals with thousands separators and a true minus, as the chart prints (static/v2/js/core/format.js num)."""
    v = 0.0 if abs(v) < 0.005 else v
    return "{:,.2f}".format(v).replace("-", "−")


def clean_reading(raw: Any) -> Optional[Dict[str, Any]]:
    """The reading the chart sent, checked: a known indicator, a ticker, a bar size, numbers or nothing for each of the
    indicator's values, the bar's date, and why there is no value if there is none. None when it is not a reading."""
    if not isinstance(raw, dict) or raw.get("id") not in REGISTRY:
        return None
    e = REGISTRY[raw["id"]]
    sym = str(raw.get("symbol") or "").upper()
    out: Dict[str, Any] = {"id": e["id"], "short": e["short"], "name": e["name"],
                           "symbol": sym if _SYMBOL.match(sym) else None,
                           "interval": raw.get("interval") if raw.get("interval") in _INTERVALS else None,
                           "values": {}, "close": _num(raw.get("close")),
                           "at": raw.get("at") if isinstance(raw.get("at"), str) and _DATE.match(raw["at"]) else None,
                           "forming": raw.get("forming") is True, "bars": None, "unavailable": None}
    vals = raw.get("values") if isinstance(raw.get("values"), dict) else {}
    for k in e["values"]:
        out["values"][k] = _num(vals.get(k))
    bars = _num(raw.get("bars"))
    out["bars"] = int(bars) if bars is not None and bars >= 0 else None
    # Why there is no value, said by Optic: the browser sends only which case it is
    why = raw.get("unavailable")
    if why == "no_bars" or out["values"][e["values"][0]] is None or out["at"] is None:
        if why == "no_bars" or out["bars"] in (None, 0):
            out["unavailable"] = "the chart's bars did not load, so Optic has no live value"
        else:
            out["unavailable"] = ("not enough data for a {} yet: it needs {} bars and the chart has {}".format(
                _what(e), e["needs"], out["bars"]))
    return out


def _what(e: Dict[str, Any]) -> str:
    return {"rsi": "14-bar RSI", "macd": "MACD line (26 bars)", "ma": "20-bar average", "ema": "9-bar average",
            "bb": "20-bar Bollinger Band"}[e["id"]]


def _pct(a: float, b: float) -> str:
    return "{:.1f}%".format(abs(a / b - 1) * 100)


def _against(close: float, avg: Optional[float], n: int, kind: str) -> str:
    if avg is None:
        return "not enough bars for the {}-bar {} yet".format(n, kind)
    if abs(close / avg - 1) < 0.0005:
        return "level with the {}-bar {} ({})".format(n, kind, money(avg))
    return "{} {} the {}-bar {} ({})".format(_pct(close, avg), "above" if close > avg else "below", n, kind, money(avg))


def describe(r: Dict[str, Any]) -> str:
    """What a reading describes, in words worked out from the reading alone. Descriptive only; '' with no value."""
    if not r or r.get("unavailable"):
        return ""
    v, c, sym = r["values"], r.get("close"), r.get("symbol") or "the stock"
    if r["id"] == "rsi":
        x = v["rsi"]
        if x >= 99.995:
            head = "An RSI of 100 means every bar in the 14-bar window closed higher, so there were no losses to set against the gains."
        elif x <= 0.005:
            head = "An RSI of 0 means every bar in the 14-bar window closed lower, so there were no gains to set against the losses."
        else:
            head = ("An RSI of {} means that over the last 14 bars, with Wilder's smoothing, the average gain on up "
                    "bars was {:.2f} times the average loss on down bars.").format(money(x), x / (100 - x))
        if x >= 70:
            band = (" That is above 70, the band often called overbought: a name for how large recent gains were next "
                    "to losses, not a forecast that the price will fall.")
        elif x <= 30:
            band = (" That is below 30, the band often called oversold: a name for how large recent losses were next "
                    "to gains, not a forecast that the price will rise.")
        elif 45 <= x <= 55:
            band = " That is close to 50, where the average gain and the average loss would be equal."
        else:
            band = " That is between 30 and 70."
        return head + band
    if r["id"] == "macd":
        line, sig, hist = v["line"], v["signal"], v["hist"]
        out = ("The MACD line is {}: the 12-bar exponential average of {}'s closes is {} {} the 26-bar one, in its "
               "price units.").format(money(line), sym, money(abs(line)), "above" if line >= 0 else "below")
        if sig is None or hist is None:
            return out + " The signal line needs 9 values of the MACD line first, so there is no signal line yet."
        return out + (" The signal line, a 9-bar average of the MACD line, is {}, so the histogram is {}: the MACD "
                      "line is {} its signal line.").format(money(sig), money(hist), "above" if hist >= 0 else "below")
    if r["id"] in ("ma", "ema"):
        if c is None:
            return ""
        kind = "average" if r["id"] == "ma" else "exponential average"
        ns = (20, 50, 200) if r["id"] == "ma" else (9, 21, 50)
        parts = [_against(c, v[k], n, kind) for k, n in zip(REGISTRY[r["id"]]["values"], ns)]
        return "The latest close, {}, is {}, {} and {}.".format(money(c), parts[0], parts[1], parts[2])
    if r["id"] == "bb":
        up, mid, lo = v["upper"], v["middle"], v["lower"]
        if c is None or mid in (None, 0) or up is None or lo is None or up <= lo:
            return ""
        width = "The bands span {:.1f}% of their 20-bar average ({}).".format((up - lo) / mid * 100, money(mid))
        if c > up:
            where = "The latest close, {}, is above the upper band ({}) by {}.".format(money(c), money(up), money(c - up))
        elif c < lo:
            where = "The latest close, {}, is below the lower band ({}) by {}.".format(money(c), money(lo), money(lo - c))
        else:
            where = ("The latest close, {}, sits {:.0f}% of the way from the lower band ({}) to the upper band "
                     "({}).").format(money(c), (c - lo) / (up - lo) * 100, money(lo), money(up))
        return where + " " + width
    return ""


def values_said(r: Dict[str, Any]) -> str:
    """The reading's values as the chart prints them: 'RSI 58.21', 'MACD 2.31, signal 1.85, histogram 0.46'."""
    if not r or r.get("unavailable"):
        return ""
    v = r["values"]
    names = {"rsi": [("rsi", "RSI")], "macd": [("line", "MACD"), ("signal", "signal"), ("hist", "histogram")],
             "ma": [("sma20", "SMA 20"), ("sma50", "SMA 50"), ("sma200", "SMA 200")],
             "ema": [("ema9", "EMA 9"), ("ema21", "EMA 21"), ("ema50", "EMA 50")],
             "bb": [("upper", "upper"), ("middle", "middle"), ("lower", "lower")]}[r["id"]]
    return ", ".join("{} {}".format(n, money(v[k]) if v[k] is not None else "not enough bars") for k, n in names)


def header_lines(r: Dict[str, Any], level: str = DEFAULT_LEVEL, timeframe: Optional[str] = None) -> List[str]:
    """The CONTEXT header's lines for an Explain press: the reading as the chart computed it, Optic's description of
    it, the definition at the reader's level and the limits, and the fixed shape of the answer."""
    e = REGISTRY[r["id"]]
    on = "{}'s {}chart".format(r["symbol"], "{} ".format(timeframe) if timeframe else "") if r.get("symbol") else "the chart"
    lines = ["The reader pressed Explain on {} ({}; {}) on {}.".format(e["short"], e["name"], settings_said(r["id"]), on)]
    if r.get("unavailable"):
        lines.append("Optic has no live value for it: {}. Give the general explanation only, and begin The current "
                     "reading with \"Live value unavailable: {}.\"".format(r["unavailable"], r["unavailable"]))
    else:
        bar = "{}{}".format(r["at"], ", the latest bar, still forming, so the value can change until it closes"
                            if r.get("forming") else ", the latest bar")
        lines.append("Optic's chart computed it on its own bars: {} on {}.".format(values_said(r), bar))
        said = describe(r)
        if said:
            lines.append("What that reading describes, worked out by Optic: " + said)
    lines.append("Optic's definition at the reader's level: {} Formula: {}. Its limits: {}".format(
        definition(r["id"], level), e["formula"], e["limits"]))
    lines.append("Answer in four short parts with these headings, in this order: **What it measures**, **The current "
                 "reading**, **Limitations**, **Sources**. Keep to the reader's level and be concise. In The current "
                 "reading, quote Optic's values and their date exactly as given and say what they describe; never "
                 "compute, round differently or supply another value. In Sources, name the price data ({}) and the "
                 "definition's source ({}). Describe, never advise: no buy, sell, hold, enter, exit, trim, add, "
                 "target or stop, no \"consider\" with an action, and if you use \"overbought\" or \"oversold\", say "
                 "it names a reading above 70 or below 30 and predicts nothing on its own.".format(PRICE_SOURCE,
                                                                                                   e["source"]))
    return lines


def used(r: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """What the panel shows above the answer: the indicator, the values as the chart prints them and the bar's date,
    or why there is no value; with the two sources."""
    if not r:
        return None
    e = REGISTRY[r["id"]]
    return {"id": e["id"], "short": e["short"], "name": e["name"], "symbol": r.get("symbol"),
            "interval": r.get("interval"), "values": values_said(r), "at": r.get("at"), "forming": bool(r.get("forming")),
            "unavailable": r.get("unavailable"), "describes": describe(r), "price_source": PRICE_SOURCE,
            "definition_source": e["source"]}
