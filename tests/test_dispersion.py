"""Dispersion (app/analytics/dispersion.py): Cboe's VIXEQ against the VIX."""
from __future__ import annotations

import pandas as pd
import pytest

from app.analytics import dispersion as dp
from app.desk import evidence as ev


class FakeProvider:
    def __init__(self, values, dspx_days=300):
        self.values = values
        self.dspx_days = dspx_days

    def history(self, sym, period="5d", interval="1d"):
        if sym not in self.values:
            return pd.DataFrame()
        if sym == "^DSPX":
            idx = pd.bdate_range(end="2026-10-13", periods=self.dspx_days)
            vals = [20 + i * 0.05 for i in range(self.dspx_days - 1)] + [self.values[sym]]
            return pd.DataFrame({"Close": vals}, index=idx)
        return pd.DataFrame({"Close": [self.values[sym]]}, index=pd.DatetimeIndex(["2026-10-13"]))


VALS = {"^VIX": 15.27, "^VIXEQ": 39.8, "^COR1M": 7.57, "^DSPX": 36.77}


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.setenv("TRACKER_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("OPTIC_CBOE_HISTORY", raising=False)
    return tmp_path


def test_today_reads_without_history_and_says_so(store):
    r = dp.build(FakeProvider(VALS))
    assert r["available"] and r["gap"] == pytest.approx(24.53)
    assert r["gap_percentile"] is None and r["cor1m_percentile"] is None
    # DSPX has Yahoo history: the last of a rising series beats the rest.
    assert r["dspx_percentile"] == pytest.approx(299 / 300 * 100, abs=0.1)
    assert "a gap of 24.5 points" in r["text"] and "wider than" not in r["text"]
    assert "did not predict" not in r["text"] and "predicted nothing" in r["evidence"]["finding"]


def test_each_day_is_stored_once(store):
    dp.build(FakeProvider(VALS))
    dp.build(FakeProvider(dict(VALS, **{"^VIX": 16.0})))
    assert dp.stored("VIX") == {"2026-10-13": 16.0}


def _csv(name, rows):
    if name in ("VIXEQ", "DSPX"):
        return "DATE,{}\n".format(name) + "".join("{},{}\n".format(d, v) for d, v in rows)
    return "DATE,OPEN,HIGH,LOW,CLOSE\n" + "".join("{0},{1},{1},{1},{1}\n".format(d, v) for d, v in rows)


def test_cboe_history_only_when_switched_on(store, monkeypatch):
    days = pd.bdate_range("2025-01-02", periods=200)
    series = {"VIX": [15.0] * 200, "VIXEQ": [25.0 + i * 0.05 for i in range(200)], "COR1M": [20.0 - i * 0.05 for i in range(200)],
              "DSPX": [25.0] * 200}
    asked = []

    def fetch(url):
        name = url.split("/")[-1].replace("_History.csv", "")
        asked.append(name)
        return _csv(name, [(d.strftime("%m/%d/%Y"), v) for d, v in zip(days, series[name])])

    r = dp.build(FakeProvider(VALS), fetch=fetch)
    assert asked == [] and r["gap_percentile"] is None
    monkeypatch.setenv("OPTIC_CBOE_HISTORY", "1")
    r = dp.build(FakeProvider(VALS), fetch=fetch)
    assert set(asked) == {"VIX", "VIXEQ", "COR1M", "DSPX"}
    # Today's gap (24.5) is wider than every day of a history that ran 10 to
    # 19.95; today's own reading is in the history too, as in the IV rank.
    assert r["gap_percentile"] == pytest.approx(200 / 201 * 100, abs=0.1) and r["gap_history_from"] == "2025-01-02"
    assert r["cor1m_percentile"] == 0.0 and "lower than 100% of days" in r["text"]
    assert any("Cboe daily index history" in s for s in r["sources"])


def test_missing_vixeq_is_unavailable_not_guessed(store):
    r = dp.build(FakeProvider({"^VIX": 15.0}))
    assert r["available"] is False


def test_the_desk_gets_a_row_that_says_what_the_gap_did_not_predict(store):
    g = ev.Gatherer()
    ev.gather_dispersion(g, dp.build(FakeProvider(VALS)))
    row = g.rows[-1]
    assert row.kind == "volatility" and row.value == pytest.approx(24.53) and row.unit == "pts"
    assert "do not call it a warning" in row.method
    g2 = ev.Gatherer()
    ev.gather_dispersion(g2, {"available": False, "reason": "x"})
    assert not g2.rows and g2.coverage[-1]["ok"] is False


def test_ordinals_read_as_english():
    import json, os, shutil, subprocess
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    app = (root / "static/app.js").read_text()
    fn = app[app.index("function ordinal("):]
    fn = fn[:fn.index("\n}\n") + 3]
    jsc = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc"
    exe = jsc if os.path.exists(jsc) else shutil.which("jsc")
    if not exe:
        pytest.skip("no JavaScriptCore")
    out = subprocess.run([exe, "-e", fn + "print(JSON.stringify([1,2,3,4,11,12,13,21,22,98,101,111].map(ordinal)))"],
                         capture_output=True, text=True, timeout=30).stdout
    assert json.loads(out) == ["1st", "2nd", "3rd", "4th", "11th", "12th", "13th", "21st", "22nd", "98th", "101st", "111th"]
    assert "th percentile`" not in app.replace("${ordinal(", "")
