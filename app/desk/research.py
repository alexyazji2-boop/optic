"""Milo's research pack: underlying sources, chosen by what the question needs.

Milo used to see what the reader's browser had open, plus one ticker snapshot
the server fetched when a question named a symbol. That snapshot is technical
analysis and options, so a question about a business's quality, its valuation,
its next report or the economy was answered from chart indicators.

Now the server reads the question, decides what kind it is, and retrieves the
evidence that kind of question turns on:

  long_term     business quality, valuation, financial health and risks:
                revenue growth, margins, free cash flow, capex intensity,
                dilution, debt, valuation multiples, the 10-K's description
  pre_earnings  expectations and event risk: the date, the consensus EPS and
                revenue, estimate revisions, the surprise record, the latest
                results filing
  day_trade     fresh market data and liquidity: the quote and its timestamp,
                the session, today's range and volume against normal, news in
                the last hours
  swing         price structure with what is coming: events in the next three
                weeks, the market backdrop, relative strength, the 20-day range
  macro         official series, the calendar, the rate path
  desk          a section of Optic Desk with the evidence it cites, re-read
                where it has moved since publication

Every item carries its source, link, period and timestamp, so Milo can cite it
and say how fresh it is. What a free feed cannot supply (management commentary,
guidance text, reported revenue against its estimate, intraday options liquidity)
is listed under `not_available` rather than guessed. Retrieval is bounded in
time: a slow source is skipped and named, never waited on.
"""

from __future__ import annotations

import concurrent.futures as cf
import logging
import math
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional

log = logging.getLogger(__name__)

TIME_BUDGET_SECONDS = 8.0

_EARN = re.compile(r"\b(earnings|report(s|ing)?|results|guidance|quarter|eps|beat|miss|whisper|ahead of (the )?print)\b", re.I)
# "today" alone is not a day trade: "a good long-term investment at today's
# price" was routed to intraday data in the first comparison (2026-10-13).
_DAY = re.compile(r"\b(day ?trad\w*|intraday|scalp\w*|at the open|into the close|vwap|0 ?dte|premarket|pre-market)\b", re.I)
_SWING = re.compile(r"\b(swing|next (few|couple of) weeks|setup|entry|stop|breakout|pullback|support|resistance|invalidat\w*)\b", re.I)
_LONG = re.compile(r"\b(long[- ]term|invest\w*|hold(ing)? (it|for)|valuation|moat|business|years|fundamental\w*|dividend|"
                   r"undervalued|overvalued|cheap|expensive|quality|balance sheet|free cash|cash flow|capex|dilution|margin\w*)\b", re.I)
_MACRO = re.compile(r"\b(fed|rates?|inflation|cpi|ppi|pce|yields?|treasur\w*|dollar|economy|recession|jobs|payrolls|"
                    r"unemployment|gdp|soft landing|credit spreads?)\b", re.I)
_DESK = re.compile(r"\b(optic desk|the desk|newsletter|this edition|today's edition)\b", re.I)


def intent(question: str, horizon: Optional[str] = None, ticker: Optional[str] = None,
           desk_section: Optional[Dict[str, Any]] = None) -> str:
    q = question or ""
    if desk_section or _DESK.search(q):
        return "desk"
    if ticker and _EARN.search(q):
        return "pre_earnings"
    explicit_long = re.search(r"\b(long[- ]term|for years|invest(ing|ment)?|retire\w*)\b", q, re.I)
    if explicit_long and not _DAY.search(q):
        return "long_term" if ticker else "macro"
    if horizon == "day" or _DAY.search(q):
        return "day_trade" if ticker else "macro" if _MACRO.search(q) else "day_trade"
    # Swing words before the looser long-term ones: "does the setup hold for a
    # swing" says "hold for", and is not a question about owning the business.
    if horizon == "swing" or _SWING.search(q):
        return "swing"
    if horizon == "long" or _LONG.search(q):
        return "long_term" if ticker else "macro"
    if not ticker and _MACRO.search(q):
        return "macro"
    return "long_term" if ticker else "macro"


