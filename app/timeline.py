"""One company's events in one list, newest first (owner's Handoff 9, 2026-11-03: the Company Event Timeline).

News, earnings, insider trades, congressional trades, analyst actions and SEC filings for one company each sat on
their own Dossier page or panel, and a reader put the story together by hand. This merges what those pages already
read, through the same calls (no new feed; mostly the provider's cache once the Dossier has loaded), into entries of
one shape: when, which kind, a one-line summary, the source and its link, and the delay between an event and its
disclosure where there is one.

**Which date each source gives**, checked in the code on 2026-11-04, is said on every entry (`date_kind`):

- News: when the story was published, as the headline feed gives it (news.analyse over Yahoo Finance's feeds).
- Earnings: the day the company reported, New York time, with before the open or after the close where the feed has
  it. The next report is "scheduled, not yet reported" (analytics/earnings.py `_next_report`).
- Insiders: the transaction date on the Form 4, from Yahoo Finance's list and the SEC's own filings where that list
  stops (insider_fill). The trade became public when the form was filed, within two business days.
- Congress: the day the House received the disclosure, with the trade date beside it (analytics/congress.py). A
  member has up to 45 days.
- Analysts: when Yahoo Finance recorded the firm's action, usually the day it was announced (analysts.for_symbol).
- Filings: the filing date EDGAR gives (analytics/filings.py).

**Never silently incomplete.** Every source answers for itself, and the response says each one's state beside what
did arrive:
- a failure or a time-out;
- a source that does not apply (a fund files no 10-Q);
- a source whose reach is shorter than the period: the headline feed's latest stories, or the House's current year.

A failed fetch reads as an empty one in the provider, so each source's calls run inside yf.noting_failures().

**Nothing is merged across sources.** Two entries are one only when they are the same source's same item: a news
story's link, or a filing's or a Form 4's accession number. An 8-K announcing results and the earnings entry for the
same report stay two entries, each with its source.

**Wording.** What the filing or the feed says, in neutral words. An insider's or a member's trade is the record of a
disclosed trade. No entry calls it a signal or suggests anything improper.
"""

from __future__ import annotations

import concurrent.futures as cf
import hashlib
import logging
import re
import threading
import time
from datetime import date, datetime, time as dtime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple

from . import analysts as analysts_mod, insider_fill, news as news_mod
from .analytics import congress as congress_mod, earnings as earnings_mod, filings as filings_mod
from .analytics import fundamentals as fundamentals_mod
from .session import ET, market_today
from .providers import yf as yf_mod

log = logging.getLogger(__name__)

TYPES = ("news", "earnings", "insiders", "congress", "analysts", "filings")
LABELS = {"news": "News", "earnings": "Earnings", "insiders": "Insiders", "congress": "Congress",
          "analysts": "Analysts", "filings": "Filings"}
# The empty state for each kind, in the handoff's words ("No congressional trades reported for this company in
# this period").
EMPTY = {
    "news": "No news stories about this company in this period.",
    "earnings": "No earnings reports for this company in this period.",
    "insiders": "No insider trades reported for this company in this period.",
    "congress": "No congressional trades reported for this company in this period.",
    "analysts": "No analyst actions reported for this company in this period.",
    "filings": "No notable SEC filings for this company in this period.",
}
# What a failed source's note calls it ("X feed temporarily unavailable").
NOUNS = {"news": "News", "earnings": "Earnings", "insiders": "Insider trades", "congress": "Congressional trades",
         "analysts": "Analyst actions", "filings": "SEC filings"}
# What the date on an entry is.
DATE_LABELS = {"published": "Published", "reported": "Reported", "scheduled": "Scheduled, not yet reported",
               "due": "Report date passed, results not in the feed yet", "traded": "Transaction date",
               "disclosed": "Disclosed", "recorded": "Recorded", "filed": "Filed"}
