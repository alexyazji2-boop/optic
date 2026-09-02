"""The catalyst library and catalyst mode.

The load-bearing test here is the EDGAR gate. A model asked which companies
benefit from a policy will produce confident, plausible, wrong tickers, and a
wrong ticker on a research page is worse than one fewer name — so nothing
unvalidated may reach the store.
"""

from __future__ import annotations

import pytest

from app import catalysts, catalyst_live


DIRECTORY = {"NVDA": "NVIDIA CORP", "MP": "MP Materials Corp. / DE", "XOM": "Exxon Mobil"}


def test_invented_tickers_are_dropped():
    raw = [{"ticker": "NVDA", "directness": "direct", "strength": "strong"},
           {"ticker": "ZZZQ", "directness": "direct", "strength": "strong"},
           {"ticker": "LITHIUMCO", "directness": "direct", "strength": "strong"}]
    out = catalysts.validate_companies(raw, DIRECTORY)
    assert [c["ticker"] for c in out] == ["NVDA"]


def test_company_name_comes_from_edgar_not_the_model():
    """The ticker is what gets verified, so the name must share its source."""
    raw = [{"ticker": "MP", "name": "Mountain Pass Mining Incorporated"}]
    out = catalysts.validate_companies(raw, DIRECTORY)
    assert out[0]["name"] == "MP Materials Corp. / DE"


def test_duplicate_tickers_collapse():
    raw = [{"ticker": "NVDA", "strength": "strong"}, {"ticker": "NVDA", "strength": "weak"}]
    assert len(catalysts.validate_companies(raw, DIRECTORY)) == 1


def test_bad_enum_values_fall_back_rather_than_render():
    raw = [{"ticker": "NVDA", "directness": "enormous", "strength": "gigantic"}]
    out = catalysts.validate_companies(raw, DIRECTORY)
    assert out[0]["directness"] in catalysts.DIRECTNESS
    assert out[0]["strength"] in catalysts.STRENGTH


def test_empty_directory_keeps_nothing():
    """If EDGAR is down, no company link is better than an unverified one."""
    raw = [{"ticker": "NVDA", "directness": "direct"}]
    assert catalysts.validate_companies(raw, {}) == []


def test_company_count_is_capped():
    raw = [{"ticker": "NVDA"} for _ in range(40)]
    assert len(catalysts.validate_companies(raw, DIRECTORY)) <= catalysts.MAX_COMPANIES


# ---------------------------------------------------------------- relevance

@pytest.mark.parametrize("horizon,age,expected", [
    ("short-term", 10, True),
    ("short-term", 90, False),
    ("medium-term", 90, True),
    ("medium-term", 400, False),
    ("long-term", 400, True),
    ("long-term", 900, False),
])
def test_relevance_depends_on_horizon(horizon, age, expected):
    """A structural catalyst must outlive a short-term one, not share an expiry."""
    assert catalysts._is_relevant(horizon, age) is expected


def test_unknown_age_is_treated_as_relevant():
    assert catalysts._is_relevant("medium-term", None) is True


# ------------------------------------------------------------ catalyst mode

def test_consensus_is_absent_and_explained():
    """The panel must never carry an invented estimate.

    Guards the decision directly: if a consensus field ever appears here it has
    to come with a real licensed source, not a free mirror.
    """
    import inspect
    src = inspect.getsource(catalyst_live)
    assert '"available": False' in src
    assert "licensed product" in src


def test_reaction_assets_cover_each_macro_channel():
    """One asset per question; a board missing duration or the dollar is blind."""
    symbols = {a["symbol"] for a in catalyst_live.REACTION_ASSETS}
    for needed in ("SPY", "QQQ", "IWM", "TLT", "UUP", "GLD"):
        assert needed in symbols
    for a in catalyst_live.REACTION_ASSETS:
        assert a["reads"], "every asset must say what it is a read on"


def test_reaction_survives_a_dead_provider():
    class Broken:
        def batch_history(self, *a, **k):
            raise RuntimeError("down")
    assert catalyst_live.market_reaction(Broken())["available"] is False


def test_window_is_wide_enough_to_survive_a_weekend():
    """36 hours went blank on a Friday-evening read of a Wednesday print."""
    assert catalyst_live.MAX_AGE_HOURS >= 48
