"""The editorial, interaction and credibility pass (2026-10-19 to 20).

Copy: short, specific, finding first; no development commentary ("the current app" became "the classic app" where
a feature still lives there, since v2 is the default); formulas folded behind "How this works". Milo: quiet
contextual actions in one place (a section's heading), generated text labelled as such, requests that carry the
right instrument and view, plain unavailable and failed states. Credibility: missing data is never a zero or a
conclusion, three clocks said apart, no figures under the wrong ticker, tables aligned by what they hold, one way
to write signs, units, ordinals and dates.

Checked in a browser on real data from the local server, with difficult states made in that browser only
(~/Optic/work/v2-editorial: capture.py, states.py, transitions.py, milo_context.py, wraps.py).
"""
import re

from tests.test_frontend_v2_stage0 import V2
from tests.test_v2_p3 import _run

ROOT = V2.parent.parent
JS = V2 / "js"
SRC = {p.relative_to(JS).as_posix(): p.read_text() for p in JS.rglob("*.js")}


def _visible(src):
    """The source without comments, for checks about what a reader can see."""
    return "\n".join(l for l in src.splitlines() if not l.strip().startswith(("//", "*", "/*")))


def test_the_format_rules(tmp_path):
    got = _run(tmp_path, f"""
      const F = await import('{(JS / "core/format.js").as_posix()}');
      print(JSON.stringify({{
        blank: F.isNum('  '), bool: F.isNum(true), arr: F.isNum([]), str: F.isNum('12.5'), nul: F.isNum(null),
        tinyNeg: F.signed(-0.001), tinyPos: F.signed(0.004), negZeroNum: F.num(-0.001), money0: F.money(-0.001),
        compact: [F.compact(999950), F.compact(999949), F.compact(1234), F.compact(-2.5e9)],
        bad: F.shortDate('bad'), full: F.fullDate('2026-11-02'),
        ord: [1, 2, 3, 4, 11, 12, 13, 21, 22, 81, 101, 111].map(F.ordinal),
        cap: F.capFirst('n/a'),
        bold: F.bolded('Utilities fell **-2.0%** and the Nasdaq **+1.2%**, a 20-day high (-3 points).'),
        iso: F.clean('The company reports on 2026-11-02, before this expiry.'),
        url: F.clean('See https://example.com/2026-11-02/x and id=2026-11-02 and 2026-11-02a.'),
      }}));
    """)
    assert (got["blank"], got["bool"], got["arr"], got["str"], got["nul"]) == (False, False, False, True, False)
    assert got["tinyNeg"] == "0.00%" and got["tinyPos"] == "0.00%", "a value that prints as zero carries no sign"
    assert got["negZeroNum"] == "0.00" and got["money0"] == "$0.00"
    assert got["compact"] == ["1.0M", "999.9K", "1.2K", "−2.5B"]
    assert got["bad"] == "" and got["full"] == "Nov 2, 2026"
    assert got["ord"] == ["1st", "2nd", "3rd", "4th", "11th", "12th", "13th", "21st", "22nd", "81st", "101st", "111th"]
    assert got["cap"] == "n/a"
    assert got["bold"] == "Utilities fell <b>−2.0%</b> and the Nasdaq <b>+1.2%</b>, a 20-day high (−3 points).", got["bold"]
    assert got["iso"] == "The company reports on Nov 2, 2026, before this expiry."
    assert got["url"] == "See https://example.com/2026-11-02/x and id=2026-11-02 and 2026-11-02a.", "addresses, queries and ids are left alone"


def test_split_words(tmp_path):
    got = _run(tmp_path, f"""
      const M = await import('{(JS / "pages/financials.js").as_posix()}');
      print(JSON.stringify([1.5, 4, 0.1, 0.5, 7, null].map(M.splitWords)));
    """)
    assert got == ["3 for 2", "4 for 1", "1 for 10, a reverse split", "1 for 2, a reverse split", "7 for 1", "ratio not reported"]


