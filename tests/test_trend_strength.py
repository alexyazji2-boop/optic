"""The Trend Strength Oscillator pane on the Charting tab (2026-10-12).

Asked for with TrendSpider's email ("Momentum or Mirage?", KO daily, TSO
14, 14, 5): "add this feature to the charting tab as well". The formula is
TrendSpider's published script: (ADX - 25) / 75 * 100 + (RSI - 50), a 5-bar
simple average of that, dotted levels at +50, 0 and -50, green above +50 and
red below -50 ("Bullish/Bearish Trend Overextension").
"""
from __future__ import annotations

import json
import math
import os
import re
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from app.analytics import indicators

ROOT = Path(__file__).resolve().parent.parent
APP = (ROOT / "static/app.js").read_text()
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc"


def _fn(name: str) -> str:
    return re.search(r"^function " + name + r"\([^\n]*\) \{.*?^\}", APP, re.M | re.S).group()


def _bars(n: int = 400, seed: int = 7):
    rng = np.random.default_rng(seed)
    close = 100 * np.exp(np.cumsum(rng.normal(0.0004, 0.015, n) + 0.01 * np.sin(np.arange(n) / 25)))
    spread = np.abs(rng.normal(0, 0.012, n)) * close
    high = close + spread * rng.uniform(0.2, 1.0, n)
    low = close - spread * rng.uniform(0.2, 1.0, n)
    return [round(x, 4) for x in high], [round(x, 4) for x in low], [round(x, 4) for x in close]


def _js(high, low, close):
    exe = JSC if os.path.exists(JSC) else shutil.which("jsc")
    if not exe:
        pytest.skip("no JavaScriptCore on this machine")
    consts = re.search(r"^const TSO_ADX = [^\n]*;", APP, re.M).group()
    src = "\n".join([consts, _fn("smaSeries"), _fn("rsiSeries"), _fn("adxSeries"), _fn("tsoSeries"),
                     "var h = %s, l = %s, c = %s;" % (json.dumps(high), json.dumps(low), json.dumps(close)),
                     "print(JSON.stringify({ adx: adxSeries(h, l, c, 14), tso: tsoSeries(h, l, c),"
                     " rsi: rsiSeries(c, 14) }));"])
    out = subprocess.run([exe, "-e", src], capture_output=True, text=True, timeout=30)
    return json.loads(out.stdout)


def _wilder_adx(high, low, close, p=14):
    """Textbook Wilder (New Concepts, 1978): sums seed the smoothing, the first
    ADX is the mean of the first p DX values."""
    n = len(close)
    out = [None] * n
    tr = pdm = mdm = 0.0
    dxs = []
    adx = None
    for i in range(1, n):
        up, down = high[i] - high[i - 1], low[i - 1] - low[i]
        t = max(high[i] - low[i], abs(high[i] - close[i - 1]), abs(low[i] - close[i - 1]))
        pm = up if up > down and up > 0 else 0.0
        mm = down if down > up and down > 0 else 0.0
        if i <= p:
            tr, pdm, mdm = tr + t, pdm + pm, mdm + mm
            if i < p:
                continue
        else:
            tr, pdm, mdm = tr - tr / p + t, pdm - pdm / p + pm, mdm - mdm / p + mm
        pdi, mdi = 100 * pdm / tr, 100 * mdm / tr
        dx = 100 * abs(pdi - mdi) / (pdi + mdi) if pdi + mdi else 0.0
        if adx is None:
            dxs.append(dx)
            if len(dxs) == p:
                adx = sum(dxs) / p
                out[i] = adx
        else:
            adx = (adx * (p - 1) + dx) / p
            out[i] = adx
    return out


def test_adx_is_wilders():
    high, low, close = _bars()
    got = _js(high, low, close)["adx"]
    want = _wilder_adx(high, low, close)
    assert got.index(next(v for v in got if v is not None)) == 27, "first ADX on bar 2p-1"
    assert all((a is None) == (b is None) for a, b in zip(got, want))
    assert max(abs(a - b) for a, b in zip(got, want) if a is not None) < 1e-9
    # And the server's (an exponential average seeded differently) agrees once
    # both have warmed up.
    df = pd.DataFrame({"High": high, "Low": low, "Close": close})
    server = indicators.adx(df, 14)["adx"].tolist()
    assert max(abs(got[i] - server[i]) for i in range(150, len(close))) < 0.5


def test_tso_is_trendspiders_formula():
    high, low, close = _bars()
    out = _js(high, low, close)
    adx, rsi, tso = out["adx"], out["rsi"], out["tso"]
    raw = [None if a is None or r is None else (a - 25) / 75 * 100 + (r - 50) for a, r in zip(adx, rsi)]
    for i in range(len(close)):
        window = raw[i - 4:i + 1] if i >= 4 else [None]
        want = sum(window) / 5 if None not in window else None
        assert (tso[i] is None) == (want is None), i
        if want is not None:
            assert math.isclose(tso[i], want, abs_tol=1e-9), i
    vals = [v for v in tso if v is not None]
    assert min(vals) < 0 < max(vals), "the synthetic trend runs both ways"


def test_the_pane_is_offered_and_drawn_like_the_others():
    panes = APP[APP.index("const WS_PANES = ["):]
    panes = panes[:panes.index("];")]
    assert "{ id: 'tso', label: 'Trend Strength Oscillator', height: 132 }" in panes
    osc = _fn("wsWithOscillators")
    assert "out.tso = tsoSeries(base.high || [], base.low || [], closes);" in osc
    mount = _fn("wsMountPanes")
    assert "mount('ws-pane-tso'" in mount
    assert "yTicks: [-TSO_LEVEL, 0, TSO_LEVEL]" in mount
    assert "{ value: TSO_LEVEL, label: '', color: C.pos, emphasis: true }" in mount
    assert "{ value: -TSO_LEVEL, label: '', color: C.neg, emphasis: true }" in mount
    assert "v > TSO_LEVEL ? C.pos : v < -TSO_LEVEL ? C.neg : null" in mount
    assert "'overextended up'" in mount and "'overextended down'" in mount
    assert "const TSO_ADX = 14, TSO_RSI = 14, TSO_SMOOTH = 5, TSO_LEVEL = 50;" in APP
