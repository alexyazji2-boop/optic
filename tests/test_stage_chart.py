"""The stage label on the charts: the endpoint, the chip, and the guard.

The chip is fetched per symbol and painted asynchronously on two charts, so
the property that matters most is not the label but *whose* label it is. It
was proven in a browser rather than argued: with AAPL on screen and TSLA's
fetch still in flight, painting without the guard put "Stage 4 · Declining" --
TSLA's reading -- under AAPL's name. With the guard the late answer is dropped.
"""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd
from fastapi.testclient import TestClient

import app.main as main

ROOT = Path(__file__).resolve().parent.parent
APP = (ROOT / "static/app.js").read_text()
CSS = (ROOT / "static/styles.css").read_text()


def _strip(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.S)
    return re.sub(r"^\s*//.*$", " ", text, flags=re.M)


def _fn(name: str) -> str:
    code = _strip(APP)
    body = code[code.index("function " + name + "("):]
    return body[:body.index("\n}") + 2]


CLEAN_CSS = _strip(CSS)


def _rule(selector: str) -> str:
    """The rule whose selector list *is* `selector`, not one that merely ends in
    it. A substring search found `.sec-id .stage-chip {` before the base
    `.stage-chip {` once the Dossier strip gained a chip, because the descendant
    rule sits earlier in the file -- and asserted the base rule's display
    against a rule that only sets alignment."""
    m = re.search(r"(?:^|[}\n])\s*" + re.escape(selector) + r"\s*\{", CLEAN_CSS)
    assert m, "no rule for " + selector
    start = m.end()
    return CLEAN_CSS[start:CLEAN_CSS.index("}", start)]


# ---------------------------------------------------------------- endpoint


class _Weekly:
    def __init__(self, closes):
        self.calls = []
        self._closes = closes

    def history(self, symbol, period="2y", interval="1d"):
        self.calls.append((symbol, period, interval))
        return pd.DataFrame({"Close": self._closes})


def test_the_endpoint_answers_with_a_stage(monkeypatch):
    feed = _Weekly([50 + i for i in range(80)])
    monkeypatch.setattr(main, "YF_PROVIDER", feed)
    body = TestClient(main.app).get("/api/stage", params={"symbol": "PLTR"}).json()
    assert body["available"] is True and body["stage"] == 2
    assert body["symbol"] == "PLTR"


def test_it_asks_for_two_years_of_weekly_bars_whatever_the_chart_shows(monkeypatch):
    feed = _Weekly([50 + i for i in range(80)])
    monkeypatch.setattr(main, "YF_PROVIDER", feed)
    TestClient(main.app).get("/api/stage", params={"symbol": "^GSPC"})
    assert feed.calls == [("^GSPC", "2y", "1wk")]


def test_a_symbol_that_breaks_a_path_is_a_query_parameter(monkeypatch):
    """`^GSPC` and `ES=F` do not survive a path segment -- the reason
    `/api/instrument` takes one too."""
    feed = _Weekly([50 + i for i in range(80)])
    monkeypatch.setattr(main, "YF_PROVIDER", feed)
    body = TestClient(main.app).get("/api/stage", params={"symbol": "ES=F"}).json()
    assert body["symbol"] == "ES=F"


# ------------------------------------------------------------------- chip


def test_a_late_answer_for_another_symbol_is_not_painted():
    """The guard the browser proved load-bearing."""
    fn = _fn("paintStage")
    assert "stillCurrent" in fn
    assert "if (stillCurrent && !stillCurrent()) return;" in fn
    # ...and it is checked after the await, not before it, or it guards nothing.
    assert fn.index("await fetchStage(symbol)") < fn.index("!stillCurrent()")


def test_both_charts_pass_a_guard_for_their_own_symbol():
    code = _strip(APP)
    assert "paintStage('stage-ws', stageSym, () => STATE.chartSymbol === stageSym)" in code
    assert "paintStage('stage-inst', stageSym," in code
    inst = code[code.index("paintStage('stage-inst'"):]
    assert "=== stageSym" in inst[:200]


def test_an_unavailable_reading_is_not_a_falsy_test():
    """An unavailable reading is a truthy object. CLAUDE.md records a falsy
    check sailing past exactly that shape once."""
    assert "r.available !== true" in _fn("paintStage")


