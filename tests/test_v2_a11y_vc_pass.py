"""Accessibility and layout fixes from the VC demo pass, 27 October 2026.

Each was found in the browser (the local server, at 1440, 390 and 720 by 500
for 200% zoom) or by the A11y Enforcer's contrast check on the tokens."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).parent.parent
V2 = ROOT / "static" / "v2"


def _lum(h):
    h = h.lstrip("#")
    rgb = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def _ratio(a, b):
    x, y = sorted((_lum(a), _lum(b)), reverse=True)
    return (x + 0.05) / (y + 0.05)


def test_light_positive_text_passes_on_every_light_surface():
    tok = (V2 / "css" / "tokens.css").read_text()
    light = tok[:tok.index(':root[data-theme="charcoal"]')]
    get = lambda n: re.search(r"--%s:\s*(#[0-9a-fA-F]{6})" % n, light).group(1)  # noqa: E731
    for surface in ("c-plane", "c-raised", "c-sunk"):
        assert _ratio(get("c-pos"), get(surface)) >= 4.5, surface      # was 4.20:1 on --c-sunk


def test_a_drawer_gives_focus_back_even_when_the_page_redrew_its_opener():
    src = (V2 / "js" / "ui" / "drawer.js").read_text()
    assert "function twinOf(el)" in src
    assert "const back = document.contains(from) ? from : twinOf(from); if (back) back.focus();" in src


def test_the_phone_chart_header_shares_the_tickers_line_and_keeps_44px_targets():
    css = (V2 / "css" / "pages.css").read_text()
    block = css[css.index("VC demo pass (2026-10-27)"):]
    assert "higher. The price, the session and its time keep their own line. Other tabs keep the full row. */\n@media (max-width: 559px) {" in block
    assert ".dhead.bar.dhead-chart .acts { order: 2;" in block and "min-height: var(--tap)" in block
    assert ".dhead.bar.dhead-chart .dh-price { order: 3; flex-basis: 100%; }" in block, "price and session keep a line"
    frame = (V2 / "js" / "pages" / "dossier-frame.js").read_text()
    assert "${view === 'chart' ? ' dhead-chart' : ''}" in frame
    assert '<span class="acts-milo-t">Ask about ${sym}</span>' in frame, "the name stays for a screen reader"


def test_the_classic_milo_box_is_labelled():
    page = (ROOT / "static" / "index.html").read_text()
    assert re.search(r'<textarea id="chat-input" placeholder="[^"]*" aria-label="Ask Milo">', page)
    assert 'id="chat-file" aria-label="Attach an image or PDF"' in page


def test_no_section_chip_is_cut_mid_word(tmp_path):
    """Seven jump chips read "What options price for the…" and the like (VC audit, 2026-10-26)."""
    from tests.test_frontend_v2_stage0 import _run
    got = _run(tmp_path, f"""
      const s = await import('{(V2 / "js/ui/sections.js").as_posix()}');
      const titles = ['Four questions, answered separately', 'Long-term trend score, from price history', 'The multiple against its own history',
        'Fair-value model, discounted cash flow', 'Valuation and accumulation levels', 'The business behind the reports', 'What options price for the report'];
      print(JSON.stringify(titles.map(s.chipLabel)));
    """)
    assert all(len(t) <= 28 and not t.endswith("…") for t in got), got


def test_sandbox_brokerage_data_says_it_is_test_data_on_every_section():
    """Rehearsing the demo on the sandbox, Overview showed $79,117.31 of holdings and nothing said they were made up;
    only Connections named the sandbox."""
    src = (V2 / "js" / "pages" / "brokerage.js").read_text()
    paint = src[src.index("function paint(focusSel)"):]
    assert "const sandbox = (S.status || {}).mode === 'sandbox';" in paint
    assert "Sandbox: test data only. These accounts, holdings and values are made up for demonstration and belong to no one." in paint