DATES = {
    "news": "When the story was published, as the headline feed gives it. The event a story covers can be earlier "
            "or later.",
    "earnings": "The day the company reported, New York time. The next report is the date expected, scheduled and "
                "not yet reported.",
    "insiders": "The transaction date on the Form 4. Insiders have two business days to file it, so a trade became "
                "public up to two business days later.",
    "congress": "The day the House received the disclosure, with the trade date beside it. Members may disclose a "
                "trade up to 45 days after it.",
    "analysts": "When Yahoo Finance recorded the firm's action, usually the day it was announced.",
    "filings": "The filing date EDGAR gives.",
}
SOURCES = {
    "news": "Yahoo Finance's headline feeds, each story credited to its publisher",
    "earnings": "Yahoo Finance's earnings dates and estimates",
    "insiders": "Form 4 filings, as Yahoo Finance lists them and from SEC EDGAR where its list stops",
    "congress": "Periodic Transaction Reports from the Clerk of the House",
    "analysts": "Yahoo Finance's record of each firm's rating and price-target actions",
    "filings": "SEC EDGAR",
}
PERIODS = (30, 90, 365)
DEFAULT_DAYS = 90
PER_PAGE = 50
MAX_PER = 100
TTL = 300                 # a built timeline, every source answered
TTL_PARTIAL = 30          # one with a source that failed or timed out, so the next look asks again soon
WAIT = 25.0               # seconds the slowest source is waited for
FILINGS_LIMIT = 100       # EDGAR's recent window holds a year of a large company's notable filings
EARNINGS_DUE_DAYS = 7     # a past report date with no figures yet is said for a week, then left to the feed
OWNERS = {"SP": "spouse", "JT": "joint account", "DC": "dependent child"}
CONGRESS_SIDE = {"buy": "purchase", "sell": "sale", "other": "transaction"}
INSIDER_FORM4 = ("https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik}&type=4&dateb=&owner=include"
                 "&count=40")
FORM4_INDEX = "https://www.sec.gov/Archives/edgar/data/{cik}/{folder}/{accession}-index.htm"
HOUSE_NOTE = "House filings only: the Senate publishes no comparable archive."
# The Yahoo Finance pages the earnings dates and the analyst actions are read from, as Optic already cites them
# (providers/yf.py EARNINGS_PAGE, desk/research.py).
EARNINGS_URL = "https://finance.yahoo.com/calendar/earnings?symbol={}"
ANALYSIS_URL = "https://finance.yahoo.com/quote/{}/analysis"

_CACHE: Dict[Tuple[str, int], Tuple[float, Dict[str, Any]]] = {}
_CACHE_LOCK = threading.Lock()


# ------------------------------------------------------------------------------------------------ small parts

def _ident(*parts: Any) -> str:
    return hashlib.sha1("|".join(str(p) for p in parts).encode("utf-8")).hexdigest()[:12]


def _instant(value: Any) -> Optional[datetime]:
    """An ISO time as an aware UTC datetime, or None."""
    if not value:
        return None
    try:
        t = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if t.tzinfo is None:
        t = t.replace(tzinfo=timezone.utc)
    return t.astimezone(timezone.utc)


def _day(value: Any) -> Optional[date]:
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def _ny_day(t: datetime) -> date:
    return t.astimezone(ET).date()


def _noon(d: date) -> datetime:
    """Where a dated entry with no time sorts: midday in New York that day."""
    return datetime.combine(d, dtime(12, 0), ET).astimezone(timezone.utc)


def _long(d: date) -> str:
    return "{} {}, {}".format(d.strftime("%b"), d.day, d.year)


def _money(v: Any) -> Optional[str]:
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    a = abs(x)
    for cut, suffix in ((1e9, " billion"), (1e6, " million")):
        if a >= cut:
            return "${:,.1f}{}".format(x / cut, suffix)
    return "${:,.0f}".format(x)


def _price(v: Any) -> Optional[str]:
    try:
        return "${:,.2f}".format(float(v))
    except (TypeError, ValueError):
        return None


def _count(v: Any) -> Optional[str]:
    try:
        return "{:,.0f}".format(float(v))
    except (TypeError, ValueError):
        return None


