"""The Ask Pulse questions on Home, from what happened today.

Asked for with a screenshot of the panel: "these are relatively the same each
day with different numbers, alter these every day based on what goes on this
day". The day's biggest move led, and four standing templates rotated under
it, most on twenty-day changes, which hardly move from one day to the next.

Now the day's own events come first: the biggest move, asked in its market's
own words; the session when it is shut; the day's top story; the release due
today or tomorrow; and any other move bigger than its instrument's ordinary
day, in a market not already asked about. The standing questions fill what is
left, and skip one that a question above already asks. On 2026-10-01 the
panel read: EUR/USD down 0.8%; the FT's "Top Fed official signals central bank
will keep rates on hold in October"; the jobs report out tomorrow at 8:30 AM
ET; the US 3M yield down 1.2%; VIX at 16.5. The standing Fed question gave way
to the Fed story.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc"


def _questions(payload, extra=""):
    exe = JSC if os.path.exists(JSC) else shutil.which("jsc")
    if not exe:
        pytest.skip("no JavaScriptCore on this machine")
    script = """
      load('tests/support/browser_stubs.js');
      document.documentElement.style = document.documentElement.style || {};
      document.documentElement.style.setProperty = function () {};
      document.documentElement.style.removeProperty = function () {};
      try { load('static/charts.js'); load('static/app.js'); } catch (e) {}
      var data = %s;
      %s
      var html = marketQuestions(data);
      var qs = (html.match(/data-ask-text="[^"]*"/g) || []).map(function (a) {
        return a.slice(15, -1).replace(/&#39;/g, "'").replace(/&quot;/g, '"').replace(/&amp;/g, '&');
      });
      print('RESULT:' + JSON.stringify(qs));
    """ % (json.dumps(payload), extra)
    out = subprocess.run([exe, "-e", script], capture_output=True, text=True, timeout=120,
                         cwd=str(ROOT))
    assert "RESULT:" in out.stdout, (out.stdout + out.stderr)[-2000:]
    return json.loads(out.stdout.split("RESULT:", 1)[1].split("\n")[0])


def _inst(label, chg, atr, **more):
    return {"label": label, "chg_1d": chg, "atr_pct": atr, "chg_20d": more.pop("chg_20d", 1.0),
            "last": more.pop("last", 100.0), **more}


def _day(**over):
    data = {
        "session": {"now_et": "2026-10-01T14:00:00-04:00", "phase": "regular"},
        "macro": {
            "regime": "mildly risk-off",
            "groups": {
                "fx": [_inst("EUR/USD", -0.83, 0.51), _inst("DXY", 0.62, 0.45)],
                "rates": [_inst("US 3M", -1.19, 0.82), _inst("US 10Y", -1.02, 1.5)],
                "volatility": [_inst("VIX", 0.7, 5.0, last=16.5)],
                "commodities": [_inst("WTI Crude", 2.77, 4.98)],
                "equity": [_inst("S&P 500", 0.2, 1.0)],
            },
            "ratios": [{"name": "Copper / Gold", "chg_20d": 6.0, "reads": "industrial demand vs safety bid"}],
        },
        "indices": {"counts": {"uptrend": 0, "downtrend": 1, "neutral": 3}},
        "read": {"stories": [{"title": "Top Fed official signals central bank will keep rates on hold in October",
                              "tier": "breaking"}]},
        "morning_desk": {"catalyst": {"title": "Employment Situation", "short": "Jobs", "importance": 10,
                                      "days_away": 1, "time_label": "8:30 AM ET",
                                      "at": "2026-10-02T08:30:00-04:00"}},
    }
    data.update(over)
    return data


def test_the_day_leads_and_the_standing_questions_follow():
    qs = _questions(_day())
    assert qs == [
        "Why is EUR/USD down 0.8% today?",
        "Top Fed official signals central bank will keep rates on hold in October: what does that mean for markets?",
        "The jobs report is out tomorrow at 8:30 AM ET. What would a hot or a cool number do?",
        "The US 3M yield is down 1.2% today. What is moving rates?",
        qs[4],
    ]
    assert "DXY" not in " ".join(qs), "a second currency move is a second ask of one market"
    assert not any("WTI" in q for q in qs), "oil moved less than on an ordinary day"
    assert "What is the market expecting from the Fed?" not in qs, "the Fed story asks it"
    assert not qs[4].startswith("The 3m/10y spread"), "the rates move asks about rates already"


def test_a_different_day_asks_different_questions():
    a = _questions(_day())
    b = _questions(_day(
        macro={"regime": "risk-on", "groups": {
            "commodities": [_inst("WTI Crude", -4.9, 2.1)],
            "volatility": [_inst("VIX", 14.0, 6.0, last=21.3)],
            "equity": [_inst("Nasdaq 100", -2.4, 1.2)],
        }},
        read={"stories": [{"title": "Oil slides as OPEC+ agrees to lift output"}]},
        morning_desk={"catalyst": {"title": "Consumer Price Index", "short": "CPI", "importance": 10,
                                   "days_away": 0, "time_label": "8:30 AM ET",
                                   "at": "2026-10-01T08:30:00-04:00"}},
    ))
    assert not set(a) & set(b), "nothing carried over"
    assert b[:3] == [
        "WTI Crude is down 4.9% today. Is that supply or demand?",
        "Oil slides as OPEC+ agrees to lift output: what does that mean for markets?",
        "CPI came out today. What did it change?",
    ]
    assert "VIX is up 14.0% today. What is the market bracing for?" in b
    assert "Why is the Nasdaq 100 down 2.4% today?" in b


def test_each_market_is_asked_in_its_own_words():
    qs = _questions(_day(
        read={"stories": []}, morning_desk={},
        macro={"groups": {
            "credit": [_inst("HYG", -1.8, 0.5)],
            "crypto": [_inst("Bitcoin", 6.0, 2.6)],
            "futures": [_inst("S&P 500 futures", -1.5, 0.9)],
        }},
    ))
    # Ranked by each move against its instrument's ordinary day: 3.6, 2.3, 1.7.
    assert qs[:3] == [
        "HYG is down 1.8% today. Is credit agreeing with stocks?",
        "Why is Bitcoin up 6.0% today?",
        "S&P 500 futures are down 1.5%. What are they pricing in?",
    ]
    calm = _questions(_day(read={"stories": []}, morning_desk={},
                           macro={"groups": {"volatility": [_inst("VVIX", -9.0, 5.2)]}}))
    assert calm[0] == "VVIX is down 9.0% today. Is the market getting complacent?"


def test_a_release_before_and_after_it_prints_and_a_minor_one_not_at_all():
    def release(**c):
        base = {"title": "Consumer Price Index", "short": "CPI", "importance": 10,
                "days_away": 0, "time_label": "8:30 AM ET", "at": "2026-10-01T08:30:00-04:00"}
        base.update(c)
        return [q for q in _questions(_day(morning_desk={"catalyst": base}, read={"stories": []}))
                if "CPI" in q or "Fed decision" in q or "Productivity" in q]
    assert release() == ["CPI came out today. What did it change?"]
    assert release(at="2026-10-01T16:00:00-04:00", time_label="4:00 PM ET") == [
        "CPI is out today at 4:00 PM ET. What would surprise the market?"]
    assert release(short="FOMC", title="FOMC decision", days_away=1, time_label="2:00 PM ET",
                   at="2026-10-02T14:00:00-04:00") == ["The Fed decision is tomorrow at 2:00 PM ET. What is priced in?"]
    assert release(days_away=2) == [], "not today's news yet"
    assert release(short="Productivity", title="Productivity and Costs", importance=4) == [], "minor"


def test_a_quiet_day_still_asks_five_and_the_story_is_kept_readable():
    qs = _questions(_day(
        read={"stories": [{"title": "x" * 140}]}, morning_desk={},
        macro={"regime": "neutral", "groups": {"equity": [_inst("S&P 500", 0.1, 1.0)]},
               "ratios": [{"name": "Copper / Gold", "chg_20d": 2.0, "reads": "growth"}]},
    ))
    assert qs[0] == "Why is the S&P 500 up 0.1% today?", "the biggest move leads however small"
    assert len(qs) == 5 and not any("xxxx" in q for q in qs), "a headline too long to be a question is left"


def test_closed_markets_still_say_so():
    qs = _questions(_day(session={"now_et": "2026-10-03T12:00:00-04:00", "phase": "closed"}))
    assert "Single stocks are not trading. What are the futures telling me?" in qs[:2]


def test_on_every_day_of_the_rotation_a_standing_question_gives_way_to_its_market():
    """The standing questions rotate by date, so each is checked on every
    offset of the rotation rather than on whichever one today falls on."""
    def week(**over):
        out = []
        for k in range(9):
            day = _day(**over)
            day["session"] = {"now_et": "2026-10-%02dT14:00:00-04:00" % (1 + k), "phase": "regular"}
            day["macro"]["curve_3m10y"] = 0.42
            day["macro"]["groups"]["fx"].append(_inst("Dollar", 0.3, 0.45, chg_20d=1.2))
            out.append(_questions(day))
        return out
    asked = week()
    for qs in asked:
        assert not any(q.startswith("The 3m/10y spread") for q in qs), "rates are asked about"
        assert not any(q.startswith("The dollar is") for q in qs), "so are currencies"
        assert "What is the market expecting from the Fed?" not in qs, "the Fed story asks it"
    quiet = week(read={"stories": [{"title": "Oil slides as OPEC+ agrees to lift output"}]})
    assert any("What is the market expecting from the Fed?" in qs for qs in quiet), (
        "without a Fed story, the standing question has its turn")
