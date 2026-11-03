"""Insider trades Yahoo's list leaves out, filled from SEC Form 4s (app/insider_fill.py, app/form4_store.py).

Yahoo's insider list stops at its 150 latest rows, so for a company that files many awards the chart's two years
were short and the older purchases never reached it: UNH's list began on 2025-06-24 (146 awards, 4 sales) and the
executives' May 2025 purchases were not in Optic (2026-11-03). Nothing here touches the network: the SEC's answers
are recorded shapes and the store is a temporary database.
"""
from __future__ import annotations

import datetime as dt
import json

import pytest

from app import form4_store, insider_fill as F
from app.analytics import fundamentals

TODAY = dt.date(2026, 11, 3)
SINCE = "2024-11-03"


@pytest.fixture(autouse=True)
def store(tmp_path, monkeypatch):
    monkeypatch.setattr(form4_store, "DB_PATH", str(tmp_path / "form4.db"))
    started = []
    monkeypatch.setattr(F, "start", lambda ticker, until: started.append((ticker, until)) or True)
    monkeypatch.setattr(F.time, "sleep", lambda s: None)
    return started


def yahoo(n=150, oldest="2025-06-24", purchase_on=None):
    """A Yahoo list of `n` rows, newest first, ending on `oldest`: awards, and one sale."""
    rows = [{"insider": "DIRECTOR {}".format(i), "position": "Director", "date": "2026-10-01", "shares": 10.0,
             "value": None, "action": "other", "detail": "Stock Award(Grant) at price 0.00 per share."} for i in range(n - 2)]
    rows.append({"insider": "SELLER", "position": "Officer", "date": "2026-09-01", "shares": 5.0, "value": 500.0,
                 "action": "sale", "detail": "Sale at price 100.00 per share."})
    rows.append({"insider": "LAST", "position": "Director", "date": oldest, "shares": 1.0, "value": None,
                 "action": "other", "detail": "Stock Award(Grant) at price 0.00 per share."})
    return {"summary_6m": {}, "transactions": rows}


def keep_list(filings, reaches="2010-08-01", fetched_at=None):
    form4_store.save_list("UNH", "731766", filings, reaches)
    if fetched_at:
        import sqlite3
        with sqlite3.connect(form4_store.DB_PATH) as c:
            c.execute("UPDATE form4_lists SET fetched_at = ?", (fetched_at,))


def purchase(date, shares, price, insider="HEMSLEY STEPHEN J", issuer="731766"):
    return {"available": True, "issuer_cik": issuer, "insider": insider, "roles": ["Director", "Chief Executive Officer"],
            "trades": [{"date": date, "code": "P", "shares": shares, "value": round(shares * price, 2), "price": price}]}


def test_a_list_short_of_150_rows_or_reaching_two_years_back_is_left_alone(store):
    short = yahoo(n=40)
    assert F.gap(short["transactions"], TODAY) is None and F.complete("UNH", short, TODAY) is short
    whole = yahoo(oldest="2024-10-01")
    assert F.gap(whole["transactions"], TODAY) is None and F.complete("UNH", whole, TODAY) is whole
    assert store == [], "nothing to read"
    assert F.gap(yahoo()["transactions"], TODAY) == (SINCE, "2025-06-24")


def test_the_stretch_before_yahoos_list_is_filled_from_kept_filings(store):
    keep_list([["0000731766-25-000150", "2025-05-20"], ["0000731766-25-000140", "2025-05-16"],
               ["0001-25-000100", "2025-03-10"], ["0000731766-24-000900", "2024-10-01"]])
    form4_store.save("0000731766-25-000150", "731766", purchase("2025-05-16", 86700, 288.57))
    form4_store.save("0000731766-25-000140", "731766", purchase("2025-05-15", 1000, 290.0, insider="REX JOHN F"))
    # a filing the company made as the owner of another issuer's shares is not an insider trade in it
    form4_store.save("0001-25-000100", "731766", purchase("2025-03-10", 50, 10.0, issuer="999"))
    got = F.complete("UNH", yahoo(), TODAY)
    sec = [r for r in got["transactions"] if r.get("source") == "sec"]
    assert [(r["date"], r["action"], r["insider"]) for r in sec] == [("2025-05-16", "purchase", "HEMSLEY STEPHEN J"),
                                                                    ("2025-05-15", "purchase", "REX JOHN F")]
    assert sec[0]["value"] == pytest.approx(86700 * 288.57) and sec[0]["position"] == "Director, Chief Executive Officer"
    assert sec[0]["detail"] == "Purchase at price 288.57 per share, from the Form 4 filed with the SEC."
    dates = [r["date"] for r in got["transactions"]]
    assert dates == sorted(dates, reverse=True) and len(got["transactions"]) == 152, "Yahoo's rows kept as they were"
    assert got["coverage"] == {"since": SINCE, "yahoo_from": "2025-06-24", "yahoo_rows": 150, "sec_rows": 2,
                               "sec_filings": 3, "sec_unread": 0, "listed": True, "complete": True}, \
        "the 2024-10-01 filing is before the two years and not counted"
    assert store == [], "a fresh list, every filing in the stretch read: nothing to start"