def _event(kind: str, *, ident: str, when: date, at: Optional[datetime] = None, date_kind: str, title: str,
           summary: str = "", source: str, source_url: Optional[str] = None, source_link: Optional[str] = None,
           delay_note: Optional[str] = None, when_note: Optional[str] = None,
           detail: Optional[List[Tuple[str, str]]] = None) -> Dict[str, Any]:
    """One entry, the shape every source is put in (the handoff's date, type, title, summary, source_url and
    delay_note, with what the date is and the detail an entry expands to)."""
    sort_at = at if at is not None else _noon(when)
    return {
        "id": "{}:{}".format(kind, ident),
        "type": kind,
        "type_label": LABELS[kind],
        "date": when.isoformat(),
        "at": at.isoformat() if at is not None else None,
        "date_kind": date_kind,
        "date_label": DATE_LABELS[date_kind],
        "when_note": when_note,
        "title": title,
        "summary": summary,
        "source": source,
        "source_url": source_url,
        "source_link": source_link,
        "delay_note": delay_note,
        "detail": [{"label": k, "value": v} for k, v in (detail or []) if v],
        "_sort": sort_at.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S"),
    }


def _state(kind: str, events: List[Dict[str, Any]], *, failed: Optional[str] = None,
           absent: Optional[str] = None, reach: Optional[str] = None, partial: Optional[str] = None
           ) -> Dict[str, Any]:
    """A source's answer: its entries and how it answered.

    `failed`: it did not answer and nothing of it is here. `absent`: it answered and does not apply to this
    company. `reach`: it answered, but covers less than the period. `partial`: part of it failed and what came back
    is shown."""
    state = "failed" if failed else "partial" if partial else "none" if absent else "ok"
    return {"type": kind, "events": events, "state": state, "failed": failed, "absent": absent, "reach": reach,
            "partial": partial}


# ------------------------------------------------------------------------------------------------ the sources

def news_events(provider, sym: str, since: date) -> Dict[str, Any]:
    """The company's headlines from the feed the News tab reads, at the length /api/ticker asks for, so the cache
    is shared. Only stories about the company: market context is the News tab's."""
    with yf_mod.noting_failures() as failed:
        data = news_mod.analyse(provider, sym)
    articles = data.get("articles") or []
    held = (data.get("held") or {}).get("note")
    if failed and not articles:
        return _state("news", [], failed="The headline feed did not answer.")
    events: List[Dict[str, Any]] = []
    seen = set()
    oldest: Optional[datetime] = None
    about = [a for a in articles if a.get("about_company") is not False]
    for a in about:
        key = a.get("url") or a.get("title")
        if not key or key in seen:
            continue
        seen.add(key)
        at = _instant(a.get("published"))
        if at is None:
            continue
        oldest = at if oldest is None or at < oldest else oldest
        if _ny_day(at) < since:
            continue
        publisher = (a.get("publisher") or "").strip()
        summary = re.sub(r"\s+", " ", str(a.get("summary") or "")).strip()
        if len(summary) > 240:
            summary = summary[:240].rsplit(" ", 1)[0] + "…"
        events.append(_event(
            "news", ident=_ident(key), when=_ny_day(at), at=at, date_kind="published",
            title=str(a.get("title") or "").strip(), summary=summary,
            source="{}, via Yahoo Finance".format(publisher) if publisher else "Yahoo Finance",
            source_url=a.get("url") or None,
            detail=[("Publisher", publisher or "Not given"),
                    ("Catalyst types found in the wording", ", ".join(c.get("type", "") for c in a.get("catalysts") or [])
                     or None)]))
    reach = None
    if oldest is not None and _ny_day(oldest) > since:
        reach = ("The headline feed holds its latest {} stories about the company, which reach back to {}. Older "
                 "news is not in it.".format(len(seen), _long(_ny_day(oldest))))
    elif not about and articles:
        reach = "The feed's stories were all about the wider market; they are on the News tab."
    partial = held if held else None
    return _state("news", events, reach=reach, partial=partial)


def _fiscal_end(provider, sym: str) -> Optional[str]:
    try:
        fin = provider.financials(sym) or {}
    except Exception:                                        # noqa: BLE001
        return None
    return ((fin.get("income_annual") or {}).get("periods") or [None])[0]


