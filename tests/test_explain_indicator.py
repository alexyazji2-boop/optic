"""Handoff 7 of the owner's handover pack (2026-11-03): Explain This Indicator.

What existed, verified first: the chart computes the moving averages, Bollinger Bands, RSI and MACD itself
(static/v2/js/ui/pricechart.js), its legend printed the averages' and bands' values at the crosshair's bar, the RSI and
MACD panes printed no value at all, and Milo had no way to be sent an indicator's reading: its only indicator
integration was an action card that turns an indicator on.

Now every indicator Milo can explain has Explain on its legend row or its pane and in the menus. A press drafts the
question in Milo's panel with the chart's own reading attached (the values at the latest bar, the bar's date, whether
it is still forming), and app/indicator_registry.py gives Milo the definition at the reader's level, the formula, the
limits and the definition's source, and the fixed four-part shape of the answer. The panel draws the reading above the
answer, so the value shown is the chart's whatever the model writes.

These tests use real AAPL and SPY daily closes (tests/fixtures/explain_bars_AAPL_SPY_2026-11-04.json), the chart's own
maths in JavaScriptCore, and the real chat route with a stand-in for the model that records what it was sent. No test
here judges a real model's wording, which needs a model call.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import app.main as m
from app import ai, ai_policy, indicator_registry as reg
from tests.test_frontend_v2_stage0 import V2, _run
from tests.test_milo_context_bar import ask, stand_in, told, used_of


def ask_at(context, question, level):
    """`ask`, at one of the reader's knowledge levels (the panel sends it as `mode`)."""
    from fastapi.testclient import TestClient
    r = TestClient(m.app).post("/api/chat", json={"messages": [{"role": "user", "content": question}], "context": context, "mode": level})
    assert r.status_code == 200, r.text
    out = []
    for chunk in r.text.strip().split("\n\n"):
        lines = chunk.split("\n")
        data = "".join(x[len("data: "):] for x in lines[1:] if x.startswith("data: "))
        out.append((lines[0][len("event: "):], json.loads(data) if data else None))
    return out

JS = V2 / "js"
PC = (JS / "ui/pricechart.js").read_text()
CHART = (JS / "pages/chart.js").read_text()
MILO = (JS / "ui/milo.js").read_text()
BARS = json.loads((Path(__file__).parent / "fixtures" / "explain_bars_AAPL_SPY_2026-11-04.json").read_text())["bars"]


def readings(tmp_path, sym, n=None, ids=("rsi", "macd", "ma", "ema", "bb")):
    """Each indicator's reading at the latest bar, from the chart's own functions over the fixture's closes, with the
    values as the chart prints them (core/format.js num) and the series the chart draws at that bar."""
    b = BARS[sym]
    dates, closes = b["dates"][-n:] if n else b["dates"], b["close"][-n:] if n else b["close"]
    return _run(tmp_path, f"""
      const P = await import('{(JS / "ui/pricechart.js").as_posix()}');
      const F = await import('{(JS / "core/format.js").as_posix()}');
      const dates = {json.dumps(dates)}, closes = {json.dumps(closes)};
      const bars = dates.map((d, i) => ({{ t: Date.parse(d), o: closes[i], h: closes[i], l: closes[i], c: closes[i], v: 0 }}));
      // the chart's own indicators(), as createPriceChart builds them
      const ind = {{ sma20: P.sma(closes, 20), sma50: P.sma(closes, 50), sma200: P.sma(closes, 200), ema9: P.ema(closes, 9),
        ema21: P.ema(closes, 21), ema50: P.ema(closes, 50), bb: P.bollinger(closes), rsi: P.rsi(closes), macd: P.macd(closes) }};
      const last = bars.length - 1, out = {{}};
      for (const id of {json.dumps(list(ids))}) {{
        const r = P.indicatorReading(id, bars, ind);
        out[id] = {{ reading: {{ id, symbol: '{sym}', interval: 'daily', values: r.values, close: r.close, at: dates[last], forming: false, bars: r.bars }},
          printed: Object.fromEntries(Object.entries(r.values).map(([k, v]) => [k, v === null ? null : F.num(v)])) }};
      }}
      out.series = {{ rsi: ind.rsi[last], macd: ind.macd.line[last], signal: ind.macd.signal[last], sma50: ind.sma50[last], upper: ind.bb.up[last] }};
      print(JSON.stringify(out));
    """)


def chart_context(sym, reading, interval="daily"):
    return {"focus": {"scope": "auto", "view": "chart", "view_label": "{} Dossier, Chart".format(sym), "ticker": sym,
                      "section": "Chart", "chart": {"interval": interval, "range": "1Y",
                                                    "indicators": [{"id": reading["id"]}]}},
            "indicator_explain": reading}


