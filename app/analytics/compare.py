"""Side-by-side comparison of two to four tickers.

Every number here already exists per-ticker. What the terminal could not do was
answer "which of these two" — and that is a different question from "is this one
good", because it needs the same metrics computed the same way at the same moment
for every name. Loading two tabs and eyeballing them invites exactly the mistake
this avoids: comparing a figure from one lookback against the same-named figure
from another.

**Three horizons, ranked separately.** A name can be the best swing setup and the
worst multi-year hold — those are not contradictions, they are different
questions, and collapsing them into one "winner" would hide the only interesting
case. Each horizon states which windows it used, because a comparison whose
lookbacks are invisible is not checkable.

**Today's move deliberately does not drive the position or long-term ranks.**
It is shown as context because a reader wants to see it, but letting a single
session reorder a multi-year assessment is how a comparison becomes a momentum
screen wearing a longer label.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

log = logging.getLogger(__name__)

MIN_TICKERS, MAX_TICKERS = 2, 4

# The performance lines: a year of sessions, sent as one point a week and the
# last session, so four names cost about two hundred numbers.
PERF_SESSIONS = 252
PERF_STEP = 5

# What each horizon is scored from, stated so the panel can show it.
HORIZONS = [
    {
        "id": "swing",
        "name": "Swing setup",
        "horizon": "1–8 weeks",
        "basis": ("14-session RSI, implied against 20-session realised volatility, "
                  "21-session relative strength versus SPY, and where price sits "
                  "against its 20- and 50-day averages. Today's tape is context "
                  "only."),
    },
    {
        "id": "position",
        "name": "Position setup",
        "horizon": "several weeks to several months",
        "basis": ("Price against its 50- and 200-day averages, 21-session relative "
                  "strength, and valuation against the company's own history. "
                  "Today's change does not materially influence this."),
    },
    {
        "id": "longterm",
        "name": "Long-term trend",
        "horizon": "multi-year",
        "basis": ("Five-year annualised price return and that rate per unit of "
                  "the same five years' volatility, how far it sits below its "
                  "high and its worst fall (both over up to 12 years of daily "
                  "closes), position against the 200-day average, and valuation "
                  "against the company's own multi-year range. Not driven by "
                  "today's move."),
    },
]


def _num(value: Any) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return None if out != out or out in (float("inf"), float("-inf")) else out


def _clip(value: float) -> float:
    return max(0.0, min(100.0, value))


def _scaled(value: Optional[float], lo: float, hi: float,
            invert: bool = False) -> Optional[float]:
    """Map a value onto 0-100 across an explicit band."""
    if value is None or hi == lo:
        return None
    pct = (value - lo) / (hi - lo) * 100.0
    return _clip(100.0 - pct if invert else pct)


def _ratio(top: Optional[float], bottom: Optional[float]) -> Optional[float]:
    if top is None or not bottom:
        return None
    return round(top / bottom, 2)


def _mean(parts: List[Optional[float]]) -> Optional[float]:
    usable = [p for p in parts if p is not None]
    return round(sum(usable) / len(usable), 1) if usable else None


# Two scores this close are level. One rule for the headline, the cards, the bars, the ranks and the table:
# the gap is taken between the scores as shown (one decimal), so 70.3 against 65.3 is five points and
# decisive, where the unrounded difference (4.9999...) once printed "5.0 apart, under 5" (audit 2026-10-20).
TIE_POINTS = 5.0


def _gap(a: Optional[float], b: Optional[float]) -> Optional[float]:
    if a is None or b is None:
        return None
    return round(round(a, 1) - round(b, 1), 1)


# What a fund has no figure for, and what the benchmark cannot be measured against.
FUND_TYPES = {"ETF", "MUTUALFUND", "INDEX"}
BENCHMARK = "SPY"
AGAINST_BENCHMARK = ("rs_vs_spy", "excess_cagr_5y_pct", "beta_vs_spy")


def _metrics(payload: Dict[str, Any], longterm: Dict[str, Any]) -> Dict[str, Any]:
    """Pull the comparable figures out of the per-ticker payloads.

    The key paths here were all verified against live payloads rather than
    guessed. Three of them were wrong on the first pass and the metric simply
    rendered as "—" instead of failing, which is the failure mode worth naming:
    a silent None reads as "no data for this name" when it actually means
    "wrong key". Anything read here is read from a shape that was printed first.
    """
    tech = payload.get("technicals") or {}
    fund_meta = ((longterm or {}).get("holding") or {}).get("fundamentals") or {}
    qtype = str(fund_meta.get("quote_type") or (payload.get("quote") or {}).get("quote_type") or "").upper()
    mas = tech.get("moving_averages") or {}
    vol = tech.get("volatility") or {}
    quote = payload.get("quote") or {}
    entry = payload.get("entry_plan") or {}
    sc = payload.get("sector_confirm") or {}
    holding = (longterm or {}).get("holding") or {}
    vh = holding.get("valuation_history") or {}
    hz = holding.get("horizons") or {}
    risk = holding.get("risk") or {}
    trend = holding.get("long_trend") or {}
    val = holding.get("valuation") or {}
    draw = holding.get("drawdown") or {}

    def ma_dist(key: str) -> Optional[float]:
        return _num((mas.get(key) or {}).get("distance_pct"))

    return {
        "price": _num(quote.get("price")),
        "change_pct": _num(quote.get("change_pct")),
        # technicals.rsi is an object — the number is under .value.
        "rsi": _num((tech.get("rsi") or {}).get("value")),
        "atr_pct": _num(vol.get("atr_pct")),
        "iv_pct": _num((entry.get("iv_context") or {}).get("atm_iv_pct")),
        "hv_pct": _num(vol.get("realised_vol_20d")),
        "rs_vs_spy": _num(sc.get("rs_vs_spy_pct")),
        "vs_sma20": ma_dist("sma20"),
        "vs_sma50": ma_dist("sma50"),
        "vs_sma200": ma_dist("sma200"),
        "composite": _num((payload.get("verdict") or {}).get("composite_score")),
        "pe_percentile": _num(vh.get("percentile")),
        "pe_read": vh.get("read"),
        "forward_pe": _num(val.get("forward_pe")),
        # Current distance from the all-time high, not the worst historical one.
        "drawdown_pct": _num(draw.get("current_drawdown_pct")),
        # Annualised over five years, so it is comparable between names with
        # different listing histories. Total return would flatter the older one.
        "cagr_5y_pct": _num(hz.get("cagr_5y_pct")),
        "excess_cagr_5y_pct": _num(holding.get("excess_cagr_5y_pct")),
        "beta_vs_spy": _num(risk.get("beta_vs_spy")),
        "annual_vol_pct": _num(risk.get("annualised_vol_pct")),
        "max_drawdown_pct": _num(draw.get("max_drawdown_pct")),
        "vol_5y_pct": _num(risk.get("annualised_vol_5y_pct")),
        # Derived here rather than taken from holding.sharpe_proxy, which divides
        # a trailing one-year return by a multi-year volatility. Mixing windows
        # inside one ratio is the exact error this tab exists to avoid, so the
        # five-year rate is divided by the volatility of the same five years.
        # (Until 2026-10-20 it was divided by the full, up to 12-year, figure.)
        "cagr_per_vol_5y": _ratio(_num(hz.get("cagr_5y_pct")),
                                  _num(risk.get("annualised_vol_5y_pct"))),
        # How much daily history the multi-year figures stand on: up to 12 years.
        "history_years": _num(((longterm or {}).get("holding") or {}).get("data_quality", {}).get("history_years")),
        # A fund has no earnings, so no P/E, and its "sector" is a fund family.
        "kind": "fund" if qtype in FUND_TYPES else "stock",
        "vs_sma40w": _num(trend.get("vs_40w_sma")),
        "trend_phase": trend.get("phase"),
        "sector": sc.get("sector") or (holding.get("fundamentals") or {}).get("sector"),
        "name": holding.get("name") or payload.get("ticker"),
    }


def _swing_parts(m: Dict[str, Any]) -> List[Optional[float]]:
    """Momentum without being extended, and options not overpriced."""
    # RSI is best in the upper-middle: 50-70 is trending, above 75 is stretched.
    rsi = m.get("rsi")
    rsi_score = None
    if rsi is not None:
        rsi_score = _scaled(rsi, 30, 65) if rsi <= 65 else _scaled(rsi, 65, 90, invert=True)
    iv, hv = m.get("iv_pct"), m.get("hv_pct")
    # Cheap implied vol relative to what the stock actually does is a better entry.
    vol_score = _scaled(iv / hv, 0.7, 1.6, invert=True) if iv and hv else None
    return [
        rsi_score,
        _scaled(m.get("rs_vs_spy"), -10, 15),
        _scaled(m.get("vs_sma20"), -8, 8),
        _scaled(m.get("vs_sma50"), -12, 12),
        vol_score,
    ]


def _position_parts(m: Dict[str, Any]) -> List[Optional[float]]:
    """Trend intact over months, and not paying a record multiple for it."""
    return [
        _scaled(m.get("vs_sma50"), -12, 12),
        _scaled(m.get("vs_sma200"), -20, 25),
        _scaled(m.get("rs_vs_spy"), -10, 15),
        # A low percentile means cheap against its own history.
        _scaled(m.get("pe_percentile"), 0, 100, invert=True),
    ]


def _longterm_parts(m: Dict[str, Any]) -> List[Optional[float]]:
    """Multi-year trend, how far off the high, and valuation against its range."""
    return [
        # A five-year CAGR, so the band is annual-return sized. Scoring a total
        # return on this band would put every large-cap winner at 100.
        _scaled(m.get("cagr_5y_pct"), -5, 35),
        # A shallow current drawdown is a healthier long-term chart.
        _scaled(m.get("drawdown_pct"), -40, 0),
        _scaled(m.get("vs_sma200"), -20, 25),
        _scaled(m.get("pe_percentile"), 0, 100, invert=True),
        # Return per unit of volatility — two names can compound at the same
        # rate with very different holding experiences. SPY sits near 0.65 on
        # this ratio, so the band is set either side of that.
        _scaled(m.get("cagr_per_vol_5y"), -0.2, 1.2),
        # The worst peak-to-trough this name has actually put a holder through.
        _scaled(m.get("max_drawdown_pct"), -75, -20),
    ]


def _score_swing(m: Dict[str, Any]) -> Optional[float]:
    return _mean(_swing_parts(m))


def _score_position(m: Dict[str, Any]) -> Optional[float]:
    return _mean(_position_parts(m))


def _score_longterm(m: Dict[str, Any]) -> Optional[float]:
    return _mean(_longterm_parts(m))


SCORERS = {"swing": _score_swing, "position": _score_position, "longterm": _score_longterm}
PARTS = {"swing": _swing_parts, "position": _position_parts, "longterm": _longterm_parts}


def _closes(payload: Dict[str, Any]) -> List[Tuple[str, float]]:
    """The daily closes the snapshot already carries, as (date, close)."""
    ps = ((payload or {}).get("technicals") or {}).get("price_series") or {}
    out = []
    for d, c in zip(ps.get("dates") or [], ps.get("close") or []):
        v = _num(c)
        if d and v and v > 0:
            out.append((str(d)[:10], v))
    return out


def _performance(closes: Dict[str, List[Tuple[str, float]]]) -> Optional[Dict[str, Any]]:
    """Each name's price over the past year, rebased to 100 on the first day all
    of them traded, so the lines start together and where each ends says how it
    did against the others. Price only: the closes are split-adjusted and leave
    dividends out. None when two names do not share a month of sessions."""
    usable = {t: c for t, c in closes.items() if c}
    if len(usable) < MIN_TICKERS:
        return None
    common = set.intersection(*(set(d for d, _ in c) for c in usable.values()))
    dates = sorted(common)[-(PERF_SESSIONS + 1):]
    if len(dates) < 21:
        return None
    keep = dates[::PERF_STEP]
    if keep[-1] != dates[-1]:
        keep.append(dates[-1])
    series = []
    for ticker, rows in usable.items():
        by_date = dict(rows)
        base = by_date[dates[0]]
        series.append({"ticker": ticker,
                       "values": [round(by_date[d] / base * 100.0, 2) for d in keep],
                       "change_pct": round((by_date[dates[-1]] / base - 1.0) * 100.0, 1)})
    return {"dates": keep, "start": dates[0], "end": dates[-1],
            "sessions": len(dates) - 1, "series": series}


def build(snapshot_fn, longterm_fn, tickers: List[str]) -> Dict[str, Any]:
    """Compare tickers across the three horizons.

    `snapshot_fn` and `longterm_fn` are injected so this module never touches a
    provider directly — the same reason the scoring is pure: it can be tested
    without a network.
    """
    clean: List[str] = []
    for raw in tickers or []:
        sym = str(raw or "").upper().strip()
        if sym and sym not in clean:
            clean.append(sym)
    if len(clean) < MIN_TICKERS:
        return {"available": False,
                "reason": "Give at least {} tickers to compare.".format(MIN_TICKERS)}
    clean = clean[:MAX_TICKERS]

    rows: List[Dict[str, Any]] = []
    failed: List[Dict[str, str]] = []
    closes: Dict[str, List[Tuple[str, float]]] = {}
    for sym in clean:
        try:
            payload = snapshot_fn(sym)
        except Exception as exc:
            failed.append({"ticker": sym, "reason": str(exc)[:120]})
            continue
        if not payload or payload.get("error"):
            failed.append({"ticker": sym,
                           "reason": (payload or {}).get("error") or "no data"})
            continue
        try:
            lt = longterm_fn(sym)
        except Exception as exc:
            log.info("compare: long-term unavailable for %s: %s", sym, exc)
            lt = {}
        m = _metrics(payload, lt or {})
        m["ticker"] = sym
        # The benchmark against itself is not a measurement: its relative strength, excess return and beta
        # are said to be the benchmark's, not shown as n/a, 0 and 1 (audit 2026-10-20).
        m["is_benchmark"] = sym == BENCHMARK
        m["why_na"] = {}
        if m["is_benchmark"]:
            for key in AGAINST_BENCHMARK:
                m[key] = None
                m["why_na"][key] = "the benchmark"
        if m["kind"] == "fund":
            for key in ("forward_pe", "pe_percentile"):
                if m.get(key) is None:
                    m["why_na"][key] = "a fund"
        m["scores"] = {k: fn(m) for k, fn in SCORERS.items()}
        m["score_inputs"] = {k: [sum(p is not None for p in fn(m)), len(fn(m))] for k, fn in PARTS.items()}
        rows.append(m)
        closes[sym] = _closes(payload)

    if len(rows) < MIN_TICKERS:
        return {"available": False,
                "reason": "Only {} of {} tickers returned data.".format(len(rows), len(clean)),
                "failed": failed}

    # Rank within each horizon. Names within TIE_POINTS of the top are level and share first place; below
    # them, a score equal to the one before shares its rank. Each entry says where it stands in words the
    # page shows as they are: "best", "level" or "#3".
    ranks: Dict[str, List[Dict[str, Any]]] = {}
    for hid in SCORERS:
        scored = [r for r in rows if r["scores"].get(hid) is not None]
        scored.sort(key=lambda r: -r["scores"][hid])
        top = scored[0]["scores"][hid] if scored else None
        level = [r for r in scored if _gap(top, r["scores"][hid]) < TIE_POINTS]
        out = []
        for i, r in enumerate(scored):
            if r in level:
                rank, standing = 1, "level" if len(level) > 1 else "best"
            elif out and _gap(out[-1]["score"], r["scores"][hid]) == 0:
                rank, standing = out[-1]["rank"], out[-1]["standing"]
            else:
                rank, standing = i + 1, "#{}".format(i + 1)
            out.append({"ticker": r["ticker"], "score": r["scores"][hid], "rank": rank, "standing": standing,
                        "inputs": r["score_inputs"][hid]})
        ranks[hid] = out

    return {
        "available": True,
        "tickers": [r["ticker"] for r in rows],
        "rows": rows,
        "ranks": ranks,
        "horizons": HORIZONS,
        "performance": _performance(closes),
        "leaders": leaders(rows),
        "tie_points": TIE_POINTS,
        "failed": failed,
        "method": (
            "Every figure is computed the same way at the same moment for each "
            "name, which is the point. Comparing a number from one tab against a "
            "same-named number from another risks comparing different lookbacks. "
            "The three horizons are ranked separately because a name can be the "
            "best swing setup and the worst multi-year hold; that is not a "
            "contradiction. Today's price change is shown as context and "
            "deliberately does not drive the position or long-term ranks. Research "
            "context, not instructions to buy or sell."
        ),
    }


# ---------------------------------------------------------------- Optic's take

# Metrics worth calling out a leader on, with the direction that counts as good
# and the words to say it in. Chosen because each one answers a question someone
# actually brings to a comparison; a leader on "beta" is trivia.
TAKE_METRICS = [
    ("rs_vs_spy", True, "the strongest relative strength against SPY"),
    ("cagr_5y_pct", True, "the best five-year compound growth"),
    ("cagr_per_vol_5y", True, "the most return per unit of volatility"),
    ("drawdown_pct", True, "the smallest drawdown from its high"),
    ("annual_vol_pct", False, "the calmest price action"),
    ("forward_pe", False, "the cheapest forward multiple"),
]


# Every row of the table where one direction is better, with the decimals the table shows it to and the
# smallest gap that counts at that scale. The table's dots and the take's standouts are read off this one
# list (the page used to compute its own dots on a 2%-of-spread rule that never fired for two names, and
# gave an exact tie's dot to the first column).
LEAD_ROWS = {
    # key: (higher is better, decimals shown, floor)
    "rs_vs_spy": (True, 2, 0.25), "cagr_5y_pct": (True, 2, 0.25), "excess_cagr_5y_pct": (True, 2, 0.25),
    "cagr_per_vol_5y": (True, 2, 0.05), "drawdown_pct": (True, 2, 0.25), "max_drawdown_pct": (True, 2, 0.25),
    "annual_vol_pct": (False, 1, 0.25), "forward_pe": (False, 1, 0.25), "pe_percentile": (False, 0, 1.0),
    "composite": (True, 0, 1.0),
}


def leaders(rows: List[Dict[str, Any]]) -> Dict[str, Optional[str]]:
    """The leading ticker on each row that has a direction, or None for no clear leader."""
    out = {}
    for key, (high_good, _dp, _floor) in LEAD_ROWS.items():
        got = _leader(rows, key, high_good)
        out[key] = got["ticker"] if got else None
    return out


def _leader(rows: List[Dict[str, Any]], key: str, high_is_good: bool):
    """The name leading on one metric, or None when too few have the number."""
    have = [(r["ticker"], _num(r.get(key))) for r in rows]
    have = [(t, v) for t, v in have if v is not None]
    if len(have) < 2:
        return None
    have.sort(key=lambda pair: pair[1], reverse=high_is_good)
    best, second = have[0], have[1]
    _hg, dp, floor = LEAD_ROWS.get(key, (high_is_good, 2, 0.25))
    # level as the table prints them is level: no leader between two equal figures
    if round(best[1], dp) == round(second[1], dp):
        return None

    # A leader by a hair is not a finding.
    #
    # The first version compared the top-two gap against the spread across the
    # whole field, which is meaningless for two names: the spread IS the gap, so
    # `gap < spread * 0.08` reduces to `gap < gap * 0.08` and never fires. The
    # near-tie guard was dead in the most common case — a two-name comparison.
    #
    # Measured against the size of the numbers instead, which works at any
    # count: 5% of the larger magnitude. The floor catches values straddling
    # zero, where a ratio is unstable — a relative strength of +0.1 against
    # -0.05 is not a leader either.
    gap = abs(best[1] - second[1])
    scale = max(abs(best[1]), abs(second[1]))
    if gap < max(scale * 0.05, floor):
        return None
    return {"ticker": best[0], "value": best[1]}


def take(payload: Dict[str, Any]) -> Dict[str, Any]:
    """A plain-language read across the comparison.

    The tab already scored three horizons separately and said in its own
    subtitle that "that disagreement is the useful part" — and then left the
    reader to find the disagreement by eye across a table of twenty-six rows.
    This states it.

    Derived, not written. No model call: a comparison is re-run every time
    someone changes a ticker, and a summary that costs an AI call would either
    blow the hourly budget or go blank halfway through the task.
    """
    rows = payload.get("rows") or []
    ranks = payload.get("ranks") or {}
    if len(rows) < 2 or not ranks:
        return {"available": False,
                "reason": "Two names with data are needed before there is anything to compare."}

    horizons = {h["id"]: h for h in (payload.get("horizons") or [])}
    winners: Dict[str, Any] = {}
    for hid, entries in ranks.items():
        ordered = [e for e in entries if _num(e.get("score")) is not None]
        if len(ordered) < 2:
            continue
        top, second = ordered[0], ordered[1]
        gap = _gap(_num(top["score"]), _num(second["score"]))
        winners[hid] = {
            "ticker": top["ticker"],
            "score": _num(top["score"]),
            "gap": gap,
            # Under five points on a 0-100 scale, across scores built from a
            # handful of inputs, is not a ranking anyone should act on.
            "decisive": gap >= TIE_POINTS,
            "name": (horizons.get(hid) or {}).get("name", hid),
        }

    # Only a decisive horizon has a leader. A close call is level everywhere it is said: the headline, the
    # overall pick, the cards, the bars and the table (owner, 2026-10-19: the headline named SPY the
    # long-term leader by 0.3 points while the table called the two level).
    decisive = [w for w in winners.values() if w["decisive"]]
    level = [w for w in winners.values() if not w["decisive"]]
    tickers = [w["ticker"] for w in decisive]
    unanimous = not level and len(set(tickers)) == 1 and len(tickers) > 1

    # Most horizons won, not the highest score.
    #
    # The first version took max() over the scores, which compares numbers from
    # different scales answering different questions — a swing score of 81 is
    # not "more" than a position score of 70. It named NVDA overall on a
    # comparison where KO won two of the three horizons.
    #
    # None when the count ties: a split verdict is the finding, and picking a
    # winner out of a tie would bury it.
    counts: Dict[str, int] = {}
    for t in tickers:
        counts[t] = counts.get(t, 0) + 1
    overall = None
    if counts:
        best = max(counts.values())
        leading = [t for t, n in counts.items() if n == best]
        overall = leading[0] if len(leading) == 1 else None

    # Standouts, spread across names.
    #
    # The metric list is ordered by how interesting each one is, and taking the
    # first three straight off it gave all three to the same name — so a
    # comparison where one name holds every growth metric and the other holds
    # every risk metric reported only the growth. At most two per ticker, so the
    # second name's strengths reach the summary.
    picked: List[Dict[str, Any]] = []
    per_ticker: Dict[str, int] = {}
    for key, high_good, phrase in TAKE_METRICS:
        got = _leader(rows, key, high_good)
        if not got:
            continue
        sym = got["ticker"]
        if per_ticker.get(sym, 0) >= 2:
            continue
        per_ticker[sym] = per_ticker.get(sym, 0) + 1
        picked.append({"ticker": sym, "phrase": phrase,
                       "metric": key, "value": got["value"]})
    standouts = picked

    # The sentence. Assembled rather than templated over one shape, because
    # "they all agree" and "they disagree by horizon" are different findings and
    # flattening them into one phrasing loses the distinction.
    level_bit = ""
    if level:
        names = [w["name"].lower() for w in level]
        level_bit = "the {} {} level".format(" and the ".join(names), "is" if len(names) == 1 else "are")
    if unanimous:
        headline = "{} leads every horizon.".format(tickers[0])
    elif decisive and len(set(tickers)) == 1:
        headline = "{} leads the {}{}.".format(tickers[0], " and the ".join(w["name"].lower() for w in decisive),
                                               "; " + level_bit if level_bit else "")
    elif decisive:
        bits = ", ".join("{} on the {}".format(w["ticker"], w["name"].lower()) for w in decisive)
        headline = "No name leads throughout: {}{}.".format(bits, "; " + level_bit if level_bit else "")
    elif len(winners) > 1:
        headline = "No name leads: the scores are level on every horizon."
    else:
        headline = "The one horizon with enough data is level." if level else "Neither name has enough data to rank."

    weak = [w for w in winners.values() if not w["decisive"]]
    # How the horizons relate, said once beside the heading: "disagree" only when two decisive horizons name
    # different leaders (it used to say so whenever the verdict was not unanimous, a level horizon included).
    if unanimous:
        agreement = "All three horizons name {}.".format(tickers[0]) if len(winners) == 3 else "Every horizon names {}.".format(tickers[0])
    elif len(set(tickers)) > 1:
        agreement = "The horizons name different leaders."
    elif tickers:
        n = len(level)
        agreement = "{} leads where the scores separate; {} horizon{} level.".format(
            tickers[0], {1: "one", 2: "two"}.get(n, str(n)), " is" if n == 1 else "s are")
    else:
        agreement = "Level on every horizon."
    return {
        "available": True,
        "headline": headline,
        "agreement": agreement,
        "overall": overall,
        "unanimous": unanimous,
        "winners": winners,
        "standouts": standouts[:4],
        "close_calls": [{"name": w["name"], "gap": w["gap"], "ticker": w["ticker"]}
                        for w in weak],
        "method": (
            "Leaders are read off the same three scores the table below shows. A "
            "horizon whose top two are within five points is flagged as a close "
            "call rather than a ranking: the scores are built from a handful of "
            "inputs each and do not resolve that finely."
        ),
    }
