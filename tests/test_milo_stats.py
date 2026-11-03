"""The evaluation's intervals (tests/milo_eval/stats.py, Phase 13): checked against values worked out by hand."""
import pytest

from tests.milo_eval import stats as S


def test_wilson_matches_known_values():
    lo, hi = S.wilson(18, 60)
    assert lo == pytest.approx(0.1993, abs=1e-3) and hi == pytest.approx(0.4249, abs=1e-3)
    lo, hi = S.wilson(0, 10)
    assert lo == 0.0 and hi == pytest.approx(0.2775, abs=1e-3)
    assert S.wilson(0, 0) == (0.0, 1.0)


def test_the_zero_failure_bound_is_the_rule_of_three():
    assert S.zero_failure_upper(300) == pytest.approx(0.00994, abs=1e-4)
    assert S.zero_failure_upper(300) == pytest.approx(3 / 300, rel=0.01)
    assert S.needed_for_zero_failures(0.01) == 299 and S.needed_for_zero_failures(0.05) == 59


def test_describe_keeps_a_decimal_near_the_ends():
    assert S.describe(1231, 1231) == "1231 of 1231 (100.0%; 95% interval 99.7% to 100.0%)"
