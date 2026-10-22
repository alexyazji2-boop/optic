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


# ---------------------------------------------------------------- 7. an option is not one share

from app.analytics import portfolio_risk as prisk
_TODAY = _dt.date(2026, 10, 22)


class _RiskProvider:
    def batch_history(self, symbols, period="6mo", interval="1d"):
        idx = _pd.bdate_range(end="2026-10-21", periods=130)
        out = {}
        for i, s in enumerate(symbols):
            rng = _np.random.default_rng(10 + i)
            out[s] = _pd.DataFrame({"Close": 100 * _np.cumprod(1 + rng.normal(0, 0.01, 130))}, index=idx)
            out[s].iloc[-1, 0] = 100.0
        return out

    def profile(self, sym):
        return {"sector": "Technology"}


def _opt(sym="AAA", typ="call", direction="long", qty=2, strike=100.0, mark=4.0, **kw):
    return {"ticker": sym, "instrument": "option", "direction": direction, "option_type": typ, "strike": strike,
            "expiry": "2026-12-18", "qty": qty, "entry_price": mark, "mark_price": mark, "entry_spot": 100.0, **kw}


def test_an_at_the_money_call_weighs_about_half_its_hundred_shares():
    ex = prisk.option_exposure(_opt(), 100.0, _TODAY)
    assert ex["multiplier"] == 100 and ex["multiplier_basis"] == "standard contract assumed"
    assert 0.5 < ex["delta"] < 0.6
    assert ex["notional"] == 20000.0 and ex["premium_at_risk"] == 800.0
    assert abs(ex["delta_exposure"] - ex["delta"] * 100 * 2 * 100) < 1


def test_puts_and_shorts_carry_their_sign_and_shorts_no_premium_cap():
    lp = prisk.option_exposure(_opt(typ="put"), 100.0, _TODAY)
    sc = prisk.option_exposure(_opt(direction="short"), 100.0, _TODAY)
    assert lp["delta"] < 0 and lp["delta_exposure"] < 0
    assert sc["delta_exposure"] < 0 and sc["premium_at_risk"] is None


def test_an_adjusted_contract_uses_its_own_multiplier_and_a_given_delta():
    ex = prisk.option_exposure(_opt(multiplier=150, delta=0.4), 100.0, _TODAY)
    assert ex["multiplier_basis"] == "position" and ex["delta_basis"] == "position"
    assert ex["delta_exposure"] == 0.4 * 100 * 2 * 150


def test_missing_greeks_are_reported_not_guessed():
    expired = prisk.option_exposure(_opt(expiry="2026-10-01"), 100.0, _TODAY)
    unsolvable = prisk.option_exposure(_opt(mark=0.0, entry_price=0.0), 100.0, _TODAY)
    assert expired["delta_exposure"] is None and expired["uncovered_reason"] == "at or past expiry"
    assert unsolvable["delta_exposure"] is None


def test_shares_and_options_reconcile_in_one_unit():
    shares = {"ticker": "BBB", "instrument": "shares", "direction": "long", "qty": 100, "entry_price": 100.0}
    book = prisk.build(_RiskProvider(), [shares, _opt(), _opt(sym="CCC", expiry="2026-10-01")], today=_TODAY)
    aaa = next(p for p in book["positions"] if p["symbol"] == "AAA")
    bbb = next(p for p in book["positions"] if p["symbol"] == "BBB")
    assert abs(bbb["signed_value"] - 10000.0) < 1
    ex = next(o for o in book["options"] if o["symbol"] == "AAA")
    assert abs(aaa["signed_value"] - ex["delta_exposure"]) < 1 and aaa["signed_value"] > 5000, "two contracts, not two shares"
    assert book["options_uncovered"] == 1 and "left out" in book["option_note"] and "CCC" not in [p["symbol"] for p in book["positions"]]
    assert "understated" not in (JS / "pages/tracker.js").read_text()


# ---------------------------------------------------------------- 8. setups say where they stand; the ledger says what it waits for

from app.analytics import entry as entry_mod


@pytest.mark.parametrize("close,want", [(110.0, "armed"), (101.0, "triggered"), (95.0, "invalidated")])
def test_a_long_pullback_setup_is_armed_triggered_or_invalidated(close, want):
    out = entry_mod.setup_state({"style": "Pullback setup", "zone": [100.0, 102.0]}, close, True)
    assert out["state"] == want
    if want == "triggered":
        assert "confirmation is not checked" in out["state_detail"]


def test_a_breakout_needs_the_close_and_the_volume():
    e = {"style": "Breakout setup", "zone": [120.0, 121.0]}
    assert entry_mod.setup_state(e, 119.0, True)["state"] == "armed"
    assert entry_mod.setup_state(e, 122.0, True, volume=2e6, avg_volume=1e6)["state"] == "triggered"
    light = entry_mod.setup_state(e, 122.0, True, volume=5e5, avg_volume=1e6)
    assert light["state"] == "armed" and "lighter volume" in light["state_detail"]
    short = entry_mod.setup_state({"style": "Pullback setup", "zone": [100.0, 102.0]}, 104.0, False)
    assert short["state"] == "invalidated"


