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


# ---------------------------------------------------------------- 4. the flow proxy claims no buyers or openings

def test_no_flow_label_claims_a_side_an_opening_or_a_motive():
    import pandas as pd
    from app.analytics import flow as flow_mod
    rows = []
    for strike, is_call, vol, oi in ((100, True, 900, 100), (105, True, 800, 50), (95, False, 50, 900), (90, False, 40, 800)):
        rows.append({"strike": float(strike), "is_call": is_call, "volume": float(vol), "open_interest": float(oi),
                     "last": 2.0, "bid": 1.9, "ask": 2.1, "mid": 2.0, "iv": 0.4 if is_call else 0.3,
                     "expiry": "2026-11-20", "dte": 29, "contract": "X"})
    out = flow_mod.analyse(pd.DataFrame(rows), 100.0)
    text = " ".join(out["notes"]).lower() + " " + out["new_positions"]["definition"].lower()
    for banned in ("new positions", "bought", "speculation", "protection", "fear bid", "chase bid", "institutional", "sweep"):
        assert banned not in text.replace("who bought", "").replace("bought or sold", ""), banned
    panels = (JS / "pages/options-panels.js").read_text()
    for banned in ("Time value bought in calls", "New positions, calls share", "', new'", "Net premium by strike"):
        assert banned not in panels, banned
    tools = open("app/milo_tools.py").read()
    assert "never call it new or opening" in tools


# ---------------------------------------------------------------- 5-6. Retirement: final weights, total return

import numpy as _np
import pandas as _pd
from app.analytics import retirement as ret


class _RothProvider:
    """Ten years of daily bars for the fund universe: price drifts, plus a cash
    distribution each quarter that only the adjusted close carries back in."""
    def __init__(self, young=("AVUV",), price_only=()):
        self.young, self.price_only = set(young), set(price_only)

    def batch_history(self, symbols, period="10y", interval="1d"):
        out = {}
        for i, sym in enumerate(symbols):
            n = 1600 if sym in self.young else 2520
            idx = _pd.bdate_range(end="2026-10-21", periods=n)
            rng = _np.random.default_rng(i + 1)
            price = 100 * _np.cumprod(1 + rng.normal(0.0002, 0.01, n))
            adj = price * _np.cumprod(_np.where(_np.arange(n) % 63 == 62, 1.008, 1.0))
            frame = _pd.DataFrame({"Close": price, "Adj Close": adj, "Open": price, "High": price, "Low": price, "Volume": 1.0}, index=idx)
            out[sym] = frame.drop(columns=["Adj Close"]) if sym in self.price_only else frame
        return out

    def fund_meta(self, sym):
        return {"expense_ratio_pct": 0.05, "yield_pct": 2.0}


@pytest.mark.parametrize("risk", ["conservative", "balanced", "growth"])
@pytest.mark.parametrize("years", [1, 5, 15, 30, 45])
def test_the_headline_split_is_the_table_summed(risk, years, monkeypatch):
    monkeypatch.setattr(ret, "_stock_sleeve", lambda *a, **k: {"available": False, "rows": []})
    d = ret.analyse(_RothProvider(), years=years, risk=risk)
    a, rows = d["allocation"], d["rows"]
    by = lambda roles: sum(r["weight_pct"] for r in rows if r["role"] in roles)
    assert abs(a["bond_pct"] - by({"bonds"})) < 0.15
    assert abs(a["gold_pct"] - by({"gold"})) < 0.15
    assert abs(a["equity_pct"] - (by(set(ret.EQUITY_ROLES)) + by({"reit"}))) < 0.15
    assert abs(a["equity_pct"] + a["bond_pct"] + a["gold_pct"] - 100) < 0.3


def test_the_default_model_no_longer_reads_90_and_11():
    a = ret._model_allocation(30, "balanced")
    assert a["glidepath_equity_pct"] == 89.5
    assert a["bond_pct"] == 6.5 and a["reit_pct"] == 4.0 and abs(a["equity_pct"] - 93.5) <= 0.15   # rounded weights summed


def test_a_stock_sleeve_is_inside_the_split(monkeypatch):
    monkeypatch.setattr(ret, "_stock_sleeve", lambda *a, **k: {"available": True, "rows": [{"suggested_pct": 6.0}]})
    d = ret.analyse(_RothProvider(), years=30, risk="growth", stock_candidates="AAPL")
    a, rows = d["allocation"], d["rows"]
    assert a["stock_sleeve_pct"] == 6.0
    assert abs(a["equity_pct"] - (sum(r["weight_pct"] for r in rows if r["role"] in ret.EQUITY_ROLES or r["role"] == "reit") + 6.0)) < 0.15
    assert "The stock sleeve is grown at the same rate" in d["projection"]["rate_basis"]


def test_returns_include_reinvested_distributions():
    f = _RothProvider().batch_history(["BND"])["BND"]
    st = ret._fund_stats(f)
    yrs = (len(f)) / ret.TRADING_DAYS
    want = ((f["Adj Close"].iloc[-1] / f["Adj Close"].iloc[0]) ** (1 / yrs) - 1) * 100
    assert st["return_basis"] == "total" and abs(st["cagr_full_pct"] - want) < 0.01
    price_only = ret._fund_stats(f.drop(columns=["Adj Close"]))
    assert price_only["return_basis"] == "price" and price_only["cagr_full_pct"] < st["cagr_full_pct"] - 2.5


def test_the_projection_rate_is_one_window_not_a_blend_of_spans(monkeypatch):
    monkeypatch.setattr(ret, "_stock_sleeve", lambda *a, **k: {"available": False, "rows": []})
    d = ret.analyse(_RothProvider(young=("AVUV",)), years=30, risk="balanced")
    bl, pr = d["blended"], d["projection"]
    assert bl["window"]["years"] < 6.5, "the youngest fund (1,600 sessions) sets the shared window"
    assert pr["rate_pct"] == bl["cagr_long_pct"] and "hypothetical" in pr["rate_basis"]
    assert "not a probability range" in pr["band_note"] and "Nominal dollars" in pr["inflation_note"]
    assert pr["contribution_timing"].startswith("Each year's contribution goes in at the start")
    assert "upper bound" not in bl["caveat"].lower()
    mixed = ret.analyse(_RothProvider(price_only=("BND",)), years=30, risk="balanced")["blended"]
    assert mixed["return_basis"] == "mixed"


def test_roth_language_is_qualified():
    notes = " ".join(n["body"] for n in ret._roth_notes({"bond_pct": 20}, "balanced", 30))
    assert "never taxed" not in notes and "five years" in notes and "59½" in notes
    assert "belongs in the Roth" not in notes