@dataclass
class Deps:
    provider: Any
    sec_history: Optional[Callable[[str], Dict[str, Any]]] = None
    filings: Optional[Callable[[str], Dict[str, Any]]] = None
    business: Optional[Callable[[str], Optional[Dict[str, Any]]]] = None
    news: Optional[Callable[[str], Dict[str, Any]]] = None
    fred_series: Optional[Callable[[str], Dict[str, Any]]] = None
    events: Optional[Callable[[], Dict[str, Any]]] = None
    rate_path: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None
    desk_load: Optional[Callable[[str], Optional[Dict[str, Any]]]] = None
    ex_dividend: Optional[Callable[[str], Optional[str]]] = None
    session_state: Optional[Callable[[], Dict[str, Any]]] = None
    market: Optional[Callable[[], Optional[Dict[str, Any]]]] = None


def _f(x: Any, d: int = 2) -> Optional[float]:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return round(v, d) if math.isfinite(v) else None


class Pack:
    def __init__(self, kind: str, ticker: Optional[str]) -> None:
        self.kind, self.ticker = kind, ticker
        self.items: List[Dict[str, Any]] = []
        self.missing: List[str] = []
        self.not_available: List[str] = []

    def add(self, label: str, value: Any = None, *, unit: str = "", period: str = "", source: str = "",
            url: Optional[str] = None, as_of: Optional[str] = None, text: str = "", group: str = "") -> None:
        self.items.append({k: v for k, v in {
            "id": "R{}".format(len(self.items) + 1), "group": group, "label": label, "value": value,
            "unit": unit, "period": period, "source": source, "url": url, "as_of": as_of, "text": text}.items()
            if v not in (None, "", [])})

    def out(self) -> Dict[str, Any]:
        return {"intent": self.kind, "ticker": self.ticker, "items": self.items,
                "missing": self.missing, "not_available": self.not_available,
                "assembled_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "note": ("Retrieved by the server for this question from the sources named on each item. "
                         "Cite them; say how fresh they are; list what is not available rather than guessing.")}


# ------------------------------------------------------------ the pieces

def _statement(raw: Dict[str, Any], table: str, row: str) -> List[Optional[float]]:
    t = (raw or {}).get(table) or {}
    vals = ((t.get("rows") or {}).get(row)) or []
    return [(_f(v, 0) if v is not None else None) for v in vals]


_BANKLIKE = re.compile(r"\b(bank|banks|capital markets|insurance|credit services|asset management|mortgage)\b", re.I)


