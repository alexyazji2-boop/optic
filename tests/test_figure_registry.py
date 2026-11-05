"""The canonical figure registry (owner's Handoff 1, 2026-11-03; app/figures, static/v2/js/core/figures.js, ui/figure.js).

On 2026-11-03 the same AAPL figure read differently on different pages: net debt $62.7B in the Financials chart caption
(cash and equivalents only) and $44.0B beside it (cash and short-term investments); a fiscal-year net margin of 26.9%
from the provider's statements beside the provider's own twelve-month 27.6%; a forward P/E of 30.9 on Compare (a model
cached at an earlier price) against 31.2 on the Dossier. These tests hold the fix: every figure is a registry entry with
a definition, formula, period and source; one function computes each; the Dossier, Compare and Milo print the same text;
a figure the registry does not know fails here; and the edge cases (restated, missing, negative, another currency) read
as the handoff requires.
"""
import json
import re
from pathlib import Path

import pytest

from app import ai_policy, figures
from app import milo_tools
from app.analytics import compare, longterm
from app.figures import registry as reg
from app.figures import compute as res
from app.valuation import inputs as vi
from tests.test_frontend_v2_stage0 import _run

ROOT = Path(__file__).resolve().parent.parent
V2JS = ROOT / "static" / "v2" / "js"
USD = "USD"


# ------------------------------------------------------------------------------------------------ fixtures
def fact(val, end, start=None, form="10-K", filed="2026-02-10", fp="FY", accn="0000000001-26-000001"):
    r = {"val": val, "end": end, "form": form, "filed": filed, "fp": fp, "accn": accn, "fy": 2025}
    if start:
        r["start"] = start
    return r


def filings(gaap):
    blob = {"entityName": "Acme Corp", "facts": {"us-gaap": {
        tag: {"units": {unit: rows}} for tag, (unit, rows) in gaap.items()}}}
    return vi.Filings(blob, "0000000001", "2026-10-01T00:00:00+00:00")


Q = dict(form="10-Q", filed="2026-08-01", fp="Q2", accn="0000000001-26-000009")
Q1 = dict(form="10-Q", filed="2026-05-01", fp="Q1", accn="0000000001-26-000005")
Q3P = dict(form="10-Q", filed="2025-11-01", fp="Q3", accn="0000000001-25-000012")


def acme(revenue=400.0, restated_revenue=None, capex=True, cash=True):
    """A December filer: fiscal 2025 from its 10-K, then a 10-Q to June 30, 2026 (and the quarters between)."""
    rev = [fact(revenue, "2025-12-31", "2025-01-01"),
           fact(220.0, "2026-06-30", "2026-01-01", **Q), fact(190.0, "2025-06-30", "2025-01-01", **Q),
           fact(105.0, "2026-03-31", "2026-01-01", **Q1), fact(290.0, "2025-09-30", "2025-01-01", **Q3P)]
    if restated_revenue is not None:
        rev.append(fact(restated_revenue, "2025-12-31", "2025-01-01", form="10-K/A", filed="2026-04-15",
                        accn="0000000001-26-000007"))
    gaap = {
        "Revenues": (USD, rev),
        "NetIncomeLoss": (USD, [fact(80.0, "2025-12-31", "2025-01-01"), fact(50.0, "2026-06-30", "2026-01-01", **Q),
                                fact(36.0, "2025-06-30", "2025-01-01", **Q)]),
        "NetCashProvidedByUsedInOperatingActivities": (USD, [
            fact(120.0, "2025-12-31", "2025-01-01"), fact(70.0, "2026-06-30", "2026-01-01", **Q),
            fact(55.0, "2025-06-30", "2025-01-01", **Q)]),
        "Assets": (USD, [fact(900.0, "2025-12-31"), fact(950.0, "2026-06-30", **Q)]),
        "LongTermDebt": (USD, [fact(150.0, "2026-06-30", **Q), fact(160.0, "2025-12-31")]),
        "CommercialPaper": (USD, [fact(10.0, "2026-06-30", **Q)]),
        "FinanceLeaseLiability": (USD, [fact(5.0, "2026-06-30", **Q)]),
        "ShortTermInvestments": (USD, [fact(30.0, "2026-06-30", **Q)]),
        "OperatingLeaseLiability": (USD, [fact(20.0, "2026-06-30", **Q)]),
    }
    if capex:
        gaap["PaymentsToAcquirePropertyPlantAndEquipment"] = (USD, [
            fact(20.0, "2025-12-31", "2025-01-01"), fact(12.0, "2026-06-30", "2026-01-01", **Q),
            fact(9.0, "2025-06-30", "2025-01-01", **Q)])
    if cash:
        gaap["CashAndCashEquivalentsAtCarryingValue"] = (USD, [fact(50.0, "2026-06-30", **Q), fact(45.0, "2025-12-31")])
    return filings(gaap)