def test_the_plan_and_the_tracker_say_the_ledger_does_not_wait_for_triggers():
    from tests.test_catalyst_verdict import _plan
    plan = _plan([])
    assert "do not wait for these setups" in plan["ledger_note"]
    assert all("state" in e for e in plan["entry_options"])
    tr = (JS / "pages/tracker.js").read_text()
    assert "['Does not wait for', \"the Options tab's pullback or breakout triggers" in tr
    v = open("app/analytics/swing.py").read()
    assert "four independent reads" not in v and "agreement is one source, not two" in v


# ---------------------------------------------------------------- 9 / 22. how the simulated ledger fills

from app import paper as paper_mod


def _share_pos(**kw):
    p = {"instrument": "shares", "direction": "long", "stop": 95.0, "target": 110.0,
         "entry_at": "2026-10-20T15:00:00+00:00", "entry_price": 100.0}
    p.update(kw)
    return p


def test_a_day_touching_both_levels_counts_the_stop():
    assert paper_mod._exit_check(_share_pos(), 100.0, 100.0, bar_high=111.0, bar_low=94.0) == "Stop hit"
    short = _share_pos(direction="short", stop=105.0, target=90.0)
    assert paper_mod._exit_check(short, 100.0, 100.0, bar_high=106.0, bar_low=89.0) == "Stop hit"


def test_the_execution_note_is_beside_the_record():
    assert "the stop counts" in paper_mod.EXECUTION_NOTE and "No commission or slippage" in paper_mod.EXECUTION_NOTE
    src = open("app/paper.py").read()
    assert "fill = min(pos[\"stop\"], price) if long_pos else max(pos[\"stop\"], price)" in src, "a gap through a long's stop fills below it"
    assert "How fills are modelled." in (JS / "pages/tracker.js").read_text()


# ---------------------------------------------------------------- 14. headline tone, tense, pages and times

@pytest.mark.parametrize("title,sign", [
    ("Apple faces margin pressure as growth slows in China", -1),
    ("Company fails to beat estimates", 0),
    ("Shares sink after the miss", -1),
    ("Upbeat outlook for the beaten-down stock", 0),
])
def test_tone_reads_negation_whole_words_and_margin_pressure(title, sign):
    score, hits = news_mod._score_text(title)
    assert (score > 0) - (score < 0) == sign, (title, score, hits)


def test_a_future_headline_counts_half_and_says_so():
    past, _ = news_mod._score_text("Apple beat estimates")
    future, _ = news_mod._score_text("Apple could beat estimates")
    assert future == past * news_mod.FUTURE_WEIGHT


@pytest.mark.parametrize("title,url,landing", [
    ("Apple Inc. (AAPL) Stock Price, News, Quote & History", "https://finance.yahoo.com/quote/AAPL/", True),
    ("Stock Market News", "https://example.com/news/", True),
    ("Apple ships a minor iOS point release", "https://example.com/news/apple-ships-ios-1.html", False),
])
def test_site_index_pages_are_left_out(title, url, landing):
    assert news_mod.is_landing_page(title, url) is landing


def test_rows_say_what_their_time_and_tone_measure():
    class P:
        def news(self, t, limit=12):
            return [{"title": "Apple could beat estimates next week", "summary": "", "publisher": "Reuters",
                     "published": "2026-10-21T12:00:00Z", "url": "https://x.test/1"},
                    {"title": "Apple Inc. (AAPL) Stock Price, News, Quote & History", "publisher": "Yahoo",
                     "published": "2026-10-22T12:00:00Z", "url": "https://finance.yahoo.com/quote/AAPL/"}]
        def earnings_date(self, t): return None
        def quote(self, t): return {"name": "Apple Inc."}
    out = news_mod.analyse(P(), "AAPL")
    row = out["articles"][0]
    assert row["tense"] == "future" and row["tone_basis"] == "headline wording" and row["publisher"] == "Reuters"
    assert "publication time" in row["time_basis"] and out["fetched_at"] and out["dropped"]["landing"] == 1


# ---------------------------------------------------------------- 15. rendering and record identity

def test_the_portfolio_intro_link_is_markup_not_text():
    tr = (JS / "pages/tracker.js").read_text()
    assert "store.signedIn() ? html` Accounts you link are under <a class=\"textlink\" href=\"#/brokerage\">Brokerage</a>" in tr
    assert "store.signedIn() ? ' Accounts you link" not in tr


