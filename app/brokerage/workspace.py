"""The Brokerage workspace's sections, assembled from stored data.

Nothing here calls the brokerage provider: a page view reads what the last
sync stored (holdings, transactions, balance history, snapshots), so opening
the workspace can never spend a provider call or breach its rate limits. The
market-data lookups (quotes, calendars, fundamentals, price history, fund
holdings) are injected by `app.main` through `set_market`, are shared across
readers through the providers' own caches, and are bounded per section.

Every section takes the signed-in reader and an optional account scope; the
scope is always intersected with the reader's own accounts
(`service.scoped`), so no id in a request can reach another reader's data.

Each section says where its figures come from:
- `broker`: what the brokerage reported, with the account's sync time and the
  broker's own "as of" where it gave one;
- `market`: Optic's quotes and market data, with their own times;
- `optic`: Optic's calculations, with a version and method.
"""

from __future__ import annotations

import hashlib
import json
import logging
import threading
import time
from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple

from . import alerts as alerts_mod
from . import briefing as briefing_mod
from . import desk_section
from . import events as events_mod
from . import portfolio, service, store

log = logging.getLogger("optic.brokerage")

MARKET: Dict[str, Callable] = {}
SECTION_TTL = 60.0             # seconds a section's assembled payload is reused for the same reader and data
_cache: Dict[str, Tuple[float, Any]] = {}
_cache_lock = threading.Lock()
MAX_QUOTES = 40


def set_market(**fns: Callable) -> None:
    MARKET.update(fns)


def _m(name: str) -> Optional[Callable]:
    return MARKET.get(name)


def _safe(fn: Optional[Callable], *a: Any, default: Any = None, **k: Any) -> Any:
    if fn is None:
        return default
    try:
        out = fn(*a, **k)
    except Exception as exc:                                    # noqa: BLE001
        log.info("workspace lookup %s failed: %s", getattr(fn, "__name__", "?"), type(exc).__name__)
        return default
    return default if out is None else out


def _version(uid: str, scope: List[str]) -> str:
    """Changes when a sync, a selection or a nickname changes what a section
    would show, so a cached section is never older than the stored data."""
    rows = store.accounts(uid)
    stamp = "|".join("{}:{}:{}:{}:{}".format(a["id"], a.get("last_sync_at"), a.get("selected"), a.get("name"),
                                             a.get("activities_synced_at")) for a in rows)
    return hashlib.sha256((stamp + "|" + ",".join(sorted(scope))).encode()).hexdigest()[:16]


def _cached(key: str, producer: Callable[[], Any], ttl: float = SECTION_TTL) -> Any:
    now = time.monotonic()
    with _cache_lock:
        hit = _cache.get(key)
        if hit and now - hit[0] < ttl:
            return hit[1]
    value = producer()
    with _cache_lock:
        if len(_cache) > 400:
            for k in sorted(_cache, key=lambda k: _cache[k][0])[:100]:
                _cache.pop(k, None)
        _cache[key] = (now, value)
    return value


def forget(user_id: str) -> None:
    """Drop every cached section for a reader (after a sync or a delete)."""
    with _cache_lock:
        for k in [k for k in _cache if k.startswith(user_id + ":")]:
            _cache.pop(k, None)


def _lookups() -> Dict[str, Callable]:
    from . import routes as broute
    return dict(broute.LOOKUPS)


def _core(user: Dict[str, Any], account_ids: Optional[List[str]]) -> Dict[str, Any]:
    """The overview for the scope, cached per reader, scope and data version."""
    uid = user["id"]
    _, chosen = service.scoped(uid, account_ids)
    key = "{}:core:{}".format(uid, _version(uid, chosen))
    return _cached(key, lambda: service.overview(user, account_ids=chosen or None, **_lookups()))


def _freshness(core: Dict[str, Any], quotes: Optional[Dict[str, Dict[str, Any]]] = None) -> Dict[str, Any]:
    as_of = core.get("as_of") or {}
    qt = [q.get("as_of") for q in (quotes or {}).values() if q.get("as_of")]
    delays = [q.get("delayed_minutes") for q in (quotes or {}).values() if q.get("delayed_minutes") is not None]
    return {
        "broker": {"oldest_broker_as_of": as_of.get("oldest_broker"), "broker_complete": as_of.get("broker_complete"),
                   "oldest_sync": as_of.get("oldest_sync"), "newest_sync": as_of.get("newest_sync")},
        "market": {"quotes_oldest": min(qt) if qt else None, "quotes_newest": max(qt) if qt else None,
                   "delayed_minutes": max(delays) if delays else None},
    }


