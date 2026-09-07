"""Optic Pulse, why it's moving, and what matters next.

Three panels that lead the asset page. Every assertion here is about honesty
rather than formatting, because the failure mode for all three is the same: a
panel that reads confidently off a key that is not there, or off a number the
project already knows is not predictive.
"""

from datetime import date

import pytest

from app.analytics import pulse


def _verdict(**components):
    """A verdict shaped like swing.verdict()'s output."""
    return {
        "stance": "bullish",
        "composite_score": 41.2,
        "conviction": "moderate",
        "components": components,
        "breakdown": [
            {"component": k, "weight_pct": 20, "measures": "what {} means".format(k),
             "unavailable": False, "status": "included", "status_reason": None}
            for k in components
        ],
        "signal_agreement_pct": 80,
        "conflicts": [],
    }


# --------------------------------------------------------------- the stance

def test_the_headline_is_a_stance_not_a_score():
    """`composite_score` is in the payload and must never be the headline. The
    project's own evaluate module reports that this blend does not beat a single
    momentum factor, so a big number would be the most confident thing on the
    page and the least supported."""
    out = pulse.pulse({"verdict": _verdict(technicals=90.0, macro=-6.0)})
    assert out["stance_label"] == "BULLISH"
    assert out["conviction"] == "moderate"
    # Still available for anything that ranks or sorts.
    assert out["composite_score"] == 41.2


def test_a_factor_with_no_data_is_absent_not_neutral():
    """A half-full bar for "we could not price this" reads as a neutral reading,
    which is a different claim from having no reading."""
    v = _verdict(technicals=90.0, gamma=None)
    for row in v["breakdown"]:
        if row["component"] == "gamma":
            row["unavailable"] = True
            row["status_reason"] = "no options chain"
    out = pulse.pulse({"verdict": v})
    gamma = next(f for f in out["factors"] if f["key"] == "gamma")
    assert gamma["unavailable"] is True
    assert gamma["bar"] is None, "an unpriced factor must not get a bar position"
    assert gamma["why_unavailable"] == "no options chain"
    assert out["factors_priced"] == 1 and out["factors_total"] == 2


def test_the_bar_keeps_the_sign_available_separately():
    """The bar is 0-100 because a bar cannot be negative, but a reader still has
    to be able to tell a bearish factor from a weak bullish one."""
    out = pulse.pulse({"verdict": _verdict(technicals=-80.0)})
    row = out["factors"][0]
    assert row["bar"] == pytest.approx(10.0)
    assert row["score"] == -80.0
    assert row["direction"] == "down"


def test_a_factor_inside_the_neutral_band_reads_flat():
    out = pulse.pulse({"verdict": _verdict(news=12.0, macro=-5.8)})
    assert all(f["direction"] == "flat" for f in out["factors"])


# ------------------------------------------------------------- the skill note

def test_the_skill_note_says_so_when_the_blend_loses():
    """The finding lives three clicks away on its own tab that nobody opens. It
    belongs on the panel it undermines."""
    note = pulse.skill_note({"comparison": [
        {"single_factor_ic": 0.09, "beats_single_factor": False},
        {"single_factor_ic": 0.11, "beats_single_factor": False},
    ]})
    assert note["beats_single"] is False
    assert "has not beaten" in note["text"]


def test_the_skill_note_says_so_when_the_blend_wins():
    note = pulse.skill_note({"comparison": [
        {"single_factor_ic": 0.02, "beats_single_factor": True},
    ]})
    assert note["beats_single"] is True
    assert "beat a single momentum factor" in note["text"]


def test_the_skill_note_admits_when_nothing_was_measured():
    """Silence would read as endorsement."""
    for payload in (None, {}, {"comparison": []},
                    {"comparison": [{"single_factor_ic": None}]}):
        note = pulse.skill_note(payload)
        assert note["available"] is False
        assert note["beats_single"] is None
        assert note["text"]


# ------------------------------------------------------------ why it's moving

def test_only_factors_above_the_floor_become_reasons():
    """Ranking every factor would present a -6 macro reading as a driver."""
    out = pulse.why({"verdict": _verdict(technicals=90.0, news=12.0, macro=-5.8),
                     "technicals": {"bias": "bullish"}})
    assert len(out["reasons"]) == 1
    assert out["reasons"][0]["factor"] == "technicals"


def test_reasons_are_ranked_by_strength_not_declaration_order():
    out = pulse.why({
        "verdict": _verdict(technicals=30.0, flow=70.0),
        "technicals": {"bias": "bullish"},
        "flow": {"volume": {"put_call_ratio": 0.53}},
    })
    assert [r["factor"] for r in out["reasons"]] == ["flow", "technicals"]


def test_at_most_three_reasons():
    out = pulse.why({
        "verdict": _verdict(technicals=90.0, gamma=80.0, flow=70.0, news=60.0, macro=50.0),
        "technicals": {"bias": "bullish"}, "gex": {"regime": {"state": "positive"}},
        "flow": {"volume": {"put_call_ratio": 0.5}}, "news": {"tone": "positive"},
    })
    assert len(out["reasons"]) == 3


