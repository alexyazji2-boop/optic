"""The macro regime reads the bond market in its own units.

Asked "does the macro tab take into account whats going on with the bond
markets right now?" on 1 October 2026: the 10-year at 5.29%, up half a point
in September, the 2-year up as much, the high-yield spread 46bp wider. Bonds
were most of a -12.2 score and still undercounted. The 10-year was scored on
the yield's percent change and capped at -4, which a quarter point reaches;
credit was HYG's price, which moves with Treasury yields too; HYG / TLT read
"risk-on" because Treasuries fell faster than junk bonds; and the notes said
nothing about bonds. Then "go ahead" with the four changes:

  * the 10-year scored in basis points, a rise in full (-0.2 per bp, to -10,
    which a half-point month reaches) and a fall at half, since a fast fall is
    as often a flight to safety as relief;
  * credit scored on the high-yield spread from FRED (-0.1 per bp wider, to
    12.5 either way, HYG's old cap), with HYG's price where FRED is out;
  * HYG / TLT "rates-led" when both legs moved the same way and Treasuries
    moved further;
  * a note when either moves 25bp in 20 sessions.

Checked on the local server against the day's data: -14.5 where it was -12.2,
the 10-year -8.8 for 44bp, the spread -4.6 for 46bp to 3.12%, HYG / TLT
rates-led, and the notes "10-year yield 5.24%, up 44bp in 20 sessions, near
its 52-week high. Bonds are selling off" and "High-yield spread 3.12%, 46bp
wider in 20 sessions. Credit is pricing more default risk".
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from app import fred
from app.analytics import macro

APP = (Path(__file__).resolve().parent.parent / "static/app.js").read_text()
# The module's own reader, taken at import: the suite's conftest stands a stub in
# for it during every test, so that nothing reads FRED.
REAL_READER = macro._hy_spread_rows


def _frame(vals):
    idx = pd.date_range("2025-01-01", periods=len(vals), freq="B", tz="America/New_York")
    return pd.DataFrame({"Close": vals, "High": vals, "Low": vals,
                         "Open": vals, "Volume": [1e6] * len(vals)}, index=idx)


def _flat(level, n=260):
    return [float(level)] * n


def _ramp(start, end, n=260, over=20):
    """Flat at `start`, then a straight line to `end` over the last `over` bars."""
    steps = [start + (end - start) * (i + 1) / over for i in range(over)]
    return _flat(start, n - over) + steps


class _Feed:
    def __init__(self, **series):
        self.series = series

    def batch_history(self, symbols, period="1y", interval="1d"):
        return {s: _frame(self.series.get(s, _flat(100.0))) for s in symbols}


def _spread_rows(start, end, n=260, over=20):
    days = pd.bdate_range(end="2026-09-30", periods=n)
    return [(str(d.date()), round(v, 4)) for d, v in zip(days, _ramp(start, end, n, over))]


def _day(monkeypatch, tnx=(4.796, 5.237), spread=(2.66, 3.12), hyg=(79.11, 76.9), tlt=(81.95, 77.71)):
    monkeypatch.setattr(macro, "_hy_spread_rows",
                        (lambda: _spread_rows(*spread)) if spread else (lambda: []))
    feed = _Feed(**{"^TNX": _ramp(*tnx), "^IRX": _flat(3.98), "HYG": _ramp(*hyg),
                    "TLT": _ramp(*tlt)})
    return macro.analyse(feed)


def _factor(out, name):
    return next((f for f in out["factors"] if f["factor"] == name), None)


def test_the_first_of_october_in_its_own_units(monkeypatch):
    out = _day(monkeypatch)
    y10 = _factor(out, "10-year yield 20-day")
    assert y10["unit"] == "bp" and y10["value"] == pytest.approx(44.1, abs=0.1)
    assert y10["contribution"] == pytest.approx(-8.82, abs=0.01), "it was -4.0, at its cap"
    assert y10["rule"].startswith("up 44bp in 20 sessions;")
    spread = _factor(out, "High-yield spread 20-day")
    assert spread["value"] == pytest.approx(46.0) and spread["contribution"] == pytest.approx(-4.6)
    assert spread["level"] == 3.12 and spread["as_of"] == "2026-09-30"
    assert _factor(out, "High-yield credit 20-day") is None, "credit is counted once, on the spread"
    assert out["score_unattributed"] == 0, "the terms still add up to the score"
    notes = [n for n in out["notes"] if n.startswith(("10-year", "High-yield"))]
    assert notes[0].endswith("up 44bp in 20 sessions, near its 52-week high. Bonds are selling off")
    assert notes[1] == ("High-yield spread 3.12%, 46bp wider in 20 sessions. "
                        "Credit is pricing more default risk")


def test_a_rise_counts_in_full_and_a_fall_at_half(monkeypatch):
    def contribution(start, end):
        return _factor(_day(monkeypatch, tnx=(start, end)), "10-year yield 20-day")["contribution"]
    assert contribution(4.20, 5.00) == -10.0, "a rise is capped at -10"
    assert contribution(5.00, 4.70) == pytest.approx(3.0), "+0.1 per bp down"
    assert contribution(5.00, 4.20) == 5.0, "and a fall at +5"
    assert contribution(4.50, 4.60) == pytest.approx(-2.0)


def test_small_moves_write_no_note_and_falls_say_rallying(monkeypatch):
    quiet = _day(monkeypatch, tnx=(4.50, 4.60), spread=(3.00, 3.10))
    assert not any(n.startswith(("10-year", "High-yield")) for n in quiet["notes"])
    rally = _day(monkeypatch, tnx=(5.00, 4.60), spread=(3.40, 3.00))
    lines = [n for n in rally["notes"] if n.startswith(("10-year", "High-yield"))]
    assert lines[0].endswith("down 40bp in 20 sessions. Bonds are rallying"), lines[0]
    assert lines[1] == "High-yield spread 3.00%, 40bp tighter in 20 sessions. Credit appetite is strong"
    assert _factor(rally, "High-yield spread 20-day")["contribution"] == pytest.approx(4.0)


def test_without_fred_the_credit_term_is_hygs_price(monkeypatch):
    out = _day(monkeypatch, spread=None)
    assert _factor(out, "High-yield spread 20-day") is None
    hyg = _factor(out, "High-yield credit 20-day")
    assert hyg is not None and hyg["contribution"] < 0
    assert out["score_unattributed"] == 0


def test_hyg_tlt_says_when_its_move_is_rates(monkeypatch):
    def ratio(hyg, tlt):
        r = next(r for r in _day(monkeypatch, hyg=hyg, tlt=tlt)["ratios"] if r["name"] == "HYG / TLT")
        return r["signal"], r["signal_note"]
    signal, note = ratio((79.11, 76.9), (81.95, 77.71))         # both down, TLT further
    assert signal == "rates-led" and note.startswith("Both fell over 20 sessions and Treasuries fell further")
    signal, note = ratio((76.0, 78.0), (80.0, 84.0))            # both up, TLT further
    assert signal == "rates-led" and "not a move to safety" in note
    assert ratio((76.0, 78.0), (80.0, 79.0)) == ("risk-on", None), "junk up, Treasuries down"
    assert ratio((80.0, 76.0), (80.0, 79.0)) == ("risk-off", None), "both down, junk further"


def test_a_fred_failure_is_not_retried_on_every_load(monkeypatch):
    calls = []

    def observations(series, timeout=None):
        calls.append((series, timeout))
        return []

    monkeypatch.setattr(fred, "observations", observations)
    monkeypatch.setattr(macro, "_HY_FAILED_AT", [0.0])
    assert REAL_READER() == [] and REAL_READER() == []
    assert calls == [("BAMLH0A0HYM2", 4.0)], "one try, with the short timeout, then fifteen minutes"
    macro._HY_FAILED_AT[0] -= macro.HY_RETRY_SECONDS + 1
    REAL_READER()
    assert len(calls) == 2, "and tried again after them"


def test_fred_takes_the_timeout_and_the_card_shows_why():
    src = Path(fred.__file__).read_text()
    assert 'key="fred:" + series, user_agent="", timeout=timeout)' in src
    assert "${r.signal_note ? `<p class=\"caveat\"" in APP
