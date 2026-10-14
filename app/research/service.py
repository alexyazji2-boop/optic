"""Gathers the inputs for one ticker, runs the modes asked for, and keeps their
conclusions apart.

Fetching happens here and only here; the graders (`quality`, `swing_setup`,
`earnings_view`) take plain data, which is what makes them testable. Every
fetch is bounded in time and a slow or failed source becomes a named gap in
`data.gaps`, never a stalled answer or a silent zero.
"""

from __future__ import annotations

import concurrent.futures as cf
import logging
import re
import threading
import time
from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional
from zoneinfo import ZoneInfo

import pandas as pd

from . import METHOD_VERSION, earnings_view, forecasts, policy as policy_mod, quality, swing_setup
from .. import session as session_mod

log = logging.getLogger(__name__)
ET = ZoneInfo("America/New_York")

# The page waits for the panel, so it gets time for a cold cache: the first
# read of a ticker on a fresh server queued behind the page's own load (the
# feed serialises its requests) and every source missed a 20s budget
# (NVDA, 2026-10-14). Milo's hook has its own, shorter limit in main.py.
FETCH_BUDGET_SECONDS = 45.0
CACHE_TTL = 600.0
_CACHE: Dict[str, Any] = {}
_LOCK = threading.Lock()

# The sector ETF each Yahoo sector is measured against for relative strength.
SECTOR_ETF = {
    "Technology": "XLK", "Financial Services": "XLF", "Healthcare": "XLV", "Consumer Cyclical": "XLY",
    "Consumer Defensive": "XLP", "Energy": "XLE", "Industrials": "XLI", "Basic Materials": "XLB",
    "Real Estate": "XLRE", "Utilities": "XLU", "Communication Services": "XLC",
}


# ---------------------------------------------------------------- freshness

_MT = re.compile(r"^\s*(\d{1,2}):(\d{2})\s*([AP]M)", re.I)


def quote_freshness(quote: Dict[str, Any], last_bar: Optional[str], stale_minutes: int,
                    now: Optional[datetime] = None) -> Dict[str, Any]:
    """Whether the price is current for the session it claims.

    During the regular session the feed's own price time is compared with
    the clock, allowing for the usual fifteen-minute delay. Outside it the
    price is a close or an extended-hours print and is labelled as such."""
    now = now or datetime.now(timezone.utc)
    st = session_mod.state(now)
    phase = st.get("phase")
    mt = (quote or {}).get("market_time")
    out: Dict[str, Any] = {"phase": phase, "session_label": st.get("label"), "market_time": mt,
                           "last_completed_bar": last_bar}
    if phase != "regular":
        out.update({"state": "closed_session",
                    "text": "Market {}: the price is the last regular close{}.".format(
                        (st.get("label") or "closed").lower(),
                        " or an extended-hours print" if phase in ("pre", "after", "overnight") else "")})
        return out
    m = _MT.match(mt or "")
    if not m:
        # No price time (the feed's quote-summary path, which carries it, is
        # the one Yahoo throttles first). The bars still say whether today has
        # traded in the data at all.
        today = now.astimezone(ET).date().isoformat()
        if last_bar and last_bar < today:
            out.update({"state": "stale", "text": "Regular session, but the daily bars stop at {}: today's trading "
                                                   "is not in the data yet.".format(last_bar)})
        else:
            out.update({"state": "delayed", "text": "Regular session; the feed gave no price time, so its exact "
                                                     "age is unknown (normally about 15 minutes delayed)."})
        return out
    h, mi, ap = int(m.group(1)) % 12, int(m.group(2)), m.group(3).upper()
    h += 12 if ap == "PM" else 0
    et_now = now.astimezone(ET)
    stamp = et_now.replace(hour=h, minute=mi, second=0, microsecond=0)
    age = (et_now - stamp).total_seconds() / 60.0
    if age < -5:
        age += 24 * 60  # a stamp from the previous day
    limit = stale_minutes + 15
    out["age_minutes"] = round(age)
    if age > limit:
        out.update({"state": "stale", "text": "The last price is {:.0f} minutes old in an open session (the feed is "
                                               "normally about 15 minutes delayed).".format(age)})
    else:
        out.update({"state": "delayed", "text": "Regular session, price about {:.0f} minutes old (delayed "
                                                 "feed).".format(max(age, 0))})
    return out


