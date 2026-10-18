"""Stage 0 of the v2 switch-over: Milo's answer rendering, the palette's
reading of what was typed, link safety, and the valuation body that both apps
save. Pure functions, run in JavaScriptCore like test_frontend_v2.py."""
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

V2 = Path(__file__).resolve().parent.parent / "static" / "v2"
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc"
STUBS = """
  globalThis.window = { addEventListener() {}, matchMedia() { return { matches: false, addEventListener() {} }; } };
  globalThis.location = { hash: '', pathname: '/v2/', search: '' };
  const mem = {};
  globalThis.localStorage = { getItem: (k) => (k in mem ? mem[k] : null), setItem: (k, v) => { mem[k] = String(v); }, removeItem: (k) => { delete mem[k]; } };
  globalThis.sessionStorage = globalThis.localStorage;
  globalThis.document = { documentElement: { dataset: {}, style: {}, setAttribute() {}, removeAttribute() {} }, addEventListener() {}, querySelector() { return null; }, querySelectorAll() { return []; }, createElement() { return { style: {}, setAttribute() {}, appendChild() {}, addEventListener() {}, classList: { add() {}, remove() {}, toggle() {} } }; }, body: { appendChild() {}, classList: { add() {}, remove() {}, toggle() {} } }, cookie: '' };
  globalThis.navigator = { onLine: true };
  globalThis.matchMedia = window.matchMedia;
"""


def _run(tmp_path, body):
    exe = JSC if os.path.exists(JSC) else shutil.which("jsc")
    if not exe:
        pytest.skip("jsc not available")
    script = tmp_path / "check.mjs"
    script.write_text(STUBS + body)
    out = subprocess.run([exe, "-m", str(script)], capture_output=True, text=True, timeout=30)
    assert out.returncode == 0, out.stderr + out.stdout
    return json.loads(out.stdout.strip().splitlines()[-1])


def test_milo_answers_render_sources_charts_actions_and_follow_ups(tmp_path):
    got = _run(tmp_path, f"""
      const m = await import('{(V2 / "js/core/milo-text.js").as_posix()}');
      const text = 'Apple trades at **30 times** earnings [[src framework]].\\n\\n[[chart AAPL 6m]]\\n\\n[[action watch AAPL]]\\n\\n'
        + '[[action open MSFT options]]\\n\\n[[action level 210 "Support"]]\\n\\n[click](javascript:alert(1)) and [ok](https://www.sec.gov/x)\\n\\n'
        + '→ What would change this?\\n→ How does MSFT compare?';
      const r = m.renderAnswer(text, 'AAPL');
      print(JSON.stringify({{
        html: r.html, ups: r.ups,
        tail: m.streamingTail('Partly written [[src fram'),
        acts: [m.parseAction('open', ['msft', 'options']), m.parseAction('compare', ['AAPL']), m.parseAction('indicator', ['ema9']), m.parseAction('level', ['$1,234.5', 'Wall']), m.parseAction('delete', [])],
        args: m.actionArgs('AAPL "Main list" x'),
      }}));
    """)
    h = got["html"]
    assert "<strong>30 times</strong>" in h and "[[src" not in h
    assert 'data-v2-milo-chart="AAPL"' in h and 'data-span="6m"' in h
    assert "<p><figure" not in h                    # a tag alone in its paragraph is the block
    assert h.count('class="milo-act"') == 2           # at most two action cards per answer
    # only http(s) links become links; anything else stays as the text it was
    assert 'href="javascript' not in h and "<a href=\"javascript" not in h and 'href="https://www.sec.gov/x"' in h
    assert got["ups"] == ["What would change this?", "How does MSFT compare?"]
    assert got["tail"] == "Partly written"
    a = got["acts"]
    assert a[0]["kind"] == "open" and a[0]["sym"] == "MSFT" and a[0]["section"] == "options"
    assert "bad" in a[1] and "bad" not in a[2]
    assert a[3]["price"] == 1234.5 and a[3]["note"] == "Wall"
    assert "bad" in a[4]
    assert got["args"] == ["AAPL", "Main list", "x"]


def test_links_with_unsafe_schemes_are_neutralised(tmp_path):
    got = _run(tmp_path, f"""
      const d = await import('{(V2 / "js/core/dom.js").as_posix()}');
      const urls = ['javascript:alert(1)', ' JAVASCRIPT:x', 'data:text/html,x', '//evil.example/x', 'https://ok.example/a?b=1', '/classic#/AAPL', '#/scan', 'mailto:a@b.c', 'vbscript:x'];
      print(JSON.stringify(urls.map((u) => d.toString(d.html`<a href="${{u}}">x</a>`))));
    """)
    hrefs = [s.split('href="')[1].split('"')[0] for s in got]
    assert hrefs[:4] == ["#", "#", "#", "#"]
    assert hrefs[4].startswith("https://ok.example/a?b=1")
    assert hrefs[5:8] == ["/classic#/AAPL", "#/scan", "mailto:a@b.c"]
    assert hrefs[8] == "#"


