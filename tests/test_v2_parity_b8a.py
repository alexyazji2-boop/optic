"""Classic parity, batch B8a (2026-10-21): Home's What matters today and the Desk. The pure rules run in
JavaScriptCore: where each dated row falls on the week of trading days (Classic's catalystPlacement), a released
result in place of "Out", the words for a result, a row's key surviving "reports" becoming "reported", and the Desk in
full with the reason its written version is not showing. The strip's notes, rows kept open across a repaint and the
phone fit were driven in headless Chrome (~/Optic/work/classic-parity/b8a_check.py). The server's results are
tests/test_home_results.py. These tests are not interaction evidence. Ledger: docs/frontend-v2/CLASSIC-PARITY.md, B8a.
"""
from tests.test_frontend_v2_stage0 import V2, _run

JS = V2 / "js"
HOME = (JS / "pages/home.js").read_text()
WS = (JS / "pages/workspace.js").read_text()
CLASSIC = (V2.parent / "app.js").read_text()
BOARD = """{ horizon_days: 5, closed_days: { '2026-10-26': 'Test holiday' }, columns: [
  { id: 'events', rows: [
    { kind: 'event', impact: 'low', title: 'Wage earnings', date: '2026-10-21', time: '10:00 AM ET', why: 'Wages.' },
    { kind: 'event', impact: 'high', title: 'Producer Price Index', short: 'PPI', date: '2026-10-21', time: '8:30 AM ET', released: true, why: 'Prices.', result: { short: '+1.3%', text: 'PPI +1.3%.' } },
    { kind: 'event', impact: 'high', title: 'Retail Sales', short: 'Retail sales', date: '2026-10-21', time: '8:30 AM ET', released: true, why: 'Spending.', result: { pending: true, text: 'Released; waiting.' } },
    { kind: 'event', impact: 'medium', title: 'CFTC Commitments of Traders', short: 'COT', days_away: 2, time: '3:30 PM ET' },
    { kind: 'event', impact: 'high', title: 'Far away', date: '2026-11-30' }] },
  { id: 'earnings', rows: [
    { kind: 'earnings', impact: 'medium', ticker: 'ABT', title: 'ABT reported Wednesday', when: 'Wednesday', date: '2026-10-21', result: { short: 'In line', text: 'EPS 1.42 against 1.41 expected: in line.' } },
    { kind: 'earnings', impact: 'high', ticker: 'BX', title: 'BX reports Thursday', when: 'Thursday', date: '2026-10-22' },
    { kind: 'earnings', impact: 'medium', ticker: 'GM', title: 'GM reported Tuesday', when: 'Tuesday', date: '2026-10-20', result: { short: 'Beat' } }] }] }"""


def test_the_week_as_trading_days(tmp_path):
    got = _run(tmp_path, f"""
      const H = await import('{(JS / "pages/home.js").as_posix()}');
      const r = H.catalystDays({BOARD}, '2026-10-21');
      print(JSON.stringify({{ placed: r.placed, days: r.days.map((d) => ({{ iso: d.iso, name: d.name, closed: d.closed, items: d.items.map((i) => [i.title, i.time, i.result, i.kind]) }})) }}));
    """)
    days = got["days"]
    assert [d["name"] for d in days] == ["Today", "Thu 22", "Fri 23", "Mon 26"], "no weekend, the horizon inclusive (Wed to Mon)"
    assert days[3]["closed"] == "Test holiday"
    assert days[0]["items"] == [["PPI", "+1.3%", True, "event"], ["Retail sales", "Out", False, "event"], ["ABT", "In line", True, "earnings"], ["Wage earnings", "10:00 AM ET", False, "event"]], \
        "high impact first; a release that is out says what it printed, or Out while its figures are on their way; a report by its ticker"
    assert days[1]["items"] == [["BX", "", False, "earnings"]], "no time invented for a report the feed dates only"
    assert days[2]["items"] == [["COT", "3:30 PM ET", False, "event"]], "placed by days away when there is no date"
    assert got["placed"] == 6, "yesterday's report and a release past the horizon stay in the list below"
    # Classic's rules: two shown a day, weekdays only, inclusive horizon capped at a week
    assert "const CATALYST_SHOWN = 2;" in CLASSIC and "Math.max(1, Math.min(7, Number.isFinite(p.horizon_days) ? p.horizon_days : 5))" in CLASSIC
    assert "const CATALYST_SHOWN = 2;" in HOME


