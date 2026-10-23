"""Home's portfolio panel with under a week of value history (owner, 2026-10-23).

SnapTrade's balance-history add-on is off, so Optic's value history starts at the first sync (2026-10-22). Two equal
snapshots drew a flat "three months" chart with an axis of 12,698.102 to 12,698.198 and "0.00% over the period",
which read as "my portfolio has not moved at all".
"""
from __future__ import annotations

import json
import re

from tests.test_frontend_v2_stage0 import V2
from tests.test_v2_p3 import _run


def _panel(tmp_path, perf):
    ov = {"totals": {"value": 12565.14, "combined_usd": {"value": 12698.16}}, "holdings_count": 3,
          "today": {"total": -129.43, "total_pct": -1.02, "rows": []},
          "freshness": {"broker": {"newest_sync": "2026-10-23T14:00:00+00:00"}}}
    return _run(tmp_path, f"""
      globalThis.localStorage = {{ getItem() {{ return null; }}, setItem() {{}}, removeItem() {{}} }};
      const H = await import('{(V2 / "js/pages/home.js").as_posix()}');
      const D = await import('{(V2 / "js/core/dom.js").as_posix()}');
      const html = D.toString(H.portfolio({json.dumps(ov)}, {json.dumps(perf)}));
      print(JSON.stringify({{ html, series: H.portfolioSeries().length }}));
    """)


def test_two_days_of_snapshots_say_how_much_history_there_is_and_draw_no_three_month_chart(tmp_path):
    perf = {"series": [{"date": "2026-10-22", "value": 12698.15}, {"date": "2026-10-23", "value": 12564.16}],
            "period": {"covered_days": 1, "measured_start": "2026-10-22", "measured_end": "2026-10-23"},
            "returns": {"twr": {"pct": -1.06}},
            "data_status": [{"account": "Robinhood", "balance_history": "unavailable"}]}
    got = _panel(tmp_path, perf)
    text = re.sub(r"<[^>]+>", "", got["html"])
    assert got["series"] == 0 and 'data-chart="portfolio"' not in got["html"]
    assert "Optic has 2 days of value history for these accounts, since Oct 22, 2026." in text
    assert "does not send past balances" in text
    assert "\u22121.06% from Oct 22, 2026 to Oct 23, 2026" in text
    assert "$12,698.15 on Oct 22" in text and "$12,564.16 on Oct 23" in text
    assert "three months. It includes" not in text and "over the period" not in text


def test_a_long_history_keeps_the_chart_and_names_the_span_of_its_return(tmp_path):
    perf = {"series": [{"date": f"2026-09-{d:02d}", "value": 12000 + d * 10} for d in range(1, 29)],
            "period": {"covered_days": 27, "measured_start": "2026-09-01", "measured_end": "2026-09-28"},
            "returns": {"twr": {"pct": 2.2}}, "data_status": []}
    got = _panel(tmp_path, perf)
    text = re.sub(r"<[^>]+>", "", got["html"])
    assert got["series"] == 28 and 'data-chart="portfolio"' in got["html"]
    assert "+2.20% from Sep 1, 2026 to Sep 28, 2026, time-weighted" in text


def test_a_flat_series_gets_an_axis_in_proportion_to_its_level(tmp_path):
    got = _run(tmp_path, f"""
      const C = await import('{(V2 / "js/ui/chart.js").as_posix()}');
      const r = C.lineChart([{{ d: '2026-10-22', c: 12698.15 }}, {{ d: '2026-10-23', c: 12698.15 }}], {{ w: 600, h: 180, dp: 0 }});
      print(JSON.stringify({{ html: r.html }}));
    """)
    ticks = re.findall(r">([\d,]+\.\d+)<", got["html"])
    assert not any(len(t.split(".")[1]) >= 3 for t in ticks), ticks
