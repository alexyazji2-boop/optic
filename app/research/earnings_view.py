"""Earnings analysis: the expectations hurdle before a release, the diagnostic
after it, and the separation the brief insists on between three predictions.

Before a release there are three different questions, answered separately:

1. **Operating results** against expectations (revenue, EPS).
2. **Guidance**: what management says about the next period.
3. **The stock's reaction**, which depends on what was already expected and
   priced, not on whether the company beat.

A predicted beat never becomes a bullish price call on its own: a company that
beats in most quarters is *expected* to beat, so the beat is the base case and
the reaction turns on the size of the beat, the guidance and the run-up.

Confidence is qualitative (low / moderate / high) with the reasons stated.
Numerical probabilities need a validated method, and none exists here yet; the
forecast store (`forecasts.py`) is how one will be earned. After a release, the
saved forecast is compared with the result without rewriting it.

Free data has no guidance text, transcripts or segment estimates, and the feed
does not timestamp individual estimates. Each of those gaps is named in the
output rather than filled in.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from statistics import mean
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

LEANS = ("better than expected", "in line", "worse than expected", "no clear lean")


def _f(x: Any, d: int = 2) -> Optional[float]:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return round(v, d) if np.isfinite(v) else None


def _pct(x: Optional[float], d: int = 1, signed: bool = False) -> str:
    if x is None:
        return "n/a"
    return ("{:+.{d}f}%" if signed else "{:.{d}f}%").format(x, d=d)


# ---------------------------------------------------------------- trajectory

def quarterly_trajectory(sec: Optional[Dict[str, Any]], fin_q: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Revenue and EPS growth against the same quarter a year earlier, and the
    operating margin's year-over-year change. Year-over-year, not sequential,
    so seasonality cancels out."""
    out: Dict[str, Any] = {"available": False}
    rev_yoy: List[Dict[str, Any]] = []
    if sec and sec.get("available"):
        for row in (sec.get("revenue_yoy") or [])[-6:]:
            if row.get("growth_pct") is not None:
                rev_yoy.append({"period_end": row.get("period_end"), "yoy_pct": _f(row["growth_pct"], 1),
                                "available_from": row.get("available_from")})
        out["source"] = sec.get("source")
    if rev_yoy:
        out["available"] = True
        out["revenue_yoy"] = rev_yoy
        vals = [r["yoy_pct"] for r in rev_yoy if r["yoy_pct"] is not None]
        if len(vals) >= 3:
            recent, earlier = vals[-1], mean(vals[-3:-1])
            out["revenue_trend"] = ("accelerating" if recent > earlier + 1.0 else
                                    "decelerating" if recent < earlier - 1.0 else "steady")
            out["revenue_trend_text"] = (
                "Revenue grew {} against the same quarter a year earlier in the latest quarter, against an "
                "average of {} over the two before: {}.".format(_pct(recent, signed=True), _pct(earlier, signed=True),
                                                                out["revenue_trend"]))
    if fin_q and fin_q.get("periods"):
        rows = fin_q.get("rows") or {}
        periods = fin_q["periods"]
        rev = rows.get("Total Revenue") or rows.get("Operating Revenue")
        op = rows.get("Operating Income")
        if rev and op and len(periods) >= 5 and rev[0] and rev[4] and op[0] is not None and op[4] is not None:
            m_now, m_ago = op[0] / rev[0] * 100.0, op[4] / rev[4] * 100.0
            out["available"] = True
            out["operating_margin"] = {"latest_period": periods[0], "latest_pct": _f(m_now, 1),
                                       "year_ago_period": periods[4], "year_ago_pct": _f(m_ago, 1),
                                       "change_pts": _f(m_now - m_ago, 1),
                                       "source": "Yahoo Finance quarterly income statement"}
    return out


# ---------------------------------------------------------------- hurdle

def _run_up(daily: Optional[pd.DataFrame], bench: Optional[pd.DataFrame], n: int = 21) -> Optional[Dict[str, Any]]:
    try:
        c = daily["Close"].astype(float)
        b = bench["Close"].astype(float).reindex(c.index).ffill()
        s = float(c.iloc[-1] / c.iloc[-1 - n] - 1) * 100
        m = float(b.iloc[-1] / b.iloc[-1 - n] - 1) * 100
    except Exception:                                                       # noqa: BLE001
        return None
    return {"stock_pct": _f(s, 1), "spy_pct": _f(m, 1), "excess_pct": _f(s - m, 1), "sessions": n}


