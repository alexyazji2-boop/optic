"""The catalyst library: market events that keep mattering after the day they broke.

A news feed answers "what happened this morning" and then throws it away. That is
the wrong shape for the things that actually move positions over months — a
tariff regime, an industrial-policy push, a rate-cycle turn. Those are published
once and matter for a year, so this stores them, links each to the public
companies plausibly connected, and lets a reader search back through them.

Three boundaries, and they are the whole design.

**A catalyst comes from a published source.** Every row here traces to a story
or release the terminal actually fetched, with its URL kept. The model's job is
to recognise which stories are durable and to name the connections — never to
supply the event itself.

**Ticker links are validated against EDGAR, not trusted.** A model asked which
companies benefit from critical-minerals policy will happily produce a plausible
ticker that does not exist, or one that belongs to something else entirely.
Every symbol is checked against EDGAR's company directory and dropped if it does
not resolve, and the company name shown is EDGAR's, not the model's.

**Directness and strength are labelled as judgement.** "MP Materials is a direct
beneficiary" is an inference, not a datum. The UI says so, the method note says
so, and no row here is a recommendation — the library is context for research,
which is why it stores what a catalyst *is* rather than what to do about it.

The first boundary was stated and not enforced. The model was asked to echo
each story's URL back, and all three catalysts in the local store came back
without one. Stories now carry an id, the model cites ids, and the URL, source
and date are filled in here from the story itself. A catalyst citing nothing
the scan read is dropped.

**The library keeps itself current.** It filled only when somebody pressed
"Scan for new catalysts", and on the hosted terminal that button needs the
write token, so in practice nobody could: on 2026-09-28 the live store held
nothing and the local one held three catalysts from 2026-08-14. A scan now also
runs on a schedule, one model call every CATALYST_SCAN_HOURS. That is a fixed,
bounded cost, so the rule the button existed for still holds: opening a tab
never spends anything.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import sqlite3
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from . import feeds

log = logging.getLogger(__name__)

_DATA_DIR = os.environ.get(
    "TRACKER_DATA_DIR",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data"),
)
DB_PATH = os.environ.get("CATALYST_DB", os.path.join(_DATA_DIR, "catalysts.db"))

_LOCK = threading.RLock()
# One scan at a time. The schedule and the button can land together, and two
# scans of the same stories pay twice to store the same rows.
_SCAN_LOCK = threading.Lock()

# How long a catalyst stays "currently relevant", by horizon. These are the
# whole point of the library: a short-term catalyst stops mattering quickly, a
# structural one does not, and collapsing them into one expiry would either bury
# live policy shifts or keep stale earnings reactions on the page for a year.
HORIZON_DAYS = {"short-term": 45, "medium-term": 180, "long-term": 540}
HORIZONS = list(HORIZON_DAYS)

CATEGORIES = [
    "government", "monetary-policy", "geopolitical", "regulatory",
    "commodity", "technology", "corporate",
]

# How direct a company's link to the catalyst is.
DIRECTNESS = ["direct", "indirect", "peripheral"]
# How strong the read-through is, separately from how direct it is. A direct
# link can still be a weak read-through if the exposure is a small share of
# revenue, and keeping them apart is what stops "direct" reading as "big".
STRENGTH = ["strong", "moderate", "weak"]

MAX_COMPANIES = 8

# ------------------------------------------------------------- the schedule
#
# Hours between scans. At least one: the loop looks every fifteen minutes, and
# a zero here would be a model call on every look.
SCAN_EVERY_HOURS = max(1.0, float(os.environ.get("CATALYST_SCAN_HOURS", "6")))
# The wait after a scan that failed. Shorter than the interval, because a
# failure is usually the API or EDGAR briefly out of reach; not zero, because an
# outage would otherwise cost a call on every look.
SCAN_RETRY_HOURS = 1.0
AUTO = os.environ.get("CATALYST_AUTO", "true").strip().lower() != "false"

# ------------------------------------------------------ what one scan reads
#
# It read the thirty newest stories. Measured on 2026-09-28 that was 44 minutes
# of news, 13:30 to 14:14 UTC, and the model saw 25 of them (the prompt
# builder's list cap), 18 from CNBC and MarketWatch, out of 494 stories from 33
# sources in the week the scan said it covered. The newest from every source in
# turn is what makes the window the week it names: BBC World, the ECB and the
# EIA reach the model beside the market desk.
SCAN_STORIES = 120
SUMMARY_CHARS = 280
# Stored catalysts shown to the model, so it can tell a development in one of
# them from a new event instead of filing the same blockade twice.
LIBRARY_CONTEXT = 40

SCHEMA = """
CREATE TABLE IF NOT EXISTS catalysts (
  id          TEXT PRIMARY KEY,   -- stable hash of the source url + title
  created_at  TEXT NOT NULL,
  event_date  TEXT NOT NULL,      -- when the catalyst happened, YYYY-MM-DD
  title       TEXT NOT NULL,
  summary     TEXT NOT NULL,
  category    TEXT NOT NULL,
  horizon     TEXT NOT NULL,
  themes      TEXT NOT NULL,      -- JSON list
  sectors     TEXT NOT NULL,      -- JSON list
  companies   TEXT NOT NULL,      -- JSON list of {ticker,name,directness,strength,why}
  source_url  TEXT,
  source_name TEXT
);
CREATE INDEX IF NOT EXISTS catalysts_date ON catalysts(event_date DESC);
CREATE TABLE IF NOT EXISTS catalyst_scans (
  at          TEXT NOT NULL,      -- when the scan finished, ISO UTC
  kind        TEXT NOT NULL,      -- scheduled or manual
  ok          INTEGER NOT NULL,   -- 1 when the model answered and the answer was kept
  scanned     INTEGER NOT NULL DEFAULT 0,
  identified  INTEGER NOT NULL DEFAULT 0,
  written     INTEGER NOT NULL DEFAULT 0,
  unsourced   INTEGER NOT NULL DEFAULT 0,   -- answers dropped for citing no story
  reason      TEXT
);
CREATE INDEX IF NOT EXISTS catalyst_scans_at ON catalyst_scans(at DESC);
"""


# Columns added to a table after it first shipped. CREATE TABLE IF NOT EXISTS
# never touches a table that is already there, so a store made before a column
# existed refuses every insert naming it: measured on the local store, whose
# scan table predated `unsourced`, every scan after that went unrecorded and
# the page kept showing the one row from before it.
_ADDED_COLUMNS = {
    "catalyst_scans": [("unsourced", "INTEGER NOT NULL DEFAULT 0")],
}


def _connect() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(SCHEMA)
    for table, columns in _ADDED_COLUMNS.items():
        have = {r[1] for r in conn.execute("PRAGMA table_info(%s)" % table)}
        for name, decl in columns:
            if name not in have:
                conn.execute("ALTER TABLE %s ADD COLUMN %s %s" % (table, name, decl))
    return conn


def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    out = dict(row)
    for key in ("themes", "sectors", "companies"):
        try:
            out[key] = json.loads(out.get(key) or "[]")
        except ValueError:
            out[key] = []
    # On the way out as well as the way in: rows stored before the scan
    # cleaned its text still carry the model's dashes, and they are on the page.
    out["title"] = _plain(out.get("title"))
    out["summary"] = _plain(out.get("summary"))
    out["themes"] = [_plain(t) for t in out["themes"]]
    for co in out["companies"]:
        if isinstance(co, dict) and co.get("why"):
            co["why"] = _plain(co["why"])
    out["age_days"] = _age_days(out.get("event_date"))
    out["relevant"] = _is_relevant(out.get("horizon"), out["age_days"])
    return out


def _age_days(event_date: Optional[str]) -> Optional[int]:
    if not event_date:
        return None
    try:
        when = datetime.strptime(str(event_date)[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None
    return (datetime.now(timezone.utc) - when).days


def _is_relevant(horizon: Optional[str], age_days: Optional[int]) -> bool:
    if age_days is None:
        return True
    return age_days <= HORIZON_DAYS.get(horizon or "medium-term", 180)


# A spaced dash of either kind, or an em dash at all, is a parenthetical and
# reads as a comma. An unspaced en dash joins a range or a pair, "2025-2026" or
# "U.S.-China", and becomes a hyphen.
_PAREN_DASH = re.compile(r"\s*\u2014\s*|\s+\u2013\s+")


def _plain(text: Any) -> str:
    """Model text without em or en dashes, which the terminal does not print.

    The prompt says so and the model does not always listen: all three
    catalysts in the local store were titled "... \u2014 August 2026"."""
    text = _PAREN_DASH.sub(", ", str(text or ""))
    return text.replace("\u2013", "-").strip(" ,")


# ------------------------------------------------------------ ticker check

TICKER_MAP_URL = "https://www.sec.gov/files/company_tickers.json"
TICKER_MAP_TTL = 86400


def ticker_directory() -> Dict[str, str]:
    """EDGAR's ticker → company-name map, cached for a day.

    This is the gate that stops invented symbols reaching the page. A model
    naming beneficiaries of a policy will produce confident tickers that do not
    exist; anything absent here is dropped rather than shown.
    """
    try:
        blob = feeds.fetch_json(TICKER_MAP_URL, TICKER_MAP_TTL, key="sec:tickers")
    except Exception as exc:
        log.warning("catalysts: EDGAR ticker directory unavailable: %s", exc)
        return {}
    if not isinstance(blob, dict):
        return {}
    out: Dict[str, str] = {}
    for row in blob.values():
        if isinstance(row, dict):
            sym = str(row.get("ticker", "")).upper().strip()
            if sym:
                out[sym] = str(row.get("title", "")).strip()
    return out


def validate_companies(raw: Any, directory: Dict[str, str]) -> List[Dict[str, Any]]:
    """Keep only companies whose ticker resolves in EDGAR, with EDGAR's name."""
    out: List[Dict[str, Any]] = []
    seen = set()
    for item in (raw or [])[: MAX_COMPANIES * 3]:
        if not isinstance(item, dict):
            continue
        sym = str(item.get("ticker", "")).upper().strip()
        if not sym or sym in seen:
            continue
        official = directory.get(sym)
        if not official:
            log.info("catalysts: dropped unresolvable ticker %r", sym)
            continue
        seen.add(sym)
        directness = str(item.get("directness", "")).lower().strip()
        strength = str(item.get("strength", "")).lower().strip()
        out.append({
            "ticker": sym,
            # EDGAR's name, not the model's — the ticker is the thing being
            # verified, so the name has to come from the same place.
            "name": official,
            "directness": directness if directness in DIRECTNESS else "indirect",
            "strength": strength if strength in STRENGTH else "moderate",
            "why": _plain(item.get("why", ""))[:280],
        })
        if len(out) >= MAX_COMPANIES:
            break
    return out


