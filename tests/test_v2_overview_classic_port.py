"""Classic's Overview in v2 (owner's screenshots of INTC, 2026-10-25), and the refined Optic Score.

The owner asked for Classic's header (logo, Weinstein stage with Explain, "Show advanced analysis"), its four questions,
"The past year" with E, D and S marks, key figures with their definitions, the bull case and the bear case with
Evidence links, "What should I look at next?" and Optic's read, from the same endpoints and in Classic's words; and then
for the Optic Score to say what it measures without overclaiming. The owner chose to replace v2's own four answers and
long-term views with Classic's, rather than show both.

v2's functions run in JavaScriptCore; Classic's score helpers are lifted out of static/app.js and run the same fixtures,
so the two apps read the same payload the same way. The pages were checked in a browser at 1440, 390 and 375 by 549.
"""
import json
import os
import re
import shutil
import subprocess

import pytest
from fastapi.testclient import TestClient

import app.main as m
from tests.test_frontend_v2_stage0 import V2, _run

ROOT = V2.parent.parent

JS = V2 / "js"
OVR = (JS / "pages/overview-research.js").read_text()
DOS = (JS / "pages/dossier.js").read_text()
FRAME = (JS / "pages/dossier-frame.js").read_text()
APP = (ROOT / "static/app.js").read_text()
CSS = (V2 / "css/pages.css").read_text()
NOW = "Date.parse('2026-10-25T16:00:00Z')"

# ---------------------------------------------------------------- fixtures: one ticker payload per case

FACTORS = [("technicals", "Momentum", 38), ("gamma", "Options", 27), ("flow", "Positioning", 22), ("news", "News", 13)]


def ticker(composite, stance, scores, *, missing=(), pending=False, age_h=0):
    weights = {k: w for k, _, w in FACTORS}
    live = [k for k, _, _ in FACTORS if k not in missing]
    total = sum(weights[k] for k in live)
    factors = [{"key": k, "label": lab, "score": None if k in missing else scores[k],
                "weight_pct": 0.0 if k in missing else round(weights[k] / total * 100),
                "unavailable": k in missing, "why_unavailable": "the option chain did not load" if k in missing else None}
               for k, lab, _ in FACTORS]
    return {"generated_at": f"2026-10-25T{16 - age_h:02d}:00:00Z" if age_h else "2026-10-25T15:50:00Z",
            "verdict": {"composite_score": composite, "stance": stance, "pending_catalyst": {"pending": pending},
                        "breakdown": [{"component": k, "nominal_weight_pct": w} for k, _, w in FACTORS]},
            "pulse": {"factors": factors},
            "why": {"reasons": [{"factor": "technicals", "headline": "Chart structure is constructive"}]}}


def holding(score, conviction, factors, *, reliable=True, years=12.0, excess=4.2, sharpe=0.6, fwd=31.0, above200=True):
    return {"generated_at": "2026-10-25T15:00:00Z", "holding": {
        "conviction_score": score, "conviction": conviction, "plan": "The long-term trend model reads positive, not strongly.",
        "conviction_scale": {"min_possible": -78, "max_possible": 97, "thresholds": {"high": 40, "moderate": 12, "cautious": -12, "low": -40}},
        "conviction_factors": [{"label": lab, "points": pts, "detail": det, "kind": "trend"} for lab, pts, det in factors],
        "data_quality": {"reliable": reliable, "history_years": years}, "excess_cagr_5y_pct": excess,
        "risk": {"sharpe_proxy": sharpe}, "valuation": {"forward_pe": fwd},
        "long_trend": {"above_200w_sma": above200, "phase": "uptrend, correcting"}}}


