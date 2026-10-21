"""Classic parity, batch B7b (2026-10-21): saved fair-value models. The pure rules run in JavaScriptCore: what a snapshot
keeps, a guest's model kept in Classic's optic.dcf.v1 `models` (newest first, 40 at most, the edits left alone), and a
saved model compared with the one on screen. Saving, the list, rerunning exactly, comparing, using and deleting were
driven in headless Chrome as a guest and on the local account (~/Optic/work/classic-parity/b7b_check.py). These tests
are not interaction evidence. Ledger: docs/frontend-v2/CLASSIC-PARITY.md, B7b.
"""
from tests.test_frontend_v2_stage0 import V2, _run

JS = V2 / "js"
DCF = (JS / "pages/dcf.js").read_text()
CLASSIC_VJ = (V2.parent / "valuation.js").read_text()
D = """{ base: { revenue: 1 }, model_version: 'v9', inputs_digest: { balance_date: '2026-06-28', price: 339.5 },
  assumptions: { changed: ['growth.y1'], drivers: { growth: { y1: 0.3 }, horizon: 10 }, wacc: { erp: 0.05 } },
  dcf: { per_share: 194, terminal_share: 0.55, wacc: { wacc: 0.09 } }, scenarios: { bear: { per_share: 120 }, bull: { per_share: 260 } } }"""


def test_a_snapshot_and_a_guests_models_in_classics_format(tmp_path):
    got = _run(tmp_path, f"""
      const M = await import('{(JS / "pages/dcf.js").as_posix()}');
      const d = {D};
      const snap = M.snapshotOf('AAPL', d, 'Mine', {{ capex: 24.4e9 }});
      localStorage.setItem(M.STORE_KEY, JSON.stringify({{ edits: {{ AAPL: {{ drivers: {{ horizon: 8 }} }} }}, models: Array.from({{ length: 40 }}, (_, i) => ({{ id: 'local-' + i, symbol: 'MSFT' }})) }}));
      const kept = M.keepLocalModel(snap, new Date('2026-10-21T13:00:00Z'));
      const st = JSON.parse(localStorage.getItem(M.STORE_KEY));
      print(JSON.stringify({{ snap, kept, n: st.models.length, first: st.models[0].id, last: st.models[39].id, edits: st.edits, max: M.MAX_LOCAL_MODELS }}));
    """)
    s = got["snap"]
    assert s == {"symbol": "AAPL", "name": "Mine", "base": {"revenue": 1}, "assumptions": {"changed": ["growth.y1"], "drivers": {"growth": {"y1": 0.3}, "horizon": 10}, "wacc": {"erp": 0.05}},
                 "model_version": "v9", "inputs": {"balance_date": "2026-06-28", "price": 339.5, "supplied": {"capex": 24.4e9}},
                 "result": {"per_share": 194, "wacc": 0.09, "terminal_share": 0.55, "bear": 120, "bull": 260}}, "the reported figures, the assumptions and the result together"
    k = got["kept"]
    assert k["id"] == "local-1792587600000" and k["created_at"] == "2026-10-21T13:00:00.000Z" and k["changed"] == ["growth.y1"] and k["snapshot"] == s
    assert got["n"] == 40 and got["first"] == k["id"] and got["last"] == "local-38", "newest first, the oldest dropped past 40"
    assert got["edits"] == {"AAPL": {"drivers": {"horizon": 8}}}, "the edits are left alone"
    assert "id: `local-${Date.now()}`, created_at: new Date().toISOString()," in CLASSIC_VJ and "const MAX_LOCAL_MODELS = 40;" in CLASSIC_VJ


def test_a_saved_model_against_the_one_on_screen(tmp_path):
    got = _run(tmp_path, f"""
      const M = await import('{(JS / "pages/dcf.js").as_posix()}');
      const now = {{ assumptions: {{ drivers: {{ growth: {{ y1: 0.1477 }}, horizon: 10 }}, wacc: {{ erp: 0.05, debt_weight: null }} }}, inputs_digest: {{ balance_date: '2026-09-27', price: 340 }}, dcf: {{ per_share: 172 }} }};
      const m = {{ snapshot: {{ assumptions: {{ drivers: {{ growth: {{ y1: 0.3 }}, horizon: 10 }}, wacc: {{ erp: 0.05 }} }}, inputs: {{ balance_date: '2026-06-28', price: 339.5 }}, result: {{ per_share: 194 }} }} }};
      print(JSON.stringify(M.compareModel(m, now)));
    """)
    assert got["rows"] == [{"label": "Revenue growth, first year", "saved": "30.00%", "now": "14.77%"}], "only what differs; a blank and a missing value are the same"
    assert got["notes"] == ["Newer filings since then: balance sheet Jun 28, 2026 then, Sep 27, 2026 now.", "Price $339.50 then, $340.00 now."] and got["savedValue"] == 194 and got["nowValue"] == 172


def test_saved_models_on_the_page():
    assert "await api.post('/api/valuation-models', snap)" in DCF and "api.post('/api/valuation-models/replay', m.snapshot)" in DCF
    assert "api.del(`/api/valuation-models/${encodeURIComponent(id)}`)" in DCF
    assert "Delete this saved model? This cannot be undone." in DCF and "window.confirm" not in DCF, "asked in the page, as v2's other deletes are, not with the browser's dialog"
    assert "function paintSaved(" in DCF and "draw(host, savedHTML(V.data));" in DCF, "only the fold repaints, so a box being typed in is left alone"