QUOTE = {"ticker": "ACME", "price": 120.0, "forward_eps": 4.8, "forward_pe": 24.6, "profit_margin": 0.27,
         "quote_type": "EQUITY", "currency": "USD", "financial_currency": "USD",
         "trade_time": "2026-11-03T21:00:00+00:00", "as_of": "2026-11-03T21:05:00+00:00"}


def block(fl=None, quote=None, fin=None):
    return figures.resolve("ACME", dict(QUOTE, **(quote or {})), sec=(fl or acme(), "0000000001", None), financials=fin)


def figs(fl=None, **kw):
    return block(fl, **kw)["figures"]


# ------------------------------------------------------------------------------------------------ the registry
def test_every_entry_has_every_field_and_a_definition_at_every_level():
    assert set(reg.IDS) >= {"net_margin_fy", "net_margin_ttm", "forward_pe", "free_cash_flow_fy", "free_cash_flow_ttm",
                            "operating_cash_flow_fy", "operating_cash_flow_ttm", "net_debt", "net_debt_with_leases"}
    pub = reg.public()
    assert pub["levels"] == ["new", "beginner", "intermediate", "advanced", "expert"], "the slider's five, in order"
    for fid, e in reg.REGISTRY.items():
        for k in reg.REQUIRED:
            assert e.get(k) not in (None, ""), (fid, k)
        assert e["unit"] in reg.UNITS and e["period"] in reg.PERIODS, fid
        assert all(r in reg.REGISTRY for r in e["related"]), (fid, "a related id that is not registered")
        d = pub["figures"][fid]
        assert set(d["definitions"]) == set(reg.LEVELS) and all(len(t) > 40 for t in d["definitions"].values()), fid
        assert d["limits"] and d["period_name"], fid


def test_two_legitimate_definitions_are_two_entries_never_one():
    """A fiscal year and the last twelve months, net debt with and without operating leases: each pair is two ids,
    each labelled with what it is, so a page that shows both says which is which (handoff, desired behaviour 2)."""
    for a, b in (("net_margin_fy", "net_margin_ttm"), ("free_cash_flow_fy", "free_cash_flow_ttm"),
                 ("operating_cash_flow_fy", "operating_cash_flow_ttm"), ("net_debt", "net_debt_with_leases")):
        ea, eb = reg.REGISTRY[a], reg.REGISTRY[b]
        assert ea["name"] != eb["name"] and (ea["period"] != eb["period"] or ea["formula"] != eb["formula"]), (a, b)
        assert b in ea["related"] and a in eb["related"], (a, b, "each names the other")


def test_definitions_describe_and_never_advise():
    """Definitions say what a figure measures and what it cannot tell you; none judges a reading (handoff,
    compliance). Optic's own advice check reads them, and no em dash reaches a reader."""
    judging = re.compile(r"\b(buy|sell|cheap|expensive|good|bad|undervalued|overvalued|attractive|bargain|should|"
                         r"recommend\w*)\b", re.I)
    for fid in reg.IDS:
        e = reg.public()["figures"][fid]
        for text in list(e["definitions"].values()) + [e["limits"], e["formula"], e["name"]]:
            assert not judging.search(text), (fid, judging.search(text).group(0), text)
            assert ai_policy.check_output(text) == [], (fid, text)
            assert "\u2014" not in text, (fid, "no em dashes")


