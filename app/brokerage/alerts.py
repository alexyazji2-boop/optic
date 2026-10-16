"""In-app alerts about the reader's linked portfolio.

Five kinds, each with a threshold the reader controls and a dedupe key that
decides when the same situation may be raised again:

| kind          | fires when                                                        | raised again          |
|---------------|-------------------------------------------------------------------|-----------------------|
| earnings      | a holding reports within N days (confirmed or estimated, said so) | once per report date  |
| concentration | one holding, or one sector, passes a share of the portfolio       | once a month while over |
| drift         | a holding's weight moved N points against the baseline snapshot   | once a month per direction |
| exposure      | a sector's share moved N points against the baseline snapshot     | once a month per direction |
| thesis        | something new is reported about a name with a saved thesis        | once per development  |
| connection    | a linked connection needs reconnecting or failed its last sync    | once per day          |

Alerts are derived from holdings, so their text is sealed with the reader's
brokerage data key, as the holdings are; the dedupe key is a hash, so even
the index says nothing about what is held. They go when brokerage data is
deleted (`store.purge_local`).

Email is off unless the reader turns it on, and then the message carries only
a count and a link: nothing about holdings leaves Optic by email.
"""

from __future__ import annotations

import copy
import hashlib
import json
import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional

from .. import db, vault
from . import store

log = logging.getLogger("optic.brokerage")

VERSION = "alerts-2026-10-15.1"

# The single source for the settings form: the UI renders these choices and
# the server refuses anything else (CLAUDE.md: a compared parameter needs its
# vocabulary written down).
CHOICES = {
    "earnings.days": [3, 7, 14],
    "concentration.single_pct": [10, 15, 20, 25, 33],
    "concentration.sector_pct": [30, 40, 50, 60],
    "drift.pp": [3, 5, 10],
    "exposure.pp": [5, 10, 15],
}

DEFAULTS: Dict[str, Any] = {
    "earnings": {"on": True, "days": 7},
    "concentration": {"on": True, "single_pct": 20, "sector_pct": 40},
    "drift": {"on": True, "pp": 5},
    "exposure": {"on": True, "pp": 10},
    "thesis": {"on": True},
    "connection": {"on": True},
    "email": False,
}

BASELINE_DAYS = 30          # drift and exposure compare against the snapshot about this long ago
MIN_BASELINE_DAYS = 7       # and stay quiet until there is one at least this old
KEEP_DAYS = 90


# ------------------------------------------------------------------ settings


def settings(user_id: str) -> Dict[str, Any]:
    row = db.row("SELECT settings FROM portfolio_alert_settings WHERE user_id = ?", (user_id,))
    out = copy.deepcopy(DEFAULTS)
    try:
        saved = json.loads((row or {}).get("settings") or "{}")
    except (TypeError, ValueError):
        saved = {}
    for k, v in (saved or {}).items():
        if k in out and isinstance(out[k], dict) and isinstance(v, dict):
            out[k].update({kk: vv for kk, vv in v.items() if kk in out[k]})
        elif k in out and not isinstance(out[k], dict):
            out[k] = v
    return out


def validate(changes: Dict[str, Any]) -> Dict[str, Any]:
    """Settings after `changes`, or ValueError naming what was refused."""
    out = copy.deepcopy(DEFAULTS)
    for k, v in (changes or {}).items():
        if k not in out:
            raise ValueError("Unknown alert setting: {}".format(k))
        if isinstance(out[k], dict):
            if not isinstance(v, dict):
                raise ValueError("{} takes an object.".format(k))
            for kk, vv in v.items():
                if kk not in out[k]:
                    raise ValueError("Unknown alert setting: {}.{}".format(k, kk))
                if kk == "on":
                    out[k][kk] = bool(vv)
                    continue
                allowed = CHOICES.get("{}.{}".format(k, kk))
                if allowed is None or vv not in allowed:
                    raise ValueError("{}.{} must be one of {}.".format(k, kk, allowed))
                out[k][kk] = vv
        else:
            out[k] = bool(v)
    return out