def test_two_books_closing_one_name_are_two_identified_alerts(monkeypatch):
    from app import alerts as alerts_mod
    raised = []
    monkeypatch.setattr(alerts_mod, "raise_alert", lambda kind, title, **kw: raised.append((title, kw)) or True)
    base = {"ticker": "NOW", "instrument": "shares", "direction": "long", "exit_reason": "Stop hit",
            "exit_price": 900.0, "entry_price": 950.0, "exit_at": "2026-10-21T15:00:00+00:00"}
    alerts_mod.from_scan({"closed_positions": [dict(base, id=11, book="balanced"), dict(base, id=12, book="aggressive")]})
    titles = [t for t, _ in raised]
    assert titles == ["NOW long shares closed in the Balanced book: Stop hit", "NOW long shares closed in the Aggressive book: Stop hit"]
    assert len({kw["dedupe_key"] for _, kw in raised}) == 2, "kept apart by trade id, not merged on matching text"
    assert "Trade #11, entered at 950.0." in raised[0][1]["body"]


# ---------------------------------------------------------------- 17. Milo: page context apart from what the answer concerns

def test_an_nvda_answer_asked_from_aapl_is_labelled_nvda(tmp_path):
    got = _run(tmp_path, f"""
      const M = await import('{(JS / "ui/milo.js").as_posix()}');
      const D = await import('{(JS / "core/dom.js").as_posix()}');
      const ctx = {{ focus: {{ ticker: 'AAPL', view_label: 'AAPL Dossier, Investing' }} }};
      const strip = (h) => D.toString(h).replace(/<[^>]+>/g, '');
      print(JSON.stringify({{
        nvda: strip(M.aboutLine({{ symbol: 'AAPL', context: ctx, retrieved: [{{ symbols: ['NVDA'], ok: true }}] }}, {{ symbol: 'AAPL' }})),
        both: strip(M.aboutLine({{ symbol: 'AAPL', context: ctx, loaded: [{{ symbols: ['NVDA'] }}], retrieved: [{{ symbols: ['AAPL'], ok: true }}] }}, {{ symbol: 'AAPL' }})),
        plain: strip(M.aboutLine({{ symbol: 'AAPL', context: ctx }}, {{ symbol: 'AAPL' }})),
        failed: strip(M.aboutLine({{ symbol: 'AAPL', context: ctx, retrieved: [{{ symbols: ['XYZQ'], ok: false }}] }}, {{ symbol: 'AAPL' }})),
      }}));
    """)
    assert got["nvda"] == "About NVDA; AAPL Dossier, Investing attached as context. Not about AAPL, the page now open."
    assert got["both"].startswith("About NVDA and AAPL; asked from AAPL Dossier, Investing")
    assert got["plain"].startswith("About AAPL; asked from AAPL Dossier, Investing")
    assert got["failed"].startswith("About AAPL"), "a lookup that failed is not what the answer concerns"


def test_the_done_event_carries_what_was_loaded():
    from app import ai
    rows = ai.auto_loaded_sources({"auto_loaded": {"nvda": {"quote": {"source": "Yahoo Finance quote (delayed)", "as_of_utc": "2026-10-22T15:00:00Z"}}}})
    assert rows == [{"symbols": ["NVDA"], "label": "NVDA quote, chart and options summary", "data_type": "quote, chart and options summary",
                     "source": "Yahoo Finance quote (delayed)", "as_of": "2026-10-22T15:00:00Z", "ok": True}]
    assert ai.auto_loaded_sources({}) == [] and ai.auto_loaded_sources(None) == []


# ---------------------------------------------------------------- 20. the health hint agrees with enabled

def test_an_enabled_assistant_is_not_described_as_unconfigured(monkeypatch):
    from app import ai
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-not-a-real-key")
    monkeypatch.setattr(ai, "_client", lambda: object())
    on = ai.available()
    assert on["enabled"] is True and "not configured" not in on["hint"]
    monkeypatch.setattr(ai, "_client", lambda: None)
    off = ai.available()
    assert off["enabled"] is False and ("not configured" in off["hint"] or "ANTHROPIC_API_KEY" in off["hint"])


# ---------------------------------------------------------------- 22. response headers

def test_every_answer_carries_the_protections_and_hsts_only_over_https():
    from fastapi.testclient import TestClient
    import app.main as m
    c = TestClient(m.app)
    for path in ("/", "/api/health", "/v2/"):
        r = c.get(path)
        assert r.headers["x-content-type-options"] == "nosniff", path
        assert r.headers["x-frame-options"] == "DENY" and "frame-ancestors 'none'" in r.headers["content-security-policy"]
        assert "cdn.jsdelivr.net" in r.headers["content-security-policy-report-only"]
        assert "strict-transport-security" not in r.headers
    assert c.get("/api/health", headers={"x-forwarded-proto": "https"}).headers["strict-transport-security"] == "max-age=15552000"