def test_an_unknown_level_reads_as_the_default_rather_than_failing():
    assert reg.definition("net_debt", "professional") == reg.definition("net_debt", reg.DEFAULT_LEVEL)


# ------------------------------------------------------------------------------------------------ one computation each
def test_the_filings_give_every_figure_with_its_period_formula_inputs_and_source():
    f = figs()
    assert f["net_margin_fy"]["text"] == "20.0%" and f["net_margin_fy"]["period"]["label"] == "Fiscal year ended Dec 31, 2025"
    assert f["free_cash_flow_fy"]["text"] == "$100" and f["operating_cash_flow_fy"]["text"] == "$120"
    # twelve months to the 10-Q: the 10-K's year plus this year to date, less the same months a year earlier
    t = f["net_margin_ttm"]
    assert t["value"] == pytest.approx(94 / 430 * 100) and t["text"] == "21.9%"
    assert t["period"]["label"] == "12 months to Jun 30, 2026"
    assert t["period"]["quarters"] == ["2025-09-30", "2025-12-31", "2026-03-31", "2026-06-30"], "the four quarters, listed"
    assert "Sep 30, 2025, Dec 31, 2025, Mar 31, 2026 and Jun 30, 2026" in t["period"]["quarters_text"]
    assert f["free_cash_flow_ttm"]["value"] == pytest.approx(135 - 23) and f["operating_cash_flow_ttm"]["value"] == pytest.approx(135)
    nd = f["net_debt"]
    assert nd["value"] == pytest.approx(150 + 10 + 5 - 50 - 30) and nd["period"]["label"] == "On Jun 30, 2026"
    assert [i["key"] for i in nd["inputs"]] == ["debt", "finance_leases", "cash", "short_term_investments"]
    assert f["net_debt_with_leases"]["value"] == pytest.approx(85 + 20)
    for fid, fv in f.items():
        if fid == "forward_pe":
            continue
        assert fv["source"]["provider"] == "SEC EDGAR" and fv["source"]["url"].startswith("https://www.sec.gov/Archives/"), fid
        assert fv["restatement"] == "checked" and fv["status"] == "ok", fid


def test_the_forward_pe_is_the_price_on_the_page_over_the_forward_eps():
    """Not the feed's own forwardPE, which is worked at the feed's price at another moment: Compare read 30.9 against
    the Dossier's 31.2 for AAPL (authenticated audit, 2026-11-03)."""
    fpe = figs()["forward_pe"]
    assert fpe["value"] == pytest.approx(120 / 4.8) and fpe["text"] == "25.0", "25.0, not the feed's 24.6"
    assert fpe["period"]["fiscal_year"] == "Not disclosed by the provider", "said literally, never hidden"
    assert fpe["as_of"] == QUOTE["trade_time"] and "4:00 PM ET" in fpe["period"]["label"]


def test_the_research_frameworks_net_debt_is_the_registrys_function():
    from app.research import quality
    src = (ROOT / "app/research/quality.py").read_text()
    assert "net_debt = figures_mod.net_debt_value(balance)" in src, "one function for the check and every page"
    bal = vi.balance_sheet(acme(), "2026-06-30")
    hist = [{"fy_end": "2025-12-31", "flows": {"operating_income": {"value": 100.0}, "da": {"value": 10.0},
                                               "interest_expense": {"value": 5.0}}}]
    out = quality.health_component(hist, bal, "operating", {"leverage_max_net_debt_ebitda": 3.0, "coverage_min_ebit_interest": 3.0})
    assert out["status"] == "scored"
    assert out["figures"]["net_debt"] == figures.net_debt_value(bal) == pytest.approx(85.0)
    assert out["figures"]["net_debt"] == figures.resolve("ACME", dict(QUOTE), sec=(acme(), "1", None))["figures"]["net_debt"]["value"]