def save_settings(user_id: str, changes: Dict[str, Any]) -> Dict[str, Any]:
    current = settings(user_id)
    merged = copy.deepcopy(current)
    for k, v in (changes or {}).items():
        if isinstance(merged.get(k), dict) and isinstance(v, dict):
            merged[k].update(v)
        else:
            merged[k] = v
    clean = validate(merged)
    db.execute("INSERT INTO portfolio_alert_settings (user_id, settings, updated_at) VALUES (?,?,?) "
               "ON CONFLICT(user_id) DO UPDATE SET settings = excluded.settings, updated_at = excluded.updated_at",
               (user_id, json.dumps(clean), db.utcnow()))
    return clean


# ---------------------------------------------------------------- evaluation


def _key(*parts: Any) -> str:
    return hashlib.sha256("|".join(str(p) for p in parts).encode()).hexdigest()[:32]


def _month(today: date) -> str:
    return today.strftime("%Y-%m")


def baseline(snapshots: List[Dict[str, Any]], today: date) -> Optional[Dict[str, Any]]:
    """The daily snapshot nearest BASELINE_DAYS ago, but at least
    MIN_BASELINE_DAYS old; None before there is one."""
    best = None
    for s in snapshots:
        d = (s.get("taken_at") or "")[:10]
        try:
            age = (today - date.fromisoformat(d)).days
        except ValueError:
            continue
        if age < MIN_BASELINE_DAYS:
            continue
        if best is None or abs(age - BASELINE_DAYS) < abs(best[0] - BASELINE_DAYS):
            best = (age, s)
    return best[1] if best else None


def _weights_of(snapshot: Dict[str, Any]) -> Dict[str, float]:
    """Share of long value by symbol in a stored snapshot (options excluded,
    the same denominator the overview uses for its weights)."""
    vals: Dict[str, float] = {}
    for p in (snapshot.get("positions") or {}).values():
        if p.get("kind") == "option" or not p.get("symbol"):
            continue
        v = float(p.get("value") or 0.0)
        if v > 0:
            vals[str(p["symbol"]).upper()] = vals.get(str(p["symbol"]).upper(), 0.0) + v
    total = sum(vals.values())
    return {k: 100.0 * v / total for k, v in vals.items()} if total else {}


