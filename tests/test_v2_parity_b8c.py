"""Classic parity, batch B8c (2026-10-21): Today's Read built on the reader's press, and ticker suggestions on Analysts
and Compare. The pure rules run in JavaScriptCore: which suggestion an Enter with nothing highlighted means (Classic's
typedNamePick) and the typed text marked in a suggestion, escaped. The build (none on load, its cost said first, one
request on the press) and the suggestions (keys, mouse, emulated touch, phones) were driven in headless Chrome
(~/Optic/work/classic-parity/b8c_check.py). These tests are not interaction evidence. Ledger:
docs/frontend-v2/CLASSIC-PARITY.md, B8c.
"""
from tests.test_frontend_v2_stage0 import V2, _run

JS = V2 / "js"
CLASSIC = (V2.parent / "app.js").read_text()
READ = (JS / "pages/read.js").read_text()
CMP = (JS / "pages/compare.js").read_text()
AN = (JS / "pages/analysts.js").read_text()


def test_which_suggestion_an_enter_means(tmp_path):
    got = _run(tmp_path, f"""
      const T = await import('{(JS / "ui/typeahead.js").as_posix()}');
      const items = [{{ symbol: 'AAPL', name: 'Apple Inc' }}, {{ symbol: 'APLE', name: 'Apple Hospitality REIT, Inc' }}, {{ symbol: 'F', name: 'Ford Motor Company' }}];
      const p = (q, listed = q) => T.typedNamePick(items, listed, q);
      print(JSON.stringify([p('apple'), p('hospitality'), p('F'), p('aapl'), p('BRK-B'), p('apple', 'appl'), p(''), p('zzz')]));
    """)
    assert got == [0, 1, -1, -1, -1, -1, -1, -1], "a typed name takes its company; a symbol, a symbol-like text, or a list for an earlier keystroke is taken as typed"
    assert "function typedNamePick(items, listedFor, typed)" in CLASSIC and "if (/[\\^=.\\-]/.test(q)) return -1;" in CLASSIC


def test_the_typed_text_is_marked_and_escaped(tmp_path):
    got = _run(tmp_path, f"""
      const T = await import('{(JS / "ui/typeahead.js").as_posix()}');
      print(JSON.stringify([T.marked('Apple Inc', 'appl'), T.marked('AT&T <Inc>', 't&t'), T.marked('NVIDIA', 'zz'), T.marked('', 'a')]));
    """)
    assert got == ["<b>Appl</b>e Inc", "A<b>T&amp;T</b> &lt;Inc&gt;", "NVIDIA", ""]


def test_the_boxes_use_it():
    assert "data-v2-ta" in AN and "typeahead(main, (pick) => { Q.ticker = String(pick.symbol).toUpperCase(); load(); });" in AN
    assert "data-v2-ta value=" in CMP and "<datalist" not in CMP and "typeahead(main, (pick, input) =>" in CMP, "Compare's native datalist is replaced"
    assert "attachTypeahead('an-ticker'" in CLASSIC and "attachTypeahead(`cmp-input-${i}`" in CLASSIC


def test_the_read_is_built_only_on_the_readers_press():
    assert "api.get('/api/brief?cached=true'" in READ, "the page asks only for what is built, so loading it cannot start a model write"
    load = READ.split("export async function render(main)")[1].split("\n}\n")[0]
    assert "api.get('/api/brief'," not in load
    assert "if (b('[data-v2-read-build]')) { buildRead(); return; }" in READ and "let r = await api.get('/api/brief', { ttl: 0, force: true, timeout: 120000 });" in READ
    assert "an AI model writes the summary: one model call for this edition, shared by every reader" in READ, "the cost is said before the press"
    assert "The classic app can build it on request" not in READ
