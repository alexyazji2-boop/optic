"""Named workspace layouts on the reader's account (Pass 2, 2026-11-17).

Home's layouts were kept in one browser (`optic.v2.workspace.v1`), so a layout made on a laptop was not there on the
phone. A reader can now name a layout, save it on the account, open it from any browser and delete it. The page
sends the layout's own JSON; this module checks its shape and size and never interprets it beyond that, so a later
panel or setting needs no change here.

Built to be shared later (round 6, organizations): every row names its owner as a kind and an id. Today the kind is
always "user"; nothing here reads or writes another kind yet.
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List

from fastapi import APIRouter, Body, HTTPException, Request

from . import db
from .auth import deps

router = APIRouter(prefix="/api/layouts", tags=["layouts"])

MAX_LAYOUTS = 20
MAX_BODY = 32 * 1024
NAME = re.compile(r"^[A-Za-z0-9 &'.,:()/\-]{1,40}$")
PANEL_ID = re.compile(r"^[a-z][a-z0-9_]{0,23}$")


def _name(raw: Any) -> str:
    name = re.sub(r"\s+", " ", str(raw or "")).strip()
    if not NAME.match(name):
        raise HTTPException(status_code=400, detail="A layout's name is 1 to 40 letters, numbers, spaces or simple punctuation.")
    return name


def check_body(body: Any) -> Dict[str, Any]:
    """The layout as the workspace sends it: {panels: [{id, span, h, hidden, grp?}], groups?: {name: SYM}}. Anything
    else is refused rather than stored."""
    if not isinstance(body, dict) or not isinstance(body.get("panels"), list) or not body["panels"]:
        raise HTTPException(status_code=400, detail="A layout needs its panels.")
    panels = []
    for p in body["panels"][:60]:
        if not isinstance(p, dict) or not PANEL_ID.match(str(p.get("id") or "")):
            raise HTTPException(status_code=400, detail="A panel in the layout is not one Optic has.")
        span = p.get("span")
        if span not in (3, 4, 6, 8, 12):
            raise HTTPException(status_code=400, detail="A panel's width is not one Optic offers.")
        h = p.get("h") if p.get("h") in ("s", "m", "l") else "m"
        grp = p.get("grp") if p.get("grp") in ("blue", "gold", "teal", "none") else None
        panels.append({"id": p["id"], "span": span, "h": h, "hidden": bool(p.get("hidden")), **({"grp": grp} if grp else {})})
    groups = {}
    for k, v in (body.get("groups") or {}).items() if isinstance(body.get("groups"), dict) else []:
        if k in ("blue", "gold", "teal") and isinstance(v, str) and re.fullmatch(r"[A-Z0-9.^=\-]{1,12}", v):
            groups[k] = v
    out = {"panels": panels, "groups": groups}
    if len(json.dumps(out)) > MAX_BODY:
        raise HTTPException(status_code=413, detail="That layout is too large to keep.")
    return out


def _out(r: Dict[str, Any]) -> Dict[str, Any]:
    return {"name": r["name"], "layout": json.loads(r["body"]), "updated_at": r["updated_at"], "shared": r["owner_kind"] != "user"}


def mine(user_id: str) -> List[Dict[str, Any]]:
    return [_out(r) for r in db.rows(
        "SELECT * FROM workspace_layouts WHERE owner_kind = 'user' AND owner_id = ? ORDER BY updated_at DESC", (user_id,))]


@router.get("")
async def list_layouts(request: Request) -> Dict[str, Any]:
    user = deps.require_user(request)
    return {"layouts": mine(user["id"]), "max": MAX_LAYOUTS}


@router.put("/{name}")
async def save_layout(name: str, request: Request, payload: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    user = deps.require_user(request)
    deps.csrf_guard(request)
    name = _name(name)
    body = check_body(payload.get("layout"))
    now = db.utcnow()
    have = db.row("SELECT id FROM workspace_layouts WHERE owner_kind = 'user' AND owner_id = ? AND name = ?", (user["id"], name))
    if have:
        db.execute("UPDATE workspace_layouts SET body = ?, updated_at = ? WHERE id = ?", (json.dumps(body), now, have["id"]))
    else:
        count = (db.row("SELECT COUNT(*) AS n FROM workspace_layouts WHERE owner_kind = 'user' AND owner_id = ?", (user["id"],)) or {}).get("n", 0)
        if count >= MAX_LAYOUTS:
            raise HTTPException(status_code=409, detail="You have {} saved layouts, the most an account keeps. Delete one to save another.".format(MAX_LAYOUTS))
        db.execute("INSERT INTO workspace_layouts (id, user_id, owner_kind, owner_id, name, body, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?)",
                   (db.new_id(), user["id"], "user", user["id"], name, json.dumps(body), now, now))
    return {"saved": True, "name": name, "replaced": bool(have), "layouts": mine(user["id"])}


@router.delete("/{name}")
async def delete_layout(name: str, request: Request) -> Dict[str, Any]:
    user = deps.require_user(request)
    deps.csrf_guard(request)
    gone = db.execute("DELETE FROM workspace_layouts WHERE owner_kind = 'user' AND owner_id = ? AND name = ?", (user["id"], _name(name)))
    if not gone:
        raise HTTPException(status_code=404, detail="No saved layout by that name.")
    return {"deleted": True, "layouts": mine(user["id"])}
