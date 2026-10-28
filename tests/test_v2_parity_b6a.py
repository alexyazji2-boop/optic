"""Classic parity, batch B6a (2026-10-21): the thesis check on the Overview, and the Overview's advanced research. The
rules and the stored record run in JavaScriptCore against Classic's shapes (optic.thesis.v1, old and partial records,
one Brokerage wrote). The interactions (the form, a redraw while typing, saving in the browser and to the account,
a failed save, Delete and Undo, Milo's drafted question) were driven in headless Chrome
(~/Optic/work/classic-parity/b6a_thesis_check.py). These tests are not interaction evidence. Ledger:
docs/frontend-v2/CLASSIC-PARITY.md, B6a.
"""
from tests.test_frontend_v2_stage0 import V2, _run

JS = V2 / "js"
THESIS = (JS / "pages/thesis.js").read_text()
CLASSIC = (V2.parent / "app.js").read_text()
D = """{ quote: { price: 250, revenue_growth: -0.02, profit_margin: 0.2 }, technicals: { bias: 'bullish', rsi: { value: 61 }, moving_averages: { sma200: { value: 240 } } },
  company: { financials: { margins: { net_pct: 21.5 } }, earnings_history: { quarters: [{ date: '2026-07-30', surprise_pct: -1.5 }], upcoming: [{ date: '2026-11-02' }] } },
  sector_confirm: { available: true, rs_vs_sector_label: 'Lagging its sector', window_sessions: 21, rs_vs_sector_pct: -3.2 },
  pulse: { stance: 'bullish', conviction: 'low' }, gex: { regime: { state: 'positive' } }, flow: { stance: 'neutral' } }"""
LT = "{ holding: { valuation_history: { available: true, usable_years: 4, current_pe: 30, median_pe: 24 } } }"


def test_the_seven_conditions_read_as_classics(tmp_path):
    got = _run(tmp_path, f"""
      const T = await import('{(JS / "pages/thesis.js").as_posix()}');
      const d = {D}, lt = {LT};
      const r = Object.fromEntries(T.CHECKS.map((c) => [c.id, T.readItem(d, lt, {{ id: c.id, level: 260 }})]));
      print(JSON.stringify({{ ids: T.CHECKS.map((c) => c.id), labels: T.CHECKS.map((c) => c.label), r, none: T.readItem({{}}, null, {{ id: 'trend' }}), noval: T.readItem(d, {{ holding: {{ valuation_history: {{ available: true, usable_years: 2, current_pe: 30, median_pe: 24 }} }} }}, {{ id: 'value' }}),
        lead: T.readItem(Object.assign({{}}, d, {{ sector_confirm: {{ available: true, rs_vs_sector_label: 'Leading its sector', rs_vs_sector_pct: 5 }} }}), lt, {{ id: 'sector' }}), snap: T.snapshot(d), lv: [T.levelOf('$1,200.50'), T.levelOf(''), T.levelOf('abc')] }}));
    """)
    assert got["ids"] == ["trend", "growth", "profit", "beats", "value", "sector", "level"]
    for label in got["labels"]:
        assert f"label: '{label}'" in CLASSIC, f"Classic's wording: {label}"
    r = got["r"]
    assert r["trend"] == {"ok": True, "now": "$250.00 against a 200-day average of $240.00"}
    assert r["growth"]["ok"] is False and r["growth"]["now"].endswith("in the latest quarter against a year earlier")
    assert r["profit"] == {"ok": True, "now": "net margin 21.5%"}, "the reported margin before the quote's"
    assert r["beats"]["ok"] is False and r["beats"]["now"].startswith("last report Jul 30:")
    assert r["value"]["ok"] is False and "30.0 times earnings" in r["value"]["now"] and "4-year average" in r["value"]["now"], "25% over its own history"
    assert r["sector"]["ok"] is False and r["sector"]["now"].startswith("lagging its sector over 21 sessions")
    assert got["lead"]["ok"] is True and got["lead"]["now"].startswith("leading its sector over 21"), "said once when the label already has it (Classic printed 'its its')"
    assert r["level"] == {"ok": False, "now": "$250.00 against your level of $260.00"}
    assert got["none"] is None and got["noval"] is None, "a missing figure is unknown, never a guess; fewer than 3 years of P/E is no history"
    assert got["snap"] == {"stance": "bullish", "conviction": "low", "price": 250, "bias": "bullish", "rsi": 61, "gamma": "positive", "flow": "neutral", "earnings": None}
    assert got["lv"][0] == 1200.5 and got["lv"][1] is None and got["lv"][2] is None, "NaN, as JSON's null"


