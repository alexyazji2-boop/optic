"""Analysts' rating and price-target actions, by firm.

Asked for with a screenshot of another terminal's feed of them: "if not yet
included, include analyst estimates as well". The terminal had each name's
consensus and mean target, not who moved them. Yahoo carries the actions one
symbol at a time (969 for AAPL on 2026-09-30, the newest Morgan Stanley
reiterating Overweight at $360 on September 29) and has no market-wide list,
so the server reads the covered names in the background and keeps the recent
ones. Nothing here touches the network.
"""
from __future__ import annotations

import asyncio
import functools
import json
import os
import shutil
import subprocess
import time
import types
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient

import app.main as main
from app import analysts
from app.providers import yf as yf_provider

ROOT = Path(__file__).resolve().parent.parent
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc"
NOW = datetime(2026, 9, 30, 20, 0, tzinfo=timezone.utc).timestamp()


def _at(days_ago, hour=14):
    at = datetime.fromtimestamp(NOW, timezone.utc) - timedelta(days=days_ago)
    return at.replace(hour=hour, minute=0, second=0).strftime("%Y-%m-%dT%H:%M:%S") + "+00:00"


def _act(days_ago, firm, to, frm, action, pt_action, pt, prior):
    return {"at": _at(days_ago), "firm": firm, "to_grade": to, "from_grade": frm,
            "action": action, "pt_action": pt_action, "pt": pt, "prior_pt": prior}


BOOK = {
    "AAPL": [_act(1, "Morgan Stanley", "Overweight", "Overweight", "reit", "Maintains", 360.0, 360.0),
             _act(12, "Evercore ISI Group", "Outperform", "Outperform", "main", "Raises", 380.0, 365.0),
             _act(80, "Old Firm", "Buy", "Buy", "main", "Raises", 300.0, 290.0)],
    "INTC": [_act(2, "Citigroup", "Neutral", "Sell", "up", "Raises", 45.0, 30.0),
             _act(3, "Jefferies", "Underperform", "Hold", "down", "Lowers", 20.0, 28.0),
             _act(4, "Needham", "Buy", "", "init", "Announces", 50.0, None)],
}


class _Provider:
    def __init__(self):
        self.asked = []

    def analyst_actions(self, ticker):
        self.asked.append(ticker)
        if ticker == "BROKEN":
            raise RuntimeError("Yahoo said no")
        return list(BOOK.get(ticker, []))


@pytest.fixture
def store(monkeypatch, tmp_path):
    monkeypatch.setattr(analysts, "DB_PATH", str(tmp_path / "analysts.db"))
    return _Provider()


# ------------------------------------------------------------- the ratings


@pytest.mark.parametrize("grade,cls", [
    # The words firms used on fifteen names from 2025 on, by count.
    ("Buy", "buy"), ("Overweight", "buy"), ("Outperform", "buy"), ("Positive", "buy"),
    ("Market Outperform", "buy"), ("Strong Buy", "buy"), ("Sector Outperform", "buy"),
    ("Action List Buy", "buy"),
    ("Neutral", "hold"), ("Hold", "hold"), ("Equal-Weight", "hold"), ("Market Perform", "hold"),
    ("Sector Perform", "hold"), ("In-Line", "hold"), ("Peer Perform", "hold"),
    ("Sector Weight", "hold"), ("Perform", "hold"),
    ("Sell", "sell"), ("Underweight", "sell"), ("Underperform", "sell"), ("Reduce", "sell"),
    ("Market Underperform", "sell"), ("Strong Sell", "sell"),
    ("", None), ("Speculative", None),
])
def test_a_firms_word_is_put_in_its_class_and_nothing_is_guessed(grade, cls):
    assert analysts.grade_class(grade) == cls


# ------------------------------------------------------------- the feed


def test_the_pass_reads_what_is_due_and_keeps_the_recent_actions(store):
    out = analysts.refresh(store, ["AAPL", "INTC"], budget=10, now=NOW)
    assert out == {"read": 2, "kept": 5, "busy": False}, "the 80-day-old one is not kept"
    store.asked.clear()
    again = analysts.refresh(store, ["AAPL", "INTC"], budget=10, now=NOW + 3600)
    assert again["read"] == 0 and store.asked == [], "not due again within the refresh"
    later = analysts.refresh(store, ["AAPL", "INTC"], budget=1,
                             now=NOW + analysts.REFRESH_HOURS * 3600 + 1)
    assert later["read"] == 1, "a batch at a time"


def test_a_name_yahoo_will_not_answer_for_waits_for_the_next_cycle(store):
    analysts.refresh(store, ["BROKEN", "AAPL"], budget=10, now=NOW)
    assert analysts.due(["BROKEN", "AAPL"], now=NOW + 60) == []