def test_the_five_figures_match_across_the_dossier_compare_and_milo(monkeypatch):
    """Handoff 1's first acceptance test, on one company's data: the Dossier's snapshot block, Compare's row, Milo's
    quote tool, Milo's figure set (for get_fundamentals, get_valuation, get_assessment) and the long-term model's
    notes print the same text for each figure."""
    fl = acme()
    monkeypatch.setattr(vi, "load_filings", lambda t, force=False: (fl, "0000000001", None))

    class Provider:
        def quote(self, sym):
            return dict(QUOTE)

        def financials(self, sym):
            return {}

        def sec_filings(self, sym):
            return figures.load(sym)

    dossier = figures.resolve("ACME", dict(QUOTE), sec=figures.load("ACME"), financials=None)["figures"]
    milo = figures.for_ticker(Provider(), "ACME", Provider())
    milo_compact = figures.compact(milo)
    quote_tool = milo_tools.compact_quote(dict(QUOTE))
    row = compare._metrics({"ticker": "ACME", "quote": dict(QUOTE), "figures": {"figures": dossier}}, {})
    notes = " ".join(longterm._valuation_read(dict(QUOTE), milo["figures"])["notes"])
    for fid in ("net_margin_fy", "net_margin_ttm", "forward_pe", "free_cash_flow_ttm", "free_cash_flow_fy",
                "operating_cash_flow_ttm", "operating_cash_flow_fy", "net_debt", "net_debt_with_leases"):
        assert dossier[fid]["text"] == milo["figures"][fid]["text"] == milo_compact["ACME " + fid]["text"], fid
        assert dossier[fid]["value"] == milo["figures"][fid]["value"], fid
    assert row["figures"]["forward_pe"]["text"] == dossier["forward_pe"]["text"] == quote_tool["figures"]["ACME forward_pe"]["text"]
    assert row["forward_pe"] == dossier["forward_pe"]["value"] and quote_tool["quote"]["forward_pe"] == dossier["forward_pe"]["value"]
    assert "Forward P/E {}.".format(dossier["forward_pe"]["text"]) in notes
    assert "Net margin {}, over the 12 months to Jun 30, 2026.".format(dossier["net_margin_ttm"]["text"]) in notes


def test_milos_sources_carry_the_figures_it_was_given():
    """The retrieved list under an answer names each registry figure a lookup returned, with its id, so the panel it
    opens is the Dossier's definition (desired behaviour 3); its label and ok stay where the panel reads them."""
    rec = milo_tools.Record("get_quote", {"ticker": "ACME"}, True, "ok", 0.1,
                            figures=milo_tools._figures_of(milo_tools.compact_quote(dict(QUOTE))))
    pub = rec.public()
    assert pub["label"] == "ACME quote" and pub["ok"] is True
    assert pub["figures"] == [{"figure_id": "forward_pe", "symbol": "ACME", "name": "Forward P/E", "text": "25.0",
                               "status": "ok", "period": pub["figures"][0]["period"],
                               "source": "Yahoo Finance quote and analysts' consensus", "as_of": QUOTE["trade_time"]}]
    plain = milo_tools.Record("get_news", {"ticker": "ACME"}, True, "ok", 0.1).public()
    assert "figures" not in plain, "a lookup with no registry figures keeps its old shape"


def test_a_tool_result_makes_room_for_the_figures_inside_its_limit():
    big = {"source": "x", "data": {"rows": ["y" * 400 for _ in range(60)]}}
    figs_ = figures.compact(block())
    out = milo_tools.with_figures(big, figs_)
    assert out["figures"] == figs_ and len(json.dumps(out, default=str)) <= milo_tools.RESULT_CHARS + 200