CASES = {
    "bullish": ticker(36.7, "bullish", {"technicals": 60, "gamma": 40, "flow": 20, "news": -10}),
    "slight": ticker(12, "leaning bullish", {"technicals": 30, "gamma": 5, "flow": 0, "news": 0}),
    "neutral": ticker(4, "neutral", {"technicals": 10, "gamma": 0, "flow": 0, "news": 2}),
    "bearish": ticker(-55, "bearish", {"technicals": -80, "gamma": -40, "flow": -30, "news": -20}),
    "missing": ticker(-7.5, "neutral", {"technicals": -10, "news": 0}, missing=("gamma", "flow"), pending=True),
    "stale": ticker(20, "leaning bullish", {"technicals": 40, "gamma": 10, "flow": 0, "news": 0}, age_h=3),
}
LONG = {
    "positive": holding(37, "moderate", [("200-week trend", 25, "Above the 200-week average. Secular trend is up."),
                                         ("40-week trend", 12, "Above the 40-week average. Intermediate trend supportive."),
                                         ("Valuation", 0, "Forward P/E of 31.0 is between the 20 and 45 thresholds. No adjustment either way.")], excess=None),
    "neutral43": holding(-10.9, "neutral", [("200-week trend", -25, "Below."), ("40-week trend", 12, "Above."), ("Dividend", 2.1, "Yield.")]),
    "short": holding(25, "moderate", [("200-week trend", 25, "Above."), ("40-week trend", 12, "Above."), ("Valuation", 8, "Low.")], reliable=False, years=2.1),
    "mixed": holding(37, "moderate", [("200-week trend", 25, "Above."), ("Return per unit of risk", 10, "Well compensated."),
                                      ("Drawdown opportunity", 10, "Far below the high."), ("40-week trend", -8, "Below the 40-week average.")]),
    "negative": holding(-45, "low", [("200-week trend", -25, "Below."), ("5-year vs SPY", -15, "Under."), ("Return per unit of risk", -10, "Poor.")]),
}


def v2_reads(tmp_path):
    return _run(tmp_path, f"""
      const R = await import('{(JS / "pages/overview-research.js").as_posix()}');
      const T = {json.dumps(CASES)}, L = {json.dumps(LONG)}, now = {NOW};
      const s = {{}}, l = {{}};
      for (const k of Object.keys(T)) s[k] = R.shortScore(T[k], now);
      for (const k of Object.keys(L)) l[k] = R.longScore(L[k], now);
      print(JSON.stringify({{ s, l, gone: R.longScore({{ error: 'no history' }}, now), wait: R.longScore(null, now),
        clash: R.scoreNotes(s.bearish, l.positive, L.positive), agree: R.scoreNotes(s.bullish, l.positive, L.positive) }}));
    """)


JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc"


def _fn(name):
    at = APP.index("function %s(" % name)
    return APP[at:APP.index("\n}\n", at) + 3]


def classic_reads():
    exe = JSC if os.path.exists(JSC) else shutil.which("jsc")
    if not exe:
        pytest.skip("no JavaScriptCore on this machine")
    prelude = ("function fmt(v, d) { return Number(v).toLocaleString('en-US', { minimumFractionDigits: d, maximumFractionDigits: d }); }\n"
               "function cap(t) { const s = String(t || ''); return s ? s[0].toUpperCase() + s.slice(1) : s; }\n"
               + "\n".join(_fn(n) for n in ("score100", "agoWords", "oscPickDrivers", "oscShortRead", "oscLongRead")))
    script = f"""
      const T = {json.dumps(CASES)}, L = {json.dumps(LONG)}, now = {NOW};
      Date.now = () => now;
      const s = {{}}, l = {{}};
      for (const k of Object.keys(T)) s[k] = oscShortRead(T[k], now);
      for (const k of Object.keys(L)) l[k] = oscLongRead(L[k], now);
      print('RESULT:' + JSON.stringify({{ s, l }}));"""
    out = subprocess.run([exe, "-e", prelude + script], capture_output=True, text=True, timeout=60)
    assert "RESULT:" in out.stdout, (out.stdout + out.stderr)[-2000:]
    return json.loads(out.stdout.split("RESULT:", 1)[1].split("\n")[0])


# ---------------------------------------------------------------- the Optic Score: what it says, in both apps

