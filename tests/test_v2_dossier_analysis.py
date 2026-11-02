"""The Dossier's analysis: the Simple Analysis at five levels, one view at a time, and responses tied to their visit
(post-demo Phase 06, directive 06).

The Simple Analysis (pages/overview-simple.js) answers three questions from figures the Overview already loads, by
fixed rules, in the reader's knowledge level. These tests build it in JavaScriptCore from fixtures shaped like the
server's payloads, so they check the words against figures known in advance: the same figures at every level, every
caveat at every level, Optic's own advice check passing at every level, and missing data said as missing. How the page
swaps the two views, and what happens when tickers change while requests are in flight, are checked in headless
Chrome by tools/phase06_checks.py (TEST_RESULTS.md, Phase 06); the source checks here pin the guards it relies on.
"""
import json
import re

from app import ai_policy
from tests.test_frontend_v2_stage0 import V2, _run

JS = V2 / "js"
src = lambda p: (JS / p).read_text()   # noqa: E731
LEVELS = ["new", "beginner", "intermediate", "advanced", "expert"]


def closes(n=300, start=200.0, peak=238.0, end=212.6, flat=48, peak_at=200):
    """A daily series flat at `start` until the year's window opens (252 sessions back from the last close), then up to
    `peak` and back to `end`: a year's change of +6.3% and a close 10.7% below the high, which every level must state
    alike."""
    out = []
    for i in range(n):
        if i < flat:
            out.append(start)
        elif i <= peak_at:
            out.append(start + (peak - start) * (i - flat + 1) / (peak_at - flat + 1))
        else:
            out.append(peak + (end - peak) * (i - peak_at) / (n - 1 - peak_at))
    return [round(x, 2) for x in out]


def dates(n=300):
    import datetime as dt
    d, out = dt.date(2025, 8, 18), []
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d += dt.timedelta(days=1)
    return out


def company(**over):
    t = {"quote": {"price": 212.6, "change_pct": -0.8, "trailing_pe": 27.0, "forward_pe": 13.4, "revenue_growth": 1.059, "profit_margin": 0.556,
                   "delayed_minutes": 15, "name": "Test Corporation", "fifty_two_low": 150, "fifty_two_high": 240},
         "company": {"financials": {"available": True, "growth": {"revenue_yoy_pct": 65.47, "net_income_yoy_pct": 64.75},
                                    "margins": {"gross_pct": 71.07, "operating_pct": 60.38, "net_pct": 55.6},
                                    "annual_periods": ["2026-01-31"], "annual_fiscal": ["FY26"]}},
         "technicals": {"price_series": {"dates": dates(), "close": closes()}},
         "news": {"earnings_date": "2026-11-17", "days_to_earnings": 19, "article_count": 2, "overall_tone": "neutral"}}
    lt = {"holding": {"valuation_history": {"available": True, "usable_years": 4, "current_pe": 27.0, "median_pe": 36.2, "low_pe": 32.2, "high_pe": 102.8}}}
    earnings = {"implied": {"available": True, "implied_move_pct": 8.52, "expiry": "2026-11-20"}}
    session = {"session": {"is_regular": False}, "profile": {"name": "Test Corporation"}}
    for k, v in over.items():
        {"t": t, "lt": lt, "earnings": earnings, "session": session}[k].update(v) if isinstance(v, dict) else None
    return {"sym": "TEST", "kind": "company", "t": t, "lt": lt, "earnings": earnings, "session": session}


def build(tmp_path, fx, levels=LEVELS):
    """Each level's three answers for one fixture, with the facts they were built from."""
    return _run(tmp_path, f"""
      const OR = await import('{(JS / "pages/overview-research.js").as_posix()}');
      const S = await import('{(JS / "pages/overview-simple.js").as_posix()}');
      const fx = {json.dumps(fx)};
      const now = Date.parse('2026-10-29T20:00:00Z');
      const c = OR.context({{ sym: fx.sym, t: fx.t, lt: fx.lt, stars: null, fund: fx.kind === 'fund', advanced: false, phase: '', now }});
      const F = S.simpleFacts({{ sym: fx.sym, kind: fx.kind, t: fx.t, lt: fx.lt, quote: fx.t.quote, session: fx.session, earnings: fx.earnings, price: c.price, f: c.f, today: new Date(now) }});
      const out = {{}};
      for (const L of {json.dumps(levels)}) out[L] = S.simpleAnalysis(F, L).map(([q, lines]) => [q, lines.join(' ')]);
      print(JSON.stringify({{ F, out }}));
    """)