def test_unread_filings_or_a_missing_list_start_the_reader_and_a_whole_fresh_one_does_not(store):
    got = F.complete("UNH", yahoo(), TODAY)
    assert got["coverage"]["listed"] is False and store == [("UNH", "2025-06-24")]
    store.clear()
    now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    keep_list([["0000731766-25-000150", "2025-05-20"]], fetched_at=now)
    got = F.complete("UNH", yahoo(), TODAY)
    assert got["coverage"]["sec_unread"] == 1 and got["coverage"]["complete"] is False and store
    store.clear()
    form4_store.save("0000731766-25-000150", "731766", {"available": False, "reason": "no ownership document"})
    got = F.complete("UNH", yahoo(), TODAY)
    assert got["coverage"]["complete"] is True and store == [], "every filing read, a failure kept as read"


def test_complete_makes_no_request(monkeypatch):
    monkeypatch.setattr(F.feeds, "fetch_text", lambda *a, **k: pytest.fail("the page's request reads the store only"))
    F.complete("UNH", yahoo(), TODAY)


def test_the_six_month_counts_say_when_they_are_a_floor():
    rows = yahoo(oldest="2026-06-01")["transactions"]
    assert fundamentals._six_month_trades(rows, TODAY)["complete"] is False, "Yahoo's 150 rows start inside the six months"
    assert fundamentals._six_month_trades(rows[:40], TODAY)["complete"] is True
    cov = {"yahoo_from": "2026-06-01", "complete": True}
    assert fundamentals._six_month_trades(rows, TODAY, cov)["complete"] is True, "the SEC filings cover the rest"
    assert fundamentals._six_month_trades(rows, TODAY, dict(cov, complete=False))["complete"] is False
    assert fundamentals._six_month_trades(rows, TODAY, {"yahoo_from": "2025-06-24", "complete": False})["complete"] is True


def test_the_company_block_carries_the_filled_trades_and_the_coverage(monkeypatch):
    keep_list([["0000731766-25-000150", "2025-05-20"]])
    form4_store.save("0000731766-25-000150", "731766", purchase("2025-05-16", 86700, 288.57))

    class Provider:
        def insiders(self, t): return yahoo()
        def institutions(self, t): return {}
        def short_interest(self, t): return {}
        def financials(self, t): return {}
        def earnings_history(self, t): return {}
    monkeypatch.setattr(F, "_today", lambda: TODAY)
    own = fundamentals.analyse(Provider(), "UNH", {})["ownership"]
    assert own["recent_transactions"][-1]["source"] == "sec" and own["recent_transactions"][-1]["action"] == "purchase"
    assert own["insider_coverage"]["sec_rows"] == 1
    assert "the SEC's own Form 4 filings for the rest" in own["insider_method"]


def test_a_filing_is_kept_as_its_open_market_trades_one_per_day_and_code():
    parsed = {"available": True, "issuer_cik": "731766", "insider": "HEMSLEY STEPHEN J", "roles": ["Director"],
              "transactions": [
                  {"kind": "share", "code": "P", "date": "2025-05-16", "shares": 60000.0, "price": 288.0, "value": 17280000.0},
                  {"kind": "share", "code": "P", "date": "2025-05-16", "shares": 26700.0, "price": 290.0, "value": 7743000.0},
                  {"kind": "share", "code": "A", "date": "2025-05-16", "shares": 500.0, "price": 0.0, "value": None},
                  {"kind": "derivative", "code": "P", "date": "2025-05-16", "shares": 9.0, "price": 1.0, "value": 9.0},
                  {"kind": "share", "code": "S", "date": "2025-05-19", "shares": 10.0, "price": None, "value": None}]}
    got = F.compact(parsed)
    trades = {(t["date"], t["code"]): t for t in got["trades"]}
    assert set(trades) == {("2025-05-16", "P"), ("2025-05-19", "S")}, "awards and derivative lines are not trades"
    assert trades[("2025-05-16", "P")]["shares"] == 86700 and trades[("2025-05-16", "P")]["value"] == 25023000.0
    assert trades[("2025-05-16", "P")]["price"] == pytest.approx(25023000.0 / 86700)
    assert trades[("2025-05-19", "S")]["value"] is None and trades[("2025-05-19", "S")]["price"] is None, "no price, no value"
    assert F.compact({"available": False, "reason": "unparsable"}) == {"available": False, "reason": "unparsable"}


