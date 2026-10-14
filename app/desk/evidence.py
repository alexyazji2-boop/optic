"""Stage 1: gather every fact an edition may use.

Deterministic, and every leg optional: a leg that fails is recorded in
`coverage` with its reason, and the edition says what it could not see rather
than writing around a hole. Nothing here calls a model.

Units are decided here, once. The feed's `chg_1d` for the 10-year yield is the
percentage change OF the yield (5.24 to 5.217 is -0.44%), which is not how
anyone talks about yields; the change a reader means is in basis points (-2.3bp)
and is computed from the two closes. The same care for every figure: a level is
a level, a change says its unit (%, pp or bp) and what it is a change from.
"""

from __future__ import annotations

import logging
import math
import time
from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

from .model import Evidence, cluster, now_iso

log = logging.getLogger(__name__)
ET = ZoneInfo("America/New_York")

BENCHMARKS = [("SPY", "S&P 500 (SPY)"), ("QQQ", "Nasdaq 100 (QQQ)"), ("IWM", "Russell 2000 (IWM)"),
              ("DIA", "Dow 30 (DIA)"), ("RSP", "S&P 500 equal weight (RSP)")]

# Official series from FRED, each with the form a reader quotes. The period a
# figure describes is FRED's observation date, kept as `period`.
FRED_SERIES = [
    ("DGS2", "2-year Treasury yield", "rates"),
    ("DGS10", "10-year Treasury yield", "rates"),
    ("T10Y2Y", "10-year minus 2-year Treasury spread", "rates"),
    ("DFF", "Effective federal funds rate", "policy"),
    ("CPIAUCSL", "CPI inflation, all items, year over year", "macro"),
    ("PCEPILFE", "Core PCE inflation, year over year", "macro"),
    ("UNRATE", "Unemployment rate", "macro"),
    ("PAYEMS", "Nonfarm payrolls, change on the month", "macro"),
    ("ICSA", "Initial jobless claims, weekly", "macro"),
    ("BAMLH0A0HYM2", "High-yield bond spread over Treasuries", "credit"),
    ("T10YIE", "10-year breakeven inflation", "macro"),
    ("MORTGAGE30US", "30-year mortgage rate", "rates"),
]

# The macro strip's instruments the edition reads, and the unit their change
# is told in. Yields change in basis points; everything else in percent.
MACRO_SYMBOLS = {
    "^TNX": ("10-year Treasury yield (market)", "rates", "bp"),
    "^FVX": ("5-year Treasury yield (market)", "rates", "bp"),
    "^IRX": ("13-week Treasury bill yield", "rates", "bp"),
    "DX-Y.NYB": ("US dollar index (DXY)", "fx", "%"),
    "CL=F": ("WTI crude oil", "commodity", "%"),
    "GC=F": ("Gold", "commodity", "%"),
    "HG=F": ("Copper", "commodity", "%"),
    "HYG": ("High-yield bond ETF (HYG)", "credit", "%"),
    "^VIX": ("VIX", "volatility", "pts"),
    "ES=F": ("S&P 500 futures", "index", "%"),
    "NQ=F": ("Nasdaq 100 futures", "index", "%"),
}

CONSENSUS_CONFLICT_PCT = 2.0

# Large companies whose day is worth reading when the news names them. Matched
# on the names a headline uses; the move is computed from bars like any other.
LARGE_CAPS = [
    ("AAPL", ("apple",)), ("MSFT", ("microsoft",)), ("NVDA", ("nvidia",)), ("GOOGL", ("alphabet", "google")),
    ("AMZN", ("amazon",)), ("META", ("meta platforms", "meta ", "facebook")), ("TSLA", ("tesla",)),
    ("AVGO", ("broadcom",)), ("TSM", ("tsmc", "taiwan semiconductor")), ("MU", ("micron",)),
    ("AMD", ("amd", "advanced micro")), ("INTC", ("intel",)), ("QCOM", ("qualcomm",)), ("ASML", ("asml",)),
    ("ORCL", ("oracle",)), ("NFLX", ("netflix",)), ("JPM", ("jpmorgan", "jp morgan")),
    ("BAC", ("bank of america",)), ("WFC", ("wells fargo",)), ("GS", ("goldman",)), ("MS", ("morgan stanley",)),
    ("C", ("citigroup", "citi ")), ("UNH", ("unitedhealth",)), ("LLY", ("eli lilly", "lilly")),
    ("NVO", ("novo nordisk",)), ("XOM", ("exxon",)), ("CVX", ("chevron",)), ("WMT", ("walmart",)),
    ("COST", ("costco",)), ("V", ("visa ",)), ("MA", ("mastercard",)), ("BRK-B", ("berkshire",)),
    ("JNJ", ("johnson & johnson",)), ("PG", ("procter",)), ("HD", ("home depot",)), ("BA", ("boeing",)),
    ("DIS", ("disney",)), ("PLTR", ("palantir",)), ("CRM", ("salesforce",)),
]


