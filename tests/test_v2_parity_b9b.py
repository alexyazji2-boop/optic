"""Classic parity, batch B9b (2026-10-21): glossary terms marked on eligible text, once per section, header labels
explained whole, "Explain this with Milo", and nothing marked at Professional. The pure rules run in JavaScriptCore:
what the matcher finds, the Professional rule, Classic's label definitions word for word, and the Milo question. The
marking on real pages (skipped places, once per section, a redraw), the press, keys, hover, touch and the Milo draft
were driven in headless Chrome (~/Optic/work/classic-parity/b9b_check.py). These tests are not interaction evidence.
Ledger: docs/frontend-v2/CLASSIC-PARITY.md, B9b.
"""
import re

from tests.test_frontend_v2_stage0 import V2, _run

JS = V2 / "js"
CLASSIC = (V2.parent / "app.js").read_text()
GM = (JS / "ui/glossmark.js").read_text()
APP = (JS / "app.js").read_text()


def test_the_matcher_and_the_level(tmp_path):
    got = _run(tmp_path, f"""
      const G = await import('{(JS / "ui/glossmark.js").as_posix()}');
      const find = (t) => {{ const m = G.TERM_RE.exec(t); return m ? m[1] : null; }};
      print(JSON.stringify({{
        hits: ['The forward P/E is 28.', 'Dealer gamma flips here.', 'Free cash flow rose.', 'EPS beat.', 'a put/call ratio of 0.8', 'Its realised P&L is up.'].map(find),
        misses: ['The model on screen.', 'In this universe of names.', 'No surprise there.', 'Apple pays.', 'subscription'].map(find),
        level: ['professional', 'simple', 'literate', 'advanced', 'adaptive', ''].map(G.marking) }}));
    """)
    assert got["hits"] == ["forward P/E", "Dealer gamma", "Free cash flow", "EPS", "put/call ratio", "realised P&L"], "the longest term first, whole words, any case"
    assert got["misses"] == [None, None, None, None, None], "words whose everyday sense is the common one here are left plain"
    assert got["level"] == [False, True, True, True, True, True], "Professional marks nothing, as Classic's explain 'off'"
    assert '"explain": EXPLAIN_OFF,' in (V2.parent.parent / "app" / "knowledge.py").read_text()


def test_the_places_kept_plain():
    skip = re.search(r"const SKIP = \[(.*?)\]\.join", GM, re.S).group(1)
    for sel in ("'a'", "'button'", "'input'", "'textarea'", "'select'", "'[contenteditable]'", "'code'", "'pre'", "'svg'", "'.chart-wrap'", "'.chart-tip'", "'.milo-panel'", "'.milo-log'", "'.dhead'", "'summary'", "'h1'"):
        assert sel in skip, sel
    assert "if (h && h.querySelector('[data-v2-term]')) return false;" in GM, "a heading that already holds a term is left alone"
    assert "const SCOPE = 'details, [role=\"tabpanel\"], .view, section.section, [data-ws-panel], .drawer, .page-view';" in GM, "once per section; a fold is its own section"
    assert "watchGlossary($('#main'));" in APP, "the page only: the Milo panel is outside it"


def test_classics_header_labels_and_its_milo_question(tmp_path):
    got = _run(tmp_path, f"""
      const T = await import('{(JS / "ui/term.js").as_posix()}');
      const G = await import('{(JS / "core/glossary.js").as_posix()}');
      const dd = {{ tagName: 'DD', textContent: ' 28.4 ' }};
      const inTile = {{ textContent: 'Forward P/E', closest: (s) => (s === 'dt' ? {{ nextElementSibling: dd }} : null) }};
      const inText = {{ textContent: 'gamma', closest: () => null }};
      print(JSON.stringify({{ head: T.define('head:5y cagr'), spread: T.define('head:spread'), none: T.define('head:value'),
        tile: T.explainPrompt(inTile, 'AAPL Overview', 'AAPL'), text: T.explainPrompt(inText, 'Market overview', ''), n: Object.keys(G.LABEL_DEFS).length }}));
    """)
    assert got["head"]["def"].startswith("The compound annual growth rate over five years") and got["spread"]["def"].startswith("The gap between the best bid and the best ask")
    assert got["none"] is None, "a generic label means something different in every table, so it takes no definition"
    assert got["tile"] == "Explain Forward P/E (28.4) for AAPL on the AAPL Overview page: what it measures, why someone would use it, what this value suggests, and what it cannot tell me."
    assert got["text"] == "Explain gamma on the Market overview page: what it measures, why someone would use it, what this value suggests, and what it cannot tell me."
    assert got["n"] == 18
    assert "'and what it cannot tell me.'" in CLASSIC and "const LABEL_DEFS = {" in CLASSIC
    glossary = (JS / "core/glossary.js").read_text()
    for line in re.search(r"const LABEL_DEFS = \{\n(.*?)\n\};", CLASSIC, re.S).group(1).split("\n"):
        assert line in glossary, line[:60]


def test_the_shell_that_marks_terms_also_loads_their_handlers():
    """The marks are made by ui/glossmark.js, in the shell; what a press does is ui/term.js's document listeners.
    Only pages that build a term by hand imported term.js, so on a first visit to Macro (or Read, Scan, Compare)
    every marked word took the click and did nothing (investor audit, 2026-10-27)."""
    from pathlib import Path
    from app import frontend
    shell = frontend.static_graph(Path(__file__).resolve().parent.parent / "static/v2")
    assert "/v2/js/ui/glossmark.js" in shell and "/v2/js/ui/term.js" in shell