def completed_bars(daily: Optional[pd.DataFrame], phase: Optional[str], now: Optional[datetime] = None) -> Optional[pd.DataFrame]:
    """Daily bars with today's forming bar removed while the session is open,
    so every reading is a closed candle."""
    if daily is None or daily.empty:
        return daily
    today = (now or datetime.now(timezone.utc)).astimezone(ET).date()
    if phase == "regular" and daily.index[-1].date() == today:
        return daily.iloc[:-1]
    return daily


# ---------------------------------------------------------------- gathering

class _Gather:
    def __init__(self, budget: float) -> None:
        self.pool = cf.ThreadPoolExecutor(max_workers=8)
        self.jobs: Dict[str, cf.Future] = {}
        self.deadline = time.monotonic() + budget
        self.gaps: List[str] = []

    def start(self, name: str, fn: Callable[..., Any], *a: Any, **k: Any) -> None:
        self.jobs[name] = self.pool.submit(fn, *a, **k)

    def get(self, name: str) -> Any:
        fut = self.jobs.get(name)
        if fut is None:
            return None
        try:
            return fut.result(timeout=max(0.1, self.deadline - time.monotonic()))
        except cf.TimeoutError:
            self.gaps.append("{} did not answer in time".format(name))
        except Exception as exc:                                                  # noqa: BLE001
            self.gaps.append("{} failed ({})".format(name, str(exc)[:80]))
        return None

    def close(self) -> None:
        self.pool.shutdown(wait=False, cancel_futures=True)


def _needs(mode: str) -> Dict[str, bool]:
    lt = mode in ("long_term", "combined")
    sw = mode in ("swing", "combined")
    er = mode in ("pre_earnings", "post_earnings", "combined", "earnings")
    return {"long_term": lt, "swing": sw, "earnings": er}