def named_in(text: str) -> List[str]:
    low = " {} ".format((text or "").lower())
    return [sym for sym, names in LARGE_CAPS if any(n in low for n in names)]


NEWS_SECTORS = ("markets", "economy", "business", "tech", "energy", "policy", "finance", "health", "world")


def _f(x: Any, digits: int = 4) -> Optional[float]:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return round(v, digits) if math.isfinite(v) else None


class Gatherer:
    """Collects Evidence rows with stable ids by kind, and the coverage log."""

    PREFIX = {"index": "I", "sector": "S", "breadth": "B", "macro": "M", "rates": "R", "policy": "R",
              "fx": "X", "commodity": "C", "credit": "K", "volatility": "V", "calendar": "E",
              "earnings": "Q", "company": "P", "filing": "F", "news": "N", "options": "O"}

    def __init__(self) -> None:
        self.rows: List[Evidence] = []
        self.coverage: List[Dict[str, Any]] = []
        self._n: Dict[str, int] = {}

    def add(self, **kw: Any) -> Evidence:
        p = self.PREFIX.get(kw["kind"], "Z")
        self._n[p] = self._n.get(p, 0) + 1
        ev = Evidence(id="{}{}".format(p, self._n[p]), as_of=kw.pop("as_of", None) or now_iso(), **kw)
        self.rows.append(ev)
        return ev

    def leg(self, name: str, fn: Callable[[], Any]) -> Any:
        t0 = time.perf_counter()
        try:
            out = fn()
            self.coverage.append({"leg": name, "ok": True, "ms": round((time.perf_counter() - t0) * 1000)})
            return out
        except Exception as exc:                                   # noqa: BLE001
            log.warning("desk evidence leg %s failed: %s", name, exc)
            self.coverage.append({"leg": name, "ok": False, "ms": round((time.perf_counter() - t0) * 1000),
                                  "reason": "{}: {}".format(type(exc).__name__, str(exc)[:160])})
            return None


# ------------------------------------------------------------------ prices

def _bar_moves(frame) -> Optional[Dict[str, Any]]:
    """Last close, its date, 1/5/21-day changes, trend and volume, from daily bars."""
    if frame is None or getattr(frame, "empty", True) or "Close" not in frame:
        return None
    close = frame["Close"].dropna()
    if len(close) < 3:
        return None
    idx = close.index
    last_day = idx[-1]
    try:
        last_day = last_day.tz_convert(ET) if last_day.tzinfo else last_day
    except Exception:                                              # noqa: BLE001
        pass
    c = close.to_numpy(dtype=float)

    def chg(n: int) -> Optional[float]:
        return _f((c[-1] / c[-1 - n] - 1) * 100, 2) if len(c) > n and c[-1 - n] else None

    sma50 = float(c[-50:].mean()) if len(c) >= 50 else None
    sma200 = float(c[-200:].mean()) if len(c) >= 200 else None
    vol_ratio = None
    if "Volume" in frame:
        v = frame["Volume"].dropna().to_numpy(dtype=float)
        if len(v) >= 21 and v[-21:-1].mean() > 0:
            vol_ratio = _f(v[-1] / v[-21:-1].mean(), 2)
    hi20 = float(frame["High"].dropna().to_numpy(dtype=float)[-21:-1].max()) if "High" in frame and len(c) > 21 else None
    lo20 = float(frame["Low"].dropna().to_numpy(dtype=float)[-21:-1].min()) if "Low" in frame and len(c) > 21 else None
    # Its own typical day: the mean absolute close-to-close change over the 20
    # sessions before this one. A move is judged against this, not against a
    # fixed size: 2% is a quiet day for a chip stock and a big one for a bank.
    rets = [abs(c[i] / c[i - 1] - 1) * 100 for i in range(max(1, len(c) - 21), len(c) - 1) if c[i - 1]]
    typical = _f(sum(rets) / len(rets), 3) if rets else None
    return {"last": _f(c[-1], 2), "prev": _f(c[-2], 2), "date": str(getattr(last_day, "date", lambda: last_day)()),
            "typical_abs_1d": typical,
            "chg_1d": chg(1), "chg_5d": chg(5), "chg_21d": chg(21),
            "vs_sma50_pct": _f((c[-1] / sma50 - 1) * 100, 2) if sma50 else None,
            "vs_sma200_pct": _f((c[-1] / sma200 - 1) * 100, 2) if sma200 else None,
            "sma50": _f(sma50, 2), "sma200": _f(sma200, 2),
            "high_20d": _f(hi20, 2), "low_20d": _f(lo20, 2), "volume_vs_20d": vol_ratio}


