"""The morning desk: what happened, what it means, and what would change it.

Written to a fixed shape, because the shape is the argument. A reader who opens
this every day should find the same five moves in the same order: the one thing
setting the tone, the branches that thing could take, a factual correction of
whatever the branch invites people to get wrong, the releases with their
numbers, and a synthesis that says what to distrust.

**What this will not do.** It will not print a consensus estimate, because
nothing here has one: FRED publishes what was released, and surveyed
expectations are licensed (see `econ.py`). So a release is compared against its
own prior print, which is a fact, rather than against "what the street
expected", which would be invented. It will not tell anyone what to buy, size
or when to enter. And it will not name a mechanism for a move it cannot
measure, which is the same rule `global_markets.py` is built on.

**The rate line is derived, not forecast.** Fed funds futures are a price, and
the arithmetic from that price to an implied policy rate is public and stated in
`rate_path`. Where a meeting falls inside the contract month the month-weighted
method gives a probability; where one does not, this reports basis points priced
and says that is what it is, rather than dressing a monthly average up as odds
on a decision that is not in the window.
"""

from __future__ import annotations

import calendar as _cal
import logging
import re
from datetime import date, datetime
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)

# 30-day fed funds futures. Priced as 100 minus the average daily effective rate
# over the contract month, which is what makes the arithmetic below possible.
RATE_SYMBOL = "ZQ=F"

# One policy step. The committee has moved in other sizes and may again; this is
# the denominator for "how much of a move is priced", and it is named rather
# than buried so a reader can see what the percentage is a percentage of.
STEP_BP = 25.0

# Above this many basis points priced, the rate market is saying something worth
# leading with. Below it, the number is noise and the desk leads elsewhere.
RATE_LEAD_BP = 8.0

# Calendar categories that do not publish a number.
#
# The first version of the branch block applied "comes in hot" and "comes in
# soft" to whatever the next catalyst was, and the next catalyst was quadruple
# witching: an options expiry has no print to come in hot or soft, so the desk
# invented a reading for an event that does not have one. Separated by what the
# event *is* rather than by how important it is.
FLOW_CATEGORIES = ("positioning",)

# Below this, a percentage move is not a direction. Used where two instruments
# are compared: a falling yield alongside a dollar that has not moved is not
# "the combination that means a rate story", and reading flat as positive said
# it was.
FLAT_PCT = 0.1

# Days that must fall after the meeting for the unwind to be worth doing.
#
# The month-weighted method divides the whole month's priced move by the days
# remaining after the decision, so a meeting near month-end multiplies both the
# signal and the noise: a meeting on the 28th of a 31-day month turned 27bp
# priced into a 209bp implied move and a probability pinned at 100%. That is not
# the market being certain, it is the wrong contract for the question. Traders
# use the following month's contract for a late-month meeting; this refuses the
# calculation instead of publishing its artefact.
MIN_DAYS_AFTER = 7


def _f(value: Any, digits: int = 2) -> Optional[float]:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    if out != out or out in (float("inf"), float("-inf")):
        return None
    return round(out, digits)


# ------------------------------------------------------------- the rate path


def _as_date(value: Any) -> Optional[date]:
    if isinstance(value, date):
        return value
    if isinstance(value, str) and value:
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return None
    return None


