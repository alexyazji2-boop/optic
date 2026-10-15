"""Pre- and post-earnings analysis and the immutable forecast store."""

from __future__ import annotations

import sqlite3
from datetime import date, datetime, timedelta, timezone

import numpy as np
import pandas as pd
import pytest

from app.research import earnings_view as E
from app.research import forecasts


def ea_fixture(**over):
    ea = {
        "spot": 100.0,
        "next_report": {"date": "2026-10-29", "timing": "after_close", "days_away": 15, "confirmed": True,
                        "eps_consensus": 1.50, "eps_low": 1.40, "eps_high": 1.60, "revenue_consensus": 10.5e9,
                        "revenue_consensus_label": "$10.5B", "eps_dispersion_pct": 13.0},
        "surprise": {"available": True, "quarters": 8, "beat_rate_pct": 88, "avg_surprise_pct": 4.5,
                     "avg_abs_move_pct": 4.0, "avg_move_on_beat_pct": -0.8, "avg_move_on_miss_pct": -5.0,
                     "rows": [{"date": "2026-07-30", "surprise_pct": 4.0, "eps_reported": 1.4, "eps_estimate": 1.35,
                               "timing": "after_close"}]},
        "revisions": {"direction": "rising", "drift_90d_pct": 6.0,
                      "rows": [{"period": "+1q", "current": 1.62, "chg_30d_pct": 2.0}]},
        "implied": {"available": True, "expiry": "2026-10-30", "dte": 16, "straddle_cost": 7.0, "strike": 100,
                    "implied_move_pct": 7.0, "atm_iv_pct": 45.0},
        "pricing": {"available": True, "stance": "fair", "ratio": 1.0, "baseline_move_pct": 7.0,
                    "baseline_kind": "event-plus-ordinary", "note": "fair"},
        "latest_result": {"available": True, "date": "2026-07-30", "age_days": 76},
    }
    ea.update(over)
    return ea


def sec_fixture():
    q = []
    d = date(2024, 3, 31)
    for i in range(10):
        q.append({"period_end": d.isoformat(), "value": 8e9 * (1.03 ** i), "available_from": d.isoformat()})
        d = (pd.Timestamp(d) + pd.offsets.QuarterEnd(1)).date()
    yoy = [{"period_end": q[i]["period_end"], "growth_pct": round((q[i]["value"] / q[i - 4]["value"] - 1) * 100, 1)}
           for i in range(4, len(q))]
    return {"available": True, "revenue_quarters": q, "revenue_yoy": yoy, "eps_quarters": [], "source": "SEC"}


# ---------------------------------------------------------------- pre

def test_three_predictions_are_separate_and_a_beat_is_not_a_bullish_call():
    pre = E.pre_earnings("XYZ", ea_fixture(), sec=sec_fixture())
    assert pre["available"]
    p = pre["predictions"]
    assert set(p) == {"results", "guidance", "reaction"}
    assert p["results"]["lean"].startswith(("better", "modestly better"))
    # A serial beater whose stock falls on beats: the reaction is not "skewed up".
    assert p["reaction"]["lean"] != "skewed up"
    assert pre["view"]["headline"].startswith("My best-supported pre-earnings view is")
    assert set(pre["view"]["confidence"]) == {"results", "guidance", "reaction"}
    assert pre["view"]["probabilities"] is None and "calibration" in pre["view"]["probabilities_note"]
    assert "volatility drops" in pre["view"]["thesis_vs_trade"]


def test_consensus_is_kept_apart_from_guidance_and_gaps_are_named():
    pre = E.pre_earnings("XYZ", ea_fixture(), sec=sec_fixture())
    assert "company guidance is a different thing" in pre["consensus"]["basis"]
    assert "company guidance text" in pre["not_available"]
    assert "does not timestamp" in pre["consensus"]["timestamp_note"]
    assert pre["hurdle"]["whisper_note"]


def test_missing_consensus_lowers_what_can_be_said():
    ea = ea_fixture()
    ea["next_report"].update({"eps_consensus": None, "revenue_consensus": None})
    ea["surprise"] = {"available": False, "rows": []}
    ea["revisions"] = {"direction": "unknown", "rows": []}
    pre = E.pre_earnings("XYZ", ea, sec=None)
    r = pre["predictions"]["results"]
    assert r["confidence"] == "insufficient" and r["lean"] == "no clear lean"
    assert pre["hurdle"]["state"] == "insufficient"
    assert pre["view"].get("insufficient") is True


def test_uncertain_release_date_is_labelled():
    ea = ea_fixture()
    ea["next_report"]["confirmed"] = False
    pre = E.pre_earnings("XYZ", ea, sec=sec_fixture())
    assert pre["release"]["date_status"].startswith("estimated")


