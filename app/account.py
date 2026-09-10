"""What a signed-in reader owns: watchlists and saved research.

**Not to be confused with `/api/watchlist`**, singular, which already exists and
is not going away. That endpoint takes a list of symbols from the browser and
returns a computed feed for them — quotes, signals, what changed. It is stateless
and it answers guests. The routes here are the *stored* list: which symbols, in
which named list, belonging to which account. The feed endpoint stays the thing
that turns symbols into rows, whether they came from an account or from
localStorage.

**Authorization.** Every function takes the user from the session and puts the
user id in the WHERE clause. There is no route where an id from the caller
decides what is read: `PATCH /api/watchlists/{id}` on someone else's list matches
zero rows and answers 404, which is the same answer as a list that does not
exist, because to the caller those are the same thing.

**Plan limits** come from `store.PLANS` and are checked on create. They exist so
the free tier is a real tier rather than a label, and so the day a plan is sold
the enforcement is already in place and tested.

**Saved research is at `/api/saved-research`, not `/api/research`.** The latter
is taken: `app/main.py` serves the streaming deep-research endpoint there and is
registered first, so it wins. Sharing the path would have left GET working and
POST quietly running a live web search instead of saving anything.
"""

from __future__ import annotations

import json
import re
import sqlite3
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, HTTPException, Query, Request

from . import db
from .analytics import watches as watches_mod
from .auth import deps, store

router = APIRouter(prefix="/api", tags=["account"])

# Broad on purpose. The terminal loads equities (NVDA), indices (^GSPC), forex
# pairs (EURUSD=X) and crypto (BTC-USD), and a validator that only allowed
# letters would quietly refuse three of the four.
SYMBOL = re.compile(r"^[A-Za-z0-9.\-^=:]{1,20}$")

DEFAULT_LIST = "Main Watchlist"

RESEARCH_TYPES = ("note", "pulse", "deep_research", "compare", "thesis", "scan")


def _symbol(raw: Any) -> str:
    symbol = str(raw or "").strip().upper()
    if not SYMBOL.match(symbol):
        raise HTTPException(status_code=400,
                            detail="That does not look like a symbol.")
    return symbol


def _list_payload(watchlist: Dict[str, Any]) -> Dict[str, Any]:
    items = db.rows(
        "SELECT symbol, asset_type, created_at FROM watchlist_items "
        "WHERE watchlist_id = ? ORDER BY position, created_at", (watchlist["id"],))
    return {
        "id": watchlist["id"],
        "name": watchlist["name"],
        "created_at": watchlist["created_at"],
        "updated_at": watchlist["updated_at"],
        "symbols": [i["symbol"] for i in items],
        "items": items,
    }


def _lists_for(user_id: str) -> List[Dict[str, Any]]:
    return db.rows("SELECT * FROM watchlists WHERE user_id = ? ORDER BY position, created_at",
                   (user_id,))


def _owned_list(user_id: str, watchlist_id: str) -> Dict[str, Any]:
    found = db.row("SELECT * FROM watchlists WHERE id = ? AND user_id = ?",
                   (watchlist_id, user_id))
    if not found:
        raise HTTPException(status_code=404, detail="That watchlist does not exist.")
    return found


def ensure_default(user_id: str) -> Dict[str, Any]:
    """The first list, created on first use rather than at signup.

    At signup it would mean every account that never opens the watchlist owns an
    empty one. On first use it means the list exists exactly when something is
    about to go in it."""
    existing = _lists_for(user_id)
    if existing:
        return existing[0]
    now = db.utcnow()
    wid = db.new_id()
    db.execute("INSERT INTO watchlists (id,user_id,name,position,created_at,updated_at) "
               "VALUES (?,?,?,0,?,?)", (wid, user_id, DEFAULT_LIST, now, now))
    found = db.row("SELECT * FROM watchlists WHERE id = ?", (wid,))
    assert found is not None
    return found


# ------------------------------------------------------------------ watchlists


@router.get("/watchlists")
async def get_watchlists(request: Request) -> Dict[str, Any]:
    user = deps.require_user(request)
    lists = [_list_payload(w) for w in _lists_for(user["id"])]
    return {"watchlists": lists,
            "limit": store.subscription(user["id"])["limits"]["watchlists"]}


