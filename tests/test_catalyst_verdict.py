"""The verdict has to see the catalyst, not just the chart.

Reported on RARE the morning after the FDA cleared its Sanfilippo gene therapy.
The stock gapped ~14% on an approval that was public news, and the verdict read
"leaning bearish, low conviction". The measured breakdown:

    technicals  -75.0  x 34%  =  -25.5
    gamma       +20.0  x 24%  =   +4.8
    flow        -60.0  x 20%  =  -12.0
    news        +63.2  x 12%  =   +7.6
    macro       +14.2  x 10%  =   +1.4
                               ------
                                 -23.7

The news input was not broken: at +63.2 it was near its own +70 cap and had
registered the approval. It was outvoted. Technicals carried nearly three times
the weight, and `trend_score` on that morning was measuring the drift *into* the
binary, not its resolution. One of the six major headlines was "RARE Stock Hits
Fresh 52-Week Low As Sanfilippo Drug Ruling Nears", filed 44 hours before.

So the chart was describing a regime the catalyst had ended, at full weight.
"""
from __future__ import annotations

import pytest

from app import news as news_mod
from app.analytics import swing


def _article(tier="breaking", importance="high", kind="regulatory / clinical",
             age=1.0, about=True, sentiment=10.0, title="FDA approval"):
    return {"tier": tier, "age_hours": age, "about_company": about,
            "title": title, "tone": "bullish", "sentiment_score": sentiment,
            "catalysts": [{"type": kind, "importance": importance}]}


# ------------------------------------------------------------- detection


def test_a_fresh_major_company_catalyst_is_material():
    read = news_mod.material_catalyst({"articles": [_article()]})
    assert read["material"] is True
    assert read["kinds"] == ["regulatory / clinical"]
    assert read["count"] == 1


@pytest.mark.parametrize("kwargs,why", [
    ({"about": False}, "a market-wide headline is not this company's catalyst"),
    ({"age": 200.0}, "outside the window the chart has already absorbed it"),
    ({"tier": "background"}, "no catalyst matched, so the taxonomy rated it noise"),
    ({"tier": "notable"}, "notable is below the bar on purpose"),
    ({"importance": "low"}, "a product launch is not a binary resolving"),
    ({"importance": "medium"}, "an analyst note is not either"),
])
def test_what_does_not_count_as_material(kwargs, why):
    read = news_mod.material_catalyst({"articles": [_article(**kwargs)]})
    assert read["material"] is False, why


def test_no_news_at_all_is_not_material():
    assert news_mod.material_catalyst({})["material"] is False
    assert news_mod.material_catalyst({"articles": []})["material"] is False


def test_direction_comes_from_the_material_headlines_only():
    """The overall net sentiment averages them with background coverage, which
    is how a resolved binary ends up reading like a mildly positive week."""
    read = news_mod.material_catalyst({"articles": [
        _article(sentiment=10.0),
        _article(sentiment=8.0, age=3.0),
        _article(tier="background", importance="low", sentiment=-9.0),
    ]})
    assert read["lean"] == pytest.approx(9.0, abs=0.01)
    assert read["count"] == 2


def test_the_freshest_is_the_one_reported():
    read = news_mod.material_catalyst({"articles": [
        _article(age=40.0, title="old"), _article(age=2.0, title="new")]})
    assert read["freshest_hours"] == 2.0
    assert read["headline"] == "new"


# ------------------------------------------------------------ reweighting


@pytest.fixture(autouse=True)
def _gamma(monkeypatch):
    """RARE's gamma read, stubbed.

    All five inputs have to be present or the weights renormalise over the
    survivors and the published percentages are no longer the ones a reader
    sees. A first version passed an empty gex and no macro, which dropped two
    components, pushed the composite to a flatly bearish -37 and made
    `weight_pct` 26 rather than 17. That is correct arithmetic on the wrong
    fixture: the point here is the real breakdown.
    """
    monkeypatch.setattr(swing, "_gamma_score", lambda gex, spot: 20.0)


def _verdict(trend, news_articles, net_sentiment=5.27):
    """RARE's own numbers the morning after the approval."""
    return swing.verdict(
        {"trend_score": trend},
        {}, {"flow_score": -60.0},
        {"net_sentiment": net_sentiment, "days_to_earnings": 46,
         "articles": news_articles},
        {"risk_score": 14.2}, 14.77)


def test_a_material_catalyst_moves_weight_off_the_chart():
    out = _verdict(-75.0, [_article()])
    weights = out["effective_weights"]
    assert weights["technicals"] == pytest.approx(0.17, abs=0.001)
    assert weights["news"] == pytest.approx(0.29, abs=0.001)
    # Nothing is created: what the chart loses, the news gains.
    assert sum(weights.values()) == pytest.approx(sum(swing.WEIGHTS.values()), abs=1e-9)


