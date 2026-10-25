"""The beginner-usability pass (owner's brief, 2026-10-20): what a first-time guest meets, said plainly, with every
advanced reading kept one step away. The synthesis of the long-term views, the price-trend finding and the absent-
figure words run in JavaScriptCore; the rest is read as text. The brief's seven journeys were walked as a guest in
headless Chrome at 360, 390, 430 and 1440 (~/Optic/work/beginner/beginner_verify.py, 100 checks): a structured
walkthrough, with no real beginners taking part.
"""
from tests.test_frontend_v2_stage0 import V2, _run

JS = V2 / "js"
WS = (JS / "pages/workspace.js").read_text()
OV = (JS / "pages/dossier.js").read_text()
PAL = (JS / "ui/palette.js").read_text()
MILO = (JS / "ui/milo.js").read_text()
TR = (JS / "pages/tracker.js").read_text()
EX = (JS / "pages/explore.js").read_text()
SET = (JS / "pages/settings.js").read_text()
STATUS = (JS / "core/status.js").read_text()
HOME = (JS / "pages/home.js").read_text()
NAV = (JS / "nav.js").read_text()


def test_navigation_names_are_unchanged():
    # the owner's rule: no sidebar section, item or phone label renamed without an explicit yes in conversation
    for label in ("label: 'Dossier'", "label: 'Positions'", "label: 'Discover'", "label: 'Markets'", "label: 'Optic Portfolio'", "label: 'Paper Desk'"):
        assert label in NAV, label


def test_home_starts_with_three_plain_ways_in():
    ob = WS[WS.index("function onboard() {"):WS.index("// A row the next panel cannot join ends early")]
    for want in ("Research a company.", "Understand today's market.", "Save a company to follow.", "${term('ticker', 'ticker')}", "it does not buy shares or spend money", "SPY is a fund that tracks the S&P 500"):
        assert want in ob, want
    assert "data-ws-mode" not in ob, "the level is Milo's setting, not a first-visit question"
    assert "export const STARTER_NAMES = { AAPL: 'Apple', NVDA: 'NVIDIA', MSFT: 'Microsoft', SPY: 'S&P 500 fund' };" in HOME
    btn = WS[WS.index("function followBtn("):WS.index("function onboard() {")]
    assert "${STARTER_NAMES[sym] || sym} <span class=\"ob-sym\">${sym}</span>" in btn, "Follow Apple AAPL, never Follow AAPL"


def test_linked_panels_say_what_they_follow_and_sit_under_it():
    row = WS[WS.index("function linkRow() {"):WS.index("function panelShell(")]
    assert "Company or fund shown in linked panels" in row and ">Update panels</button>" in row
    assert "show this company or fund; the others show the whole market." in row
    assert "Linked ticker</label>" not in WS and ">Link</button>" not in WS
    assert "i === shown.findIndex((y) => PANELS[y.id].linked) ? linkRow() : ''" in WS, "right above the first panel it drives"


def test_the_market_strip_and_conditions_are_plain():
    assert "title: 'Markets at a glance'" in WS and "'WTI Crude': 'Dollars a barrel'" in WS and "VIX: 'Volatility index'" in WS
    # every move by its direction only, the VIX and the 10-year included, as Classic's strip (owner, 2026-10-21,
    # pointing at the VIX's uncoloured -4.04%); before that, the beginner brief left those two uncoloured
    assert "NEUTRAL_MOVE" not in WS and '<span class="d ${dir(i.chg_1d)}">' in WS
    assert "title: 'Market conditions'" in WS
    body = WS[WS.index("title: 'Market conditions'"):WS.index("  expected: {")]
    assert body.index('<p class="ws-lead">') < body.index('<details class="ws-more"><summary>How these readings are built</summary>'), "the finding before the arithmetic"
    assert "'neutral / mixed': 'Mixed: no clear lean'" in WS


def test_the_calendar_says_why_a_figure_is_missing(tmp_path):
    got = _run(tmp_path, f"""
      const F = await import('{(JS / "core/finviz.js").as_posix()}');
      print(JSON.stringify(F.MISSING));
    """)
    assert got == {"pending": "Not released yet", "na": "Not applicable", "unavailable": "Not available"}
    cal = WS[WS.index("const cellFig = (e, r, k) => {"):WS.index("let day = '';")]
    assert "FV.MISSING.pending" in cal and "FV.MISSING.na" in cal and "FV.MISSING.unavailable" in cal and "pending</span>" not in WS


def test_overview_opens_on_what_the_company_does():
    paint = OV[OV.index("function paint(main, sym) {"):]
    assert paint.index("${about(sym)}") < paint.index('section class="section dchart"')
    ab = OV[OV.index("function about(sym) {"):OV.index("/* ---------------- the rest, one step away")]
    for want in ("What ${name} does", "<dt>${fund ? 'Kind of fund' : 'Industry'}</dt>", "Where its revenue comes from", "US dollars; quotes delayed about 15 minutes", "replace(/^The Company\\b/, name)"):
        assert want in ab, want
    assert "String(d.data_caveat).split(" in OV, "the chart's footer is the delay, not Greeks and Black-Scholes"
    # A company's four answers are Classic's four questions since 2026-10-25 (owner's screenshots; the owner chose to
    # replace v2's set rather than show both): the share price's trend is said inside "Is there a trade?", beside the
    # setup. A fund keeps its four, with the price trend in place of a trade setup.
    ans = OV[OV.index("function answers(sym) {"):OV.index("function answerGrid(out) {")]
    assert "return answerGrid(fundAnswers(sym, trendItem(sym)));" in ans
    assert "${fund ? (D.fwError && D.fvError && D.earnError ? failed('The four answers', D.fwError, { retry: 'dossier' }) : answers(sym)) : OR.fourQuestions(c)}" in OV
    ovr = (JS / "pages/overview-research.js").read_text()
    assert "This describes the stock, not the business." in ovr and "tile('trade', 'Is there a trade?', value, sw.why" in ovr