def fundamentals(p: Pack, d: Deps, t: str) -> None:
    raw = d.provider.financials(t) or {}
    q = d.provider.quote(t) or {}
    # A bank's operating cash flow moves with deposits, loans and trading
    # balances, so "free cash flow" and capex intensity mean nothing there:
    # measured on 2026-10-13, JPMorgan's last fiscal year read as -$148bn of
    # free cash flow. The figures that matter for a lender (net interest income,
    # credit losses, capital ratios) are not in the free statements.
    if q.get("sector") == "Financial Services" and _BANKLIKE.search(q.get("industry") or ""):
        p.not_available.append("Free cash flow, capex and margins are not meaningful for a bank or insurer; "
                               "net interest income, credit losses and capital ratios are not in the free data.")
        inc = (raw.get("income_annual") or {})
        periods = inc.get("periods") or []
        rev = _statement(raw, "income_annual", "Total Revenue")
        ni = _statement(raw, "income_annual", "Net Income")
        sh = _statement(raw, "income_annual", "Diluted Average Shares")
        src = "Company financial statements via Yahoo Finance (annual)"
        url = "https://finance.yahoo.com/quote/{}/financials".format(t)
        if rev and rev[0] and len(rev) > 1 and rev[1]:
            p.add("Revenue growth", _f((rev[0] / rev[1] - 1) * 100, 1), unit="%",
                  period="fiscal year ended {} vs prior year".format(periods[0] if periods else ""), source=src, url=url,
                  group="business")
        if ni and ni[0] and len(ni) > 1 and ni[1]:
            p.add("Net income growth", _f((ni[0] / ni[1] - 1) * 100, 1), unit="%",
                  period="fiscal year ended {} vs prior year".format(periods[0] if periods else ""), source=src, url=url,
                  group="business")
        if sh and len(sh) > 1 and sh[0] and sh[1]:
            p.add("Change in diluted share count", _f((sh[0] / sh[1] - 1) * 100, 2), unit="%",
                  period="fiscal year ended {} vs prior year".format(periods[0] if periods else ""), source=src, url=url,
                  group="dilution")
        return
    inc = (raw.get("income_annual") or {})
    periods = inc.get("periods") or []
    rev = _statement(raw, "income_annual", "Total Revenue")
    gp = _statement(raw, "income_annual", "Gross Profit")
    op = _statement(raw, "income_annual", "Operating Income")
    ni = _statement(raw, "income_annual", "Net Income")
    sh = _statement(raw, "income_annual", "Diluted Average Shares")
    ocf = _statement(raw, "cashflow_annual", "Operating Cash Flow")
    capex = _statement(raw, "cashflow_annual", "Capital Expenditure")
    fcf = _statement(raw, "cashflow_annual", "Free Cash Flow")
    buyback = _statement(raw, "cashflow_annual", "Repurchase Of Capital Stock")
    sbc = _statement(raw, "cashflow_annual", "Stock Based Compensation")
    src = "Company financial statements via Yahoo Finance (annual, fiscal years as the company reports them)"
    url = "https://finance.yahoo.com/quote/{}/financials".format(t)
    fy = lambda i: "fiscal year ended {}".format(periods[i]) if i < len(periods) else ""
    if rev and rev[0]:
        p.add("Revenue", _f(rev[0] / 1e9, 2), unit="$bn", period=fy(0), source=src, url=url, group="business")
        if len(rev) > 1 and rev[1]:
            p.add("Revenue growth", _f((rev[0] / rev[1] - 1) * 100, 1), unit="%", period="{} vs prior year".format(fy(0)),
                  source=src, url=url, group="business")
        for name, row in (("Gross margin", gp), ("Operating margin", op), ("Net margin", ni)):
            if row and row[0] is not None:
                p.add(name, _f(row[0] / rev[0] * 100, 1), unit="%", period=fy(0), source=src, url=url, group="business")
        if capex and capex[0] is not None:
            p.add("Capital expenditure", _f(abs(capex[0]) / 1e9, 2), unit="$bn", period=fy(0), source=src, url=url,
                  group="cash")
            p.add("Capex as a share of revenue", _f(abs(capex[0]) / rev[0] * 100, 1), unit="%", period=fy(0),
                  source=src, url=url, group="cash")
            if len(capex) > 1 and capex[1]:
                p.add("Capex growth", _f((abs(capex[0]) / abs(capex[1]) - 1) * 100, 1), unit="%",
                      period="{} vs prior year".format(fy(0)), source=src, url=url, group="cash")
        if fcf and fcf[0] is not None:
            p.add("Free cash flow", _f(fcf[0] / 1e9, 2), unit="$bn", period=fy(0), source=src, url=url, group="cash",
                  text="Operating cash flow minus capital expenditure.")
            p.add("Free cash flow margin", _f(fcf[0] / rev[0] * 100, 1), unit="%", period=fy(0), source=src, url=url,
                  group="cash")
            if ni and ni[0]:
                p.add("Free cash flow as a share of net income", _f(fcf[0] / ni[0] * 100, 0), unit="%", period=fy(0),
                      source=src, url=url, group="cash",
                      text="Below 100% means less cash came in than accounting profit, often because of capex or working capital.")
        if ocf and ocf[0] is not None:
            p.add("Operating cash flow", _f(ocf[0] / 1e9, 2), unit="$bn", period=fy(0), source=src, url=url, group="cash")
    if sh and len(sh) > 1 and sh[0] and sh[1]:
        p.add("Change in diluted share count", _f((sh[0] / sh[1] - 1) * 100, 2), unit="%",
              period="{} vs prior year".format(fy(0)), source=src, url=url, group="dilution",
              text="Positive is dilution; negative means buybacks retired more shares than were issued.")
    if buyback and buyback[0]:
        p.add("Share repurchases", _f(abs(buyback[0]) / 1e9, 2), unit="$bn", period=fy(0), source=src, url=url, group="dilution")
    if sbc and sbc[0]:
        p.add("Stock-based compensation", _f(sbc[0] / 1e9, 2), unit="$bn", period=fy(0), source=src, url=url, group="dilution")
    bal = (raw.get("balance_annual") or {})
    debt = _statement(raw, "balance_annual", "Total Debt")
    cash = _statement(raw, "balance_annual", "Cash And Cash Equivalents")
    if debt and debt[0] is not None:
        bp = (bal.get("periods") or [""])[0]
        p.add("Total debt", _f(debt[0] / 1e9, 2), unit="$bn", period="balance sheet at {}".format(bp), source=src, url=url,
              group="balance")
        if cash and cash[0] is not None:
            p.add("Net cash (cash minus debt)", _f((cash[0] - debt[0]) / 1e9, 2), unit="$bn",
                  period="balance sheet at {}".format(bp), source=src, url=url, group="balance")


