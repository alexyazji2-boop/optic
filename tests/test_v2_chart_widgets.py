"""The classic Chart page's side widgets in v2 (C12; the Learn widget of C17): the eighteen panels opened
from a rail beside the plot (static/v2/js/pages/chart-widgets.js, wired in pages/chart.js).

Names, order, marks, the checklist's questions and the glossary are compared with static/app.js as text.
Each widget is drawn in JavaScriptCore from a trimmed copy of a real /api/ticker payload (AAPL, 19 Oct
2026, tests/fixtures/v2_chart_widgets_AAPL_2026-10-19.json), with the page stubbed. The layout was checked
in a browser at 1440, 1024 and 390 px against the running server.
"""
import json
import re
from pathlib import Path

from tests.test_frontend_v2_stage0 import V2
from tests.test_v2_p3 import _run

ROOT = V2.parent.parent
JS = V2 / "js"
CLASSIC = (ROOT / "static/app.js").read_text()
CW = (JS / "pages/chart-widgets.js").read_text()
CH = (JS / "pages/chart.js").read_text()
CSS = (V2 / "css/pages.css").read_text()
FIXTURE = json.loads((ROOT / "tests/fixtures/v2_chart_widgets_AAPL_2026-10-19.json").read_text())


def _widgets(src, start):
    i = src.index(start)
    block = src[i:src.index("\n];", i)]
    rows = re.findall(r"\{ id: '([a-z]+)', label: '([^']+)',(?:[^\n]*?short: '([^']+)')?[\s\S]*?icon: '([^']+)' \}", block)
    return [(a, b, c or None, d) for a, b, c, d in rows]


def test_the_eighteen_widgets_keep_the_classic_names_order_and_marks():
    classic, v2 = _widgets(CLASSIC, "const WS_WIDGETS = ["), _widgets(CW, "export const WIDGETS = [")
    assert len(classic) == 18 and v2 == classic


def test_the_checklist_and_the_glossary_are_the_classic_words():
    i = CLASSIC.index("const WS_CHECKS = [")
    classic_checks = re.findall(r"'([^']+)'", CLASSIC[i:CLASSIC.index("];", i)])
    i = CW.index("export const CHECKS = [")
    assert re.findall(r"'([^']+)'", CW[i:CW.index("];", i)]) == classic_checks and len(classic_checks) == 7
    i = CLASSIC.index("const GLOSSARY = {")
    classic_body = CLASSIC[i:CLASSIC.index("\n};\n", i)]
    v2 = (JS / "core/glossary.js").read_text()
    i = v2.index("const GLOSSARY = {")
    assert v2[i:v2.index("\n};\n", i)] == classic_body, "a definition changed in one copy and not the other"


def test_what_the_reader_types_is_kept_in_the_classic_keys_and_the_personal_ones_are_guarded():
    device = (JS / "core/device.js").read_text()
    for key in ("optic.chart.notes.v1", "optic.chart.checks.v1", "optic.chart.stopcheck.v1"):
        assert f"'{key}'" in CW and f"'{key}'" in device and f"'{key}'" in CLASSIC
    for key in ("optic.chart.backtest.v1", "optic.chart.pairs.v1"):
        assert f"'{key}'" in CW and f"'{key}'" in CLASSIC and f"'{key}'" not in device   # classed as Classic classes them
    assert "const PERSONAL = new Set([KEY.notes, KEY.checks, KEY.stop]);" in CW
    assert "if (PERSONAL.has(k) && !held()) return {};" in CW and "if (PERSONAL.has(k) && !held()) {" in CW


def test_only_free_endpoints_and_only_once_a_panel_is_open():
    urls = set(re.findall(r"[`'](/api/[a-z/-]+)", CW))
    assert urls == {"/api/alerts", "/api/analysts/", "/api/seasonality/", "/api/tracker", "/api/stop-check/", "/api/pairs/", "/api/backtest/", "/api/backtest/strategies"}, urls
    for paid in ("/api/chat", "/api/brief", "/brief", "/api/catalyst-mode", "/read"):
        assert paid not in CW
    # requests start from need(id), which the page calls for a panel it has just put on screen
    assert "added.forEach((id) => W.need(id));" in CH
    assert "W.need(" not in CH.split("function syncSide")[0]


