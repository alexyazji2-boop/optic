"""The books' rules from 2026-10-21.

The owner asked for the triggers to be reconsidered after the aggressive book
fell 8% in three weeks, and approved five rules (report and replay in the work
folder portfolio-triggers-2026-10-21): long only, a 2x gross cap for balanced
and aggressive, a stop at least 1.5 ATR from the entry, one position per idea
with options only when Optic rates implied volatility cheap, and trading costs
in the ledger. Open positions keep the rules they were opened with, and the
record keeps running with a dated line saying the rules changed.

These tests hold each of those to its decision, and hold the old positions to
theirs.
"""
from __future__ import annotations

import re

import pytest

from app import paper


@pytest.fixture()
def ledger(tmp_path, monkeypatch):
    monkeypatch.setattr(paper, "DB_PATH", str(tmp_path / "tracker.db"))
    paper.init_db()
    return paper


def _snapshot(score=45.0, spot=100.0, support=None, atr14=2.0, verdict="cheap",
              quotable=True, ticker="NVDA"):
    plan = {"actionable": True, "iv_context": {"verdict": verdict},
            "recommended": ({"strike": 100.0, "expiry": "2026-12-18", "entry_mid": 4.0}
                            if quotable else {})}
    return {"ticker": ticker, "verdict": {"composite_score": score, "summary": "test"},
            "quote": {"price": spot}, "entry_plan": plan,
            "technicals": {"support_resistance": ([{"price": support}] if support else []),
                           "volatility": {"atr14": atr14, "atr_pct": atr14 / spot * 100}}}


# ------------------------------------------------------------- the settings


def test_every_book_carries_the_approved_settings():
    want = {
        "conservative": (None, [], False),
        "balanced": (2.0, ["cheap"], True),
        "aggressive": (2.0, ["cheap"], True),
    }
    for book, (gross, iv, prefer) in want.items():
        cfg = paper.book_config(book)
        assert cfg["allow_shorts"] is False, book
        assert cfg["max_gross_exposure"] == gross, book
        assert cfg["min_stop_atr"] == 1.5, book
        assert cfg["option_iv_verdicts"] == iv, book
        assert cfg["one_leg_per_idea"] is True, book
        assert cfg["charge_costs"] is True, book
        assert cfg["prefer_options"] is prefer, book


def test_the_books_still_differ_in_what_they_were_built_to_show():
    """The new rules are common to all three; risk, bar, volatility and option
    access still separate them."""
    risks = [paper.book_config(b)["risk_per_trade"] for b in paper.BOOK_IDS]
    assert risks == sorted(risks) and len(set(risks)) == 3
    assert paper.book_config("conservative")["allow_options"] is False


# --------------------------------------------------------------- long only


def test_a_bearish_signal_opens_nothing_in_any_book():
    for book in paper.BOOK_IDS:
        found, notes = paper.consider_ticker(_snapshot(score=-70.0, support=110.0), 100_000.0, book)
        assert found == [], book
        assert notes and "long only" in notes[0], (book, notes)


def test_a_bullish_signal_still_trades():
    found, _ = paper.consider_ticker(_snapshot(score=60.0, support=90.0), 100_000.0, "conservative")
    assert len(found) == 1 and found[0]["direction"] == "long"


# --------------------------------------------------------------- stop floor


def test_a_stop_inside_one_and_a_half_atr_is_moved_out():
    """Support half a point under a $100 stock with a $2 ATR would put the stop
    inside one day's ordinary range."""
    found, notes = paper.consider_ticker(_snapshot(support=99.4, verdict="fair"), 100_000.0, "balanced")
    (leg,) = found
    assert leg["stop"] == 97.0, "100 - 1.5 x 2"
    assert leg["target"] == 106.0, "2R from the moved stop"
    assert any("stop moved out" in n for n in notes)


def test_a_stop_already_wide_enough_is_left_where_support_put_it():
    found, notes = paper.consider_ticker(_snapshot(support=95.0, verdict="fair"), 100_000.0, "balanced")
    (leg,) = found
    assert leg["stop"] == round(95.0 * 0.99, 2)
    assert not any("stop moved out" in n for n in notes)


def test_a_wider_stop_means_fewer_shares_not_more_risk():
    tight = paper.size_shares(100.0, 99.0, 100_000.0, "aggressive")
    floored = paper.size_shares(100.0, 97.0, 100_000.0, "aggressive")
    assert floored["qty"] <= tight["qty"]
    assert floored["risk_dollars"] <= 100_000.0 * 0.02 + 1e-6


# --------------------------------------------- one leg, options when cheap


def test_aggressive_takes_the_option_instead_of_the_shares_when_iv_is_cheap():
    found, _ = paper.consider_ticker(_snapshot(support=90.0, verdict="cheap"), 100_000.0, "aggressive")
    assert [leg["instrument"] for leg in found] == ["option"]
    assert found[0]["option_type"] == "call"