def test_each_short_term_case_reads_its_band_not_a_confidence(tmp_path):
    s = v2_reads(tmp_path)["s"]
    assert (round(s["bullish"]["n"], 2), s["bullish"]["tone"], s["bullish"]["label"], s["bullish"]["line"]) == (68.35, "pos", "Bullish", "The inputs lean bullish.")
    assert s["slight"]["line"] == "The inputs lean bullish, but only slightly." and s["slight"]["tone"] == "pos"
    assert (s["neutral"]["n"], s["neutral"]["tone"], s["neutral"]["line"]) == (52, "", "The inputs roughly cancel out: no lean either way.")
    assert (s["bearish"]["n"], s["bearish"]["tone"], s["bearish"]["line"]) == (22.5, "neg", "The inputs lean strongly bearish.")
    for k, r in s.items():
        assert "conviction" not in json.dumps(r).lower(), (k, "conviction is a band of the score's size, so it is not named")


def test_drivers_are_the_inputs_that_moved_the_score_most_with_their_share_of_it(tmp_path):
    d = v2_reads(tmp_path)["s"]["bullish"]["drivers"]
    assert [x["label"] for x in d] == ["Momentum", "Options", "Positioning"], "three at most, by their pull on the score"
    assert [round(x["pts"], 2) for x in d] == [11.4, 5.4, 2.2], "score x weight / 200: each input's share of the distance from 50"
    assert d[0]["detail"] == "Reads +60 with 38% of the weight. Chart structure is constructive."
    b = v2_reads(tmp_path)["s"]["bearish"]["drivers"]
    assert all(x["pts"] < 0 for x in b), "a negative driver is shown as one"


def test_missing_and_stale_inputs_are_said_never_scored_as_neutral(tmp_path):
    s = v2_reads(tmp_path)["s"]
    notes = s["missing"]["notes"]
    assert notes[0] == ("Options and Positioning had no data on this run (the option chain did not load; the option chain did not load), "
                        "so their weight went to the other inputs. They are left out, not counted as neutral.")
    assert "A scheduled event is still ahead, and nothing here predicts which way it resolves." in notes
    assert [r["missing"] for r in s["missing"]["rows"]] == [False, True, True, False]
    assert s["stale"]["notes"] == ["Worked out 3 hours ago; the inputs may have moved since."]
    assert s["bullish"]["notes"] == [], "a fresh, complete reading carries no qualification"


def test_the_long_term_score_reads_the_models_own_bands_and_says_what_it_lacks(tmp_path):
    got = v2_reads(tmp_path)
    p = got["l"]["positive"]
    assert (round(p["n"]), p["tone"], p["label"], p["phase"]) == (69, "pos", "Positive", "Uptrend, correcting")
    assert [x["label"] for x in p["drivers"]] == ["200-week trend", "40-week trend"], "a zero factor is not a driver"
    assert round(p["drivers"][0]["pts"], 1) == 12.9, "25 model points on the positive side of 0 to 100 (50 / 97 each)"
    assert p["notes"] == ["Not scored for lack of data, so it adds nothing either way: the five-year return against the S&P 500. The score rests on the rest."]
    n43 = got["l"]["neutral43"]
    assert round(n43["n"]) == 43 and n43["tone"] == "", "the model calls 43 neutral, so it is not coloured as unfavourable (Classic coloured it red)"
    assert [round(x) for x in n43["band"]] == [42, 56], "the shaded neutral band is the model's own"
    short = got["l"]["short"]
    assert all(x["pts"] is None and x["model"] for x in short["drivers"]), "a capped total cannot be split onto 0 to 100, so model points are shown"
    assert "Only 2.1 years of usable price history, so the model holds the score between 34 and 63." in short["notes"]
    assert [x["label"] for x in got["l"]["mixed"]["drivers"]] == ["200-week trend", "Return per unit of risk", "40-week trend"], \
        "a material negative (-8 model points, about -4 on 0 to 100) takes the third place rather than a third positive"
    assert got["l"]["negative"]["label"] == "Strongly negative", "the model's 'low' band is its most negative, not a weak reading"
    assert got["gone"] == {"unavailable": "no history"} and got["wait"] == {"pending": True}