def test_a_failed_fetch_is_not_cached():
    """A blip would otherwise hide the chip for half an hour. An unavailable
    answer -- too little history -- is real and is kept."""
    fn = _fn("fetchStage")
    assert "stageCache.delete(symbol)" in fn
    assert re.search(r"if \(!r\) stageCache\.delete", fn)


def test_both_hosts_exist_and_start_hidden():
    code = _strip(APP)
    assert '<span class="stage-chip" id="stage-ws" hidden></span>' in code
    assert '<span class="stage-chip" id="stage-inst" hidden></span>' in code


# -------------------------------------------------------------------- css


def test_the_chip_has_its_hidden_pair():
    """CLAUDE.md: an author `display` beats the UA's `[hidden]` rule whatever
    the specificity, so a chip given one needs its own."""
    assert "display: inline-flex" in _rule(".stage-chip")
    assert "display: none" in _rule(".stage-chip[hidden]")


def test_colour_follows_the_direction_the_stage_describes():
    assert "var(--pos)" in _rule(".stage-chip.stage-2")
    assert "var(--neg)" in _rule(".stage-chip.stage-4")
    assert "var(--warn)" in _rule(".stage-chip.stage-3")


def test_it_shortens_rather_than_clips_in_a_narrow_header():
    """Measured at 561px: the header 263px wide, nowrap and overflow hidden,
    and the full chip ran 41px past its edge. "Stage 2" survives."""
    assert ".ws-body.narrow .ws-head .stage-name" in CLEAN_CSS
    assert ".ws-body.narrow .ws-head .stage-tag" in CLEAN_CSS
    block = CLEAN_CSS[CLEAN_CSS.index("body.chat-open .ws-head .stage-name"):]
    assert "display: none" in block[:block.index("}")]


# ------------------------------------------------------ the Dossier header


def _sec_header() -> str:
    return _fn("securityHeader")


def test_the_overview_strip_carries_the_chip_beside_the_change():
    fn = _sec_header()
    assert 'id="stage-sec-overview"' in fn
    # After the change figure, before the exchange line that is pushed right.
    assert fn.index('class="sec-chg') < fn.index('id="stage-sec-') < fn.index('class="sec-meta"')


def test_only_the_overview_shows_it():
    """Asked for on Overview only. It first went on every facet sharing the
    strip -- Financials, News, Earnings and Investing -- and the other facets
    are about the company's numbers, filings and news, where a trend label
    repeated over each is a claim restated rather than information added."""
    fn = _sec_header()
    assert "const showStage = !opts.compact && view === 'overview';" in fn
    assert "${showStage ? '<span class=\"stage-chip\" id=\"stage-sec-overview\"" in fn, \
        "the host must be drawn only when showStage holds"
    assert "if (showStage) {" in fn, "and painted only then"


def test_no_facet_id_is_left_behind():
    """While five sections could each hold a copy it was one id per facet; with
    only Overview holding it, a per-facet id would be dead machinery."""
    code = _strip(APP)
    assert "'stage-sec-' + view" not in code
    assert "stage-sec-${esc(view)}" not in code


def test_charting_is_unaffected_and_still_shows_one_chip():
    """Compact is Charting and Options. Charting keeps its own chip in its
    price header, so the strip must never add a second there."""
    fn = _sec_header()
    assert "!opts.compact" in fn[fn.index("const showStage"):fn.index("const showStage") + 80]


def test_the_overview_chip_is_guarded_on_the_dossiers_own_symbol():
    """STATE.ticker, not STATE.chartSymbol: CLAUDE.md records the two as
    deliberately independent. Proven in a browser -- with TSLA on screen,
    NVDA's late answer painted unguarded read Stage 2 under TSLA's name."""
    fn = _sec_header()
    block = fn[fn.index("if (showStage) {"):fn.index("return `<header")]
    assert "() => (STATE.ticker || '') === sym" in block
    assert "chartSymbol" not in block


def test_it_is_painted_after_the_caller_puts_the_strip_in_the_page():
    """securityHeader returns a string; its callers assign it synchronously,
    so a microtask is the first moment the host exists."""
    assert "queueMicrotask(() => paintStage('stage-sec-overview'" in _sec_header()


def test_the_chip_sits_on_the_prices_line():
    assert "align-self: center" in _rule(".sec-id .stage-chip")
