"""ETF look-through from SEC N-PORT, and the exposure built on it.

The fixtures under tests/fixtures/nport are real EDGAR responses fetched on
2026-10-15, trimmed to a few holdings with their structure, namespaces and
numbers untouched. Two edits, both named where they are made: the SPY
document's Berkshire row carries a `BRK/B` ticker in the form Direxion files
them (no other fund measured carried one), and fund tests that need a
different name or direction change the bytes in memory.

What these pin down: percentages, countries, currencies and how each ticker
was found; the residual rows that make a fund add to 100; the week-long
cache and the stale copy served when SEC refuses; leveraged, inverse, stock
and commodity symbols refused with a reason; and exposure arithmetic that
redistributes fund value without ever adding to the total.

Nothing here touches the network except the one test that needs
OPTIC_LIVE_EDGAR=1.
"""

from __future__ import annotations

import gzip
import io
import json
import os
import re
from datetime import datetime, timedelta, timezone

import pytest

from app.brokerage import exposure, lookthrough as L

FIX = os.path.join(os.path.dirname(__file__), "fixtures", "nport")
NOW = datetime(2026, 10, 15, 16, 0, tzinfo=timezone.utc)

QQQ_DOC = "https://www.sec.gov/Archives/edgar/data/1067839/000106783926000030/primary_doc.xml"
QQQ_OLDER_DOC = "https://www.sec.gov/Archives/edgar/data/1067839/000106783926000024/primary_doc.xml"
SPY_DOC = "https://www.sec.gov/Archives/edgar/data/884394/000141036826089410/primary_doc.xml"
TQQQ_DOC = "https://www.sec.gov/Archives/edgar/data/1174610/000207169126017348/primary_doc.xml"
EWG_DOC = "https://www.sec.gov/Archives/edgar/data/930667/000100472626006446/primary_doc.xml"

ROUTES = {
    L.MF_TICKERS_URL: "company_tickers_mf.json",
    L.CO_TICKERS_URL: "company_tickers.json",
    L.SERIES_FEED_URL.format(series="S000101292"): "qqq_feed.atom",
    L.SERIES_FEED_URL.format(series="S000024908"): "tqqq_feed.atom",
    L.SERIES_FEED_URL.format(series="S000004269"): "ewg_feed.atom",
    L.SUBMISSIONS_URL.format(cik=884394): "spy_submissions.json",
    L.SUBMISSIONS_URL.format(cik=320193): "aapl_submissions.json",
    L.SUBMISSIONS_URL.format(cik=1222333): "gld_submissions.json",
    QQQ_DOC: "qqq_primary_doc.xml",
    SPY_DOC: "spy_primary_doc.xml",
    TQQQ_DOC: "tqqq_primary_doc.xml",
    EWG_DOC: "ewg_primary_doc.xml",
}


def fixture_bytes(name: str) -> bytes:
    with open(os.path.join(FIX, name), "rb") as fh:
        return fh.read()


class Edgar:
    """A stand-in for EDGAR that answers from the fixtures and logs each call."""

    def __init__(self, override=None, down=False):
        self.calls = []
        self.override = override or {}
        self.down = down

    def __call__(self, url, *, max_bytes, timeout):
        self.calls.append(url)
        if self.down:
            raise L.FetchFailed("SEC answered 403")
        if url in self.override:
            return self.override[url]
        if url not in ROUTES:
            raise L.FetchFailed("SEC answered 404")
        return fixture_bytes(ROUTES[url])


@pytest.fixture(autouse=True)
def _fresh_directory_memo(monkeypatch):
    # The parsed ticker directories are memoised per path; each test has its
    # own tmp_path, and clearing keeps one test's copy out of another's.
    monkeypatch.setattr(L, "_MAP_MEMO", {})


def by_name(result, name):
    return next(h for h in result["holdings"] if h["name"] == name)


def fixture_pcts(name):
    return [float(x) for x in re.findall(r"<pctVal>(.*?)</pctVal>", fixture_bytes(name).decode())]


# ---------------------------------------------------------------- parsing