def earnings_events(provider, sym: str, since: date, today: date) -> Dict[str, Any]:
    """Each report in the period with its EPS as the feed lists it, and the next one, scheduled."""
    with yf_mod.noting_failures() as failed:
        history = provider.earnings_history(sym) or []
    if failed and not history:
        return _state("earnings", [], failed="The earnings feed did not answer.")
    with yf_mod.noting_failures() as cal_failed:
        calendar = provider.earnings_calendar(sym) or {}
    fy_end = _fiscal_end(provider, sym) if history else None
    reported = {str(r.get("date")) for r in history if r.get("eps_reported") is not None}
    events: List[Dict[str, Any]] = []
    for r in history:
        d = _day(r.get("date"))
        if d is None or d < since:
            continue
        timing = r.get("timing")
        when_note = ("before the open, New York time" if timing == "before_open"
                     else "after the close, New York time" if timing == "after_close" else None)
        fiscal = fundamentals_mod.reported_quarter(d.isoformat(), fy_end) if fy_end else None
        if r.get("eps_reported") is None:
            # a past date with no figures: said for a week (the feed is often a day behind), not as a report
            if d < today and str(d) not in reported and (today - d).days <= EARNINGS_DUE_DAYS:
                events.append(_event(
                    "earnings", ident=_ident("due", d), when=d, date_kind="due", when_note=when_note,
                    title="Earnings report date{}".format(", " + fiscal if fiscal else ""),
                    summary="The date has passed and the feed has no results for it yet.",
                    source="Yahoo Finance", source_url=EARNINGS_URL.format(sym), source_link="earnings"))
            continue
        eps, est, surprise = r.get("eps_reported"), r.get("eps_estimate"), r.get("surprise_pct")
        words = "Earnings per share {}".format(_price(eps))
        if est is not None:
            words += " against an average estimate of {}".format(_price(est))
            if surprise is not None:
                words += ", {:.1f}% {}".format(abs(float(surprise)), "above it" if float(surprise) > 0
                                               else "below it" if float(surprise) < 0 else "in line")
        words += ", as Yahoo Finance lists them."
        quarter = ("{}, the fiscal quarter reported on {}".format(fiscal, _long(d)) if fiscal
                   else "The quarter reported on {}".format(_long(d)))
        events.append(_event(
            "earnings", ident=_ident("reported", d), when=d, date_kind="reported", when_note=when_note,
            title="Reported quarterly results{}".format(" for " + fiscal if fiscal else ""), summary=words,
            source="Yahoo Finance", source_url=EARNINGS_URL.format(sym), source_link="earnings",
            detail=[("Period", quarter),
                    ("Earnings per share, as reported", _price(eps)),
                    ("Average analyst estimate before the report", _price(est)),
                    ("Surprise, as Yahoo Finance lists it: (reported minus estimate) over the estimate",
                     "{:+.1f}%".format(float(surprise)) if surprise is not None else None)]))
    nxt = earnings_mod._next_report(history, calendar, reported) if (history or calendar) else {}
    nd = _day(nxt.get("date")) if nxt else None
    if nd is not None and nd >= today:
        confirmed = nxt.get("confirmed")
        basis = ("confirmed, as Yahoo Finance flags it" if confirmed is True
                 else "an estimate, not confirmed by the company" if confirmed is False
                 else "not marked confirmed or estimated in the feed")
        usual = nxt.get("usual_timing") or {}
        habit = ""
        if usual.get("timing") in ("before_open", "after_close"):
            habit = " The company reported {} at each of its last {} reports; the time of this one is not given.".format(
                "before the open" if usual["timing"] == "before_open" else "after the close", usual.get("count"))
        consensus = nxt.get("eps_consensus")
        events.append(_event(
            "earnings", ident=_ident("next", nd), when=nd, date_kind="scheduled",
            title="Next earnings report", source="Yahoo Finance", source_url=EARNINGS_URL.format(sym),
            source_link="earnings",
            summary="Scheduled, not yet reported. The date is {}.{}".format(basis, habit),
            detail=[("Average estimate of earnings per share", _price(consensus) if consensus is not None else None),
                    ("Days away", str(nxt.get("days_away")) if nxt.get("days_away") is not None else None)]))
    partial = ("The next report's date could not be read." if cal_failed and not any(
        e["date_kind"] == "scheduled" for e in events) else None)
    return _state("earnings", events, partial=partial)