@router.post("/watchlists")
async def create_watchlist(request: Request,
                           payload: Dict[str, Any] = Body(default={})) -> Dict[str, Any]:
    user = deps.require_user(request)
    deps.csrf_guard(request)
    name = str(payload.get("name") or "").strip()[:60]
    if not name:
        raise HTTPException(status_code=400, detail="Give the list a name.")

    limit = store.subscription(user["id"])["limits"]["watchlists"]
    existing = _lists_for(user["id"])
    if len(existing) >= limit:
        raise HTTPException(
            status_code=403,
            detail="The Free plan keeps {} watchlists. Rename or delete one to make "
                   "room.".format(limit))
    if any(w["name"].lower() == name.lower() for w in existing):
        raise HTTPException(status_code=409, detail="You already have a list with that name.")

    now = db.utcnow()
    wid = db.new_id()
    db.execute("INSERT INTO watchlists (id,user_id,name,position,created_at,updated_at) "
               "VALUES (?,?,?,?,?,?)", (wid, user["id"], name, len(existing), now, now))
    symbols = payload.get("symbols")
    if isinstance(symbols, list):
        _put_symbols(wid, symbols)
    return {"ok": True, "watchlist": _list_payload(_owned_list(user["id"], wid))}


@router.patch("/watchlists/{watchlist_id}")
async def rename_watchlist(watchlist_id: str, request: Request,
                           payload: Dict[str, Any] = Body(default={})) -> Dict[str, Any]:
    user = deps.require_user(request)
    deps.csrf_guard(request)
    _owned_list(user["id"], watchlist_id)
    name = str(payload.get("name") or "").strip()[:60]
    if not name:
        raise HTTPException(status_code=400, detail="Give the list a name.")
    if db.row("SELECT id FROM watchlists WHERE user_id = ? AND id != ? "
              "AND name = ? COLLATE NOCASE", (user["id"], watchlist_id, name)):
        raise HTTPException(status_code=409, detail="You already have a list with that name.")
    db.execute("UPDATE watchlists SET name = ?, updated_at = ? WHERE id = ? AND user_id = ?",
               (name, db.utcnow(), watchlist_id, user["id"]))
    return {"ok": True, "watchlist": _list_payload(_owned_list(user["id"], watchlist_id))}


@router.put("/watchlists/{watchlist_id}/order")
async def reorder_items(watchlist_id: str, request: Request,
                        payload: Dict[str, Any] = Body(default={})) -> Dict[str, Any]:
    """Set the order of the symbols already in a list.

    Both tables have carried a `position` column and ordered by it since the
    schema was written, and nothing could ever set one: `_put_symbols` appends
    at the end and that was the only writer. So "my order" was whatever order
    things had been added in, permanently.

    Deliberately a reorder, not an upsert. It moves the symbols the list already
    holds and ignores anything else in the payload, so a stale tab replaying an
    old order cannot resurrect a symbol the reader has since deleted.
    """
    user = deps.require_user(request)
    deps.csrf_guard(request)
    _owned_list(user["id"], watchlist_id)
    wanted = payload.get("symbols")
    if not isinstance(wanted, list):
        raise HTTPException(status_code=400, detail="Send the symbols in the order you want.")

    held = {r["symbol"] for r in db.rows(
        "SELECT symbol FROM watchlist_items WHERE watchlist_id = ?", (watchlist_id,))}
    statements = []
    position = 0
    seen = set()
    for raw in wanted[:200]:
        try:
            symbol = _symbol(raw)
        except HTTPException:
            continue
        if symbol not in held or symbol in seen:
            continue
        seen.add(symbol)
        position += 1
        statements.append((
            "UPDATE watchlist_items SET position = ? WHERE watchlist_id = ? AND symbol = ?",
            (position, watchlist_id, symbol)))
    # Anything the caller did not mention keeps its relative order, after the
    # ones it did. A partial payload must not silently shuffle the remainder.
    for symbol in sorted(held - seen):
        position += 1
        statements.append((
            "UPDATE watchlist_items SET position = ? WHERE watchlist_id = ? AND symbol = ?",
            (position, watchlist_id, symbol)))
    if statements:
        db.execute_many(statements)
    db.execute("UPDATE watchlists SET updated_at = ? WHERE id = ?",
               (db.utcnow(), watchlist_id))
    return {"ok": True, "watchlist": _list_payload(_owned_list(user["id"], watchlist_id))}