def test_conflicting_horizons_are_said_as_normal_and_not_compared_as_one_scale(tmp_path):
    got = v2_reads(tmp_path)
    assert got["clash"] == ["The two point different ways. That is common: the short-term reading weighs the last few weeks of trading, the long-term one up to five years of the price's path."]
    assert got["agree"] == []


def test_classic_reads_the_same_payloads_the_same_way(tmp_path):
    v2, cl = v2_reads(tmp_path), classic_reads()
    for k in CASES:
        a, b = v2["s"][k], cl["s"][k]
        assert (a["n"], a["tone"], a["label"], a["line"], a["notes"], [x["label"] for x in a["drivers"]]) == \
               (b["n"], b["tone"], b["label"], b["line"], b["notes"], [x["label"] for x in b["drivers"]]), k
    for k in LONG:
        a, b = v2["l"][k], cl["l"][k]
        assert (a["n"], a["tone"], a["label"], a["notes"], [x["label"] for x in a["drivers"]]) == (b["n"], b["tone"], b["label"], b["notes"], [x["label"] for x in b["drivers"]]), k


def test_the_section_says_what_the_scores_are_and_what_they_are_not():
    body = APP[APP.index("function ovScoreHTML(d) {"):APP.index("/* The long-term score for the Overview, once per symbol.")]
    for src in (OVR[OVR.index("export function scoreSection(c) {"):OVR.index("/* ---------------- Optic's read")], body):
        assert "no edge" not in src and "See how it is scored" not in src and "conviction" not in src.replace("conviction_", "")
        assert src.count("How this is calculated") == 2, "one disclosure per score"
        assert "50 is each model's neutral midpoint, where its inputs balance; it is not a measured break-even." in src
        assert "neither has been shown to predict returns" in src and "not directly comparable" in src
        assert "Short term: 2 to 8 weeks" in src and "Long term: several years" in src
        assert "The full breakdown, on Options" in src and "The full breakdown, on Investing" in src, "the deep links kept"
    assert ".osc-tile + .osc-tile { padding: var(--space-1) 0 var(--space-2) var(--space-5); border-left: 1px solid var(--border); }" in (ROOT / "static/styles.css").read_text(), "divided, not boxed"


# ---------------------------------------------------------------- Classic's sections, in Classic's words

QUOTE = {"price": 86.96, "market_cap": 459.68e9, "revenue_growth": 0.254, "profit_margin": -0.198, "fifty_two_high": 142.35, "fifty_two_low": 32.89, "trailing_pe": None}


def test_the_four_questions_grade_with_classics_words(tmp_path):
    fw = {"available": True, "method_version": "research-1.0", "policy": {"version": "policy-2026-10-14"},
          "long_term": {"available": True, "quality": {"status": "scored", "grade": "F", "components": []},
                        "conviction": {"label": "Not Investable", "why": "Business quality grades F."},
                        "valuation": {"status": "insufficient", "reason": "Fewer than two valuation measures could be scored."}},
          "swing": {"grade": "No Setup", "why": "The trend is up but price is neither at a level nor back at its averages: no defined entry.", "objections": []},
          "earnings": {"pre": {"available": True, "release": {"date": "2026-10-29", "timing": "unknown", "confirmed": True}, "view": {"headline": "Results lean in line."}}}}
    got = _run(tmp_path, f"""
      const R = await import('{(JS / "pages/overview-research.js").as_posix()}');
      const {{ toString: String }} = await import('{(JS / "core/dom.js").as_posix()}');
      const t = {{ quote: {json.dumps(QUOTE)}, company: {{ financials: {{ available: true, growth: {{ revenue_yoy_pct: 0.4, net_income_yoy_pct: null }}, margins: {{ net_pct: -0.9 }}, annual_periods: ['2025-12-31'] }} }} }};
      const c = R.context({{ sym: 'INTC', t, fw: {json.dumps(fw)}, lt: null, stars: null, fund: false, advanced: false, phase: 'closed', now: {NOW} }});
      const html = String(R.fourQuestions(c)), wait = String(R.fourQuestions({{ ...c, fw: undefined }})), off = String(R.fourQuestions({{ ...c, fw: {{ available: false, reason: 'No filings' }} }}));
      print(JSON.stringify({{ html, wait, off }}));
    """)
    h = got["html"]
    for want in ("Is it a strong business?", "Quality F", "Is the price attractive?", "Insufficient Data", "Is there a trade?", "No Setup",
                 "What about earnings?", "Reports Oct 29", "Quality and price together: Not Investable. Business quality grades F.",
                 "Revenue was roughly flat in the latest fiscal year, and the company is not yet profitable.", "It lost about 1 cents on each dollar of sales.",
                 "Show the figures", "Why", "none has been shown to predict returns"):
        assert want in h, want
    assert "after the close" not in h, "an upcoming report's session is not said (core/reports.js)"
    assert got["wait"].count("Grading…") == 4 and "The four grades are not available for this symbol: No filings." in got["off"]