def _cik(sym: str) -> Optional[str]:
    try:
        return filings_mod._cik_for(sym)
    except Exception:                                        # noqa: BLE001
        return None


def insider_events(provider, sym: str, since: date) -> Dict[str, Any]:
    """Each Form 4 transaction in the period, by its transaction date. Yahoo's rows carry no link to their filing,
    so they link the company's Form 4 list on EDGAR; a row read from the SEC links its own filing."""
    with yf_mod.noting_failures() as failed:
        raw = provider.insiders(sym)
    full = insider_fill.complete(sym, raw or {})
    trades = full.get("transactions") or []
    if failed and not trades:
        return _state("insiders", [], failed="The insider-trade feed did not answer.")
    cik = _cik(sym)
    events: List[Dict[str, Any]] = []
    seen = set()
    for t in trades:
        d = _day(t.get("date"))
        if d is None or d < since:
            continue
        acc = t.get("accession")
        if acc:
            if acc in seen:
                continue
            seen.add(acc)
        who = (t.get("insider") or "An insider").strip()
        role = (t.get("position") or "").strip()
        action = t.get("action")
        shares = _count(t.get("shares"))
        value = _money(t.get("value")) if t.get("value") else None
        filing_words = re.sub(r"(\d) - (\d)", r"\1 to \2", str(t.get("detail") or "").strip())
        by = "{}{}".format(who, ", " + role if role else "")
        if action in ("sale", "purchase"):
            title = "{} of {} shares by {}".format("Sale" if action == "sale" else "Purchase",
                                                   shares or "an unstated number of", by)
        else:
            title = "Form 4 transaction{} by {}".format(" of {} shares".format(shares) if shares else "", by)
        summary = filing_words or "The feed does not say what kind of transaction this is; the filing does."
        if value and action in ("sale", "purchase"):
            summary = ("{}. Value about {}, as reported.".format(summary.rstrip("."), value) if filing_words
                       else "Value about {}, as reported.".format(value))
        from_sec = t.get("source") == "sec"
        url = None
        if from_sec and acc and cik:
            url = FORM4_INDEX.format(cik=int(cik), folder=acc.replace("-", ""), accession=acc)
        elif cik:
            url = INSIDER_FORM4.format(cik=cik)
        events.append(_event(
            "insiders", ident=acc or _ident(who, d, t.get("shares"), action, t.get("value"), filing_words),
            when=d, date_kind="traded", title=title, summary=summary,
            source="Form 4, from SEC EDGAR" if from_sec else "Form 4, via Yahoo Finance",
            source_url=url, source_link="insiders",
            delay_note=("This is the transaction date. Insiders have two business days to file the Form 4, so the "
                        "trade became public up to two business days later."),
            detail=[("Shares", shares), ("Value, as reported on the Form 4", value),
                    ("The filing's own description", filing_words or None),
                    ("Link", "The company's Form 4 list on EDGAR: Yahoo Finance does not give the filing itself"
                     if url and not from_sec else None)]))
    cov = full.get("coverage") or {}
    reach = None
    if cov and not cov.get("complete") and cov.get("sec_unread"):
        reach = ("Yahoo Finance's list reaches back to {}; {} older Form 4 filings are still being read from the SEC."
                 .format(_long(_day(cov.get("yahoo_from"))) if _day(cov.get("yahoo_from")) else "a recent date",
                         cov.get("sec_unread")))
    partial = "Part of the insider feed did not answer, so this list may be short." if failed else None
    return _state("insiders", events, reach=reach, partial=partial)


