"""The publication workflow: one canonical edition per market date and slot.

  premarket  a trading day, written about 8:15 ET: the previous session, the
             night, today's calendar
  close      a trading day, written about 16:30 ET: the session just finished
  closed     a weekend day or market holiday, written about 10:00 ET

Generation is claimed on disk (`ai_store.claim`) so two processes, a deploy or
two readers cannot write the same edition twice, and nothing here runs on a
page load: the routes read what is kept. The loop in app/main.py
(`DESK_EDITION_AUTO`, off unless set) or the admin route writes editions.

Every stage is timed and the edition keeps its own record: how long each
stage took, what the model call cost, which evidence legs failed, which checks
failed and whether the written draft or the assembled one was published.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional
from zoneinfo import ZoneInfo

from . import evidence as ev_mod

log = logging.getLogger(__name__)
ET = ZoneInfo("America/New_York")

DB_PATH = os.path.join(os.environ.get("TRACKER_DATA_DIR", "data"), "desk_editions.db")
_LOCK = threading.Lock()

# When each slot is due, ET. Configurable as "premarket=08:15,close=16:30,closed=10:00".
DEFAULT_TIMES = {"premarket": (8, 15), "close": (16, 30), "closed": (10, 0)}
MAX_ATTEMPTS = 2
RETRY_SECONDS = 1800.0

SLOT_LABELS = {"premarket": "Before the open", "close": "After the close", "closed": "Market closed"}


def slot_times() -> Dict[str, tuple]:
    raw = os.environ.get("DESK_EDITION_TIMES", "")
    out = dict(DEFAULT_TIMES)
    for part in raw.split(","):
        if "=" in part:
            k, v = part.split("=", 1)
            try:
                h, m = v.strip().split(":")
                if k.strip() in out:
                    out[k.strip()] = (int(h), int(m))
            except ValueError:
                continue
    return out


def trading_day(day: date, session_mod) -> bool:
    if day.weekday() >= 5:
        return False
    try:
        return not session_mod.market_holidays(day.year).get(day)
    except Exception:                                              # noqa: BLE001
        return True


def due_slot(now: datetime, session_mod) -> Optional[str]:
    """The slot whose time has come today and is the latest one so: the edition
    a reader should be reading now. None before the first slot of the day."""
    et = now.astimezone(ET)
    times = slot_times()
    if not trading_day(et.date(), session_mod):
        h, m = times["closed"]
        return "closed" if (et.hour, et.minute) >= (h, m) else None
    due = None
    for slot in ("premarket", "close"):
        h, m = times[slot]
        if (et.hour, et.minute) >= (h, m):
            due = slot
    return due


def edition_key(day: date, slot: str) -> str:
    return "{}:{}".format(day.isoformat(), slot)


def next_due(now: datetime, session_mod) -> Dict[str, str]:
    et = now.astimezone(ET)
    times = slot_times()
    for offset in range(0, 8):
        day = et.date() + timedelta(days=offset)
        slots = ("premarket", "close") if trading_day(day, session_mod) else ("closed",)
        for slot in slots:
            h, m = times[slot]
            at = datetime(day.year, day.month, day.day, h, m, tzinfo=ET)
            if at > et:
                return {"slot": slot, "at": at.isoformat(), "key": edition_key(day, slot)}
    return {}


# ------------------------------------------------------------------- store

SCHEMA = """
CREATE TABLE IF NOT EXISTS editions (
  key          TEXT PRIMARY KEY,
  day          TEXT NOT NULL,
  slot         TEXT NOT NULL,
  status       TEXT NOT NULL,        -- written | assembled
  payload      TEXT NOT NULL,
  generated_at TEXT NOT NULL,
  metrics      TEXT NOT NULL DEFAULT '{}'
);
"""


def _connect() -> sqlite3.Connection:
    d = os.path.dirname(DB_PATH)
    if d:
        os.makedirs(d, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def keep(key: str, payload: Dict[str, Any], status: str, metrics: Dict[str, Any]) -> None:
    day, slot = key.split(":", 1)
    with _LOCK, _connect() as conn:
        conn.execute("INSERT OR REPLACE INTO editions (key, day, slot, status, payload, generated_at, metrics)"
                     " VALUES (?,?,?,?,?,?,?)",
                     (key, day, slot, status, json.dumps(payload, default=str),
                      datetime.now(timezone.utc).isoformat(timespec="seconds"), json.dumps(metrics, default=str)))


def load(key: str) -> Optional[Dict[str, Any]]:
    try:
        with _LOCK, _connect() as conn:
            row = conn.execute("SELECT * FROM editions WHERE key = ?", (key,)).fetchone()
    except sqlite3.Error:
        return None
    return _row(row) if row else None


def latest(before: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """The newest kept edition (optionally strictly before a key)."""
    q = "SELECT * FROM editions {} ORDER BY day DESC, CASE slot WHEN 'close' THEN 2 WHEN 'closed' THEN 2 ELSE 1 END DESC LIMIT 1"
    args: tuple = ()
    if before:
        q = q.format("WHERE key < ?")
        args = (before,)
    else:
        q = q.format("")
    try:
        with _LOCK, _connect() as conn:
            row = conn.execute(q, args).fetchone()
    except sqlite3.Error:
        return None
    return _row(row) if row else None


def archive(limit: int = 30) -> List[Dict[str, Any]]:
    try:
        with _LOCK, _connect() as conn:
            rows = conn.execute("SELECT key, day, slot, status, generated_at, payload FROM editions "
                                "ORDER BY day DESC, generated_at DESC LIMIT ?", (limit,)).fetchall()
    except sqlite3.Error:
        return []
    out = []
    for r in rows:
        p = json.loads(r["payload"])
        out.append({"key": r["key"], "day": r["day"], "slot": r["slot"], "status": r["status"],
                    "generated_at": r["generated_at"], "headline": p.get("headline"),
                    "test_edition": bool(p.get("test_edition"))})
    return out


def _row(row: sqlite3.Row) -> Dict[str, Any]:
    out = json.loads(row["payload"])
    out["key"] = row["key"]
    out["status"] = row["status"]
    out["generated_at"] = row["generated_at"]
    out["metrics"] = json.loads(row["metrics"] or "{}")
    return out


# ----------------------------------------------------------------- gather

@dataclass
class Sources:
    """What the gatherer reads, injected so a test can hand it fakes."""
    provider: Any
    macro: Callable[[], Dict[str, Any]]
    fred_series: Callable[[str], Dict[str, Any]]
    events: Callable[[], Dict[str, Any]]
    earnings_week: Callable[[], Dict[str, Any]]
    wires: Callable[[], List[Dict[str, Any]]]
    official: Callable[[], List[Dict[str, Any]]]
    rate_path: Callable[[Dict[str, Any]], Dict[str, Any]]
    index_surface: Callable[[str], Optional[Dict[str, Any]]]
    quotes: Callable[[List[str]], Dict[str, Any]]
    session_mod: Any
    sectors: List[Dict[str, str]]
    themes: List[Dict[str, str]]
    # Cboe's dispersion readings (app/analytics/dispersion.py); optional.
    dispersion: Optional[Callable[[], Dict[str, Any]]] = None
    # An index ETF's GEX read, as the Swing tab computes it; optional.
    index_gex: Optional[Callable[[str], Dict[str, Any]]] = None


def gather(src: Sources, slot: str, now: Optional[datetime] = None) -> Dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    g = ev_mod.Gatherer()
    today = now.astimezone(ET).date()
    g.leg("prices", lambda: ev_mod.gather_prices(g, src.provider, src.sectors, src.themes))
    macro = g.leg("macro", src.macro) or {}
    g.leg("macro_tape", lambda: ev_mod.gather_macro_tape(g, macro))
    g.leg("fred", lambda: ev_mod.gather_fred(g, src.fred_series, today))
    events = g.leg("calendar", src.events) or {}
    g.leg("calendar_rows", lambda: ev_mod.gather_calendar(g, events, now.astimezone(ET)))
    g.leg("rate_path", lambda: ev_mod.gather_rate_path(g, src.rate_path(events)))
    week = g.leg("earnings_week", src.earnings_week) or {}
    majors = [r.get("ticker") for d in (week.get("days") or []) for r in (d.get("rows") or [])
              if r.get("major") and r.get("ticker")]
    quotes = g.leg("earnings_quotes", lambda: src.quotes(majors) if majors else {}) or {}
    g.leg("earnings", lambda: ev_mod.gather_earnings(g, src.provider, week, quotes, today))
    since = ev_mod.news_window_start(now, slot, src.session_mod)
    wires = g.leg("wires", src.wires) or []
    official = g.leg("official", src.official) or []
    g.leg("news", lambda: ev_mod.gather_news(g, wires, official, since))
    named: List[str] = []
    for e in g.rows:
        if e.kind == "news":
            for sym in ev_mod.named_in(e.label):
                if sym not in named:
                    named.append(sym)
    for sym in majors:
        if sym not in named:
            named.append(sym)
    g.leg("companies", lambda: ev_mod.gather_companies(g, src.provider, named[:24]))
    g.leg("options", lambda: ev_mod.gather_options(g, src.index_surface))
    if src.dispersion is not None:
        disp = g.leg("dispersion", src.dispersion) or {}
        g.leg("dispersion_rows", lambda: ev_mod.gather_dispersion(g, disp))
    if src.index_gex is not None:
        spy_gex = g.leg("gamma", lambda: src.index_gex("SPY")) or {}
        g.leg("gamma_rows", lambda: ev_mod.gather_gamma(g, "SPY", spy_gex))
    try:
        session = src.session_mod.state(now)
    except Exception:                                              # noqa: BLE001
        session = {}
    out = ev_mod.bundle(g, slot=slot, now=now, session=session)
    out["news_since"] = since.isoformat()
    return out


# ---------------------------------------------------------------- publish

Writer = Callable[[Dict[str, Any], List[Dict[str, Any]], Optional[List[str]], Optional[Dict[str, Any]]],
                  "tuple"]


def compose(bundle: Dict[str, Any], writer: Optional[Writer] = None) -> Dict[str, Any]:
    """Outline, draft, check, repair once, fall back: the edition and its record.

    Pure apart from the writer, so a test can run every branch with a fake one."""
    from . import assemble, check, outline as outline_mod

    stages: Dict[str, int] = {}
    t = time.perf_counter()
    outline = outline_mod.build(bundle)
    shown = outline_mod.evidence_for(bundle, outline)
    stages["outline_ms"] = int((time.perf_counter() - t) * 1000)

    calls: List[Dict[str, Any]] = []
    result, draft, voice = None, None, "assembled"
    if writer is not None:
        t = time.perf_counter()
        draft, info = writer(outline, shown, None, None)
        calls.append(info)
        stages["draft_ms"] = int((time.perf_counter() - t) * 1000)
        if draft:
            result = check.run(draft, bundle, outline)
            if not result["ok"]:
                t = time.perf_counter()
                fixed, info = writer(outline, shown, result["errors"], draft)
                calls.append(info)
                stages["repair_ms"] = int((time.perf_counter() - t) * 1000)
                if fixed:
                    second = check.run(fixed, bundle, outline)
                    result = {**second, "first_errors": result["errors"]}
                    draft = fixed
            if result["ok"]:
                voice = "written"
    if voice != "written":
        failed_draft = result
        t = time.perf_counter()
        draft = assemble.build(bundle, outline)
        result = check.run(draft, bundle, outline)
        stages["assemble_ms"] = int((time.perf_counter() - t) * 1000)
        if failed_draft is not None:
            result["draft_refused"] = failed_draft.get("errors")
    # The evidence a reader can open from the page: everything cited, and the
    # outline's, so every source link beside a claim resolves.
    cited = set()
    from .check import units as _units
    for _, u in _units(draft):
        cited |= set(u.get("cites") or [])
    cited |= set(draft.get("headline_cites") or [])
    keep_ids = cited | {e["id"] for e in shown}
    return {
        "edition": draft,
        "voice": voice,
        "outline": {k: outline[k] for k in ("lead_theme", "theme_scores", "quiet", "relationships", "conflicts",
                                            "limits", "target_words", "watch")},
        "evidence": [e for e in bundle.get("evidence") or [] if e["id"] in keep_ids],
        "check": result,
        "calls": calls,
        "stages": stages,
    }


def publish(src: Sources, slot: str, now: Optional[datetime] = None, writer: Optional[Writer] = None,
            force: bool = False, claim: Optional[Callable[[str], bool]] = None,
            test_label: Optional[str] = None) -> Dict[str, Any]:
    """Gather, compose and keep one edition. Claimed so it is written once."""
    now = now or datetime.now(timezone.utc)
    day = now.astimezone(ET).date()
    key = edition_key(day, slot)
    if not force:
        if load(key):
            return {"key": key, "skipped": "already published"}
        if claim is not None and not claim(key):
            return {"key": key, "skipped": "claimed by another writer, or retried too recently"}
    t0 = time.perf_counter()
    bundle = gather(src, slot, now)
    gather_ms = int((time.perf_counter() - t0) * 1000)
    out = compose(bundle, writer)
    cost = sum((c.get("cost_usd") or 0) for c in out["calls"])
    metrics = {
        "stages": {"gather_ms": gather_ms, **out["stages"]},
        "total_ms": int((time.perf_counter() - t0) * 1000),
        "cost_usd": round(cost, 4),
        "calls": out["calls"],
        "coverage": bundle.get("coverage"),
        "legs_failed": [c["leg"] for c in bundle.get("coverage") or [] if not c.get("ok")],
        "evidence_counts": _counts(bundle),
        "check": {k: out["check"].get(k) for k in ("ok", "errors", "warnings", "stats", "first_errors", "draft_refused")},
    }
    payload = {
        "date": day.isoformat(),
        "slot": slot,
        "slot_label": SLOT_LABELS.get(slot, slot),
        "timezone": "America/New_York (ET)",
        "cutoff": bundle.get("cutoff"),
        "gathered_at": bundle.get("gathered_at"),
        "news_since": bundle.get("news_since"),
        "session": bundle.get("session"),
        "voice": out["voice"],
        **out["edition"],
        "outline": out["outline"],
        "evidence": out["evidence"],
        "test_edition": test_label,
    }
    keep(key, payload, out["voice"], metrics)
    log.info("desk edition %s kept (%s) in %dms, $%.4f", key, out["voice"], metrics["total_ms"], cost)
    return {"key": key, "status": out["voice"], "metrics": metrics}


def _counts(bundle: Dict[str, Any]) -> Dict[str, int]:
    out: Dict[str, int] = {}
    for e in bundle.get("evidence") or []:
        out[e["kind"]] = out.get(e["kind"], 0) + 1
    return out


def served(now: Optional[datetime] = None, session_mod=None) -> Dict[str, Any]:
    """What a reader should see now: the due edition if it is kept, else the
    newest kept one, labelled with its own date and whether it is today's."""
    now = now or datetime.now(timezone.utc)
    day = now.astimezone(ET).date()
    slot = due_slot(now, session_mod) if session_mod else None
    current = load(edition_key(day, slot)) if slot else None
    ed = current or latest()
    if not ed:
        return {"available": False, "reason": "No edition has been published yet.",
                "next": next_due(now, session_mod) if session_mod else {}}
    is_today = ed.get("date") == day.isoformat()
    return {"available": True, "edition": ed, "is_today": is_today,
            "is_current": bool(current) and ed.get("key") == (current or {}).get("key"),
            "due_slot": slot, "next": next_due(now, session_mod) if session_mod else {},
            "freshness": ("current" if current else "today's earlier edition" if is_today
                          else "from {}; today's has not been published".format(ed.get("date")))}