def test_the_case_for_and_against_and_what_to_look_at_next(tmp_path):
    t = {"quote": QUOTE, "news": {"earnings_date": "2026-10-29", "days_to_earnings": 4, "article_count": 12},
         "company": {"financials": {"available": True, "growth": {"revenue_yoy_pct": 0.4}, "margins": {"net_pct": -0.9}, "balance_sheet": {"net_cash": -32.3e9}},
                     "earnings_history": {"available": True, "sample_size": 8, "beat_count": 6, "upcoming": [{"date": "2026-10-29", "timing": "after_close", "eps_estimate": 0.4}]},
                     "ownership": {"available": True, "insider_signal": "buying"}},
         "whats_next": {"this_week": [{"date": "2026-10-28", "label": "FOMC statement and rate decision", "detail": "Wed, Oct 28, Fed"},
                                      {"date": "2026-10-30", "label": "Monthly options expiry (Opex)", "kind": "expiry"}]}}
    got = _run(tmp_path, f"""
      const R = await import('{(JS / "pages/overview-research.js").as_posix()}');
      const t = {json.dumps(t)}, today = new Date(Date.UTC(2026, 9, 25, 12));
      const f = R.factors(t, {{ today }});
      print(JSON.stringify({{ f, ev: R.events(t, false, today), adv: R.events(t, true, today).length, steps: R.nextSteps('INTC', t, f, false, today) }}));
    """)
    pos, neg = [x["text"] for x in got["f"]["pos"]], [x["text"] for x in got["f"]["neg"]]
    assert pos == ["Beat analysts' earnings estimates in 6 of the last 8 quarters", "Company insiders bought more shares than they sold over six months"]
    assert neg == ["Earnings report on Oct 29, in 4 days", "The company lost money over the latest period", "Owes $32.3B more than it holds in cash while losing money"]
    assert next(e for e in got["ev"] if e["label"] == "Earnings report") == {"date": "2026-10-29", "label": "Earnings report", "detail": "in 4 days, analysts expect EPS of 0.40", "view": "earnings"}, "no time of day for a report not yet made"
    assert len(got["ev"]) == 2 and got["adv"] == 3, "the options expiry only at the Advanced level, as in Classic"
    assert [s["text"] for s in got["steps"]] == ["Review past results before the report on Oct 29", "Check the statements behind the weaker figures",
                                                 "See how the price compares with its own valuation history", "Read the 12 latest headlines"]
    assert 'aria-label="Evidence for: ${x.text}">Evidence</a>' in OVR and "Ask Milo writes a question for you to edit. Nothing is sent until you press Send." in OVR


