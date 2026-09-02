"""The fear-and-greed reading.

The point worth protecting here is honesty about provenance: this is not CNN's
index and must never present itself as one, because three of their seven inputs
need data free sources do not carry.
"""
from __future__ import annotations
import pandas as pd, pytest
from app.analytics import sentiment as sn


def _f(vals):
    return pd.DataFrame({"Close": vals, "High": vals, "Low": vals,
                         "Open": vals, "Volume": [1e6] * len(vals)})


class _P:
    def __init__(self, frames): self.frames = frames
    def batch_history(self, symbols, period="2y", interval="1d"):
        return {s: self.frames.get(s) for s in symbols if s in self.frames}


def _all(n=420, rising=True):
    up = [100 + i * 0.2 for i in range(n)]
    flat = [100.0] * n
    frames = {sn.SPY: _f(up if rising else flat), sn.VIX: _f(flat),
              sn.TLT: _f(flat), sn.HYG: _f(flat), sn.LQD: _f(flat)}
    for e in sn.SECTORS:
        frames[e["symbol"]] = _f(up if rising else flat)
    return frames


def test_scores_land_on_the_published_scale():
    r = sn.build(_P(_all()))
    assert r["available"] is True
    assert 0 <= r["score"] <= 100


@pytest.mark.parametrize("score,label", [
    (5, "Extreme Fear"), (35, "Fear"), (50, "Neutral"), (65, "Greed"), (90, "Extreme Greed"),
])
def test_band_labels(score, label):
    assert sn._label(score) == label


def test_acceleration_reads_greedier_than_deceleration():
    """Percentile scoring measures change against a recent norm, not level.

    This is the semantic that replaced fixed saturation widths, and it is worth
    stating plainly: a market rising at a CONSTANT rate is not greedy by this
    gauge, because it has been equally strong the whole way and today's reading
    sits mid-distribution. What registers is a market pulling away from its own
    recent behaviour.
    """
    n = 400
    calm = [100 + i * 0.1 for i in range(n)]
    surge = [100 + i * 0.1 for i in range(n - 40)] + \
            [100 + (n - 40) * 0.1 + j * 1.2 for j in range(40)]

    def board(series):
        frames = {sn.SPY: _f(series), sn.VIX: _f([15.0] * n), sn.TLT: _f([100.0] * n),
                  sn.HYG: _f([100.0] * n), sn.LQD: _f([100.0] * n)}
        for e in sn.SECTORS:
            frames[e["symbol"]] = _f(series)
        return sn.build(_P(frames))["score"]

    assert board(surge) > board(calm)


def test_steady_ramp_is_not_scored_as_extreme():
    """Guards the old bug: a constant trend used to peg the gauge near maximum."""
    score = sn.build(_P(_all(rising=True)))["score"]
    assert score < 75, "a constant ramp should not read as extreme greed"


def test_low_vix_reads_as_greed_not_fear():
    """Volatility is inverted; the wrong sign would invert the whole gauge.

    Tested through build() rather than against _scale, because the inversion
    lives at the call site — checking the helper in isolation tests the wrong
    thing and passes while the gauge is upside down.
    """
    def with_vix(series):
        frames = _all()
        frames[sn.VIX] = _f(series)
        return sn.build(_P(frames))

    # The move has to be recent enough that the 50-day average has not caught up:
    # 50 flat bars at the new level leaves VIX sitting exactly on its own average
    # and the component correctly reads 50, which tests nothing.
    calm = with_vix([30.0] * 280 + [14.0] * 20)
    panic = with_vix([14.0] * 280 + [30.0] * 20)
    calm_c = next(c for c in calm["components"] if c["key"] == "volatility")
    panic_c = next(c for c in panic["components"] if c["key"] == "volatility")
    assert calm_c["score"] > 50 > panic_c["score"]


def test_history_is_computed_not_stored():
    """Comparisons must be real on day one rather than blank for a month."""
    r = sn.build(_P(_all()))
    assert set(r["history"]) == {"prev_close", "week", "month"}
    for h in r["history"].values():
        assert isinstance(h["score"], float) and h["label"]


def test_missing_inputs_reduce_the_count_rather_than_the_score():
    """A missing input redistributes; it must not be scored as zero (max fear)."""
    frames = _all()
    for k in (sn.HYG, sn.LQD, sn.TLT):
        frames.pop(k)
    r = sn.build(_P(frames))
    assert r["available"] is True
    assert r["inputs_used"] < r["inputs_total"]
    # The surviving inputs must still produce a real reading rather than
    # collapsing toward zero, which is what scoring a missing input as 0 would do.
    assert 20 < r["score"] < 80


def test_no_inputs_says_so():
    assert sn.build(_P({}))["available"] is False


def test_provider_failure_does_not_raise():
    class Broken:
        def batch_history(self, *a, **k): raise RuntimeError("down")
    assert sn.build(Broken())["available"] is False


def test_every_component_is_explained():
    """Each input needs a label, a note, a plain question and three readings."""
    for key in sn.WEIGHTS:
        assert key in sn.COMPONENT_LABELS and key in sn.COMPONENT_NOTES
        assert len(sn.COMPONENT_NOTES[key]) > 40
        assert key in sn.COMPONENT_QUESTIONS
        assert sn.COMPONENT_QUESTIONS[key].endswith("?"), key
        assert len(sn.COMPONENT_READINGS[key]) == 3, key


def test_weights_are_reported_as_actually_applied():
    """A missing input redistributes, so the printed weight must reflect the
    blend that produced the score rather than the nominal table."""
    r = sn.build(_P(_all()))
    total = sum(c["weight_pct"] for c in r["components"] if c["score"] is not None)
    assert total == pytest.approx(100.0, abs=0.5)


def test_components_are_ordered_by_weight():
    r = sn.build(_P(_all()))
    weights = [c["weight_pct"] for c in r["components"]]
    assert weights == sorted(weights, reverse=True)


def test_data_quality_reflects_available_inputs():
    full = sn.build(_P(_all()))
    assert full["data_quality"] == "healthy"
    frames = _all()
    for k in (sn.HYG, sn.LQD, sn.TLT):
        frames.pop(k)
    assert sn.build(_P(frames))["data_quality"] in ("partial", "thin")


def test_reading_text_matches_the_band():
    """A component scoring high must not be described with the low text."""
    r = sn.build(_P(_all()))
    for c in r["components"]:
        if c["score"] is None:
            continue
        high, mid, low = sn.COMPONENT_READINGS[c["key"]]
        expected = high if c["score"] >= 60 else low if c["score"] <= 40 else mid
        assert c["reading"] == expected


def test_methodology_version_is_published():
    """A reading has to be placeable against the method that produced it."""
    assert sn.build(_P(_all()))["methodology"] == sn.METHODOLOGY_VERSION


def test_method_disclaims_cnn_and_names_the_gap():
    note = sn.build(_P(_all()))["method"]
    assert "not CNN's" in note
    assert "McClellan" in note and "put/call" in note


def test_caveat_refuses_to_treat_the_gauge_as_predictive():
    c = sn.build(_P(_all()))["caveat"]
    assert "never what happens next" in c
