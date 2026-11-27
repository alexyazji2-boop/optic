"""Milo reads the reader's paper book whichever app sent it (2026-11-25).

Both apps keep one paper book in the browser (`optic.paper.v1`) and send its open trades with a Milo question as
`reader_holdings`, in two shapes: Classic as `{source, positions}` (static/app.js, the chat context) and v2's Paper
page as the bare list of positions (static/v2/js/pages/paper.js, provideContext). The server read only Classic's:
`.get("positions")` on v2's list raised AttributeError, the chat route answered in general mode (Handoff 6), and a v2
reader asking about their own paper book got "Page context unavailable" and an answer that never saw the book. Any
question that kept the block raised, not only a portfolio question: the block was read before the portfolio words
were tested. Reproduced 2026-11-24 on origin/main 3e4fa5fb; the Milo eval's paper fixture sends Classic's shape, so
the eval never met v2's.

v2 also told Milo less about each trade than Classic: no option type, strike or expiry, so Milo could not name a v2
option contract, and no entry time or target. Since 2026-11-26 it sends Classic's fields in its own shape.
"""
from __future__ import annotations

import asyncio
import json

import pytest
from fastapi.testclient import TestClient

import app.main as main
from app import ai
from tests.milo_eval import harness as H
from tests.test_frontend_v2_stage0 import V2, _run as _jsc

SECTORS = {"AAPL": "Technology", "XOM": "Energy"}

# Two open trades as the book stores them (pages/paper.js, `book.open`): 10 AAPL shares in at $300, and 2 XOM call
# contracts in at a $5.00 premium. Notional at entry is $3,000 and 2 x $5.00 x 100 = $1,000, so 75% and 25%.
STORED = [
    {"id": "p1", "ticker": "AAPL", "instrument": "shares", "direction": "long", "option_type": None, "strike": None,
     "expiry": None, "qty": 10, "entry_price": 300, "entry_spot": 300, "entry_at": "2026-11-20T15:00:00.000Z",
     "stop": 280, "target": 340, "thesis": "Held the 50-day", "plan": None, "entry_note": None, "revisions": [],
     "read": None},
    {"id": "p2", "ticker": "XOM", "instrument": "option", "direction": "long", "option_type": "call", "strike": 120,
     "expiry": "2026-12-18", "qty": 2, "entry_price": 5.0, "entry_spot": 118.2, "entry_at": "2026-11-21T15:00:00.000Z",
     "stop": 2.5, "target": 9, "thesis": "", "plan": None, "entry_note": None, "revisions": [], "read": None},
]
MARKS = {"marked_at": "2026-11-25T15:00:00Z", "marks": [{"id": "p1", "mark_price": 304.5, "pnl": 45},
                                                        {"id": "p2", "mark_price": 2.0, "pnl": -600}]}

# The same two trades as each app sends them with a question. Classic sends these eleven fields a trade under
# `{source, positions}`, and v2's Paper page the bare list, with the same fields and the P&L of its latest marks.
CLASSIC_FIELDS = ("ticker", "instrument", "direction", "option_type", "strike", "expiry", "qty", "entry_price",
                  "entry_at", "stop", "target")
CLASSIC_SENT = {
    "source": "paper trades the reader entered in Optic (simulated, in this browser). Not a brokerage account; linked "
              "brokerage holdings, if any, are added by the server as brokerage_portfolio.",
    "positions": [{k: p[k] for k in CLASSIC_FIELDS} for p in STORED],
}
V2_SENT = [dict(p, pnl=m["pnl"]) for p, m in zip(CLASSIC_SENT["positions"], MARKS["marks"])]
# A v2 tab loaded before 2026-11-26 sends seven fields a trade until it reloads: no option type, strike, expiry,
# entry time or target
V2_SENT_BEFORE = [{k: p[k] for k in ("ticker", "instrument", "direction", "qty", "entry_price", "stop", "pnl")}
                  for p in V2_SENT]

BY_SECTOR = [{"sector": "Technology", "share_pct": 75.0}, {"sector": "Energy", "share_pct": 25.0}]
LARGEST = [{"ticker": "AAPL", "share_pct": 75.0}, {"ticker": "XOM", "share_pct": 25.0}]


def augment(question, holdings, monkeypatch):
    """main._augment_chat_context on the Paper page's context, with the named-symbol lookups passing it through."""
    async def as_sent(history, context):
        return context
    monkeypatch.setattr(main, "_augment_chat_context_lookups", as_sent)
    monkeypatch.setattr(main.YF_PROVIDER, "profile", lambda sym: {"sector": SECTORS.get(sym)})
    ctx = {"view": "paper", "reader_holdings": holdings, "focus": {"scope": "auto", "view": "paper"}}
    return asyncio.run(main._augment_chat_context([{"role": "user", "content": question}], ctx))


@pytest.mark.parametrize("sent", [V2_SENT, V2_SENT_BEFORE, CLASSIC_SENT], ids=["v2", "v2-before-2026-11-26", "classic"])
def test_a_portfolio_question_gets_the_paper_books_summary_from_either_app(sent, monkeypatch):
    summary = augment("How is my portfolio doing?", sent, monkeypatch)["portfolio_summary"]
    assert summary["positions"] == 2
    assert summary["by_sector"] == BY_SECTOR, "an option counts 100 shares a contract, a 'shares' trade one"
    assert summary["largest"] == LARGEST


def test_a_question_about_one_trade_keeps_the_book(monkeypatch):
    """No portfolio words, so no summary. It raised all the same on v2's list."""
    out = augment("Should I close my XOM trade?", V2_SENT, monkeypatch)
    assert "portfolio_summary" not in out and out["reader_holdings"] == V2_SENT