def congress_events(sym: str, since: date, today: date,
                    refresh: Optional[Callable[[], Any]] = None) -> Dict[str, Any]:
    """Each House disclosure of a trade in the company's stock, placed on the day it was filed."""
    if refresh is not None and congress_mod.stale():
        refresh()
    out = congress_mod.summary(ticker=sym, limit=1000)
    if not out.get("available") and not out.get("filings_known"):
        return _state("congress", [], failed="The House disclosure archive has not been read on this server yet.")
    events: List[Dict[str, Any]] = []
    for t in out.get("trades") or []:
        filed = _day(t.get("filed"))
        if filed is None or filed < since:
            continue
        traded = _day(t.get("traded_iso"))
        side = CONGRESS_SIDE.get(t.get("side"), "transaction")
        what = t.get("transaction") or side
        low, high = _money(t.get("amount_low")), _money(t.get("amount_high"))
        band = "{} to {}".format(low, high) if low and high else "an unstated amount"
        member = (t.get("member") or "A member of the House").strip()
        owner = OWNERS.get(t.get("owner") or "")
        title = "{} disclosed a {} of {}".format(member, what, band)
        summary = "Held by the {}.".format(owner) if owner else "Held by the member."
        if t.get("date_suspect"):
            delay = ("Disclosed {}. The trade date in the filing, {}, falls after the date it was filed, so one of the "
                     "two is a typo in the filing.".format(_long(filed), _long(traded) if traded else t.get("traded")))
        else:
            delay = ("Disclosed {}; the trade occurred on or around {}. Members may disclose a trade up to 45 days "
                     "after it.".format(_long(filed), _long(traded) if traded else "a date the filing does not give"))
            lag = t.get("disclosure_lag_days")
            if isinstance(lag, int) and lag > 45:
                delay += " This one was disclosed {} days after the trade.".format(lag)
        events.append(_event(
            "congress", ident=_ident(t.get("doc_id"), t.get("traded"), t.get("side"), t.get("amount_low"),
                                     t.get("owner"), t.get("description")),
            when=filed, date_kind="disclosed", title=title, summary=summary,
            source="Periodic Transaction Report, Clerk of the House", source_url=t.get("source_url"),
            source_link="congress", delay_note=delay,
            detail=[("Amount", "{}, the band the member reported, not an exact figure".format(band)),
                    ("Trade date in the filing", _long(traded) if traded else t.get("traded")),
                    ("District", t.get("district")),
                    ("The filing's own description", t.get("description"))]))
    year_start = date(today.year, 1, 1)
    notes = [HOUSE_NOTE]
    if since < year_start:
        notes.append("Optic reads the House's filings for {} only, so trades disclosed before {} are not here."
                     .format(today.year, _long(year_start)))
    if out.get("filings_known") and not out.get("complete"):
        notes.append("{} of the year's {} filings are read so far.".format(out.get("filings_parsed"),
                                                                          out.get("filings_known")))
    return _state("congress", events, reach=" ".join(notes))


def analyst_events(provider, sym: str, since: date, days: int, now: Optional[float] = None) -> Dict[str, Any]:
    """Each firm's rating and price-target action in the period, in the firm's own words."""
    out = analysts_mod.for_symbol(provider, sym, limit=1000, days=days, now=now)
    if not out.get("available"):
        return _state("analysts", [], failed="The analyst-action feed did not answer.")
    events: List[Dict[str, Any]] = []
    for r in out.get("rows") or []:
        at = _instant(r.get("at"))
        if at is None:
            continue
        timed = (at.hour, at.minute, at.second) != (0, 0, 0)
        d = _ny_day(at) if timed else at.date()
        if d < since:
            continue
        firm = r.get("firm") or "A firm"
        rating, prior, action = r.get("rating") or "", r.get("prior_rating") or "", r.get("action") or ""
        if action == "up" and prior:
            title = "{} upgraded the stock to {} from {}".format(firm, rating, prior)
        elif action == "down" and prior:
            title = "{} downgraded the stock to {} from {}".format(firm, rating, prior)
        elif action == "init":
            title = "{} started coverage at {}".format(firm, rating) if rating else "{} started coverage".format(firm)
        elif rating:
            title = "{} {} its {} rating".format(firm, "reiterated" if action == "reit" else "kept", rating)
        else:
            title = "{}: {}".format(firm, r.get("action_label") or "rating action")
        target, prior_t, t_action = r.get("target"), r.get("prior_target"), r.get("target_action") or ""
        if target and prior_t and t_action in ("Raises", "Lowers"):
            summary = "Price target {} to {} from {}.".format("raised" if t_action == "Raises" else "lowered",
                                                               _price(target), _price(prior_t))
        elif target:
            summary = "Price target {}.".format(_price(target))
        else:
            summary = "No price target given."
        events.append(_event(
            "analysts", ident=_ident(firm, r.get("at"), action, rating, target), when=d, at=at if timed else None,
            date_kind="recorded", title=title, summary=summary,
            source="Yahoo Finance's record of analyst actions", source_url=ANALYSIS_URL.format(sym),
            source_link="analysts",
            detail=[("Rating, the firm's own word", rating or None), ("Rating before", prior or None),
                    ("Price target, a 12-month forecast by the firm", _price(target) if target else None),
                    ("Price target before", _price(prior_t) if prior_t else None)]))
    return _state("analysts", events)


