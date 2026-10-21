"""Classic parity, batch B7d (2026-10-21): Milo's proposal card for the fair-value model. The pure rules run in
JavaScriptCore: how a proposal's KEY=VALUE pairs are read (Classic's parseAction), how a change lands in the working
edits, and what Milo is told about the model. Show the effect, Apply, Undo, the refusals and the phone fit were driven
in headless Chrome against the STAND-IN model (~/Optic/work/classic-parity/b7d_check.py): stand-in verification, not a
real-model run. These tests are not interaction evidence. Ledger: docs/frontend-v2/CLASSIC-PARITY.md, B7d.
"""
import re

from tests.test_frontend_v2_stage0 import V2, _run

JS = V2 / "js"
CLASSIC_VJ = (V2.parent / "valuation.js").read_text()
MILO = (JS / "ui/milo.js").read_text()
DCF = (JS / "pages/dcf.js").read_text()


def test_a_proposal_is_read_as_classic_reads_it(tmp_path):
    got = _run(tmp_path, f"""
      const M = await import('{(JS / "core/milo-text.js").as_posix()}');
      const a = (xs) => M.valuationAction(xs);
      print(JSON.stringify({{
        pct: a(['growth.y1=20%', 'capex_pct.target=4', 'margin.target=0.31', 'wacc.beta_raw=1.1x', 'horizon=8', 'Because the guide was raised.']),
        bad: a(['magic.factor=12%', 'A reason here.']), nan: a(['growth.y1=.', 'A reason here.']), noWhy: a(['growth.y1=20%', 'ok']),
        open: a(['Look at the model']), none: a([]) }}));
    """)
    p = got["pct"]
    assert [(c["key"], c["value"]) for c in p["changes"]] == [("growth.y1", 0.2), ("capex_pct.target", 0.04), ("margin.target", 0.31), ("wacc.beta_raw", 1.1), ("horizon", 8)], \
        "20% and 20 are both 0.2; 0.31 is already a fraction; a beta and a year count are taken as they are"
    assert p["propose"] is True and p["why"] == "Because the guide was raised."
    assert p["label"] == "Try on the model on screen: Revenue growth, first year 20.0%, Capex it settles at 4.0%, Operating margin it settles at 31.0%, Beta (raw, before adjustment) 1.1, Forecast years 8"
    assert got["bad"] == {"bad": 'the model has no "magic.factor" assumption'}
    assert got["nan"] == {"bad": "growth.y1 is not a number"}
    assert got["noWhy"] == {"bad": "a proposed change needs its reason"}
    assert got["open"]["label"] == "Open the valuation model" and "propose" not in got["open"] and got["none"]["label"] == "Open the valuation model", \
        "with no pair it is v2's earlier link to the model, not a proposal"
    # Classic's rules, word for word: the pattern, every field proposable, the percent reading, the 240-character reason
    assert r"/^([a-z_]+(?:\.[a-z_0-9]+)?)=(-?[0-9.]+)(%|x)?$/i" in CLASSIC_VJ and "const PROPOSABLE = new Set(FIELDS.map((f) => f.key));" in CLASSIC_VJ
    assert "(c.unit === '%' || Math.abs(c.value) > 1.5 ? c.value / 100 : c.value)" in CLASSIC_VJ and "words.join(' ').trim().slice(0, 240)" in CLASSIC_VJ


def test_the_fields_are_classics(tmp_path):
    got = _run(tmp_path, f"""
      const F = await import('{(JS / "core/dcf-fields.js").as_posix()}');
      const D = await import('{(JS / "pages/dcf.js").as_posix()}');
      print(JSON.stringify({{ keys: F.FIELDS.map((f) => f.key), same: D.FIELDS === F.FIELDS }}));
    """)
    classic = re.findall(r"\{ group: '[^']+', key: '([^']+)'", CLASSIC_VJ)
    assert got["keys"] == classic and got["same"], "one list, shared by the editor and the card, Classic's keys in Classic's order"


def test_a_change_lands_in_the_working_edits_only(tmp_path):
    got = _run(tmp_path, f"""
      const M = await import('{(JS / "pages/dcf.js").as_posix()}');
      const before = {{ drivers: {{ growth: {{ y2: 0.1 }} }}, wacc: {{ erp: 0.05 }}, base: {{ revenue: 1 }}, equity: {{ ri: {{ roe_start: 0.14 }} }} }};
      const keep = JSON.stringify(before);
      const after = M.withChanges(before, [{{ key: 'growth.y1', value: 0.2 }}, {{ key: 'horizon', value: 8 }}, {{ key: 'wacc.beta_raw', value: 1.1 }}, {{ key: 'ri.roe_start', value: 0.2 }}, {{ key: 'nope', value: 1 }}]);
      print(JSON.stringify({{ after, untouched: JSON.stringify(before) === keep, fromNothing: M.withChanges(null, [{{ key: 'tax.start', value: 0.21 }}]) }}));
    """)
    assert got["after"] == {"drivers": {"growth": {"y2": 0.1, "y1": 0.2}, "horizon": 8}, "wacc": {"erp": 0.05, "beta_raw": 1.1}, "base": {"revenue": 1}, "equity": {"ri": {"roe_start": 0.14}}}, \
        "a nested driver, a flat one and a discount-rate part; the equity models and unknown keys are not proposable"
    assert got["untouched"], "a copy: Show the effect runs on it and the edits on screen stay as they were"
    assert got["fromNothing"]["drivers"] == {"tax": {"start": 0.21}}


