"""Scores in green and red with a line filled to the score (owner, 2026-10-21: "use the green/red color scheme
wherever applicable, such as optic score ... include a line filled percentage based on the score like how classic used
to show"). The rules run in JavaScriptCore; each page's scores were checked on screen in headless Chrome
(~/Optic/work/classic-parity/scores_check.py).
"""
from tests.test_frontend_v2_stage0 import V2, _run

JS = V2 / "js"
CLASSIC = (V2.parent / "app.js").read_text()


def test_the_rules(tmp_path):
    got = _run(tmp_path, f"""
      const S = await import('{(JS / "ui/score.js").as_posix()}');
      const {{ toString }} = await import('{(JS / "core/dom.js").as_posix()}');
      print(JSON.stringify({{
        t100: [82, 55, 54, 50, 46, 45, 12, null].map((n) => S.tone100(n)),
        sign: [9, 0, -3, null].map((n) => S.toneSign(n)),
        band: ['Greed', 'Extreme fear', 'Neutral', 'solid', 'strong', 'weak', 'moderate', ''].map(S.toneBand),
        line: toString(S.scoreLine(82)), none: toString(S.scoreLine(null)), band68: toString(S.scoreLine(68, {{ tone: 'up' }})),
        signed: toString(S.signedLine(-40)), over: toString(S.scoreLine(140)) }}));
    """)
    assert got["t100"] == ["up", "up", "flat", "flat", "flat", "down", "down", ""], "green from 55, red to 45 (Classic's Optic Score)"
    assert got["sign"] == ["up", "flat", "down", ""]
    assert got["band"] == ["up", "down", "flat", "up", "up", "down", "flat", ""], "greed, strong and solid green; fear and weak red"
    assert got["line"] == '<span class="sline is-up" aria-hidden="true"><i style="width:82.0%"></i></span>'
    assert 'class="sline is-none"' in got["none"] and 'width:68.0%' in got["band68"] and 'width:100.0%' in got["over"]
    assert '<span class="sl-half sl-neg"><i style="width:40.0%"></i></span>' in got["signed"] and 'class="sline sline-signed is-down"' in got["signed"], "from the middle, leftward below zero"
    assert "n >= 55 ? ' up' : n <= 45 ? ' down' : ''" in CLASSIC, "Classic's own thresholds"


def test_the_pages_use_them():
    uses = {
        "pages/overview-research.js": "${scoreLine(n)}",
        "pages/dossier.js": "${scoreLine(s100)}",
        "pages/investing.js": "${scoreLine(s)}",
        "pages/options-panels.js": "${scoreLine(s)}",
        "pages/read.js": "scoreLine(s.score, { tone: toneBand(s.label) })",
        "pages/workspace.js": "${signedLine(m.risk_score)}",
        "pages/compare.js": "${scoreLine(x.score)}",
    }
    for path, snippet in uses.items():
        assert snippet in (JS / path).read_text(), path
    assert "scoreLine(dv.score, { tone: toneBand(dv.band) })" in (JS / "pages/investing.js").read_text(), "the dividend score by its band"
