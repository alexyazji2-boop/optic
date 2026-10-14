"""The opening-range break with a VWAP retest (app/analytics/session_rules.py).

Built on hand-made sessions where every step is known: an opening range of
100 to 101 traded on heavy volume, so VWAP sits at 100.50 and stays there (the
later bars carry no volume), then a break, an extension and a retest whose
prices are chosen to land on each rule's edge.
"""
from __future__ import annotations

import pandas as pd
import pytest

from app.analytics import backtest as bt
from app.analytics import session_rules as sr

COST = sr.COST_BPS / 10000.0

# Bars 6 to 13 of the session: (open, high, low, close).
QUALIFIED = [
    (100.6, 101.3, 100.6, 101.2),   # 6: closes above the range: the break
    (101.2, 101.6, 101.1, 101.5),   # 7
    (101.5, 102.2, 101.4, 102.0),   # 8: high 102.2 >= 101 + one width: extended
    (102.0, 102.0, 101.4, 101.5),   # 9
    (101.5, 101.6, 100.6, 100.8),   # 10: low 100.6 stays above VWAP
    (100.8, 100.9, 100.4, 100.7),   # 11: first touch of 100.50: entry
    (100.7, 101.0, 100.5, 100.9),   # 12
    (100.9, 101.6, 100.8, 101.4),   # 13: reaches 101.50, the 2R target
]


def _session(day, middle, tail=101.4):
    rows = [(100.5, 101.0, 100.0, 100.5, 1e6)] * 6
    rows += [(o, h, l, c, 0.0) for o, h, l, c in middle]
    while len(rows) < 78:
        rows.append((tail, tail, tail, tail, 0.0))
    idx = pd.date_range(day + " 09:30", periods=78, freq="5min", tz="America/New_York")
    return pd.DataFrame(rows, index=idx, columns=["Open", "High", "Low", "Close", "Volume"])


def _one(middle, tail=101.4, **prm):
    s = sr.sessions(_session("2026-10-05", middle, tail))[0]
    p = sr.params_for(prm)
    return s, p, sr._setup(s, p)


def _mirror(rows):
    # 201 - price maps the range onto itself and turns every rise into a fall.
    return [(201 - o, 201 - l, 201 - h, 201 - c) for o, h, l, c in rows]


def test_vwap_is_the_volume_weighted_typical_price():
    s, _, _ = _one(QUALIFIED)
    vw = sr.vwap(s)
    assert vw[5] == pytest.approx(100.5)
    # Bars without volume leave it where it was.
    assert vw[40] == pytest.approx(100.5)


def test_a_qualified_long_enters_at_vwap_and_takes_the_target():
    s, p, su = _one(QUALIFIED)
    assert su["side"] == "long" and su["i"] == 11
    assert (su["orl"], su["orh"]) == (100.0, 101.0)
    assert su["break_i"] == 6 and su["ext_i"] == 8
    assert su["fill"] == pytest.approx(100.5)
    res = sr._manage(s, "long", su["i"], su["fill"], p["stop_ranges"] * su["w"], p["target_r"], COST)
    assert res["why"] == "target" and res["exit"] == pytest.approx(101.5) and res["j"] == 13
    assert res["stop"] == pytest.approx(100.0)
    assert res["ret"] == pytest.approx(101.5 * (1 - COST) / (100.5 * (1 + COST)) - 1)


def test_a_bar_that_opens_through_the_line_fills_at_its_open():
    rows = list(QUALIFIED)
    rows[5] = (100.3, 100.6, 100.2, 100.5)    # bar 11 opens below 100.50
    _, _, su = _one(rows)
    assert su["i"] == 11 and su["fill"] == pytest.approx(100.3)


def test_a_close_back_through_vwap_before_the_extension_disqualifies():
    rows = list(QUALIFIED)
    rows[1] = (101.2, 101.3, 100.3, 100.4)    # bar 7 closes under 100.50
    _, _, su = _one(rows)
    assert su == {"skip": "closed back through VWAP"}


