"""HTTP routes for the Brokerage workspace (`/api/brokerage/workspace/...`).

Every route reads the reader from the session and answers only for them:
`_reader` refuses a guest, a reader with nothing linked, and (in owner-only
mode) anyone but the owner, with the same sentence the status route uses, so
no route confirms that linking exists to someone it is closed to. Account ids
in `accounts=` are filtered to the reader's own (`service.scoped`). State
changes pass `csrf_guard`.

The written briefing is the one route that spends money: it is metered by the
same allowance as a Milo message (`SPEND_GUARD`, injected by `app.main`) and
cached per reader and facts, so asking twice for the same facts is free.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional

from fastapi import APIRouter, Body, HTTPException, Request
from starlette.concurrency import run_in_threadpool

from ..auth import deps
from . import alerts as alerts_mod
from . import service, store, workspace

log = logging.getLogger("optic.brokerage")
router = APIRouter(prefix="/api/brokerage/workspace", tags=["brokerage-workspace"])

HOOKS: Dict[str, Callable] = {}       # spend_guard, write_brief: set by app.main
PERIODS = ("1m", "3m", "ytd", "1y", "all")
BENCHMARKS = ("SPY", "VTI", "QQQ", "ACWI", "AGG")
FUNDING = ("cash", "new_money", "pro_rata")
MAX_CHANGES = 12


def set_hooks(**fns: Callable) -> None:
    HOOKS.update(fns)


def _reader(request: Request) -> Dict[str, Any]:
    user = deps.require_user(request)
    if not service.open_to(user):
        raise HTTPException(status_code=404, detail=service.NOT_SWITCHED_ON)
    if not store.link(user["id"]) or not store.accounts(user["id"]):
        raise HTTPException(status_code=409, detail="No brokerage is linked yet. Connect one in Connections.")
    return user


def _scope(accounts: Any) -> Optional[List[str]]:
    """`accounts=` as a comma list in a query, or a list in a JSON body."""
    raw = accounts if isinstance(accounts, list) else str(accounts or "").split(",")
    ids = [str(a).strip()[:64] for a in raw if str(a).strip()]
    return ids[:20] or None


async def _run(fn: Callable, *a: Any, **k: Any) -> Dict[str, Any]:
    try:
        return await run_in_threadpool(fn, *a, **k)
    except HTTPException:
        raise
    except Exception as exc:                                    # noqa: BLE001
        log.warning("workspace %s failed: %s", getattr(fn, "__name__", "?"), type(exc).__name__)
        raise HTTPException(status_code=500, detail="That part of the workspace could not be built just now.")


@router.get("/overview")
async def ws_overview(request: Request, accounts: Optional[str] = None) -> Dict[str, Any]:
    return await _run(workspace.overview, _reader(request), _scope(accounts))


@router.get("/holdings")
async def ws_holdings(request: Request, accounts: Optional[str] = None) -> Dict[str, Any]:
    return await _run(workspace.holdings, _reader(request), _scope(accounts))


@router.get("/scorecard")
async def ws_scorecard(request: Request, accounts: Optional[str] = None) -> Dict[str, Any]:
    return await _run(workspace.scorecard, _reader(request), _scope(accounts))


@router.get("/options")
async def ws_options(request: Request, accounts: Optional[str] = None) -> Dict[str, Any]:
    return await _run(workspace.options_risk, _reader(request), _scope(accounts))


@router.get("/performance")
async def ws_performance(request: Request, accounts: Optional[str] = None, period: str = "1y",
                         benchmark: str = "SPY") -> Dict[str, Any]:
    if period not in PERIODS:
        raise HTTPException(status_code=400, detail="period must be one of {}.".format(", ".join(PERIODS)))
    if benchmark.upper() not in BENCHMARKS:
        raise HTTPException(status_code=400, detail="benchmark must be one of {}.".format(", ".join(BENCHMARKS)))
    return await _run(workspace.performance, _reader(request), _scope(accounts), period, benchmark.upper())


@router.get("/events")
async def ws_events(request: Request, accounts: Optional[str] = None) -> Dict[str, Any]:
    return await _run(workspace.events_research, _reader(request), _scope(accounts))


@router.get("/briefing")
async def ws_briefing(request: Request, accounts: Optional[str] = None) -> Dict[str, Any]:
    user = _reader(request)
    out = await _run(workspace.briefing, user, _scope(accounts))
    written = await run_in_threadpool(store.briefing, user["id"], out["facts_key"])
    latest = written or await run_in_threadpool(store.briefing, user["id"], None)
    out["written"] = written
    out["written_earlier"] = None if written else latest
    return out


@router.post("/briefing/written")
async def ws_briefing_write(request: Request, payload: Dict[str, Any] = Body(default={})) -> Dict[str, Any]:
    """Write the briefing from today's measured facts. Costs one Milo message,
    unless the same facts were already written up, when it is free."""
    user = _reader(request)
    deps.csrf_guard(request)
    facts = await _run(workspace.briefing, user, _scope((payload or {}).get("accounts")))
    kept = await run_in_threadpool(store.briefing, user["id"], facts["facts_key"])
    if kept:
        return {"written": kept, "cached": True}
    guard, writer = HOOKS.get("spend_guard"), HOOKS.get("write_brief")
    if writer is None:
        raise HTTPException(status_code=503, detail="Written briefings are not available on this server.")
    if guard is not None:
        guard(request)                                          # raises 401/429 like a Milo message
    slim = {k: facts.get(k) for k in ("today", "since_sync", "drivers", "upcoming", "observations", "limitations")}
    out = await run_in_threadpool(writer, slim)
    if out.get("available") is not True:
        raise HTTPException(status_code=502, detail=out.get("reason") or "The briefing could not be written.")
    await run_in_threadpool(store.save_briefing, user["id"], facts["facts_key"], out)
    return {"written": dict(out, facts_key=facts["facts_key"]), "cached": False}


@router.post("/scenario")
async def ws_scenario(request: Request, payload: Dict[str, Any] = Body(default={})) -> Dict[str, Any]:
    """A what-if on the current holdings. Nothing is traded: the result is
    arithmetic on hypothetical changes, and is not stored."""
    user = _reader(request)
    deps.csrf_guard(request)
    changes = (payload or {}).get("changes") or []
    funding = (payload or {}).get("funding") or "cash"
    if not isinstance(changes, list) or len(changes) > MAX_CHANGES:
        raise HTTPException(status_code=400, detail="Up to {} changes at a time.".format(MAX_CHANGES))
    if funding not in FUNDING:
        raise HTTPException(status_code=400, detail="funding must be one of {}.".format(", ".join(FUNDING)))
    clean = []
    for c in changes:
        if not isinstance(c, dict):
            raise HTTPException(status_code=400, detail="Each change is an object.")
        sym = str(c.get("symbol") or "").strip().upper()[:15]
        if not sym:
            raise HTTPException(status_code=400, detail="Each change needs a symbol.")
        try:
            amount = float(c.get("amount"))
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="{}: the amount is not a number.".format(sym))
        clean.append({"symbol": sym, "action": str(c.get("action") or ""), "amount_type": str(c.get("amount_type") or ""),
                      "amount": amount})
    return await _run(workspace.scenario, user, clean, funding, _scope((payload or {}).get("accounts")))


@router.get("/alerts")
async def ws_alerts(request: Request) -> Dict[str, Any]:
    user = _reader(request)
    out = await run_in_threadpool(alerts_mod.listing, user["id"])
    out["settings"] = alerts_mod.settings(user["id"])
    out["choices"] = alerts_mod.CHOICES
    return out


@router.post("/alerts/refresh")
async def ws_alerts_refresh(request: Request) -> Dict[str, Any]:
    user = _reader(request)
    deps.csrf_guard(request)
    new = await _run(workspace.refresh_alerts, user)
    out = await run_in_threadpool(alerts_mod.listing, user["id"])
    out["new"] = new
    return out


@router.post("/alerts/seen")
async def ws_alerts_seen(request: Request, payload: Dict[str, Any] = Body(default={})) -> Dict[str, Any]:
    user = _reader(request)
    deps.csrf_guard(request)
    ids = (payload or {}).get("ids")
    n = await run_in_threadpool(alerts_mod.mark_seen, user["id"], ids if isinstance(ids, list) else None)
    return {"ok": True, "marked": n}


@router.put("/alerts/settings")
async def ws_alerts_settings(request: Request, payload: Dict[str, Any] = Body(default={})) -> Dict[str, Any]:
    user = _reader(request)
    deps.csrf_guard(request)
    try:
        saved = await run_in_threadpool(alerts_mod.save_settings, user["id"], payload or {})
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"ok": True, "settings": saved}