# ------------------------------------------------------------------------------------------------ edge cases
def test_a_restated_figure_says_so_with_the_earlier_value_and_the_date():
    f = figs(acme(restated_revenue=390.0))["net_margin_fy"]
    assert f["value"] == pytest.approx(80 / 390 * 100), "the latest filing's value"
    assert f["restated"] == {"on": "2026-04-15", "prior": pytest.approx(20.0), "prior_text": "20.0%"}
    rev = next(i for i in f["inputs"] if i["key"] == "revenue")
    assert rev["restated"] == {"on": "2026-04-15", "prior": 400.0}
    # the twelve months include the restated year, so they say so too, rebuilt from the earlier value
    t = figs(acme(restated_revenue=390.0))["net_margin_ttm"]
    assert t["restated"]["on"] == "2026-04-15" and t["restated"]["prior"] == pytest.approx(94 / 430 * 100)


def test_a_restated_balance_restates_both_net_debts():
    fl = acme()
    fl.gaap["CashAndCashEquivalentsAtCarryingValue"]["units"]["USD"].append(
        fact(40.0, "2026-06-30", form="10-Q/A", filed="2026-09-01", fp="Q2", accn="0000000001-26-000011"))
    f = figs(fl)
    assert f["net_debt"]["value"] == pytest.approx(150 + 10 + 5 - 40 - 30)
    assert f["net_debt"]["restated"] == {"on": "2026-09-01", "prior": pytest.approx(85.0), "prior_text": "$85"}
    assert f["net_debt_with_leases"]["restated"]["on"] == "2026-09-01"
    assert f["net_debt_with_leases"]["restated"]["prior"] == pytest.approx(85.0 + 20.0)


def test_the_provider_fallback_says_its_restatement_history_is_unavailable_and_names_its_currency():
    fin = {"available": True, "annual_periods": ["2025-12-31"], "quarterly_periods": [],
           "annual": {"revenue": [3.81e12], "net_income": [1.70e12], "operating_cash_flow": [2.27e12],
                      "capital_expenditure": [-1.28e12]},
           "quarterly": {}, "balance_sheet": {"total_debt": 1.0e12, "cash_and_short_term": 3.06e12}}
    b = figures.resolve("TSM", {"price": 300.0, "forward_eps": 14.0, "forward_pe": 17.3, "quote_type": "EQUITY",
                                "currency": "USD", "financial_currency": "TWD"},
                        sec=(None, None, "no US-GAAP filings"), financials=fin)
    f = b["figures"]
    assert b["statement_source"]["provider"] == "Yahoo Finance"
    assert f["free_cash_flow_fy"]["text"] == "TWD 990.0B" and f["free_cash_flow_fy"]["currency"] == "TWD"
    capex = next(i for i in f["free_cash_flow_fy"]["inputs"] if i["key"] == "capex")
    assert capex["value"] == 1.28e12 and capex["text"] == "TWD 1.28T", "money spent, not the statement's negative"
    assert f["net_debt"]["text"] == "−TWD 2.06T" and f["net_debt"]["note"] == "Negative means net cash."
    for fid in ("net_margin_fy", "free_cash_flow_fy", "net_debt"):
        assert f[fid]["restatement"] == "unavailable" and f[fid]["source"]["url"] is None, fid
        assert "Filing link unavailable" in f[fid]["source"]["note"], fid
    # quarterly cash flow is not in the fallback: said, never zero
    assert f["free_cash_flow_ttm"]["status"] == "not_reported" and f["free_cash_flow_ttm"]["value"] is None
    # another currency's EPS is never divided into a dollar price here: the provider's own ratio, said to be its own
    assert f["forward_pe"]["text"] == "17.3" and "does not divide one into the other" in f["forward_pe"]["source"]["note"]


