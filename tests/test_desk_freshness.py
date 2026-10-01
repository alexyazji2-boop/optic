"""The Optic Desk's futures figures stay accurate all day.

Reported as: the futures percentages on the desk are not accurate. Two causes.

The one in the screenshot was the reference price, fixed in the provider and
tested in test_live_quote_change.py: every row was measured from yfinance's
hourly `previousClose`, which for a future on a Monday is Sunday evening's
price, so the desk printed S&P 500 futures up 0.12% while the index was down
0.42%.

The other is tested here. The written desk is written once a day, and its lead
quotes the index futures and the VIX, so those figures froze at whatever the
first reader of the day saw and stayed on the home page until midnight. Now the
written voice gives way to the deterministic desk, built live on every request,
once the tape has moved past what it quotes.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

import app.main as main

ROOT = Path(__file__).resolve().parent.parent


def _tape(es=-0.11, nq=-0.09, rty=-0.05, vix=16.08):
    return {"futures": [{"symbol": "ES=F", "chg_1d": es}, {"symbol": "NQ=F", "chg_1d": nq},
                        {"symbol": "RTY=F", "chg_1d": rty}],
            "vix": {"symbol": "^VIX", "last": vix}}


def _marks(**kw):
    return main._desk_tape({"tape": _tape(**kw)})


# ------------------------------------------------------------------ the rule


def test_the_marks_are_the_figures_the_lead_quotes():
    assert _marks() == {"ES=F": -0.11, "NQ=F": -0.09, "RTY=F": -0.05, "^VIX": 16.08}


@pytest.mark.parametrize("now,moved", [
    ({}, False),                              # nothing changed
    ({"es": -0.19}, False),                   # within a tenth, same word
    ({"es": -0.25}, True),                    # 0.14 points on the S&P
    ({"nq": -0.21}, True),                    # 0.12 on the Nasdaq
    ({"rty": 0.06}, True),                    # 0.11 points, though both read "flat"
    ({"vix": 16.5}, False),                   # under half a point
    ({"vix": 16.7}, True),                    # over it
])
def test_moved_is_a_tenth_of_a_point_or_half_a_vix_point(now, moved):
    assert main._desk_moved(_marks(), _marks(**now)) is moved


def test_a_word_the_lead_would_now_print_differently_is_stale_at_any_size():
    """0.12 is "up slightly" and 0.08 is "flat": four hundredths apart, and a
    lead that still says up is wrong."""
    then, now = _marks(es=0.12), _marks(es=0.08)
    assert abs(0.12 - 0.08) < main.DESK_STALE_PCT
    assert main._desk_moved(then, now) is True


def test_a_figure_that_vanished_is_stale():
    now = _marks()
    now["ES=F"] = None
    assert main._desk_moved(_marks(), now) is True


# ------------------------------------------------------------- the assembly


@pytest.fixture
def desk_parts(monkeypatch):
    """_morning_desk with every network leg stubbed and the tape settable."""
    live = {"tape": _tape()}
    monkeypatch.setattr(main.events_mod, "upcoming", lambda: {"events": []})
    monkeypatch.setattr(main.YF_PROVIDER, "batch_quote", lambda syms: {})
    monkeypatch.setattr(main.YF_PROVIDER, "contract_month", lambda sym: None)
    monkeypatch.setattr(main.econ_mod, "series", lambda *a, **k: None)
    monkeypatch.setattr(main, "_home_read", lambda: {"stories": []})
    monkeypatch.setattr(main.morning_desk_mod, "build", lambda **k: {
        "date": "2026-09-28", "tape": live["tape"], "lead": ["assembled lead"],
        "scenarios": [], "note": "assembled note", "overall": "assembled overall"})
    monkeypatch.setattr(main.ai, "available", lambda: {"enabled": True})
    # A stale desk is written again in the background; never for real here.
    monkeypatch.setattr(main.ai, "write_morning_desk", lambda desk: None)
    return live, monkeypatch


def _written(tape_marks):
    return {"lead": ["written lead, futures -0.11%"], "scenarios": [], "note": "",
            "overall": "", "written_by": "claude", "tape_marks": tape_marks,
            "written_at": "2026-09-28T13:05:00+00:00"}


def test_the_written_desk_shows_while_the_tape_still_matches_it(desk_parts):
    live, patch = desk_parts
    patch.setattr(main, "_desk_prose", lambda desk: _written(_marks()))
    desk = main._morning_desk(None)
    assert desk["voice"] == "written" and desk["lead"] == ["written lead, futures -0.11%"]
    assert "voice_reason" not in desk


def test_the_live_desk_replaces_it_once_the_tape_has_moved(desk_parts):
    live, patch = desk_parts
    patch.setattr(main, "_desk_prose", lambda desk: _written(_marks()))
    live["tape"] = _tape(es=0.12, nq=0.19, rty=0.23, vix=15.91)
    desk = main._morning_desk(None)
    assert desk["voice"] == "mechanical" and desk["lead"] == ["assembled lead"]
    assert desk["voice_reason"] == "moved"
    assert desk["written_at"] == "2026-09-28T13:05:00+00:00"


@pytest.mark.parametrize("enabled,reason", [(True, "unwritten"), (False, "unconfigured")])
def test_a_missing_written_desk_says_which_kind_of_missing(desk_parts, enabled, reason):
    """"Not configured on this deployment" was printed on the live site, where
    the assistant is configured and the day's note had simply failed."""
    live, patch = desk_parts
    patch.setattr(main, "_desk_prose", lambda desk: None)
    patch.setattr(main.ai, "available", lambda: {"enabled": enabled})
    assert main._morning_desk(None)["voice_reason"] == reason


