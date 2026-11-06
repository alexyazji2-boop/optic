"""The saved research library (Handoff 5 of the owner's handover pack, 2026-11-03).

**What was missing.** The authenticated audit of 2026-11-03 (defect 6) found that research had no home: a comparison,
a Milo conversation or a research sheet could not be kept and returned to as one thing. What existed, verified in the
code: the `saved_research` table (accounts database) and its page at #/research, which keep questions to ask again,
Classic's and v2's alike; Milo's conversations in this browser only (`optic.pulse.history.v1`), without the sources
behind each answer; theses and valuations in tables of their own.

**A saved item is a `saved_research` row** (migration 20 adds `tickers`, `ref`, `summary`, `payload` and `item_key`), so
the plan's limit on saved items, the account's export and deletion, and the volume backups already cover it:

- company: a Dossier, by reference (its ticker and tab). The summary keeps its name and the price when saved, so the
  item stays readable if the ticker later goes.
- comparison: Compare's tickers, by reference.
- sheet: a research sheet, by reference.
- conversation: a Milo conversation and the sources behind each answer, as they were. A reference would let the cited
  figures change under the reader, so this is the one kind that keeps a copy (`payload`), read only when it is opened.

Questions saved before (research_type "pulse" and the rest, `item_key` NULL) are listed with them, as questions.

**Rules.** Only explicit saves: nothing is saved by viewing a page. Every query is the owner's, and another account's
item is "not here" (404), never "forbidden", so an id reveals nothing. A second save of the same thing is not a second
row: the reader is asked whether to update the saved one or keep a copy under another name. The older list
(`/api/saved-research`, which Classic reads) keeps showing questions only, so Classic is unchanged.
"""

from __future__ import annotations

import json
import re
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, Iterable, List, Optional, Set

from fastapi import APIRouter, Body, HTTPException, Query, Request
from starlette.concurrency import run_in_threadpool

from . import account, db, universe
from .auth import deps, store

router = APIRouter(prefix="/api", tags=["library"])

KINDS = ("company", "comparison", "conversation", "sheet", "screen", "investigation")
# Kept by its own page as it runs (app/investigation.py, Handoff 10), never by POST /library
KEPT_ELSEWHERE = ("investigation",)
# A row saved before the library (a question to ask again) is listed as this kind
QUESTION = "question"
MAX_TICKERS = 4
PAGE, PAGE_MAX = 30, 100
NAME_MAX = 120
SUMMARY_MAX = 6000          # characters of JSON: names, prices when saved, a note
PAYLOAD_MAX = 200000        # a Milo conversation with its sources; the table's existing limit on one entry
MESSAGES_MAX = 60           # Milo's own limit on a kept conversation (ui/milo.js MAX_MESSAGES)
TABS = ("", "chart", "options", "investing", "earnings", "financials", "news")
# Set by app/main.py: the quote source, for a ticker the exchange directory does not list (an over-the-counter or
# foreign listing still trades; a delisted one has no price)
QUOTE: Optional[Callable[[str], Dict[str, Any]]] = None
GONE_TTL = 3600.0
TRADED_DAYS = 10
_LISTED: Dict[str, Any] = {}


def _err(status: int, detail: str) -> HTTPException:
    return HTTPException(status_code=status, detail=detail)


def _tickers(raw: Any, kind: str) -> List[str]:
    """The item's symbols, in the order given, each as one company is spelt everywhere (account.canonical)."""
    if raw is None:
        raw = []
    if isinstance(raw, str):
        raw = [x for x in re.split(r"[\s,]+", raw) if x]
    if not isinstance(raw, list):
        raise _err(400, "Tickers are a list of symbols.")
    out: List[str] = []
    for x in raw:
        sym = account._symbol(x)
        if sym not in out:
            out.append(sym)
    if len(out) > MAX_TICKERS:
        raise _err(400, "At most {} tickers in one saved item.".format(MAX_TICKERS))
    least = {"company": 1, "sheet": 1, "comparison": 2, "conversation": 0, "screen": 0, "investigation": 1}[kind]
    if len(out) < least:
        raise _err(400, "A {} needs {} ticker{}.".format(
            "comparison" if kind == "comparison" else "saved " + kind, least, "s" if least > 1 else ""))
    if kind in ("company", "sheet", "investigation") and len(out) > 1:
        out = out[:1]
    return out


