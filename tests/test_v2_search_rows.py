"""Search laid out as TradingView's (owner, 2026-10-21: "any search bar within optic should look like this, whether
the user searches the name of a company, ETF or ticker. include the logo as well"), squared corners and the typed
letters in gold (the owner's two choices). The row markup and the logo route are tested here; the palette, the filter
row and the symbol boxes were driven in headless Chrome (~/Optic/work/classic-parity/search_check.py).
"""
import os

import pytest
from fastapi.testclient import TestClient

import app.main as m
from tests.test_frontend_v2_stage0 import V2, _run

JS = V2 / "js"


def test_a_row_and_its_logo(tmp_path):
    got = _run(tmp_path, f"""
      const S = await import('{(JS / "ui/symbols.js").as_posix()}');
      print(JSON.stringify({{
        hood: S.rowHTML({{ symbol: 'HOOD', name: 'Robinhood Markets, Inc. Class A', kind: 'stock' }}, 'hood'),
        fund: S.rowHTML({{ symbol: 'NVDX', name: 'T-Rex 2X Long NVIDIA Daily Target ETF', etf: true }}, 'nvidia'),
        index: S.logoHTML('^GSPC'), pair: S.logoHTML('BTC-USD'), kinds: ['stock', 'etf', 'commodity', 'future', 'rate', 'crypto'].map(S.filterOf) }}));
    """)
    assert got["hood"].startswith('<span class="sym-logo" aria-hidden="true" data-l="H"><img src="/api/logo/HOOD" alt="" loading="lazy" decoding="async"></span>')
    assert '<span class="sym-sym"><b>HOOD</b></span><span class="sym-name">Robin<b>hood</b> Markets, Inc. Class A</span><span class="sym-kind">stock</span>' in got["hood"]
    assert '<span class="sym-kind">fund etf</span>' in got["fund"] and "T-Rex 2X Long <b>NVIDIA</b>" in got["fund"]
    assert got["index"] == '<span class="sym-logo" aria-hidden="true" data-l="G"></span>', "an index has no logo to ask for: its initial"
    assert "<img" in got["pair"]
    assert got["kinds"] == ["stock", "etf", "futures", "futures", "index", "crypto"]


@pytest.fixture
def logos(tmp_path, monkeypatch):
    monkeypatch.setattr(m, "_LOGO_DIR", str(tmp_path))
    calls = []
    def fetch(sym):
        calls.append(sym)
        return {"AAPL": (b"<svg xmlns='http://www.w3.org/2000/svg'/>", "image/svg+xml"), "HOOD": (b"\x89PNG....", "image/png")}.get(sym)
    monkeypatch.setattr(m, "_logo_fetch", fetch)
    return calls


def test_the_logo_route(logos):
    c = TestClient(m.app)
    a = c.get("/api/logo/aapl")
    assert a.status_code == 200 and a.headers["content-type"].startswith("image/svg+xml")
    assert "sandbox" in a.headers["content-security-policy"] and a.headers["x-content-type-options"] == "nosniff", "an SVG opened on its own runs nothing"
    assert c.get("/api/logo/AAPL").status_code == 200 and logos == ["AAPL"], "kept on disk: asked for once"
    assert c.get("/api/logo/ZZZZ").status_code == 404 and c.get("/api/logo/ZZZZ").status_code == 404 and logos.count("ZZZZ") == 1, "no logo is remembered too"
    for bad in ("%5EGSPC", "ES%3DF", "..%2Fetc", "A" * 14):
        assert c.get(f"/api/logo/{bad}").status_code == 404
    assert "^GSPC" not in logos and len(logos) == 2, "an index, a future or a path is never asked for"


def test_only_images_are_kept(monkeypatch):
    class R:
        def __init__(self, kind, body): self.headers = {"Content-Type": kind}; self.body = body
        def read(self, n=-1): return self.body
        def __enter__(self): return self
        def __exit__(self, *a): return False
    answers = [R("text/html", b"<!DOCTYPE html><p>nope"), R("image/png", b"\x89PNG..")]
    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=6: answers.pop(0))
    assert m._logo_fetch("NVDA") == (b"\x89PNG..", "image/png"), "a web page from the first service is skipped for the second's image"


def test_the_palette_reads_as_one_list():
    pal = (JS / "ui/palette.js").read_text()
    assert "rest.splice(lastSym + 1, 0, ...subs.map((r) => Object.assign(r, { group: `More for ${g}` })));" in pal, "the top symbol's pages follow the list"
    assert "data-pal-clear" in pal and "data-pal-filter" in pal and "Cancel</button>" not in pal
    assert ".sym-row b { color: var(--c-gold); font-weight: inherit; }" in (V2 / "css/components.css").read_text(), "the typed letters in gold (owner)"