def test_no_catalyst_leaves_the_nominal_weights_alone():
    out = _verdict(-75.0, [_article(tier="background", importance="low")])
    assert out["effective_weights"] == swing.WEIGHTS


def test_the_rare_case_no_longer_reads_bearish():
    """The regression this exists for. Same inputs, catalyst included."""
    before = _verdict(-75.0, [_article(tier="background", importance="low")])
    after = _verdict(-75.0, [_article()])
    assert before["stance"] == "leaning bearish"
    assert after["stance"] == "neutral"
    assert after["composite_score"] > before["composite_score"]


def test_the_reweighting_is_published_not_hidden():
    """A score you can audit. `nominal_weight_pct` is what the input would have
    carried with everything available and no catalyst, so the two together say
    the weight moved and by how much."""
    out = _verdict(-75.0, [_article()])
    rows = {b["component"]: b for b in out["breakdown"]}
    assert rows["technicals"]["weight_pct"] == 17.0
    assert rows["technicals"]["nominal_weight_pct"] == 34.0
    assert rows["news"]["weight_pct"] == 29.0
    assert rows["news"]["nominal_weight_pct"] == 12.0


def test_the_catalyst_rides_on_the_verdict():
    out = _verdict(-75.0, [_article()])
    assert out["catalyst"]["material"] is True
    assert "regulatory / clinical" in out["catalyst"]["kinds"]


def test_the_reader_is_told_the_chart_predates_the_catalyst():
    out = _verdict(-75.0, [_article()])
    joined = " ".join(out["conflicts"])
    assert "measuring the period before it" in joined
    assert "half its usual weight" in joined


def test_a_catalyst_against_the_chart_is_named_as_such():
    out = _verdict(-75.0, [_article()])
    assert any("point opposite ways" in c for c in out["conflicts"])


def test_a_catalyst_agreeing_with_the_chart_raises_no_disagreement():
    out = _verdict(70.0, [_article()])
    assert not any("point opposite ways" in c for c in out["conflicts"])


def test_the_damping_is_not_a_deletion():
    """Where price sits against its levels still matters. What stops being
    informative is the trend through them."""
    assert 0 < swing.CATALYST_TECH_DAMPING < 1
    out = _verdict(-75.0, [_article()])
    assert out["effective_weights"]["technicals"] > 0


# ------------------------------------------------------------- news score


def test_an_imminent_print_still_halves_tone_without_a_catalyst():
    plain = swing._news_score({"net_sentiment": 5.0, "days_to_earnings": 3}, None)
    assert plain == pytest.approx(30.0, abs=0.01)


def test_a_resolved_catalyst_suppresses_the_earnings_halving():
    """The halving exists because an unresolved earnings date makes tone
    unreliable. A cleared approval is the opposite situation, and a company
    reporting in a week can also be approved in a week."""
    with_cat = swing._news_score({"net_sentiment": 5.0, "days_to_earnings": 3},
                                 {"material": True})
    assert with_cat == pytest.approx(60.0, abs=0.01)


# ----------------------------------------------------------------- copy


@pytest.mark.parametrize("hours,expected", [
    (1.0, "an hour ago"), (1.4, "an hour ago"), (3.0, "3 hours ago"),
    (23.0, "23 hours ago"), (30.0, "a day ago"), (60.0, "2 days ago"),
    (None, "recently"),
])
def test_the_age_reads_as_english(hours, expected):
    """Two bugs here. The first version printed "1 hours ago", and its bands
    met at the same boundary from both sides, so "a day ago" was unreachable:
    anything at or above 36 hours was also at least 1.5 days."""
    assert news_mod.age_phrase(hours) == expected


def test_the_headline_count_agrees_with_its_noun():
    assert news_mod.count_words(1, "headline") == "One headline"
    assert news_mod.count_words(6, "headline") == "6 headlines"


# ================================================ the investing tab =========
#
# Same detector, deliberately applied a different way. The swing verdict dampens
# its trend input because a `trend_score` read the morning after a binary
# resolves is mostly pre-event bars. That argument does not transfer to a
# 200-week average, which is *supposed* to ignore one day: damping it because
# something happened on Tuesday would defeat the instrument. So the long-run
# factors are left alone and the catalyst is added as a factor of its own.

from app.analytics import longterm