# --------------------------------------------------------------- storage

def upsert(entries: List[Dict[str, Any]]) -> int:
    """Store catalysts, updating any with the same id. Returns rows changed.

    An update replaces the text and carries the date forward, so a catalyst
    that keeps developing stays at the top of the list and inside its horizon.
    A different, older story never carries it back: a scan that rereads one
    would otherwise date a September development to August. The same story
    may, since its own date is the right one for it. Companies survive an
    update that brought none, since an empty list is a thin answer, not a
    finding that the links stopped existing.
    """
    if not entries:
        return 0
    now = datetime.now(timezone.utc).isoformat()
    written = 0
    try:
        with _LOCK, _connect() as conn:
            for e in entries:
                if not e.get("id") or not e.get("title"):
                    continue
                cur = conn.execute(
                    """INSERT INTO catalysts
                       (id, created_at, event_date, title, summary, category, horizon,
                        themes, sectors, companies, source_url, source_name)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                       ON CONFLICT(id) DO UPDATE SET
                         event_date=excluded.event_date,
                         title=excluded.title, summary=excluded.summary,
                         category=excluded.category, horizon=excluded.horizon,
                         themes=excluded.themes, sectors=excluded.sectors,
                         companies=CASE WHEN excluded.companies = '[]'
                                        THEN catalysts.companies
                                        ELSE excluded.companies END,
                         source_url=COALESCE(excluded.source_url, catalysts.source_url),
                         source_name=COALESCE(excluded.source_name, catalysts.source_name)
                       WHERE excluded.event_date >= catalysts.event_date
                          OR excluded.source_url = catalysts.source_url""",
                    (e["id"], now, e.get("event_date") or now[:10], e["title"],
                     e.get("summary", ""), e.get("category", "corporate"),
                     e.get("horizon", "medium-term"),
                     json.dumps(e.get("themes") or []),
                     json.dumps(e.get("sectors") or []),
                     json.dumps(e.get("companies") or []),
                     e.get("source_url"), e.get("source_name")),
                )
                written += max(cur.rowcount, 0)
    except sqlite3.Error as exc:
        log.warning("catalysts: write failed: %s", exc)
        return 0
    return written


