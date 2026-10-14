"""Pre-earnings forecasts as immutable research snapshots, and their scoring.

A forecast is only worth scoring if it was made before the result was known,
from inputs that existed then. Three rules make that checkable rather than
promised:

* **Written before the cutoff or not at all.** `save()` refuses a forecast
  whose `created_at` is at or after the release cutoff (06:00 ET for a release
  before the open, 16:00 ET after the close, midnight ET when the timing is
  unknown). A refused forecast is not stored under a different label.
* **Never edited.** SQLite triggers abort any UPDATE or DELETE on both tables.
  The outcome is a separate row that points at the forecast, so scoring adds
  information without touching what was said.
* **Inputs travel with the forecast.** The consensus, revisions, options
  pricing and the method and policy versions are stored inside the snapshot,
  with a digest, so a later reader can see exactly what the forecast knew.

At most one forecast is kept per ticker, release date, method version and ET
day: the first of the day. Reloading a page must not stuff the record with
near-duplicates that would count one view many times.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
DB_PATH = os.path.join(os.environ.get("TRACKER_DATA_DIR", "data"), "research_forecasts.db")
_LOCK = threading.Lock()

# The minimum record before any hit rate is reported as more than a count.
# Twenty is not a significance threshold; it is the point below which a rate
# moves by five points or more with each new quarter, so quoting one would
# describe noise.
MIN_SCORED = 20

SCHEMA = [
    """CREATE TABLE IF NOT EXISTS forecasts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ticker TEXT NOT NULL, report_date TEXT NOT NULL, timing TEXT,
        period TEXT, created_at TEXT NOT NULL, created_day TEXT NOT NULL,
        release_cutoff TEXT NOT NULL, method_version TEXT NOT NULL, policy_version TEXT NOT NULL,
        forecast TEXT NOT NULL, digest TEXT NOT NULL,
        UNIQUE (ticker, report_date, method_version, created_day))""",
    """CREATE TABLE IF NOT EXISTS outcomes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        forecast_id INTEGER NOT NULL UNIQUE REFERENCES forecasts(id),
        recorded_at TEXT NOT NULL, actual TEXT NOT NULL, scores TEXT NOT NULL)""",
    """CREATE TRIGGER IF NOT EXISTS forecasts_no_update BEFORE UPDATE ON forecasts
       BEGIN SELECT RAISE(ABORT, 'saved forecasts are immutable'); END""",
    """CREATE TRIGGER IF NOT EXISTS forecasts_no_delete BEFORE DELETE ON forecasts
       BEGIN SELECT RAISE(ABORT, 'saved forecasts are immutable'); END""",
    """CREATE TRIGGER IF NOT EXISTS outcomes_no_update BEFORE UPDATE ON outcomes
       BEGIN SELECT RAISE(ABORT, 'recorded outcomes are immutable'); END""",
    """CREATE TRIGGER IF NOT EXISTS outcomes_no_delete BEFORE DELETE ON outcomes
       BEGIN SELECT RAISE(ABORT, 'recorded outcomes are immutable'); END""",
]


def _connect() -> sqlite3.Connection:
    d = os.path.dirname(DB_PATH)
    if d:
        os.makedirs(d, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=5)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    for stmt in SCHEMA:
        conn.execute(stmt)
    return conn


def _digest(blob: Dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(blob, sort_keys=True, default=str).encode()).hexdigest()


def snapshot_of(pre: Dict[str, Any]) -> Dict[str, Any]:
    """What is kept: the predictions, the view, and every input they used."""
    keep = ("release", "consensus", "revisions", "surprise_history", "trajectory", "run_up", "hurdle",
            "options", "predictions", "view", "not_available")
    out = {k: pre.get(k) for k in keep}
    # News is kept as titles and links only: the full list is long and the
    # forecast's reasoning does not read it.
    out["news"] = [{"title": s.get("title"), "published": s.get("published"), "kind": s.get("kind")}
                   for s in ((pre.get("news") or {}).get("stories") or [])[:8]]
    return out


def save(ticker: str, pre: Dict[str, Any], method_version: str, policy_version: str,
         now: Optional[datetime] = None) -> Dict[str, Any]:
    """Store a pre-earnings forecast if it is genuinely pre-release.

    Returns {saved: bool, id?, reason?}. `saved` False with reason 'duplicate'
    means today's forecast for this release already exists, which is normal."""
    now = now or datetime.now(timezone.utc)
    rel = (pre or {}).get("release") or {}
    cutoff = rel.get("cutoff_utc")
    if not pre or not pre.get("available") or not rel.get("date") or not cutoff:
        return {"saved": False, "reason": "No release date, so there is no cutoff to be before."}
    if now >= datetime.fromisoformat(cutoff):
        return {"saved": False, "reason": "after_cutoff",
                "text": "The release cutoff ({}) has passed, so this cannot be stored as a pre-release "
                        "forecast.".format(cutoff)}
    snap = snapshot_of(pre)
    row = (ticker.upper(), rel["date"], rel.get("timing"), rel.get("period"), now.isoformat(),
           now.astimezone(ET).date().isoformat(), cutoff, method_version, policy_version,
           json.dumps(snap, default=str), _digest(snap))
    try:
        with _LOCK, _connect() as conn:
            cur = conn.execute(
                "INSERT OR IGNORE INTO forecasts (ticker, report_date, timing, period, created_at, created_day,"
                " release_cutoff, method_version, policy_version, forecast, digest)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?)", row)
            if cur.rowcount != 1:
                return {"saved": False, "reason": "duplicate"}
            return {"saved": True, "id": cur.lastrowid, "created_at": row[4]}
    except sqlite3.Error as exc:
        return {"saved": False, "reason": "storage: {}".format(exc)}