def test_the_past_year_marks_reports_dividends_and_splits(tmp_path):
    got = _run(tmp_path, f"""
      const R = await import('{(JS / "pages/overview-research.js").as_posix()}');
      const t = {{ company: {{ earnings_history: {{ quarters: [{{ date: '2026-07-24', timing: 'after_close', eps_reported: 0.1, eps_estimate: 0.05, surprise_pct: 100 }}, {{ date: '2024-01-01' }}] }} }} }};
      const x = {{ actions: {{ dividends: [{{ date: '2026-08-07', amount: 0.125 }}], splits: [{{ date: '2026-03-02', ratio: 2 }}] }} }};
      print(JSON.stringify({{ m: R.chartMarks(t, x, '2025-10-24', '2026-10-23'), src: R.chartSource({{}}, '2026-10-23', '2026-10-29'), title: R.chartTitle('INTC', [40, 142, 86]) }}));
    """)
    assert [(e["kind"], e["d"], e["text"]) for e in got["m"]] == [("S", "2026-03-02", "2.00-for-1"), ("E", "2026-07-24", "Reported after the close EPS 0.10 against 0.05 expected (beat by 100.0%)"), ("D", "2026-08-07", "$0.13 a share")]
    assert got["m"][1]["detail"] == "EPS 0.10 against 0.05 expected (beat by 100.0%)", "the drawer names the session itself, so its figures do not repeat it"
    assert got["src"] == "Daily closes, split-adjusted, through Oct 23, 2026. Source: Yahoo Finance. Marked: E an earnings report, D an ex-dividend date, S a split. Next report Oct 29, 2026."
    assert got["title"] == "INTC is up 115% over the 3 sessions shown, 39% below its highest close"
    assert "OR.marksFold(chartEvents(shown))" in DOS and "/api/extras/${enc}?benchmark=SPY" in DOS


def test_key_figures_carry_classics_definitions_word_for_word():
    a = APP.index("const KEY_STAT_DEFS = {")
    classic = dict(re.findall(r"\n  (\w+): \"(.*?)\",", APP[a:APP.index("};", a)]))
    term = (JS / "ui/term.js").read_text()
    for k, v in classic.items():
        assert v in term, k
    assert "export const OV_ESSENTIALS = ['market_cap', 'pe_trailing', 'revenue_growth', 'profit_margin', 'dividend_yield', 'high_52', 'low_52'];" in OVR
    assert "Select a label for what it means. All eighteen figures are under Advanced research below." in OVR


def test_optic_read_keeps_its_inputs_scale_skill_line_and_method_fold():
    read = OVR[OVR.index("export function opticRead(c) {"):OVR.index("/* ---------------- Advanced research")]
    for want in ("Optic's read", "of inputs agree", "Each input scores from -100 to +100: a bar fills right of the line when the input leans bullish and left when it leans bearish.",
                 "skill.text", "dg.method ? how(", "role=\"group\" aria-label=\"How the ${p.factors_total || 5} inputs scored\""):
        assert want in read, want
    assert "<summary>Read more</summary>" in OVR and "Every input that had data points the same way." in OVR


def test_the_header_and_the_switch():
    assert "${raw(logoHTML(sym, { lazy: false }))}" in FRAME and "/api/logo/${encodeURIComponent(sym)}" in (JS / "ui/symbols.js").read_text()
    assert "main: `Stage ${r.stage} · ${r.name || ''}`.trim(), tag: r.transition_short || ''" in OVR, "Classic's 'Stage 3 · Topping' and 'breakdown'"
    assert "miloButton('Explain', { ask: st.ask(sym)" in FRAME, "Explain drafts the question; nothing is sent"
    assert "role=\"switch\" aria-checked=\"${on}\" data-v2-adv-toggle" in FRAME and "Show advanced analysis" in FRAME
    assert "if (e.target.closest('[data-v2-adv-toggle]')) { prefs.setAdvanced(!prefs.advancedOn()); return; }" in DOS, "Classic's keys (optic.knowledge.v1)"
    assert '<details class="adv-fold" data-adv ${c.advanced ? \'open\' : \'\'}>' in OVR and '<details class="more-inline cs-fold" data-adv ${c.advanced ? \'open\' : \'\'}>' in OVR