def test_qqq_holdings_dates_and_source(tmp_path):
    edgar = Edgar()
    r = L.constituents("qqq", fetch=edgar, cache_dir=str(tmp_path), now=NOW)
    assert r["available"] is True and r["status"] == "ok"
    assert r["symbol"] == "QQQ"
    assert r["fund_name"] == "Invesco QQQ Trust, Series 1"
    assert r["series_id"] == "S000101292"
    # repPdDate, not repPdEnd: the filing's repPdEnd is 2026-09-30, the
    # fiscal year end, and is not the date the holdings are as of.
    assert r["report_date"] == "2026-06-30"
    assert r["filed"] == "2026-08-28"
    assert r["source"] == "SEC Form N-PORT"
    assert r["source_url"].endswith("/1067839/000106783926000030/0001067839-26-000030-index.htm")
    assert r["rows_total"] == 9 and r["rows_kept"] == 9
    assert r["report_age_days"] == 107
    assert any("2026-06-30" in n and "not today's holdings" in n for n in r["notes"])
    # The newest original filing's own document, and no older one.
    assert QQQ_DOC in edgar.calls and QQQ_OLDER_DOC not in edgar.calls

    nvda = by_name(r, "NVIDIA Corp.")
    assert nvda["pct"] == pytest.approx(7.5968, abs=1e-4)
    assert nvda["value_usd"] > 3.7e10
    assert (nvda["country"], nvda["currency"]) == ("US", "USD")
    assert (nvda["asset_category"], nvda["asset_class"], nvda["issuer_category"]) == ("EC", "equity", "CORP")
    assert nvda["cusip"] == "67066G104" and nvda["isin"] == "US67066G1040"
    assert (nvda["ticker"], nvda["ticker_source"], nvda["ticker_confidence"]) == ("NVDA", "sec_name", "medium")

    assert by_name(r, "ASML Holding N.V.")["country"] == "NL"
    assert by_name(r, "ASML Holding N.V.")["ticker"] == "ASML"
    # "Amazon.com, Inc." against SEC's "AMAZON COM INC": a spacing difference.
    assert by_name(r, "Amazon.com, Inc.")["ticker"] == "AMZN"


def test_share_class_not_in_the_filing_is_said_not_guessed(tmp_path):
    r = L.constituents("QQQ", fetch=Edgar(), cache_dir=str(tmp_path), now=NOW)
    alphabet = [h for h in r["holdings"] if h["name"] == "Alphabet Inc."]
    assert len(alphabet) == 2
    for h in alphabet:
        # Class A is GOOGL and Class C is GOOG, and nothing in the filing or
        # SEC's directory links the letter to the ticker. Both rows get the
        # company's main line and say the class is not known.
        assert h["ticker"] == "GOOGL"
        assert h["share_class_known"] is False
        assert h["issuer_tickers"] == ["GOOGL", "GOOG"]
        assert h["cik"] == 1652044


def test_futures_ticker_and_cash_rows_are_not_stocks(tmp_path):
    r = L.constituents("QQQ", fetch=Edgar(), cache_dir=str(tmp_path), now=NOW)
    fut = by_name(r, "CME E-Mini NASDAQ 100 Index Future")
    # The filing carries NQU6 as this row's ticker; it is a futures contract.
    assert fut["asset_category"] == "DE" and fut["derivative"] == "future"
    assert fut["ticker"] is None
    cash = by_name(r, "Invesco Private Prime Fund")
    assert cash["asset_class"] == "cash_like" and cash["ticker"] is None


def test_residual_row_makes_the_fund_add_to_100(tmp_path):
    r = L.constituents("QQQ", fetch=Edgar(), cache_dir=str(tmp_path), now=NOW)
    filed = sum(fixture_pcts("qqq_primary_doc.xml"))
    net = next(h for h in r["holdings"] if h.get("residual") == "net_other_assets")
    assert net["pct"] == pytest.approx(100.0 - filed, abs=1e-4)
    assert not any(h.get("residual") == "other_holdings" for h in r["holdings"])
    assert sum(h["pct"] for h in r["holdings"]) == pytest.approx(100.0, abs=1e-3)
    assert r["coverage_pct"] == pytest.approx(round(filed, 2))
    assert r["mix"]["asset_class"]["net_other_assets"] == pytest.approx(100.0 - filed, abs=1e-3)


