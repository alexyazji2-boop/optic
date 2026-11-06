"""One value for each registered figure, for one company, computed one way.

Every surface that shows one of these figures (the Dossier's tabs, Compare, Milo's tools) gets it from `resolve`, as a
value with its text already formatted, so two pages cannot round, date or define it differently. The definitions
live in `registry.py`; this module only computes.

**Where the statements come from.** The company's own SEC filings (XBRL company facts, us-gaap), read through
`app/valuation/inputs.py`, the same reader the valuation workspace and the research framework use: every input
carries its tag, period, form, filing date and a link to the filing, and a value a later filing changed is marked
restated. A company with no usable US-GAAP filings (a foreign issuer filing IFRS, a fund) falls back to Yahoo
Finance's statements, and every figure says so: provider Yahoo Finance, no filing link, restatement history
unavailable. Measured 2026-11-03: AAPL's fiscal 2026 10-K was filed that morning and Yahoo still carried fiscal 2025,
so a page reading Yahoo and a page reading the filings disagreed by a year. One source per company ends that.

**A figure that cannot be computed says why, and is never zero.** `status` is ok, not_reported (the source has no
such line), not_meaningful (a negative denominator, a loss on estimates) or unavailable (the source did not answer).
"""

from __future__ import annotations

import logging
import math
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple

from ..valuation import inputs as vi
from . import periods as periods_mod
from .registry import IDS, REGISTRY, VERSION

log = logging.getLogger("optic")

MINUS = "−"
_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
STATUS_TEXT = {"not_reported": "Not reported", "not_meaningful": "Not meaningful",
               "unavailable": "Temporarily unavailable"}
SEC_NAME = "SEC EDGAR, XBRL company facts (us-gaap)"
YAHOO_NAME = "Yahoo Finance statements"
# A Yahoo year this much newer than the filings' latest means the filings stopped (a company now filing under a new
# holding company's CIK, which app/valuation/inputs.py does not join), so the newer statements win.
STALE_FILINGS_DAYS = 300


# ------------------------------------------------------------------------------------------------ formatting
def _num(v: Any) -> Optional[float]:
    try:
        out = float(v)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def date_words(iso: Any) -> str:
    """"Sep 26, 2026", the client's fullDate()."""
    try:
        d = date.fromisoformat(str(iso)[:10])
    except ValueError:
        return str(iso or "")
    return "{} {}, {}".format(_MONTHS[d.month - 1], d.day, d.year)


def _fixed(v: float, dp: int) -> str:
    s = "{:,.{dp}f}".format(abs(v), dp=dp)
    return (MINUS if v < 0 and float(s.replace(",", "")) != 0 else "") + s


def money_text(v: float, ccy: str = "USD") -> str:
    """The client's compact(): two places in trillions, one in billions, millions and thousands."""
    a = abs(v)
    if a >= 1e12 or round(a / 1e9, 1) >= 1000:
        body = "{:.2f}T".format(a / 1e12)
    elif a >= 1e9 or round(a / 1e6, 1) >= 1000:
        body = "{:.1f}B".format(a / 1e9)
    elif a >= 1e6 or round(a / 1e3, 1) >= 1000:
        body = "{:.1f}M".format(a / 1e6)
    elif a >= 1e3:
        body = "{:.1f}K".format(a / 1e3)
    else:
        body = "{:,.0f}".format(a)
    sign = MINUS if v < 0 and body.strip("0.KMBT,") else ""
    return "{}{}{}".format(sign, "$" if (ccy or "USD").upper() == "USD" else (ccy.upper() + " "), body)


def text_for(unit: str, value: float, ccy: str = "USD") -> str:
    if unit == "percent":
        return _fixed(value, 1) + "%"
    if unit == "multiple":
        return _fixed(value, 1)
    return money_text(value, ccy)


# ------------------------------------------------------------------------------------------------ building blocks
def _input(key: str, name: str, f: Optional[Dict[str, Any]], ccy: str = "USD", line: Optional[str] = None,
           note: Optional[str] = None) -> Dict[str, Any]:
    """One input as the definition panel lists it: its value, the line it was read from and where it was filed."""
    f = f or {}
    v = _num(f.get("value"))
    out = {"key": key, "name": name, "value": v, "text": money_text(v, ccy) if v is not None else "Not reported",
           "line": line or f.get("tag") or f.get("rule"), "start": f.get("start"), "end": f.get("end"),
           "form": f.get("form"), "filed": f.get("filed"), "url": f.get("url")}
    if f.get("kind") == "not_reported":
        out["text"] = "None reported"
    words = note or f.get("note") or f.get("reason")
    if words:
        out["note"] = words
    r = _restated(f)
    if r:
        out["restated"] = r
    return {k: v for k, v in out.items() if v is not None}