@pytest.mark.parametrize("kw,status,why", [
    (dict(capex=False), "not_reported", "capital expenditure"),
    (dict(cash=False), "not_reported", "No cash balance"),
])
def test_a_missing_line_is_not_reported_never_zero(kw, status, why):
    f = figs(acme(**kw))
    fid = "free_cash_flow_fy" if "capex" in kw else "net_debt"
    assert f[fid]["status"] == status and f[fid]["value"] is None and f[fid]["text"] == "Not reported"
    assert why in f[fid]["why"]


def test_a_margin_on_negative_revenue_and_a_pe_on_a_loss_are_not_meaningful():
    f = figs(acme(revenue=-5.0))
    assert f["net_margin_fy"]["status"] == "not_meaningful" and f["net_margin_fy"]["text"] == "Not meaningful"
    assert "zero or negative" in f["net_margin_fy"]["why"]
    loss = figs(quote={"forward_eps": -1.2})["forward_pe"]
    assert loss["status"] == "not_meaningful" and loss["value"] is None and "loss per share" in loss["why"]
    none = figs(quote={"forward_eps": None})["forward_pe"]
    assert none["status"] == "not_reported"
    gone = figs(quote={"price": None})["forward_pe"]
    assert gone["status"] == "unavailable" and gone["text"] == "Temporarily unavailable"


def test_with_no_quarter_since_the_10k_the_twelve_months_are_the_year_and_say_so():
    fl = filings({"Revenues": (USD, [fact(400.0, "2026-09-26", "2025-09-28")]),
                  "NetIncomeLoss": (USD, [fact(110.0, "2026-09-26", "2025-09-28")]),
                  "Assets": (USD, [fact(900.0, "2026-09-26")]),
                  "CashAndCashEquivalentsAtCarryingValue": (USD, [fact(36.0, "2026-09-26")])})
    t = figs(fl)["net_margin_ttm"]
    assert t["text"] == figs(fl)["net_margin_fy"]["text"] == "27.5%"
    assert t["period"]["label"] == "12 months to Sep 26, 2026" and "no quarter has been reported since" in t["period"]["detail"]


def test_a_fund_and_an_unreachable_source_say_why_figure_by_figure():
    fund = figures.resolve("SPY", {"price": 600.0, "quote_type": "ETF"}, sec=(None, None, "x"), financials=None)["figures"]
    assert all(fv["status"] == "not_reported" and "not a company" in fv["why"] for k, fv in fund.items() if k != "forward_pe")
    down = figures.unavailable("ACME", "EDGAR did not answer.")
    assert down["available"] is False and all(fv["status"] == "unavailable" for fv in down["figures"].values())


def test_the_money_text_matches_the_clients_compact_rounding():
    assert res.money_text(136.06e9) == "$136.1B" and res.money_text(1.234e12) == "$1.23T"
    assert res.money_text(-24.8e9) == "−$24.8B" and res.money_text(999_950_000) == "$1.0B"
    assert res.text_for("percent", -12.34) == "−12.3%" and res.text_for("multiple", 31.07) == "31.1"


# ------------------------------------------------------------------------------------------------ the CI check
# A financial figure rendered on v2 must come from the registry. Two ways round it would be a page reading one of these
# raw fields out of a payload itself, or naming a figure id the registry does not have. Both fail here.
FIELDS = r"forward_pe|profit_margin|net_pct|net_cash|net_debt|free_cash_flow|operating_cash_flow"
RAW = re.compile(r"(?<!figures)(?<!figures \|\| \{\}\))\.(" + FIELDS + r")\b")
# core/figures.js strips these fields from what Milo is sent; the Financials tab and Milo's charts plot fiscal-year
# history series, each bar labelled with its year (registering the series is the backfill's next step,
# docs/claude-handoffs/HANDOFF-1-figure-registry.md)
ALLOWED = {"core/figures.js": {"forward_pe", "profit_margin", "net_pct", "net_cash"},
           "pages/financials.js": {"free_cash_flow", "operating_cash_flow"},
           "ui/finfigs.js": {"free_cash_flow", "operating_cash_flow"}}
