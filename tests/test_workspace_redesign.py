"""The workspace redesign (2026-10-07): what it added, held in place.

The redesign is a restyle, so most of it is guarded by the stylesheet tests
that were already here. It also added two things the stylesheet cannot carry
on its own: a page header that says where the reader is and what the page is
for, and section labels in the rail. Both are presentation over existing
words, and the property worth holding is exactly that: the header's copy is
the navigation's own (SUB_TITLES, SUB_LABELS, the group names), never new
claims, and every nav group has a section so a new group cannot render
unlabelled at the end of the wrong one.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
JS = (ROOT / "static/app.js").read_text(encoding="utf-8")
CSS = (ROOT / "static/styles.css").read_text(encoding="utf-8")
HTML = (ROOT / "static/index.html").read_text(encoding="utf-8")
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc"


def _block(src: str, start: str, open_ch: str = "{", close_ch: str = "}") -> str:
    """The text from `start` to its matching close, skipping strings well enough
    for the declarations lifted here (no braces inside their string literals)."""
    i = src.index(start)
    j = src.index(open_ch, i)
    depth = 0
    for k in range(j, len(src)):
        if src[k] == open_ch:
            depth += 1
        elif src[k] == close_ch:
            depth -= 1
            if depth == 0:
                return src[i:k + 1]
    raise AssertionError("unbalanced: " + start)


def _fn(name: str) -> str:
    return _block(JS, "function %s(" % name)


# ------------------------------------------------------------- the markup


def test_the_page_header_has_a_slot_inside_main_before_the_views():
    main = HTML[HTML.index('<main id="main"'):HTML.index("</main>")]
    assert '<header class="page-head" id="page-head" hidden></header>' in main
    assert main.index('id="page-head"') < main.index('id="view-home"'), \
        "above the views, so it heads whichever one is active"


def test_the_secondary_face_is_one_already_loaded_face():
    """Every label and every ticker in one secondary face, Space Grotesk, which
    index.html already loads from jsDelivr (not Google Fonts: the page is meant
    to be openable without sending the reader's address to Google). The
    monospace it replaced is gone with its request."""
    assert ("https://cdn.jsdelivr.net/npm/@fontsource-variable/space-grotesk/index.css"
            in HTML)
    assert "jetbrains" not in HTML.lower() and "fonts.googleapis.com" not in HTML
    assert re.search(r'--label-face:\s*"Space Grotesk Variable"', CSS)
    assert "var(--mono)" not in CSS, "one secondary face, not two"


# ---------------------------------------------------------- the page header


def test_the_header_is_painted_on_every_switch():
    body = _fn("switchView")
    assert "paintPageHead(view);" in body
    assert body.index("paintNav(view);") < body.index("paintPageHead(view);")


def test_pages_with_their_own_header_get_none():
    own = re.search(r"const PAGE_HEAD_OWN = new Set\(\[([^\]]*)\]\)", JS).group(1)
    assert {"'home'", "'instrument'", "'paper'", "'insiders'"} == \
        {s.strip() for s in own.split(",")}
    body = _fn("paintPageHead")
    assert "SECURITY_VIEWS.includes(view)" in body, "the Dossier header names the symbol"
    assert "host.hidden = true;" in body


def test_the_header_writes_only_the_navigations_own_words():
    """Every string it can show is SUB_TITLES, SUB_LABELS, a group's label, or
    the word Settings. A literal sentence here would be new copy, and a claim
    nobody wrote for that page."""
    body = _fn("paintPageHead")
    assert "SUB_TITLES[view]" in body and "navGroupLabel(group)" in body
    literals = set(re.findall(r"'([^'\n$]{8,})'", body))
    assert literals <= {"page-head", "settings", "Settings"}, literals
    assert "esc(title)" in body and "esc(desc)" in body and "esc(eyebrow)" in body


def test_hidden_is_honoured_by_the_header():
    """An author `display` beats `[hidden]`, so the pair has to be written."""
    assert ".page-head[hidden] { display: none; }" in CSS
    assert re.search(r"\.page-head \{[^}]*display: flex", CSS)


@pytest.mark.skipif(not os.path.exists(JSC) or shutil.which("true") is None,
                    reason="JavaScriptCore not available")
def test_the_header_splits_a_title_from_its_description(tmp_path):
    """Run paintPageHead itself over the real tables: Optic's Read is a title
    and a description, Macro is a description under its page name, Home and
    the Dossier get no header at all."""
    pieces = [
        _block(JS, "const SECURITY_VIEWS = [", "[", "]") + ";",
        _block(JS, "const SUB_LABELS = {") + ";",
        _block(JS, "const SUB_TITLES = {") + ";",
        re.search(r"const PAGE_HEAD_OWN = new Set\(\[[^\]]*\]\);", JS).group(0),
        _fn("paintPageHead"),
    ]
    harness = """
    var host = { hidden: true, innerHTML: '' };
    var document = { getElementById: function () { return host; } };
    function esc(s) { return String(s); }
    function navGroupLabel(g) { return g.label; }
    var NAV_GROUPS = [
      { id: 'market', label: 'Markets', views: ['brief', 'market', 'indices'] },
      { id: 'follow', label: 'Watchlist', views: ['watchlist', 'alerts'] },
    ];
    %s
    function run(view) {
      paintPageHead(view);
      var text = host.innerHTML.replace(/<[^>]+>/g, '|').replace(/\\s+/g, ' ')
        .split('|').map(function (s) { return s.trim(); }).filter(Boolean).join(' / ');
      print(view + ' => ' + (host.hidden ? 'HIDDEN' : text));
    }
    ['brief', 'market', 'watchlist', 'settings', 'home', 'overview', 'chart', 'paper']
      .forEach(run);
    """ % "\n".join(pieces)
    path = tmp_path / "head.js"
    path.write_text(harness)
    out = subprocess.run([JSC, str(path)], capture_output=True, text=True, timeout=30)
    assert out.returncode == 0, out.stderr
    lines = dict(line.split(" => ", 1) for line in out.stdout.strip().splitlines())
    assert lines["brief"] == "Markets / Optic's Read / The daily market, macro and world summary"
    assert lines["market"] == "Markets / Macro / Macro regime and sector rotation"
    # The eyebrow is dropped when it would repeat the title.
    assert lines["watchlist"] == "Watchlist / What changed on the names you follow"
    assert lines["settings"] == "Settings"
    for view in ("home", "overview", "chart", "paper"):
        assert lines[view] == "HIDDEN", view


# --------------------------------------------------------- the rail sections


def test_every_nav_group_has_a_section():
    """A group missing from NAV_SECTIONS would render under whichever label
    came before it, which is a claim about what it is."""
    groups = set(re.findall(r"\{ id: '([a-z]+)', label:", _block(JS, "const NAV_GROUPS = [", "[", "]")))
    sections = dict(re.findall(r"([a-z]+): '([A-Za-z]+)'", _block(JS, "const NAV_SECTIONS = {")))
    assert groups, "NAV_GROUPS moved"
    assert groups == set(sections), (groups ^ set(sections))
    assert sections["reports"] == "Owner", "the owner's group is labelled as the owner's"


def test_the_labels_are_drawn_after_the_strip_and_hidden_from_assistive_tech():
    nav = _fn("paintNav")
    assert "labelNavSections(nav);" in nav
    assert nav.index("nav.innerHTML =") < nav.index("labelNavSections(nav);")
    assert nav.rstrip().endswith("navMenuSides();\n}"), \
        "paintNav still ends by measuring the menus (test_roth_view)"
    label = _fn("labelNavSections")
    assert "label.setAttribute('aria-hidden', 'true');" in label
    assert "label.textContent = section;" in label, "text, never markup"


def test_a_collapsed_rail_draws_a_label_as_a_rule_not_as_clipped_text():
    rule = re.search(r"body\.rail-tight \.rail nav\.tabs-group \.nav-sec \{([^}]*)\}", CSS)
    assert rule, "the collapsed-rail rule for section labels is gone"
    assert "color: transparent;" in rule.group(1) and "height: 1px;" in rule.group(1)


# ------------------------------------------------------------ the boundary


def test_the_redesign_block_names_no_new_colours():
    """Tokens only, comments stripped: the light theme and the reader's chart
    colours have to keep working through it."""
    start = CSS.index("WORKSPACE REDESIGN (2026-10-07)")
    block = re.sub(r"/\*.*?\*/", " ", CSS[start:], flags=re.S)
    assert not re.findall(r"#[0-9a-fA-F]{3,8}\b", block)
    assert not re.findall(r"rgba?\(", block)
