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
    # "Hot" and "soft" were the desk's words; "higher" and "lower than last
    # time" are the plain ones that replaced them, and neither applies.
    for word in ("hot", "soft", "higher", "lower"):
        assert word not in labels, word
    assert "passes quietly" in labels and "moves prices" in labels
    body = " ".join(r["text"] for r in rows)
    assert "do not print a number" in body


def test_a_data_release_does_get_a_hot_and_soft_branch():
    rows = md._scenarios({"available": False}, _catalyst("Consumer Price Index", "inflation"))
    labels = " ".join(r["label"] for r in rows).lower()
    assert "higher than last time" in labels and "lower than last time" in labels
    assert "about the same" in labels


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
    assert "do not tell a clear story" in out
    assert "where they think interest rates are headed" not in out


def test_yields_and_the_dollar_moving_together_is_named():
    tape = {"ten_year": {"chg_1d": 0.9}, "dollar": {"chg_1d": 0.5}}
    assert "where they think interest rates are headed" in md._overall(
        tape, {"available": False}, [])


def test_a_quiet_day_says_levels_rather_than_narrative():
    out = md._overall({}, {"available": False}, [])
    # Levels over narrative, in words: it was "the moves here are flow. That
    # makes levels worth more than narrative today."
    assert "no big news" in out
    assert "where prices actually end up matters more than any explanation" in out


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


# ------------------------------------------------------------- written voice


def test_the_prose_writer_declines_without_credentials():
    """None is a legitimate answer, not an error: `build` has already written a
    correct note and this only replaces the prose."""
    from app import ai
    assert ai.write_morning_desk({"date": "2026-09-17"}) is None


def test_the_prompt_forbids_the_figures_this_terminal_does_not_have():
    """The desk's whole claim is that a release is compared against its own
    prior print, because surveyed expectations are licensed and absent here. A
    model given a rate figure will reach for "expected" unless told not to."""
    from app.ai import DESK_PROMPT
    low = DESK_PROMPT.lower()
    assert "only the figures in the data block" in low
    assert "consensus" in low and "do not invent" in low
    assert "no em dashes" in low
    for banned in ("price target", "when to enter"):
        assert banned in low
    # And it must not promote basis points priced into a month into odds.
    assert "do not promote it to a probability" in low


def test_the_prompt_asks_for_the_samples_five_moves():
    from app.ai import DESK_PROMPT
    low = DESK_PROMPT.lower()
    for section in ("setting the tone", "branches", "note:", "releases", "synthesis"):
        assert section in low
    assert '"lead"' in DESK_PROMPT and '"scenarios"' in DESK_PROMPT


def test_the_prose_is_an_overlay_and_never_touches_a_figure():
    """So the desk and the strip above it cannot disagree. The model is given
    the assembled payload and may rewrite four prose keys; everything else,
    including `rate_path` and `tape`, stays exactly as built."""
    main_src = open("app/main.py").read()
    block = main_src[main_src.index("def _morning_desk("):]
    block = block[:block.index("\ndef _home_read")]
    code = _code(block)
    assert 'desk["voice"] = "mechanical"' in code, "the default is the safe one"
    assert 'for key in ("scenarios", "note", "overall"):' in code
    assert 'desk["lead"] = prose["lead"]' in code
    for untouchable in ("rate_path", "tape", "limits", "calendar"):
        assert 'desk["{}"] = prose'.format(untouchable) not in code


def test_the_prose_is_written_once_a_day_and_the_failure_is_cached_too():
    """The home page is the most requested endpoint here, so a call per view
    would be a call per reader. Holding the failure matters as much: an
    unavailable model at 9am must not be retried on every request all day.
    Both are kept on disk now, so a deploy does not pay again either; the
    behaviour is in tests/test_ai_credits.py."""
    main_src = open("app/main.py").read()
    block = main_src[main_src.index("def _desk_prose("):]
    block = block[:block.index("\n# How far the tape may move")]
    code = _code(block)
    assert "if _DESK_PROSE.get(day) is not None:" in code
    assert 'ai_store.kept("desk", day)' in code
    assert 'ai_store.claim("desk", day, DESK_MAX_ATTEMPTS, DESK_RETRY_SECONDS)' in code
    assert "_DESK_PROSE[day] = prose" in code
    assert "_DESK_PROSE.clear()" in code, "one day at a time, or it grows forever"


def test_the_reader_is_told_which_voice_wrote_it():
    fn = APP_JS[APP_JS.index("function morningDesk(data)"):]
    fn = fn[:fn.index("\nfunction whatMattersNow")]
    assert "d.voice === 'written'" in fn
    assert "Written for today by" in fn
    assert "not configured on this deployment" in fn
    assert ".md-voice" in CSS


# --------------------------------------------------------- a voice for anyone


# The desk's own language, which a reader with no market background cannot
# follow. Asked for as "simplify the voice of the optic desk ... make it so
# that anyone, regardless of financial and economic knowledge can understand
# whats going on for the day".
DESK_JARGON = (r"\btape\b", r"\bflow\b", r"\bpositioning\b", r"basis point", r"\bpriced\b",
               r"front end", r"open interest", r"\bstrip\b", r"\bthe curve\b",
               r"\bimplied\b", r"effective rate", r"\breprice", r"\bhot\b", r"\bsoft\b")


