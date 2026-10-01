"""Weinstein stage analysis.

Built after a reference chart -- TrendSpider's weekly PLTR, labelled "Back to
Stage 2" -- and calibrated against live data before the thresholds were fixed.
Every series here is synthetic so each stage is proven by construction rather
than by whatever the market happens to be doing on the day the suite runs.

The one thing a test cannot assert about this module is that it is right about
the future. It is not meant to be, and every reading says so.
"""
from __future__ import annotations

import pytest

from app.analytics import stage


def _ramp(start, step, n):
    return [start + step * i for i in range(n)]


def _flat(level, n, wiggle=0.0):
    return [level + (wiggle if i % 2 else -wiggle) for i in range(n)]


LONG = stage.MIN_WEEKS + 20


# ------------------------------------------------------------- the four stages


def test_a_steady_advance_is_stage_2():
    r = stage.classify(_ramp(50, 1.0, LONG))
    assert r["stage"] == 2 and r["name"] == "Advancing"
    assert r["trend"] == "rising" and r["vs_sma_pct"] > 0


def test_a_steady_decline_is_stage_4():
    r = stage.classify(_ramp(200, -1.0, LONG))
    assert r["stage"] == 4 and r["name"] == "Declining"
    assert r["trend"] == "falling" and r["vs_sma_pct"] < 0


def test_flattening_after_an_advance_is_a_top_not_a_base():
    """The whole point of the prior window: a flat average means opposite
    things depending on where the trend came from."""
    series = _ramp(50, 1.0, 45) + _flat(95, 40)
    assert stage.classify(series)["stage"] == 3


def test_flattening_after_a_decline_is_a_base_not_a_top():
    series = _ramp(200, -1.0, 45) + _flat(155, 40)
    assert stage.classify(series)["stage"] == 1


# ------------------------------------------------------------- the transitions


def test_a_breakout_above_a_still_falling_average_is_stage_1_not_2():
    """META and BTC read like this on the day it was calibrated. Price above
    the average is not an advance until the average itself turns up -- which
    is what Weinstein waited for, and what the label must not skip."""
    series = _ramp(200, -1.0, 60) + _flat(145, 6) + [175, 180, 185]
    r = stage.classify(series)
    assert r["vs_sma_pct"] > 0 and r["trend"] != "rising"
    assert r["stage"] == 1
    assert "not rising yet" in r["transition"]


def test_a_newly_turned_advance_says_it_is_new():
    """The PLTR case: a real Stage 2, but one that only just turned. The
    reading is the same as a mature advance; the warning is not."""
    series = _ramp(200, -1.5, 40) + _flat(140, 12) + _ramp(140, 3.0, 14)
    r = stage.classify(series)
    assert r["stage"] == 2
    assert r["transition"] and "Newly in Stage 2" in r["transition"]


def test_a_mature_advance_carries_no_transition_note():
    assert stage.classify(_ramp(50, 1.0, LONG))["transition"] is None


def test_slipping_below_a_rising_average_is_the_first_sign_of_a_top():
    series = _ramp(50, 1.0, 70) + [60, 58, 55]
    r = stage.classify(series)
    assert r["stage"] == 3
    assert "first sign of a top" in r["transition"]


# ------------------------------------------------------------------- the limits


def test_too_little_history_says_how_much_it_needs():
    """A 3-month chart holds about thirteen weeks. The label must decline,
    and say why, rather than classify an average that does not exist."""
    r = stage.classify(_ramp(50, 1.0, 13))
    assert r["available"] is False
    assert str(stage.MIN_WEEKS) in r["reason"] and "13" in r["reason"]


def test_the_minimum_is_exact_on_both_sides():
    """The test above uses thirteen weeks, far below any threshold, and a
    mutation loosening the guard to 31 weeks passed it -- 31 is enough for the
    average itself but not for the two slope windows behind it, which would
    then read averages that do not exist yet. So both sides of the boundary."""
    one_short = stage.classify(_ramp(50, 1.0, stage.MIN_WEEKS - 1))
    assert one_short["available"] is False
    exact = stage.classify(_ramp(50, 1.0, stage.MIN_WEEKS))
    assert exact["available"] is True and exact["stage"] == 2
    # Between the average's own need and the full minimum: declined, not crashed.
    for n in (stage.SMA_WEEKS + 1, stage.SMA_WEEKS + stage.SLOPE_WEEKS):
        assert stage.classify(_ramp(50, 1.0, n))["available"] is False


def test_every_reading_states_what_it_cannot_tell_you():
    for series in (_ramp(50, 1.0, LONG), _ramp(50, 1.0, 5)):
        assert "not where it goes next" in stage.classify(series)["limits"]


def test_missing_and_non_positive_closes_are_dropped_not_averaged():
    """A None or a zero inside an average is a fabricated price."""
    clean = _ramp(50, 1.0, LONG)
    dirty = clean[:10] + [None, 0, -5, float("nan")] + clean[10:]
    assert stage.classify(dirty)["stage"] == stage.classify(clean)["stage"]
    assert stage.classify(dirty)["weeks"] == len(clean)


def test_the_explanation_is_checkable_against_the_numbers():
    """Claims must be checkable: the sentence carries the figures the stage
    was decided on, so a reader can disagree with them."""
    r = stage.classify(_ramp(50, 1.0, LONG))
    assert "{:.1f}%".format(abs(r["vs_sma_pct"])) in r["explain"]
    assert "{:.1f}%".format(abs(r["slope_pct"])) in r["explain"]
    assert "30-week" in r["explain"]