def _quotes(symbols: List[str]) -> Dict[str, Dict[str, Any]]:
    fn = _m("quotes_of")
    syms = sorted({s for s in symbols if s})[:MAX_QUOTES]
    return _safe(fn, syms, default={}) if syms else {}


def _scope_meta(user: Dict[str, Any], core: Dict[str, Any]) -> Dict[str, Any]:
    accts = core.get("accounts") or []
    return {"accounts": [{"id": a.get("id"), "name": a.get("name"), "number_mask": a.get("number_mask"),
                          "account_type": a.get("account_type"), "selected": bool(a.get("selected")),
                          "sync_state": a.get("sync_state")} for a in accts],
            "scope": core.get("scope") or [], "counted": core.get("accounts_counted")}


# ------------------------------------------------------------------ overview


def overview(user: Dict[str, Any], account_ids: Optional[List[str]] = None,
             today: Optional[date] = None) -> Dict[str, Any]:
    """What do I own, what changed, what deserves attention."""
    core = _core(user, account_ids)
    today = today or date.today()
    holdings = core.get("holdings") or []
    quotes = _quotes([h.get("symbol") for h in holdings if h.get("kind") in ("equity", "etf", "fund", "crypto")])
    ev = events(user, account_ids, today=today, core=core)
    brief = briefing_mod.build(core, ev, quotes, news_of=None)
    totals = core.get("totals") or {}
    unseen = 0
    try:
        unseen = alerts_mod.listing(user["id"], limit=50)["unseen"]
    except Exception:                                           # noqa: BLE001
        unseen = 0
    return {
        "section": "overview",
        "scope": _scope_meta(user, core),
        "totals": totals,
        "cash": core.get("cash"),
        "top_holdings": [{k: h.get(k) for k in ("symbol", "description", "kind", "weight_pct", "market_value",
                                                "value_usd", "unrealized_pl", "unrealized_pct", "currency")}
                         for h in holdings[:5]],
        "holdings_count": len(holdings),
        "options_count": len(core.get("options") or []),
        "allocation": {"by_kind": (core.get("allocation") or {}).get("by_kind")},
        "performance": core.get("performance"),
        "today": brief["today"],
        "since_sync": brief["since_sync"],
        "observations": brief["observations"],
        "upcoming": brief["upcoming"],
        "alerts_unseen": unseen,
        "freshness": _freshness(core, quotes),
        "notes": core.get("notes") or [],
        "sources": {"totals": "broker", "today": "market", "observations": "optic", "upcoming": "market"},
    }


# ---------------------------------------------------------- holdings & exposure


def holdings(user: Dict[str, Any], account_ids: Optional[List[str]] = None) -> Dict[str, Any]:
    core = _core(user, account_ids)
    exp = exposure(user, account_ids, core=core)
    quotes = _quotes([h.get("symbol") for h in core.get("holdings") or []])
    return {
        "section": "holdings",
        "scope": _scope_meta(user, core),
        "holdings": core.get("holdings") or [],
        "options": core.get("options") or [],
        "cash": core.get("cash") or [],
        "cash_equivalents": core.get("cash_equivalents") or [],
        "unsupported": core.get("unsupported") or [],
        "allocation": core.get("allocation") or {},
        "concentration": core.get("concentration") or {},
        "performance": core.get("performance") or {},
        "price_checks": core.get("price_checks") or [],
        "quotes": {s: {k: q.get(k) for k in ("price", "prev_close", "change_pct", "as_of", "market_time",
                                             "delayed_minutes", "source")} for s, q in quotes.items()},
        "exposure": exp,
        "freshness": _freshness(core, quotes),
        "notes": core.get("notes") or [],
    }