def test_the_chart_computes_what_explain_sends():
    # the arrays an Explain press reads are the ones the chart draws, built by the same functions
    built = PC[PC.index("const indicators = () => ({"):PC.index("  const ind = indicators();")]
    for call in ("sma20: sma(closes, 20)", "ema9: ema(closes, 9)", "bb: bollinger(closes), rsi: rsi(closes), macd: macd(closes)"):
        assert call in built
    assert "reading: (id) => indicatorReading(id, bars, ind, N - 1)," in PC, "the latest bar, from the chart's own `ind`"
    # the panes now say their value, as the legend does for the lines on the price
    assert "RSI 14${Number.isFinite(ind.rsi[vi]) ? `: ${num(ind.rsi[vi])}` : ''}</text>" in PC
    assert "MACD 12, 26, 9${Number.isFinite(m.line[vi]) ? `: ${num(m.line[vi])}" in PC and "const vi = cross >= 0 ? cross : to;" in PC


def test_acceptance_1_values_match_the_chart_at_two_levels_with_a_limitations_section(tmp_path, monkeypatch):
    """RSI, MACD, SMA and Bollinger explanations on AAPL and SPY carry the chart's values, at two knowledge levels,
    with a limitations section."""
    seen = stand_in(monkeypatch)
    for sym in ("AAPL", "SPY"):
        got = readings(tmp_path, sym)
        assert got["rsi"]["reading"]["values"]["rsi"] == got["series"]["rsi"]
        assert got["macd"]["reading"]["values"]["line"] == got["series"]["macd"] and got["macd"]["reading"]["values"]["signal"] == got["series"]["signal"]
        assert got["ma"]["reading"]["values"]["sma50"] == got["series"]["sma50"] and got["bb"]["reading"]["values"]["upper"] == got["series"]["upper"]
        for iid in ("rsi", "macd", "ma", "bb"):
            reading, printed = got[iid]["reading"], got[iid]["printed"]
            for level in ("beginner", "advanced"):
                seen.clear()
                events = ask_at(chart_context(sym, reading), "Explain {} on this {} daily chart.".format(reg.REGISTRY[iid]["short"], sym), level)
                said = told(seen)
                assert seen and "Optic's chart computed it on its own bars:" in said, (sym, iid)
                # every value exactly as the chart prints it, and the date of its bar
                for k, v in printed.items():
                    if v is not None:
                        assert v in said, (sym, iid, k, v)
                assert BARS[sym]["dates"][-1] in said
                assert "**What it measures**, **The current reading**, **Limitations**, **Sources**" in said
                assert reg.REGISTRY[iid]["limits"] in said, "the limitations Optic lists go with it"
                assert reg.definition(iid, level) in said and reg.definition(iid, "intermediate") not in said, (iid, level)
                ex = used_of(events)["explain"]
                assert ex["id"] == iid and ex["symbol"] == sym and not ex["unavailable"]
                assert all(v in ex["values"] for v in printed.values() if v is not None), "the card prints the chart's values"
                assert ex["definition_source"] == reg.REGISTRY[iid]["source"] and "Yahoo Finance" in ex["price_source"]


def test_acceptance_2_too_little_history_and_no_value_are_said_and_only_the_general_explanation_follows(tmp_path, monkeypatch):
    short = readings(tmp_path, "AAPL", n=10, ids=("rsi", "macd"))
    rsi = short["rsi"]["reading"]
    assert rsi["values"]["rsi"] is None and rsi["bars"] == 10
    r = reg.clean_reading(rsi)
    assert r["unavailable"] == "not enough data for a 14-bar RSI yet: it needs 15 bars and the chart has 10"
    no_bars = reg.clean_reading({"id": "macd", "symbol": "AAPL", "interval": "daily", "values": {}, "bars": 0, "unavailable": "no_bars"})
    assert no_bars["unavailable"] == "the chart's bars did not load, so Optic has no live value"
    # thirty bars: the MACD line, but no signal line yet, which is said rather than left out
    partial = readings(tmp_path, "AAPL", n=30, ids=("macd",))["macd"]["reading"]
    assert partial["values"]["line"] is not None and partial["values"]["signal"] is None
    assert "no signal line yet" in reg.describe(reg.clean_reading(partial))

    seen = stand_in(monkeypatch)
    for reading, reason in ((rsi, r["unavailable"]), (dict(no_bars, id="macd"), no_bars["unavailable"])):
        seen.clear()
        events = ask(chart_context("AAPL", reading), "Explain this indicator.")
        said = told(seen)
        assert "Optic has no live value for it: {}. Give the general explanation only".format(reason) in said
        assert 'begin The current reading with "Live value unavailable: {}."'.format(reason) in said
        assert "Optic's chart computed it" not in said
        ex = used_of(events)["explain"]
        assert ex["unavailable"] == reason and ex["values"] == ""
    card = _run(tmp_path, f"""
      const M = await import('{(JS / "ui/milo.js").as_posix()}');
      const D = await import('{(JS / "core/dom.js").as_posix()}');
      const strip = (t) => D.toString(t).replace(/<[^>]+>/g, ' ').replace(/\\s+/g, ' ').trim();
      const off = {json.dumps(reg.used(r))}, live = {json.dumps(reg.used(reg.clean_reading(dict(readings(tmp_path, "AAPL", ids=("rsi",))["rsi"]["reading"], forming=True))))};
      print(JSON.stringify({{ off: strip(M._test.explainCard({{ used: {{ explain: off }} }})), live: strip(M._test.explainCard({{ used: {{ explain: live }} }})) }}));
    """)
    assert card["off"] == ("RSI 14 · AAPL · Daily Live value unavailable: not enough data for a 14-bar RSI yet: it needs 15 bars "
                           "and the chart has 10. What follows is the general explanation only.")
    assert card["live"].startswith("RSI 14 · AAPL · Daily RSI ") and "on Nov 4, 2026" in card["live"]
    assert card["live"].endswith("The latest bar is still forming, so this value can change until it closes.")


