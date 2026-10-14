"""The round-number stop check (app/analytics/stops.py) and its route."""
from __future__ import annotations

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.analytics import stops


def test_the_grid_follows_the_price():
    assert [stops.grid_step(p) for p in (1.5, 8, 45, 208, 778, 1450)] == [0.1, 1, 5, 10, 10, 50]
    assert stops.strength(200, 10) == "major" and stops.strength(250, 10) == "half"
    assert stops.strength(210, 10) == "minor"
    assert [r["price"] for r in stops.round_levels(195, 222, 10)] == [200, 210, 220]


def test_a_long_stop_just_under_a_round_number_moves_a_buffer_past_it():
    r = stops.check(205, 199.9, 4.0)
    assert r["side"] == "long" and r["round_level"] == {"price": 200.0, "strength": "major"}
    assert r["moved"] and r["adjusted_stop"] == 199.0
    assert r["risk_per_share"] == pytest.approx(5.1) and r["risk_per_share_adjusted"] == pytest.approx(6.0)
    assert r["past_level_atr"] == pytest.approx(0.25)
    # From the study: 18.9% of falls through a round number went past 0.25 ATR.
    assert r["swept_share_pct"] == 18.9
    # 0.1 below 200 with a $4 ATR is 0.025 ATR: past nearly every cross.
    assert r["swept_share_pct_before"] == 53.8


def test_a_stop_inside_the_level_is_reached_by_every_cross():
    r = stops.check(205, 200.4, 4.0)
    assert r["moved"] and r["adjusted_stop"] == 199.0 and r["swept_share_pct_before"] == 100.0
    assert "just inside" in r["text"]


def test_a_short_is_the_mirror_image():
    r = stops.check(195, 200.1, 4.0)
    assert r["side"] == "short" and r["adjusted_stop"] == 201.0 and r["moved"]
    assert r["swept_share_pct"] == 16.7     # rises through a round number


def test_a_stop_is_never_moved_closer_to_the_price():
    r = stops.check(205, 199.0, 4.0)        # already 0.25 ATR past 200
    assert not r["moved"] and r["adjusted_stop"] == 199.0
    assert "already" in r["text"]
    # Further than the window from any round number: nothing to move past.
    assert stops.check(205, 198.0, 4.0)["round_level"] is None


def test_no_round_number_nearby_leaves_the_stop_and_says_why():
    r = stops.check(205, 196.3, 4.0)
    assert r["round_level"] is None and not r["moved"] and r["swept_share_pct"] is None
    assert "No round number" in r["text"]


def test_the_strongest_level_in_reach_wins():
    # A $10 ATR makes the window 2.5 wide; 250 is the level in it.
    r = stops.check(262, 250.5, 10.0)
    assert r["round_level"]["price"] == 250.0 and r["round_level"]["strength"] == "half"


def test_sizing_from_the_wider_stop():
    r = stops.check(45.2, 44.95, 1.2, account=25000, risk_pct=1.0)
    assert r["shares_for_risk"] == 1000 and r["shares_for_risk_adjusted"] == 500


def test_bad_input_is_refused_not_guessed():
    assert stops.check(100, 100, 2)["available"] is False
    assert stops.check(100, 90, 0)["available"] is False
    assert stops.check(float("nan"), 90, 2)["available"] is False


def test_the_evidence_rows_line_up():
    e = stops.EVIDENCE
    for k in ("round_down", "control_down", "round_up", "control_up"):
        assert len(e[k]) == len(e["buffers_atr"])
        assert e[k] == sorted(e[k], reverse=True)


def test_the_route(monkeypatch):
    import app.main as m
    idx = pd.date_range("2026-01-01", periods=60, freq="B")
    df = pd.DataFrame({"Open": 204.0, "High": 206.0, "Low": 202.0, "Close": 205.0, "Volume": 1e6}, index=idx)
    monkeypatch.setattr(m.YF_PROVIDER, "history", lambda *a, **k: df)
    c = TestClient(m.app)
    r = c.get("/api/stop-check/abc?stop=199.9").json()
    assert r["ticker"] == "ABC" and r["entry"] == 205.0 and r["atr"] == pytest.approx(4.0, abs=0.01)
    assert r["adjusted_stop"] == 199.0
    assert c.get("/api/stop-check/ABC").status_code == 422


# ------------------------------------------------------------- the widget

from pathlib import Path  # noqa: E402

APP = (Path(__file__).resolve().parent.parent / "static/app.js").read_text()


def _fn(head):
    start = APP.index(head)
    return APP[start:APP.index("\n}\n", start)]


def test_the_widget_is_on_the_dock_and_loads_when_opened():
    assert "{ id: 'stopcheck', label: 'Stop check', short: 'Stop'," in APP
    assert "if (id === 'stopcheck') return wsStopCheckHTML();" in APP
    assert "if (on && id === 'stopcheck') loadStopCheck(STATE.chartSymbol);" in APP
    assert "if (wsDockOpen.includes('stopcheck')) loadStopCheck(sym);" in APP


def test_the_stop_starts_from_the_entry_plan():
    assert "plan.risk && plan.risk.underlying_stop" in _fn("function scPlanStop(")
    assert "stop = Number(SC.stop[sym]) > 0 ? Number(SC.stop[sym]) : scPlanStop(sym)" in _fn("function scInputs(")


def test_the_lines_are_for_this_symbol_only():
    lines = _fn("function stopCheckLines(")
    assert "r.ticker !== symbol" in lines
    assert "...stopCheckLines(d.ticker || STATE.chartSymbol)," in APP


def test_stops_and_the_account_size_are_personal():
    personal = APP[APP.index("const PERSONAL_KEYS = ["):]
    personal = personal[:personal.index("];")]
    assert "'optic.chart.stopcheck.v1'" in personal


def test_milo_gets_the_check_with_both_shares():
    assert "ctx.stop_check = {" in APP
    assert "swept_share_pct_before: r.swept_share_pct_before, swept_share_pct: r.swept_share_pct" in APP


def test_a_closed_widget_leaves_nothing_on_the_chart():
    shown = _fn("function wsWidgetShown(")
    assert "wsIsNarrow() ? wsNarrowWidget === id : wsDockOpen.includes(id)" in shown
    assert "!wsWidgetShown('backtest')" in _fn("function backtestMarkers(")
    assert "!wsWidgetShown('stopcheck')" in _fn("function stopCheckLines(")
    assert "if (!on && (id === 'backtest' || id === 'stopcheck')) wsRedrawChart();" in _fn("function wsToggleWidget(")