def test_saving_keeps_classics_record_and_the_readers_other_words(tmp_path):
    got = _run(tmp_path, f"""
      const T = await import('{(JS / "pages/thesis.js").as_posix()}');
      const d = {D}, lt = {LT};
      const items = T.itemsFrom(d, lt, ['trend', 'level', 'nonesuch'], '$245');
      const fresh = T.entryFor(null, {{ note: '  Services  ', items, d, now: '2026-10-21T12:00:00Z' }});
      // what Brokerage's form writes, with its own reassess line, horizon and assumptions
      const bk = {{ bull: 'AI capex', bear: 'Concentration', catalysts: 'Ramp', invalidation: 'If capex is cut', horizon: '3 years', assumptions: 'Supply holds', created_at: '2026-01-01', snapshot: {{}} }};
      const over = T.entryFor(bk, {{ note: 'AI capex', items, d, now: 'x' }});
      // a thesis check saved before, whose words are the automatic ones: they are rewritten with the new conditions
      const auto = T.entryFor(fresh, {{ note: 'n', items: T.itemsFrom(d, lt, ['profit'], ''), d, now: 'y' }});
      print(JSON.stringify({{ items, fresh, over, auto, noLevel: T.itemsFrom(d, lt, ['trend', 'level'], ''), none: T.itemsFrom(d, lt, [], '') }}));
    """)
    assert got["items"] == [{"id": "trend", "was": True, "was_text": "$250.00 against a 200-day average of $240.00"},
                            {"id": "level", "level": 245, "was": True, "was_text": "$250.00 against your level of $245.00"}], "an unknown rule is dropped"
    f = got["fresh"]
    assert f["bull"] == "Services" and f["bear"] == "" and f["catalysts"] == "" and f["saved_at"] == "2026-10-21T12:00:00Z"
    assert f["invalidation"] == "Would change my mind if any of these stop holding: The price stays above its 200-day average; The price stays above $245.00."
    assert f["snapshot"]["check"] == {"v": 1, "items": got["items"]} and f["snapshot"]["stance"] == "bullish"
    o = got["over"]
    assert (o["bear"], o["catalysts"], o["invalidation"], o["horizon"], o["assumptions"], o["created_at"]) == ("Concentration", "Ramp", "If capex is cut", "3 years", "Supply holds", "2026-01-01")
    assert got["auto"]["invalidation"] == "Would change my mind if any of these stop holding: It stays profitable."
    assert got["noLevel"] is None and got["none"] is None, "the level ticked without a level is refused, not dropped"
    assert "invalidation: 'Would change my mind if any of these stop holding: ' + labels.join('; ') + '.'" in CLASSIC, "Classic's words"


def test_a_saved_check_is_read_against_now(tmp_path):
    got = _run(tmp_path, f"""
      const T = await import('{(JS / "pages/thesis.js").as_posix()}');
      const d = {D}, lt = {LT};
      const rv = T.review([{{ id: 'trend', was: false }}, {{ id: 'profit', was: true }}, {{ id: 'growth', was: true }}, {{ id: 'nonesuch', was: true }}, {{ id: 'beats' }}], d, lt);
      const one = T.review([{{ id: 'trend', was: true }}], d, lt), blind = T.review([{{ id: 'trend', was: true }}], {{}}, null);
      // Classic's record shapes: a check, an old free-text one, junk
      const shapes = [T.checkOf({{ snapshot: {{ check: {{ v: 1, items: [] }} }} }}), T.checkOf({{ bull: 'x', snapshot: {{ price: 1 }} }}), T.checkOf(null), T.checkOf({{ snapshot: {{ check: {{ items: 'no' }} }} }})].map(Boolean);
      localStorage.setItem(T.THESIS_KEY, '[1,2]'); const arr = T.localAll();
      localStorage.setItem(T.THESIS_KEY, 'nonsense'); const junk = T.localAll();
      const q = T.stressText('AAPL', {{ bull: 'Mine', snapshot: {{ check: {{ items: [{{ id: 'trend' }}, {{ id: 'level', level: 200 }}] }} }} }});
      print(JSON.stringify({{ rv, one: one.head, blind: blind.head, shapes, arr, junk, q }}));
    """)
    rv = got["rv"]
    assert [r["state"] for r in rv["rows"]] == ["holds", "holds", "changed", "unknown", "changed"]
    assert [r["flipped"] for r in rv["rows"]] == [True, False, True, False, False], "a condition never read when written cannot have flipped"
    assert rv["head"] == "2 of your 4 conditions hold." and rv["flips"] == 2 and rv["broken"] is True
    assert got["one"] == "Your condition holds." and got["blind"] == "Optic could not check your conditions just now."
    assert got["shapes"] == [True, False, False, False]
    assert got["arr"] == {} and got["junk"] == {}
    assert got["q"] == ('Stress-test my thesis on AAPL. My conditions: The price stays above its 200-day average; The price stays above $200.00. In my words: "Mine" '
                        "Using the data on this page, what is the strongest evidence against it, which condition is closest to breaking, and what should I watch next? "
                        "Treat these as my reasons, not as a recommendation.")
    assert "Using the data on this page, what is the strongest evidence against it, which condition is closest to breaking, and what should I watch next? Treat these as my reasons, not as a recommendation." in CLASSIC


