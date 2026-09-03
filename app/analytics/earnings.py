"""Earnings analysis: consensus, surprise history, growth, and the event's price.

Three things a trader actually needs before an earnings print:

1. What is expected (consensus EPS/revenue, and whether analysts have been
   raising or cutting into the date).
2. What normally happens (does this name beat? and does beating actually move
   the stock up?).
3. What the move costs (the options market's implied move versus the moves this
   stock has historically delivered).

Company guidance text isn't in any free feed, so the estimate-revision trend
stands in for guidance direction — labeled as such everywhere it surfaces.
"""

from __future__ import annotations

from .. import legal as legal_mod

from typing import Any, Dict, List, Optional, Set

import numpy as np
import pandas as pd

from .greeks import implied_vol


def _f(value: Any, digits: int = 4) -> Optional[float]:
    try:
        if value is None:
            return None
        out = float(value)
        if not np.isfinite(out):
            return None
        return round(out, digits)
    except (TypeError, ValueError):
        return None


def _human(value: Optional[float]) -> str:
    if value is None:
        return "—"
    a = abs(value)
    for cut, suffix in ((1e12, "T"), (1e9, "B"), (1e6, "M"), (1e3, "K")):
        if a >= cut:
            return f"{value / cut:.1f}{suffix}"
    return f"{value:.0f}"


# --------------------------------------------------------------- next report


def _next_report(history: List[Dict[str, Any]], calendar: Dict[str, Any],
                 reported_dates: Optional[Set[str]] = None) -> Dict[str, Any]:
    """The upcoming print: date, days away, and the consensus band for it.

    earnings_dates includes future rows with an estimate but no reported figure,
    which is the most reliable way to spot the next date; the calendar endpoint
    fills in the low/high analyst range around it.

    `reported_dates` is the set of dates that already have a reported EPS. The
    feed sometimes carries *both* a stale estimate-only row and a reported row for
    the same date, and taking the estimate-only one made the panel announce a
    report that had already happened — pricing a forward straddle for an event
    that was over, while the surprise table two panels down showed the result.
    """
    today = pd.Timestamp.today().normalize()
    already_reported = reported_dates or set()
    future = [
        r for r in history
        if r.get("eps_reported") is None and r.get("date")
        and pd.Timestamp(r["date"]) >= today
        and str(r["date"]) not in already_reported
    ]
    future.sort(key=lambda r: r["date"])

    date = future[0]["date"] if future else None
    if date is None:
        dates = [d for d in (calendar.get("dates") or []) if str(d) not in already_reported]
        date = dates[0] if dates else None

    out: Dict[str, Any] = {
        "date": date,
        "days_away": None,
        "confirmed": calendar.get("confirmed"),
        "eps_consensus": calendar.get("eps_avg") or (future[0].get("eps_estimate") if future else None),
        "eps_low": calendar.get("eps_low"),
        "eps_high": calendar.get("eps_high"),
        "revenue_consensus": calendar.get("revenue_avg"),
        "revenue_low": calendar.get("revenue_low"),
        "revenue_high": calendar.get("revenue_high"),
    }
    if date:
        out["days_away"] = int((pd.Timestamp(date) - today).days)
    if out["revenue_consensus"]:
        out["revenue_consensus_label"] = "$" + _human(out["revenue_consensus"])
    # A wide analyst band means low agreement, which usually means a bigger move.
    if out["eps_low"] and out["eps_high"] and out["eps_consensus"]:
        spread = (out["eps_high"] - out["eps_low"]) / abs(out["eps_consensus"]) * 100.0
        out["eps_dispersion_pct"] = _f(spread, 1)
        out["dispersion_note"] = (
            "Analysts disagree widely on this quarter. A bigger surprise either way is likely."
            if spread > 25 else
            "Analysts are tightly clustered, so a large surprise would be genuinely unexpected."
        )
    return out


# ------------------------------------------------------ surprise + reaction


def _reaction_map(hist: pd.DataFrame, dates: List[str]) -> Dict[str, Optional[float]]:
    """Percent price change on the first session after each report date.

    Reports land either before the open or after the close, and the free feed
    doesn't say which. Taking the first session that *ends* after the report
    timestamp captures the reaction candle in both cases.
    """
    if hist is None or hist.empty:
        return {}
    closes = hist["Close"].dropna()
    if closes.empty:
        return {}
    idx = closes.index.tz_localize(None) if closes.index.tz is not None else closes.index
    values = closes.to_numpy()
    out: Dict[str, Optional[float]] = {}
    for date in dates:
        stamp = pd.Timestamp(date)
        after = np.nonzero(idx > stamp)[0]
        if len(after) == 0:
            out[date] = None
            continue
        i = int(after[0])
        if i == 0:
            out[date] = None
            continue
        out[date] = _f((values[i] / values[i - 1] - 1.0) * 100.0, 2)
    return out