def test_balanced_does_the_same():
    found, _ = paper.consider_ticker(_snapshot(support=90.0, verdict="cheap"), 100_000.0, "balanced")
    assert [leg["instrument"] for leg in found] == ["option"]


@pytest.mark.parametrize("verdict", ["fair", "slightly rich", "rich", "unknown", None])
def test_any_other_iv_verdict_takes_the_shares_and_says_why(verdict):
    for book in ("balanced", "aggressive"):
        found, notes = paper.consider_ticker(_snapshot(support=90.0, verdict=verdict), 100_000.0, book)
        assert [leg["instrument"] for leg in found] == ["shares"], (book, verdict)
        if book == "balanced":
            assert any("buys options only when it reads cheap" in n for n in notes), notes


def test_conservative_never_holds_an_option():
    found, _ = paper.consider_ticker(_snapshot(score=60.0, support=90.0, verdict="cheap"), 100_000.0,
                                     "conservative")
    assert [leg["instrument"] for leg in found] == ["shares"]


def test_with_no_quotable_contract_the_shares_are_taken():
    found, _ = paper.consider_ticker(_snapshot(support=90.0, verdict="cheap", quotable=False),
                                     100_000.0, "aggressive")
    assert [leg["instrument"] for leg in found] == ["shares"]


def test_the_rules_are_settings_not_code_paths(monkeypatch):
    """Switched off, a book behaves as it did before 2026-10-21: both legs, any
    IV verdict, shorts allowed."""
    for key, value in (("one_leg_per_idea", False), ("option_iv_verdicts", None),
                       ("allow_shorts", True), ("min_stop_atr", None)):
        monkeypatch.setitem(paper.BOOKS["balanced"], key, value)
    found, _ = paper.consider_ticker(_snapshot(support=90.0, verdict="rich"), 100_000.0, "balanced")
    assert sorted(leg["instrument"] for leg in found) == ["option", "shares"]
    short, _ = paper.consider_ticker(_snapshot(score=-60.0, support=None), 100_000.0, "balanced")
    assert short and all(leg["direction"] in ("short", "long") for leg in short)


# -------------------------------------------------------------- gross cap


def test_gross_exposure_counts_shares_and_option_premium_at_their_marks():
    rows = [{"instrument": "shares", "qty": 100, "entry_price": 50.0, "mark_price": 60.0},
            {"instrument": "option", "qty": 2, "entry_price": 3.0, "mark_price": None},
            {"instrument": "shares", "qty": 10, "entry_price": 20.0, "mark_price": 20.0}]
    assert paper.gross_exposure(rows) == 100 * 60 + 2 * 3 * 100 + 10 * 20


def test_a_candidate_over_the_room_is_cut_to_fit():
    cand = {"instrument": "shares", "qty": 400, "entry_price": 100.0, "stop": 97.0, "risk_dollars": 1200.0}
    fit = paper._fit_gross(cand, 25_000.0)
    assert fit["qty"] == 250 and fit["risk_dollars"] == 750.0
    assert cand["qty"] == 400, "the original is not mutated"


def test_below_one_unit_the_candidate_is_dropped_and_no_cap_passes_it():
    cand = {"instrument": "option", "qty": 3, "entry_price": 4.0, "stop": 90.0, "risk_dollars": 1200.0}
    assert paper._fit_gross(cand, 300.0) is None, "one contract is $400"
    assert paper._fit_gross(cand, 800.0)["qty"] == 2
    assert paper._fit_gross(cand, None) is cand


def test_capacity_reports_gross_against_the_books_cap(ledger):
    pos = dict(paper.consider_ticker(_snapshot(support=90.0, verdict="fair"), 100_000.0, "aggressive")[0][0])
    paper.open_position(pos)
    cap = paper._capacity(100_000.0, "aggressive")
    gross = pos["qty"] * pos["entry_price"]
    assert cap["gross_exposure"] == round(gross, 2)
    assert cap["max_gross_exposure_x"] == 2.0
    assert cap["gross_room"] == round(200_000.0 - gross, 2)
    assert paper._capacity(100_000.0, "conservative")["gross_room"] is None


def test_the_scan_fits_each_candidate_under_the_cap_before_the_risk_check():
    src = open("app/paper.py").read()
    loop = src[src.index("def run_scan"):]
    loop = loop[:loop.index("\ndef ", 10)]
    fit = loop.index('_fit_gross(candidate, cap.get("gross_room"))')
    assert fit < loop.index('room = cap["risk_budget_left"]'), "cut first, then admit the risk"


# ------------------------------------------------------------------- costs


