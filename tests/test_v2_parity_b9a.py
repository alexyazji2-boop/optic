"""Classic parity, batch B9a (2026-10-21): the Optic Portfolio page's sections fold, with Classic's defaults; Financials'
stock-against-the-index line and dividend columns; bars in Scan's ranked column. The pure rules run in JavaScriptCore:
which sections start open, when Scan draws bars and against what. The folds kept across a reload, the charts and the
bars on screen were driven in headless Chrome (~/Optic/work/classic-parity/b9a_check.py). These tests are not
interaction evidence. Ledger: docs/frontend-v2/CLASSIC-PARITY.md, B9a.
"""
from tests.test_frontend_v2_stage0 import V2, _run

JS = V2 / "js"
CLASSIC = (V2.parent / "app.js").read_text()
FIN = (JS / "pages/financials.js").read_text()
TRK = (JS / "pages/tracker.js").read_text()


def test_which_sections_start_open(tmp_path):
    got = _run(tmp_path, f"""
      const S = await import('{(JS / "ui/sections.js").as_posix()}');
      const open = ['optic portfolio', 'open positions'];
      print(JSON.stringify([
        S.openByDefault(null, 'Anything'), S.openByDefault(open, 'Optic Portfolio, Equities'), S.openByDefault(open, 'Month by month'),
        S.startsOpen({{}}, 'tracker|month by month', 0, 1, false), S.startsOpen({{ 'tracker|month by month': true }}, 'tracker|month by month', 0, 1, false),
        S.startsOpen({{ 'tracker|optic portfolio': false }}, 'tracker|optic portfolio', 0, 1, true), S.startsOpen({{}}, 'x|y', 2, 1, true) ]));
    """)
    assert got == [True, True, False, False, True, False, False], "a list opens only its headings; the reader's own choice wins; the level still folds"
    assert "tracker: ['optic portfolio', 'open positions', 'three books', 'no trades yet']," in CLASSIC
    assert "sections(main, 'tracker', { open: ['optic portfolio', 'open positions', 'three simulated accounts', 'no trades yet'] });" in TRK


def test_when_scan_draws_bars(tmp_path):
    got = _run(tmp_path, f"""
      const S = await import('{(JS / "pages/scan.js").as_posix()}');
      const res = (kind, vals) => ({{ ranked_by: {{ key: 'k' }}, columns: [{{ key: 'k', kind }}], rows: vals.map((v) => ({{ k: v }})) }});
      print(JSON.stringify({{
        close: S.rankBars(res('score', [82, 81.8, 79.9, 76.4, 74])), spread: S.rankBars(res('pct', [59.6, -49.8, 47.8, 12, -8])),
        usd: S.rankBars(res('usd', [9e9, 4e9, 1e9])), ratio: S.rankBars(res('ratio', [0.9, 0.5, 0.1])), pctile: S.rankBars(res('num', [95, 40, 10])),
        two: S.rankBars(res('pct', [50, -50])), none: S.rankBars({{ columns: [], rows: [] }}),
        neg: S.cellBar(-24.9, {{ key: 'k', oneSided: false, max: 49.8 }}), one: S.cellBar(4e9, {{ key: 'k', oneSided: true, max: 9e9 }}), nan: S.cellBar(null, {{ max: 1 }}) }}));
    """)
    assert got["close"] is None, "scores that barely differ draw the same bar every row, so none"
    assert got["spread"] == {"key": "k", "oneSided": False, "max": 59.6}
    assert got["usd"]["oneSided"] is True and got["ratio"]["max"] == 1 and got["pctile"]["max"] == 100, "a share against its whole, a percentile against 100"
    assert got["two"] is None and got["none"] is None, "three rows at least"
    assert 'aria-hidden="true"' in got["neg"] and 'class="neg" x="13.5" y="1" width="12.5"' in got["neg"], "from zero leftward, half its side; the figure beside it says the value"
    assert 'class="one" x="0"' in got["one"] and got["nan"] == ""
    assert "(rkTop - Math.min(...rkVals)) / rkTop >= 0.35" in CLASSIC and "const SCAN_ONE_SIDED = new Set(['usd', 'mult', 'ratio', 'pct_plain', 'num']);" in CLASSIC


def test_the_financials_charts():
    assert "out.rel = (w) => lineChart(rel, { w, h: 200, dp: 1, area: true, refs: [{ v: 100 }]" in FIN, "the stock against the index from 100, with the even line"
    assert "out.divs = (w) => groupedBars(" in FIN and "Each year's total" in FIN, "dividends as columns, the table folded under them"
    assert "refLines: [{ value: 100, color: C.baseline, label: 'even', emphasis: true }]," in CLASSIC and "vizMount('viz-fin-divs'" in CLASSIC