def test_no_extension_no_trade():
    rows = list(QUALIFIED)
    rows[2] = (101.5, 101.9, 101.4, 101.8)    # tops at 101.9, short of 102
    rows[3] = (101.8, 101.9, 101.4, 101.5)
    _, _, su = _one(rows)
    assert su == {"skip": "never extended"}


def test_the_extension_is_a_parameter():
    rows = list(QUALIFIED)
    rows[2] = (101.5, 101.9, 101.4, 101.8)
    rows[3] = (101.8, 101.9, 101.4, 101.5)
    _, _, su = _one(rows, extension=0.75)     # 101.75 is enough now
    assert su["side"] == "long"


def test_a_bar_reaching_both_the_stop_and_the_target_is_a_stop():
    rows = list(QUALIFIED)
    rows[7] = (100.9, 101.6, 99.9, 101.4)     # bar 13 spans 99.9 to 101.6
    s, p, su = _one(rows)
    res = sr._manage(s, "long", su["i"], su["fill"], p["stop_ranges"] * su["w"], p["target_r"], COST)
    assert res["why"] == "stopped" and res["exit"] == pytest.approx(100.0)


def test_the_entry_bar_can_stop_but_not_take_profit():
    rows = list(QUALIFIED)
    rows[5] = (100.8, 101.9, 99.8, 100.7)     # the touch bar also reaches 99.8 and 101.9
    s, p, su = _one(rows)
    res = sr._manage(s, "long", su["i"], su["fill"], p["stop_ranges"] * su["w"], p["target_r"], COST)
    assert res["why"] == "stopped" and res["j"] == su["i"]


def test_a_trade_that_reaches_neither_is_flat_at_the_close():
    rows = QUALIFIED[:6] + [(100.7, 100.9, 100.5, 100.8)] * 2
    s, p, su = _one(rows, tail=100.9)
    res = sr._manage(s, "long", su["i"], su["fill"], p["stop_ranges"] * su["w"], p["target_r"], COST)
    assert res["why"] == "flat at the close" and res["j"] == 77 and res["exit"] == pytest.approx(100.9)


def test_no_target_holds_to_the_close():
    s, p, su = _one(QUALIFIED, target_r=0)
    res = sr._manage(s, "long", su["i"], su["fill"], p["stop_ranges"] * su["w"], p["target_r"], COST)
    assert res["why"] == "flat at the close" and res["exit"] == pytest.approx(101.4)


def test_a_short_is_the_mirror_image():
    s, p, su = _one(_mirror(QUALIFIED), tail=201 - 101.4)
    assert su["side"] == "short" and su["i"] == 11 and su["fill"] == pytest.approx(100.5)
    res = sr._manage(s, "short", su["i"], su["fill"], p["stop_ranges"] * su["w"], p["target_r"], COST)
    assert res["why"] == "target" and res["exit"] == pytest.approx(99.5)
    assert res["ret"] == pytest.approx((100.5 * (1 - COST) - 99.5 * (1 + COST)) / (100.5 * (1 - COST)))


def test_sides_can_be_switched_off():
    _, _, su = _one(_mirror(QUALIFIED), tail=201 - 101.4, allow_short=False)
    assert "skip" in su


def test_no_entry_after_the_cut_off():
    # Bar 11 is 55 minutes after the open.
    _, _, su = _one(QUALIFIED, last_entry=50)
    assert su == {"skip": "no retest in time"}


def test_the_entry_uses_nothing_from_its_own_bar_or_later():
    """The fill level is VWAP through the bar before the touch; what the touch
    bar and the bars after it do cannot move it."""
    _, _, base = _one(QUALIFIED)
    rows = list(QUALIFIED)
    rows[5] = (100.8, 100.9, 100.4, 100.45)
    rows[6:] = [(90.0, 120.0, 80.0, 95.0)] * 2
    _, _, other = _one(rows, tail=50.0)
    assert (other["i"], other["fill"]) == (base["i"], base["fill"])


def test_the_plain_break_enters_at_the_open_after_the_breaking_close():
    s, p, _ = _one(QUALIFIED)
    pb = sr._plain_break(s, p, COST)
    assert pb["side"] == "long" and pb["i"] == 7
    # Entry 101.2 at bar 7's open, risk 0.5, target 102.2: bar 8 reaches it.
    assert pb["why"] == "target" and pb["exit"] == pytest.approx(102.2)