def test_max_rows_folds_the_rest_into_other_holdings(tmp_path):
    r = L.constituents("QQQ", fetch=Edgar(), cache_dir=str(tmp_path), now=NOW, max_rows=3)
    listed = [h for h in r["holdings"] if not h.get("residual")]
    assert [h["name"] for h in listed] == ["NVIDIA Corp.", "Apple Inc.", "Microsoft Corp."]
    pcts = sorted(fixture_pcts("qqq_primary_doc.xml"), reverse=True)
    other = next(h for h in r["holdings"] if h.get("residual") == "other_holdings")
    assert other["rows"] == 6
    assert other["pct"] == pytest.approx(sum(pcts[3:]), abs=1e-4)
    assert r["rows_kept"] == 3 and r["rows_total"] == 9
    assert r["coverage_pct"] == pytest.approx(round(sum(pcts[:3]), 2))
    assert sum(h["pct"] for h in r["holdings"]) == pytest.approx(100.0, abs=1e-3)
    # The whole-fund mix is over every row, not only the three listed.
    assert sum(r["mix"]["country"].values()) == pytest.approx(100.0, abs=1e-3)
    assert r["mix"]["country"]["NL"] == pytest.approx(0.7896, abs=1e-4)


def test_spy_is_a_trust_found_through_its_cik(tmp_path):
    edgar = Edgar()
    r = L.constituents("SPY", fetch=edgar, cache_dir=str(tmp_path), now=NOW)
    assert r["available"] is True
    # Not in SEC's fund directory at all: a unit investment trust has no series.
    assert L.SUBMISSIONS_URL.format(cik=884394) in edgar.calls
    assert r["series_id"] is None and r["cik"] == 884394
    assert r["fund_name"] == "State Street SPDR S&P 500 ETF Trust"
    assert r["report_date"] == "2026-06-30" and r["filed"] == "2026-08-28"

    brk = by_name(r, "Berkshire Hathaway Inc")
    assert (brk["ticker"], brk["ticker_source"], brk["ticker_confidence"]) == ("BRK-B", "filing", "high")
    # SEC conforms the name as "SCHWAB CHARLES CORP": a reordered match, weaker.
    schwab = by_name(r, "Charles Schwab Corp/The")
    assert (schwab["ticker"], schwab["ticker_source"], schwab["ticker_confidence"]) == \
        ("SCHW", "sec_name_reordered", "low")


def test_currency_country_and_no_invented_ticker(tmp_path):
    r = L.constituents("EWG", fetch=Edgar(), cache_dir=str(tmp_path), now=NOW)
    sap = by_name(r, "SAP SE")
    assert (sap["currency"], sap["country"], sap["ticker"]) == ("EUR", "DE", "SAP")
    siemens = by_name(r, "Siemens Aktiengesellschaft")
    # No SEC registrant has this name, so it has no ticker rather than a guess.
    assert siemens["ticker"] is None and siemens["ticker_source"] is None
    assert siemens["currency"] == "EUR"
    euro = by_name(r, "EURO")
    assert euro["asset_class"] == "cash_like" and euro["country"] is None
    dax = by_name(r, "DAX INDEX FUTURE JUN26")
    assert dax["ticker"] is None and dax["derivative"] == "future"
    assert r["mix"]["currency"]["EUR"] > 20 and "USD" in r["mix"]["currency"]
    assert r["leveraged"] is False and r["inverse"] is False


# --------------------------------------------------------------- refusals

def test_stock_symbol_refused_with_a_reason(tmp_path):
    edgar = Edgar()
    r = L.constituents("AAPL", fetch=edgar, cache_dir=str(tmp_path), now=NOW)
    assert r["available"] is False and r["status"] == "not_a_fund"
    assert "company's stock" in r["reason"] and "Apple Inc." in r["reason"]
    assert r["holdings"] == []
    assert not any("primary_doc" in u for u in edgar.calls)


def test_commodity_trust_refused_with_a_reason(tmp_path):
    r = L.constituents("GLD", fetch=Edgar(), cache_dir=str(tmp_path), now=NOW)
    assert r["available"] is False and r["status"] == "not_a_fund"
    assert "commodity trust" in r["reason"]


def test_unknown_symbol(tmp_path):
    r = L.constituents("ZZZZQ", fetch=Edgar(), cache_dir=str(tmp_path), now=NOW)
    assert r["available"] is False and r["status"] == "unknown_symbol"
    assert "ZZZZQ" in r["reason"]