def build(provider, yf, ticker: str, mode: str = "combined", *, rate: float = 0.0,
          vol_event: Optional[Dict[str, Any]] = None, now: Optional[datetime] = None,
          save_forecast: bool = True, with_comps: Optional[bool] = None, overrides: Optional[Dict[str, Any]] = None,
          deps: Optional[Dict[str, Callable[..., Any]]] = None,
          budget: float = FETCH_BUDGET_SECONDS) -> Dict[str, Any]:
    """The research framework's output for one ticker.

    `mode` is long_term, swing, pre_earnings, post_earnings, earnings (pre or
    post by the calendar) or combined. `deps` lets tests and the route inject
    the module functions that fetch (longterm, valuation, sec, news, earnings).
    """
    sym = (ticker or "").upper().strip()
    mode = mode if mode in ("long_term", "swing", "pre_earnings", "post_earnings", "earnings", "combined") else "combined"
    key = "{}:{}".format(sym, mode)
    if now is None and not overrides:
        with _LOCK:
            hit = _CACHE.get(key)
        if hit and time.time() - hit[0] < CACHE_TTL:
            return hit[1]
    # Peers cost one quote-feed lookup each (eight), so they are read for a
    # long-term question and left out of the Overview's combined read, which
    # runs on every visit; the fair-value workspace has them on request.
    if with_comps is None:
        with_comps = mode == "long_term"
    pol = policy_mod.current(overrides)
    vals = pol["values"]
    d = _deps(deps)
    need = _needs(mode)
    g = _Gather(budget)
    g.yf = yf
    try:
        g.start("quote", provider.quote, sym)
        if need["swing"] or need["earnings"]:
            g.start("daily", yf.history, sym, period="2y", interval="1d")
            g.start("spy", yf.history, "SPY", period="2y", interval="1d")
        if need["earnings"]:
            g.start("earnings", d["earnings"], provider, yf, sym, rate)
        elif need["swing"]:
            # A swing read needs only the date and its timing, not the chain:
            # the calendar and the surprise table are cached feed reads.
            g.start("earnings", d["earnings_dates"], yf, sym)
        if need["earnings"]:
            g.start("sec", d["sec"], sym)
            g.start("financials", yf.financials, sym)
            g.start("news", d["news"], yf, sym)
        if need["long_term"] or need["earnings"]:
            g.start("longterm", d["longterm"], yf, sym)
        if need["long_term"]:
            g.start("valuation", d["valuation"], yf, sym)
            g.start("gathered", d["gathered"], yf, sym)
            g.start("splits", yf.splits, sym)
            if with_comps:
                g.start("comps", d["comps"], yf, sym)
        quote = g.get("quote") or {}
        out: Dict[str, Any] = {
            "available": True, "ticker": sym, "name": quote.get("name"), "mode": mode,
            "method_version": METHOD_VERSION, "policy": {"version": pol["version"], "changed": pol["changed"],
                                                         "ignored": pol["ignored"]},
            "generated_at": (now or datetime.now(timezone.utc)).isoformat(timespec="seconds"),
            "price": quote.get("price"),
        }
        daily_raw = g.get("daily") if (need["swing"] or need["earnings"]) else None
        fresh = quote_freshness(quote, str(daily_raw.index[-1].date()) if daily_raw is not None and
                                not daily_raw.empty else None, int(vals["quote_stale_minutes"]), now)
        out["freshness"] = fresh
        ea = g.get("earnings") if (need["earnings"] or need["swing"]) else None
        lt = g.get("longterm") if (need["long_term"] or need["earnings"]) else None
        spy_raw = g.get("spy") if (need["swing"] or need["earnings"]) else None
        daily = completed_bars(daily_raw, fresh.get("phase"), now)
        spy = completed_bars(spy_raw, fresh.get("phase"), now)
        if need["long_term"]:
            out["long_term"] = _long_term(g, lt, vals)
            if not out["long_term"].get("available") and _missed(g, "gathered", "valuation"):
                out["long_term"]["conviction"]["why"] = ("The company's filings did not load in time ({}). Try "
                                                         "again in a moment.".format(_missed(g, "gathered", "valuation")))
        if need["swing"]:
            out["swing"] = _swing(yf, daily, spy, ea, fresh, quote, vals)
        if need["earnings"]:
            out["earnings"] = _earnings(sym, mode, ea, g, daily, spy, lt, quote, fresh, vol_event, vals, pol,
                                        save_forecast, now, daily_raw=daily_raw, spy_raw=spy_raw)
            if ea is None and _missed(g, "earnings"):
                out["earnings"] = {"available": False,
                                   "reason": "Earnings data did not load in time ({}). Try again in a moment.".format(
                                       _missed(g, "earnings"))}
        if mode == "combined":
            out["combined"] = agreement(out)
        out["data"] = {"gaps": g.gaps, "sources": SOURCES}
        out["limitations"] = LIMITATIONS
    finally:
        g.close()
    # A read with a missing source is never cached: the next request should
    # try again rather than serve the gap for ten minutes.
    if now is None and not overrides and not out["data"]["gaps"]:
        with _LOCK:
            _CACHE[key] = (time.time(), out)
    return out


def _calendar(g: "_Gather", sym: str) -> Optional[Dict[str, Any]]:
    """The feed's earnings calendar (a cached read), for the second consensus
    figure a post-earnings audit has to reconcile."""
    yf = getattr(g, "yf", None)
    if yf is None or not hasattr(yf, "earnings_calendar"):
        return None
    try:
        return yf.earnings_calendar(sym)
    except Exception:                                                              # noqa: BLE001
        return None


def _missed(g: "_Gather", *names: str) -> str:
    hits = [gap for gap in g.gaps if any(gap.startswith(n + " ") for n in names)]
    return "; ".join(hits)


SOURCES = {
    "statements": "SEC EDGAR XBRL company facts (us-gaap), each figure linked to its filing",
    "prices": "Yahoo Finance daily bars and quote (delayed about 15 minutes in session)",
    "estimates": "Yahoo Finance analyst consensus, estimate trend and surprise history",
    "options": "The options chain's at-the-money straddle on the first expiry after the release",
    "risk_free": "10-year US Treasury yield (FRED) for the valuation; 13-week bill for options",
    "news": "Yahoo Finance headlines, word-list tagged",
}

