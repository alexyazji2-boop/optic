"""Handoff 10 (owner's handover pack, 2026-11-03): Guided Investigation, "Investigate this company".

The four acceptance tests, each named for it, then the edge cases. Every source is stood in (the registry's figures,
the segment tables, the business description, the peer comparables and the Company events timeline), and so is the
model, through the same client Milo uses: no feed and no model is reached. The allowance is the real one."""
import json
import re
import types

import pytest
from fastapi.testclient import TestClient

import app.main as m
from app import ai, ai_store, investigation, library
from app.analytics import business as business_mod
from app.auth import config, store
from tests.test_frontend_v2_stage0 import V2, _run

JS = V2 / "js"
GOOD = "tungsten-carbide-9"
SEC = "https://www.sec.gov/Archives/edgar/data/320193/000032019325000079/aapl-20250927.htm"


def _fig(fid, name, value, text, period, end, inputs=()):
    return {"id": fid, "name": name, "status": "ok", "value": value, "text": text, "unit": "percent",
            "period": {"type": "annual", "label": period, "end": end}, "as_of": end, "inputs": list(inputs),
            "source": {"provider": "SEC EDGAR", "form": "10-K", "filed": "2025-10-31", "url": SEC}}


REVENUE = {"key": "revenue", "name": "Revenue", "value": 416.161e9, "text": "$416.2 billion", "start": "2024-09-29",
           "end": "2025-09-27", "form": "10-K", "filed": "2025-10-31", "url": SEC, "line": "Revenues"}
FIGURES = {"ticker": "AAPL", "available": True, "figures": {
    "net_margin_fy": _fig("net_margin_fy", "Net margin, fiscal year", 26.92, "26.9%", "Fiscal year ended Sep 27, 2025",
                          "2025-09-27", [REVENUE, dict(REVENUE, key="net_income", name="Net income", value=112.01e9,
                                                       text="$112.0 billion", line="NetIncomeLoss")]),
    "net_margin_ttm": _fig("net_margin_ttm", "Net margin, last 12 months", 27.3, "27.3%", "12 months to Sep 27, 2025",
                           "2025-09-27"),
    "free_cash_flow_ttm": dict(_fig("free_cash_flow_ttm", "Free cash flow, last 12 months", 98.77e9, "$98.8 billion",
                                    "12 months to Sep 27, 2025", "2025-09-27"), unit="money"),
    "net_debt": dict(_fig("net_debt", "Net debt", 34.0e9, "$34.0 billion", "On Sep 27, 2025", "2025-09-27"), unit="money"),
    "forward_pe": {"id": "forward_pe", "name": "Forward P/E", "status": "unavailable", "value": None,
                   "text": "Not available", "why": "No analysts' forecast came back just now."},
}}
SEGMENTS = {"available": True, "ticker": "AAPL", "filings_unread": 0, "kpis": None,
            "kpi_note": "Operating metrics are not in the filings. Those figures are published in press releases.",
            "tables": [{"axis": "segment", "axis_label": "Segment", "metric": "revenue", "metric_label": "Revenue",
                        "rows": [], "annual": {"ends": ["2024-09-28", "2025-09-27"], "rows": [
                            {"member": "Americas", "values": [167.0e9, 178.4e9]},
                            {"member": "Europe", "values": [101.3e9, 111.0e9]},
                            {"member": "Greater China", "values": [66.9e9, 64.4e9]}]}},
                       {"axis": "segment", "axis_label": "Segment", "metric": "operating_income",
                        "metric_label": "Operating income", "rows": [], "annual": {"ends": ["2025-09-27"], "rows": [
                            {"member": "Americas", "values": [72.1e9]}]}}]}