def test_leveraged_fund_refused(tmp_path):
    r = L.constituents("TQQQ", fetch=Edgar(), cache_dir=str(tmp_path), now=NOW)
    assert r["available"] is False and r["status"] == "leveraged_or_inverse"
    assert r["leveraged"] is True and r["inverse"] is False
    assert r["holdings"] == []
    assert r["derivative_exposure_pct"] > 150
    assert "leveraged" in r["reason"] and "not the sum of what it holds" in r["reason"]
    # It still says which filing it read and when.
    assert r["fund_name"] == "ProShares UltraPro QQQ" and r["report_date"] == "2026-05-31"


def test_leverage_is_read_from_the_filing_not_only_the_name(tmp_path):
    doc = fixture_bytes("tqqq_primary_doc.xml").replace(b"ProShares UltraPro QQQ", b"ProShares Nasdaq Fund")
    r = L.constituents("TQQQ", fetch=Edgar({TQQQ_DOC: doc}), cache_dir=str(tmp_path), now=NOW)
    assert L.name_flags("ProShares Nasdaq Fund") == (False, False)
    assert r["status"] == "leveraged_or_inverse" and r["leveraged"] is True
    assert "its name says so" not in r["reason"]


def test_inverse_is_read_from_short_derivatives(tmp_path):
    doc = fixture_bytes("tqqq_primary_doc.xml").decode().replace("ProShares UltraPro QQQ", "ProShares Nasdaq Fund")
    # ProShares writes a short swap as a negative notional and a short future
    # as payOffProf Short (SQQQ, 2026-05-31).
    doc = re.sub(r"<notionalAmt>(\d)", r"<notionalAmt>-\1", doc).replace(
        "<payOffProf>Long</payOffProf>", "<payOffProf>Short</payOffProf>")
    r = L.constituents("TQQQ", fetch=Edgar({TQQQ_DOC: doc.encode()}), cache_dir=str(tmp_path), now=NOW)
    assert r["inverse"] is True and r["available"] is False


@pytest.mark.parametrize("name,flags", [
    ("ProShares UltraPro QQQ", (True, False)),
    ("ProShares UltraPro Short QQQ", (True, True)),
    ("ProShares UltraShort S&P500", (True, True)),
    ("Direxion Daily S&P 500 Bull 3X Shares", (True, False)),
    ("Direxion Daily S&P 500 Bear 1X Shares", (False, True)),
    ("Invesco QQQ Trust, Series 1", (False, False)),
    ("iShares Short Treasury Bond ETF", (False, False)),
    ("JPMorgan Ultra-Short Income ETF", (False, False)),
    ("Invesco Ultra Short Duration ETF", (False, False)),
])
def test_name_flags(name, flags):
    assert L.name_flags(name) == flags


def test_a_filing_for_another_series_is_never_shown(tmp_path):
    other = fixture_bytes("ewg_primary_doc.xml")
    edgar = Edgar({QQQ_DOC: other, QQQ_OLDER_DOC: other})
    r = L.constituents("QQQ", fetch=edgar, cache_dir=str(tmp_path), now=NOW)
    assert r["available"] is False and r["status"] == "unverified"
    assert "S000004269" in r["reason"]


def test_oversized_document_is_refused(tmp_path, monkeypatch):
    monkeypatch.setattr(L, "MAX_DOC_BYTES", 2000)
    r = L.constituents("QQQ", fetch=Edgar(), cache_dir=str(tmp_path), now=NOW)
    assert r["available"] is False and r["status"] == "too_large"


def test_original_filing_preferred_over_a_later_amendment():
    filings = [{"form": "NPORT-P/A", "filed": "2026-09-30", "accession": "a"},
               {"form": "NPORT-P", "filed": "2026-08-28", "accession": "b"},
               {"form": "NPORT-P", "filed": "2026-05-28", "accession": "c"}]
    assert [f["accession"] for f in L._ordered(filings)] == ["b", "c", "a"]


# ------------------------------------------------------------------ cache

def test_cache_answers_within_a_week_without_sec(tmp_path):
    first = L.constituents("QQQ", fetch=Edgar(), cache_dir=str(tmp_path), now=NOW)
    assert os.path.exists(os.path.join(str(tmp_path), "QQQ.json"))
    edgar = Edgar(down=True)
    again = L.constituents("QQQ", fetch=edgar, cache_dir=str(tmp_path), now=NOW + timedelta(days=6))
    assert edgar.calls == []
    assert again["stale"] is False and again["holdings"] == first["holdings"]


