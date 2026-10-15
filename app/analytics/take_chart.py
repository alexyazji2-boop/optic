"""The chart behind a take on a stock: levels and trend lines for the timeframe asked (2026-10-15).

The owner's reference for how Milo should answer "Thoughts on HOOD in the near/long term?" is a trader's
reply with a chart: daily candles over a couple of years, the long rising trend line from the major low,
and the near-term supports the text names. This builds that chart's numbers once, on the server, for a
span. The same function gives Milo the levels it quotes (CONTEXT `chart_levels`, main._with_take_levels)
and the inline chart the lines it draws (GET /api/take-chart), so the words and the picture cannot
disagree.

The rules, stated so they can be argued with:

* The span follows the timeframe asked: 3m for a day trade, 6m for days to weeks, 2y for owning it, or
  when the question asks for both; 1y when it names none.
* Levels are support_resistance_levels (touches, rejection, volume, recency; analytics/technicals.py)
  over the last year of the span at most: on a two-year chart the levels a reader acts on are the
  recent ones, and the long view is carried by the trend line. A level within half a day's typical
  range (ATR) of the close is where price is sitting, said as such; beyond that, the nearest two below
  are the supports and the nearest two above the resistances.
* Trend lines are trendlines.build over the whole span: three touches, never closed through between
  them, within reach of the price (analytics/trendlines.py). The longest-running ones are the chart's
  "trend" in the reference's sense.

Nothing here predicts. A level is where price turned before; a trend line is a line the market has
respected; whether either holds is the question the answer is about.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import pandas as pd

from . import trendlines as trendlines_mod
from .technicals import atr, support_resistance_levels

SPANS = {"3m": 63, "6m": 126, "1y": 252, "2y": 504, "5y": 1260}
LEVEL_LOOKBACK_MAX = 252
# Words for each span, said under the chart and in CONTEXT.
SPAN_WORDS = {"3m": "3 months", "6m": "6 months", "1y": "1 year", "2y": "2 years", "5y": "5 years"}


def span_for(horizon: Optional[str], question: str = "") -> str:
    """The chart span for a question: its timeframe, or both near and long."""
    import re
    q = question or ""
    # The same wording research/modes.py routes to both assessments: "near/long term", "short and long term".
    both = re.search(r"\b(near|short)(?:[- ]?term)?\b.{0,40}\blong[- ]?term\b|"
                     r"\blong[- ]?term\b.{0,40}\b(near|short)[- ]?term\b|"
                     r"\b(?:next (?:few|couple of) (?:weeks|days)|swing)\b.{0,60}\b(?:for years|long[- ]?term|long run)\b",
                     q, re.I)
    if both:
        return "2y"
    return {"day": "3m", "swing": "6m", "long": "2y"}.get(horizon or "", "1y")


def _level(lv: Dict[str, Any]) -> Dict[str, Any]:
    return {"price": lv.get("price"), "touches": lv.get("touches"), "strength": lv.get("strength"),
            "distance_pct": lv.get("distance_pct"), "last_touch_bars_ago": lv.get("last_touch_bars_ago")}


def build(df: Optional[pd.DataFrame], span: str = "1y") -> Dict[str, Any]:
    """Levels and trend lines over one span of daily bars. Bars ride along for the chart."""
    if span not in SPANS:
        span = "1y"
    if df is None or len(df) == 0 or "Close" not in df:
        return {"available": False, "span": span, "reason": "No daily history."}
    window = df.dropna(subset=["Close"]).tail(SPANS[span])
    if len(window) < 40:
        return {"available": False, "span": span, "reason": "Too little history for this span."}
    close = float(window["Close"].iloc[-1])
    lookback = min(len(window), LEVEL_LOOKBACK_MAX)
    levels = support_resistance_levels(window, close, lookback=lookback, max_levels=12)
    a = atr(window, 14).dropna()
    near = float(a.iloc[-1]) * 0.5 if len(a) else close * 0.01
    at_price = sorted((lv for lv in levels if abs((lv.get("price") or 0) - close) <= near),
                      key=lambda lv: -(lv.get("strength") or 0))[:1]
    supports = sorted((lv for lv in levels if (lv.get("price") or 0) < close - near),
                      key=lambda lv: -(lv.get("price") or 0))[:2]
    resistances = sorted((lv for lv in levels if (lv.get("price") or 0) > close + near),
                         key=lambda lv: lv.get("price") or 0)[:2]
    tl = trendlines_mod.build(window)
    dates = [str(i.date()) for i in window.index]
    lines: List[Dict[str, Any]] = []
    # Unbroken first, then the longest-running: the line the market has respected longest is the trend.
    for ln in sorted(tl.get("lines") or [], key=lambda x: (bool(x.get("broken")), -(x.get("span_bars") or 0))):
        si = ln.get("start_index")
        lines.append({"kind": ln.get("kind"), "direction": ln.get("direction"), "touches": ln.get("touches"),
                      "start_date": dates[si] if isinstance(si, int) and 0 <= si < len(dates) else None,
                      "start_index": si, "start_price": ln.get("start_price"),
                      "price_now": ln.get("price_now"), "broken": ln.get("broken"),
                      "distance_atr": ln.get("distance_atr")})
    return {
        "available": True,
        "span": span,
        "span_words": SPAN_WORDS[span],
        "bars": len(window),
        "as_of": dates[-1],
        "close": round(close, 2),
        "atr": round(near * 2, 2),
        "at_price": [_level(lv) for lv in at_price],
        "supports": [_level(lv) for lv in supports],
        "resistances": [_level(lv) for lv in resistances],
        "trend_lines": lines[:3],
        # What the chart draws: the longest unbroken line each side, so two lines at most.
        "drawn": [ln for kind in ("support", "resistance")
                  for ln in [next((x for x in lines if x["kind"] == kind and not x["broken"]), None)] if ln],
        "method": ("Daily bars over {}. Supports and resistances: price shelves where swings clustered over the "
                   "last {} sessions, scored on touches, rejection, volume and recency; the nearest two each side "
                   "of the close. Trend lines: three or more swing points on one straight line, never closed "
                   "through between them. Places price turned before, not forecasts.").format(SPAN_WORDS[span],
                                                                                            lookback),
        "_window": window,
    }


def for_context(out: Dict[str, Any], ticker: str) -> Dict[str, Any]:
    """What Milo is sent: the levels and lines without the bars, and the chart tag that draws them."""
    if not out.get("available"):
        return {"available": False, "span": out.get("span"), "reason": out.get("reason")}
    body = {k: v for k, v in out.items() if not k.startswith("_")}
    # Only the lines the chart draws, so a line Milo names is a line the reader can see.
    body.pop("trend_lines")
    body["trend_lines"] = [{k: v for k, v in ln.items() if k != "start_index"} for ln in body.pop("drawn")]
    body["chart_tag"] = "[[chart {} {}]]".format(ticker, out["span"])
    return body
