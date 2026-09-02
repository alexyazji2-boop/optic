"""Does the sector agree with the stock?

A setup on a single name reads differently depending on what the group around it
is doing. A breakout in a sector the whole market is buying has a tailwind; the
same chart in a sector being sold is fighting one. This answers that in one
panel: which sector the company is in, how that sector's ETF is trading, and how
the stock is performing against both the market and its own group.

**Relative strength against the sector is the useful number, not against SPY.**
Beating the index while trailing every peer means the sector carried you, and a
reader who only sees "+5% vs SPY" will mistake that for stock selection. Both are
shown, and when they disagree the panel says which is which.

Nothing here predicts anything. A supportive sector is context; it is not a
reason a particular company's shares will rise, and the note says so.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .sectors import SECTORS
from . import sector_board

# yfinance's sector strings to the SPDR fund that tracks them. yfinance uses its
# own vocabulary ("Financial Services", "Technology"), which does not match the
# fund names, so the mapping is explicit rather than fuzzy — a near-miss here
# would benchmark a bank against semiconductors.
SECTOR_TO_ETF = {
    "technology": "XLK",
    "financial services": "XLF",
    "financials": "XLF",
    "healthcare": "XLV",
    "health care": "XLV",
    "consumer cyclical": "XLY",
    "consumer discretionary": "XLY",
    "consumer defensive": "XLP",
    "consumer staples": "XLP",
    "energy": "XLE",
    "industrials": "XLI",
    "basic materials": "XLB",
    "materials": "XLB",
    "utilities": "XLU",
    "real estate": "XLRE",
    "communication services": "XLC",
}

ETF_NAME = {s["symbol"]: s["name"] for s in SECTORS}

# Windows used for relative strength, in sessions.
RS_WINDOW = 21

# How far the stock has to diverge from its sector before that counts as
# stock-specific rather than sector drift.
RS_BAND_PCT = 3.0


def _num(value: Any) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return None if out != out or out in (float("inf"), float("-inf")) else out


def _ret(closes, bars: int) -> Optional[float]:
    if closes is None or len(closes) <= bars:
        return None
    prev, last = _num(closes.iloc[-1 - bars]), _num(closes.iloc[-1])
    if prev is None or last is None or prev <= 0:
        return None
    return (last / prev - 1.0) * 100.0


def build(provider, ticker: str, sector_name: Optional[str]) -> Dict[str, Any]:
    """The sector backdrop for one stock."""
    ticker = (ticker or "").upper().strip()
    key = (sector_name or "").lower().strip()
    etf = SECTOR_TO_ETF.get(key)
    if not etf:
        return {"available": False,
                "reason": ("No sector benchmark for {}. Funds, trusts and foreign "
                           "issuers often have no sector classification, and guessing "
                           "one would benchmark against the wrong group."
                           .format(sector_name or ticker))}

    try:
        frames = provider.batch_history([ticker, etf, "SPY"], period="6mo",
                                        interval="1d") or {}
    except Exception as exc:                     # noqa: BLE001
        return {"available": False, "reason": "Price history unavailable: {}".format(exc)}

    def closes(sym):
        f = frames.get(sym)
        return f["Close"].dropna() if f is not None and not f.empty else None

    stock_ret = _ret(closes(ticker), RS_WINDOW)
    etf_ret = _ret(closes(etf), RS_WINDOW)
    spy_ret = _ret(closes("SPY"), RS_WINDOW)
    if stock_ret is None:
        return {"available": False, "reason": "Not enough price history for {}.".format(ticker)}

    vs_spy = (stock_ret - spy_ret) if spy_ret is not None else None
    vs_sector = (stock_ret - etf_ret) if etf_ret is not None else None

    # The sector ETF's own overnight trend, from the same definition the sector
    # board uses — one source for "is XLK trending", not two that can disagree.
    etf_trend, etf_row = None, None
    try:
        board = sector_board.build(provider)
        etf_row = next((r for r in board.get("rows", [])
                        if r.get("symbol") == etf and r.get("available")), None)
        if etf_row:
            etf_trend = etf_row.get("trend")
    except Exception:
        pass

    # Verdict. Deliberately three-way and deliberately cautious: a supportive
    # backdrop is the weakest of the three claims this terminal makes about a
    # setup, and overstating it is how a reader ends up buying a weak chart in a
    # strong sector.
    if etf_trend == "uptrend" and (vs_sector is None or vs_sector > -RS_BAND_PCT):
        verdict, label = "supportive", "Supportive sector backdrop"
        note = ("The sector ETF is in an overnight uptrend and this name is not "
                "lagging it, so group flows are at least not working against the "
                "setup. That is a tailwind, not a reason on its own.")
    elif etf_trend == "downtrend" and (vs_sector is None or vs_sector < RS_BAND_PCT):
        verdict, label = "against", "Sector backdrop is against it"
        note = ("The sector ETF is in an overnight downtrend and this name is not "
                "outrunning it. A setup here is fighting its own group, which does "
                "not make it wrong but does raise the bar.")
    else:
        verdict, label = "mixed", "Neutral sector backdrop"
        note = ("Sector backdrop is mixed. Individual setups should be judged more "
                "heavily on their own rating, momentum and company-specific "
                "catalysts than on the group.")

    # The interesting disagreement: beating the index while trailing the sector.
    conflict = None
    if vs_spy is not None and vs_sector is not None:
        if vs_spy > 0 and vs_sector < -RS_BAND_PCT:
            conflict = ("Ahead of the market but behind its own sector — the group "
                        "carried this, not the company. Relative strength against "
                        "peers is the harder test and this name is failing it.")
        elif vs_spy < 0 and vs_sector > RS_BAND_PCT:
            conflict = ("Behind the market but ahead of its own sector — the drag is "
                        "the group, and this name is the better half of a weak "
                        "neighbourhood.")

    return {
        "available": True,
        "ticker": ticker,
        "sector": sector_name,
        "etf": etf,
        "etf_name": ETF_NAME.get(etf, etf),
        "etf_trend": etf_trend,
        "etf_summary": (etf_row or {}).get("summary"),
        "window_sessions": RS_WINDOW,
        "stock_return_pct": round(stock_ret, 2),
        "etf_return_pct": round(etf_ret, 2) if etf_ret is not None else None,
        "spy_return_pct": round(spy_ret, 2) if spy_ret is not None else None,
        "rs_vs_spy_pct": round(vs_spy, 2) if vs_spy is not None else None,
        "rs_vs_sector_pct": round(vs_sector, 2) if vs_sector is not None else None,
        "rs_vs_spy_label": (None if vs_spy is None else
                            "Outperforming SPY" if vs_spy > 0 else "Underperforming SPY"),
        "rs_vs_sector_label": (
            None if vs_sector is None else
            "Leading its sector" if vs_sector > RS_BAND_PCT else
            "Lagging its sector" if vs_sector < -RS_BAND_PCT else
            "In line with sector"),
        "verdict": verdict,
        "label": label,
        "note": note,
        "conflict": conflict,
        "method": (
            "Relative strength over the last {} sessions against both SPY and the "
            "sector's own SPDR fund. The ETF's trend uses the same prior-session "
            "high and low the sector board uses, so the two cannot disagree. "
            "Sector confirmation is research context only: a supportive group does "
            "not guarantee any individual holding moves, and every name still needs "
            "its own setup, momentum and risk structure."
            .format(RS_WINDOW)
        ),
    }