def test_cost_rates_are_the_validation_programs():
    assert paper.cost_bps_for("SPY") == 10.0, "5 bp a fund plus 5 slippage"
    assert paper.cost_bps_for("soxl") == 10.0
    assert paper.cost_bps_for("NVDA") == 15.0, "10 bp a stock plus 5 slippage"


def test_a_position_with_a_rate_is_charged_both_sides():
    pos = {"instrument": "shares", "direction": "long", "qty": 10, "entry_price": 100.0, "cost_bps": 15.0}
    out = paper._pnl(pos, 110.0)
    assert out["costs"] == round(15 / 1e4 * (100 + 110) * 10, 2)
    assert out["pnl"] == round(100.0 - out["costs"], 2)


def test_options_are_charged_on_premium():
    pos = {"instrument": "option", "direction": "long", "qty": 2, "entry_price": 4.0, "cost_bps": 15.0}
    out = paper._pnl(pos, 5.0)
    assert out["costs"] == round(15 / 1e4 * (4 + 5) * 2 * 100, 2)


def test_a_position_from_before_the_change_is_charged_nothing():
    """The owner's decision: open positions keep the rules they were opened with.
    The Paper Desk shares this function and has no rate either."""
    pos = {"instrument": "shares", "direction": "long", "qty": 10, "entry_price": 100.0}
    assert paper._pnl(pos, 110.0) == {"pnl": 100.0, "pnl_pct": 10.0}
    pos["cost_bps"] = None
    assert paper._pnl(pos, 110.0) == {"pnl": 100.0, "pnl_pct": 10.0}


def test_a_new_position_opens_net_of_costs_and_records_its_rules(ledger):
    leg = paper.consider_ticker(_snapshot(support=90.0, verdict="fair"), 100_000.0, "balanced")[0][0]
    assert leg["rules_version"] == paper.RULES_VERSION and leg["cost_bps"] == 15.0
    pid = paper.open_position(leg)
    row = paper._rows("SELECT * FROM positions WHERE id=?", (pid,))[0]
    both_sides = 15 / 1e4 * 2 * leg["entry_price"] * leg["qty"]
    assert row["pnl"] == pytest.approx(-both_sides, abs=0.01)
    assert row["costs"] == pytest.approx(both_sides, abs=0.01)
    assert row["rules_version"] == paper.RULES_VERSION


def test_closing_records_net_pnl_and_the_summary_reports_costs(ledger):
    leg = paper.consider_ticker(_snapshot(support=90.0, verdict="fair"), 100_000.0, "balanced")[0][0]
    pid = paper.open_position(leg)
    row = paper._rows("SELECT * FROM positions WHERE id=?", (pid,))[0]
    paper.close_position(pid, 110.0, 110.0, "Target hit", row)
    closed = paper._rows("SELECT * FROM positions WHERE id=?", (pid,))[0]
    gross = (110.0 - leg["entry_price"]) * leg["qty"]
    costs = 15 / 1e4 * (leg["entry_price"] + 110.0) * leg["qty"]
    assert closed["pnl"] == pytest.approx(gross - costs, abs=0.01)
    s = paper.summary("balanced")
    assert s["costs_charged"] == pytest.approx(costs, abs=0.01)
    assert s["equity"] == pytest.approx(100_000.0 + gross - costs, abs=0.01)


def test_an_old_open_position_closes_without_costs(ledger):
    """A row from before the change: no rules_version, no rate."""
    with paper._connect() as conn:
        conn.execute(
            "INSERT INTO positions (book,ticker,instrument,direction,qty,entry_price,entry_spot,"
            "entry_at,status,pnl,pnl_pct,risk_dollars,stop,target) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            ("aggressive", "HD", "shares", "short", 56, 289.775, 289.775,
             "2026-09-29T14:00:00+00:00", "open", 0.0, 0.0, 1972.6, 325.0, 219.32))
    row = paper._rows("SELECT * FROM positions WHERE ticker='HD'")[0]
    paper.close_position(row["id"], 314.57, 314.57, "Time stop (45 days)", row)
    closed = paper._rows("SELECT * FROM positions WHERE ticker='HD'")[0]
    assert closed["pnl"] == round((289.775 - 314.57) * 56, 2)
    assert closed["costs"] is None


# ------------------------------------------------------- the dated change


def test_the_rules_change_is_dated_once_and_never_moves(ledger):
    first = paper.rules_change()
    assert first["version"] == paper.RULES_VERSION and first["at"] and first["date"]
    paper.init_db()
    paper.init_db()
    assert paper.rules_change()["at"] == first["at"]
    keys = [r["key"] for r in paper._rows("SELECT key FROM ledger_meta")]
    assert keys.count(paper.RULES_CHANGE_KEY) == 1


def test_a_rules_change_is_not_a_restart(ledger):
    """The record keeps running: nothing is archived by the change."""
    paper.open_position(paper.consider_ticker(_snapshot(support=90.0, verdict="fair"),
                                              100_000.0, "balanced")[0][0])
    paper.init_db()
    assert paper.summary("balanced")["open_count"] == 1
    assert len(paper.archived_records()) == len(paper.RESTARTS)


