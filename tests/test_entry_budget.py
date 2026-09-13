"""What an entry costs, and where the entry zone actually is.

Two reader reports about the same panel.

**"Not everyone has the capital for $4,000 entries."** The panel ranks
candidates on payoff and recommends the best one, and the best one on a large
name is routinely four thousand dollars for a single contract. Somebody with
five hundred was shown a plan they could not take, with nothing saying which
part of it was out of reach.

**"40.0 - 55.96 sounds like a guess."** It was not a guess, it was an envelope:
`min` to `max` across five heterogeneous levels. The three moving averages
cluster within a point of each other while a dealer wall can sit 30% away, so
one far level stretched the band until it said nothing.
"""

from __future__ import annotations

import pytest

from app.analytics import entry


# ------------------------------------------------------------- the zone

def levels(*pairs):
    return [{"price": p, "label": l} for p, l in pairs]


def test_the_zone_is_the_tightest_cluster_not_the_outer_envelope():
    """The reported case, to the numbers. Three averages bunched near spot, a
    Fibonacci level below them and a dealer wall far under both."""
    lv = levels((55.96, "9-day EMA"), (54.80, "20-day SMA"), (54.10, "21-day EMA"),
                (48.20, "nearest Fibonacci support"), (40.00, "dealer put wall"))
    lo, hi, used, dropped = entry._cluster_zone(lv, spot=56.5, atr=1.6)
    envelope = max(x["price"] for x in lv) - min(x["price"] for x in lv)
    assert hi - lo < envelope / 10, "%.2f-%.2f is still an envelope" % (lo, hi)
    assert (hi - lo) / 56.5 < 0.05, "a zone wider than 5% of spot is not an entry"
    assert len(used) >= 2 and len(dropped) >= 1


def test_the_levels_it_did_not_use_are_reported_with_their_distance():
    """A panel that shows only the survivors cannot be checked. "What it did not
    use" is the half a reader needs in order to disagree with it."""
    lv = levels((54.80, "20-day SMA"), (54.10, "21-day EMA"), (40.00, "dealer put wall"))
    _, _, _, dropped = entry._cluster_zone(lv, spot=56.5, atr=1.6)
    assert [d["label"] for d in dropped] == ["dealer put wall"]
    assert dropped[0]["away"] == pytest.approx(14.1, abs=0.01)


def test_agreement_wins_and_proximity_breaks_the_tie():
    """Two clusters of one each: the nearer is the one reachable this week."""
    lv = levels((54.0, "21-day EMA"), (30.0, "dealer put wall"))
    lo, hi, used, _ = entry._cluster_zone(lv, spot=56.0, atr=1.0)
    assert lo == hi == 54.0
    assert [u["label"] for u in used] == ["21-day EMA"]


def test_a_lone_level_is_a_zone_of_one():
    """A line rather than a band, which is the honest answer where only one
    thing sits under the price. Widening it to look like a range would be
    inventing a level."""
    lo, hi, used, dropped = entry._cluster_zone(levels((54.0, "21-day EMA")), 56.0, 1.0)
    assert lo == hi == 54.0 and len(used) == 1 and dropped == []


def test_the_tolerance_scales_with_the_instrument():
    """Half an average daily range, not a percentage of price. 2% of a $600
    stock is twelve points, which merges levels that are genuinely separate; 2%
    of an $8 stock is sixteen cents, which splits levels that are one area."""
    wide = levels((600.0, "a"), (603.0, "b"))
    lo, hi, used, _ = entry._cluster_zone(wide, spot=610.0, atr=12.0)
    assert len(used) == 2, "a $3 gap on a $12-range stock is one area"
    lo, hi, used, _ = entry._cluster_zone(wide, spot=610.0, atr=1.0)
    assert len(used) == 1, "a $3 gap on a $1-range stock is two areas"


def test_no_levels_is_no_zone():
    assert entry._cluster_zone([], 50.0, 1.0) == (None, None, [], [])


# ----------------------------------------------------------- the budget

def chain(*costs):
    return [{"strike": 100 + i, "cost_per_contract": c} for i, c in enumerate(costs)]


def test_no_budget_filters_nothing():
    """The default, and it stays the default. What somebody can spend is their
    own business and nothing here should assume a figure."""
    out = entry._apply_budget(chain(400, 1900, 4000), None)
    assert len(out["candidates"]) == 3
    assert out["filtered"] is False and out["hidden"] == 0


def test_a_budget_drops_what_it_cannot_place():
    out = entry._apply_budget(chain(400, 1900, 4000), 2000)
    assert [c["cost_per_contract"] for c in out["candidates"]] == [400, 1900]
    assert out["hidden"] == 1


def test_the_boundary_is_inclusive():
    """A contract costing exactly the limit is one the reader can place."""
    out = entry._apply_budget(chain(500), 500)
    assert len(out["candidates"]) == 1


def test_nothing_affordable_says_how_far_off_it_is():
    """Empty is the honest answer and it needs the number that makes it
    actionable: not that the limit was missed, but by how much."""
    out = entry._apply_budget(chain(1885, 4000), 500)
    assert out["candidates"] == []
    assert out["cheapest"] == 1885
    assert "$1,885" in out["note"] and "$500" in out["note"]


def test_a_shortened_list_says_it_was_shortened():
    """A list that quietly got smaller looks like a thin chain. Saying how many
    went tells the reader whether to raise the limit or look elsewhere."""
    out = entry._apply_budget(chain(400, 1900, 4000), 2000)
    assert "1 of 3" in out["note"]


def test_everything_fitting_says_so_too():
    """Silence after setting a limit is ambiguous: it could mean the filter did
    nothing or that it is not running."""
    out = entry._apply_budget(chain(400, 900), 5000)
    assert out["hidden"] == 0 and "fits" in out["note"]


def test_a_candidate_with_no_cost_is_not_assumed_affordable():
    """Unmeasurable is not cheap. A row with no price must not be recommended
    on the grounds that nothing said it was expensive."""
    out = entry._apply_budget([{"strike": 100, "cost_per_contract": None}], 500)
    assert out["candidates"] == []


def test_a_zero_limit_is_the_absence_of_one():
    """The API accepts ge=0, so zero can arrive. Treating it as a real limit
    would hide the whole chain behind a bound nothing can meet, which looks
    exactly like a name with no options on it. Zero is how "no limit" is
    spelled when a form submits an empty field."""
    out = entry._apply_budget(chain(400, 1900), 0)
    assert len(out["candidates"]) == 2
    assert out["filtered"] is False


def test_a_negative_limit_is_refused_the_same_way():
    out = entry._apply_budget(chain(400), -100)
    assert len(out["candidates"]) == 1 and out["filtered"] is False
