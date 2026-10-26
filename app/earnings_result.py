"""When a report lands, and what a released one said: for Home's What Matters Today.

Asked for on 2026-10-26 with screenshots of the week strip. "FCX reports
Tuesday" did not say whether the market would trade on it that morning or the
next, and "EPS 1.31 against 1.27 expected: beat by 2.8%" was the whole read of
a released result.

**The session is never guessed.** Two sources say it, and each is used only
where it has shown it can be trusted:

- Yahoo's quote carries the scheduled report's time and its call's. On a date
  Yahoo has confirmed, 37 of 37 names reporting the week of 2026-10-26 sat at
  8:30 AM or 4 PM and agreed with each company's last four reports. The
  unscheduled ones (AAPL, NVDA, AMD) sat at 3 PM, inside the session, which no
  company reporting before the open or after the close would choose. So a time
  inside the session is read as no time, and a call that contradicts the
  report's side of the close cancels it.
- The surprise table stamps a released report with its time. That is what the
  Earnings tab's reaction already reads; here it must also agree with the
  quote's time for the same day where the quote has one.

A company's habit (it has reported after the close four times running) is not
this report's time, and is not used as one.

**Revenue against its estimate needs a record Optic keeps itself.** Once a
company reports, Yahoo moves its consensus to the next quarter: on 2026-10-26,
hours after Verizon reported, the calendar still dated the report that morning
but its revenue estimate was Q4's (its year-ago figure was December's). So the
estimate is recorded here before the report, and a recorded estimate is used
only if its EPS consensus matches the surprise table's estimate for the
quarter, which is what shows it was this quarter's.
"""

from __future__ import annotations

import json
import logging
import os
import threading
from datetime import date as date_cls, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from . import session as session_mod

log = logging.getLogger(__name__)
ET = session_mod.ET

OPEN_MIN = 9 * 60 + 30
CLOSE_MIN = 16 * 60

LABEL = {"before_open": "Before the open", "after_close": "After the close"}
SHORT = {"before_open": "Before open", "after_close": "After close"}

# Within 1% either way is in line, the rule the panel already used for EPS.
IN_LINE_PCT = 1.0
# A revenue estimate this far from the filed figure is almost always on another
# basis (a bank's managed revenue against its GAAP total), not a surprise.
BASIS_GAP_PCT = 15.0
# How far the recorded EPS consensus may sit from the surprise table's final
# estimate and still be the same quarter's. Consensus drifts a cent or two in
# the last days; a quarter apart is usually 5% or more (VZ: 1.16 against 1.27).
MATCH_PCT = 4.0
MATCH_ABS = 0.02

_DATA_DIR = os.environ.get(
    "TRACKER_DATA_DIR",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data"),
)
STORE_PATH = os.path.join(_DATA_DIR, "earnings_consensus.json")
_LOCK = threading.Lock()


def _et(stamp: Any) -> Optional[datetime]:
    try:
        when = datetime.fromisoformat(str(stamp))
    except (TypeError, ValueError):
        return None
    if when.tzinfo is None:
        return None
    return when.astimezone(ET)


def session_of(stamp: Any) -> Optional[str]:
    """Before the open or after the close, from a report's time, or None when
    the time cannot say: midnight is no time, and inside the session is
    Yahoo's placeholder far more often than a midday report."""
    when = _et(stamp)
    if when is None:
        return None
    m = when.hour * 60 + when.minute
    if m == 0 or OPEN_MIN <= m < CLOSE_MIN:
        return None
    return "before_open" if m < OPEN_MIN else "after_close"


def scheduled_session(cal: Dict[str, Any], day: str, confirmed_only: bool = True) -> Optional[str]:
    """The session Yahoo's quote gives the report on `day`, or None."""
    if confirmed_only and cal.get("date_is_estimate") is not False:
        return None
    stamp = next((t for t in cal.get("report_times") or [] if (_et(t) and _et(t).date().isoformat() == day)), None)
    side = session_of(stamp)
    call = _et(cal.get("call_at"))
    if side and call and call.date().isoformat() == day:
        m = call.hour * 60 + call.minute
        # A call before the close after a report after it, or the other way
        # round, means one of the two times is wrong; neither is used.
        if (side == "after_close" and m < CLOSE_MIN) or (side == "before_open" and m >= CLOSE_MIN):
            return None
    return side