def valuation(p: Pack, d: Deps, t: str) -> None:
    q = d.provider.quote(t) or {}
    src = "Yahoo Finance quote summary"
    url = "https://finance.yahoo.com/quote/{}/key-statistics".format(t)
    for label, key, unit in (("Price", "price", "$"), ("Market value", "market_cap", "$bn"),
                             ("Trailing P/E", "trailing_pe", "x"), ("Forward P/E", "forward_pe", "x"),
                             ("PEG ratio", "peg_ratio", "x"), ("Price to book", "price_to_book", "x"),
                             ("Dividend yield", "dividend_yield", "%")):
        v = q.get(key)
        if v is None:
            continue
        if key == "market_cap":
            v = v / 1e9
        if key == "dividend_yield":
            v = v * 100 if v < 1 else v
        p.add(label, _f(v, 2), unit=unit, period="latest quote", source=src, url=url, as_of=q.get("as_of"),
              group="valuation")
    p.not_available.append("Valuation against the company's own history and peers is not computed here: "
                           "a multiple alone does not say whether a price is attractive.")


def describe(p: Pack, d: Deps, t: str) -> None:
    if not d.business:
        return
    b = d.business(t) or {}
    text = (b.get("text") or "")[:600]
    if text:
        p.add("What the business does", text=text,
              source="{} filed {} (SEC EDGAR)".format(b.get("form_name") or b.get("form") or "Annual report", b.get("filed")),
              url=b.get("url"), period="period ended {}".format(b.get("period")), group="business")


def filings(p: Pack, d: Deps, t: str, items: Optional[set] = None, limit: int = 4) -> None:
    if not d.filings:
        return
    f = d.filings(t) or {}
    if f.get("available") is False:
        p.missing.append("SEC filings: {}".format(f.get("reason")))
        return
    n = 0
    for r in f.get("filings") or []:
        codes = {c.strip() for c in str(r.get("items") or "").split(",") if c.strip()}
        if items and not (codes & items) and r.get("form") not in ("10-Q", "10-K"):
            continue
        p.add("{} filed {}".format(r.get("form"), r.get("filed")), text=r.get("what") or "",
              source="SEC EDGAR", url=r.get("url"), period="filed {}".format(r.get("filed")), group="filings")
        n += 1
        if n >= limit:
            break


def earnings(p: Pack, d: Deps, t: str) -> None:
    cal = d.provider.earnings_calendar(t) or {}
    src = "Yahoo Finance earnings calendar and estimates"
    url = "https://finance.yahoo.com/quote/{}/analysis".format(t)
    if cal.get("date") or cal.get("earnings_date"):
        p.add("Next report", text=str(cal.get("date") or cal.get("earnings_date")), source=src, url=url,
              group="expectations")
    for label, key, unit in (("Consensus EPS", "eps_avg", "$"), ("Consensus EPS, low", "eps_low", "$"),
                             ("Consensus EPS, high", "eps_high", "$"), ("Consensus revenue", "revenue_avg", "$bn")):
        v = cal.get(key)
        if v is None:
            continue
        if unit == "$bn":
            v = v / 1e9
        p.add(label, _f(v, 3), unit=unit, period="quarter to be reported", source=src, url=url, group="expectations")
    est = d.provider.estimates(t) or {}
    trend = est.get("eps_trend") or {}
    cur = trend.get("0q") or trend.get("current_quarter") or {}
    if cur.get("current") is not None and cur.get("90daysAgo") is not None:
        p.add("Current-quarter EPS estimate now vs 90 days ago",
              _f((cur["current"] / cur["90daysAgo"] - 1) * 100, 1) if cur["90daysAgo"] else None, unit="%",
              period="estimate revisions over 90 days", source=src, url=url, group="expectations",
              text="Rising estimates into a report raise the bar the result has to clear.")
    hist = d.provider.earnings_history(t) or []
    for h in hist[:4]:
        if h.get("eps_reported") is None:
            continue
        p.add("EPS surprise, report of {}".format(str(h.get("date"))[:10]), _f(h.get("surprise_pct"), 1), unit="%",
              period="quarter reported {}".format(str(h.get("date"))[:10]), source="Yahoo Finance earnings history",
              url=url, group="record", text="Reported ${} against ${}.".format(h.get("eps_reported"), h.get("eps_estimate")))
    p.not_available += ["Management commentary and guidance text (not in the free feeds; the results filing is linked where available).",
                        "Reported revenue against its estimate for past quarters."]


