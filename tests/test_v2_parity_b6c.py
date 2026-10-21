"""Classic parity, batch B6c (2026-10-21): the track record on Options, Investing and the Overview's stage.

Part 1 takes from the unmerged `validation` branch only what the slots need: /api/validation's `history` (main.py,
14 lines) and the file it reads, app/validation/history.json, byte for byte as the branch has it (the program's
pre-registered results to 2026-10-14). Nothing else of the branch is taken: its research code, its docs, the retirement
planner's change to total returns and its wording edits in the analytics stay on the branch for the owner.
Part 2's wording runs in JavaScriptCore below. The slots on their pages were checked in headless Chrome
(~/Optic/work/classic-parity/b6c_check.py). Ledger: docs/frontend-v2/CLASSIC-PARITY.md, B6c.
"""
import json
import subprocess
from pathlib import Path

from fastapi.testclient import TestClient

from app import main as m
from app import signal_archive as sa
from tests.test_frontend_v2_stage0 import V2, _run

ROOT = Path(__file__).resolve().parent.parent
JS = V2 / "js"


def test_the_endpoint_adds_what_history_says(monkeypatch):
    monkeypatch.setattr(m, "_VALIDATION", {"at": 0.0, "body": None})
    monkeypatch.setattr(sa, "reads", lambda: [])
    got = TestClient(m.app).get("/api/validation").json()
    h = got["history"]
    assert got["claims"]["composite"]["status"] == "collecting", "the forward record is unchanged"
    assert set(h) == {"as_of", "method", "rules", "scale", "untestable"} and h["as_of"] == "2026-10-14"
    for key in ("setups", "trend_score", "iv_verdict", "candles", "long_term", "stage", "regime", "backtest"):
        assert h["rules"][key]["line"] and h["rules"][key]["sample"], key
    assert "Benjamini-Hochberg" in h["method"] and "no free history of open interest" in h["untestable"]


def test_a_missing_or_broken_history_is_none_not_an_error(monkeypatch, tmp_path):
    monkeypatch.setattr(m, "_VALIDATION_HISTORY_PATH", tmp_path / "nope.json")
    assert m._validation_history() is None
    bad = tmp_path / "bad.json"; bad.write_text("{not json")
    monkeypatch.setattr(m, "_VALIDATION_HISTORY_PATH", bad)
    assert m._validation_history() is None


def test_the_file_is_the_branchs_own():
    try:
        theirs = subprocess.run(["git", "-C", str(ROOT), "show", "validation:app/validation/history.json"], capture_output=True, check=True).stdout
    except (subprocess.CalledProcessError, FileNotFoundError):
        return   # a checkout without the branch (a deploy): nothing to compare against
    assert (ROOT / "app/validation/history.json").read_bytes() == theirs
    assert not (ROOT / "app/validation/__init__.py").exists(), "the research package itself is not taken"


# ---------------------------------------------------------------- part 2: the words, and where they are said
BODY = """{ claims: {
    composite: { status: 'collecting', since: '2026-10-19', counts: { observations: 13, days: 2 } },
    regime: { status: 'collecting', counts: { positive: 1, negative: 0 } },
    walls: { status: 'tested', counts: { touches: 60 }, result: { wall_hold_pct: 58, placebo_hold_pct: 51, horizon_days: 5 } },
    setups: { status: 'tested', counts: { observations: 80 }, result: { by_horizon: { '10 candles': { beat_spy_pct: 52, mean_excess_pct: 0.31, n: 80 } } } } },
  history: { method: 'M', scale: 'S', untestable: 'U', rules: {
    trend_score: { what: 'w', line: '4 of 4 tests showed no reliable effect.', sample: '58 names', counts: { n: 4 } },
    setups: { what: 'w', line: '34 of 34 tests showed no reliable effect.', sample: '58 names', counts: {} } } } }"""


def test_the_track_record_in_classics_words(tmp_path):
    got = _run(tmp_path, f"""
      const T = await import('{(JS / "core/track.js").as_posix()}');
      const b = {BODY};
      print(JSON.stringify({{ none: ['composite', 'setups', 'other'].map((k) => T.forwardText(k, null)),
        comp: T.trackText('composite', b), reg: T.trackText('regime', b), walls: T.forwardText('walls', b), setups: T.trackText('setups', b),
        nohist: T.trackText('regime', {{ claims: {{}} }}), line: [T.historyLine('setups', b), T.historyLine('candles', b)], ctx: T.context(b), ctx0: T.context(null) }}));
    """)
    assert got["none"] == ["not yet tested: not yet shown to predict returns.", "not yet tested: not yet shown to beat the market.", "not yet tested."], "before the record answers, nothing is implied"
    c = got["comp"]
    assert c["fwd"] == ("not yet tested. Optic began keeping this read on Oct 19 2026; a fair test needs 200 readings over 20 trading days, "
                        "so far 13 readings over 2 days. Until then, treat it as a description, not a prediction.")
    assert c["hist"] == ["Its chart input, replayed on history:", "4 of 4 tests showed no reliable effect. Sample: 58 names."]
    assert got["reg"]["fwd"].endswith("so far 1 positive and 0 negative reading. Until then, treat it as a description, not a prediction.")
    assert got["reg"]["hist"][1] == "No history of open interest exists, so this forward record is its only test." and got["nohist"]["hist"] is None
    assert got["walls"] == "price closed back on the near side the first day it reached a wall 58% of the time, against 51% for the strikes beside it (60 touches, within 5 days)."
    assert got["setups"]["fwd"] == "after 10 candles, 52% of setups beat SPY in their direction, by +0.31% on average (80 setups)."
    assert got["line"] == ["34 of 34 tests showed no reliable effect. Sample: 58 names.", ""]
    assert got["ctx"]["history"]["rules"]["setups"] == {"rule": "w", "result": "34 of 34 tests showed no reliable effect.", "sample": "58 names", "counts": {}}
    assert got["ctx0"]["status"] == "not yet tested" and "has not shown" in got["ctx0"]["note"]
    classic = (V2.parent / "app.js").read_text()
    for w in ("not yet shown to predict returns.", "not yet shown to beat the market.", "Until then, treat it as a description, not a prediction."):
        assert w in classic, w


def test_where_the_track_record_is_said():
    panels = (JS / "pages/options-panels.js").read_text()
    for s in ("TR.slot('composite')", "TR.slot('regime')}${TR.slot('walls')", "TR.slot('setups')", "TR.historySlot('iv_verdict')", "TR.historySlot('candles')"):
        assert s in panels, s
    assert "TR.historySlot('long_term')" in (JS / "pages/investing.js").read_text()
    assert "session ? '' : TR.historySlot('backtest')" in (JS / "pages/chart-widgets.js").read_text()
    assert "TR.historySlot('regime')" in (JS / "pages/read.js").read_text()
    assert "tested ? `Replayed on history: ${tested}` : ''" in (JS / "pages/dossier.js").read_text()
    for page in ("options", "investing"):
        assert "track_record: TR.context()," in (JS / f"pages/{page}.js").read_text(), page
