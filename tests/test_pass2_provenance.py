"""Pass 2, item 4 (2026-11-17): where every figure came from, reported facts set apart from Milo's reading, and the
full insider history from the SEC rather than the last batch the free feed lists.

Already in place and held by earlier tests: every registry figure opens its definition with the period, basis,
inputs, filing, as-of date and source (ui/figure.js, Handoff 1); quotes carry their delay and time (core/delays.js).
New here: a figure Milo quotes with its source is marked as reported, apart from his reading; and a company's
open-market insider trades over 2, 5 or 10 years, each row saying whether it is Yahoo's or a Form 4 read from EDGAR.
"""
from __future__ import annotations

import datetime as dt

import pytest
from fastapi.testclient import TestClient

from app import form4_store, insider_fill as F, main
from tests.test_frontend_v2_stage0 import V2, _run

TODAY = dt.date(2026, 11, 17)


@pytest.fixture
def kept(tmp_path, monkeypatch):
    monkeypatch.setattr(form4_store, "DB_PATH", str(tmp_path / "form4.db"))
    started = []
    monkeypatch.setattr(F, "start", lambda *a: started.append(a) or True)
    return started


def _yahoo(rows):
    return {"summary_6m": {}, "transactions": rows}


def _row(date, action, insider="A. INSIDER"):
    return {"insider": insider, "position": "Director", "date": date, "shares": 100.0, "value": 10000.0,
            "action": action, "detail": "{} at price 100.00 per share.".format(action.title())}


def test_a_long_history_reads_before_yahoos_oldest_row_even_when_its_list_is_short(kept):
    y = _yahoo([_row("2026-09-01", "sale"), _row("2025-01-10", "purchase")])
    assert F.gap(y["transactions"], TODAY) is None, "the chart's two years: a short list is whole"
    since, until = F.gap(y["transactions"], TODAY, days=5 * 365)
    assert since == (TODAY - dt.timedelta(days=5 * 365)).isoformat() and until == "2025-01-10"


def test_the_history_merges_sec_form4_trades_before_yahoo_and_says_which_is_which(kept):
    form4_store.save_list("UNH", "731766", [["0000731766-23-000101", "2023-05-20"]], "2010-01-01")
    form4_store.save("0000731766-23-000101", "731766", {
        "available": True, "issuer_cik": "731766", "insider": "HEMSLEY STEPHEN J", "roles": ["Chief Executive Officer"],
        "trades": [{"date": "2023-05-18", "code": "P", "shares": 1000, "value": 500000.0, "price": 500.0}]})
    y = _yahoo([_row("2026-09-01", "sale"), _row("2025-01-10", "other")])
    h = F.history("UNH", y, 5, today=TODAY)
    by = {(r["date"], r["source"]) for r in h["rows"]}
    assert ("2026-09-01", "yahoo") in by and ("2023-05-18", "sec") in by
    assert all(r["action"] in ("purchase", "sale") for r in h["rows"]), "awards are not trades"
    assert h["coverage"]["sec_rows"] == 1 and h["coverage"]["cik"] == "731766" and h["coverage"]["sec_unread"] == 0
    assert kept == [] or all(a[2] == 5 * 365 for a in kept if len(a) > 2)


def test_filings_not_yet_read_are_counted_and_start_the_reader_for_the_span_asked(kept):
    form4_store.save_list("UNH", "731766", [["0000731766-22-000001", "2022-03-01"]], "2010-01-01")
    h = F.history("UNH", _yahoo([_row("2026-09-01", "sale")]), 10, today=TODAY)
    assert h["coverage"]["sec_unread"] == 1 and h["coverage"]["complete"] is False
    assert kept and kept[-1][0] == "UNH" and kept[-1][2] == 10 * 365


def test_the_history_route_checks_its_input_and_answers_with_the_feed_down(kept, monkeypatch):
    c = TestClient(main.app)
    assert c.get("/api/insiders/AAPL%3B/history").status_code in (400, 404)
    assert c.get("/api/insiders/AAPL/history?years=3").status_code == 422
    monkeypatch.setattr(main.YF_PROVIDER, "insiders", lambda sym: (_ for _ in ()).throw(RuntimeError("down")))
    r = c.get("/api/insiders/AAPL/history?years=2")
    assert r.status_code == 200 and r.json()["rows"] == [] and r.json()["yahoo_answered"] is False


def test_a_figure_milo_quotes_with_its_source_is_marked_reported_and_a_bare_bold_phrase_is_not(tmp_path):
    got = _run(tmp_path, f"""
      const m = await import('{(V2 / "js/core/milo-text.js").as_posix()}');
      const a = m.renderAnswer('Revenue was **$94.9B** [[src earnings]] last quarter, which **looks strong** to me.', 'AAPL').html;
      print(JSON.stringify({{ a, key: m.FACT_KEY }}));
    """)
    assert 'class="milo-fact"' in got["a"] and ">$94.9B</strong>" in got["a"]
    assert "<strong>looks strong</strong>" in got["a"], "Milo's own emphasis stays his reading"
    assert "reported" in got["key"] and "Milo's reading" in got["key"]


def test_financials_draws_the_full_history_with_its_source_per_row():
    src = (V2 / "js" / "pages" / "financials.js").read_text()
    assert "/api/insiders/${encodeURIComponent(sym)}/history?years=${ihYears}" in src
    assert "'SEC Form 4'" in src and "'Yahoo Finance'" in src and "still being read" in src


def test_every_financials_chart_names_its_source_under_it_and_no_delay():
    """The source was said once, at the Statements section's head; each chart carried its period and no source, where
    Home's headline chart names Yahoo Finance under it (Pass 2 gauntlet, D5, 2026-11-18). Every fv figure's caption on
    Financials now ends with a source line. Statements are filed, not quoted, so the line carries no delay."""
    src = (V2 / "js" / "pages" / "financials.js").read_text()
    figures = src.split('<figure class="fv')[1:]
    assert len(figures) >= 10, "the eight statement charts and the two segment figures"
    for f in figures:
        cap = f[:f.index("</figcaption>")]
        title = cap[cap.find("<h3>") + 4:cap.find("</h3>")]
        assert "${src}" in cap or "${sourceLine(" in cap, "no source line under " + title
    line = src[src.index("const sourceLine"):src.index("\n", src.index("const sourceLine"))]
    assert 'class="fv-unit"' in line and "Source: ${s}" in line
    for name in ("STATEMENTS_SOURCE", "FILINGS_SOURCE"):
        said = src[src.index("const " + name):src.index("\n", src.index("const " + name))]
        assert "delay" not in said.lower() and "minute" not in said.lower(), said
    assert "f.source ? clean(f.source)" in src, "the feed's own source line wins when it names one"
    assert "—" not in src and "–" not in src