def _ref(raw: Any, kind: str) -> Dict[str, Any]:
    """Where the item reopens, beyond its tickers: a Dossier's tab, the Milo conversation's own id."""
    raw = raw if isinstance(raw, dict) else {}
    if kind == "company":
        tab = str(raw.get("tab") or "").strip().lower()
        return {"tab": tab if tab in TABS else ""}
    if kind == "conversation":
        cid = str(raw.get("conversation") or "").strip()
        return {"conversation": cid} if re.match(r"^[A-Za-z0-9_-]{1,64}$", cid) else {}
    return {}


# A saved screen (Handoff 8): the request in words and the filters exactly as confirmed, so it reopens and runs again.
# Its key is the filters' canonical form hashed the way static/v2/js/core/library.js screenKey hashes it (FNV-1a over
# the same string), so a Save button knows the screen is already saved without asking the server to hash it.
_SCREEN_BOUND = ("min", "max")


def _canon_number(v: Any) -> str:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return ""
    return ("%.6f" % f).rstrip("0").rstrip(".") if f == f else ""


def screen_canonical(spec: Dict[str, Any]) -> str:
    """One string per screen: its filters sorted by field, its states sorted, its sort and direction."""
    parts = []
    for f in sorted(spec.get("filters") or [], key=lambda x: str(x.get("field"))):
        parts.append("{}|{}|{}|{}|{}|{}|{}".format(f.get("field"), _canon_number(f.get("min")), _canon_number(f.get("max")),
                                                  1 if f.get("min_exclusive") else 0, 1 if f.get("max_exclusive") else 0,
                                                  f.get("min_peer") or "", f.get("max_peer") or ""))
    return "{};{};{};{}".format(",".join(parts), ",".join(sorted(spec.get("states") or [])),
                                spec.get("sort") or "score", spec.get("direction") or "desc")


def fnv1a(text: str) -> str:
    h = 0x811C9DC5
    for byte in text.encode("utf-8"):
        h = ((h ^ byte) * 0x01000193) & 0xFFFFFFFF
    return "{:08x}".format(h)


def _screen(raw: Any) -> Optional[Dict[str, Any]]:
    """A screen as saved: checked against the screener's own vocabulary, as a run checks it."""
    from .analytics import screener
    if not isinstance(raw, dict):
        return None
    filters = screener.parse_filters(raw.get("filters"))
    states = screener.parse_states(raw.get("states"))
    if not filters and not states:
        return None
    sort = raw.get("sort") if raw.get("sort") in screener.FIELD_BY_ID else "score"
    direction = "asc" if raw.get("direction") == "asc" else "desc"
    return {"text": re.sub(r"\s+", " ", str(raw.get("text") or "")).strip()[:300] or None, "filters": filters,
            "states": states, "sort": sort, "direction": direction,
            "said": [screener.plain(f) for f in filters] + [screener.STATE_BY_ID[k]["label"] for k in states]}


def item_key(kind: str, tickers: List[str], ref: Dict[str, Any]) -> Optional[str]:
    """What makes two saves the same thing: a company's or a sheet's ticker, a comparison's set of tickers in any
    order, a conversation's own id. A conversation without one is always new (its key is then its row's id)."""
    if kind in ("company", "sheet"):
        return "{}:{}".format(kind, tickers[0])
    if kind == "comparison":
        return "comparison:" + ",".join(sorted(tickers))
    if kind == "conversation" and ref.get("conversation"):
        return "conversation:" + ref["conversation"]
    if kind == "screen" and ref.get("screen"):
        return "screen:" + ref["screen"]
    return None


