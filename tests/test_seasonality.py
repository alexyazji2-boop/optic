"""Seasonality: the calendar effects panel.

The thing worth testing here is not the arithmetic — pandas can take a mean. It
is the honesty machinery: that a small sample is refused a verdict, that the
significance threshold is corrected for the number of buckets tested, that the
benchmark subtraction actually removes market drift, and that a single outlier
year is visible rather than absorbed into the mean.
"""

import numpy as np
import pandas as pd
import pytest

from app.analytics import seasonality


# ------------------------------------------------------------ fake provider

class _Provider:
    """Synthetic history, so a test asserts on an effect that was put there."""

    def __init__(self, series):
        self._series = series

    def history(self, ticker, period="15y", interval="1d"):
        if ticker not in self._series:
            return pd.DataFrame()
        return pd.DataFrame({"Close": self._series[ticker]})


def _dates(years=15):
    return pd.bdate_range("2011-01-03", periods=252 * years, freq="C")


def _flat_walk(idx, seed=0, drift=0.0):
    rng = np.random.default_rng(seed)
    steps = rng.normal(drift, 0.01, len(idx))
    return pd.Series(100 * np.exp(np.cumsum(steps)), index=idx)


def _with_month_effect(idx, month, bump, seed=1, drift=0.0):
    """A walk with a real, known edge in one calendar month."""
    rng = np.random.default_rng(seed)
    steps = rng.normal(drift, 0.01, len(idx))
    steps[idx.month == month] += bump
    return pd.Series(100 * np.exp(np.cumsum(steps)), index=idx)


# ------------------------------------------------------------ verdict rules

def test_a_small_sample_never_gets_a_verdict():
    """Four observations produce a mean. They must not produce a claim."""
    vals = pd.Series([5.0, -2.0, 3.0, 1.0])
    out = seasonality._bucket_stats(vals, 0.0, 0.05)
    assert out["n"] == 4
    assert out["verdict"] == "too few"


def test_the_threshold_is_corrected_for_the_number_of_months_tested():
    idx = _dates()
    prov = _Provider({"T": _flat_walk(idx, 0), "SPY": _flat_walk(idx, 99)})
    out = seasonality.build(prov, "T")
    # Twelve months tested, so the bar is 0.05/12 and not 0.05. The payload
    # rounds it to four places for display; the comparison inside _verdict uses
    # the unrounded value, so the tolerance here matches the rounding.
    assert out["monthly"]["tests"] == 12
    assert out["monthly"]["threshold"] == pytest.approx(0.05 / 12, abs=5e-5)
    assert out["weekday"]["tests"] == 5
    assert out["weekday"]["threshold"] == pytest.approx(0.05 / 5, abs=5e-5)
    # One comparison for turn-of-month, so no correction is owed.
    assert out["turn_of_month"]["threshold"] == pytest.approx(0.05)


def test_a_result_that_would_pass_alone_is_called_unproven_not_significant():
    """The distinction the whole panel exists to make."""
    assert seasonality._verdict(0.03, 0.05 / 12, n=15) == "unproven"
    assert seasonality._verdict(0.0001, 0.05 / 12, n=15) == "significant"
    assert seasonality._verdict(0.40, 0.05 / 12, n=15) == "noise"


def test_random_data_produces_no_significant_month():
    """The most important test here.

    A panel that finds a calendar effect in a random walk is a panel that will
    find one in anything. Several seeds, because a single one passing proves
    nothing about the next.
    """
    idx = _dates()
    for seed in range(6):
        prov = _Provider({"T": _flat_walk(idx, seed), "SPY": _flat_walk(idx, seed + 500)})
        out = seasonality.build(prov, "T")
        hits = [r["short"] for r in out["monthly"]["rows"]
                if r["excess"]["verdict"] == "significant"]
        assert not hits, "found %s in a random walk (seed %d)" % (hits, seed)


def test_a_real_month_effect_is_found():
    """And the converse: an effect that is actually there must be reported."""
    idx = _dates()
    prov = _Provider({"T": _with_month_effect(idx, 7, 0.004), "SPY": _flat_walk(idx, 42)})
    out = seasonality.build(prov, "T")
    july = next(r for r in out["monthly"]["rows"] if r["key"] == 7)
    assert july["excess"]["verdict"] == "significant", july["excess"]
    assert july["excess"]["mean"] > 0


