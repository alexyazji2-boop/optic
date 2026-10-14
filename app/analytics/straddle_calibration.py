"""How the at-the-money straddle has priced this stock's moves, measured.

The Options tab says what the straddle is priced for ("a move of about
+/-4.2% by Nov 13"). Whether that has been a fair price for this stock is a
question the chain cannot answer; its history can. From DoltHub's
`option_chain` (each Monday from October 2024): on each Monday, the first expiry
21 to 50 days out and the strike nearest the close; the straddle's mid against
the move the stock actually made to that expiry
(`docs/research/straddle-calibration-2026-10-14.md`, built by
`docs/research/straddle_calibration.py` into app/data/straddle_calibration.json).

**Reading it.** An at-the-money straddle costs about the average absolute
move (under the model, E|S_T - K|). So a fair price shows a mean ratio of
realised to implied near 1, and the realised move exceeding the straddle a
little under half the time, not half: for normal moves the move beats its own
mean about 42% of the time (P(|Z| > 0.798)). A mean ratio well under 1 says
options on this stock were dearer than the moves that followed (the variance
risk premium, strongest in index options); over 1, cheaper.

Derived from DoltHub's CC BY-SA 4.0 data, so shown only where OPTIC_DOLTHUB is
on, with the attribution.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional

PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "straddle_calibration.json")
MIN_SAMPLES = 40
FAIR_EXCEED_PCT = 42.5
_cache: Dict[str, Any] = {}


def _load() -> Dict[str, Any]:
    if "data" not in _cache:
        try:
            with open(PATH) as f:
                _cache["data"] = json.load(f)
        except (OSError, ValueError):
            _cache["data"] = {}
    return _cache["data"]


def for_symbol(symbol: str) -> Dict[str, Any]:
    from .. import dolthub_vol
    if not dolthub_vol.enabled():
        return {"available": False, "reason": "off"}
    data = _load()
    row = (data.get("symbols") or {}).get(symbol.upper())
    if not row or row.get("n", 0) < MIN_SAMPLES:
        return {"available": False, "reason": "not calibrated"}
    ratio = row["mean_ratio"]
    lo, hi = (row.get("ci95") or [None, None])
    # A lean only where the interval clears 1; the samples overlap, so the
    # interval is wide, and most names will read as not clearly either.
    lean = ("dearer than the moves that followed" if hi is not None and hi < 1 else
            "cheaper than the moves that followed" if lo is not None and lo > 1 else
            "not clearly dearer or cheaper than the moves that followed")
    return {
        "available": True, "symbol": symbol.upper(), **row,
        "fair_exceed_pct": FAIR_EXCEED_PCT,
        "text": ("From {} to {}, the at-the-money straddle about a month out was {}: on average the stock moved "
                 "{:.2f} times what it cost (95% interval {:.2f} to {:.2f}; {} weekly samples, overlapping), and moved "
                 "further than it {:.0f}% of the time against about {:.0f}% for a fair price.").format(
                     row["from"], row["to"], lean, ratio, lo, hi, row["n"], row["exceed_pct"], FAIR_EXCEED_PCT),
        "source": data.get("source"), "source_url": data.get("source_url"),
        "method": data.get("method"),
    }
