"""Classic parity, batch B8b (2026-10-21): Home's What changed since yesterday, Questions worth asking and Index and
sector trends. The pure rules run in JavaScriptCore: the day's questions (Classic's marketQuestions, its questions
word for word), the holdings sent with the briefing, the briefing's rows, and the trend board's basis line. The panels,
a question drafting into Milo with nothing sent, opening Options at Swing setups and the phone fit were driven in
headless Chrome (~/Optic/work/classic-parity/b8b_check.py). These tests are not interaction evidence. Ledger:
docs/frontend-v2/CLASSIC-PARITY.md, B8b.
"""
from tests.test_frontend_v2_stage0 import V2, _run

JS = V2 / "js"
CLASSIC = (V2.parent / "app.js").read_text()
WS = (JS / "pages/workspace.js").read_text()
HOME = """{ session: { now_et: '2026-10-21T10:00:00-04:00', phase: 'regular' },
  macro: { regime: 'mildly risk-on', curve_3m10y: 1.02, ratios: [{ name: 'Nasdaq / S&P', chg_20d: -2.9, reads: 'growth vs broad market leadership; more' }],
    groups: { equity: [{ label: 'S&P 500', chg_1d: 0.3, atr_pct: 1.0 }, { label: 'S&P 500 futures', chg_1d: 0.35, atr_pct: 1.0 }],
              commodities: [{ label: 'Nat Gas', chg_1d: -4.3, atr_pct: 4.0, chg_20d: 9.1 }, { label: 'Gold', chg_1d: 2.4, atr_pct: 1.2, chg_20d: 3.0 }],
              volatility: [{ label: 'VIX', last: 17.24, chg_1d: 1.0, atr_pct: 6 }] } },
  indices: { counts: { uptrend: 1, downtrend: 0, neutral: 3 } },
  read: { stories: [{ title: 'Oil falls as traders hope for progress.' }] },
  morning_desk: { catalyst: { title: 'Producer Price Index', short: 'PPI', importance: 6, days_away: 1, time_label: '8:30 AM ET' } } }"""


def test_the_days_questions(tmp_path):
    got = _run(tmp_path, f"""
      const Q = await import('{(JS / "core/market-questions.js").as_posix()}');
      const d = {HOME};
      const next = JSON.parse(JSON.stringify(d)); next.session.now_et = '2026-10-22T10:00:00-04:00';
      const shut = JSON.parse(JSON.stringify(d)); shut.session.phase = 'closed';
      print(JSON.stringify({{ qs: Q.marketQuestions(d), all: Q.marketQuestions(d, 20), next: Q.marketQuestions(next, 20), shut: Q.marketQuestions(shut)[1], ranked: Q.rankedMoves(d).map((m) => m.label), none: Q.marketQuestions(null) }}));
    """)
    qs = got["qs"]
    assert qs[0] == "Gold is up 2.4% today. Is that supply or demand?", "the day's biggest move against its own typical day (Gold 3.2 typical days, Nat Gas 1.7), not the biggest percent"
    assert qs[1] == "Oil falls as traders hope for progress: what does that mean for markets?"
    assert qs[2] == "PPI is out tomorrow at 8:30 AM ET. What would a hot or a cool number do?"
    assert len(qs) == 5 and got["none"] == []
    assert got["ranked"][:2] == ["Gold", "Nat Gas"] and "S&P 500 futures" in got["ranked"] and "S&P 500" not in got["ranked"], "one row per market: the larger mover of the pair keeps the place"
    assert not any(q.startswith("Nat Gas is up 9.1% over twenty days") for q in got["all"]), "commodities already asked about today, so the standing commodity question is skipped"
    assert "What is the market expecting from the Fed?" in got["all"] and "VIX is at 17.2. Is the market underpricing risk?" in got["all"]
    assert got["all"][3:] != got["next"][3:] and sorted(got["all"][3:]) == sorted(got["next"][3:]), "the pool rotates by the market day; the same questions, another order"
    assert got["shut"] == "Single stocks are not trading. What are the futures telling me?"
    for words in ("Is the market underpricing risk?", "What would a hot or a cool number do?", "What are the futures telling me?", "What does that hold up?".replace("What does", "Does"), "Who does that hurt?"):
        assert words in CLASSIC, words
    assert "const RANGE_PER_SIGMA = 1.6;" in CLASSIC


