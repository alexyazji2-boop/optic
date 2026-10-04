"""Fair value, the analysts' view and a dividend score on the Investing tab.

Asked for with a list of what another app puts behind a paid tier: "stock picks
chosen by experts", a rating, "1,000s of company research reports", "model
portfolio strategies + stock ideas", "fair value analysis + dividend scores";
"add these features to the optic terminal wherever applicable". Model
portfolios and stock ideas were here already (Optic Portfolio and Scan), and a
research report on any symbol is the Dossier. What was missing is built here
from data the terminal already reads, with the method on the page.

Checked on 3 October 2026 against the local server: Apple $243 to $304 around
$273 with the price 22% above the middle; Coca-Cola $79 to $89 around $84 with
the price inside it and a dividend score of 68 (23 years of increases); Tesla
and Coinbase, whose multiples have swung from the teens to the hundreds, given
their numbers and no verdict; SPY no score, since a fund has no earnings.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.analytics import fair_value as fv

ROOT = Path(__file__).resolve().parent.parent
APP = (ROOT / "static/app.js").read_text()
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc"
TODAY = datetime(2026, 10, 3, tzinfo=timezone.utc)


def _pe(eps=8.71, bands=(27.9, 31.3, 34.9), weeks=260, short=False, available=True):
    return {"available": available, "reason": "No filing history.", "pe_series": [{"ttm_eps": eps}],
            "pe_bands": {"25": bands[0], "50": bands[1], "75": bands[2]}, "band_weeks": weeks,
            "short_history": short, "pe_current": 38.3, "source": "SEC"}


# ----------------------------------------------------------------- fair value

def test_the_range_is_trailing_earnings_at_its_own_multiples():
    out = fv.fair_value(_pe(), 333.69)
    assert (out["low"], out["mid"], out["high"]) == (243.01, 272.62, 303.98)
    assert out["position"] == "above its range" and out["gap_to_mid_pct"] == 22.4
    assert out["wide"] is False and out["range_width"] == 0.22
    assert out["basis"].startswith("Trailing twelve-month EPS of $8.71 at its own 5-year P/E of 27.9x")
    assert fv.fair_value(_pe(), 250.0)["position"] == "inside its range"
    assert fv.fair_value(_pe(), 200.0)["position"] == "below its range"


def test_a_range_too_wide_to_read_a_price_against_gets_no_verdict():
    out = fv.fair_value(_pe(eps=1.08, bands=(72.5, 197.4, 391.4)), 370.59)
    assert out["wide"] is True and out["position"] == "too wide to call"
    assert out["range_width"] > fv.WIDE_RANGE and "no verdict" in out["wide_note"]
    assert (out["low"], out["high"]) == (78.3, 422.71), "the numbers are still shown"


@pytest.mark.parametrize("pe,why", [
    (_pe(available=False), "No filing history."),
    (_pe(eps=-1.2), "not positive"),
    (_pe(eps=None), "not positive"),
    (_pe(weeks=100), "Less than three years"),
    (_pe(short=True), "Less than three years"),
    (_pe(bands=(None, 31.3, 34.9)), "missing"),
])
def test_without_what_it_needs_it_says_so_and_gives_no_number(pe, why):
    out = fv.fair_value(pe, 100.0)
    assert out["available"] is False and why in out["reason"]
    assert "mid" not in out


def test_without_a_price_there_is_no_range_to_place():
    assert fv.fair_value(_pe(), None)["available"] is False


# ------------------------------------------------------------------- analysts

VIEW = {"targets": {"mean": 94.65, "low": 75.0, "high": 104.0},
        "ratings": [{"period": "0m", "strong_buy": 6, "buy": 13, "hold": 4, "sell": 1, "strong_sell": 0},
                    {"period": "-1m", "strong_buy": 6, "buy": 13, "hold": 4, "sell": 1, "strong_sell": 0},
                    {"period": "-2m", "strong_buy": 5, "buy": 13, "hold": 4, "sell": 1, "strong_sell": 0},
                    {"period": "-3m", "strong_buy": 5, "buy": 13, "hold": 4, "sell": 1, "strong_sell": 0},
                    {"period": "-4m", "strong_buy": 5, "buy": 13, "hold": 4, "sell": 1, "strong_sell": 0}]}


def test_the_analysts_view_counts_the_current_month_and_is_not_an_optic_pick():
    out = fv.analysts_view(VIEW, 85.65)
    assert (out["buys"], out["holds"], out["sells"], out["analyst_count"]) == (19, 4, 1, 24)
    assert out["upside_pct"] == 10.5 and out["buy_share_pct"] == 79.0
    assert len(out["ratings"]) == 4 and "Not an Optic pick" in out["note"]


def test_no_coverage_is_not_a_panel():
    out = fv.analysts_view({"targets": {}, "ratings": []}, 100.0)
    assert out["available"] is False and "No analyst coverage" in out["reason"]


# ------------------------------------------------------------------- dividend

def _actions(streak=23, cut=None, last="2026-09-12", annual=(1.56, 1.6, 1.64, 1.68, 1.76, 1.84, 1.94, 2.04),
             amount=0.51, pays=True):
    return {"pays_dividend": pays,
            "dividends": [{"date": d, "amount": amount} for d in
                          ("2025-12-01", "2026-03-14", "2026-06-13", last)] if pays else [],
            "annual": [{"year": 2018 + i, "total": v} for i, v in enumerate(annual)],
            "growth_streak_years": streak, "last_cut_year": cut, "source": "Yahoo"}


def test_the_score_is_four_parts_of_twenty_five():
    out = fv.dividend_score(_actions(), 85.65, 26.9, 0.0248, today=TODAY)
    parts = {p["id"]: p for p in out["parts"]}
    assert parts["streak"]["points"] == 25.0 and parts["streak"]["value"] == "23 years in a row"
    assert parts["cover"]["value"] == "64% of earnings paid out" and parts["cover"]["points"] == 12.0
    assert parts["growth"]["value"] == "+4.5% a year" and parts["growth"]["points"] == 16.0
    assert parts["yield"]["points"] == 15.5
    assert out["score"] == 68 and out["band"] == "solid" and out["scored_of"] == 4


def test_a_recent_cut_holds_the_streak_down_and_a_loss_scores_no_cover():
    out = fv.dividend_score(_actions(streak=7, cut=2024), 85.65, 26.9, 0.0248, today=TODAY)
    streak = next(p for p in out["parts"] if p["id"] == "streak")
    assert streak["points"] == 8.0 and "Cut in 2024" in streak["why"]
    old = fv.dividend_score(_actions(streak=7, cut=2002), 85.65, 26.9, 0.0248, today=TODAY)
    assert next(p for p in old["parts"] if p["id"] == "streak")["points"] == 17.5
    loss = fv.dividend_score(_actions(), 85.65, None, 0.0248, today=TODAY)
    assert next(p for p in loss["parts"] if p["id"] == "cover")["points"] == 0.0


def test_a_yield_that_high_is_no_credit_and_missing_parts_are_left_out_and_scaled():
    high = fv.dividend_score(_actions(), 85.65, 26.9, 0.11, today=TODAY)
    part = next(p for p in high["parts"] if p["id"] == "yield")
    assert part["points"] == 0.0 and "price that has fallen" in part["why"]
    short = fv.dividend_score(_actions(annual=(1.0, 1.1, 1.2)), 85.65, 26.9, 0.0248, today=TODAY)
    growth = next(p for p in short["parts"] if p["id"] == "growth")
    assert growth["points"] is None and short["scored_of"] == 3
    assert short["score"] == round((12 + 25 + 15.5) / 75 * 100)


@pytest.mark.parametrize("kwargs,why", [
    ({"actions": _actions(pays=False)}, "does not pay"),
    ({"actions": _actions(last="2024-01-02")}, "No dividend paid since"),
    ({"actions": _actions(), "quote_type": "ETF"}, "A fund passes on"),
])
def test_no_score_for_a_name_that_pays_nothing_stopped_or_is_a_fund(kwargs, why):
    kwargs.setdefault("quote_type", "EQUITY")
    out = fv.dividend_score(kwargs.pop("actions"), 85.65, 26.9, 0.0248, today=TODAY, **kwargs)
    assert out["available"] is False and why in out["reason"]


def test_each_block_fails_on_its_own():
    class Provider:
        def quote(self, sym):
            return {"price": 100.0, "quote_type": "EQUITY", "trailing_pe": 20.0, "dividend_yield": 0.02}

        def analyst_view(self, sym):
            raise RuntimeError("feed down")

    out = fv.build(Provider(), "xyz")
    assert out["ticker"] == "XYZ"
    assert out["morningstar"]["available"] is False, "asked of every symbol, and a stock has none"
    assert out["stars"]["available"] is False, "rated from the fair value, which a bare quote has none of"
    assert out["analysts"] == {"available": False, "reason": "Could not be worked out right now."}
    assert set(out) >= {"fair_value", "dividend", "generated_at"}


# ------------------------------------------------------------------ the page

def _run(script):
    exe = JSC if os.path.exists(JSC) else shutil.which("jsc")
    if not exe:
        pytest.skip("no JavaScriptCore on this machine")

    def piece(head):
        at = APP.index(head)
        return APP[at:APP.index("\n}\n", at) + 3]

    pieces = "\n".join(piece(h) for h in (
        "function fvPct(", "function renderFairValueBlock(", "function renderAnalystsBlock(",
        "function renderDividendBlock(", "function renderMorningstarBlock(", "function starsText(",
        "function renderStarBlock(", "function renderFairValue("))
    prelude = """
      function esc(v) { return String(v).replace(/&/g, '&amp;').replace(/</g, '&lt;'); }
      function cap(v) { return v.charAt(0).toUpperCase() + v.slice(1); }
      function hg(v) { return v; }
      function askPulse(t) { return '[ask ' + t + ']'; }
      function usd(v, d) { return v === null || v === undefined ? '-' : '$' + Number(v).toFixed(d === undefined ? 2 : d); }
      function fmt(v, d) { return Number(v).toFixed(d); }
      function fmtPct(v, d) { return (v >= 0 ? '+' : '') + Number(v).toFixed(d) + '%'; }
      function signClass(v) { return v > 0 ? 'up' : v < 0 ? 'down' : 'flat'; }
      function tile(label, value, note, cls) { return '<tile ' + (cls || '') + '>' + label + '|' + value + '|' + (note || '') + '</tile>'; }
    """ + pieces
    out = subprocess.run([exe, "-e", prelude + script], capture_output=True, text=True, timeout=60, cwd=str(ROOT))
    assert "RESULT:" in out.stdout, (out.stdout + out.stderr)[-2000:]
    return json.loads(out.stdout.split("RESULT:", 1)[1].split("\n")[0])


FAIR = fv.fair_value(_pe(), 333.69)
ANALYSTS = fv.analysts_view(VIEW, 85.65)
DIVIDEND = fv.dividend_score(_actions(), 85.65, 26.9, 0.0248, today=TODAY)


def test_the_panels_show_the_range_the_verdict_and_what_it_cannot_do():
    out = _run("print('RESULT:' + JSON.stringify(renderFairValue(%s)));" % json.dumps(
        {"fair_value": FAIR, "analysts": ANALYSTS, "dividend": DIVIDEND}))
    for text in ("<tile >Fair value, middle|$272.62|31.3× its own median</tile>",
                 "Range|$243 to $304|27.9× to 34.9×", "Price now|$333.69|38.3× today",
                 "<tile down>Above its range|+22.4%|price against the middle</tile>",
                 'class="fv-bar"', "A range to read the price against, not a target.",
                 "It assumes the next years look like the last ones",
                 "What analysts say", "<tile up>Mean target|$94.65|+10.5% from here</tile>",
                 "Buy / hold / sell|19 · 4 · 1|24 analysts", "Not an Optic pick",
                 "Dividend score", 'class="fv-score-n up">68<', "Solid",
                 "Years of increases", "23 years in a row", "25 of 25", "cannot see debt"):
        assert text in out, text


def test_a_wide_range_has_numbers_and_a_note_but_no_verdict_and_nothing_empty_is_shown():
    wide = fv.fair_value(_pe(eps=1.08, bands=(72.5, 197.4, 391.4)), 370.59)
    out = _run("print('RESULT:' + JSON.stringify([renderFairValue(%s), renderFairValue(%s)]));" % (
        json.dumps({"fair_value": wide, "analysts": {"available": False}, "dividend": {"available": False}}),
        json.dumps({"fair_value": {"available": False, "reason": "No filing history."},
                    "analysts": {"available": False}, "dividend": {"available": False}})))
    shown, bare = out
    assert "<tile >Too wide to call|" in shown and "no verdict" in shown
    assert "What analysts say" not in shown and "Dividend score" not in shown
    assert "No filing history." in bare and "fv-bar" not in bare


def test_it_loads_under_the_multiple_history_and_drops_another_symbols_answer():
    assert '<div id="fv-host" class="span-all">${STATE.fairValueFor === STATE.ticker' in APP
    load = APP[APP.index("async function loadFairValue(force) {"):]
    load = load[:load.index("\n}\n")]
    assert "/api/fair-value/" in load and "if (STATE.ticker !== sym) return;" in load
    assert "    loadPeHistory();\n    loadFairValue();" in APP
    for topic in ("fairvalue", "analystsview", "divscore"):
        assert "  %s: '" % topic in APP


# ---------------------------------------------------------------- Morningstar
#
# "add the morningstar rating too". Morningstar's rating is licensed, and the
# only copy the terminal can read is in Yahoo's quote, for mutual funds only:
# on 3 October 2026 VFIAX and FXAIX had 4 stars and Average risk, and AAPL, KO,
# SPY and QQQ had no field. Shown as Morningstar's, never worked out here.

def test_a_funds_morningstar_rating_is_shown_as_morningstars():
    out = fv.morningstar({"morningstar_rating": 4.0, "morningstar_risk": 3.0})
    assert (out["stars"], out["risk"], out["risk_word"]) == (4, 3, "Average")
    assert out["source"] == "Morningstar, via Yahoo Finance" and "not a forecast" in out["note"]
    assert fv.morningstar({"morningstar_rating": 5, "morningstar_risk": None})["risk_word"] is None


@pytest.mark.parametrize("quote", [{}, {"morningstar_rating": None}, {"morningstar_rating": 0},
                                   {"morningstar_rating": 7}, {"morningstar_rating": "n/a"}])
def test_no_rating_in_the_feed_is_no_rating_and_none_is_made_up(quote):
    out = fv.morningstar(quote)
    assert out["available"] is False and "only in the feed for mutual funds" in out["reason"]


def test_the_quote_carries_it_and_the_page_shows_stars_only_when_there_are_some():
    src = (ROOT / "app/providers/yf.py").read_text()
    assert '"morningstar_rating": _f(info.get("morningStarOverallRating")),' in src
    assert '"morningstar_risk": _f(info.get("morningStarRiskRating")),' in src
    rated = fv.morningstar({"morningstar_rating": 4, "morningstar_risk": 3})
    out = _run_ms("print('RESULT:' + JSON.stringify([renderMorningstarBlock(%s), renderMorningstarBlock(%s)]));"
                  % (json.dumps(rated), json.dumps(fv.morningstar({}))))
    shown, none = out
    assert "Morningstar rating" in shown and "★★★★☆" in shown
    assert "4 of 5 stars" in shown and "Risk rating|Average|3 of 5" in shown
    assert "not Optic's" in shown and "Source: Morningstar, via Yahoo Finance." in shown
    assert none == ""
    assert "renderMorningstarBlock(d.morningstar), renderFairValueBlock(d.fair_value)" in APP


def _run_ms(script):
    exe = JSC if os.path.exists(JSC) else shutil.which("jsc")
    if not exe:
        pytest.skip("no JavaScriptCore on this machine")
    fn = ""
    for head in ("function starsText(", "function renderMorningstarBlock("):
        at = APP.index(head)
        fn += APP[at:APP.index("\n}\n", at) + 3]
    prelude = """
      function esc(v) { return String(v); }
      function hg(v) { return v; }
      function tile(label, value, note) { return label + '|' + value + '|' + (note || ''); }
    """
    out = subprocess.run([exe, "-e", prelude + fn + script], capture_output=True, text=True,
                         timeout=60, cwd=str(ROOT))
    assert "RESULT:" in out.stdout, (out.stdout + out.stderr)[-1500:]
    return json.loads(out.stdout.split("RESULT:", 1)[1].split("\n")[0])


# ------------------------------------------------------------- Optic stars
#
# "build the optic star rating for stocks", after Morningstar's own turned out
# to be in the feed for funds only. Five steps of the price against the fair
# value range. Measured on 3 October 2026: Apple 1 star (above its range),
# Coca-Cola 3, Microsoft 4, Alphabet 5 (a P/E of 17 against its own 27), and
# none for Amazon, whose usual multiple ran 35x to 91x, nor for Intel, whose
# earnings have all but gone and whose "fair value" came out at $2.69.

@pytest.mark.parametrize("price,stars", [
    (230.0, 5), (243.0, 5), (243.01, 4), (260.0, 4), (266.0, 3), (272.62, 3), (280.0, 3), (290.0, 2), (303.98, 2), (310.0, 1)])
def test_the_stars_follow_the_price_through_the_range(price, stars):
    out = fv.star_rating(fv.fair_value(_pe(), price))
    assert out["available"] is True and out["stars"] == stars
    assert out["word"] == fv.STAR_WORDS[stars]
    assert "not a recommendation" in out["note"] and "5 stars below the fair value range" in out["rule"]


def test_no_stars_without_a_range_or_with_one_that_says_nothing():
    assert fv.star_rating({"available": False})["available"] is False
    wide = fv.fair_value(_pe(eps=1.08, bands=(72.5, 197.4, 391.4)), 370.59)
    assert fv.star_rating(wide)["available"] is False


def test_earnings_far_from_their_usual_level_get_no_verdict():
    gone = fv.fair_value(_pe(eps=0.09, bands=(24.8, 29.9, 35.8)), 119.33)
    assert gone["wide"] is True and gone["position"] == "too wide to call"
    assert "far from their usual level" in gone["wide_note"] and "44.4 times" in gone["wide_note"]
    assert fv.star_rating(gone)["available"] is False
    cheap = fv.fair_value(_pe(eps=50.0, bands=(27.9, 31.3, 34.9)), 300.0)
    assert cheap["wide"] is True, "a third of its usual value is the same doubt the other way"


def test_the_star_panel_sits_above_the_range_and_is_optics():
    out = _run("print('RESULT:' + JSON.stringify(renderFairValue(%s)));" % json.dumps({
        "stars": fv.star_rating(fv.fair_value(_pe(), 333.69)), "fair_value": fv.fair_value(_pe(), 333.69),
        "analysts": {"available": False}, "dividend": {"available": False}}))
    assert out.index("Optic star rating") < out.index("Fair value")
    assert "★☆☆☆☆" in out and "Above its usual valuation range" in out
    assert "not a recommendation" in out
    none = _run("print('RESULT:' + JSON.stringify(renderFairValue(%s)));" % json.dumps({
        "stars": {"available": False}, "fair_value": {"available": False, "reason": "x"}}))
    assert "Optic star rating" not in none


# ------------------------------------------------- the stars on the Overview
#
# "show the star rating on the overview tab too". The Investing card carries
# the stars once the rating is in and the P/E until then; checked in a browser:
# MSFT's card went from "28.8" to "★★★★☆ Optic star rating · Below its usual
# valuation · P/E 28.8", AMZN (no rating) kept its P/E, and SPY's Overview had
# no Financials card, as its strip has no Financials tab.

def _overview(script):
    exe = JSC if os.path.exists(JSC) else shutil.which("jsc")
    if not exe:
        pytest.skip("no JavaScriptCore on this machine")
    fns = ""
    for head in ("function starsText(", "function overviewCard(", "function ovInvestingCard("):
        at = APP.index(head)
        fns += APP[at:APP.index("\n}\n", at) + 3]
    prelude = """
      var STATE = { ticker: 'MSFT', swing: { ticker: 'MSFT', quote: { trailing_pe: 28.83 } },
                    fairValue: null, fairValueFor: null };
      function esc(v) { return String(v); }
      function fmt(v, d) { return Number(v).toFixed(d); }
    """
    out = subprocess.run([exe, "-e", prelude + fns + script], capture_output=True, text=True,
                         timeout=60, cwd=str(ROOT))
    assert "RESULT:" in out.stdout, (out.stdout + out.stderr)[-1500:]
    return json.loads(out.stdout.split("RESULT:", 1)[1].split("\n")[0])


def test_the_overview_card_shows_the_stars_once_they_are_in():
    rated = fv.star_rating(fv.fair_value(_pe(), 260.0))
    out = _overview("""
      var before = ovInvestingCard();
      STATE.fairValueFor = 'MSFT'; STATE.fairValue = { stars: %s }; var after = ovInvestingCard();
      STATE.fairValueFor = 'AAPL'; var stale = ovInvestingCard();
      STATE.fairValueFor = 'MSFT'; STATE.fairValue = { stars: { available: false } }; var none = ovInvestingCard();
      print('RESULT:' + JSON.stringify([before, after, stale, none]));
    """ % json.dumps(rated))
    before, after, stale, none = out
    assert ">28.8</span>" in before and "trailing P/E" in before
    assert "★★★★☆" in after and "Optic star rating · Below its usual valuation · P/E 28.8" in after
    assert "★" not in stale, "another symbol's rating is not this one's"
    assert ">28.8</span>" in none and "★" not in none


def test_the_overview_asks_for_the_rating_and_a_fund_has_no_financials_card():
    view = APP[APP.index("function renderOverviewView() {"):]
    view = view[:view.index("\n}\n")]
    assert "${ovInvestingCard()}" in view and "  loadFairValue();" in view
    assert "${symbolIsFund(STATE.ticker) ? '' : overviewCard('financials', 'Financials'," in view
    load = APP[APP.index("async function loadFairValue(force) {"):]
    load = load[:load.index("\n}\n")]
    assert "if (card && STATE.view === 'overview') card.outerHTML = ovInvestingCard();" in load