def text(blocks):
    return " ".join(t for _q, t in blocks)


def test_three_questions_at_every_level_worded_differently(tmp_path):
    got = build(tmp_path, company())
    for L in LEVELS:
        assert [q for q, _t in got["out"][L]] == ["What's happening?", "Why does it matter?", "What else should I know?"], L
        assert all(t.strip() for _q, t in got["out"][L]), L
    texts = [text(got["out"][L]) for L in LEVELS]
    assert len(set(texts)) == 5, "five levels, five wordings"
    words = [len(t.split()) for t in texts]
    assert words[0] > words[4], "New to Markets explains more than Expert says"


def test_the_same_figures_at_every_level(tmp_path):
    got = build(tmp_path, company())
    F = got["F"]
    assert round(F["yr"], 1) == 6.3 and round(F["off"], 1) == -10.7, F
    # each figure, in the form each level writes it: rounding changes with the level, the figure does not
    want = {
        "new": ["up 6%", "11% below", "down 0.8%", "grew 65%", "56 cents", "$27", "$36", "4 years", "Nov 17, in 19 days", "Jan 31, 2026"],
        "beginner": ["up 6%", "11% below", "down 0.8%", "65%", "56%", "27.0", "36.2", "Nov 17, in 19 days", "Jan 31, 2026"],
        "intermediate": ["6.3%", "10.7%", "0.8%", "65.5%", "64.8%", "55.6%", "27.0", "36.2", "25%", "Nov 17, in 19 days", "Jan 31, 2026"],
        "advanced": ["+6.3%", "−10.7%", "−0.80%", "+65.5%", "+64.8%", "55.6%", "27.0", "36.2", "32.2 to 102.8", "−25%", "13.4", "Nov 17 (19 days)", "±8.5%", "Nov 20"],
        "expert": ["+6.3%", "−10.7%", "−0.80%", "+65.5%", "+64.8%", "NM 55.6%", "27.0x", "36.2x", "−25%", "13.4x", "Nov 17, 19d", "±8.5%", "Nov 20"],
    }
    for L, needles in want.items():
        t = text(got["out"][L])
        for n in needles:
            assert n in t, (L, n, t)


def test_every_level_keeps_the_caveats_and_none_gives_advice(tmp_path):
    fx = company()
    fx["t"]["gex"] = {"regime": {"state": "negative"}}   # a risk whose reason is its caveat
    got = build(tmp_path, fx)
    for L in LEVELS:
        t = text(got["out"][L])
        assert "An assumption, not reported positions." in t, (L, "a risk keeps its caveat at every level")
        assert re.search(r"[Dd]elayed 15 minutes", t), (L, "the delay")
        assert re.search(r"not a recommendation|does not tell you what to buy or sell", t), L
        assert "either way" in t or "either direction" in t or "Nov 17" in t, (L, "the report is two-sided")
        assert "—" not in t, (L, "no em dashes")
        assert ai_policy.check_output(t) == [], (L, ai_policy.check_output(t))


