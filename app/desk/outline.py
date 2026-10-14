"""Stage 2: the analytical outline, decided by code before anything is written.

The model writes prose; it does not decide what matters. This module does, from
the evidence alone, and every choice it makes is a rule a reader can check:

* **Salience** is a move against the instrument's own typical day (the mean
  absolute daily change over the previous 20 sessions, or the ATR for the macro
  strip), so a 2% day for a chip stock is not ranked with a 2% day for a bank.
* **The lead** is the theme with the most salient evidence, with a scheduled
  high-impact release in the next two days as the tension when there is one.
* **The numbers that matter** are the most salient figures, at most one per
  theme, three to six of them, each carrying its period and comparison base.
* **Relationships** (rates and growth stocks, the dollar and gold, oil and
  inflation expectations, credit and equities, breadth and the index, the VIX
  and the index, bank results and the consumer) are evaluated against today's
  evidence and given a status: consistent, contradicted, mixed or not enough
  evidence. They are hypotheses to test, never rules to apply.
* **What to watch** is the dated calendar, with conditions in both directions.

Nothing here calls a model or fetches.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

THEMES = ("equities", "rates", "dollar", "oil", "credit", "volatility", "earnings", "sectors",
          "companies", "news", "calendar")

# Words that mark a story as about markets, the economy or a company rather
# than lifestyle, personal finance advice or general news.
_MARKET_WORDS = re.compile(
    r"\b(stock|stocks|shares|market|markets|index|s&p|nasdaq|dow|yield|yields|treasur|bond|bonds|"
    r"fed|federal reserve|rate|rates|inflation|cpi|ppi|jobs|payroll|gdp|tariff|earnings|profit|"
    r"revenue|guidance|outlook|forecast|oil|crude|opec|dollar|currency|gold|bank|banks|chip|chips|"
    r"semiconductor|ai|capex|merger|acquisition|deal|ipo|sec|ftc|doj|antitrust|fine|settle|"
    r"lawsuit|sanction|recession|economy|economic|consumer|spending|retail|housing|mortgage)\b", re.I)
_NOT_NEWS = re.compile(r"\b(my (sister|brother|mother|father|wife|husband)|should i|ask a|dear|horoscope|"
                       r"recipe|crab|celebrity|how to retire|retirement plan|jim cramer says)\b", re.I)


def _ev(bundle: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    return {e["id"]: e for e in bundle.get("evidence") or []}


def _change(e: Dict[str, Any]) -> Optional[float]:
    """The day's change in the evidence's own unit: a percent for prices, basis
    points for yields, points for the VIX."""
    comp = e.get("compare") or {}
    if comp.get("change") is not None and comp.get("change_unit") in ("bp", "pts"):
        return comp["change"]
    if e.get("unit") == "%" and e.get("kind") in ("index", "sector", "company", "fx", "commodity", "credit"):
        return e.get("value")
    return None


def salience(e: Dict[str, Any]) -> float:
    ch = _change(e)
    typ = (e.get("detail") or {}).get("typical_abs_1d")
    if ch is None or not typ:
        return 0.0
    return abs(ch) / typ


def theme_of(e: Dict[str, Any]) -> str:
    k = e.get("kind")
    return {"index": "equities", "rates": "rates", "policy": "rates", "fx": "dollar", "credit": "credit",
            "volatility": "volatility", "earnings": "earnings", "sector": "sectors", "company": "companies",
            "news": "news", "calendar": "calendar", "breadth": "equities", "options": "volatility",
            "macro": "macro"}.get(k, "other") if not (k == "commodity" and "oil" in (e.get("label") or "").lower()) else "oil"


def relevant_news(evs: List[Dict[str, Any]], limit: int = 12) -> List[Dict[str, Any]]:
    """Market-relevant stories, most widely carried and then newest first."""
    scored = []
    for e in evs:
        if e.get("kind") != "news":
            continue
        title = e.get("label") or ""
        if _NOT_NEWS.search(title):
            continue
        official = bool((e.get("detail") or {}).get("official"))
        hits = len(_MARKET_WORDS.findall(title + " " + (e.get("text") or "")))
        if not hits and not official:
            continue
        score = hits + 2 * ((e.get("sources_in_cluster") or 1) - 1) + (2 if official else 0)
        scored.append((score, e.get("published_at") or "", e))
    scored.sort(key=lambda t: (t[0], t[1]), reverse=True)
    return [e for _, _, e in scored[:limit]]


# --------------------------------------------------------------- relationships

def _get(evm: Dict[str, Dict[str, Any]], **match) -> Optional[Dict[str, Any]]:
    for e in evm.values():
        if all(e.get(k) == v for k, v in match.items()):
            return e
    return None


def _sym(evm, sym, kind=None):
    for e in evm.values():
        if e.get("symbol") == sym and (kind is None or e.get("kind") == kind):
            return e
    return None


def _sign(x: Optional[float], flat: float) -> int:
    if x is None or abs(x) < flat:
        return 0
    return 1 if x > 0 else -1


def relationships(evm: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    spy, qqq, iwm = _sym(evm, "SPY", "index"), _sym(evm, "QQQ", "index"), _sym(evm, "IWM", "index")
    tnx, dxy, gold = _sym(evm, "^TNX"), _sym(evm, "DX-Y.NYB"), _sym(evm, "GC=F")
    wti, hyg, vix = _sym(evm, "CL=F"), _sym(evm, "HYG"), _sym(evm, "^VIX")
    xle = _sym(evm, "XLE", "sector")
    t10 = _change(tnx) if tnx else None

    def rel(rid, claim, mechanism, ids, status, note):
        out.append({"id": rid, "claim": claim, "mechanism": mechanism,
                    "evidence": [i for i in ids if i], "status": status, "note": note})

    # Rates and long-duration growth stocks.
    if tnx and qqq and spy and t10 is not None and abs(t10) >= 3:
        rel_perf = (qqq.get("value") or 0) - (spy.get("value") or 0)
        expect = -1 if t10 > 0 else 1          # higher yields, growth lags
        got = _sign(rel_perf, 0.15)
        status = "consistent" if got == expect else "contradicted" if got == -expect else "mixed"
        rel("rates_growth", "Higher yields weigh on growth stocks, whose value rests more on profits far in the future",
            "A higher discount rate lowers the present value of distant cash flows more than near ones.",
            [tnx["id"], qqq["id"], spy["id"]], status,
            "The 10-year moved {:+.1f}bp; the Nasdaq 100 did {:+.2f} points {} the S&P 500.".format(
                t10, rel_perf, "better than" if rel_perf >= 0 else "worse than"))
    # Dollar and gold.
    if dxy and gold and _sign(dxy.get("value"), 0.15):
        expect = -_sign(dxy.get("value"), 0.15)
        got = _sign(gold.get("value"), 0.2)
        rel("dollar_gold", "A stronger dollar usually weighs on gold, which is priced in dollars",
            "Gold costs more in other currencies when the dollar rises, which can reduce demand.",
            [dxy["id"], gold["id"]], "consistent" if got == expect else "contradicted" if got == -expect else "mixed",
            "Dollar {:+.2f}%, gold {:+.2f}%. Real yields, central-bank buying and safe-haven demand also move gold.".format(
                dxy.get("value") or 0, gold.get("value") or 0))
    # Oil and inflation expectations / energy shares.
    if wti and _sign(wti.get("value"), 1.0):
        ids = [wti["id"], xle["id"] if xle else None]
        got = _sign(xle.get("value"), 0.3) if xle else 0
        exp = _sign(wti.get("value"), 1.0)
        rel("oil_energy", "Oil prices feed into inflation expectations and energy company profits",
            "Energy is a direct input cost across the economy and the revenue line of producers.",
            ids, "consistent" if got == exp else "contradicted" if got == -exp else "mixed" if xle else "insufficient",
            "WTI {:+.2f}%{}.".format(wti.get("value") or 0,
                                      ", energy shares (XLE) {:+.2f}%".format(xle.get("value") or 0) if xle else ""))
    # Credit and equities agree on risk appetite?
    if hyg and spy:
        a, b = _sign(hyg.get("value"), 0.1), _sign(spy.get("value"), 0.2)
        if a or b:
            rel("credit_equity", "Credit and stocks usually agree about risk",
                "High-yield bonds are paid only if companies stay solvent, so they react to the same worries as shares.",
                [hyg["id"], spy["id"]], "consistent" if a == b else "contradicted" if a == -b else "mixed",
                "High-yield bonds (HYG) {:+.2f}%, S&P 500 {:+.2f}%.".format(hyg.get("value") or 0, spy.get("value") or 0))
    # Breadth against the index.
    up = _get(evm, kind="breadth", label="Sector ETFs higher on the day")
    if up and spy:
        total = (up.get("detail") or {}).get("total") or 11
        share = (up.get("value") or 0) / total
        s = _sign(spy.get("value"), 0.2)
        narrow = (s > 0 and share < 0.5) or (s < 0 and share > 0.5)
        rel("breadth", "A move carried by most sectors says more than one carried by a few",
            "When the index moves on a handful of large companies, the average stock can be doing something different.",
            [up["id"], spy["id"]], "mixed" if narrow else "consistent" if s else "insufficient",
            "{} of {} sector funds rose while the S&P 500 moved {:+.2f}%.".format(int(up.get("value") or 0), total,
                                                                               spy.get("value") or 0))
    # The VIX and the index.
    if vix and spy:
        vch = (vix.get("compare") or {}).get("change")
        a, b = _sign(vch, 0.3), _sign(spy.get("value"), 0.2)
        if a and b:
            rel("vix_index", "The VIX usually rises when stocks fall",
                "Investors pay more for protection after declines, which lifts implied volatility.",
                [vix["id"], spy["id"]], "consistent" if a == -b else "mixed",
                "VIX {:+.2f} points to {:.2f}; S&P 500 {:+.2f}%.".format(vch, vix.get("value") or 0, spy.get("value") or 0))
    # Bank results and the consumer: evidence about customers, not the economy.
    banks = [e for e in evm.values() if e.get("kind") == "earnings" and (e.get("detail") or {}).get("sector") == "Financial Services"
             and (e.get("detail") or {}).get("eps_reported") is not None]
    if banks:
        claims = _get(evm, symbol="ICSA")
        unrate = _get(evm, symbol="UNRATE")
        rel("banks_consumer", "Bank results are evidence about their own customers' borrowing and repayment",
            "Loan growth, card spending and credit losses at large banks reflect households and businesses they lend to.",
            [b["id"] for b in banks] + [claims["id"] if claims else None, unrate["id"] if unrate else None],
            "insufficient",
            "{} large bank{} reported. A few banks do not establish the state of the whole economy; jobless claims and "
            "unemployment are the broader cross-check.".format(len(banks), "" if len(banks) == 1 else "s"))
    return out


# --------------------------------------------------------------- the outline

_CONDITIONS = {
    "inflation": ("hotter than the previous reading", "would strengthen the case for interest rates staying high for longer, which yields would show first",
                  "cooler than the previous reading", "would ease pressure on yields; watch whether the dollar falls with them"),
    "employment": ("stronger than the previous reading", "would support the growth story but could push yields up",
                   "weaker than the previous reading", "would raise the odds of rate cuts, and the question of whether growth is slowing"),
    "fed": ("a firmer tone than expected", "would push short-term yields up first",
            "a softer tone", "would pull short-term yields down and could weaken the dollar"),
}


def _watch(evm: Dict[str, Dict[str, Any]], now: datetime) -> List[Dict[str, Any]]:
    rows = []
    for e in evm.values():
        if e.get("kind") == "calendar" and not (e.get("detail") or {}).get("released"):
            d = e.get("detail") or {}
            if d.get("impact") not in ("high", "medium") and "expiry" not in (e.get("label") or "").lower():
                continue
            cat = d.get("category") or ""
            cond = _CONDITIONS.get("inflation" if cat == "inflation" else "employment" if cat in ("employment", "labour", "labor")
                                   else "fed" if cat in ("fed", "policy", "central bank") else "", None)
            rows.append({"evidence": e["id"], "when": e.get("event_at"), "what": e.get("label"),
                         "previous": (e.get("compare") or {}).get("value"),
                         "previous_headline": (e.get("compare") or {}).get("headline"),
                         "if_up": cond and "If it comes in {}, that {}.".format(cond[0], cond[1]),
                         "if_down": cond and "If it comes in {}, that {}.".format(cond[2], cond[3])})
        if e.get("kind") == "earnings" and (e.get("detail") or {}).get("eps_reported") is None and e.get("event_at"):
            rows.append({"evidence": e["id"], "when": e.get("event_at"), "what": e.get("label"),
                         "previous": None, "if_up": None, "if_down": None})
    rows.sort(key=lambda r: r.get("when") or "")
    return rows[:8]


def build(bundle: Dict[str, Any], now: Optional[datetime] = None) -> Dict[str, Any]:
    now = now or datetime.fromisoformat(bundle.get("gathered_at"))
    evm = _ev(bundle)
    rows = list(evm.values())

    # Salient moves, by theme.
    moves = sorted([(salience(e), e) for e in rows if salience(e) > 0], key=lambda t: t[0], reverse=True)
    by_theme: Dict[str, List[Tuple[float, Dict[str, Any]]]] = {}
    for sc, e in moves:
        by_theme.setdefault(theme_of(e), []).append((sc, e))
    theme_score = {t: v[0][0] for t, v in by_theme.items()}

    earnings_done = [e for e in rows if e.get("kind") == "earnings" and (e.get("detail") or {}).get("eps_reported") is not None]
    if earnings_done:
        theme_score["earnings"] = max(theme_score.get("earnings", 0),
                                      1.0 + 0.5 * len(earnings_done)
                                      + max(abs((e.get("detail") or {}).get("reaction_pct") or 0) for e in earnings_done) / 2)
    news = relevant_news(rows)
    if news and (news[0].get("sources_in_cluster") or 1) >= 2:
        theme_score["news"] = max(theme_score.get("news", 0), 0.8 + 0.4 * (news[0].get("sources_in_cluster") or 1))

    watch = _watch(evm, now)
    soon = [w for w in watch if w.get("when") and _days_until(w["when"], now) <= 2
            and (evm.get(w["evidence"], {}).get("detail") or {}).get("impact") == "high"]

    ranked = sorted(theme_score.items(), key=lambda t: t[1], reverse=True)
    lead_theme = ranked[0][0] if ranked else "calendar"
    quiet = (ranked[0][1] if ranked else 0) < 1.3 and not earnings_done

    # Numbers that matter: most salient, one per theme, then the next big release.
    numbers: List[str] = []
    seen_theme = set()
    for sc, e in moves:
        t = theme_of(e)
        if t in seen_theme or sc < 0.8:
            continue
        seen_theme.add(t)
        numbers.append(e["id"])
        if len(numbers) >= 4:
            break
    for e in earnings_done[:2]:
        if len(numbers) < 6:
            numbers.append(e["id"])
    if soon and len(numbers) < 6:
        numbers.append(soon[0]["evidence"])
    for code in ("UNRATE", "CPIAUCSL"):
        if len(numbers) >= 3:
            break
        e = _get(evm, symbol=code)
        if e:
            numbers.append(e["id"])

    # Companies in focus: reported results, then the biggest named movers.
    companies = [e["id"] for e in earnings_done]
    movers = sorted([e for e in rows if e.get("kind") == "company"], key=salience, reverse=True)
    for e in movers:
        if salience(e) >= 1.5 and len(companies) < 5 and not any(evm[c].get("symbol") == e.get("symbol") for c in companies):
            companies.append(e["id"])
    sectors = sorted([e for e in rows if e.get("kind") == "sector"], key=lambda e: e.get("value") or 0)
    leaders = [e["id"] for e in sectors[::-1][:3]]
    laggards = [e["id"] for e in sectors[:3]]

    structure = [e["id"] for e in rows if e.get("kind") in ("index", "breadth", "volatility")]
    options = [e["id"] for e in rows if e.get("kind") == "options"]

    conflicts = [{"evidence": e["id"], **(e.get("detail") or {}).get("consensus_conflict", {})}
                 for e in earnings_done if (e.get("detail") or {}).get("consensus_conflict")]
    stale = [e["id"] for e in rows if e.get("stale")]
    failed = [c for c in bundle.get("coverage") or [] if not c.get("ok")]

    limits = [
        "Economic releases are compared with their own previous reading: Optic carries no consensus forecasts for them.",
        "Company results are EPS against the feed's consensus; reported revenue against its estimate and the text of guidance are not in the free data.",
        "Prices are about 15 minutes delayed during the session; close-to-close changes use the last daily bar.",
        "Options figures are Optic's estimates from delayed quotes; open interest is the previous session's.",
    ]
    if conflicts:
        limits.append("For {} the feed's two consensus figures disagree, so a beat or miss is not called.".format(
            ", ".join(evm[c["evidence"]].get("symbol") or "" for c in conflicts)))
    for f in failed:
        limits.append("Not available for this edition: {} ({}).".format(f.get("leg"), f.get("reason") or "failed"))

    return {
        "lead_theme": lead_theme,
        "theme_scores": {t: round(s, 2) for t, s in ranked},
        "quiet": quiet,
        "tension": soon[0] if soon else None,
        "numbers": numbers[:6],
        "relationships": relationships(evm),
        "companies": companies,
        "leaders": leaders,
        "laggards": laggards,
        "news": [e["id"] for e in news],
        "structure": structure,
        "options": options,
        "watch": watch,
        "conflicts": conflicts,
        "stale": stale,
        "limits": limits,
        "target_words": [350, 650] if quiet else [700, 1100],
    }


def _days_until(when: str, now: datetime) -> float:
    try:
        return (datetime.fromisoformat(when) - now).total_seconds() / 86400
    except (TypeError, ValueError):
        return 99.0


def evidence_for(bundle: Dict[str, Any], outline: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Only the evidence the outline uses, which is all the writer is shown."""
    want = set(outline["numbers"]) | set(outline["companies"]) | set(outline["leaders"]) | set(outline["laggards"]) \
        | set(outline["news"]) | set(outline["structure"]) | set(outline["options"]) \
        | {w["evidence"] for w in outline["watch"]}
    for r in outline["relationships"]:
        want |= set(r["evidence"])
    if outline.get("tension"):
        want.add(outline["tension"]["evidence"])
    for code in ("DGS2", "T10Y2Y", "CPIAUCSL", "PCEPILFE", "UNRATE", "PAYEMS", "ICSA", "BAMLH0A0HYM2", "DFF"):
        for e in bundle.get("evidence") or []:
            if e.get("symbol") == code:
                want.add(e["id"])
    for e in bundle.get("evidence") or []:
        if e.get("kind") in ("rates", "policy", "fx", "commodity", "credit"):
            want.add(e["id"])
    return [e for e in bundle.get("evidence") or [] if e["id"] in want]
