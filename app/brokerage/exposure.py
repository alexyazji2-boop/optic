"""What a linked portfolio is exposed to, looking through its funds where it can.

**Look-through redistributes, it never adds.** Every dollar of long value is
placed exactly once in each breakdown. A dollar in QQQ is counted under the
companies, sectors, countries and currencies QQQ owns, in proportion to its
latest N-PORT, and is then no longer counted as QQQ. NVDA held directly for
1,000 and through 1,000 of a fund that is 10% NVDA is 1,100 of NVDA out of a
2,000 portfolio: never 2,100. Each breakdown carries the total it adds to.

The fund side comes from `lookthrough.constituents`, which is months old by
design (SEC publishes N-PORT about 60 days after the quarter it describes),
so every result carries each fund's report date and says so.

What each breakdown is, and is not:

* **Companies** count shares only, held directly or through funds. A bond a
  fund holds is a loan to that company, not a stake in it, and is counted
  under asset class instead.
* **Sectors** come from `sector_of(ticker)`, bounded by `max_lookups`, spent
  on the companies with the most value first. What was not looked up is
  "Sector not known" and is reported as such, never spread pro rata.
* **Issuer country** is where a company is organised or based: the filing's
  `invCountry`, or the company profile for a stock held directly. It is not
  where revenue is earned, and Optic has no data on that.
* **Currency** is the currency each security is priced in. A dollar-priced
  stock can earn most of its revenue abroad and a hedged fund's currency
  risk is not visible here, so this is not economic currency exposure.

Pure: data in, dict out. Lookups are arguments and nothing reaches the network.
"""

from __future__ import annotations

import math
from typing import Any, Callable, Dict, List, Optional, Tuple

from . import lookthrough as lt

VERSION = "exposure-2026-10-15.1"
COMPANY_FLAG_PCT = 10.0
TOP_COMPANIES = 25
FUND_KINDS = ("etf", "fund")

ASSET_LABELS = {
    "equity": "Stocks", "debt": "Bonds and other debt", "cash_like": "Cash and equivalents in funds",
    "derivatives": "Derivatives held by funds (marked value)", "other": "Other assets",
    "crypto": "Crypto", "options": "Options (market value)", "cash": "Cash at the broker",
    "funds_not_looked_through": "Funds not looked through",
}

# ISO 3166 codes as N-PORT writes them. A code not here is shown as the code.
COUNTRY_NAMES = {
    "US": "United States", "CA": "Canada", "MX": "Mexico", "BR": "Brazil", "AR": "Argentina", "CL": "Chile",
    "GB": "United Kingdom", "IE": "Ireland", "NL": "Netherlands", "DE": "Germany", "FR": "France",
    "CH": "Switzerland", "BE": "Belgium", "LU": "Luxembourg", "ES": "Spain", "PT": "Portugal", "IT": "Italy",
    "AT": "Austria", "DK": "Denmark", "SE": "Sweden", "NO": "Norway", "FI": "Finland", "PL": "Poland",
    "GR": "Greece", "IL": "Israel", "TR": "Turkey", "ZA": "South Africa", "SA": "Saudi Arabia",
    "AE": "United Arab Emirates", "QA": "Qatar", "KW": "Kuwait", "EG": "Egypt", "IN": "India", "CN": "China",
    "HK": "Hong Kong", "TW": "Taiwan", "KR": "South Korea", "JP": "Japan", "SG": "Singapore",
    "MY": "Malaysia", "TH": "Thailand", "ID": "Indonesia", "PH": "Philippines", "VN": "Vietnam",
    "AU": "Australia", "NZ": "New Zealand", "BM": "Bermuda", "KY": "Cayman Islands", "JE": "Jersey",
    "GG": "Guernsey", "IM": "Isle of Man", "VG": "British Virgin Islands", "CW": "Curacao", "PR": "Puerto Rico",
    "PA": "Panama", "UY": "Uruguay", "CO": "Colombia", "PE": "Peru", "CY": "Cyprus", "MT": "Malta",
    "LR": "Liberia", "MH": "Marshall Islands", "BS": "Bahamas", "GI": "Gibraltar", "CZ": "Czech Republic",
    "HU": "Hungary", "RO": "Romania", "IS": "Iceland",
}

FUND_SECTOR_LABELS = {"debt": "Bonds and other debt (in funds)",
                      "derivatives": "Derivatives (in funds, marked value)",
                      "other": "Other assets (in funds)"}