def test_the_palette_reads_page_names_questions_tickers_and_screens(tmp_path):
    got = _run(tmp_path, f"""
      const p = await import('{(V2 / "js/ui/palette.js").as_posix()}');
      const places = p.PLACES.filter((x) => !x.owner && !x.brokerage);
      print(JSON.stringify({{
        exact: ['scan', 'Watchlist', 'paper desk', 'retirement', 'nvda'].map((q) => (p.exactPlace(q, places) || {{}}).label || null),
        q: ['why did nvda fall today?', 'is AAPL expensive', 'NVDA', 'scan'].map(p.looksLikeQuestion),
        t: ['NVDA', 'brk-b', '^GSPC', 'why', 'scan'].map(p.looksLikeTicker),
        screen: ['find cheap tech stocks with momentum', 'NVDA'].map(p.looksLikeScreen),
        sector: p.sectorMentioned('find cheap energy stocks'),
      }}));
    """)
    assert got["exact"][0] == "Scan" and got["exact"][1] == "Watchlist"
    assert got["exact"][2] == "Paper Desk" and got["exact"][3] == "Retirement"
    assert got["exact"][4] is None                  # a ticker is not a page
    assert got["q"] == [True, True, False, False]
    assert got["t"][:2] == [True, True] and got["t"][2] is False   # an index goes through search, not the ticker guess
    assert got["screen"] == [True, False]
    assert got["sector"]


def test_a_v2_valuation_save_keeps_what_the_classic_app_wrote(tmp_path):
    got = _run(tmp_path, f"""
      const v = await import('{(V2 / "js/pages/valuation-scenarios.js").as_posix()}');
      // a stored body as the classic app's valuationBodyOf writes it
      const prev = {{ v: 1, shared: {{ years: 5, required_return: null, revenue: 3e11, shares: null }},
        bear: {{ note: '', growth: null, margin: null, share_change: null, pe: null }},
        base: {{ note: 'Mine', growth: 8, margin: 30, share_change: -1, pe: 28 }},
        bull: {{ note: '', growth: null, margin: null, share_change: null, pe: null }},
        from_history: ['base.growth', 'base.margin'] }};
      const box = (x) => ({{ value: x === null || x === undefined ? '' : String(x) }});
      const form = {{}};
      ['years', 'required_return', 'revenue', 'shares'].forEach((k) => {{ form[`shared.${{k}}`] = box(prev.shared[k]); }});
      ['bear', 'base', 'bull'].forEach((c) => ['growth', 'margin', 'share_change', 'pe', 'note'].forEach((k) => {{ form[`${{c}}.${{k}}`] = box(prev[c][k]); }}));
      form['base.margin'] = box('31');          // the reader typed over a figure filled from history
      form['shared.revenue'] = box('300B');
      const body = v.readForm(form, prev);
      const blank = v.emptyBody(); blank.base.note = 'kept';
      print(JSON.stringify({{ body, amounts: ['394B', '2.5t', '1,000', 'x', ''].map(v.amount), emptyWithNote: v.isEmpty(blank), empty: v.isEmpty(v.emptyBody()) }}));
    """)
    b = got["body"]
    assert b["v"] == 1 and b["shared"]["revenue"] == 3e11 and b["shared"]["years"] == 5
    assert b["shared"]["required_return"] is None   # a blank box stays blank, not a default
    assert b["base"]["note"] == "Mine" and b["bear"]["note"] == ""
    assert b["base"]["margin"] == 31 and b["base"]["pe"] == 28
    assert b["from_history"] == ["base.growth"]     # the typed-over box is the reader's now
    # NaN for an unreadable amount, which JSON carries as null like the blank one
    assert got["amounts"] == [394e9, 2.5e12, 1000, None, None]
    assert got["emptyWithNote"] is False and got["empty"] is True


def test_market_structure_breaks_follow_confirmed_swings_only(tmp_path):
    """The chart's MSB study (ui/pricechart.js marketStructure): a close above
    the latest confirmed swing high is a bullish break, below the latest
    swing low a bearish one, each level breaks once, and a swing counts only
    after the 3 bars on its right have closed."""
    got = _run(tmp_path, f"""
      const p = await import('{(V2 / "js/ui/pricechart.js").as_posix()}');
      // high, low, close per bar; o = c
      const raw = [[100, 98, 99], [101, 99, 100], [102, 100, 101], [101, 99, 100], [105, 101, 104],
                   [110, 104, 106], [106, 102, 103], [105, 101, 102], [104, 100, 101], [106, 101, 105],
                   [108, 104, 107], [109, 105, 108], [112, 107, 111], [113, 108, 112], [111, 106, 107],
                   [108, 99, 100], [104, 97, 98], [103, 96, 97], [102, 95, 96], [100, 90, 91]];
      const bars = raw.map(([h, l, c], i) => ({{ t: i, o: c, h, l, c }}));
      const all = p.marketStructure(bars, 3);
      // the same series cut before the swing high's 3rd right-hand bar: nothing is confirmed yet
      const early = p.marketStructure(bars.slice(0, 8), 3);
      print(JSON.stringify({{ all, early }}));
    """)
    breaks = got["all"]
    assert breaks[0] == {"dir": "bull", "from": 5, "at": 12, "price": 110}   # close 111 above the 110 swing high of bar 5
    bears = [b for b in breaks if b["dir"] == "bear"]
    assert bears and bears[0]["price"] < 105 and bears[0]["at"] >= 15     # a later close below the latest swing low
    assert len({(b["dir"], b["from"]) for b in breaks}) == len(breaks)     # each level breaks once
    assert got["early"] == []
