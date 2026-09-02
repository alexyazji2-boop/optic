"""Economic series from FRED.

The one place an economic chart routinely misleads is the choice between a level
and a change. CPI as a level is a smooth line that only ever rises and tells you
nothing; the unemployment rate as a month-over-month change is noise. So the
tests here are mostly about that choice being made per series and applied
correctly — the fetching is FRED's problem and is tested elsewhere.
"""

import pytest

from app.analytics import econ


def _rows(values, start="2020-01-01", freq_days=31):
    from datetime import date, timedelta
    d = date.fromisoformat(start)
    out = []
    for v in values:
        out.append((d.isoformat(), float(v)))
        d = d + timedelta(days=freq_days)
    return out


# ------------------------------------------------------------- the catalogue

def test_every_grouped_series_is_defined():
    for g in econ.GROUPS:
        for code in g["series"]:
            assert code in econ.SERIES, "%s is grouped but not defined" % code


def test_every_series_declares_a_known_form():
    for code, spec in econ.SERIES.items():
        assert spec["form"] in econ.FORM_LABEL, "%s: %s" % (code, spec["form"])


def test_every_series_explains_how_to_read_it():
    for code, spec in econ.SERIES.items():
        assert spec.get("note"), code
        assert len(spec["note"]) > 30, "%s: note too thin to be useful" % code


def test_price_indices_are_plotted_as_changes_not_levels():
    """A price index level only ever rises. Plotting CPI that way is the classic
    useless economic chart."""
    for code in ("CPIAUCSL", "PCEPILFE", "PPIFIS", "M2SL"):
        assert econ.SERIES[code]["form"] == "yoy", (
            "%s must be a rate of change, not a level" % code)


def test_rates_and_ratios_are_plotted_as_levels():
    """The opposite case: the level IS the number, and a change would be noise."""
    for code in ("UNRATE", "DFF", "DGS10", "T10Y2Y", "BAMLH0A0HYM2"):
        assert econ.SERIES[code]["form"] == "level", code


def test_payrolls_is_a_difference():
    """The level of total employment is not the release; the monthly change is."""
    assert econ.SERIES["PAYEMS"]["form"] == "diff"


def test_the_catalogue_does_not_fetch():
    """It has to be cheap enough to render the picker without hitting FRED 23
    times."""
    cat = econ.catalogue()
    assert cat["count"] == len(econ.SERIES)
    assert len(cat["groups"]) == len(econ.GROUPS)
    for g in cat["groups"]:
        for sx in g["series"]:
            assert sx["form_label"], sx["code"]


# ------------------------------------------------------------- the transforms

def test_level_passes_values_through():
    out = econ._transform(_rows([1, 2, 3]), "level", "%")
    assert [p["value"] for p in out] == [1, 2, 3]


def test_diff_reports_the_change_and_drops_the_first_point():
    out = econ._transform(_rows([100, 130, 125]), "diff", "k")
    assert [p["value"] for p in out] == [30, -5]
    # The first observation has nothing to difference against.
    assert len(out) == 2


def test_yoy_steps_back_a_full_year_not_a_fixed_row_count():
    """A weekly series compared to '12 rows ago' is a quarter, not a year. The
    step has to come from the dates."""
    weekly = _rows([100] * 60, freq_days=7)
    # Make the last value 10% above the one 52 weeks earlier.
    weekly[-1] = (weekly[-1][0], 110.0)
    out = econ._transform(weekly, "yoy", "%")
    assert out, "weekly yoy produced nothing"
    assert out[-1]["value"] == pytest.approx(10.0, abs=0.01)


def test_yoy_on_monthly_uses_twelve_periods():
    monthly = _rows([100] * 30, freq_days=31)
    monthly[-1] = (monthly[-1][0], 105.0)
    out = econ._transform(monthly, "yoy", "%")
    assert out[-1]["value"] == pytest.approx(5.0, abs=0.01)


def test_quarterly_annualised_compounds():
    """1% in a quarter is about 4.06% annualised, not 4%."""
    out = econ._transform(_rows([100, 101], freq_days=91), "qoq_ann", "%")
    assert out[0]["value"] == pytest.approx(4.06, abs=0.02)


def test_a_zero_base_does_not_divide_by_zero():
    out = econ._transform(_rows([0, 0, 5] + [5] * 20), "yoy", "%")
    for p in out:
        assert p["value"] is None or abs(p["value"]) < 1e9


def test_dollar_levels_are_scaled_to_billions():
    """The Fed balance sheet in raw millions is a nine-digit axis label."""
    out = econ._transform(_rows([7_000_000]), "level", "$")
    assert out[0]["value"] == pytest.approx(7000, abs=1)


def test_frequency_inference():
    assert econ._periods_per_year(_rows([1, 2, 3], freq_days=1)) == 252
    assert econ._periods_per_year(_rows([1, 2, 3], freq_days=7)) == 52
    assert econ._periods_per_year(_rows([1, 2, 3], freq_days=31)) == 12
    assert econ._periods_per_year(_rows([1, 2, 3], freq_days=91)) == 4


def test_an_unknown_series_is_refused_rather_than_guessed():
    out = econ.series("NOTASERIES")
    assert "error" in out