def _restated(f: Optional[Dict[str, Any]], signs: Optional[Sequence[int]] = None) -> Optional[Dict[str, Any]]:
    """{"on", "prior"} when a later filing changed this value, with the value before it; {"on": None} when a later
    filing changed it and the earlier value cannot be rebuilt; None when no filing changed it.

    A derived value (debt, a twelve-month total) is restated when one of its parts is; its prior value is rebuilt
    from the parts' prior values with the rule's own signs (a twelve-month total subtracts its third part)."""
    if not f or not f.get("restated"):
        return None
    if f.get("kind") == "derived":
        parts = f.get("parts") or []
        signs = list(signs or [1] * len(parts))
        if len(signs) != len(parts) or any(p.get("restated") and _num(p.get("prior_value")) is None for p in parts):
            return {"on": max((p.get("restated_on") or "" for p in parts), default="") or None, "prior": None}
        prior = sum(s * (_num(p["prior_value"]) if p.get("restated") else (_num(p.get("value")) or 0.0))
                    for s, p in zip(signs, parts))
        on = max((p.get("restated_on") or "" for p in parts if p.get("restated")), default="") or None
        return {"on": on, "prior": prior}
    return {"on": f.get("restated_on"), "prior": _num(f.get("prior_value"))}


def _fig(fid: str, value: Optional[float] = None, *, status: str = "ok", why: Optional[str] = None,
         period: Optional[Dict[str, Any]] = None, inputs: Optional[List[Dict[str, Any]]] = None,
         source: Optional[Dict[str, Any]] = None, restated: Optional[Dict[str, Any]] = None,
         restatement: str = "checked", ccy: str = "USD", as_of: Optional[str] = None,
         note: Optional[str] = None) -> Dict[str, Any]:
    e = REGISTRY[fid]
    if status == "ok" and value is None:
        status = "not_reported"
    out: Dict[str, Any] = {"id": fid, "name": e["name"], "status": status, "value": value if status == "ok" else None,
                           "text": text_for(e["unit"], value, ccy) if status == "ok" else STATUS_TEXT[status],
                           "unit": e["unit"], "currency": ccy, "period": period or {"type": e["period"]},
                           "as_of": as_of or (period or {}).get("end"), "inputs": inputs or [],
                           "source": source or {}, "restatement": restatement}
    if why:
        out["why"] = why
    if note:
        out["note"] = note
    if restated:
        prior = restated.get("prior")
        out["restated"] = {"on": restated.get("on"), "prior": prior,
                           "prior_text": text_for(e["unit"], prior, ccy) if prior is not None else None}
    return out


def _missing(fid: str, status: str, why: str, **kw: Any) -> Dict[str, Any]:
    return _fig(fid, None, status=status, why=why, **kw)