def test_the_long_term_views_are_told_apart_and_summed_up(tmp_path):
    got = _run(tmp_path, f"""
      const O = await import('{(JS / "pages/dossier.js").as_posix()}');
      const pts = Array.from({{ length: 300 }}, (_, i) => ({{ d: `2026-${{String(1 + Math.floor(i / 28) % 12).padStart(2, '0')}}-01`, c: 100 + i * 0.5 }}));
      print(JSON.stringify({{
        apple: O.synthesis(82, 'A', {{ available: true, stars: 1 }}, 'Stretched', 'Neutral'),
        allGood: O.synthesis(85, 'A', {{ available: true, stars: 5 }}, 'Cheap', 'Positive'),
        none: O.synthesis(null, null, {{}}, '', 'Neutral'),
        trend: O.trendFinding(pts, 200),
      }}));
    """)
    assert got["apple"] == "The business grades A and the long-term price trend is strong (82 of 100), but the price is above its fair value range (valuation stretched). Weighing them, Optic's combined long-term case is neutral."
    assert " but " not in got["allGood"] and got["allGood"].startswith("The business grades A")
    assert got["none"] == "Optic's combined long-term case is neutral."
    assert abs(got["trend"]["ch"] - ((249.5 - 123.5) / 123.5 * 100)) < 1e-6 and got["trend"]["span"] == "a year", "a year back: 252 sessions"
    # the summing up leads "Taken together"; the trend score itself is the Optic Score's long-term reading (2026-10-25)
    comb = OV[OV.index("function combined() {"):OV.index("/* ---------------- what changed lately")]
    assert "const syn = synthesisLine();" in comb and '<p class="synth">${syn}</p>' in comb
    ovr = (JS / "pages/overview-research.js").read_text()
    assert "span: 'Long term: several years'" in ovr and "line: clean(h.plan || '')" in ovr, "the trend model's own wording, as its reading"


def test_search_can_be_dismissed_on_a_phone_and_leads_with_companies():
    # a visible way out on a phone (no Escape key): since 2026-10-21 TradingView's close button, labelled
    assert 'placeholder="Search a company, fund or ticker"' in PAL and '<button type="button" class="palette-x" data-pal-close aria-label="Close search" title="Close">${icon(\'close\').s}</button>' in PAL
    assert "e.target.closest('[data-pal-close]')) { close(); return; }" in PAL
    empty = PAL[PAL.index("  if (!q) {"):PAL.index("  const upper = q.toUpperCase()")]
    assert empty.index("group: 'Companies'") < empty.index("group: 'Actions'") < empty.index("group: 'Go to'")
    assert "['AAPL', 'Apple', 'iPhone, Mac and services']" in PAL


def test_milo_tells_a_guest_what_needs_an_account():
    acc = MILO[MILO.index("function accessHTML(b) {"):MILO.index("function chromeHTML() {")]
    assert "Milo is available. A free account lets you ask it" in acc and 'href="#/signin">Sign in or create an account' in acc
    assert "Without an account you can search companies, read every page" in acc
    assert "return html`${accessHTML(b)}${ctxHTML()}${movedHTML()}${personaHTML()}`;" in MILO, "said first, the personas still shown"
    assert "const fm = $('.milo-form', h); if (fm) fm.hidden = !!b && b.kind !== 'spent';" in MILO, "no disabled form presented as ready"
    assert "'Milo is available with a free account.'" in STATUS and "'Milo is answering.'" not in STATUS


def test_the_level_is_labelled_as_milos():
    assert "How Milo explains things" in SET and "The pages are the same at every level" in SET
    assert "every page leads with plain-language summaries and the specialist panels start folded" not in SET, "it never did that"


def test_discover_starts_with_questions_and_their_real_periods():
    g = EX[EX.index("const GUIDED = ["):EX.index("const colText")]
    assert "['movers', 'Which stocks have moved the most?', 'The largest moves over the past month, up or down, among liquid stocks. A month, not today.']" in g
    assert "'volume'" in g and "'steady'" in g
    gd = EX[EX.index("function guided() {"):EX.index("function readings() {")]
    assert "Being on a list is not a recommendation" in gd and "See the full list" in gd and "c.label.toLowerCase()" in gd, "why each name is there"


def test_positions_says_whose_portfolio_it_is():
    head = TR[TR.index("draw(mainEl, html`<header class=\"page-head\">"):TR.index("${D.err ? failed(")]
    assert "This is Optic's demonstration portfolio, not yours." in head and "No money is real and no order reaches a broker." in head and 'href="#/paper">Paper Desk' in head
    assert "Three simulated accounts" in TR and "which traders call a book" in TR
    assert "aggressive: 'Higher risk: bigger gains and bigger losses'" in TR and "${RISK_WORDS[b.id] || b.tagline}" in TR, "no 'high reward' promise"
    assert 'class="btn btn-primary" data-v2-tk="scan"' not in TR and "These act on the demonstration portfolio every reader sees." in TR
