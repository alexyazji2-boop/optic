"""Capture exactly what Milo's model would be sent for each eval case.

    .venv/bin/python capture.py <worktree> <label> [--client before|after]

No network and no model call: `ai._client` is replaced by a fake whose
`stream()` records its keyword arguments and stops. The page context is built
from saved API responses in fixtures/ the way static/app.js's
chatContextPayload() builds it (`--client before` = origin/main's key list,
`after` = the strategy-pass list), plus what main.py's _augment_chat_context
would add for the case.

Writes out/<label>/<case>.json (the request) and out/<label>/summary.json
(level, horizon, humour, context size, which sections reached the model).
"""
import asyncio
import copy
import inspect
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
FIX = os.path.join(HERE, "fixtures")


def load(name):
    with open(os.path.join(FIX, name)) as fh:
        return json.load(fh)


SWING = {s: load("swing-%s.json" % s) for s in ("AAPL", "NVDA")}
LONG = {s: load("long-%s.json" % s) for s in ("AAPL", "NVDA")}
MARKET = load("market.json")
BRIEF = load("brief.json")

VIEW_LABELS = {"overview": "Overview", "options": "Options", "investing": "Investing",
               "chart": "Chart", "paper": "Paper Desk", "home": "Home"}

# Paper trades for the portfolio case: tech-heavy on purpose.
HOLDINGS = [
    {"ticker": "AAPL", "instrument": "stock", "direction": "long", "qty": 40, "entry_price": 300.0},
    {"ticker": "NVDA", "instrument": "stock", "direction": "long", "qty": 60, "entry_price": 190.0},
    {"ticker": "MSFT", "instrument": "stock", "direction": "long", "qty": 15, "entry_price": 480.0},
    {"ticker": "AMD", "instrument": "option", "direction": "long", "option_type": "call", "strike": 260,
     "expiry": "2026-11-20", "qty": 2, "entry_price": 9.5},
    {"ticker": "XOM", "instrument": "stock", "direction": "long", "qty": 20, "entry_price": 118.0},
]
SECTORS = {"AAPL": "Technology", "NVDA": "Technology", "MSFT": "Technology", "AMD": "Technology",
           "XOM": "Energy"}


def portfolio_summary():
    """main._portfolio_summary's output for HOLDINGS, without the profile fetch."""
    rows = [(h["ticker"], abs(h["qty"] * h["entry_price"] * (100 if h["instrument"] == "option" else 1)))
            for h in HOLDINGS]
    total = sum(v for _, v in rows)
    by_sec = {}
    for t, v in rows:
        by_sec[SECTORS[t]] = by_sec.get(SECTORS[t], 0) + v
    share = lambda v: round(100.0 * v / total, 1)
    return {
        "source": "paper trades the reader entered in Optic; not a brokerage account",
        "positions": len(rows),
        "by_sector": sorted(({"sector": k, "share_pct": share(v)} for k, v in by_sec.items()),
                            key=lambda x: -x["share_pct"]),
        "largest": sorted(({"ticker": t, "share_pct": share(v)} for t, v in rows),
                          key=lambda x: -x["share_pct"]),
        "note": "Shares are of notional at entry (price x quantity, x100 for options), not of "
                "current value. Sectors from each symbol's profile; Unknown where none was found.",
    }


BEFORE_KEYS = ["ticker", "quote", "verdict", "technicals", "gex", "greeks", "flow", "news",
               "entry_plan", "company", "naked_ideas", "strategy_ideas"]
# The keys strategy-pass adds from the same payload (see chatContextPayload).
AFTER_EXTRA = ["cases", "why", "whats_next", "pulse", "next_earnings_date", "sector_confirm",
               "earnings_momentum"]


def page_context(case, client):
    now = datetime.now(timezone.utc)
    # The question is asked now; only the company data is old (stale_minutes).
    captured = now
    ctx = {}
    sym = case.get("sym")
    view = case["view"]
    s = SWING.get(sym) if sym else None
    if s and view not in ("home",):
        for k in BEFORE_KEYS + (AFTER_EXTRA if client == "after" else []):
            if k in s:
                ctx[k] = copy.deepcopy(s[k])
    ctx["macro"] = MARKET.get("macro")
    ctx["sectors"] = MARKET.get("sectors")
    if view == "home":
        ctx["read"] = {k: BRIEF.get(k) for k in ("day", "summary", "overview", "calendar")}
    # Long-term data: before, only when the Investing tab was opened; after, the
    # Overview keeps the payload it already fetches.
    if sym and (view == "investing" or (client == "after" and view == "overview")):
        ctx["long_term"] = copy.deepcopy(LONG[sym])
    ctx["active_view"] = {"options": "swing", "investing": "long"}.get(view, view)
    if s and s.get("digest"):
        ctx["digest"] = s["digest"]
    ctx["reader_watchlist"] = {"source": "the reader's watchlist in Optic", "name": "Watchlist",
                               "symbols": ["NVDA", "QQQ", "SPY", "AMD"]}
    if case.get("holdings"):
        ctx["reader_holdings"] = {
            "source": "paper trades the reader entered in Optic (simulated, in this browser). Not a "
                      "brokerage account: Optic has no brokerage connection.",
            "positions": HOLDINGS}
    if s:
        stamp = datetime.fromisoformat(s["generated_at"].replace("Z", "+00:00"))
        ctx["data_as_of"] = (stamp - timedelta(minutes=case.get("stale_minutes", 0))).isoformat()
    focus = {"scope": "auto", "view": ctx["active_view"], "view_label": VIEW_LABELS.get(view, view),
             "ticker": sym if view not in ("home", "paper") else None,
             "captured_at": captured.isoformat()}
    if view == "chart":
        focus["chart"] = {"range": "6M", "interval": "daily"}
    if case.get("previous"):
        focus["previous_ticker"] = case["previous"]
    ctx["focus"] = focus
    # What main.py's _augment_chat_context appends after the browser's payload.
    if case.get("holdings"):
        ctx["portfolio_summary"] = portfolio_summary()
    if case["id"] == "M1":
        ctx["market"] = {"as_of": BRIEF.get("day"), "written_summary": BRIEF.get("summary"),
                         "indices": ((BRIEF.get("overview") or {}).get("groups") or {}).get("indices"),
                         "note": "Index and sector levels from the terminal's daily brief."}
    return ctx


