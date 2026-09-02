"""Tests for the side-by-side comparison.

Two things are worth guarding here. The scoring is pure arithmetic and easy to
cover. The extraction is not: `_metrics` reads about twenty nested paths out of
two large payloads, and when a path is wrong the metric renders as an em-dash
rather than raising. That looks identical to "this name has no data", so a
wrong key can sit there indefinitely. Three of them did. The shape fixtures
below mirror the live payloads exactly for that reason.
"""

from app.analytics import compare


def _snapshot():
    """Mirrors the live `_swing_snapshot` shape for the paths `_metrics` reads."""
    return {
        "ticker": "NVDA",
        "quote": {"price": 217.56, "change_pct": -0.99},
        "technicals": {
            "rsi": {"value": 54.2, "length": 14, "state": "neutral"},
            "moving_averages": {
                "sma20": {"distance_pct": 2.44},
                "sma50": {"distance_pct": 5.04},
                "sma200": {"distance_pct": 11.47},
            },
            "volatility": {"atr_pct": 3.03, "realised_vol_20d": 37.74},
        },
        "entry_plan": {"iv_context": {"atm_iv_pct": 49.32}},
        "sector_confirm": {"rs_vs_spy_pct": 2.18, "sector": "Technology"},
        "verdict": {"composite_score": 61.2},
    }


def _longterm():
    """Mirrors `longterm.analyse_holding` wrapped as main.py wraps it."""
    return {
        "holding": {
            "name": "NVIDIA Corporation",
            "horizons": {"cagr_5y_pct": 61.7, "return_1y_pct": 30.0},
            "excess_cagr_5y_pct": 50.05,
            "drawdown": {"current_drawdown_pct": -7.71, "max_drawdown_pct": -66.36},
            "risk": {"beta_vs_spy": 2.1, "annualised_vol_pct": 48.0,
                     "sharpe_proxy": 1.4},
            "long_trend": {"phase": "secular uptrend", "vs_40w_sma": 11.64},
            "valuation": {"forward_pe": 33.3},
            "valuation_history": {"percentile": 25.0, "read": "cheap"},
            "fundamentals": {"sector": "Technology"},
        }
    }


def test_metrics_reads_every_advertised_path():
    m = compare._metrics(_snapshot(), _longterm())
    # Nothing the table has a row for may come back None from a full payload —
    # that is exactly the silent-wrong-key failure this guards.
    for key in ("price", "change_pct", "rsi", "rs_vs_spy", "vs_sma20", "vs_sma50",
                "vs_sma200", "vs_sma40w", "atr_pct", "iv_pct", "hv_pct",
                "beta_vs_spy", "annual_vol_pct", "cagr_per_vol_5y",
                "max_drawdown_pct", "forward_pe", "pe_percentile",
                "drawdown_pct", "cagr_5y_pct", "excess_cagr_5y_pct",
                "trend_phase", "composite", "name", "sector"):
        assert m.get(key) is not None, key
    assert m["rsi"] == 54.2, "RSI lives under technicals.rsi.value, not technicals.rsi"
    assert m["name"] == "NVIDIA Corporation"
    assert m["drawdown_pct"] == -7.71, "current drawdown, not the historical maximum"


def test_metrics_tolerates_a_missing_longterm_payload():
    m = compare._metrics(_snapshot(), {})
    assert m["price"] == 217.56
    assert m["cagr_5y_pct"] is None
    assert m["name"] == "NVDA", "falls back to the symbol"


def test_scaled_band_and_clip():
    assert compare._scaled(0, 0, 100) == 0.0
    assert compare._scaled(50, 0, 100) == 50.0
    assert compare._scaled(500, 0, 100) == 100.0, "clipped, not extrapolated"
    assert compare._scaled(-500, 0, 100) == 0.0
    assert compare._scaled(25, 0, 100, invert=True) == 75.0
    assert compare._scaled(None, 0, 100) is None


def test_swing_penalises_an_extended_rsi():
    base = {"rs_vs_spy": 5.0, "vs_sma20": 2.0, "vs_sma50": 3.0,
            "iv_pct": 30.0, "hv_pct": 30.0}
    trending = compare._score_swing({**base, "rsi": 62})
    stretched = compare._score_swing({**base, "rsi": 88})
    assert trending > stretched, "RSI 88 is stretched, not twice as good as 62"


def test_swing_prefers_cheap_implied_vol():
    base = {"rsi": 55, "rs_vs_spy": 5.0, "vs_sma20": 2.0, "vs_sma50": 3.0}
    cheap = compare._score_swing({**base, "iv_pct": 22.0, "hv_pct": 30.0})
    rich = compare._score_swing({**base, "iv_pct": 45.0, "hv_pct": 30.0})
    assert cheap > rich


def test_longterm_band_is_sized_for_an_annual_rate():
    """A 61% five-year CAGR should top out; a total return would too, which is
    why the metric must be the annualised figure."""
    strong = compare._score_longterm(
        {"cagr_5y_pct": 30.0, "drawdown_pct": -5.0, "vs_sma200": 20.0,
         "pe_percentile": 20.0, "cagr_per_vol_5y": 1.0,
         "max_drawdown_pct": -30.0})
    weak = compare._score_longterm(
        {"cagr_5y_pct": -2.0, "drawdown_pct": -38.0, "vs_sma200": -18.0,
         "pe_percentile": 95.0, "cagr_per_vol_5y": -0.1,
         "max_drawdown_pct": -70.0})
    assert strong > 75
    assert weak < 20