def test_the_list_reads_older_pages_only_while_they_reach_into_the_two_years(monkeypatch):
    asked = []
    recent = {"accessionNumber": ["a-26", "a-25", "q-25"], "form": ["4", "4/A", "10-Q"],
              "filingDate": ["2026-10-01", "2025-06-01", "2025-05-01"]}
    pages = {"CIK0000731766-submissions-001.json": {"accessionNumber": ["a-24"], "form": ["4"], "filingDate": ["2024-12-01"]}}

    def fetch(url, ttl, **kw):
        asked.append(url)
        assert kw.get("store") is False, "the shared feed cache keeps sixty entries; these are not kept there"
        name = url.rsplit("/", 1)[1]
        return json.dumps(pages[name] if name in pages else {"filings": {"recent": recent, "files": [
            {"name": "CIK0000731766-submissions-001.json", "filingFrom": "2024-06-01", "filingTo": "2025-04-30"},
            {"name": "CIK0000731766-submissions-002.json", "filingFrom": "2020-01-01", "filingTo": "2024-05-31"}]}})
    monkeypatch.setattr(F.feeds, "fetch_text", fetch)
    from app.analytics import sec_facts
    monkeypatch.setattr(sec_facts, "cik_for", lambda t: "0000731766")
    got = F.list_filings("UNH", SINCE)
    assert got == {"cik": "731766", "filings": [["a-26", "2026-10-01"], ["a-25", "2025-06-01"], ["a-24", "2024-12-01"]],
                   "reaches": "2024-05-31"}
    assert len(asked) == 2 and not any(u.endswith("-002.json") for u in asked), "a page ending before the two years is not read"
    monkeypatch.setattr(sec_facts, "cik_for", lambda t: None)
    assert F.list_filings("NOPE", SINCE) is None


def test_the_reader_reads_newest_first_within_its_budget_and_stops_when_refused(monkeypatch):
    keep_list([["0000731766-25-00015{}".format(i), "2025-05-{:02d}".format(20 - i)] for i in range(6)],
              reaches="2010-08-01", fetched_at=dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"))
    read = []

    def parse(index_url, acc, store=True):
        assert store is False and index_url == "https://www.sec.gov/Archives/edgar/data/731766/{}/{}-index.htm".format(
            acc.replace("-", ""), acc)
        read.append(acc)
        return {"available": True, "issuer_cik": "731766", "insider": "X", "roles": [], "transactions": []}
    monkeypatch.setattr(F.insiders_mod, "parse_filing", parse)
    got = F.fill("UNH", "2025-06-24", budget=4, today=TODAY)
    assert got["read"] == 4 and read == ["0000731766-25-00015{}".format(i) for i in range(4)]
    assert len(form4_store.load_many(read)) == 4
    read.clear()

    def refuse(index_url, acc, store=True):
        read.append(acc)
        raise OSError("403")
    monkeypatch.setattr(F.insiders_mod, "parse_filing", refuse)
    form4_store.save_list("UNH", "731766", [["r-{}".format(i), "2025-05-01"] for i in range(9)], "2010-08-01")
    got = F.fill("UNH", "2025-06-24", today=TODAY)
    assert got["failed"] == 3 and len(read) == 3, "three refusals in a row and it stops; the next visit resumes"
    assert form4_store.load_many(read) == {}, "a refusal is not kept as a failed parse"


def test_the_reader_can_be_switched_off(monkeypatch, store):
    monkeypatch.setattr(F, "ENABLED", False)
    F.complete("UNH", yahoo(), TODAY)
    assert store == []
