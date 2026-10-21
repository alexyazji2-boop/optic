"""Classic parity, batch B5 (2026-10-21): the alerts inbox, setup alerts and signal history. The pure rules run in
JavaScriptCore: the urgency groups and filters, the readings, and signal history's browser store in Classic's format
(optic.signals.v1), with old and partial records and a reply that must not replace what was recorded. The
interactions (filters, why it fired, mark read, Clear all and its confirmation, the delivery note, the filters asked
of the server, setting a setup alert on the account and in the browser, a page check that fires one) were driven in
headless Chrome against fixtures, at 1440, 1024, 430, 390 and 360 (~/Optic/work/classic-parity/b5_check.py, touch
emulated). These tests are not interaction evidence. Ledger: docs/frontend-v2/CLASSIC-PARITY.md, B5.
"""
from tests.test_frontend_v2_stage0 import V2, _run

JS = V2 / "js"
ALERTS = (JS / "pages/alerts.js").read_text()
SIGNALS = (JS / "pages/signals.js").read_text()
CLASSIC = (V2.parent / "app.js").read_text()

ROWS = """[
  { id: 5, kind: 'idea', urgency: 'normal', seen: 0, created_at: '2026-10-21T15:10:00Z' },
  { id: 4, kind: 'risk', urgency: 'high', seen: 0, created_at: '2026-10-21T15:00:00Z' },
  { id: 3, kind: 'pattern', urgency: 'low', seen: 1, created_at: '2026-10-21T14:30:00Z' },
  { id: 2, kind: 'idea', seen: 1, created_at: '2026-10-21T14:10:00Z' },
  { id: 1, kind: 'closed', urgency: 'high', seen: 0, created_at: '2026-10-21T14:05:00Z' }]"""


def test_the_book_reads_by_urgency_and_its_filters(tmp_path):
    got = _run(tmp_path, f"""
      const A = await import('{(JS / "pages/alerts.js").as_posix()}');
      const g = (k, u) => A.bookGroups({ROWS}, k, u).map((x) => x.id + ':' + x.rows.map((r) => r.id).join(','));
      print(JSON.stringify({{ urg: A.URGENCY, all: g('all', false), idea: g('idea', false), unread: g('all', true), none: g('risk', true).length === 1 ? 'ok' : 'x',
        rd: A.readings({{ exit_price: 182.4, id: 'x', dedupe_key: 'k', ticker: 'N', nested: {{ a: 1 }}, empty: '', flag: true, n: 3, a: 1, b: 2, c: 3, d: 4, e: 5 }}),
        off: A.deliveryNote({{ enabled: true }}, false), none2: A.deliveryNote({{ enabled: false, blockers: [] }}, true) }}));
    """)
    assert got["urg"] == [["high", "Needs attention"], ["normal", "Worth knowing"], ["low", "For the record"]]
    assert got["all"] == ["high:4,1", "normal:5,2", "low:3"], "an alert without an urgency is 'normal', as the server says"
    assert got["idea"] == ["normal:5,2"] and got["unread"] == ["high:4,1", "normal:5"]
    assert got["rd"][0] == ["Exit price", "182.40"] and ["Flag", "true"] in got["rd"] and len(got["rd"]) == 8
    assert not any(k in ("Id", "Dedupe key", "Ticker", "Nested", "Empty") for k, _ in got["rd"])
    assert got["off"] == "" and got["none2"] == "", "the note is the owner's, and says nothing when there is nothing to say"
    for label in ("Needs attention", "Worth knowing", "For the record"):
        assert f"label: '{label}'" in CLASSIC, "Classic's ALERT_URGENCY, word for word"


def test_the_inbox_controls_are_the_owners(tmp_path):
    assert "const isOwner = () => !!(store.state.me && store.state.me.admin);" in ALERTS
    book = ALERTS[ALERTS.index("function bookRow("):ALERTS.index("const bookSub")]
    assert "fresh = owner && !x.seen" in book, "a reader sees no unread marks: the read state is the owner's"
    assert "${owner ? html`<label class=\"check\"><input type=\"checkbox\" data-v2-book-unread" in book
    assert "${owner ? html`<div class=\"cluster al-owner\">" in book, "Mark all read and Clear all, the owner's only"
    assert "This clears them for every reader and cannot be undone." in book, "Clear all asks first, in the page"
    assert "await api.post('/api/alerts/seen', ids ? { ids } : {})" in ALERTS and "await api.post('/api/alerts/clear', {})" in ALERTS