def test_no_release_date_means_no_forecast():
    ea = ea_fixture()
    ea["next_report"]["date"] = None
    out = E.pre_earnings("XYZ", ea)
    assert out["available"] is False and "investor-relations" in out["reason"]


def test_options_move_is_not_called_an_earnings_move_without_isolation():
    o = E.options_read(ea_fixture(), None, 100.0)
    assert o["event_isolated"] is False and "not an earnings-only" in o["event_note"]
    assert "every day to expiry" in o["expiry_move_method"]
    o = E.options_read(ea_fixture(), {"available": True, "move_pct": 5.1, "method": "m"}, 100.0)
    assert o["event_isolated"] and o["range"]["move_pct"] == 5.1


def test_illiquid_or_missing_options_say_why():
    ea = ea_fixture(implied={"available": False, "reason": "This ticker has no listed options."})
    o = E.options_read(ea, None, 100.0)
    assert o["available"] is False and "no listed options" in o["reason"]


def test_conflicting_evidence_reads_balanced():
    pts_ea = ea_fixture()
    pts_ea["revisions"] = {"direction": "falling", "drift_90d_pct": -5.0, "rows": []}
    h = E.expectations_hurdle(pts_ea, {}, None, {"stock_pct": 8, "spy_pct": 1, "excess_pct": 7}, None)
    # Up: run-up and beat rate; down: falling estimates.
    assert h["state"] == "balanced"


def test_basis_mismatch_is_detected():
    rows = [{"surprise_pct": -22.0 + i * 0.5} for i in range(8)]
    w = E.basis_warning({"rows": rows}, "REIT - Retail")
    assert w and "different bases" in w and "funds from operations" in w
    r = E.predict_results({"surprise": {"rows": rows, "beat_rate_pct": 0, "quarters": 8}}, {}, {}, "REIT - Retail")
    assert r["confidence"] == "insufficient"


def test_release_cutoff_by_timing():
    assert E.release_cutoff("2026-10-29", "after_close").startswith("2026-10-29T20:00")
    assert E.release_cutoff("2026-10-29", "before_open").startswith("2026-10-29T10:00")
    assert E.release_cutoff("2026-10-29", None).startswith("2026-10-29T04:00")


# ---------------------------------------------------------------- post

def test_in_line_band_keeps_a_marginal_miss_from_counting_as_a_miss():
    assert E.classify_vs(0.995, 1.00, 1.0)["state"] == "in line"
    assert E.classify_vs(0.97, 1.00, 1.0)["state"] == "miss"
    assert E.classify_vs(1.05, 1.00, 1.0)["state"] == "beat"
    # Negative consensus: the surprise is against its size, not its sign.
    assert E.classify_vs(-0.40, -0.50, 1.0)["state"] == "beat"


def test_earnings_quality_needs_three_criteria_and_ignores_the_reaction():
    assert E.earnings_quality({"eps": 1, "revenue": None, "growth_trend": None})["status"] == "insufficient"
    g = E.earnings_quality({"eps": 0, "revenue": 1, "growth_trend": 1, "margin": 1})
    assert g["grade"] == "A" and "not on the stock's reaction" in g["note"]
    g = E.earnings_quality({"eps": -1, "revenue": 1, "growth_trend": 1, "margin": 1})
    assert g["grade"] == "B"           # one miss does not override stronger results


def _reaction_bars():
    idx = pd.bdate_range("2026-09-01", "2026-10-16")
    close = np.linspace(100, 104, len(idx))
    df = pd.DataFrame({"Open": close, "High": close * 1.01, "Low": close * 0.99, "Close": close,
                       "Volume": np.full(len(idx), 1e6)}, index=idx)
    i = list(idx.date).index(date(2026, 10, 15))
    df.iloc[i, df.columns.get_loc("Open")] = df["Close"].iloc[i - 1] * 0.94
    df.iloc[i, df.columns.get_loc("Close")] = df["Close"].iloc[i - 1] * 0.97
    df.iloc[i, df.columns.get_loc("Volume")] = 3e6
    return df


def test_reaction_reads_the_session_after_an_after_close_release():
    r = E.reaction(_reaction_bars(), None, "2026-10-14", "after_close", {}, "after", today=date(2026, 10, 16))
    assert r["reaction_day"] == "2026-10-15" and r["observation"] == "completed session"
    assert r["gap_pct"] == pytest.approx(-6.0, abs=0.01) and r["gap_behaviour"] == "faded"
    assert r["relative_volume"] == pytest.approx(3.0, abs=0.01)
    assert "not who bought" in r["caveat"]


