"""The fair-value workspace in the page (static/valuation.js), under JavaScriptCore.

The page computes nothing: these tests check that it parses, that Milo's
proposals are checked before they become cards, that the context Milo gets is
the server's numbers, that headline figures are rounded, and that app.js's
hooks are in place.
"""

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc"
APP = (ROOT / "static/app.js").read_text(encoding="utf-8")
VJS = (ROOT / "static/valuation.js").read_text(encoding="utf-8")

SAMPLE = {
    "available": True, "model_version": "dcf-1.0", "ticker": "SYN", "name": "Synthetic Co",
    "market": {"price": 20.0, "as_of": "2026-10-13T20:00:00+00:00", "currency": "USD"},
    "classification": {"label": "Operating company", "confidence": "normal", "primary": "dcf",
                       "models": {"dcf": {"fit": "primary", "why": "fits", "name": "DCF"}}},
    "inputs": {"fy_ends": ["2025-12-31"], "balance_date": "2026-06-30", "shares": {"method": "cover"}},
    "inputs_digest": {"balance_date": "2026-06-30"},
    "defaults": {"drivers": {"growth": {"y1": 0.05, "y2": None}, "margin": {"start": 0.2, "target": 0.2, "years": 5},
                             "capex_pct": {"start": 0.06, "target": 0.06, "years": 5}, "terminal": {"growth": 0.025, "ronic": 0.1},
                             "tax": {"start": 0.2, "terminal": 0.22}, "horizon": 10, "nwc_pct": 0.1, "dep_rate": 0.1},
                 "wacc": {"risk_free": 0.04, "erp": 0.0423, "beta_raw": 1.0},
                 "rationale": [{"key": "margin.target", "kind": "history", "why": "Three-year average."}]},
    "assumptions": {"drivers": {"growth": {"y1": 0.05, "y2": None}, "margin": {"start": 0.2, "target": 0.25, "years": 5},
                                "capex_pct": {"start": 0.06, "target": 0.06, "years": 5}, "terminal": {"growth": 0.025, "ronic": 0.1},
                                "tax": {"start": 0.2, "terminal": 0.22}, "horizon": 10, "nwc_pct": 0.1, "dep_rate": 0.1},
                    "wacc": {"risk_free": 0.04, "erp": 0.0423, "beta_raw": 1.0}, "changed": ["margin.target"]},
    "dcf": {"available": True, "per_share": 23.4567, "upside": 0.1728, "margin_of_safety": 0.147, "terminal_share": 0.61,
            "enterprise_value": 2.4e9, "equity_value": 2.3e9, "shares": 1e8, "rows": [{"year": 1}],
            "terminal": {"method": "value_driver", "growth": 0.025, "ronic": 0.1, "pv": 1.4e9},
            "wacc": {"wacc": 0.085}, "checks": [], "bridge": {"lines": []}},
    "scenarios": {"bear": {"per_share": 15.0}, "base": {"per_share": 23.4567}, "bull": {"per_share": 33.0}},
    "tornado": [{"label": "Discount rate", "step_low": -0.01, "value_low": 30.0, "step_high": 0.01, "value_high": 19.0}],
    "what_ifs": [{"label": "Capex stays", "per_share": 21.0, "change": -0.105}],
    "reverse": {"solves": [{"label": "Revenue growth", "value": 0.08, "text": "t", "held": "h"}]},
}


def _run(script):
    exe = JSC if os.path.exists(JSC) else shutil.which("jsc")
    if not exe:
        pytest.skip("no JavaScriptCore on this machine")
    src = """
      load('tests/support/browser_stubs.js');
      document.documentElement.style = document.documentElement.style || {};
      document.documentElement.style.setProperty = function () {};
      document.documentElement.style.removeProperty = function () {};
      try { load('static/charts.js'); load('static/app.js'); } catch (e) { }
      try { load('static/valuation.js'); } catch (e) { print('LOADFAIL:' + e + ' ' + e.stack); }
      var R = {};
      var V = window.OpticValuation;
      STATE.ticker = 'SYN';
      V._state.data.SYN = %s;
    """ % json.dumps(SAMPLE) + script + "\nprint('RESULT:' + JSON.stringify(R));"
    out = subprocess.run([exe, "-e", src], capture_output=True, text=True, timeout=120, cwd=str(ROOT))
    blob = out.stdout + out.stderr
    assert "LOADFAIL" not in blob, blob[-2000:]
    assert "RESULT:" in blob, blob[-2000:]
    return json.loads(blob.split("RESULT:", 1)[1].split("\n")[0])