def test_the_thresholds_are_the_calibrated_ones():
    """Ten weeks, not four: over four the S&P's steady uptrend read +1.5%,
    close enough to the flat band to flicker into Stage 3 on a quiet week."""
    assert stage.SMA_WEEKS == 30
    assert stage.SLOPE_WEEKS == 10
    assert stage.FLAT_PCT == 1.0


def test_the_label_uses_no_em_dash():
    """CLAUDE.md: a deliberate pass removed them from reader-facing copy."""
    r = stage.classify(_ramp(50, 1.0, LONG))
    for field in ("label", "explain", "limits"):
        assert "—" not in r[field]


# ------------------------------------------------------------------ the fetch


class _Frame:
    """Weekly bars labelled by their Monday, as the feed labels them."""

    def __init__(self, closes):
        import pandas as pd
        self.index = pd.date_range("2016-01-04", periods=len(closes), freq="W-MON",
                                   tz="America/New_York")
        self._df = pd.DataFrame({"Close": closes}, index=self.index)
        self.empty = self._df.empty

    def __getitem__(self, key):
        return self._df[key]


class _Provider:
    def __init__(self, closes):
        self.closes, self.calls = closes, []

    def history(self, symbol, period, interval):
        self.calls.append((symbol, period, interval))
        return _Frame(self.closes)


def test_it_fetches_its_own_weekly_history_not_the_charts_range():
    """The stage belongs to the instrument, not to the range on screen. Every
    week since the listing, because the All range draws every bar since it,
    and ten years left NVDA's first seventeen on All as "No stage yet"."""
    p = _Provider(_ramp(50, 1.0, LONG))
    stage.for_symbol(p, "PLTR")
    assert p.calls == [("PLTR", "max", "1wk")]


def test_the_payload_carries_a_stage_for_every_week_that_has_one():
    closes = _ramp(50, 1.0, LONG)
    r = stage.for_symbol(_Provider(closes), "PLTR")
    assert len(r["history"]) == LONG - (stage.MIN_WEEKS - 1)
    assert r["history"][-1][1] == r["stage"], "the newest bar and the chip disagree"
    assert r["names"] == {"1": "Basing", "2": "Advancing", "3": "Topping", "4": "Declining"}


def test_an_unavailable_reading_sends_no_history():
    r = stage.for_symbol(_Provider(_ramp(50, 1.0, stage.MIN_WEEKS - 1)), "NEW")
    assert r["available"] is False and "history" not in r


def test_an_empty_fetch_is_unavailable_not_an_error():
    r = stage.for_symbol(_Provider([]), "NOPE")
    assert r["available"] is False and "NOPE" in r["reason"]


# ------------------------------------------------------------ every week's stage


def _mondays(n, start="2016-01-04"):
    import datetime as dt
    first = dt.date.fromisoformat(start)
    return [first + dt.timedelta(weeks=i) for i in range(n)]


def _cycle():
    """Up, over, down, along the bottom and up again: all four stages."""
    up = _ramp(50, 1.0, 60)
    top = _flat(up[-1], 30, 0.3)
    down = _ramp(top[-1], -1.0, 50)
    base = _flat(down[-1], 30, 0.3)
    again = _ramp(base[-1], 1.0, 40)
    return up + top + down + base + again


def test_each_week_is_read_from_its_own_past_and_nothing_later():
    """The property the colours rest on. A bar coloured with hindsight would
    show a top forming before the price that made it."""
    closes = _cycle()
    hist = stage.history(_mondays(len(closes)), closes)
    offset = stage.MIN_WEEKS - 1
    for k, (_, st) in enumerate(hist):
        assert st == stage.classify(closes[:offset + k + 1])["stage"], k


def test_a_full_cycle_colours_all_four_stages_in_order():
    closes = _cycle()
    stages = [st for _, st in stage.history(_mondays(len(closes)), closes)]
    runs = [s for i, s in enumerate(stages) if i == 0 or s != stages[i - 1]]
    want = iter([2, 3, 4, 1, 2])
    nxt = next(want)
    for s in runs:
        if s == nxt:
            nxt = next(want, None)
            if nxt is None:
                break
    assert nxt is None, runs


def test_the_first_52_weeks_have_no_stage_rather_than_a_guess():
    closes = _ramp(50, 1.0, LONG)
    weeks = _mondays(LONG)
    hist = stage.history(weeks, closes)
    assert hist[0][0] == weeks[stage.MIN_WEEKS - 1].isoformat()
    assert stage.history(weeks[:stage.MIN_WEEKS - 1], closes[:stage.MIN_WEEKS - 1]) == []


def test_weeks_are_keyed_on_their_monday_whatever_day_labels_them():
    """The client finds a daily bar's week by its Monday. A feed that labelled
    weeks by their Friday would otherwise match nothing, silently."""
    import datetime as dt
    fridays = [d + dt.timedelta(days=4) for d in _mondays(LONG)]
    hist = stage.history(fridays, _ramp(50, 1.0, LONG))
    assert all(dt.date.fromisoformat(k).weekday() == 0 for k, _ in hist)
    assert hist[-1][0] == _mondays(LONG)[-1].isoformat()


def test_a_bad_close_drops_its_own_week_and_no_other():
    """Filtering closes without their dates would slide every later stage one
    week early."""
    closes = _ramp(50, 1.0, LONG)
    weeks = _mondays(LONG)
    hole = LONG - 5
    closes[hole] = None
    keys = [k for k, _ in stage.history(weeks, closes)]
    assert weeks[hole].isoformat() not in keys
    assert keys[-1] == weeks[-1].isoformat()
    assert weeks[hole + 1].isoformat() in keys and weeks[hole - 1].isoformat() in keys