def evaluate(overview: Dict[str, Any], events: Dict[str, Any], snapshots: List[Dict[str, Any]],
             connections: List[Dict[str, Any]], theses_news: Dict[str, List[Dict[str, Any]]],
             sector_of: Any, prefs: Dict[str, Any], today: date) -> List[Dict[str, Any]]:
    """Candidate alerts from what the workspace already computed. Pure: no
    lookups beyond `sector_of`, which the caller backs with its cache."""
    out: List[Dict[str, Any]] = []

    def add(kind, dedupe, title, body, symbol=None, link=None, severity="info"):
        out.append({"kind": kind, "dedupe_key": _key(kind, *dedupe), "title": title, "body": body,
                    "symbol": symbol, "link": link, "severity": severity})

    if prefs["earnings"]["on"]:
        for e in (events or {}).get("events") or []:
            if e.get("kind") == "earnings" and e.get("days_away", 99) <= prefs["earnings"]["days"]:
                when = "today" if e["days_away"] == 0 else "in {} day{}".format(
                    e["days_away"], "" if e["days_away"] == 1 else "s")
                add("earnings", (e["symbol"], e["date"]),
                    "{} reports {}{}".format(e["symbol"], when, "" if e.get("confirmed") else " (estimated date)"),
                    "{:.1f}% of your portfolio. {}".format(e.get("weight_pct") or 0.0,
                                                           "Date confirmed." if e.get("confirmed") else
                                                           "The company has not confirmed the date."),
                    symbol=e["symbol"], link="#/{}/earnings".format(e["symbol"]))

    weights = {str(h.get("symbol") or "").upper(): float(h.get("weight_pct") or 0.0)
               for h in overview.get("holdings") or [] if h.get("symbol")}
    funds = {str(h.get("symbol") or "").upper() for h in overview.get("holdings") or []
             if h.get("kind") in ("etf", "fund")}
    if prefs["concentration"]["on"]:
        cap = prefs["concentration"]["single_pct"]
        for sym, w in weights.items():
            # A fund is many companies: VOO at 47% of a portfolio is not the
            # risk a single stock at 47% is (first local run, 2026-10-16).
            if w >= cap and sym not in funds:
                add("concentration", (sym, cap, _month(today)),
                    "{} is {:.1f}% of your portfolio".format(sym, w),
                    "Above the {}% you set for a single holding. Exposure through funds is in Holdings & "
                    "Exposure.".format(cap), symbol=sym, link="#/brokerage/holdings", severity="watch")
        scap = prefs["concentration"]["sector_pct"]
        for row in ((overview.get("allocation") or {}).get("by_sector") or []):
            share = float(row.get("share_of_long_pct", row.get("share_pct")) or 0.0)
            label = row.get("label") or row.get("key")
            if share >= scap and label and "not looked through" not in str(label):
                add("concentration", ("sector", label, scap, _month(today)),
                    "{} is {:.1f}% of your portfolio".format(label, share),
                    "Above the {}% you set for one sector, counting directly held stocks.".format(scap),
                    link="#/brokerage/holdings", severity="watch")

    base = baseline(snapshots or [], today)
    if base is not None:
        then = _weights_of(base)
        since = (base.get("taken_at") or "")[:10]
        if prefs["drift"]["on"]:
            pp = prefs["drift"]["pp"]
            for sym in set(weights) | set(then):
                d = weights.get(sym, 0.0) - then.get(sym, 0.0)
                if abs(d) >= pp and sym in weights and sym in then:
                    add("drift", (sym, "up" if d > 0 else "down", _month(today)),
                        "{} weight {} {:.1f} points".format(sym, "up" if d > 0 else "down", abs(d)),
                        "{:.1f}% now against {:.1f}% on {}. Price moves and trades both count.".format(
                            weights[sym], then[sym], since), symbol=sym, link="#/brokerage/holdings")
        if prefs["exposure"]["on"] and sector_of is not None:
            pp = prefs["exposure"]["pp"]

            def sectors(ws: Dict[str, float]) -> Dict[str, float]:
                acc: Dict[str, float] = {}
                for sym, w in ws.items():
                    try:
                        sec = sector_of(sym)
                    except Exception:                           # noqa: BLE001
                        sec = None
                    if sec:
                        acc[sec] = acc.get(sec, 0.0) + w
                return acc
            now_s, then_s = sectors(weights), sectors(then)
            for sec in set(now_s) | set(then_s):
                d = now_s.get(sec, 0.0) - then_s.get(sec, 0.0)
                if abs(d) >= pp:
                    add("exposure", (sec, "up" if d > 0 else "down", _month(today)),
                        "{} exposure {} {:.1f} points".format(sec, "up" if d > 0 else "down", abs(d)),
                        "{:.1f}% now against {:.1f}% on {}, counting directly held stocks.".format(
                            now_s.get(sec, 0.0), then_s.get(sec, 0.0), since), link="#/brokerage/holdings")

    if prefs["thesis"]["on"]:
        for sym, rows in (theses_news or {}).items():
            for r in rows[:3]:
                add("thesis", (sym, r.get("id") or r.get("title")),
                    "New for your {} thesis: {}".format(sym, (r.get("title") or "")[:90]),
                    "{}{}. Compare it with what you wrote; nothing in your thesis was changed.".format(
                        r.get("source_name") or r.get("basis") or "Reported",
                        " on {}".format(r.get("event_date")) if r.get("event_date") else ""),
                    symbol=sym, link="#/brokerage/events")

    if prefs["connection"]["on"]:
        for c in connections or []:
            if c.get("status") in ("expired", "error", "outage"):
                add("connection", (c.get("id"), c.get("status"), today.isoformat()),
                    "{} {}".format(c.get("institution") or "A connection",
                                   "needs reconnecting" if c["status"] == "expired" else "did not sync"),
                    c.get("status_reason") or "Open Connections to see what happened.",
                    link="#/brokerage/connections", severity="watch")
    return out