def test_the_feed_is_newest_first_and_filters(store):
    analysts.refresh(store, ["AAPL", "INTC"], budget=10, now=NOW)
    feed = analysts.feed(days=7, now=NOW)
    assert [(r["ticker"], r["firm"]) for r in feed["rows"]] == [
        ("AAPL", "Morgan Stanley"), ("INTC", "Citigroup"), ("INTC", "Jefferies"),
        ("INTC", "Needham")]
    assert feed["covered"] == 2 and feed["count"] == 4
    first = feed["rows"][0]
    assert first["rating"] == "Overweight" and first["rating_class"] == "buy"
    assert first["action_label"] == "Reiterated" and first["target"] == 360.0

    def tickers(**kw):
        return [(r["ticker"], r["firm"]) for r in analysts.feed(now=NOW, **kw)["rows"]]
    assert tickers(days=7, show="upgrades") == [("INTC", "Citigroup")]
    assert tickers(days=7, show="downgrades") == [("INTC", "Jefferies")]
    assert tickers(days=7, show="initiated") == [("INTC", "Needham")]
    assert tickers(days=30, show="raised") == [("INTC", "Citigroup"), ("AAPL", "Evercore ISI Group")]
    assert tickers(days=30, show="lowered") == [("INTC", "Jefferies")]
    assert tickers(days=7, rating="sell") == [("INTC", "Jefferies")]
    assert tickers(days=7, rating="hold") == [("INTC", "Citigroup")]
    assert len(tickers(days=30)) == 5


def test_coverage_is_the_curated_names_then_the_most_traded_ranked_ones():
    ranked = [{"symbol": "ILMN", "dollar_volume": 9e8}, {"symbol": "AAPL", "dollar_volume": 9e9},
              {"symbol": "BE", "dollar_volume": 2e9}]
    assert analysts.coverage(ranked, ["NVDA", "AAPL"]) == ["NVDA", "AAPL", "BE", "ILMN"]


def test_one_name_is_read_directly_whatever_it_is(store):
    out = analysts.for_symbol(store, "intc", limit=2)
    assert out["ticker"] == "INTC" and [r["firm"] for r in out["rows"]] == ["Citigroup", "Jefferies"]
    assert out["rows"][0]["prior_rating"] == "Sell" and out["rows"][0]["action_label"] == "Upgrade"
    assert analysts.for_symbol(store, "BROKEN")["available"] is False


def test_the_provider_reads_yahoos_frame(monkeypatch):
    frame = pd.DataFrame(
        {"Firm": ["Morgan Stanley", "Needham"], "ToGrade": ["Overweight", "Buy"],
         "FromGrade": ["Overweight", ""], "Action": ["reit", "init"],
         "priceTargetAction": ["Maintains", "Announces"],
         "currentPriceTarget": [360.0, 50.0], "priorPriceTarget": [360.0, 0.0]},
        index=pd.DatetimeIndex(["2026-09-29 17:40:43", "2026-09-30 09:00:00"], name="GradeDate"))
    monkeypatch.setattr(yf_provider.yf, "Ticker",
                        lambda sym: types.SimpleNamespace(upgrades_downgrades=frame))
    monkeypatch.setattr(yf_provider, "_CACHE", {})
    rows = yf_provider.YFinanceProvider().analyst_actions("TEST")
    assert [r["firm"] for r in rows] == ["Needham", "Morgan Stanley"], "newest first"
    assert rows[1] == {"at": "2026-09-29T17:40:43+00:00", "firm": "Morgan Stanley",
                       "to_grade": "Overweight", "from_grade": "Overweight", "action": "reit",
                       "pt_action": "Maintains", "pt": 360.0, "prior_pt": 360.0}
    assert rows[0]["prior_pt"] is None, "a target of 0 is none given"


# ------------------------------------------------------------- the server


def test_the_endpoints(store, monkeypatch):
    # Pinned like every other test here. The route calls feed() with no `now`,
    # so it read the real clock, and the fixture's actions are dated from NOW:
    # INTC's upgrade, two days before 2026-09-30, fell out of the seven-day
    # window on 2026-10-05 and this failed on a tree nobody had touched.
    monkeypatch.setattr(main.analysts_mod, "feed", functools.partial(analysts.feed, now=NOW + 60))
    analysts.refresh(store, ["AAPL", "INTC"], budget=10, now=NOW)
    client = TestClient(main.app)
    feed = client.get("/api/analysts/latest", params={"days": 7, "show": "upgrades"}).json()
    assert [r["ticker"] for r in feed["rows"]] == ["INTC"] and feed["show"] == "upgrades"
    monkeypatch.setattr(main, "YF_PROVIDER", store)
    one = client.get("/api/analysts/AAPL", params={"limit": 1}).json()
    assert one["ticker"] == "AAPL" and len(one["rows"]) == 1


