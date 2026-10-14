"""The assembled workspace, its routes, and saved models, on synthetic filings."""

import copy

import pytest
from fastapi.testclient import TestClient

from app import main
from app.auth import config
from app.valuation import defaults, engine, inputs, service

YEARS = ["2022-12-31", "2023-12-31", "2024-12-31", "2025-12-31"]


def _flow(val, end, filed=None):
    start = "{}-01-01".format(end[:4])
    return {"val": val, "start": start, "end": end, "form": "10-K", "fp": "FY", "fy": int(end[:4]),
            "filed": filed or "{}-02-15".format(int(end[:4]) + 1), "accn": "0000000009-{}-000001".format(end[2:4])}


def _inst(val, end, form="10-K"):
    return {"val": val, "end": end, "form": form, "fp": "FY" if form == "10-K" else "Q2",
            "fy": int(end[:4]), "filed": "{}-02-15".format(int(end[:4]) + 1) if form == "10-K" else "2026-08-01",
            "accn": "0000000009-26-000002"}


def company_blob(kind="operating", rev=(800.0, 880.0, 950.0, 1000.0), margin=0.20):
    g = {}

    def flows(tag, values, unit="USD"):
        g[tag] = {"units": {unit: [_flow(v, e) for v, e in zip(values, YEARS)]}}

    def insts(tag, values, q=None, unit="USD"):
        rows = [_inst(v, e) for v, e in zip(values, YEARS)]
        if q is not None:
            rows.append(_inst(q, "2026-06-30", form="10-Q"))
        g[tag] = {"units": {unit: rows}}

    flows("Revenues", rev)
    if kind != "bank":
        flows("OperatingIncomeLoss", [r * margin for r in rev])
        flows("PaymentsToAcquirePropertyPlantAndEquipment", [r * 0.06 for r in rev])
        flows("DepreciationDepletionAndAmortization", [r * 0.05 for r in rev])
        insts("AssetsCurrent", [300.0, 320, 340, 360], q=370)
        insts("LiabilitiesCurrent", [200.0, 210, 220, 230], q=235)
        insts("PropertyPlantAndEquipmentNet", [400.0, 420, 440, 460], q=465)
    flows("IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
          [r * margin * 0.95 for r in rev])
    flows("IncomeTaxExpenseBenefit", [r * margin * 0.95 * 0.2 for r in rev])
    flows("NetIncomeLoss", [r * margin * 0.95 * 0.8 for r in rev])
    flows("InterestExpense", [8.0, 8, 8, 8])
    flows("PaymentsOfDividends", [40.0, 44, 48, 52])
    flows("PaymentsForRepurchaseOfCommonStock", [10.0, 10, 10, 10])
    flows("CommonStockDividendsPerShareDeclared", [0.40, 0.44, 0.48, 0.52], unit="USD/shares")
    flows("WeightedAverageNumberOfDilutedSharesOutstanding", [101.0, 101, 101, 101], unit="shares")
    flows("WeightedAverageNumberOfSharesOutstandingBasic", [100.0, 100, 100, 100], unit="shares")
    insts("CashAndCashEquivalentsAtCarryingValue", [50.0, 55, 60, 65], q=70)
    insts("LongTermDebt", [150.0, 150, 150, 150], q=150)
    insts("StockholdersEquity", [600.0, 640, 680, 720], q=730)
    insts("Assets", [1100.0, 1150, 1200, 1250], q=1260)
    insts("Liabilities", [500.0, 510, 520, 530], q=530)
    dei = {"EntityCommonStockSharesOutstanding": {"units": {"shares": [
        {"val": 100.0, "end": "2026-07-25", "form": "10-Q", "filed": "2026-08-01", "accn": "0000000009-26-000002"}]}}}
    return {"entityName": "Synthetic Co", "facts": {"us-gaap": g, "dei": dei}}