def test_reaction_before_the_session_trades_uses_extended_hours_or_waits():
    bars = _reaction_bars().loc[:"2026-10-14"]
    r = E.reaction(bars, None, "2026-10-14", "after_close", {"post_market_change_pct": -4.2}, "after",
                   today=date(2026, 10, 14))
    assert r["observation"] == "after-hours" and "thin volume" in r["text"]
    r = E.reaction(bars, None, "2026-10-14", "after_close", {}, "after", today=date(2026, 10, 14))
    assert r["observation"] == "pending"


# ---------------------------------------------------------------- forecasts

@pytest.fixture()
def store(tmp_path, monkeypatch):
    monkeypatch.setattr(forecasts, "DB_PATH", str(tmp_path / "f.db"))
    return forecasts


def _pre():
    return E.pre_earnings("XYZ", ea_fixture(), sec=sec_fixture())


def test_saved_before_the_cutoff_only(store):
    pre = _pre()
    before = datetime(2026, 10, 20, 15, tzinfo=timezone.utc)
    after = datetime(2026, 10, 29, 21, tzinfo=timezone.utc)
    assert store.save("XYZ", pre, "m1", "p1", now=before)["saved"] is True
    out = store.save("XYZ", pre, "m1", "p1", now=after)
    assert out["saved"] is False and out["reason"] == "after_cutoff"
    # One per day: a page reload is not a second forecast.
    assert store.save("XYZ", pre, "m1", "p1", now=before + timedelta(hours=2))["reason"] == "duplicate"
    assert store.save("XYZ", pre, "m1", "p1", now=before + timedelta(days=1))["saved"] is True


def test_saved_forecasts_cannot_be_edited_or_deleted(store):
    store.save("XYZ", _pre(), "m1", "p1", now=datetime(2026, 10, 20, 15, tzinfo=timezone.utc))
    with sqlite3.connect(store.DB_PATH) as conn:
        with pytest.raises(sqlite3.DatabaseError):
            conn.execute("UPDATE forecasts SET forecast = '{}'")
        with pytest.raises(sqlite3.DatabaseError):
            conn.execute("DELETE FROM forecasts")


def test_outcome_is_recorded_once_and_quality_counts_until_the_minimum(store):
    s = store.save("XYZ", _pre(), "m1", "p1", now=datetime(2026, 10, 20, 15, tzinfo=timezone.utc))
    f = store.for_release("XYZ", "2026-10-29")
    assert f and f["pre_release"] and f["forecast"]["predictions"]["results"]["lean"]
    review = E.review_forecast(f, {"state": "beat"}, {"state": "unknown"}, {"available": True, "day_pct": -2.0})
    assert review["scores"]["results"]["correct"] is True
    assert review["scores"]["guidance"]["correct"] is None
    assert store.record_outcome(s["id"], {"eps": "beat"}, review) is True
    assert store.record_outcome(s["id"], {"eps": "miss"}, review) is False
    q = store.quality()
    assert q["by_prediction"]["results"]["status"] == "collecting"
    assert "not a measure of skill" in q["by_prediction"]["results"]["text"]


def test_the_review_quotes_what_was_said_without_rewriting_it(store):
    store.save("XYZ", _pre(), "m1", "p1", now=datetime(2026, 10, 20, 15, tzinfo=timezone.utc))
    f = store.for_release("XYZ", "2026-10-29")
    said = f["forecast"]["predictions"]["reaction"]["lean"]
    review = E.review_forecast(f, {"state": "miss"}, {"state": "unknown"}, {"available": True, "day_pct": 9.0})
    assert review["scores"]["reaction"]["said"] == said
    assert store.for_release("XYZ", "2026-10-29")["forecast"] == f["forecast"]


def test_unknown_timing_reads_the_session_with_the_volume_spike():
    bars = _reaction_bars()
    i = list(bars.index.date).index(date(2026, 10, 14))
    bars.iloc[i, bars.columns.get_loc("Volume")] = 5e6          # release-day spike (a before-the-open bank)
    r = E.reaction(bars, None, "2026-10-14", None, {}, "after", today=date(2026, 10, 16))
    assert r["reaction_day"] == "2026-10-14" and "heavier volume" in r["timing_inferred"]
    r = E.reaction(_reaction_bars(), None, "2026-10-14", None, {}, "after", today=date(2026, 10, 16))
    assert r["reaction_day"] == "2026-10-15"


def test_scenario_arithmetic_is_shown_with_its_inputs():
    pre = E.pre_earnings("XYZ", ea_fixture(), sec=sec_fixture())
    figs = {f["label"]: f for f in pre["view"]["figures"]}
    f = figs["EPS if the average surprise repeats"]
    assert f["value"] == pytest.approx(1.50 * 1.045, abs=0.01) and "not a forecast" in f["kind"]
    assert "Revenue growth the consensus implies" in figs


