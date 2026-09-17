"""The morning desk.

Written to a fixed shape because the shape is the argument, and the thing most
worth protecting is the honesty of the one number a reader will quote: what the
fed funds strip is pricing.

That figure was wrong four different ways before it was right, and each way is a
test below. Fed funds futures settle on the *average* effective rate over a
delivery month, so turning a price into odds on a meeting needs the delivery
month, the meeting's date inside it, and enough days after the meeting for the
unwind to mean anything. Miss any of the three and the arithmetic still returns
a number, which is what makes this dangerous rather than merely broken.
"""
from __future__ import annotations

import re
from datetime import date

import pytest

from app.analytics import morning_desk as md

APP_JS = open("static/app.js").read()
CSS = open("static/styles.css").read()

QUOTE = {"last": 96.10}          # implies a 3.90% average for the delivery month
EFFECTIVE = 3.63


def _code(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.S)
    return re.sub(r"^\s*//.*$", " ", text, flags=re.M)


# --------------------------------------------------------------- rate path


def test_the_implied_average_is_a_hundred_minus_the_price():
    out = md.rate_path(QUOTE, EFFECTIVE)
    assert out["available"] is True
    assert out["implied_average"] == pytest.approx(3.90, abs=0.001)


@pytest.mark.parametrize("quote,effective,needle", [
    (None, EFFECTIVE, "futures quote"),
    ({"last": None}, EFFECTIVE, "futures quote"),
    (QUOTE, None, "effective rate"),
])
def test_a_missing_input_is_reported_not_guessed(quote, effective, needle):
    out = md.rate_path(quote, effective)
    assert out["available"] is False
    assert needle in out["reason"]


def test_without_a_delivery_month_it_refuses_to_call_it_odds():
    """The first version assumed the front contract meant the current calendar
    month. On 2026-09-17 ZQ=F was the October contract, so weighting against
    September's days turned 27bp priced into a 101bp move and a probability
    pinned at 100%."""
    out = md.rate_path(QUOTE, EFFECTIVE, None, date(2026, 9, 23))
    assert out["kind"] == "priced"
    assert out.get("probability") is None
    assert "delivery month" in out["limit"]


def test_a_meeting_outside_the_delivery_month_is_not_priced_by_this_contract():
    out = md.rate_path(QUOTE, EFFECTIVE, "2026-10-01", date(2026, 12, 9),
                       today=date(2026, 10, 2))
    assert out["kind"] == "priced"
    assert "No meeting falls inside October" in out["limit"]


def test_a_delivery_month_that_is_not_this_month_stays_priced():
    """The unwind treats today's effective rate as the rate in force up to the
    meeting, which only holds when the delivery month is the month we are in.
    With the contract on October and today in September, a September decision
    would already be lifting October's whole average and this would read its
    effect as post-meeting tightening."""
    out = md.rate_path(QUOTE, EFFECTIVE, "2026-10-01", date(2026, 10, 14),
                       today=date(2026, 9, 17))
    assert out["kind"] == "priced"
    assert out["basis_points"] == pytest.approx(27.0, abs=0.2)
    assert "not the current month" in out["limit"]


def test_a_late_month_meeting_is_refused_rather_than_amplified():
    """The method divides a whole month's priced move by the days after the
    decision, so a meeting near month-end multiplies the noise with the signal:
    the 28th of a 31-day month turned 27bp priced into a 209bp implied move."""
    out = md.rate_path(QUOTE, EFFECTIVE, "2026-10-01", date(2026, 10, 28),
                       today=date(2026, 10, 1))
    assert out["kind"] == "priced"
    assert out.get("probability") is None
    assert "amplifies the error" in out["limit"]


def test_a_mid_month_meeting_in_the_current_month_gives_odds():
    out = md.rate_path(QUOTE, EFFECTIVE, "2026-10-01", date(2026, 10, 14),
                       today=date(2026, 10, 2))
    assert out["kind"] == "probability"
    assert out["direction"] == "hike"
    assert 0 <= out["probability"] <= 100
    assert out["meeting"] == "2026-10-14"
    # The method is published with the number, because a percentage backed out
    # of a futures price is not a survey and must not read like one.
    assert "average daily" in out["method"] and "October" in out["method"]


