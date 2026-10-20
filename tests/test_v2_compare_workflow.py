"""Compare (backlog task 7, 2026-10-20): one rule for leaders and ties, honest windows and labels, the
benchmark and funds said as such, and a phone table that fits.

The scoring runs on built rows; the page's wiring is read as text and its tie arithmetic runs in
JavaScriptCore. The page itself was driven in headless Chrome at 360, 390, 430, 844x390, 768 and 1440 px
(~/Optic/work/v2-backlog/cmp_check.py: SPY against MSFT, a third name added and removed, a refusal and Try
again, the phone table's fit, short rows and sticky names).
"""
import numpy as np
import pandas as pd

from app.analytics import compare, longterm
from tests.test_compare import _longterm, _snapshot
from tests.test_frontend_v2_stage0 import V2, _run

PAGE = (V2 / "js/pages/compare.js").read_text()


def _built(scores_a, scores_b, extra_a=None, extra_b=None):
    """Two rows with fixed scores, through build()'s ranking and the take."""
    rows = {"AAA": scores_a, "BBB": scores_b}
    extras = {"AAA": extra_a or {}, "BBB": extra_b or {}}
    orig = dict(compare.SCORERS)
    try:
        for hid in compare.SCORERS:
            compare.SCORERS[hid] = (lambda h: (lambda m: rows[m["ticker"]].get(h)))(hid)
        snap = lambda sym: dict(_snapshot(), ticker=sym)                      # noqa: E731
        lt = lambda sym: _longterm()                                           # noqa: E731
        out = compare.build(snap, lt, ["AAA", "BBB"])
    finally:
        compare.SCORERS.update(orig)
    for r in out["rows"]:
        r.update(extras[r["ticker"]])
    out["leaders"] = compare.leaders(out["rows"])
    out["take"] = compare.take(out)
    return out


def test_five_points_as_shown_is_decisive_everywhere():
    # 70.3 - 65.3 is 4.999... in floating point: it printed "5.0 apart, under 5" and was called level
    out = _built({"swing": 70.3, "position": 60.0, "longterm": 50.0}, {"swing": 65.3, "position": 59.0, "longterm": 49.6})
    w = out["take"]["winners"]["swing"]
    assert w["gap"] == 5.0 and w["decisive"] is True
    sw = {e["ticker"]: e["standing"] for e in out["ranks"]["swing"]}
    assert sw == {"AAA": "best", "BBB": "#2"}
    pos = {e["ticker"]: (e["standing"], e["rank"]) for e in out["ranks"]["position"]}
    assert pos == {"AAA": ("level", 1), "BBB": ("level", 1)}, "within five points share first place"


def test_the_agreement_line_says_disagree_only_when_leaders_differ():
    one = _built({"swing": 80, "position": 80, "longterm": 50}, {"swing": 60, "position": 60, "longterm": 49})
    assert one["take"]["agreement"] == "AAA leads where the scores separate; one horizon is level."
    split = _built({"swing": 80, "position": 50, "longterm": 50}, {"swing": 60, "position": 70, "longterm": 49})
    assert split["take"]["agreement"] == "The horizons name different leaders."
    all3 = _built({"swing": 80, "position": 80, "longterm": 80}, {"swing": 60, "position": 60, "longterm": 60})
    assert all3["take"]["agreement"] == "All three horizons name AAA."
    none = _built({"swing": 50, "position": 50, "longterm": 50}, {"swing": 49, "position": 48, "longterm": 47})
    assert none["take"]["agreement"] == "Level on every horizon."
    assert "pill" not in PAGE.split("function take(c)")[1].split("function perf")[0]


def test_an_exact_tie_has_no_leader_and_a_hair_is_not_one():
    rows = [{"ticker": "AAA", "cagr_5y_pct": 12.0}, {"ticker": "BBB", "cagr_5y_pct": 12.0}]
    assert compare.leaders(rows)["cagr_5y_pct"] is None
    rows = [{"ticker": "AAA", "cagr_5y_pct": 12.004}, {"ticker": "BBB", "cagr_5y_pct": 12.001}]
    assert compare.leaders(rows)["cagr_5y_pct"] is None, "equal as the table prints them"
    rows = [{"ticker": "AAA", "cagr_5y_pct": 18.0}, {"ticker": "BBB", "cagr_5y_pct": 12.0}]
    assert compare.leaders(rows)["cagr_5y_pct"] == "AAA"
    rows = [{"ticker": "AAA", "annual_vol_pct": 30.0}, {"ticker": "BBB", "annual_vol_pct": 20.0}]
    assert compare.leaders(rows)["annual_vol_pct"] == "BBB", "lower is calmer"


def test_the_table_and_the_take_read_leaders_off_one_list():
    assert set(k for k, _h, _p in compare.TAKE_METRICS) <= set(compare.LEAD_ROWS)
    lead_rows = PAGE.split("export const GROUPS")[1].split("export function cell")[0]
    for key in compare.LEAD_ROWS:
        assert f"key: '{key}'" in lead_rows and "lead:" in lead_rows.split(f"key: '{key}'")[1].split("}")[0], key
    assert "leader(m, rows, c.leaders)" in PAGE and "within 2% of the row's spread" not in PAGE