def test_the_written_desk_records_what_it_was_written_against(monkeypatch):
    monkeypatch.setattr(main, "_DESK_PROSE", {})
    monkeypatch.setattr(main.ai, "write_morning_desk", lambda desk: {"lead": ["x"]})
    prose = main._desk_prose({"date": "2026-09-28", "tape": _tape()})
    assert prose["tape_marks"] == _marks()
    assert prose["written_at"]


# ------------------------------------------------------------------ the page

APP_RAW = (ROOT / "static/app.js").read_text()
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc"


def _raw_fn(name):
    return re.search(r"^function " + name + r"\([^\n]*\) \{.*?^\}", APP_RAW, re.M | re.S).group()


def test_the_line_under_the_desk_says_why_it_is_the_assembled_one():
    exe = JSC if os.path.exists(JSC) else shutil.which("jsc")
    if not exe:
        pytest.skip("no JavaScriptCore on this machine")
    src = ("function assert(v, m) { if (!v) throw new Error(m); }\n"
           "function activeZone() { return 'UTC'; }\n"
           "function stampIn(iso) { return 'STAMP'; }\n"
           + _raw_fn("deskVoiceReason") + """
      var moved = deskVoiceReason({voice_reason: 'moved', written_at: 'T'});
      assert(moved.indexOf('from STAMP is not shown') > 0 && moved.indexOf('no longer match') > 0, moved);
      assert(deskVoiceReason({voice_reason: 'unwritten'}).indexOf('could not be produced') > 0, 'unwritten');
      assert(deskVoiceReason({voice_reason: 'unconfigured'}).indexOf('not configured') > 0, 'unconfigured');
      assert(deskVoiceReason({}).indexOf('not configured') > 0, 'an old payload');
      print('TEST_OK');""")
    out = subprocess.run([exe, "-e", src], capture_output=True, text=True, timeout=30)
    assert "TEST_OK" in out.stdout, out.stdout + out.stderr


# ------------------------------------------------------------- written again


def _settle():
    """Wait for any rewrite started in the background to finish."""
    import threading
    for t in [t for t in threading.enumerate() if t.name == "desk-rewrite"]:
        t.join(timeout=5)


@pytest.fixture
def rewrites(desk_parts, monkeypatch):
    """The desk with a counting writer: the nth write's lead says n."""
    live, patch = desk_parts
    patch.setattr(main, "_DESK_PROSE", {})
    written = []

    def write(desk):
        written.append(dict(desk["tape"]))
        return {"lead": ["written {}".format(len(written))], "scenarios": [], "note": "",
                "overall": "", "written_by": "claude"}
    patch.setattr(main.ai, "write_morning_desk", write)
    return live, patch, written


def test_a_desk_the_tape_has_moved_past_is_written_again(rewrites):
    """Asked for as "just have it update whenever necessary". Necessary is the
    same test that hides it: once the futures or the VIX have moved past what
    the written desk says, a new one is written against the tape as it is."""
    live, patch, written = rewrites
    first = main._morning_desk(None)
    assert first["voice"] == "written" and first["lead"] == ["written 1"]
    live["tape"] = _tape(es=0.12, nq=0.19, rty=0.23, vix=15.91)
    moved = main._morning_desk(None)
    # The reader who found it stale is not kept waiting for the rewrite.
    assert moved["voice"] == "mechanical" and moved["voice_reason"] == "moved"
    assert moved["rewriting"] is True
    _settle()
    again = main._morning_desk(None)
    assert again["voice"] == "written" and again["lead"] == ["written 2"]
    assert len(written) == 2 and written[1] == live["tape"], "written against the new tape"


def test_one_rewrite_a_half_hour_at_most(rewrites):
    live, patch, written = rewrites
    main._morning_desk(None)
    live["tape"] = _tape(es=0.12, nq=0.19, rty=0.23, vix=15.91)
    main._morning_desk(None)
    _settle()
    live["tape"] = _tape(es=-0.4, nq=-0.5, rty=-0.6, vix=17.2)
    later = main._morning_desk(None)
    assert later["voice_reason"] == "moved" and later["rewriting"] is False
    assert len(written) == 2, "the second move inside the same half hour waits"
    assert main.DESK_REWRITE_SECONDS == 1800


def test_and_a_dozen_a_day_at_most(rewrites):
    live, patch, written = rewrites
    assert main.DESK_REWRITES_PER_DAY == 12
    patch.setattr(main, "DESK_REWRITE_SECONDS", 0.000001)     # every request its own slot
    patch.setattr(main, "DESK_REWRITES_PER_DAY", 2)
    main._morning_desk(None)
    for es in (0.5, 1.0, 1.5, 2.0):
        live["tape"] = _tape(es=es, nq=es, rty=es, vix=15.0 + es)
        main._morning_desk(None)
        _settle()
    assert len(written) == 1 + 2, "the first write, then two rewrites"


def test_no_assistant_no_rewrite(rewrites):
    live, patch, written = rewrites
    main._morning_desk(None)
    patch.setattr(main.ai, "available", lambda: {"enabled": False})
    live["tape"] = _tape(es=0.12, nq=0.19, rty=0.23, vix=15.91)
    assert main._morning_desk(None)["rewriting"] is False
    _settle()
    assert len(written) == 1


def test_the_line_under_the_desk_says_a_new_one_is_coming():
    fn = _raw_fn("deskVoiceReason")
    assert "(d.rewriting ? ' A new one is being written against the figures above.' : '')" in fn
