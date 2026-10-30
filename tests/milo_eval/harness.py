"""Milo evaluation harness: runs each case through the real chat route on fixed fixtures (post-demo Phase 08,
2026-10-29; ported by hand from the milo-upgrade branch's tests/milo_eval/harness.py at 55721f6).

The model call is replaced by a capture, so what is checked is everything Optic decides before the model writes:
the evidence that reaches CONTEXT, the tools offered, the instructions, the request's size, what is withheld from
whom, and what each tool returns (figures, freshness, failures). Answers are checked by `answer_checks.py` when
there are answers to check: the real model cannot be called on this machine (BLOCKERS BL-01).
"""
from __future__ import annotations

import asyncio
import contextlib
import json
import time
import types
from typing import Any, Dict, List, Optional
from unittest import mock

from tests.milo_eval import fixtures as F


def _search(query: str, limit: int = 10, _idx=None) -> List[Dict[str, Any]]:
    q = (query or "").strip().upper()
    if not q:
        return []
    alias = F.ALIASES.get(q)
    out = []
    for d in F.DIRECTORY:
        s = d["symbol"]
        if s == q or s.replace("-", ".") == q:
            out.append((0, dict(d, match="symbol")))
        elif alias == s:
            out.append((0.5, dict(d, match="alias")))
        elif s.startswith(q) and len(q) >= 2:
            out.append((1, dict(d, match="prefix")))
        elif d["name"].upper().startswith(q) and len(q) >= 3:
            out.append((2, dict(d, match="name")))
    out.sort(key=lambda x: (x[0], len(x[1]["symbol"])))
    return [r for _, r in out][:limit]