def test_the_briefings_holdings_and_rows(tmp_path):
    got = _run(tmp_path, f"""
      const H = await import('{(JS / "pages/home.js").as_posix()}');
      const {{ toString }} = await import('{(JS / "core/dom.js").as_posix()}');
      localStorage.setItem('optic.paper.v1', JSON.stringify({{ open: [{{ ticker: 'tsla', qty: 3 }}], closed: [{{ ticker: 'GONE' }}] }}));
      localStorage.setItem('optic.roth.inputs', JSON.stringify({{ holdings: 'VTI 10\\nschd, 4\\n  12 bad' }}));
      const held = H.briefingHoldings([{{ symbol: 'aapl', quantity: 2 }}, {{ symbol: 'TSLA' }}]);
      const items = [1, 2, 3, 4, 5].map((i) => ({{ symbol: 'SPY', headline: `SPY thing ${{i}}`, why: i < 3 ? 'Same reason.' : `Reason ${{i}}.`, link: i === 1 ? {{ view: 'swing', panel: 'Swing setups' }} : {{ view: 'chart' }} }}));
      const t = (all) => toString(H.changesBlock({{ available: true, summary: 'x', items, names: [], period: {{ label: 'From A to B' }} }}, all));
      print(JSON.stringify({{ held, four: (t(false).match(/class="dc-item"/g) || []).length, five: (t(true).match(/class="dc-item"/g) || []).length, same: (t(false).match(/Same reason\\./g) || []).length,
        head: /class="dc-head">Thing 1</.test(t(false)), open: /data-v2-dc-view="options" data-v2-dc-panel="Swing setups">Swing setups/.test(t(false)), more: /All 5 changes/.test(t(false)) }}));
    """)
    assert got["held"] == ["TSLA", "VTI", "SCHD", "AAPL"], "open paper trades, the planner's holdings box, a linked brokerage; symbols only, once each"
    assert got["four"] == 4 and got["five"] == 5 and got["more"], "four, and the rest one press away"
    assert got["same"] == 1, "a kind of change says what it means once"
    assert got["head"] and got["open"], "the symbol is not said twice; a setup opens Options at Swing setups"
    assert "const DAILY_ITEMS_SHOWN = 4;" in CLASSIC and "paperBook.open" in CLASSIC and "STATE.rothInputs" in CLASSIC
    assert "api.post('/api/briefing', { symbols: store.allSymbols(), holdings: briefingHoldings(" in WS


def test_the_trend_boards_basis_line(tmp_path):
    got = _run(tmp_path, f"""
      const H = await import('{(JS / "pages/home.js").as_posix()}');
      const now = new Date('2026-10-21T14:10:00Z');
      print(JSON.stringify({{
        live: H.trendBasis({{ levels_label: "Tuesday's session", price_kind: 'regular session', price_kinds: {{ 'regular session': 13, 'last close': 1 }}, price_as_of: '2026-10-21T14:04:00Z', price_as_of_from: '2026-10-21T13:50:00Z', delayed: [{{ symbol: 'QQQ', minutes: 15 }}] }}, now),
        closed: H.trendBasis({{ levels_label: "Tuesday's session", price_kind: 'last close', price_kinds: {{ 'last close': 14 }} }}, now),
        none: H.trendBasis(null) }}));
    """)
    assert got["live"] == ("Levels: Tuesday's session. Price: regular session, struck between 9:50 AM ET and 10:04 AM ET. "
                           "1 of 14 have not traded since that close, so they show it and read neutral. Delayed by the feed: QQQ 15 minutes.")
    assert got["closed"].startswith("Levels: Tuesday's session. Price: the last close, as nothing has printed since it.")
    assert got["none"] == ""
    assert "have not traded since that close, so they show it and read neutral." in CLASSIC


def test_the_panels_on_home():
    overview = WS.split("market: { label: 'Market Overview'")[1].split("\n")[0]
    for pid in ("changes", "questions", "trends"):
        assert f"  {pid}: {{" in WS and f"'{pid}'" not in overview, f"{pid}: one Add panel away; Market Overview keeps the owner's order (tests/test_v2_navigation_layout.py)"
    assert "const MARKET_PANELS = ['indices', 'regime', 'expected', 'sectors', 'watch', 'quote', 'contracts', 'portfolio', 'trends'];" in WS
    assert "miloButton(q, { ask: q, context: 'Home, Questions worth asking'" in WS, "a question only drafts into Milo"