LIMITATIONS = [
    "No company guidance text, call transcripts or segment-level consensus: those are in the release and the call.",
    "Moat evidence is measured from the accounts; what the advantage is needs the annual report.",
    "Grades and conviction labels follow stated framework rules; none has been shown to predict returns.",
    "Debt maturities beyond the next year are not read from the filings.",
]


def _deps(deps: Optional[Dict[str, Callable[..., Any]]]) -> Dict[str, Callable[..., Any]]:
    out: Dict[str, Callable[..., Any]] = {}

    def lazy_longterm(yf, sym):
        from ..analytics import longterm
        return longterm.analyse_holding(yf, sym)

    def lazy_valuation(yf, sym):
        from ..valuation import service as vs
        return vs.build(yf, sym)

    def lazy_gathered(yf, sym):
        from ..valuation import service as vs
        return vs.gathered(yf, sym)

    def lazy_comps(yf, sym):
        from ..valuation import service as vs
        return vs.comps(yf, sym)

    def lazy_sec(sym):
        from ..analytics import sec_facts
        return sec_facts.history(sym)

    def lazy_news(yf, sym):
        from .. import news
        return news.analyse(yf, sym)

    def lazy_earnings(provider, yf, sym, rate):
        from ..analytics import earnings
        quote = provider.quote(sym)
        return earnings.analyse(provider, yf, sym, quote, rate=rate)

    def lazy_dates(yf, sym):
        from ..analytics import earnings
        hist = yf.earnings_history(sym, limit=16) or []
        cal = yf.earnings_calendar(sym) or {}
        reported = {str(r.get("date")) for r in hist if r.get("eps_reported") is not None}
        return {"next_report": earnings._next_report(hist, cal, reported)}

    out.update({"earnings_dates": lazy_dates, "longterm": lazy_longterm, "valuation": lazy_valuation, "gathered": lazy_gathered,
                "comps": lazy_comps, "sec": lazy_sec, "news": lazy_news, "earnings": lazy_earnings})
    out.update(deps or {})
    return out


# ---------------------------------------------------------------- modes

def _wacc(val: Dict[str, Any]) -> Optional[float]:
    w = ((val.get("dcf") or {}).get("wacc") or {}).get("wacc")
    if w is not None:
        return float(w)
    try:
        from ..valuation import defaults
        return float(defaults.compute_wacc(val["wacc_parts_default"], val["base"])["wacc"])
    except Exception:                                                              # noqa: BLE001
        return None


def _long_term(g: _Gather, lt: Optional[Dict[str, Any]], vals: Dict[str, Any]) -> Dict[str, Any]:
    val = g.get("valuation") or {}
    data = g.get("gathered") or {}
    comps = g.get("comps")
    if not data.get("available"):
        return {"available": False, "conviction": {"label": "Insufficient Data",
                                                   "why": data.get("reason") or val.get("reason") or
                                                   "The filings could not be read."}}
    kind = ((val.get("classification") or {}).get("business_type")) or "operating"
    q = quality.business_quality(data, kind, _wacc(val), val.get("cost_of_equity"), vals, splits=g.get("splits"))
    growth = next((c for c in q.get("components") or [] if c["id"] == "growth"), {})
    vg = quality.valuation_grade(val, data, lt or {}, comps, kind, (growth.get("figures") or {}).get("revenue_cagr"))
    chart = quality.chart_context(lt or {}, quality.weekly_volume_read(_weekly_from_lt(lt)))
    conv = quality.conviction(q, vg, chart, vals)
    zones = quality.accumulation_zones(lt or {}, q, vg, conv)
    bull = bear = None
    sc = val.get("scenarios") or {}
    if sc.get("bull") and sc.get("bear"):
        bull = {"per_share": sc["bull"].get("per_share"), "text": "Growth above the base path, higher margins, "
                "lighter capex (the DCF bull case)."}
        bear = {"per_share": sc["bear"].get("per_share"), "text": "Growth below the base path, lower margins, "
                "heavier capex (the DCF bear case)."}
    return {
        "available": True, "business_type": kind,
        "business_type_label": (val.get("classification") or {}).get("label"),
        "quality": q, "valuation": vg, "chart": chart, "conviction": conv,
        "accumulation": zones, "scenarios": {"bull": bull, "bear": bear},
        "loss_paths": quality.loss_paths(data, q, vg, lt or {}, kind),
        "policy_note": "Business quality below {} caps conviction at Neutral: a configurable rule "
                       "(quality_cap_grade), not a finding.".format(vals["quality_cap_grade"]),
        "separation_note": "Business quality and valuation are graded separately: a strong business can be an "
                           "expensive stock, and the chart's weakness is not by itself a failed business thesis.",
        "sources": {"filings": data.get("source_note"), "valuation_model": val.get("model_version"),
                    "fy_ends": data.get("fy_ends"), "warnings": data.get("warnings")},
    }


