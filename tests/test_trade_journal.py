"""The connected trade journal (roadmap stage 3, 2026-10-22), in JavaScriptCore.

A practice trade carries its plan, frozen when it opens; later changes are revisions beside it. Evidence is
counted by source family. The review states its sample size and what the records were missing. A pick from
the contract picker reaches the Paper Desk's ticket without being typed again. The journal lives in the
browser's own Paper Desk book, apart from Optic Portfolio.
"""
from __future__ import annotations

from tests.test_frontend_v2_stage0 import V2, _run

JS = V2 / "js"
PAPER = (JS / "pages/paper.js").read_text()


def test_the_plan_is_frozen_and_a_change_is_a_revision(tmp_path):
    got = _run(tmp_path, f"""
      const J = await import('{(JS / "core/journal.js").as_posix()}');
      const plan = J.freezePlan({{ thesis: 'Held the 50-day', setup: 'pullback', hold_days: '10', stop: 95, target: 110, invalidation: 'Close below 95',
        evidence: [{{ text: 'Held the 50-day', family: 'trend' }}, {{ text: 'RSI back over 50', family: 'momentum' }}, {{ text: 'MACD crossed', family: 'momentum' }}, {{ text: '', family: 'volume' }}] }}, '2026-10-20T15:00:00Z');
      const t0 = {{ id: 'a', plan, revisions: [] }};
      const t1 = J.revise(t0, {{ target: 115, hold_days: 10 }}, '2026-10-21T15:00:00Z');
      const empty = J.freezePlan({{ target: null, hold_days: '' }});
      print(JSON.stringify({{ plan, t1, cur: J.currentPlan(t1), ind: J.independence(plan.evidence), empty }}));
    """)
    assert got["plan"]["hold_days"] == 10 and got["plan"]["setup"] == "pullback" and len(got["plan"]["evidence"]) == 3
    assert got["empty"]["target"] is None and got["empty"]["hold_days"] is None, "a blank is not a zero"
    assert got["t1"]["plan"]["target"] == 110, "the original plan is untouched"
    assert got["t1"]["revisions"] == [{"at": "2026-10-21T15:00:00Z", "field": "target", "from": 110, "to": 115}], "an unchanged field is not a revision"
    assert got["cur"]["target"] == 115
    ind = got["ind"]
    assert ind["items"] == 3 and ind["families"] == 2 and ind["repeated"][0]["family"] == "momentum"
    assert "2 momentum readings count once" in ind["note"] and "not a probability" in ind["note"]


def test_the_review_counts_what_it_rests_on_and_what_is_missing(tmp_path):
    got = _run(tmp_path, f"""
      const J = await import('{(JS / "core/journal.js").as_posix()}');
      const mk = (i, pnl, setup, days, adh, through) => ({{ id: 'c' + i, ticker: 'X', pnl, r: pnl / 100, entry_at: `2026-09-${{String(1 + i).padStart(2, '0')}}T15:00:00Z`,
        closed_at: new Date(Date.parse(`2026-09-${{String(1 + i).padStart(2, '0')}}T15:00:00Z`) + days * 864e5).toISOString(),
        plan: setup ? {{ setup, hold_days: days, catalyst_date: through ? `2026-09-${{String(2 + i).padStart(2, '0')}}` : null, evidence: [] }} : null,
        adherence: adh ? {{ entry: adh, exit: adh }} : null, reflection: i % 2 ? 'ok' : '' }});
      const closed = [mk(1, 200, 'pullback', 3, 'yes', true), mk(2, -100, 'pullback', 10, 'no', false), mk(3, -150, 'breakout', 30, 'yes', false), mk(4, 50, null, 2, null, false)];
      print(JSON.stringify(J.review(closed)));
    """)
    assert got["all"]["n"] == 4 and got["all"]["wins"] == 2 and abs(got["all"]["expectancy"] - 0.0) < 1e-9
    assert got["all"]["avg_win"] == 125 and got["all"]["avg_loss"] == -125
    setups = {x["label"]: x["n"] for x in got["by_setup"]}
    assert setups == {"Pullback in a trend": 2, "Breakout": 1, "Not recorded": 1}
    assert {x["label"] for x in got["by_hold"]} == {"up to 5 days", "6 to 20 days", "21 to 60 days"}
    assert {x["label"]: x["n"] for x in got["by_adherence"]} == {"followed the plan": 2, "departed from it": 1, "not recorded": 1}
    assert {x["label"] for x in got["by_catalyst"]} >= {"held through its catalyst", "no catalyst recorded"}
    assert got["max_drawdown"] == -250, "from +200 to -50 in close order"
    assert got["missing"]["no_plan"] == 1 and got["small"] and "too few" in got["note"]


def test_milo_gets_the_record_and_a_rule_not_to_invent(tmp_path):
    got = _run(tmp_path, f"""
      const J = await import('{(JS / "core/journal.js").as_posix()}');
      print(JSON.stringify(J.forMilo([{{ ticker: 'X', pnl: 5, plan: {{ thesis: 't' }}, reflection: '' }}])));
    """)
    assert "Do not invent trades, prices, motives or explanations" in got["rule"]
    assert got["trades"][0]["plan"] == {"thesis": "t"} and got["trades"][0]["reflection"] is None


def test_a_pick_reaches_the_ticket_without_retyping(tmp_path):
    got = _run(tmp_path, f"""
      const K = await import('{(JS / "pages/options-picker.js").as_posix()}');
      const P = await import('{(JS / "pages/paper.js").as_posix()}');
      const c = {{ type: 'call', expiry: '2026-12-18', strike: 350, ask: 13.2, scenarios: {{ before_expiry: [{{ label: 'Stock moves against you', value: 128 }}] }} }};
      const d = {{ plan: {{ thesis: 'bull', hold_days: 30, target: 370, through_event: true }}, event_in_hold: true, earnings: '2026-11-02' }};
      const draft = K.draftFrom(d, c, 'AAPL');
      print(JSON.stringify({{ draft, ticket: P.ticketFromDraft(draft) }}));
    """)
    d, t = got["draft"], got["ticket"]
    assert d["stop"] == 1.28, "a premium stop: the model's value if the stock reaches the adverse case, per share"
    assert t["ticker"] == "AAPL" and t["instrument"] == "option" and t["optionType"] == "call" and t["strike"] == "350"
    assert t["entry"] == "13.2" and t["hold_days"] == "30" and t["catalyst_date"] == "2026-11-02" and t["hold_through"] is True
    assert t["source"] == "the contract picker" and "Expect a rise in AAPL toward 370 within 30 days." == t["thesis"]


def test_the_desk_attaches_the_plan_and_keeps_the_journal_private():
    assert "plan: planOf(t, entry, qty, isOpt ? 100 : 1)" in PAPER
    assert "localStorage.removeItem(DRAFT_KEY)" in PAPER, "a draft is read once"
    assert "nothing here reaches Optic Portfolio, whose shared record is separate" in PAPER
    dev = (JS / "core/device.js").read_text()
    assert "'optic.v2.paper.draft.v1'" in dev and "'optic.paper.v1'" in dev