COMPS = {"available": True, "ticker": "AAPL", "peer_source": "industry",
         "peers": [{"symbol": s, "name": n, "market_cap": 1e12, "origin": "industry"}
                   for s, n in (("MSFT", "Microsoft"), ("GOOGL", "Alphabet"), ("META", "Meta"), ("AMZN", "Amazon"),
                                ("NVDA", "NVIDIA"))],
         "implied": [{"key": "pe", "label": "Price / earnings", "own_multiple": 35.1, "peers_with_value": 5,
                      "outliers": [], "implied": {"low": {"multiple": 24.0}, "mid": {"multiple": 28.4},
                                                  "high": {"multiple": 33.0}}, "spread": 1.38, "wide": False},
                     {"key": "ev_ebitda", "label": "EV / EBITDA", "own_multiple": 26.0, "peers_with_value": 2,
                      "implied": None, "reason": "Fewer than three peers have a positive EV / EBITDA."}],
         "source": "Yahoo Finance, trailing twelve months, for the company and each peer"}
EVENTS = {"since": "2026-08-06", "today": "2026-11-04", "sources": {
    "news": {"state": "ok", "reach": "The headline feed holds its latest 11 stories about the company."},
    "earnings": {"state": "ok"}, "insiders": {"state": "ok"}, "congress": {"state": "ok"},
    "analysts": {"state": "failed", "failed": "The analyst-action feed did not answer."}, "filings": {"state": "ok"}},
    "events": [
        {"type": "earnings", "type_label": "Earnings", "date": "2027-01-28", "date_kind": "scheduled",
         "date_label": "Scheduled, not yet reported", "title": "Next earnings report",
         "summary": "Scheduled, not yet reported.", "source": "Yahoo Finance", "source_url": None},
        {"type": "earnings", "type_label": "Earnings", "date": "2026-10-30", "date_kind": "reported",
         "date_label": "Reported", "title": "Reported quarterly results for Q4 FY26",
         "summary": "Earnings per share $1.85 against an average estimate of $1.77, 4.5% above it.",
         "source": "Yahoo Finance", "source_url": None},
        {"type": "insiders", "type_label": "Insiders", "date": "2026-10-02", "date_kind": "traded",
         "date_label": "Transaction date", "title": "Sale of 129,963 shares by COOK TIMOTHY D, Chief Executive Officer",
         "summary": "Sale at price 255.00 to 258.00 per share.", "source": "Form 4, via Yahoo Finance",
         "source_url": None, "delay_note": "This is the transaction date."},
    ]}
DESCRIPTION = {"text": "Apple Inc. designs, manufactures and markets smartphones, personal computers, tablets, wearables "
                       "and accessories, and sells a variety of related services.",
               "form": "10-K", "form_name": "annual report on Form 10-K", "filed": "2025-10-31",
               "period": "fiscal 2025", "url": SEC}


class Provider:
    def profile(self, t):
        return {"name": "Apple Inc.", "is_company": True, "industry": "Consumer Electronics", "sector": "Technology",
                "employees": 166000} if t == "AAPL" else {"name": t, "is_company": False}

    def quote(self, t):
        return {"name": "Apple Inc." if t == "AAPL" else t, "price": 270.0}


EXTRA = " About 12% of sales came from services last quarter."


@pytest.fixture
def model(monkeypatch):
    """The model, stood in behind the client ai._ask is given: it quotes the first two facts it was sent, by id, and
    adds one figure that is in none of them. `fail` holds step numbers that fail as an overloaded API does; `advise`
    adds a sentence of advice."""
    seen = {"prompts": [], "fail": set(), "advise": False}

    def create(**kw):
        prompt = kw["messages"][-1]["content"]
        seen["prompts"].append({"prompt": prompt, "system": kw["system"], "model": kw["model"]})
        step = re.search(r"INVESTIGATION STEP (\d+) of", prompt)
        if step and int(step.group(1)) in seen["fail"]:
            raise RuntimeError("overloaded_error: the stand-in is overloaded on purpose")
        facts = re.findall(r"^\[(F\d+)\] ([^:\n]+): ([^(\n]+?) \(", prompt, re.M)
        text = " ".join("{} is {} [{}].".format(lbl.strip(), val.strip(), fid) for fid, lbl, val in facts[:2]) + EXTRA
        if seen["advise"]:
            text += " You should buy the stock before the report."
        return types.SimpleNamespace(model=ai.PULSE_MODEL, stop_reason="end_turn",
                                     usage=types.SimpleNamespace(input_tokens=900, output_tokens=120),
                                     content=[types.SimpleNamespace(type="text", text=text)])
    client = types.SimpleNamespace(messages=types.SimpleNamespace(create=create))
    monkeypatch.setattr(investigation, "_sync_client", lambda: client)
    monkeypatch.setattr(ai_store, "record", lambda *a, **k: None)
    return seen