def test_figures_are_told_from_words(tmp_path):
    got = _run(tmp_path, f"""
      const A = await import('{(JS / "ui/align.js").as_posix()}');
      const yes = ['342.94', '−0.52%', '$1,250', '120.8M', '±5.31%', '1.04×', '+4.2 pts', '12 days', '2.8', '350 to 310'];
      const no = ['Sold', 'Officer and Director', 'Oct 6, 2026', 'Calls', 'Bullish breakout', 'NVDA'];
      print(JSON.stringify({{ yes: yes.filter((v) => !A.FIG.test(v)), no: no.filter((v) => A.FIG.test(v)) }}));
    """)
    assert got == {"yes": [], "no": []}, got
    css = (V2 / "css/components.css").read_text()
    assert "table.t th.l, table.t td.l { text-align: left; } table.t th.n, table.t td.n { text-align: right; }" in css
    assert "watchTables($('#app'));" in SRC["app.js"]
    assert "if (body.every((v) => /^(FY\\s?)?(19|20)\\d\\d$/i.test(v)))" in SRC["ui/align.js"], "a column of years is labels, kept left"
    assert ".dchart > .state.err, .ws-body > .state.err, .op-sec .state.err { border: 0;" in (V2 / "css/components.css").read_text(), "a failure inside a panel is not a second card"


def test_the_later_quote_wins_and_the_header_says_when(tmp_path):
    got = _run(tmp_path, f"""
      const F = await import('{(JS / "pages/dossier-frame.js").as_posix()}');
      const older = {{ price: 100, market_time: '2026-10-19T19:00:00Z', name: 'A' }}, newer = {{ price: 101, market_time: '2026-10-19T19:30:00Z' }};
      print(JSON.stringify({{
        a: F.fresher(older, newer).price, b: F.fresher(newer, older).price, name: F.fresher(newer, older).name,
        open: F.priceWhen({{ quote: {{ market_time: '2026-10-19T19:30:00Z' }}, session: {{ prices: {{ phase: 'regular' }}, session: {{ last_close: {{ date: '2026-10-16' }} }} }} }}),
        shut: F.priceWhen({{ quote: {{}}, session: {{ prices: {{ phase: 'closed' }}, session: {{ last_close: {{ date: '2026-10-19' }} }} }} }}),
      }}));
    """)
    assert got["a"] == 101 and got["b"] == 101 and got["name"] == "A", "the later trade wins, the other fills gaps"
    assert got["open"].startswith("Delayed about 15 minutes, last trade "), "in session a delayed trade, never the close"
    assert got["shut"] == "Close of Mon Oct 19"
    frame = SRC["pages/dossier-frame.js"]
    assert "${isNum(q.price) ? html`<span class=\"dh-ext\">${priceWhen(D)}</span>` : ''}" in frame
    assert "D.quote = fresher(D.quote, d.quote || d);" in SRC["pages/dossier.js"] and "D.quote = fresher(D.quote, t.quote);" in SRC["pages/options.js"]


def test_the_chart_read_says_only_what_was_reported(tmp_path):
    got = _run(tmp_path, f"""
      const C = await import('{(JS / "ui/chartread.js").as_posix()}');
      const m = C.chartReadModel({{ technicals: {{ moving_averages: {{ sma200: {{ value: 300, distance_pct: 14 }}, sma50: {{ value: 320, position: 'above', distance_pct: 7 }} }}, rsi: {{ value: 85 }} }} }});
      print(JSON.stringify(m));
    """)
    assert "Price is 14.0% above the 200-day average." in got["facts"], "a missing position takes the distance's sign"
    assert not any("not stacked" in f for f in got["facts"]), "no claim about stacking without the structure"
    assert got["rsi"] == "85" and got["trend"] == "Uptrend"


