"""The printable research sheet (roadmap stage 4, 2026-10-22).

Reached from the Dossier at #/SYM/sheet, not a tab. Its facts come from the same payloads the Dossier reads,
each section is tagged Reported, Estimate or Optic, missing figures are said, and private holdings are never
read. Printed at Letter and A4 it is two pages, the second an intentional continuation: measured in print media
at 710 x 940 and 688 x 1010 (AAPL 840/874 px, SPY 579/870 px) and in Chromium's PDF output (two pages). Those widths
are under the 860 px breakpoint, where the shell is one column anyway; from a wider window it was not (Pass 2, D4), so
it is re-measured from a 1280 px window too (2026-11-18: sheet 1280 px wide, two pages at Letter and at A4).
"""
from __future__ import annotations

import re

from tests.test_frontend_v2_stage0 import V2, _run

JS = V2 / "js"
SHEET = (JS / "pages/sheet.js").read_text()
CSS = (V2 / "css/pages.css").read_text()


def test_the_route_is_the_dossiers_not_a_tab(tmp_path):
    got = _run(tmp_path, f"""
      const R = await import('{(JS / "core/router.js").as_posix()}');
      const N = await import('{(JS / "nav.js").as_posix()}');
      print(JSON.stringify({{ r: R.parse('#/AAPL/sheet'), tabs: N.GROUPS.find((g) => g.id === 'security').pages.map((p) => p.slug) }}));
    """)
    assert got["r"]["view"] == "sheet" and got["r"]["symbol"] == "AAPL"
    assert "sheet" not in got["tabs"], "no new Dossier tab"
    frame = (JS / "pages/dossier-frame.js").read_text()
    # the header's More menu is the shared ticker menu since Phase 2 (2026-10-24): the sheet's link lives there
    company = open("static/v2/js/ui/company.js").read()
    assert '${tickerMenu(sym)}' in frame and 'href="#/${e}/sheet">Export research sheet</a>' in company
    assert 'title="A printable research sheet">Export</a>' in frame


def test_the_facts_carry_their_periods_and_missing_data_is_null(tmp_path):
    got = _run(tmp_path, f"""
      const S = await import('{(JS / "pages/sheet.js").as_posix()}');
      const full = S.sheetFacts({{ sym: 'AAPL',
        ticker: {{ quote: {{ name: 'Apple Inc.', price: 346 }}, company: {{ financials: {{ available: true, annual: {{ revenue: [416e9], net_income: [112e9], free_cash_flow: [98e9] }},
          annual_periods: ['2025-09-30'], annual_fiscal: ['FY25'], growth: {{ revenue_yoy_pct: 6.4 }}, margins: {{ operating_pct: 32 }}, balance_sheet: {{ net_cash: -62e9 }} }} }},
          figures: {{ periods: {{ statements: {{ basis: 'GAAP', annual: [{{ type: 'annual', available: true, start: '2024-09-29', end: '2025-09-27', short: 'FY25', label: 'Fiscal year ended Sep 27, 2025', dated_by: 'filing', provider_end: '2025-09-30' }}] }} }} }},
          technicals: {{ support_resistance: [{{ price: 336, distance_pct: -2.9, role: 'support', touches: 2 }}, {{ price: 400, distance_pct: 15, role: 'resistance', touches: 1 }}] }}, cases: {{ bull: [{{ claim: 'a' }}], bear: [] }} }},
        session: {{ profile: {{ summary: 'The Company makes phones. It sells services. It has a third sentence.' }} }},
        fairValue: {{ fair_value: {{ available: true, low: 244, mid: 275, high: 307 }}, stars: {{ available: true, stars: 1, word: 'Above its usual valuation range' }} }},
        earnings: {{ next_report: {{ date: '2026-11-02', eps_consensus: 1.98 }} }} }});
      const bare = S.sheetFacts({{ sym: 'SPY', ticker: {{ quote: {{ price: 600 }}, company: {{ financials: {{ available: false }} }} }}, fairValue: {{}}, earnings: {{}} }});
      print(JSON.stringify({{ full, bare }}));
    """)
    f, b = got["full"], got["bare"]
    # the year as the 10-K names and dates it (Sep 27), not the provider's month-end date (Handoff 2)
    assert f["financials"]["period"] == "2025-09-27" and f["financials"]["fiscal"] == "FY25"
    assert f["financials"]["label"] == "FY25, fiscal year ended Sep 27, 2025" and f["financials"]["basis"] == "GAAP"
    assert f["valuation"]["available"] and f["valuation"]["stars"] == 1
    assert f["chart"]["levels"][0]["price"] == 336, "nearest level first"
    assert b["financials"] is None and b["valuation"]["available"] is False and b["earnings"]["date"] is None and b["options"] is None


def test_each_section_says_what_kind_of_figure_it_is_and_no_holdings_are_read():
    for k in ("tag('reported')", "tag('estimate')", "tag('optic')"):
        assert k in SHEET
    assert "A reading against its own history, not an intrinsic value or a forecast." in SHEET
    assert "Estimated from open interest, not reported positions." in SHEET
    assert "brokerage" not in SHEET and "optic.paper" not in SHEET and "reader_holdings" not in SHEET
    assert "Private holdings are never included." in SHEET
    assert ".sh-cont { break-before: page; }" in CSS and "never smaller reading type" in CSS


def test_a_decimal_does_not_end_a_sentence(tmp_path):
    """The sheet's evidence line printed "Trading above the 200-day average. 99 .": its sentence split took every
    full stop as an end, so "$217.94 ... at $187.99. The line ..." came back as "99." (investor audit, 2026-10-27).
    The Overview's company summary used the same split."""
    got = _run(tmp_path, f"""
      const S = await import('{(JS / "pages/sheet.js").as_posix()}');
      const O = await import('{(JS / "pages/dossier.js").as_posix()}');
      const t = '$217.94 is 16.2% above the 200-day at $187.99. The line most long-term trend followers watch.';
      print(JSON.stringify([S.firstSentences(t, 1), O.firstSentences(t, 1)]));
    """)
    assert got == ["$217.94 is 16.2% above the 200-day at $187.99."] * 2


def _print_block():
    """The @media print block that carries the sheet's rules, braces matched."""
    start = CSS.index("@media print", CSS.index(".sh-chart svg { width: 100%"))
    depth, i = 0, CSS.index("{", start)
    while True:
        depth += {"{": 1, "}": -1}.get(CSS[i], 0)
        if depth == 0:
            return CSS[start:i + 1]
        i += 1


def test_the_sheet_prints_in_one_column_and_never_as_a_grid():
    """Printed from a window wider than 860 px, the sheet fell into the rail's column: the print block hid .rail but left
    .shell a two-column grid (components.css: the 256 px rail, then the page), so .sheet measured 256 px wide at x 0
    and the PDF ran to four pages (Pass 2 gauntlet, D4, 2026-11-18). Inside a grid Chromium also printed a paragraph
    broken across a page over the next one. The shell, the sheet and each page are blocks in print."""
    block = _print_block()
    assert ".sh-cont { break-before: page; }" in block, "the block found is the sheet's"
    rules = re.sub(r"/\*.*?\*/", "", block, flags=re.S).split("}")
    rule = next((r for r in rules if "display: block" in r and ".shell" in r.split("{")[0]), "")
    names = {n.strip() for n in rule.split("{")[0].split(",")}
    assert {".shell", ".sheet", ".sh-page"} <= names, "the shell, sheet and pages are one column of blocks in print: " + rule
    assert "measured at 710 x 940)" not in block, "the measurement in the comment is the one taken from a wide window"