@pytest.fixture(autouse=True)
def stood_in(accounts, monkeypatch):
    monkeypatch.setattr(m, "YF_PROVIDER", Provider())
    monkeypatch.setattr(m, "PROVIDER", Provider())
    monkeypatch.setattr(m.figures_mod, "for_ticker", lambda p, s, yf=None: FIGURES if s == "AAPL" else
                        m.figures_mod.unavailable(s, "No filings for a fund."))
    monkeypatch.setattr(m.segments_mod, "build", lambda s, force=False: SEGMENTS if s == "AAPL" else
                        {"available": False, "reason": "SPY is not in EDGAR's directory."})
    monkeypatch.setattr(m.valuation_service, "comps", lambda p, s, peers=None: COMPS if s == "AAPL" else
                        {"available": False, "reason": "No peer list: the quote feed gives no industry for SPY."})
    monkeypatch.setattr(m.timeline_mod, "cached", lambda p, s, days=90, **kw: json.loads(json.dumps(EVENTS)) if s == "AAPL"
                        else {"since": "2026-08-06", "today": "2026-11-04", "events": [], "sources": {}})
    monkeypatch.setattr(business_mod, "latest", lambda s, wait=False: DESCRIPTION if s == "AAPL" else None)
    monkeypatch.setattr(m, "_assistant_status", lambda: {"enabled": True})
    monkeypatch.setattr(m, "_ai_calls", {})
    return accounts


def account(email="reader@example.com", plan="pro"):
    http = TestClient(m.app)
    http.post("/api/auth/register", json={"first_name": "A", "last_name": "B", "email": email,
                                          "password": GOOD, "confirm_password": GOOD})
    user = store.get_user_by_email(email)
    if plan != "free":
        store.set_plan(user["id"], plan)
    return http, {"X-Optic-CSRF": http.cookies.get(config.CSRF_COOKIE)}, user


def investigate(http, headers, skip=(), order=None):
    started = http.post("/api/investigate/AAPL", headers=headers, json={"skip": list(skip), "order": order,
                                                                         "level": "intermediate"})
    assert started.status_code == 200, started.text
    body = started.json()
    results = {}
    for sid in body["investigation"]["order"]:
        if sid in skip:
            continue
        r = http.post("/api/investigate/AAPL/step", headers=headers, json={"step": sid, "item_id": body["item_id"]})
        assert r.status_code == 200, r.text
        results[sid] = r.json()["result"]
    return body, results


def summary_html(tmp_path, inv, **opts):
    return _run(tmp_path, f"""
      globalThis.console = globalThis.console || {{ log() {{}}, warn() {{}}, error() {{}} }};
      const P = await import('{(JS / "pages/investigate.js").as_posix()}');
      const D = await import('{(JS / "core/dom.js").as_posix()}');
      const inv = {json.dumps(inv)};
      print(JSON.stringify({{ html: D.toString(P.summaryHTML(inv, {json.dumps(opts)})), status: P.statusLine(inv),
        sources: P.combinedSources(inv), steps: Object.fromEntries(inv.order.map((id) => [id, D.toString(P.stepBody(inv.steps[id] || {{ state: 'pending' }}))])) }}));
    """)


# ---------------------------------------------------------------- the four acceptance tests