def tape(p: Pack, d: Deps, t: str) -> None:
    q = d.provider.quote(t) or {}
    src = "Yahoo Finance quote (about 15 minutes delayed in session)"
    url = "https://finance.yahoo.com/quote/{}".format(t)
    if q.get("price") is not None:
        p.add("Last price", _f(q["price"], 2), unit="$", period="latest quote", as_of=q.get("as_of"), source=src, url=url,
              group="tape")
        if q.get("change_pct") is not None:
            p.add("Change on the day", _f(q["change_pct"], 2), unit="%", period="since the previous close",
                  as_of=q.get("as_of"), source=src, url=url, group="tape")
    if q.get("volume") and q.get("avg_volume"):
        p.add("Volume against its average", _f(q["volume"] / q["avg_volume"], 2), unit="x",
              period="so far today vs the average daily volume", as_of=q.get("as_of"), source=src, url=url, group="tape",
              text="During the session this compares a part-day with a full day, so it understates relative volume early on.")
    if q.get("day_high") and q.get("day_low"):
        p.add("Today's range", text="{} to {}".format(q["day_low"], q["day_high"]), as_of=q.get("as_of"), source=src,
              url=url, group="tape")
    if d.session_state:
        s = d.session_state() or {}
        p.add("Market session", text=s.get("label") or s.get("phase") or "", source="Optic session clock (NYSE hours)",
              group="tape")
    try:
        bars = d.provider.intraday_history(t, period="1d", interval="5m")
        if bars is not None and not bars.empty and "Volume" in bars:
            px = (bars["High"] + bars["Low"] + bars["Close"]) / 3
            vol = bars["Volume"].fillna(0)
            if vol.sum() > 0:
                vwap = float((px * vol).sum() / vol.sum())
                last_bar = str(bars.index[-1])
                p.add("Session VWAP", _f(vwap, 2), unit="$", period="today's 5-minute bars to {}".format(last_bar),
                      source="Yahoo Finance intraday bars", url=url, group="tape",
                      text="The volume-weighted average price of today's trading.")
    except Exception:                                              # noqa: BLE001
        p.missing.append("intraday bars")
    p.not_available.append("Quote size, the order book and the bid-ask spread for the shares.")


def recent_news(p: Pack, d: Deps, t: str, hours: Optional[int] = None, limit: int = 6) -> None:
    if not d.news:
        return
    from .model import cluster
    n = d.news(t) or {}
    rows = [r for r in (n.get("articles") or []) if r.get("about_company", True)]
    if hours:
        cut = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
        rows = [r for r in rows if (r.get("published") or "") >= cut]
    for c in cluster(rows)[:limit]:
        p.add(c.get("title") or "", source=c.get("source") or c.get("publisher") or "",
              url=c.get("url") or c.get("link"), as_of=c.get("published") or c.get("time"), group="news",
              text=("Carried by {} outlets: one report, not separate confirmation.".format(len(c.get("outlets") or []))
                    if len(c.get("outlets") or []) > 1 else ""))


def upcoming(p: Pack, d: Deps, t: Optional[str], days: int = 21) -> None:
    if t:
        try:
            ed = d.provider.earnings_date(t)
            if ed:
                p.add("Next earnings date", text=str(ed), source="Yahoo Finance", group="events",
                      url="https://finance.yahoo.com/quote/{}/analysis".format(t))
        except Exception:                                          # noqa: BLE001
            p.missing.append("earnings date")
        if d.ex_dividend:
            ex = d.ex_dividend(t)
            if ex:
                p.add("Next ex-dividend date", text=str(ex), source="Yahoo Finance", group="events")
    if d.events:
        ev = d.events() or {}
        now = datetime.now(timezone.utc)
        for r in ev.get("events") or []:
            try:
                when = datetime.fromisoformat(r["at"])
            except (KeyError, ValueError, TypeError):
                continue
            if when - now > timedelta(days=days) or r.get("impact") not in ("high", "medium"):
                continue
            prev = r.get("previous") or {}
            p.add(r.get("title") or "", text="Scheduled {}{}".format(
                when.astimezone().strftime("%a %d %b %H:%M"),
                "; previous: {}".format(prev.get("headline")) if isinstance(prev, dict) and prev.get("headline") else ""),
                source="Official release schedule", url=prev.get("url") if isinstance(prev, dict) else None,
                group="events")