def test_a_company_losing_money_says_so_and_invents_no_multiple(tmp_path):
    fx = company(t={"quote": {"price": 11.45, "change_pct": -1.9, "trailing_pe": None, "forward_pe": -6.6, "revenue_growth": 0.272, "profit_margin": -0.55, "delayed_minutes": 15, "name": "Loss Co"}})
    fx["t"]["company"]["financials"].update({"growth": {"revenue_yoy_pct": 8.39, "net_income_yoy_pct": None}, "margins": {"gross_pct": 2.7, "operating_pct": -66.5, "net_pct": -67.7}})
    fx["lt"] = {"holding": {"valuation_history": {"available": False}}}
    got = build(tmp_path, fx)
    assert "losing money: about 68 cents on every dollar of sales" in text(got["out"]["new"])
    assert "no price-to-earnings figure" in text(got["out"]["new"])
    assert "It has no P/E" in text(got["out"]["beginner"]) and "There is no P/E to read: its earnings are negative." in text(got["out"]["intermediate"])
    assert "P/E not meaningful (negative earnings)." in text(got["out"]["expert"])
    for L in LEVELS:
        assert "−6.6" not in text(got["out"][L]) and "6.6x" not in text(got["out"][L]), "a negative forward P/E is not shown as a multiple"


def test_missing_statements_are_said_to_be_missing(tmp_path):
    fx = company()
    fx["t"]["company"]["financials"] = {"available": False}
    fx["t"]["quote"]["profit_margin"] = None
    got = build(tmp_path, fx, ["new", "intermediate", "expert"])
    assert "could not read TEST's financial statements" in text(got["out"]["new"]) and "missing information, not a bad result" in text(got["out"]["new"])
    assert "missing data, not a bad result" in text(got["out"]["intermediate"])
    assert "No financial statements in the data." in text(got["out"]["expert"])


def test_a_fund_an_index_and_a_coin_are_described_as_what_they_are(tmp_path):
    base = company()
    fund = dict(base, sym="SPY", kind="fund", session={"session": {"is_regular": False}, "profile": {"category": "Large Blend", "fund_family": "State Street"}})
    fund["t"] = dict(base["t"], quote={"price": 769.4, "change_pct": -0.4, "trailing_pe": 24.4, "dividend_yield": 0.0099, "delayed_minutes": 15, "name": "SPDR S&P 500 ETF"})
    fund["lt"] = {"holding": {"risk": {"annualised_vol_pct": 17.5}, "drawdown": {"current_drawdown_pct": -1.3}}}
    got = build(tmp_path, fund, ["new", "beginner"])
    assert "SPY is a fund" in text(got["out"]["new"]) and "about $24 for every $1" in text(got["out"]["new"])
    assert "Its distribution yield, what it pays out a year as a share of its price, is 0.99%." in text(got["out"]["beginner"])
    index = dict(base, sym="^GSPC", kind="index")
    index["t"] = dict(base["t"], quote={"price": 7720.4, "change_pct": -0.3, "name": "S&P 500"})
    got = build(tmp_path, index, ["new", "expert"])
    assert "The S&P 500 is not a company" in text(got["out"]["new"]) and "Index; no fundamentals of its own." in text(got["out"]["expert"])
    coin = dict(base, sym="BTC-USD", kind="crypto")
    coin["t"] = dict(base["t"], quote={"price": 78591.4, "change_pct": -3.3, "name": "Bitcoin USD"})
    got = build(tmp_path, coin, ["new", "intermediate"])
    assert "Bitcoin is a digital currency, not a company" in text(got["out"]["new"])
    assert "no valuation measure applies" in text(got["out"]["intermediate"])
    for out in got["out"].values():
        assert "P/E" not in text(out), "no company measure is put on a coin"


def test_the_section_says_its_level_and_leaves_its_own_explanations_unmarked():
    s = src("pages/overview-simple.js")
    assert "${label ? `Worded for ${label}. ` : ''}<a class=\"textlink\" href=\"#/settings\">Change the level</a>" in s
    assert "const own = level === 'new' || level === 'beginner';" in s and "${own ? 'data-no-gloss' : ''}" in s, \
        "New to Markets and Beginner explain their own terms, so the glossary does not explain them twice"
    assert "data-v2-milo=\"${ask}\"" in s and "Nothing is sent until you press Send." in s
    assert "api." not in s and "fetch(" not in s, "nothing is fetched for it"