def test_acceptance_1_six_steps_with_sources_and_a_saved_summary_and_a_labelled_partial(tmp_path, model):
    """AAPL investigation completes all six steps with per-step sources and a saved summary; skipping a step still
    yields a coherent partial summary labeled as such."""
    http, headers, user = account()
    body, results = investigate(http, headers)
    assert body["kept"] and body["item_id"] and body["investigation"]["order"] == list(investigation.STEP_IDS)
    assert set(results) == set(investigation.STEP_IDS) and len(model["prompts"]) == 6
    for sid, r in results.items():
        assert r["state"] == "done" and not r["no_data"], sid
        assert r["facts"] and r["sources"], sid
        assert {f["source_n"] for f in r["facts"]} == {s["n"] for s in r["sources"]}, "every fact names a listed source"
        assert re.search(r"\[F\d+\]", r["text"]), "the answer cites its facts"
        assert all(f["period"] or f["kind"] in ("text", "universe") or f["as_of"] for f in r["facts"]), sid
    # one model call a step, Milo's model and prompt, never another model
    assert {p["model"] for p in model["prompts"]} == {ai.PULSE_MODEL}
    assert all(ai.SYSTEM_PROMPT in p["system"][0]["text"] for p in model["prompts"])
    # kept as it ran, then saved under its name
    got = http.get("/api/investigate/item/{}".format(body["item_id"])).json()
    assert got["status"]["complete"] and got["status"]["done"] == 6 and got["status"]["status"] == "draft"
    saved = http.patch("/api/investigate/item/{}".format(body["item_id"]), headers=headers,
                       json={"status": "saved", "name": "Apple, a first look"})
    assert saved.status_code == 200 and saved.json()["investigation"]["status"] == "saved"
    listed = http.get("/api/library?kind=investigation").json()
    assert [x["name"] for x in listed["items"]] == ["Apple, a first look"] and listed["counts"]["investigation"] == 1
    item = listed["items"][0]
    assert item["kind"] == "investigation" and item["tickers"] == ["AAPL"] and item["summary"]["complete"]
    h = summary_html(tmp_path, saved.json()["investigation"])
    assert h["status"] == {"partial": False, "text": "Complete: all 6 steps."}
    for title in ("What the company does", "Financial health", "Segments and company KPIs", "Peers", "Recent events",
                  "Risks and questions to check"):
        assert ">{}".format(title) in h["html"], title
    assert h["sources"] and all(s["steps"] for s in h["sources"]) and "Research, not investment advice." in h["html"]
    # skipping Peers: five steps, a summary labelled partial that says what is missing and fills nothing in
    body2, results2 = investigate(http, headers, skip=("peers",))
    assert set(results2) == set(investigation.STEP_IDS) - {"peers"}
    inv2 = http.get("/api/investigate/item/{}".format(body2["item_id"])).json()
    assert inv2["status"]["partial"] and inv2["status"]["skipped"] == ["peers"] and inv2["status"]["done"] == 5
    h2 = summary_html(tmp_path, inv2["investigation"])
    assert h2["status"]["partial"] and "Skipped: Peers." in h2["status"]["text"]
    assert "<b>Partial.</b>" in h2["html"] and "nothing is filled in for the others" in h2["html"]
    assert ">Peers<" not in h2["html"], "a skipped step has no section in the summary"