@pytest.mark.parametrize("sent", ["AAPL", True, [None, "AAPL"], {"positions": "AAPL"}])
def test_a_block_that_is_no_paper_book_costs_the_answer_nothing(sent, monkeypatch):
    """The browser decides what arrives under the key: anything that is not a book is no summary, never an error that
    takes the rest of the page's context with it."""
    out = augment("How is my portfolio doing?", sent, monkeypatch)
    assert out["view"] == "paper" and "portfolio_summary" not in out


def v2_paper_context(tmp_path):
    """What v2's panel sends from the Paper page, from its own code: the page rendered in JavaScriptCore over STORED,
    priced by a stub of /api/paper/mark, then ui/milo.js buildContext as Send calls it."""
    return _jsc(tmp_path, f"""
      // JavaScriptCore waits for every timer: a zero-delay one runs as a microtask, the page's polls never
      globalThis.setTimeout = (fn, ms) => {{ if (!ms) Promise.resolve().then(fn); return 0; }};
      globalThis.clearTimeout = () => {{}}; globalThis.setInterval = () => 0; globalThis.clearInterval = () => {{}};
      globalThis.requestAnimationFrame = () => 0; globalThis.CSS = {{ escape: (s) => String(s) }};
      globalThis.CustomEvent = class {{ constructor(t, o) {{ this.type = t; this.detail = o && o.detail; }} }};
      window.dispatchEvent = () => true; globalThis.history = {{ state: null, replaceState() {{}} }};
      globalThis.AbortController = class {{ constructor() {{ this.signal = {{ aborted: false, reason: null, addEventListener() {{}} }}; }} abort() {{ this.signal.aborted = true; }} }};
      globalThis.fetch = async (url) => ({{ ok: true, status: 200, statusText: '', headers: {{ get: () => null }},
        text: async () => JSON.stringify(String(url).startsWith('/api/paper/mark') ? {json.dumps(MARKS)} : {{}}) }});
      localStorage.setItem('optic.paper.v1', JSON.stringify({json.dumps({"open": STORED, "closed": []})}));
      const M = await import('{(V2 / "js/ui/milo.js").as_posix()}');
      const P = await import('{(V2 / "js/pages/paper.js").as_posix()}');
      const el = () => ({{ innerHTML: '', style: {{ setProperty() {{}} }}, dataset: {{}}, addEventListener() {{}}, contains: () => false,
        querySelector: () => null, querySelectorAll: () => [] }});
      const replay = el(), main = Object.assign(el(), {{ querySelector: (s) => (s === '#pt-replay' ? replay : null) }});
      M.resetContext({{ view: 'paper' }});
      await P.render(main, {{ view: 'paper', params: {{}} }});
      for (let i = 0; i < 40; i++) await Promise.resolve();
      print(JSON.stringify(M.buildContext('auto', null, new Date('2026-11-25T15:00:00Z'))));
    """)


def test_v2_tells_milo_what_classic_does_about_each_trade(tmp_path):
    """v2 sent seven fields a trade to Classic's eleven. Without the option type, strike and expiry Milo could not name
    a v2 option contract, only "2 XOM options", and without the entry time and the target it could not say how long a
    trade had run or how far it was from its target. v2 sends Classic's fields now, and its marks' P&L as before."""
    assert v2_paper_context(tmp_path)["reader_holdings"] == V2_SENT


def chat(question, context):
    """POST /api/chat in the eval harness's offline world, the model replaced by a capture: (status, events, seen)."""
    seen = {}

    async def capture(history, **kw):
        seen.update(kw)
        yield ai._sse("done", {})
    with H.world(None) as m, pytest.MonkeyPatch.context() as mp:
        mp.setattr(m.ai, "stream_chat", capture)
        mp.setattr(m.YF_PROVIDER, "profile", lambda sym: {"sector": SECTORS.get(sym)})
        r = TestClient(m.app).post("/api/chat", json={"messages": [{"role": "user", "content": question}],
                                                      "context": context})
    events = {}
    for block in r.text.split("\n\n"):
        lines = dict(ln.split(": ", 1) for ln in block.splitlines() if ": " in ln)
        if "event" in lines and "data" in lines:
            events[lines["event"]] = json.loads(lines["data"])
    return r.status_code, events, seen


def test_a_v2_paper_question_reaches_milo_with_the_book_and_its_summary(tmp_path):
    context = v2_paper_context(tmp_path)
    status, events, seen = chat("How is my portfolio doing?", context)
    assert status == 200
    assert events["context"]["unavailable"] is False, "the panel said 'Page context unavailable' and answered in general"
    sent = seen["context"]
    assert sent["reader_holdings"] == context["reader_holdings"], "the book reaches Milo as the page sent it"
    assert sent["journal"] == context["journal"]
    assert sent["portfolio_summary"]["by_sector"] == BY_SECTOR and sent["portfolio_summary"]["largest"] == LARGEST


def test_a_classic_paper_question_still_reaches_milo_with_the_book_and_its_summary():
    context = {"active_view": "paper", "reader_holdings": CLASSIC_SENT,
               "focus": {"scope": "auto", "view": "paper", "view_label": "Paper Desk", "ticker": None}}
    status, events, seen = chat("How is my portfolio doing?", context)
    assert status == 200 and events["context"]["unavailable"] is False
    sent = seen["context"]
    assert sent["reader_holdings"] == CLASSIC_SENT
    assert sent["portfolio_summary"]["by_sector"] == BY_SECTOR and sent["portfolio_summary"]["largest"] == LARGEST