def structure(p: Pack, d: Deps, t: str) -> None:
    from .evidence import _bar_moves
    frames = d.provider.batch_history([t, "SPY"], period="1y", interval="1d") or {}
    mv, spy = _bar_moves(frames.get(t)), _bar_moves(frames.get("SPY"))
    src = "Yahoo Finance daily bars"
    url = "https://finance.yahoo.com/quote/{}/chart".format(t)
    if not mv:
        return
    p.add("Close", mv["last"], unit="$", period="daily bar of {}".format(mv["date"]), source=src, url=url, group="structure")
    for label, key in (("Change over 21 sessions", "chg_21d"), ("Distance from the 50-day average", "vs_sma50_pct"),
                       ("Distance from the 200-day average", "vs_sma200_pct")):
        if mv.get(key) is not None:
            p.add(label, mv[key], unit="%", period="to {}".format(mv["date"]), source=src, url=url, group="structure")
    if mv.get("low_20d") and mv.get("high_20d"):
        p.add("Range of the previous 20 sessions", text="{} to {}".format(mv["low_20d"], mv["high_20d"]),
              period="to {}".format(mv["date"]), source=src, url=url, group="structure")
    if spy and mv.get("chg_21d") is not None and spy.get("chg_21d") is not None:
        p.add("Relative to the S&P 500 over 21 sessions", _f(mv["chg_21d"] - spy["chg_21d"], 2), unit="pp",
              period="to {}".format(mv["date"]), source=src, url=url, group="structure")


def macro(p: Pack, d: Deps) -> None:
    codes = [("DGS2", "2-year Treasury yield"), ("DGS10", "10-year Treasury yield"), ("T10Y2Y", "10-year minus 2-year spread"),
             ("DFF", "Effective fed funds rate"), ("CPIAUCSL", "CPI inflation, year over year"),
             ("PCEPILFE", "Core PCE inflation, year over year"), ("UNRATE", "Unemployment rate"),
             ("PAYEMS", "Payrolls, change on the month"), ("ICSA", "Initial jobless claims"),
             ("BAMLH0A0HYM2", "High-yield credit spread")]
    if not d.fred_series:
        return
    for code, label in codes:
        s = d.fred_series(code) or {}
        latest = s.get("latest") or {}
        if latest.get("value") is None:
            p.missing.append("FRED " + code)
            continue
        v = latest["value"] / 1000 if (s.get("unit") == "k" and abs(latest["value"]) >= 10000) else latest["value"]
        p.add(label, _f(v, 3), unit=s.get("unit") or "", period=str(latest.get("date")),
              source="FRED (St. Louis Fed): {}".format(code), url="https://fred.stlouisfed.org/series/{}".format(code),
              group="macro")
    if d.rate_path and d.events:
        r = d.rate_path(d.events() or {}) or {}
        if r.get("available"):
            p.add("Fed funds futures", _f(r.get("probability") if r.get("kind") == "probability" else r.get("basis_points"), 1),
                  unit="%" if r.get("kind") == "probability" else "bp", period=str(r.get("meeting") or r.get("contract_month_label") or ""),
                  source="CME fed funds futures via Yahoo; Optic's arithmetic", group="macro",
                  text=r.get("limit") or "Implied chance of a move at the meeting.")
    p.not_available.append("Consensus forecasts for economic releases (licensed; each release is compared with its previous reading).")