@router.put("/watchlists/order")
async def reorder_lists(request: Request,
                        payload: Dict[str, Any] = Body(default={})) -> Dict[str, Any]:
    """Set the order of the lists themselves. Same rule as the one above."""
    user = deps.require_user(request)
    deps.csrf_guard(request)
    wanted = payload.get("ids")
    if not isinstance(wanted, list):
        raise HTTPException(status_code=400, detail="Send the list ids in the order you want.")
    owned = {w["id"] for w in _lists_for(user["id"])}
    statements = []
    position = 0
    seen = set()
    for wid in wanted[:50]:
        wid = str(wid)
        if wid not in owned or wid in seen:
            continue
        seen.add(wid)
        position += 1
        statements.append(("UPDATE watchlists SET position = ? WHERE id = ? AND user_id = ?",
                           (position, wid, user["id"])))
    for wid in sorted(owned - seen):
        position += 1
        statements.append(("UPDATE watchlists SET position = ? WHERE id = ? AND user_id = ?",
                           (position, wid, user["id"])))
    if statements:
        db.execute_many(statements)
    return {"ok": True, "watchlists": [_list_payload(w) for w in _lists_for(user["id"])]}


@router.delete("/watchlists/{watchlist_id}")
async def delete_watchlist(watchlist_id: str, request: Request) -> Dict[str, Any]:
    user = deps.require_user(request)
    deps.csrf_guard(request)
    _owned_list(user["id"], watchlist_id)
    # The items go with it through ON DELETE CASCADE.
    db.execute("DELETE FROM watchlists WHERE id = ? AND user_id = ?",
               (watchlist_id, user["id"]))
    return {"ok": True, "watchlists": [_list_payload(w) for w in _lists_for(user["id"])]}


def _put_symbols(watchlist_id: str, symbols: List[Any]) -> int:
    """Add symbols, ignoring the ones already there.

    `INSERT OR IGNORE` against the UNIQUE(watchlist_id, symbol) index rather
    than a read-then-write: two tabs adding the same ticker at once would both
    see it absent and both insert."""
    now = db.utcnow()
    # Positions continue from what is already there. Without them every row
    # would carry position 0 and the same second-resolution created_at, and
    # `ORDER BY position, created_at` over a set of ties is unspecified in SQL:
    # a watchlist that reordered itself between two reads. Caught by a test that
    # was checking something else.
    top = db.row("SELECT MAX(position) AS top FROM watchlist_items WHERE watchlist_id = ?",
                 (watchlist_id,))
    position = int((top or {}).get("top") or 0)
    added = 0
    statements = []
    for raw in symbols[:200]:
        try:
            symbol = _symbol(raw)
        except HTTPException:
            continue                     # skip junk in a bulk import, do not fail it
        position += 1
        statements.append((
            "INSERT OR IGNORE INTO watchlist_items (id,watchlist_id,symbol,asset_type,"
            "position,created_at) VALUES (?,?,?,'equity',?,?)",
            (db.new_id(), watchlist_id, symbol, position, now)))
        added += 1
    if statements:
        db.execute_many(statements)
    return added


@router.post("/watchlists/{watchlist_id}/items")
async def add_item(watchlist_id: str, request: Request,
                   payload: Dict[str, Any] = Body(default={})) -> Dict[str, Any]:
    user = deps.require_user(request)
    deps.csrf_guard(request)
    _owned_list(user["id"], watchlist_id)
    symbols = payload.get("symbols")
    if not isinstance(symbols, list):
        # One symbol is validated strictly: somebody typed it and wants to know
        # it did not take. Skipping silently is only right for a bulk import,
        # where one bad row should not lose the other forty.
        symbols = [_symbol(payload.get("symbol"))]
    _put_symbols(watchlist_id, symbols)
    db.execute("UPDATE watchlists SET updated_at = ? WHERE id = ?",
               (db.utcnow(), watchlist_id))
    return {"ok": True, "watchlist": _list_payload(_owned_list(user["id"], watchlist_id))}


@router.delete("/watchlists/{watchlist_id}/items/{symbol}")
async def remove_item(watchlist_id: str, symbol: str, request: Request) -> Dict[str, Any]:
    user = deps.require_user(request)
    deps.csrf_guard(request)
    _owned_list(user["id"], watchlist_id)
    db.execute("DELETE FROM watchlist_items WHERE watchlist_id = ? AND symbol = ?",
               (watchlist_id, _symbol(symbol)))
    db.execute("UPDATE watchlists SET updated_at = ? WHERE id = ?",
               (db.utcnow(), watchlist_id))
    return {"ok": True, "watchlist": _list_payload(_owned_list(user["id"], watchlist_id))}


