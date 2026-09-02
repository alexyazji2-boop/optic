"""Stock maps: a screen laid out as a picture rather than a table.

Two shapes, and the choice between them is the whole design:

* **Tile map** (a treemap) sizes each tile by one measure and colours it by
  another. Size answers "how much of this does the market care about" and colour
  answers "what is it doing", so a big red tile is a large thing going down —
  which is a sentence a table takes four columns and a scan to say.
* **Bubble chart** plots one measure against another with size as a third. That
  is the right shape when the *relationship* is the question — cheap versus
  growing, volatile versus trending — because a treemap cannot show a
  correlation and a scatter can.

**On the templates.** Each is a preset combination of universe, size, colour and
axes. They exist because "P/E outliers in Energy" is a question and "size by
market cap, colour by trailing P/E, filter to XLE" is a configuration, and most
people want to ask the question.

**What this refuses to do.** Every template names its measures and every tile
reports the raw values, because a treemap is unusually good at making a
comparison look authoritative. A tile is only as good as the measure under it,
and two of the templates here use ratios that are meaningless for loss-making
companies — those rows are dropped rather than drawn at an arbitrary position,
and the count of what was dropped is reported.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Sequence

import numpy as np

from .sectors import SECTORS, THEMES

# Measures a map can size or colour by. `higher_is_better` decides which end of
# the diverging colour ramp a value lands on; None means the measure has no
# natural direction and gets a sequential ramp instead.
MEASURES: Dict[str, Dict[str, Any]] = {
    "market_cap": {"label": "Market cap", "unit": "$", "higher_is_better": None,
                   "note": "How much the company is worth. Size only — it says "
                           "nothing about whether it is a good business."},
    "dollar_volume": {"label": "Dollar volume", "unit": "$", "higher_is_better": None,
                      "note": "Price times average daily volume. Used to size ETF "
                              "maps because an ETF has no market cap — what it "
                              "measures is how much money moves through the thing "
                              "each day, which for sizing a map is arguably the "
                              "better question anyway."},
    "chg_1d": {"label": "1-day change", "unit": "%", "higher_is_better": True,
               "note": "Today's move."},
    "chg_20d": {"label": "20-day change", "unit": "%", "higher_is_better": True,
                "note": "Roughly a month of price movement."},
    "chg_60d": {"label": "60-day change", "unit": "%", "higher_is_better": True,
                "note": "A quarter of price movement."},
    "trailing_pe": {"label": "P/E (trailing)", "unit": "x", "higher_is_better": False,
                    "note": "Price divided by the last twelve months of earnings. "
                            "Undefined for a loss-making company, so those are "
                            "dropped rather than drawn at zero."},
    "forward_pe": {"label": "P/E (forward)", "unit": "x", "higher_is_better": False,
                   "note": "Price against expected earnings. Carries analyst "
                           "forecast error as well as market opinion."},
    "price_to_book": {"label": "Price / book", "unit": "x", "higher_is_better": False,
                      "note": "Price against balance-sheet equity. Meaningful for "
                              "banks and asset-heavy businesses, close to "
                              "meaningless for software."},
    "revenue_growth": {"label": "Revenue growth", "unit": "%", "higher_is_better": True,
                       "note": "Year-on-year top-line growth."},
    "profit_margin": {"label": "Profit margin", "unit": "%", "higher_is_better": True,
                      "note": "Net income as a share of revenue."},
    "rsi": {"label": "RSI (14)", "unit": "", "higher_is_better": None,
            "note": "Momentum oscillator, 0-100. No natural good end — high is "
                    "strong and also stretched."},
    "atr_pct": {"label": "Daily range", "unit": "%", "higher_is_better": None,
                "note": "Average true range as a percentage of price. How much "
                        "this name moves on an ordinary day."},
    "vs_sma200": {"label": "vs 200-day", "unit": "%", "higher_is_better": True,
                  "note": "Distance from the long moving average — the crude "
                          "definition of a trend."},
    "pct_from_52w_high": {"label": "From 52-week high", "unit": "%",
                          "higher_is_better": True,
                          "note": "How far below the year's high it is trading."},
    "dividend_yield": {"label": "Dividend yield", "unit": "%", "higher_is_better": True,
                       "note": "Trailing dividend against price. A high yield is "
                               "often a falling price rather than a generous board."},
    "beta": {"label": "Beta", "unit": "", "higher_is_better": None,
             "note": "Sensitivity to the market. Above 1 moves more than the "
                     "index, below 1 less."},
}

TEMPLATES: List[Dict[str, Any]] = [
    {
        "id": "sector-month", "shape": "tile", "label": "Sector performance",
        "universe": "sectors",
        "size": "dollar_volume", "color": "chg_20d",
        "question": "Which parts of the market moved this month, weighted by how "
                    "much money trades through them each day?",
    },
    {
        "id": "sector-today", "shape": "tile", "label": "Sectors today",
        "universe": "sectors",
        "size": "dollar_volume", "color": "chg_1d",
        "question": "Where did today's move actually come from?",
    },
    {
        "id": "theme-month", "shape": "tile", "label": "Themes and industries",
        "universe": "themes",
        "size": "dollar_volume", "color": "chg_20d",
        "question": "Narrower than sectors — semis, biotech, homebuilders, miners.",
    },
    {
        "id": "pe-vs-growth", "shape": "bubble", "label": "Valuation vs growth",
        "universe": "megacap",
        "x": "revenue_growth", "y": "forward_pe", "size": "market_cap",
        "color": "chg_60d",
        "question": "What are you paying for growth, sector by sector? Cheap and "
                    "growing sits bottom-right.",
    },
    {
        "id": "trend-vs-vol", "shape": "bubble", "label": "Trend vs volatility",
        "universe": "sectors",
        "x": "atr_pct", "y": "vs_sma200", "size": "dollar_volume", "color": "rsi",
        "question": "Which sectors are trending without much noise? Top-left is "
                    "a strong trend in a quiet name.",
    },
    {
        "id": "drawdown", "shape": "tile", "label": "Distance from the highs",
        "universe": "sectors",
        "size": "dollar_volume", "color": "pct_from_52w_high",
        "question": "What has been left behind, and is it big enough to matter?",
    },
    {
        "id": "yield-map", "shape": "tile", "label": "Dividend yield",
        "universe": "sectors",
        "size": "dollar_volume", "color": "dividend_yield",
        "question": "Where is the income, and what price has it come at?",
    },
    {
        "id": "beta-map", "shape": "bubble", "label": "Beta vs trend",
        "universe": "megacap",
        "x": "beta", "y": "chg_60d", "size": "market_cap", "color": "vs_sma200",
        "question": "Is the quarter's move explained by market sensitivity, or is "
                    "something outperforming its own beta?",
    },
]

TEMPLATE_BY_ID = {t["id"]: t for t in TEMPLATES}
# Individual companies, for the templates whose measures only exist for real
# businesses. An ETF has no P/E, no revenue growth and no beta in the data feed,
# and drawing those templates over ETFs dropped every row — which is the correct
# behaviour and a useless map.
#
# Deliberately the largest names rather than a screen: the point of these two
# templates is the shape of the relationship, and a universe that changes
# underneath you makes two viewings incomparable.
MEGACAP: List[Dict[str, str]] = [
    {"symbol": "AAPL", "name": "Apple"},
    {"symbol": "MSFT", "name": "Microsoft"},
    {"symbol": "NVDA", "name": "Nvidia"},
    {"symbol": "AMZN", "name": "Amazon"},
    {"symbol": "GOOGL", "name": "Alphabet"},
    {"symbol": "META", "name": "Meta"},
    {"symbol": "AVGO", "name": "Broadcom"},
    {"symbol": "TSLA", "name": "Tesla"},
    {"symbol": "BRK-B", "name": "Berkshire Hathaway"},
    {"symbol": "JPM", "name": "JPMorgan"},
    {"symbol": "LLY", "name": "Eli Lilly"},
    {"symbol": "V", "name": "Visa"},
    {"symbol": "XOM", "name": "Exxon Mobil"},
    {"symbol": "UNH", "name": "UnitedHealth"},
    {"symbol": "COST", "name": "Costco"},
    {"symbol": "WMT", "name": "Walmart"},
    {"symbol": "PG", "name": "Procter & Gamble"},
    {"symbol": "JNJ", "name": "Johnson & Johnson"},
    {"symbol": "HD", "name": "Home Depot"},
    {"symbol": "KO", "name": "Coca-Cola"},
]

UNIVERSES = {
    "sectors": {"label": "The eleven S&P sectors", "members": SECTORS},
    "themes": {"label": "Themes and sub-industries", "members": THEMES},
    "megacap": {"label": "The twenty largest US companies", "members": MEGACAP},
}


def _f(v: Any, digits: int = 2) -> Optional[float]:
    try:
        out = float(v)
    except (TypeError, ValueError):
        return None
    return None if not np.isfinite(out) else round(out, digits)


def _needed(template: Dict[str, Any]) -> List[str]:
    return [template[k] for k in ("size", "color", "x", "y") if template.get(k)]


def _squarify(items: Sequence[Dict[str, Any]], x: float, y: float,
              w: float, h: float) -> List[Dict[str, Any]]:
    """Treemap layout, squarified.

    Plain slice-and-dice produces long thin slivers that are impossible to
    compare by area, which defeats the point of sizing by a measure. This is the
    standard squarified algorithm: lay tiles into rows along the shorter side and
    close a row when adding another tile would make the aspect ratios worse.
    """
    out: List[Dict[str, Any]] = []
    todo = [dict(it) for it in items if (it.get("_size") or 0) > 0]
    if not todo:
        return out
    total = sum(it["_size"] for it in todo)
    if total <= 0:
        return out
    # Scale so areas sum to the rectangle.
    scale = (w * h) / total
    for it in todo:
        it["_area"] = it["_size"] * scale

    def worst(row: List[Dict[str, Any]], length: float) -> float:
        if not row or length <= 0:
            return float("inf")
        area = sum(r["_area"] for r in row)
        if area <= 0:
            return float("inf")
        side = area / length
        ratios = [max(side / (r["_area"] / side), (r["_area"] / side) / side)
                  for r in row if r["_area"] > 0]
        return max(ratios) if ratios else float("inf")

    cx, cy, cw, ch = x, y, w, h
    todo.sort(key=lambda r: -r["_area"])
    i = 0
    while i < len(todo):
        row: List[Dict[str, Any]] = []
        vertical = cw >= ch
        length = ch if vertical else cw
        while i < len(todo):
            trial = row + [todo[i]]
            if row and worst(trial, length) > worst(row, length):
                break
            row.append(todo[i])
            i += 1
        area = sum(r["_area"] for r in row)
        thickness = area / length if length else 0
        pos = cy if vertical else cx
        for r in row:
            extent = (r["_area"] / thickness) if thickness else 0
            if vertical:
                out.append({**r, "x": cx, "y": pos, "w": thickness, "h": extent})
                pos += extent
            else:
                out.append({**r, "x": pos, "y": cy, "w": extent, "h": thickness})
                pos += extent
        if vertical:
            cx += thickness
            cw -= thickness
        else:
            cy += thickness
            ch -= thickness
    return out


def build(provider, template_id: str = "sector-month") -> Dict[str, Any]:
    """One map: the layout, the values behind it, and what was dropped."""
    tpl = TEMPLATE_BY_ID.get(template_id) or TEMPLATES[0]
    universe = UNIVERSES.get(tpl["universe"]) or UNIVERSES["sectors"]
    members = universe["members"]
    symbols = [m["symbol"] for m in members]

    frames = provider.batch_history(symbols, period="1y", interval="1d")
    from .series_stats import snapshot

    needed = _needed(tpl)
    rows: List[Dict[str, Any]] = []
    dropped: List[Dict[str, str]] = []

    for meta in members:
        sym = meta["symbol"]
        df = frames.get(sym)
        snap = snapshot(df) if df is not None and not df.empty else {}
        quote = provider.quote(sym) or {}
        vals: Dict[str, Optional[float]] = {}
        # Derived, not reported. price * average volume.
        px = quote.get("price") or snap.get("last")
        avg = quote.get("avg_volume")
        if px is not None and avg is not None:
            quote = {**quote, "dollar_volume": float(px) * float(avg)}
        for key in MEASURES:
            raw = quote.get(key)
            if raw is None:
                raw = snap.get(key)
            # yfinance reports growth and margins as fractions; the measure is
            # declared in percent, so convert rather than showing 0.34%.
            if key in ("revenue_growth", "profit_margin", "dividend_yield") \
                    and raw is not None and abs(float(raw)) < 3:
                raw = float(raw) * 100
            vals[key] = _f(raw)

        missing = [k for k in needed if vals.get(k) is None]
        if missing:
            # Dropped, not drawn at zero. A P/E of nothing plotted at the origin
            # reads as "very cheap", which is the opposite of the truth for a
            # company that has no earnings.
            dropped.append({"symbol": sym, "name": meta.get("name", sym),
                            "missing": ", ".join(MEASURES[k]["label"] for k in missing)})
            continue

        rows.append({
            "symbol": sym,
            "name": meta.get("name", sym),
            "values": vals,
            "last": _f(snap.get("last")),
        })

    layout: List[Dict[str, Any]] = []
    if tpl["shape"] == "tile" and rows:
        sized = [{**r, "_size": abs(r["values"].get(tpl["size"]) or 0)} for r in rows]
        layout = _squarify(sized, 0.0, 0.0, 100.0, 100.0)
        for tile in layout:
            tile.pop("_size", None)
            tile.pop("_area", None)

    colour_key = tpl.get("color")
    colour_vals = [r["values"][colour_key] for r in rows
                   if colour_key and r["values"].get(colour_key) is not None]

    return {
        "template": tpl,
        "templates": [{"id": t["id"], "label": t["label"], "shape": t["shape"],
                       "question": t["question"], "universe": t["universe"]}
                      for t in TEMPLATES],
        "measures": {k: MEASURES[k] for k in set(needed)},
        "universe_label": universe["label"],
        "rows": rows,
        "layout": layout,
        "dropped": dropped,
        "colour_domain": {
            "min": _f(min(colour_vals)) if colour_vals else None,
            "max": _f(max(colour_vals)) if colour_vals else None,
            "higher_is_better": MEASURES.get(colour_key, {}).get("higher_is_better")
            if colour_key else None,
        },
    }