def test_the_page_payload_carries_the_change_and_dated_caveats(ledger):
    state = paper.state(book="aggressive")
    rc = state["rules_change"]
    assert rc["date"] and "long only" in rc["summary"]
    first = state["caveats"][0]
    assert first.startswith("The rules changed on " + rc["date"])
    assert "keep the rules they were opened with" in first
    assert any("charged" in c and "basis points" in c for c in state["caveats"])
    assert not any("no commission or slippage is charged" in c for c in state["caveats"])
    cfg = state["config"]
    assert (cfg["cost_bps_fund"], cfg["cost_bps_stock"], cfg["slippage_bps"]) == (5.0, 10.0, 5.0)
    book = next(b for b in state["books"] if b["id"] == "aggressive")
    assert book["max_gross_exposure"] == 2.0 and book["capacity"]["max_gross_exposure_x"] == 2.0


def test_no_copy_reads_with_an_em_dash():
    text = paper.RULES_CHANGE_SUMMARY + " ".join(paper.book_config(b)["blurb"] for b in paper.BOOK_IDS)
    assert "—" not in text


# ------------------------------------------------------------- the pages


def _code(text):
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.S)
    return re.sub(r"^\s*//.*$", " ", text, flags=re.M)


V2 = _code(open("static/v2/js/pages/tracker.js").read())
CLASSIC = _code(open("static/app.js").read())


def test_v2_shows_the_dated_line_under_the_book_cards():
    books = V2[V2.index("function books("):V2.index("function ledger(")]
    assert "${rulesChangedLine(d.rules_change)}" in books
    line = V2[V2.index("export function rulesChangedLine"):]
    line = line[:line.index("\n}") + 2]
    assert "Rules changed on ${rc.date}." in line
    assert "if (!rc || !rc.date) return ''" in line, "no line before a change is recorded"
    assert "class=\"pill\"" not in line and "—" not in line


def test_v2_describes_each_book_from_its_own_settings():
    rules = V2[V2.index("export function bookRules"):]
    rules = rules[:rules.index("\n}") + 2]
    assert "b.allow_shorts === false" in rules and "long only" in rules
    assert "b.max_gross_exposure" in rules
    assert "${bookRules(b)}" in V2
    assert "Each trades both instruments" not in V2


def test_v2_rule_table_reads_the_selected_books_values():
    rest = V2[V2.index("function rest("):V2.index("function paint(")]
    for needle in ("bk.max_gross_exposure", "bk.min_stop_atr", "bk.charge_costs", "bk.allow_shorts === false",
                   "bk.min_composite ?? cfg.min_composite", "capFirst(legsText(bk))"):
        assert needle in rest, needle


def test_classic_shows_the_same_line_and_rules():
    sel = CLASSIC[CLASSIC.index("function renderBookSelector("):CLASSIC.index("\nfunction renderTracker")]
    assert "${rulesChangedHTML(d.rules_change)}" in sel
    assert "bookLegsText(b)" in sel and "b.allow_shorts === false" in sel
    fn = CLASSIC[CLASSIC.index("function rulesChangedHTML("):]
    fn = fn[:fn.index("\n}") + 2]
    assert "Rules changed on ${esc(rc.date)}." in fn and "—" not in fn
    assert "Each trades\n      both instruments" not in CLASSIC


def test_the_portfolio_disclaimer_no_longer_says_no_costs():
    """It said the trades bear no commission or slippage, which stops being true
    for new trades when the 2026-10-21 rules take effect. The Paper Desk's own
    notice is untouched. The rules start when a build with them first opens the
    ledger, not on the day they were approved, so no notice names a date: each
    points to the dated "Rules changed on" line instead."""
    from app import legal
    assert legal.AREAS["tracker"] == legal.TRACKER_SIMULATED
    for text in (legal.TRACKER_SIMULATED, legal.PAGE_AREAS["tracker"]):
        assert "modelled allowance for commission and slippage" in text
        assert "earlier trades carry none" in text
        assert "Since the rules change dated on this page" in text and "2026" not in text
    assert "bear no commission, slippage" in legal.PAGE_AREAS["paper"]
    for path in ("static/app.js", "static/v2/js/core/legal.js"):
        text = open(path).read()
        start = text.index("tracker: ", text.index("areas: {"))
        quote = text[start + len("tracker: ")]
        tracker = text[start + len("tracker: ") + 1:]
        tracker = tracker[:tracker.index(quote + ",\n")]
        assert tracker == legal.PAGE_AREAS["tracker"], path
        assert "bear no commission, slippage" not in tracker, path
        assert "<strong>Hypothetical performance.</strong> Positions you enter" in text, path
