"""Tests for the optional indicator catalogue.

The catalogue is a contract between two files: `indicators.CATALOGUE` server-side
and the fallback list the picker draws before the first fetch returns. They drifted
apart the moment Bollinger was added to one and not the other, and the failure is
silent — the dropdown simply omits an indicator that the API would happily serve.
"""

import numpy as np
import pandas as pd
import pytest

from app.analytics import indicators


def _frame(n=200, start=100.0, drift=0.25, spread=1.5):
    idx = pd.date_range("2025-01-01", periods=n, freq="B")
    close = start + np.arange(n) * drift + np.sin(np.arange(n) / 7.0) * 4.0
    return pd.DataFrame({
        "Open": close - 0.3,
        "High": close + spread,
        "Low": close - spread,
        "Close": close,
        "Volume": np.full(n, 1_000_000.0),
    }, index=idx)


def test_every_catalogue_entry_computes():
    df = _frame()
    bench = df["Close"] * 0.9
    out = indicators.compute(df, [r["id"] for r in indicators.CATALOGUE], bench=bench)
    assert out["available"] is True
    assert out["unknown"] == []
    for key, value in out["indicators"].items():
        assert value.get("available") is True, (key, value.get("reason"))


def test_unknown_ids_are_reported_not_ignored():
    """A typo that silently returns nothing looks the same as an indicator with no
    data, so the id comes back in `unknown`."""
    out = indicators.compute(_frame(), ["vwap", "not-an-indicator"])
    assert out["unknown"] == ["not-an-indicator"]
    assert "vwap" in out["indicators"]


def test_bollinger_returns_three_bands_and_a_width_percentile():
    out = indicators.compute(_frame(), ["bollinger"])["indicators"]["bollinger"]
    assert [l["name"] for l in out["lines"]] == [
        "Bollinger upper", "Bollinger mid", "Bollinger lower"]
    # The width is what the bands are for; a touch of a band is common by
    # construction and says much less.
    assert out["last"] is not None
    assert 0 <= out["width_percentile"] <= 100


def test_bollinger_and_keltner_disagree_on_a_wide_range_quiet_close():
    """The reason both exist. Bollinger measures the spread of CLOSES, Keltner the
    true range — so bars that travel a long way and close in the same place squeeze
    one and not the other. If these ever moved together, one of them would be
    redundant."""
    n = 200
    idx = pd.date_range("2025-01-01", periods=n, freq="B")
    close = np.full(n, 100.0)                 # closes pinned: zero deviation
    wide = pd.DataFrame({"Open": close, "High": close + 8.0, "Low": close - 8.0,
                         "Close": close, "Volume": np.full(n, 1e6)}, index=idx)
    got = indicators.compute(wide, ["bollinger", "keltner"])["indicators"]
    b = got["bollinger"]["lines"]
    k = got["keltner"]["lines"]
    b_width = b[0]["values"][-1] - b[2]["values"][-1]
    k_width = k[0]["values"][-1] - k[2]["values"][-1]
    assert b_width == pytest.approx(0.0, abs=1e-6), "identical closes: no deviation"
    assert k_width > 5.0, "a 16-point daily range is real volatility"


def test_price_pane_membership_matches_the_client_list():
    """The dropdown labels each option 'on the chart' or 'own pane' from a
    hard-coded client list. If that disagrees with the server's `pane` field the
    label lies, and an overlay ends up in a pane or vice versa."""
    with open("static/app.js", encoding="utf-8") as fh:
        source = fh.read()
    marker = "const IND_PRICE_PANE = ["
    start = source.index(marker) + len(marker)
    listed = {chunk.strip().strip("'\"")
              for chunk in source[start:source.index("]", start)].split(",")
              if chunk.strip()}
    server = {r["id"] for r in indicators.CATALOGUE if r["pane"] == "price"}
    assert listed == server, "client overlay list and server pane field disagree"


def test_client_fallback_catalogue_lists_every_indicator():
    """Drawn before the first fetch returns, so anything missing here is simply
    absent from the dropdown even though the API serves it."""
    with open("static/app.js", encoding="utf-8") as fh:
        source = fh.read()
    marker = "const IND_FALLBACK_CATALOGUE = ["
    block = source[source.index(marker):]
    block = block[:block.index("\n];")]
    for row in indicators.CATALOGUE:
        assert "id: '%s'" % row["id"] in block, row["id"]


def test_every_entry_states_what_it_measures():
    for row in indicators.CATALOGUE:
        assert row["measures"].strip(), row["id"]
        assert row["pane"] in ("price", "own"), row["id"]


def test_every_entry_explains_itself_in_three_registers():
    """A pane that shows a chart and a number without saying what it represents is
    asking the reader to already know."""
    for row in indicators.CATALOGUE:
        for field in ("represents", "why", "caveat"):
            assert row.get(field, "").strip(), (row["id"], field)


def test_the_caveat_is_a_limitation_not_a_sales_pitch():
    """The UI puts this field under a heading that reads "What it will not tell you",
    so it has to contain a limitation. Three of these were originally written as
    reasons TO use the indicator — that argument belongs in `why`, and leaving it
    here both duplicated it and mislabelled it.

    Checked by shape rather than by meaning: a limitation says what the thing does
    not do, so it should not open by recommending it.
    """
    sales = ("worth having", "read against", "rising through a falling market means")
    for row in indicators.CATALOGUE:
        opening = row["caveat"][:60].lower()
        for phrase in sales:
            assert not opening.startswith(phrase), (row["id"], row["caveat"][:70])


def test_readings_describe_the_current_value():
    """The live reading is the line that changes; without it the pane explains an
    indicator in general and says nothing about this name today."""
    df = _frame(300)
    bench = df["Close"] * 0.9
    out = indicators.compute(df, [r["id"] for r in indicators.CATALOGUE], bench=bench)
    got = out["indicators"]
    # Every indicator with enough synthetic history should produce one.
    for key in ("vwap", "bollinger", "keltner", "donchian", "sec", "adx",
                "stochastic", "obv", "mfi", "rs"):
        assert got[key].get("reading"), key


def test_a_reading_failure_does_not_cost_the_indicator():
    """The description is a nicety; the numbers are the point. If _reading raises,
    the pane must still get its chart."""
    df = _frame(300)
    original = indicators._reading

    def boom(*_args, **_kwargs):
        raise ValueError("deliberate")

    indicators._reading = boom
    try:
        out = indicators.compute(df, ["adx"])
    finally:
        indicators._reading = original
    assert out["indicators"]["adx"]["available"] is True
    assert out["indicators"]["adx"]["reading"] is None
    assert out["indicators"]["adx"]["lines"]


def test_adx_reading_does_not_claim_a_direction_on_a_tie():
    """+DI 21.24 against -DI 21.27 is a tie. The first version reported "down" and
    printed both as 21 in the same sentence, contradicting itself."""
    text = indicators._reading("adx", _frame(300), {
        "lines": [{"name": "ADX", "values": [30.0]},
                  {"name": "+DI", "values": [21.24]},
                  {"name": "-DI", "values": [21.27]}]})
    assert "Neither side is in control" in text


def test_mfi_reading_only_claims_an_extreme_when_there_is_one():
    mid = indicators._reading("mfi", _frame(300),
                              {"lines": [{"name": "MFI", "values": [61.0]}]})
    hot = indicators._reading("mfi", _frame(300),
                              {"lines": [{"name": "MFI", "values": [88.0]}]})
    assert "extreme" not in mid
    assert "extreme" in hot