def test_signal_history_keeps_classics_browser_format(tmp_path):
    got = _run(tmp_path, f"""
      const S = await import('{(JS / "pages/signals.js").as_posix()}');
      // Classic's own record, an old partial one, and junk alongside
      localStorage.setItem(S.SIGNALS_KEY, JSON.stringify({{ signals: [
        {{ signal_key: 'T|rsi_50|bull|2026-10-09', symbol: 'T', strategy: 'rsi_50', strategy_label: 'RSI reclaims 50', direction: 'bull', trigger_at: '2026-10-09', trigger_price: 240.5, params: {{ signal_ttl: 10 }} }},
        {{ signal_key: 'A|macd|bear|2026-10-16', symbol: 'A', strategy: 'macd', direction: 'bear', trigger_at: '2026-10-16' }}, null, {{ symbol: 'NOKEY' }}],
        events: {{ 'T|rsi_50|bull|2026-10-09': [{{ kind: 'observation', label: 'after 1 candle', data_as_of: '2026-10-10', price: 243, change_pct: 1.04, observed_at: '2026-10-10T21:00:00Z' }}] }} }}));
      const body = S.followupBody();
      S.keepFollowup({{ events: {{
        'T|rsi_50|bull|2026-10-09': [{{ kind: 'observation', label: 'after 1 candle', price: 999 }}, {{ kind: 'observation', label: 'after 5 candles', data_as_of: '2026-10-16', price: 251, change_pct: 4.37 }}],
        'A|macd|bear|2026-10-16': [{{ kind: 'status', label: 'invalidated', data_as_of: '2026-10-17' }}, {{ kind: 'status', label: 'expired' }}],
        'NOT|MINE': [{{ kind: 'status', label: 'expired' }}] }} }}, '2026-10-21T20:00:00Z');
      const st = JSON.parse(localStorage.getItem(S.SIGNALS_KEY));
      const rows = S.localRows(st, {{ 'A|macd|bear|2026-10-16': [{{ horizon: 1, state: 'missing' }}, {{ horizon: 5, state: 'pending' }}] }});
      // a record seen again is not kept twice; past 200, the oldest go with what followed them
      const again = S.keepSignal({{ signal_key: 'T|rsi_50|bull|2026-10-09', symbol: 'T' }});
      localStorage.setItem(S.SIGNALS_KEY, JSON.stringify({{ signals: Array.from({{ length: 200 }}, (_, i) => ({{ signal_key: 'k' + i, trigger_at: i ? '2026-01-' + String(1 + (i % 28)).padStart(2, '0') : '2025-12-31' }})), events: {{ k0: [1] }} }}));
      S.keepSignal({{ signal_key: 'new', trigger_at: '2026-10-20' }}, '2026-10-21T00:00:00Z');
      const capped = JSON.parse(localStorage.getItem(S.SIGNALS_KEY));
      localStorage.setItem(S.SIGNALS_KEY, 'nonsense');
      print(JSON.stringify({{ body, st, rows: rows.map((r) => [r.signal_key, r.status, r.horizons.map((h) => h.state + (h.change_pct != null ? ':' + h.change_pct : '')).join(' ')]),
        again, capped: [capped.signals.length, capped.signals[0].signal_key, capped.signals[0].origin, capped.signals[0].recorded_at, 'k0' in capped.events || capped.signals.some((x) => x.signal_key === 'k0')],
        junk: S.readLocal(), labels: S.HORIZONS.map(S.horizonLabel) }}));
    """)
    assert [b["signal_key"] for b in got["body"]] == ["A|macd|bear|2026-10-16", "T|rsi_50|bull|2026-10-09"], "newest trigger first; the keyless record is skipped"
    assert got["body"][1] == {"signal_key": "T|rsi_50|bull|2026-10-09", "symbol": "T", "direction": "bull", "trigger_at": "2026-10-09", "trigger_price": 240.5, "params": {"signal_ttl": 10}}
    st = got["st"]
    assert set(st) == {"signals", "events"} and len(st["signals"]) == 4, "the store keeps its shape and every record, untouched"
    t = st["events"]["T|rsi_50|bull|2026-10-09"]
    assert [(e["label"], e["price"]) for e in t] == [("after 1 candle", 243), ("after 5 candles", 251)], "the first reading is never replaced"
    assert t[1]["observed_at"] == "2026-10-21T20:00:00Z" and t[0]["observed_at"] == "2026-10-10T21:00:00Z"
    assert [e["label"] for e in st["events"]["A|macd|bear|2026-10-16"]] == ["invalidated"], "one status per signal"
    assert "NOT|MINE" not in st["events"], "a reply's keys for records this browser does not hold are ignored"
    assert got["rows"] == [["A|macd|bear|2026-10-16", "invalidated", "missing pending unknown unknown"],
                           ["T|rsi_50|bull|2026-10-09", "unresolved", "observed:1.04 observed:4.37 unknown unknown"]]
    assert got["again"] is False
    assert got["capped"][:4] == [200, "new", "alert check on the page", "2026-10-21T00:00:00Z"] and got["capped"][4] is False, "the oldest went, with what followed it"
    assert got["junk"] == {"signals": [], "events": {}} and got["labels"] == ["after 1 candle", "after 5 candles", "after 10 candles", "after 20 candles"]
    # the label is the server's, so a horizon recorded by either app is found by the other
    assert 'label = "after {} candle{}".format(h, "" if h == 1 else "s")' in (V2.parent.parent / "app/signal_history.py").read_text()
    assert "const SIGNALS_KEY = 'optic.signals.v1';" in CLASSIC and "SIGNALS_LOCAL_MAX = 200" in CLASSIC