# Words that tell a reader to act: an explanation describes, so none of these may appear in Optic's own text
_ADVICE = re.compile(r"\b(?:buy|buying|sell|selling|you\s+should|should\s+you|consider\s+\w+ing|take\s+profits?|time\s+to|target|"
                     r"stop[- ]loss|enter|exit|trim|go\s+long|go\s+short)\b", re.I)


def _corpus():
    """Optic's own words for every indicator: each level's definition, the formula, the limits, and what a reading
    describes over a grid of readings, including the extremes, crossings and closes outside the bands."""
    out = []
    for iid, e in reg.REGISTRY.items():
        out += [e["levels"][lv] for lv in reg.LEVELS] + [e["formula"], e["limits"]]
    for x in [0, 0.5, 12, 29.9, 30, 41.2, 50, 58.21, 70, 70.01, 85, 99.5, 100]:
        out.append(reg.describe(reg.clean_reading({"id": "rsi", "symbol": "AAPL", "values": {"rsi": x}, "at": "2026-11-04", "bars": 300})))
    for line, sig in [(2.31, 1.85), (-1.2, -0.4), (0.0, 0.3), (-3.0, None)]:
        out.append(reg.describe(reg.clean_reading({"id": "macd", "symbol": "SPY", "values": {"line": line, "signal": sig, "hist": None if sig is None else line - sig},
                                                   "at": "2026-11-04", "bars": 300})))
    for c in (300.0, 349.51, 400.0):
        out.append(reg.describe(reg.clean_reading({"id": "ma", "symbol": "AAPL", "close": c, "values": {"sma20": 340.0, "sma50": 349.5, "sma200": None},
                                                   "at": "2026-11-04", "bars": 120})))
        out.append(reg.describe(reg.clean_reading({"id": "ema", "symbol": "AAPL", "close": c, "values": {"ema9": 345.0, "ema21": 341.0, "ema50": 330.0},
                                                   "at": "2026-11-04", "bars": 300})))
        out.append(reg.describe(reg.clean_reading({"id": "bb", "symbol": "AAPL", "close": c, "values": {"upper": 360.1, "middle": 340.25, "lower": 320.4},
                                                   "at": "2026-11-04", "bars": 300})))
    return [t for t in out if t]


def test_acceptance_3_no_recommendation_language_in_a_corpus_of_explanations():
    corpus = _corpus()
    assert len(corpus) >= 60, len(corpus)
    for text in corpus:
        assert not _ADVICE.search(text), text
        assert not ai_policy.check_output(text), text
    # "overbought" and "oversold" appear only as names for a reading, never as a call
    named = [t for t in corpus if "overbought" in t or "oversold" in t]
    assert named and all("not a forecast" in t or "describe the size of recent moves, not what comes next" in t for t in named)
    # and a model's answer that turns a reading into an order is caught by the advice gate before the reader sees it
    advice = ["RSI at 72 is overbought, consider taking profits.", "With RSI at 75, it's time to take profits.",
              "The MACD just crossed its signal line, so you should buy.", "Now is a good time to trim.",
              "Sell when the price closes above the upper band."]
    described = ["An RSI of 72 means the average gain over the last 14 bars was 2.57 times the average loss.",
                 "Readings above 70 are often called overbought; the name describes recent gains, not what comes next.",
                 "When RSI tops 70, some traders consider trimming, but the reading predicts nothing on its own.",
                 "The MACD line is above its signal line by 0.46.", "The close sits 75% of the way from the lower band to the upper."]
    assert all(ai_policy.check_output(t) for t in advice), [t for t in advice if not ai_policy.check_output(t)]
    assert not any(ai_policy.check_output(t) for t in described), [t for t in described if ai_policy.check_output(t)]
    # and Milo is told the same rule with every Explain press
    lines = "\n".join(reg.header_lines(reg.clean_reading({"id": "rsi", "symbol": "AAPL", "values": {"rsi": 72.0}, "at": "2026-11-04", "bars": 300})))
    assert "Describe, never advise" in lines and 'say it names a reading above 70 or below 30 and predicts nothing on its own' in lines


