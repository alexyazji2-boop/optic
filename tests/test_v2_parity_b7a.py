"""Classic parity, batch B7a (2026-10-21): the fair-value model's editor on Investing. The pure rules run in
JavaScriptCore: Classic's optic.dcf.v1 store (edits kept per symbol, the saved models left as they are, junk read as
empty), how a box's text becomes an edit, the formats, and the methods side by side. The server does the arithmetic
(POST /api/valuation/{T}/run); the interactions (typing with the caret kept, a redraw while typing, the overrides, a
method switch, the bridge, a reload, reset, the folds, phones) were driven in headless Chrome
(~/Optic/work/classic-parity/b7a_check.py). These tests are not interaction evidence. Ledger:
docs/frontend-v2/CLASSIC-PARITY.md, B7a.
"""
from tests.test_frontend_v2_stage0 import V2, _run

JS = V2 / "js"
DCF = (JS / "pages/dcf.js").read_text()
CLASSIC_VJ = (V2.parent / "valuation.js").read_text()


def test_classics_store_kept_per_symbol(tmp_path):
    got = _run(tmp_path, f"""
      const M = await import('{(JS / "pages/dcf.js").as_posix()}');
      const reads = [];
      for (const raw of [JSON.stringify({{ edits: {{ MSFT: {{ drivers: {{ growth: {{ y1: 0.12 }} }}, wacc: {{}} }} }}, models: [{{ id: 'm1' }}] }}), 'nonsense', '[1]', JSON.stringify({{ edits: 'x', models: 'y' }})]) {{
        localStorage.setItem(M.STORE_KEY, raw); reads.push(M.readStore());
      }}
      localStorage.setItem(M.STORE_KEY, JSON.stringify({{ edits: {{ MSFT: {{ drivers: {{ horizon: 8 }} }} }}, models: [{{ id: 'm1', symbol: 'MSFT' }}] }}));
      M.rememberEdits('AAPL', {{ drivers: {{ growth: {{ y1: 0.25 }} }}, wacc: {{}}, base: {{}}, equity: {{}} }});
      const one = JSON.parse(localStorage.getItem(M.STORE_KEY));
      M.rememberEdits('AAPL', {{ drivers: {{}}, wacc: {{}}, base: {{}}, equity: {{}} }});
      const two = JSON.parse(localStorage.getItem(M.STORE_KEY));
      print(JSON.stringify({{ reads, one, two, any: [M.anyEdits({{ drivers: {{}}, wacc: {{ erp: 0.05 }} }}), M.anyEdits({{ drivers: {{}} }}), M.anyEdits(null)] }}));
    """)
    r = got["reads"]
    assert r[0] == {"edits": {"MSFT": {"drivers": {"growth": {"y1": 0.12}}, "wacc": {}}}, "models": [{"id": "m1"}]}
    assert r[1] == r[2] == r[3] == {"edits": {}, "models": []}, "a bad copy reads as empty, never breaks the page"
    assert got["one"]["edits"]["AAPL"]["drivers"]["growth"]["y1"] == 0.25 and got["one"]["edits"]["MSFT"] == {"drivers": {"horizon": 8}}
    assert got["one"]["models"] == [{"id": "m1", "symbol": "MSFT"}], "saved models are left as they are"
    assert "AAPL" not in got["two"]["edits"] and "MSFT" in got["two"]["edits"], "no edits left: the symbol is forgotten, the rest stays"
    assert got["any"] == [True, False, False]
    assert "const STORE_KEY = 'optic.dcf.v1';" in CLASSIC_VJ