def rate_path(quote: Optional[Dict[str, Any]], effective: Optional[float],
              contract_month: Any = None, meeting: Any = None,
              today: Any = None) -> Dict[str, Any]:
    """What the fed funds strip is pricing, and by what arithmetic.

    `quote` is a `batch_quote` row for ZQ=F, `effective` the current daily
    effective rate from FRED's DFF, `contract_month` the delivery month the
    front contract actually refers to, `meeting` the next FOMC decision date.

    The contract settles on the *average* effective rate across its delivery
    month, so a meeting partway through blends the old rate and the new one.
    With a meeting inside that month the weighting is undone to recover the rate
    expected after it, which is the CME method and the only version of this that
    is odds on a decision rather than a statement about a monthly average.

    `contract_month` is not optional in spirit. The first version of this
    assumed the front contract meant the current calendar month; on 2026-09-17
    ZQ=F was the *October* contract, so weighting against September's days
    turned 27bp of priced tightening into a 101bp move and a probability that
    clamped at 100%. Without the month, this reports the priced move and says
    so rather than guessing.
    """
    if not quote or quote.get("last") is None:
        return {"available": False,
                "reason": "The fed funds futures quote is unavailable."}
    if effective is None:
        return {"available": False,
                "reason": "The current effective rate is unavailable, so there is "
                          "nothing to measure the futures price against."}

    price = float(quote["last"])
    implied_avg = _f(100.0 - price, 4)
    if implied_avg is None:
        return {"available": False, "reason": "The futures price did not parse."}

    bp = _f((implied_avg - float(effective)) * 100.0, 1)
    out: Dict[str, Any] = {
        "available": True,
        "symbol": RATE_SYMBOL,
        "price": _f(price, 4),
        "implied_average": implied_avg,
        "effective": _f(effective, 3),
        "basis_points": bp,
        "kind": "priced",
        "method": "Fed funds futures settle on 100 minus the average daily "
                  "effective rate over the delivery month.",
    }

    cm = _as_date(contract_month)
    meet = _as_date(meeting)
    if cm is None:
        out["limit"] = ("The delivery month of the front contract could not be "
                        "read, so this is the move priced into that month's "
                        "average and not odds on any one meeting.")
        return out

    out["contract_month"] = cm.isoformat()
    out["contract_month_label"] = cm.strftime("%B %Y")

    if not (meet and meet.year == cm.year and meet.month == cm.month):
        out["limit"] = ("No meeting falls inside {}, the delivery month of the "
                        "front contract, so this is the move priced into that "
                        "month's average rather than the odds on a decision."
                        .format(cm.strftime("%B")))
        return out

    # The unwind treats today's effective rate as the rate in force right up to
    # the meeting. That only holds when the delivery month is the month we are
    # in: with the contract on October and today in September, a September
    # decision would already be lifting October's whole average and the method
    # would read its effect as post-meeting tightening. Measured on 2026-09-17,
    # that mistake turned 27bp priced into 46.5bp and a probability at the cap.
    now = _as_date(today) or date.today()
    if (cm.year, cm.month) != (now.year, now.month):
        out["limit"] = ("The front contract delivers in {}, which is not the "
                        "current month, so the rate in force before the meeting "
                        "is not today's. This is the move priced into {}'s "
                        "average; odds on the decision need the contract for the "
                        "month the meeting sits in."
                        .format(cm.strftime("%B"), cm.strftime("%B")))
        return out

    days = _cal.monthrange(cm.year, cm.month)[1]
    before = meet.day - 1            # days still at the current rate
    after = days - before            # days at whatever the meeting sets
    if after < MIN_DAYS_AFTER:
        out["limit"] = ("The meeting falls on the {} of {}, leaving {} day{} of "
                        "the delivery month after it. Unwinding a whole month's "
                        "average across that few days amplifies the error more "
                        "than the signal, so this stays as the move priced into "
                        "the month rather than odds on the decision."
                        .format(meet.day, cm.strftime("%B"), after,
                                "" if after == 1 else "s"))
        return out

    # implied_avg = (before * effective + after * expected) / days
    expected = (implied_avg * days - before * float(effective)) / after
    move_bp = (expected - float(effective)) * 100.0
    odds = max(0.0, min(100.0, abs(move_bp) / STEP_BP * 100.0))
    out.update({
        "kind": "probability",
        "meeting": meet.isoformat(),
        "expected_after": _f(expected, 3),
        "basis_points": _f(move_bp, 1),
        "step_bp": STEP_BP,
        "probability": _f(odds, 0),
        "direction": "hike" if move_bp > 0 else "cut" if move_bp < 0 else "hold",
        "method": ("Fed funds futures settle on 100 minus the average daily "
                   "effective rate over the delivery month. With {} of {} days "
                   "in {} falling after the meeting, an implied average of {}% "
                   "unwinds to {}% afterwards against {}% today, which is {} of "
                   "a {:.0f}bp step.").format(
                       after, days, cm.strftime("%B"), implied_avg,
                       _f(expected, 3), _f(effective, 3),
                       "{:.0f}%".format(odds), STEP_BP),
    })
    return out