def default_name(kind: str, tickers: List[str], now: Optional[datetime] = None) -> str:
    """The ticker(s) and the date, as the handoff asks: "AAPL, Nov 4, 2026", "AAPL vs MSFT, Nov 4, 2026". The page
    sends its own in the reader's timezone; this is the server's, on New York's calendar, for a save without one."""
    from zoneinfo import ZoneInfo
    day = (now or datetime.now(timezone.utc)).astimezone(ZoneInfo("America/New_York"))
    date = "{} {}, {}".format(day.strftime("%b"), day.day, day.year)
    if kind == "screen":
        return "Screen, {}".format(date)
    if not tickers:
        return "Milo conversation, {}".format(date)
    return "{}, {}".format(" vs ".join(tickers), date)


def _json(value: Any, cap: int, what: str) -> Optional[str]:
    if value in (None, "", {}, []):
        return None
    try:
        text = json.dumps(value, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError):
        raise _err(400, "The {} could not be read.".format(what))
    if len(text) > cap:
        raise _err(413, "The {} is too large to save.".format(what))
    return text


def _conversation(raw: Any) -> Dict[str, Any]:
    """A Milo conversation as saved: each message's words, and each answer's sources with the times they were read.
    Only these fields are kept, each to a length, so a save cannot carry anything else."""
    raw = raw if isinstance(raw, dict) else {}
    msgs = raw.get("messages") if isinstance(raw.get("messages"), list) else []
    if not any(isinstance(m, dict) and m.get("role") == "assistant" and str(m.get("content") or "").strip() for m in msgs):
        raise _err(400, "There is no answer in this conversation to save yet.")

    def text(v: Any, n: int) -> str:
        return str(v if v is not None else "")[:n]

    def entries(v: Any, keys: Iterable[str]) -> List[Dict[str, Any]]:
        out = []
        for e in (v if isinstance(v, list) else [])[:40]:
            if isinstance(e, dict):
                kept = {k: (e[k] if isinstance(e[k], (int, float, bool)) else text(e[k], 400))
                        for k in keys if e.get(k) not in (None, "")}
                if kept:
                    out.append(kept)
        return out

    clean = []
    for m in msgs[-MESSAGES_MAX:]:
        if not isinstance(m, dict) or m.get("role") not in ("user", "assistant"):
            continue
        one: Dict[str, Any] = {"role": m["role"], "content": text(m.get("content"), 12000)}
        for k in ("policy", "amended", "level"):
            if m.get(k):
                one[k] = text(m[k], 400)
        src = m.get("sources") if isinstance(m.get("sources"), dict) else {}
        kept = {"citations": entries(src.get("citations"), ("title", "url")),
                "read": entries(src.get("read"), ("symbol", "source", "url", "what", "period", "kind")),
                "retrieved": entries(src.get("retrieved"), ("label", "source", "as_of", "retrieved_at", "ok")),
                "loaded": entries(src.get("loaded"), ("label", "source", "as_of"))}
        kept = {k: v for k, v in kept.items() if v}
        if kept:
            one["sources"] = kept
        focus = m.get("focus") if isinstance(m.get("focus"), dict) else {}
        focus = {k: text(focus[k], 120) for k in ("view_label", "ticker", "captured_at") if focus.get(k)}
        if focus:
            one["focus"] = focus
        clean.append(one)
    return {"messages": clean, "saved_from": text(raw.get("saved_from"), 120)}


def _transcript(conv: Dict[str, Any]) -> str:
    """The conversation as plain text: what the older list and the search read."""
    lines = []
    for m in conv.get("messages") or []:
        lines.append("{}: {}".format("Q" if m["role"] == "user" else "A", m["content"]))
    return "\n\n".join(lines)[:20000]


