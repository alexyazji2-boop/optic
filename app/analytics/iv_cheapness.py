"""Are this stock's options cheap or dear? What IV rank does and does not say.

From a post: "buy options when IV rank is 30 or below". Measured on DoltHub's
daily history (2026-10-14, `docs/research/iv-rank-cheapness-2026-10-14.md`):
1,423 optionable US stocks, 304,314 stock-days from October 2025 to September
2026, each day's 30-day ATM IV against the realised volatility of the 30 days
that followed.

* Implied beat the realised volatility that followed on 70% of days: options
  usually cost more than the moves they insured (the variance risk premium).
* A low IV rank narrows that, but rarely reverses it: after rank 0-10 the move
  beat implied 38% of the time, 10-20 33%, 20-30 29%, against 25 to 29% above
  rank 30. Only the lowest tenth came near fair in variance terms (1.09).
* Implied below the stock's own trailing realised vol was the stronger sign:
  45% of those days were followed by more movement than implied, against 22%
  otherwise. Still under half.
* One year, one regime: by month the share ranged from 16% to 49%.

So the reading here says where today's options sit on those two measures and
what followed such days in the sample, and does not call options cheap.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Dict, Optional


def _r1(x: float) -> str:
    """One decimal, half up, as the page's fmt prints the same figure beside it
    (12.35 read 12.4 on the line above and 12.3 here)."""
    return str(Decimal(str(x)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))

SAMPLE = "1,423 optionable US stocks, October 2025 to September 2026 (DoltHub daily volatility history)"
BY_RANK = [((0, 10), 38.1, 1.090), ((10, 20), 32.9, 0.957), ((20, 30), 28.7, 0.918), ((30, 50), 28.1, 0.901),
           ((50, 70), 29.1, 0.905), ((70, 90), 27.5, 0.886), ((90, 100.1), 25.0, 0.829)]
OVERALL_PCT = 29.6
IV_BELOW_HV_PCT, IV_ABOVE_HV_PCT = 45.4, 22.5


def read(iv_rank: Optional[Dict[str, Any]], iv_hv: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    rank = (iv_rank or {}).get("rank") if (iv_rank or {}).get("available") else None
    hv = iv_hv if (iv_hv or {}).get("available") else None
    if rank is None and hv is None:
        return {"available": False, "reason": "No IV rank or realised volatility to read."}
    parts = []
    bucket = None
    if rank is not None:
        for (lo, hi), pct, var in BY_RANK:
            if lo <= rank < hi:
                bucket = {"range": [lo, min(hi, 100)], "moved_more_pct": pct, "variance_ratio": var}
        parts.append("At an IV rank of {:.0f}, days in the {:.0f} to {:.0f} band were followed by more movement than "
                     "implied {:.0f}% of the time across the sample, against {:.0f}% for all days.".format(
                         rank, bucket["range"][0], bucket["range"][1], bucket["moved_more_pct"], OVERALL_PCT))
    if hv is not None:
        below = hv["iv30"] < hv["hv30"]
        parts.append("Implied is {} the past 30 days' realised volatility ({}% against {}%); days like that "
                     "were followed by more movement than implied {:.0f}% of the time.".format(
                         "below" if below else "above", _r1(hv["iv30"]), _r1(hv["hv30"]),
                         IV_BELOW_HV_PCT if below else IV_ABOVE_HV_PCT))
        own = hv.get("iv_above_next_rv_pct")
        if own is not None:
            parts.append("On this stock over the past year, implied beat the volatility that followed on {:.0f}% of "
                         "days.".format(own))
    return {
        "available": True, "rank": rank, "rank_bucket": bucket,
        "iv_below_hv": None if hv is None else hv["iv30"] < hv["hv30"],
        "text": " ".join(parts),
        "finding": ("Options usually cost more than the moves that followed (70% of days). A low IV rank narrows "
                    "that but rarely reverses it; implied below recent realised volatility is the stronger sign, "
                    "and still under half. None of it makes buying options the better side on its own."),
        "sample": SAMPLE,
    }