def test_acceptance_2_could_not_verify_is_its_own_section_never_mixed_with_verified(tmp_path, model):
    """"Could not verify" items appear in their own section, never mixed with verified figures."""
    http, headers, _ = account()
    _, results = investigate(http, headers)
    for sid, r in results.items():
        # Milo's sentence with a figure no fact holds is out of the answer and in the list, with its figure
        assert "12%" not in r["text"], sid
        moved = [u for u in r["unverified"] if u["kind"] == "unmatched"]
        assert moved and moved[0]["figures"] == ["12%"] and "services" in moved[0]["text"], sid
        # and nothing in the verified table is a figure Optic does not hold
        assert all(not f["text"].startswith("12%") for f in r["facts"])
    health = results["health"]
    # what the sources did not have is in the list too, never estimated
    assert any(u["text"].startswith("Forward P/E: Not available") for u in health["unverified"])
    assert any(u["text"].startswith("Revenue and profit growth:") for u in health["unverified"])
    assert any(u["text"].startswith("Company KPIs:") for u in results["segments"]["unverified"])
    assert any(u["text"].startswith("Analyst actions (events):") for u in results["events"]["unverified"])
    # step 2 uses the registry's figures and the inputs they are worked out from, nothing else
    for f in health["facts"]:
        assert f["kind"] in ("figure", "input"), f
        if f["kind"] == "figure":
            assert f["figure"] in m.figures_mod.REGISTRY and f["formula"] == m.figures_mod.REGISTRY[f["figure"]]["formula"]
    # drawn: the facts table, then "Could not verify" as its own heading and list, the sentence only there
    h = summary_html(tmp_path, {"order": ["health"], "skipped": [], "steps": {"health": health}})
    body = h["steps"]["health"]
    table, rest = body.split('<h3 class="t-h3 gi-sub">Could not verify</h3>', 1)
    assert "About 12% of sales" not in table and "About 12% of sales came from services last quarter." in rest
    assert "Optic found no source for 12%, so it was taken out of the answer." in rest
    assert '<table class="t gi-facts">' in table and "26.9%" in table and "Formula: Net income divided by revenue" in table
    assert "<h3 class=\"t-h3\">Could not verify</h3>" in h["html"] and h["html"].count("About 12% of sales") == 1
    # the checker on its own: rounded figures match their fact, others do not, dates and labels are not figures
    facts = [{"id": "F1", "label": "Net margin", "text": "26.9%", "period": "Fiscal year ended Sep 27, 2025"},
             {"id": "F2", "label": "Revenue", "text": "$416.2 billion", "period": "2025"}]
    got = investigation.check("Margin was 26.9% [F1] on about $416 billion [F2], reported Oct 30, 2025 for Q4 FY25. "
                              "Revenue rose 6.4% [F7]. It has three segments.", facts)
    assert got["text"] == ("Margin was 26.9% [F1] on about $416 billion [F2], reported Oct 30, 2025 for Q4 FY25. "
                           "It has three segments.")
    assert got["unverified"] == [{"text": "Revenue rose 6.4%.", "figures": ["6.4%"]}] and got["cited"] == ["F1", "F2"]


def test_acceptance_3_a_failed_step_keeps_the_others_and_can_be_retried(tmp_path, model):
    """Mid-investigation step failure retains completed steps and allows retry."""
    http, headers, _ = account()
    model["fail"].add(3)
    body, results = investigate(http, headers)
    assert results["segments"]["state"] == "failed" and "Milo did not answer this step" in results["segments"]["why"]
    others = [s for s in investigation.STEP_IDS if s != "segments"]
    assert all(results[s]["state"] == "done" for s in others), "the steps after it ran too"
    kept = http.get("/api/investigate/item/{}".format(body["item_id"])).json()
    assert kept["status"]["failed"] == ["segments"] and kept["status"]["done"] == 5 and kept["status"]["partial"]
    assert kept["investigation"]["steps"]["business"]["text"] == results["business"]["text"], "kept as it was"
    h = summary_html(tmp_path, kept["investigation"])
    assert "Failed: Segments and company KPIs." in h["status"]["text"]
    page = _run(tmp_path, f"""
      globalThis.console = globalThis.console || {{ log() {{}}, warn() {{}}, error() {{}} }};
      const P = await import('{(JS / "pages/investigate.js").as_posix()}');
      const D = await import('{(JS / "core/dom.js").as_posix()}');
      const plan = {{ steps: {json.dumps([{"id": s["id"], "title": s["title"], "reads": s["reads"]} for s in investigation.STEPS])} }};
      P._test.set({{ sym: 'AAPL', plan, inv: {json.dumps(kept["investigation"])}, current: null, open: new Map(), focusStep: 'segments' }});
      print(JSON.stringify({{ failed: D.toString(P._test.stepItem('segments', 2)), done: D.toString(P._test.stepItem('business', 0)) }}));
    """)
    assert 'data-state="failed"' in page["failed"] and 'data-gi-retry="segments"' in page["failed"]
    assert "Milo did not answer this step" in page["failed"] and "The other steps are unaffected." in page["failed"]
    assert 'data-gi-retry="business"' in page["done"] and "Run again" in page["done"]
    # retried: it runs once more on the reader's press, and the investigation is whole
    model["fail"].clear()
    again = http.post("/api/investigate/AAPL/step", headers=headers, json={"step": "segments", "item_id": body["item_id"]})
    assert again.status_code == 200 and again.json()["result"]["state"] == "done"
    assert again.json()["status"]["complete"] and not again.json()["status"]["failed"]


