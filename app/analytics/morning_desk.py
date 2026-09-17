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

    bp = rate.get("basis_points") if rate.get("available") else None
    if rate.get("kind") == "probability" and rate.get("probability") is not None:
        out.append(
            "The fed funds strip has {}% of a {:.0f} basis point {} priced for the "
            "{} meeting, against an effective rate of {}% today. {}"
            .format(rate["probability"], rate.get("step_bp", STEP_BP),
                    rate.get("direction") or "move",
                    datetime.fromisoformat(rate["meeting"]).strftime("%-d %B"),
                    rate.get("effective"),
                    "That is the market saying the decision itself is settled, "
                    "which moves the question to the language around it."
                    if (rate["probability"] or 0) >= 80 else
                    "That is a market that has not made its mind up, which is "
                    "the condition that keeps a room tense into the print."))
    elif bp is not None and abs(bp) >= RATE_LEAD_BP:
        out.append(
            "The front fed funds contract is pricing an average effective rate of "
            "{}% for {}, against {}% today. So about {:.0f} basis points of {} sits "
            "in the curve before anyone has said anything."
            .format(rate.get("implied_average"),
                    rate.get("contract_month_label") or "the delivery month",
                    rate.get("effective"), abs(bp),
                    "tightening" if bp > 0 else "easing"))

    if spx and spx.get("chg_1d") is not None:
        vix = tape.get("vix") or {}
        line = "{} are {} at {}".format(
            spx.get("label"), _move_word(spx.get("chg_1d")), _pct(spx.get("chg_1d")))
        others = [r for r in front if r is not spx and r.get("chg_1d") is not None]
        if others:
            line += ", with {}".format(" and ".join(
                "{} {}".format(r["label"], _pct(r["chg_1d"])) for r in others[:2]))
        if vix.get("last") is not None:
            line += ". Volatility is at {}{}".format(
                vix["last"],
                ", which is not a market bracing for much" if vix["last"] < 18
                else ", which is a market paying up for protection" if vix["last"] > 24
                else "")
        out.append(line + ".")

    if releases:
        titles = [r.get("title") or "" for r in releases[:3]]
        out.append("On the calendar this morning: {}. The numbers are below, each "
                   "against its own prior print.".format(", ".join(t for t in titles if t)))
    elif catalyst and catalyst.get("days_away") is not None:
        when = (catalyst.get("when_label") or "").lower() or "ahead"
        flow = (catalyst.get("category") or "") in FLOW_CATEGORIES
        out.append("Nothing is scheduled to print today. The next dated item is {} "
                   "{}, which {}."
                   .format(catalyst.get("title"), when,
                           "changes what is holding price rather than what is "
                           "known about the economy" if flow else
                           "is what the week builds toward"))
    else:
        out.append("Nothing is scheduled to print today and nothing dated is inside "
                   "the calendar horizon, so this is a tape trading on its own.")
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
        step = "{:.0f}bp".format(rate.get("step_bp", STEP_BP))
        move = rate.get("direction") or "move"
        rows.append({
            "label": "{} {}, and a soft statement".format(step, move),
            "text": "If the decision lands as priced and the language leans "
                    "toward it being a response to one thing rather than the "
                    "start of a series, the event risk comes out of the market "
                    "and the tape is free to move on whatever it was going to "
                    "trade anyway."})
        rows.append({
            "label": "{} {}, and a firm statement".format(step, move),
            "text": "If the language points at more of the same, the front end "
                    "reprices first and equities take their cue from it. The "
                    "thing to watch is the two-year, not the index."})
        rows.append({
            "label": "No change",
            "text": "With {}% priced for a {}, holding would be the genuine "
                    "surprise, and a surprise reprices bonds, the dollar and "
                    "equities together rather than one at a time."
                    .format(rate["probability"], move)})
    elif catalyst and (catalyst.get("category") or "") in FLOW_CATEGORIES:
        title = catalyst.get("title") or "the next event"
        rows.append({
            "label": "{}, and the unwind is orderly".format(title),
            "text": "Expiries and positioning reports do not print a number, so "
                    "there is nothing to beat or miss. What they do is move open "
                    "interest: contracts that have been pinning price stop "
                    "pinning it. An orderly one passes without a mark on the "
                    "chart."})
        rows.append({
            "label": "{}, and it moves the tape".format(title),
            "text": "Where a large amount of open interest sits at one strike, "
                    "price can be held near it into the event and released "
                    "after. A move on the day that reverses the next morning is "
                    "the signature of flow rather than news."})
        rows.append({
            "label": "The session after",
            "text": "Usually the more informative one. With the expiring "
                    "contracts gone, whatever the tape does next is position "
                    "being rebuilt rather than defended."})
    elif catalyst:
        title = catalyst.get("title") or "the next release"
        rows.append({
            "label": "{} comes in hot".format(title),
            "text": "A print above its prior reading pushes the argument toward "
                    "policy staying tighter for longer, which shows up in the "
                    "front end before it shows up in the index."})
        rows.append({
            "label": "{} comes in soft".format(title),
            "text": "A print below its prior reading does the reverse, and the "
                    "first place to look is whether the move in yields is "
                    "matched by one in the dollar. If it is not, the market did "
                    "not believe it."})
        rows.append({
            "label": "It lands in line",
            "text": "The most common outcome and the least discussed one. An "
                    "in-line print leaves the tape trading position rather than "
                    "news, and the first hour usually reverses."})
    return rows