class Provider:
    def __init__(self, industry="Specialty Industrial Machinery", beta=1.0, price=20.0):
        self.industry, self.beta, self.price = industry, beta, price

    def quote(self, t):
        return {"price": self.price, "as_of": "2026-10-13T20:00:00+00:00", "currency": "USD",
                "market_cap": self.price * 100.0, "beta": self.beta, "quote_type": "EQUITY",
                "industry": self.industry, "sector": "Industrials", "financial_currency": "USD"}

    def short_interest(self, t):
        return {"shares_outstanding": 100.0}

    def estimates(self, t):
        return {}

    def history(self, *a, **k):
        raise RuntimeError("no history in tests")


@pytest.fixture()
def synthetic(monkeypatch):
    holder = {"blob": company_blob(), "sic": "3560"}
    monkeypatch.setattr(inputs, "load_filings",
                        lambda t, force=False: (inputs.Filings(holder["blob"], "0000000009", "2026-10-01T00:00:00+00:00"),
                                                "0000000009", None))
    monkeypatch.setattr(inputs, "submissions", lambda cik: {"sic": holder["sic"], "sic_description": "Test"})
    monkeypatch.setattr(inputs, "risk_free", lambda p: {"value": 0.04, "as_of": "2026-10-10", "kind": "reported",
                                                       "source": "test"})
    monkeypatch.setattr(service, "_CACHE", {})
    return holder


def test_the_workspace_builds_from_reported_figures(synthetic):
    out = service.build(Provider(), "SYN")
    assert out["available"] and out["dcf"]["available"]
    assert out["classification"]["primary"] == "dcf"
    assert out["inputs"]["balance_date"] == "2026-06-30"
    assert out["dcf"]["timing"]["stub_fraction"] == pytest.approx(184 / 365)
    # Bridge at the 10-Q date, not the year end.
    assert out["base"]["bridge"]["cash"] == 70.0
    # Each default carries a reason and a kind.
    kinds = {r["key"]: r["kind"] for r in out["defaults"]["rationale"]}
    assert kinds["margin.start"] == "reported" and kinds["tax.terminal"] == "assumption"
    assert kinds["growth.y1"] == "history"


def test_scenarios_are_ordered_and_symmetric_around_the_base(synthetic):
    out = service.build(Provider(), "SYN")
    s = out["scenarios"]
    assert s["bear"]["per_share"] < s["base"]["per_share"] < s["bull"]["per_share"]
    assert s["base"]["per_share"] == pytest.approx(out["dcf"]["per_share"])
    assert s["bear"]["deltas"]["margin_target"] == pytest.approx(-s["bull"]["deltas"]["margin_target"])
    assert s["bear"]["deltas"]["growth"] == pytest.approx(-s["bull"]["deltas"]["growth"])


def test_edits_are_merged_range_checked_and_reported(synthetic):
    out = service.build(Provider(), "SYN", edits={"drivers": {"margin": {"target": 0.25}, "junk": 1},
                                                  "wacc": {"erp": 0.05}})
    assert out["assumptions"]["changed"] == ["margin.target", "wacc.erp"]
    assert out["assumptions"]["drivers"]["margin"]["target"] == 0.25
    bad = service.build(Provider(), "SYN", edits={"drivers": {"terminal": {"growth": 0.5}}})
    assert not bad["available"] and bad["input_errors"] == ["Growth after the forecast must be between -5% and 8%."]


def test_the_linked_statements_balance_on_real_shaped_inputs(synthetic):
    ts = service.build(Provider(), "SYN")["three_statement"]
    assert ts["available"] and ts["balances"]
    for y in ts["years"]:
        assert y["fcff_from_statements"] == pytest.approx(y["fcff_dcf"])


def test_a_bank_is_valued_on_its_equity_not_with_fcff(synthetic):
    synthetic["blob"], synthetic["sic"] = company_blob("bank"), "6022"
    out = service.build(Provider(industry="Banks - Regional"), "BNK")
    assert out["classification"]["business_type"] == "bank"
    assert not out["dcf"]["available"] and "raw material" in out["dcf"]["reason"]
    ri = out["residual_income"]
    assert ri["available"] and ri["fit"]["fit"] == "primary" and ri["implied_roe"] is not None