def test_smaller_max_rows_is_served_from_the_cache(tmp_path):
    L.constituents("QQQ", fetch=Edgar(), cache_dir=str(tmp_path), now=NOW)
    edgar = Edgar(down=True)
    r = L.constituents("QQQ", fetch=edgar, cache_dir=str(tmp_path), now=NOW, max_rows=3)
    assert edgar.calls == []
    assert r["rows_kept"] == 3
    assert sum(h["pct"] for h in r["holdings"]) == pytest.approx(100.0, abs=1e-3)


def test_stale_copy_served_when_sec_refuses(tmp_path):
    L.constituents("QQQ", fetch=Edgar(), cache_dir=str(tmp_path), now=NOW)
    edgar = Edgar(down=True)
    r = L.constituents("QQQ", fetch=edgar, cache_dir=str(tmp_path), now=NOW + timedelta(days=8))
    assert edgar.calls, "a week-old copy must be refreshed, not served as fresh"
    assert r["available"] is True and r["stale"] is True
    assert r["report_date"] == "2026-06-30"
    assert any("403" in n and "copy Optic kept" in n for n in r["notes"])


def test_no_copy_and_no_sec_is_unavailable_and_not_kept(tmp_path):
    r = L.constituents("QQQ", fetch=Edgar(down=True), cache_dir=str(tmp_path), now=NOW)
    assert r["available"] is False and r["status"] == "unavailable"
    assert "could not be reached" in r["reason"]
    # A connection failure is not a fact about the fund: the next call tries.
    edgar = Edgar()
    again = L.constituents("QQQ", fetch=edgar, cache_dir=str(tmp_path), now=NOW)
    assert again["available"] is True and edgar.calls


def test_refusals_are_kept_too(tmp_path):
    L.constituents("AAPL", fetch=Edgar(), cache_dir=str(tmp_path), now=NOW)
    edgar = Edgar(down=True)
    r = L.constituents("AAPL", fetch=edgar, cache_dir=str(tmp_path), now=NOW + timedelta(days=1))
    assert edgar.calls == [] and r["status"] == "not_a_fund"


def test_default_cache_dir_follows_tracker_data_dir(monkeypatch, tmp_path):
    monkeypatch.setenv("TRACKER_DATA_DIR", str(tmp_path))
    assert L.default_cache_dir() == os.path.join(str(tmp_path), "lookthrough")


# ------------------------------------------------------------- the fetcher

