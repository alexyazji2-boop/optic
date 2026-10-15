"""Two fixes in Milo's panel, reported by the owner with screenshots (2026-10-15).

1. The "Sources Milo read" chip redirected. It opened the Overview, which never shows the research pack,
   and from Home, with no symbol loaded, it landed on "No symbol loaded". Now the chip opens a list of the
   sources Milo was sent, under its own answer: the server sends them with the reply (`read`, built from
   the CONTEXT after the budget). Any other chip whose panel needs a symbol says so instead of opening an
   empty page when none is loaded.
2. The timeframe row cut "Long term". Four equal quarters (flex-basis 0) gave "Long term" the same room as
   "Day"; each choice is now as wide as its word, and the row wraps rather than clip.

Checked in a browser at 300 to 520px panels: no choice cut at any width (the control takes its own line
below 340px); the chip opened the list and stayed on Home; the Quote chip with nothing loaded said so and
stayed; with a symbol loaded the Quote chip still opened the Overview.
"""
from __future__ import annotations

import asyncio
import json
import types
from pathlib import Path

from app import ai, ai_store

ROOT = Path(__file__).resolve().parent.parent
APP = (ROOT / "static/app.js").read_text()
CSS = (ROOT / "static/styles.css").read_text()

PACK = {"intent": "long_term", "ticker": "AAPL", "items": [
    {"id": "R1", "group": "business", "label": "Revenue, trailing four quarters", "value": 466.82, "unit": "$bn",
     "period": "four quarters to 2026-06-30", "source": "Company quarterly statements via Yahoo Finance",
     "url": "https://finance.yahoo.com/quote/AAPL/financials"},
    {"id": "R2", "group": "business", "label": "Net income, trailing four quarters", "value": 128.93, "unit": "$bn",
     "period": "four quarters to 2026-06-30", "source": "Company quarterly statements via Yahoo Finance",
     "url": "https://finance.yahoo.com/quote/AAPL/financials"},
    {"id": "R3", "group": "filings", "label": "10-K for fiscal 2025", "source": "SEC EDGAR",
     "url": "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=0000320193", "as_of": "2025-10-31"},
    {"id": "R4", "group": "news", "label": "A headline", "source": "Yahoo Finance news", "url": "javascript:alert(1)"},
]}


def _request(context):
    kw, _ = ai.build_chat_request([{"role": "user", "content": "Is Apple expensive?"}], context=context)
    return kw


def test_the_sources_are_the_ones_milo_was_sent_one_row_per_source():
    rows = ai.sources_read(_request({"quote": {"ticker": "AAPL", "price": 345.0}, "research": PACK}))
    assert [r["source"] for r in rows] == ["Company quarterly statements via Yahoo Finance", "SEC EDGAR",
                                           "Yahoo Finance news"]
    assert rows[0]["what"] == "Revenue, trailing four quarters, Net income, trailing four quarters"
    assert rows[0]["period"] == "four quarters to 2026-06-30" and rows[1]["period"] == "2025-10-31"
    assert rows[2]["url"] == "", "only http(s) links reach the page"


def test_no_research_no_list():
    assert ai.sources_read(_request({"quote": {"ticker": "AAPL", "price": 345.0}})) == []
    assert ai.sources_read(None) == [] and ai.sources_read({"messages": []}) == []


def test_many_labels_are_counted_not_listed():
    items = [{"label": "Item %d" % i, "source": "SEC EDGAR", "url": "https://www.sec.gov/x"} for i in range(6)]
    rows = ai.sources_read(_request({"research": {"items": items}}))
    assert rows == [{"source": "SEC EDGAR", "url": "https://www.sec.gov/x", "period": "",
                     "what": "Item 0, Item 1, Item 2 and 3 more"}]


class _Stream:
    def __init__(self, events, final):
        self.events, self.final = events, final

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    def __aiter__(self):
        async def gen():
            for e in self.events:
                yield e
        return gen()

    async def get_final_message(self):
        return self.final


def test_the_reply_carries_the_list(monkeypatch):
    delta = types.SimpleNamespace(type="content_block_delta",
                                  delta=types.SimpleNamespace(type="text_delta", text="Fully priced. [[src research]]"))
    final = types.SimpleNamespace(model=ai.PULSE_MODEL, stop_reason="end_turn", content=[],
                                  usage=types.SimpleNamespace(input_tokens=10, output_tokens=5, cache_read_input_tokens=0))
    client = types.SimpleNamespace(beta=types.SimpleNamespace(messages=types.SimpleNamespace(
        stream=lambda **kw: _Stream([delta], final))))
    monkeypatch.setattr(ai, "_client", lambda: client)
    monkeypatch.setattr(ai_store, "record", lambda *a, **k: None)

    async def run():
        return [e async for e in ai.stream_chat([{"role": "user", "content": "Is Apple expensive?"}],
                                                context={"research": PACK})]
    events = asyncio.run(run())
    done = next(e for e in events if e.startswith("event: done"))
    payload = json.loads(done.split("data: ", 1)[1])
    assert [r["source"] for r in payload["read"]][:2] == ["Company quarterly statements via Yahoo Finance", "SEC EDGAR"]


def test_the_chip_opens_the_list_and_never_an_empty_panel():
    assert "research: ['Sources Milo read', 'sources']," in APP
    handler = APP[APP.index("const src = evt.target.closest('[data-src-view]');"):]
    handler = handler[:handler.index("\n});\n")]
    assert "if (view === 'sources') {" in handler and "box.open = true;" in handler
    assert "if (SECURITY_VIEWS.includes(view) && view !== 'earnings' && !STATE.ticker) {" in handler
    # The empty-panel guard runs before any navigation.
    assert handler.index("!STATE.ticker") < handler.index("switchView(view);")
    assert "sourcesEl.insertAdjacentHTML('beforeend', pulseReadHTML(payload.read));" in APP
    assert "function pulseReadHTML(read) {" in APP and ".msg .milo-read {" in CSS


def test_the_timeframe_choices_are_as_wide_as_their_words():
    assert ".hz-seg { flex: 1 1 auto; display: flex; min-width: min-content; }" in CSS
    assert ".hz-seg button { flex: 1 1 auto; min-width: max-content;" in CSS
    assert ".hz-seg button { flex: 1 1 0; min-width: 0;" not in CSS
    assert "long: 'Long term'" in APP, "the label itself is unchanged"