def test_a_loss_maker_gets_a_placeholder_margin_and_low_confidence(synthetic):
    synthetic["blob"] = company_blob(margin=-0.3)
    out = service.build(Provider(), "LOSS")
    assert out["classification"]["business_type"] == "unprofitable"
    assert out["classification"]["confidence"] == "low"
    why = next(r for r in out["defaults"]["rationale"] if r["key"] == "margin.target")
    assert "Placeholder" in why["why"]
    assert out["classification"]["models"]["reverse_dcf"]["fit"] == "primary"


def test_missing_operating_income_is_rebuilt_from_pretax_and_said_so(synthetic):
    blob = company_blob()
    del blob["facts"]["us-gaap"]["OperatingIncomeLoss"]
    synthetic["blob"] = blob
    out = service.build(Provider(), "SYN")
    assert out["dcf"]["available"]
    ebit = out["inputs"]["history"][0]["facts"]["operating_income"]
    assert ebit["kind"] == "derived" and "pre-tax income" in ebit["rule"]
    assert ebit["value"] == pytest.approx(1000 * 0.20 * 0.95 + 8.0)


def test_missing_operating_income_and_pretax_blocks_the_dcf_rather_than_guessing(synthetic):
    blob = company_blob()
    for tag in ("OperatingIncomeLoss",
                "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest"):
        del blob["facts"]["us-gaap"][tag]
    synthetic["blob"] = blob
    out = service.build(Provider(), "SYN")
    assert not out["dcf"]["available"] and "operating income" in out["dcf"]["reason"]


def test_output_is_json_safe(synthetic):
    import json
    json.dumps(service.clean(service.build(Provider(), "SYN")), allow_nan=False)


# ------------------------------------------------------------------ routes

client = TestClient(main.app)
GOOD = "tungsten-carbide-9"


def register(email):
    client.cookies.clear()
    client.post("/api/auth/register", json={"first_name": "Test", "last_name": "Reader", "email": email,
                                            "password": GOOD, "confirm_password": GOOD})
    return client.cookies.get(config.CSRF_COOKIE)


@pytest.fixture()
def wired(synthetic, monkeypatch):
    monkeypatch.setattr(main, "YF_PROVIDER", Provider())
    return synthetic


def test_routes_compute_and_refuse_bad_input(wired):
    r = client.get("/api/valuation/SYN")
    assert r.status_code == 200 and r.json()["dcf"]["available"]
    r2 = client.post("/api/valuation/SYN/run", json={"drivers": {"capex_pct": {"target": 0.08}}})
    assert r2.status_code == 200 and r2.json()["dcf"]["per_share"] < r.json()["dcf"]["per_share"]
    r3 = client.post("/api/valuation/SYN/run", json={"wacc": {"override": 5}})
    assert r3.status_code == 400 and r3.json()["detail"] == "Discount rate must be between 1% and 40%."


def _snapshot(out):
    return {"symbol": "SYN", "name": "My base case", "base": out["base"],
            "assumptions": out["assumptions"], "model_version": out["model_version"],
            "inputs": out["inputs_digest"], "result": {"per_share": out["dcf"]["per_share"]}}


def test_saved_models_replay_exactly_and_are_private(wired, accounts):
    out = service.build(Provider(), "SYN")
    csrf = register("a@example.com")
    saved = client.post("/api/valuation-models", headers={"X-Optic-CSRF": csrf}, json=_snapshot(out))
    assert saved.status_code == 200
    mid = saved.json()["model"]["id"]
    listed = client.get("/api/valuation-models?symbol=SYN").json()["models"]
    assert [m["id"] for m in listed] == [mid]
    got = client.get("/api/valuation-models/" + mid).json()
    assert got["replay"]["matches"] and not got["replay"]["version_changed"]
    # Saving again is a new snapshot, never an overwrite.
    client.post("/api/valuation-models", headers={"X-Optic-CSRF": csrf}, json=_snapshot(out))
    assert len(client.get("/api/valuation-models").json()["models"]) == 2
    other = register("b@example.com")
    assert client.get("/api/valuation-models/" + mid).status_code == 404
    assert client.delete("/api/valuation-models/" + mid, headers={"X-Optic-CSRF": other}).status_code == 404