# -------------------------------------------------------------------- storage


def record(user_id: str, candidates: Iterable[Dict[str, Any]]) -> int:
    """Store new alerts; a dedupe key already stored is a no-op. Returns how
    many were new."""
    key = store.dek(user_id)
    if key is None:
        return 0
    new = 0
    now = db.utcnow()
    for c in candidates:
        if db.row("SELECT 1 FROM portfolio_alerts WHERE user_id = ? AND dedupe_key = ?", (user_id, c["dedupe_key"])):
            continue
        aid = db.new_id()
        body = {k: c.get(k) for k in ("kind", "title", "body", "symbol", "link", "severity")}
        sealed = vault.seal(key, json.dumps(body), "alert:{}:{}".format(user_id, aid))
        try:
            db.execute("INSERT INTO portfolio_alerts (id, user_id, kind, dedupe_key, payload, created_at) "
                       "VALUES (?,?,?,?,?,?)", (aid, user_id, c["kind"], c["dedupe_key"], sealed, now))
            new += 1
        except Exception:                                       # noqa: BLE001  (a racing insert of the same key)
            continue
    cutoff = (datetime.now(timezone.utc) - timedelta(days=KEEP_DAYS)).strftime("%Y-%m-%dT%H:%M:%SZ")
    db.execute("DELETE FROM portfolio_alerts WHERE user_id = ? AND created_at < ?", (user_id, cutoff))
    return new


def listing(user_id: str, limit: int = 50) -> Dict[str, Any]:
    key = store.dek(user_id)
    rows = db.rows("SELECT * FROM portfolio_alerts WHERE user_id = ? ORDER BY created_at DESC, rowid DESC LIMIT ?",
                   (user_id, limit))
    out = []
    for r in rows:
        try:
            body = json.loads(vault.open_(key, r["payload"], "alert:{}:{}".format(user_id, r["id"]))) if key else None
        except Exception:                                       # noqa: BLE001
            body = None
        if body is None:
            continue
        out.append(dict(body, id=r["id"], created_at=r["created_at"], seen=bool(r["seen_at"])))
    return {"alerts": out, "unseen": sum(1 for a in out if not a["seen"]), "version": VERSION}


def mark_seen(user_id: str, ids: Optional[List[str]] = None) -> int:
    now = db.utcnow()
    if ids:
        n = 0
        for aid in ids[:200]:
            n += db.execute("UPDATE portfolio_alerts SET seen_at = ? WHERE user_id = ? AND id = ? AND seen_at IS NULL",
                            (now, user_id, str(aid)))
        return n
    return db.execute("UPDATE portfolio_alerts SET seen_at = ? WHERE user_id = ? AND seen_at IS NULL", (now, user_id))


def email_pending(user: Dict[str, Any], send: Any, link: str) -> bool:
    """One message naming only the count, for a reader who opted in. `send`
    is `mailer.send`; it returns False (and logs) where SMTP is not set up."""
    if not settings(user["id"]).get("email") or not user.get("email"):
        return False
    rows = db.rows("SELECT id FROM portfolio_alerts WHERE user_id = ? AND emailed_at IS NULL AND seen_at IS NULL",
                   (user["id"],))
    if not rows:
        return False
    n = len(rows)
    ok = send(user["email"], "Optic: {} new portfolio alert{}".format(n, "" if n == 1 else "s"),
              "You have {} new alert{} about your linked portfolio in Optic. Open the Brokerage page to read "
              "them. This message says nothing about your holdings by design.".format(n, "" if n == 1 else "s"),
              link)
    if ok:
        now = db.utcnow()
        for r in rows:
            db.execute("UPDATE portfolio_alerts SET emailed_at = ? WHERE id = ? AND user_id = ?",
                       (now, r["id"], user["id"]))
    return bool(ok)