def test_the_parameters_are_clamped_and_rounded_to_whole_bars():
    p = sr.params_for({"range_minutes": "17", "extension": "99", "stop_ranges": "-1", "target_r": "nan",
                       "allow_long": "false", "allow_short": "false"})
    assert p["range_minutes"] == 15
    assert p["extension"] == 4.0 and p["stop_ranges"] == 0.1 and p["target_r"] == 2.0
    # Both sides off would test nothing; long comes back on.
    assert p["allow_long"] is True


def test_a_day_without_its_opening_bar_is_dropped():
    df = _session("2026-10-05", QUALIFIED).iloc[1:]
    assert sr.sessions(df) == []


def _week(middle):
    return pd.concat([_session(d, middle) for d in
                      ("2026-10-05", "2026-10-06", "2026-10-07", "2026-10-08", "2026-10-09")])


def test_the_run_reports_trades_baselines_and_a_small_sample():
    r = bt.run(_week(QUALIFIED), "orb_vwap_retest", {}, timeframe="5m")
    assert r["available"] and r["engine"] == "session"
    assert r["stats"]["trades"] == 5 and r["stats"]["sides"] == {"long": 5}
    assert r["stats"]["exit_reasons"] == {"target": 5}
    t = r["trades"][0]
    assert t["entry_date"] == "2026-10-05 10:25" and t["exit_date"] == "2026-10-05 10:35"
    assert r["benchmark"]["plain_break"]["trades"] == 5
    assert r["benchmark"]["random_runs"] == sr.RANDOM_RUNS
    assert r["window"]["sessions"] == 5
    assert "far too few" in r["verdict"]
    assert len(r["equity"]) == 5 and r["equity"][-1]["strategy"] > 1


def test_it_runs_on_five_minute_bars_only():
    r = bt.run(_week(QUALIFIED), "orb_vwap_retest", {}, timeframe="1d")
    assert r["available"] is False and "5 minutes" in r["reason"]
    r = bt.run(_week(QUALIFIED), "golden_cross", {}, timeframe="5m")
    assert r["available"] is False


def test_the_catalogue_says_which_bars_each_rule_takes():
    cat = {s["id"]: s for s in bt.catalogue()}
    assert cat["orb_vwap_retest"]["timeframes"] == ["5m"]
    assert cat["macd_turn_below_zero"]["timeframes"] == ["1d", "4h", "1h"]
    assert "5m" in bt.TIMEFRAMES
    kinds = {p["id"]: p["kind"] for p in cat["orb_vwap_retest"]["params"]}
    assert kinds["extension"] == "float" and kinds["allow_short"] == "bool"


# ------------------------------------------------------------- the widget

from pathlib import Path  # noqa: E402

APP = (Path(__file__).resolve().parent.parent / "static/app.js").read_text()


def _fn(head):
    start = APP.index(head)
    return APP[start:APP.index("\n}\n", start)]


def test_the_widget_offers_only_the_bars_a_rule_takes():
    html = _fn("function wsBacktestHTML(")
    assert "btTimeframes(s).filter((k) => allTfs[k])" in html
    assert "[[0, 'Last 60 sessions']]" in html
    change = _fn("function btOnChange(")
    assert "if (k === 'strategy') btFixTimeframe();" in change
    assert "btFixTimeframe();" in _fn("async function loadBacktest(")


def test_decimal_parameters_step_in_decimals():
    params = _fn("function btParamsHTML(")
    assert "p.kind === 'float'" in params and "inputmode=\"${float ? 'decimal' : 'numeric'}\"" in params


def test_markers_land_on_the_minute_and_shorts_read_the_other_way():
    marks = _fn("function backtestMarkers(")
    assert "String(d).replace('T', ' ').slice(0, 16)" in marks
    assert "String(d).slice(0, 10)" not in marks
    assert "short ? 'S' : 'B'" in marks and "short ? 'B' : 'S'" in marks


def test_milo_is_told_which_sides_were_traded():
    assert "sides: r.sides || 'long only'" in APP