def test_one_view_at_a_time_from_one_state(tmp_path):
    d = src("pages/dossier.js")
    assert "${mode === 'advanced' ? advancedView(sym, c, fund) : simpleView(sym, c)}" in d
    assert "const mode = prefs.advancedOn() ? 'advanced' : 'simple';" in d, "the density setting is the one state"
    assert d.count("data-v2-analysis=") == 1 and "ov-simple" not in src("pages/overview-research.js")
    got = _run(tmp_path, f"""
      const dom = await import('{(JS / "core/dom.js").as_posix()}');
      const fr = await import('{(JS / "pages/dossier-frame.js").as_posix()}');
      print(JSON.stringify({{ s: dom.toString(fr.advToggle('simple')), a: dom.toString(fr.advToggle('advanced')) }}));
    """)
    assert ">Show advanced analysis</button>" in got["s"] and ">Show simple analysis</button>" in got["a"]
    assert 'aria-controls="ov-analysis"' in got["s"] and 'role="switch"' not in got["s"]


def test_a_response_is_drawn_only_into_the_visit_that_asked_for_it():
    d = src("pages/dossier.js")
    assert "const sym = route.symbol, visit = ++VISIT;" in d and "const mine = () => live && D.visit === visit;" in d
    assert "p.then((d) => { if (mine()) ok(d); }, (e) => { if (mine()) bad(e); }).finally(() => { if (mine()) paint(main, sym); });" in d
    assert "setTimeout(() => { if (mine()) stageRead(tries - 1); }, 30000)" in d and "TR.load().then(() => { if (mine() && D.stage) stageFor(sym); });" in d
    assert "D.sym === sym" not in d, "a symbol check alone let an earlier visit to the same symbol draw into this one"
    assert "if (main.dataset.v2Wired) return;" in d, "Try again renders into the same element; the toggle must not be wired twice"
    assert "(d) => { D.session = d; learn(sym, { session: d, quote: D.quote }); }, () => { D.session = null; });" in d, \
        "a failed session read must not leave the simple analysis waiting"


def test_the_swap_fades_and_keeps_its_place():
    d = src("pages/dossier.js")
    assert "if (now && anchor !== null && anchor < wasTop) window.scrollTo(0, Math.max(0, window.scrollY + now.getBoundingClientRect().top - top - 8));" in d
    assert "queueMicrotask(() => {" in d, "after the section strip is redrawn for the new view, before a frame is drawn"
    assert "st.textContent = `Showing the ${mode} analysis.`" in d and '<p class="sr" role="status" data-v2-analysis-status></p>' in d
    css = (V2 / "css/pages.css").read_text()
    assert ".ov-analysis[data-swapped] { animation: ov-swap var(--m-content) var(--ease-out); }" in css
    assert "@keyframes ov-swap { from { opacity: 0; } to { opacity: 1; } }" in css, "opacity only: nothing moves"
    base = (V2 / "css/base.css").read_text()
    assert ':root[data-motion="reduce"] *' in base and "prefers-reduced-motion: reduce" in base, "reduced motion stills it"


def test_a_search_opened_before_the_arrival_frame_keeps_focus():
    """The shell focuses a page's heading one frame after it arrives, for a screen reader. A search opened in between
    lost its focus to that heading, and the Overview's next redraw replaced the heading, so Enter went nowhere: 3 of 40
    searches in a row did nothing (BUG-093)."""
    app = (JS / "app.js").read_text()
    assert "const h = drawer.isOpen() || palette.isOpen() ? null : view.querySelector('h1');" in app
    d = src("pages/dossier.js")
    assert "(keepFocus.tagName === 'H1' ? 'h1' : '')" in d and "if (key === 'h1') el.setAttribute('tabindex', '-1');" in d, \
        "a focused heading keeps focus through the Overview's redraws"


def test_the_simple_analysis_follows_the_headers_price_refresh():
    d = src("pages/dossier.js")
    assert "onQuote: () => { if (mine()) refreshSimple(main, sym); }" in d
    assert "if (prefs.advancedOn() || quoteKey() === D.simpleKey) return;" in d and "sec.replaceWith(tmp.firstElementChild);" in d, \
        "redrawn in place, alone, when the quote it was written from has moved on"