# ------------------------------------------------------------- scan record

def _stamp(iso: Any) -> Optional[datetime]:
    try:
        when = datetime.fromisoformat(str(iso))
    except (TypeError, ValueError):
        return None
    return when if when.tzinfo else when.replace(tzinfo=timezone.utc)


def _record_scan(kind: str, ok: bool, scanned: int = 0, identified: int = 0,
                 written: int = 0, unsourced: int = 0,
                 reason: Optional[str] = None) -> None:
    try:
        with _LOCK, _connect() as conn:
            conn.execute(
                """INSERT INTO catalyst_scans
                   (at, kind, ok, scanned, identified, written, unsourced, reason)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (datetime.now(timezone.utc).isoformat(), kind, 1 if ok else 0,
                 scanned, identified, written, unsourced, reason))
    except sqlite3.Error as exc:
        log.warning("catalysts: could not record the scan: %s", exc)


def last_scan() -> Optional[Dict[str, Any]]:
    """The newest scan and the newest one that worked, or None if unreadable."""
    try:
        with _connect() as conn:
            last = conn.execute(
                "SELECT * FROM catalyst_scans ORDER BY at DESC LIMIT 1").fetchone()
            good = conn.execute(
                "SELECT * FROM catalyst_scans WHERE ok = 1 ORDER BY at DESC LIMIT 1"
            ).fetchone()
    except sqlite3.Error:
        return None
    return {"last": dict(last) if last else None, "last_ok": dict(good) if good else None}


def scan_due(now: Optional[datetime] = None) -> bool:
    """Whether the schedule should scan now.

    Read from the store, not kept in memory, because this platform restarts on
    every deploy and a clock that started at zero would scan on each one: the
    tracker loop learned that first. A store that cannot be read is not due. It
    cannot be written either, and a scan into it would spend a call to keep
    nothing.
    """
    now = now or datetime.now(timezone.utc)
    info = last_scan()
    if info is None:
        return False
    last = _stamp((info["last"] or {}).get("at"))
    if last and now - last < timedelta(hours=SCAN_RETRY_HOURS):
        return False
    good = _stamp((info["last_ok"] or {}).get("at"))
    return good is None or now - good >= timedelta(hours=SCAN_EVERY_HOURS)


def scheduled() -> bool:
    """Whether this server refreshes the library on its own."""
    if not AUTO:
        return False
    from . import ai                        # local: avoids an import cycle
    return ai.available().get("enabled") is True


# When this process last started a scheduled scan, on the monotonic clock.
_LAST_ATTEMPT = [0.0]


def run_if_due(now: Optional[datetime] = None) -> Optional[Dict[str, Any]]:
    """One pass of the schedule: a scan if one is due, otherwise None.

    Two locks on spend rather than one. scan_due reads the store, and a store
    that reads but cannot be written would look due on every pass, so the
    attempt is stamped here as well and no pass scans within SCAN_RETRY_HOURS
    of the last try, whatever the disk says.
    """
    if not scheduled():
        return None
    mono = time.monotonic()
    if _LAST_ATTEMPT[0] and mono - _LAST_ATTEMPT[0] < SCAN_RETRY_HOURS * 3600:
        return None
    if not scan_due(now):
        return None
    _LAST_ATTEMPT[0] = mono
    return refresh(trigger="scheduled")


def _newest_written() -> Optional[str]:
    try:
        with _connect() as conn:
            return conn.execute("SELECT MAX(created_at) FROM catalysts").fetchone()[0]
    except sqlite3.Error:
        return None


def scan_status() -> Dict[str, Any]:
    """What the page says about freshness: the last scan, and the schedule."""
    info = last_scan() or {}
    last = info.get("last") or {}
    good = info.get("last_ok") or {}
    return {
        "last_at": last.get("at"),
        "last_ok": bool(last.get("ok")) if last else None,
        # Only a failure has something to say; a success's reason is empty.
        "last_reason": None if not last or last.get("ok") else last.get("reason"),
        # A store filled before scans were recorded is dated by its newest
        # catalyst: that is when a scan last wrote to it, and "no scan yet"
        # over three August catalysts is the one answer that is certainly wrong.
        "last_ok_at": good.get("at") or _newest_written(),
        # What the last good scan found. A scan that read 120 stories and kept
        # nothing reads the same on the page as one that never ran, and these
        # are what tell them apart, and tell "nothing qualified" from "every
        # answer cited a story the scan had not read".
        "last_counts": {k: good.get(k) for k in
                        ("scanned", "identified", "written", "unsourced")} if good else None,
        "every_hours": SCAN_EVERY_HOURS if scheduled() else None,
    }


def search(query: str = "", status: str = "relevant", category: str = "",
           sector: str = "", theme: str = "", limit: int = 60) -> Dict[str, Any]:
    """Filter the library. Everything is optional; defaults to what still matters."""
    try:
        with _connect() as conn:
            rows = conn.execute(
                "SELECT * FROM catalysts ORDER BY event_date DESC LIMIT 500").fetchall()
    except sqlite3.Error as exc:
        return {"available": False, "reason": "Catalyst store unavailable: {}".format(exc)}

    items = [_row_to_dict(r) for r in rows]
    total = len(items)

    q = (query or "").lower().strip()
    if q:
        def matches(c: Dict[str, Any]) -> bool:
            hay = " ".join([
                c.get("title", ""), c.get("summary", ""),
                " ".join(c.get("themes") or []), " ".join(c.get("sectors") or []),
                " ".join(x.get("ticker", "") for x in c.get("companies") or []),
                " ".join(x.get("name", "") for x in c.get("companies") or []),
            ]).lower()
            return all(word in hay for word in q.split())
        items = [c for c in items if matches(c)]

    if status == "relevant":
        items = [c for c in items if c["relevant"]]
    elif status == "archived":
        items = [c for c in items if not c["relevant"]]

    if category:
        items = [c for c in items if c.get("category") == category]
    if sector:
        items = [c for c in items if sector in (c.get("sectors") or [])]
    if theme:
        items = [c for c in items if theme in (c.get("themes") or [])]

    return {
        "available": True,
        "catalysts": items[:limit],
        "matched": len(items),
        "stored_total": total,
        "facets": facets(),
        "scan": scan_status(),
        "method": (
            "Every catalyst here traces to a story or release this terminal "
            "fetched, and the source link is kept. Which companies are connected, "
            "how direct the link is and how strong the read-through is are "
            "judgements, not data. Every ticker is checked against EDGAR's "
            "company directory and dropped if it does not resolve, but the "
            "connection itself is an inference. Research context, never a "
            "recommendation."
        ),
    }


def facets() -> Dict[str, List[str]]:
    """The filter values actually present in the store."""
    try:
        with _connect() as conn:
            rows = conn.execute("SELECT category, sectors, themes FROM catalysts").fetchall()
    except sqlite3.Error:
        return {"categories": [], "sectors": [], "themes": []}
    cats, secs, thms = set(), set(), set()
    for r in rows:
        if r["category"]:
            cats.add(r["category"])
        for key, bucket in (("sectors", secs), ("themes", thms)):
            try:
                bucket.update(json.loads(r[key] or "[]"))
            except ValueError:
                pass
    return {"categories": sorted(cats), "sectors": sorted(secs), "themes": sorted(thms)}


def count() -> int:
    try:
        with _connect() as conn:
            return int(conn.execute("SELECT COUNT(*) FROM catalysts").fetchone()[0])
    except sqlite3.Error:
        return 0


def candidate_stories(hours: int = 168, limit: int = SCAN_STORIES) -> List[Dict[str, Any]]:
    """Recent stories worth considering as catalysts, spread across sources.

    Macro releases and world wires rather than the market desk alone, because
    the library is for events with a read-through that outlives the session: a
    policy push or a rate decision, not a single stock's move.

    The newest story from every source, then the next from every source, in
    order of weight, until the budget is spent. A plain newest-first cut is what
    handed one desk the whole scan (see SCAN_STORIES). Undated stories are left
    out: a catalyst is filed under its story's date, and an undated one would be
    filed under the day of the scan, a date on which nothing happened.
    """
    pool: List[Dict[str, Any]] = []
    for kind in ("macro", "wire"):
        try:
            entries, _status = feeds.load_kind(kind)
        except Exception as exc:
            log.warning("catalysts: %s feed unavailable: %s", kind, exc)
            continue
        pool.extend(e for e in feeds.within_hours(entries, hours)
                    if e.get("published") and e.get("title"))
    pool.sort(key=lambda e: e.get("published") or "", reverse=True)

    by_source: Dict[str, List[Dict[str, Any]]] = {}
    weight: Dict[str, float] = {}
    for e in feeds.dedupe(pool):
        sid = str(e.get("source_id") or e.get("source") or "")
        by_source.setdefault(sid, []).append(e)
        weight[sid] = max(weight.get(sid, 0.0), float(e.get("weight") or 0))
    order = sorted(by_source, key=lambda s: (-weight[s], s))

    picked: List[Dict[str, Any]] = []
    depth = 0
    while len(picked) < limit:
        layer = [by_source[s][depth] for s in order if depth < len(by_source[s])]
        if not layer:
            break
        picked.extend(layer[:limit - len(picked)])
        depth += 1
    picked.sort(key=lambda e: e.get("published") or "", reverse=True)

    return [{
        "id": "s%d" % n,
        "title": str(e.get("title") or "")[:200],
        "summary": str(e.get("summary") or "")[:SUMMARY_CHARS],
        "source": str(e.get("source") or ""),
        "desk": str(e.get("source_detail") or ""),
        "published": e.get("published"),
        "url": e.get("url"),
        "access": e.get("access"),
    } for n, e in enumerate(picked, 1)]


def _for_model(stories: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Each story as the model sees it. No URL: it would only be copied back,
    and copying is where it went missing."""
    return [{
        "id": s["id"],
        "title": s["title"],
        "summary": s["summary"],
        "source": s["source"] + (" (%s)" % s["desk"] if s.get("desk") else ""),
        "published": s["published"],
    } for s in stories]


def _stored_index(stories: List[Dict[str, Any]]) -> Dict[str, Any]:
    """The stored catalysts, in the three shapes a scan needs.

    `ids` validates a model's existing_id, `by_url` catches a catalyst it files
    again from the same story without saying so, and `library` is what it is
    shown: the relevant ones, newest first, each with the ids of any story in
    this scan it was already drawn from.
    """
    try:
        with _connect() as conn:
            rows = conn.execute(
                "SELECT id, title, event_date, horizon, source_url FROM catalysts"
                " ORDER BY event_date DESC LIMIT 500").fetchall()
    except sqlite3.Error as exc:
        log.warning("catalysts: store unreadable before a scan: %s", exc)
        rows = []
    story_ids = {s["url"]: s["id"] for s in stories if s.get("url")}
    ids, by_url, library = set(), {}, []
    for r in rows:
        ids.add(r["id"])
        if r["source_url"]:
            by_url.setdefault(r["source_url"], r["id"])
        if len(library) < LIBRARY_CONTEXT and _is_relevant(
                r["horizon"], _age_days(r["event_date"])):
            entry = {"id": r["id"], "title": r["title"], "event_date": r["event_date"]}
            if r["source_url"] in story_ids:
                entry["stories"] = [story_ids[r["source_url"]]]
            library.append(entry)
    return {"ids": ids, "by_url": by_url, "library": library}


def _cited(c: Dict[str, Any], by_id: Dict[str, Dict[str, Any]],
           by_url: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    """The fetched stories a catalyst rests on. Empty means it rests on none."""
    raw = c.get("story_ids")
    if isinstance(raw, str):
        raw = [raw]
    cited: List[Dict[str, Any]] = []
    for sid in raw if isinstance(raw, list) else []:
        story = by_id.get(str(sid).strip())
        if story is not None and story not in cited:
            cited.append(story)
    if not cited:
        # The old contract, a copied URL, still counts when it copies exactly.
        story = by_url.get(str(c.get("source_url") or "").strip())
        if story is not None:
            cited.append(story)
    return cited


# The one failure left without a named cause: the model answered, and the answer
# was not JSON the library could use.
_UNREADABLE = ("The model answered, but not in a form the library could read, so "
               "nothing was stored. The next scan tries again.")


def _failed(kind: str, reason: str, scanned: int = 0) -> Dict[str, Any]:
    _record_scan(kind, False, scanned=scanned, reason=reason)
    return {"available": False, "reason": reason}


def refresh(hours: int = 168, trigger: str = "manual") -> Dict[str, Any]:
    """Scan recent stories for catalysts and store what survives validation."""
    if not _SCAN_LOCK.acquire(blocking=False):
        return {"available": False,
                "reason": "A scan is already running. Its catalysts appear here when it finishes."}
    try:
        return _refresh(hours, trigger)
    finally:
        _SCAN_LOCK.release()


def _refresh(hours: int, trigger: str) -> Dict[str, Any]:
    from . import ai                        # local: avoids an import cycle

    stories = candidate_stories(hours=hours)
    if not stories:
        return _failed(trigger, "No recent stories to scan.")
    index = _stored_index(stories)

    found = ai.extract_catalysts(_for_model(stories), index["library"])
    # A failed call comes back as a dict with its reason, the convention every
    # writer here follows. The scan printed "Catalyst extraction failed on this
    # attempt" whatever went wrong, including a refused key, which the weekly
    # update on the same page was already naming correctly.
    if isinstance(found, dict):
        return _failed(trigger, str(found.get("reason") or _UNREADABLE),
                       scanned=len(stories))
    if found is None:
        return _failed(trigger, (
            "The assistant is not configured, so new catalysts cannot be "
            "identified. Anything already stored is still searchable."
            if ai.available().get("enabled") is not True else _UNREADABLE),
            scanned=len(stories))

    directory = ticker_directory()
    if not directory:
        return _failed(trigger, (
            "EDGAR's ticker directory is unavailable, and company links "
            "are not stored unvalidated."), scanned=len(stories))

    by_id = {s["id"]: s for s in stories}
    by_url = {s["url"]: s for s in stories if s.get("url")}
    rows: List[Dict[str, Any]] = []
    dropped = unsourced = new = 0
    for c in found:
        if not isinstance(c, dict) or not c.get("title"):
            continue
        cited = _cited(c, by_id, by_url)
        if not cited:
            unsourced += 1
            log.info("catalysts: dropped %r, no story in the scan behind it",
                     str(c["title"])[:80])
            continue
        # The link is the newest story a reader without a subscription can
        # open, or the newest of all when every one is paywalled, and the date
        # is that story's. Dated by the newest story cited, the first live
        # scan put 2026-09-28 on a fuel-economy rollback whose linked story
        # was from the 26th and a Fed proposal released on the 24th: a card
        # whose date and link disagree.
        link = max(cited, key=lambda s: (feeds.is_reachable(s), str(s["published"])))
        event_date = str(link["published"])[:10]
        title = _plain(c["title"])[:200]

        existing = str(c.get("existing_id") or "").strip()
        if existing in index["ids"]:
            ident = existing
        else:
            ident = next((index["by_url"][s["url"]] for s in cited
                          if s.get("url") in index["by_url"]), None)
        if ident is None:
            ident = hashlib.sha1(
                (str(link.get("url") or "") + "|" + title).encode("utf-8")).hexdigest()[:16]
        if any(r["id"] == ident for r in rows):
            continue                        # two answers about one catalyst; the first stands
        if ident not in index["ids"]:
            new += 1

        companies = validate_companies(c.get("companies"), directory)
        dropped += max(0, len(c.get("companies") or []) - len(companies))
        horizon = str(c.get("horizon", "")).lower().strip()
        category = str(c.get("category", "")).lower().strip()
        rows.append({
            "id": ident,
            "event_date": event_date,
            "title": title,
            "summary": _plain(c.get("summary"))[:900],
            "category": category if category in CATEGORIES else "government",
            "horizon": horizon if horizon in HORIZONS else "medium-term",
            "themes": [_plain(t)[:60] for t in (c.get("themes") or [])][:4],
            "sectors": [str(t)[:40] for t in (c.get("sectors") or [])][:5],
            "companies": companies,
            "source_url": link.get("url") or None,
            "source_name": str(link.get("source") or "")[:80] or None,
        })

    written = upsert(rows)
    _record_scan(trigger, True, scanned=len(stories), identified=len(rows),
                 written=written, unsourced=unsourced)
    return {
        "available": True,
        "scanned": len(stories),
        "identified": len(rows),
        "new": new,
        "written": written,
        "tickers_dropped": dropped,
        "unsourced": unsourced,
        "stored_total": count(),
    }