class Captured(Exception):
    pass


class FakeStream:
    def __init__(self, sink, kwargs):
        sink.append(kwargs)

    async def __aenter__(self):
        raise Captured()

    async def __aexit__(self, *a):
        return False


class FakeClient:
    def __init__(self, sink):
        sink_ref = sink

        class _Messages:
            def stream(self, **kw):
                return FakeStream(sink_ref, kw)

        class _Beta:
            messages = _Messages()

        self.beta = _Beta()


def top_keys(text):
    m = re.search(r"```json\n(.*)", text, re.S)
    if not m:
        return []
    return re.findall(r'^ ?"([a-z_]+)":', m.group(1), re.M)


async def run(worktree, label, client):
    sys.path.insert(0, worktree)
    os.chdir(worktree)
    sys.path.insert(0, HERE)
    from cases import CASES
    from app import ai
    sink = []
    ai._client = lambda: FakeClient(sink)
    ai.ai_store.record = lambda *a, **k: None
    params = inspect.signature(ai.stream_chat).parameters
    outdir = os.path.join(HERE, "out", label)
    os.makedirs(outdir, exist_ok=True)
    summary = []
    only = os.environ.get("ONLY", "").split(",") if os.environ.get("ONLY") else None
    for case in CASES:
        if only and case["id"] not in only:
            continue
        sink.clear()
        history = list(case.get("history") or []) + [{"role": "user", "content": case["q"]}]
        ctx = page_context(case, client)
        kw = dict(context=ctx, use_web=False, persona="neutral", mode=case["mode"])
        if "horizon" in params:
            kw["horizon"] = case.get("horizon", "auto")
        async for ev in ai.stream_chat(history, **kw):
            if ev.startswith("event: error") and not sink:
                print(case["id"], "error:", ev[:200])
        if not sink:
            continue
        req = sink[0]
        system = [b["text"] for b in req["system"]]
        last = req["messages"][-1]["content"]
        last_text = last if isinstance(last, str) else " ".join(
            b.get("text", "") for b in last if isinstance(b, dict))
        kept = top_keys(last_text)
        sent_keys = [k for k in ctx if k not in ("focus", "data_as_of")]
        level = next((m for m, spec in ai.knowledge.MODES.items() if spec["prompt"] in system), None)
        hz = None
        meta = {}
        if hasattr(ai, "build_chat_request"):
            _, meta = ai.build_chat_request(history, **kw)
            hz = meta.get("horizon") if meta.get("horizon") != "auto" else None
        row = {
            "id": case["id"], "persp": case["persp"], "q": case["q"], "mode": case["mode"],
            "resolved_level": level, "horizon_block": hz,
            "humour_block": any("personality" in t.lower() and "funny" in t.lower() for t in system)
            or any("humour in this reply" in t for t in system),
            "slimmed": (meta.get("context") or {}).get("slimmed"),
            "system_chars": sum(len(t) for t in system),
            "user_turn_chars": len(last_text),
            "est_input_tokens": int((sum(len(t) for t in system) + sum(
                len(m["content"]) if isinstance(m["content"], str) else len(last_text)
                for m in req["messages"])) / 3.6),
            "truncated": "[context truncated]" in last_text,
            "sent_sections": sent_keys,
            "reached_model": kept,
            "lost": [k for k in sent_keys if k not in kept],
        }
        summary.append(row)
        with open(os.path.join(outdir, case["id"] + ".json"), "w") as fh:
            # No case or checks in the request file: a stand-in model reads it
            # (2026-10-13, one saw B1's checks before this was split out).
            json.dump({"id": case["id"], "system": system, "messages": req["messages"], "metrics": row},
                      fh, indent=1, default=str)
    if not only:
        with open(os.path.join(outdir, "summary.json"), "w") as fh:
            json.dump(summary, fh, indent=1)
    for r in summary:
        print("{id:3} level={resolved_level!s:12} hz={horizon_block!s:6} humour={humour_block!s:5} "
              "ctx={user_turn_chars:>6} trunc={truncated!s:5} lost={lost}".format(**r))


if __name__ == "__main__":
    wt, label = sys.argv[1], sys.argv[2]
    client = sys.argv[sys.argv.index("--client") + 1] if "--client" in sys.argv else "before"
    asyncio.run(run(wt, label, client))
