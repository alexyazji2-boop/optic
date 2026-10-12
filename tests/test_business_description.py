"""The Overview's description comes from the latest annual report (2026-10-12).

Reported on NBIS: "The description may be out of date ... make sure that it
is always up to date". Yahoo's text read "It offers Nebius builds full-stack
infrastructure for AI"; the 20-F filed 2026-04-30 opens "Nebius, a global AI
cloud platform, delivers a unified full-stack AI cloud". Checked against live
EDGAR for NBIS, AAPL, TSM, BABA, PEP, NVDA, AMD, JPM, KO, SHOP, RKLB, NVO and
MSTR: each read its own business overview. ASML and SAP file a 20-F that is
an index into a separate report and keep Yahoo's text.

The documents below are cut-down copies of those layouts; nothing here
touches the network.
"""
from __future__ import annotations

import threading
import time
from pathlib import Path

from app.analytics import business

ROOT = Path(__file__).resolve().parent.parent
LONG = ("It designs and sells the things it sells to the customers it sells them to, "
        "in many countries, through several channels, and it has done so for years.")


def _doc(*parts: str) -> str:
    return "<html><body>" + "".join(parts) + "</body></html>"


def test_a_10k_is_read_from_item_1_and_not_from_the_contents_page():
    raw = _doc(
        "<table><tr><td>Item 1.</td><td>Business</td><td>1</td></tr>",
        "<tr><td>Item 1A.</td><td>Risk Factors</td><td>5</td></tr></table>",
        "<p>Item 1. Business</p><p>Company Background</p>",
        "<p>The Company designs, manufactures and markets smartphones, personal computers and "
        "tablets, and sells a variety of related services. The Company’s fiscal year is the 52- "
        "or 53-week period that ends on the last Saturday of September.</p>",
        "<p>Products</p><p>iPhone</p>",
        "<p>iPhone ® is the Company’s line of smartphones based on its iOS operating system, sold "
        "around the world.</p>",
        "<p>Mac</p><p>" + LONG + "</p>",
        "<p>Item 1A. Risk Factors</p><p>" + LONG + "</p>")
    text = business.extract(raw, "10-K")
    assert text.startswith("The Company designs, manufactures and markets smartphones")
    assert "fiscal year" not in text, "housekeeping, not what the company does"
    assert "iPhone is the Company’s line" in text, "the ® goes, and the space before it"
    assert "Risk" not in text


def test_a_20f_is_read_from_its_business_overview_not_its_history():
    raw = _doc(
        "<p>ITEM 4. INFORMATION ON THE COMPANY</p><p>Our History and Structure</p>",
        "<p>We were incorporated in 1987 as a company limited by shares and listed in 1994 on an "
        "exchange, then listed our depositary shares in New York in 1997.</p>",
        "<p>Business Overview of the Company</p>",
        "<p>As a foundry, we manufacture semiconductors using our manufacturing processes for our "
        "customers based on proprietary integrated circuit designs provided by them.</p>",
        "<p>" + LONG + "</p><p>Item 5. Operating Results</p>")
    assert business.extract(raw, "20-F").startswith("As a foundry, we manufacture")


def test_a_paragraph_split_across_a_page_is_read_from_its_start():
    raw = _doc(
        "<p>B. Business Overview</p>",
        "<p>We offer a comprehensive range of wafer fabrication processes, including processes to "
        "manufacture logic, and</p>",
        "<p>TSMC 3DFabric advanced silicon stacking and packaging services, and testing services.</p>",
        "<p>" + LONG + "</p>")
    text = business.extract(raw, "20-F")
    assert text.startswith("We offer a comprehensive range"), text
    assert "manufacture logic, and TSMC 3DFabric" in text


def test_paragraphs_about_the_report_itself_are_skipped():
    raw = _doc(
        "<p>Item 1. Business</p>",
        "<p>When used in this report, the terms “we,” “us,” “our,” “PepsiCo” and the “Company” "
        "mean PepsiCo, Inc. and its consolidated subsidiaries, collectively.</p>",
        "<p>Reference is made to the sections '2025 at a glance' on page 7 and 'Purpose, strategy "
        "and culture' on page 9 of our Annual Report 2025.</p>",
        "<p>We are a leading global beverage and convenient food company with a complementary "
        "portfolio of brands sold in more than 200 countries.</p><p>" + LONG + "</p>")
    assert business.extract(raw, "10-K").startswith("We are a leading global beverage")