@contextlib.contextmanager
def world(user: Optional[str] = None, extra: Optional[Dict[str, Any]] = None):
    """Every outside dependency of the chat route replaced by the fixtures, for one reader."""
    import app.main as m
    from app import universe as universe_mod
    from app.analytics import filings as filings_mod, sec_facts as sec_facts_mod
    from app import ai as ai_mod, milo_tools, session as session_mod
    u = F.USERS.get(user) if user else None
    extra = extra or {}

    def current_user(request):
        return u

    def link(uid):
        return {"id": "link-" + uid} if uid in F.ACCOUNTS else None

    def accounts(uid):
        return [{"id": a} for a in F.ACCOUNTS.get(uid, [])]

    def milo_context(user, account_ids=None, **kw):
        return F.milo_block(user["id"], account_ids) if user and user["id"] in F.ACCOUNTS else None

    def lists_for(uid):
        return [{"id": "{}-{}".format(uid, i), "name": n, "_symbols": s} for i, (n, s) in enumerate(F.WATCHLISTS.get(uid, []))]

    async def framework(history, context, horizon=None, attachments=None):
        from app.research import modes as research_modes
        last = next((t for t in reversed(history or []) if t.get("role") != "assistant"), None)
        ctx = dict(context or {})
        ticker = m._research_ticker(ctx)
        routing = research_modes.resolve((last or {}).get("content") or "", ticker, saved_horizon=horizon)
        if routing.get("mode"):
            ctx["framework"] = {"routing": routing, "ticker": ticker, "fixture": True}
        return ctx

    async def no_levels(history, context, horizon=None):
        # the take chart's levels read five years of daily bars; the fixture's history serves them when a case asks
        if not extra.get("levels"):
            return context
        return await real_levels(history, context, horizon)
    real_levels = m._with_take_levels

    # A fixed clock: the weekend after Friday's close unless the case says the session is open, so freshness
    # notes do not change with the day the suite runs.
    from datetime import datetime as _dt
    now = F.NOW_SESSION if extra.get("clock") == "session" else F.NOW_WEEKEND
    state = dict(F.REGULAR if extra.get("clock") == "session" else F.CLOSED,
                 label="Regular" if extra.get("clock") == "session" else "Closed",
                 phase="regular" if extra.get("clock") == "session" else "closed")

    class Clock(_dt):
        @classmethod
        def now(cls, tz=None):
            return now if tz else now.replace(tzinfo=None)

    async def _market_context():
        return {"as_of": "2026-10-23", "indices": [{"label": "S&P 500", "chg_1d": -0.4}], "source": "daily brief (fixture)"}

    patches = [
        mock.patch.object(ai_mod, "datetime", Clock),
        mock.patch.object(session_mod, "state", lambda now_=None: state),
        mock.patch.object(m, "_market_context", _market_context),
        mock.patch.object(m, "_screen_candidates", lambda: {"source": "screener (fixture)", "rows": [{"symbol": "NVDA"}, {"symbol": "AMD"}]}),
        mock.patch.object(m, "_spend_guard", lambda request: None),
        mock.patch.object(m, "_count_question", lambda request, kind: None),
        mock.patch.object(m.auth_deps, "current_user", current_user),
        mock.patch.object(m.brokerage_service, "open_to", lambda user: bool(user)),
        mock.patch.object(m.brokerage_store, "link", link),
        mock.patch.object(m.brokerage_store, "accounts", accounts),
        mock.patch.object(m.brokerage_service, "milo_context", milo_context),
        # the portfolio tool's other parts (they read the real store, which the suite has no rows in)
        mock.patch.object(m.brokerage_workspace, "exposure", F.workspace_part("exposure")),
        mock.patch.object(m.brokerage_workspace, "performance", F.workspace_part("performance")),
        mock.patch.object(m.brokerage_workspace, "events_research", F.workspace_part("events")),
        mock.patch.object(m.brokerage_workspace, "scorecard", F.workspace_part("scorecard")),
        mock.patch.object(m.brokerage_workspace, "options_risk", F.workspace_part("options")),
        mock.patch.object(m.brokerage_workspace, "briefing", F.workspace_part("briefing")),
        mock.patch.object(m.account_mod, "_lists_for", lists_for),
        mock.patch.object(m.account_mod, "_list_payload", lambda w: {"name": w["name"], "symbols": w["_symbols"]}),
        mock.patch.object(m.PROVIDER, "quote", extra.get("quote", F.quote)),
        mock.patch.object(m.YF_PROVIDER, "quote", extra.get("quote", F.quote)),
        mock.patch.object(m.YF_PROVIDER, "history", lambda t, period="5y", interval="1d": F.history_frame(t, period, interval)),
        mock.patch.object(m.news_mod, "analyse", lambda p, t, n=12: F.news(t, n)),
        mock.patch.object(m, "_swing_snapshot", F.swing_snapshot),
        mock.patch.object(m.desk_research_mod, "build", F.research_pack),
        mock.patch.object(m, "_with_framework", framework),
        mock.patch.object(m, "_with_take_levels", no_levels),
        mock.patch.object(universe_mod, "search", _search),
        mock.patch.object(universe_mod, "search_with_status",
                          lambda q, limit=10: {"results": _search(q, limit), "available": True, "stale": bool(extra.get("directory_stale"))}),
        mock.patch.object(filings_mod, "recent", F.filings_recent),
        mock.patch.object(sec_facts_mod, "history", F.sec_history),
        mock.patch.object(m, "_tool_earnings", lambda ticker: dict(F.EARNINGS.get(ticker, {"ticker": ticker}), status="ok")
                          if ticker in F.EARNINGS else {"status": "not_found", "error": "No earnings data (fixture)."}),
        mock.patch.object(m, "_tool_valuation", lambda ticker: {"status": "unavailable", "error": "Bank: the DCF does not fit (fixture)."}
                          if ticker == "JPM" else {"status": "ok", "source": "Optic's valuation engine (fixture)", "ticker": ticker,
                                                   "value_per_share": round(F.closes(ticker)[-1] * 0.9, 2)}),
        mock.patch.object(m, "_tool_fundamentals", lambda ticker: {"status": "ok", "source": "Optic's long-term model (fixture)",
                                                                   "holding": {"ticker": ticker, "conviction": "moderate"}}),
        mock.patch.object(m, "_tool_market", lambda: {"status": "ok", "source": "Optic's daily brief (fixture)",
                                                      "indices": [{"label": "S&P 500", "chg_1d": -0.4}], "as_of": "2026-10-23"}),
        mock.patch.object(m, "_tool_compare", lambda tickers: {"status": "ok", "source": "Optic's Compare view (fixture)", "tickers": tickers}),
        mock.patch.object(m, "_tool_assessment", lambda ticker, mode: {"status": "ok", "source": "framework (fixture)", "ticker": ticker, "mode": mode}),
        mock.patch.object(m, "_tool_screen", lambda request: {"status": "ok", "source": "screener (fixture)", "understood": [request[:40]]}),
    ]
    if hasattr(milo_tools, "describe"):
        real_describe = milo_tools.describe

        def describe(name, result, is_error, now_=None, session_state=None):
            return real_describe(name, result, is_error, now=now, session_state=state)
        patches.append(mock.patch.object(milo_tools, "describe", describe))
    with contextlib.ExitStack() as stack:
        for p in patches:
            stack.enter_context(p)
        yield m