def test_scores_are_none_when_nothing_is_available():
    assert compare._score_longterm({}) is None
    assert compare._score_swing({}) is None


def _build(rows, longterm=None):
    snaps = {k: v for k, v in rows.items()}
    return compare.build(
        lambda s: snaps[s],
        lambda s: (longterm or {}).get(s, _longterm()),
        list(snaps),
    )


def test_build_rejects_a_single_ticker():
    out = compare.build(lambda s: _snapshot(), lambda s: _longterm(), ["NVDA"])
    assert out["available"] is False
    assert "least 2" in out["reason"]


def test_build_caps_the_ticker_count():
    out = compare.build(lambda s: _snapshot(), lambda s: _longterm(),
                        ["A", "B", "C", "D", "E", "F"])
    assert len(out["tickers"]) == compare.MAX_TICKERS


def test_build_deduplicates():
    out = compare.build(lambda s: _snapshot(), lambda s: _longterm(),
                        ["NVDA", "nvda", "AMD"])
    assert out["tickers"] == ["NVDA", "AMD"]


def test_build_reports_a_failed_lookup_without_losing_the_rest():
    def snap(sym):
        if sym == "BAD":
            raise ValueError("No price data found for 'BAD'.")
        return _snapshot()

    out = compare.build(snap, lambda s: _longterm(), ["NVDA", "AMD", "BAD"])
    assert out["available"] is True
    assert len(out["rows"]) == 2
    assert out["failed"] == [{"ticker": "BAD", "reason": "No price data found for 'BAD'."}]


def test_build_unavailable_when_too_few_survive():
    def snap(sym):
        if sym == "NVDA":
            return _snapshot()
        raise ValueError("nope")

    out = compare.build(snap, lambda s: _longterm(), ["NVDA", "BAD"])
    assert out["available"] is False
    assert out["failed"][0]["ticker"] == "BAD"


def test_ranks_are_ordered_and_ties_share_a_rank():
    """Identical inputs must not be ordered by something arbitrary."""
    out = compare.build(lambda s: _snapshot(), lambda s: _longterm(), ["AAA", "BBB"])
    for hid, ranks in out["ranks"].items():
        assert [r["rank"] for r in ranks] == [1, 1], hid


def test_horizons_are_ranked_independently():
    """The whole reason this is a separate tab: the answer can differ by horizon."""
    swing_winner = _snapshot()
    swing_winner["technicals"]["rsi"]["value"] = 60
    swing_winner["technicals"]["moving_averages"]["sma20"]["distance_pct"] = 7.0

    long_winner = _snapshot()
    long_winner["technicals"]["rsi"]["value"] = 38
    long_winner["technicals"]["moving_averages"]["sma20"]["distance_pct"] = -6.0

    lt_strong = _longterm()
    lt_strong["holding"]["horizons"]["cagr_5y_pct"] = 34.0
    lt_strong["holding"]["risk"]["annualised_vol_pct"] = 30.0
    lt_weak = _longterm()
    lt_weak["holding"]["horizons"]["cagr_5y_pct"] = -3.0
    lt_weak["holding"]["risk"]["annualised_vol_pct"] = 70.0
    lt_weak["holding"]["drawdown"]["current_drawdown_pct"] = -35.0

    snaps = {"HOT": swing_winner, "SLOW": long_winner}
    lts = {"HOT": lt_weak, "SLOW": lt_strong}
    out = compare.build(lambda s: snaps[s], lambda s: lts[s], ["HOT", "SLOW"])
    assert out["ranks"]["swing"][0]["ticker"] == "HOT"
    assert out["ranks"]["longterm"][0]["ticker"] == "SLOW"


def test_todays_move_does_not_drive_the_longer_horizons():
    """The panel says so, so it has to be true."""
    calm, crashed = _snapshot(), _snapshot()
    crashed["quote"]["change_pct"] = -14.0
    a = compare._metrics(calm, _longterm())
    b = compare._metrics(crashed, _longterm())
    for hid in ("position", "longterm"):
        assert compare.SCORERS[hid](a) == compare.SCORERS[hid](b)


def test_every_horizon_has_a_scorer_and_a_stated_basis():
    ids = {h["id"] for h in compare.HORIZONS}
    assert ids == set(compare.SCORERS)
    for h in compare.HORIZONS:
        assert h["basis"].strip() and h["horizon"].strip() and h["name"].strip()


def test_ratio_uses_a_matched_window():
    """`cagr_per_vol_5y` is derived rather than read from holding.sharpe_proxy,
    which divides a one-year return by a multi-year volatility."""
    lt = _longterm()
    lt["holding"]["horizons"]["cagr_5y_pct"] = 24.0
    lt["holding"]["risk"]["annualised_vol_pct"] = 48.0
    lt["holding"]["risk"]["sharpe_proxy"] = 6.84  # the mixed-window figure
    m = compare._metrics(_snapshot(), lt)
    assert m["cagr_per_vol_5y"] == 0.5
    assert "sharpe_proxy" not in m


def test_ratio_guards_a_zero_denominator():
    assert compare._ratio(10.0, 0) is None
    assert compare._ratio(10.0, None) is None
    assert compare._ratio(None, 10.0) is None