def exposure(user: Dict[str, Any], account_ids: Optional[List[str]] = None,
             core: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    core = core or _core(user, account_ids)
    from . import exposure as exposure_mod
    held = core.get("holdings") or []
    funds = sorted({str(h["symbol"]).upper() for h in held if h.get("kind") in ("etf", "fund") and h.get("symbol")})
    lt = {s: _safe(_m("constituents_of"), s, default={"available": False, "reason": "No fund-holdings source."})
          for s in funds}
    fx = _lookups().get("fx_to_usd")

    def usd(amount: Any, ccy: Optional[str]) -> float:
        if amount is None:
            return 0.0
        if (ccy or "USD").upper() == "USD":
            return float(amount)
        r = _safe(fx, ccy)
        return float(amount) * float(r) if r else 0.0
    cash_usd = sum(usd(c.get("amount"), c.get("currency")) for c in core.get("cash") or [])
    opts_usd = sum(float(o.get("market_value_est") or 0) for o in core.get("options") or []
                   if (o.get("currency") or "USD") == "USD")
    try:
        return exposure_mod.build(held, lt, _m("sector_of") or (lambda s: None), country_of=_m("country_of"),
                                  cash_usd=round(cash_usd, 2), options_usd=round(opts_usd, 2))
    except TypeError:
        return exposure_mod.build(held, lt, _m("sector_of") or (lambda s: None), country_of=_m("country_of"))


def scorecard(user: Dict[str, Any], account_ids: Optional[List[str]] = None,
              today: Optional[date] = None) -> Dict[str, Any]:
    from . import scorecard as scorecard_mod
    core = _core(user, account_ids)
    today = today or date.today()
    held = core.get("holdings") or []
    syms = [str(h["symbol"]).upper() for h in held if h.get("symbol")][:30]
    exp = exposure(user, account_ids, core=core)
    closes = _safe(_m("closes_of"), syms + ["SPY"], "1y", default={}) or {}
    bench = closes.get("SPY") or []
    ev = events(user, account_ids, today=today, core=core)
    flat = [{"symbol": e.get("symbol"), "kind": e.get("kind"), "date": e.get("date"), "confirmed": e.get("confirmed"),
             "weight_pct": e.get("weight_pct")} for e in ev.get("events") or []]
    market = _safe(_m("market_ref"), default={"pe": None, "ten_year": None})
    out = scorecard_mod.build(held, exp, _m("fundamentals_of") or (lambda s: None),
                              {s: v for s, v in closes.items() if s != "SPY"}, bench, flat, market, today)
    out["section"] = "scorecard"
    return out


def options_risk(user: Dict[str, Any], account_ids: Optional[List[str]] = None) -> Dict[str, Any]:
    from . import options_risk as options_mod
    core = _core(user, account_ids)
    opts = core.get("options") or []
    if not opts:
        return {"section": "options", "available": False, "reason": "No option positions in the accounts counted."}
    shares: Dict[str, float] = {}
    for h in core.get("holdings") or []:
        if h.get("symbol") and h.get("kind") in ("equity", "etf"):
            shares[str(h["symbol"]).upper()] = shares.get(str(h["symbol"]).upper(), 0.0) + float(h.get("quantity") or 0)
    rate = _safe(_m("rate"), default={"rate": 0.0, "source": "unavailable", "as_of": None})
    out = options_mod.build(opts, shares, _m("spot_of") or (lambda s: None), rate,
                            _m("div_of") or (lambda s: {"yield": None, "next_ex_date": None}),
                            datetime.now(timezone.utc))
    out["section"] = "options"
    out["available"] = True
    return out


# ------------------------------------------------------------------ performance


def performance(user: Dict[str, Any], account_ids: Optional[List[str]] = None, period: str = "1y",
                benchmark: str = "SPY", today: Optional[date] = None) -> Dict[str, Any]:
    from . import performance as perf_mod
    uid = user["id"]
    today = today or date.today()
    accts, chosen = service.scoped(uid, account_ids)
    scope = [a for a in accts if a["id"] in chosen]
    rows = {a["id"]: store.account(uid, a["id"]) or {} for a in scope}
    acts = {a["id"]: store.activities(uid, a["id"]) or [] for a in scope}
    hists = {a["id"]: h for a in scope for h in [store.history(uid, a["id"])] if h}
    current = {}
    for a in scope:
        d = portfolio.account_detail(a)
        if d:
            ccy = d["currency"]
            current[a["id"]] = {"value": (d["total"] or {}).get(ccy), "currency": ccy,
                                "as_of": a.get("broker_as_of") or a.get("last_sync_at")}
    bench = _safe(_m("benchmark_of"), benchmark, default=None) if benchmark else None
    out = perf_mod.build(
        [{"id": a["id"], "name": a.get("name"), "currency": (a.get("currency") or "USD").upper(),
          "transactions_first_date": rows[a["id"]].get("activities_first_date"),
          "activities_state": rows[a["id"]].get("activities_state"),
          "history_state": rows[a["id"]].get("history_state")} for a in scope],
        acts, hists, store.daily_snapshots(uid), current, bench, today, period)
    out["section"] = "performance"
    out["data_status"] = [{"account": a.get("name"), "transactions": rows[a["id"]].get("activities_state") or "not yet",
                           "transactions_synced_at": rows[a["id"]].get("activities_synced_at"),
                           "first_transaction": rows[a["id"]].get("activities_first_date"),
                           "balance_history": rows[a["id"]].get("history_state") or "not yet"} for a in scope]
    return out


# ------------------------------------------------------------- events & research


def events(user: Dict[str, Any], account_ids: Optional[List[str]] = None, today: Optional[date] = None,
           core: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    core = core or _core(user, account_ids)
    today = today or date.today()
    key = "{}:events:{}:{}".format(user["id"], _version(user["id"], core.get("scope") or []), today.isoformat())
    return _cached(key, lambda: events_mod.build(core.get("holdings") or [], core.get("options") or [], today,
                                                 earnings_of=_m("earnings_calendar_of"),
                                                 dividend_of=_m("dividend_of")), ttl=900.0)


def theses(user: Dict[str, Any], core: Dict[str, Any]) -> Dict[str, Any]:
    from .. import db
    rows = db.rows("SELECT * FROM theses WHERE user_id = ? ORDER BY updated_at DESC", (user["id"],))
    held = {str(h.get("symbol") or "").upper(): h for h in core.get("holdings") or []}
    out = []
    for r in rows:
        sym = r["symbol"]
        out.append({"symbol": sym, "held": sym in held, "weight_pct": (held.get(sym) or {}).get("weight_pct"),
                    "why": r.get("bull") or "", "risks": r.get("bear") or "", "catalysts": r.get("catalysts") or "",
                    "reassess_if": r.get("invalidation") or "", "horizon": r.get("horizon") or "",
                    "assumptions": r.get("assumptions") or "", "saved_at": r.get("updated_at"),
                    "created_at": r.get("created_at")})
    missing = [s for s in held if s and s not in {t["symbol"] for t in out}]
    return {"theses": out, "held_without_thesis": missing[:20]}


def thesis_news(user: Dict[str, Any], symbols: List[str], since: Optional[Dict[str, str]] = None,
                limit_names: int = 8) -> Dict[str, List[Dict[str, Any]]]:
    """Developments for names with a saved thesis, newer than the thesis was
    last saved: the shared, free catalyst rows (headlines, filings, wires and
    the calendar), cached 30 minutes per symbol by `catalysts`."""
    fn = _m("catalysts_of")
    out: Dict[str, List[Dict[str, Any]]] = {}
    for sym in symbols[:limit_names]:
        rows = _safe(fn, sym, default=[]) or []
        cut = (since or {}).get(sym)
        keep = []
        for r in rows:
            when = str(r.get("event_date") or "")
            if cut and when and when < cut[:10]:
                continue
            keep.append({k: r.get(k) for k in ("id", "title", "summary", "event_date", "category", "basis",
                                               "source_name", "source_url", "upcoming", "relevant")})
        out[sym] = keep[:6]
    return out


def events_research(user: Dict[str, Any], account_ids: Optional[List[str]] = None,
                    today: Optional[date] = None) -> Dict[str, Any]:
    core = _core(user, account_ids)
    today = today or date.today()
    ev = events(user, account_ids, today=today, core=core)
    th = theses(user, core)
    since = {t["symbol"]: (t.get("saved_at") or "") for t in th["theses"]}
    news = thesis_news(user, [t["symbol"] for t in th["theses"] if t["held"]] +
                       [t["symbol"] for t in th["theses"] if not t["held"]], since)
    for t in th["theses"]:
        t["developments"] = news.get(t["symbol"], [])
    served = _safe(_m("desk_served"), default={"available": False, "reason": "The Optic Desk is not available here."})
    desk = desk_section.build(served, core.get("holdings") or [], sector_of=_m("sector_of"),
                              named_in=_m("named_in"), today=today)
    return {"section": "events", "scope": _scope_meta(user, core), "calendar": ev, "theses": th, "desk": desk,
            "alerts": alerts_mod.listing(user["id"]), "alert_settings": alerts_mod.settings(user["id"]),
            "alert_choices": alerts_mod.CHOICES}


def briefing(user: Dict[str, Any], account_ids: Optional[List[str]] = None) -> Dict[str, Any]:
    core = _core(user, account_ids)
    quotes = _quotes([h.get("symbol") for h in core.get("holdings") or []])
    ev = events(user, account_ids, core=core)
    out = briefing_mod.build(core, ev, quotes, news_of=_m("news_of"))
    out["section"] = "briefing"
    out["freshness"] = _freshness(core, quotes)
    out["facts_key"] = facts_key(out)
    return out


def facts_key(brief: Dict[str, Any]) -> str:
    """Identifies the facts a written briefing was made from: the same facts
    give the cached text back; new prices or a sync make a new one."""
    today = brief.get("today") or {}
    basis = {"day": (brief.get("generated_at") or "")[:10],
             "moves": [(r["symbol"], round(r["change_pct"], 1)) for r in (today.get("rows") or [])[:8]],
             "since": (brief.get("since_sync") or {}).get("since"),
             "upcoming": [(e.get("symbol"), e.get("kind"), e.get("date")) for e in brief.get("upcoming") or []]}
    return hashlib.sha256(json.dumps(basis, sort_keys=True).encode()).hexdigest()[:24]


# ---------------------------------------------------------------- scenarios


def scenario(user: Dict[str, Any], changes: List[Dict[str, Any]], funding: str,
             account_ids: Optional[List[str]] = None) -> Dict[str, Any]:
    from . import scenarios as scen_mod
    core = _core(user, account_ids)
    held = core.get("holdings") or []
    syms = sorted({str(h["symbol"]).upper() for h in held if h.get("symbol")} |
                  {str(c.get("symbol") or "").upper() for c in changes or [] if c.get("symbol")})[:30]
    closes = _safe(_m("closes_of"), syms + ["SPY"], "1y", default={}) or {}
    cash_usd = sum(float(c.get("amount") or 0) for c in core.get("cash") or [] if (c.get("currency") or "USD") == "USD")
    exp = exposure(user, account_ids, core=core)
    out = scen_mod.run(held, round(cash_usd, 2), changes or [], funding,
                       _m("price_of") or (lambda s: None), _m("sector_of") or (lambda s: None),
                       {s: v for s, v in closes.items() if s != "SPY"}, closes.get("SPY") or [], exposure=exp)
    out["section"] = "scenarios"
    out["scope"] = _scope_meta(user, core)
    return out


# ------------------------------------------------------------------- alerts


def refresh_alerts(user: Dict[str, Any], today: Optional[date] = None) -> int:
    """Evaluate the reader's alerts on their counted accounts (not a narrowed
    view: alerts are about the portfolio) and store the new ones."""
    today = today or date.today()
    core = _core(user, None)
    ev = events(user, None, today=today, core=core)
    th = theses(user, core)
    since = {t["symbol"]: t.get("saved_at") or "" for t in th["theses"] if t["held"]}
    news = thesis_news(user, list(since), since) if since else {}
    candidates = alerts_mod.evaluate(core, ev, store.daily_snapshots(user["id"]),
                                     service.connections_payload(user), news, _m("sector_of"),
                                     alerts_mod.settings(user["id"]), today)
    return alerts_mod.record(user["id"], candidates)


# ---------------------------------------------------------- background alerts

ALERTS_EVERY_HOURS = 6
_alerts_ran: Dict[str, float] = {}


def alerts_due(limit: int = 20, send: Optional[Callable] = None, link: str = "") -> int:
    """Refresh alerts for linked readers not refreshed in ALERTS_EVERY_HOURS,
    then email the ones who opted in. Run from the brokerage background loop,
    so an earnings alert exists before the reader next opens Optic. Readers the
    workspace is closed to (owner-only mode) are skipped."""
    from .. import db
    from ..auth import store as auth_store
    done = 0
    now = time.monotonic()
    for row in db.rows("SELECT user_id FROM brokerage_users WHERE provider_removed_at IS NULL"):
        uid = row["user_id"]
        if now - _alerts_ran.get(uid, -1e9) < ALERTS_EVERY_HOURS * 3600:
            continue
        user = auth_store.get_user(uid)
        if not user or not service.open_to(user) or not store.accounts(uid):
            continue
        _alerts_ran[uid] = now
        try:
            refresh_alerts(user)
            if send is not None:
                alerts_mod.email_pending(user, send, link)
        except Exception as exc:                                # noqa: BLE001
            log.warning("portfolio alerts skipped: %s", type(exc).__name__)
        done += 1
        if done >= limit:
            break
    return done