def test_the_probability_is_bounded():
    """A price can imply more than one step. That is a real reading, but it is
    not a probability above 100."""
    out = md.rate_path({"last": 90.0}, EFFECTIVE, "2026-10-01",
                       date(2026, 10, 14), today=date(2026, 10, 2))
    assert out["probability"] == 100.0


def test_the_step_is_named_rather_than_buried():
    """It is the denominator of the percentage, so a reader has to be able to
    see what the percentage is a percentage of."""
    out = md.rate_path(QUOTE, EFFECTIVE, "2026-10-01", date(2026, 10, 14),
                       today=date(2026, 10, 2))
    assert out["step_bp"] == md.STEP_BP == 25.0


# ------------------------------------------------------------ the branches


def _catalyst(title, category, days=1):
    return {"title": title, "category": category, "days_away": days,
            "impact": "high", "importance": 5, "when_label": "Tomorrow"}


def test_an_expiry_does_not_come_in_hot_or_soft():
    """The bug this names: the branch block applied "comes in hot" to whatever
    the next catalyst was, and the next catalyst was quadruple witching. An
    options expiry publishes no number, so the desk was inventing a reading for
    an event that does not have one."""
    rows = md._scenarios({"available": False}, _catalyst("Quadruple witching", "positioning"))
    labels = " ".join(r["label"] for r in rows).lower()
    assert "hot" not in labels and "soft" not in labels
    assert "unwind" in labels or "moves the tape" in labels
    body = " ".join(r["text"] for r in rows)
    assert "do not print a number" in body


def test_a_data_release_does_get_a_hot_and_soft_branch():
    rows = md._scenarios({"available": False}, _catalyst("Consumer Price Index", "inflation"))
    labels = " ".join(r["label"] for r in rows).lower()
    assert "hot" in labels and "soft" in labels and "in line" in labels


def test_the_branches_are_conditional_and_carry_no_instruction():
    """Describing a setup, not calling it. Nothing here may tell a reader what
    to buy, size or when to enter."""
    for catalyst in (_catalyst("CPI", "inflation"),
                     _catalyst("Quadruple witching", "positioning")):
        for row in md._scenarios({"available": False}, catalyst):
            text = row["text"].lower()
            for banned in ("you should", "we recommend", "buy ", "sell ",
                           "take profit", "stop loss", "position size"):
                assert banned not in text, row["label"]


def test_a_priced_rate_leads_the_branches_over_a_calendar_item():
    rate = md.rate_path(QUOTE, EFFECTIVE, "2026-10-01", date(2026, 10, 14),
                        today=date(2026, 10, 2))
    rows = md._scenarios(rate, _catalyst("CPI", "inflation"))
    assert any("No change" == r["label"] for r in rows), \
        "the decision branches win when a decision is priced"


# ------------------------------------------------------------- the synthesis


def test_a_flat_dollar_is_not_a_direction():
    """A falling yield beside a dollar that has not moved is not "the
    combination that usually means a rate story", and reading flat as positive
    said that it was."""
    tape = {"ten_year": {"chg_1d": -0.9}, "dollar": {"chg_1d": 0.02}}
    out = md._overall(tape, {"available": False}, [])
    assert "saying nothing together" in out
    assert "usually means a rate story" not in out


def test_yields_and_the_dollar_moving_together_is_named():
    tape = {"ten_year": {"chg_1d": 0.9}, "dollar": {"chg_1d": 0.5}}
    assert "rate story" in md._overall(tape, {"available": False}, [])


def test_a_quiet_day_says_levels_rather_than_narrative():
    out = md._overall({}, {"available": False}, [])
    assert "flow" in out and "levels" in out


def test_a_day_with_releases_warns_off_the_first_reaction():
    out = md._overall({}, {"available": False}, [{"title": "CPI"}])
    assert "least reliable" in out


# ------------------------------------------------------------------- build


def test_the_desk_always_says_it_carries_no_consensus():
    """The single most likely thing for a reader to mistake for an omission
    rather than a deliberate refusal to invent a number."""
    out = md.build(today=date(2026, 9, 17))
    assert out["available"] is True
    assert any("consensus" in l for l in out["limits"])


def test_a_quiet_calendar_renders_no_calendar_section_and_says_so():
    out = md.build(events={"events": []}, today=date(2026, 9, 17))
    assert out["calendar"] == []
    assert any("Nothing is scheduled" in l for l in out["limits"])