def _surprise_history(history: List[Dict[str, Any]], hist: pd.DataFrame, limit: int = 8) -> Dict[str, Any]:
    reported = [
        r for r in history
        if r.get("eps_reported") is not None and r.get("eps_estimate") is not None
    ]
    reported.sort(key=lambda r: r["date"], reverse=True)
    reported = reported[:limit]
    if not reported:
        return {"available": False, "rows": []}

    reactions = _reaction_map(hist, [r["date"] for r in reported])

    rows: List[Dict[str, Any]] = []
    for r in reported:
        surprise = r.get("surprise_pct")
        if surprise is None and r.get("eps_estimate"):
            est = r["eps_estimate"]
            surprise = (r["eps_reported"] - est) / abs(est) * 100.0
        rows.append({
            "date": r["date"],
            "eps_estimate": _f(r.get("eps_estimate"), 2),
            "eps_reported": _f(r.get("eps_reported"), 2),
            "surprise_pct": _f(surprise, 1),
            "beat": bool(surprise is not None and surprise > 0),
            "next_day_move_pct": reactions.get(r["date"]),
        })

    surprises = [r["surprise_pct"] for r in rows if r["surprise_pct"] is not None]
    moves = [r["next_day_move_pct"] for r in rows if r["next_day_move_pct"] is not None]
    beats = [r for r in rows if r["surprise_pct"] is not None and r["surprise_pct"] > 0]
    misses = [r for r in rows if r["surprise_pct"] is not None and r["surprise_pct"] <= 0]

    def avg_move(subset):
        vals = [r["next_day_move_pct"] for r in subset if r["next_day_move_pct"] is not None]
        return _f(float(np.mean(vals)), 2) if vals else None

    out = {
        "available": True,
        "rows": rows,
        "quarters": len(rows),
        "beat_count": len(beats),
        "beat_rate_pct": _f(len(beats) / len(surprises) * 100.0, 0) if surprises else None,
        "avg_surprise_pct": _f(float(np.mean(surprises)), 1) if surprises else None,
        "avg_abs_move_pct": _f(float(np.mean([abs(m) for m in moves])), 2) if moves else None,
        "largest_move_pct": _f(max(moves, key=abs), 2) if moves else None,
        "avg_move_on_beat_pct": avg_move(beats),
        "avg_move_on_miss_pct": avg_move(misses),
    }

    notes: List[str] = []
    if out["beat_rate_pct"] is not None:
        notes.append(
            f"Beaten consensus in {out['beat_count']} of the last {len(surprises)} quarters "
            f"({out['beat_rate_pct']:.0f}%)."
        )
    # The interesting case: a serial beater whose stock still sells off. It means
    # expectations, not the print, are what moves this name.
    on_beat = out["avg_move_on_beat_pct"]
    if on_beat is not None and out["beat_rate_pct"] and out["beat_rate_pct"] >= 70 and on_beat < 0:
        notes.append(
            "Beats haven't been enough. The stock has averaged a decline even after beating, "
            "so the bar sits above consensus."
        )
    elif on_beat is not None and on_beat > 0:
        notes.append(f"A beat has typically been rewarded, averaging {on_beat:+.1f}% the next session.")
    if out["avg_abs_move_pct"] is not None:
        notes.append(
            f"Average move the session after a report is {out['avg_abs_move_pct']:.1f}% in either direction."
        )
    out["notes"] = notes
    return out


# ------------------------------------------------- estimate revisions (guidance proxy)

_PERIOD_LABELS = {
    "0q": "Current quarter",
    "+1q": "Next quarter",
    "0y": "Current fiscal year",
    "+1y": "Next fiscal year",
}


def _extended_move(quote: Dict[str, Any]) -> Dict[str, Any]:
    """The extended-hours reaction, if there is one.

    This is not a footnote. Most large caps report after the close, and the bulk
    of the move to a print happens in the post-market session hours before the
    next open — a company can beat and be down 6% before anyone can trade it in
    regular hours. Treating the next regular session as the only reaction meant
    the panel said "the reaction isn't in yet" while a 6% rejection sat in the
    same quote object.
    """
    for kind, price_key, pct_key, time_key in (
        ("after hours", "post_market_price", "post_market_change_pct", "post_market_time"),
        ("pre-market", "pre_market_price", "pre_market_change_pct", "pre_market_time"),
    ):
        pct = quote.get(pct_key)
        if pct is None:
            continue
        return {
            "available": True,
            "kind": kind,
            "price": _f(quote.get(price_key), 2),
            "move_pct": _f(pct, 2),
            "as_of": quote.get(time_key),
            "caveat": (
                "Extended-hours volume is a fraction of the regular session, so this level is "
                "struck by far fewer participants and can retrace once the open provides real "
                "liquidity. It is the market's first read, not its settled one."
            ),
        }
    return {"available": False}