# ------------------------------------------------------------------ the tape


def _tape(macro: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Where the tape stands, from the macro strip the rest of the app uses."""
    groups = ((macro or {}).get("groups")) or {}
    rows: Dict[str, Dict[str, Any]] = {}
    for bucket in groups.values():
        for row in (bucket or []):
            if row.get("symbol"):
                rows[row["symbol"]] = row
    pick = lambda sym: rows.get(sym) or {}
    return {
        "futures": [r for r in (pick("ES=F"), pick("NQ=F"), pick("RTY=F"))
                    if r.get("chg_1d") is not None],
        "cash": [r for r in (pick("^GSPC"), pick("^NDX"), pick("^RUT"))
                 if r.get("chg_1d") is not None],
        "vix": pick("^VIX"),
        "ten_year": pick("^TNX"),
        "crude": pick("CL=F"),
        "gold": pick("GC=F"),
        "dollar": pick("DX-Y.NYB"),
    }


def _move_word(pct: Optional[float]) -> str:
    if pct is None:
        return "unchanged"
    size = abs(pct)
    if size < 0.1:
        return "flat"
    lead = "up" if pct > 0 else "down"
    if size >= 1.5:
        return lead + " sharply"
    if size >= 0.6:
        return lead
    return lead + " slightly"


def _pct(value: Optional[float], digits: int = 2) -> str:
    return "unavailable" if value is None else "{:+.{d}f}%".format(value, d=digits)


# --------------------------------------------------------------- the calendar


def _today_releases(events: Optional[Dict[str, Any]],
                    today: Optional[date] = None) -> List[Dict[str, Any]]:
    """Today's scheduled items, biggest first."""
    rows = ((events or {}).get("events")) or []
    out = [r for r in rows if r.get("days_away") == 0]
    out.sort(key=lambda r: -(r.get("importance") or 0))
    return out


def _next_catalyst(events: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """The next thing with real weight, today or ahead."""
    rows = ((events or {}).get("events")) or []
    ranked = [r for r in rows if (r.get("impact") or "") in ("high", "medium")]
    ranked.sort(key=lambda r: (r.get("days_away") if r.get("days_away") is not None else 99,
                               -(r.get("importance") or 0)))
    return ranked[0] if ranked else None


def _lead(tape: Dict[str, Any], rate: Dict[str, Any],
          catalyst: Optional[Dict[str, Any]],
          releases: List[Dict[str, Any]]) -> List[str]:
    """What is setting the tone, and what the tape says about positioning.

    Ordered by what is actually happening rather than by a fixed template: a
    rate market pricing a move leads, then a dated catalyst, then the tape on
    its own. A morning with none of those gets a short paragraph, because the
    alternative is padding a quiet day into sounding like a busy one.
    """
    out: List[str] = []
    fut = tape.get("futures") or []
    cash = tape.get("cash") or []
    front = (fut or cash)
    spx = next((r for r in front if "S&P" in (r.get("label") or "")), None)

    # In words anyone can follow: see the note on DESK_PROMPT in app/ai.py for
    # what this voice replaced. A figure stays where it is the point, rounded,
    # and a market word is said in plain terms the first time it appears.
    bp = rate.get("basis_points") if rate.get("available") else None
    if rate.get("kind") == "probability" and rate.get("probability") is not None:
        move = {"cut": "cut", "hike": "raise"}.get(rate.get("direction") or "", "change")
        out.append(
            "Traders betting on interest rates put the chance that the Federal "
            "Reserve will {} rates by a quarter of a point at its {} meeting at "
            "about {:.0f}%. {}"
            .format(move, datetime.fromisoformat(rate["meeting"]).strftime("%-d %B"),
                    rate["probability"],
                    "So most of them think the decision is already settled, and what "
                    "matters is what the Fed says about what comes next."
                    if (rate["probability"] or 0) >= 80 else
                    "So the market has not made up its mind, which tends to keep "
                    "investors on edge until the decision."))
    elif bp is not None and abs(bp) >= RATE_LEAD_BP:
        out.append(
            "Traders expect the Federal Reserve's interest rate to {} a little over "
            "{}, before the Fed has said anything about it."
            .format("rise" if bp > 0 else "fall",
                    rate.get("contract_month_label") or "the coming month"))

    if spx and spx.get("chg_1d") is not None:
        vix = tape.get("vix") or {}
        # One figure, the S&P's, which is the one the strip above leads with;
        # the rest in words. "S&P 500 futures +0.48%, Nasdaq 100 futures
        # +0.58%" read as a table, not a sentence.
        line = "{} are {} ({})".format(
            spx.get("label"), _move_word(spx.get("chg_1d")), _pct(spx.get("chg_1d")))
        others = [r for r in front if r is not spx and r.get("chg_1d") is not None]
        if others:
            names = [r["label"] for r in others[:2]]
            # "Nasdaq 100 futures is up" read wrong: futures are plural.
            plural = len(names) > 1 or names[0].endswith("futures")
            line += ", and {} {} {}".format(" and ".join(names), "are" if plural else "is",
                                            _move_word(others[0]["chg_1d"]))
        out.append(line + ".")
        if vix.get("last") is not None:
            out.append(
                "Investors look calm: the VIX, a measure of how nervous they are, is low."
                if vix["last"] < 18 else
                "Investors look nervous: the VIX, a measure of how worried they are, "
                "is high, which means people are paying up to protect themselves."
                if vix["last"] > 24 else
                "The VIX, a measure of how nervous investors are, is in its normal range.")

    if releases:
        titles = [r.get("title") or "" for r in releases[:3]]
        out.append("Today's reports: {}. Each is explained below, next to its last "
                   "reading.".format(", ".join(t for t in titles if t)))
    elif catalyst and catalyst.get("days_away") is not None:
        label = catalyst.get("when_label") or ""
        # "tomorrow" reads as a word; a date needs its "on", where lowering it
        # gave "the next one is CFTC Commitments of Traders fri oct 9".
        when = (label.lower() if label in ("Today", "Tomorrow", "This week", "Next week")
                else "on " + label if label else "ahead")
        flow = (catalyst.get("category") or "") in FLOW_CATEGORIES
        out.append("There are no big economic reports today. The next one is {} {}, "
                   "which {}."
                   .format(catalyst.get("title"), when,
                           "shows what big traders were already betting on rather "
                           "than anything new about the economy" if flow else
                           "is what this week is building up to"))
    else:
        out.append("There are no big economic reports today or in the days ahead, so "
                   "prices are moving on their own.")
    return out


def _scenarios(rate: Dict[str, Any],
               catalyst: Optional[Dict[str, Any]]) -> List[Dict[str, str]]:
    """The branches, conditional and without a recommendation in any of them.

    The sample's shape: name the branch, say what it would mean. Written as
    conditions rather than predictions, which is the difference between
    describing a setup and calling it.
    """
    rows: List[Dict[str, str]] = []
    if rate.get("kind") == "probability" and rate.get("probability") is not None:
        move = {"cut": "cuts", "hike": "raises"}.get(rate.get("direction") or "", "moves")
        rows.append({
            "label": "The Fed {} rates and sounds relaxed".format(move),
            "text": "If the decision goes as traders expect and the Fed signals it "
                    "is a one-off, the uncertainty is over and markets can move on."})
        rows.append({
            "label": "The Fed {} rates and hints at more".format(move),
            "text": "If the Fed suggests further moves are coming, interest rates on "
                    "bonds react first, and stocks usually follow their lead."})
        rows.append({
            "label": "No change",
            "text": "With about {:.0f}% of traders expecting a move, holding rates "
                    "steady would be a real surprise, and surprises tend to move "
                    "bonds, the dollar and stocks all at once."
                    .format(rate["probability"])})
    elif catalyst and (catalyst.get("category") or "") in FLOW_CATEGORIES:
        # Not "comes in higher": an options expiry or a positioning report
        # publishes no number to be higher or lower about. And these branches
        # are about bets expiring, so they are an expiry's alone. The weekly
        # positions report expires nothing and moves nothing on its own, and
        # was being given "the bets expire" anyway; it gets no branches.
        title = catalyst.get("title") or "the next event"
        if not re.search(r"expir|witching", title, re.I):
            return rows
        rows.append({
            "label": "{} passes quietly".format(title),
            "text": "Option expiries and reports on what big traders hold do not "
                    "print a number, so there is nothing to beat or miss. Most of "
                    "the time they pass without anyone noticing."})
        rows.append({
            "label": "{} moves prices".format(title),
            "text": "When many bets are tied to one price, a stock or an index can "
                    "stick near it until the bets expire and move more freely after. "
                    "A jump that reverses the next morning is usually this, not news."})
        rows.append({
            "label": "The day after",
            "text": "Usually more telling. Once the expiring bets are gone, the next "
                    "move reflects what investors actually think."})
    elif catalyst:
        title = catalyst.get("title") or "the next report"
        rows.append({
            "label": "{} comes in higher than last time".format(title),
            "text": "For most reports, a higher reading makes it more likely that "
                    "interest rates stay high for longer. Bond markets usually react "
                    "before stocks do."})
        rows.append({
            "label": "{} comes in lower than last time".format(title),
            "text": "That points the other way. Watch whether interest rates and the "
                    "dollar both fall: if only one does, investors may not believe "
                    "the number."})
        rows.append({
            "label": "It comes in about the same",
            "text": "The most common result. Markets then tend to carry on with "
                    "whatever they were already doing, and early moves often reverse."})
    return rows


def _note(rate: Dict[str, Any], catalyst: Optional[Dict[str, Any]],
          releases: Optional[List[Dict[str, Any]]] = None) -> str:
    """One factual correction of whatever the branches invite people to get wrong."""
    if rate.get("kind") == "probability":
        return ("That percentage is not a forecast or a survey. It is worked out "
                "from what traders are paying in the futures market, so it shows "
                "where their money is, not what will happen. The decision is a "
                "vote by the Fed's committee.")
    bp = rate.get("basis_points") if rate.get("available") else None
    if bp is not None and abs(bp) >= RATE_LEAD_BP:
        # Only when the lead said it. Below RATE_LEAD_BP the lead leaves the
        # rate out, and this explained "that expected change" to a reader who
        # had not been told of one.
        # Not odds: a contract priced on the month's average rate says how far
        # the average is expected to move, not how likely a decision is. The
        # contract-month caveat itself is in the limits list, in full.
        return ("That expected change is an average over the whole month, not the "
                "chance of a decision at a particular meeting.")
    # Only with reports below to compare: on a day whose next item is days
    # away this told the reader about "each report below" with none there.
    if releases:
        return ("Each report below is compared with its own last reading, not with "
                "what economists predicted. This site does not carry those "
                "predictions, so \"higher than last time\" means exactly that.")
    return ("A quiet calendar does not mean a quiet market. Without news, prices "
            "move on traders' own buying and selling, so the first hour of trading "
            "is the least worth trusting.")


def _calendar(releases: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    """Each release, with what it is for and its own prior print where the feed
    carries one. No forecast column, and the absence is stated rather than left
    as an empty cell."""
    rows: List[Dict[str, str]] = []
    for row in releases:
        parts: List[str] = []
        if row.get("why"):
            parts.append(row["why"])
        prev = row.get("previous") or {}
        if isinstance(prev, dict) and prev.get("headline"):
            parts.append("Last time: {}".format(prev["headline"]))
        if row.get("impact_note"):
            parts.append(row["impact_note"])
        rows.append({
            "title": row.get("title") or "",
            "time": row.get("time_label") or "",
            "impact": row.get("impact") or "",
            "detail": " ".join(parts),
        })
    return rows


def _overall(tape: Dict[str, Any], rate: Dict[str, Any],
             releases: List[Dict[str, Any]]) -> str:
    """The synthesis, and the caution the sample ends on."""
    bits: List[str] = []
    ten = tape.get("ten_year") or {}
    dollar = tape.get("dollar") or {}
    crude = tape.get("crude") or {}
    if ten.get("chg_1d") is not None and dollar.get("chg_1d") is not None:
        flat = abs(ten["chg_1d"]) < FLAT_PCT or abs(dollar["chg_1d"]) < FLAT_PCT
        same = (ten["chg_1d"] > 0) == (dollar["chg_1d"] > 0)
        bits.append("Interest rates on government bonds are {} and the dollar is {}, {}"
                    .format(_move_word(ten["chg_1d"]), _move_word(dollar["chg_1d"]),
                            "but one of the two has barely moved, so together they do "
                            "not tell a clear story" if flat else
                            # Not "it is usually about interest rates", which
                            # read back as rates being about rates.
                            "and when the two move together like this, investors "
                            "are usually reacting to where they think interest "
                            "rates are headed"
                            if same else
                            "so they are pulling in different directions, and "
                            "something different is driving each one"))
    if crude.get("chg_1d") is not None and abs(crude["chg_1d"]) >= 1.5:
        bits.append("oil is {}, which matters because energy costs feed into the "
                    "prices of almost everything".format(_move_word(crude["chg_1d"])))
    tail = ("The first reaction to news is the least reliable part of the day. The "
            "real verdict usually shows up over the next few days."
            if (releases or rate.get("kind") == "probability") else
            "With no big news today, moves are mostly traders shuffling their bets, "
            "so where prices actually end up matters more than any explanation for "
            "them.")
    if not bits:
        return tail
    return "{}. {}".format(". ".join(b[0].upper() + b[1:] for b in bits), tail)


def build(macro: Optional[Dict[str, Any]] = None,
          events: Optional[Dict[str, Any]] = None,
          rate: Optional[Dict[str, Any]] = None,
          stories: Optional[List[Dict[str, Any]]] = None,
          today: Optional[date] = None) -> Dict[str, Any]:
    """The facts the desk is written from, plus what it cannot say.

    Assembled from panels the rest of the app already builds, so the desk cannot
    disagree with the strip above it. Nothing here fetches.
    """
    today = today or date.today()
    tape = _tape(macro)
    releases = _today_releases(events, today)
    catalyst = _next_catalyst(events)
    rate = rate or {"available": False, "reason": "Not requested."}

    limits = [
        "No consensus estimates, meaning no economists' predictions. Each report is "
        "compared with its own last reading, because those predictions are sold "
        "under licence and this site does not carry them.",
        "Happening together is not the same as causing. When a headline and a "
        "price move land on the same morning, both are reported, and neither is "
        "said to have caused the other.",
    ]
    if not releases:
        limits.append("Nothing is scheduled for today, so there is no data section.")
    if rate.get("available") and rate.get("kind") == "priced":
        limits.append(rate.get("limit") or "")

    return {
        "available": True,
        "date": today.isoformat(),
        "title": "Optic Desk",
        "lead": _lead(tape, rate, catalyst, releases),
        "scenarios": _scenarios(rate, catalyst),
        "note": _note(rate, catalyst, releases),
        "calendar": _calendar(releases),
        "overall": _overall(tape, rate, releases),
        "tape": tape,
        "releases": releases,
        "catalyst": catalyst,
        "rate_path": rate,
        "stories": (stories or [])[:3],
        "limits": [l for l in limits if l],
    }