def assemble(case: Dict[str, Any]) -> Dict[str, Any]:
    """Run one case through POST /api/chat; return what the model would have been sent."""
    from fastapi.testclient import TestClient
    from app import ai
    seen: Dict[str, Any] = {}

    async def capture(history, **kw):
        seen.update(kw, history=history)
        yield ai._sse("done", {})
    messages = list(case.get("history") or []) + [{"role": "user", "content": case["question"]}]
    body = {"messages": messages, "context": case.get("context") or {}, "web": bool(case.get("web"))}
    if case.get("mode"):
        body["mode"] = case["mode"]
    with world(case.get("user"), case.get("world")) as m, mock.patch.object(m.ai, "stream_chat", capture):
        t0 = time.perf_counter()
        r = TestClient(m.app).post("/api/chat", json=body)
        took = time.perf_counter() - t0
        box = seen.get("toolbox")
        names = [d["name"] for d in box.definitions()] if box is not None else []
        ctx = seen.get("context") or {}
        opts = {k: seen[k] for k in ("persona", "mode", "horizon") if seen.get(k) is not None}
        kwargs, meta = ai.build_chat_request(messages, context=ctx, use_web=bool(case.get("web")), **opts)
        if kwargs is not None and box is not None:        # as stream_chat adds them
            kwargs["tools"] = box.definitions() + list(kwargs.get("tools") or [])
        header = ai.context_header(ctx)
    system = "\n".join(b["text"] for b in (kwargs or {}).get("system", []) if isinstance(b, dict))
    last = (kwargs or {}).get("messages", [{}])[-1].get("content", "")
    last = last if isinstance(last, str) else " ".join(b.get("text", "") for b in last if isinstance(b, dict))
    return {"status": r.status_code, "seconds": took, "context": ctx, "tools": names, "toolbox": box, "header": header,
            "meta": meta, "system": system, "user_turn": last, "kwargs": kwargs, "mode": seen.get("mode"),
            "input_chars": len(system) + sum(len(json.dumps(m_["content"])) for m_ in (kwargs or {}).get("messages", []))
            + len(json.dumps((kwargs or {}).get("tools") or []))}


def run_tool(case: Dict[str, Any], name: str, args: Dict[str, Any]) -> Dict[str, Any]:
    """One tool call through the route's own toolbox for this case's reader and context."""
    with world(case.get("user"), case.get("world")) as m:
        history = list(case.get("history") or []) + [{"role": "user", "content": case["question"]}]
        box = m._milo_toolbox(types.SimpleNamespace(), case.get("context") or {}, history)
        if case.get("tool_timeout"):
            box.call_timeout = case["tool_timeout"]
        t0 = time.perf_counter()
        content, is_error, cleaned = asyncio.run(box.run(name, args))
        took = time.perf_counter() - t0
    try:
        body = json.loads(content)
    except ValueError:
        body = {"raw": content}
    return {"body": body, "is_error": is_error, "seconds": took, "offered": name in box.runners}
