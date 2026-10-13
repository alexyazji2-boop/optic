"""The assembled edition: the whole newsletter from the outline, with no model.

Published when the assistant is unavailable or a written draft fails its checks
twice, and labelled so. It is drier than a written edition but held to the same
checks (tests/test_desk_edition.py runs it through `check.run`), because it is
the floor every reader gets on a bad day.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Optional

from .outline import salience

_DAY = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def _pct(v: Optional[float], d: int = 1) -> str:
    return "{:+.{d}f}%".format(v, d=d) if v is not None else "unavailable"


def _when(iso: Optional[str]) -> str:
    try:
        d = datetime.fromisoformat(iso).date() if "T" in (iso or "") else date.fromisoformat((iso or "")[:10])
    except (TypeError, ValueError):
        return ""
    return "{} {} {}".format(_DAY[d.weekday()], d.day, d.strftime("%B"))


def _unit(text: str, *cites: Optional[str]) -> Dict[str, Any]:
    return {"text": text, "cites": [c for c in cites if c]}


def _word(v: Optional[float], flat: float = 0.15) -> str:
    if v is None:
        return "was unchanged"
    if abs(v) < flat:
        return "was little changed"
    return "rose" if v > 0 else "fell"


def build(bundle: Dict[str, Any], outline: Dict[str, Any]) -> Dict[str, Any]:
    evm = {e["id"]: e for e in bundle.get("evidence") or []}
    sym = lambda s, kind=None: next((e for e in evm.values() if e.get("symbol") == s
                                     and (kind is None or e.get("kind") == kind)), None)
    spy, qqq, iwm = sym("SPY", "index"), sym("QQQ", "index"), sym("IWM", "index")
    tnx, vix, dxy = sym("^TNX"), sym("^VIX"), sym("DX-Y.NYB")
    tension = outline.get("tension")
    companies = [evm[c] for c in outline.get("companies") or [] if c in evm]
    lead_co = max(companies, key=lambda e: salience(e) if e.get("kind") == "company" else 0, default=None)
    if lead_co is not None and lead_co.get("kind") != "company":
        lead_co = next((e for e in companies if e.get("kind") == "company"), None)

    # Headline: the most salient company move or the index, then the tension.
    if lead_co is not None:
        head = "{} {} {:.1f}%".format(lead_co["symbol"], "falls" if (lead_co.get("value") or 0) < 0 else "rises",
                                     abs(lead_co.get("value") or 0))
    elif spy is not None:
        head = "S&P 500 {} {:.1f}%".format("slips" if (spy.get("value") or 0) < 0 else "gains", abs(spy.get("value") or 0))
    else:
        head = "Markets ahead of {}".format(tension["what"] if tension else "the next session")
    if tension:
        head += "; {} is due {}".format(tension["what"], _when(tension["when"]).split(" ")[0])
    head_cites = [lead_co["id"] if lead_co else (spy or {}).get("id"), (tension or {}).get("evidence")]

    sections: List[Dict[str, Any]] = []
    opening: List[Dict[str, Any]] = []
    if spy and qqq:
        s = "The S&P 500 {} {} on the session of {}, and the Nasdaq 100 {} {}.".format(
            _word(spy.get("value")), _pct(spy.get("value"), 2), _when(spy.get("event_at")),
            _word(qqq.get("value")), _pct(qqq.get("value"), 2))
        if iwm:
            s += " Smaller companies in the Russell 2000 {} {}.".format(_word(iwm.get("value")), _pct(iwm.get("value"), 2))
        opening.append(_unit(s, spy["id"], qqq["id"], (iwm or {}).get("id")))
    done = [e for e in companies if e.get("kind") == "earnings"]
    if done:
        names = ", ".join(e["symbol"] for e in done)
        conflict = any((e.get("detail") or {}).get("consensus_conflict") for e in done)
        opening.append(_unit(
            "Results from {} set much of the tone.{}".format(
                names, " The free data carries two different consensus figures for {}, so whether each result "
                       "cleared expectations depends on which figure is used, and this edition does not call it."
                .format("these companies" if len(done) > 1 else "this company") if conflict else ""),
            *[e["id"] for e in done]))
    if tension:
        t = evm.get(tension["evidence"]) or {}
        prev = tension.get("previous")
        opening.append(_unit(
            "The next test is {} on {}.{}".format(
                tension["what"], _when(tension["when"]),
                " Its previous reading was {}{}.".format(prev, "%" if (t.get("detail") or {}).get("category") == "inflation" else "")
                if prev is not None else ""),
            tension["evidence"]))
    sections.append({"id": "opening", "paragraphs": opening or [_unit("A quiet session with little to report.", (spy or {}).get("id"))]})

    # The numbers that matter.
    items = []
    for i in outline.get("numbers") or []:
        e = evm.get(i)
        if not e:
            continue
        items.append(_number_item(e))
    if items:
        sections.append({"id": "numbers", "title": "The numbers that matter", "items": items})

    # Why this matters: the relationships, with their status.
    why = []
    for r in outline.get("relationships") or []:
        verdict = {"consistent": "Today's figures fit that pattern.",
                   "contradicted": "Today's figures went the other way, so something else was driving at least one of them.",
                   "mixed": "Today's figures give a mixed picture.",
                   "insufficient": "There is not enough evidence today to say more."}[r["status"]]
        why.append(_unit("{}. {} {}".format(r["claim"], r["note"], verdict), *r["evidence"][:3]))
    if why:
        sections.append({"id": "why", "title": "Why this matters", "paragraphs": why[:4]})

    # Good, bad, unresolved.
    leaders = [evm[i] for i in outline.get("leaders") or [] if i in evm]
    laggards = [evm[i] for i in outline.get("laggards") or [] if i in evm]
    good = [_unit("{} led the sectors at {}.".format(e["label"], _pct(e.get("value"), 2)), e["id"]) for e in leaders[:2]]
    bad = [_unit("{} lagged at {}.".format(e["label"], _pct(e.get("value"), 2)), e["id"]) for e in laggards[:2]]
    unresolved = [_unit("For {}, the free data's two consensus figures were {} and {}, so the surprise is unresolved.".format(
        evm[c["evidence"]].get("symbol"), c.get("calendar"), c.get("history")), c["evidence"])
        for c in outline.get("conflicts") or []]
    if good or bad or unresolved:
        sections.append({"id": "balance", "title": "The good, the bad and the unresolved",
                         "good": good, "bad": bad, "unresolved": unresolved})

    # Companies in focus.
    focus = []
    for e in companies:
        d = e.get("detail") or {}
        if e.get("kind") == "earnings":
            text = "{} reported EPS of ${:.2f} against a consensus of ${:.2f} in the history table".format(
                e["symbol"], d.get("eps_reported") or 0, d.get("eps_estimate") or 0)
            if d.get("consensus_conflict"):
                text += ", while the earnings calendar's consensus was ${:.2f}; the two figures differ".format(
                    d["consensus_conflict"]["calendar"])
            if d.get("reaction_pct") is not None:
                text += ". The shares moved {} on the day".format(_pct(d["reaction_pct"], 2))
            focus.append(_unit(text + ".", e["id"]))
        else:
            focus.append(_unit("{} shares {} {} on the session of {}.".format(
                e["symbol"], _word(e.get("value")), _pct(e.get("value"), 2), _when(e.get("event_at"))), e["id"]))
    if focus:
        sections.append({"id": "focus", "title": "Companies and sectors in focus", "items": focus[:5]})

    # Market structure and options.
    st = []
    if spy:
        d = spy.get("detail") or {}
        if d.get("vs_sma50_pct") is not None and d.get("vs_sma200_pct") is not None:
            st.append(_unit("On daily bars, SPY closed at {} on {}, {} from its 50-day average and {} from its 200-day.".format(
                d.get("last"), _when(spy.get("event_at")), _pct(d["vs_sma50_pct"], 1), _pct(d["vs_sma200_pct"], 1)), spy["id"]))
        if d.get("high_20d") and d.get("low_20d"):
            st.append(_unit("Its range over the previous 20 sessions runs from {} to {}.".format(d["low_20d"], d["high_20d"]), spy["id"]))
    if vix:
        st.append(_unit("The VIX ended at {:.2f}, {} {:.2f} points from the previous close.".format(
            vix.get("value") or 0, "up" if ((vix.get("compare") or {}).get("change") or 0) >= 0 else "down",
            abs((vix.get("compare") or {}).get("change") or 0)), vix["id"]))
    for i in outline.get("options") or []:
        e = evm.get(i)
        d = (e or {}).get("detail") or {}
        if e and d.get("expiry") and "expected move" in (e.get("label") or ""):
            st.append(_unit("{} options price an expected move of about {:.1f}% either way to the {} expiry: the at-the-money straddle "
                            "as a share of the price, over every day to that expiry, not a forecast.".format(
                                e["symbol"], e.get("value") or 0, _when(d["expiry"])), e["id"]))
            break
    if st:
        sections.append({"id": "structure", "title": "Market structure and options context", "paragraphs": st})

    # What to watch.
    watch = []
    for w in (outline.get("watch") or [])[:5]:
        text = "{}: {}.".format(_when(w.get("when")), w.get("what"))
        if w.get("if_up"):
            text += " " + w["if_up"] + " " + (w.get("if_down") or "")
        watch.append({"when": w.get("when"), "what": w.get("what"), "text": text.strip(), "cites": [w["evidence"]]})
    if watch:
        sections.append({"id": "watch", "title": "What to watch next", "items": watch})

    # Takeaways: a watch plan.
    take = []
    if tension:
        take.append(_unit("{} on {} is the next fact that can confirm or weaken the current read.".format(
            tension["what"], _when(tension["when"])), tension["evidence"]))
    if outline.get("conflicts"):
        take.append(_unit("Treat this week's earnings surprises with care where the consensus figures disagree.",
                          outline["conflicts"][0]["evidence"]))
    if leaders and laggards:
        take.append(_unit("Watch whether leadership in {} and weakness in {} persist beyond a single session.".format(
            leaders[0]["label"], laggards[0]["label"]), leaders[0]["id"], laggards[0]["id"]))
    if tnx:
        take.append(_unit("Yields are the cross-check for any move in growth stocks.", tnx["id"]))
    if len(take) < 3 and spy:
        take.append(_unit("Where the S&P 500 closes against its 20-day range is the simplest read of trend.", spy["id"]))
    sections.append({"id": "takeaways", "title": "Key takeaways", "items": take[:5]})

    summary_bits = [opening[0]["text"]] if opening else []
    if tension:
        summary_bits.append("{} on {} is next.".format(tension["what"], _when(tension["when"])))
    return {
        "headline": head,
        "headline_cites": [c for c in head_cites if c],
        "summary": _unit(" ".join(summary_bits) or head, *(opening[0]["cites"] if opening else []), (tension or {}).get("evidence")),
        "sections": sections,
        "voice": "assembled",
    }


def _number_item(e: Dict[str, Any]) -> Dict[str, Any]:
    d = e.get("detail") or {}
    comp = e.get("compare") or {}
    kind = e.get("kind")
    if kind == "calendar":
        figure = "previous {}".format(comp.get("value")) if comp.get("value") is not None else "due"
        why = "{}: scheduled for {}. {}".format(e.get("label"), _when(e.get("event_at")),
                                               "Its previous reading was {}.".format(comp.get("value")) if comp.get("value") is not None else "")
    elif kind == "earnings":
        figure = "{:+.1f}% EPS surprise (history table)".format(e.get("value") or 0)
        why = "{} reported EPS of ${:.2f} against ${:.2f}{}.".format(
            e.get("symbol"), d.get("eps_reported") or 0, d.get("eps_estimate") or 0,
            "; the calendar's consensus of ${:.2f} differs, so the surprise is unresolved".format(d["consensus_conflict"]["calendar"])
            if d.get("consensus_conflict") else "")
    elif comp.get("change_unit") == "bp":
        figure = "{:.2f}%, {:+.1f}bp".format(e.get("value") or 0, comp.get("change") or 0)
        why = "{} at {:.2f}%, {:+.1f}bp on the day.".format(e.get("label"), e.get("value") or 0, comp.get("change") or 0)
    elif e.get("kind") == "macro":
        figure = "{} {}".format(e.get("value"), e.get("unit") or "")
        why = "{} for the period {}, against {} before.".format(e.get("label"), e.get("period"), comp.get("value"))
    else:
        figure = _pct(e.get("value"), 2)
        typ = d.get("typical_abs_1d")
        why = "{} moved {} on the day{}.".format(
            e.get("label"), _pct(e.get("value"), 2),
            ", against a typical daily move of about {:.1f}% over the previous 20 sessions".format(typ) if typ else "")
    return {"evidence": e["id"], "label": e.get("label"), "figure": figure, "period": e.get("period"),
            "source": e.get("source"), "text": why, "cites": [e["id"]]}