USE = [re.compile(r"(?:FIG|F)\.of\([^()]*?,\s*'([a-z_]+)'\)"), re.compile(r"regFig\('([a-z_]+)'\)"),
       re.compile(r"\breg\('([a-z_]+)'\)"), re.compile(r"data-v2-fig=\"([a-z_]+)\"")]


def raw_reads(root=V2JS):
    out = []
    for p in sorted(root.rglob("*.js")):
        rel = p.relative_to(root).as_posix()
        for m in RAW.finditer(p.read_text()):
            if m.group(1) not in ALLOWED.get(rel, set()):
                out.append("{}: .{}".format(rel, m.group(1)))
    return out


def ids_used(root=V2JS):
    out = set()
    for p in sorted(root.rglob("*.js")):
        s = p.read_text()
        for rx in USE:
            out.update(rx.findall(s))
    return out


def test_no_v2_page_prints_one_of_these_figures_from_a_raw_field():
    assert raw_reads() == [], "print the registry's figure (core/figures.js FIG.of, ui/figure.js fig) instead"


def test_every_figure_a_page_names_is_in_the_registry():
    used = ids_used()
    assert used, "the pattern found the pages' figure ids"
    assert used <= set(reg.IDS), sorted(used - set(reg.IDS))


def test_the_check_catches_a_new_unregistered_figure_and_a_raw_read(tmp_path):
    """The check itself, against a page written the wrong way twice (the repo's rule: a test is shown to catch what it
    names before it is trusted)."""
    (tmp_path / "pages").mkdir()
    (tmp_path / "pages" / "new.js").write_text(
        "const a = FIG.of(t, 'gross_margin_fy');\nconst b = `${num(q.forward_pe, 1)}`;\nconst c = (h.figures || {}).forward_pe;\n")
    assert raw_reads(tmp_path) == ["pages/new.js: .forward_pe"], "a raw read is caught; a read through figures is not"
    assert "gross_margin_fy" in ids_used(tmp_path) and "gross_margin_fy" not in reg.IDS


def test_the_server_resolves_exactly_the_registered_ids_and_nothing_else():
    assert list(block()["figures"]) == list(reg.IDS)
    for fv in block()["figures"].values():
        assert set(fv) >= {"id", "name", "status", "value", "text", "unit", "period", "as_of", "inputs", "source",
                           "restatement"}, fv["id"]


# ------------------------------------------------------------------------------------------------ the routes
def test_the_routes_serve_the_registry_and_a_companys_figures(monkeypatch):
    from fastapi.testclient import TestClient
    from app import main
    monkeypatch.setattr(main.figures_mod, "for_ticker", lambda provider, sym, yf=None, quote=None: block())
    client = TestClient(main.app)
    r = client.get("/api/figures/registry")
    assert r.status_code == 200 and r.json()["levels"][0] == "new", "the registry, not a ticker called REGISTRY"
    assert "max-age=3600" in r.headers.get("cache-control", "")
    f = client.get("/api/figures/acme").json()
    assert f["figures"]["net_debt"]["text"] == "$85" and f["statement_source"]["provider"] == "SEC EDGAR"
    src = (ROOT / "app/main.py").read_text()
    assert src.index('@app.get("/api/figures/registry")') < src.index('@app.get("/api/figures/{ticker}")')
    assert "include_figures=True, budget=budget, parallel=True" in src, "the Dossier's snapshot carries them"
    assert "include_earnings=False, include_figures=True)" in src, "and Compare's"