_FAILED_FILINGS = ("EDGAR ticker directory unavailable", "EDGAR filings unavailable", "EDGAR returned no filing")


def filing_events(sym: str, since: date) -> Dict[str, Any]:
    """The company's notable filings in the period (10-K, 10-Q, 8-K and the rest of analytics/filings.py's list).
    Form 4s are the insider entries, so they are not repeated here."""
    out = filings_mod.recent(sym, limit=FILINGS_LIMIT)
    reason = str(out.get("reason") or "")
    if not out.get("available") and not out.get("filings"):
        if any(reason.startswith(x) for x in _FAILED_FILINGS) or "not available on this site" in reason:
            return _state("filings", [], failed="SEC EDGAR did not answer.")
        return _state("filings", [], absent=(reason[:1].upper() + reason[1:]).rstrip(".") + "." if reason else None)
    rows = out.get("filings") or []
    events: List[Dict[str, Any]] = []
    seen = set()
    for f in rows:
        d = _day(f.get("filed"))
        if d is None or d < since:
            continue
        url = f.get("url") or ""
        m = re.search(r"/data/\d+/(\d{18})/", url)
        key = m.group(1) if m else _ident(f.get("form"), f.get("filed"), f.get("items"))
        if key in seen:
            continue
        seen.add(key)
        what = f.get("what") or f.get("form") or "Filing"
        events.append(_event(
            "filings", ident=key, when=d, date_kind="filed",
            title="{} (Form {})".format(what, f.get("form")), source="SEC EDGAR", source_url=url or None,
            source_link="filings",
            detail=[("Form", f.get("form")), ("8-K items, the filer's own codes", f.get("items") or None)]))
    reach = None
    if len(rows) >= FILINGS_LIMIT and rows and _day(rows[-1].get("filed")) and _day(rows[-1].get("filed")) > since:
        reach = "EDGAR's recent window ends at {}; older filings are on EDGAR.".format(_long(_day(rows[-1]["filed"])))
    return _state("filings", events, reach=reach)


# ------------------------------------------------------------------------------------------------ the timeline

def _now() -> datetime:
    return datetime.now(timezone.utc)


def build(provider, sym: str, days: int = DEFAULT_DAYS, *, now: Optional[datetime] = None,
          congress_refresh: Optional[Callable[[], Any]] = None, wait: float = WAIT) -> Dict[str, Any]:
    """Every source's entries for the period, newest first, and each source's state. Sources run side by side; one
    that has not answered after `wait` seconds is said to have timed out, and its thread finishes into the cache."""
    now = now or _now()
    today = market_today(now)
    since = today - timedelta(days=days)
    jobs = {
        "news": lambda: news_events(provider, sym, since),
        "earnings": lambda: earnings_events(provider, sym, since, today),
        "insiders": lambda: insider_events(provider, sym, since),
        "congress": lambda: congress_events(sym, since, today, congress_refresh),
        "analysts": lambda: analyst_events(provider, sym, since, days, now.timestamp()),
        "filings": lambda: filing_events(sym, since),
    }
    pool = cf.ThreadPoolExecutor(max_workers=len(jobs), thread_name_prefix="timeline")
    futures = {kind: pool.submit(fn) for kind, fn in jobs.items()}
    cf.wait(list(futures.values()), timeout=wait)
    pool.shutdown(wait=False)
    sources: Dict[str, Dict[str, Any]] = {}
    for kind, fut in futures.items():
        if not fut.done():
            sources[kind] = _state(kind, [], failed="The {} source did not answer in time.".format(LABELS[kind].lower()))
            continue
        try:
            sources[kind] = fut.result()
        except Exception as exc:                             # noqa: BLE001
            log.warning("timeline: %s for %s failed: %s", kind, sym, exc)
            sources[kind] = _state(kind, [], failed="The {} source did not answer.".format(LABELS[kind].lower()))
    events = [e for kind in TYPES for e in sources[kind]["events"]]
    # two rows with nothing to tell them apart (the same insider, day, shares and value twice) are both kept, as two
    # entries: each gets its own id, so opening one does not open the other
    taken: Dict[str, int] = {}
    for e in events:
        n = taken.get(e["id"], 0) + 1
        taken[e["id"]] = n
        if n > 1:
            e["id"] = "{}-{}".format(e["id"], n)
    events.sort(key=lambda e: (e["_sort"], e["id"]), reverse=True)
    return {"ticker": sym, "days": days, "since": since.isoformat(), "today": today.isoformat(),
            "built_at": now.isoformat(), "events": events,
            "sources": {k: {kk: vv for kk, vv in v.items() if kk != "events"} for k, v in sources.items()}}