def test_the_sections_are_the_samples_five_moves():
    out = md.build(today=date(2026, 9, 17))
    for key in ("lead", "scenarios", "note", "calendar", "overall", "limits"):
        assert key in out


def test_todays_releases_are_the_ones_dated_today():
    events = {"events": [
        {"title": "CPI", "days_away": 0, "importance": 5},
        {"title": "Jobless claims", "days_away": 0, "importance": 3},
        {"title": "GDP", "days_away": 2, "importance": 5},
    ]}
    rows = md._today_releases(events, date(2026, 9, 17))
    assert [r["title"] for r in rows] == ["CPI", "Jobless claims"], \
        "today only, biggest first"


def test_the_desk_quotes_the_strip_it_sits_under():
    """Passed the macro payload rather than refetching, so the desk and the
    strip above it cannot disagree about the same figure."""
    macro = {"groups": {"futures": [
        {"symbol": "ES=F", "label": "S&P 500 futures", "chg_1d": 0.49}]}}
    out = md.build(macro=macro, today=date(2026, 9, 17))
    assert any("+0.49%" in p for p in out["lead"])


# --------------------------------------------------- the contract month code


def test_the_contract_month_comes_from_the_month_code(monkeypatch):
    """Not from the expiry. Yahoo reported 2026-11-02 for a contract whose code
    says October, because a 30-day fed funds contract settles on a business day
    after its delivery month and by how much depends on the weekend. Backing a
    month out of that date produced November for the October contract."""
    from app.providers import yf as adapter

    class _T:
        def __init__(self, sym): pass
        @property
        def info(self):
            return {"underlyingSymbol": "ZQV26.CBT", "expireDate": 1793577600}

    for key in [k for k in adapter._CACHE if k.startswith("cmonth:")]:
        del adapter._CACHE[key]
    monkeypatch.setattr(adapter.yf, "Ticker", _T)
    assert adapter.YFinanceProvider().contract_month("ZQ=F") == "2026-10-01"
    for key in [k for k in adapter._CACHE if k.startswith("cmonth:")]:
        del adapter._CACHE[key]


def test_the_month_code_table_skips_i_and_l():
    """I and L are absent from the standard CME set, which is why this is a
    table and not an alphabet offset."""
    from app.providers.yf import FUTURES_MONTHS
    assert "I" not in FUTURES_MONTHS and "L" not in FUTURES_MONTHS
    assert FUTURES_MONTHS["V"] == 10 and FUTURES_MONTHS["F"] == 1
    assert sorted(FUTURES_MONTHS.values()) == list(range(1, 13))


# ----------------------------------------------------------- client wiring


def test_the_desk_renders_on_the_home_page():
    code = _code(APP_JS)
    assert "function morningDesk(data)" in code
    assert "${morningDesk(data)}" in code, "and is actually called from renderHome"


def test_the_desk_is_absent_rather_than_empty_when_unavailable():
    fn = APP_JS[APP_JS.index("function morningDesk(data)"):]
    fn = fn[:fn.index("\nfunction whatMattersNow")]
    assert "d.available !== true" in fn and "return ''" in fn


def test_the_ask_pulse_topic_exists_in_both_maps():
    """CLAUDE.md: a topic that is asked for and never defined makes
    openPulseWith return early, so the button takes the click and does nothing.
    It does not error; it reads as a slow app."""
    assert "askPulse('morning_desk')" in APP_JS
    assert re.search(r"^\s+morning_desk: '(?!Explain this desk)", APP_JS, re.M), \
        "the prompt entry"
    assert "morning_desk: 'Explain this desk'," in APP_JS, "the label entry"


def test_the_desk_does_not_reuse_the_briefs_morning_topic():
    """The existing `morning` prompt asks about the overnight window and the
    geopolitical headlines the brief lists, neither of which this panel carries.
    Pointing a button at a question about something else on screen is worse than
    no button."""
    fn = APP_JS[APP_JS.index("function morningDesk(data)"):]
    fn = fn[:fn.index("\nfunction whatMattersNow")]
    assert "askPulse('morning')" not in fn


def test_the_prose_has_a_measure():
    """A paragraph across the full 908px block is about 160 characters a line."""
    assert "--md-measure" in CSS
    assert ".md-p" in CSS and "max-width: var(--md-measure)" in CSS