@router.post("/watchlists/adopt")
async def adopt_local(request: Request,
                      payload: Dict[str, Any] = Body(default={})) -> Dict[str, Any]:
    """Take over a browser-held watchlist on first sign-in.

    The terminal kept watchlists in localStorage for as long as it had no
    accounts, and those lists are real work. This merges them into the account's
    default list rather than replacing it, so running it twice adds nothing the
    second time and cannot delete anything."""
    user = deps.require_user(request)
    deps.csrf_guard(request)
    symbols = payload.get("symbols")
    if not isinstance(symbols, list) or not symbols:
        raise HTTPException(status_code=400, detail="Nothing to import.")
    target = ensure_default(user["id"])
    before = len(_list_payload(target)["symbols"])
    _put_symbols(target["id"], symbols)
    after = _list_payload(target)
    return {"ok": True, "added": len(after["symbols"]) - before, "watchlist": after}


# -------------------------------------------------------------- saved research


def _research_payload(found: Dict[str, Any], full: bool = False) -> Dict[str, Any]:
    out = {
        "id": found["id"],
        "title": found["title"],
        "symbol": found.get("symbol"),
        "research_type": found.get("research_type") or "note",
        "created_at": found["created_at"],
        "updated_at": found["updated_at"],
    }
    if full:
        out["content"] = found.get("content") or ""
    else:
        # A list of forty entries does not need forty full research reports in
        # it. The preview is what the list renders; the content is one more
        # request away, on the entry that gets opened.
        out["preview"] = (found.get("content") or "")[:280]
    return out


@router.get("/saved-research")
async def list_research(request: Request,
                        symbol: str = Query("", max_length=20),
                        limit: int = Query(50, ge=1, le=200)) -> Dict[str, Any]:
    user = deps.require_user(request)
    if symbol:
        found = db.rows(
            "SELECT * FROM saved_research WHERE user_id = ? AND symbol = ? "
            "ORDER BY created_at DESC LIMIT ?",
            (user["id"], _symbol(symbol), limit))
    else:
        found = db.rows(
            "SELECT * FROM saved_research WHERE user_id = ? ORDER BY created_at DESC "
            "LIMIT ?", (user["id"], limit))
    return {"research": [_research_payload(r) for r in found],
            "limit": store.subscription(user["id"])["limits"]["saved_research"]}


@router.get("/saved-research/{research_id}")
async def get_research(research_id: str, request: Request) -> Dict[str, Any]:
    user = deps.require_user(request)
    found = db.row("SELECT * FROM saved_research WHERE id = ? AND user_id = ?",
                   (research_id, user["id"]))
    if not found:
        raise HTTPException(status_code=404, detail="That saved research is not here.")
    return {"research": _research_payload(found, full=True)}


@router.post("/saved-research")
async def save_research(request: Request,
                        payload: Dict[str, Any] = Body(default={})) -> Dict[str, Any]:
    user = deps.require_user(request)
    deps.csrf_guard(request)
    title = str(payload.get("title") or "").strip()[:200]
    content = str(payload.get("content") or "")
    kind = str(payload.get("research_type") or "note").strip().lower()
    symbol_raw = payload.get("symbol")
    if not content.strip():
        raise HTTPException(status_code=400, detail="There is nothing to save.")
    if kind not in RESEARCH_TYPES:
        kind = "note"
    symbol = _symbol(symbol_raw) if symbol_raw else None
    if not title:
        title = "{} research".format(symbol) if symbol else "Research note"

    limit = store.subscription(user["id"])["limits"]["saved_research"]
    count = db.row("SELECT COUNT(*) AS n FROM saved_research WHERE user_id = ?",
                   (user["id"],))
    if int((count or {}).get("n") or 0) >= limit:
        raise HTTPException(
            status_code=403,
            detail="This plan keeps {} saved items. Delete one to save another.".format(limit))

    now = db.utcnow()
    rid = db.new_id()
    db.execute(
        "INSERT INTO saved_research (id,user_id,title,symbol,content,research_type,"
        "created_at,updated_at) VALUES (?,?,?,?,?,?,?,?)",
        # 200 KB is far more than any answer this app produces and stops one
        # entry filling the volume.
        (rid, user["id"], title, symbol, content[:200000], kind, now, now))
    saved = db.row("SELECT * FROM saved_research WHERE id = ?", (rid,))
    assert saved is not None
    return {"ok": True, "research": _research_payload(saved, full=True)}