def test_signal_filters_and_their_query(tmp_path):
    got = _run(tmp_path, f"""
      const S = await import('{(JS / "pages/signals.js").as_posix()}');
      const rows = [{{ symbol: 'B', strategy: 'x', status: 'unresolved', direction: 'bull' }}, {{ symbol: 'A', strategy: 'y', strategy_label: 'Why', status: 'expired', direction: 'bear' }}, {{ symbol: 'B', strategy: 'z', status: 'invalidated', direction: 'bear' }}];
      const f = (o) => Object.assign({{ status: 'all', direction: 'all', symbol: '', strategy: '' }}, o);
      print(JSON.stringify({{
        q0: S.query(f({{}})), q1: S.query(f({{ status: 'invalidated', direction: 'bear', symbol: 'BRK.B', strategy: 'rsi_50' }})),
        local: S.rowsShown({{ where: 'browser', signals: rows }}, f({{ direction: 'bear', symbol: 'B' }})).map((r) => r.strategy),
        account: S.rowsShown({{ where: 'account', signals: rows }}, f({{ direction: 'bull' }})).length,
        opts: S.optionsOf(rows, {{ x: 'Ex', z: 'Zed' }}), def: [S.filtersDefault(f({{}})), S.filtersDefault(f({{ symbol: 'A' }}))] }}));
    """)
    assert got["q0"] == "/api/signals" and got["q1"] == "/api/signals?status=invalidated&direction=bear&symbol=BRK.B&strategy=rsi_50"
    assert got["local"] == ["z"] and got["account"] == 3, "the account's rows come filtered by the server"
    assert got["opts"] == {"symbols": ["A", "B"], "strategies": [{"id": "x", "label": "Ex"}, {"id": "y", "label": "Why"}, {"id": "z", "label": "Zed"}]}
    assert got["def"] == [True, False]


def test_a_setup_alert_is_classics_swing_setup_watch(tmp_path):
    got = _run(tmp_path, f"""
      const W = await import('{(JS / "core/watches.js").as_posix()}');
      localStorage.setItem(W.LOCAL_KEY, JSON.stringify([{{ id: 'local-old', symbol: 'MSFT', kind: 'price_above', params: {{ level: 300 }}, active: true }}, {{ id: 'gone', symbol: 'X', kind: 'move_pct', params: {{}}, deleted_at: '2026-10-01' }}]));
      const made = await W.addAlert({{ symbol: 'aapl', kind: 'swing_setup', params: {{ preset: 'rsi_50' }} }});
      let dup = ''; try {{ await W.addAlert({{ symbol: 'AAPL', kind: 'swing_setup', params: {{ preset: 'rsi_50' }} }}); }} catch (e) {{ dup = e.message; }}
      const list = JSON.parse(localStorage.getItem(W.LOCAL_KEY));
      localStorage.setItem(W.LOCAL_KEY, JSON.stringify(Array.from({{ length: 40 }}, (_, i) => ({{ id: 'l' + i, symbol: 'S' + i, kind: 'move_pct', params: {{}} }}))));
      let full = ''; try {{ await W.addAlert({{ symbol: 'AAPL', kind: 'swing_setup', params: {{ preset: 'any' }} }}); }} catch (e) {{ full = e.message; }}
      print(JSON.stringify({{ made, dup, list, full }}));
    """)
    m = got["made"]
    assert m["symbol"] == "AAPL" and m["kind"] == "swing_setup" and m["params"] == {"preset": "rsi_50"} and m["active"] is True and m["id"].startswith("local-")
    assert {"created_at", "last_met_at", "last_evidence"} <= set(m), "Classic's addWatchDef fields, so Classic reads it"
    assert got["dup"] == "You already have that alert on AAPL."
    assert [w["id"] for w in got["list"]][:1] == ["local-old"] and len(got["list"]) == 2, "the other alerts are kept, in order"
    assert got["full"] == "That is 40 alerts, which is the limit. Delete one to add another."
    assert "addWatchDef(row.symbol, 'swing_setup', { preset: row.preset })" in CLASSIC
    panels = (JS / "pages/options-panels.js").read_text()
    assert 'data-v2-setup-alert="${r.preset}"' in panels and "Filters, rule settings and back-tests for setups are in the" in panels
    assert "await addAlert({ symbol: sym, kind: 'swing_setup', params: { preset: b.dataset.v2SetupAlert } });" in (JS / "pages/options.js").read_text()


def test_signal_history_is_shown_as_recorded():
    assert "never an option's price or a trade's result" in SIGNALS
    assert "'None: this rule sets no target'" in SIGNALS and "'not recorded'" in SIGNALS, "a missing value says so; no number is made up"
    assert 'aria-label="The stock\'s close after 1, 5, 10 and 20 completed candles"' in SIGNALS
    assert "html`${horizonCell(h)} `" in SIGNALS, "the cells are spaced, so a screen reader does not run them together"
    assert "main.addEventListener('toggle'" in ALERTS and ", true);" in ALERTS.split("main.addEventListener('toggle'")[1].split("\n")[0], "an open record stays open across repaints"
    assert "/api/chat" not in SIGNALS and "/api/research" not in SIGNALS, "no model is called"