def test_missing_data_is_never_a_zero_or_a_conclusion():
    v = _visible
    fin, inv, op, pan, ws, earn = (SRC[k] for k in ("pages/financials.js", "pages/investing.js", "pages/options.js", "pages/options-panels.js", "pages/workspace.js", "pages/earnings.js"))
    for bad in ("(ow.institutional_pct_held || 0)", "(ow.insider_pct_held || 0)", "(h.pct_held || 0)", "(si.percent_of_float || 0)"):
        assert bad not in fin, bad
    for bad in ("(d.upside || 0)", "(d.discount_rate || 0)", "(d.terminal_share || 0)", "(sc[k].upside || 0)"):
        assert bad not in inv, bad
    assert "((r.call || {}).iv || 0) + ((r.put || {}).iv || 0)" not in pan and "const atmIv = (r) =>" in pan, "one missing side no longer halves the IV"
    assert "(r.p_itm_model || 0)" not in op and "(u.iv || 0)" not in pan
    assert "v: (r) => r.mid * 100" not in ws
    # one rule for every result since 2026-10-20 (core/finviz.js surprise): no estimate is said, never "Missed by 0.0%"
    assert "sv.cls === 'missing' ? 'no estimate to compare with'" in earn and "No estimate" in (V2 / "js/core/finviz.js").read_text(), "no 'Missed by 0.0%' without a surprise"
    assert "pr.stance === 'expensive' ? 'rich' : 'cheap'" not in earn, "no 'cheap' for an unknown stance"
    assert "g.revenue_yoy_pct - g.net_income_yoy_pct > 2 ? ': sales grew" not in fin and "revenue outpaced net income" in fin
    assert "${c.uptrend || 0} in uptrends" not in SRC["pages/market-shared.js"]
    assert "valuation added ${num(valuation ? valuation.points : 0, 0)}" not in SRC["pages/dossier.js"]
    # a source that failed is said so, not read as a finding
    dos = SRC["pages/dossier.js"]
    ovr = SRC["pages/overview-research.js"]   # a company's four questions since 2026-10-25 (Classic's, ported)
    assert "if (c.fwError) body = pendingGrid(c, `The four grades are not available right now:" in ovr and "D.fwNetError = e" in dos
    assert "The long-term score is not available:" in ovr and "had no data on this run" in ovr, "a missing score or input is said, never scored as neutral"
    # colour only on a figure that exists
    for k, s in SRC.items():
        if k.startswith("pages/"):
            assert not re.search(r"class=\"\$\{[A-Za-z_][\w.]* >= 0 \? 'up' : 'down'\}", v(s)), k


def test_unavailable_short_interest_server_text():
    from app.analytics.fundamentals import analyse_short_interest
    r = analyse_short_interest({"shares_short": 10, "short_ratio_days": 1}, None)
    assert " . " not in r["caveat"] and r["squeeze_potential"] == "not known"


def test_no_figures_under_the_wrong_ticker_and_retry_works():
    ch, earn, cmp, dos = SRC["pages/chart.js"], SRC["pages/earnings.js"], SRC["pages/compare.js"], SRC["pages/dossier.js"]
    assert "const box = D;\n  if (!D.tPromise) D.tPromise = api.get(" in ch and ".then((t) => { box.t = t; return t; })" in ch
    assert "const box = D;\n  box.brief = 'loading'" in earn and "catch (e) { if (D.sym === sym) D.err = e; }" in earn
    assert "if (mine !== seq) return;" in cmp and "result = null; seq++;" in cmp
    assert "render(main, route); } };" in dos and "draw(main, route); } };" not in dos, "Try again re-renders the page, not '[object Object]'"
    assert "const HOME_GROUP = { instrument: 'market'," in SRC["nav.js"], "an instrument page marks Markets in the sidebar"


def test_the_copy_rules():
    for k, s in SRC.items():
        vis = _visible(s)
        assert "current app" not in vis, k
        assert "paid model" not in vis and "paid call" not in vis, k
        assert "on this deployment" not in vis, k
    assert "not a fourth thing to read" not in SRC["pages/explore.js"]
    assert "÷ 16)" not in _visible(SRC["pages/home.js"]).split("${how(")[0], "the formula is inside the fold"
    assert "VIX ${num(em.vix, 1)} ÷ 16, ±" not in SRC["pages/macro.js"]
    assert "% ÷ ±${num(pr.baseline_move_pct)}% typical for" not in SRC["pages/options.js"]
    assert "${how(html`<p>The ratio is the priced move" in SRC["pages/dossier.js"]


def test_milo_presence():
    st, milo, op = SRC["ui/states.js"], SRC["ui/milo.js"], SRC["pages/options.js"]
    assert "export const generated = (x, { at } = {}) =>" in st
    assert "Written by an AI model from the figures" in st and "Compiled by fixed rules from the figures" in st
    for k in ("pages/read.js", "pages/market-shared.js", "pages/earnings.js"):
        assert "generated(" in SRC[k], k
    assert "Generated by an AI model from Optic's data. It can be wrong; check the figures against the sources." in milo
    assert "slot.appendChild(m);" in op and "m.dataset.v2MiloCtx = `${D.sym} Dossier, Options: ${label}`" in op, "the panel's Milo action in its heading, naming the panel"
    assert "focus_label: D.d && D.d.label ? `${D.d.label} (${D.sym})` : ''" in SRC["pages/instrument.js"]
    assert "Milo did not respond${status ? ` (HTTP ${status})` : ''}. Wait a moment and send it again; your question is still in the box." in milo
