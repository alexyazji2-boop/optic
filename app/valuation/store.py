"""Saved fair-value models: immutable, reproducible snapshots per reader.

A snapshot keeps three things: the reported **base** the engine ran on (so a
later filing does not silently change an old model), the reader's
**assumptions**, and the **result** as it was. Replaying a snapshot reruns the
same engine version on the stored base and should give the stored result to
the cent; when the engine's version has moved on, the replay says so.

Rows are never updated. Saving again creates a new snapshot, so a model a
reader saved cannot be overwritten by anything, Milo included.

Authorization follows app/account.py: the user id comes from the session and
is in every WHERE clause, and another reader's id answers 404.
"""

from __future__ import annotations

import json
import math
import re
from typing import Any, Dict, List

from fastapi import APIRouter, Body, HTTPException, Request

from .. import db
from ..auth import deps
from . import MODEL_VERSION, analysis, engine

router = APIRouter(prefix="/api")

SYMBOL = re.compile(r"^[A-Z0-9.\-^=]{1,15}$")
MAX_MODELS = 300
MAX_SNAPSHOT_BYTES = 200_000
MAX_NAME, MAX_NOTE = 80, 2000


def _symbol(raw: Any) -> str:
    sym = str(raw or "").strip().upper()
    if not SYMBOL.match(sym):
        raise HTTPException(status_code=400, detail="That does not look like a symbol.")
    return sym


def _finite(obj: Any) -> bool:
    if isinstance(obj, float):
        return math.isfinite(obj)
    if isinstance(obj, dict):
        return all(_finite(v) for v in obj.values())
    if isinstance(obj, list):
        return all(_finite(v) for v in obj)
    return True


def validate_snapshot(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Keep the parts a replay needs; refuse anything malformed."""
    base = payload.get("base")
    assumptions = payload.get("assumptions")
    if not isinstance(base, dict) or not isinstance(assumptions, dict):
        raise HTTPException(status_code=400, detail="A saved model needs its base and assumptions.")
    drivers, wacc = assumptions.get("drivers"), assumptions.get("wacc")
    if not isinstance(drivers, dict) or not isinstance(wacc, dict):
        raise HTTPException(status_code=400, detail="A saved model needs its drivers and discount rate.")
    snap = {"base": base, "assumptions": {"drivers": drivers, "wacc": wacc,
                                          "changed": assumptions.get("changed") or []},
            "result": payload.get("result") if isinstance(payload.get("result"), dict) else {},
            "inputs": payload.get("inputs") if isinstance(payload.get("inputs"), dict) else {},
            "model_version": str(payload.get("model_version") or MODEL_VERSION)[:20]}
    if not _finite(snap):
        raise HTTPException(status_code=400, detail="The model contains a number that is not finite.")
    if len(json.dumps(snap)) > MAX_SNAPSHOT_BYTES:
        raise HTTPException(status_code=413, detail="That model is too large to save.")
    # A snapshot must be runnable: refuse one the engine cannot replay.
    replay(snap)
    return snap


def replay(snap: Dict[str, Any]) -> Dict[str, Any]:
    """Rerun the engine on a snapshot's own base and assumptions."""
    a = snap["assumptions"]
    try:
        r = analysis.run_case(snap["base"], a["drivers"], a["wacc"])
    except (engine.ModelError, KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="This model cannot be run: {}".format(exc))
    saved = (snap.get("result") or {}).get("per_share")
    return {"per_share": r["per_share"], "enterprise_value": r["enterprise_value"],
            "wacc": r["wacc"]["wacc"], "terminal_share": r["terminal_share"],
            "saved_per_share": saved,
            "matches": (saved is not None and abs(r["per_share"] - saved) < 0.005),
            "engine_version": MODEL_VERSION, "saved_version": snap.get("model_version"),
            "version_changed": snap.get("model_version") != MODEL_VERSION}


def _row(r: Dict[str, Any], full: bool = False) -> Dict[str, Any]:
    snap = json.loads(r["snapshot"])
    out = {"id": r["id"], "symbol": r["symbol"], "name": r["name"], "note": r["note"],
           "model_version": r["model_version"], "created_at": r["created_at"],
           "result": snap.get("result") or {}, "inputs": snap.get("inputs") or {},
           "changed": (snap.get("assumptions") or {}).get("changed") or []}
    if full:
        out["snapshot"] = snap
    return out


@router.get("/valuation-models")
async def list_models(request: Request, symbol: str = "") -> Dict[str, Any]:
    user = deps.require_user(request)
    if symbol:
        rows = db.rows("SELECT * FROM valuation_models WHERE user_id = ? AND symbol = ? "
                       "ORDER BY created_at DESC", (user["id"], _symbol(symbol)))
    else:
        rows = db.rows("SELECT * FROM valuation_models WHERE user_id = ? ORDER BY created_at DESC",
                       (user["id"],))
    return {"models": [_row(r) for r in rows], "limit": MAX_MODELS}


@router.get("/valuation-models/{model_id}")
async def get_model(model_id: str, request: Request) -> Dict[str, Any]:
    user = deps.require_user(request)
    r = db.row("SELECT * FROM valuation_models WHERE id = ? AND user_id = ?", (model_id, user["id"]))
    if r is None:
        raise HTTPException(status_code=404, detail="No saved model with that id.")
    out = _row(r, full=True)
    out["replay"] = replay(out["snapshot"])
    return out


@router.post("/valuation-models")
async def save_model(request: Request, payload: Dict[str, Any] = Body(default={})) -> Dict[str, Any]:
    user = deps.require_user(request)
    deps.csrf_guard(request)
    sym = _symbol(payload.get("symbol"))
    snap = validate_snapshot(payload)
    count = db.row("SELECT COUNT(*) AS n FROM valuation_models WHERE user_id = ?", (user["id"],))
    if int((count or {}).get("n") or 0) >= MAX_MODELS:
        raise HTTPException(status_code=403, detail="That is {} saved models, the limit. Delete one to "
                                                    "save another.".format(MAX_MODELS))
    mid, now = db.new_id(), db.utcnow()
    db.execute("INSERT INTO valuation_models (id,user_id,symbol,name,note,model_version,snapshot,created_at) "
               "VALUES (?,?,?,?,?,?,?,?)",
               (mid, user["id"], sym, str(payload.get("name") or "").strip()[:MAX_NAME],
                str(payload.get("note") or "").strip()[:MAX_NOTE], snap["model_version"],
                json.dumps(snap, separators=(",", ":")), now))
    saved = db.row("SELECT * FROM valuation_models WHERE id = ?", (mid,))
    assert saved is not None
    return {"ok": True, "model": _row(saved)}


@router.delete("/valuation-models/{model_id}")
async def delete_model(model_id: str, request: Request) -> Dict[str, Any]:
    user = deps.require_user(request)
    deps.csrf_guard(request)
    removed = db.execute("DELETE FROM valuation_models WHERE id = ? AND user_id = ?", (model_id, user["id"]))
    if not removed:
        raise HTTPException(status_code=404, detail="No saved model with that id.")
    return {"ok": True}


@router.post("/valuation-models/replay")
async def replay_unsaved(payload: Dict[str, Any] = Body(default={})) -> Dict[str, Any]:
    """Replay a snapshot held in the browser (a guest's saved model)."""
    snap = validate_snapshot(payload)
    return replay(snap)