@router.delete("/saved-research/{research_id}")
async def drop_research(research_id: str, request: Request) -> Dict[str, Any]:
    user = deps.require_user(request)
    deps.csrf_guard(request)
    removed = db.execute("DELETE FROM saved_research WHERE id = ? AND user_id = ?",
                         (research_id, user["id"]))
    if not removed:
        raise HTTPException(status_code=404, detail="That saved research is not here.")
    return {"ok": True}


# ------------------------------------------------------------------- watches
#
# `app/analytics/watches.py` evaluates a watch and stays stateless; this stores
# the definitions. The split matters: evaluation reads live market panels and
# must not care whose watch it is, and storage cares about nothing else.
#
# **Params are serialised with sorted keys** so that the UNIQUE index on
# (user_id, symbol, kind, params) actually catches a duplicate. `{"level": 100}`
# and `{ "level" : 100 }` are the same watch, and a naive `json.dumps` of two
# equal dicts is only guaranteed to agree if the key order does.

MAX_WATCHES = 40


def _params_key(params: Dict[str, Any]) -> str:
    return json.dumps(params or {}, sort_keys=True, separators=(",", ":"))


def _watch_payload(found: Dict[str, Any]) -> Dict[str, Any]:
    try:
        params = json.loads(found.get("params") or "{}")
    except (TypeError, ValueError):
        params = {}
    try:
        evidence = json.loads(found.get("last_evidence") or "null")
    except (TypeError, ValueError):
        evidence = None
    return {
        "id": found["id"],
        "symbol": found["symbol"],
        "kind": found["kind"],
        "params": params,
        "note": found.get("note"),
        "active": bool(found.get("active")),
        "created_at": found["created_at"],
        "last_met_at": found.get("last_met_at"),
        "last_evidence": evidence,
    }


@router.get("/watches")
async def list_watches(request: Request,
                       symbol: str = Query("", max_length=20)) -> Dict[str, Any]:
    user = deps.require_user(request)
    if symbol:
        found = db.rows("SELECT * FROM watches WHERE user_id = ? AND symbol = ? "
                        "ORDER BY created_at", (user["id"], _symbol(symbol)))
    else:
        found = db.rows("SELECT * FROM watches WHERE user_id = ? "
                        "ORDER BY symbol, created_at", (user["id"],))
    return {"watches": [_watch_payload(w) for w in found], "limit": MAX_WATCHES}


@router.post("/watches")
async def create_watch(request: Request,
                       payload: Dict[str, Any] = Body(default={})) -> Dict[str, Any]:
    user = deps.require_user(request)
    deps.csrf_guard(request)

    symbol = _symbol(payload.get("symbol"))
    kind = str(payload.get("kind") or "").strip()
    if kind not in watches_mod.CONDITIONS:
        # Validated against the catalogue rather than accepted and left to fail
        # at evaluation time, where the failure would look like the watch being
        # broken instead of never having been valid.
        raise HTTPException(status_code=400,
                            detail="That is not a condition Optic can watch for.")

    spec = watches_mod.CONDITIONS[kind]
    params: Dict[str, Any] = {}
    if spec.get("param"):
        key = spec["param"]["key"]
        raw = (payload.get("params") or {}).get(key, payload.get(key))
        if raw is None or str(raw).strip() == "":
            raise HTTPException(
                status_code=400,
                detail="{} needs a value for {}.".format(spec["label"],
                                                         spec["param"]["label"]))
        kind_of = spec["param"].get("kind")
        if kind_of in ("price", "percent", "number", "days"):
            try:
                number = float(raw)
            except (TypeError, ValueError):
                raise HTTPException(status_code=400,
                                    detail="{} has to be a number.".format(
                                        spec["param"]["label"]))
            if number != number or number in (float("inf"), float("-inf")):
                raise HTTPException(status_code=400,
                                    detail="{} has to be a real number.".format(
                                        spec["param"]["label"]))
            if kind_of == "days":
                number = max(1, min(365, int(number)))
            params[key] = number
        else:
            value = str(raw).strip().lower()[:32]
            allowed = [str(c["value"]) for c in (spec["param"].get("choices") or [])]
            if allowed and value not in allowed:
                # Refused rather than stored. A watch holding a value the
                # evaluator does not recognise is silently dead, and "did not
                # fire" is indistinguishable from the correct answer.
                raise HTTPException(
                    status_code=400,
                    detail="{} has to be one of: {}.".format(
                        spec["param"]["label"], ", ".join(allowed)))
            params[key] = value

    count = db.row("SELECT COUNT(*) AS n FROM watches WHERE user_id = ?", (user["id"],))
    if int((count or {}).get("n") or 0) >= MAX_WATCHES:
        raise HTTPException(
            status_code=403,
            detail="That is {} watches, which is the limit. Delete one to add "
                   "another.".format(MAX_WATCHES))

    now = db.utcnow()
    wid = db.new_id()
    try:
        db.execute(
            "INSERT INTO watches (id,user_id,symbol,kind,params,note,active,created_at) "
            "VALUES (?,?,?,?,?,?,1,?)",
            (wid, user["id"], symbol, kind, _params_key(params),
             str(payload.get("note") or "").strip()[:200] or None, now))
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409,
                            detail="You are already watching that on {}.".format(symbol))
    saved = db.row("SELECT * FROM watches WHERE id = ?", (wid,))
    assert saved is not None
    return {"ok": True, "watch": _watch_payload(saved)}


