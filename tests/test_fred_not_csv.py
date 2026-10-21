"""FRED answering with a web page instead of its CSV (2026-10-21, local and live).

The page's first stylesheet line, `<link href="https://fonts.googleapis.com/css?family=Open+Sans:300,400,...`, split
on commas, read as a DGS10 observation of 400 dated with the HTML, so every fair-value model ran on a 400% risk-free
rate labelled "reported". Only a CSV that names its series, and rows that start with a date, are read now; anything
else is no answer, dropped from the cache, and the valuation falls back to the quote feed's 10-year index, which is
itself refused outside 0 to 25%.
"""
from __future__ import annotations

import app.fred as fred
import app.valuation.inputs as inputs

PAGE = '<!DOCTYPE html>\n<link href="https://fonts.googleapis.com/css?family=Open+Sans:300,400,600" rel="stylesheet">\n<p>Something went wrong</p>\n'
CSV = "observation_date,DGS10\n2026-10-19,4.31\n2026-10-20,.\n2026-10-21,4.28\n"


def test_a_web_page_is_not_read_as_observations(monkeypatch):
    dropped = []
    monkeypatch.setattr(fred.feeds, "fetch_text", lambda *a, **k: PAGE)
    monkeypatch.setattr(fred.feeds, "forget_prefix", lambda p: dropped.append(p) or 1)
    assert fred.observations("DGS10") == []
    assert dropped == ["fred:DGS10"], "dropped, so the next request asks FRED again"


def test_the_csv_is_read_and_its_dots_skipped(monkeypatch):
    monkeypatch.setattr(fred.feeds, "fetch_text", lambda *a, **k: CSV)
    assert fred.observations("DGS10") == [("2026-10-19", 4.31), ("2026-10-21", 4.28)]


class Quote:
    def __init__(self, price):
        self.price = price

    def quote(self, sym):
        return {"price": self.price, "as_of": "2026-10-21T15:00:00Z"}


def test_the_valuation_falls_back_to_the_10_year_index_and_refuses_a_misread(monkeypatch):
    monkeypatch.setattr(fred, "observations", lambda s, **k: [])
    got = inputs.risk_free(Quote(42.8))
    assert abs(got["value"] - 0.0428) < 1e-9 and "^TNX" in got["source"], "FRED gave nothing: the index, said so"
    monkeypatch.setattr(fred, "observations", lambda s, **k: [("2026-10-21", 400.0)])
    got = inputs.risk_free(Quote(4.28))
    assert abs(got["value"] - 0.0428) < 1e-9, "a 400 is not a yield"
    monkeypatch.setattr(fred, "observations", lambda s, **k: [])
    assert inputs.risk_free(Quote(None))["value"] is None
