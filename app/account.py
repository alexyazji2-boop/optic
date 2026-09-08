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

import re
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, HTTPException, Query, Request

from . import db
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
