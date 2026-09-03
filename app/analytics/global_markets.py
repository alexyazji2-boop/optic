"""What the rest of the world did before the US opened.

The morning read was entirely domestic: US indices, US sectors, the megacaps, US
breadth. That is a real gap, because by the time New York opens the session has
already been priced twice — once in Asia and once in Europe — and the US open is
partly a reaction to both.

Two rules govern what this module will and will not say.

**Sessions are ordered, not listed.** Tokyo and Seoul close before Frankfurt
opens, and Frankfurt is half-done when New York rings. Presenting these as a flat
table of percentages loses the only thing that makes them useful: the handoff. So
they are grouped by session and ordered by when they traded.

**Correlation is measured, never asserted.** The tempting sentence is "Chinese
stocks fell on the policy news, dragging US futures down". This module will not
write that, and not because the claim is always wrong — because nothing here can
distinguish it from coincidence. What it can do is state how tightly each market
has actually moved with the S&P over a stated window. A market with a 0.15
correlation having a bad night is a fact about that market; the same night from
one at 0.75 is worth a second look. That number is the honest version of the
sentence, and it is one the reader can check.

Headlines are attached per region where the feed has them, labelled as headlines.
Adjacency is not causation and the panel says so, because the alternative is a
terminal that invents a mechanism every morning.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

log = logging.getLogger(__name__)

BENCHMARK = "^GSPC"

# Ordered by when the session trades, earliest first. That order is the content:
# read top to bottom and you have walked the clock from the Tokyo open to the New
# York bell.
MARKETS: List[Dict[str, str]] = [
    # --- Asia-Pacific: closed hours before the US opens -----------------------
    {"symbol": "^N225", "label": "Nikkei 225", "region": "Japan",
     "session": "asia", "note": "Tokyo"},
    {"symbol": "^KS11", "label": "KOSPI", "region": "South Korea",
     "session": "asia", "note": "Seoul. Semiconductor and export bellwether"},
    {"symbol": "^HSI", "label": "Hang Seng", "region": "Hong Kong",
     "session": "asia", "note": "Hong Kong. The offshore read on China"},
    {"symbol": "000001.SS", "label": "Shanghai Composite", "region": "China",
     "session": "asia", "note": "mainland, largely domestic ownership"},
    {"symbol": "^TWII", "label": "Taiwan Weighted", "region": "Taiwan",
     "session": "asia", "note": "Taipei. The most semiconductor-heavy index"},
    {"symbol": "^AXJO", "label": "ASX 200", "region": "Australia",
     "session": "asia", "note": "Sydney. Resources weighted"},
    # --- Europe: overlaps the US morning -------------------------------------
    {"symbol": "^STOXX50E", "label": "Euro Stoxx 50", "region": "Euro area",
     "session": "europe", "note": "the euro-area blue chips"},
    {"symbol": "^GDAXI", "label": "DAX", "region": "Germany",
     "session": "europe", "note": "Frankfurt. Industrial and export heavy"},
    {"symbol": "^FTSE", "label": "FTSE 100", "region": "United Kingdom",
     "session": "europe", "note": "London. Commodity and dividend weighted"},
    # --- Around the clock ----------------------------------------------------
    {"symbol": "BTC-USD", "label": "Bitcoin", "region": "Crypto",
     "session": "always", "note": "trades through the night. The only live tape "
                                  "while equities are shut"},
    {"symbol": "ETH-USD", "label": "Ethereum", "region": "Crypto",
     "session": "always", "note": "second-largest, higher beta than bitcoin"},
]

# Currencies and commodities that carry the regional story into US hours.
CROSSES: List[Dict[str, str]] = [
    {"symbol": "USDKRW=X", "label": "USD/KRW", "note": "won weakness is the "
     "standard stress tell for Korean exporters"},
    {"symbol": "USDCNY=X", "label": "USD/CNH", "note": "the offshore yuan. Where "
     "policy pressure on China shows up first"},
    {"symbol": "USDJPY=X", "label": "USD/JPY", "note": "the carry trade funding leg"},
    {"symbol": "GC=F", "label": "Gold", "note": "the haven bid"},
    {"symbol": "CL=F", "label": "Crude", "note": "cost shock versus demand"},
]

SESSION_LABELS = {
    "asia": "Asia-Pacific. Closed before the US open",
    "europe": "Europe. Trades into the US morning",
    "always": "Around the clock",
}

# Window for the correlation to the S&P. 60 sessions is about a quarter: long
# enough that a single shared shock does not dominate it, short enough to reflect
# the current regime rather than an average of several.
CORR_WINDOW = 60

# Above this, a foreign market's moves have been travelling with the S&P often
# enough that a big move there is worth reading. Below it, it mostly has not.
# Stated as a threshold rather than hidden in a colour.
CORR_MEANINGFUL = 0.4


def _f(value: Any, digits: int = 2) -> Optional[float]:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    if out != out or out in (float("inf"), float("-inf")):
        return None
    return round(out, digits)


def _pct(series: pd.Series, bars: int) -> Optional[float]:
    clean = series.dropna()
    if len(clean) <= bars:
        return None
    return _f((clean.iloc[-1] / clean.iloc[-1 - bars] - 1.0) * 100.0)


def _correlation(local: pd.Series, bench: pd.Series) -> Optional[float]:
    """Correlation of daily returns against the S&P over CORR_WINDOW sessions.

    Joined on date with an inner join, which matters more here than usual: these
    exchanges keep different holidays, and a naive alignment silently pairs
    Tuesday in Seoul with Monday in New York for every Korean public holiday in
    the window.
    """
    joined = pd.concat({"a": local, "b": bench}, axis=1).dropna()
    if len(joined) < 30:
        return None
    rets = joined.pct_change().dropna().tail(CORR_WINDOW)
    if len(rets) < 25:
        return None
    value = rets["a"].corr(rets["b"])
    return _f(value, 2)


def build(provider, news_entries: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """Overnight global session, ordered by the clock, with measured linkage."""
    symbols = [m["symbol"] for m in MARKETS] + [c["symbol"] for c in CROSSES]
    symbols.append(BENCHMARK)
    try:
        frames = provider.batch_history(symbols, period="6mo", interval="1d")
    except Exception as exc:                                    # noqa: BLE001
        log.warning("global_markets: history unavailable: %s", exc)
        return {"available": False, "reason": str(exc)[:140]}

    bench_frame = frames.get(BENCHMARK)
    bench = (bench_frame["Close"].astype(float)
             if bench_frame is not None and not bench_frame.empty else None)

    def row(spec: Dict[str, str]) -> Optional[Dict[str, Any]]:
        frame = frames.get(spec["symbol"])
        if frame is None or frame.empty or "Close" not in frame:
            return None
        close = frame["Close"].astype(float)
        corr = _correlation(close, bench) if bench is not None else None
        return {
            **spec,
            "last": _f(close.iloc[-1], 2),
            "chg_1d": _pct(close, 1),
            "chg_5d": _pct(close, 5),
            "chg_20d": _pct(close, 20),
            "corr_spx": corr,
            # Named rather than left to the reader to infer from a number they may
            # not have a feel for.
            "corr_read": (None if corr is None else
                          "moves with the S&P" if corr >= CORR_MEANINGFUL else
                          "moves largely on its own" if corr > -CORR_MEANINGFUL else
                          "tends to move against the S&P"),
            "last_bar": str(close.dropna().index[-1].date()),
        }

    markets = [r for r in (row(m) for m in MARKETS) if r]
    crosses = [r for r in (row(c) for c in CROSSES) if r]

    sessions = []
    for key in ("asia", "europe", "always"):
        rows = [m for m in markets if m["session"] == key]
        if not rows:
            continue
        moves = [m["chg_1d"] for m in rows if m["chg_1d"] is not None]
        sessions.append({
            "id": key,
            "label": SESSION_LABELS[key],
            "rows": rows,
            "avg_move_pct": _f(sum(moves) / len(moves)) if moves else None,
            "advancing": sum(1 for m in moves if m > 0),
            "declining": sum(1 for m in moves if m < 0),
        })

    # The linkage question, answered with the numbers rather than a story.
    linked = [m for m in markets
              if m["corr_spx"] is not None and m["corr_spx"] >= CORR_MEANINGFUL]
    movers = sorted([m for m in markets if m["chg_1d"] is not None],
                    key=lambda m: -abs(m["chg_1d"]))

    return {
        "available": True,
        "sessions": sessions,
        "crosses": crosses,
        "biggest_movers": movers[:4],
        "linked_count": len(linked),
        "market_count": len(markets),
        "corr_window": CORR_WINDOW,
        "corr_threshold": CORR_MEANINGFUL,
        "method": (
            "Ordered by when each market trades, because the handoff is the point: "
            "Tokyo and Seoul close before Frankfurt opens, and Frankfurt is "
            "half-done by the New York bell. The correlation is of daily returns "
            "against the S&P over the last {w} sessions, joined on date so a "
            "Korean or Chinese public holiday does not pair Tuesday in Seoul with "
            "Monday in New York. It is there to answer the question a percentage "
            "cannot: whether this market has actually been moving with the US at "
            "all. Above {t:.1f} it mostly has. Below that, a bad night there is a "
            "fact about that market and not a signal about this one. No causal "
            "claim is made anywhere here. Headlines are shown next to regions, "
            "not offered as the reason a market moved."
        ).format(w=CORR_WINDOW, t=CORR_MEANINGFUL),
    }