def _row(r: sqlite3.Row) -> Dict[str, Any]:
    d = dict(r)
    d["forecast"] = json.loads(d.get("forecast") or "{}")
    d["pre_release"] = d["created_at"] < d["release_cutoff"]
    return d


def for_release(ticker: str, report_date: str, tolerance_days: int = 3) -> Optional[Dict[str, Any]]:
    """The last pre-release forecast for this release (dates within a few days
    match, because feeds move an estimated date as it is confirmed)."""
    try:
        with _LOCK, _connect() as conn:
            rows = [_row(r) for r in conn.execute(
                "SELECT * FROM forecasts WHERE ticker = ? AND abs(julianday(report_date) - julianday(?)) <= ?"
                " AND created_at < release_cutoff ORDER BY created_at DESC LIMIT 1",
                (ticker.upper(), report_date, tolerance_days))]
    except sqlite3.Error:
        return None
    return rows[0] if rows else None


def history(ticker: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
    q = ("SELECT f.*, o.recorded_at AS outcome_at, o.scores AS outcome_scores FROM forecasts f"
         " LEFT JOIN outcomes o ON o.forecast_id = f.id")
    args: List[Any] = []
    if ticker:
        q += " WHERE f.ticker = ?"
        args.append(ticker.upper())
    q += " ORDER BY f.created_at DESC LIMIT ?"
    args.append(limit)
    try:
        with _LOCK, _connect() as conn:
            out = []
            for r in conn.execute(q, args):
                d = _row(r)
                d["outcome_scores"] = json.loads(d["outcome_scores"]) if d.get("outcome_scores") else None
                out.append(d)
            return out
    except sqlite3.Error:
        return []


def record_outcome(forecast_id: int, actual: Dict[str, Any], scores: Dict[str, Any],
                   now: Optional[datetime] = None) -> bool:
    """Attach what happened. Once per forecast; the first record stands."""
    now = now or datetime.now(timezone.utc)
    try:
        with _LOCK, _connect() as conn:
            cur = conn.execute("INSERT OR IGNORE INTO outcomes (forecast_id, recorded_at, actual, scores)"
                               " VALUES (?,?,?,?)", (forecast_id, now.isoformat(),
                                                     json.dumps(actual, default=str), json.dumps(scores, default=str)))
            return cur.rowcount == 1
    except sqlite3.Error:
        return False


def quality() -> Dict[str, Any]:
    """Forecast quality so far, each prediction type on its own, against a
    naive baseline: for results, always predicting the company's usual beat;
    for the reaction, a coin flip on direction."""
    rows = [r for r in history(limit=10000) if r.get("pre_release") and r.get("outcome_scores")]
    out: Dict[str, Any] = {"scored_forecasts": len(rows), "minimum": MIN_SCORED, "by_prediction": {}}
    for kind in ("results", "guidance", "reaction"):
        graded = [r["outcome_scores"]["scores"].get(kind) for r in rows
                  if isinstance(r["outcome_scores"].get("scores"), dict)]
        graded = [g for g in graded if g and g.get("correct") is not None]
        n, hits = len(graded), sum(1 for g in graded if g["correct"])
        entry: Dict[str, Any] = {"scored": n, "correct": hits}
        if n >= MIN_SCORED:
            entry["hit_rate_pct"] = round(hits / n * 100.0, 1)
            entry["status"] = "measured"
        else:
            entry["status"] = "collecting"
            entry["text"] = ("{} scored so far; a hit rate is reported from {}. Until then this is a count, not "
                             "a measure of skill.".format(n, MIN_SCORED))
        out["by_prediction"][kind] = entry
    out["baselines"] = {
        "results": "Always predicting a beat (most large companies beat EPS consensus most quarters), so a "
                   "results forecast has to do better than the company's own beat rate to show skill.",
        "reaction": "A coin flip on direction, and for two-sided calls whether the move stayed inside the "
                    "options-implied range.",
        "guidance": "Not scored: guidance outcomes are not in Optic's data.",
    }
    out["no_hindsight"] = ("Only forecasts stored before their release cutoff are scored, and the stored text is "
                           "never edited; outcomes are separate rows.")
    return out
