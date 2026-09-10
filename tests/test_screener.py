"""Free-form screening: the fourteenth question.

The terminal had thirteen curated screens and no way to ask anything else. This
is a filter and a sort over the ranking the scans already share — it never builds
one, because that is three thousand downloads and belongs in the background.

The tests that matter most here are about honesty rather than arithmetic. A
screener that quietly drops half the universe before your first filter runs, or
counts an unmeasurable value as passing a bound, gives an answer that is wrong in
a way you cannot see.
"""

from __future__ import annotations

import re
import time
from pathlib import Path

import pytest

from app.analytics import screener

ROOT = Path(__file__).resolve().parent.parent
APP_JS = (ROOT / "static" / "app.js").read_text()
STYLES = (ROOT / "static" / "styles.css").read_text()
MAIN_PY = (ROOT / "app" / "main.py").read_text()


def _ranking(rows, age_hours=1.0):
    return {"ranked": rows, "ranked_at": time.time() - age_hours * 3600,
            "universe_size": 2951, "passed": len(rows),
            "gates": {"min_price": 5.0, "min_dollar_volume": 2e7}}


def _row(symbol, **kw):
    base = {"symbol": symbol, "price": 100.0, "dollar_volume": 5e7,
            "sma20": 95.0, "sma50": 90.0, "sma200": 80.0,
            "roc20": 5.0, "roc60": 10.0, "range_position": 0.8,
            "volume_expansion": 1.2, "atr_pct": 3.0, "score": 40.0}
    base.update(kw)
    return base


# ------------------------------------------------------------ the vocabulary

def test_every_field_is_fully_described():
    for f in screener.FIELDS:
        for key in ("id", "label", "unit", "decimals", "help", "get"):
            assert key in f, f"{f.get('id')} has no {key}"


def test_describe_does_not_leak_the_getters():
    """It is JSON on the wire. A callable would raise at serialisation time, on
    the endpoint rather than here."""
    out = screener.describe()
    assert all("get" not in f for f in out["fields"])
    assert out["blind_spot"]


def test_the_ui_is_generated_from_the_published_list():
    """CLAUDE.md: three watch conditions once compared a stored parameter against
    a vocabulary spelled elsewhere in the app. All three stored fine, evaluated
    fine and never fired, which looks exactly like "nothing matched"."""
    assert "getJSON('/api/screener/fields')" in APP_JS
    for f in screener.FIELDS:
        # No field id may be hardcoded into the builder's markup.
        assert f"'{f['id']}'" not in APP_JS.split("function screenerBuilder(", 1)[1] \
            .split("\n}\n", 1)[0], f"{f['id']} is hardcoded in the builder"


# ------------------------------------------------------------ parsing bounds

def test_an_unknown_field_is_dropped_not_fatal():
    """A filter the server does not know is a stale tab. Losing the whole request
    would be a worse answer than running the rest."""
    out = screener.parse_filters([{"field": "pe_ratio", "min": 1},
                                  {"field": "price", "min": 10}])
    assert [f["field"] for f in out] == ["price"]


def test_an_empty_bound_is_not_a_filter():
    assert screener.parse_filters([{"field": "price"}]) == []
    assert screener.parse_filters([{"field": "price", "min": None, "max": None}]) == []


def test_a_reversed_pair_is_read_as_a_typo():
    out = screener.parse_filters([{"field": "price", "min": 90, "max": 10}])
    assert out == [{"field": "price", "min": 10.0, "max": 90.0}]


def test_the_filter_count_is_capped():
    many = [{"field": "price", "min": i} for i in range(40)]
    assert len(screener.parse_filters(many)) <= screener.MAX_FILTERS


def test_junk_input_does_not_raise():
    for junk in (None, "price", 7, [{"nope": 1}], [None], [[]]):
        screener.parse_filters(junk)
        screener.parse_states(junk)


# -------------------------------------------------------------------- running

def test_no_ranking_says_why_and_points_somewhere():
    out = screener.run(None, filters=[{"field": "price", "min": 1}])
    assert out["available"] is False
    assert "background" in out["reason"]
    assert "scan" in out["reason"].lower()


def test_bounds_are_inclusive_at_both_ends():
    rows = [_row("A", price=10.0), _row("B", price=20.0), _row("C", price=30.0)]
    out = screener.run(_ranking(rows), filters=[{"field": "price", "min": 10, "max": 30}])
    assert {r["symbol"] for r in out["rows"]} == {"A", "B", "C"}


def test_an_unmeasurable_value_does_not_pass_a_bound():
    """"Missing" is not "small". A None ATR sailing through `atr_pct < 6` would
    put untested names at the top of a screen for calm movers."""
    rows = [_row("A", atr_pct=3.0), _row("B", atr_pct=None)]
    out = screener.run(_ranking(rows), filters=[{"field": "atr_pct", "max": 6}])
    assert [r["symbol"] for r in out["rows"]] == ["A"]


