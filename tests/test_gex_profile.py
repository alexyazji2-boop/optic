"""The GEX profile along the price axis (app/analytics/gex.py profile_strikes,
and the chart layer in static/app.js and static/charts.js)."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from app.analytics import gex

ROOT = Path(__file__).resolve().parent.parent
APP = (ROOT / "static/app.js").read_text()
CHARTS = (ROOT / "static/charts.js").read_text()


from app.analytics import vol_surface as vs
from tests.test_options_research_api import R, Q, SPOT, _chain


def _read(monkeypatch=None, cap=None):
    if cap is not None:
        monkeypatch.setattr(gex, "PROFILE_MAX", cap)
    today = pd.Timestamp.now(tz="America/New_York").normalize()
    chain = _chain([str((today + pd.Timedelta(days=d)).date()) for d in (10, 31)])
    chain = vs.resolve_surface(vs.apply_quotes(vs.apply_clock(chain)), SPOT, R, Q, american=True)
    return gex.analyse(chain, SPOT, rate=R, div=Q, ticker="SPY")


def test_the_profile_is_the_strikes_within_the_band_in_order():
    ks = [r["strike"] for r in _read()["profile_strikes"]]
    # Strikes 80 to 120 by 5; within 12% of 100 is 90 to 110.
    assert ks == [90.0, 95.0, 100.0, 105.0, 110.0]


def test_over_the_cap_it_keeps_the_nearest_not_the_lowest(monkeypatch):
    ks = [r["strike"] for r in _read(monkeypatch, cap=3)["profile_strikes"]]
    assert ks == [95.0, 100.0, 105.0]


def test_the_layer_is_wired_and_drawn_from_the_left():
    assert "{ id: 'levels', label: 'Levels', items: ['fib', 'trends', 'sr', 'zones', 'accum', 'gex'] }" in APP
    assert "gexProfile: showGex ? gexProfileBars(d) : null," in APP
    assert "...(showGex ? gexLines(d) : [])," in APP
    assert "gex: (on) => { showGex = on; storeFlag(SHOW_GEX_KEY, on); }," in APP
    draw = CHARTS[CHARTS.index("if (gexProfile && gexProfile.length) {"):]
    draw = draw[:draw.index("\n  }\n")]
    assert "x: m.l," in draw and "b.value > 0 ? C.pos : C.neg" in draw


def test_the_walls_say_they_are_untested():
    lines = APP[APP.index("function gexLines("):]
    lines = lines[:lines.index("\n}\n")]
    assert "will test them against nearby strikes" in lines
    assert "g.assumption" in lines


def test_the_desk_reads_spy_gamma_as_positioning_not_a_forecast():
    from app.desk import evidence as ev
    read = _read()
    g = ev.Gatherer()
    ev.gather_gamma(g, "SPY", read)
    row = g.rows[-1]
    assert row.kind == "options" and row.unit == "$m per 1%"
    assert "has not been tested" in row.method and "not as support" in row.method
    assert row.detail["flip_point"] == read["regime"]["flip_point"]
    g2 = ev.Gatherer()
    ev.gather_gamma(g2, "SPY", {"error": "frozen chain"})
    assert not g2.rows and g2.coverage[-1]["reason"] == "frozen chain"
