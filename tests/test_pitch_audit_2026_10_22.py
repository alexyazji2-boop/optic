"""The pitch-readiness audit of 2026-10-22 (~/Optic/work/pitch-audit-2026-10-22/AUDIT.md): each finding that
was reproduced, held to its correction. Front-end functions run in JavaScriptCore; the server's in Python.
"""
from tests.test_frontend_v2_stage0 import V2, _run

JS = V2 / "js"
OV = (JS / "pages/dossier.js").read_text()


# ---------------------------------------------------------------- 1. the valuation answer and its question

def test_every_valuation_state_is_described_not_answered_yes_or_no(tmp_path):
    got = _run(tmp_path, f"""
      const O = await import('{(JS / "pages/dossier.js").as_posix()}');
      const st = (n) => ({{ stars: {{ available: true, stars: n }}, fair_value: {{ available: true }} }});
      print(JSON.stringify({{
        q: O.PRICE_Q,
        s: [1, 2, 3, 4, 5].map((n) => O.priceAnswer(st(n))),
        wide: O.priceAnswer({{ stars: {{ available: false }}, fair_value: {{ available: true, wide: true }} }}),
        none: O.priceAnswer({{ stars: {{ available: false }}, fair_value: {{ available: false }} }}),
        failed: O.priceAnswer({{}}, new Error('x')),
        loading: O.priceAnswer(undefined),
      }}));
    """)
    assert got["q"] == "How is it priced against its own history?"
    assert got["s"] == ["Above its usual valuation range.", "Inside its usual range, in the upper half.",
                        "Near the middle of its usual range.", "Inside its usual range, in the lower half.",
                        "Below its usual valuation range."]
    for a in got["s"]:
        assert not a.lower().startswith(("yes", "no", "not especially")), a
    assert got["wide"] == "Its usual range is too wide to place the price in."
    assert got["none"] == "No valuation range for this company."
    assert got["failed"] == "Not available right now." and got["loading"] is None
    assert "q: 'Is the share price expensive?'" not in OV and "q: PRICE_Q, a: priceA" in OV


def test_quality_answers_describe_the_grade():
    assert "Yes, high quality." not in OV and "Yes, good quality." not in OV
    assert "A: \"Strong on Optic's quality measures.\"" in OV


def test_four_stars_is_not_called_below_the_range(tmp_path):
    got = _run(tmp_path, f"""
      const O = await import('{(JS / "pages/dossier.js").as_posix()}');
      print(JSON.stringify({{ four: O.synthesis(null, null, {{ available: true, stars: 4 }}, '', ''),
                              five: O.synthesis(null, null, {{ available: true, stars: 5 }}, '', ''),
                              two: O.synthesis(null, null, {{ available: true, stars: 2 }}, '', '') }}));
    """)
    assert got["four"] == "The price is in the lower half of its fair value range."
    assert got["five"] == "The price is below its fair value range."
    assert got["two"] == "The price is in the upper half of its fair value range."


def test_fund_drawers_carry_the_fund_questions():
    wire = OV[OV.index("function wire(main, sym) {"):]
    assert "if (isFundHere(sym)) Object.assign(titles, { quality: 'What is it?', price: 'What do its holdings cost?', next: 'What does it pay?' });" in wire


# ---------------------------------------------------------------- 11. the chart and the one-year answer share a start

def test_the_one_year_chart_starts_on_the_close_the_answer_measures_from(tmp_path):
    got = _run(tmp_path, f"""
      const O = await import('{(JS / "pages/dossier.js").as_posix()}');
      const pts = Array.from({{ length: 400 }}, (_, i) => ({{ d: `d${{i}}`, c: 100 + i }}));
      const w = O.windowOf(pts, '1Y'), t = O.trendFinding(pts, null);
      print(JSON.stringify({{ first: w[0].d, from: t.from.d, last: w[w.length - 1].d, to: t.to.d, n: w.length }}));
    """)
    assert got["first"] == got["from"] and got["last"] == got["to"] and got["n"] == 253
    assert "Daily closes from ${fullDate(first.d)} through ${fullDate(last.d)}." in OV


# ---------------------------------------------------------------- 2. catalyst timing: one event, one state

import datetime as _dt
import pytest
from app import news as news_mod

TODAY = "2026-10-22"


def _row(title, age=20.0, publisher="Reuters", published="2026-10-21T16:00:00Z", about=True):
    tags = news_mod._catalysts(title)
    return {"title": title, "summary": "", "age_hours": age, "about_company": about,
            "tier": news_mod.tier_for(age, tags)["tier"], "tone": "neutral", "sentiment_score": 0.0,
            "catalysts": tags, "publisher": publisher, "published": published, "url": "https://x.test/a"}


def _news(rows, nxt=None, last=None):
    return {"articles": rows, "today": TODAY, "earnings_date": nxt, "last_report_date": last,
            "days_to_earnings": None if not nxt else (_dt.date.fromisoformat(nxt) - _dt.date.fromisoformat(TODAY)).days}