def test_saving_needs_an_account_and_the_csrf_pair(wired, accounts):
    out = service.build(Provider(), "SYN")
    client.cookies.clear()
    assert client.post("/api/valuation-models", json=_snapshot(out)).status_code == 401
    register("c@example.com")
    assert client.post("/api/valuation-models", json=_snapshot(out)).status_code == 403


def test_an_unrunnable_snapshot_is_refused(wired, accounts):
    out = service.build(Provider(), "SYN")
    snap = _snapshot(out)
    snap["assumptions"] = copy.deepcopy(snap["assumptions"])
    snap["assumptions"]["drivers"]["terminal"]["growth"] = 0.5
    r = client.post("/api/valuation-models/replay", json=snap)
    assert r.status_code == 400 and "cannot be run" in r.json()["detail"]
    ok = client.post("/api/valuation-models/replay", json=_snapshot(out))
    assert ok.status_code == 200 and ok.json()["matches"]


def test_a_missing_beta_asks_for_it_and_the_readers_beta_runs_the_model(synthetic):
    p = Provider(beta=None)
    out = service.build(p, "SYN")
    assert not out["dcf"]["available"] and out["dcf"]["needs_input"] and "beta" in out["dcf"]["reason"]
    assert out["defaults"]["drivers"]["terminal"]["ronic"] is None
    fixed = service.build(p, "SYN", edits={"wacc": {"beta_raw": 1.0}})
    assert fixed["dcf"]["available"]
    service._CACHE.clear()                      # the cached quote has no beta
    assert fixed["dcf"]["per_share"] == pytest.approx(service.build(Provider(beta=1.0), "SYN")["dcf"]["per_share"])


def _segments(quarters):
    return {"available": True, "quarters": quarters, "q4_derived": 1, "tables": [
        {"axis": "StatementBusinessSegmentsAxis", "axis_label": "Segment", "metric": "operating_income",
         "rows": [{"member": "Machines", "values": [30.0, 30.0, 30.0, 30.0]},
                  {"member": "Services", "values": [25.0, 25.0, 25.0, 25.0]},
                  {"member": "Corporate Non Segment", "values": [-5.0, -5.0, -5.0, -5.0]}]}]}


def test_sum_of_the_parts_starts_at_the_dcf_and_takes_the_readers_multiples(synthetic, monkeypatch):
    from app.analytics import segments as segments_mod
    q = ["2025-09-30", "2025-12-31", "2026-03-31", "2026-06-30"]
    monkeypatch.setattr(segments_mod, "build", lambda t, force=False: _segments(q))
    out = service.sotp_model(Provider(), "SYN")
    assert out["available"] and out["segments_ttm_total"] == pytest.approx(200.0)
    assert out["unallocated"] == pytest.approx(-20.0)
    implied = out["dcf_implied_ev_ebit"]
    assert out["enterprise_value"] == pytest.approx(200.0 * implied)
    mine = service.sotp_model(Provider(), "SYN", {"Machines": 20.0, "Services": 10.0}, 10.0)
    assert mine["enterprise_value"] == pytest.approx(120 * 20 + 100 * 10 - 20 * 10)
    assert {r["name"]: r["multiple_source"] for r in mine["segments"]} == {"Machines": "reader", "Services": "reader"}


def test_sum_of_the_parts_refuses_a_year_with_a_missing_quarter(synthetic, monkeypatch):
    from app.analytics import segments as segments_mod
    q = ["2025-06-30", "2025-12-31", "2026-03-31", "2026-06-30"]
    monkeypatch.setattr(segments_mod, "build", lambda t, force=False: _segments(q))
    out = service.sotp_model(Provider(), "SYN")
    assert not out["available"] and "not consecutive" in out["reason"]


def test_a_cyclical_margin_moves_only_halfway_to_its_average(synthetic):
    synthetic["sic"] = "3312"
    out = service.build(Provider(industry="Steel"), "STL")
    assert out["classification"]["business_type"] == "cyclical"
    m = out["defaults"]["drivers"]["margin"]
    assert m["target"] == pytest.approx(m["start"])        # synthetic margins are flat at 20%
    why = next(r for r in out["defaults"]["rationale"] if r["key"] == "margin.target")
    assert "Halfway" in why["why"] and why["kind"] == "assumption"
