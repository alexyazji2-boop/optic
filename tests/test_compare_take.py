"""Optic's take on a comparison.

The tab's own subtitle already said the three horizons are scored separately
"so a name can lead one and trail another. That disagreement is the useful
part" — and then printed twenty-six rows and left the reader to find it. These
tests are about the two ways a summary like this lies: calling a coin flip a
verdict, and reporting only one name's strengths.
"""

import pytest

from app.analytics import compare

HZ = [
    {"id": "swing", "name": "Swing setup"},
    {"id": "position", "name": "Position setup"},
    {"id": "longterm", "name": "Long-term trend"},
]

GROWTH = {"ticker": "NVDA", "rs_vs_spy": 12.0, "cagr_5y_pct": 59.0,
          "annual_vol_pct": 48.0, "forward_pe": 42.0,
          "cagr_per_vol_5y": 1.24, "drawdown_pct": -3.0}
DEFENSIVE = {"ticker": "KO", "rs_vs_spy": -4.0, "cagr_5y_pct": 7.0,
             "annual_vol_pct": 14.0, "forward_pe": 21.0,
             "cagr_per_vol_5y": 0.50, "drawdown_pct": -1.0}


def _take(ranks, rows=None):
    return compare.take({"rows": rows or [GROWTH, DEFENSIVE],
                         "ranks": ranks, "horizons": HZ})


def test_unanimous_agreement_is_stated_plainly():
    out = _take({h["id"]: [{"ticker": "NVDA", "score": 80.0},
                           {"ticker": "KO", "score": 40.0}] for h in HZ})
    assert out["unanimous"] is True
    assert out["headline"] == "NVDA leads every horizon."


def test_disagreement_names_every_horizon_and_its_leader():
    """The finding the tab exists for. Flattening it to a single winner throws
    away the only thing three separate scores buy you."""
    out = _take({
        "swing": [{"ticker": "NVDA", "score": 81.0}, {"ticker": "KO", "score": 40.0}],
        "position": [{"ticker": "KO", "score": 70.0}, {"ticker": "NVDA", "score": 55.0}],
        "longterm": [{"ticker": "KO", "score": 66.0}, {"ticker": "NVDA", "score": 61.0}],
    })
    assert out["unanimous"] is False
    assert "No name leads throughout" in out["headline"]
    for bit in ("NVDA on the swing setup", "KO on the position setup",
                "KO on the long-term trend"):
        assert bit in out["headline"], bit


def test_overall_counts_horizons_won_not_the_highest_score():
    """The first version took max() over the scores, which compares numbers on
    different scales answering different questions — a swing score of 81 is not
    "more" than a position score of 70. It named NVDA on a comparison where KO
    won two of the three horizons."""
    out = _take({
        "swing": [{"ticker": "NVDA", "score": 81.0}, {"ticker": "KO", "score": 40.0}],
        "position": [{"ticker": "KO", "score": 70.0}, {"ticker": "NVDA", "score": 55.0}],
        "longterm": [{"ticker": "KO", "score": 66.0}, {"ticker": "NVDA", "score": 61.0}],
    })
    assert out["overall"] == "KO"


def test_an_even_split_picks_no_winner():
    """A split verdict is the finding. Choosing a side out of a tie buries it."""
    out = _take({
        "swing": [{"ticker": "NVDA", "score": 80.0}, {"ticker": "KO", "score": 40.0}],
        "position": [{"ticker": "KO", "score": 70.0}, {"ticker": "NVDA", "score": 55.0}],
    })
    assert out["overall"] is None


def test_a_near_tie_is_flagged_rather_than_ranked():
    """Under five points, on scores built from a handful of inputs each, is not
    a ranking anyone should act on."""
    out = _take({"swing": [{"ticker": "NVDA", "score": 61.0},
                           {"ticker": "KO", "score": 59.8}]})
    win = out["winners"]["swing"]
    assert win["decisive"] is False
    assert out["close_calls"] and out["close_calls"][0]["gap"] == pytest.approx(1.2, abs=0.05)


def test_a_clear_gap_is_not_flagged():
    out = _take({"swing": [{"ticker": "NVDA", "score": 81.0},
                           {"ticker": "KO", "score": 40.0}]})
    assert out["winners"]["swing"]["decisive"] is True
    assert out["close_calls"] == []


def test_standouts_reach_both_names():
    """The metric list is ordered by how interesting each one is, and taking the
    first three straight off it gave all three to the growth name — so a
    comparison where one name holds every growth metric and the other holds
    every risk metric reported only the growth."""
    out = _take({"swing": [{"ticker": "NVDA", "score": 81.0},
                           {"ticker": "KO", "score": 40.0}]})
    names = {s["ticker"] for s in out["standouts"]}
    assert names == {"NVDA", "KO"}, out["standouts"]
    # And no name may monopolise it.
    for sym in names:
        assert sum(1 for s in out["standouts"] if s["ticker"] == sym) <= 2


def test_a_metric_leader_by_a_hair_is_not_a_finding():
    """The threshold scales with the spread across the field, so it works
    whether the names are 2% or 200% apart."""
    a = dict(GROWTH, ticker="AAA", cagr_5y_pct=40.0)
    b = dict(DEFENSIVE, ticker="BBB", cagr_5y_pct=39.9)
    out = compare.take({"rows": [a, b], "horizons": HZ,
                        "ranks": {"swing": [{"ticker": "AAA", "score": 60.0},
                                            {"ticker": "BBB", "score": 50.0}]}})
    assert not any(s["metric"] == "cagr_5y_pct" for s in out["standouts"])


def test_one_name_is_refused_rather_than_summarised():
    out = compare.take({"rows": [GROWTH], "horizons": HZ,
                        "ranks": {"swing": [{"ticker": "NVDA", "score": 60.0}]}})
    assert out["available"] is False
    assert "Two names" in out["reason"]


def test_the_method_explains_the_close_call_threshold():
    out = _take({"swing": [{"ticker": "NVDA", "score": 81.0},
                           {"ticker": "KO", "score": 40.0}]})
    assert "five points" in out["method"]
