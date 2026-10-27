"""News says when Optic fetched the list in words, never a field's name.

NVDA's News tab read "The list was fetched at fetched_at." on 26 October
2026: the server's note ended with the field's name where a time belonged."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from app import news
from tests.test_frontend_v2_stage0 import V2, _run


class _Feed:
    def news(self, ticker, limit=12):
        return [{"title": "NVIDIA unveils new systems", "publisher": "Wire", "published": "2026-10-26T20:00:00Z",
                 "url": "https://example.test/a", "tickers": ["NVDA"]}]

    def earnings_date(self, ticker):
        return None

    def quote(self, ticker):
        return {"name": "NVIDIA Corporation", "sector": "Technology", "industry": "Semiconductors"}


def test_the_note_carries_no_field_name_and_the_time_is_its_own_field():
    out = news.analyse(_Feed(), "NVDA")
    assert "fetched_at" not in out["times_note"] and "_" not in out["times_note"]
    assert datetime.fromisoformat(out["fetched_at"])


def test_the_page_formats_the_time_in_new_york_and_leaves_out_a_bad_one(tmp_path):
    got = _run(tmp_path, f"""
      const t = await import('{(V2 / "js/core/marketTime.js").as_posix()}');
      print(JSON.stringify([t.etStamp('2026-10-27T02:15:00Z'), t.etStamp(''), t.etStamp('fetched_at'), t.etStamp(null)]));
    """)
    assert got[0].endswith("10:15 PM ET") and got[1:] == ["", "", ""]
    src = (V2 / "js/pages/news.js").read_text()
    assert "etStamp(n.fetched_at) ? ` Optic fetched this list at ${etStamp(n.fetched_at)}.` : ''" in src
