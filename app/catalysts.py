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
"""

from __future__ import annotations

import json
import logging
import os
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
"""


def _connect() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(SCHEMA)
    return conn


def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    out = dict(row)
    for key in ("themes", "sectors", "companies"):
        try:
            out[key] = json.loads(out.get(key) or "[]")
        except ValueError:
            out[key] = []
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
            "why": str(item.get("why", "")).strip()[:280],
        })
        if len(out) >= MAX_COMPANIES:
            break
    return out


# --------------------------------------------------------------- storage

def upsert(entries: List[Dict[str, Any]]) -> int:
    """Store catalysts, replacing any with the same id."""
    if not entries:
        return 0
    now = datetime.now(timezone.utc).isoformat()
    written = 0
    try:
        with _LOCK, _connect() as conn:
            for e in entries:
                if not e.get("id") or not e.get("title"):
                    continue
                conn.execute(
                    """INSERT INTO catalysts
                       (id, created_at, event_date, title, summary, category, horizon,
                        themes, sectors, companies, source_url, source_name)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                       ON CONFLICT(id) DO UPDATE SET
                         title=excluded.title, summary=excluded.summary,
                         category=excluded.category, horizon=excluded.horizon,
                         themes=excluded.themes, sectors=excluded.sectors,
                         companies=excluded.companies""",
                    (e["id"], now, e.get("event_date") or now[:10], e["title"],
                     e.get("summary", ""), e.get("category", "corporate"),
                     e.get("horizon", "medium-term"),
                     json.dumps(e.get("themes") or []),
                     json.dumps(e.get("sectors") or []),
                     json.dumps(e.get("companies") or []),
                     e.get("source_url"), e.get("source_name")),
                )
                written += 1
    except sqlite3.Error as exc:
        log.warning("catalysts: write failed: %s", exc)
        return 0
    return written


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
        "method": (
            "Every catalyst here traces to a story or release this terminal "
            "fetched, and the source link is kept. Which companies are connected, "
            "how direct the link is and how strong the read-through is are "
            "judgements, not data — every ticker is checked against EDGAR's "
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


def candidate_stories(hours: int = 168, limit: int = 30) -> List[Dict[str, Any]]:
    """Recent stories worth considering as catalysts.

    Macro releases and world wires rather than the market desk, because the
    library is for events with a read-through that outlives the session — a
    policy push or a rate decision, not a single stock's move.
    """
    out: List[Dict[str, Any]] = []
    for kind in ("macro", "wire"):
        try:
            entries, _status = feeds.load_kind(kind)
        except Exception as exc:
            log.warning("catalysts: %s feed unavailable: %s", kind, exc)
            continue
        for e in feeds.within_hours(entries, hours):
            out.append({
                "title": e.get("title"), "summary": (e.get("summary") or "")[:600],
                "url": e.get("url"), "source": e.get("source"),
                "published": e.get("published"), "kind": kind,
            })
    out.sort(key=lambda e: e.get("published") or "", reverse=True)
    return out[:limit]


def refresh(hours: int = 168) -> Dict[str, Any]:
    """Scan recent stories for catalysts and store what survives validation."""
    from . import ai                        # local: avoids an import cycle

    stories = candidate_stories(hours=hours)
    if not stories:
        return {"available": False, "reason": "No recent stories to scan."}

    found = ai.extract_catalysts(stories)
    if found is None:
        return {"available": False,
                "reason": ("The assistant is not configured, so new catalysts cannot be "
                           "identified. Anything already stored is still searchable."
                           if ai.available().get("enabled") is not True else
                           "Catalyst extraction failed on this attempt.")}

    directory = ticker_directory()
    if not directory:
        return {"available": False,
                "reason": ("EDGAR's ticker directory is unavailable, and company links "
                           "are not stored unvalidated.")}

    import hashlib
    rows, dropped = [], 0
    for c in found:
        if not isinstance(c, dict) or not c.get("title"):
            continue
        url = str(c.get("source_url") or "").strip()
        ident = hashlib.sha1((url + "|" + str(c["title"])).encode("utf-8")).hexdigest()[:16]
        companies = validate_companies(c.get("companies"), directory)
        dropped += max(0, len(c.get("companies") or []) - len(companies))
        horizon = str(c.get("horizon", "")).lower().strip()
        category = str(c.get("category", "")).lower().strip()
        rows.append({
            "id": ident,
            "event_date": str(c.get("event_date") or "")[:10] or None,
            "title": str(c["title"])[:200],
            "summary": str(c.get("summary") or "")[:900],
            "category": category if category in CATEGORIES else "government",
            "horizon": horizon if horizon in HORIZONS else "medium-term",
            "themes": [str(t)[:60] for t in (c.get("themes") or [])][:4],
            "sectors": [str(t)[:40] for t in (c.get("sectors") or [])][:5],
            "companies": companies,
            "source_url": url or None,
            "source_name": str(c.get("source") or c.get("source_name") or "")[:80] or None,
        })

    written = upsert(rows)
    return {
        "available": True,
        "scanned": len(stories),
        "identified": len(rows),
        "written": written,
        "tickers_dropped": dropped,
        "stored_total": count(),
    }
