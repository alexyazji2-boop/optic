"""Classic parity, batch B4d (2026-10-21): saving questions and Saved research at #/research. The record handling runs
in JavaScriptCore against Classic's formats; the rest are source checks. The interactions were driven in headless
Chrome, signed in and as a guest (~/Optic/work/classic-parity/b4d_check.py). Ledger: CLASSIC-PARITY.md, B4d.
"""
from tests.test_frontend_v2_stage0 import V2, _run

JS = V2 / "js"
RES = (JS / "core/research.js").read_text()
CLASSIC = (V2.parent / "app.js").read_text()


def test_both_stores_are_read_in_classics_shapes_old_and_partial_records_too(tmp_path):
    got = _run(tmp_path, f"""
      globalThis.localStorage = {{ getItem: () => null, setItem: () => {{}}, removeItem: () => {{}} }};
      const R = await import('{(JS / "core/research.js").as_posix()}');
      print(JSON.stringify({{
        local: R.normalise({{ question: 'Is NVDA priced for perfection?', ticker: 'nvda', at: '2026-10-10T14:00:00Z' }}, 'browser'),
        partial: R.normalise({{ question: 'What moves the market?' }}, 'browser'),
        row: R.normalise({{ id: 'r1', title: 'T', content: 'Why did MSFT move?', symbol: 'MSFT', research_type: 'pulse', created_at: '2026-10-18T10:00:00Z' }}, 'account'),
        bad: [R.normalise({{ bad: 1 }}, 'browser'), R.normalise('nonsense', 'browser'), R.normalise(null, 'browser')],
        same: R.sameQuestion('Why  did MSFT move? ', 'why did msft move?'), key: R.RESEARCH_KEY, max: R.LOCAL_MAX }}));
    """)
    assert got["local"] == {"id": None, "question": "Is NVDA priced for perfection?", "symbol": "NVDA", "at": "2026-10-10T14:00:00Z", "where": "browser"}
    assert got["partial"] == {"id": None, "question": "What moves the market?", "symbol": None, "at": None, "where": "browser"}
    assert got["row"]["question"] == "Why did MSFT move?" and got["row"]["symbol"] == "MSFT" and got["row"]["id"] == "r1"
    assert got["bad"] == [None, None, None] and got["same"] is True
    assert got["key"] == "optic.research.v1" and got["max"] == 40
    assert "const RESEARCH_KEY = 'optic.research.v1';" in CLASSIC and "all.slice(0, 40)" in CLASSIC


def test_saving_writes_what_classic_writes():
    assert "api.post('/api/saved-research', { title: q.slice(0, 200), symbol: sym, content: q, research_type: 'pulse' })" in RES
    assert "title: question.slice(0, 200)," in CLASSIC and "research_type: 'pulse'," in CLASSIC
    assert "all.unshift({ question: q, ticker: sym, at: new Date().toISOString() });" in RES, "Classic's local record"
    assert "localStorage.setItem(RESEARCH_KEY, JSON.stringify(all.slice(0, LOCAL_MAX)))" in RES


def test_the_hub_is_routed_linked_and_drafts_only():
    assert "SLUG_VIEW.research = 'saved';" in (JS / "core/router.js").read_text()
    assert "saved: 'discover'" in (JS / "nav.js").read_text(), "no new sidebar item: the hub is reached from the account sheet, the palette and Milo"
    app = (JS / "app.js").read_text()
    assert '<a class="rail-row" href="#/research">Saved research</a>' in app and "saved: P.saved" in app
    assert "{ view: 'saved', label: 'Saved research', href: '#/research'" in (JS / "ui/palette.js").read_text()
    page = (JS / "pages/saved.js").read_text()
    assert "openMilo({ question: x.question, opener: b, symbol: x.symbol || '', about: 'Saved research' })" in page and "send(" not in page and "sendNow" not in page and "send: true" not in page
    for phrase in ("Which names look strongest right now?", "Deep research runs live web sources and cites them. Slower, and rate limited."):
        assert phrase in page and phrase in CLASSIC
    milo = (JS / "ui/milo.js").read_text()
    assert "const savable = String(m.content || '').trim().length > 12;" in milo and "const savable = role === 'user' && text && text.length > 12;" in CLASSIC
    assert "const r = await saveQuestion({ question: a.question, symbol: sym });" in milo, "Milo's own save action, the same store"