def _load(text: Optional[str], default: Any) -> Any:
    if not text:
        return default
    try:
        return json.loads(text)
    except ValueError:
        return default


def _out(row: Dict[str, Any], full: bool = False) -> Dict[str, Any]:
    """One item as the library lists it; `full` adds a conversation's saved copy, or a question's text."""
    # a library row always has a key; a question saved before the library has none
    kind = row.get("research_type") if row.get("item_key") and row.get("research_type") in KINDS else QUESTION
    tickers = _load(row.get("tickers"), None)
    if not isinstance(tickers, list):
        tickers = [row["symbol"]] if row.get("symbol") else []
    out = {"id": row["id"], "kind": kind, "name": row.get("title") or "", "tickers": tickers,
           "created_at": row.get("created_at"), "updated_at": row.get("updated_at"),
           "ref": _load(row.get("ref"), {}), "summary": _load(row.get("summary"), {})}
    if kind == QUESTION:
        out["question"] = (row.get("preview") if "preview" in row else row.get("content") or "")[:2000]
        out["research_type"] = row.get("research_type") or "note"
    if full:
        if kind == "conversation":
            out["conversation"] = _load(row.get("payload"), {"messages": []})
        elif kind == "screen":
            out["screen"] = _load(row.get("payload"), None)
        elif kind == QUESTION:
            out["question"] = row.get("content") or ""
    return out


# ------------------------------------------------------------------ whether a saved ticker still trades

def _traded_recently(q: Dict[str, Any]) -> bool:
    stamp = q.get("trade_time")
    if not stamp:
        return True                      # a price without its time: the source has it, which is enough
    try:
        at = datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
    except ValueError:
        return True
    return datetime.now(timezone.utc) - at <= timedelta(days=TRADED_DAYS)


def listed(sym: str) -> Optional[bool]:
    """True while a symbol is listed or still trades, False once nothing does, None when that cannot be told now.
    The exchange directory first (in memory); then, for a symbol it does not list, the quote source: a trade in the
    last ten days still counts (an over-the-counter listing), no price at all does not. A source that fails is "cannot
    tell", never "gone", and the answer is kept an hour."""
    hit = _LISTED.get(sym)
    if hit and time.time() - hit[0] < GONE_TTL:
        return hit[1]
    try:
        known = universe.known_symbol(sym)
    except Exception:                                     # noqa: BLE001 - the directory failing is "cannot tell"
        known = None
    answer: Optional[bool]
    if known:
        answer = True
    elif QUOTE is None:
        answer = None
    else:
        try:
            q = QUOTE(sym) or {}
            answer = None if q.get("price") is None and known is None else (
                q.get("price") is not None and _traded_recently(q))
        except Exception:                                 # noqa: BLE001 - the source failing is not the symbol going
            answer = None
    if answer is not None:
        _LISTED[sym] = (time.time(), answer)
    return answer


def _gone(symbols: Set[str]) -> Set[str]:
    return {s for s in symbols if listed(s) is False}


# ------------------------------------------------------------------ routes

def _owned(item_id: str, user_id: str, columns: str = "*") -> Dict[str, Any]:
    found = db.row("SELECT {} FROM saved_research WHERE id = ? AND user_id = ?".format(columns), (item_id, user_id))
    if not found:
        raise _err(404, "That saved item is not here.")
    return found


_LIST_COLUMNS = ("id, title, symbol, research_type, created_at, updated_at, tickers, ref, summary, item_key, "
                 "substr(content, 1, 2000) AS preview")