def released_session(row: Optional[Dict[str, Any]], cal: Dict[str, Any], day: str) -> Optional[str]:
    """The session of a report that is out: the surprise table's stamp, unless
    the quote's time for that day says otherwise."""
    stamped = session_of((row or {}).get("at"))
    quoted = scheduled_session(cal, day, confirmed_only=False)
    if stamped and quoted and stamped != quoted:
        return None
    return stamped or quoted


# ------------------------------------------------------- the recorded estimate


def _cutoff(day: str, side: Optional[str]) -> Optional[datetime]:
    """The last moment an estimate can be recorded as this report's. Before the
    open, the report day's midnight; after the close, half an hour before it.
    Unknown, midnight too, so a report at 7 AM cannot be recorded after it."""
    try:
        d = date_cls.fromisoformat(day)
    except (TypeError, ValueError):
        return None
    if side == "after_close":
        return datetime(d.year, d.month, d.day, 15, 30, tzinfo=ET)
    return datetime(d.year, d.month, d.day, tzinfo=ET)


def record_consensus(symbol: str, day: str, cal: Dict[str, Any], side: Optional[str],
                     now: Optional[datetime] = None, path: Optional[str] = None) -> bool:
    """Keep Yahoo's consensus for a report still to come, newest wins, until the
    cutoff. True when it was written."""
    when = (now or datetime.now(timezone.utc)).astimezone(ET)
    cut = _cutoff(day, side)
    if cut is None or when >= cut or day not in [str(d)[:10] for d in cal.get("dates") or []]:
        return False
    if cal.get("eps_avg") is None and cal.get("revenue_avg") is None:
        return False
    target = path or STORE_PATH
    with _LOCK:
        data = _read(target)
        data["{}|{}".format(symbol, day)] = {
            "eps_avg": cal.get("eps_avg"), "revenue_avg": cal.get("revenue_avg"),
            "revenue_low": cal.get("revenue_low"), "revenue_high": cal.get("revenue_high"),
            "recorded_at": when.isoformat(timespec="minutes"),
        }
        # Two quarters is plenty: a record is read only in the week it reports.
        keep = (when.date() - timedelta(days=200)).isoformat()
        data = {k: v for k, v in data.items() if k.split("|")[-1] >= keep}
        try:
            os.makedirs(os.path.dirname(target), exist_ok=True)
            tmp = target + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(data, fh, sort_keys=True)
            os.replace(tmp, target)
        except OSError as exc:
            log.warning("earnings consensus: could not record %s: %s", symbol, exc)
            return False
    return True