def test_the_thesis_section_survives_the_overviews_redraws():
    dossier = (JS / "pages/dossier.js").read_text()
    assert "html`<div data-tc-slot></div>`" in dossier and "mountThesis(main, sym, () => D);" in dossier
    assert dossier.index("mountThesis(main, sym, () => D);") < dossier.index("if (Math.abs(window.scrollY - scrollY) > 2)"), "put back before the scroll is restored"
    assert "The thesis check is in the classic app." not in dossier
    assert "slot.replaceWith(TC.node);" in THESIS and "n.addEventListener('focusin'" in THESIS, "one node for the visit; focus and the caret put back"
    assert "not by an AI model, and not a recommendation" in THESIS and "/api/chat" not in THESIS


# ---------------------------------------------------------------- the Overview's deeper research (B6a.2 to B6a.6)
RESEARCH = (JS / "pages/overview-research.js").read_text()
T = """{ quote: { price: 250, market_cap: 3.7e12, trailing_pe: 30, forward_pe: 0, trailing_eps: 8.3, dividend_yield: 0, volume: 4.1e7, fifty_two_high: 260, fifty_two_low: 180, profit_margin: 0.27, revenue_growth: 0.164, beta: 1.1 },
  company: { financials: { available: true, growth: { revenue_yoy_pct: 6.4, net_income_yoy_pct: -3 }, margins: { net_pct: 26.9 }, balance_sheet: { net_cash: -6e10 } },
    earnings_history: { available: true, sample_size: 8, beat_count: 7, upcoming: [{ date: '2026-11-02', timing: 'before_open', eps_estimate: 1.98 }] },
    short_interest: { available: true, percent_of_float: 0.0083, days_to_cover: 2.8, settlement_date: '2026-09-30', squeeze_potential: 'low' }, ownership: { available: true, insider_signal: 'selling' } },
  news: { overall_tone: 'mildly bearish', article_count: 12 }, sector_confirm: { available: true, rs_vs_sector_label: 'Leading its sector', rs_vs_spy_label: 'Outperforming SPY', window_sessions: 21, stock_return_pct: 0.2, etf_return_pct: -4.8, spy_return_pct: -0.6 },
  gex: { regime: { state: 'negative' } }, verdict: { composite_score: 7.4 },
  pulse: { stance: 'bullish', conviction: 'low', agreement_pct: 60, factors_priced: 4, factors_total: 5, pending_catalyst: { pending: true },
    factors: [{ key: 'technicals', label: 'Momentum', score: 60, weight_pct: 17 }, { key: 'gamma', label: 'Options', score: 40, weight_pct: 24 }, { key: 'flow', label: 'Positioning', score: 5, weight_pct: 20 },
      { key: 'news', label: 'News', score: -30, weight_pct: 29 }, { key: 'macro', label: 'Macro', unavailable: true, why_unavailable: 'no FRED key' }], conflicts: ['A conflict.'] },
  whats_next: { this_week: [{ date: '2026-10-23', label: 'CFTC Commitments of Traders (COT)', kind: 'macro' }, { date: '2026-10-28', label: 'FOMC statement and rate decision (FOMC)', kind: 'macro' }] } }"""