def gather_prices(g: Gatherer, provider, sectors: List[Dict[str, str]], themes: List[Dict[str, str]]) -> None:
    syms = [s for s, _ in BENCHMARKS] + [r["symbol"] for r in sectors + themes]
    frames = provider.batch_history(syms, period="1y", interval="1d") or {}
    src = "Yahoo Finance daily bars (about 15 minutes delayed in session)"
    for sym, label in BENCHMARKS:
        mv = _bar_moves(frames.get(sym))
        if not mv:
            continue
        g.add(kind="index", label=label, symbol=sym, value=mv["chg_1d"], unit="%",
              period="session of {} (close to close)".format(mv["date"]), event_at=mv["date"],
              source=src, url="https://finance.yahoo.com/quote/{}".format(sym),
              method="Close-to-close change from daily bars; during an open session the last bar is still forming.",
              compare={"base": "previous close", "value": mv["prev"]}, detail=mv)
    sector_rows = []
    for r in sectors + themes:
        mv = _bar_moves(frames.get(r["symbol"]))
        if not mv or mv["chg_1d"] is None:
            continue
        ev = g.add(kind="sector", label="{} ({})".format(r["name"], r["symbol"]), symbol=r["symbol"],
                   value=mv["chg_1d"], unit="%", period="session of {}".format(mv["date"]), event_at=mv["date"],
                   source=src, url="https://finance.yahoo.com/quote/{}".format(r["symbol"]),
                   method="Close-to-close change of the sector ETF.", detail={**mv, "group": "theme" if r in themes else "sector"})
        if r in sectors:
            sector_rows.append(ev)
    if sector_rows:
        up = sum(1 for e in sector_rows if (e.value or 0) > 0)
        g.add(kind="breadth", label="Sector ETFs higher on the day", value=float(up), unit="of {}".format(len(sector_rows)),
              period=sector_rows[0].period, source=src,
              method="Count of the {} SPDR sector ETFs that closed above their previous close.".format(len(sector_rows)),
              detail={"up": up, "total": len(sector_rows)})
    spy, rsp = _bar_moves(frames.get("SPY")), _bar_moves(frames.get("RSP"))
    if spy and rsp and spy["chg_5d"] is not None and rsp["chg_5d"] is not None:
        gap = _f(rsp["chg_5d"] - spy["chg_5d"], 2)
        g.add(kind="breadth", label="Equal-weight minus cap-weight S&P 500, five sessions", value=gap, unit="pp",
              period="five sessions to {}".format(spy["date"]), source=src,
              method="RSP five-session change minus SPY five-session change. Positive means the average stock beat the index's largest names.",
              detail={"rsp_5d": rsp["chg_5d"], "spy_5d": spy["chg_5d"]})


def gather_companies(g: Gatherer, provider, symbols: List[str]) -> None:
    """The day's move for the companies the news and the earnings calendar name."""
    if not symbols:
        return
    frames = provider.batch_history(symbols, period="1y", interval="1d") or {}
    for sym in symbols:
        mv = _bar_moves(frames.get(sym))
        if not mv or mv["chg_1d"] is None:
            continue
        g.add(kind="company", label="{} shares".format(sym), symbol=sym, value=mv["chg_1d"], unit="%",
              period="session of {} (close to close)".format(mv["date"]), event_at=mv["date"],
              source="Yahoo Finance daily bars", url="https://finance.yahoo.com/quote/{}".format(sym),
              method="Close-to-close change from daily bars.", detail=mv)