def test_the_funnel_reports_each_bound():
    """An empty screen has to say which condition emptied it."""
    rows = [_row(s, roc60=r) for s, r in (("A", 50.0), ("B", 5.0), ("C", -5.0))]
    out = screener.run(_ranking(rows), filters=[{"field": "roc60", "min": 10},
                                                {"field": "price", "min": 1e9}])
    assert [(f["before"], f["after"]) for f in out["funnel"]] == [(3, 1), (1, 0)]
    assert out["matched"] == 0


def test_the_states_are_relationships_a_bound_cannot_express():
    rows = [_row("UP", sma50=90.0, sma200=80.0), _row("DOWN", sma50=70.0, sma200=80.0)]
    out = screener.run(_ranking(rows), states=["golden"])
    assert [r["symbol"] for r in out["rows"]] == ["UP"]


def test_unmeasurable_rows_sink_whichever_way_the_sort_runs():
    """Ascending, a None would otherwise arrive first as though it were the
    smallest value in the set."""
    rows = [_row("A", roc60=5.0), _row("B", roc60=None), _row("C", roc60=1.0)]
    for direction, first in (("asc", "C"), ("desc", "A")):
        out = screener.run(_ranking(rows), sort="roc60", direction=direction)
        assert out["rows"][0]["symbol"] == first, direction
        assert out["rows"][-1]["symbol"] == "B", direction


def test_the_columns_always_carry_price_return_and_score():
    out = screener.run(_ranking([_row("A")]), filters=[{"field": "atr_pct", "max": 9}])
    ids = [c["id"] for c in out["columns"]]
    assert {"price", "roc20", "score"} <= set(ids)
    assert ids[0] == "score", "the sort field leads the table"


def test_the_prefilter_is_reported_not_hidden():
    """The biggest cut is one the reader never set: 1,930 of 2,951 names are
    dropped as illiquid before any bound of theirs runs. A "12 matched" with no
    denominators beside it is a different claim entirely."""
    out = screener.run(_ranking([_row("A")]))
    assert out["universe"] == 2951, "the ranking's key is universe_size, not universe"
    assert out["prefiltered"] == 1
    assert out["gates"]["min_dollar_volume"] == 2e7


def test_a_stale_ranking_is_labelled():
    out = screener.run(_ranking([_row("A")], age_hours=40))
    assert out["stale"] is True
    fresh = screener.run(_ranking([_row("A")], age_hours=1))
    assert fresh["stale"] is False


def test_the_blind_spot_is_always_present():
    """Every panel states what it cannot tell you."""
    for out in (screener.run(None), screener.run(_ranking([_row("A")]))):
        assert "fundamentals" in out["blind_spot"]


def test_the_row_limit_is_bounded():
    rows = [_row(f"S{i}") for i in range(300)]
    assert len(screener.run(_ranking(rows), limit=99999)["rows"]) <= 200


# ------------------------------------------------------------------ the wiring

def test_the_endpoints_exist():
    assert '@app.get("/api/screener/fields")' in MAIN_PY
    assert '@app.post("/api/screener")' in MAIN_PY


def test_the_screener_never_builds_a_ranking():
    """screen.run downloads and scores three thousand symbols. A screener that
    triggered it would be a page that hangs."""
    block = MAIN_PY.split('@app.post("/api/screener")', 1)[1].split("@app.", 1)[0]
    assert "_cached_ranking()" in block
    assert "screen_mod.run" not in block


@pytest.mark.parametrize("attr,handler", [
    ("data-sc-add", "paintScreener"),
    ("data-sc-del", "splice"),
    ("data-sc-reset", "STATE.screener ="),
    ("data-sc-run", "runScreener"),
    ("data-scan-mode", "STATE.scanMode"),
])
def test_every_builder_control_has_a_handler(attr, handler):
    assert f"closest('[{attr}]')" in APP_JS, f"{attr} has no handler"
    block = APP_JS.split(f"closest('[{attr}]')", 1)[1][:500]
    assert handler in block, f"{attr} does not reach {handler}"


def test_the_builder_is_delegated_not_bound():
    """It rebuilds itself every time a filter is added or removed, so a
    bind-once loop would only reach the rows that existed at view paint."""
    assert "document.addEventListener('click'" in APP_JS
    block = APP_JS.split("function bindScanPills() {", 1)[1].split("\n}\n", 1)[0]
    assert "data-sc-" not in block, "the builder is being bound directly"


def test_the_bounds_do_not_repaint_on_every_keystroke():
    """A repaint per keystroke rebuilt the row under the cursor and lost the
    caret halfway through typing "12.5"."""
    block = APP_JS.split("if (t.dataset.scMin !== undefined", 1)[1][:400]
    assert "return;" in block
    assert "paintScreener()" not in block


def test_switching_modes_does_not_refetch_the_scan():
    assert "STATE.scanResult = res;" in APP_JS
    block = APP_JS.split("closest('[data-scan-mode]')", 1)[1][:600]
    assert "STATE.scanResult" in block


@pytest.mark.parametrize("cls", [".scan-modes", ".sc-filter", ".sc-field", ".sc-bound",
                                 ".sc-drop", ".sc-help", ".sc-states", ".sc-sort",
                                 ".sc-funnel", ".sc-fn-n"])
def test_the_builder_is_styled(cls):
    assert re.search(re.escape(cls) + r"[\s,{:]", STYLES), f"{cls} has no rule"