# ------------------------------------------------------------------------------------------------ the page side
def test_the_control_and_the_panel(tmp_path):
    got = _run(tmp_path, f"""
      const FG = await import('{(V2JS / "ui/figure.js").as_posix()}');
      const fv = {json.dumps(block()["figures"]["net_debt"])};
      print(JSON.stringify({{ btn: String(FG.fig(fv, {{ sym: 'acme' }}).s), name: String(FG.figName(fv, 'Net debt', {{ sym: 'ACME' }}).s),
        none: String(FG.fig(null).s) }}));
    """)
    assert 'data-v2-fig="net_debt"' in got["btn"] and 'data-v2-fig-sym="ACME"' in got["btn"] and ">$85</button>" in got["btn"]
    assert 'aria-haspopup="dialog"' in got["btn"] and 'aria-label="Net debt: $85. Show how it is defined"' in got["btn"]
    assert 'data-v2-fig="net_debt"' in got["name"] and ">Net debt</button>" in got["name"], "the label opens the same panel"
    assert got["none"] == '<span class="fig-missing">Not reported</span>', "a missing figure says so, never a blank"
    src = (V2JS / "ui/figure.js").read_text()
    for need in ("Definition unavailable.", "The definition could not be loaded just now.", "Retry",
                 "Restatement history unavailable from this source.", "What it cannot tell you", "Open the filing",
                 "(max-width: 559px)", "is-sheet", "Explain this with Milo", "e.key === 'Escape'", "focus({ preventScroll: true })"):
        assert need in src, need
    # the handoff's error states: a registry that cannot be read marks every figure; a figure that could not be worked
    # out offers a retry, which asks for the company's figures again rather than showing an older value
    core = (V2JS / "core/figures.js").read_text()
    assert "document.documentElement.dataset.figRegistry = 'failed'" in core
    assert "class=\"btn btn-sm fig-refetch\"" in src and "api.get(`/api/figures/${encodeURIComponent(sym)}`, { force: true" in src
    css = (ROOT / "static/v2/css/components.css").read_text()
    assert ':root[data-fig-registry="failed"] .fig:not(.fig-name)::after { content: " (definition unavailable)";' in css
    assert ".fig-pop.is-sheet { position: fixed; top: auto; right: 0; bottom: 0; left: 0;" in css, "a bottom sheet on a phone"
    assert ".fig:focus-visible" in css and "font-variant-numeric: tabular-nums" in css.split(".fig {", 1)[1].split("}", 1)[0]


def test_milos_research_pack_carries_the_registry_figures_in_place_of_its_own():
    """The pack Milo answers from (app/desk/research.py) printed its own net margin, cash flows, a net cash of cash
    and equivalents less debt, and the feed's forward P/E; with the registry it carries the registry's text, each
    item tagged with its id, and none of its own copies."""
    from app.desk import research

    class Provider:
        def quote(self, sym):
            return dict(QUOTE)

        def financials(self, sym):
            per = {"periods": ["2025-12-31"]}
            return {"income_annual": dict(per, rows={"Total Revenue": [400.0], "Net Income": [70.0], "Gross Profit": [200.0],
                                                     "Operating Income": [100.0]}),
                    "cashflow_annual": dict(per, rows={"Operating Cash Flow": [110.0], "Capital Expenditure": [-25.0],
                                                       "Free Cash Flow": [85.0]}),
                    "balance_annual": dict(per, rows={"Total Debt": [160.0], "Cash And Cash Equivalents": [45.0]})}

    p = research.Pack("company", "ACME")
    d = research.Deps(provider=Provider(), figures=lambda t: block())
    research.fundamentals(p, d, "ACME")
    research.valuation(p, d, "ACME")
    items = {i["label"]: i for i in p.items}
    want = block()["figures"]
    for fid in ("net_margin_fy", "free_cash_flow_fy", "operating_cash_flow_fy", "net_debt", "forward_pe"):
        item = next(i for i in p.items if i.get("figure_id") == fid)
        assert item["value"] == want[fid]["text"] and item["label"] == want[fid]["name"], fid
    for own in ("Net margin", "Free cash flow", "Operating cash flow", "Net cash (cash minus debt)", "Forward P/E"):
        assert own not in items or items[own].get("figure_id"), own
    # without the registry the pack keeps its own lines, as before
    q = research.Pack("company", "ACME")
    research.fundamentals(q, research.Deps(provider=Provider()), "ACME")
    assert "Net cash (cash minus debt)" in {i["label"] for i in q.items}