def test_the_workspace_loads_and_exposes_its_hooks():
    out = _run("R.keys = Object.keys(V).sort();")
    assert {"hostHTML", "load", "context", "parseAction", "actionCard"} <= set(out["keys"])


def test_milo_proposals_are_checked_before_they_become_cards():
    out = _run("""
      R.ok = V.parseAction(['capex_pct.target=30%', 'margin.target=0.4', '"AI', 'capex', 'stays', 'high"']);
      R.unknown = V.parseAction(['price_target=900', 'because']);
      R.noreason = V.parseAction(['capex_pct.target=30%']);
      R.nothing = V.parseAction(['just', 'words', 'here']);
      R.card = V.actionCard(R.ok);
    """)
    ok = out["ok"]
    assert ok["kind"] == "valuation" and ok["sym"] == "SYN"
    assert [c["key"] for c in ok["changes"]] == ["capex_pct.target", "margin.target"]
    assert ok["changes"][0]["value"] == pytest.approx(0.30) and ok["changes"][1]["value"] == pytest.approx(0.40)
    assert "price_target" in out["unknown"]["bad"]
    assert "reason" in out["noreason"]["bad"]
    assert "no assumption" in out["nothing"]["bad"]
    card = out["card"]
    assert "data-milo-val-preview" in card and "disabled" in card
    assert "saved models are never changed" in card


def test_the_milo_context_is_the_servers_numbers_with_their_kinds():
    out = _run("R.ctx = V.context('SYN');")["ctx"]
    assert out["base_case"]["value_per_share"] == 23.46
    assert out["base_case"]["terminal_value_share_of_ev"] == 0.61
    m = next(a for a in out["assumptions"] if a["key"] == "margin.target")
    assert m["value"] == 0.25 and m["default"] == 0.2 and m["kind"] == "history" and m["edited_by_reader"]
    assert out["what_ifs"][0]["value_per_share"] == 21.0
    assert out["reverse_dcf"][0]["held_fixed"] == "h"
    assert "Deterministic" in out["what"]


def test_the_headline_rounds_and_says_it_is_not_a_target():
    out = _run("R.lede = V._lede(V._state.data.SYN);")["lede"]
    assert "about $23" in out and "23.4567" not in out
    assert "Under these assumptions, this model estimates" in out


@pytest.fixture()
def real_payload(monkeypatch):
    """A full server answer, from the service tests' synthetic filings."""
    from tests.test_valuation_service import Provider, company_blob
    from app.valuation import inputs, service
    blob = company_blob()
    monkeypatch.setattr(inputs, "load_filings", lambda t, force=False: (
        inputs.Filings(blob, "0000000009", "2026-10-01T00:00:00+00:00"), "0000000009", None))
    monkeypatch.setattr(inputs, "submissions", lambda cik: {"sic": "3560"})
    monkeypatch.setattr(inputs, "risk_free", lambda p: {"value": 0.04, "as_of": "2026-10-10", "kind": "reported",
                                                       "source": "test"})
    monkeypatch.setattr(service, "_CACHE", {})
    return service.clean(service.build(Provider(), "SYN"))