def _note(rate: Dict[str, Any], catalyst: Optional[Dict[str, Any]]) -> str:
    """One factual correction of whatever the branches invite people to get wrong."""
    if rate.get("kind") == "probability":
        return ("Worth being precise about what that percentage is. It is not a "
                "forecast and nobody surveyed anyone for it: it is backed out of "
                "the price of a futures contract that settles on the average "
                "effective rate for its delivery month, so it is what the market "
                "is charging rather than what it believes. The decision itself is "
                "a vote of the committee, and the chair is one member of it.")
    if rate.get("available") and rate.get("basis_points") is not None:
        return ("That basis point figure is a monthly average, not odds on a "
                "meeting. {} Turning one into the other needs the contract for "
                "the month the decision sits in, and this says which it has."
                .format(rate.get("limit") or ""))
    if catalyst:
        return ("The comparison below is against the previous print, not against "
                "an expectation. This terminal does not carry surveyed consensus, "
                "so a release that beats its own prior month is described as "
                "exactly that and not as a beat.")
    return ("A quiet calendar is not the same as a quiet market. It means the "
            "moves on the tape are position and flow rather than news, which is "
            "the condition in which the first hour is least worth trusting.")


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
        bits.append("Yields are {} and the dollar is {}, which {}"
                    .format(_move_word(ten["chg_1d"]), _move_word(dollar["chg_1d"]),
                            "leaves them saying nothing together: one of the two "
                            "has not moved" if flat else
                            "is the combination that usually means a rate story"
                            if same else
                            "pull against each other, so whatever is moving one is "
                            "not the thing moving the other"))
    if crude.get("chg_1d") is not None and abs(crude["chg_1d"]) >= 1.5:
        bits.append("crude is {} at {}, which feeds the inflation argument from "
                    "the cost side".format(_move_word(crude["chg_1d"]),
                                           _pct(crude["chg_1d"])))
    tail = ("Whatever the first reaction is, it is the least reliable part of the "
            "day. The market has to digest the path rather than the headline, and "
            "that shows up over the days after, not in the first hour."
            if (releases or rate.get("kind") == "probability") else
            "With nothing dated to react to, the moves here are flow. That makes "
            "levels worth more than narrative today.")
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
        "No consensus estimates. Releases are compared against their own prior "
        "print, because surveyed expectations are licensed and this terminal "
        "does not carry them.",
        "Adjacency is not causation. Where a headline and a move happen the same "
        "morning, both are reported and no mechanism is asserted between them.",
    ]
    if not releases:
        limits.append("Nothing is scheduled for today, so there is no data section.")
    if rate.get("available") and rate.get("kind") == "priced":
        limits.append(rate.get("limit") or "")

    return {
        "available": True,
        "date": today.isoformat(),
        "title": "Morning desk",
        "lead": _lead(tape, rate, catalyst, releases),
        "scenarios": _scenarios(rate, catalyst),
        "note": _note(rate, catalyst),
        "calendar": _calendar(releases),
        "overall": _overall(tape, rate, releases),
        "tape": tape,
        "releases": releases,
        "catalyst": catalyst,
        "rate_path": rate,
        "stories": (stories or [])[:3],
        "limits": [l for l in limits if l],
    }