def test_each_widget_draws_from_a_real_ticker_payload(tmp_path):
    got = _run(tmp_path, f"""
      const W = await import('{(JS / "pages/chart-widgets.js").as_posix()}');
      const t = {json.dumps(FIXTURE)};
      W.bind({{ sym: () => 'AAPL', t: () => t, tErr: () => null, phase: () => 'regular', repaint() {{}}, chart() {{}}, overlayOn: () => false, overlay() {{}} }});
      W.reset();
      const {{ toString }} = await import('{(JS / "core/dom.js").as_posix()}');
      const text = (id) => toString(W.body(id)).replace(/<[^>]+>/g, ' ').replace(/&amp;/g, '&').replace(/&#39;/g, "'").replace(/\\s+/g, ' ').trim();
      const out = {{}};
      const asks = {{}};
      for (const id of W.IDS) {{ out[id] = text(id); asks[id] = toString(W.body(id)).includes('sk-wrap'); }}
      const waiting = {{}};
      W.bind({{ sym: () => 'AAPL', t: () => null, tErr: () => null, phase: () => null, repaint() {{}}, chart() {{}}, overlayOn: () => false, overlay() {{}} }});
      for (const id of W.FROM_TICKER) waiting[id] = toString(W.body(id)).includes('sk-wrap');
      print(JSON.stringify({{ out, asks, waiting, terms: [W.termName('atm'), W.termName('forward p/e'), W.termName('realised p&l'), W.termName('yoy'), W.termName('iron condor')] }}));
    """)
    o = got["out"]
    # those waiting on their own endpoint say so (nothing is fetched in this stub): the analysts' latest actions
    # and the stop check's answer under figures already drawn, the others in place of them
    assert sorted(k for k, v in got["asks"].items() if v) == ["alerts", "analysts", "backtest", "seasonality", "stopcheck", "trading", "watchlist"]
    for id_, words in o.items():
        assert "could not be drawn" not in words, id_
        assert words or got["asks"][id_], id_
    assert "Mean target $329.38" in o["analysts"] and "Consensus Buy" in o["analysts"] and "−3.7% to the mean target" in o["analysts"]
    # the payload's real fields, which the classic widgets missed
    assert "Gross margin 46.9%" in o["reports"] and "Revenue growth, year on year +6.4%" in o["reports"] and "EPS beat rate 100% of 8 quarters" in o["reports"]
    assert "ATM IV, 7 days 21.6%" in o["options"] and "Call wall 350.00 (+2.3%)" in o["options"] and "Net GEX $" in o["options"]
    assert "Short float 0.83%" in o["insiders"] and "Sold NEWSTEAD JENNIFER" in o["insiders"] and "Net shares +248,641" in o["insiders"]
    assert "The chart marks the 1 sale among the 2 latest filings Optic has, Oct 2 to Oct 6, 2026" in o["insiders"]
    assert "High today $345.99" in o["stats"] and "52-week low $243.42" in o["stats"]
    assert "Double top not confirmed" in o["patterns"] and "Inverted hammer" in o["patterns"]
    assert "276.13 Support −19.3% 61" in o["levels"]
    assert "Mildly bullish, 12 stories." in o["news"]
    assert "Stop from the entry plan" in o["stopcheck"]
    assert "0 of 7 for AAPL." in o["checklist"]
    assert "terms, the definitions the current app shows" in o["learn"]
    assert all(got["waiting"].values()), "a widget that reads the payload says it is loading until it arrives"
    assert got["terms"] == ["ATM", "Forward P/E", "Realised P&L", "YoY", "Iron condor"]


def test_a_daily_trade_lands_on_its_day(tmp_path):
    got = _run(tmp_path, f"""
      const W = await import('{(JS / "pages/chart-widgets.js").as_posix()}');
      const daily = ['2026-05-01', '2026-05-04', '2026-05-05'].map((s) => ({{ t: Date.parse(s) }}));
      const dk = daily.map((b) => W.barKey(b.t, false));
      print(JSON.stringify({{
        dk, got: [W.barTime(daily, dk, '2026-05-04'), W.barTime(daily, dk, '2026-05-04 10:25'), W.barTime(daily, dk, '2026-05-02'), W.barTime(daily, dk, '2026-04-30')],
        expect: daily[1].t,
      }}));
    """)
    assert got["dk"] == ["2026-05-01", "2026-05-04", "2026-05-05"]
    assert got["got"] == [got["expect"], got["expect"], None, None], "its day, an intraday trade on its day, and no bar no mark"