def test_nothing_on_the_overview_calls_a_model_or_sends():
    assert "api." not in OVR and "fetch(" not in OVR
    for path in ("/api/extras/", "/api/stage?symbol=", "/api/framework/", "/api/longterm/"):
        assert path in DOS
    assert "/api/ai" not in DOS and "/api/chat" not in DOS


def test_no_em_dashes_or_pills_in_what_was_added():
    for src in (OVR, FRAME, (JS / "ui/symbols.js").read_text()):
        assert "—" not in src
    block = CSS[CSS.index("/* Classic's Overview, in v2"):]
    assert "--r-pill" not in block and "999px" not in block


# ---------------------------------------------------------------- the logo route (from the search work of 2026-10-21)

@pytest.fixture
def logos(tmp_path, monkeypatch):
    monkeypatch.setattr(m, "_LOGO_DIR", str(tmp_path))
    calls = []

    def fetch(sym):
        calls.append(sym)
        return {"AAPL": (b"<svg xmlns='http://www.w3.org/2000/svg'/>", "image/svg+xml"), "INTC": (b"\x89PNG....", "image/png")}.get(sym)
    monkeypatch.setattr(m, "_logo_fetch", fetch)
    return calls


def test_the_logo_route(logos):
    c = TestClient(m.app)
    a = c.get("/api/logo/aapl")
    assert a.status_code == 200 and a.headers["content-type"].startswith("image/svg+xml")
    assert "sandbox" in a.headers["content-security-policy"] and a.headers["x-content-type-options"] == "nosniff", "an SVG opened on its own runs nothing"
    assert c.get("/api/logo/AAPL").status_code == 200 and logos == ["AAPL"], "kept on disk: asked for once"
    assert c.get("/api/logo/ZZZZ").status_code == 404 and c.get("/api/logo/ZZZZ").status_code == 404 and logos.count("ZZZZ") == 1, "no logo is remembered too"
    for bad in ("%5EGSPC", "ES%3DF", "..%2Fetc", "A" * 14):
        assert c.get(f"/api/logo/{bad}").status_code == 404
    assert "^GSPC" not in logos and len(logos) == 2, "an index, a future or a path is never asked for"


def test_only_images_are_kept(monkeypatch):
    class R:
        def __init__(self, kind, body): self.headers = {"Content-Type": kind}; self.body = body
        def read(self, n=-1): return self.body
        def __enter__(self): return self
        def __exit__(self, *a): return False
    answers = [R("text/html", b"<!DOCTYPE html><p>nope"), R("image/png", b"\x89PNG..")]
    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=6: answers.pop(0))
    assert m._logo_fetch("NVDA") == (b"\x89PNG..", "image/png"), "a web page from the first service is skipped for the second's image"


def test_coming_up_lists_what_it_keeps_by_date(tmp_path):
    """NVDA's Nov 17 report was listed above three Oct 28 events; the report is still never cut (investor audit,
    2026-10-27)."""
    from tests.test_frontend_v2_stage0 import V2, _run
    got = _run(tmp_path, f"""
      const R = await import('{(V2 / "js/pages/overview-research.js").as_posix()}');
      const t = {{ news: {{ earnings_date: '2026-11-17', days_to_earnings: 21 }}, whats_next: {{ this_week: [
        {{ date: '2026-10-28', label: 'Fed decision' }}, {{ date: '2026-10-29', label: 'GDP' }}, {{ date: '2026-10-28', label: 'Home sales' }},
        {{ date: '2026-10-30', label: 'PCE prices' }}, {{ date: '2026-10-31', label: 'Payrolls' }}] }} }};
      print(JSON.stringify(R.events(t, false, '2026-10-27').map((e) => [e.date, e.label])));
    """)
    assert got[-1] == ["2026-11-17", "Earnings report"] and len(got) == 4
    assert [d for d, _ in got] == sorted(d for d, _ in got)
