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


# ============================================ the dossier overview =========
#
# That tab renders Optic Pulse and nothing else about the judgement, and Pulse
# does not render conflicts. So on the morning RARE's approval landed it showed
# "neutral" over a Momentum bar at -75 with nothing saying the chart was
# measuring the week before the approval. The stance was right and
# unexplained, which is the combination that reads as the panel being broken.

APP_JS = open("static/app.js").read()
CSS = open("static/styles.css").read()


def test_pulse_carries_the_catalyst_as_its_own_field():
    """Not left inside `conflicts`, so a caller can render one line from it
    without parsing prose out of an array."""
    from app.analytics import pulse
    read = pulse.pulse({"verdict": {
        "stance": "neutral", "catalyst": {"material": True, "kinds": ["M&A"]},
        "conflicts": [],
    }})
    assert read["catalyst"]["material"] is True
    assert read["catalyst"]["kinds"] == ["M&A"]


def test_pulse_defaults_the_catalyst_rather_than_omitting_it():
    """A missing key and "no catalyst" must not be the same shape to a client."""
    from app.analytics import pulse
    read = pulse.pulse({"verdict": {"stance": "neutral"}})
    assert read["catalyst"] == {"material": False}


def test_the_overview_renders_the_catalyst_above_the_bars():
    """A caveat printed after the thing it qualifies is a footnote. This one
    changes how the bars are read, so it goes before the disclosure."""
    fn = APP_JS[APP_JS.index("function renderOpticPulse(d) {"):]
    fn = fn[:fn.index("\n/* ") if "\n/* " in fn else len(fn)]
    assert "pulseCatalystLine(p.catalyst)" in fn
    assert fn.index("pulseCatalystLine") < fn.index("pl-bars"), \
        "it has to come before the factor bars it explains"


def test_the_catalyst_line_is_absent_when_there_is_none():
    fn = APP_JS[APP_JS.index("function pulseCatalystLine(cat) {"):]
    fn = fn[:fn.index("\nfunction renderOpticPulse")]
    assert "cat.material !== true) return ''" in fn


def test_the_catalyst_line_agrees_with_its_own_count():
    """"One headline ... the freshest" has nothing to be freshest of."""
    fn = APP_JS[APP_JS.index("function pulseCatalystLine(cat) {"):]
    fn = fn[:fn.index("\nfunction renderOpticPulse")]
    assert "'One headline'" in fn and "headlines`" in fn
    assert "'filed'" in fn and "'the freshest'" in fn


def test_the_overview_line_does_not_repeat_the_weighting_arithmetic():
    """The Options tab prints the reweighting next to the weights, where it
    belongs. Here the reader needs only that a catalyst landed and the chart
    predates it."""
    fn = APP_JS[APP_JS.index("function pulseCatalystLine(cat) {"):]
    fn = fn[:fn.index("\nfunction renderOpticPulse")]
    assert "half its usual weight" not in fn
    assert "predate it" in fn


def test_the_catalyst_line_is_styled():
    assert ".pl-catalyst {" in CSS


# =============================================== the entry plan ============
#
# A resolved catalyst changes what the plan is built on, twice over. The
# trigger levels come from Fibonacci structure and the gamma walls, both read
# off price history that mostly predates the event. The stop is 1.5 x ATR, and
# ATR is inflated by the gap day itself, so the stop sits wider and the size
# lands smaller than the pre-event chart implied.
#
# The premium warning is the mirror of the earnings one already there. That
# says do not buy vol into a print; this says the print has happened.

import numpy as np
import pandas as pd

from app.analytics import entry as entry_mod


def _chain(spot=15.0):
    """A minimal chain with the columns rank_strikes actually reads."""
    rows = []
    for strike in (12.0, 14.0, 15.0, 16.0, 18.0):
        for is_call in (True, False):
            moneyness = (spot - strike) / spot if is_call else (strike - spot) / spot
            delta = float(np.clip(0.5 + moneyness * 2.0, 0.05, 0.95))
            rows.append({
                "contract": "X", "expiry": "2026-12-18", "dte": 60, "tau": 60 / 365.0,
                "strike": strike, "is_call": is_call, "last": 1.0,
                "bid": 0.95, "ask": 1.05, "mid": 1.0, "volume": 500,
                "open_interest": 2000, "iv": 0.8, "in_the_money": False,
                "delta": delta if is_call else -delta,
                "gamma": 0.05, "theta": -0.02, "vega": 0.03,
                "spread_pct": 5.0, "break_even": strike + 1.0,
            })
    return pd.DataFrame(rows)