class _P:
    """Enough provider for analyse_holding, with a falling 12-year history."""

    def __init__(self, n=3200):
        import numpy as np
        import pandas as pd
        idx = pd.date_range("2014-01-01", periods=n, freq="B")
        fall = np.linspace(120.0, 15.0, n)
        self._df = pd.DataFrame({"Close": fall, "High": fall * 1.01,
                                 "Low": fall * 0.99, "Open": fall,
                                 "Volume": [1e6] * n}, index=idx)

    def history(self, ticker, period="2y", interval="1d"):
        return self._df

    def quote(self, ticker):
        return {"name": "Test", "price": 15.0, "forward_pe": 72.8,
                "dividend_yield": 0.0}


def _holding(articles):
    return longterm.analyse_holding(
        _P(), "RARE", {"net_sentiment": 5.27, "articles": articles})


def test_the_investing_tab_records_a_resolved_catalyst():
    """RARE scored -66 and "avoid new capital until the trend repairs" on the
    day the FDA approved its first therapy, with no way to say so at all."""
    out = _holding([_article()])
    labels = [f["label"] for f in out["conviction_factors"]]
    assert "Resolved catalyst" in labels
    row = next(f for f in out["conviction_factors"] if f["label"] == "Resolved catalyst")
    assert row["points"] == 12.0
    assert row["kind"] == "catalyst"


def test_a_negative_catalyst_counts_against():
    out = _holding([_article(sentiment=-9.0, kind="legal / regulatory")])
    row = next(f for f in out["conviction_factors"] if f["label"] == "Resolved catalyst")
    assert row["points"] == -12.0


def test_a_directionless_catalyst_is_recorded_at_zero():
    """Like valuation between its thresholds: "the model looked and shrugged"
    beats the factor silently vanishing."""
    out = _holding([_article(sentiment=0.0)])
    row = next(f for f in out["conviction_factors"] if f["label"] == "Resolved catalyst")
    assert row["points"] == 0.0
    assert "no clear direction" in row["detail"]


def test_no_catalyst_adds_no_factor():
    out = _holding([_article(tier="background", importance="low")])
    assert not any(f["label"] == "Resolved catalyst" for f in out["conviction_factors"])


def test_the_panel_still_works_with_no_news_at_all():
    """Twelve years of prices must not fail because a headline feed is down."""
    out = longterm.analyse_holding(_P(), "RARE", None)
    assert out["conviction_score"] is not None
    assert out["catalyst"]["material"] is False


def test_the_secular_trend_is_not_damped_by_a_catalyst():
    """The opposite of the swing treatment, and on purpose. A 200-week average
    that flinches at one day is not a 200-week average."""
    with_cat = _holding([_article()])
    without = _holding([_article(tier="background", importance="low")])
    def trend(out):
        return {f["label"]: f["points"] for f in out["conviction_factors"]
                if f["label"] in ("200-week trend", "40-week trend")}
    assert trend(with_cat) == trend(without)
    # And pinned to the documented weights, because comparing the two sides
    # only catches a *conditional* change: damping the trend unconditionally
    # moves both and slips through. That mutation did.
    assert trend(with_cat)["200-week trend"] == -25.0
    assert trend(with_cat)["40-week trend"] == -8.0


def test_the_catalyst_cannot_outweigh_the_multi_year_record():
    """One approval does not erase five years.

    Stated as the arithmetic rather than as a label, because the label depends
    on where the rest of the score lands and this fixture is not RARE. What
    holds either way: the catalyst moves the score by exactly its own twelve
    points and leaves a deeply negative long-run record negative. Measured on
    the real symbol, RARE went from -66 to -54 and stayed "low" conviction,
    which is the honest answer for a long-horizon read on a company
    underperforming SPY by 43%/yr at a 72.8 forward P/E.
    """
    with_cat = _holding([_article()])
    without = _holding([_article(tier="background", importance="low")])
    assert with_cat["conviction_score"] == without["conviction_score"] + 12.0
    assert with_cat["conviction_score"] < 0, "one headline does not rescue the record"


def test_the_scale_admits_the_new_factor():
    """`max_possible` is the sum of the best case for every factor. Leaving it
    at 85 with a twelve-point factor in play would misreport how close to
    "perfect" a score is."""
    out = _holding([_article()])
    scale = out["conviction_scale"]
    assert scale["max_possible"] == 97
    assert scale["min_possible"] == -86


def test_both_tabs_share_one_detector():
    """Two copies would drift, and the swing one already carries the measured
    reasoning for every condition."""
    lt = open("app/analytics/longterm.py").read()
    sw = open("app/analytics/swing.py").read()
    assert "news_mod.material_catalyst(" in lt
    assert "material_catalyst(news)" in sw
    assert "def material_catalyst(" in open("app/news.py").read()
    assert "def material_catalyst(" not in lt and "def material_catalyst(" not in sw
