"""Ownership and disclosures (backlog task 11, 2026-10-20): insider direction from open-market trades only,
amendments shown beside what they may correct, filing and trade dates kept apart, the visible scope said.

The server functions run on built records; the pages' wiring is read as text. The pages were driven in
headless Chrome at 360, 390, 430, 844x390, 768 and 1440 px on MSFT (~/Optic/work/v2-backlog/own_check.py).
"""
import datetime as dt

from app import insiders
from app.analytics import fundamentals as F
from tests.test_frontend_v2_stage0 import V2

FIN = (V2 / "js/pages/financials.js").read_text()
INS = (V2 / "js/pages/insiders.js").read_text()
TODAY = dt.date(2026, 10, 20)


def _tx(days_ago, action, shares, value=None):
    return {"insider": "A", "position": "Officer", "date": (TODAY - dt.timedelta(days=days_ago)).isoformat(),
            "shares": shares, "value": value, "action": action, "detail": action}


def test_awards_are_not_purchases():
    # Yahoo's tally: 16 "purchases" (every acquisition, awards included) against 10 sales
    raw = {"summary_6m": {"Purchases": {"shares": 513644.0, "transactions": 16.0}, "Sales": {"shares": 249649.0, "transactions": 10.0},
                          "Net Shares Purchased (Sold)": {"shares": 263995.0, "transactions": 26.0}},
           "transactions": [_tx(10, "sale", 7305, 3.9e6), _tx(40, "sale", 41674, 2.0e7), _tx(50, "other", 120000),
                            _tx(60, "other", 90000), _tx(300, "purchase", 1000, 4e5)]}
    out = F.analyse_ownership(raw, {}, now=TODAY)
    six = out["insider_6m"]
    assert six["basis"] == "open_market" and (six["purchase_count"], six["sale_count"], six["other_count"]) == (0, 2, 2)
    assert six["net_shares"] == -(7305 + 41674)
    assert out["insider_signal"] == "selling", "Yahoo's tally read 'buying'"
    assert out["yahoo_tally_6m"]["acquired_count"] == 16.0 and "awards" in out["yahoo_tally_6m"]["note"]
    assert "not decisions to buy or sell" in out["notes"][0] and "Reported history" in out["insider_method"]


def test_no_open_market_trades_is_said_and_stays_neutral():
    raw = {"summary_6m": {}, "transactions": [_tx(10, "other", 5000), _tx(400, "sale", 100)]}
    out = F.analyse_ownership(raw, {}, now=TODAY)
    assert out["insider_signal"] == "neutral", "the classic page prints 'Insiders are net {signal}'"
    assert out["notes"][0].startswith("No open-market purchases or sales")


def test_a_full_feed_whose_oldest_row_is_recent_is_a_floor():
    rows = [_tx(k % 100, "sale", 10) for k in range(200)]
    assert F._six_month_trades(rows, TODAY)["complete"] is False
    assert F._six_month_trades(rows[:50], TODAY)["complete"] is True


def test_an_amendment_is_paired_never_merged(monkeypatch):
    listed = [{"accession": "A2", "form": "4/A", "filed_at": "2026-10-16T10:00:00", "index_url": "u2"},
              {"accession": "A1", "form": "4", "filed_at": "2026-10-14T18:08:00", "index_url": "u1"},
              {"accession": "B1", "form": "4", "filed_at": "2026-10-13T09:00:00", "index_url": "u3"}]
    tx = {"date": "2026-10-10", "code": "S", "shares": 100.0, "price": 500.0}
    parsed = {"A1": [tx], "A2": [tx], "B1": [dict(tx, shares=100.0)]}
    monkeypatch.setattr(insiders, "index", lambda **k: {"available": True, "rows": listed})
    monkeypatch.setattr(insiders.feeds, "cached_json", lambda key: None)
    monkeypatch.setattr(insiders.feeds, "store_json", lambda *a, **k: None)
    who = {"A1": "Hood", "A2": "Hood", "B1": "Smith"}
    monkeypatch.setattr(insiders, "parse_filing", lambda url, acc: {"available": True, "ticker": "MSFT", "issuer": "Microsoft",
                                                                    "insider": who[acc], "roles": [], "transactions": parsed[acc]})
    out = insiders.latest(limit=10, show="all")
    rows = {r["accession"]: r for r in out["rows"]}
    assert len(out["rows"]) == 3 and out["amendments"] == 1, "nothing is removed"
    assert rows["A2"]["amendment"] and rows["A2"]["may_amend"]["accession"] == "A1"
    assert rows["A1"]["may_be_amended_by"]["accession"] == "A2"
    assert "may_amend" not in rows["B1"] and "may_be_amended_by" not in rows["B1"], "another insider's like trade is not paired"


def test_the_pages_say_what_each_record_is():
    assert "export function insiderLine" in FIN and "on the open market" in FIN and "Insider signal, 6 months" not in FIN
    assert "does not carry when it was filed" in FIN and "#/insiders?symbol=${sym}&view=insiders" in FIN
    assert "Showing the newest ${rows.length}" in INS and "shown beside what they may correct, not merged" in INS
    assert "timeZone: 'America/New_York' })} ET" in INS and "Form ${r.form || '4'}${r.amendment ? ', amendment' : ''}" in INS
    assert "data-v2-ins-row" in INS and 'class="ins-detail"' in INS