NOT_LOOKED = "Funds not looked through"
NOT_ITEMISED = "Fund holdings not itemised"
FUND_NET_OTHER = "Fund cash and other net assets"


def _num(v: Any) -> Optional[float]:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def _r(v: Optional[float], n: int = 2) -> Optional[float]:
    return None if v is None else round(v, n)


def _money(v: float) -> str:
    return "${:,.2f}".format(v)


def _country_label(v: Optional[str]) -> Optional[str]:
    if not v:
        return None
    s = str(v).strip()
    if len(s) == 2 and s.isalpha():
        return COUNTRY_NAMES.get(s.upper(), s.upper())
    return s


def _company_key(row: Dict[str, Any]) -> Optional[str]:
    """One key per company, so GOOGL and GOOG in a fund and GOOG held directly
    land in one line: SEC's CIK when the row was matched, else its ticker,
    else its normalised name."""
    if row.get("cik"):
        return "cik:{}".format(row["cik"])
    t = lt.normalise_ticker(row.get("ticker"))
    if t:
        return "t:" + t
    n = lt.normalise_name(row.get("name"))
    return "n:" + n if n else None


def _fund_rows(result: Dict[str, Any]) -> List[Tuple[Dict[str, Any], float]]:
    """(row, share of the fund) with the shares scaled to add to exactly one.

    The filing's percentages, kept to four places, add to 100.0002 on SPY
    and VTI; scaling keeps every breakdown adding to the cent."""
    rows = [r for r in result.get("holdings") or [] if isinstance(r, dict)]
    total = sum(_num(r.get("pct")) or 0.0 for r in rows)
    if not rows or total <= 0:
        return []
    return [(r, (_num(r.get("pct")) or 0.0) / total) for r in rows]


def _fund_mix(result: Dict[str, Any], key: str) -> List[Tuple[str, float]]:
    """(bucket, share) for a whole fund, from every row of its filing where the
    result carries that mix, else from the listed rows and their residuals."""
    mix = ((result.get("mix") or {}).get(key)) if isinstance(result.get("mix"), dict) else None
    pairs: List[Tuple[str, float]] = []
    if isinstance(mix, dict) and mix:
        pairs = [(k, _num(v) or 0.0) for k, v in mix.items()]
    else:
        for r, share in _fund_rows(result):
            res = r.get("residual")
            if res == "net_other_assets":
                k = "net_other_assets"
            elif res:
                k = "not_itemised"
            else:
                k = _row_class(r) if key == "asset_class" else (r.get(key) or "not_reported")
            pairs.append((k, share * 100.0))
    total = sum(v for _, v in pairs)
    if total <= 0:
        return []
    return [(k, v / total) for k, v in pairs]


def _row_class(r: Dict[str, Any]) -> str:
    """The row's coarse asset class. A hand-built row with a ticker and no
    class is a stock: that is the only kind of row that carries one."""
    cls = r.get("asset_class")
    if cls:
        return cls
    if r.get("asset_category"):
        return lt.ASSET_CLASS.get(r["asset_category"], "other")
    return "equity" if (r.get("ticker") or r.get("cik")) else "other"


def _looked_through(result: Any) -> bool:
    return (isinstance(result, dict) and result.get("available") is True
            and not result.get("leveraged") and not result.get("inverse") and bool(result.get("holdings")))


class _Buckets:
    """Ordered value per label, with a fixed total to check against."""

    def __init__(self) -> None:
        self.values: Dict[str, float] = {}
        self.kind: Dict[str, str] = {}

    def add(self, label: str, value: float, kind: str = "named") -> None:
        self.values[label] = self.values.get(label, 0.0) + value
        self.kind.setdefault(label, kind)

    def rows(self, total: float) -> List[Dict[str, Any]]:
        out = [{"label": k, "value_usd": round(v, 2), "share_pct": _r(100.0 * v / total) if total else None,
                "kind": self.kind.get(k, "named")}
               for k, v in self.values.items() if abs(v) >= 0.005]
        return sorted(out, key=lambda x: (x["kind"] != "named", -x["value_usd"]))