def gather_macro_tape(g: Gatherer, macro: Dict[str, Any]) -> None:
    found = (macro or {}).get("instruments") or {}
    rows: Dict[str, Dict[str, Any]] = {}
    for bucket in ((macro or {}).get("groups") or {}).values():
        for r in bucket or []:
            if r.get("symbol"):
                rows[r["symbol"]] = r
    for sym, r in found.items() if isinstance(found, dict) else []:
        if isinstance(r, dict):
            rows.setdefault(sym, {**r, "symbol": sym})
    for sym, (label, kind, unit) in MACRO_SYMBOLS.items():
        r = rows.get(sym)
        if not r or r.get("last") is None:
            continue
        last, prev = _f(r.get("last")), _f(r.get("prev_close"))
        # The typical day, close to close, from the strip's own closes. Not the
        # ATR: that is the average high-to-low range, larger than a close-to-
        # close move (gold's ATR read 2.0% on 2026-10-13), and the first
        # written sample called it "gold's typical daily swing".
        closes = [float(x) for x in (r.get("series") or []) if isinstance(x, (int, float))]
        diffs = [closes[i] - closes[i - 1] for i in range(max(1, len(closes) - 20), len(closes))]
        pcts = [abs(closes[i] / closes[i - 1] - 1) * 100 for i in range(max(1, len(closes) - 20), len(closes))
                if closes[i - 1]]
        typical_pct = _f(sum(pcts) / len(pcts), 3) if len(pcts) >= 10 else None
        typical_bp = _f(sum(abs(d) for d in diffs) / len(diffs) * 100, 2) if len(diffs) >= 10 else None
        typical_pts = _f(sum(abs(d) for d in diffs) / len(diffs), 2) if len(diffs) >= 10 else None
        if unit == "bp":
            # ^TNX quotes the yield in percent (5.217 is 5.217%).
            change = _f((last - prev) * 100, 1) if (last is not None and prev is not None) else None
            g.add(kind=kind, label=label, symbol=sym, value=last, unit="%", period="latest quote",
                  as_of=r.get("quote_as_of"), source="Yahoo Finance quote for {}".format(sym),
                  url="https://finance.yahoo.com/quote/{}".format(sym),
                  compare={"base": "previous close", "value": prev, "change": change, "change_unit": "bp"},
                  method="Change in basis points from the previous close (one basis point is 0.01 percentage point).",
                  detail={"chg_5d_pct_of_yield": r.get("chg_5d"), "pct_from_52w_high": r.get("pct_from_52w_high"),
                          "typical_abs_1d": typical_bp})
        elif unit == "pts":
            change = _f(last - prev, 2) if (last is not None and prev is not None) else None
            g.add(kind=kind, label=label, symbol=sym, value=last, unit="index", period="latest quote",
                  as_of=r.get("quote_as_of"), source="Yahoo Finance quote for ^VIX (Cboe)",
                  url="https://finance.yahoo.com/quote/%5EVIX",
                  compare={"base": "previous close", "value": prev, "change": change, "change_unit": "pts"},
                  method="The VIX is the 30-day implied volatility of S&P 500 options, in annualised percent.",
                  detail={"typical_abs_1d": typical_pts, "pct_from_52w_high": r.get("pct_from_52w_high")})
        else:
            g.add(kind=kind, label=label, symbol=sym, value=_f(r.get("chg_1d"), 2), unit="%", period="day, latest quote",
                  as_of=r.get("quote_as_of"), source="Yahoo Finance quote for {}".format(sym),
                  url="https://finance.yahoo.com/quote/{}".format(sym),
                  compare={"base": "previous close", "value": prev, "level": last},
                  method="Percentage change from the previous close.",
                  detail={"level": last, "chg_5d": r.get("chg_5d"), "chg_20d": r.get("chg_20d"),
                          "typical_abs_1d": typical_pct})