def _types_view(built: Dict[str, Any]) -> List[Dict[str, Any]]:
    counts = {k: 0 for k in TYPES}
    for e in built["events"]:
        counts[e["type"]] += 1
    out = []
    for k in TYPES:
        s = built["sources"][k]
        out.append({"id": k, "label": LABELS[k], "count": counts[k], "state": s["state"], "failed": s["failed"],
                    "absent": s["absent"], "reach": s["reach"], "partial": s["partial"], "empty": EMPTY[k],
                    "dates": DATES[k], "source": SOURCES[k]})
    return out


def page(built: Dict[str, Any], kind: str = "all", page_no: int = 1, per: int = PER_PAGE) -> Dict[str, Any]:
    """The response: one page of the entries of one kind (or all), with every source's state, whatever the page."""
    per = max(1, min(int(per), MAX_PER))
    chosen = [e for e in built["events"] if kind == "all" or e["type"] == kind]
    total = len(chosen)
    pages = max(1, -(-total // per))
    page_no = max(1, min(int(page_no), pages))
    rows = [{k: v for k, v in e.items() if k != "_sort"} for e in chosen[(page_no - 1) * per: page_no * per]]
    types = _types_view(built)
    failed = [t for t in types if t["state"] == "failed"]
    answered = len(TYPES) - len(failed)
    return {
        "available": True, "ticker": built["ticker"], "days": built["days"], "since": built["since"],
        "today": built["today"], "built_at": built["built_at"], "type": kind, "page": page_no, "per": per,
        "pages": pages, "total": total, "events": rows, "types": types,
        "complete": not failed,
        "answered": answered,
        # the handoff's error state, one line per source that did not answer, beside the entries that did arrive
        "notes": ["{} temporarily unavailable. {}".format(NOUNS[t["id"]], t["failed"]) for t in failed],
        "method": ("Six sources the Dossier already reads, merged without a new feed, newest first. Each entry keeps "
                   "its source, and two entries are one only when they are the same source's same item. The date on "
                   "each entry says what it is, per source. Not investment advice: an insider's or a member's trade "
                   "is the record of a disclosed trade, not a signal."),
    }


def cached(provider, sym: str, days: int = DEFAULT_DAYS, *, force: bool = False,
           congress_refresh: Optional[Callable[[], Any]] = None) -> Dict[str, Any]:
    """The built timeline, kept TTL seconds when every source answered and TTL_PARTIAL when one did not, so paging
    and filtering read one build and a failed source is asked again soon."""
    key = (sym, days)
    with _CACHE_LOCK:
        hit = _CACHE.get(key)
    if hit and not force:
        at, built = hit
        complete = all(s["state"] != "failed" for s in built["sources"].values())
        if time.time() - at < (TTL if complete else TTL_PARTIAL):
            return built
    built = build(provider, sym, days, congress_refresh=congress_refresh)
    with _CACHE_LOCK:
        _CACHE[key] = (time.time(), built)
        if len(_CACHE) > 200:
            for k in sorted(_CACHE, key=lambda k: _CACHE[k][0])[:50]:
                _CACHE.pop(k, None)
    return built