def test_the_put_call_ratio_is_read_from_where_it_actually_lives():
    """It is nested under flow.volume, not on flow. Read off the wrong level it
    returns None and the one number this reason exists for vanishes silently."""
    out = pulse.why({"verdict": _verdict(flow=70.0),
                     "flow": {"volume": {"put_call_ratio": 0.531}}})
    evidence = " ".join(out["reasons"][0]["evidence"])
    assert "put/call 0.53" in evidence


def test_the_gamma_reason_reads_the_regime_state_not_a_flip_key():
    """There is no `flip` field on this payload. `regime.state` carries the sign
    and `levels` carries the strikes."""
    out = pulse.why({
        "verdict": _verdict(gamma=70.0),
        "gex": {"regime": {"state": "positive"},
                "totals": {"net_gex_per_1pct_millions": 12.3},
                "levels": {"gamma_pin": {"strike": 230.0}}},
    })
    r = out["reasons"][0]
    assert "dampening" in r["headline"]
    assert any("12.3M" in e for e in r["evidence"])
    assert any("230" in e for e in r["evidence"])


def test_no_driver_is_itself_reported_as_the_read():
    """Every factor flat is a finding — drift rather than a move with a thesis
    behind it — not an empty panel."""
    out = pulse.why({"verdict": _verdict(technicals=5.0, news=-2.0)})
    assert out["available"] is False
    assert out["reasons"] == []
    assert "drift" in out["reason_none"]


def test_why_does_not_claim_to_know_the_cause():
    """These are the model's own factors ranked by strength. That is an
    attribution, and a price can move on something no input here can see."""
    out = pulse.why({"verdict": _verdict(technicals=90.0), "technicals": {"bias": "bullish"}})
    assert "not a causal explanation" in out["method"]


# --------------------------------------------------------- what matters next

def _tech(spot, levels):
    return {"spot": spot, "support_resistance": levels}


def test_the_nearest_level_each_side_is_surfaced():
    out = pulse.whats_next({
        "technicals": _tech(230.0, [
            {"price": 235.65, "touches": 2}, {"price": 250.0, "touches": 1},
            {"price": 229.0, "touches": 3}, {"price": 200.0, "touches": 5},
        ]),
    }, today=date(2026, 9, 7))
    labels = [i["label"] for i in out["today"] if i["kind"] == "level"]
    assert any("235.65" in l for l in labels)
    assert any("229.00" in l for l in labels)
    # Not the far ones: two levels a reader is about to care about, not four.
    assert not any("250" in l or "200.00" in l for l in labels)


def test_the_expiry_list_is_dates_not_rows():
    """`expiries` is {available: [ISO strings]}. Iterating it as dicts and
    calling .get on a string is the bug this guards."""
    out = pulse.whats_next(
        {"expiries": {"available": ["2026-09-04", "2026-09-09", "2026-09-11"]}},
        today=date(2026, 9, 7))
    week = [i for i in out["this_week"] if i["kind"] == "expiry"]
    assert len(week) == 1
    assert "2026-09-09" in week[0]["label"], "must skip the expiry already past"


def test_earnings_inside_the_window_lands_this_week_and_far_ones_do_not():
    near = pulse.whats_next({"next_earnings_date": "2026-09-11"}, today=date(2026, 9, 7))
    far = pulse.whats_next({"next_earnings_date": "2026-11-17"}, today=date(2026, 9, 7))
    assert any(i["kind"] == "earnings" for i in near["this_week"])
    assert not any(i["kind"] == "earnings" for i in far["this_week"] + far["today"])


def test_macro_rows_are_read_from_the_at_timestamp():
    """events.upcoming() rows carry an ISO `at` with an offset, not a `date`."""
    out = pulse.whats_next({}, calendar=[
        {"title": "Consumer Price Index", "short": "CPI",
         "at": "2026-09-11T08:30:00-04:00", "agency_short": "BLS", "importance": 3},
        {"title": "Ancient release", "at": "2026-01-01T08:30:00-05:00"},
    ], today=date(2026, 9, 7))
    week = [i for i in out["this_week"] if i["kind"] == "macro"]
    assert len(week) == 1
    assert "CPI" in week[0]["label"] and "BLS" in week[0]["detail"]


def test_an_empty_board_is_stated_rather_than_blank():
    out = pulse.whats_next({}, today=date(2026, 9, 7))
    assert out["available"] is False
    assert "no catalyst on the board" in out["reason_none"]


def test_whats_next_does_not_present_itself_as_a_forecast():
    out = pulse.whats_next({"technicals": _tech(230.0, [{"price": 235.0, "touches": 2}])},
                           today=date(2026, 9, 7))
    assert "is a forecast" in out["method"], "must disclaim, however it is worded"