def test_every_section_renders_from_a_real_answer(real_payload):
    out = _run("""
      V._state.data.SYN = %s;
      V._state.defaults.SYN = V._state.data.SYN;
      V._state.open = {forecast: true, wacc: true, bridge: true, statements: true, methods: true, sources: true, formulas: true, form: true};
      R.html = V.hostHTML();
    """ % json.dumps(real_payload))
    html = out["html"]
    for needle in ("What moves the value most", "Scenarios and other methods, side by side",
                   "What today's price implies", "Sensitivity", "Bear, base and bull",
                   "The forecast, year by year", "How the discount rate is built",
                   "From enterprise value to a value per share", "Assets equal liabilities plus equity",
                   "Free cash flow from these statements equals the DCF", "data-dcf-field=\"capex_pct.target\"",
                   "Save a snapshot", "not a price target", "Operating leases"):
        assert needle in html, needle
    assert "undefined" not in html and "NaN" not in html


def test_app_js_hooks_the_workspace_in():
    assert '<div id="dcf-host" class="span-all">' in APP
    assert "window.OpticValuation.load()" in APP
    assert "ctx.valuation = v;" in APP
    assert "if (kind === 'valuation')" in APP
    assert "valuation: ['Fair-value model', 'long']" in APP
    assert "'optic.dcf.v1'" in APP[APP.index("const PERSONAL_KEYS = ["):APP.index("];", APP.index("const PERSONAL_KEYS = ["))]
    html = (ROOT / "static/index.html").read_text(encoding="utf-8")
    assert html.index('src="app.js') < html.index('src="valuation.js')


def test_the_page_does_no_valuation_arithmetic():
    """The engine computes; the page formats. No discounting or growth
    compounding may appear in the page's code."""
    assert "Math.pow" not in VJS and "**" not in VJS.replace("/**", "").replace("**/", "")


def test_a_bank_shows_the_method_that_fits_and_its_sensitivity(monkeypatch):
    from tests.test_valuation_service import Provider, company_blob
    from app.valuation import inputs, service
    blob = company_blob("bank")
    monkeypatch.setattr(inputs, "load_filings", lambda t, force=False: (
        inputs.Filings(blob, "0000000009", "2026-10-01T00:00:00+00:00"), "0000000009", None))
    monkeypatch.setattr(inputs, "submissions", lambda cik: {"sic": "6022"})
    monkeypatch.setattr(inputs, "risk_free", lambda p: {"value": 0.04, "as_of": "2026-10-10", "kind": "reported",
                                                       "source": "test"})
    monkeypatch.setattr(service, "_CACHE", {})
    payload = service.clean(service.build(Provider(industry="Banks - Regional"), "BNK"))
    out = _run("""
      STATE.ticker = 'BNK';
      V._state.data.BNK = %s;
      R.html = V.hostHTML();
    """ % json.dumps(payload))
    html = out["html"]
    assert "does not suit" in html and "residual income" in html
    assert "The methods that fit, side by side" in html and "Starting return on equity" in html
    assert "capital spending" not in html and "return on equity does BNK" in html
    assert 'data-dcf-field="ri.roe_start"' in html and "Cost of equity</legend>" in html
    assert 'data-dcf-field="wacc.beta_raw"' in html and "Residual income, bear to bull" in html
    assert "undefined" not in html and "NaN" not in html


def test_amounts_accept_suffixes():
    out = _run("R.v = [V._parseAmount('24.4B'), V._parseAmount('1,250m'), V._parseAmount('7000'), V._parseAmount('lots')];")
    assert out["v"] == [24.4e9, 1.25e9, 7000, None]


def test_a_saved_model_is_compared_field_by_field(real_payload):
    saved = json.loads(json.dumps(real_payload))
    saved["assumptions"]["drivers"]["capex_pct"]["target"] = 0.30
    snap = {"snapshot": {"assumptions": saved["assumptions"], "result": {"per_share": 12.0},
                         "inputs": dict(saved["inputs_digest"], price=15.0)}}
    out = _run("""
      V._state.data.SYN = %s;
      R.c = V._compareModel(%s, V._state.data.SYN);
    """ % (json.dumps(real_payload), json.dumps(snap)))["c"]
    assert [r["label"] for r in out["rows"]] == ["Capex it settles at"]
    assert out["rows"][0]["saved"] == "30.00%" and out["savedValue"] == 12.0
    assert any("Price $15.0 then" in n for n in out["notes"])
