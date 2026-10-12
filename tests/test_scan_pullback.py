"""TrendSpider's two sample scans, read without a model (2026-10-12).

"10% pull back after 20% rally" and "2% or more above prev close" were not
expressible: no field for the day's move, and "pullback" meant only "under
the 20-day in an uptrend". Now both read to exact filters by rule, so neither
costs a Claude call, and the box keeps "your recent prompts".
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from app.analytics import scan_request, screen, screener

ROOT = __import__("pathlib").Path(__file__).resolve().parent.parent
APP = (ROOT / "static/app.js").read_text()


def test_the_two_samples_read_to_exact_filters():
    r = scan_request.read("10% pull back after 20% rally")
    assert r["filters"] == [{"field": "off_high", "min": None, "max": -10.0},
                            {"field": "rally", "min": 20.0, "max": None}]
    assert not r["leftover"]
    assert scan_request.read("2% or more above prev close")["filters"] == [
        {"field": "chg1d", "min": 2.0, "max": None}]
    assert scan_request.read("down 3% today")["filters"] == [{"field": "chg1d", "min": None, "max": -3.0}]
    # The plain word keeps its old meaning.
    assert scan_request.read("pullbacks in strong uptrends")["filters"][0]["field"] == "pct_from_sma20"


def test_the_fields_are_computed_from_the_bars():
    n = 260
    close = np.concatenate([np.linspace(100, 100, 150), np.linspace(100, 130, 60), np.linspace(130, 115, 50)])
    frame = pd.DataFrame({"Close": close, "Volume": np.full(n, 1e6),
                          "High": close * 1.01, "Low": close * 0.99, "Open": close})
    m = screen._metrics("TEST", frame)
    assert round(m["rally"]) == 30, "from the 100 base to the 130 high"
    assert round(m["off_high"], 1) == round((115 / 130 - 1) * 100, 1)
    assert round(m["chg1d"], 2) == round((close[-1] / close[-2] - 1) * 100, 2)
    for fid in ("chg1d", "off_high", "rally"):
        assert fid in screener.FIELD_BY_ID


def test_recent_prompts_are_kept_per_reader_and_offered_back():
    assert "const SCAN_RECENT_KEY = 'optic.scan.recent.v1';" in APP
    personal = APP[APP.index("const PERSONAL_KEYS = ["):]
    assert "'optic.scan.recent.v1'" in personal[:personal.index("];")]
    assert "Your recent prompts" in APP and "data-sc-recent-clear" in APP
    assert "'10% pull back after 20% rally'," in APP and "'2% or more above prev close'," in APP