def _frame(n=320, spot=15.0):
    idx = pd.date_range("2025-01-01", periods=n, freq="B")
    close = np.linspace(spot * 1.6, spot, n)
    return pd.DataFrame({"Close": close, "High": close * 1.02, "Low": close * 0.98,
                         "Open": close, "Volume": [1e6] * n}, index=idx)


def _plan(articles, stance="bullish"):
    from app.analytics import technicals as tech_mod
    frame = _frame()
    return entry_mod.build_plan(
        _chain(), 15.0, {"stance": stance, "conviction": "moderate"},
        tech_mod.analyse(frame), {},
        {"days_to_earnings": 46, "net_sentiment": 5.0, "articles": articles},
        rate=0.04, div=0.0, history=frame)


def test_the_entry_plan_warns_that_its_levels_predate_the_catalyst():
    plan = _plan([_article()])
    joined = " ".join(plan.get("warnings") or [])
    assert "catalyst resolved" in joined
    assert "predates it" in joined
    assert "ATR the gap itself inflated" in joined


def test_no_catalyst_leaves_the_plan_warnings_alone():
    plan = _plan([_article(tier="background", importance="low")])
    joined = " ".join(plan.get("warnings") or [])
    assert "catalyst resolved" not in joined


def test_the_premium_warning_is_the_mirror_of_the_earnings_one():
    """The earnings warning says do not buy vol into a print. After a resolved
    binary the event premium is usually already deflating, which a long option
    pays for twice. It only fires when IV is actually rich."""
    src = open("app/analytics/entry.py").read()
    block = src[src.index("    catalyst = material_catalyst(news)"):]
    block = block[:block.index("\n    flip =")]
    assert 'ivc.get("verdict") == "rich"' in block
    assert "rich after the event, not before it" in block


def test_the_entry_plan_uses_the_shared_detector():
    src = open("app/analytics/entry.py").read()
    assert "from ..news import material_catalyst" in src
    assert "def material_catalyst(" not in src


# ============================================ upcoming catalysts ==========
#
# The opposite case, and it needs the opposite treatment. A resolved catalyst
# is information: it moves weight off a chart that has gone stale. A scheduled
# one is the absence of information. Nobody knows how a vote goes, so nothing
# may push the stance either way; what it can say is that a high-conviction
# read is not available while the outcome is outstanding.

def _pending(title, kind="regulatory / clinical", age=5.0, importance="high"):
    return {"title": title, "summary": "", "age_hours": age, "tier": "major",
            "about_company": True, "sentiment_score": 2.0,
            "catalysts": [{"type": kind, "importance": importance}]}


@pytest.mark.parametrize("title,kind", [
    ("FDA sets PDUFA date of March 12 for the peptide therapy", "regulatory / clinical"),
    ("Senate to vote on CLARITY Act for crypto market structure", "legislation"),
    ("Sanfilippo Drug Ruling Nears", "regulatory / clinical"),
    ("Decision expected in the antitrust case", "legal / regulatory"),
])
def test_scheduled_events_are_detected(title, kind):
    out = news_mod.pending_catalyst({"articles": [_pending(title, kind)]})
    assert out["pending"] is True, title
    assert kind in out["kinds"]


@pytest.mark.parametrize("title", [
    "Shares slip ahead of the open",
    "Company unveils new product",
    "Analyst raises price target ahead of the print",
])
def test_forward_language_alone_is_not_a_catalyst(title):
    """Both halves are required: a forward marker AND a catalyst the taxonomy
    rates high. "ahead of the open" carries the first and none of the second.

    Classified for real rather than handed a tag. A first version passed
    `importance="high"` into the fixture for "Shares slip ahead of the open",
    which is not what the taxonomy does with it, and then asserted the detector
    should ignore it. The detector was right and the fixture was lying.
    """
    tags = news_mod._catalysts(title)
    article = {"title": title, "summary": "", "age_hours": 5.0, "tier": "major",
               "about_company": True, "sentiment_score": 1.0, "catalysts": tags}
    assert news_mod.pending_catalyst({"articles": [article]})["pending"] is False


def test_a_real_pending_headline_still_fires_through_the_real_classifier():
    """The other side of the same check: end to end, no hand-supplied tags."""
    title = "FDA decision expected in March for the peptide therapy"
    article = {"title": title, "summary": "", "age_hours": 5.0, "tier": "major",
               "about_company": True, "sentiment_score": 1.0,
               "catalysts": news_mod._catalysts(title)}
    assert news_mod.pending_catalyst({"articles": [article]})["pending"] is True