def test_a_20f_that_only_points_elsewhere_gives_nothing():
    raw = _doc("<p>Information on the Company</p><p>A. History and Development</p>",
               "<p>Cover page</p><p>1</p><p>B. Business Overview</p><p>At a glance</p><p>6</p>",
               "<p>Our marketplace</p><p>22</p>")
    assert business.extract(raw, "20-F") is None


def test_a_long_overview_is_cut_at_a_sentence():
    raw = _doc("<p>Item 1. Business</p>", "<p>" + " ".join([LONG] * 20) + "</p>")
    text = business.extract(raw, "10-K")
    assert len(text) <= business.MAX_CHARS and text.endswith(".")


def test_the_request_never_waits_on_edgar(monkeypatch):
    gate = threading.Event()
    calls = []

    def slow_refresh(symbol):
        calls.append(symbol)
        gate.wait(5)
        with business._LOCK:
            business._RUNNING.discard(symbol)
            business._CHECKED[symbol] = (time.time(), {"text": "From the filing.", "form": "10-K"})

    monkeypatch.setattr(business, "_refresh", slow_refresh)
    monkeypatch.setattr(business, "_CHECKED", {})
    monkeypatch.setattr(business, "_RUNNING", set())
    t = time.time()
    assert business.latest("ZZZT") is None, "first ask: nothing yet, and no wait"
    assert business.latest("ZZZT") is None
    assert time.time() - t < 0.5
    assert calls == ["ZZZT"], "one look in flight, not one per ask"
    gate.set()
    for _ in range(50):
        if business.latest("ZZZT"):
            break
        time.sleep(0.05)
    assert business.latest("ZZZT")["text"] == "From the filing."


def test_the_session_payload_carries_it_and_the_overview_dates_it():
    main = (ROOT / "app/main.py").read_text()
    assert "filing = business_mod.latest(symbol)" in main
    assert "summary=filing[\"text\"], summary_source=" in main
    app = (ROOT / "static/app.js").read_text()
    fn = app[app.index("function ovAboutSourceHTML("):]
    fn = fn[:fn.index("\n}\n")]
    assert "from its latest ${esc(src.form_name)}, filed ${esc(filed)}" in fn
    assert "Read the filing" in fn and "www\\.sec\\.gov" in fn
    assert "The description may be out of date." not in app


def test_the_endpoint_swaps_in_the_filing_and_keeps_the_feed_text_without_one(monkeypatch):
    from fastapi.testclient import TestClient
    from app import main

    feed = {"ticker": "NBIS", "name": "Nebius Group N.V.", "kind": "EQUITY", "is_company": True,
            "summary": "It offers Nebius builds full-stack infrastructure for AI.", "sector": "Technology"}
    monkeypatch.setattr(main.YF_PROVIDER, "profile", lambda s: dict(feed))
    monkeypatch.setattr(main.PROVIDER, "quote", lambda s: {"name": "Nebius Group N.V.", "price": 100.0})
    monkeypatch.setattr(main.session_mod, "overnight_started_at", lambda: None)
    filing = {"text": "Nebius, a global AI cloud platform, delivers a unified full-stack AI cloud.",
              "form": "20-F", "form_name": "annual report (Form 20-F)", "filed": "2026-04-30",
              "period": "2025-12-31", "url": "https://www.sec.gov/Archives/edgar/data/1513845/x.htm"}
    monkeypatch.setattr(main.business_mod, "latest", lambda s: filing)
    client = TestClient(main.app)
    prof = client.get("/api/session/NBIS?fresh=1").json()["profile"]
    assert prof["summary"].startswith("Nebius, a global AI cloud platform")
    assert prof["summary_source"]["filed"] == "2026-04-30" and prof["sector"] == "Technology"

    monkeypatch.setattr(main.business_mod, "latest", lambda s: None)
    prof = client.get("/api/session/NBIT?fresh=1").json()["profile"]
    assert prof["summary"].startswith("It offers") and "summary_source" not in prof