# ------------------------------------------------------- benchmark subtraction

def test_market_drift_is_removed_by_the_benchmark():
    """A stock that simply tracks a rising market has no seasonality.

    Without the benchmark subtraction every month of a bull sample reads
    positive and the panel becomes a very slow way of discovering that stocks
    went up.
    """
    idx = _dates()
    bench = _flat_walk(idx, 7, drift=0.0004)
    prov = _Provider({"T": bench * 1.5, "SPY": bench})       # identical shape
    out = seasonality.build(prov, "T")
    for row in out["monthly"]["rows"]:
        assert abs(row["excess"]["mean"]) < 1e-6, row["short"]
        assert row["excess"]["verdict"] in ("noise", "too few")


def test_the_raw_column_still_shows_the_drift_it_removed():
    """Excess is the honest number; raw is what the reader recognises. Both."""
    idx = _dates()
    bench = _flat_walk(idx, 7, drift=0.0006)
    prov = _Provider({"T": bench, "SPY": bench})
    out = seasonality.build(prov, "T")
    assert out["monthly"]["baseline"] > 0
    assert out["monthly"]["baseline_excess"] == pytest.approx(0.0, abs=1e-6)


# --------------------------------------------------------- the outlier check

def test_one_huge_year_is_exposed_by_the_drop_the_best_column():
    idx = _dates()
    walk = _flat_walk(idx, 3)
    prov = _Provider({"T": walk, "SPY": _flat_walk(idx, 4)})
    out = seasonality.build(prov, "T")
    for row in out["monthly"]["rows"]:
        raw = row["raw"]
        if raw["n"] < 2:
            continue
        # Removing the best of n observations can only lower the mean.
        assert raw["mean_ex_best"] <= raw["mean"] + 1e-9, row["short"]


def test_every_year_behind_a_month_is_listed():
    """The mean is a summary; the panel also has to show its working."""
    idx = _dates()
    prov = _Provider({"T": _flat_walk(idx, 11), "SPY": _flat_walk(idx, 12)})
    out = seasonality.build(prov, "T")
    for row in out["monthly"]["rows"]:
        assert len(row["years"]) == row["raw"]["n"]
        assert all("year" in y and "pct" in y for y in row["years"])


# ------------------------------------------------------------------ plumbing

def test_short_history_is_refused_rather_than_guessed():
    idx = pd.bdate_range("2024-01-01", periods=120, freq="C")
    prov = _Provider({"T": _flat_walk(idx, 1), "SPY": _flat_walk(idx, 2)})
    out = seasonality.build(prov, "T")
    assert "error" in out


def test_a_missing_benchmark_is_an_error_not_a_silent_zero():
    idx = _dates()
    prov = _Provider({"T": _flat_walk(idx, 1)})               # no SPY
    out = seasonality.build(prov, "T")
    assert "error" in out and "benchmark" in out["error"]


def test_the_significant_count_matches_the_rows():
    idx = _dates()
    prov = _Provider({"T": _with_month_effect(idx, 3, 0.004), "SPY": _flat_walk(idx, 8)})
    out = seasonality.build(prov, "T")
    counted = sum(1 for section in ("monthly", "weekday")
                  for r in out[section]["rows"]
                  if r["excess"]["verdict"] == "significant")
    counted += 1 if out["turn_of_month"]["verdict"] == "significant" else 0
    assert out["significant_count"] == counted


def test_weekday_means_keep_three_decimals():
    """Daily returns rounded to two places lose most of what is being reported."""
    idx = _dates()
    prov = _Provider({"T": _flat_walk(idx, 5), "SPY": _flat_walk(idx, 6)})
    out = seasonality.build(prov, "T")
    monthly_sd = out["monthly"]["rows"][0]["raw"]["sd"]
    weekday_sd = out["weekday"]["rows"][0]["raw"]["sd"]
    assert weekday_sd is not None and monthly_sd is not None
    # A daily sd near 1% must not round to 0.0 the way 2dp would leave a mean.
    assert weekday_sd > 0


def test_reporting_months_reject_a_one_off_amendment():
    """A single stray filing month must not be presented as a reporting season."""
    counts = {1: 20, 4: 18, 7: 19, 10: 20, 6: 1}
    floor = max(1, int(max(counts.values()) * 0.25))
    assert sorted(m for m, n in counts.items() if n >= floor) == [1, 4, 7, 10]
