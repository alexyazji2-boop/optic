"""How an option's value moves (renderGreeksLab in static/app.js): the pricer
against textbook values, and the lab's wiring."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
APP = (ROOT / "static/app.js").read_text()
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc"


def _fn(name):
    start = APP.index("function {}(".format(name))
    return APP[start:APP.index("\n}\n", start) + 3]


def _js(script):
    exe = JSC if os.path.exists(JSC) else shutil.which("jsc")
    if not exe:
        pytest.skip("no JavaScriptCore")
    out = subprocess.run([exe, "-e", _fn("glCdf") + _fn("glBS") + script], capture_output=True, text=True, timeout=30)
    return json.loads(out.stdout.strip().splitlines()[-1])


def test_black_scholes_matches_the_textbook():
    r = _js("print(JSON.stringify([glBS(100,100,1,0.2,0.05,true), glBS(100,100,1,0.2,0.05,false)]))")
    call, put = r
    assert call["price"] == pytest.approx(10.4506, abs=1e-3)
    assert put["price"] == pytest.approx(5.5735, abs=1e-3)
    assert call["delta"] == pytest.approx(0.6368, abs=1e-3)
    assert put["delta"] == pytest.approx(0.6368 - 1, abs=1e-3)
    assert call["gamma"] == pytest.approx(0.018762, abs=1e-5)


def test_at_expiry_it_is_worth_what_it_is_worth():
    r = _js("print(JSON.stringify([glBS(110,100,0,0.2,0.05,true), glBS(90,100,0,0.2,0.05,true), glBS(90,100,0,0.2,0.05,false)]))")
    assert [x["price"] for x in r] == [10, 0, 10]


def test_decay_speeds_up_into_expiry():
    r = _js("""var day = function (d) { return glBS(100,100,d/365,0.3,0.04,true).price - glBS(100,100,(d-1)/365,0.3,0.04,true).price; };
               print(JSON.stringify([day(60), day(30), day(7), day(2)]))""")
    assert r[0] < r[1] < r[2] < r[3]


def test_the_lab_is_on_the_options_tab_and_says_it_is_a_model():
    assert "${renderGreeksLab(d)}" in APP
    lab = _fn("renderGreeksLab")
    assert "A lesson, not a quote" in lab
    assert "data-gl-set=\"kind\"" in lab and "data-gl-set=\"dte\"" in lab and "data-gl-set=\"iv\"" in lab