def test_intraday_and_weekly_charts_place_trades_by_minute_and_by_week(tmp_path):
    got = _run(tmp_path, f"""
      const W = await import('{(JS / "pages/chart-widgets.js").as_posix()}');
      const bar = (s) => ({{ t: Date.parse(s) }});
      const intra = ['2026-05-04T09:30:00-04:00', '2026-05-04T10:25:00-04:00', '2026-05-05T09:30:00-04:00'].map(bar);
      const ik = intra.map((b) => W.barKey(b.t, true));
      const weekly = ['2026-04-27', '2026-05-04'].map(bar);
      const wk = weekly.map((b) => W.barKey(b.t, false));
      print(JSON.stringify({{
        ik, intra: [W.barTime(intra, ik, '2026-05-04 10:25', {{ intraday: true }}), W.barTime(intra, ik, '2026-05-05', {{ intraday: true }}), W.barTime(intra, ik, '2026-05-06 10:00', {{ intraday: true }})],
        weekly: [W.barTime(weekly, wk, '2026-05-06', {{ weekly: true }}), W.barTime(weekly, wk, '2026-05-20', {{ weekly: true }})],
        expect: [intra[1].t, intra[2].t, weekly[1].t],
      }}));
    """)
    assert got["ik"] == ["2026-05-04 09:30", "2026-05-04 10:25", "2026-05-05 09:30"], "New York time, to the minute"
    e = got["expect"]
    assert got["intra"] == [e[0], e[1], None], "to the minute; a daily trade at its day's first bar; no bar that day, no mark"
    assert got["weekly"] == [e[2], None]


def test_the_chart_draws_what_the_open_widgets_ask_for():
    pc = (JS / "ui/pricechart.js").read_text()
    assert "(S.lines || []).forEach((l) => { o += hline(l.price, l.cls, l.label, l); });" in pc
    assert "(S.marks || []).forEach((m) => {" in pc and "<title>${esc(m.label)}</title>" in pc
    assert "...extras()," in CH and "function paintExtras() { if (chart) chart.set(extras()); }" in CH
    # what a widget draws goes with it: only the widgets on screen
    assert "W.onChart(shown())" in CH
    assert "shown.includes('backtest') && BT.show" in CW and "shown.includes('stopcheck') && SC.show" in CW


def test_the_rail_and_the_dock_on_the_page():
    assert "${W.rail(shown(), isPhone())}" in CH and 'role="toolbar" aria-label="Widgets"' in CW
    assert "const shown = () => (isPhone() ? V.dock.slice(-1) : V.dock.slice());" in CH, "one at a time on a phone"
    assert "dock: []" in CH and "dock: V.dock" in CH, "nothing open to start; the open ones remembered"
    assert "W.IDS.filter((id) => shown().includes(id))" in CH, "panels in the rail's order"
    # arrows move along the rail, a closed panel gives the focus back to its button
    assert "ArrowDown: i + 1, ArrowRight: i + 1, ArrowUp: i - 1, ArrowLeft: i - 1, Home: 0, End: all.length - 1" in CH
    assert "toggleWidget(id); const r = $(`[data-chw=\"${id}\"]`, mainEl); if (r) r.focus();" in CH
    # a result redraws after the event that asked for it, keeping the focused control and open details
    assert "pendingT = setTimeout(flushRepaints, 0)" in CH and "n.focus({ preventScroll: true })" in CH
    assert "the side widgets are in the current app" not in CH