def _every_desk():
    """The template desk on each branch it has: a decision with odds, a
    month's average priced, an expiry, a data release, and a quiet day."""
    probability = md.rate_path(QUOTE, EFFECTIVE, "2026-10-01", date(2026, 10, 14),
                               today=date(2026, 10, 2))
    priced = {"available": True, "kind": "priced", "basis_points": 12.0,
              "implied_average": 4.0, "effective": 3.88,
              "contract_month_label": "November", "limit": "A limit."}
    macro = {"groups": {"futures": [
        {"symbol": "ES=F", "label": "S&P 500 futures", "chg_1d": 0.48},
        {"symbol": "NQ=F", "label": "Nasdaq 100 futures", "chg_1d": 0.58},
        {"symbol": "RTY=F", "label": "Russell 2000 futures", "chg_1d": -0.31}]},
        "vix": {"last": 15.59}}
    cpi = {"events": [{"title": "Consumer Price Index", "days_away": 0, "importance": 5,
                       "impact": "high", "category": "inflation"}]}
    expiry = {"events": [{"title": "Quadruple witching", "days_away": 1, "importance": 5,
                          "impact": "high", "category": "positioning",
                          "when_label": "Tomorrow"}]}
    for rate, events in ((probability, None), (priced, None), ({"available": False}, expiry),
                         ({"available": False}, cpi), ({"available": False}, {"events": []})):
        yield md.build(macro=macro, events=events, rate=rate, today=date(2026, 10, 5))


def _prose(desk):
    parts = list(desk["lead"]) + [desk["note"], desk["overall"]] + list(desk["limits"])
    for row in desk["scenarios"]:
        parts += [row["label"], row["text"]]
    return " ".join(p for p in parts if p)


def test_the_assembled_desk_speaks_without_the_desks_jargon():
    for desk in _every_desk():
        text = _prose(desk).lower()
        for pattern in DESK_JARGON:
            assert not re.search(pattern, text), (pattern, text[:200])


def test_the_assembled_lead_carries_a_few_numbers_not_a_table():
    """The written desk of 2026-10-05 had sixteen figures in five paragraphs.
    The assembled lead quotes the S&P's move and, when a decision is priced,
    its odds: words for the rest."""
    for desk in _every_desk():
        lead = " ".join(desk["lead"])
        # Names are not figures: "S&P 500", "Nasdaq 100", and a meeting's date.
        named = re.sub(r"\b(S&P|Nasdaq|Russell|Dow)( Jones)? \d+", "", lead)
        named = re.sub(r"\b\d{1,2} [A-Z][a-z]+\b", "", named)
        figures = re.findall(r"\d+(?:\.\d+)?", named)
        # Two: the S&P's move, and the odds when a decision is priced. Three
        # let every index's percentage back in with one of them still missing.
        assert len(figures) <= 2, (figures, lead)


def test_the_prompt_writes_for_someone_who_has_never_bought_a_stock():
    from app.ai import DESK_PROMPT
    low = DESK_PROMPT.lower()
    assert "never bought a stock" in low and "knows nothing about finance or economics" in low
    # A number budget, and rounding.
    assert "at most four in the whole lead" in low
    assert "never more than one" in low and "round them" in low
    # The words it may not use, and the rule for the ones it must.
    for word in ("tape", "flow", "positioning", "priced in", "basis points", "open interest"):
        assert word in low, word
    assert "say what it is in plain words" in low and "the first time" in low
    # And the probability rule survives the simpler voice.
    assert "do not call it" in low and "odds or a chance" in low


def test_the_page_names_the_branches_and_the_bottom_line():
    from pathlib import Path
    app_js = (Path(__file__).resolve().parent.parent / "static/app.js").read_text()
    fn = app_js[app_js.index("function morningDesk(data) {"):]
    fn = fn[:fn.index("\nfunction ")]
    assert '<h3 class="md-h3">What could happen next</h3>' in fn
    assert "<strong>Bottom line:</strong>" in fn
    assert '<h3 class="md-h3">Today\'s reports</h3>' in fn


def test_the_note_explains_only_what_the_desk_has_said():
    """Two mismatches found reading the plain version aloud: the note explained
    "that expected change" when the lead had left a small one out, and "each
    report below" on a day with no reports."""
    small = {"available": True, "kind": "priced", "basis_points": 6.5,
             "implied_average": 3.945, "effective": 3.88, "contract_month_label": "November"}
    cot = _catalyst("CFTC Commitments of Traders", "positioning", days=4)
    out = md.build(rate=small, events={"events": [cot]}, today=date(2026, 10, 5))
    assert "expected change" not in out["note"]
    assert "report below" not in out["note"]
    assert not any("interest rate" in p for p in out["lead"]), "the lead left it out"
    big = dict(small, basis_points=12.0)
    assert "expected change" in md.build(rate=big, today=date(2026, 10, 5))["note"]
    cpi = {"title": "CPI", "days_away": 0, "importance": 5, "impact": "high"}
    assert "report below" in md.build(events={"events": [cpi]}, today=date(2026, 10, 5))["note"]


def test_a_positions_report_is_not_given_an_expirys_branches():
    """The weekly report of what big traders hold expires nothing, and was told
    "the bets expire" and "the day after" anyway."""
    assert md._scenarios({"available": False},
                         _catalyst("CFTC Commitments of Traders", "positioning")) == []
    assert md._scenarios({"available": False},
                         _catalyst("Quadruple witching", "positioning"))


def test_the_lead_reads_as_sentences():
    macro = {"groups": {"futures": [
        {"symbol": "ES=F", "label": "S&P 500 futures", "chg_1d": 0.48},
        {"symbol": "NQ=F", "label": "Nasdaq 100 futures", "chg_1d": 0.58}]}}
    cot = dict(_catalyst("CFTC Commitments of Traders", "positioning", days=4),
               when_label="Fri Oct 9")
    lead = " ".join(md.build(macro=macro, events={"events": [cot]},
                             today=date(2026, 10, 5))["lead"])
    assert "Nasdaq 100 futures are up slightly" in lead, lead
    assert "on Fri Oct 9" in lead and "fri oct 9" not in lead
