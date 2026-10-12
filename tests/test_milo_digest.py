"""Digests and portfolio-aware context (2026-10-12).

What changed (observed), what may explain it (headlines, labelled), what to
look at; shared per symbol and session, no model call. The reader's watchlist
and paper trades reach Milo labelled as what they are, never as an account.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from app import digest, main

ROOT = Path(__file__).resolve().parent.parent
APP = (ROOT / "static/app.js").read_text()
NOW = datetime(2026, 10, 12, 21, 0, tzinfo=timezone.utc)
BRIEF = {"available": True, "period": {"latest": "2026-10-12", "previous": "2026-10-09"},
         "items": [{"symbol": "NVDA", "kind": "move", "headline": "NVDA fell 4.2% to $180.10", "detail": "x"}],
         "names": [{"symbol": "NVDA", "state": "changed", "change_pct": -4.2, "close": 180.1, "not_checked": []},
                   {"symbol": "KO", "state": "unchanged", "summary": "No meaningful change.", "not_checked": []}],
         "summary": "1 of 2 names changed.", "source": "Yahoo Finance daily candles"}
NEWS = {"days_to_earnings": 9, "earnings_date": "2026-10-21", "articles": [
    {"title": "Chip stocks slide on demand worries", "publisher": "Wire", "url": "https://example.com/a",
     "published": "2026-10-12T15:00:00+00:00", "about_company": True, "tone": "negative"},
    {"title": "Old story", "publisher": "Wire", "url": "https://example.com/b",
     "published": "2026-09-01T15:00:00+00:00", "about_company": True},
    {"title": "Other company", "url": "https://example.com/c", "published": "2026-10-12T15:00:00+00:00",
     "about_company": False}]}


def test_facts_and_possible_explanations_are_kept_apart():
    d = digest.compose("NVDA", BRIEF, NEWS, NOW)
    assert [f["text"] for f in d["changed"]] == ["NVDA fell 4.2% to $180.10"]
    assert [e["headline"] for e in d["explanations"]] == ["Chip stocks slide on demand worries"]
    assert d["explanations"][0]["url"] and d["explanations"][0]["published"]
    assert "does not know whether any of these caused the move" in d["explanations_note"]
    assert any("Earnings are due in 9 days" in x for x in d["look_closer"])
    assert "not by an AI model" in d["method"] and d["as_of"]


def test_a_big_move_with_no_headline_is_flagged_not_explained():
    d = digest.compose("NVDA", BRIEF, {"articles": []}, NOW)
    assert d["explanations"] == []
    assert any("no company headline" in x for x in d["look_closer"])


def test_the_list_puts_changed_names_first():
    out = digest.compose_list(["KO", "NVDA"], BRIEF, {"NVDA": NEWS}, NOW)
    assert [n["symbol"] for n in out["names"]] == ["NVDA", "KO"]


def test_the_route_is_shared_per_symbol_and_session_and_bounded(monkeypatch):
    calls = []
    monkeypatch.setattr(main, "_briefing_report", lambda syms, held: (calls.append(tuple(syms)), BRIEF)[1])
    monkeypatch.setattr(main, "_digest_news", lambda s: NEWS)
    main._DIGEST_CACHE.clear()
    client = TestClient(main.app)
    a = client.get("/api/digest/NVDA").json()
    b = client.get("/api/digest/nvda").json()
    assert a["symbol"] == "NVDA" and a == b and calls == [("NVDA",)], "second reader reads the cache"
    assert client.get("/api/digest/%3Cscript%3E").status_code == 400
    many = client.post("/api/digest", json={"symbols": ["NVDA"] * 3 + ["KO"]}).json()
    assert [n["symbol"] for n in many["names"]] == ["NVDA", "KO"]


def test_the_portfolio_summary_is_paper_and_says_how_it_weighs(monkeypatch):
    monkeypatch.setattr(main.YF_PROVIDER, "profile", lambda s: {"sector": {"NVDA": "Technology", "KO": "Consumer Defensive"}.get(s)})
    out = main._portfolio_summary([
        {"ticker": "NVDA", "qty": 10, "entry_price": 100, "instrument": "stock"},
        {"ticker": "NVDA", "qty": 1, "entry_price": 5, "instrument": "option"},
        {"ticker": "KO", "qty": 10, "entry_price": 50, "instrument": "stock"},
        {"ticker": "DROP TABLE", "qty": 1, "entry_price": 1}])
    assert out["positions"] == 3 and "not a brokerage account" in out["source"]
    assert out["by_sector"][0] == {"sector": "Technology", "share_pct": 75.0}
    assert "notional at entry" in out["note"]


def test_a_cleared_context_gets_nothing_added(monkeypatch):
    import asyncio

    async def boom(*a, **k):
        raise AssertionError("no lookups when the reader cleared the context")
    monkeypatch.setattr(main, "_augment_chat_context_lookups", boom)
    ctx = {"focus": {"scope": "none"}}
    assert asyncio.run(main._augment_chat_context([{"role": "user", "content": "how is NVDA"}], ctx)) is ctx


def test_milo_is_handed_the_lists_labelled_and_the_digest_on_screen():
    assert "source: 'paper trades the reader entered in Optic (simulated, in this browser). Not a brokerage account" in APP
    assert "ctx.reader_watchlist = { source: 'the reader\\'s watchlist in Optic'" in APP
    assert "if (dg && dg.data && dg.data.available !== false) ctx.digest = dg.data;" in APP
    assert 'data-milo-digest="watchlist">What changed on my watchlist?</button>' in APP
    assert "From Optic's data, no AI used" in APP
    from app import ai
    assert "never a brokerage account" in ai.FORMAT_PROMPT
