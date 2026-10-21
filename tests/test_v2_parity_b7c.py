"""Classic parity, batch B7c (2026-10-21): the fair-value model's other methods (FCFE, the dividend model, residual
income, a REIT's FFO, peers' multiples and the sum of the parts) and the equity models' form. The pure rules run in
JavaScriptCore: the equity models' fields and their edits, and how peers and the parts join the methods side by side.
Which methods suit, peers (Optic's and the reader's), the segments with the reader's multiples, the dividend model's
form, a bank and a REIT were driven in headless Chrome (~/Optic/work/classic-parity/b7c_check.py). These tests are not
interaction evidence. Ledger: docs/frontend-v2/CLASSIC-PARITY.md, B7c.
"""
from tests.test_frontend_v2_stage0 import V2, _run

JS = V2 / "js"
DCF = (JS / "pages/dcf.js").read_text()
CLASSIC_VJ = (V2.parent / "valuation.js").read_text()


def test_the_equity_models_form(tmp_path):
    got = _run(tmp_path, f"""
      const M = await import('{(JS / "pages/dcf.js").as_posix()}');
      const e = {{ drivers: {{}}, wacc: {{}}, base: {{}}, equity: {{}} }};
      const f = (k) => M.fieldOf(k);
      M.setEdit(e, f('ri.roe_start'), '14'); M.setEdit(e, f('ddm.years_high'), '7'); M.setEdit(e, f('reit.p_ffo'), '18x');
      const one = JSON.parse(JSON.stringify(e.equity));
      M.setEdit(e, f('ri.roe_start'), ''); M.setEdit(e, f('ddm.years_high'), ''); M.setEdit(e, f('reit.p_ffo'), '');
      const d = {{ residual_income: {{ available: true, roe_start: 0.15, defaults: {{ roe_start: 0.12 }} }}, reit: {{ available: true, own_history: {{ median: 16.2 }}, at_multiple: {{ multiple: 18 }} }}, ddm: {{ available: false }} }};
      print(JSON.stringify({{ one, after: e.equity, v: [M.eqValue(d, f('ri.roe_start'), 'current'), M.eqValue(d, f('ri.roe_start'), 'default'), M.eqValue(d, f('reit.p_ffo'), 'default'), M.eqValue(d, f('reit.p_ffo'), 'current'), M.eqValue(d, f('ddm.growth_high'), 'default')],
        labels: M.EQ_FIELDS.map((x) => x.label) }}));
    """)
    assert got["one"] == {"ri": {"roe_start": 0.14}, "ddm": {"years_high": 7}, "reit": {"p_ffo": 18}}, "kept in edits.equity, by the model's own key"
    assert got["after"] == {}, "emptied boxes are the defaults again"
    assert got["v"] == [0.15, 0.12, 16.2, 18, None], "a REIT's default multiple is its own median; an unavailable model has none"
    for label in got["labels"]:
        assert label in CLASSIC_VJ, label


def test_peers_and_the_parts_join_the_methods(tmp_path):
    got = _run(tmp_path, f"""
      const M = await import('{(JS / "pages/dcf.js").as_posix()}');
      const comps = {{ available: true, implied: [
        {{ key: 'ev_ebitda', label: 'EV / EBITDA', implied: {{ low: {{ per_share: 140 }}, mid: {{ per_share: 160 }}, high: {{ per_share: 190 }} }} }},
        {{ key: 'pb', label: 'Price / book', implied: {{ low: {{ per_share: 20 }}, mid: {{ per_share: 30 }}, high: {{ per_share: 40 }} }} }},
        {{ key: 'pe', label: 'Price / earnings', wide: true, implied: {{ low: {{ per_share: 50 }}, mid: {{ per_share: 150 }}, high: {{ per_share: 400 }} }} }},
        {{ key: 'ev_rev', label: 'EV / revenue', implied: null }}] }};
      print(JSON.stringify({{ rows: M.extraRowsOf(comps, {{ available: true, per_share: 180 }}), none: M.extraRowsOf({{ available: false }}, {{ loading: true }}) }}));
    """)
    assert got["rows"] == [{"label": "Peers' EV / EBITDA", "lo": 140, "mid": 160, "hi": 190, "fit": "supporting"}, {"label": "Sum of the parts", "mid": 180, "fit": "supporting"}], "not price to book, not a spread too wide to read"
    assert got["none"] == []
    assert "c.implied && c.key !== 'pb' && !c.wide" in CLASSIC_VJ


def test_the_methods_on_the_page():
    assert "fold('methods', 'Other valuation methods and when each fits', methodsHTML(d))" in DCF
    assert "api.get(`/api/valuation/${encodeURIComponent(sym)}/comps" in DCF and "api.post(`/api/valuation/${encodeURIComponent(sym)}/sotp`, body" in DCF
    assert "if (t.matches('[data-dcf-peers]')) { V.peers = t.value; return; }" in DCF, "typed peers are kept, so a rerun's repaint puts them back"
    assert "if (!dcf.available && V.open.methods === undefined) V.open.methods = true;" in DCF, "when the cash-flow model does not suit, the methods open"