def test_the_server_reads_batch_after_batch_then_idles(monkeypatch):
    sleeps, due_left = [], [5, 0]

    async def sleep(seconds):
        sleeps.append(seconds)
        if len(sleeps) > 3:
            raise asyncio.CancelledError

    monkeypatch.setattr(main.asyncio, "sleep", sleep)
    monkeypatch.setattr(main, "_analyst_coverage", lambda: ["AAPL"])
    monkeypatch.setattr(main.analysts_mod, "refresh", lambda p, s, b: {"read": 1})
    monkeypatch.setattr(main.analysts_mod, "due",
                        lambda s: ["X"] * due_left.pop(0) if due_left else [])
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(main._analysts_loop())
    assert sleeps[:3] == [main.ANALYSTS_BOOT_DELAY, main.ANALYSTS_BATCH_PAUSE, main.ANALYSTS_IDLE]


def test_the_loop_starts_with_the_server_and_can_be_switched_off():
    src = open("app/main.py", encoding="utf-8").read()
    start = src[src.index("async def _start_tracker() -> None:"):][:1200]
    assert "if ANALYSTS_FEED:\n        app.state.analysts_task = asyncio.create_task(_analysts_loop())" in start
    assert 'ANALYSTS_FEED = os.environ.get("ANALYSTS_FEED", "true")' in src


# ------------------------------------------------------------- the page


APP = (ROOT / "static/app.js").read_text()


def test_the_page_is_registered_under_discover():
    assert 'id="view-analysts"' in (ROOT / "static/index.html").read_text()
    assert "analysts: $('#view-analysts')," in APP
    assert "views: ['explore', 'scan', 'insiders', 'analysts'] }," in APP
    assert "if (view === 'analysts') return loadAnalysts(force);" in APP
    assert "{ view: 'analysts', label: 'Analyst actions'," in APP
    assert "analysts: 'Analysts'," in APP
    tickerless = APP[APP.index("const TICKERLESS_VIEWS = ["):]
    assert "'analysts'" in tickerless[:tickerless.index("]")]


def _jsc(script):
    exe = JSC if os.path.exists(JSC) else shutil.which("jsc")
    if not exe:
        pytest.skip("no JavaScriptCore on this machine")
    out = subprocess.run([exe, "-e", """
      load('tests/support/browser_stubs.js');
      document.documentElement.style = document.documentElement.style || {};
      document.documentElement.style.setProperty = function () {};
      document.documentElement.style.removeProperty = function () {};
      try { load('static/charts.js'); load('static/app.js'); } catch (e) {}
    """ + script], capture_output=True, text=True, timeout=120, cwd=str(ROOT))
    assert "RESULT:" in out.stdout, (out.stdout + out.stderr)[-2000:]
    return json.loads(out.stdout.split("RESULT:", 1)[1].split("\n")[0])


ROW = {"ticker": "INTC", "at": "2026-09-28T14:00:00+00:00", "firm": "Citigroup",
       "rating": "Neutral", "prior_rating": "Sell", "rating_class": "hold", "action": "up",
       "action_label": "Upgrade", "target_action": "Raises", "target": 45.0, "prior_target": 30.0}


def test_the_page_shows_each_action_like_the_reference():
    data = {"available": True, "days": 7, "count": 1, "covered": 400, "rows": [ROW],
            "method": "As Yahoo lists them."}
    html = _jsc("print('RESULT:' + JSON.stringify({ html: analystsHTML(%s) }));"
                % json.dumps(data))["html"]
    head = html[html.index("<thead>"):html.index("</thead>")]
    order = [head.index(">%s<" % c) for c in ("Date", "Symbol", "Analyst", "Prior target",
                                              "Target", "Action", "Rating")]
    assert order == sorted(order)
    assert 'class="tkr"\n      data-analyse="INTC">INTC</button>' in html
    assert '<td class="num up">45.00</td>' in html and '<td class="num">30.00</td>' in html
    assert '<span class="an-action up">Upgrade</span>' in html
    assert 'title="From Sell">Neutral</span>' in html
    assert "1 action in the last 7 days, across 400 names" in html
    for attr in ("data-an-show", "data-an-rating", "data-an-days"):
        assert attr in html
    first = _jsc("print('RESULT:' + JSON.stringify({ html: analystsHTML({ available: true, "
                 "days: 7, count: 0, covered: 0, rows: [] }) }));")["html"]
    assert "reading the analyst actions for the first time" in first