def test_legislation_is_in_the_taxonomy():
    """It was not, so every one of these classified as `[]`, landed in the
    background tier and was invisible to anything reading catalysts. A bill
    deciding whether an asset class is legal to custody is not background."""
    for title in ("Senate to vote on CLARITY Act for crypto market structure",
                  "House panel advances stablecoin legislation",
                  "Congress weighs crypto regulatory framework bill"):
        assert [c["type"] for c in news_mod._catalysts(title)] == ["legislation"], title


@pytest.mark.parametrize("title", [
    "Bill Ackman raises stake in the company",
    "The board did not act on the offer",
    "Company billings rose 12% in the quarter",
])
def test_the_legislation_pattern_does_not_over_match(title):
    """Anchored on the legislative body rather than on "act" or "bill" alone:
    lowercased text makes `\\w+ act` match "did not act" and `\\bbill\\b` match a
    person called Bill."""
    assert "legislation" not in [c["type"] for c in news_mod._catalysts(title)]


def test_a_scheduled_event_is_not_counted_as_resolved():
    """The two detectors have to be mutually exclusive or the pending case
    silently becomes the resolved one. "Senate to vote on CLARITY Act" landed in
    the major tier with a high tag and was damping the chart for an event that
    had not happened. RARE's own "Sanfilippo Drug Ruling Nears" would have done
    the same two days before the approval it was anticipating."""
    arts = [_pending("Senate to vote on CLARITY Act", "legislation")]
    assert news_mod.material_catalyst({"articles": arts})["material"] is False
    assert news_mod.pending_catalyst({"articles": arts})["pending"] is True


def _v(articles, trend=70.0):
    return swing.verdict({"trend_score": trend}, {}, {"flow_score": 55.0},
                         {"net_sentiment": 6.0, "days_to_earnings": 46,
                          "articles": articles},
                         {"risk_score": 20.0}, 100.0)


def test_a_pending_event_caps_conviction_without_moving_the_stance():
    quiet = _v([_pending("Company unveils new product", "product news", importance="low")])
    ahead = _v([_pending("Senate to vote on CLARITY Act", "legislation")])
    assert quiet["conviction"] == "high"
    assert ahead["conviction"] == "moderate", "an outstanding binary caps it"
    assert ahead["stance"] == quiet["stance"], "and must not move the direction"


def test_a_pending_event_does_not_reweight_the_chart():
    """Only a resolved catalyst makes the chart stale."""
    ahead = _v([_pending("Senate to vote on CLARITY Act", "legislation")])
    assert ahead["effective_weights"] == swing.WEIGHTS


def test_the_pending_event_is_named_in_the_conflicts():
    out = _v([_pending("Senate to vote on CLARITY Act", "legislation")])
    line = next(c for c in out["conflicts"] if "still ahead" in c)
    assert "predicts which way it resolves" in line
    assert line.startswith("One headline flags"), "subject and verb have to agree"


def test_the_news_halving_generalises_beyond_earnings():
    """The earnings halving exists because tone ahead of an event does not
    predict the event. That is just as true of a scheduled vote."""
    plain = swing._news_score({"net_sentiment": 5.0, "days_to_earnings": 46}, None, None)
    ahead = swing._news_score({"net_sentiment": 5.0, "days_to_earnings": 46},
                              None, {"pending": True})
    assert plain == pytest.approx(60.0, abs=0.01)
    assert ahead == pytest.approx(30.0, abs=0.01)


def test_the_entry_plan_warns_about_an_unresolved_binary():
    plan = _plan([_pending("FDA sets PDUFA date for the peptide therapy")])
    joined = " ".join(plan.get("warnings") or [])
    assert "still ahead" in joined
    assert "size it as a binary or wait" in joined


def test_the_overview_shows_pending_separately_from_resolved():
    """They say opposite things, and on a name awaiting a second decision after
    a first one landed, both should show."""
    fn = APP_JS[APP_JS.index("function pulsePendingLine(pend) {"):]
    fn = fn[:fn.index("\nfunction renderOpticPulse")]
    assert "pend.pending !== true) return ''" in fn
    assert "still ahead" in fn
    assert "pulsePendingLine(p.pending_catalyst)" in APP_JS
    assert ".pl-catalyst.is-pending" in CSS