def build(holdings: List[Dict[str, Any]], lookthrough: Dict[str, Dict[str, Any]],
          sector_of: Callable[[str], Optional[str]],
          country_of: Optional[Callable[[str], Optional[str]]] = None,
          max_lookups: int = 40, cash_usd: Optional[float] = None,
          options_usd: Optional[float] = None) -> Dict[str, Any]:
    """Direct and look-through exposure for `holdings` (portfolio.build's
    holdings with `value_usd`). `lookthrough` maps a fund symbol to its
    `constituents()` result. `sector_of` and `country_of` are called for at
    most `max_lookups` distinct tickers in all, largest exposure first."""
    lookthrough = {lt.normalise_ticker(k) or str(k).upper(): v for k, v in (lookthrough or {}).items()}
    limitations: List[str] = []

    # ------------------------------------------------------ what is counted
    lines: List[Dict[str, Any]] = []
    shorts: List[str] = []
    no_value: List[str] = []
    for h in holdings or []:
        v = _num(h.get("value_usd"))
        label = h.get("symbol") or h.get("description") or "Unnamed holding"
        if v is None:
            no_value.append(label)
            continue
        if v < 0:
            shorts.append(label)
            continue
        if v == 0:
            continue
        lines.append({"h": h, "value": v, "kind": (h.get("kind") or "other"), "label": label,
                      "symbol": lt.normalise_ticker(h.get("symbol"))})
    opt = max(0.0, _num(options_usd) or 0.0)
    long_value = sum(x["value"] for x in lines) + opt
    cash = _num(cash_usd)

    # --------------------------------------------------------------- funds
    funds: List[Dict[str, Any]] = []
    through: Dict[str, Dict[str, Any]] = {}
    for x in lines:
        if x["kind"] not in FUND_KINDS:
            continue
        res = lookthrough.get(x["symbol"]) if x["symbol"] else None
        entry = {"symbol": x["symbol"] or x["label"], "name": x["h"].get("description"),
                 "value_usd": _r(x["value"]), "share_pct": _r(100.0 * x["value"] / long_value) if long_value else None,
                 "status": None, "reason": None, "fund_name": None, "report_date": None, "filed": None,
                 "coverage_pct": None, "rows_kept": None, "rows_total": None, "leveraged": False,
                 "inverse": False, "source": lt.SOURCE, "source_url": None, "stale": False}
        if isinstance(res, dict):
            entry.update({k: res.get(k) for k in ("fund_name", "report_date", "filed", "coverage_pct", "rows_kept",
                                                   "rows_total", "source_url")})
            entry.update({"leveraged": bool(res.get("leveraged")), "inverse": bool(res.get("inverse")),
                          "stale": bool(res.get("stale"))})
        if _looked_through(res):
            entry["status"] = "looked_through"
            through[x["symbol"]] = res
            x["through"] = res
        elif isinstance(res, dict) and (res.get("leveraged") or res.get("inverse")):
            entry["status"] = "leveraged_or_inverse"
            entry["reason"] = res.get("reason") or "Leveraged or inverse: its holdings do not describe its exposure."
        elif isinstance(res, dict):
            entry["status"] = "unavailable"
            entry["reason"] = res.get("reason") or "No holdings list was available."
        else:
            entry["status"] = "not_looked_up"
            entry["reason"] = "Optic did not look up this fund's holdings."
        funds.append(entry)

    # ----------------------------------------------------------- companies
    companies: Dict[str, Dict[str, Any]] = {}
    alias: Dict[str, str] = {}
    fund_country: Dict[str, str] = {}

    def company(key: str, name: Optional[str], ticker: Optional[str]) -> Dict[str, Any]:
        c = companies.get(key)
        if c is None:
            c = companies[key] = {"key": key, "name": name, "ticker": ticker, "direct_usd": 0.0,
                                  "via": {}, "held_directly": False}
        if not c["name"] and name:
            c["name"] = name
        if not c["ticker"] and ticker:
            c["ticker"] = ticker
        return c

    def counts_as_company(r: Dict[str, Any]) -> bool:
        return (not r.get("residual") and _row_class(r) == "equity"
                and r.get("issuer_category") != "RF")

    for sym, res in through.items():
        for r, _share in _fund_rows(res):
            if not counts_as_company(r):
                continue
            key = _company_key(r)
            if not key:
                continue
            for t in [r.get("ticker")] + list(r.get("issuer_tickers") or []):
                t = lt.normalise_ticker(t)
                if t:
                    alias.setdefault(t, key)
            if r.get("country") and key not in fund_country:
                fund_country[key] = r["country"]

    for x in lines:
        if x["kind"] != "equity":
            continue
        key = alias.get(x["symbol"]) if x["symbol"] else None
        key = key or ("t:" + x["symbol"] if x["symbol"]
                      else "n:" + (lt.normalise_name(x["label"]) or str(x["label"]).upper()))
        c = company(key, x["h"].get("description") or x["label"], x["symbol"] or None)
        # The reader's own ticker for a company they hold, not the fund's line.
        if x["symbol"]:
            c["ticker"] = x["symbol"]
        c["direct_usd"] += x["value"]
        c["held_directly"] = True
        x["company"] = key

    for x in lines:
        res = x.get("through")
        if not res:
            continue
        for r, share in _fund_rows(res):
            if not counts_as_company(r):
                continue
            key = _company_key(r)
            if not key:
                continue
            c = company(key, r.get("name"), lt.normalise_ticker(r.get("ticker")) or None)
            c["via"][x["symbol"]] = c["via"].get(x["symbol"], 0.0) + x["value"] * share

    fund_value: Dict[str, float] = {}
    for x in lines:
        if x.get("through"):
            fund_value[x["symbol"]] = fund_value.get(x["symbol"], 0.0) + x["value"]
    for c in companies.values():
        c["indirect_usd"] = sum(c["via"].values())
        c["total_usd"] = c["direct_usd"] + c["indirect_usd"]

    # ------------------------------------------------------------ lookups
    ranked = sorted(companies.values(), key=lambda c: -c["total_usd"])
    budget = max(0, int(max_lookups or 0))
    spent: Dict[str, bool] = {}
    skipped_lookups = 0

    def spend(ticker: Optional[str]) -> bool:
        nonlocal skipped_lookups
        if not ticker:
            return False
        if ticker in spent:
            return True
        if len(spent) >= budget:
            skipped_lookups += 1
            return False
        spent[ticker] = True
        return True

    def call(fn: Optional[Callable[[str], Optional[str]]], ticker: str) -> Optional[str]:
        if fn is None:
            return None
        try:
            v = fn(ticker)
        except Exception:                                          # noqa: BLE001
            return None
        return str(v).strip() if v else None

    direct_sector = {x["company"]: x["h"].get("sector") for x in lines if x.get("company") and x["h"].get("sector")}
    sectors_known: Dict[str, Optional[str]] = {}
    countries: Dict[str, Optional[str]] = {}
    for c in ranked:
        key, t = c["key"], c["ticker"]
        sec = direct_sector.get(key)
        need_country = c["held_directly"] and key not in fund_country and country_of is not None
        if (sec is None or need_country) and spend(t):
            if sec is None:
                sec = call(sector_of, t)
            if need_country:
                countries[key] = _country_label(call(country_of, t))
        sectors_known[key] = sec
        c["sector"] = sec

    # ----------------------------------------------- the company breakdown
    total_company = sum(c["total_usd"] for c in companies.values())
    flags: List[str] = []
    rows_out: List[Dict[str, Any]] = []
    for c in ranked[:TOP_COMPANIES]:
        share = 100.0 * c["total_usd"] / long_value if long_value else None
        direct_share = 100.0 * c["direct_usd"] / long_value if long_value else 0.0
        flag = bool(share is not None and share > COMPANY_FLAG_PCT)
        via = [{"symbol": s, "value_usd": round(v, 2),
                "pct_of_fund": _r(100.0 * v / fund_value[s], 4) if fund_value.get(s) else None}
               for s, v in sorted(c["via"].items(), key=lambda kv: -kv[1])]
        rows_out.append({
            "name": c["name"], "ticker": c["ticker"], "key": c["key"], "sector": c.get("sector"),
            "direct_usd": round(c["direct_usd"], 2), "via_funds": via,
            "indirect_usd": round(c["indirect_usd"], 2), "total_usd": round(c["total_usd"], 2),
            "share_pct": _r(share), "flag": flag,
        })
        if flag:
            parts = []
            if c["direct_usd"]:
                parts.append("{} held directly".format(_money(c["direct_usd"])))
            if via:
                parts.append("{} through {}".format(_money(c["indirect_usd"]), ", ".join(v["symbol"] for v in via)))
            hidden = direct_share <= COMPANY_FLAG_PCT
            flags.append("{} is {:.2f}% of long holdings once what your funds hold is counted ({}){}.".format(
                c["ticker"] or c["name"], share, " and ".join(parts),
                ", more than the {:.0f}% its direct position alone suggests".format(direct_share) if hidden and c["direct_usd"]
                else ""))
    shown = sum(c["total_usd"] for c in ranked[:TOP_COMPANIES])
    companies_out = {
        "rows": rows_out,
        "count": len(companies),
        "shown_usd": round(shown, 2),
        "other_companies_usd": round(total_company - shown, 2),
        "not_company_usd": round(long_value - total_company, 2),
        "long_value_usd": round(long_value, 2),
        "flags": flags,
        "threshold_pct": COMPANY_FLAG_PCT,
        "no_double_counting": (
            "Look-through splits each fund's value across what the fund holds and never adds to the "
            "total: a dollar in a fund is counted once, under the companies it owns, and no longer as "
            "the fund. The shown companies, the other companies and the value that is not a company "
            "stake add up to the long value."),
        "basis": ("Stakes in companies: shares held directly plus the fund's value times the company's "
                  "share of the fund in its latest N-PORT. Share classes of one company are combined. "
                  "Bonds, cash, derivatives, funds not looked through and fund holdings not itemised are "
                  "the value that is not a company stake."),
    }

    # -------------------------------------------------------------- sectors
    direct_only = _Buckets()
    look = _Buckets()
    stock_value = 0.0
    unclassified = 0.0
    not_itemised = 0.0
    for x in lines:
        k, v = x["kind"], x["value"]
        if k == "equity":
            sec = sectors_known.get(x.get("company"))
            direct_only.add(sec or "Sector not known", v, "named" if sec else "unknown")
            look.add(sec or "Sector not known", v, "named" if sec else "unknown")
            stock_value += v
            if not sec:
                unclassified += v
        elif k in FUND_KINDS:
            direct_only.add("ETFs and funds (not looked through)", v, "other")
            res = x.get("through")
            if not res:
                look.add(NOT_LOOKED, v, "other")
                not_itemised += v
                continue
            for r, share in _fund_rows(res):
                part = v * share
                if r.get("residual") == "other_holdings":
                    look.add(NOT_ITEMISED, part, "other")
                    not_itemised += part
                elif r.get("residual"):
                    look.add(FUND_NET_OTHER, part, "other")
                elif counts_as_company(r):
                    key = _company_key(r)
                    sec = sectors_known.get(key) if key else None
                    look.add(sec or "Sector not known", part, "named" if sec else "unknown")
                    stock_value += part
                    if not sec:
                        unclassified += part
                elif _row_class(r) == "equity":
                    look.add("Funds held by funds", part, "other")
                elif _row_class(r) == "cash_like":
                    look.add(FUND_NET_OTHER, part, "other")
                else:
                    look.add(FUND_SECTOR_LABELS.get(_row_class(r), "Other assets (in funds)"), part, "other")
        else:
            label = {"bond": "Bonds", "crypto": "Crypto"}.get(k, "Other")
            direct_only.add(label, v, "other")
            look.add(label, v, "other")
    if opt:
        direct_only.add("Options", opt, "other")
        look.add("Options", opt, "other")
    sectors_out = {
        "direct_only": direct_only.rows(long_value),
        "look_through": look.rows(long_value),
        "total_usd": round(long_value, 2),
        "stock_value": round(stock_value, 2),
        "coverage_pct": _r(100.0 * (stock_value - unclassified) / stock_value) if stock_value else None,
        "unclassified_value": round(unclassified, 2),
        "not_itemised_value": round(not_itemised, 2),
        "lookups_used": len(spent),
        "lookups_skipped": skipped_lookups,
        "basis": ("Both views add to the long value. 'Direct only' treats each fund as one line; 'look "
                  "through' replaces each fund with its holdings. Coverage is the share of stock exposure, "
                  "direct and inside funds, whose sector is known; unclassified value is stock exposure "
                  "with no sector, and not itemised value is fund value Optic could not break down."),
    }

    # ---------------------------------------------------------- asset class
    ac = _Buckets()
    for x in lines:
        k, v = x["kind"], x["value"]
        if k == "equity":
            ac.add(ASSET_LABELS["equity"], v)
        elif k == "bond":
            ac.add(ASSET_LABELS["debt"], v)
        elif k == "crypto":
            ac.add(ASSET_LABELS["crypto"], v)
        elif k in FUND_KINDS:
            res = x.get("through")
            if not res:
                ac.add(ASSET_LABELS["funds_not_looked_through"], v, "other")
                continue
            for bucket, share in _fund_mix(res, "asset_class"):
                if bucket in ("net_other_assets", "cash_like"):
                    ac.add(ASSET_LABELS["cash_like"], v * share)
                elif bucket == "not_itemised":
                    ac.add(NOT_ITEMISED, v * share, "other")
                else:
                    ac.add(ASSET_LABELS.get(bucket, "Other assets"), v * share)
        else:
            ac.add(ASSET_LABELS["other"], v)
    if opt:
        ac.add(ASSET_LABELS["options"], opt)
    ac_total = long_value
    if cash is not None and cash > 0:
        ac.add(ASSET_LABELS["cash"], cash)
        ac_total += cash
    elif cash is not None and cash < 0:
        limitations.append("The cash balance is negative ({}), which is borrowing rather than an asset, so "
                           "it is not in the asset-class breakdown.".format(_money(cash)))
    asset_out = {
        "rows": ac.rows(ac_total), "total_usd": round(ac_total, 2),
        "includes_cash": bool(cash is not None and cash > 0),
        "basis": ("Funds are split by the asset category of every holding in their N-PORT (equity, debt, "
                  "cash-like, derivatives, other), with each fund's cash and other assets less liabilities "
                  "counted as cash. A fund's derivatives are at their marked value, not their notional. "
                  + ("Broker cash is included, so this adds to long value plus cash."
                     if cash is not None and cash > 0 else "It adds to the long value.")),
    }

    # ------------------------------------------------------ issuer country
    ctry = _Buckets()
    for x in lines:
        k, v = x["kind"], x["value"]
        if k == "equity":
            key = x.get("company")
            name = _country_label(fund_country.get(key)) or countries.get(key)
            ctry.add(name or "Not known", v, "named" if name else "unknown")
        elif k in FUND_KINDS:
            res = x.get("through")
            if not res:
                ctry.add(NOT_LOOKED, v, "other")
                continue
            for code, share in _fund_mix(res, "country"):
                if code == "net_other_assets":
                    ctry.add(FUND_NET_OTHER, v * share, "other")
                elif code == "not_itemised":
                    ctry.add(NOT_ITEMISED, v * share, "other")
                elif code == "not_reported":
                    ctry.add("Not reported in the filing", v * share, "unknown")
                else:
                    ctry.add(_country_label(code), v * share)
        elif k == "crypto":
            ctry.add("No issuer (crypto)", v, "other")
        else:
            ctry.add("Not known", v, "unknown")
    if opt:
        ctry.add("Options (not attributed)", opt, "other")
    country_out = {
        "rows": ctry.rows(long_value), "total_usd": round(long_value, 2),
        "label": "Where issuers are organised or located",
        "basis": ("Where each issuer is organised or based: the country a fund reports for each holding "
                  "(N-PORT invCountry), and the company profile for stocks held directly. It is not where "
                  "revenue is earned: a US company can earn most of its sales abroad."),
    }

    # ------------------------------------------------------------ currency
    cur = _Buckets()
    for x in lines:
        k, v = x["kind"], x["value"]
        ccy = (x["h"].get("currency") or "USD").upper()
        res = x.get("through") if k in FUND_KINDS else None
        if not res:
            cur.add(ccy, v)
            continue
        for code, share in _fund_mix(res, "currency"):
            if code == "net_other_assets":
                cur.add(FUND_NET_OTHER, v * share, "other")
            elif code == "not_itemised":
                cur.add(NOT_ITEMISED, v * share, "other")
            elif code == "not_reported":
                cur.add("Not reported in the filing", v * share, "unknown")
            else:
                cur.add(code.upper(), v * share)
    if opt:
        cur.add("Options (not attributed)", opt, "other")
    currency_out = {
        "rows": cur.rows(long_value), "total_usd": round(long_value, 2),
        "label": "Currency securities are priced in",
        "basis": ("The currency each security is priced in, looking through funds where Optic can; a fund "
                  "that is not looked through counts in the currency it trades in. This is not economic "
                  "currency exposure: revenue earned abroad and a fund's currency hedges are not in it. Each "
                  "fund's cash and other assets less liabilities is its own line, and it is negative when "
                  "a fund owes more than the cash it holds (securities-lending collateral is the usual "
                  "cause: VTI's holdings add to 100.47% of its net assets)."),
    }

    # --------------------------------------------------------- limitations
    unlooked = [f for f in funds if f["status"] != "looked_through"]
    if unlooked:
        v = sum(f["value_usd"] or 0 for f in unlooked)
        limitations.append("{} of your {} ({}, {:.2f}% of long value) {} not looked through and {} as one line "
                           "each, under '{}'.".format(
                               len(unlooked), "funds" if len(funds) > 1 else "fund", _money(v),
                               100.0 * v / long_value if long_value else 0.0,
                               "are" if len(unlooked) > 1 else "is", "count" if len(unlooked) > 1 else "counts",
                               NOT_LOOKED))
        for f in unlooked[:5]:
            if f["status"] != "leveraged_or_inverse":
                limitations.append(f["reason"] if f["symbol"] in (f["reason"] or "")
                                   else "{}: {}".format(f["symbol"], f["reason"]))
    lev = [f["symbol"] for f in funds if f["status"] == "leveraged_or_inverse"]
    if lev:
        limitations.append("Leveraged or inverse funds ({}) are left out of look-through: their exposure comes "
                           "from swaps and futures, not from what they hold.".format(", ".join(lev)))
    looked = [f for f in funds if f["status"] == "looked_through"]
    if looked:
        dates = sorted({f["report_date"] for f in looked if f["report_date"]})
        limitations.append("Fund holdings come from SEC filings as of {}, published about 60 days later. They "
                           "are not today's holdings.".format(
                               dates[0] if len(dates) == 1 else "{} to {}".format(dates[0], dates[-1]))
                           if dates else "The funds' filings do not state the date their holdings are as of.")
        partial = [f for f in looked if (f["coverage_pct"] or 0) < 99.5]
        if partial:
            limitations.append("Not every fund holding is listed: {}. The rest is counted as '{}'.".format(
                "; ".join("{} lists {:.2f}% of its value".format(f["symbol"], f["coverage_pct"] or 0.0)
                          for f in partial), NOT_ITEMISED))
        stale = [f["symbol"] for f in looked if f["stale"]]
        if stale:
            limitations.append("SEC could not be reached for {}, so an earlier copy of their holdings is used."
                               .format(", ".join(stale)))
    if skipped_lookups:
        limitations.append("Sectors were looked up for the {} companies with the most value; {} smaller ones "
                           "were not and count as 'Sector not known'.".format(len(spent), skipped_lookups))
    if stock_value and unclassified > 0.005:
        limitations.append("{} of stock exposure ({:.2f}%) has no known sector.".format(
            _money(unclassified), 100.0 * unclassified / stock_value))
    if country_of is None and any(x["kind"] == "equity" for x in lines):
        limitations.append("No company profile lookup was given, so stocks held directly have a country only "
                           "when a fund you hold also reports one for them.")
    limitations.append("Issuer country is where a company is organised or based. Revenue by country is not "
                       "available, so this does not show where your companies earn their money.")
    limitations.append("Currency is the currency of pricing, not economic exposure, and fund currency hedges "
                       "are not shown.")
    if opt:
        limitations.append("Options are counted at market value as one line, not delta-adjusted and not "
                           "assigned to their underlying company.")
    if shorts:
        limitations.append("Short positions ({}) are left out of every breakdown.".format(", ".join(shorts[:5])))
    if no_value:
        limitations.append("No US dollar value was available for {}, so it is left out.".format(
            ", ".join(no_value[:5])))
    if any(_row_class(r) == "equity" and r.get("issuer_category") == "RF"
           for res in through.values() for r in res.get("holdings") or []):
        limitations.append("Funds held inside your funds are counted as one line each and not looked through "
                           "again.")

    return {
        "version": VERSION,
        "long_value_usd": round(long_value, 2),
        "companies": companies_out,
        "sectors": sectors_out,
        "asset_class": asset_out,
        "issuer_country": country_out,
        "currency": currency_out,
        "etfs": funds,
        "limitations": limitations,
        "method": ("Long value is stocks, ETFs, funds, bonds, crypto and long options in US dollars; cash and "
                   "shorts are not in it. Each fund looked through is replaced by its holdings from its latest "
                   "SEC Form N-PORT, weighted by each holding's share of the fund's net assets, so every "
                   "breakdown still adds to the long value. Sector and country lookups are limited to {} "
                   "companies, largest first.".format(budget)),
    }