class _FakeResponse:
    def __init__(self, body, headers):
        self._buf = io.BytesIO(body)
        self.headers = headers

    def read(self, n=-1):
        return self._buf.read(n)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_http_get_identifies_itself_unzips_and_caps(monkeypatch):
    seen = {}
    big = b"<x>" + b"a" * 300000 + b"</x>"

    def urlopen(req, timeout=None):
        seen["ua"] = req.get_header("User-agent")
        seen["enc"] = req.get_header("Accept-encoding")
        return _FakeResponse(gzip.compress(big), {"Content-Encoding": "gzip"})

    monkeypatch.setattr(L.urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(L.feeds, "POLITE_GAP_SECONDS", 0.0)
    assert L.http_get("https://www.sec.gov/x", max_bytes=10 ** 6, timeout=5) == big
    # SEC refuses a bare Name/Version token; app/feeds.py's form carries a URL.
    assert seen["ua"] == L.feeds.USER_AGENT and "http" in seen["ua"]
    assert seen["enc"] == "gzip"
    with pytest.raises(L.TooLarge):
        L.http_get("https://www.sec.gov/x", max_bytes=100000, timeout=5)


# --------------------------------------------------------------- exposure

def fund(rows, **extra):
    out = {"available": True, "status": "ok", "fund_name": "Test Fund", "report_date": "2026-06-30",
           "filed": "2026-08-28", "coverage_pct": 100.0, "rows_kept": len(rows), "rows_total": len(rows),
           "leveraged": False, "inverse": False, "holdings": rows}
    out.update(extra)
    return out


def stock(name, ticker, pct, **extra):
    row = {"name": name, "ticker": ticker, "pct": pct, "asset_category": "EC", "asset_class": "equity",
           "issuer_category": "CORP", "country": "US", "currency": "USD"}
    row.update(extra)
    return row


SECTORS = {"NVDA": "Technology", "AAPL": "Technology", "XOM": "Energy"}


def sector_of(t):
    return SECTORS.get(t)


def total(rows):
    return round(sum(r["value_usd"] for r in rows), 2)


def test_direct_and_fund_exposure_count_once():
    holdings = [{"symbol": "NVDA", "description": "NVIDIA", "kind": "equity", "currency": "USD", "value_usd": 1000.0},
                {"symbol": "FUND", "description": "A fund", "kind": "etf", "currency": "USD", "value_usd": 1000.0}]
    lt = {"FUND": fund([stock("NVIDIA Corp", "NVDA", 10.0), stock("Exxon Mobil Corp", "XOM", 60.0),
                        {"name": "Other holdings", "residual": "other_holdings", "pct": 30.0}])}
    r = exposure.build(holdings, lt, sector_of)
    assert r["version"] == "exposure-2026-10-15.1"
    assert r["long_value_usd"] == 2000.0
    nvda = next(c for c in r["companies"]["rows"] if c["ticker"] == "NVDA")
    assert (nvda["direct_usd"], nvda["indirect_usd"], nvda["total_usd"]) == (1000.0, 100.0, 1100.0)
    assert nvda["share_pct"] == 55.0 and nvda["flag"] is True
    assert nvda["via_funds"] == [{"symbol": "FUND", "value_usd": 100.0, "pct_of_fund": 10.0}]
    xom = next(c for c in r["companies"]["rows"] if c["ticker"] == "XOM")
    assert xom["total_usd"] == 600.0 and xom["share_pct"] == 30.0
    c = r["companies"]
    assert c["not_company_usd"] == 300.0
    assert round(c["shown_usd"] + c["other_companies_usd"] + c["not_company_usd"], 2) == 2000.0
    assert "never adds to the total" in c["no_double_counting"]
    assert any(f.startswith("NVDA is 55.00%") for f in c["flags"])

    s = r["sectors"]
    assert total(s["direct_only"]) == 2000.0 and total(s["look_through"]) == 2000.0
    look = {x["label"]: x["value_usd"] for x in s["look_through"]}
    assert look == {"Technology": 1100.0, "Energy": 600.0, "Fund holdings not itemised": 300.0}
    direct = {x["label"]: x["value_usd"] for x in s["direct_only"]}
    assert direct == {"Technology": 1000.0, "ETFs and funds (not looked through)": 1000.0}
    assert s["coverage_pct"] == 100.0 and s["unclassified_value"] == 0.0 and s["not_itemised_value"] == 300.0
    for key in ("asset_class", "issuer_country", "currency"):
        assert total(r[key]["rows"]) == pytest.approx(2000.0, abs=0.02), key


def test_a_fund_without_look_through_is_a_stated_gap():
    holdings = [{"symbol": "NVDA", "kind": "equity", "currency": "USD", "value_usd": 1000.0},
                {"symbol": "GLD", "kind": "etf", "currency": "USD", "value_usd": 1000.0}]
    lt = {"GLD": {"available": False, "status": "not_a_fund",
                  "reason": "GLD (SPDR GOLD TRUST) is a commodity trust."}}
    r = exposure.build(holdings, lt, sector_of)
    assert r["companies"]["rows"][0]["total_usd"] == 1000.0
    assert r["companies"]["rows"][0]["share_pct"] == 50.0
    assert r["companies"]["not_company_usd"] == 1000.0
    look = {x["label"]: x["value_usd"] for x in r["sectors"]["look_through"]}
    assert look == {"Technology": 1000.0, "Funds not looked through": 1000.0}
    assert r["sectors"]["not_itemised_value"] == 1000.0
    assert r["sectors"]["coverage_pct"] == 100.0
    gld = r["etfs"][0]
    assert gld["status"] == "unavailable" and "commodity trust" in gld["reason"]
    assert any("not looked through" in x and "50.00%" in x for x in r["limitations"])
    assert any("commodity trust" in x for x in r["limitations"])
    ac = {x["label"]: x["value_usd"] for x in r["asset_class"]["rows"]}
    assert ac["Funds not looked through"] == 1000.0


def test_leveraged_fund_counts_as_one_line():
    holdings = [{"symbol": "TQQQ", "kind": "etf", "currency": "USD", "value_usd": 500.0}]
    lt = {"TQQQ": {"available": False, "status": "leveraged_or_inverse", "leveraged": True, "inverse": False,
                   "reason": "TQQQ is leveraged.", "report_date": "2026-05-31"}}
    r = exposure.build(holdings, lt, sector_of)
    assert r["etfs"][0]["status"] == "leveraged_or_inverse" and r["etfs"][0]["leveraged"] is True
    assert r["companies"]["rows"] == [] and r["companies"]["not_company_usd"] == 500.0
    assert any("Leveraged or inverse funds (TQQQ)" in x for x in r["limitations"])


def test_share_classes_of_one_company_are_one_line():
    holdings = [{"symbol": "GOOG", "description": "Alphabet C", "kind": "equity", "currency": "USD",
                 "value_usd": 300.0},
                {"symbol": "FUND", "kind": "etf", "currency": "USD", "value_usd": 1000.0}]
    rows = [stock("Alphabet Inc.", "GOOGL", 4.0, cik=1652044, issuer_tickers=["GOOGL", "GOOG"]),
            stock("Alphabet Inc.", "GOOGL", 3.0, cik=1652044, issuer_tickers=["GOOGL", "GOOG"]),
            {"name": "Other holdings", "residual": "other_holdings", "pct": 93.0}]
    r = exposure.build(holdings, {"FUND": fund(rows)}, lambda t: "Communication Services")
    alphabet = [c for c in r["companies"]["rows"] if c["key"] == "cik:1652044"]
    assert len(alphabet) == 1
    assert alphabet[0]["ticker"] == "GOOG"           # the reader's own line
    assert (alphabet[0]["direct_usd"], alphabet[0]["indirect_usd"]) == (300.0, 70.0)


def test_lookups_go_to_the_largest_exposures_first():
    holdings = [{"symbol": "FUND", "kind": "etf", "currency": "USD", "value_usd": 1000.0}]
    rows = [stock("Small Co", "SMOL", 5.0), stock("Big Co", "BIG", 50.0), stock("Mid Co", "MID", 20.0),
            {"name": "Other holdings", "residual": "other_holdings", "pct": 25.0}]
    asked = []

    def lookup(t):
        asked.append(t)
        return "Industrials"

    r = exposure.build(holdings, {"FUND": fund(rows)}, lookup, max_lookups=2)
    assert asked == ["BIG", "MID"]
    s = r["sectors"]
    look = {x["label"]: x["value_usd"] for x in s["look_through"]}
    assert look["Industrials"] == 700.0 and look["Sector not known"] == 50.0
    assert s["unclassified_value"] == 50.0 and s["coverage_pct"] == pytest.approx(93.33)
    assert s["lookups_used"] == 2 and s["lookups_skipped"] == 1
    assert any("2 companies with the most value" in x for x in r["limitations"])


def test_a_lookup_that_raises_is_an_unknown_not_a_failure():
    holdings = [{"symbol": "NVDA", "kind": "equity", "currency": "USD", "value_usd": 100.0}]

    def boom(t):
        raise TimeoutError("profile timed out")

    r = exposure.build(holdings, {}, boom, country_of=boom)
    assert r["sectors"]["look_through"][0]["label"] == "Sector not known"
    assert r["issuer_country"]["rows"][0]["label"] == "Not known"


def test_breakdowns_from_real_filings_add_up(tmp_path):
    lt = {s: L.constituents(s, fetch=Edgar(), cache_dir=str(tmp_path), now=NOW) for s in ("QQQ", "EWG", "TQQQ")}
    holdings = [
        {"symbol": "NVDA", "description": "NVIDIA", "kind": "equity", "currency": "USD", "value_usd": 4000.0},
        {"symbol": "SHOP", "description": "Shopify", "kind": "equity", "currency": "CAD", "value_usd": 1000.0},
        {"symbol": "QQQ", "kind": "etf", "currency": "USD", "value_usd": 10000.0},
        {"symbol": "EWG", "kind": "etf", "currency": "USD", "value_usd": 3000.0},
        {"symbol": "TQQQ", "kind": "etf", "currency": "USD", "value_usd": 2000.0},
        {"symbol": "BTC", "kind": "crypto", "currency": "USD", "value_usd": 500.0},
        {"symbol": "TSLA", "kind": "equity", "currency": "USD", "value_usd": -700.0},
        {"symbol": "XYZ", "kind": "equity", "currency": "USD", "value_usd": None},
    ]
    r = exposure.build(holdings, lt, sector_of, country_of=lambda t: {"SHOP": "Canada"}.get(t),
                       cash_usd=1500.0, options_usd=250.0)
    long_value = 4000 + 1000 + 10000 + 3000 + 2000 + 500 + 250
    assert r["long_value_usd"] == long_value
    for key in ("issuer_country", "currency"):
        assert r[key]["total_usd"] == long_value
        assert total(r[key]["rows"]) == pytest.approx(long_value, abs=0.05), key
    assert r["asset_class"]["total_usd"] == long_value + 1500.0 and r["asset_class"]["includes_cash"] is True
    assert total(r["asset_class"]["rows"]) == pytest.approx(long_value + 1500.0, abs=0.05)
    for view in ("direct_only", "look_through"):
        assert total(r["sectors"][view]) == pytest.approx(long_value, abs=0.05), view
    c = r["companies"]
    assert c["shown_usd"] + c["other_companies_usd"] + c["not_company_usd"] == pytest.approx(long_value, abs=0.02)

    nvda = next(x for x in c["rows"] if x["ticker"] == "NVDA")
    assert nvda["indirect_usd"] == pytest.approx(10000 * 0.075968, abs=0.01)
    country = {x["label"]: x["value_usd"] for x in r["issuer_country"]["rows"]}
    assert country["Canada"] == 1000.0
    assert country["Germany"] == pytest.approx(3000 * (11.9738 + 9.4918 + 0.0096) / 100, abs=0.02)
    assert country["Netherlands"] == pytest.approx(10000 * 0.7896 / 100, abs=0.01)
    currency = {x["label"]: x["value_usd"] for x in r["currency"]["rows"]}
    assert currency["CAD"] == 1000.0 and currency["EUR"] > 600
    assert "not where revenue is earned" in r["issuer_country"]["basis"]
    assert r["issuer_country"]["label"] == "Where issuers are organised or located"
    assert "not economic currency exposure" in r["currency"]["basis"]

    status = {f["symbol"]: f["status"] for f in r["etfs"]}
    assert status == {"QQQ": "looked_through", "EWG": "looked_through", "TQQQ": "leveraged_or_inverse"}
    qqq = next(f for f in r["etfs"] if f["symbol"] == "QQQ")
    assert qqq["report_date"] == "2026-06-30" and qqq["rows_kept"] == 9
    text = " ".join(r["limitations"])
    for needle in ("Leveraged or inverse funds (TQQQ)", "2026-05-31 to 2026-06-30", "Revenue by country is not",
                   "Short positions (TSLA)", "No US dollar value was available for XYZ", "not delta-adjusted"):
        assert needle in text, needle


def test_no_em_dashes_in_reader_facing_text(tmp_path):
    lt = {s: L.constituents(s, fetch=Edgar(), cache_dir=str(tmp_path), now=NOW)
          for s in ("QQQ", "SPY", "TQQQ", "AAPL", "GLD", "ZZZZQ")}
    holdings = [{"symbol": s, "kind": "etf", "currency": "USD", "value_usd": 100.0} for s in lt]
    blob = json.dumps([lt, exposure.build(holdings, lt, sector_of)], ensure_ascii=False)
    assert "—" not in blob and "–" not in blob


# ------------------------------------------------------------------- live

@pytest.mark.skipif(os.environ.get("OPTIC_LIVE_EDGAR") != "1",
                    reason="reads EDGAR; set OPTIC_LIVE_EDGAR=1 to run")
def test_live_qqq(tmp_path):
    r = L.constituents("QQQ", cache_dir=str(tmp_path))
    assert r["available"] is True, r["reason"]
    assert r["series_id"] == "S000101292"
    assert r["rows_total"] > 90
    assert "NVDA" in {h["ticker"] for h in r["holdings"]}
    age = (datetime.now(timezone.utc).date() - datetime.strptime(r["report_date"], "%Y-%m-%d").date()).days
    assert 0 < age < 200
