"""A framework result as a plain-language report (Markdown).

The order follows the brief's rule for every mode: the assessment first, then
the evidence for it, the evidence against it, and what would change it. Every
figure is the service's; this module only words it, and every section says
where its numbers came from.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def _n(x: Any, d: int = 2) -> str:
    try:
        return "{:,.{d}f}".format(float(x), d=d)
    except (TypeError, ValueError):
        return "n/a"


def _bul(items: List[str]) -> str:
    return "\n".join("- " + i for i in items if i) + ("\n" if items else "")


def _src(c: Dict[str, Any]) -> str:
    s = (c.get("sources") or [None])[0]
    if not s:
        return ""
    return " ([{} {} filed {}]({}))".format(s.get("form") or "filing", s.get("period") or "", s.get("filed") or "",
                                            s.get("url") or "")


def long_term(lt: Dict[str, Any]) -> str:
    if not lt or not lt.get("available"):
        return "## Long term\n\n**Insufficient Data.** {}\n".format(((lt or {}).get("conviction") or {}).get("why", ""))
    q, v, conv, ch = lt["quality"], lt["valuation"], lt["conviction"], lt.get("chart") or {}
    out = ["## Long term: {}".format(conv["label"]), "",
           conv.get("why", ""), "",
           "**Business quality: {}.** {}".format(q.get("grade") or "Insufficient Data",
                                               q.get("summary") or q.get("reason") or ""), ""]
    for c in q.get("components") or []:
        if c["status"] == "scored":
            out.append("- {} ({}): {}{}".format(c["label"], c["grade"], c["headline"], _src(c)))
        else:
            out.append("- {}: {} ({})".format(c["label"], "not applicable" if c["status"] == "not_applicable"
                                                else "insufficient data", c.get("reason")))
    r40 = q.get("rule_of_40") or {}
    if r40.get("applies") and r40.get("available"):
        out.append("- Rule of 40: {}".format(r40["text"]))
    out += ["", "**Valuation: {}.** {}".format(v.get("label") or "Insufficient Data", v.get("summary") or v.get("reason") or ""), ""]
    for c in v.get("components") or []:
        out.append("- {}: {}".format(c["label"], c["headline"] if c["status"] == "scored" else
                                     "{} ({})".format("not graded" if c["status"] == "not_applicable" else "no data",
                                                      c.get("reason"))))
    out += ["", "**The chart, as context.** {} {}".format(ch.get("text", ""), (ch.get("volume") or {}).get("text", "")), ""]
    sc = lt.get("scenarios") or {}
    if sc.get("bull") or sc.get("bear"):
        out += ["**Bull case.** {} Model value {}.".format((sc.get("bull") or {}).get("text", ""),
                                                          _n((sc.get("bull") or {}).get("per_share"))),
                "", "**Bear case.** {} Model value {}.".format((sc.get("bear") or {}).get("text", ""),
                                                               _n((sc.get("bear") or {}).get("per_share"))), ""]
    out += ["**Two ways this could lose money over three years.**", "",
            _bul(["{}: {}".format(p["risk"], p["text"]) for p in lt.get("loss_paths") or []])]
    acc = lt.get("accumulation") or {}
    if acc.get("offered"):
        out += ["**Levels to reassess at (conditional).**", "",
                _bul(["{} ({}, {:+.1f}%)".format(_n(z["price"]), z["basis"], z["distance_pct"]) for z in acc["zones"]]),
                acc["condition"], ""]
    else:
        out += ["*{}*".format(acc.get("reason", "")), ""]
    out += ["*{} {}*".format(lt.get("policy_note", ""), lt.get("separation_note", "")), ""]
    return "\n".join(out)


def swing(sw: Dict[str, Any]) -> str:
    if not sw:
        return ""
    out = ["## Swing: {}".format(sw.get("grade")), ""]
    objs = sorted(sw.get("objections") or [], key=lambda o: -o["severity"])
    if sw.get("plan"):
        out += ["**Reasons to skip it first.**", "",
                _bul([o["text"] for o in objs]) if objs else "No specific objection found in the data.\n"]
    out += ["**Grade.** {}".format(sw.get("why", "")), ""]
    for r in sw.get("rules") or []:
        out.append("- Rule applied: {} ({}).".format(r["text"], r["rule"]))
    plan = sw.get("plan")
    rd = sw.get("readings") or {}
    if plan:
        inv = plan["invalidation"]
        sens = plan.get("sensitivity") or {}
        out += ["", "**The plan, conditionally.**", "",
                "- Setup: {} ({}). Entry zone {} to {}, representative entry {}.".format(
                    plan["kind"], plan["side"], _n(plan["entry_zone"][0]), _n(plan["entry_zone"][1]), _n(plan["entry"])),
                "- Confirmation: {}".format(plan["confirmation"]),
                "- Invalidation: {} ({}). {}".format(_n(inv["price"]), inv.get("structure"), inv.get("note")),
                "- Targets: {} ({}).".format(", ".join(_n(t) for t in plan["targets"]), plan["target_basis"]),
                "- Reward to risk: {} by {}; {} to {} across fills, spread and slippage.".format(
                    _n(plan["reward_to_risk"]), plan["rr_formula"], _n(sens.get("low")), _n(sens.get("high"))),
                "- Holding: {}".format((plan.get("holding") or {}).get("basis")),
                "- Earnings: {}".format((plan.get("earnings") or {}).get("text")),
                "- Reassess: {}".format(plan.get("reassess"))]
        se = plan.get("sizing_example") or {}
        if se.get("available"):
            out.append("- Sizing arithmetic ({}): {} shares, about {} at risk at the stop. {}".format(
                se.get("label"), se["shares"], _n(se["planned_loss"], 0), se.get("gap_note", "")))
    elif sw.get("reassess_when"):
        out += ["", "**What would warrant another look.** {}".format(sw["reassess_when"])]
    if rd:
        rs = rd.get("relative_strength") or {}
        out += ["", "**Readings ({}, completed bars).** Daily trend {}, weekly {}{}. 20-day EMA {}, 50-day EMA {}, "
                "200-day {}. RSI {} (the stock against its own recent moves). Relative strength against SPY: {} over "
                "one month, {} over three (the stock against the market). ATR {} ({}% of price), volume {}x its "
                "average.".format(rd.get("as_of"), rd.get("daily_trend"), rd.get("weekly_trend"),
                                  ", aligned" if rd.get("aligned") else ", not aligned", _n(rd.get("ema20")),
                                  _n(rd.get("ema50")), _n(rd.get("sma200")), _n(rd.get("rsi14"), 1),
                                  _signed((rs.get("SPY_1m") or {}).get("excess_pct")),
                                  _signed((rs.get("SPY_3m") or {}).get("excess_pct")), _n(rd.get("atr14")),
                                  _n(rd.get("atr_pct")), _n(rd.get("relative_volume")))]
    out += ["", "*{}*".format(sw.get("framework_note", "")), ""]
    return "\n".join(out)


def _signed(x: Any) -> str:
    try:
        return "{:+.1f} points".format(float(x))
    except (TypeError, ValueError):
        return "n/a"


def pre(p: Dict[str, Any]) -> str:
    if not p or not p.get("available"):
        return "## Before the release\n\n**Insufficient Data.** {}\n".format((p or {}).get("reason", ""))
    rel, cons, view = p["release"], p["consensus"], p["view"]
    preds = p["predictions"]
    out = ["## Before the release ({}, {}, {})".format(rel["date"], rel.get("timing"), rel.get("date_status")), "",
           "**{}**".format(view.get("headline")), "",
           "**The hurdle.** Consensus EPS {} (range {} to {}), revenue {}. {} {}".format(
               _n(cons.get("eps")), _n(cons.get("eps_low")), _n(cons.get("eps_high")),
               _n((cons.get("revenue") or 0) / 1e9) + "bn" if cons.get("revenue") else "n/a",
               cons.get("basis"), cons.get("timestamp_note")), "",
           (p.get("hurdle") or {}).get("text", ""), "",
           _bul([x["text"] for x in (p.get("hurdle") or {}).get("points") or []])]
    for k, label in (("results", "Results"), ("guidance", "Guidance"), ("reaction", "Stock reaction")):
        x = preds[k]
        out += ["**{}: {}** (confidence: {}).".format(label, x["lean"], view["confidence"].get(k)), "",
                _bul([e["text"] for e in x.get("evidence") or []] + (x.get("gaps") or []))]
    o = p.get("options") or {}
    if o.get("available"):
        out += ["**What options are priced for.** {}% to the {} expiry ({} days). {} {}".format(
            _n(o.get("expiry_move_pct"), 1), o.get("expiry"), o.get("dte"), o.get("expiry_move_method"),
            o.get("event_move_method") if o.get("event_isolated") else o.get("event_note")), ""]
        if o.get("range"):
            out += ["Priced range: {} to {} ({}). {}".format(_n(o["range"]["low"]), _n(o["range"]["high"]),
                                                             o["range"]["basis"], o["range"]["note"]), ""]
    else:
        out += ["**Options.** {}".format(o.get("reason", "")), ""]
    news = (p.get("news") or {}).get("stories") or []
    if news:
        out += ["**News since the last report** (one story counted once, labelled by kind):", "",
                _bul(["{} ({}; {}; {} outlet(s))".format(s["title"], s["kind"], s["bears_on"], s["outlet_count"])
                      for s in news[:6]])]
    c = view.get("cases") or {}
    if view.get("figures"):
        out += ["**The arithmetic behind the cases.**", "",
                _bul(["{}: {} ({}; {}).".format(f["label"], f["value"], f["calc"], f["kind"]) for f in view["figures"]])]
    out += ["**Base case.** {}".format(c.get("base")), "", "**Bull case.** {}".format(c.get("bull")), "",
            "**Bear case.** {}".format(c.get("bear")), "", "**What will decide it.**", "", _bul(view.get("deciders") or []),
            "**What would prove the view wrong.**", "", _bul(view.get("invalidators") or []),
            "*{} {}*".format(view.get("thesis_vs_trade", ""), view.get("probabilities_note", "")), "",
            "*Not in the data: {}.*".format(", ".join(p.get("not_available") or [])), ""]
    if p.get("saved"):
        out.append("*Forecast snapshot: {}.*\n".format(
            "saved {}".format(p["saved"].get("created_at")) if p["saved"].get("saved") else p["saved"].get("reason")))
    return "\n".join(out)


def post(p: Dict[str, Any]) -> str:
    if not p or not p.get("available"):
        return "## After the release\n\n**Insufficient Data.** {}\n".format((p or {}).get("reason", ""))
    a, q, rx = p["headline_audit"], p.get("quality") or {}, p.get("reaction") or {}
    eps = a["eps"]
    out = ["## After the release ({})".format(p["release"]["date"]), "",
           "**Report quality: {}.** {}".format(q.get("grade") or "not graded", q.get("note") or q.get("reason") or ""), "",
           "**Headline audit.**", "",
           _bul(["EPS {} against {}: {} ({}{}).".format(_n(eps.get("actual")), _n(eps.get("consensus")), eps.get("state"),
                                                       "{:+.2f}% surprise; ".format(eps["surprise_pct"])
                                                       if eps.get("surprise_pct") is not None else "", eps.get("basis")),
                 eps.get("resolution") or "",
                 " ".join(a.get("pending") or []),
                 "GAAP diluted EPS: {} for {} (SEC).".format(_n((a.get("eps_gaap") or {}).get("value")),
                                                           (a.get("eps_gaap") or {}).get("period_end"))
                 if a.get("eps_gaap") else "",
                 "Revenue: {}.".format((a["revenue"].get("reason") or "").rstrip(".") or "{} ({})".format(
                     _n((a["revenue"].get("actual") or 0) / 1e9) + "bn", a["revenue"].get("state"))),
                 "Guidance: {}".format(a["guidance"].get("reason")), a.get("basis_warning") or "",
                 a.get("reconcile_note")]),
           "**The reaction ({}).** {} {} {}".format(rx.get("observation"), rx.get("text", ""),
                                                    rx.get("timing_inferred") or "", rx.get("caveat", "")), "",
           "**Positives.**", "", _bul(p.get("positives") or ["None found within the reviewed evidence."]),
           "**Weaknesses.**", "", _bul(p.get("weaknesses") or ["None found within the reviewed evidence."]),
           "**Red flags.** {}".format(" ".join(p.get("red_flags") or [])), ""]
    fr = p.get("forecast_review") or {}
    if fr.get("available"):
        out += ["**The saved forecast, reviewed** (saved {}, never edited).".format(fr.get("saved_at")), ""]
        for k, v in (fr.get("scores") or {}).items():
            out.append("- {}: said \"{}\"; {}.".format(k, v.get("said"), "correct" if v.get("correct") else
                                                      "not scored" if v.get("correct") is None else "wrong"))
        out.append("")
    else:
        out += ["*{}*".format(fr.get("reason", "")), ""]
    out += ["**Next quarter.** {} {}".format((p.get("next_quarter") or {}).get("date") or "",
                                             (p.get("next_quarter") or {}).get("watch", "")), "",
            "*{}*".format(p.get("separation_note", "")), ""]
    return "\n".join(out)


def render(out: Dict[str, Any], title: Optional[str] = None) -> str:
    head = ["# {}".format(title or "{}: research framework ({})".format(out.get("ticker"), out.get("mode"))), "",
            "Generated {} with method {} and policy {}. {}".format(
                out.get("generated_at"), out.get("method_version"), (out.get("policy") or {}).get("version"),
                (out.get("freshness") or {}).get("text", "")), ""]
    if out.get("combined"):
        head += ["**Where the assessments land.**", "", _bul(out["combined"]["lines"]),
                 "**Agreement.** {}".format(out["combined"]["verdict"]), ""]
    body = []
    if out.get("long_term"):
        body.append(long_term(out["long_term"]))
    if out.get("swing"):
        body.append(swing(out["swing"]))
    er = out.get("earnings") or {}
    if er.get("pre"):
        body.append(pre(er["pre"]))
    if er.get("post"):
        body.append(post(er["post"]))
    if er and not er.get("pre") and not er.get("post"):
        body.append("## Earnings\n\n**Insufficient Data.** {}\n".format(er.get("reason", "")))
    tail = ["## Sources and limits", "", _bul(["{}: {}".format(k, v) for k, v in (out.get("data") or {}).get(
        "sources", {}).items()]), _bul(out.get("limitations") or [])]
    gaps = (out.get("data") or {}).get("gaps") or []
    if gaps:
        tail.append("Not loaded for this report: {}.".format("; ".join(gaps)))
    return "\n".join(head + body + tail) + "\n"