def test_the_rail_follows_the_house_rules():
    rule = CSS[CSS.index(".chw-btn {"):CSS.index("}", CSS.index(".chw-btn {"))]
    assert "var(--r-ctl-in)" in rule and "var(--r-pill)" not in rule
    pressed = CSS[CSS.index('.chw-btn[aria-pressed="true"]'):]
    assert "gold" not in pressed[:pressed.index("}")], "the gold outline is the sidebar's alone"
    chw = "\n".join(line for line in CSS.splitlines() if ".chw" in line)
    sizes = [float(x) for x in re.findall(r"font(?:-size)?:[^;]*?(\d+(?:\.\d+)?)px", chw)]
    assert sizes and min(sizes) >= 12, "nothing under 12px"
    assert "@container chartpage (max-width: 1020px)" in CSS and "container: chartpage / inline-size" in CSS


# ------------------------------------------------------------ insider trades on the price (2026-10-19)

def test_insider_trades_become_arrows_with_the_words_for_their_box(tmp_path):
    payload = {"company": {"ownership": {"recent_transactions": [
        {"insider": "SMITH JANE", "position": "Director", "date": "2026-09-29", "shares": 2005.0, "value": 99987.0, "action": "purchase", "detail": "Purchase at price 49.87 per share."},
        {"insider": "COOK TIMOTHY D", "position": "Officer and Director", "date": "2026-10-02", "shares": 191753.0, "value": 63845841.0, "action": "sale", "detail": "Sale at price 331.44 - 333.94 per share."},
        {"insider": "COOK TIMOTHY D", "position": "Officer and Director", "date": "2026-10-02", "shares": 26325.0, "value": 0.0, "action": "other", "detail": "Stock Gift at price 0.00 per share."},
        {"insider": "NO DATE", "position": "", "date": "", "shares": 1.0, "value": 1.0, "action": "sale", "detail": ""},
    ]}}}
    got = _run(tmp_path, f"""
      const W = await import('{(JS / "pages/chart-widgets.js").as_posix()}');
      const day = (s) => ({{ t: Date.parse(s) }});
      const bars = ['2026-10-01', '2026-10-02', '2026-10-05'].map(day), keys = bars.map((b) => W.barKey(b.t, false));
      print(JSON.stringify({{
        marks: W.insiderMarks({json.dumps(payload)}),
        sat: [W.barTime(bars, keys, '2026-10-03', {{ within: 4 }}), W.barTime(bars, keys, '2026-10-03')], fri: bars[1].t,
      }}));
    """)
    m = got["marks"]
    assert [x["side"] for x in m] == ["buy", "sell"], "purchases and sales only: a gift or an exercise is pay, not a view"
    assert m[0] == {"at": "2026-09-29", "side": "buy", "date": "Sep 29, 2026", "value": 99987, "who": "SMITH JANE", "role": "Director",
                    "amount": "2,005 shares, $100.0K", "note": "Purchase at price 49.87 per share."}
    assert m[1]["amount"] == "191,753 shares, $63.8M"
    assert got["sat"] == [got["fri"], None], "a trade on a day with no session goes to the bar before it"


def test_the_arrows_their_box_and_the_switches():
    pc = (JS / "ui/pricechart.js").read_text()
    assert "if (S.overlays.ins !== false && (S.insiders || []).length) {" in pc
    assert "<path class=\"ins ${buy ? 'buy' : 'sell'}\"" in pc, "a green arrow for a purchase, a red one for a sale"
    assert "const k = `${i}${it.side}`" in pc, "one arrow for each side's trades in a bar"
    assert "tipEl.className = 'pc-tip'; tipEl.setAttribute('role', 'tooltip')" in pc
    assert "svg.offsetTop" not in pc, "an <svg> has no offsetTop; the box is placed from the two bounding boxes"
    assert "insider ${g.side === 'buy' ? 'purchase' : 'sale'}" in pc, "the keyboard's bar reads its trades aloud"
    assert "if (e.pointerType !== 'touch') hoverP = null;" in pc, "a tap opens the box and lifting the finger keeps it"
    # on by default, in Indicators and in the Insiders panel
    assert "['ins', 'Insider trades']" in CH and "events: true, ins: true }" in CH
    assert "insiders: place(ins, 4)" in CH
    assert "data-chw-ins" in CW and "if (el.matches('[data-chw-ins]')) { C.overlay('ins', el.checked); return true; }" in CW
    css = CSS[CSS.index(".pc .ins {"):]
    assert ".pc .ins.buy { fill: var(--c-pos); } .pc .ins.sell { fill: var(--c-neg); }" in css[:400]