def _weekly_from_lt(lt: Optional[Dict[str, Any]]) -> Optional[pd.DataFrame]:
    s = ((lt or {}).get("long_trend") or {}).get("series") or {}
    if not s.get("dates") or not s.get("volume"):
        return None
    try:
        return pd.DataFrame({"Close": s["close"], "Volume": s["volume"]}, index=pd.to_datetime(s["dates"]))
    except Exception:                                                              # noqa: BLE001
        return None


def _earn_dates(ea: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    nr = (ea or {}).get("next_report") or {}
    return {"date": nr.get("date"), "confirmed": nr.get("confirmed"), "timing": nr.get("timing")}


def _swing(yf, daily, spy, ea, fresh, quote, vals) -> Dict[str, Any]:
    sector_sym = SECTOR_ETF.get((quote or {}).get("sector") or "")
    sector = None
    if sector_sym:
        try:
            sector = completed_bars(yf.history(sector_sym, period="2y", interval="1d"), fresh.get("phase"))
        except Exception:                                                          # noqa: BLE001
            sector = None
    return swing_setup.assess(daily, spy, vals, earnings=_earn_dates(ea), freshness=fresh,
                              sector=sector, sector_symbol=sector_sym)


def _earnings(sym, mode, ea, g, daily, spy, lt, quote, fresh, vol_event, vals, pol, save_forecast, now,
              daily_raw=None, spy_raw=None):
    if not ea or ea.get("not_applicable"):
        return {"available": False, "reason": (ea or {}).get("reason") or "No earnings data for this symbol."}
    lr = ea.get("latest_result") or {}
    nr = ea.get("next_report") or {}
    today = (now or datetime.now(timezone.utc)).astimezone(ET).date()
    since = None
    if lr.get("date"):
        try:
            since = (today - date.fromisoformat(str(lr["date"])[:10])).days
        except ValueError:
            since = None
    which = mode
    if mode in ("earnings", "combined"):
        recent = since is not None and 0 <= since <= int(vals["post_earnings_window_days"])
        which = "post_earnings" if recent else "pre_earnings"
    sec, fin = g.get("sec"), (g.get("financials") or {}).get("income_quarterly")
    bench_state = None
    if spy is not None and not spy.empty and len(spy) > 200:
        c = spy["Close"].astype(float)
        last, m50, m200 = c.iloc[-1], c.tail(50).mean(), c.tail(200).mean()
        bench_state = "risk-on" if last > m50 and last > m200 else "risk-off" if last < m50 and last < m200 else "mixed"
    out: Dict[str, Any] = {"which": which}
    if which == "pre_earnings":
        pre = earnings_view.pre_earnings(sym, ea, sec=sec, fin_q=fin, daily=daily, bench=spy,
                                         val_hist=(lt or {}).get("valuation_history"), vol_event=vol_event,
                                         news=g.get("news"), bench_state=bench_state, spot=quote.get("price"),
                                         industry=(quote or {}).get("industry"))
        if pre.get("available") and save_forecast:
            pre["saved"] = forecasts.save(sym, pre, METHOD_VERSION, pol["version"], now=now)
        out["pre"] = pre
    else:
        saved = forecasts.for_release(sym, lr.get("date")) if lr.get("date") else None
        # The reaction reads the raw bars, forming one included: on the day of a
        # release before the open, today's bar IS the reaction, and the
        # completed-bar series used for indicators does not have it yet (JPM,
        # 2026-10-14: "the reaction session has not traded yet" at 12:45).
        post = earnings_view.post_earnings(sym, ea, float(vals["inline_band_pct"]), sec=sec, fin_q=fin,
                                           daily=daily_raw if daily_raw is not None else daily,
                                           bench=spy_raw if spy_raw is not None else spy, quote=quote,
                                           phase=fresh.get("phase"), forecast=saved, today=today,
                                           industry=(quote or {}).get("industry"), calendar=_calendar(g, sym))
        rx = post.get("reaction") or {}
        rv = post.get("forecast_review") or {}
        if saved and rx.get("observation") == "completed session" and rv.get("available"):
            forecasts.record_outcome(saved["id"], {"eps": post["headline_audit"]["eps"], "reaction": rx}, rv, now=now)
        out["post"] = post
    out["next_report"] = {"date": nr.get("date"), "confirmed": nr.get("confirmed"), "timing": nr.get("timing")}
    return out


# ---------------------------------------------------------------- combined

FAVOURABLE_LT = ("High Conviction", "Constructive")
FAVOURABLE_SW = ("S", "A")


def agreement(out: Dict[str, Any]) -> Dict[str, Any]:
    """Where the separate assessments agree and disagree, in plain English."""
    lt = out.get("long_term") or {}
    sw = out.get("swing") or {}
    er = out.get("earnings") or {}
    lines: List[str] = []
    conv = (lt.get("conviction") or {}).get("label") or "Insufficient Data"
    q = (lt.get("quality") or {}).get("grade")
    v = (lt.get("valuation") or {}).get("label")
    grade = sw.get("grade") or "Insufficient Data"
    lines.append("Long term: {}{}.".format(conv, " (business quality {}, valuation {})".format(q, (v or "not graded").lower())
                                            if q else ""))
    lines.append("Swing: {}. {}".format(grade, sw.get("why") or ""))
    pre, post = er.get("pre") or {}, er.get("post") or {}
    if pre.get("available"):
        lines.append("Earnings ({}): {}".format(pre["release"]["date"], pre["view"].get("headline")))
    elif post.get("available"):
        qg = (post.get("quality") or {}).get("grade")
        lines.append("Earnings just reported ({}): report quality {}; {}".format(
            post["release"]["date"], qg or "not graded", (post.get("reaction") or {}).get("text") or ""))
    lt_good, sw_good = conv in FAVOURABLE_LT, grade in FAVOURABLE_SW
    missing = [name for name, ok in (("the long-term view", lt.get("available") is not False and conv != "Insufficient Data"),
                                     ("the swing setup", grade != "Insufficient Data")) if not ok]
    if missing:
        return {"lines": lines,
                "verdict": "{} could not be graded here, so there is no agreement to report; each assessment that "
                           "did load stands on its own.".format(" and ".join(missing).capitalize()),
                "note": "Each assessment answers its own question; none is averaged into the others."}
    if lt_good and sw_good:
        verdict = ("They agree: the business, the price and the chart all lean the same way. Agreement is not "
                   "extra certainty; each still has its own way of being wrong.")
    elif lt_good and not sw_good:
        verdict = ("They disagree, and that is normal. The long-term view is about years of cash flows at today's "
                   "valuation; the swing grade is about the next few weeks' reward against risk at today's price. A "
                   "good company can be a poor trade right now{}.".format(
                       " because " + (sw.get("most_damaging") or {}).get("text", "").rstrip(".").lower()
                       if sw.get("most_damaging") else ""))
    elif sw_good and not lt_good:
        verdict = ("A tradeable setup in a business the framework would not hold for years ({}). The trade rests on "
                   "price behaviour, so its stop matters more than the business case, and a weak report could break "
                   "it.".format(conv.lower()))
    else:
        verdict = "Neither the long-term case nor the trade stands out on the evidence here."
    exp = ((sw.get("plan") or {}).get("earnings") or {})
    if exp.get("in_window"):
        verdict += (" The release on {} falls inside any swing window: event risk a long-term holder can absorb but "
                    "a stop cannot.".format(exp.get("date")))
    return {"lines": lines, "verdict": verdict,
            "note": "Each assessment answers its own question; none is averaged into the others."}