def test_the_benchmark_and_a_fund_are_said_as_such():
    lt = _longterm()
    lt["holding"]["fundamentals"]["quote_type"] = "ETF"
    lt["holding"]["valuation"]["forward_pe"] = None
    snap = lambda sym: dict(_snapshot(), ticker=sym)                          # noqa: E731
    out = compare.build(snap, lambda sym: lt if sym == "SPY" else _longterm(), ["SPY", "NVDA"])
    spy = next(r for r in out["rows"] if r["ticker"] == "SPY")
    assert spy["is_benchmark"] and spy["kind"] == "fund"
    assert spy["rs_vs_spy"] is None and spy["beta_vs_spy"] is None and spy["excess_cagr_5y_pct"] is None
    assert spy["why_na"]["rs_vs_spy"] == "the benchmark" and spy["why_na"]["forward_pe"] == "a fund"
    nv = next(r for r in out["rows"] if r["ticker"] == "NVDA")
    assert not nv["is_benchmark"] and nv["kind"] == "stock" and nv["why_na"] == {}
    assert "cell(m.kind, r[m.key], (r.why_na || {})[m.key])" in PAGE and "'The benchmark'" in PAGE


def test_a_score_says_how_many_inputs_it_had():
    snap = lambda sym: dict(_snapshot(), ticker=sym, entry_plan={})           # no implied volatility off hours
    out = compare.build(snap, lambda sym: _longterm(), ["AAA", "BBB"])
    sw = out["ranks"]["swing"][0]
    assert sw["inputs"] == [4, 5]
    assert "from ${x.inputs[0]} of ${x.inputs[1]} inputs" in PAGE


def test_the_five_year_ratio_uses_five_years_of_volatility():
    idx = pd.bdate_range("2014-01-01", periods=12 * 252)
    rng = np.random.default_rng(1)
    calm, wild = rng.normal(0, 0.005, 7 * 252), rng.normal(0, 0.03, 5 * 252)
    close = pd.Series(100 * np.cumprod(1 + np.concatenate([calm, wild])), index=idx)
    r = longterm._risk_stats(close, None)
    assert r["annualised_vol_5y_pct"] > r["annualised_vol_pct"] * 1.3, "the last five years were the wild ones"
    short = longterm._risk_stats(close.tail(3 * 252), None)
    assert short["annualised_vol_5y_pct"] is None


def test_labels_say_price_only_and_the_twelve_year_window():
    for s in ("Five-year price return", "Below its 12-year high", "Worst fall in 12 years",
              "Annualised volatility, up to 12 years", "Return per unit of volatility, five years"):
        assert s in PAGE, s
    for gone in ("all-time high", "on record", "SPY ≈ 0.65"):
        assert gone not in PAGE, gone
    assert "all-time high" not in compare.HORIZONS[2]["basis"]


def test_the_page_gap_is_taken_at_one_decimal(tmp_path):
    got = _run(tmp_path, f"""
      const c = await import('{(V2 / "js/pages/compare.js").as_posix()}');
      print(JSON.stringify({{ gap: c.gapOf(70.3, 65.3), st: c.standing([{{ ticker: 'A', score: 70.3 }}, {{ ticker: 'B', score: 65.3 }}]),
        served: c.standing([{{ ticker: 'A', score: 66.8, standing: 'level' }}, {{ ticker: 'B', score: 66.4, standing: 'level' }}]),
        tie: c.leader({{ key: 'k', lead: 'high' }}, [{{ ticker: 'A', k: 5 }}, {{ ticker: 'B', k: 5 }}]) }}));
    """)
    assert got["gap"] == 5 and got["st"] == {"A": "best", "B": "#2"}
    assert got["served"] == {"A": "level", "B": "level"}
    assert got["tie"] is None, "an exact tie's dot used to go to the first column"


def test_state_a_stale_result_a_forced_retry_and_the_address():
    assert "const stale = () =>" in PAGE and "These results are for" in PAGE
    assert "run({ force: !(result && result.available) })" in PAGE
    assert "if (!got || !got.available) api.invalidate(path);" in PAGE
    assert "history.replaceState(history.state, '', `${location.pathname}${location.search}${want}`)" in PAGE


def test_a_phone_table_fits_and_keeps_what_rows_measure_on_request():
    css = (V2 / "css/pages.css").read_text()
    phone = css.split("/* A phone: the table fits the screen")[1].split("\n}\n")[0]
    assert ".cmp-t { table-layout: fixed; width: 100%; }" in phone
    assert ".cmp-t:not(.show-means) small.cmp-means { display: none; }" in phone
    assert "top: var(--cmp-top, 64px)" in phone and ".cmp-wrap.tscroll { overflow: visible; }" in phone
    assert ":not(.cmp-t) td:first-child" in (V2 / "css/components.css").read_text()
    assert "data-v2-cmp-means aria-pressed" in PAGE
