"""v2 screen quality (owner's overnight brief, 2026-10-19, priority 3): the chart read carried over from
the current app, Milo's availability said before a press, and the Financials hierarchy.

The chart read's model runs in JavaScriptCore against payloads shaped like /api/ticker's `technicals`;
the wiring is read from the page modules as text. Each was also checked in a browser at 1440 and 390 px.
"""
import json
import os
import re
import shutil
import subprocess

import pytest

from tests.test_frontend_v2_stage0 import JSC, STUBS, V2

JS = V2 / "js"
CSS = (V2 / "css/components.css").read_text() + (V2 / "css/pages.css").read_text()


def _run(tmp_path, body):
    exe = JSC if os.path.exists(JSC) else shutil.which("jsc")
    if not exe:
        pytest.skip("jsc not available")
    script = tmp_path / "check.mjs"
    script.write_text(STUBS + body)
    out = subprocess.run([exe, "-m", str(script)], capture_output=True, text=True, timeout=30)
    assert out.returncode == 0, out.stderr + out.stdout
    return json.loads(out.stdout.strip().splitlines()[-1])


def _src(rel):
    return (JS / rel).read_text()


# ------------------------------------------------------------ the chart read (C18)

UP = {"technicals": {
    "moving_averages": {"sma20": {"value": 340, "position": "above", "distance_pct": 1.8},
                        "sma50": {"value": 325, "position": "above", "distance_pct": 5.5, "slope_10d_pct": 1.02},
                        "sma200": {"value": 292, "position": "above", "distance_pct": 17.4}},
    "structure": {"stacked_bullish": True},
    "support_resistance": [{"role": "support", "distance_pct": -1.2, "band_low": 316.32, "band_high": 320.34},
                           {"role": "support", "distance_pct": -6.0, "band_low": 300, "band_high": 305},
                           {"role": "resistance", "distance_pct": 0.4, "band_low": 344.01, "band_high": 348.03}],
    "rsi": {"value": 62.4, "state": "bullish"}, "macd": {"state": "bullish", "event": "histogram expanding up"}}}
DOWN = {"technicals": {
    "moving_averages": {"sma50": {"value": 90, "position": "below", "distance_pct": -4.0, "slope_10d_pct": -0.5},
                        "sma200": {"value": 100, "position": "below", "distance_pct": -12.0}},
    "structure": {"stacked_bearish": True, "cross_event": "death cross"},
    "rsi": {"value": 28, "state": "oversold"}, "macd": {"state": "bearish"}}}


def test_the_chart_read_says_what_the_daily_technicals_say(tmp_path):
    got = _run(tmp_path, f"""
      const m = await import('{(JS / "ui/chartread.js").as_posix()}');
      print(JSON.stringify({{ up: m.chartReadModel({json.dumps(UP)}), down: m.chartReadModel({json.dumps(DOWN)}),
        none: m.chartReadModel({{ technicals: {{ moving_averages: {{ sma50: {{ value: 1 }} }} }} }}),
        mixed: m.chartReadModel({{ technicals: {{ moving_averages: {{ sma50: {{ value: 90 }}, sma200: {{ value: 100, position: 'above', distance_pct: 2 }} }} }} }}).trend }}));
    """)
    up, down = got["up"], got["down"]
    assert up["trend"] == "Uptrend" and down["trend"] == "Downtrend" and got["mixed"] == "Mixed trend"
    assert up["facts"][0] == "Price is 17.4% above the 200-day average."
    assert "stacked in rising order" in " ".join(up["facts"]) and "rising, 1.02% over ten sessions" in " ".join(up["facts"])
    assert up["support"]["band_low"] == 316.32, "the nearest support below the price, not the strongest"
    assert up["resistance"]["band_high"] == 348.03
    assert up["rsi"] == "Firm, 62" and up["macd"] == "Momentum building"
    assert down["rsi"] == "Oversold, 28" and down["macd"] == "Below its signal"
    assert "crossed below the 200-day" in " ".join(down["facts"])
    assert down["support"] is None and down["resistance"] is None
    assert got["none"] is None, "no 200-day average, no trend to read"


def test_the_chart_read_is_free_and_one_press_away():
    cr = _src("ui/chartread.js")
    assert "api." not in cr and "fetch(" not in cr, "the read fetches nothing and asks no model"
    assert "—" not in cr
    ch = _src("pages/chart.js")
    assert "data-v2-ch-read" in ch and "chartReadCard(D.sym, D.t" in ch
    assert "read: false" in ch, "closed by default, as the classic popover is, so the plot keeps its width"
    assert "read: V.read" in ch, "the choice is kept with the chart's other view settings"


# ------------------------------------------------------------ Milo's availability

def test_milo_buttons_say_milo_is_off_before_a_press():
    milo = _src("ui/milo.js")
    btn = milo[milo.index("export function button("):milo.index("\n}\n", milo.index("export function button("))]
    assert "aria-describedby=\"milo-off-desc\"" in btn
    chk = milo[milo.index("export async function checkAvailability"):milo.index("\n}\n", milo.index("export async function checkAvailability"))]
    assert "/api/ai-allowance" in chk and "enabled === false" in chk and "MutationObserver" in chk
    assert "checkAvailability();" in _src("app.js")
    assert 'html[data-milo="off"] .btn-milo::after' in CSS
    assert 'html[data-milo="off"] [data-v2-milo].btn.ws-ask::after { content: none; }' in CSS, "no tag in each Home panel header"
    # the drawer still explains, and still opens
    assert "Milo is switched off right now" in milo


# ------------------------------------------------------------ Financials

def test_financials_leads_with_a_summary_and_a_jump_list():
    fin = _src("pages/financials.js")
    paint = fin[fin.index("function paint()"):fin.index("\n}\n", fin.index("function paint()"))]
    order = re.findall(r"\$\{(readings|jumpList|statements|segments|record\('earnings'\)|ownership|record\('short'\)|extras|filings|congress)\(", paint)
    assert order[:3] == ["readings", "jumpList", "statements"] and order[3] == "segments"
    for sec in ("fin-summary", "fin-statements", "fin-segments", "fin-earnings", "fin-ownership", "fin-short", "fin-actions", "fin-filings", "fin-congress"):
        assert f'id="{sec}"' in fin, sec
    assert "data-fin-jump" in fin and "data-fin-jumpsel" in fin
    assert "prefers-reduced-motion" in fin
    # the Earnings tables share the rule since 2026-10-20 (backlog task 8)
    rule = CSS[CSS.index(".fin .tscroll .t th:first-child, .fin .tscroll .t td:first-child"):]
    assert rule.split("{")[1].strip().startswith("position: sticky; left: 0;") and ".earn .tscroll .t td:first-child" in rule.split("{")[0]
    assert "fin-card-v" in fin, "each chart card states its latest value and change"