def test_a_future_earnings_preview_is_never_a_resolved_report():
    # the audit's AAPL case: a report eleven days out, the last one in July, an earnings headline this week
    n = _news([_row("Apple earnings: iPhone demand in focus for Q4"), _row("Apple Q4 earnings preview: what to expect")],
              nxt="2026-11-02", last="2026-07-30")
    m = news_mod.material_catalyst(n)
    assert m["material"] is False
    assert {x["state"] for x in m["set_aside"]} == {"upcoming"}
    p = news_mod.pending_catalyst(n)
    assert p["pending"] is True and p["events"][0]["kind"] == "earnings" and p["events"][0]["event_date"] == "2026-11-02"


def test_a_completed_report_is_resolved_with_its_date_and_evidence():
    n = _news([_row("Apple beats Q4 earnings estimates as services climb", age=10.0)], nxt="2027-01-29", last="2026-10-21")
    m = news_mod.material_catalyst(n)
    assert m["material"] is True
    ev = m["events"][0]
    assert ev["kind"] == "earnings" and ev["event_date"] == "2026-10-21" and ev["date_basis"] == "the earnings calendar"
    assert ev["headline"].startswith("Apple beats") and ev["publisher"] == "Reuters"
    # the preview written before that report is about the report that is out, not a pending one
    old = _news([_row("Apple Q4 earnings preview: what to expect", age=24 * 5)], nxt="2027-01-29", last="2026-10-21")
    assert news_mod.pending_catalyst(old)["pending"] is False


def test_the_calendar_still_showing_a_report_just_passed_counts_as_that_report():
    n = _news([_row("Apple reports Q4 results", age=6.0)], nxt="2026-10-21", last="2026-07-30")
    assert news_mod.material_catalyst(n)["events"][0]["event_date"] == "2026-10-21"


def test_an_earnings_headline_with_no_report_dates_is_ambiguous_not_resolved():
    m = news_mod.material_catalyst(_news([_row("Apple earnings in focus")]))
    assert m["material"] is False and m["set_aside"][0]["state"] == "ambiguous"


def test_two_different_catalysts_stay_two_events():
    n = _news([_row("FDA approves the company's therapy", age=5.0),
               _row("Company hit with antitrust lawsuit", age=30.0, publisher="AP")],
              nxt="2026-11-02", last="2026-07-30")
    m = news_mod.material_catalyst(n)
    kinds = sorted(e["kind"] for e in m["events"])
    assert kinds == ["legal / regulatory", "regulatory / clinical"]
    assert all(e["date_basis"] == "headline publication time" for e in m["events"])


def _plan(news):
    from tests.test_catalyst_verdict import _chain, _frame
    from app.analytics import entry as entry_mod, technicals as tech_mod
    frame = _frame()
    return entry_mod.build_plan(_chain(), 15.0, {"stance": "bullish", "conviction": "moderate"},
                                tech_mod.analyse(frame), {}, news, rate=0.04, div=0.0, history=frame)


def test_the_entry_plan_never_calls_an_upcoming_report_resolved():
    n = _news([_row("Apple Q4 earnings preview: what to expect")], nxt="2026-11-01", last="2026-07-30")
    n["days_to_earnings"] = 10
    plan = _plan(n)
    joined = " ".join(plan["warnings"])
    assert "Earnings on 2026-11-01 (in 10 days), from the earnings calendar." in joined
    assert "resolved" not in joined and "report of" not in joined and "rich after the event" not in joined
    assert "still ahead" not in joined, "the preview is the dated report already warned about"
    assert plan["catalyst_events"]["resolved"] == []


def test_the_entry_plan_names_a_resolved_report_and_its_headline():
    n = _news([_row("Apple beats Q4 earnings estimates", age=10.0)], nxt="2027-01-29", last="2026-10-21")
    joined = " ".join(_plan(n)["warnings"])
    assert "The earnings report of 2026-10-21 is out: “Apple beats Q4 earnings estimates” (Reuters, published 2026-10-21)." in joined


# ---------------------------------------------------------------- 3. the expected-move ratio is reproducible

def test_the_ratio_is_the_displayed_figures_divided():
    from tests.test_expected_move import _move, _spx
    for vix, spread in ((18.7, 0.0096), (12.3, 0.004), (31.0, 0.02)):
        em = _move(vix, frame=_spx(spread=spread))
        shown = round(em["implied_pct"], 2) / round(em["realized_pct"], 2)
        assert abs(em["ratio"] - shown) <= 0.0051, (vix, em)   # the ratio itself is shown to two places
        assert "daily-equivalent approximation" in em["implied_basis"] and "30-day" in em["implied_basis"]


def test_every_surface_shows_the_atr_converted_beside_the_ratio():
    ws = (JS / "pages/workspace.js").read_text()
    body = ws[ws.index("  expected: {"):ws.index("milo: 'Is the market\\'s one-day expected move")]
    assert "<dt>Typical day lately</dt><dd>±${num(em.realized_pct)}%" in body and "14-day ATR ${num(em.atr_pct)}% ÷ 1.6" in body
    assert "<dt>Recently delivered</dt><dd>${num(em.atr_pct)}%" not in body
    mac = (JS / "pages/macro.js").read_text()
    assert "html`${num(em.atr_pct, 2)}% a day" not in mac and "['Its typical day lately', html`±${num(em.realized_pct, 2)}%" in mac
    home = (JS / "pages/home.js").read_text()
    assert "30-day implied volatility as one day's move, an approximation" in home