def test_a_names_widget_lists_its_latest_actions():
    html = _jsc("""
      STATE.chartSymbol = 'INTC';
      STATE.chartData = { quote: { analyst_target: 50, recommendation: 'buy', price: 40 } };
      STATE.analystActionsFor = 'INTC';
      STATE.analystActions = { available: true, rows: [%s] };
      print('RESULT:' + JSON.stringify({ html: wsWidgetBody('analysts') }));
    """ % json.dumps(ROW))["html"]
    assert '<h4 class="ws-sub-h">Latest actions</h4>' in html
    assert "Citigroup" in html and 'data-analyse="INTC"' not in html, "its own name, no symbol column"
    assert "loadAnalystActions(false, STATE.chartSymbol);" in APP
    assert "if (wsDockOpen.includes('analysts')) loadAnalystActions(false, sym);" in APP


# ------------------------------------------------------------- the search


def test_a_searched_name_is_read_with_the_pages_filters(store):
    """Asked for as "include a search ticker bar in here". Any name, read
    directly, so one the feed does not cover works the same."""
    def firms(**kw):
        out = analysts.for_symbol(store, "INTC", now=NOW, **kw)
        return [r["firm"] for r in out["rows"]], out["count"]
    assert firms(limit=50) == (["Citigroup", "Jefferies", "Needham"], 3)
    assert firms(limit=50, days=3) == (["Citigroup"], 1), "the window, from now"
    assert firms(limit=50, show="downgrades") == (["Jefferies"], 1)
    assert firms(limit=50, show="initiated") == (["Needham"], 1)
    assert firms(limit=50, rating="buy") == (["Needham"], 1)
    assert firms(limit=1) == (["Citigroup"], 3), "the count is all that matched"
    old = analysts.for_symbol(store, "AAPL", limit=50, days=365, now=NOW)
    assert old["count"] == 3, "a year reaches past the feed's 45 days"


def test_the_endpoint_passes_the_filters(store, monkeypatch):
    monkeypatch.setattr(main, "YF_PROVIDER", store)
    client = TestClient(main.app)
    out = client.get("/api/analysts/INTC", params={"days": 30, "show": "upgrades",
                                                   "rating": "hold"}).json()
    assert [r["firm"] for r in out["rows"]] == ["Citigroup"]
    assert out["show"] == "upgrades" and out["rating"] == "hold" and out["days"] == 30


def test_the_page_has_a_search_bar_with_suggestions():
    out = _jsc("""
      analystQuery.ticker = 'INTC'; analystQuery.days = 365;
      var one = analystsHTML({ available: true, ticker: 'INTC', count: 1, days: 365, rows: [%s] });
      analystQuery.ticker = ''; analystQuery.days = 7;
      var all = analystsHTML({ available: true, days: 7, count: 0, covered: 400, rows: [] });
      print('RESULT:' + JSON.stringify({ one: one, all: all }));
    """ % json.dumps(ROW))
    one, every = out["one"], out["all"]
    assert '<form class="an-search" data-an-search role="search">' in one
    assert 'id="an-ticker" class="an-ticker" value="INTC"' in one
    assert 'aria-controls="an-ticker-results"' in one and 'id="an-ticker-results"' in one
    assert "data-an-clear>All names</button>" in one and "data-an-clear" not in every
    assert "Analyst actions: INTC</h2>" in one
    assert "1 action on INTC in the last year." in one
    assert 'data-an-days="365"' in one and 'data-an-days="365"' not in every
    assert 'value=""' in every


def test_the_search_reads_one_name_directly_and_clears_back_to_the_feed():
    fn = APP[APP.index("async function loadAnalysts(force) {"):]
    fn = fn[:fn.index("\n}")]
    assert "await getJSON(`/api/analysts/${encodeURIComponent(analystQuery.ticker)}?limit=200`" in fn
    mount = APP[APP.index("function mountAnalysts(data) {"):]
    mount = mount[:mount.index("\n}")]
    assert "attachTypeahead('an-ticker', 'an-ticker-results', (pick) => {" in mount
    clear = APP[APP.index("if (evt.target.closest('[data-an-clear]')) {"):][:300]
    assert "if (!ANALYST_DAYS.includes(analystQuery.days)) analystQuery.days = 30;" in clear
    submit = APP[APP.index("const form = evt.target.closest && evt.target.closest('[data-an-search]');"):][:400]
    assert "analystQuery.ticker = String((box && box.value) || '').trim().toUpperCase()" in submit