def test_a_box_becomes_an_edit_as_in_classic(tmp_path):
    got = _run(tmp_path, f"""
      const M = await import('{(JS / "pages/dcf.js").as_posix()}');
      const e = {{ drivers: {{}}, wacc: {{}}, base: {{}}, equity: {{}} }};
      const f = (k) => M.fieldOf(k);
      const out = [M.setEdit(e, f('growth.y1'), '25'), M.setEdit(e, f('horizon'), '8'), M.setEdit(e, f('wacc.erp'), '5.5%'), M.setEdit(e, f('wacc.beta_raw'), '1.2x'),
        M.setEdit(e, f('wacc.debt_weight'), ''), M.setEdit(e, f('growth.y2'), 'abc')];
      const snap = JSON.parse(JSON.stringify(e));
      M.setEdit(e, f('growth.y1'), ''); M.setEdit(e, f('horizon'), '');
      print(JSON.stringify({{ out, snap, after: e, shown: [M.shown(f('growth.y1'), 0.1477), M.shown(f('horizon'), 10), M.shown(f('wacc.beta_raw'), 1.23456), M.shown(f('growth.y1'), null)],
        amounts: ['24.4B', '1,200', '3.5m', '-2k', 'abc', ''].map(M.parseAmount), n: M.FIELDS.length, groups: M.GROUPS }}));
    """)
    assert got["out"] == [None, None, None, None, None, "Revenue growth, second year needs a number."]
    s = got["snap"]
    assert s["drivers"] == {"growth": {"y1": 0.25}, "horizon": 8} and s["wacc"] == {"erp": 0.055, "beta_raw": 1.2, "debt_weight": None}, "percent / 100; a blank with a meaning is an explicit null"
    assert got["after"]["drivers"] == {}, "an emptied box is the default again, and an empty group goes"
    assert got["shown"] == ["14.77", "10", "1.235", ""]
    assert got["amounts"] == [24.4e9, 1200, 3.5e6, -2000, None, None]
    assert got["n"] == 25 and got["groups"] == ["Growth", "Profitability", "Reinvestment", "Taxes", "Discount rate", "Cross-check"]
    for label in ("Revenue growth, first year", "Return on new capital after the forecast", "Or set the discount rate directly", "Exit EV/EBITDA (cross-check only)"):
        assert label in CLASSIC_VJ, f"Classic's label: {label}"


def test_the_formats_and_the_methods_side_by_side(tmp_path):
    got = _run(tmp_path, f"""
      const M = await import('{(JS / "pages/dcf.js").as_posix()}');
      const d = {{ scenarios: {{ bear: {{ per_share: 114 }}, base: {{ per_share: 172 }}, bull: {{ per_share: 242 }} }}, fcfe: {{ available: true, per_share: 173, fit: {{ fit: 'supporting' }} }},
        ddm: {{ available: true, per_share: 20.4, fit: {{ fit: 'limited' }} }}, residual_income: {{ available: false }}, reit: {{ available: true, own_history: {{ per_share_low: 40, per_share_mid: 50, per_share_high: 60 }} }} }};
      print(JSON.stringify({{ money: [M.money(339.5), M.money(12.345), M.money(4.567), M.money(-150), M.money(5, 'EUR'), M.money(null)], about: [M.about(171.9), M.about(9.87), M.about(0), M.about(1234)],
        pct: [M.pct(0.1477), M.signedPct(-0.493), M.pts(-0.005, 1)], when: M.priceWhen({{ as_of: '2026-10-21T12:34:00Z' }}),
        rows: M.rangeRows(d, {{ rows: [{{ label: 'Sum of the parts', mid: 180, fit: 'supporting' }}] }}).map((r) => [r.label, r.lo ?? null, r.mid, r.hi ?? null, r.fit]) }}));
    """)
    assert got["money"] == ["$340", "$12.3", "$4.57", "−$150", "5.00 EUR", "n/a"]
    assert got["about"] == ["about $170", "about $9.9", "nothing per share", "about $1,200"], "two significant figures in the sentence"
    assert got["pct"] == ["14.8%", "−49%", "−0.5 pts"]
    assert got["when"].startswith("quote fetched Oct 21, 2026"), "a fetched quote is not called a trade"
    assert got["rows"] == [["DCF, bear to bull", 114, 172, 242, "primary"], ["Equity DCF (FCFE)", None, 173, None, "supporting"], ["Dividend discount", None, 20.4, None, "limited"],
                           ["P/FFO, its own history", 40, 50, 60, "primary"], ["Sum of the parts", None, 180, None, "supporting"]], "never averaged; B7c adds its rows"


def test_the_editor_on_investing():
    inv = (JS / "pages/investing.js").read_text()
    assert "<div data-dcf-slot></div>" in inv and "mountDcf(mainEl, sym);" in inv and "valuation: dcfContext()," in inv
    assert "Edit the model in the classic app" not in inv and "/api/valuation/${enc}`" not in inv, "the editor loads the model itself, with the reader's edits"
    assert "slot.replaceWith(V.node)" in DCF and "runNow().then(() => paintResults())" in DCF, "one node for the visit; typing repaints the results only"
    assert "api.post(`/api/valuation/${encodeURIComponent(sym)}/run`" in DCF and "/api/chat" not in DCF
    assert "A model-implied value under stated assumptions. It is not a price target, a forecast Optic stands behind, or a signal to buy or sell." in DCF