def _consensus_growth(nr: Dict[str, Any], sec: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Revenue growth the consensus implies against the same quarter a year
    earlier, from the filed figure. None when either side is missing."""
    cons = nr.get("revenue_consensus")
    if not cons or not sec or not sec.get("available"):
        return None
    quarters = sec.get("revenue_quarters") or []
    if len(quarters) < 4:
        return None
    # The quarter being reported follows the last one filed, so its year-ago
    # quarter ended about 274 days before that filed quarter (one quarter on,
    # a year back). Matched by date, because a filer's series can have holes.
    try:
        last = date.fromisoformat(str(quarters[-1]["period_end"])[:10])
    except (KeyError, ValueError):
        return None
    want = last - timedelta(days=274)
    year_ago = min(quarters, key=lambda q: abs((date.fromisoformat(str(q["period_end"])[:10]) - want).days))
    if abs((date.fromisoformat(str(year_ago["period_end"])[:10]) - want).days) > 20 or not year_ago.get("value"):
        return None
    implied = (float(cons) / float(year_ago["value"]) - 1.0) * 100.0
    return {"implied_yoy_pct": _f(implied, 1), "year_ago_period": year_ago.get("period_end"),
            "year_ago_revenue": year_ago.get("value"), "consensus_revenue": cons}


def expectations_hurdle(ea: Dict[str, Any], traj: Dict[str, Any], sec: Optional[Dict[str, Any]],
                        run_up: Optional[Dict[str, Any]], val_hist: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Whether expectations look demanding or conservative, from evidence
    points that each push one way, listed. Insufficient below two points."""
    nr = ea.get("next_report") or {}
    sur = ea.get("surprise") or {}
    rev = ea.get("revisions") or {}
    points: List[Dict[str, Any]] = []

    def add(push: int, text: str, kind: str) -> None:
        points.append({"push": push, "text": text, "kind": kind})

    if run_up and run_up.get("excess_pct") is not None:
        x = run_up["excess_pct"]
        if x >= 5:
            add(1, "The stock is {} the S&P 500 over the last month ({} against {}): good news is partly "
                   "in the price.".format(_pct(x, signed=True) + " ahead of", _pct(run_up["stock_pct"], signed=True),
                                          _pct(run_up["spy_pct"], signed=True)), "run_up")
        elif x <= -5:
            add(-1, "The stock has trailed the S&P 500 by {} over the last month: some disappointment is "
                    "already priced.".format(_pct(abs(x))), "run_up")
    pct = (val_hist or {}).get("percentile")
    if pct is not None:
        p = pct / 100.0 if pct > 1 else pct
        if p >= 0.8:
            add(1, "The P/E is in the top fifth of its five-year range: the multiple assumes things keep going "
                   "well.", "valuation")
        elif p <= 0.2:
            add(-1, "The P/E is in the bottom fifth of its five-year range: the multiple assumes little.",
                "valuation")
    if rev.get("direction") == "rising":
        add(1, "Analysts raised full-year estimates {} over 90 days: the bar has moved up.".format(
            _pct(rev.get("drift_90d_pct"), signed=True)), "revisions")
    elif rev.get("direction") == "falling":
        add(-1, "Analysts cut full-year estimates {} over 90 days: the bar has come down.".format(
            _pct(rev.get("drift_90d_pct"), signed=True)), "revisions")
    br = sur.get("beat_rate_pct")
    if br is not None and (sur.get("quarters") or 0) >= 4:
        if br >= 75:
            add(1, "The company beat EPS consensus in {:.0f}% of the last {} quarters, so a beat is the base "
                   "case, not news.".format(br, sur.get("quarters")), "beat_rate")
        elif br <= 40:
            add(-1, "The company beat in only {:.0f}% of the last {} quarters: a beat would be a surprise.".format(
                br, sur.get("quarters")), "beat_rate")
    cg = _consensus_growth(nr, sec)
    recent = None
    vals = [r["yoy_pct"] for r in (traj.get("revenue_yoy") or []) if r.get("yoy_pct") is not None]
    if vals:
        recent = vals[-1]
    if cg and recent is not None:
        gap = cg["implied_yoy_pct"] - recent
        if gap >= 2:
            add(1, "Consensus revenue implies {} growth on the year-ago quarter, faster than the {} just "
                   "reported: the forecast needs acceleration.".format(_pct(cg["implied_yoy_pct"], signed=True),
                                                                        _pct(recent, signed=True)), "implied_growth")
        elif gap <= -3:
            add(-1, "Consensus revenue implies {} growth on the year-ago quarter, slower than the {} just "
                    "reported: the forecast already assumes a slowdown.".format(
                        _pct(cg["implied_yoy_pct"], signed=True), _pct(recent, signed=True)), "implied_growth")
    if len(points) < 2:
        state, text = "insufficient", ("Fewer than two pieces of evidence on how demanding expectations are, so "
                                       "no call is made either way.")
    else:
        total = sum(p["push"] for p in points)
        state = "demanding" if total >= 2 else "conservative" if total <= -2 else "balanced"
        ups, downs = sum(1 for p in points if p["push"] > 0), sum(1 for p in points if p["push"] < 0)
        text = {"demanding": "Expectations look demanding: {} of {} signals point to a high bar.".format(ups, len(points)),
                "conservative": "Expectations look conservative: {} of {} signals point to a low bar.".format(
                    downs, len(points)),
                "balanced": "Expectations look balanced: {} signals point to a high bar and {} to a low one.".format(
                    ups, downs)}[state]
    return {"state": state, "text": text, "points": points, "consensus_growth": cg,
            "whisper_note": "No whisper number or positioning data is used: neither is in Optic's data, and a "
                            "number without a source would be invented."}


# ---------------------------------------------------------------- news

_RUMOR = ("reportedly", "sources say", "people familiar", "rumor", "rumour", "speculat", "could be", "considering")
_ANALYST = ("upgrade", "downgrade", "price target", "initiat", "reiterat", "overweight", "underweight",
            "outperform", "analyst")
_OFFICIAL = ("announces", "reports", "files", "8-k", "press release", "declares", "sec filing")
_OUTLOOK = ("guidance", "outlook", "forecast", "contract", "order", "deal", "acquisi", "launch", "approval",
            "recall", "layoff", "lawsuit", "tariff", "investigation", "price increase", "pricing")


def _tokens(text: str) -> set:
    return {w for w in "".join(ch.lower() if ch.isalnum() else " " for ch in (text or "")).split() if len(w) > 3}


def news_since(news: Optional[Dict[str, Any]], since: Optional[str]) -> Dict[str, Any]:
    """Headlines since the previous report, grouped so a story repeated by
    several outlets counts once, and labelled by what kind of claim it is.

    The labels are a word-list heuristic, stated as one: they sort the list for
    reading, they do not establish that a headline changed the outlook."""
    arts = [a for a in ((news or {}).get("articles") or []) if a.get("about_company")]
    if since:
        try:
            cut = pd.Timestamp(since).tz_localize("UTC") if pd.Timestamp(since).tzinfo is None else pd.Timestamp(since)
            arts = [a for a in arts if not a.get("published") or pd.Timestamp(a["published"]) >= cut]
        except (ValueError, TypeError):
            pass
    stories: List[Dict[str, Any]] = []
    for a in arts:
        tok = _tokens(a.get("title") or "")
        hit = None
        for s in stories:
            inter = len(tok & s["_tok"])
            union = len(tok | s["_tok"]) or 1
            if inter / union >= 0.5:
                hit = s
                break
        if hit:
            hit["outlets"].append(a.get("publisher"))
            continue
        t = (a.get("title") or "").lower()
        kind = ("rumour or unconfirmed" if any(w in t for w in _RUMOR) else
                "analyst opinion" if any(w in t for w in _ANALYST) else
                "company announcement" if any(w in t for w in _OFFICIAL) else "reporting")
        bears = ("could affect the financial outlook" if any(w in t for w in _OUTLOOK) else
                 "valuation narrative" if kind == "analyst opinion" else "neither, on its face")
        stories.append({"title": a.get("title"), "publisher": a.get("publisher"), "published": a.get("published"),
                        "url": a.get("url"), "kind": kind, "bears_on": bears, "outlets": [a.get("publisher")],
                        "catalysts": [c.get("type") for c in (a.get("catalysts") or []) if isinstance(c, dict)],
                        "_tok": tok})
    for s in stories:
        s.pop("_tok", None)
        s["outlet_count"] = len({o for o in s["outlets"] if o})
    return {"stories": stories[:10], "count": len(stories), "since": since,
            "note": ("Grouped so one story carried by several outlets counts once. The kind and 'bears on' "
                     "labels are a word-list sort for reading, not a finding that the story changes anything.")}


# ---------------------------------------------------------------- options

def options_read(ea: Dict[str, Any], vol_event: Optional[Dict[str, Any]], spot: Optional[float]) -> Dict[str, Any]:
    imp = ea.get("implied") or {}
    pr = ea.get("pricing") or {}
    out: Dict[str, Any] = {"available": bool(imp.get("available"))}
    if not imp.get("available"):
        out["reason"] = imp.get("reason") or "No event-spanning straddle could be read."
        return out
    move = imp.get("implied_move_pct")
    out.update({
        "expiry": imp.get("expiry"), "dte": imp.get("dte"), "straddle": imp.get("straddle_cost"),
        "strike": imp.get("strike"), "atm_iv_pct": imp.get("atm_iv_pct"),
        "expiry_move_pct": move,
        "expiry_move_method": ("At-the-money straddle on the first expiry after the release, divided by the "
                               "price: the breakeven move to that expiry ({} days). It covers every day to "
                               "expiry, not the release alone.".format(imp.get("dte"))),
        "pricing_vs_history": {"stance": pr.get("stance"), "ratio": pr.get("ratio"),
                               "baseline_pct": pr.get("baseline_move_pct"), "baseline_kind": pr.get("baseline_kind"),
                               "note": pr.get("note")} if pr.get("available") else None,
    })
    if vol_event and vol_event.get("available") and vol_event.get("move_pct") is not None:
        out["event_move_pct"] = vol_event["move_pct"]
        out["event_move_method"] = vol_event.get("method")
        out["event_isolated"] = True
    else:
        out["event_isolated"] = False
        out["event_note"] = ("The release's own move is not isolated (needs a quoted expiry on each side of the "
                             "report), so the figure above is the whole expiry's move, not an earnings-only one.")
    m = out.get("event_move_pct") or move
    if spot and m:
        out["range"] = {"low": _f(spot * (1 - m / 100.0)), "high": _f(spot * (1 + m / 100.0)), "move_pct": m,
                        "basis": "event-isolated move" if out["event_isolated"] else "straddle breakeven to expiry",
                        "note": "What options are priced for, one way or the other. Not a forecast, not a limit: "
                                "moves beyond it happen, and the direction is not priced."}
    out["caveats"] = [
        "Implied volatility usually collapses once the result is out, so an option bought for the release loses "
        "value even when the stock moves the expected amount in the expected direction.",
        "Unusual options volume is a reason to look closer, not evidence of an informed bet: it can be a hedge, "
        "one leg of a spread, a roll or a closing trade, and free data cannot tell which side was the buyer.",
    ]
    return out


# ---------------------------------------------------------------- predictions

def _confidence(agree: int, total: int, gaps: int) -> str:
    if total == 0:
        return "insufficient"
    share = agree / total
    if total >= 3 and share >= 0.75 and gaps == 0:
        return "moderate"
    if share >= 0.67 and total >= 2:
        return "low to moderate"
    return "low"


def basis_warning(sur: Dict[str, Any], industry: Optional[str]) -> Optional[str]:
    """A consensus on one basis against results on another reads as a miss (or
    a beat) every single quarter by a similar amount. Realty Income "missed" 8
    of 8 by about 22% on 2026-10-14: REIT estimates are usually funds from
    operations while the feed's reported figure is GAAP earnings."""
    rows = [r for r in (sur.get("rows") or []) if r.get("surprise_pct") is not None]
    reit = "reit" in (industry or "").lower()
    if len(rows) >= 6:
        signs = {1 if r["surprise_pct"] > 0 else -1 for r in rows}
        avg = abs(mean(r["surprise_pct"] for r in rows))
        if len(signs) == 1 and avg >= 10:
            return ("Every one of the last {} quarters {} consensus, by {} on average. A pattern that uniform "
                    "usually means the estimate and the reported figure are on different bases{}, not {} "
                    "results.".format(len(rows), "beat" if signs == {1} else "missed", _pct(avg),
                                      " (REIT estimates are typically funds from operations; the reported figure "
                                      "here is GAAP earnings)" if reit else "",
                                      "consistently strong" if signs == {1} else "consistently weak"))
    if reit:
        return ("REIT consensus is usually on funds from operations (FFO) while the feed's reported figure is GAAP "
                "earnings, so beat and miss here may compare different things.")
    return None


def predict_results(ea: Dict[str, Any], traj: Dict[str, Any], hurdle: Dict[str, Any],
                    industry: Optional[str] = None) -> Dict[str, Any]:
    sur = ea.get("surprise") or {}
    basis = basis_warning(sur, industry)
    if basis and len([r for r in (sur.get("rows") or []) if r.get("surprise_pct") is not None]) >= 6 and \
            "Every one" in basis:
        return {"lean": "no clear lean", "confidence": "insufficient", "evidence": [], "gaps": [basis],
                "basis_warning": basis,
                "text": "No call on the results: the surprise record looks like a basis mismatch, so it cannot "
                        "anchor a forecast."}
    rev = ea.get("revisions") or {}
    nr = ea.get("next_report") or {}
    ev: List[Tuple[int, str]] = []
    br, avg = sur.get("beat_rate_pct"), sur.get("avg_surprise_pct")
    if br is not None and (sur.get("quarters") or 0) >= 4:
        ev.append((1 if br >= 70 else -1 if br <= 40 else 0,
                   "Beat EPS consensus in {:.0f}% of {} quarters, by {} on average.".format(
                       br, sur.get("quarters"), _pct(avg, signed=True))))
    if rev.get("direction") in ("rising", "falling"):
        ev.append((1 if rev["direction"] == "rising" else -1,
                   "Estimates are {} into the release ({} over 90 days), which tends to {}.".format(
                       rev["direction"], _pct(rev.get("drift_90d_pct"), signed=True),
                       "precede results above them" if rev["direction"] == "rising" else
                       "reflect a softening the company has signalled")))
    cg = hurdle.get("consensus_growth")
    vals = [r["yoy_pct"] for r in (traj.get("revenue_yoy") or []) if r.get("yoy_pct") is not None]
    if cg and vals:
        gap = cg["implied_yoy_pct"] - vals[-1]
        ev.append((1 if gap <= -3 else -1 if gap >= 3 else 0,
                   "Consensus revenue implies {} growth against {} last quarter.".format(
                       _pct(cg["implied_yoy_pct"], signed=True), _pct(vals[-1], signed=True))))
    if traj.get("revenue_trend") in ("accelerating", "decelerating"):
        ev.append((1 if traj["revenue_trend"] == "accelerating" else -1, traj.get("revenue_trend_text") or ""))
    gaps = []
    if not nr.get("eps_consensus"):
        gaps.append("No EPS consensus in the feed.")
    if not nr.get("revenue_consensus"):
        gaps.append("No revenue consensus in the feed.")
    if not ev:
        return {"lean": "no clear lean", "confidence": "insufficient", "evidence": [], "gaps": gaps,
                "text": "Not enough evidence to lean either way on the results."}
    score = sum(e[0] for e in ev)
    lean = "better than expected" if score >= 2 else "worse than expected" if score <= -2 else (
        "modestly better than expected" if score == 1 else "modestly worse than expected" if score == -1 else "in line")
    agree = sum(1 for e in ev if (e[0] > 0) == (score > 0) and e[0] != 0) if score else sum(1 for e in ev if e[0] == 0)
    disp = nr.get("eps_dispersion_pct")
    conf = _confidence(agree, len(ev), len(gaps))
    if disp is not None and disp > 25 and conf != "low":
        conf = "low"
    if basis:
        gaps.append(basis)
        conf = "low"
    return {"lean": lean, "confidence": conf, "score": score, "basis_warning": basis,
            "evidence": [{"push": p, "text": t} for p, t in ev], "gaps": gaps,
            "text": "Results lean {} on {} of {} signals.".format(lean, agree, len(ev))}


def predict_guidance(ea: Dict[str, Any], traj: Dict[str, Any]) -> Dict[str, Any]:
    rev = ea.get("revisions") or {}
    rows = {r["period"]: r for r in (rev.get("rows") or [])}
    nq = rows.get("+1q") or {}
    ev: List[Tuple[int, str]] = []
    if nq.get("chg_30d_pct") is not None and abs(nq["chg_30d_pct"]) >= 1:
        ev.append((1 if nq["chg_30d_pct"] > 0 else -1,
                   "Next-quarter EPS estimates moved {} in 30 days to {:.2f}: analysts expect the outlook to "
                   "{}.".format(_pct(nq["chg_30d_pct"], signed=True), nq.get("current") or 0,
                                "improve" if nq["chg_30d_pct"] > 0 else "soften")))
    om = traj.get("operating_margin") or {}
    if om.get("change_pts") is not None and abs(om["change_pts"]) >= 1:
        ev.append((1 if om["change_pts"] > 0 else -1,
                   "Operating margin was {} points {} a year earlier last quarter, which management usually "
                   "addresses in the outlook.".format(_f(abs(om["change_pts"]), 1),
                                                     "above" if om["change_pts"] > 0 else "below")))
    gap = ("Company guidance text is not in Optic's data. What management said last quarter, and whether it "
           "beat its own guide, is in the prior release and call transcript (investor relations).")
    if not ev:
        return {"lean": "no clear lean", "confidence": "insufficient", "evidence": [], "gaps": [gap],
                "text": "No basis in the data for a guidance call; the outcome is genuinely open.",
                "next_quarter_consensus": nq.get("current")}
    score = sum(e[0] for e in ev)
    lean = ("likely to support estimates" if score > 0 else "at risk of disappointing" if score < 0 else "no clear lean")
    return {"lean": lean, "confidence": "low", "evidence": [{"push": p, "text": t} for p, t in ev], "gaps": [gap],
            "text": "Guidance is the least observable of the three: the lean rests on analyst revisions and margins, "
                    "not on anything management has said.",
            "next_quarter_consensus": nq.get("current")}


def predict_reaction(ea: Dict[str, Any], hurdle: Dict[str, Any], results: Dict[str, Any],
                     opts: Dict[str, Any], bench_state: Optional[str]) -> Dict[str, Any]:
    sur = ea.get("surprise") or {}
    ev: List[Tuple[int, str]] = []
    h = hurdle.get("state")
    if h == "demanding":
        ev.append((-1, "With a demanding bar, a beat in line with the company's history may not be enough."))
    elif h == "conservative":
        ev.append((1, "With a low bar, an ordinary result could be enough to lift the stock."))
    on_beat, on_miss = sur.get("avg_move_on_beat_pct"), sur.get("avg_move_on_miss_pct")
    if on_beat is not None and (sur.get("beat_rate_pct") or 0) >= 70:
        ev.append((1 if on_beat > 0.5 else -1 if on_beat < -0.5 else 0,
                   "After past beats the stock moved {} on average in the reacting session.".format(
                       _pct(on_beat, signed=True))))
    if bench_state in ("risk-off",):
        ev.append((-1, "The market is below its 50- and 200-day averages, which tends to make reactions to "
                       "good news smaller and to bad news larger."))
    elif bench_state == "risk-on":
        ev.append((0, "The market backdrop is supportive (SPY above its 50- and 200-day averages)."))
    if results.get("lean", "").startswith(("better", "modestly better")) and h == "demanding":
        ev.append((0, "A likely beat and a demanding bar point in opposite directions for the price."))
    score = sum(e[0] for e in ev)
    lean = ("skewed up" if score >= 2 else "skewed down" if score <= -2 else "two-sided")
    mv = (opts.get("range") or {}).get("move_pct")
    size = ("Options price about {} either way ({}).".format(_pct(mv), (opts.get("range") or {}).get("basis"))
            if mv else "No options-implied move is available for size.")
    return {"lean": lean, "confidence": "low", "evidence": [{"push": p, "text": t} for p, t in ev],
            "size": size,
            "text": "The reaction is the hardest of the three to call: it depends on what was already expected "
                    "and priced, so even a correct read on the results says little about the direction.",
            "reasons_beat_is_not_bullish": "A beat is only bullish if it is larger than what the price and the "
                                           "options already assume, and if guidance does not undercut it."}


def best_view(ticker: str, results: Dict[str, Any], guidance: Dict[str, Any], reaction: Dict[str, Any],
              hurdle: Dict[str, Any], opts: Dict[str, Any], nr: Dict[str, Any], spot: Optional[float],
              sur: Dict[str, Any]) -> Dict[str, Any]:
    if results["confidence"] == "insufficient" and hurdle.get("state") == "insufficient":
        return {"headline": "There is not enough evidence for a pre-earnings view on ${}: no consensus, history "
                            "or revisions to anchor one.".format(ticker), "insufficient": True}
    because = []
    for block in (results, hurdle):
        for p in (block.get("evidence") or block.get("points") or [])[:2]:
            if p.get("push"):
                because.append(p["text"].rstrip("."))
    because = because[:2]
    r_phrase = ("results {}".format(results["lean"]) if results["lean"] != "no clear lean"
                else "results with no clear lean against expectations")
    g_phrase = ("guidance is {}".format(guidance["lean"]) if guidance["lean"] != "no clear lean"
                else "guidance is an open question")
    head = ("My best-supported pre-earnings view is that ${} reports {}, {}, and the reaction is {}{}.".format(
                ticker, r_phrase, g_phrase, reaction["lean"],
                ", because " + "; and ".join(b[0].lower() + b[1:] for b in because) if because else ""))
    rng = opts.get("range") or {}
    cases = {
        "base": "Results {}; guidance {}; a move inside the {} priced either way{}.".format(
            results["lean"], guidance["lean"] if guidance["lean"] != "no clear lean" else "roughly in line",
            _pct(rng.get("move_pct")) if rng else "move options price",
            " ({:.2f} to {:.2f})".format(rng["low"], rng["high"]) if rng else ""),
        "bull": "A clear beat on revenue and EPS plus guidance above the next-quarter consensus{}: the move "
                "could exceed the priced range on the upside.".format(
                    " ({:.2f})".format(guidance["next_quarter_consensus"]) if guidance.get("next_quarter_consensus") else ""),
        "bear": "A beat that is smaller than usual (the average beat is {}) or a guide below consensus: with "
                "expectations {}, the stock could fall even on a headline beat.".format(
                    _pct(sur.get("avg_surprise_pct"), signed=True), hurdle.get("state")),
    }
    # Transparent arithmetic, not a forecast: what the consensus becomes if
    # the company's average surprise repeats, and the growth the revenue
    # consensus already assumes. Shown with their inputs so a reader can redo them.
    figures: List[Dict[str, Any]] = []
    eps_c, avg_s = nr.get("eps_consensus"), sur.get("avg_surprise_pct")
    if eps_c is not None and avg_s is not None and (sur.get("quarters") or 0) >= 4:
        figures.append({"label": "EPS if the average surprise repeats",
                        "value": _f(eps_c * (1 + avg_s / 100.0) if eps_c >= 0 else eps_c + abs(eps_c) * avg_s / 100.0),
                        "calc": "consensus {:.2f} adjusted by the {} average surprise over {} quarters".format(
                            eps_c, _pct(avg_s, signed=True), sur.get("quarters")),
                        "kind": "calculated from the record, not a forecast"})
    cg = hurdle.get("consensus_growth")
    if cg:
        figures.append({"label": "Revenue growth the consensus implies",
                        "value": cg["implied_yoy_pct"],
                        "calc": "consensus {:.2f}bn against {:.2f}bn in the quarter to {}".format(
                            cg["consensus_revenue"] / 1e9, cg["year_ago_revenue"] / 1e9, cg["year_ago_period"]),
                        "kind": "calculated"})
    deciders = ["Revenue against the {} consensus{}".format(
                    nr.get("revenue_consensus_label") or "revenue",
                    " (implying {} growth on the year-ago quarter)".format(
                        _pct((hurdle.get("consensus_growth") or {}).get("implied_yoy_pct"), signed=True))
                    if hurdle.get("consensus_growth") else ""),
                "EPS against {:.2f}".format(nr["eps_consensus"]) if nr.get("eps_consensus") else "EPS against consensus",
                "Next-quarter guidance against the {} consensus".format(
                    "{:.2f}".format(guidance["next_quarter_consensus"]) if guidance.get("next_quarter_consensus")
                    else "next-quarter"),
                "The segment or operating metric the growth story rests on (not in Optic's structured data; "
                "in the release)"]
    invalidators = []
    if sur.get("avg_surprise_pct") is not None:
        invalidators.append("An EPS surprise below zero, against an average of {}.".format(
            _pct(sur["avg_surprise_pct"], signed=True)))
    invalidators.append("Guidance below the next-quarter consensus.")
    if rng:
        invalidators.append("A first reaction beyond {:.2f} or {:.2f}, the edge of the priced move, against the "
                            "lean.".format(rng["low"], rng["high"]))
    return {"headline": head, "cases": cases, "figures": figures, "deciders": deciders, "invalidators": invalidators,
            "confidence": {"results": results["confidence"], "guidance": guidance["confidence"],
                           "reaction": reaction["confidence"]},
            "probabilities": None,
            "probabilities_note": "No probabilities: the forecasts have not been scored against outcomes yet, "
                                  "so a percentage would claim a calibration the method does not have.",
            "thesis_vs_trade": ("Being right about direction is not the same as an options trade making money. A "
                                "bought option pays for the expected move ({}) up front and loses value when "
                                "volatility drops after the release, so it needs a move larger than that, in the "
                                "right direction, before expiry.".format(_pct(rng.get("move_pct")) if rng else
                                                                          "the priced move"))}


def _year_ago(rows: List[Dict[str, Any]], row: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """The quarter about a year before `row`, matched by period end (within 20
    days), because filed series have holes and an index four back can be a
    different quarter."""
    try:
        want = date.fromisoformat(str(row["period_end"])[:10]) - timedelta(days=364)
    except (KeyError, ValueError):
        return None
    best = None
    for r in rows:
        try:
            gap = abs((date.fromisoformat(str(r["period_end"])[:10]) - want).days)
        except (KeyError, ValueError):
            continue
        if gap <= 20 and (best is None or gap < best[0]):
            best = (gap, r)
    return best[1] if best else None


def release_cutoff(report_date: Optional[str], timing: Optional[str]) -> Optional[str]:
    """The last moment a forecast can be called genuinely pre-release, in UTC.

    Before the open: 07:00 ET on the day (most pre-market releases land 06:00
    to 08:00, so 07:00 is not conservative enough; 06:00 is used). After the
    close: 16:00 ET. Unknown: midnight ET at the start of the day, the
    earliest the release could be."""
    if not report_date:
        return None
    from zoneinfo import ZoneInfo
    et = ZoneInfo("America/New_York")
    try:
        d = date.fromisoformat(str(report_date)[:10])
    except ValueError:
        return None
    hour = 6 if timing == "before_open" else 16 if timing == "after_close" else 0
    return datetime(d.year, d.month, d.day, hour, 0, tzinfo=et).astimezone(timezone.utc).isoformat()


def pre_earnings(ticker: str, ea: Dict[str, Any], *, sec: Optional[Dict[str, Any]] = None,
                 fin_q: Optional[Dict[str, Any]] = None, daily: Optional[pd.DataFrame] = None,
                 bench: Optional[pd.DataFrame] = None, val_hist: Optional[Dict[str, Any]] = None,
                 vol_event: Optional[Dict[str, Any]] = None, news: Optional[Dict[str, Any]] = None,
                 bench_state: Optional[str] = None, spot: Optional[float] = None,
                 industry: Optional[str] = None) -> Dict[str, Any]:
    if not ea or ea.get("not_applicable"):
        return {"available": False, "reason": (ea or {}).get("reason") or "No earnings data."}
    nr = ea.get("next_report") or {}
    if not nr.get("date"):
        return {"available": False, "reason": "No upcoming release date in the feed, so there is nothing to "
                                               "forecast yet. Check the company's investor-relations calendar."}
    traj = quarterly_trajectory(sec, fin_q)
    run = _run_up(daily, bench) if daily is not None and bench is not None else None
    hurdle = expectations_hurdle(ea, traj, sec, run, val_hist)
    opts = options_read(ea, vol_event, spot or ea.get("spot"))
    res = predict_results(ea, traj, hurdle, industry)
    gd = predict_guidance(ea, traj)
    rx = predict_reaction(ea, hurdle, res, opts, bench_state)
    last = (ea.get("latest_result") or {}).get("date")
    view = best_view(ticker, res, gd, rx, hurdle, opts, nr, spot or ea.get("spot"), ea.get("surprise") or {})
    release = {
        "date": nr.get("date"), "timing": nr.get("timing") or "unknown", "days_away": nr.get("days_away"),
        "confirmed": nr.get("confirmed"),
        "date_status": ("confirmed" if nr.get("confirmed") else "estimated (not confirmed by the company)"),
        "cutoff_utc": release_cutoff(nr.get("date"), nr.get("timing")),
        "period": _period_after((sec or {}).get("revenue_quarters")),
    }
    consensus = {
        "eps": nr.get("eps_consensus"), "eps_low": nr.get("eps_low"), "eps_high": nr.get("eps_high"),
        "revenue": nr.get("revenue_consensus"), "revenue_low": nr.get("revenue_low"),
        "revenue_high": nr.get("revenue_high"), "dispersion_pct": nr.get("eps_dispersion_pct"),
        "basis": "Analyst consensus (Yahoo Finance), adjusted EPS as the Street reports it; company guidance is a "
                 "different thing and is not in this data.",
        "retrieved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "timestamp_note": "The feed does not timestamp individual estimates; revisions over 7, 30 and 90 days come "
                          "from its estimate-trend table.",
    }
    return {"available": True, "mode": "pre_earnings", "release": release, "consensus": consensus,
            "revisions": ea.get("revisions"), "surprise_history": {k: (ea.get("surprise") or {}).get(k) for k in (
                "quarters", "beat_rate_pct", "avg_surprise_pct", "avg_abs_move_pct", "avg_move_on_beat_pct",
                "avg_move_on_miss_pct")},
            "trajectory": traj, "run_up": run, "hurdle": hurdle, "options": opts,
            "news": news_since(news, last),
            "predictions": {"results": res, "guidance": gd, "reaction": rx},
            "view": view,
            "not_available": ["company guidance text", "call transcripts", "segment and operating-metric "
                              "consensus", "whisper numbers", "investor positioning"]}


def _period_after(quarters: Optional[List[Dict[str, Any]]]) -> Optional[str]:
    if not quarters:
        return None
    try:
        last = date.fromisoformat(str(quarters[-1]["period_end"])[:10])
    except (KeyError, ValueError):
        return None
    nxt = last + timedelta(days=91)
    return "the quarter ending about {}".format(nxt.isoformat()[:7])


# ---------------------------------------------------------------- post

def classify_vs(actual: Optional[float], expected: Optional[float], band_pct: float) -> Dict[str, Any]:
    if actual is None or expected is None:
        return {"state": "unknown"}
    if expected == 0:
        diff = actual - expected
        return {"state": "beat" if diff > 0 else "miss" if diff < 0 else "in line", "surprise_pct": None}
    s = (actual - expected) / abs(expected) * 100.0
    state = "in line" if abs(s) <= band_pct else "beat" if s > 0 else "miss"
    return {"state": state, "surprise_pct": _f(s, 2)}


def reaction(daily: Optional[pd.DataFrame], bench: Optional[pd.DataFrame], release_day: str,
             timing: Optional[str], quote: Optional[Dict[str, Any]], phase: Optional[str],
             today: Optional[date] = None) -> Dict[str, Any]:
    """The first reaction session: gap, continuation or fade, relative volume,
    against SPY, and which kind of observation it is."""
    today = today or datetime.now(timezone.utc).date()
    out: Dict[str, Any] = {"available": False}
    if daily is None or daily.empty:
        return out
    try:
        rd = date.fromisoformat(str(release_day)[:10])
    except ValueError:
        return out
    idx = [d.date() for d in daily.index]
    react_day = rd if timing == "before_open" else None
    inferred = None
    if react_day is None:
        later = [d for d in idx if d > rd]
        react_day = later[0] if later else None
        # Timing unknown: the release day or the session after it. The
        # reaction session is the one carrying the volume spike, which is an
        # observation rather than a guess about the clock. JPM, 2026-10-14:
        # no timing in the feed, a before-the-open bank, and the default read
        # the day after as the reaction.
        if timing not in ("after_close",) and react_day is not None and rd in idx:
            vol = daily["Volume"].astype(float)

            def rvol(day: date) -> Optional[float]:
                i = idx.index(day)
                base = float(vol.iloc[max(0, i - 21):i - 1].mean()) if i > 2 else 0.0
                return float(vol.iloc[i]) / base if base else None

            a, b = rvol(rd), rvol(react_day)
            if a is not None and b is not None:
                # The later session may still be trading: compare it on a full
                # day's footing only when it is complete.
                partial = react_day == today and phase == "regular"
                if a >= b or partial and a >= 1.3:
                    inferred = ("The release time is not in the feed; the release day carried the heavier volume "
                                "({:.1f}x against {:.1f}x), so it is read as the reaction session.".format(a, b))
                    react_day = rd
                else:
                    inferred = ("The release time is not in the feed; the next session carried the heavier volume "
                                "({:.1f}x against {:.1f}x), so it is read as the reaction session.".format(b, a))
    if react_day is None or react_day not in idx:
        q = quote or {}
        ext = q.get("post_market_change_pct") if q.get("post_market_change_pct") is not None else q.get("pre_market_change_pct")
        if ext is not None:
            return {"available": True, "observation": "after-hours", "move_pct": _f(ext, 2),
                    "text": "Only an extended-hours move so far ({}), on thin volume; the first regular session "
                            "has not traded.".format(_pct(ext, 2, True))}
        return {"available": False, "observation": "pending", "text": "The reaction session has not traded yet."}
    i = idx.index(react_day)
    if i == 0:
        return out
    row, prev = daily.iloc[i], daily.iloc[i - 1]
    pc = float(prev["Close"])
    gap = (float(row["Open"]) / pc - 1) * 100
    day = (float(row["Close"]) / pc - 1) * 100
    cont = (float(row["Close"]) / float(row["Open"]) - 1) * 100
    vol = daily["Volume"].astype(float)
    avg = float(vol.iloc[max(0, i - 21):i - 1].mean()) if i > 2 else None
    rvol = float(row["Volume"]) / avg if avg else None
    spy_day = None
    if bench is not None and not bench.empty:
        b = bench["Close"].astype(float)
        bi = [d.date() for d in b.index]
        if react_day in bi and bi.index(react_day) > 0:
            j = bi.index(react_day)
            spy_day = (float(b.iloc[j]) / float(b.iloc[j - 1]) - 1) * 100
    in_progress = react_day == today and phase == "regular"
    after = None
    if i + 1 < len(daily):
        after = (float(daily["Close"].iloc[min(i + 3, len(daily) - 1)]) / float(row["Close"]) - 1) * 100
    if abs(gap) < 0.5:
        held = "no meaningful gap"
    elif gap * day < 0:
        held = "reversed"          # closed (or trades) on the other side of the prior close
    elif gap * cont < 0 and abs(cont) > abs(gap) * 0.5:
        held = "faded"             # gave back more than half the gap
    elif gap * cont > 0:
        held = "extended"
    else:
        held = "held"
    return {"available": True, "reaction_day": react_day.isoformat(), "timing_inferred": inferred,
            "observation": "intraday, session in progress" if in_progress else "completed session",
            "gap_pct": _f(gap, 2), "day_pct": _f(day, 2), "open_to_close_pct": _f(cont, 2),
            "relative_volume": _f(rvol, 2), "spy_day_pct": _f(spy_day, 2),
            "excess_vs_spy_pct": _f(day - spy_day, 2) if spy_day is not None else None,
            "gap_behaviour": held, "next_three_sessions_pct": _f(after, 2),
            "text": "{} {} at the open; {}{} ({} on the day, {} versus SPY), on {}x average volume{}{}.".format(
                        "Gapped" if abs(gap) >= 0.5 else "Opened", _pct(gap, 1, True),
                        {"reversed": "the gap has reversed", "faded": "the gap faded",
                         "extended": "the move extended", "held": "the gap held",
                         "no meaningful gap": "little gap to speak of"}[held],
                        " so far" if in_progress else "", _pct(day, 1, True),
                        _pct(day - spy_day, 1, True) if spy_day is not None else "n/a",
                        _f(rvol, 1) if rvol else "n/a",
                        " (a partial session, so volume will rise)" if in_progress else "",
                        "" if after is None else "; {} over the next sessions".format(_pct(after, 1, True))),
            "caveat": "Price and volume say how the market responded, not who bought or sold."}


QUALITY_CRITERIA = {
    "eps": "EPS against consensus (beat +1, in line 0, miss -1; within the in-line band counts as in line)",
    "revenue": "Revenue against consensus, same scale (needs the pre-release consensus saved in a forecast)",
    "growth_trend": "Revenue growth against the prior quarters (accelerating +1, steady 0, decelerating -1)",
    "eps_growth": "EPS against the same quarter a year earlier (up +1, down -1)",
    "margin": "Operating margin against the same quarter a year earlier (up a point or more +1, down -1)",
    "guidance": "Guidance against prior guidance or consensus (raised +1, held 0, cut -1; only when known)",
}


def earnings_quality(crit: Dict[str, Optional[int]]) -> Dict[str, Any]:
    known = {k: v for k, v in crit.items() if v is not None}
    if len(known) < 3:
        return {"grade": None, "status": "insufficient", "criteria": crit, "rubric": QUALITY_CRITERIA,
                "reason": "Fewer than three of the criteria have data."}
    avg = mean(known.values())
    grade = "A" if avg >= 0.6 else "B" if avg >= 0.2 else "C" if avg >= -0.2 else "D" if avg >= -0.6 else "F"
    return {"grade": grade, "status": "scored", "score": _f(avg, 2), "criteria": crit, "rubric": QUALITY_CRITERIA,
            "note": "Graded on the report, not on the stock's reaction. One criterion cannot decide it: a marginal "
                    "miss inside the in-line band scores zero, not minus one."}


def post_earnings(ticker: str, ea: Dict[str, Any], band_pct: float, *, sec: Optional[Dict[str, Any]] = None,
                  fin_q: Optional[Dict[str, Any]] = None, daily: Optional[pd.DataFrame] = None,
                  bench: Optional[pd.DataFrame] = None, quote: Optional[Dict[str, Any]] = None,
                  phase: Optional[str] = None, forecast: Optional[Dict[str, Any]] = None,
                  today: Optional[date] = None, industry: Optional[str] = None) -> Dict[str, Any]:
    lr = (ea or {}).get("latest_result") or {}
    if not lr.get("available"):
        return {"available": False, "reason": "No reported quarter in the feed."}
    rows = ((ea.get("surprise") or {}).get("rows") or [])
    timing = next((r.get("timing") for r in rows if r.get("date") == lr.get("date")), None)
    eps = classify_vs(lr.get("eps_reported"), lr.get("eps_estimate"), band_pct)
    basis = basis_warning(ea.get("surprise") or {}, industry)
    traj = quarterly_trajectory(sec, fin_q)
    # Revenue actual: the quarterly statement when its latest period follows
    # the previous one filed, which is how a fresh release shows up there.
    rev_actual, rev_period = None, None
    if fin_q and fin_q.get("periods"):
        r = (fin_q.get("rows") or {}).get("Total Revenue")
        try:
            lag = (date.fromisoformat(str(lr["date"])[:10]) - date.fromisoformat(fin_q["periods"][0][:10])).days
        except (KeyError, ValueError, TypeError):
            lag = None
        # Only the quarter this release reports: a period ending within about
        # three months before the release date. An older column means the
        # statement feed has not caught up yet.
        if r and r[0] and lag is not None and 0 <= lag <= 100:
            rev_actual, rev_period = r[0], fin_q["periods"][0]
    saved = (forecast or {}).get("forecast") or {}
    saved_cons = (saved.get("consensus") or {})
    rev_vs = classify_vs(rev_actual, saved_cons.get("revenue"), band_pct) if saved_cons.get("revenue") else {
        "state": "unknown", "reason": "The pre-release revenue consensus was not saved for this quarter, and the "
                                      "feed replaces it once results are out."}
    # GAAP against adjusted: the consensus is on the Street's adjusted basis;
    # the filed diluted EPS is GAAP and arrives with the 10-Q.
    gaap = None
    if sec and sec.get("available"):
        q = (sec.get("eps_quarters") or [])
        if q:
            gaap = {"value": q[-1].get("value"), "period_end": q[-1].get("period_end"), "basis": "GAAP diluted (SEC)"}
    crit: Dict[str, Optional[int]] = {
        "eps": {"beat": 1, "in line": 0, "miss": -1}.get(eps["state"]),
        "revenue": {"beat": 1, "in line": 0, "miss": -1}.get(rev_vs.get("state")),
        "growth_trend": {"accelerating": 1, "steady": 0, "decelerating": -1}.get(traj.get("revenue_trend") or ""),
        "eps_growth": None, "margin": None, "guidance": None,
    }
    eq = (sec or {}).get("eps_quarters") or []
    ago = _year_ago(eq, eq[-1]) if eq else None
    if ago is not None and eq[-1].get("value") is not None and ago.get("value") is not None:
        crit["eps_growth"] = 1 if eq[-1]["value"] > ago["value"] else -1 if eq[-1]["value"] < ago["value"] else 0
    om = traj.get("operating_margin") or {}
    if om.get("change_pts") is not None:
        crit["margin"] = 1 if om["change_pts"] >= 1 else -1 if om["change_pts"] <= -1 else 0
    quality = earnings_quality(crit)
    rx = reaction(daily, bench, lr["date"], timing, quote, phase, today=today)
    positives = [t for k, t in (("eps", "EPS {} consensus by {}".format(eps["state"], _pct(eps.get("surprise_pct"), 1, True))),
                                ("growth_trend", traj.get("revenue_trend_text")),
                                ("margin", "Operating margin up {} points on the year".format(om.get("change_pts"))))
                 if crit.get(k) == 1 and t]
    weaknesses = [t for k, t in (("eps", "EPS {} consensus ({})".format(eps["state"], _pct(eps.get("surprise_pct"), 1, True))),
                                 ("growth_trend", traj.get("revenue_trend_text")),
                                 ("margin", "Operating margin down {} points on the year".format(
                                     abs(om.get("change_pts") or 0))))
                  if crit.get(k) == -1 and t]
    red = []
    if crit.get("eps") == -1 and crit.get("margin") == -1 and crit.get("growth_trend") == -1:
        red.append("A miss, a falling margin and slowing growth together.")
    review = review_forecast(forecast, eps, rev_vs, rx) if forecast else {
        "available": False, "reason": "No pre-release forecast was saved for this quarter, so there is nothing to "
                                      "score; one is saved automatically whenever a pre-earnings analysis runs."}
    return {"available": True, "mode": "post_earnings",
            "release": {"date": lr.get("date"), "timing": timing or "unknown", "age_days": lr.get("age_days")},
            "headline_audit": {
                "eps": {"actual": lr.get("eps_reported"), "consensus": lr.get("eps_estimate"), **eps,
                        "basis": "Adjusted EPS as the Street reports it (Yahoo Finance)"},
                "eps_gaap": gaap,
                "revenue": {"actual": rev_actual, "period": rev_period, "consensus": saved_cons.get("revenue"), **rev_vs,
                            "source": "Yahoo Finance quarterly income statement"},
                "guidance": {"available": False, "reason": "Guidance text is not in Optic's data; it is in the "
                                                          "release and on the call."},
                "basis_warning": basis,
                "reconcile_note": "Consensus is on an adjusted basis; GAAP diluted EPS from the 10-Q can differ by "
                                  "stock pay, amortisation and one-off items. Compare like with like.",
            },
            "trajectory": traj, "reaction": rx, "quality": quality,
            "positives": positives, "weaknesses": weaknesses,
            "red_flags": red or ["None found within the reviewed evidence."],
            "forecast_review": review,
            "next_quarter": {"date": (ea.get("next_report") or {}).get("date"),
                             "watch": "Whether revenue growth holds against the trend above, and the next-quarter "
                                      "estimate revisions in the weeks after this report."},
            "separation_note": "The grade describes the report. The reaction describes the stock. They often "
                               "disagree, and both can be right."}


def review_forecast(forecast: Dict[str, Any], eps: Dict[str, Any], rev: Dict[str, Any],
                    rx: Dict[str, Any]) -> Dict[str, Any]:
    """Score each saved prediction separately against what happened. The
    saved text is quoted, never edited."""
    f = forecast.get("forecast") or {}
    preds = f.get("predictions") or {}
    out: Dict[str, Any] = {"available": True, "forecast_id": forecast.get("id"),
                           "saved_at": forecast.get("created_at"), "pre_release": forecast.get("pre_release"),
                           "scores": {}}
    rl = ((preds.get("results") or {}).get("lean") or "")
    actual = eps.get("state")
    if actual in ("beat", "in line", "miss") and rl:
        said = "beat" if "better" in rl else "miss" if "worse" in rl else "in line" if rl == "in line" else None
        out["scores"]["results"] = {"said": rl, "actual": actual, "correct": None if said is None else said == actual}
    rxl = ((preds.get("reaction") or {}).get("lean") or "")
    move = rx.get("day_pct") if rx.get("available") else None
    if move is not None and rxl:
        if rxl == "two-sided":
            rng = ((f.get("options") or {}).get("range") or {}).get("move_pct")
            ok = None if rng is None else abs(move) <= rng
            out["scores"]["reaction"] = {"said": rxl, "actual_pct": move, "correct": ok,
                                         "test": "stayed inside the priced move" if rng else "no priced move saved"}
        else:
            out["scores"]["reaction"] = {"said": rxl, "actual_pct": move,
                                         "correct": (move > 0) == (rxl == "skewed up")}
    out["scores"]["guidance"] = {"said": (preds.get("guidance") or {}).get("lean"), "actual": None, "correct": None,
                                 "test": "Not scored: guidance outcomes are not in Optic's data."}
    return out