def test_every_explainable_indicator_has_an_entry_on_both_sides_and_one_name():
    explainable = dict(re.findall(r"(\w+): \[([^\]]*)\]", PC[PC.index("export const EXPLAINABLE = {"):PC.index("const fin = ")]))
    assert set(explainable) == set(reg.IDS)
    for iid, keys in explainable.items():
        assert [k.strip(" '") for k in keys.split(",")] == reg.REGISTRY[iid]["values"], iid
    spec = dict(re.findall(r"(\w+): \['([^']+)', \{", CHART[CHART.index("const STUDY_SPEC = {"):CHART.index("/** The indicators on the chart now")]))
    for iid in reg.IDS:
        assert spec[iid] == reg.REGISTRY[iid]["short"], iid
        for lv in reg.LEVELS:
            assert reg.REGISTRY[iid]["levels"][lv], (iid, lv)
    from fastapi.testclient import TestClient
    pub = TestClient(m.app).get("/api/indicator-registry").json()
    assert set(pub["indicators"]) == set(reg.IDS) and pub["levels"] == list(reg.LEVELS)


def test_explain_sits_on_each_indicator_and_only_drafts():
    # the legend's rows and the panes Milo can explain, beside Remove; the menus, under each indicator that is on
    assert 'data-pc-explain="${esc(k)}" aria-label="Explain ${name} with Milo"' in PC
    assert "S.onExplain && EXPLAINABLE[k] ?" in PC and "if (b.dataset.pcExplain) { if (S.onExplain) S.onExplain(b.dataset.pcExplain); return; }" in PC
    assert "onExplain: explain," in CHART
    assert "<span>${l}</span></label>${explainBtn(k, V.overlays[k] && !no)}" in CHART and "<span>${l}</span></label>${explainBtn(k, V.panes[k] && !cannot(k))}" in CHART
    # a press opens Milo with the question drafted and the reading attached; nothing is sent until Send
    explain = CHART[CHART.index("function explain(id) {"):CHART.index("function visibleBars() {")]
    assert "openMilo({ question:" in explain and "send:" not in explain and "explain: reading" in explain
    assert "unavailable: 'no_bars'" in explain, "a chart with no bars says so rather than sending nothing"
    # the reading goes only with the page it was read from, and a press brings the page's context back after a Remove
    assert "if (scope === 'auto' && asked && asked.explain && (!r.symbol || asked.explain.symbol === r.symbol)) ctx.indicator_explain = asked.explain;" in MILO
    assert "if (explain && S.scope !== 'auto') S.scope = 'auto';" in MILO


def test_an_explain_press_gathers_no_research_and_keeps_its_reading_with_the_answer(tmp_path, monkeypatch):
    ran = []

    async def research(history, context, horizon=None):
        ran.append("research")
        return context
    stand_in(monkeypatch)
    monkeypatch.setattr(m, "_with_research", research)
    reading = readings(tmp_path, "SPY", ids=("bb",))["bb"]["reading"]
    ask(chart_context("SPY", reading), "Explain Bollinger 20, 2 on this SPY daily chart.")
    assert ran == [], "answered from the chart's reading and Optic's definition, with nothing else to wait for"
    # the reading is said once, in the header, not again in the data below it
    body = ai.budget_context(chart_context("SPY", reading))[0]
    assert "indicator_explain" not in body
    # what the answer was for, the reading included, is kept with the conversation
    kept = _run(tmp_path, f"""
      const C = await import('{(JS / "ui/milo-context.js").as_posix()}');
      const k = C.keepUsed({{ ticker: 'SPY', explain: {json.dumps(reg.used(reg.clean_reading(reading)))} }});
      print(JSON.stringify({{ k, when: C.barWhen('2026-11-04'), intraday: C.barWhen('2026-11-04T15:00') }}));
    """)
    assert kept["k"]["explain"]["short"] == "Bollinger 20, 2" and kept["k"]["explain"]["values"].startswith("upper ")
    assert kept["when"] == "Nov 4, 2026" and kept["intraday"] == "Nov 4, 2026, 3:00 pm ET"
    # a reader who removed the page's context sent no chart, so no reading is read from it
    general = dict(chart_context("SPY", reading), focus={"scope": "none", "ticker": None})
    assert ai.explain_reading(general) is None and ai.context_used(general)["explain"] is None