def test_what_milo_is_told_about_the_model(tmp_path):
    got = _run(tmp_path, f"""
      const M = await import('{(JS / "pages/dcf.js").as_posix()}');
      const d = {{ available: true, ticker: 'AAPL', name: 'Apple', model_version: 'v9', market: {{ price: 339.5, as_of: '2026-10-21T13:00:00Z' }},
        defaults: {{ rationale: [{{ key: 'growth.y1', kind: 'estimate', why: 'Analysts expect 6%.' }}] }},
        assumptions: {{ changed: ['growth.y1'], drivers: {{ growth: {{ y1: 0.123456 }} }}, wacc: {{ erp: 0.05 }} }},
        dcf: {{ available: true, per_share: 172.456, upside: -0.4921, terminal_share: 0.61, wacc: {{ wacc: 0.0912 }}, rows: [] }},
        tornado: [{{ label: 'Growth', step_low: -0.02, value_low: 150, step_high: 0.02, value_high: 195 }}],
        reverse: {{ solves: [{{ label: 'First-year growth', value: 0.31, text: 'The price implies 31%.', held: 'the rest' }}] }},
        ddm: {{ available: false, reason: 'No dividend.' }}, inputs: {{ fy_ends: ['2025-09-27'], balance_date: '2026-06-28' }} }};
      const sotp = {{ available: true, per_share: 180, segments: [{{ name: 'Services', operating_income: 9e10, multiple: 22, value: 2e12 }}] }};
      print(JSON.stringify({{ c: M.contextOf(d, 'AAPL', {{ available: false }}, sotp), off: M.contextOf({{ available: false, reason: 'A bank.' }}, 'JPM'), none: M.contextOf(null, 'X') }}));
    """)
    c = got["c"]
    g = next(a for a in c["assumptions"] if a["key"] == "growth.y1")
    assert g == {"key": "growth.y1", "label": "Revenue growth, first year", "value": 0.1235, "unit": "fraction", "kind": "estimate", "why": "Analysts expect 6%.", "edited_by_reader": True}, \
        "rounded to four places, its source and reason, and that the reader changed it (no default in this payload)"
    assert c["what"].startswith("Optic fair-value model") and "not by Milo" in c["what"]
    assert c["base_case"]["value_per_share"] == 172.46 and c["base_case"]["upside_vs_price"] == -0.4921 and c["base_case"]["discount_rate"]["wacc"] == 0.0912
    assert c["most_sensitive"] == [{"assumption": "Growth", "step_down": -0.02, "value_down": 150, "step_up": 0.02, "value_up": 195}]
    assert c["reverse_dcf"][0]["solved_for"] == "First-year growth" and c["ddm"] == {"available": False, "reason": "No dividend."}
    assert c["sum_of_the_parts"]["value_per_share"] == 180 and "peers" not in c, "peers only when Optic found them"
    assert got["off"] == {"ticker": "JPM", "available": False, "reason": "A bank."} and got["none"] is None
    for key in ("base_case", "forecast", "bridge", "shares", "scenarios", "most_sensitive", "what_ifs", "reverse_dcf", "history", "sources", "trailing_twelve_months", "dcf_not_run", "reit"):
        assert f"out.{key} =" in CLASSIC_VJ and f"out.{key} =" in DCF, key


def test_the_card_on_the_page():
    assert "if (!VALUATION || !VALUATION.ready())" in MILO and "VALUATION.sym() !== asked" in MILO, "it refuses with no model on screen, or another company's"
    assert "btn.textContent = 'Applied';" in MILO and "ap.textContent = 'Apply to my working model'; ap.disabled = false; ap.focus();" in MILO
    assert "registerValuation(VAL_API)" in DCF and "unregisterValuation(VAL_API)" in DCF
    assert "async apply(changes) { const prev = JSON.parse(JSON.stringify(editsFor())); V.edits = withChanges(prev, changes);" in DCF, \
        "Apply keeps what was there for Undo and changes the working edits; saved models are not touched"