@router.get("/library")
async def list_items(request: Request,
                     kind: str = Query("", max_length=20),
                     q: str = Query("", max_length=80),
                     key: str = Query("", max_length=200),
                     cursor: str = Query("", max_length=120),
                     limit: int = Query(PAGE, ge=1, le=PAGE_MAX)) -> Dict[str, Any]:
    """The reader's saved items, newest first, a page at a time: by kind, by a search of names, tickers and text, or
    by `key` (whether one thing is saved). A conversation's saved copy is not in the list; it is read when opened."""
    user = deps.require_user(request)
    where, args = ["user_id = ?"], [user["id"]]   # type: List[str], List[Any]
    if kind == QUESTION:
        where.append("item_key IS NULL")
    elif kind in KINDS:
        where.append("item_key IS NOT NULL AND research_type = ?")
        args.append(kind)
    elif kind:
        raise _err(400, "Kinds are company, comparison, conversation, sheet, screen, investigation and question.")
    if key:
        where.append("item_key = ?")
        args.append(key)
    words = q.strip().lower()
    if words:
        like = "%" + words.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        where.append("(lower(title) LIKE ? ESCAPE '\\' OR lower(COALESCE(tickers, symbol, '')) LIKE ? ESCAPE '\\' "
                     "OR lower(substr(content, 1, 2000)) LIKE ? ESCAPE '\\')")
        args += [like, like, like]
    if cursor:
        at, _, rid = cursor.partition("|")
        if not at or not rid:
            raise _err(400, "That page marker is not one this list gave.")
        where.append("(updated_at < ? OR (updated_at = ? AND id < ?))")
        args += [at, at, rid]
    rows = db.rows("SELECT {} FROM saved_research WHERE {} ORDER BY updated_at DESC, id DESC LIMIT ?".format(
        _LIST_COLUMNS, " AND ".join(where)), tuple(args) + (limit + 1,))
    more = len(rows) > limit
    rows = rows[:limit]
    items = [_out(r) for r in rows]
    gone = await run_in_threadpool(_gone, {t for it in items for t in it["tickers"]})
    for it in items:
        it["gone"] = [t for t in it["tickers"] if t in gone]
    counts = {k: 0 for k in KINDS + (QUESTION,)}
    for r in db.rows("SELECT CASE WHEN item_key IS NULL THEN 'question' ELSE research_type END AS k, COUNT(*) AS n "
                     "FROM saved_research WHERE user_id = ? GROUP BY k", (user["id"],)):
        if r["k"] in counts:
            counts[r["k"]] = int(r["n"])
    return {"items": items, "next": "{}|{}".format(rows[-1]["updated_at"], rows[-1]["id"]) if more else None,
            "counts": counts, "total": sum(counts.values()),
            "limit": store.subscription(user["id"])["limits"]["saved_research"]}


@router.get("/library/{item_id}")
async def get_item(item_id: str, request: Request) -> Dict[str, Any]:
    """One item in full: a conversation with the sources each answer had when it was saved."""
    user = deps.require_user(request)
    row = _owned(item_id, user["id"])
    out = _out(row, full=True)
    gone = await run_in_threadpool(_gone, set(out["tickers"]))
    out["gone"] = [t for t in out["tickers"] if t in gone]
    return {"item": out}