def test_acceptance_4_usage_is_shown_before_starting(tmp_path, model):
    """Usage (if metered) is shown before starting."""
    http, headers, _ = account(plan="free")
    plan = http.get("/api/investigate/AAPL/plan").json()
    assert plan["usage"]["enforced"] and plan["usage"]["left"] == 3 and plan["usage"]["most"] == 6
    assert plan["max_steps"] == 6 and "at most 12 minutes" in plan["time_note"] and plan["signed_in"]
    assert model["prompts"] == [], "the plan asks nothing"
    got = _run(tmp_path, f"""
      globalThis.console = globalThis.console || {{ log() {{}}, warn() {{}}, error() {{}} }};
      const P = await import('{(JS / "pages/investigate.js").as_posix()}');
      const D = await import('{(JS / "core/dom.js").as_posix()}');
      const plan = {json.dumps(plan)};
      const view = (skip) => {{ P._test.set({{ sym: 'AAPL', plan, order: plan.steps.map((s) => s.id), skip: new Set(skip), inv: null }}); return D.toString(P._test.planView('AAPL')); }};
      print(JSON.stringify({{ all: view([]), three: view(['peers', 'events', 'risks']), gate6: P.canStart(plan, 6), gate3: P.canStart(plan, 3),
        guest: P.canStart(Object.assign({{}}, plan, {{ signed_in: false, usage: Object.assign({{}}, plan.usage, {{ requires_account: true }}) }}), 6),
        admin: P.usageLine(Object.assign({{}}, plan, {{ usage: {{ enforced: false }} }}), 6) }}));
    """)
    assert "Uses up to 6 assistant messages, one for each step that asks Milo. You have 3 left on the Free plan." in got["all"]
    assert ("You have 3 assistant messages left, and these steps need up to 6. Skip steps to fit, or come back when the "
            "allowance resets.") in got["all"]
    assert re.search(r'data-gi-start\s+disabled', got["all"]) and not got["gate6"]["ok"] and got["gate3"]["ok"]
    assert "Start investigation, up to 3 messages" in got["three"] and not re.search(r'data-gi-start\s+disabled', got["three"])
    assert got["guest"]["signin"] and "Milo needs a free account" in got["guest"]["why"]
    assert got["admin"].endswith("This account's Milo use is not counted against an allowance.")
    # and it is what the server charges: a step that asks Milo is one message, the fourth is refused
    body = http.post("/api/investigate/AAPL", headers=headers, json={}).json()
    codes = [http.post("/api/investigate/AAPL/step", headers=headers,
                       json={"step": s, "item_id": body["item_id"]}).status_code for s in investigation.STEP_IDS[:4]]
    assert codes == [200, 200, 200, 429]
    kept = http.get("/api/investigate/item/{}".format(body["item_id"])).json()
    assert kept["status"]["done"] == 3 and kept["status"]["left"] == ["peers", "events", "risks"], "kept to continue"
    assert http.get("/api/investigate/AAPL/plan").json()["usage"]["left"] == 0


# ---------------------------------------------------------------- the edge cases


def test_thin_coverage_says_not_reported_and_asks_nothing(tmp_path, model):
    """A fund with none of the steps' figures: every step says what is missing, Milo is never asked, and the reader's
    allowance is untouched."""
    http, headers, _ = account(plan="free")
    results = {}
    for sid in investigation.STEP_IDS:
        r = http.post("/api/investigate/SPY/step", headers=headers, json={"step": sid})
        assert r.status_code == 200, r.text
        results[sid] = r.json()["result"]
    for sid, r in results.items():
        assert r["no_data"] and r["state"] == "done" and r["facts"] == [] and r["text"] == "", sid
        assert r["unverified"] and all(u["kind"] == "not_available" for u in r["unverified"]), sid
    assert model["prompts"] == [], "a step with no data makes no call"
    assert http.get("/api/investigate/SPY/plan").json()["usage"]["left"] == 3, "and costs nothing"
    page = summary_html(tmp_path, {"order": ["health"], "skipped": [], "steps": {"health": results["health"]}})
    assert "Not reported." in page["steps"]["health"] and "nothing was estimated" in page["steps"]["health"]
    assert "No filings for a fund." in page["steps"]["health"]