def _read(path: str) -> Dict[str, Any]:
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def recorded_consensus(symbol: str, day: str, path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    return _read(path or STORE_PATH).get("{}|{}".format(symbol, day))


# ------------------------------------------------------------- the result


def _matches(rec_eps: Optional[float], est: Optional[float]) -> bool:
    """A recorded consensus is this quarter's when its EPS sits on the surprise
    table's estimate for the report."""
    return (rec_eps is not None and est is not None
            and (abs(rec_eps - est) <= MATCH_ABS or abs(rec_eps - est) / abs(est) * 100.0 <= MATCH_PCT))


def released_estimates(symbol: str, day: str, row: Optional[Dict[str, Any]],
                       path: Optional[str] = None) -> Dict[str, Any]:
    """The street's estimates for a report already out, never Yahoo's live
    consensus, which has moved to the next quarter by then. EPS is the surprise
    table's for that report, or Optic's record from before it when the table
    is late; revenue only from that record. `note` says what is missing."""
    est = _num((row or {}).get("eps_estimate"))
    rec = recorded_consensus(symbol, day, path)
    rec_eps = _num((rec or {}).get("eps_avg"))
    rec_rev = _num((rec or {}).get("revenue_avg"))
    # With no table row yet the record stands alone; it was kept for this date,
    # before its cutoff, so it is this report's.
    usable = rec is not None and (_matches(rec_eps, est) if est is not None else rec_eps is not None)
    out: Dict[str, Any] = {
        "eps": est if est is not None else (rec_eps if usable else None),
        "eps_source": "surprise_table" if est is not None else ("recorded" if usable else None),
        "revenue": rec_rev if usable else None,
        "note": None,
    }
    if out["eps"] is None:
        out["note"] = ("Reported. Yahoo has moved its estimates to the next quarter and Optic had not "
                       "recorded this quarter's before the release.")
    elif out["revenue"] is None:
        out["note"] = ("Revenue estimate not recorded before the release; Yahoo's current one is the "
                       "next quarter's." if not usable else "Yahoo had no revenue estimate for this quarter.")
    return out




def _num(v: Any) -> Optional[float]:
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return None if x != x else x


def _money(v: float) -> str:
    a = abs(v)
    for size, unit in ((1e12, "T"), (1e9, "B"), (1e6, "M")):
        if a >= size:
            return "${:.2f}{}".format(v / size, unit)
    return "${:,.0f}".format(v)


def _verdict(actual: float, estimate: Optional[float]) -> Tuple[Optional[str], Optional[float]]:
    if estimate is None or estimate == 0:
        return None, None
    pct = (actual - estimate) / abs(estimate) * 100.0
    if abs(pct) <= IN_LINE_PCT:
        return "in line", pct
    return ("beat" if pct > 0 else "missed"), pct


def _day(iso: Any) -> Optional[date_cls]:
    try:
        return date_cls.fromisoformat(str(iso)[:10])
    except (TypeError, ValueError):
        return None


def _when_words(d: date_cls) -> str:
    return "{} {} {}".format(d.strftime("%a"), d.strftime("%b"), d.day)


def sec_history(symbol: str) -> Dict[str, Any]:
    """SEC's filed quarters. A name of its own so the suite can stand it in."""
    from .analytics import sec_facts
    return sec_facts.history(symbol)


def _reported_revenue(provider, symbol: str, day: str) -> Dict[str, Any]:
    """The quarter's revenue and the same quarter a year before, from Yahoo's
    quarterly statement or else the SEC filing, for the quarter that ended in
    the 95 days before the report (the one before it ended at least 98 days
    earlier for a company reporting a week after its quarter)."""
    rd = _day(day)
    out: Dict[str, Any] = {}
    try:
        fin = provider.financials(symbol) or {}
    except Exception:                                                      # noqa: BLE001
        fin = {}
    block = fin.get("income_quarterly") or {}
    rows = block.get("rows") or {}
    from .analytics import fundamentals as fundamentals_mod
    vals = next((rows[k] for k in (*fundamentals_mod.ROW_ALIASES.get("revenue", ()), "Total Revenue", "TotalRevenue")
                 if k in rows), None)
    periods = block.get("periods") or []
    fy = ((fin.get("income_annual") or {}).get("periods") or [None])[0]
    out["fy_end"] = fy
    if rd and vals:
        for i, p in enumerate(periods):
            pe = _day(p)
            if pe and 0 < (rd - pe).days <= 95 and i < len(vals) and _num(vals[i]):
                out.update(value=_num(vals[i]), period_end=p, source="Yahoo Finance quarterly statement")
                for j, q in enumerate(periods):
                    qe = _day(q)
                    if qe and 355 <= (pe - qe).days <= 375 and j < len(vals) and _num(vals[j]):
                        out["year_ago"] = _num(vals[j])
                break
    if out.get("value") is not None and out.get("year_ago") is not None:
        return out
    try:
        sec = sec_history(symbol) or {}
    except Exception:                                                      # noqa: BLE001
        sec = {}
    if not sec.get("available") or not rd:
        return out
    for q in reversed(sec.get("revenue_quarters") or []):
        pe = _day(q.get("period_end"))
        if pe and 0 < (rd - pe).days <= 95 and _num(q.get("value")):
            if out.get("value") is None:
                out.update(value=_num(q["value"]), period_end=q["period_end"],
                           source="SEC filing (XBRL)" + (", derived from the annual report" if q.get("derived") else ""))
            yoy = next((y for y in sec.get("revenue_yoy") or [] if y.get("period_end") == q["period_end"]), None)
            if yoy and _num(yoy.get("prior")) and out.get("year_ago") is None:
                out["year_ago"] = _num(yoy["prior"])
            break
    return out


def _reaction(provider, symbol: str, day: str, side: Optional[str], now: datetime) -> Dict[str, Any]:
    """The move in the session that reacted to the report, or the move so far."""
    if side is None:
        return {"available": False, "reason": ("The feed gives no time for this report, so it is not known whether "
                                               "that day's session or the next one reacted to it.")}
    rd = _day(day)
    if rd is None:
        return {"available": False, "reason": "No report date to measure from."}
    react = rd if side == "before_open" and session_mod.regular_close(rd) else session_mod.next_trading_day(rd)
    close_at = session_mod.regular_close(react)
    opened = datetime(react.year, react.month, react.day, 9, 30, tzinfo=ET)
    when = _when_words(react)
    if close_at is not None and now >= close_at:
        try:
            hist = provider.history(symbol, period="1mo")
        except Exception:                                                  # noqa: BLE001
            hist = None
        try:
            closes = hist["Close"].dropna()
            idx = [d.date() for d in closes.index]
            i = idx.index(react)
            if i > 0:
                move = (float(closes.iloc[i]) / float(closes.iloc[i - 1]) - 1.0) * 100.0
                return {"available": True, "kind": "session", "move_pct": round(move, 2), "session": react.isoformat(),
                        "text": "{} {:.1f}% in the session that reacted ({}).".format(
                            "Up" if move > 0 else "Down" if move < 0 else "Flat", abs(move), when)}
        except Exception:                                                  # noqa: BLE001
            pass
        q = _quote(provider, symbol)
        pct = _num(q.get("change_pct"))
        if now.date() == react and pct is not None:
            # today's bar not in the daily history yet; the quote's day move is the same session
            return {"available": True, "kind": "session", "move_pct": round(pct, 2), "session": react.isoformat(),
                    "text": "{} {:.1f}% in the session that reacted ({}).".format(
                        "Up" if pct > 0 else "Down" if pct < 0 else "Flat", abs(pct), when)}
        return {"available": False, "reason": "The daily prices for {} have not reached Optic yet.".format(when)}
    q = _quote(provider, symbol)
    if opened <= now:
        pct = _num(q.get("change_pct"))
        if pct is None:
            return {"available": False, "reason": "No quote to read the move from."}
        return {"available": True, "kind": "so_far", "move_pct": round(pct, 2), "session": react.isoformat(),
                "text": "{} {:.1f}% so far today; the session that reacts is still trading.".format(
                    "Up" if pct > 0 else "Down" if pct < 0 else "Flat", abs(pct))}
    legs = [("post", "post_market_change_pct", "after hours"), ("pre", "pre_market_change_pct", "before the open")]
    if now.date() == react:
        legs.reverse()                     # the morning's pre-market price is the newer read
    for kind, key, words in legs:
        pct = _num(q.get(key))
        if pct is not None:
            return {"available": True, "kind": kind, "move_pct": round(pct, 2), "session": react.isoformat(),
                    "text": "{} {:.1f}% {}, on thin volume; the session that reacts ({}) has not opened.".format(
                        "Up" if pct > 0 else "Down" if pct < 0 else "Flat", abs(pct), words, when)}
    return {"available": False, "reason": "The session that reacts ({}) has not opened, and there is no "
                                          "extended-hours quote.".format(when)}


def _quote(provider, symbol: str) -> Dict[str, Any]:
    try:
        return provider.quote(symbol) or {}
    except Exception:                                                      # noqa: BLE001
        return {}


def _record(rows: List[Dict[str, Any]], rd: date_cls) -> Dict[str, Any]:
    """Beat, miss and in line over the last eight reports up to this one."""
    done = sorted((r for r in rows if _num(r.get("eps_reported")) is not None and _num(r.get("eps_estimate"))
                   and _day(r.get("date")) and _day(r.get("date")) <= rd and (rd - _day(r.get("date"))).days <= 1100),
                  key=lambda r: str(r["date"]), reverse=True)[:8]
    out_rows = []
    for r in done:
        v, pct = _verdict(_num(r["eps_reported"]), _num(r["eps_estimate"]))
        if _num(r.get("surprise_pct")) is not None:
            # the table's own figure, as the headline uses: VZ's 1.31 on 1.27 is 3.1% from the rounded
            # estimate and 2.8% from the one Yahoo holds
            pct = _num(r["surprise_pct"])
            v = "in line" if abs(pct) <= IN_LINE_PCT else "beat" if pct > 0 else "missed"
        out_rows.append({"date": str(r["date"])[:10], "verdict": v, "surprise_pct": round(pct, 1) if pct is not None else None})
    n = len(out_rows)
    if n < 2:
        return {"available": False, "reason": "The surprise table has fewer than two reports with an estimate."}
    count = {k: sum(1 for r in out_rows if r["verdict"] == k) for k in ("beat", "missed", "in line")}
    parts = ["beat {} of the last {}".format(count["beat"], n)]
    if count["in line"]:
        parts.append("in line {}".format(count["in line"]))
    if count["missed"]:
        parts.append("missed {}".format(count["missed"]))
    return {"available": True, "quarters": n, "beat": count["beat"], "missed": count["missed"],
            "in_line": count["in line"], "rows": out_rows,
            "text": "EPS " + ", ".join(parts) + "."}


def build(provider, symbol: str, day: str, row: Dict[str, Any], rows: List[Dict[str, Any]],
          cal: Dict[str, Any], side: Optional[str], now: Optional[datetime] = None,
          path: Optional[str] = None) -> Dict[str, Any]:
    """The released result's deeper read. `row` is the surprise table's row for
    the report, with a reported EPS; `rows` the whole table."""
    now = (now or datetime.now(timezone.utc)).astimezone(ET)
    rd = _day(day)
    missing: List[str] = []
    eps, est = _num(row.get("eps_reported")), _num(row.get("eps_estimate"))
    eps_v, eps_pct = _verdict(eps, est)
    sur = _num(row.get("surprise_pct"))
    if sur is not None and est:
        # the table's own surprise, so this agrees with the Earnings tab to the decimal
        eps_pct = sur
        eps_v = "in line" if abs(sur) <= IN_LINE_PCT else "beat" if sur > 0 else "missed"

    # Revenue: the filed figure, and the estimate Optic recorded before the report.
    rev = _reported_revenue(provider, symbol, day)
    revenue: Dict[str, Any] = {"available": False}
    if rev.get("value") is None:
        missing.append("Reported revenue, and so its growth: not in Optic's feeds yet. Yahoo's quarterly "
                       "statement and the SEC filing come after the press release, from a day to a few weeks later.")
    else:
        revenue = {"available": True, "reported": rev["value"], "reported_label": _money(rev["value"]),
                   "period_end": rev["period_end"], "source": rev["source"]}
    rec = recorded_consensus(symbol, day, path)
    rec_eps = _num((rec or {}).get("eps_avg"))
    matches = rec is not None and _matches(rec_eps, est)
    rev_est = _num((rec or {}).get("revenue_avg")) if matches else None
    if rec is None or (rec_eps is None and _num(rec.get("revenue_avg")) is not None):
        missing.append("Revenue estimate: not available. Yahoo moves its consensus to the next quarter once a "
                       "company reports, and Optic had not recorded this quarter's before the release.")
    elif not matches:
        missing.append("Revenue estimate: the one Optic recorded does not match this quarter's EPS estimate, so it "
                       "may be another quarter's, and it is not used.")
    elif rev_est is None:
        missing.append("Revenue estimate: Yahoo had no revenue consensus for this quarter.")
    rev_v = None
    if revenue.get("available") and rev_est:
        rv, rpct = _verdict(revenue["reported"], rev_est)
        revenue.update(estimate=rev_est, estimate_label=_money(rev_est),
                       estimate_recorded=(rec or {}).get("recorded_at"))
        if abs(rpct) > BASIS_GAP_PCT:
            missing.append("Revenue against its estimate: {:.0f}% apart, which usually means the estimate and the "
                           "filed figure are on different bases, so no verdict is drawn.".format(abs(rpct)))
        else:
            rev_v = rv
            revenue.update(verdict=rv, surprise_pct=round(rpct, 1))

    # Both, said plainly.
    combined = None
    if eps_v and rev_v:
        if eps_v == rev_v == "beat":
            combined = {"kind": "double beat", "text": "A double beat: EPS and revenue both above their estimates."}
        elif eps_v == rev_v == "missed":
            combined = {"kind": "double miss", "text": "A double miss: EPS and revenue both below their estimates."}
        else:
            combined = {"kind": "mixed", "text": "Mixed: EPS {}, revenue {}.".format(eps_v, rev_v)}
    elif eps_v:
        missing.append("Double beat or miss: not called without revenue against its estimate.")

    # Year on year.
    growth: Dict[str, Any] = {}
    if revenue.get("available") and rev.get("year_ago"):
        g = (revenue["reported"] / rev["year_ago"] - 1.0) * 100.0
        growth["revenue_yoy_pct"] = round(g, 1)
        growth["revenue_text"] = "Revenue {} {:.1f}% on the same quarter a year earlier.".format(
            "up" if g >= 0 else "down", abs(g))
    elif revenue.get("available"):
        missing.append("Revenue growth: the same quarter a year earlier is not in the statement Optic has.")
    ago = None
    if rd:
        ago = next((r for r in rows if _day(r.get("date")) and 330 <= (rd - _day(r.get("date"))).days <= 400
                    and _num(r.get("eps_reported")) is not None), None)
    if ago is None:
        missing.append("EPS growth: the surprise table has no report from a year earlier.")
    elif _num(ago["eps_reported"]) <= 0:
        missing.append("EPS growth: not meaningful against a loss of {:.2f} a year earlier.".format(_num(ago["eps_reported"])))
    elif eps is not None:
        g = (eps / _num(ago["eps_reported"]) - 1.0) * 100.0
        growth.update(eps_yoy_pct=round(g, 1), eps_year_ago=_num(ago["eps_reported"]),
                      eps_text="EPS {} {:.1f}% from {:.2f} a year earlier.".format(
                          "up" if g >= 0 else "down", abs(g), _num(ago["eps_reported"])))

    record = _record(rows, rd) if rd else {"available": False, "reason": "No report date."}
    if not record.get("available"):
        missing.append("Surprise record: " + record["reason"][0].lower() + record["reason"][1:])
    reaction = _reaction(provider, symbol, day, side, now)
    if not reaction.get("available"):
        missing.append("Price reaction: " + reaction["reason"][0].lower() + reaction["reason"][1:])

    fiscal = None
    if rev.get("fy_end"):
        try:
            from .analytics import fundamentals as fundamentals_mod
            fiscal = fundamentals_mod.reported_quarter(day, rev["fy_end"])
        except Exception:                                                  # noqa: BLE001
            fiscal = None

    sources = ["EPS: Yahoo Finance surprise table (adjusted EPS)"]
    if revenue.get("available"):
        sources.append("revenue: " + revenue["source"])
    if revenue.get("estimate"):
        sources.append("revenue estimate: Yahoo consensus as Optic recorded it " + _rec_words(revenue["estimate_recorded"]))
    if reaction.get("available"):
        sources.append("prices: Yahoo Finance")
    return {"fiscal": fiscal, "eps_verdict": eps_v, "eps_surprise_pct": round(eps_pct, 1) if eps_pct is not None else None,
            "revenue": revenue, "combined": combined, "growth": growth, "record": record, "reaction": reaction,
            "missing": missing, "sources": "; ".join(sources) + "."}


def _rec_words(stamp: Any) -> str:
    when = _et(stamp)
    if when is None:
        return "before the report"
    return "on {} {}, before the report".format(when.strftime("%b"), when.day)