def gather_fred(g: Gatherer, series_fn: Callable[[str], Dict[str, Any]], today: date) -> None:
    for code, label, kind in FRED_SERIES:
        s = series_fn(code) or {}
        latest, prev = s.get("latest") or {}, s.get("previous") or {}
        if latest.get("value") is None:
            g.coverage.append({"leg": "fred:" + code, "ok": False, "reason": s.get("error") or "no value"})
            continue
        unit = s.get("unit") or ""
        period = str(latest.get("date") or "")
        scale = 1.0
        # econ.SERIES labels ICSA "k" but FRED publishes the count itself
        # (197000), so a "k" series above ten thousand is put into thousands.
        if unit == "k" and abs(latest["value"]) >= 10000:
            scale = 1000.0
            latest = {**latest, "value": latest["value"] / scale}
            prev = {**prev, "value": prev["value"] / scale} if prev.get("value") is not None else prev
        # Stale for "today" purposes: a daily series more than a week old, or a
        # monthly one more than ten weeks after its period.
        stale = False
        try:
            d = date.fromisoformat(period[:10])
            daily = code in ("DGS2", "DGS10", "T10Y2Y", "DFF", "BAMLH0A0HYM2", "T10YIE")
            stale = (today - d).days > (7 if daily else 75)
        except ValueError:
            pass
        change = _f(latest["value"] - prev["value"], 3) if prev.get("value") is not None else None
        g.add(kind=kind, label=label, symbol=code, value=_f(latest["value"], 3), unit=unit,
              period=period, event_at=period, source="FRED (St. Louis Fed): {}".format(code),
              url="https://fred.stlouisfed.org/series/{}".format(code),
              compare={"base": "previous observation ({})".format(prev.get("date")), "value": _f(prev.get("value"), 3),
                       "change": change, "change_unit": "pp" if unit == "%" else unit} if prev else None,
              method="{}; as published by the agency and redistributed by FRED.".format(s.get("form_label") or "level"),
              stale=stale, detail={"form": s.get("form")})


def gather_rate_path(g: Gatherer, rate: Dict[str, Any]) -> None:
    if not rate or not rate.get("available"):
        g.coverage.append({"leg": "rate_path", "ok": False, "reason": (rate or {}).get("reason") or "unavailable"})
        return
    if rate.get("kind") == "probability":
        g.add(kind="policy", label="Fed funds futures: implied chance of a quarter-point {} at the {} meeting".format(
                  rate.get("direction") or "move", rate.get("meeting")),
              value=_f(rate.get("probability"), 0), unit="%", period="meeting of {}".format(rate.get("meeting")),
              source="CME 30-day fed funds futures (ZQ=F) via Yahoo; Optic's arithmetic",
              url="https://www.cmegroup.com/markets/interest-rates/stirs/30-day-federal-fund.html",
              method=rate.get("method") or "Month-weighted unwind of the contract's implied average rate (CME method).",
              detail={k: rate.get(k) for k in ("implied_rate", "effective", "basis_points", "contract_month_label")})
    else:
        g.add(kind="policy", label="Fed funds futures: change priced over {}".format(rate.get("contract_month_label")),
              value=_f(rate.get("basis_points"), 1), unit="bp", period=str(rate.get("contract_month_label") or ""),
              source="CME 30-day fed funds futures (ZQ=F) via Yahoo; Optic's arithmetic",
              method=rate.get("limit") or "Average rate priced for the contract month minus the effective rate. Not odds on a meeting.")


def gather_calendar(g: Gatherer, events: Dict[str, Any], now: datetime) -> None:
    for r in (events or {}).get("events") or []:
        try:
            when = datetime.fromisoformat(r["at"])
        except (KeyError, ValueError, TypeError):
            continue
        if when - now > timedelta(days=8):
            continue
        readings = r.get("readings") or {}
        prev = r.get("previous") or {}
        g.add(kind="calendar", label=r.get("title") or "", text=r.get("why") or "",
              value=_f(readings.get("actual")) if readings else None, unit=readings.get("unit") or "",
              period=str(readings.get("period") or r.get("period") or ""), event_at=r.get("at"),
              published_at=prev.get("published") if isinstance(prev, dict) else None,
              source=r.get("source") or "Official release schedule (BLS, Federal Reserve)",
              url=(prev.get("url") if isinstance(prev, dict) else None) or r.get("url"),
              compare={"base": "previous reading", "value": _f(readings.get("previous")),
                       "headline": prev.get("headline") if isinstance(prev, dict) else None} if (readings or prev) else None,
              method="No consensus forecast: Optic does not carry surveyed expectations, so a release is compared with its own previous reading.",
              detail={"impact": r.get("impact"), "category": r.get("category"), "released": bool(r.get("released")),
                      "days_away": r.get("days_away")})


