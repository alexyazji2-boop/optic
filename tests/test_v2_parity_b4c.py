"""Classic parity, batch B4c (2026-10-21): web search, Deep research and the research modes in Milo. The modes run in
JavaScriptCore against Classic's words; the rest are source checks. The interactions were driven in headless Chrome
against the stand-in model (~/Optic/work/classic-parity/b4c_check.py), which is stand-in verification: no real web
search or research ran. Ledger: docs/frontend-v2/CLASSIC-PARITY.md, B4c.
"""
from tests.test_frontend_v2_stage0 import V2, _run

JS = V2 / "js"
MILO = (JS / "ui/milo.js").read_text()
CLASSIC = (V2.parent / "app.js").read_text()


def test_the_modes_are_classics_words_for_each_page(tmp_path):
    got = _run(tmp_path, f"""
      globalThis.localStorage = {{ getItem: () => null, setItem: () => {{}}, removeItem: () => {{}} }};
      const M = await import('{(JS / "ui/milo.js").as_posix()}');
      const ids = (r) => M.researchModes(r).map((m) => m.id);
      print(JSON.stringify({{ co: ids({{ view: 'overview', symbol: 'AAPL' }}), chart: ids({{ view: 'chart', symbol: 'AAPL' }}), bk: ids({{ view: 'brokerage' }}),
        wl: ids({{ view: 'watchlist' }}), scan: ids({{ view: 'scan' }}), mkt: ids({{ view: 'home' }}), deep: M.researchModes({{ view: 'overview', symbol: 'AAPL' }}).filter((m) => m.deep).map((m) => m.text) }}));
    """)
    assert got["co"] == ["quick", "catalyst", "thesis", "risk", "deep"] and got["chart"] == ["chart", "levels", "catalyst"]
    assert got["bk"] == ["attention", "moved", "earnings", "exposure", "research"] and got["wl"] == ["risk", "events", "review"]
    assert got["scan"] == ["screen", "pick"] and got["mkt"] == ["quick", "catalyst", "deep"]
    assert got["deep"] == ["Deep research on AAPL: what has changed in the last two weeks, with sources, and does it change the thesis?"]
    for phrase in ("give the strongest bull case and the strongest bear case from the loaded data", "Separate what you measured from headlines that only match the timing.",
                   "What do the names on this screen have in common, and which stand out from the rest?"):
        assert phrase in CLASSIC and phrase in MILO, phrase


def test_web_and_research_spend_only_on_a_press_and_say_so():
    assert "const S = { files: [], web: false, deepHint: false," in MILO, "web search starts off"
    assert "S.panel = null; S.web = false; S.deepHint = false;" in MILO, "and is off again when the panel closes; never saved"
    assert "localStorage.setItem" not in MILO.split("function toolsHTML()")[1].split("function filesHTML()")[0]
    assert "web: !!S.web, attachments" in MILO and "fetch(deep ? '/api/research' : '/api/chat'" in MILO
    assert "Each search adds to what a question costs." in MILO and "Uses one Milo question and several web searches." in MILO
    assert "Each writes a question into the box. Nothing is sent until you press Send." in MILO
    assert "Web search was on for this answer." in MILO and "Deep research: read from live web sources." in MILO
