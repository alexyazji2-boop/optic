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