def gather_earnings(g: Gatherer, provider, week: Dict[str, Any], quotes: Dict[str, Any], today: date) -> None:
    """Who reports this week and, for the majors that already have, the result
    against the consensus and the stock's reaction. EPS only: the free feed
    carries no reported revenue for a past quarter, which the edition says."""
    for d in (week or {}).get("days") or []:
        try:
            day = date.fromisoformat(d.get("date"))
        except (TypeError, ValueError):
            continue
        for r in d.get("rows") or d.get("companies") or []:
            if not r.get("major"):
                continue
            sym = r.get("ticker")
            reported = day <= today
            detail = {"name": r.get("name"), "sector": r.get("sector"), "eps_consensus": r.get("eps_consensus"),
                      "eps_low": r.get("eps_low"), "eps_high": r.get("eps_high"),
                      "revenue_consensus": r.get("revenue_consensus"), "report_date": str(day)}
            result = None
            if reported:
                try:
                    hist = provider.earnings_history(sym) or []
                except Exception:                                  # noqa: BLE001
                    hist = []
                for h in hist:
                    if str(h.get("date") or "")[:10] in (str(day), str(day - timedelta(days=1))) and h.get("eps_reported") is not None:
                        result = h
                        break
            q = quotes.get(sym) or {}
            if result:
                detail.update({"eps_reported": result.get("eps_reported"), "eps_estimate": result.get("eps_estimate"),
                               "surprise_pct": result.get("surprise_pct"), "timing": result.get("timing"),
                               "reaction_pct": _f((q["last"] / q["prev_close"] - 1) * 100, 2)
                               if q.get("last") and q.get("prev_close") else None,
                               "reaction_as_of": q.get("as_of")})
                # Two consensus figures from the same free feed, and they do not
                # always agree: on 2026-10-13 the calendar carried JPM at $5.715
                # and the history table at $5.94, UNH at $2.17 and $4.14 (likely
                # GAAP against adjusted). Whether a result beat depends on which,
                # so a gap over CONSENSUS_CONFLICT_PCT is carried as a conflict
                # and the edition may not call the beat or miss outright.
                cal, est = r.get("eps_consensus"), result.get("eps_estimate")
                if cal and est and abs(cal - est) / abs(est) * 100 > CONSENSUS_CONFLICT_PCT:
                    detail["consensus_conflict"] = {
                        "calendar": _f(cal, 3), "history": _f(est, 3),
                        "note": "The feed's two consensus EPS figures differ; the surprise depends on which is used."}
                g.add(kind="earnings", label="{} reported EPS against the consensus".format(sym), symbol=sym,
                      value=_f(result.get("surprise_pct"), 2), unit="%", period="quarter reported {}".format(day),
                      event_at=str(day), source="Yahoo Finance earnings history (reported vs consensus EPS)",
                      url="https://finance.yahoo.com/quote/{}/analysis".format(sym),
                      compare={"base": "consensus EPS", "value": _f(result.get("eps_estimate"), 3),
                               "reported": _f(result.get("eps_reported"), 3)},
                      method="Surprise = (reported EPS - consensus EPS) / |consensus EPS|. Revenue against its estimate is not in the free feed.",
                      detail=detail)
            elif day >= today:
                g.add(kind="earnings", label="{} reports {}".format(sym, "today" if day == today else day.strftime("%A %-d %B")),
                      symbol=sym, value=_f(r.get("eps_consensus"), 3), unit="$ EPS consensus",
                      period="quarter to be reported {}".format(day), event_at=str(day),
                      source="Yahoo Finance earnings calendar (consensus EPS and revenue)",
                      url="https://finance.yahoo.com/quote/{}/analysis".format(sym),
                      method="Consensus as carried by the free feed; the number of analysts is not shown.", detail=detail)


