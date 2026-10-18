"""The rebuilt frontend in static/v2 stays faithful to the current app.

Four promises are checked here:
- the navigation's names are the classic app's, word for word (the owner's
  rule that no section, page or phone-bar name changes without a yes);
- every page in the navigation is accounted for in the coverage tracker;
- the device-session module keeps exactly the classic list of personal keys,
  so the two frontends shelve the same things on an account switch;
- the pure helpers (number formatting, the 0 to 100 score, the router) give
  the same answers as the classic app.
"""
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
APP = (ROOT / "static/app.js").read_text()
V2 = ROOT / "static/v2"
NAV = (V2 / "js/nav.js").read_text()


def _classic_groups():
    block = APP[APP.index("const NAV_GROUPS = ["):]
    block = block[:block.index("];")]
    return re.findall(r"\{ id: '([a-z]+)', label: '([^']+)', views: ([^,}]+(?:\][^,}]*)?)", block)


def _sub_labels():
    block = APP[APP.index("const SUB_LABELS = {"):]
    block = block[:block.index("};")]
    return dict(re.findall(r"""(\w+): ['"]([^'"]+)['"]""", block))


def test_group_names_are_the_classic_ones():
    classic = {gid: label for gid, label, _ in _classic_groups()}
    v2 = dict(re.findall(r"\{ id: '([a-z]+)', label: '([^']+)'", NAV))
    assert v2 == classic


def test_page_names_are_the_classic_ones():
    labels = _sub_labels()
    pages = re.findall(r"\{ view: '([a-z]+)', label: '([^']+)'", NAV)
    assert pages, "nav.js lists no pages"
    for view, label in pages:
        if view in labels:
            assert label == labels[view], view
    # every classic page is in v2's navigation
    assert {v for v, _ in pages} >= set(labels) - {"overview"} | {"overview"}


def test_sections_and_phone_bar_are_the_classic_ones():
    assert re.search(r"portfolio: 'Tracking', follow: 'Tracking', brokerage: 'Tracking'", APP)
    for gid, section in re.findall(r"(\w+): '(Research|Tracking|Owner)'", NAV):
        assert re.search(r"%s: '%s'" % (gid, section), APP), gid
    classic = re.findall(r"label: '([^']+)', (?:nav|more)", APP[APP.index("const MOBILE_TABS = ["):][:600])
    block = NAV[NAV.index("export const MOBILE_TABS = ["):]
    v2 = re.findall(r"label: '([^']+)'", block[:block.index("];")])
    assert v2 == classic == ["Home", "Dossier", "Markets", "Discover", "More"]


def test_every_navigation_page_is_in_the_coverage_tracker():
    doc = (ROOT / "docs/frontend-v2/COVERAGE.md").read_text()
    rows = re.findall(r"^\| ([^|]+) \| ([^|]+) \| `[^`]+` \| (Rebuilt|Current app) \|$", doc, re.M)
    listed = {(g.strip(), p.strip()) for g, p, _ in rows}
    nav = NAV[NAV.index("export const GROUPS = ["):NAV.index("export const SETTINGS")]
    groups = dict(re.findall(r"\{ id: '([a-z]+)', label: '([^']+)'", nav))
    for gid, glabel in groups.items():
        start = nav.index("{ id: '%s'" % gid)
        end = nav.find("{ id: '", start + 5)
        for _view, plabel in re.findall(r"\{ view: '([a-z]+)', label: '([^']+)'", nav[start:end if end > 0 else None]):
            assert (glabel, plabel) in listed, (glabel, plabel)
    # and the tracker's v2 claims match nav.js
    rebuilt = {p.strip() for _g, p, s in rows if s == "Rebuilt"}
    marked = set(re.findall(r"label: '([^']+)', slug: '[^']*', v2: true", NAV))
    assert rebuilt == marked


def test_the_personal_keys_are_the_classic_list():
    def keys(text, start):
        block = text[text.index(start):]
        return re.findall(r"'(optic\.[^']+)'", block[:block.index("];")])
    assert keys((V2 / "js/core/device.js").read_text(), "export const PERSONAL_KEYS = [") \
        == keys(APP, "const PERSONAL_KEYS = [")


def test_no_browser_dialogs_in_v2():
    """Lists are named and deleted inline; prompt() and confirm() are gone."""
    for path in V2.rglob("*.js"):
        text = path.read_text()
        assert not re.search(r"\b(window\.)?(prompt|confirm|alert)\(", text), path.name


JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc"


def _jsc():
    exe = JSC if os.path.exists(JSC) else shutil.which("jsc")
    if not exe:
        pytest.skip("jsc not available")
    return exe


def test_helpers_match_the_classic_app(tmp_path):
    script = tmp_path / "check.mjs"
    script.write_text(f"""
      globalThis.window = {{ addEventListener() {{}} }};
      globalThis.location = {{ hash: '' }};
      const f = await import('{(V2 / "js/core/format.js").as_posix()}');
      const r = await import('{(V2 / "js/core/router.js").as_posix()}');
      print(JSON.stringify({{
        signed: [f.signed(1.234), f.signed(-0.5), f.signed(0)],
        money: f.money(-1234.5), compact: f.compact(5012516765696),
        score: [f.score100(62, -78, 97), f.score100(-39, -78, 97), f.score100(28.2)],
        clean: f.clean('a \\u2014 b, 1\\u20132'),
        routes: ['', '#/', '#/AAPL', '#/aapl/options', '#/watchlist', '#/alerts?symbol=MSFT',
                 '#/brokerage/holdings', '#/instrument/%5EGSPC', '#/macro', '#/settings', '#/bad sym'].map((h) => r.parse(h)),
      }}));
    """)
    out = subprocess.run([_jsc(), "-m", str(script)], capture_output=True, text=True, timeout=30)
    assert out.returncode == 0, out.stderr
    got = json.loads(out.stdout.strip().splitlines()[-1])
    assert got["signed"] == ["+1.23%", "−0.50%", "0.00%"]
    assert got["money"] == "−$1,234.50"
    assert got["compact"] == "5.01T"
    # 62 on the long-term scale is 82 of 100, as the Investing tab shows
    assert round(got["score"][0]) == 82 and round(got["score"][1]) == 25 and round(got["score"][2], 1) == 64.1
    assert got["clean"] == "a: b, 1 to 2"
    views = [(x["view"], x.get("symbol"), x.get("params", {}).get("symbol")) for x in got["routes"]]
    assert views == [("home", None, None), ("home", None, None), ("overview", "AAPL", None),
                     ("swing", "AAPL", None), ("watchlist", None, None), ("alerts", None, "MSFT"),
                     ("brokerage", None, None), ("instrument", "^GSPC", None), ("market", None, None),
                     ("settings", None, None), ("notfound", None, None)]