def test_another_account_cannot_read_or_run_it_and_the_library_will_not_save_one(model):
    http, headers, _ = account()
    body = http.post("/api/investigate/AAPL", headers=headers, json={}).json()
    other, oh, _ = account("other@example.com")
    assert other.get("/api/investigate/item/{}".format(body["item_id"])).status_code == 404
    assert other.patch("/api/investigate/item/{}".format(body["item_id"]), headers=oh, json={"notes": "x"}).status_code == 404
    assert other.post("/api/investigate/AAPL/step", headers=oh, json={"step": "health", "item_id": body["item_id"]}).status_code == 404
    assert http.post("/api/investigate/MSFT/step", headers=headers,
                     json={"step": "health", "item_id": body["item_id"]}).status_code == 409
    refused = http.post("/api/library", headers=headers, json={"kind": "investigation", "tickers": ["AAPL"]})
    assert refused.status_code == 400 and "kept by its own page" in refused.json()["detail"]
    assert http.post("/api/investigate/AAPL", headers=headers, json={"skip": list(investigation.STEP_IDS)}).status_code == 400
    assert http.post("/api/investigate/AAPL/step", headers=headers, json={"step": "everything"}).status_code == 422


def test_the_reader_edits_the_summary_never_the_facts(tmp_path, model):
    http, headers, _ = account()
    body, results = investigate(http, headers, skip=("peers", "events", "risks", "segments", "business"))
    r = http.patch("/api/investigate/item/{}".format(body["item_id"]), headers=headers,
                   json={"edits": {"health": "My own reading of the margins [F1].", "nonsense": "x"},
                         "notes": "Check the services split.", "facts": [], "steps": {}})
    inv = r.json()["investigation"]
    assert inv["edits"] == {"health": "My own reading of the margins [F1]."} and inv["notes"] == "Check the services split."
    assert inv["steps"]["health"]["facts"] == results["health"]["facts"], "the facts are not the reader's to change"
    h = summary_html(tmp_path, inv)
    assert "Edited by you" in h["html"] and "My own reading of the margins" in h["html"] and "Check the services split." in h["html"]
    content = library.db.row("SELECT content FROM saved_research WHERE id = ?", (body["item_id"],))["content"]
    assert "My own reading of the margins." in content, "the library's search reads the edited words, citations out"


def test_the_risk_step_turns_what_could_not_be_verified_into_questions(model):
    http, headers, _ = account()
    investigate(http, headers)
    risk = model["prompts"][-1]["prompt"]
    assert risk.startswith("INVESTIGATION STEP 6 of 6: Risks and questions to check")
    assert "EARLIER STEPS COULD NOT VERIFY" in risk and "About 12% of sales came from services last quarter." in risk
    # 178.4 of 353.8 billion: worked out by Optic, with its formula, not by the model
    assert "Largest segment's share of segment revenue: Americas: 50.4%" in risk
    health = next(p["prompt"] for p in model["prompts"] if "Financial health" in p["prompt"].split("\n")[0])
    assert "NOT AVAILABLE" in health and "Forward P/E: Not available" in health
    # the investigation's own instructions are among the system blocks; the house writing rules (Phase 12,
    # app/editorial.py) now follow every prompt, so they are no longer the last block
    assert any("Do not compute new numbers" in b["text"] for b in model["prompts"][0]["system"])


def test_advice_is_removed_as_from_every_milo_answer(model):
    http, headers, _ = account()
    model["advise"] = True
    r = http.post("/api/investigate/AAPL/step", headers=headers, json={"step": "health"}).json()["result"]
    assert "should buy" not in r["text"] and r["removed"] == 1


