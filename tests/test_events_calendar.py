"""Impact bands, release explanations and the previous-print lookup.

The calendar's job is to say what is scheduled without ever implying what it will
contain, so these tests care as much about what the module refuses to assert as
about what it produces.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app import events


# ------------------------------------------------------------------ impact

@pytest.mark.parametrize("weight,band", [
    (10, "high"),    # CPI, jobs
    (9, "high"),     # PPI
    (8, "high"),     # the boundary is inclusive
    (7, "medium"),   # JOLTS
    (5, "medium"),   # boundary
    (4, "low"),
    (2, "low"),      # county wages
])
def test_impact_bands(weight, band):
    assert events._impact(weight) == band


def test_impact_bands_all_have_a_note():
    """Every band a row can land in must have text explaining what it means."""
    for band in ("high", "medium", "low"):
        assert events.IMPACT_BANDS[band].strip()


def test_headline_releases_land_in_sensible_bands():
    """CPI and jobs are high; the state/county tail is low."""
    assert events._impact(events.HEADLINE_RELEASES["consumer price index"][1]) == "high"
    assert events._impact(events.HEADLINE_RELEASES["employment situation"][1]) == "high"
    assert events._impact(events.HEADLINE_RELEASES["county employment and wages"][1]) == "low"


# ------------------------------------------------------------ explanations

def test_why_matches_headline_releases():
    assert "mandate" in events._why("Consumer Price Index")
    assert "factory gate" in events._why("Producer Price Index")


def test_why_is_case_insensitive_and_matches_within_a_title():
    assert events._why("u.s. consumer price index for july") == \
        events._why("Consumer Price Index")


def test_why_covers_fomc_and_cot_which_are_titled_by_their_own_builders():
    assert "dot plot" in events._why("FOMC meeting")
    assert "crowded" in events._why("CFTC Commitments of Traders", "CFTC")


def test_unknown_bls_release_gets_the_honest_fallback():
    """The BLS tail gets a note that claims no significance for itself."""
    text = events._why("Worker Displacement", "BLS")
    assert "outside the set" in text
    assert "rather than because a reaction is expected" in text


def test_non_bls_unknown_release_gets_no_invented_explanation():
    assert events._why("Some Unlisted Release", "XYZ") == ""


def test_explanations_never_predict_direction():
    """A definition must not smuggle in a forecast.

    'A hot CPI is bearish' is a claim about what the market will do next, and it
    is often wrong because the reaction depends on positioning going in. These
    notes explain mechanism only, so the forecasting verbs must not appear.
    """
    banned = ("will rise", "will fall", "will drop", "expect a", "should rally",
              "is bullish", "is bearish", "buy ", "sell ")
    for needle, text in events.WHY_IT_MATTERS.items():
        low = text.lower()
        for phrase in banned:
            assert phrase not in low, "{} predicts: {}".format(needle, phrase)


# --------------------------------------------------------- previous print

def _feed(headline, days_old):
    published = (datetime.now(timezone.utc) - timedelta(days=days_old)).isoformat()
    return {"entries": [{"title": headline, "url": "https://example.gov/r",
                         "published": published}]}


def test_previous_release_reports_the_last_print(monkeypatch):
    monkeypatch.setattr(events.feeds, "load_source",
                        lambda src, force=False: _feed("CPI rises 0.1% in July", 2))
    got = events._last_release("Consumer Price Index")
    assert got["headline"] == "CPI rises 0.1% in July"
    assert got["age_days"] == 2


def test_previous_release_rejects_a_stale_feed(monkeypatch):
    """A print older than the guard is not 'the previous print'.

    If the feed stops updating, the last thing in it stops being the previous
    reading and becomes an old headline presented as a current one.
    """
    monkeypatch.setattr(events.feeds, "load_source",
                        lambda src, force=False: _feed("CPI rises 0.4% in March", 400))
    assert events._last_release("Consumer Price Index") is None


def test_previous_release_only_for_series_with_a_feed(monkeypatch):
    """No feed means no row, rather than a lookup against the wrong series."""
    monkeypatch.setattr(events.feeds, "load_source",
                        lambda src, force=False: _feed("anything", 1))
    assert events._last_release("Worker Displacement") is None
    assert events._last_release("") is None


def test_previous_release_survives_a_dead_feed(monkeypatch):
    """A previous-print lookup must never take the calendar down with it."""
    def boom(src, force=False):
        raise RuntimeError("connection reset")
    monkeypatch.setattr(events.feeds, "load_source", boom)
    assert events._last_release("Consumer Price Index") is None


def test_previous_release_handles_an_empty_or_undated_feed(monkeypatch):
    monkeypatch.setattr(events.feeds, "load_source", lambda src, force=False: {"entries": []})
    assert events._last_release("Consumer Price Index") is None

    monkeypatch.setattr(events.feeds, "load_source", lambda src, force=False:
                        {"entries": [{"title": "CPI up", "published": None}]})
    got = events._last_release("Consumer Price Index")
    assert got is not None and got["age_days"] is None


def test_previous_release_ignores_an_unparseable_date(monkeypatch):
    """A bad timestamp must not be read as age zero, nor raise."""
    monkeypatch.setattr(events.feeds, "load_source", lambda src, force=False:
                        {"entries": [{"title": "CPI up", "published": "not a date"}]})
    got = events._last_release("Consumer Price Index")
    assert got is not None and got["age_days"] is None


def test_no_forecast_field_is_ever_emitted():
    """There is no consensus source, so no row may carry a forecast.

    Guards against a later change quietly adding a 'forecast' key filled from a
    free mirror of somebody's licensed survey, which is how a calendar starts
    publishing stale estimates as though they were current.
    """
    assert not hasattr(events, "FORECASTS")
    for text in events.WHY_IT_MATTERS.values():
        assert "consensus is" not in text.lower()
