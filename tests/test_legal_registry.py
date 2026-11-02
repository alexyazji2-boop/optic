"""The disclaimer registry (app/legal.py) and the copy the v2 pages draw from (static/v2/js/core/legal.js).

Post-demo overhaul, Phase 02: one wording per notice. The v2 client keeps a copy so a notice draws on the first
paint without a request; these tests fail when the copy and the registry differ, and when a research area has no
notice. The wording itself is the operator's, pending counsel (docs/post-demo-ultra/COMPLIANCE_REVIEW.md).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from app import legal

ROOT = Path(__file__).resolve().parent.parent
JS = (ROOT / "static/v2/js/core/legal.js").read_text()


def test_the_page_disclosures_match_the_server_registry_word_for_word():
    js = JS
    block = js[js.index("  areas: {"):js.index("  },", js.index("  areas: {"))]
    client = {k: json.loads(v) for k, v in re.findall(r"^\s{4}(\w+): (\".*\"),$", block, re.M)}
    assert client == legal.PAGE_AREAS
    assert "export const FOOTER_LINE = '{}';".format(legal.FOOTER_LINE) in js
    assert legal.notice()["page_areas"] == legal.PAGE_AREAS and legal.notice()["version"] == legal.REGISTRY_VERSION


def test_every_research_area_has_a_notice_and_none_runs_long():
    js = JS
    mapped = re.search(r"const AREA_FOR = \{([^}]*)\}", js).group(1)
    for view in ("overview", "chart", "swing", "long", "earnings", "news", "brief", "market", "explore", "scan",
                 "insiders", "analysts", "brokerage", "roth", "tracker", "paper", "compare", "watchlist", "earningsweek"):
        assert re.search(r"\b{}: '".format(view), mapped), view
    for key, text in legal.PAGE_AREAS.items():
        plain = re.sub(r"<[^>]+>", "", text)
        assert len(plain.split()) <= 80, key


def test_the_full_disclaimer_is_the_same_in_both_places():
    block = JS[JS.index("  full: ["):JS.index("  ],", JS.index("  full: ["))]
    paras = [t.replace("\\'", "'") for t in re.findall(r"^\s{4}'((?:[^'\\]|\\.)*)',$", block, re.M)]
    assert paras == legal.FULL.split("\n\n")