def gather_news(g: Gatherer, wires: List[Dict[str, Any]], official: List[Dict[str, Any]], since: datetime) -> None:
    """Stories since the previous session's close, clustered so a story carried
    by five outlets is one row. Official releases separately."""
    cut = since.astimezone(timezone.utc).isoformat()
    fresh = [w for w in wires if (w.get("published") or "") >= cut]
    for c in cluster(sorted(fresh, key=lambda r: r.get("published") or "")):
        # Any copy's desk counts: the Bank of America fine's earliest copy was
        # the FT's, filed under "analysis", and the WSJ and CNBC copies under
        # "markets", so testing the representative alone dropped the story.
        desks = c.get("sectors") or ([c["sector"]] if c.get("sector") else [])
        if desks and not any(d in NEWS_SECTORS for d in desks):
            continue
        g.add(kind="news", label=c.get("title") or "", text=(c.get("summary") or "")[:280],
              published_at=c.get("published"), source=c.get("source") or c.get("source_id") or "",
              url=c.get("url"), sources_in_cluster=len(c.get("outlets") or []) or 1,
              detail={"outlets": c.get("outlets"), "copies": c.get("copies"), "access": c.get("access"),
                      "sector": c.get("sector"), "desks": desks},
              method="Clustered by headline and link: outlets counts distinct sites carrying the same story, which is coverage, not independent confirmation.")
    for e in official:
        if (e.get("published") or "") < cut:
            continue
        g.add(kind="news", label=e.get("title") or "", text=(e.get("summary") or "")[:280],
              published_at=e.get("published"), source=e.get("source") or "", url=e.get("url"),
              detail={"official": True, "access": e.get("access")},
              method="Official release from the agency's own feed.")


def gather_options(g: Gatherer, read_index: Callable[[str], Optional[Dict[str, Any]]]) -> None:
    """SPY's and QQQ's expected moves and skew from the corrected surface
    (app/analytics/vol_surface.py), with the expiry and method named."""
    for sym in ("SPY", "QQQ"):
        s = read_index(sym)
        if not s or not s.get("available"):
            g.coverage.append({"leg": "options:" + sym, "ok": False, "reason": (s or {}).get("reason") or "no surface"})
            continue
        rows = [r for r in (s.get("expiries") or []) if r.get("straddle_move_pct") is not None]
        near = next((r for r in rows if (r.get("dte") or 0) >= 1), rows[0] if rows else None)
        month = min(rows, key=lambda r: abs((r.get("dte") or 0) - 30)) if rows else None
        for r, which in ((near, "nearest weekly"), (month, "about a month out")):
            if not r:
                continue
            g.add(kind="options", label="{} options: expected move to {} expiry ({})".format(sym, r.get("expiry"), which),
                  symbol=sym, value=_f(r.get("straddle_move_pct"), 2), unit="% (+/-)",
                  url="https://finance.yahoo.com/quote/{}/options".format(sym),
                  period="to the {} expiry ({} days)".format(r.get("expiry"), r.get("dte")),
                  source="Optic's options surface from the Yahoo chain (about 15 minutes delayed)",
                  method="At-the-money straddle mid divided by the price: roughly the average absolute move options are priced for over the whole period to that expiry, not a forecast and not an event-only move.",
                  detail={"atm_iv_pct": r.get("atm_iv_pct"), "one_sd_pct": r.get("one_sd_move_pct"),
                          "rr25_pts": r.get("rr25_pts"), "expiry": r.get("expiry"), "dte": r.get("dte")})
            if near is month:
                break
        iv30 = (s.get("iv30") or {}).get("iv_pct")
        if iv30 is not None:
            g.add(kind="options", label="{} 30-day implied volatility".format(sym), symbol=sym, value=_f(iv30, 1), unit="%",
                  url="https://finance.yahoo.com/quote/{}/options".format(sym),
                  period="30-day constant maturity", source="Optic's options surface from the Yahoo chain",
                  method="Total variance interpolated between the expiries either side of 30 days.",
                  detail={"term": (s.get("term") or {}).get("label") if isinstance(s.get("term"), dict) else s.get("term")})