def desk(p: Pack, d: Deps, sec: Dict[str, Any]) -> None:
    if not d.desk_load or not sec:
        return
    ed = d.desk_load(sec.get("key") or "") or {}
    s = next((x for x in ed.get("sections") or [] if x.get("id") == sec.get("section")), None)
    if not s:
        p.missing.append("the Optic Desk section asked about")
        return
    from .check import units
    texts, cites = [], set()
    for path, u in units({"sections": [s]}):
        texts.append(u.get("text") or "")
        cites |= set(u.get("cites") or [])
    p.add("Optic Desk {} ({}), section: {}".format(ed.get("date"), ed.get("slot_label"), s.get("title") or s.get("id")),
          text=" ".join(texts)[:2400], source="Optic Desk edition {}".format(ed.get("key")), group="desk",
          period="information to {}".format(ed.get("cutoff")))
    evm = {e["id"]: e for e in ed.get("evidence") or []}
    now_q: Dict[str, Any] = {}
    syms = [evm[c].get("symbol") for c in cites if c in evm and evm[c].get("kind") in ("index", "sector", "company")
            and evm[c].get("symbol")]
    if syms:
        try:
            now_q = d.provider.batch_quote(syms) or {}
        except Exception:                                          # noqa: BLE001
            now_q = {}
    for c in sorted(cites):
        e = evm.get(c)
        if not e:
            continue
        text = e.get("text") or e.get("method") or ""
        q = now_q.get(e.get("symbol") or "") or {}
        if q.get("last") and q.get("prev_close"):
            text = (text + " Now: {:+.2f}% on the day as of {}.".format((q["last"] / q["prev_close"] - 1) * 100,
                                                                         q.get("as_of"))).strip()
        p.add("[{}] {}".format(c, e.get("label")), e.get("value"), unit=e.get("unit") or "", period=e.get("period") or "",
              source=e.get("source") or "", url=e.get("url"), as_of=e.get("published_at") or e.get("as_of"),
              text=text[:400], group="desk evidence")


# --------------------------------------------------------------- the pack

PLANS: Dict[str, List[str]] = {
    "long_term": ["fundamentals", "valuation", "describe", "filings", "news"],
    "pre_earnings": ["earnings", "fundamentals", "filings_results", "news", "upcoming"],
    "day_trade": ["tape", "news_fresh", "filings_today", "upcoming_short"],
    "swing": ["structure", "upcoming", "news", "valuation"],
    "macro": ["macro", "upcoming_market"],
    "desk": ["desk", "macro"],
}


def build(question: str, ticker: Optional[str], deps: Deps, *, horizon: Optional[str] = None,
          desk_section: Optional[Dict[str, Any]] = None, kind: Optional[str] = None) -> Dict[str, Any]:
    k = kind or intent(question, horizon, ticker, desk_section)
    p = Pack(k, ticker)
    t = (ticker or "").upper() or None
    jobs: Dict[str, Callable[[], None]] = {}
    for step in PLANS.get(k, []):
        if step == "fundamentals" and t:
            jobs[step] = lambda: fundamentals(p, deps, t)
        elif step == "valuation" and t:
            jobs[step] = lambda: valuation(p, deps, t)
        elif step == "describe" and t:
            jobs[step] = lambda: describe(p, deps, t)
        elif step == "filings" and t:
            jobs[step] = lambda: filings(p, deps, t)
        elif step == "filings_results" and t:
            jobs[step] = lambda: filings(p, deps, t, items={"2.02", "7.01", "8.01"})
        elif step == "filings_today" and t:
            jobs[step] = lambda: filings(p, deps, t, limit=2)
        elif step == "earnings" and t:
            jobs[step] = lambda: earnings(p, deps, t)
        elif step == "tape" and t:
            jobs[step] = lambda: tape(p, deps, t)
        elif step == "news" and t:
            jobs[step] = lambda: recent_news(p, deps, t)
        elif step == "news_fresh" and t:
            jobs[step] = lambda: recent_news(p, deps, t, hours=18)
        elif step in ("upcoming", "upcoming_short", "upcoming_market"):
            jobs[step] = lambda s=step: upcoming(p, deps, t if s != "upcoming_market" else None,
                                                 days=5 if s == "upcoming_short" else 21)
        elif step == "structure" and t:
            jobs[step] = lambda: structure(p, deps, t)
        elif step == "macro":
            jobs[step] = lambda: macro(p, deps)
        elif step == "desk":
            jobs[step] = lambda: desk(p, deps, desk_section or {})
    if not jobs:
        return p.out()
    pool = cf.ThreadPoolExecutor(max_workers=min(6, len(jobs)), thread_name_prefix="milo-research")
    futs = {pool.submit(fn): name for name, fn in jobs.items()}
    done, pending = cf.wait(futs, timeout=TIME_BUDGET_SECONDS)
    for f in done:
        exc = f.exception()
        if exc is not None:
            p.missing.append("{} ({})".format(futs[f], type(exc).__name__))
    for f in pending:
        p.missing.append("{} (slower than {:.0f}s, skipped)".format(futs[f], TIME_BUDGET_SECONDS))
    pool.shutdown(wait=False, cancel_futures=True)
    return p.out()