def _sec_source(*facts: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """The filing a figure came from: the latest filed of its inputs (they are normally one 10-K or 10-Q)."""
    # a reported fact names its form; a derived total (debt) names none, so it reads "SEC EDGAR" rather than "10-K"
    used = [f for f in facts if f and (f.get("filed") or f.get("url"))]
    best = max(used, key=lambda f: (bool(f.get("form")), f.get("filed") or ""), default={})
    return {"provider": "SEC EDGAR", "name": SEC_NAME, "form": best.get("form"), "filed": best.get("filed"),
            "url": best.get("url"), "retrieved": best.get("retrieved")}


def _yahoo_source() -> Dict[str, Any]:
    return {"provider": "Yahoo Finance", "name": YAHOO_NAME, "url": None,
            "note": "Filing link unavailable: the provider does not link its statement figures to filings."}


def _ratio_restated(n: Dict[str, Any], d: Dict[str, Any], scale: float = 100.0,
                    signs: Tuple[Optional[Sequence[int]], Optional[Sequence[int]]] = (None, None)) -> Optional[Dict[str, Any]]:
    rn, rd = _restated(n, signs[0]), _restated(d, signs[1])
    if not rn and not rd:
        return None
    on = max((r.get("on") or "" for r in (rn, rd) if r), default="") or None
    pn = (rn or {}).get("prior") if rn else _num(n.get("value"))
    pd = (rd or {}).get("prior") if rd else _num(d.get("value"))
    if pn is None or pd in (None, 0) or pd < 0:
        return {"on": on, "prior": None}
    return {"on": on, "prior": pn / pd * scale}


# ------------------------------------------------------------------------------------------------ periods
def _annual_period(start: Optional[str], end: str, dated_by: Optional[str] = None) -> Dict[str, Any]:
    out = {"type": "annual", "start": start, "end": end, "label": "Fiscal year ended {}".format(date_words(end)),
           "short": "Year to {}".format(date_words(end))}
    if dated_by:
        out["note"] = dated_by
    return out


def _quarter_ends(fl: "vi.Filings", tag: Optional[str], end: str) -> List[str]:
    """The four reporting periods ending on or before `end`, from the dates the filings report revenue on: every
    10-Q period ends on a quarter end and every 10-K on a year end, so the distinct end dates are the quarters."""
    if not tag:
        return []
    ends = sorted({r["end"] for r in fl._rows(tag, "USD")                                   # noqa: SLF001
                   if r.get("form") in vi.ANY_FORMS and r.get("start") and r.get("end")
                   and _within(vi._days(r["end"], end), 0, 370)}, reverse=True)                # noqa: SLF001
    out: List[str] = []
    for e in ends:
        if not out or (vi._days(e, out[-1]) or 0) > 45:                                    # noqa: SLF001
            out.append(e)
    return out[:4] if len(out) >= 4 else []


def _within(days: Optional[int], lo: int, hi: int) -> bool:
    """`days` in [lo, hi]. Zero days is a match: written `days or -1` it is not, and the quarter ending on the
    twelve months' own last day dropped out of the list (0 is falsy; tests/test_valuation_inputs.py has the same
    regression for an instant)."""
    return days is not None and lo <= days <= hi


def _ttm_period(end: str, quarters: List[str], detail: str) -> Dict[str, Any]:
    out = {"type": "ttm", "end": end, "label": "12 months to {}".format(date_words(end)),
           "short": "12 months to {}".format(date_words(end)), "detail": detail}
    if quarters:
        out["quarters"] = sorted(quarters)
        out["quarters_text"] = "The four quarters ended {}.".format(_join([date_words(q) for q in sorted(quarters)]))
    return out


def _balance_period(on: str, dated_by: Optional[str] = None) -> Dict[str, Any]:
    out = {"type": "balance", "end": on, "label": "On {}".format(date_words(on)), "short": date_words(on)}
    if dated_by:
        out["note"] = dated_by
    return out


def _join(items: List[str]) -> str:
    return items[0] if len(items) == 1 else "{} and {}".format(", ".join(items[:-1]), items[-1])


# ------------------------------------------------------------------------------------------------ net debt, once
def net_debt_value(balance: Dict[str, Any]) -> Optional[float]:
    """Borrowings plus finance leases, less cash and short-term investments, on one balance sheet.

    The research framework's balance-sheet check (app/research/quality.py) reads its net debt from here too, so the
    figure the check describes is the figure the Dossier prints. None when no cash balance is tagged: a net
    position without the cash side is not one."""
    cash = vi._v(balance.get("cash"))                                                       # noqa: SLF001
    if cash is None:
        return None
    return ((vi._v(balance.get("debt")) or 0.0) + (vi._v(balance.get("finance_leases")) or 0.0)    # noqa: SLF001
            - cash - (vi._v(balance.get("short_term_investments")) or 0.0))                # noqa: SLF001


# ------------------------------------------------------------------------------------------------ from the filings
def _from_filings(fl: "vi.Filings", fy_ends: List[str]) -> Dict[str, Dict[str, Any]]:
    fy0 = fy_ends[0]
    flows = {c: fl.flow(c, fy0) for c in ("revenue", "net_income", "cfo", "capex", "operating_income")}
    bal_date = vi.latest_balance_date(fl, fy0)
    bal = vi.balance_sheet(fl, bal_date)
    ttm = vi.trailing(fl, [{"fy_end": fy0, "flows": flows}], bal_date)
    rev_tag = (flows.get("revenue") or {}).get("tag")
    out: Dict[str, Dict[str, Any]] = {}

    # ---- one fiscal year
    rev, ni, cfo, capex = flows["revenue"], flows["net_income"], flows["cfo"], flows["capex"]
    start = next((f.get("start") for f in (rev, ni, cfo) if f and f.get("start")), None)
    per = _annual_period(start, fy0)
    out["net_margin_fy"] = _net_margin("net_margin_fy", rev, ni, per, _sec_source(rev, ni))
    out["operating_cash_flow_fy"] = _ocf("operating_cash_flow_fy", cfo, per)
    out["free_cash_flow_fy"] = _fcf("free_cash_flow_fy", cfo, capex, per)

    # ---- twelve months
    since = vi._days(fy0, bal_date) or 0                                                   # noqa: SLF001
    if ttm.get("available"):
        end = ttm["period_end"]
        vals = ttm["values"]
        per_t = _ttm_period(end, _quarter_ends(fl, rev_tag, end),
                            "Fiscal year ended {} plus this fiscal year to {}, less the same months a year "
                            "earlier.".format(date_words(fy0), date_words(end)))
        t = {c: (vals.get(c) if (vals.get(c) or {}).get("value") is not None else None) for c in ("revenue", "net_income", "cfo", "capex")}
        miss = {c: (vals.get(c) or {}).get("reason") for c in t if t[c] is None}
        out["net_margin_ttm"] = _net_margin("net_margin_ttm", t["revenue"], t["net_income"], per_t,
                                            _sec_source(t["revenue"], t["net_income"]), ttm=True,
                                            why_missing=miss.get("revenue") or miss.get("net_income"))
        out["operating_cash_flow_ttm"] = _ocf("operating_cash_flow_ttm", t["cfo"], per_t, ttm=True,
                                              why_missing=miss.get("cfo"))
        out["free_cash_flow_ttm"] = _fcf("free_cash_flow_ttm", t["cfo"], t["capex"], per_t, ttm=True,
                                         why_missing=miss.get("cfo") or miss.get("capex"))
    elif since < 60:
        # no quarter since the 10-K: the last twelve months are the fiscal year, and the label says so
        per_t = _ttm_period(fy0, _quarter_ends(fl, rev_tag, fy0),
                            "The fiscal year ended {}: no quarter has been reported since.".format(date_words(fy0)))
        out["net_margin_ttm"] = _net_margin("net_margin_ttm", rev, ni, per_t, _sec_source(rev, ni))
        out["operating_cash_flow_ttm"] = _ocf("operating_cash_flow_ttm", cfo, per_t)
        out["free_cash_flow_ttm"] = _fcf("free_cash_flow_ttm", cfo, capex, per_t)
    else:
        why = "The twelve months could not be built from the filings: {}".format(
            str(ttm.get("reason") or "a quarterly figure is missing").rstrip(".") + ".")
        for fid in ("net_margin_ttm", "operating_cash_flow_ttm", "free_cash_flow_ttm"):
            out[fid] = _missing(fid, "not_reported", why, source=_sec_source())

    # ---- the balance sheet
    out.update(_net_debts(bal, bal_date))
    return out


def _net_margin(fid: str, rev: Optional[Dict[str, Any]], ni: Optional[Dict[str, Any]], per: Dict[str, Any],
                source: Dict[str, Any], ttm: bool = False, why_missing: Optional[str] = None,
                restatement: str = "checked") -> Dict[str, Any]:
    ins = [_input("net_income", "Net income attributable to the company", ni),
           _input("revenue", "Total revenue", rev)]
    if rev is None or ni is None or _num(rev.get("value")) is None or _num(ni.get("value")) is None:
        which = "revenue" if (rev is None or _num((rev or {}).get("value")) is None) else "net income"
        return _missing(fid, "not_reported", why_missing or "The source reports no {} for this period.".format(which),
                        period=per, inputs=ins, source=source, restatement=restatement)
    r, n = _num(rev["value"]), _num(ni["value"])
    if r <= 0:
        return _missing(fid, "not_meaningful", "Revenue was zero or negative, so a margin on it has no meaning.",
                        period=per, inputs=ins, source=source, restatement=restatement)
    signs = (1, 1, -1) if ttm else None
    return _fig(fid, n / r * 100.0, period=per, inputs=ins, source=source, restatement=restatement,
                restated=_ratio_restated(ni, rev, signs=(signs, signs)) if restatement == "checked" else None)


def _ocf(fid: str, cfo: Optional[Dict[str, Any]], per: Dict[str, Any], ttm: bool = False,
         why_missing: Optional[str] = None, source: Optional[Dict[str, Any]] = None,
         restatement: str = "checked", ccy: str = "USD") -> Dict[str, Any]:
    ins = [_input("cfo", "Net cash provided by operating activities", cfo, ccy)]
    src = source or _sec_source(cfo)
    if cfo is None or _num(cfo.get("value")) is None:
        return _missing(fid, "not_reported", why_missing or "The source reports no operating cash flow for this "
                                                            "period.", period=per, inputs=ins, source=src,
                        restatement=restatement, ccy=ccy)
    return _fig(fid, _num(cfo["value"]), period=per, inputs=ins, source=src, restatement=restatement, ccy=ccy,
                restated=_restated(cfo, (1, 1, -1) if ttm else None) if restatement == "checked" else None)


def _fcf(fid: str, cfo: Optional[Dict[str, Any]], capex: Optional[Dict[str, Any]], per: Dict[str, Any],
         ttm: bool = False, why_missing: Optional[str] = None, source: Optional[Dict[str, Any]] = None,
         restatement: str = "checked", ccy: str = "USD") -> Dict[str, Any]:
    # capital expenditure as the money spent, a positive amount: the filings tag it so, while the provider's statement
    # carries it as a negative cash flow, which beside "operating cash flow minus capital expenditure" reads as a sign
    # error in the panel
    spent = dict(capex, value=abs(_num(capex.get("value")))) if capex and _num(capex.get("value")) is not None else capex
    ins = [_input("cfo", "Operating cash flow", cfo, ccy),
           _input("capex", "Capital expenditure (purchases of property and equipment)", spent, ccy)]
    src = source or _sec_source(cfo, capex)
    if cfo is None or capex is None or _num(cfo.get("value")) is None or _num(capex.get("value")) is None:
        which = "operating cash flow" if (cfo is None or _num((cfo or {}).get("value")) is None) else "capital expenditure"
        return _missing(fid, "not_reported", why_missing or "The source reports no {} for this period, and a "
                                                            "missing line is not taken as zero.".format(which),
                        period=per, inputs=ins, source=src, restatement=restatement, ccy=ccy)
    c, k = _num(cfo["value"]), abs(_num(capex["value"]))
    restated = None
    if restatement == "checked":
        signs = (1, 1, -1) if ttm else None
        rc, rk = _restated(cfo, signs), _restated(capex, signs)
        if rc or rk:
            pc = rc["prior"] if rc else c
            pk = abs(rk["prior"]) if rk and rk.get("prior") is not None else (None if rk else k)
            on = max((r.get("on") or "" for r in (rc, rk) if r), default="") or None
            restated = {"on": on, "prior": (pc - pk) if (pc is not None and pk is not None) else None}
    return _fig(fid, c - k, period=per, inputs=ins, source=src, restatement=restatement, ccy=ccy, restated=restated)


def _net_debts(bal: Dict[str, Any], on: str) -> Dict[str, Dict[str, Any]]:
    per = _balance_period(on)
    debt, fl_, cash, sti = bal.get("debt"), bal.get("finance_leases"), bal.get("cash"), bal.get("short_term_investments")
    ins = [_input("debt", "Borrowings", debt, line=(debt or {}).get("rule")),
           _input("finance_leases", "Finance lease liabilities", fl_),
           _input("cash", "Cash and cash equivalents", cash),
           _input("short_term_investments", "Short-term investments", sti)]
    src = _sec_source(debt, cash, sti, *((debt or {}).get("parts") or []))
    nd = net_debt_value(bal)
    out: Dict[str, Dict[str, Any]] = {}
    if nd is None:
        out["net_debt"] = _missing("net_debt", "not_reported", "No cash balance is tagged on this date, so a net "
                                                               "position cannot be worked out.",
                                   period=per, inputs=ins, source=src)
    else:
        parts = [debt, fl_, cash, sti]
        rs = [_restated(p) for p in parts]
        restated = None
        if any(rs):
            if any(r and r.get("prior") is None for r in rs):
                restated = {"on": max((r.get("on") or "" for r in rs if r), default="") or None, "prior": None}
            else:
                vals = [(r["prior"] if r else (vi._v(p) or 0.0)) for r, p in zip(rs, parts)]    # noqa: SLF001
                restated = {"on": max((r.get("on") or "" for r in rs if r), default="") or None,
                            "prior": vals[0] + vals[1] - vals[2] - vals[3]}
        out["net_debt"] = _fig("net_debt", nd, period=per, inputs=ins, source=src, restated=restated,
                               note="Negative means net cash." if nd < 0 else None)
    op = bal.get("operating_lease")
    ins_l = [{"key": "net_debt", "name": "Net debt", "value": nd,
              "text": money_text(nd) if nd is not None else "Not reported"},
             _input("operating_lease", "Operating lease liabilities", op)]
    if nd is None:
        out["net_debt_with_leases"] = _missing("net_debt_with_leases", "not_reported", "Net debt itself is not "
                                               "reported on this date.", period=per, inputs=ins_l, source=src)
    elif op is None or _num(op.get("value")) is None:
        out["net_debt_with_leases"] = _missing("net_debt_with_leases", "not_reported", "No total operating lease "
                                               "liability is tagged on this date.", period=per, inputs=ins_l,
                                               source=src)
    else:
        # restated when net debt's inputs or the lease liability were: the earlier total from the earlier parts
        rn, ro = (out["net_debt"].get("restated") or None), _restated(op)
        restated = None
        if rn or ro:
            pn = rn.get("prior") if rn else nd
            po = ro.get("prior") if ro else _num(op["value"])
            restated = {"on": max((r.get("on") or "" for r in (rn, ro) if r), default="") or None,
                        "prior": (pn + po) if (pn is not None and po is not None) else None}
        out["net_debt_with_leases"] = _fig("net_debt_with_leases", nd + _num(op["value"]), period=per,
                                           inputs=ins_l, source=_sec_source(op, debt, cash), restated=restated)
    return out


# ------------------------------------------------------------------------------------------------ from Yahoo
def _yfact(series: Any, i: int, end: Optional[str], line: str) -> Optional[Dict[str, Any]]:
    v = _num((series or [None] * (i + 1))[i] if len(series or []) > i else None)
    return None if v is None else {"value": v, "end": end, "tag": line}


def _from_yahoo(fin: Dict[str, Any], ccy: str) -> Dict[str, Dict[str, Any]]:
    """The same formulas over Yahoo Finance's statements, for a company the filings cannot cover."""
    out: Dict[str, Dict[str, Any]] = {}
    src = _yahoo_source()
    kw = {"restatement": "unavailable"}
    a, q = fin.get("annual") or {}, fin.get("quarterly") or {}
    ap, qp = fin.get("annual_periods") or [], fin.get("quarterly_periods") or []
    dated = "Dated as the provider dates it; the company's own year can end a few days earlier."
    if ap:
        per = _annual_period(None, ap[0], dated)
        rev, ni = _yfact(a.get("revenue"), 0, ap[0], "Total Revenue"), _yfact(a.get("net_income"), 0, ap[0], "Net Income")
        cfo = _yfact(a.get("operating_cash_flow"), 0, ap[0], "Operating Cash Flow")
        capex = _yfact(a.get("capital_expenditure"), 0, ap[0], "Capital Expenditure")
        out["net_margin_fy"] = _net_margin("net_margin_fy", rev, ni, per, src, **kw)
        out["operating_cash_flow_fy"] = _ocf("operating_cash_flow_fy", cfo, per, source=src, ccy=ccy, **kw)
        out["free_cash_flow_fy"] = _fcf("free_cash_flow_fy", cfo, capex, per, source=src, ccy=ccy, **kw)
    else:
        for fid in ("net_margin_fy", "operating_cash_flow_fy", "free_cash_flow_fy"):
            out[fid] = _missing(fid, "not_reported", "The statements carry no fiscal year.", source=src, **kw)
    # twelve months: the four newest quarters of the income statement, added up and listed
    qr, qn = (q.get("revenue") or [])[:4], (q.get("net_income") or [])[:4]
    if len(qp) >= 4 and len(qr) == 4 and len(qn) == 4 and all(_num(x) is not None for x in qr + qn):
        quarters = list(qp[:4])
        per_t = _ttm_period(quarters[0], quarters, "The four newest quarters on the provider's income statement, "
                                                    "added together.")
        rev_t = {"value": sum(_num(x) for x in qr), "end": quarters[0], "tag": "Total Revenue, 4 quarters"}
        ni_t = {"value": sum(_num(x) for x in qn), "end": quarters[0], "tag": "Net Income, 4 quarters"}
        out["net_margin_ttm"] = _net_margin("net_margin_ttm", rev_t, ni_t, per_t, src, **kw)
    else:
        out["net_margin_ttm"] = _missing("net_margin_ttm", "not_reported", "Fewer than four quarters of revenue "
                                         "and net income are available from the provider.", source=src, **kw)
    why = "The fallback source, the provider's statements, carries no quarterly cash flow here."
    out["operating_cash_flow_ttm"] = _missing("operating_cash_flow_ttm", "not_reported", why, source=src, **kw)
    out["free_cash_flow_ttm"] = _missing("free_cash_flow_ttm", "not_reported", why, source=src, **kw)
    bs = fin.get("balance_sheet") or {}
    on = ap[0] if ap else None
    debt, liquid = _num(bs.get("total_debt")), _num(bs.get("cash_and_short_term"))
    cash_only = _num(bs.get("cash"))
    if on and debt is not None and (liquid is not None or cash_only is not None):
        held = liquid if liquid is not None else cash_only
        ins = [{"key": "debt", "name": "Borrowings (the provider's Total Debt line)", "value": debt,
                "text": money_text(debt, ccy), "line": "Total Debt", "end": on,
                "note": "The provider does not say whether its total-debt line includes lease liabilities."},
               {"key": "cash", "name": "Cash, cash equivalents and short-term investments" if liquid is not None
                else "Cash and cash equivalents", "value": held, "text": money_text(held, ccy), "end": on,
                "line": "Cash Cash Equivalents And Short Term Investments" if liquid is not None
                else "Cash And Cash Equivalents"}]
        if liquid is None:
            ins.append({"key": "short_term_investments", "name": "Short-term investments", "value": None,
                        "text": "None reported", "note": "Not reported by the provider; treated as none."})
        nd = debt - held
        out["net_debt"] = _fig("net_debt", nd, period=_balance_period(on, dated), inputs=ins, source=src, ccy=ccy,
                               note="Negative means net cash." if nd < 0 else None, **kw)
    else:
        out["net_debt"] = _missing("net_debt", "not_reported", "The provider's balance sheet carries no debt or "
                                   "cash line.", source=src, **kw)
    out["net_debt_with_leases"] = _missing("net_debt_with_leases", "not_reported", "The fallback source does not "
                                           "separate operating lease liabilities.", source=src, **kw)
    return out


# ------------------------------------------------------------------------------------------------ forward P/E
def forward_pe(quote: Dict[str, Any]) -> Dict[str, Any]:
    """The share price on the page over the feed's forward EPS: the price every surface already shows, so the
    ratio cannot be from another minute's price. Compare's ran on a long-term model cached hours earlier and read
    30.9 against the Dossier's 31.2 for AAPL (authenticated audit, 2026-11-03)."""
    q = quote or {}
    price, eps = _num(q.get("price")), _num(q.get("forward_eps"))
    ccy, fccy = str(q.get("currency") or "USD").upper(), str(q.get("financial_currency") or q.get("currency") or "USD").upper()
    stamp = q.get("trade_time") or q.get("as_of")
    realtime = str(q.get("quote_source") or "").startswith("tradier (real-time)")
    src = {"provider": "Yahoo Finance", "name": "Yahoo Finance quote and analysts' consensus",
           "url": None, "retrieved": q.get("as_of"),
           "note": "Which fiscal year the forward EPS covers, and whether it is adjusted, are not disclosed by the "
                   "provider."}
    per = {"type": "forward", "end": None, "label": "Price at {}".format(_when(stamp)) if stamp else "Latest price",
           "short": "Forward estimate", "fiscal_year": "Not disclosed by the provider"}
    ins = [{"key": "price", "name": "Share price" + (" (real-time, Tradier)" if realtime else ""), "value": price,
            "text": _price_text(price, ccy), "end": stamp, "line": "price"},
           {"key": "forward_eps", "name": "Forward EPS, analysts' average estimate", "value": eps,
            "text": _price_text(eps, fccy if fccy != ccy else ccy), "line": "forwardEps"}]
    if price is None:
        return _missing("forward_pe", "unavailable", "The quote feed returned no price just now.", period=per,
                        inputs=ins, source=src, restatement="not_applicable", ccy=ccy)
    if fccy != ccy:
        # a foreign listing: the feed's EPS may be in the reporting currency, so the provider's own ratio is shown,
        # said to be the provider's, rather than one currency divided into another here
        given = _num(q.get("forward_pe"))
        if given is None:
            return _missing("forward_pe", "not_reported", "The feed carries no forward P/E for this listing.",
                            period=per, inputs=ins, source=src, restatement="not_applicable", ccy=ccy)
        return _fig("forward_pe", given, period=per, inputs=ins, source=dict(src, note=(
            "The provider's own forward P/E: the company reports in {} and the shares trade in {}, and the provider "
            "does not state the currency of its EPS, so Optic does not divide one into the other.".format(fccy, ccy))),
            restatement="not_applicable", ccy=ccy, as_of=stamp)
    if eps is None:
        return _missing("forward_pe", "not_reported", "The quote feed carries no analysts' forward EPS for this "
                        "company.", period=per, inputs=ins, source=src, restatement="not_applicable", ccy=ccy)
    if eps <= 0:
        return _missing("forward_pe", "not_meaningful", "Analysts expect a loss per share, so a price-to-earnings "
                        "ratio has no meaning.", period=per, inputs=ins, source=src, restatement="not_applicable",
                        ccy=ccy)
    return _fig("forward_pe", price / eps, period=per, inputs=ins, source=src, restatement="not_applicable",
                ccy=ccy, as_of=stamp)


def _price_text(v: Optional[float], ccy: str) -> str:
    if v is None:
        return "Not reported"
    return "{}{}{:,.2f}".format(MINUS if v < 0 else "", "$" if ccy == "USD" else ccy + " ", abs(v))


def _when(stamp: Any) -> str:
    try:
        from zoneinfo import ZoneInfo
        t = datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
        if t.tzinfo is None:
            return str(stamp)
        local = t.astimezone(ZoneInfo("America/New_York"))
        return "{}, {} ET".format(date_words(local.date().isoformat()), local.strftime("%I:%M %p").lstrip("0"))
    except (ValueError, ImportError):
        return str(stamp)


# ------------------------------------------------------------------------------------------------ the entry points
def load(ticker: str) -> Tuple[Optional["vi.Filings"], Optional[str], Optional[str]]:
    """The company's filings, as the snapshot's own leg; never raises (a missing filing set is a fallback)."""
    try:
        return vi.load_filings((ticker or "").upper().strip())
    except Exception as exc:                                                               # noqa: BLE001
        return None, None, "EDGAR could not be read ({}).".format(type(exc).__name__)


def load_via(provider: Any, ticker: str) -> Tuple[Optional["vi.Filings"], Optional[str], Optional[str]]:
    """The filings through the data provider, as every outside source is reached here: a stub provider in a test has
    no `sec_filings` and so reaches no network (tests/conftest.py fails a test whose request escapes its stub; the
    long-term model's first call to EDGAR did, 2026-11-03)."""
    fn = getattr(provider, "sec_filings", None)
    if not callable(fn):
        return None, None, "This data source does not read SEC filings."
    try:
        return fn((ticker or "").upper().strip())
    except Exception as exc:                                                               # noqa: BLE001
        return None, None, "EDGAR could not be read ({}).".format(type(exc).__name__)


def resolve(ticker: str, quote: Optional[Dict[str, Any]], *,
            sec: Optional[Tuple[Optional["vi.Filings"], Optional[str], Optional[str]]] = None,
            financials: Optional[Dict[str, Any]] = None, now: Optional[datetime] = None) -> Dict[str, Any]:
    """Every registered figure for one company. `sec` is load()'s answer; `financials` is the fundamentals block's
    statements (app/analytics/fundamentals.py analyse_financials), read only when the filings cannot be."""
    sym = (ticker or "").upper().strip()
    q = quote or {}
    ccy = str(q.get("financial_currency") or q.get("currency") or "USD").upper()
    figs: Dict[str, Dict[str, Any]] = {"forward_pe": forward_pe(q)}
    qtype = str(q.get("quote_type") or "").upper()
    fl, _cik, sec_reason = sec if sec is not None else (None, None, "not requested")
    fy_ends = fl.fiscal_year_ends() if fl is not None else []
    fin = financials if isinstance(financials, dict) and financials.get("available") else None
    used: Optional[Dict[str, Any]] = None
    if qtype and qtype != "EQUITY":
        why = "{} is not a company, so it reports no statements of its own.".format(sym)
        for fid in IDS:
            if fid != "forward_pe":
                figs[fid] = _missing(fid, "not_reported", why)
    else:
        yahoo_end = (fin or {}).get("annual_periods", [None])[0] if fin else None
        stale = bool(fy_ends and yahoo_end and (vi._days(fy_ends[0], yahoo_end) or 0) >= STALE_FILINGS_DAYS)  # noqa: SLF001
        if fy_ends and not stale:
            try:
                figs.update(_from_filings(fl, fy_ends))
                used = {"provider": "SEC EDGAR", "name": SEC_NAME, "cik": _cik}
            except Exception as exc:                                                       # noqa: BLE001
                log.warning("figures: filings for %s did not resolve: %s", sym, exc)
                fy_ends = []
        if used is None and fin:
            figs.update(_from_yahoo(fin, ccy))
            used = {"provider": "Yahoo Finance", "name": YAHOO_NAME,
                    "why": ("The filings stop at {}, earlier than the provider's statements.".format(date_words(fy_ends[0]))
                            if stale else sec_reason or ("The filings carry no US-GAAP fiscal year in US dollars "
                                                          "(a foreign issuer's IFRS report, for one)."))}
        if used is None:
            why = sec_reason or "Neither the filings nor the provider's statements answered."
            for fid in IDS:
                if fid not in figs:
                    figs[fid] = _missing(fid, "unavailable", why)
    # the company's fiscal calendar from the same filings (Handoff 2): every figure's period and every column of the
    # provider's statements, named as the company names it and dated as it was filed
    cal = periods_mod.calendar(fl) if fl is not None else {"available": False, "reason": sec_reason or periods_mod.UNAVAILABLE}
    _name_periods(figs, cal)
    return {"ticker": sym, "version": VERSION, "available": True, "statement_source": used,
            "generated_at": (now or datetime.now(timezone.utc)).isoformat(timespec="seconds"),
            "figures": {fid: figs[fid] for fid in IDS},
            "periods": {"calendar": periods_mod.public(cal), "statements": periods_mod.for_statements(cal, fin)}}


def _name_periods(figs: Dict[str, Dict[str, Any]], cal: Dict[str, Any]) -> None:
    """Each figure's period with its badge, and a fiscal year's name and length as the filings give them."""
    for fv in figs.values():
        per = fv.get("period")
        if not isinstance(per, dict):
            continue
        kind = per.get("type")
        per.setdefault("badge", periods_mod.BADGES.get(kind) or ("Forward estimate" if kind == "forward" else None))
        if kind == "annual" and per.get("end"):
            d = periods_mod.describe(cal, per["end"], "annual")
            if d.get("short"):
                per["fiscal"] = d["short"]
            if d.get("weeks"):
                per["weeks"] = d["weeks"]
                if d.get("note") and not per.get("note"):
                    per["note"] = d["note"]


def for_ticker(provider: Any, ticker: str, yf_provider: Any = None, quote: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """resolve() for a caller that has nothing loaded yet (Milo's tools, the long-term model, /api/figures)."""
    sym = (ticker or "").upper().strip()
    q = quote
    if q is None:
        try:
            q = provider.quote(sym) or {}
        except Exception:                                                                  # noqa: BLE001
            q = {}
    yf = yf_provider or provider
    sec = load_via(yf, sym)
    fin = None
    try:
        from ..analytics import fundamentals as fundamentals_mod
        raw = yf.financials(sym) if hasattr(yf, "financials") else None
        fin = fundamentals_mod.analyse_financials(raw) if raw else None
    except Exception:                                                                      # noqa: BLE001
        fin = None
    return resolve(sym, q, sec=sec, financials=fin)


def unavailable(ticker: str, why: str) -> Dict[str, Any]:
    """The whole block when resolving failed: every figure says so, and none is shown from somewhere else."""
    return {"ticker": (ticker or "").upper(), "version": VERSION, "available": False, "reason": why,
            "figures": {fid: _missing(fid, "unavailable", why) for fid in IDS},
            "periods": {"calendar": {"available": False, "reason": why},
                        "statements": {"annual": [], "quarterly": [], "basis": None, "dated_by": "unavailable"}}}


def compact(block: Dict[str, Any], ids: Optional[Sequence[str]] = None) -> Dict[str, Dict[str, Any]]:
    """The figures as Milo's tools carry them, keyed "AAPL net_margin_fy": the value's text, its period and its
    source, and the id that links the answer's sources to the same definition the Dossier opens. A dict, because a
    tool result's lists are cut to fit (milo_tools.fit) and a figure must not be the one cut."""
    sym = str((block or {}).get("ticker") or "").upper()
    figs = (block or {}).get("figures") or {}
    out: Dict[str, Dict[str, Any]] = {}
    for fid in (ids or IDS):
        fv = figs.get(fid)
        if not fv:
            continue
        per = fv.get("period") or {}
        src = fv.get("source") or {}
        # the period with the company's own name for it, "Fiscal year ended Sep 26, 2026 (FY26)", so an answer that
        # names the year names it as the filings do (Handoff 2)
        plabel = "{} ({})".format(per["label"], per["fiscal"]) if per.get("label") and per.get("fiscal") else per.get("label")
        item = {"figure_id": fid, "symbol": sym or None, "name": fv.get("name"), "text": fv.get("text"),
                "value": fv.get("value"), "status": fv.get("status"), "period": plabel,
                "source": src.get("name"), "filing": src.get("url"), "as_of": fv.get("as_of")}
        if fv.get("why"):
            item["why"] = fv["why"]
        out["{} {}".format(sym, fid).strip()] = {k: v for k, v in item.items() if v is not None}
    return out