def _latest_result(surprise: Dict[str, Any],
                   extended: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """The most recently reported quarter, and whether it is fresh news.

    This exists because "the next report" and "the last result" were being read
    from different sources that disagreed. When a company reports after the close,
    the feed can still carry an estimate-only row for that same date — so the
    panel would announce an upcoming print while the row below it already showed
    what was delivered. Whichever way the feed lags, the released number wins.
    """
    rows = [r for r in (surprise.get("rows") or []) if r.get("eps_reported") is not None]
    if not rows:
        return {"available": False}

    rows.sort(key=lambda r: str(r.get("date") or ""), reverse=True)
    row = rows[0]
    today = pd.Timestamp.today().normalize()
    try:
        age_days = int((today - pd.Timestamp(row["date"])).days)
    except (TypeError, ValueError):
        age_days = None

    # "Just reported" means the market hasn't finished digesting it: the session
    # after the print hasn't completed, so there's no next-day move to show yet.
    just_reported = (
        age_days is not None and age_days <= 2 and row.get("next_day_move_pct") is None
    )

    out: Dict[str, Any] = {
        "available": True,
        "date": row.get("date"),
        "age_days": age_days,
        "eps_reported": row.get("eps_reported"),
        "eps_estimate": row.get("eps_estimate"),
        "surprise_pct": row.get("surprise_pct"),
        "beat": row.get("beat"),
        "next_day_move_pct": row.get("next_day_move_pct"),
        "just_reported": just_reported,
    }

    if just_reported:
        verb = "beat" if row.get("beat") else "missed"
        ext = extended or {}
        out["extended"] = ext

        headline = "Reported {}. EPS {} vs {} consensus, {} by {}.".format(
            "today" if age_days == 0 else "{} day(s) ago".format(age_days),
            _f(row.get("eps_reported"), 2), _f(row.get("eps_estimate"), 2),
            verb, "{:.1f}%".format(abs(row.get("surprise_pct") or 0.0)),
        )

        if ext.get("available") and ext.get("move_pct") is not None:
            move = ext["move_pct"]
            direction = "up" if move > 0 else "down"
            # The interesting case is a contradiction: beat and sold off, or
            # missed and rallied. That's the whole reason a beat isn't a signal.
            fought = (row.get("beat") and move < -1.0) or (not row.get("beat") and move > 1.0)
            out["headline"] = "{} The stock is {} {:.1f}% {}.".format(
                headline, direction, abs(move), ext["kind"])
            out["note"] = (
                "The {} move is the market's first read on the print, and it's {} the "
                "result: {} and {} {:.1f}%. The number was fine; the reaction is what "
                "matters.".format(
                    ext["kind"],
                    "fighting" if fought else "agreeing with",
                    "beat" if row.get("beat") else "missed",
                    direction, abs(move))
                if fought else
                "The {} move is the market's first read on the print and it agrees with the "
                "result. The next regular session is what confirms it. Extended-hours levels "
                "are set on thin volume and can retrace at the open.".format(ext["kind"])
            )
            out["reaction_fights_result"] = bool(fought)
        else:
            out["headline"] = headline
            out["note"] = (
                "No extended-hours quote is available, so there's no read on the reaction yet . "
                "The session after a print is what decides whether the result mattered, and a "
                "company can beat and still sell off."
            )
    return out


def _revisions(est: Dict[str, Any]) -> Dict[str, Any]:
    trend = est.get("eps_trend") or {}
    revisions = est.get("eps_revisions") or {}

    rows: List[Dict[str, Any]] = []
    for key, label in _PERIOD_LABELS.items():
        block = trend.get(key) or {}
        current = block.get("current")
        if current is None:
            continue

        def drift(days_key: str) -> Optional[float]:
            past = block.get(days_key)
            if past is None or not past or current is None:
                return None
            return _f((current / past - 1.0) * 100.0, 2)

        rev = revisions.get(key) or {}
        up30 = rev.get("upLast30days")
        down30 = rev.get("downLast30days")
        rows.append({
            "period": key,
            "label": label,
            "current": _f(current, 2),
            "chg_30d_pct": drift("30daysAgo"),
            "chg_90d_pct": drift("90daysAgo"),
            "analysts_up_30d": int(up30) if up30 is not None else None,
            "analysts_down_30d": int(down30) if down30 is not None else None,
        })

    # Score direction off the fiscal-year lines: quarterly numbers are noisier and
    # a single quarter's shift often just reflects timing rather than a real change.
    annual = [r for r in rows if r["period"] in ("0y", "+1y")]
    drifts = [r["chg_90d_pct"] for r in annual if r["chg_90d_pct"] is not None]
    drift_90 = float(np.mean(drifts)) if drifts else None

    ups = sum(r["analysts_up_30d"] or 0 for r in annual)
    downs = sum(r["analysts_down_30d"] or 0 for r in annual)

    if drift_90 is None:
        direction, note = "unknown", "No estimate-revision history available for this ticker."
    elif drift_90 >= 3:
        direction = "rising"
        note = (
            f"Analysts have raised full-year EPS estimates {drift_90:+.1f}% over 90 days . "
            "The direction of travel is positive, which usually reflects upbeat guidance."
        )
    elif drift_90 <= -3:
        direction = "falling"
        note = (
            f"Analysts have cut full-year EPS estimates {drift_90:+.1f}% over 90 days . "
            "Estimates are moving down, which usually follows soft guidance."
        )
    else:
        direction = "flat"
        note = f"Full-year estimates have barely moved ({drift_90:+.1f}% over 90 days). No clear revision trend."

    return {
        "available": bool(rows),
        "rows": rows,
        "direction": direction,
        "drift_90d_pct": _f(drift_90, 2),
        "analysts_up_30d": ups or None,
        "analysts_down_30d": downs or None,
        "note": note,
        "caveat": (
            "Company guidance text isn't available in free data. This is the analyst "
            "estimate-revision trend, which moves in response to guidance. A proxy, not the guidance itself."
        ),
    }


# --------------------------------------------------------------- growth


def _series(block: Optional[Dict[str, Any]], *names: str) -> Optional[List[Optional[float]]]:
    if not block:
        return None
    rows = block.get("rows") or {}
    for name in names:
        if name in rows:
            return rows[name]
    return None


def _growth(financials: Dict[str, Any], est: Dict[str, Any]) -> Dict[str, Any]:
    """Reported growth from the statements, plus what analysts expect next."""
    quarterly = financials.get("income_quarterly")
    annual = financials.get("income_annual")

    def yoy_rows(block, label_count=5):
        """Year-over-year growth per period. Quarterly statements only carry ~5
        quarters, so YoY needs the 4-quarters-back column where it exists."""
        if not block:
            return []
        periods = block.get("periods") or []
        rev = _series(block, "Total Revenue", "TotalRevenue")
        net = _series(block, "Net Income", "NetIncome", "Net Income Common Stockholders")
        gross = _series(block, "Gross Profit", "GrossProfit")
        op = _series(block, "Operating Income", "OperatingIncome")
        out = []
        for i, period in enumerate(periods[:label_count]):
            row = {"period": period}
            for key, vals in (("revenue", rev), ("net_income", net), ("gross_profit", gross), ("operating_income", op)):
                row[key] = _f(vals[i], 0) if vals and i < len(vals) and vals[i] is not None else None
            # Margins say more than raw levels about whether growth is profitable.
            if row.get("revenue"):
                if row.get("gross_profit") is not None:
                    row["gross_margin_pct"] = _f(row["gross_profit"] / row["revenue"] * 100.0, 1)
                if row.get("operating_income") is not None:
                    row["operating_margin_pct"] = _f(row["operating_income"] / row["revenue"] * 100.0, 1)
                if row.get("net_income") is not None:
                    row["net_margin_pct"] = _f(row["net_income"] / row["revenue"] * 100.0, 1)
            out.append(row)
        return out

    q_rows = yoy_rows(quarterly, 5)
    a_rows = yoy_rows(annual, 4)

    # Quarterly YoY: compare each quarter with the same quarter a year earlier,
    # which is 4 columns further back. Sequential comparisons would be dominated
    # by seasonality for most businesses.
    for i, row in enumerate(q_rows):
        older = q_rows[i + 4] if i + 4 < len(q_rows) else None
        for key in ("revenue", "net_income"):
            if older and row.get(key) and older.get(key):
                row[key + "_yoy_pct"] = _f((row[key] / older[key] - 1.0) * 100.0, 1)

    for i, row in enumerate(a_rows):
        older = a_rows[i + 1] if i + 1 < len(a_rows) else None
        for key in ("revenue", "net_income"):
            if older and row.get(key) and older.get(key):
                row[key + "_yoy_pct"] = _f((row[key] / older[key] - 1.0) * 100.0, 1)

    # Forward expectations, straight from the analyst estimate blocks.
    forward: List[Dict[str, Any]] = []
    eps_est = est.get("eps_estimate") or {}
    rev_est = est.get("revenue_estimate") or {}
    for key, label in _PERIOD_LABELS.items():
        e = eps_est.get(key) or {}
        r = rev_est.get(key) or {}
        if e.get("avg") is None and r.get("avg") is None:
            continue
        forward.append({
            "period": key,
            "label": label,
            "eps_avg": _f(e.get("avg"), 2),
            "eps_growth_pct": _f((e.get("growth") or 0) * 100.0, 1) if e.get("growth") is not None else None,
            "eps_analysts": int(e["numberOfAnalysts"]) if e.get("numberOfAnalysts") else None,
            "revenue_avg": _f(r.get("avg"), 0),
            "revenue_label": "$" + _human(r.get("avg")) if r.get("avg") else None,
            "revenue_growth_pct": _f((r.get("growth") or 0) * 100.0, 1) if r.get("growth") is not None else None,
        })

    notes: List[str] = []
    if q_rows and q_rows[0].get("revenue_yoy_pct") is not None:
        notes.append(f"Most recent quarter grew revenue {q_rows[0]['revenue_yoy_pct']:+.1f}% year over year.")
    # Margin direction over a year separates real operating leverage from a
    # business buying its growth.
    if len(q_rows) >= 5 and q_rows[0].get("operating_margin_pct") is not None \
            and q_rows[4].get("operating_margin_pct") is not None:
        delta = q_rows[0]["operating_margin_pct"] - q_rows[4]["operating_margin_pct"]
        if delta >= 1:
            notes.append(f"Operating margin has expanded {delta:+.1f} points versus the same quarter last year.")
        elif delta <= -1:
            notes.append(f"Operating margin has compressed {delta:+.1f} points versus the same quarter last year. Growth is costing more.")
    cy = next((f for f in forward if f["period"] == "0y"), None)
    if cy and cy.get("eps_growth_pct") is not None:
        notes.append(f"Analysts model {cy['eps_growth_pct']:+.0f}% EPS growth for the current fiscal year.")

    return {"quarterly": q_rows, "annual": a_rows, "forward": forward, "notes": notes}


# --------------------------------------------------- implied vs historical move


def _implied_move(provider, ticker: str, spot: Optional[float], report_date: Optional[str],
                  rate: float) -> Dict[str, Any]:
    """What the options market charges for the earnings event.

    The at-the-money straddle at the first expiry after the report is the market's
    price for the move. Comparing it with the moves this stock has actually made
    is the whole trade: buy the event when it's cheap, sell it when it's dear.
    """
    out: Dict[str, Any] = {"available": False}
    if not spot or not report_date:
        out["reason"] = "Needs a spot price and a scheduled report date."
        return out
    try:
        expiries = provider.expirations(ticker)
    except Exception:
        expiries = []
    if not expiries:
        out["reason"] = "This ticker has no listed options."
        return out

    stamp = pd.Timestamp(report_date)
    after = [e for e in expiries if pd.Timestamp(e) >= stamp]
    if not after:
        out["reason"] = "No listed expiry falls after the next report date."
        return out
    expiry = sorted(after)[0]

    try:
        chain = provider.options_chain(ticker, [expiry])
    except Exception as exc:
        out["reason"] = f"Could not load the {expiry} chain ({exc})."
        return out
    if chain is None or chain.empty:
        out["reason"] = f"The {expiry} chain came back empty."
        return out

    # A straddle needs a call and a put at the *same* strike, and the feed's call
    # and put strike ladders don't always match — picking the single nearest
    # strike overall can land on one that only quotes one side. So restrict to
    # strikes priced on both sides first, then take the closest of those to spot.
    chain = chain.copy()
    chain["mid"] = pd.to_numeric(chain["mid"], errors="coerce")
    priced = chain[chain["mid"] > 0]
    calls = priced[priced["is_call"]].set_index("strike")["mid"]
    puts = priced[~priced["is_call"]].set_index("strike")["mid"]
    # Duplicate strikes would make the lookup ambiguous; keep the first quote.
    calls = calls[~calls.index.duplicated()]
    puts = puts[~puts.index.duplicated()]
    both = sorted(set(calls.index) & set(puts.index))
    if not both:
        out["reason"] = f"The {expiry} chain has no strike quoted on both the call and put side."
        return out

    strike = float(min(both, key=lambda k: abs(k - spot)))
    call_px, put_px = float(calls.loc[strike]), float(puts.loc[strike])
    # A strike far from spot isn't an at-the-money straddle any more, and the
    # implied move read off it would be wrong rather than merely imprecise.
    if abs(strike / spot - 1.0) > 0.05:
        out["reason"] = (
            f"Nearest strike quoted on both sides is {strike:g}, too far from {spot:.2f} "
            "to read an at-the-money straddle."
        )
        return out

    straddle = call_px + put_px
    dte = max(int((pd.Timestamp(expiry) - pd.Timestamp.today().normalize()).days), 1)
    out.update({
        "available": True,
        "expiry": expiry,
        "dte": dte,
        "strike": _f(strike, 2),
        "straddle_cost": _f(straddle, 2),
        # The straddle price as a share of spot is the standard implied-move
        # shorthand. It's the breakeven move, so slightly conservative.
        "implied_move_pct": _f(straddle / spot * 100.0, 2),
    })
    tau = dte / 365.0
    iv = implied_vol(call_px, spot, strike, tau, rate=rate, is_call=True)
    out["atm_iv_pct"] = _f(iv * 100.0, 1) if iv and np.isfinite(iv) else None
    return out


def _realised_move_over(hist: pd.DataFrame, days: int, lookback: int = 504) -> Optional[float]:
    """Average absolute percentage move over a rolling `days`-session window.

    This is the correct baseline for a straddle: an option expiring in N days is
    priced off N days of volatility, not off a single earnings reaction. Comparing
    a 30-day straddle with a one-day post-earnings move would flag almost every
    name as "expensive" purely because the tenors don't match.
    """
    if hist is None or hist.empty or days < 1:
        return None
    closes = hist["Close"].dropna().tail(lookback)
    if len(closes) < days + 20:
        return None
    values = closes.to_numpy()
    moves = np.abs(values[days:] / values[:-days] - 1.0) * 100.0
    if not len(moves):
        return None
    return _f(float(np.mean(moves)), 2)


def _event_pricing(implied: Dict[str, Any], surprise: Dict[str, Any],
                   hist: pd.DataFrame) -> Dict[str, Any]:
    """Is the option expensive or cheap for its tenor?

    Compared against the stock's own realized move over the same holding period.
    The earnings-day reaction average is reported alongside, but not used as the
    yardstick — it answers a different question (how the print lands), and using
    it here would be a tenor mismatch.
    """
    imp = implied.get("implied_move_pct")
    dte = implied.get("dte")
    if imp is None or not dte:
        return {
            "available": False,
            "note": "Need an options-implied move to compare against price history.",
        }

    # Calendar days to trading sessions: roughly 5 per 7.
    sessions = max(int(round(dte * 5 / 7)), 1)
    event_day = surprise.get("avg_abs_move_pct")

    # Which baseline is honest depends on the tenor. A straddle expiring within a
    # week of the report is essentially a pure bet on the print, so the historical
    # earnings-day reaction is the right yardstick (and the market convention). A
    # month-dated straddle is mostly ordinary volatility, so it has to be measured
    # against the stock's realized move over that same holding period.
    if dte <= 7 and event_day:
        baseline, kind = event_day, "event-day"
        window = f"the single session after past reports ({surprise.get('quarters', 0)} quarters)"
    else:
        baseline, kind = _realised_move_over(hist, sessions), "same-tenor"
        window = f"a matched {sessions}-session window over the past two years"

    if baseline is None or baseline <= 0:
        return {
            "available": False,
            "note": "Not enough price history to build a like-for-like volatility baseline.",
        }

    ratio = imp / baseline

    if ratio >= 1.25:
        stance = "expensive"
        tail = "Options are carrying event premium, which favors selling structures over buying outright."
    elif ratio <= 0.85:
        stance = "cheap"
        tail = "Long premium has the edge here, if you accept the binary risk of the print."
    else:
        stance = "fair"
        tail = "No volatility edge either way; trade the direction or stay out."

    note = (
        f"The {dte}-day straddle prices a {imp:.1f}% move, against {baseline:.1f}% actual on average "
        f"across {window}, about {ratio:.1f}x. {tail}"
    )

    out = {
        "available": True,
        "stance": stance,
        "implied_move_pct": imp,
        "baseline_move_pct": baseline,
        "baseline_kind": kind,
        "baseline_sessions": sessions,
        "ratio": _f(ratio, 2),
        "note": note,
        "event_day_avg_pct": event_day,
        "caveat": (
            "The straddle cost is the breakeven move, so it slightly understates the market's expected "
            "move. " + (
                "This expiry sits close to the report, so the comparison is against past earnings "
                "reactions." if kind == "event-day" else
                "This expiry is well past the report, so the straddle covers ordinary volatility as "
                "well as the print. It is compared against the same holding period, not the event alone."
            )
        ),
    }
    if kind == "same-tenor" and event_day is not None:
        out["event_day_note"] = (
            f"For reference, the single session after a report has averaged {event_day:.1f}% . "
            "The print's own contribution, separate from the rest of the period."
        )
    return out


# --------------------------------------------------------------- analyst view


def _analyst(view: Dict[str, Any], spot: Optional[float]) -> Dict[str, Any]:
    targets = view.get("targets") or {}
    ratings = view.get("ratings") or []
    mean = targets.get("mean")

    out: Dict[str, Any] = {
        "target_mean": _f(mean, 2),
        "target_low": _f(targets.get("low"), 2),
        "target_high": _f(targets.get("high"), 2),
        "upside_pct": _f((mean / spot - 1.0) * 100.0, 1) if mean and spot else None,
        "ratings": ratings,
    }

    current = next((r for r in ratings if r.get("period") == "0m"), ratings[0] if ratings else None)
    if current:
        buys = (current.get("strong_buy") or 0) + (current.get("buy") or 0)
        holds = current.get("hold") or 0
        sells = (current.get("sell") or 0) + (current.get("strong_sell") or 0)
        total = buys + holds + sells
        out.update({
            "buys": int(buys), "holds": int(holds), "sells": int(sells),
            "analyst_count": int(total),
            "buy_share_pct": _f(buys / total * 100.0, 0) if total else None,
        })

    notes: List[str] = []
    if out.get("upside_pct") is not None:
        notes.append(f"Mean price target implies {out['upside_pct']:+.0f}% from here.")
        if out["upside_pct"] > 40:
            notes.append(
                "That's a wide gap. Either the target is stale or the market disagrees with the "
                "sell side. Treat targets as sentiment, not a forecast."
            )
    if out.get("buy_share_pct") is not None and out["buy_share_pct"] >= 85:
        notes.append(
            f"{out['buy_share_pct']:.0f}% of analysts rate it a buy. Crowded positioning leaves "
            "little room for upgrades as a catalyst."
        )
    out["notes"] = notes
    return out


# --------------------------------------------------------------- entry point


def _verdict(next_report: Dict[str, Any], surprise: Dict[str, Any], revisions: Dict[str, Any],
             pricing: Dict[str, Any], growth: Dict[str, Any],
             latest: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Plain-language summary. Deliberately not a score: an earnings print is a
    binary event, and dressing it up as a composite number would imply more
    predictive power than any of these inputs actually have."""
    reasons: List[str] = []
    latest = latest or {}

    # A report that has already been released is the headline, whatever the
    # calendar still lists as upcoming. Leading with "reports in 0 days" while the
    # result was already in the same response was the terminal contradicting
    # itself in two panels a few hundred pixels apart.
    if latest.get("just_reported"):
        reasons.append(latest.get("note") or "")
        if pricing.get("available") and pricing.get("note"):
            reasons.append(
                "Going in, " + pricing["note"][0].lower() + pricing["note"][1:]
                if pricing.get("stale") else pricing["note"]
            )
        if surprise.get("beat_rate_pct") is not None and surprise["beat_rate_pct"] >= 75:
            reasons.append(
                "Consistent beater ({:.0f}% hit rate over {} quarters), so the beat itself was "
                "close to the base case. The reaction is the part worth watching.".format(
                    surprise["beat_rate_pct"], surprise.get("quarters") or 0)
            )
        reasons.extend(growth.get("notes", [])[:1])
        return {
            "headline": latest.get("headline") or "Results are out.",
            "reasons": [r for r in reasons if r],
            "state": "just_reported",
        }

    days = next_report.get("days_away")
    if days is None:
        headline = "No scheduled report found."
    elif days <= 7:
        headline = f"Reports in {days} day{'s' if days != 1 else ''}. Inside the event window."
        reasons.append(
            "Options into the print carry event premium that collapses the morning after, "
            "so a directional long here needs the move to happen almost immediately."
        )
    elif days <= 21:
        headline = f"Reports in {days} days. Premium is starting to build."
        reasons.append("Implied vol usually climbs into the last two weeks, which helps long premium held into the date.")
    else:
        headline = f"Next report is {days} days out. No event premium yet."
        reasons.append("Far enough out that earnings shouldn't drive strike selection for a normal swing.")

    if revisions.get("direction") == "rising":
        reasons.append("Estimate revisions are positive, which historically precedes beats more often than misses.")
    elif revisions.get("direction") == "falling":
        reasons.append("Estimates are being cut into the date. A lower bar, but a signal of deteriorating guidance.")

    if surprise.get("beat_rate_pct") is not None and surprise["beat_rate_pct"] >= 75:
        reasons.append(f"Consistent beater ({surprise['beat_rate_pct']:.0f}% hit rate), so a beat alone is close to the base case.")

    if pricing.get("available"):
        reasons.append(pricing["note"])

    reasons.extend(growth.get("notes", [])[:1])

    return {"headline": headline, "reasons": reasons, "state": "upcoming"}


def momentum(yf_provider, ticker: str) -> Dict[str, Any]:
    """The fundamental *trend* for a swing horizon, deliberately kept out of the score.

    Estimate revisions and surprise history do carry signal over weeks, which is
    why the Swing tab shows them. They are *not* folded into the composite: doing
    that would mean quietly reweighting every score in the app, and the composite
    is calibrated as a technicals-led read. Valuation is excluded outright — a
    forward P/E says nothing about the next fortnight and, being near-static,
    would apply a constant offset to every reading for a name rather than
    responding to the setup that's actually changing.

    So this reports, and the reader decides what to do with it.
    """
    try:
        est = yf_provider.estimates(ticker) or {}
        history = yf_provider.earnings_history(ticker, limit=8) or []
        financials = yf_provider.financials(ticker) or {}
    except Exception as exc:
        return {"available": False, "reason": "earnings data unavailable ({})".format(exc)}

    revisions = _revisions(est)
    surprise = _surprise_history(history, pd.DataFrame())
    growth = _growth(financials, est)

    signals: List[Dict[str, Any]] = []

    direction = revisions.get("direction")
    if direction == "rising":
        signals.append({"label": "Estimate revisions", "read": "rising", "tone": "good",
                        "detail": "Analysts have been raising forecasts. Revisions tend to drift "
                                  "in the same direction for weeks, which is the part of "
                                  "fundamentals that matters on a swing timeframe."})
    elif direction == "falling":
        signals.append({"label": "Estimate revisions", "read": "falling", "tone": "bad",
                        "detail": "Forecasts are being cut. A long here is fighting the "
                                  "direction estimates are moving."})
    elif direction:
        signals.append({"label": "Estimate revisions", "read": direction, "tone": "neutral",
                        "detail": "No clear revision trend, so this says nothing either way."})

    beat_rate = surprise.get("beat_rate_pct")
    if beat_rate is not None:
        tone = "good" if beat_rate >= 75 else "bad" if beat_rate <= 40 else "neutral"
        signals.append({
            "label": "Surprise history", "read": "{:.0f}% beat rate".format(beat_rate),
            "tone": tone,
            "detail": "Beat {} of the last {} quarters, averaging {}. A habitual beater makes a "
                      "beat the base case rather than news. Check the reaction column, not the "
                      "hit rate.".format(
                          surprise.get("beat_count"), surprise.get("quarters"),
                          "{:+.1f}%".format(surprise["avg_surprise_pct"])
                          if surprise.get("avg_surprise_pct") is not None else "n/a"),
        })

    quarterly = (growth.get("quarterly") or [])
    if quarterly:
        latest = quarterly[0]
        rev = latest.get("revenue_yoy_pct")
        if rev is not None:
            tone = "good" if rev > 8 else "bad" if rev < 0 else "neutral"
            signals.append({
                "label": "Revenue growth", "read": "{:+.1f}% YoY".format(rev), "tone": tone,
                "detail": "Most recent reported quarter versus the same quarter a year earlier, "
                          "so seasonality doesn't distort it.",
            })
        margin = latest.get("operating_margin_pct")
        prior = quarterly[1].get("operating_margin_pct") if len(quarterly) > 1 else None
        if margin is not None and prior is not None:
            delta = margin - prior
            tone = "good" if delta > 0.5 else "bad" if delta < -0.5 else "neutral"
            signals.append({
                "label": "Operating margin", "read": "{:.1f}% ({:+.1f}pp)".format(margin, delta),
                "tone": tone,
                "detail": "Versus the prior quarter. Expanding margins mean growth is getting "
                          "more profitable, not just larger.",
            })

    if not signals:
        return {"available": False,
                "reason": "No estimate or earnings history in the feed for this symbol."}

    good = sum(1 for s in signals if s["tone"] == "good")
    bad = sum(1 for s in signals if s["tone"] == "bad")
    if good and not bad:
        read, tone = "improving", "good"
    elif bad and not good:
        read, tone = "deteriorating", "bad"
    elif good or bad:
        read, tone = "mixed", "neutral"
    else:
        read, tone = "flat", "neutral"

    return {
        "available": True,
        "read": read,
        "tone": tone,
        "signals": signals,
        "revision_direction": direction,
        "excluded_note": (
            "This does not feed the composite score above. Revisions and surprise history do "
            "carry signal over a few weeks, but the composite is deliberately a technicals-led "
            "read, and folding fundamentals in would shift every score in the terminal. "
            "Valuation is left out of this panel entirely. At a two-to-eight-week horizon it has "
            "no directional value, and it's already the backbone of the Long-Term conviction "
            "score, where the horizon matches."
        ),
    }


def analyse(provider, yf_provider, ticker: str, quote: Dict[str, Any], rate: float = 0.0) -> Dict[str, Any]:
    spot = quote.get("price")

    history = yf_provider.earnings_history(ticker, limit=16) or []
    calendar = yf_provider.earnings_calendar(ticker) or {}
    est = yf_provider.estimates(ticker) or {}
    financials = yf_provider.financials(ticker) or {}
    analyst_raw = yf_provider.analyst_view(ticker) or {}

    try:
        hist = yf_provider.history(ticker, period="3y")
    except Exception:
        hist = pd.DataFrame()

    # Surprise history first: it establishes which dates already have results, and
    # the next-report lookup needs that to avoid announcing a print that's done.
    surprise = _surprise_history(history, hist)
    reported_dates = {
        str(r["date"]) for r in (surprise.get("rows") or [])
        if r.get("date") and r.get("eps_reported") is not None
    }
    next_report = _next_report(history, calendar, reported_dates)
    extended = _extended_move(quote)
    latest = _latest_result(surprise, extended)
    revisions = _revisions(est)
    growth = _growth(financials, est)
    implied = _implied_move(provider, ticker, spot, next_report.get("date"), rate)
    pricing = _event_pricing(implied, surprise, hist)
    # Straddle pricing is a statement about an event that hasn't happened. Once
    # the print is out it describes nothing actionable, so it's marked stale
    # rather than left to read as a live signal.
    if latest.get("just_reported") and pricing.get("available"):
        pricing["stale"] = True
        pricing["stale_note"] = (
            "This compares option pricing to history for a report that has already been "
            "released, so it no longer describes a decision. Event premium collapses once the "
            "numbers are out. Kept for reference on how the event was priced beforehand."
        )
    analyst = _analyst(analyst_raw, spot)

    # ETFs, funds and trusts have no earnings at all. Rather than render six
    # panels of "not available", say so once and explain why.
    if not next_report.get("date") and not surprise.get("available") and not growth.get("forward"):
        return {
            "ticker": ticker,
            "spot": _f(spot, 2),
            "not_applicable": True,
            "reason": (
                f"{ticker} has no earnings data. No scheduled report, no reported history and no "
                "analyst estimates. That's expected for an ETF, index or trust, which holds other "
                "assets rather than running a business. For a company ticker it can also mean the "
                "feed has no coverage."
            ),
        }

    return {
        "ticker": ticker,
        "spot": _f(spot, 2),
        "latest_result": latest,
        "extended_hours": extended,
        "next_report": next_report,
        "surprise": surprise,
        "revisions": revisions,
        "growth": growth,
        "implied": implied,
        "pricing": pricing,
        "analyst": analyst,
        "verdict": _verdict(next_report, surprise, revisions, pricing, growth, latest),
        "disclaimer": legal_mod.AREAS["earnings"],
        "data_caveat": (
            "Estimates, surprise history and analyst data come from yfinance and can lag or "
            "occasionally misstate a fiscal period. Company guidance text is not available in free data."
        ),
    }
