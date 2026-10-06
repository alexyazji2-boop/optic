"""Editable bear, base and bull valuation scenarios on the Investing tab.

Asked for with three rules this file holds the feature to. The starting point is
what the company reported, each figure with its source and date, and a figure
the feeds do not have is missing rather than guessed. Every assumption is the
reader's, a box filled from the company's own history says so and is never a
forecast. And the arithmetic is shown and checkable: revenue grown at the
reader's rate, a margin, a share count, an exit multiple, a discount, and a
yearly rate that is price appreciation and not total return.

The server side runs against a stub provider; the page's arithmetic and states
run in JavaScriptCore; the account routes run through TestClient with two real
sign-ins.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import app.main as main
from app import db
from app.analytics import sec_facts
from app.analytics import valuation_inputs as vi
from app.auth import config, store

ROOT = Path(__file__).resolve().parent.parent
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc"


class Provider:
    def __init__(self, quote=None, fin=None, short=None):
        self.q = quote if quote is not None else {"price": 100.0, "currency": "USD", "quote_type": "EQUITY",
                                                  "market_cap": 1e11, "trailing_pe": 25.0,
                                                  "dividend_yield": 0.012, "as_of": "2026-10-06T15:00:00+00:00",
                                                  "name": "Example Co"}
        self.fin = fin if fin is not None else statements()
        self.short = short if short is not None else {"shares_outstanding": 1e9}

    def quote(self, t):
        return self.q

    def financials(self, t):
        return self.fin

    def short_interest(self, t):
        return self.short


def statements():
    return {
        "income_annual": {"periods": ["2025-12-31", "2024-12-31", "2023-12-31", "2022-12-31"],
                          "rows": {"Total Revenue": [40e9, 36e9, 32e9, 30e9],
                                   "Net Income": [4e9, 3.6e9, 2.88e9, 2.4e9],
                                   "Diluted Average Shares": [0.97e9, 0.98e9, 0.99e9, 1.0e9]}},
        "income_quarterly": {"periods": ["2026-06-30", "2026-03-31", "2025-12-31", "2025-09-30"],
                             "rows": {"Total Revenue": [11e9, 10.5e9, 10e9, 9.5e9],
                                      "Net Income": [1.2e9, 1.1e9, 1.0e9, 0.9e9]}},
    }


def no_filings(monkeypatch):
    monkeypatch.setattr(sec_facts, "history", lambda t, force=False: {"available": False, "reason": "x"})


# ================================================================ the inputs

def test_filings_come_first_with_their_dates(monkeypatch):
    ttm = [{"period_end": "2023-06-30", "available_from": "2023-08-01", "value": 30e9, "derived": False},
           {"period_end": "2024-06-30", "available_from": "2024-08-01", "value": 33e9, "derived": False},
           {"period_end": "2025-06-30", "available_from": "2025-08-01", "value": 36e9, "derived": False},
           {"period_end": "2026-06-30", "available_from": "2026-08-02", "value": 40e9, "derived": False}]
    monkeypatch.setattr(sec_facts, "history", lambda t, force=False: {"available": True, "revenue_ttm": ttm})
    out = vi.build(Provider(), "X")
    rev = out["inputs"]["revenue"]
    assert rev["value"] == 40e9 and rev["currency"] == "USD" and "SEC" in rev["source"]
    assert rev["period_end"] == "2026-06-30" and rev["available_from"] == "2026-08-02"
    g = out["history"]["revenue_growth"]
    assert g["years"] == 3 and g["value"] == pytest.approx(((40 / 30) ** (1 / 3) - 1) * 100, abs=0.01)
    assert g["kind"] == "history" and "Not a forecast" in g["note"]


def test_without_filings_the_statements_are_used_and_say_which(monkeypatch):
    no_filings(monkeypatch)
    out = vi.build(Provider(), "X")
    rev = out["inputs"]["revenue"]
    assert rev["value"] == pytest.approx(41e9) and "last four quarters" in rev["source"]
    assert rev["currency"] is None and "does not state which currency" in rev["currency_note"]
    m = out["inputs"]["margin"]
    assert m["kind"] == "derived" and m["value"] == pytest.approx(4.2e9 / 41e9 * 100, abs=0.01)
    s = out["history"]["share_change"]
    assert s["years"] == 3 and s["value"] == pytest.approx(((0.97 / 1.0) ** (1 / 3) - 1) * 100, abs=0.01)
    assert out["history"]["margin"]["value"] == pytest.approx((10 + 10 + 9 + 8) / 4, abs=0.01)


def test_without_a_reported_count_the_market_value_gives_one_said_to_be_derived(monkeypatch):
    no_filings(monkeypatch)
    out = vi.build(Provider(short={}), "X")
    shares = out["inputs"]["shares"]
    assert shares["value"] == 1e9 and shares["kind"] == "derived"
    assert "market value divided by price" in shares["source"] and "approximate" in shares["note"]


def test_a_figure_the_feeds_lack_is_missing_not_guessed(monkeypatch):
    no_filings(monkeypatch)
    q = dict(Provider().q, market_cap=None)
    out = vi.build(Provider(quote=q, fin={}, short={}), "X")
    assert out["inputs"]["revenue"]["value"] is None and out["inputs"]["revenue"]["reason"]
    assert out["inputs"]["shares"]["value"] is None and "need yours" in out["inputs"]["shares"]["reason"]
    assert out["inputs"]["margin"]["value"] is None
    assert out["history"]["revenue_growth"]["value"] is None


def test_a_fund_is_not_valued_as_a_company(monkeypatch):
    no_filings(monkeypatch)
    out = vi.build(Provider(quote={"price": 400.0, "quote_type": "ETF", "currency": "USD"}), "SPY")
    assert out["available"] is False and "not a company" in out["reason"]


def test_currencies_that_differ_are_stated(monkeypatch):
    no_filings(monkeypatch)
    q = dict(Provider().q, financial_currency="TWD")
    out = vi.build(Provider(quote=q), "TSM")
    assert out["inputs"]["revenue"]["currency"] == "TWD"
    joined = " ".join(out["warnings"])
    assert "TWD" in joined and "USD" in joined and "receipts" in joined


def test_the_endpoint_refuses_a_bad_symbol():
    assert TestClient(main.app).get("/api/valuation-inputs/not%20a%20symbol!").status_code == 400


# ================================================================ the arithmetic

def _run(script):
    exe = JSC if os.path.exists(JSC) else shutil.which("jsc")
    if not exe:
        pytest.skip("no JavaScriptCore on this machine")
    src = """
      load('tests/support/browser_stubs.js');
      document.documentElement.style = document.documentElement.style || {};
      document.documentElement.style.setProperty = function () {};
      document.documentElement.style.removeProperty = function () {};
      try { load('static/charts.js'); load('static/app.js'); } catch (e) { print('LOADFAIL:' + e); }
      var MEM = {};
      localStorage.getItem = function (k) { return Object.prototype.hasOwnProperty.call(MEM, k) ? MEM[k] : null; };
      localStorage.setItem = function (k, v) { MEM[k] = String(v); };
      var R = {};
    """ + script + "\nprint('RESULT:' + JSON.stringify(R));"
    out = subprocess.run([exe, "-e", src], capture_output=True, text=True, timeout=120, cwd=str(ROOT))
    blob = out.stdout + out.stderr
    assert "RESULT:" in blob, blob[-2000:]
    return json.loads(blob.split("RESULT:", 1)[1].split("\n")[0])


def test_a_case_is_worked_out_the_way_the_page_says():
    out = _run("""
      R.r = valuationScenario({revenue: 100e9, shares: 1e9, price: 50, marketCap: 50e9},
        {growth: 10, margin: 20, share_change: -1, pe: 18}, {years: 5, required_return: 9});
    """)["r"]
    rev = 100e9 * 1.1 ** 5
    ni = rev * 0.2
    shares = 1e9 * 0.99 ** 5
    price = ni / shares * 18
    assert out["revenue"] == pytest.approx(rev) and out["netIncome"] == pytest.approx(ni)
    assert out["eps"] == pytest.approx(ni / shares) and out["shares"] == pytest.approx(shares)
    assert out["price"] == pytest.approx(price)
    assert out["priceToday"] == pytest.approx(price / 1.09 ** 5)
    assert out["vsPrice"] == pytest.approx(price / 1.09 ** 5 / 50 - 1)
    assert out["cagr"] == pytest.approx((price / 50) ** (1 / 5) - 1)


def test_a_case_that_ends_in_a_loss_has_no_multiple():
    out = _run("""
      R.r = valuationScenario({revenue: 10e9, shares: 1e9, price: 5}, {growth: 5, margin: -3, share_change: 0, pe: 20},
        {years: 3, required_return: 8});
      R.html = (function () {
        STATE.ticker = 'X'; VALUATION.inputsFor = 'X';
        VALUATION.inputs = {available: true, inputs: {revenue: {value: 10e9}, shares: {value: 1e9}, price: {value: 5}},
          history: {}, price_currency: 'USD'};
        var d = valuationDraft('X');
        d.shared.years = '3'; d.shared.required_return = '8';
        d.base.growth = '5'; d.base.margin = '-3'; d.base.share_change = '0'; d.base.pe = '20';
        return valuationOutputs('X', 'base');
      })();
    """)
    assert out["r"]["loss"] is True and "price" not in out["r"]
    assert "net loss" in out["html"] and "does not value it" in out["html"]


def test_without_a_share_count_it_values_the_company_not_a_share():
    out = _run("""
      R.r = valuationScenario({revenue: 10e9, shares: null, price: 5, marketCap: 40e9},
        {growth: 0, margin: 10, share_change: 0, pe: 20}, {years: 2, required_return: 0});
    """)["r"]
    assert out["companyValue"] == pytest.approx(20e9) and "eps" not in out
    assert out["vsMarketCap"] == pytest.approx(20e9 / 40e9 - 1)


def test_boxes_are_checked_one_by_one_and_blank_is_not_zero():
    out = _run("""
      var d = valuationEmptyDraft();
      d.base.growth = 'abc'; d.base.margin = '150'; d.shared.years = '2.5'; d.bull.pe = '0';
      d.shared.revenue = '12q';
      R.errs = valuationErrors(d);
      R.blank = valuationScenario({revenue: 1e9, shares: 1e6, price: 1}, valuationCaseNumbers(valuationEmptyDraft(), 'bear'),
        {years: 5, required_return: 9});
      R.amount = [valuationAmount('130.5B'), valuationAmount('350M'), valuationAmount('1,200'), valuationNumber('12%')];
    """)
    errs = out["errs"]
    assert errs["base.growth"] == "Not a number"
    assert errs["base.margin"].startswith("Between -500 and 100")
    assert errs["shared.years"] == "A whole number"
    assert errs["bull.pe"].startswith("Between 0.1")
    assert "130.5B" in errs["shared.revenue"]
    assert "base.share_change" not in errs, "a blank box is not an error"
    assert out["blank"]["ok"] is False and "revenue growth" in out["blank"]["missing"]
    assert out["amount"] == [130.5e9, 350e6, 1200, 12]


def test_nothing_is_filled_in_until_the_reader_asks_and_history_says_so():
    out = _run("""
      STATE.ticker = 'X'; VALUATION.inputsFor = 'X';
      STATE.long = {holding: {valuation_history: {available: true, median_pe: 22.4, usable_years: 5}}};
      VALUATION.inputs = {available: true, price_currency: 'USD',
        inputs: {price: {value: 50, source: 'Yahoo Finance quote', kind: 'reported', as_of: '2026-10-06T15:00:00Z'},
                 revenue: {value: 40e9, currency: 'USD', source: 'SEC filings', kind: 'reported', period_end: '2026-06-30',
                           available_from: '2026-08-02'},
                 margin: {value: 10.2, source: 'Yahoo Finance income statements', kind: 'derived', period_end: '2026-06-30'},
                 shares: {value: null, reason: 'The feed has no share count, so per-share figures need yours.'},
                 market_cap: {value: 50e9, source: 'Yahoo Finance quote', kind: 'reported'},
                 dividend_yield: {value: 0.012}},
        history: {revenue_growth: {value: 10.07, years: 3, source: 'SEC filings'}, margin: {value: 9.25, years: [1, 2, 3, 4]},
                  share_change: {value: -1.01, years: 3}}};
      R.before = renderValuationScenarios();
      valuationFillFromHistory('X', 'base');
      var d = valuationDraft('X');
      R.base = [d.base.growth, d.base.margin, d.base.share_change, d.base.pe];
      R.bull = [d.bull.growth, d.bull.pe];
      R.marks = d.from_history;
      R.after = renderValuationScenarios();
    """)
    before = out["before"]
    assert before.count("Needs ") == 3, "no case is valued before the reader gives inputs"
    assert "SEC filings, period ended Jun 30, 2026, public from Aug 2, 2026" in before
    assert "per-share figures need yours" in before
    assert "Its own history, not a forecast" in before
    assert "not a total return" in before and "1.20%" in before
    assert out["base"] == ["10.1", "9.3", "-1", "22.4"]
    assert out["bull"] == ["", ""], "bull and bear stay the reader's to fill"
    assert set(out["marks"]) == {"base.growth", "base.margin", "base.share_change", "base.pe"}
    assert out["after"].count(">history</span>") == 4


def test_a_guest_save_is_kept_in_this_browser_as_numbers():
    out = _run("""
      STATE.ticker = 'X';
      var d = valuationDraft('X');
      d.shared.years = '5'; d.base.growth = '8%'; d.base.pe = '20';
      var p = valuationSave('X');
      R.stored = JSON.parse(MEM['optic.valuation.v1'] || 'null');
      R.status = VALUATION.status['X'];
      d.base.margin = 'oops';
      valuationSave('X');
      R.refused = VALUATION.status['X'];
    """)
    base = out["stored"]["X"]["base"]
    assert base["growth"] == 8 and base["pe"] == 20 and base["margin"] is None
    assert out["stored"]["X"]["shared"]["years"] == 5
    assert out["status"].startswith("Saved")
    assert "fix the boxes" in out["refused"]


def test_the_store_is_a_personal_key():
    app = (ROOT / "static/app.js").read_text(encoding="utf-8")
    keys = app[app.index("const PERSONAL_KEYS = ["):app.index("];", app.index("const PERSONAL_KEYS = ["))]
    assert "'optic.valuation.v1'" in keys


# ================================================================ the account

client = TestClient(main.app)
GOOD = "tungsten-carbide-9"


@pytest.fixture()
def fresh(accounts):
    client.cookies.clear()
    return accounts


def register(email):
    client.cookies.clear()
    client.post("/api/auth/register", json={
        "first_name": "Test", "last_name": "Reader", "email": email,
        "password": GOOD, "confirm_password": GOOD})
    return client.cookies.get(config.CSRF_COOKIE)


BODY = {"shared": {"years": 5, "required_return": 9}, "base": {"growth": 8, "margin": 12, "share_change": -1, "pe": 20},
        "bull": {"growth": 15}, "from_history": ["base.growth", "nonsense.key"], "extra": "dropped"}


def test_scenarios_round_trip_typed_and_bounded(fresh):
    csrf = register("a@example.com")
    reply = client.put("/api/valuations/nvda", headers={"X-Optic-CSRF": csrf}, json=BODY)
    assert reply.status_code == 200, reply.text
    saved = client.get("/api/valuations").json()["valuations"]["NVDA"]
    assert saved["base"]["growth"] == 8 and saved["bull"]["growth"] == 15 and saved["bear"]["pe"] is None
    assert saved["from_history"] == ["base.growth"] and "extra" not in saved
    bad = client.put("/api/valuations/NVDA", headers={"X-Optic-CSRF": csrf},
                     json={"base": {"margin": 250}})
    assert bad.status_code == 400 and "base.margin" in bad.json()["detail"]
    empty = client.put("/api/valuations/NVDA", headers={"X-Optic-CSRF": csrf}, json={"base": {}})
    assert empty.status_code == 400
    assert client.delete("/api/valuations/NVDA", headers={"X-Optic-CSRF": csrf}).status_code == 200
    assert client.get("/api/valuations").json()["valuations"] == {}


def test_each_reader_has_only_their_own(fresh):
    a = register("a@example.com")
    client.put("/api/valuations/NVDA", headers={"X-Optic-CSRF": a}, json=BODY)
    b = register("b@example.com")
    assert client.get("/api/valuations").json()["valuations"] == {}
    assert client.delete("/api/valuations/NVDA", headers={"X-Optic-CSRF": b}).status_code == 404
    assert len(db.rows("SELECT id FROM valuations")) == 1
    client.cookies.clear()
    assert client.get("/api/valuations").status_code == 401


def test_adopting_a_browser_copy_never_overwrites(fresh):
    csrf = register("a@example.com")
    client.put("/api/valuations/NVDA", headers={"X-Optic-CSRF": csrf}, json=BODY)
    reply = client.post("/api/valuations/adopt", headers={"X-Optic-CSRF": csrf}, json={"valuations": {
        "NVDA": {"base": {"growth": 99}}, "AMD": {"base": {"growth": 7}}, "BAD!": {"base": {"growth": 1}},
        "MSFT": {"base": {"margin": 900}}}})
    out = reply.json()
    assert out["adopted"] == ["AMD"] and out["skipped"] == ["NVDA"] and set(out["refused"]) == {"BAD!", "MSFT"}
    mine = client.get("/api/valuations").json()["valuations"]
    assert mine["NVDA"]["base"]["growth"] == 8, "the account's copy wins"


def test_a_write_needs_the_csrf_pair(fresh):
    register("a@example.com")
    assert client.put("/api/valuations/NVDA", json=BODY).status_code == 403


def test_the_results_show_the_share_count_and_a_loss_maker_is_flagged():
    out = _run("""
      STATE.ticker = 'X'; VALUATION.inputsFor = 'X';
      VALUATION.inputs = {available: true, price_currency: 'USD',
        inputs: {price: {value: 10}, revenue: {value: 1e9}, shares: {value: 1e8}, margin: {value: -4.2}},
        history: {}};
      var d = valuationDraft('X');
      d.shared.years = '5'; d.base.growth = '10'; d.base.margin = '8'; d.base.share_change = '2'; d.base.pe = '15';
      R.out = valuationOutputs('X', 'base');
      R.panel = renderValuationScenarios();
    """)
    assert "Diluted shares in year 5" in out["out"] and "110.41M" in out["out"]
    assert "is losing money on its latest figures" in out["panel"]