def gather_dispersion(g: Gatherer, d: Dict[str, Any]) -> None:
    """The VIXEQ - VIX gap with its percentile, and what it has not predicted,
    so the edition can describe dispersion without calling it a warning."""
    if not d or not d.get("available"):
        g.coverage.append({"leg": "dispersion_rows", "ok": False, "reason": (d or {}).get("reason") or "no reading"})
        return
    pct = d.get("gap_percentile")
    g.add(kind="volatility", label="Dispersion: VIXEQ (average stock's implied vol) minus VIX", symbol="^VIXEQ",
          value=_f(d.get("gap"), 2), unit="pts", period="close of {}".format(d.get("as_of")),
          as_of=d.get("as_of"), source="Cboe VIXEQ and VIX, via Yahoo Finance quotes",
          url="https://www.cboe.com/us/indices/dashboard/vixeq/",
          compare={"base": "percentile of the gap since {}".format(d.get("gap_history_from")), "value": pct}
          if pct is not None else None,
          method=("VIXEQ is the 30-day implied volatility of the average large US stock, VIX the S&P 500's; the gap "
                  "is mostly low implied correlation. Tested 2014-2026: it did not predict drawdowns beyond what the "
                  "VIX itself did, and a rising gap predicted nothing. Describe it; do not call it a warning."),
          detail={"vixeq": d.get("vixeq"), "vix": d.get("vix"), "cor1m": d.get("cor1m"),
                  "cor1m_percentile": d.get("cor1m_percentile"), "dspx": d.get("dspx"),
                  "dspx_percentile": d.get("dspx_percentile")})


def gather_gamma(g: Gatherer, sym: str, gx: Dict[str, Any]) -> None:
    """The index's modelled dealer gamma: the regime, the flip and the walls,
    with the model's assumption and the fact that none of it has been tested
    in Optic's own record yet (app/signal_archive.py, from 2026-10-13)."""
    if not gx or gx.get("error") or not gx.get("totals"):
        g.coverage.append({"leg": "gamma_rows", "ok": False, "reason": (gx or {}).get("error") or "no GEX read"})
        return
    t, reg, lv = gx.get("totals") or {}, gx.get("regime") or {}, gx.get("levels") or {}
    near = gx.get("near_term") or {}
    caveat = ("Modelled, not observed: {} Whether the regime or the walls predict anything is being recorded "
              "daily since 2026-10-13 and has not been tested; describe them as positioning, not as support, "
              "resistance or a forecast.".format(gx.get("assumption") or ""))
    g.add(kind="options", label="{} dealer gamma (modelled), per 1% move".format(sym), symbol=sym,
          value=_f(t.get("net_gex_per_1pct_millions"), 1), unit="$m per 1%",
          period="open interest as of the previous session",
          source="Optic's GEX read from the Yahoo chain", url="https://finance.yahoo.com/quote/{}/options".format(sym),
          compare={"base": "regime", "value": reg.get("state")},
          method=caveat,
          detail={"flip_point": reg.get("flip_point"), "flip_distance_pct": reg.get("flip_distance_pct"),
                  "above_flip": reg.get("above_flip"),
                  "call_wall": (lv.get("call_wall") or {}).get("strike"),
                  "put_wall": (lv.get("put_wall") or {}).get("strike"),
                  "pct_of_avg_dollar_volume": t.get("pct_of_avg_dollar_volume"),
                  "near_term_share_of_gross_pct": near.get("share_of_gross_pct") if near.get("available") else None,
                  "expiries_used": gx.get("expiries_used")})


# ------------------------------------------------------------------- bundle

def news_window_start(now: datetime, slot: str, session_mod) -> datetime:
    """Where an edition's news begins: the regular close before the session it
    covers. A close edition covers today's session, so its news starts at the
    PREVIOUS close; a premarket or closed-market edition covers the night and
    the last session, so its news starts at the most recent close."""
    et = now.astimezone(ET)
    try:
        last = session_mod.last_regular_close(et)
        if last is None:
            raise ValueError("no close")
        if slot == "close" and last.date() == et.date():
            earlier = session_mod.last_regular_close(last - timedelta(hours=12))
            if earlier:
                last = earlier
        return last
    except Exception:                                              # noqa: BLE001
        return now - timedelta(hours=30)


def bundle(g: Gatherer, *, slot: str, now: datetime, session: Dict[str, Any]) -> Dict[str, Any]:
    """The evidence as the outline and the checker read it."""
    newest = max([e.published_at or e.as_of or "" for e in g.rows] + [""])
    return {
        "slot": slot,
        "date": now.astimezone(ET).date().isoformat(),
        "gathered_at": now.astimezone(timezone.utc).isoformat(timespec="seconds"),
        "cutoff": newest or None,
        "session": {k: session.get(k) for k in ("phase", "label", "holiday", "early_close")},
        "evidence": [e.as_dict() for e in g.rows],
        "coverage": g.coverage,
    }