def test_the_case_for_and_against_follows_classics_rules(tmp_path):
    got = _run(tmp_path, f"""
      const R = await import('{(JS / "pages/overview-research.js").as_posix()}');
      const t = {T}, lt = {LT}, today = new Date(2026, 9, 21);
      const f = R.factors(t, {{ lt, stars: {{ available: true, stars: 3 }}, price: {{ yr: 12, m3: -2, off: -25 }}, today }});
      const fund = R.factors(t, {{ lt, fund: true, today }});
      print(JSON.stringify({{ f, fundNeg: fund.neg.map((x) => x.text), ev: R.events(t, false, today), evAdv: R.events(t, true, today).map((e) => e.label),
        steps: R.nextSteps('AAPL', t, f, false, today), fsteps: R.nextSteps('SPY', t, f, true, today).map((s) => s.view || 'compare'), drv: R.drivers(t).map((d) => d.kind) }}));
    """)
    f = got["f"]
    assert [x["text"] for x in f["pos"]] == ["Revenue grew 6.4% in the latest fiscal year", "Profitable: about 27 cents of profit per dollar of sales",
                                             "Beat analysts' earnings estimates in 7 of the last 8 quarters", "Share price up 12% over the period shown"], "four at most, in Classic's order"
    neg = [x["text"] for x in f["neg"]]
    assert neg[0] == "Earnings report on Nov 2, in 12 days" and neg[1].startswith("Priced above its own history: 30.0 times earnings against a 4-year average of 24.0")
    assert len(neg) == 4 and neg[2] == "Net income fell 3.0% in the latest fiscal year" and neg[3] == "Options positioning may amplify price swings"
    assert all(x.get("view") for x in f["neg"]) and f["neg"][0]["why"].startswith("Results and guidance")
    assert not any("Priced above" in x for x in got["fundNeg"]), "a fund's price is not read against a P/E history"
    ev = got["ev"]
    assert next(e for e in ev if e["label"] == "Earnings report") == {"date": "2026-11-02", "label": "Earnings report", "detail": "in 12 days, analysts expect EPS of 1.98", "view": "earnings"}, "the date alone: no time of day (B1 rule)"
    # by date since the investor audit (2026-10-27): the Fed on Oct 28 before the Nov 2 report
    assert [e["label"] for e in ev] == ["FOMC statement and rate decision", "Earnings report"] and "CFTC Commitments of Traders" in got["evAdv"], "positioning reports at Advanced (the abbreviation dropped, as Classic does)"
    assert [s.get("view") or "compare" for s in got["steps"]] == ["earnings", "financials", "long", "news"] and got["steps"][1]["text"] == "Check the statements behind the weaker figures"
    assert "financials" not in got["fsteps"]
    assert got["drv"] == ["Market and sector", "Optic's short-term signals", "Options positioning"]
    assert "'Earnings report', detail: [" in RESEARCH and "reportTiming" not in RESEARCH


# Reconciled with the Overview port, 2026-10-25: B6a's pulseWhy(), scores() and keyStats() were replaced by the
# port's Optic's read, its Optic Score and keyStatRows(), the owner's refined design. Their tests are
# tests/test_v2_overview_classic_port.py and tests/test_v2_read_conviction.py; what stays here is B6a's own.


def test_the_statistics_definitions_and_the_stage_term(tmp_path):
    got = _run(tmp_path, f"""
      const Tm = await import('{(JS / "ui/term.js").as_posix()}');
      Tm.defineLive('stage:aapl', 'Price is 10% above a rising 30-week average.');
      print(JSON.stringify({{ defs: ['stat:pe_forward', 'stat:open', 'stat:nonesuch', 'open', 'stage:AAPL'].map((k) => (Tm.define(k) || {{}}).def || null) }}));
    """)
    assert "Price to earnings against what analysts expect" in got["defs"][0] and got["defs"][1].startswith("The price the regular session opened at")
    assert got["defs"][2] is None and got["defs"][3] is None, "a bare word such as 'open' is not a term: only stat: keys reach these"
    assert got["defs"][4] == "Price is 10% above a rising 30-week average."
    for k in ("pe_forward", "open", "beta", "revenue_growth"):
        assert f"  {k}: " in CLASSIC, k


def test_the_research_sections_and_where_they_sit():
    dossier = (JS / "pages/dossier.js").read_text()
    # the Overview port's layout (2026-10-25), with B6a's thesis check and a fund's risk card kept in it
    assert "${digest(sym)}${fund ? '' : html`<div data-tc-slot></div>`}${OR.nextSection(c)}${D.ticker ? more(sym) : ''}${OR.advancedSection(c)}" in dossier
    assert "levels: { 'advanced research': 2 }" in dossier, "one press away below the Advanced level"
    assert "${fund ? OR.fundRisk(sym, c.f) : ''}" in dossier and "export function fundRisk(sym, f)" in RESEARCH
    assert "api.get(`/api/stage?symbol=${enc}`" in dossier and "{ stage: () => stageFor(sym) }" in dossier, "the stage survives the live price's redraws"
    assert "TR.historyLine('stage')" in dossier, "the stage's explanation says what its replay on history found (B6c)"
    assert "/api/chat" not in RESEARCH and "repeating-linear-gradient" not in (V2 / "css/pages.css").read_text()