@router.patch("/watches/{watch_id}")
async def update_watch(watch_id: str, request: Request,
                       payload: Dict[str, Any] = Body(default={})) -> Dict[str, Any]:
    user = deps.require_user(request)
    deps.csrf_guard(request)
    owned = db.row("SELECT * FROM watches WHERE id = ? AND user_id = ?",
                   (watch_id, user["id"]))
    if not owned:
        raise HTTPException(status_code=404, detail="That watch does not exist.")
    if "active" in payload:
        db.execute("UPDATE watches SET active = ? WHERE id = ? AND user_id = ?",
                   (1 if payload.get("active") else 0, watch_id, user["id"]))
    if "note" in payload:
        db.execute("UPDATE watches SET note = ? WHERE id = ? AND user_id = ?",
                   (str(payload.get("note") or "").strip()[:200] or None,
                    watch_id, user["id"]))
    found = db.row("SELECT * FROM watches WHERE id = ?", (watch_id,))
    assert found is not None
    return {"ok": True, "watch": _watch_payload(found)}


@router.delete("/watches/{watch_id}")
async def delete_watch(watch_id: str, request: Request) -> Dict[str, Any]:
    user = deps.require_user(request)
    deps.csrf_guard(request)
    removed = db.execute("DELETE FROM watches WHERE id = ? AND user_id = ?",
                         (watch_id, user["id"]))
    if not removed:
        raise HTTPException(status_code=404, detail="That watch does not exist.")
    return {"ok": True}


@router.post("/watches/seen")
async def record_watch_results(request: Request,
                               payload: Dict[str, Any] = Body(default={})
                               ) -> Dict[str, Any]:
    """Remember which watches have tripped, so a trip is news exactly once.

    The client checks its watches and posts the outcome back here. Without this
    step a watch that is met stays met, and every page load reports the same
    thing as though it had just happened — which is how a notification feature
    becomes something people turn off.

    Only rows the caller owns are touched, and the id comes from the body only
    as a *filter* alongside `user_id`; it can name another user's watch all it
    likes and match nothing.
    """
    user = deps.require_user(request)
    deps.csrf_guard(request)
    results = payload.get("results")
    if not isinstance(results, list):
        raise HTTPException(status_code=400, detail="Send a list of results.")

    now = db.utcnow()
    statements = []
    for row in results[:MAX_WATCHES]:
        if not isinstance(row, dict) or not row.get("id"):
            continue
        if not row.get("met"):
            continue
        # `state` matters as much as `evidence`. `_signal_flip` and
        # `_analyst_revisions` report a *state*, not a transition, by design:
        # they are stateless, so the comparison against the previous state is
        # the client's job and it needs the previous state to have been kept.
        evidence = {k: row[k] for k in ("evidence", "state", "level", "value",
                                        "detail")
                    if k in row}
        statements.append((
            "UPDATE watches SET last_met_at = ?, last_evidence = ? "
            "WHERE id = ? AND user_id = ?",
            (now, json.dumps(evidence, sort_keys=True)[:2000],
             str(row["id"]), user["id"])))
    if statements:
        db.execute_many(statements)
    return {"ok": True, "recorded": len(statements)}