def test_saved_research_lists_and_reopens_an_investigation(tmp_path):
    got = _run(tmp_path, f"""
      globalThis.console = globalThis.console || {{ log() {{}}, warn() {{}}, error() {{}} }};
      const L = await import('{(JS / "core/library.js").as_posix()}');
      const S = await import('{(JS / "pages/saved.js").as_posix()}');
      const R = await import('{(JS / "core/router.js").as_posix()}');
      print(JSON.stringify({{ route: L.routeOf({{ kind: 'investigation', id: 'abc123', tickers: ['AAPL'], gone: ['AAPL'] }}),
        word: L.WORD.investigation, kinds: L.KINDS,
        draft: S.investigationAbout({{ status: 'draft', done: 3, planned: 6, failed: ['peers'] }}),
        partial: S.investigationAbout({{ status: 'saved', done: 5, planned: 5, partial: true, skipped: ['peers'] }}),
        whole: S.investigationAbout({{ status: 'saved', done: 6, planned: 6, partial: false }}),
        parsed: R.parse('#/AAPL/investigate?saved=abc123') }}));
    """)
    assert got["route"] == "#/AAPL/investigate?saved=abc123", "a record reopens even if the ticker has gone"
    assert got["word"] == "Investigation" and "investigation" in got["kinds"]
    assert got["draft"] == "Draft: 3 of 6 steps done, 1 failed"
    assert got["partial"] == "Partial: 5 of 5 steps done, 1 skipped" and got["whole"] == "Complete: 6 of 6 steps done"
    assert got["parsed"] == {"view": "investigate", "symbol": "AAPL", "params": {"saved": "abc123"}}


def test_milo_follow_ups_carry_the_investigation(tmp_path, model):
    http, headers, _ = account()
    _, results = investigate(http, headers, skip=("peers", "events", "risks", "segments", "business"))
    inv = {"name": "Investigation of AAPL", "order": list(investigation.STEP_IDS), "skipped": ["peers", "events", "risks",
                                                                                              "segments", "business"],
           "steps": {"health": results["health"]}, "edits": {}, "notes": ""}
    got = _run(tmp_path, f"""
      globalThis.console = globalThis.console || {{ log() {{}}, warn() {{}}, error() {{}} }};
      const P = await import('{(JS / "pages/investigate.js").as_posix()}');
      const M = await import('{(JS / "ui/milo.js").as_posix()}');
      M.resetContext({{ view: 'investigate', symbol: 'AAPL', params: {{}} }});
      M.provideContext(() => ({{ view: 'investigate', ticker: 'AAPL', investigation: P.contextOf({json.dumps(inv)}) }}));
      print(JSON.stringify(M.buildContext('auto', null, new Date('2026-11-04T21:00:00Z'))));
    """)
    assert got["focus"]["ticker"] == "AAPL" and got["focus"]["section"] == "Investigation"
    assert got["investigation"]["steps"][0]["step"] == "Financial health" and "[F" not in got["investigation"]["steps"][0]["text"]
    assert got["investigation"]["steps"][0]["could_not_verify"][0].startswith("Forward P/E") or got["investigation"]["steps"][0]["could_not_verify"]
    rf = ai.research_focus(got)
    assert rf["ticker"] == "AAPL" and rf["section"] == "Investigation"
    assert "The reader is researching AAPL on its Investigate this company checklist" in ai.context_header(got)


def test_entry_points_and_the_page_rules():
    menu = (JS / "ui" / "company.js").read_text()
    assert '<a href="#/${e}/investigate">Investigate this company</a>' in menu, "in the ⋯ menu on every size"
    ov = (JS / "pages" / "dossier.js").read_text()
    # on the Overview, a section after the analysis that opens the plan; the Dossier's header is unchanged
    assert 'href="#/${encodeURIComponent(sym)}/investigate">See the steps</a>' in ov
    # the Overview's View switch is gone (2026-11-09): the level control decides, and Investigate is Advanced's or one
    # Show more away below it
    assert "${has('investigate') ? (adv ? investigateEntry(sym) : opened('investigate', 'Investigate this company', investigateEntry(sym))) : ''}" in ov \
        and "['investigate', 'Investigate this company'" in ov
    page = (JS / "pages" / "investigate.js").read_text()
    assert "IntersectionObserver" not in page and "—" not in page
    # one gold action at a time: Start before, Continue while steps remain, then Save to library
    assert page.count('class="btn btn-primary"') == 2
    assert "lead = runnable().length || S.current ? 'btn' : 'btn btn-primary'" in page