@router.post("/library")
async def save_item(request: Request, payload: Dict[str, Any] = Body(default={})) -> Dict[str, Any]:
    """Save one thing. A second save of the same thing answers 409 with the saved one, unless `on_duplicate` says
    what to do: "update" (the saved one takes this save's contents and time, keeping its name) or "copy" (a new item,
    under the name given)."""
    user = deps.require_user(request)
    deps.csrf_guard(request)
    kind = str(payload.get("kind") or "").strip().lower()
    if kind in KEPT_ELSEWHERE:
        raise _err(400, "An investigation is kept by its own page as it runs, and saved there.")
    if kind not in KINDS:
        raise _err(400, "Kinds are company, comparison, conversation, sheet and screen.")
    tickers = _tickers(payload.get("tickers"), kind)
    ref = _ref(payload.get("ref"), kind)
    screen = _screen(payload.get("screen")) if kind == "screen" else None
    if kind == "screen":
        if not screen:
            raise _err(400, "A saved screen needs at least one filter.")
        ref = {"screen": fnv1a(screen_canonical(screen))}
    key = item_key(kind, tickers, ref)
    name = re.sub(r"\s+", " ", str(payload.get("name") or "")).strip()[:NAME_MAX] or default_name(kind, tickers)
    summary = _json(payload.get("summary") if isinstance(payload.get("summary"), dict) else None, SUMMARY_MAX, "summary")
    conv = _conversation(payload.get("conversation")) if kind == "conversation" else None
    body = _json(conv, PAYLOAD_MAX, "conversation") if conv else _json(screen, SUMMARY_MAX, "screen") if screen else None
    content = (_transcript(conv) if conv else "{}: {}".format(name, "; ".join([screen["text"] or ""] + screen["said"])) if screen
               else "{}: {}".format(name, ", ".join(tickers)))
    mode = str(payload.get("on_duplicate") or "ask").strip().lower()
    now = db.utcnow()

    same = db.row("SELECT * FROM saved_research WHERE user_id = ? AND item_key = ? ORDER BY updated_at DESC LIMIT 1",
                  (user["id"], key)) if key else None
    if same and mode == "update":
        db.execute("UPDATE saved_research SET tickers = ?, ref = ?, summary = ?, payload = ?, content = ?, symbol = ?, "
                   "updated_at = ? WHERE id = ? AND user_id = ?",
                   (json.dumps(tickers), json.dumps(ref), summary, body, content, tickers[0] if tickers else None, now,
                    same["id"], user["id"]))
        return {"ok": True, "updated": True, "item": _out(_owned(same["id"], user["id"]))}
    if same and mode != "copy":
        raise HTTPException(status_code=409, detail={
            "message": "This is already saved as “{}”.".format(same["title"]), "duplicate": _out(same)})

    limit = store.subscription(user["id"])["limits"]["saved_research"]
    count = db.row("SELECT COUNT(*) AS n FROM saved_research WHERE user_id = ?", (user["id"],))
    if int((count or {}).get("n") or 0) >= limit:
        raise _err(403, "This plan keeps {} saved items. Delete one to save another.".format(limit))
    rid = db.new_id()
    key = key or "{}:{}".format(kind, rid)   # never NULL: NULL is how a question saved before the library is told apart
    db.execute("INSERT INTO saved_research (id, user_id, title, symbol, content, research_type, created_at, updated_at, "
               "tickers, ref, summary, payload, item_key) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
               (rid, user["id"], name, tickers[0] if tickers else None, content, kind, now, now, json.dumps(tickers),
                json.dumps(ref), summary, body, key))
    return {"ok": True, "updated": False, "item": _out(_owned(rid, user["id"]))}


@router.patch("/library/{item_id}")
async def rename_item(item_id: str, request: Request, payload: Dict[str, Any] = Body(default={})) -> Dict[str, Any]:
    """A new name. Its saved time is unchanged: a name is not new research."""
    user = deps.require_user(request)
    deps.csrf_guard(request)
    _owned(item_id, user["id"], "id")
    name = re.sub(r"\s+", " ", str(payload.get("name") or "")).strip()[:NAME_MAX]
    if not name:
        raise _err(400, "A name cannot be empty.")
    db.execute("UPDATE saved_research SET title = ? WHERE id = ? AND user_id = ?", (name, item_id, user["id"]))
    return {"ok": True, "item": _out(_owned(item_id, user["id"]))}


@router.delete("/library/{item_id}")
async def delete_item(item_id: str, request: Request) -> Dict[str, Any]:
    """Gone from the library, the Save buttons and every device: there is one copy, the account's."""
    user = deps.require_user(request)
    deps.csrf_guard(request)
    removed = db.execute("DELETE FROM saved_research WHERE id = ? AND user_id = ?", (item_id, user["id"]))
    if not removed:
        raise _err(404, "That saved item is not here.")
    return {"ok": True}