def test_two_consensus_figures_that_disagree_leave_the_verdict_unresolved():
    ea = ea_fixture(latest_result={"available": True, "date": "2026-10-13", "age_days": 1,
                                   "eps_reported": 5.75, "eps_estimate": 5.94})
    post = E.post_earnings("JPM", ea, 1.0, calendar={"dates": ["2026-10-13"], "eps_avg": 5.715},
                           today=date(2026, 10, 14))
    eps = post["headline_audit"]["eps"]
    assert eps["state"] == "unresolved" and "two consensus figures" in eps["resolution"]
    assert post["headline_audit"]["eps_alternate"]["state"] == "in line"   # +0.6%, inside the band
    assert post["quality"]["criteria"]["eps"] is None
    # When both sources agree, the verdict stands.
    post = E.post_earnings("JPM", ea, 1.0, calendar={"dates": ["2026-10-13"], "eps_avg": 5.90},
                           today=date(2026, 10, 14))
    assert post["headline_audit"]["eps"]["state"] == "miss"


def test_post_earnings_counts_only_the_reported_quarters_figures():
    # Release on 13 October for the September quarter; SEC's newest is June.
    sec = sec_fixture()
    sec["revenue_yoy"] = [r for r in sec["revenue_yoy"] if r["period_end"] <= "2026-06-30"]
    sec["eps_quarters"] = [{"period_end": "2025-06-30", "value": 5.0}, {"period_end": "2026-06-30", "value": 7.7}]
    ea = ea_fixture(latest_result={"available": True, "date": "2026-10-13", "age_days": 1,
                                   "eps_reported": 5.75, "eps_estimate": 5.94})
    post = E.post_earnings("JPM", ea, 1.0, sec=sec, today=date(2026, 10, 14))
    a = post["headline_audit"]
    assert a["eps_gaap"] is None and "not in SEC's data yet" in " ".join(a["pending"])
    crit = post["quality"]["criteria"]
    assert crit["growth_trend"] is None and crit["eps_growth"] is None
    assert post["quality"]["status"] == "insufficient"           # only EPS is known for this quarter
    assert "not the one just reported" in post["trajectory"]["revenue_trend_text"]


def test_overnight_after_an_untimed_release_reads_the_spiked_release_day():
    """BAC overnight on 2026-10-15 (found by the Milo eval): released on the
    14th before the open, no timing in the feed, the 15th not traded yet; the
    framework said the reaction was pending although the 14th fell 4.76%."""
    bars = _reaction_bars().loc[:"2026-10-14"].copy()
    i = len(bars) - 1
    bars.iloc[i, bars.columns.get_loc("Volume")] = 3.2e6
    bars.iloc[i, bars.columns.get_loc("Close")] = bars["Close"].iloc[i - 1] * 0.9524
    r = E.reaction(bars, None, "2026-10-14", None, {"post_market_change_pct": 0.18}, "overnight",
                   today=date(2026, 10, 15))
    assert r["reaction_day"] == "2026-10-14" and r["observation"] == "completed session"
    assert r["day_pct"] == pytest.approx(-4.76, abs=0.01)
    assert "next session will carry the reaction instead" in r["timing_inferred"]
    # No spike on the release day: it may have been after the close, so the
    # extended-hours read stands.
    quiet = _reaction_bars().loc[:"2026-10-14"]
    r = E.reaction(quiet, None, "2026-10-14", None, {"post_market_change_pct": 0.18}, "overnight",
                   today=date(2026, 10, 15))
    assert r["observation"] == "after-hours"


def test_an_old_newest_result_is_flagged_as_probably_not_the_latest():
    """BAC the morning after its October release (2026-10-15): the live feed's
    newest result was July's and the next report January's."""
    rec = E.release_recency({"date": "2026-07-14"}, {"date": "2027-01-15"}, date(2026, 10, 15))
    assert rec["state"] == "probably_missing" and "2026-07-14" in rec["text"] and "2027-01-15" in rec["text"]
    assert E.release_recency({"date": "2026-10-14"}, {"date": "2027-01-15"}, date(2026, 10, 15))["state"] == "current"
    ea = ea_fixture(latest_result={"available": True, "date": "2026-07-14", "age_days": 93,
                                   "eps_reported": 0.9, "eps_estimate": 0.88})
    ea["next_report"]["date"] = "2027-01-15"
    post = E.post_earnings("BAC", ea, 1.0, today=date(2026, 10, 15))
    assert post["release"]["recency"]["state"] == "probably_missing"