def test_a_result_in_words(tmp_path):
    got = _run(tmp_path, f"""
      const H = await import('{(JS / "pages/home.js").as_posix()}');
      const {{ toString }} = await import('{(JS / "core/dom.js").as_posix()}');
      const w = (r) => toString(H.resultWords(r)).replace(/\\s+/g, ' ').trim();
      print(JSON.stringify({{
        out: w({{ text: 'PPI +1.3% for September 2026.', source: 'FRED (PPIFIS)', headline: 'PPI rises 1.3%', headline_source: 'BLS', headline_url: 'https://www.bls.gov/x', forecast_note: 'Against the previous print.' }}),
        pending: w({{ pending: true, text: 'Released; waiting.' }}), none: w(null) }}));
    """)
    assert '<b>PPI +1.3% for September 2026.</b> <span class="t-muted">FRED (PPIFIS).</span>' in got["out"]
    assert 'BLS: "PPI rises 1.3%"' in got["out"] and 'href="https://www.bls.gov/x" target="_blank" rel="noopener"' in got["out"] and "Against the previous print." in got["out"]
    assert got["pending"] == '<p class="ev-res is-pending">Released; waiting.</p>' and got["none"] == ""


def test_the_board_keeps_what_the_reader_opened(tmp_path):
    got = _run(tmp_path, f"""
      const H = await import('{(JS / "pages/home.js").as_posix()}');
      const {{ toString }} = await import('{(JS / "core/dom.js").as_posix()}');
      const b = {BOARD}; b.generated_at = '2026-10-21T13:00:00Z';
      const first = toString(H.eventsBlock(b, ['GM'], 'all'));
      const key = (first.match(/data-v2-ev="(earnings\\|BX\\|[^"]*)"/) || [])[1];
      const btn = {{ getAttribute: () => 'false', setAttribute() {{}}, dataset: {{ v2Ev: key }} }};
      document.getElementById = () => null;   // the stub document; the row's body is not on a page here
      H.evPress({{ closest: (sel) => (sel === '[data-v2-ev]' ? btn : null) }});
      b.columns[1].rows[1].title = 'BX reported Thursday'; b.columns[1].rows[1].result = {{ short: 'Beat', text: 'EPS up.' }};
      const again = toString(H.eventsBlock(b, ['GM'], 'all'));
      const row = again.slice(again.indexOf(`data-v2-ev="${{key}}"`) - 80, again.indexOf(`data-v2-ev="${{key}}"`) + 900);
      print(JSON.stringify({{ key, open: /aria-expanded="true"/.test(row), body: /class="ev-body" id="ev-[a-z0-9]+" >/.test(row), pill: /class="pill"/.test(first + again), mine: /On your list|on your list/.test(first) }}));
    """)
    assert got["key"] == "earnings|BX|2026-10-22|", "a report's key is its ticker and date, so 'reports' turning 'reported' keeps it"
    assert got["open"] and got["body"], "opened before the figures came in, still open after"
    assert not got["pill"] and got["mine"], "on your list said in the row's line, not a pill"
    assert "opened = [...body.querySelectorAll('details[data-v2-fold]')].filter((x) => x.open)" in WS and "if (top) body.scrollTop = top;" in WS, \
        "a repaint of any workspace panel keeps its named folds open and its scroll"


def test_the_desk_in_full(tmp_path):
    got = _run(tmp_path, f"""
      const H = await import('{(JS / "pages/home.js").as_posix()}');
      const {{ toString }} = await import('{(JS / "core/dom.js").as_posix()}');
      const md = {{ available: true, date: '2026-10-21', voice: 'mechanical', voice_reason: 'moved', written_at: '2026-10-21T13:40:00Z', rewriting: true,
        overall: 'Yields are down.', lead: ['First.', 'Second.'], scenarios: [{{ label: 'If yields fall', text: 'Rates help.' }}], note: 'A note.',
        calendar: [{{ title: 'Wages', time: '10:00 AM ET', impact: 'low', detail: 'Routine.' }}], limits: ['No consensus.', 'No flows.'],
        edition: {{ date: '2026-10-20', slot_label: 'Close', headline: 'A quiet day', summary: 'Little moved.', is_today: false }} }};
      const t = toString(H.deskBody(md)).replace(/\\s+/g, ' ');
      const w = toString(H.deskBody({{ available: true, voice: 'written', written_by: 'Claude', overall: 'x', lead: ['y'] }})).replace(/\\s+/g, ' ');
      print(JSON.stringify({{ t, w, order: ['desk-ed', 'desk-bottom', '<p>First.</p>', 'The whole desk', 'What could happen next', 'Today\\'s reports', 'What this does not tell you (2)', 'desk-why'].map((k) => t.indexOf(k)) }}));
    """)
    o = got["order"]
    assert all(i >= 0 for i in o) and o == sorted(o), "the edition, the bottom line, the lead, then the rest folded, the limits counted, why last"
    t = got["t"]
    assert "Latest edition, Oct 20, Close" in t and 'href="#/read"' in t, "an earlier day's edition says so rather than passing as today's"
    assert "The written version from 9:40 AM ET is not shown, because the market has moved since it was written" in t and "A new one is being written" in t
    assert "Written for today by an AI model (Claude) from the day&#39;s figures and nothing else." in got["w"] and "desk-why" not in got["w"]
    assert "The written version${at ? ` from ${at}` : ''} is not shown, because the market has `" in CLASSIC, "Classic's reason, kept"
    assert "return deskBody(md);" in WS
