"""Sourced inputs for the valuation models, read from the company's own filings.

Every figure the models use comes back as a *fact*: its value, the XBRL tag it
was read from, the period it covers, the form and filing it appeared in, the
date that filing was made public, the unit, and the date this copy of the
filings was retrieved. A figure built from several facts (debt, working
capital) carries the facts it was built from and the rule used. A figure that
is not in the filings is `None` with the reason, never a zero.

**Periods are not mixed.** Flows (revenue, EBIT, capex) are fiscal-year totals
from 10-K filings, matched by the fiscal-year end. Balances (cash, debt) are
point-in-time values on one balance-sheet date. The forecast's base year is the
last full fiscal year; the bridge uses the latest balance sheet, which may be a
10-Q. `engine.timing` counts only the cash flows after that date, so the two
fit together.

**Restatements.** A fiscal year's value is taken from the latest filing that
reports it (a later 10-K's comparative column replaces an earlier one), and a
value that changed is marked `restated`.

**Coverage.** US-GAAP filers only (10-K / 10-Q). A foreign private issuer
filing IFRS 20-F reports, or a company whose filings use none of the tags
below, is reported as not covered rather than approximated.
"""

from __future__ import annotations

import math
import time
from datetime import date, datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from .. import feeds
from ..analytics import sec_facts

SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
SUBMISSIONS_TTL = 86400
ANNUAL_FORMS = ("10-K", "10-K/A", "10-KT")
ANY_FORMS = ANNUAL_FORMS + ("10-Q", "10-Q/A")
YEAR_DAYS = (340, 380)
HISTORY_YEARS = 5

# Tags in the order preferred when more than one reports the same period.
# "Revenues" first: it is the total where a company reports both it and the
# narrower contract-revenue tag (a REIT's rental income is not contract revenue).
TAGS: Dict[str, Tuple[str, ...]] = {
    "revenue": ("Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax",
                "RevenuesNetOfInterestExpense", "SalesRevenueNet",
                "RevenueFromContractWithCustomerIncludingAssessedTax", "SalesRevenueGoodsNet",
                "SalesRevenueServicesNet"),
    "operating_income": ("OperatingIncomeLoss",),
    # Read by the research framework's margin-driver check (app/research/quality.py),
    # not by any valuation model: whether a change in operating margin came from
    # pricing and mix (gross margin) or from spending (the operating cost ratio).
    "gross_profit": ("GrossProfit",),
    "cost_of_revenue": ("CostOfRevenue", "CostOfGoodsAndServicesSold"),
    "pretax_income": ("IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
                      "IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments"),
    "income_tax": ("IncomeTaxExpenseBenefit",),
    "net_income": ("NetIncomeLoss",),
    "net_income_common": ("NetIncomeLossAvailableToCommonStockholdersBasic", "NetIncomeLoss"),
    "da": ("DepreciationDepletionAndAmortization", "DepreciationAmortizationAndAccretionNet",
           "DepreciationAndAmortization"),
    "depreciation": ("Depreciation",),
    "amortization": ("AmortizationOfIntangibleAssets",),
    "capex": ("PaymentsToAcquirePropertyPlantAndEquipment", "PaymentsToAcquireProductiveAssets"),
    "cfo": ("NetCashProvidedByUsedInOperatingActivities",
            "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations"),
    "sbc": ("ShareBasedCompensation", "AllocatedShareBasedCompensationExpense"),
    "interest_expense": ("InterestExpense", "InterestExpenseNonoperating", "InterestExpenseDebt",
                         "InterestAndDebtExpense"),
    "interest_income": ("InvestmentIncomeInterest", "InterestIncomeOther"),
    # Items filers tag as unusual, for the normalised margin (never the default).
    "restructuring": ("RestructuringCharges",),
    "goodwill_impairment": ("GoodwillImpairmentLoss",),
    "intangible_impairment": ("ImpairmentOfIntangibleAssetsExcludingGoodwill",
                              "ImpairmentOfIntangibleAssetsIndefinitelivedExcludingGoodwill"),
    "asset_impairment": ("AssetImpairmentCharges",),
    "contingent_consideration": ("BusinessCombinationContingentConsiderationArrangementsChangeInAmountOfContingentConsiderationLiability1",),
    "acquisitions": ("PaymentsToAcquireBusinessesNetOfCashAcquired",),
    "dividends_paid": ("PaymentsOfDividendsCommonStock", "PaymentsOfDividends"),
    "dps": ("CommonStockDividendsPerShareDeclared", "CommonStockDividendsPerShareCashPaid"),
    "buybacks": ("PaymentsForRepurchaseOfCommonStock",),
    "diluted_shares_avg": ("WeightedAverageNumberOfDilutedSharesOutstanding",),
    "basic_shares_avg": ("WeightedAverageNumberOfSharesOutstandingBasic",),
    "eps_diluted": ("EarningsPerShareDiluted", "EarningsPerShareBasicAndDiluted"),
    "gain_real_estate": ("GainLossOnSaleOfRealEstateInvestmentProperty",
                         "GainsLossesOnSalesOfInvestmentRealEstate",
                         "GainLossOnSaleOfPropertiesNetOfApplicableIncomeTaxes"),
    "impairment_real_estate": ("ImpairmentOfRealEstate",),
    # Balances
    "assets": ("Assets",),
    "liabilities": ("Liabilities",),
    "assets_current": ("AssetsCurrent",),
    "liabilities_current": ("LiabilitiesCurrent",),
    "cash": ("CashAndCashEquivalentsAtCarryingValue",
             "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents", "Cash"),
    # DebtSecuritiesCurrent last: Nvidia moved its marketable securities to
    # it after October 2025, and without it $34bn of cash-like holdings read
    # as "not reported" and as working capital.
    "short_term_investments": ("ShortTermInvestments", "MarketableSecuritiesCurrent",
                               "AvailableForSaleSecuritiesDebtSecuritiesCurrent", "DebtSecuritiesCurrent"),
    "long_term_investments": ("LongTermInvestments", "MarketableSecuritiesNoncurrent",
                              "AvailableForSaleSecuritiesDebtSecuritiesNoncurrent"),
    "other_long_term_investments": ("OtherLongTermInvestments",),
    "equity_securities_fv": ("EquitySecuritiesFvNi",),
    "equity_securities_nonmarketable": ("EquitySecuritiesWithoutReadilyDeterminableFairValueAmount",),
    "equity_method": ("EquityMethodInvestments",),
    "ltd_and_leases_total": ("LongTermDebtAndCapitalLeaseObligationsIncludingCurrentMaturities",),
    "ltd_and_leases_noncurrent": ("LongTermDebtAndCapitalLeaseObligations",),
    "ltd_and_leases_current": ("LongTermDebtAndCapitalLeaseObligationsCurrent",),
    "ltd_total": ("LongTermDebt",),
    "ltd_noncurrent": ("LongTermDebtNoncurrent",),
    "ltd_current": ("LongTermDebtCurrent",),
    "debt_current": ("DebtCurrent",),
    "short_term_borrowings": ("ShortTermBorrowings",),
    "notes_payable": ("NotesPayable",),
    "unsecured_debt": ("UnsecuredDebt",),
    "secured_debt": ("SecuredDebt",),
    "line_of_credit": ("LineOfCredit",),
    "line_of_credit_lt": ("LongTermLineOfCredit",),
    "commercial_paper": ("CommercialPaper",),
    "other_short_term_borrowings": ("OtherShortTermBorrowings",),
    "finance_lease": ("FinanceLeaseLiability",),
    "finance_lease_current": ("FinanceLeaseLiabilityCurrent",),
    "finance_lease_noncurrent": ("FinanceLeaseLiabilityNoncurrent",),
    "operating_lease": ("OperatingLeaseLiability",),
    "operating_lease_current": ("OperatingLeaseLiabilityCurrent",),
    "nci": ("MinorityInterest",),
    "preferred": ("PreferredStockLiquidationPreferenceValue", "PreferredStockValue",
                  "PreferredStockValueOutstanding"),
    "equity": ("StockholdersEquity",),
    "equity_incl_nci": ("StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",),
    "temporary_equity": ("TemporaryEquityCarryingAmountAttributableToParent",),
    "ppe": ("PropertyPlantAndEquipmentNet",
            "PropertyPlantAndEquipmentAndFinanceLeaseRightOfUseAssetAfterAccumulatedDepreciationAndAmortization"),
    "pension_funded_status": ("DefinedBenefitPlanFundedStatusOfPlan",),
    "shares_outstanding": ("CommonStockSharesOutstanding",),
    "real_estate_net": ("RealEstateInvestmentPropertyNet",),
}
FLOWS = {"revenue", "operating_income", "gross_profit", "cost_of_revenue", "pretax_income", "income_tax", "net_income", "net_income_common",
         "da", "depreciation", "amortization", "capex", "cfo", "sbc", "interest_expense", "interest_income",
         "dividends_paid", "dps", "buybacks", "diluted_shares_avg", "basic_shares_avg",
         "eps_diluted", "gain_real_estate", "impairment_real_estate", "restructuring",
         "goodwill_impairment", "intangible_impairment", "asset_impairment", "contingent_consideration",
         "acquisitions"}
UNITS = {"dps": "USD/shares", "eps_diluted": "USD/shares", "diluted_shares_avg": "shares",
         "basic_shares_avg": "shares", "shares_outstanding": "shares"}


def _num(value: Any) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _date(s: Any) -> Optional[date]:
    try:
        return date.fromisoformat(str(s)[:10])
    except (TypeError, ValueError):
        return None


def _days(a: Any, b: Any) -> Optional[int]:
    da, db = _date(a), _date(b)
    return None if da is None or db is None else (db - da).days


def _near(a: Any, b: Any, tol: int) -> bool:
    gap = _days(a, b)
    return gap is not None and abs(gap) <= tol


def filing_url(cik: str, accn: Optional[str]) -> Optional[str]:
    if not accn:
        return None
    return "https://www.sec.gov/Archives/edgar/data/{}/{}/".format(int(cik), accn.replace("-", ""))


def retrieved_at(key: str) -> Optional[str]:
    """When the cached copy of a feed was fetched, as an ISO date-time."""
    try:
        hit = feeds._MEM.get(key) or feeds._load_disk().get(key)        # noqa: SLF001
    except Exception:                                                   # noqa: BLE001
        hit = None
    at = (hit or {}).get("at")
    if not at:
        return None
    return datetime.fromtimestamp(float(at), tz=timezone.utc).isoformat(timespec="seconds")


class Filings:
    """One company's XBRL facts, indexed for period-exact lookups."""

    def __init__(self, blob: Dict[str, Any], cik: str, retrieved: Optional[str]):
        self.cik = cik
        self.retrieved = retrieved
        self.name = blob.get("entityName")
        facts = blob.get("facts") or {}
        self.gaap = facts.get("us-gaap") or {}
        self.dei = facts.get("dei") or {}
        self.ifrs = bool(facts.get("ifrs-full"))

    def _rows(self, tag: str, unit: str, ns: str = "gaap") -> List[Dict[str, Any]]:
        node = (self.gaap if ns == "gaap" else self.dei).get(tag) or {}
        return ((node.get("units") or {}).get(unit)) or []

    def _fact(self, concept: str, tag: str, rows: List[Dict[str, Any]], unit: str) -> Dict[str, Any]:
        best = max(rows, key=lambda r: (r.get("filed") or "", r.get("accn") or ""))
        first = min(rows, key=lambda r: r.get("filed") or "")
        vals = {round(float(r["val"]), 2) for r in rows if _num(r.get("val")) is not None}
        return {
            "concept": concept, "value": float(best["val"]), "tag": tag, "unit": unit,
            "start": best.get("start"), "end": best.get("end"), "form": best.get("form"),
            "filed": best.get("filed"), "first_filed": first.get("filed"), "accn": best.get("accn"),
            "fy": best.get("fy"), "fp": best.get("fp"),
            "url": filing_url(self.cik, best.get("accn")),
            "restated": len(vals) > 1, "kind": "reported", "retrieved": self.retrieved,
        }

    def flow(self, concept: str, fy_end: str) -> Optional[Dict[str, Any]]:
        """A fiscal-year total for the year ending on `fy_end` (within a week,
        for 52/53-week years), from the first tag in priority order that has
        one."""
        unit = UNITS.get(concept, "USD")
        for tag in TAGS[concept]:
            rows = [r for r in self._rows(tag, unit)
                    if r.get("form") in ANNUAL_FORMS and r.get("start")
                    and YEAR_DAYS[0] <= (_days(r["start"], r["end"]) or 0) <= YEAR_DAYS[1]
                    and _near(r["end"], fy_end, 7) and _num(r.get("val")) is not None]
            if rows:
                return self._fact(concept, tag, rows, unit)
        return None

    def instant(self, concept: str, on: str, forms: Sequence[str] = ANY_FORMS) -> Optional[Dict[str, Any]]:
        """A balance on the date `on` (within three days)."""
        unit = UNITS.get(concept, "USD")
        for tag in TAGS[concept]:
            rows = [r for r in self._rows(tag, unit)
                    if r.get("form") in forms and not r.get("start")
                    and _near(r["end"], on, 3) and _num(r.get("val")) is not None]
            if rows:
                return self._fact(concept, tag, rows, unit)
        return None

    def latest_instant(self, concept: str, not_after: str) -> Optional[Dict[str, Any]]:
        """The most recent balance on or before `not_after`, any date. For items
        reported only annually (a pension's funded status)."""
        unit = UNITS.get(concept, "USD")
        for tag in TAGS[concept]:
            rows = [r for r in self._rows(tag, unit)
                    if r.get("form") in ANY_FORMS and not r.get("start")
                    and (_days(r["end"], not_after) is not None and _days(r["end"], not_after) >= 0) and _num(r.get("val")) is not None]
            if rows:
                end = max(r["end"] for r in rows)
                return self._fact(concept, tag, [r for r in rows if r["end"] == end], unit)
        return None

    def fiscal_year_ends(self) -> List[str]:
        """Fiscal-year end dates, newest first, from annual-duration facts in
        10-K filings. Ends within ten days of each other are one year."""
        ends: List[str] = []
        for concept in ("revenue", "net_income", "operating_income"):
            for tag in TAGS[concept]:
                for r in self._rows(tag, "USD"):
                    if (r.get("form") in ANNUAL_FORMS and r.get("start") and r.get("fp") == "FY"
                            and YEAR_DAYS[0] <= (_days(r["start"], r["end"]) or 0) <= YEAR_DAYS[1]):
                        ends.append(r["end"])
        out: List[str] = []
        for e in sorted(set(ends), reverse=True):
            if not out or not _near(e, out[-1], 10):
                out.append(e)
        return out

    def balance_dates(self) -> List[str]:
        dates = {r["end"] for r in self._rows("Assets", "USD")
                 if r.get("form") in ANY_FORMS and not r.get("start")}
        return sorted(dates, reverse=True)

    def cover_shares(self) -> Optional[Dict[str, Any]]:
        """Shares outstanding from the latest cover page (dei). Absent for
        companies with several share classes, which tag each class with a
        dimension that the facts API does not carry."""
        rows = self._rows("EntityCommonStockSharesOutstanding", "shares", ns="dei")
        if not rows:
            return None
        end = max(r["end"] for r in rows)
        same = [r for r in rows if r["end"] == end]
        return self._fact("shares_outstanding", "dei:EntityCommonStockSharesOutstanding", same, "shares")

    def latest_period_shares(self) -> Optional[Dict[str, Dict[str, Any]]]:
        """Weighted diluted and basic shares for the most recent period of any
        length (quarter or year), for the dilution increment."""
        best = None
        for concept in ("diluted_shares_avg",):
            for tag in TAGS[concept]:
                for r in self._rows(tag, "shares"):
                    if r.get("form") in ANY_FORMS and r.get("start") and _num(r.get("val")):
                        if best is None or (r["end"], r.get("filed")) > (best["end"], best.get("filed")):
                            best = r
        if best is None:
            return None
        def at(concept: str) -> Optional[Dict[str, Any]]:
            for tag in TAGS[concept]:
                rows = [r for r in self._rows(tag, "shares")
                        if r.get("start") == best["start"] and r.get("end") == best["end"]]
                if rows:
                    return self._fact(concept, tag, rows, "shares")
            return None
        return {"diluted": at("diluted_shares_avg"), "basic": at("basic_shares_avg")}


def load_filings(ticker: str, force: bool = False) -> Tuple[Optional[Filings], Optional[str], Optional[str]]:
    """(filings, cik, reason-if-unavailable)."""
    try:
        cik = sec_facts.cik_for(ticker)
    except sec_facts.LookupUnavailable as exc:
        return None, None, "EDGAR's company directory could not be read ({}).".format(exc)
    if not cik:
        return None, None, ("{} is not in EDGAR's company directory, so there are no SEC filings "
                            "to build a model from.".format(ticker))
    key = "sec:facts:" + cik
    try:
        blob = sec_facts._json_or_stale(sec_facts.FACTS_URL.format(cik=cik),                  # noqa: SLF001
                                        0 if force else sec_facts.FACTS_TTL, key)
    except Exception as exc:                                                               # noqa: BLE001
        return None, cik, "EDGAR's financial data did not answer ({}).".format(type(exc).__name__)
    return Filings(blob or {}, cik, retrieved_at(key)), cik, None


def submissions(cik: str) -> Dict[str, Any]:
    """SIC code, its description and the fiscal-year end from EDGAR. Shares
    the cache key with the segments reader, which fetches the same document."""
    try:
        blob = feeds.fetch_json(SUBMISSIONS_URL.format(cik=cik), SUBMISSIONS_TTL, key="seg:subs:" + cik)
    except Exception:                                                                      # noqa: BLE001
        blob = feeds.cached_json("seg:subs:" + cik) or {}
    return {"sic": str(blob.get("sic") or "") or None, "sic_description": blob.get("sicDescription"),
            "fiscal_year_end": blob.get("fiscalYearEnd"), "name": blob.get("name"),
            "former_names": [f.get("name") for f in (blob.get("formerNames") or [])][:3]}


# ---------------------------------------------------------------------------
# Composite figures
# ---------------------------------------------------------------------------

def _derived(concept: str, value: Optional[float], parts: List[Optional[Dict[str, Any]]], rule: str,
             note: Optional[str] = None) -> Dict[str, Any]:
    used = [p for p in parts if p]
    out = {"concept": concept, "value": value, "kind": "derived", "rule": rule,
           "parts": [{k: p.get(k) for k in ("concept", "tag", "value", "end", "form", "filed", "url")}
                     for p in used],
           "end": max((p.get("end") or "" for p in used), default=None) or None,
           "filed": max((p.get("filed") or "" for p in used), default=None) or None,
           "url": used[0].get("url") if used else None,
           "retrieved": used[0].get("retrieved") if used else None,
           "restated": any(p.get("restated") for p in used)}
    if note:
        out["note"] = note
    return out


def _none(concept: str, reason: str) -> Dict[str, Any]:
    return {"concept": concept, "value": None, "reason": reason}


def _zero(concept: str, on: str, reason: str) -> Dict[str, Any]:
    """An item the filing does not report at all on this date: treated as none,
    and said so, which is different from a missing figure the model needs."""
    return {"concept": concept, "value": 0.0, "kind": "not_reported", "end": on, "note": reason}


def _v(f: Optional[Dict[str, Any]]) -> Optional[float]:
    return None if not f else _num(f.get("value"))


def debt_on(fl: Filings, on: str) -> Dict[str, Any]:
    """Total borrowings on one date, without counting a line twice.

    Long-term debt including its current maturities, plus short-term
    borrowings and commercial paper. Filers tag this several ways, and the same
    filer often tags a 10-Q differently from its 10-K, so the rules are tried
    in order:

    A. debt and finance leases including current maturities, one tag;
    B. long-term debt including current maturities (LongTermDebt), one tag;
    C. a noncurrent figure plus a current one. DebtCurrent already includes
       short-term borrowings, so they are not added on top of it.

    When the company reports debt *together with* finance leases (the
    ...AndCapitalLeaseObligations tags), the result says so and the bridge
    does not add finance leases again."""
    g = lambda c: fl.instant(c, on)                                  # noqa: E731
    incl_leases, st_included = False, False
    current_part: Optional[Dict[str, Any]] = None
    note = None
    total = g("ltd_and_leases_total")
    if total:
        lt, rule, lt_parts, incl_leases = total, "A: debt and finance leases incl. current maturities", [total], True
        current_part = g("ltd_and_leases_current")
    elif g("ltd_total"):
        lt = g("ltd_total")
        rule, lt_parts = "B: long-term debt incl. current maturities", [lt]
        current_part = g("ltd_current")
    else:
        nc = g("ltd_and_leases_noncurrent")
        incl_leases = bool(nc)
        nc = nc or g("ltd_noncurrent")
        cur = g("debt_current")
        st_included = bool(cur)
        cur = cur or g("ltd_and_leases_current") or g("ltd_current")
        if nc or cur:
            lt = _derived("ltd", (_v(nc) or 0.0) + (_v(cur) or 0.0), [nc, cur], "noncurrent + current")
            rule, lt_parts, current_part = "C: noncurrent + current", [nc, cur], cur
            if not (nc and cur):
                note = ("Only the {} portion is tagged on this date; the other is treated as none."
                        .format("noncurrent" if nc else "current"))
        else:
            # D: the separate instruments REITs and some others tag instead
            # of a debt total. Summed, and said to be summed.
            pieces = [g(c) for c in ("notes_payable", "unsecured_debt", "secured_debt",
                                     "line_of_credit", "line_of_credit_lt")]
            if any(pieces):
                lt = _derived("ltd", sum(_v(p) or 0.0 for p in pieces), pieces,
                              "notes + unsecured + secured debt + credit lines")
                rule, lt_parts = "D: separate debt instruments summed", pieces
                note = ("No debt total is tagged, so the separately tagged instruments are added "
                        "together. Check the filing's debt note: an instrument tagged under a "
                        "different name would be missing.")
            else:
                lt, rule, lt_parts = None, "none reported", []
    st_parts: List[Optional[Dict[str, Any]]] = []
    st_val = 0.0
    if not st_included:
        st = g("short_term_borrowings")
        if st:
            st_val, st_parts = _v(st) or 0.0, [st]
        else:
            cp, other = g("commercial_paper"), g("other_short_term_borrowings")
            st_val = (_v(cp) or 0.0) + (_v(other) or 0.0)
            st_parts = [cp, other]
    value = (_v(lt) or 0.0) + st_val
    if lt is None and not any(st_parts):
        fact = _zero("debt", on, "No borrowings are tagged on this balance sheet; treated as none.")
    else:
        fact = _derived("debt", value, lt_parts + st_parts,
                        rule + ("" if st_included else " + short-term borrowings and commercial paper"), note)
    if incl_leases:
        fact["includes_finance_leases"] = True
    current_val = (_v(current_part) or 0.0) + st_val
    return {"value": value, "fact": fact, "includes_finance_leases": incl_leases,
            "current": _derived("debt_current", current_val, [current_part] + st_parts,
                                "current maturities + short-term borrowings"), "rule": rule}


def finance_leases_on(fl: Filings, on: str, included_in_debt: bool) -> Dict[str, Any]:
    if included_in_debt:
        return {"value": 0.0, "kind": "included_elsewhere", "concept": "finance_leases", "end": on,
                "note": "Already inside the debt figure (reported together as debt and finance "
                        "lease obligations), so not added again."}
    f = fl.instant("finance_lease", on)
    if f:
        return f
    cur, nc = fl.instant("finance_lease_current", on), fl.instant("finance_lease_noncurrent", on)
    if cur or nc:
        return _derived("finance_leases", (_v(cur) or 0.0) + (_v(nc) or 0.0), [cur, nc], "current + noncurrent")
    return _zero("finance_leases", on, "No finance lease liability tagged on this date; treated as none.")


def investments_on(fl: Filings, on: str) -> Dict[str, Any]:
    """Long-term investments the operating forecast does not earn on:
    marketable securities and equity-method stakes, at book value."""
    lti = fl.instant("long_term_investments", on)
    if lti and lti["tag"] == "LongTermInvestments":
        lti = dict(lti, note="Book value. Equity-method stakes are assumed to be inside this line, "
                             "as most balance sheets present them, so they are not added again.")
        return lti
    eq = fl.instant("equity_method", on)
    other = fl.instant("other_long_term_investments", on)
    # Equity stakes tagged on their own (Nvidia's listed and non-marketable
    # holdings) count only when no other-investments total is tagged: where
    # one is (Alphabet), the stakes are already inside it.
    stakes: List[Optional[Dict[str, Any]]] = []
    if other is None:
        stakes = [fl.instant("equity_securities_fv", on), fl.instant("equity_securities_nonmarketable", on)]
    parts = [lti, eq, other] + stakes
    if any(parts):
        return _derived("long_term_investments", sum(_v(p) or 0.0 for p in parts), parts,
                        "marketable securities + equity-method + other long-term investments + equity stakes",
                        "Book values. A stake in a listed or recently funded company can be worth far "
                        "more or less than its carrying amount. Equity securities are assumed non-current "
                        "unless a current-investments tag shows otherwise.")
    return _zero("long_term_investments", on, "No long-term investments tagged; treated as none.")


def balance_sheet(fl: Filings, on: str) -> Dict[str, Any]:
    """Every balance the models need on one date, with its provenance."""
    g = lambda c: fl.instant(c, on)                                  # noqa: E731
    out: Dict[str, Any] = {"date": on}
    debt = debt_on(fl, on)
    out["debt"] = debt["fact"]
    out["debt_current"] = debt["current"]
    out["finance_leases"] = finance_leases_on(fl, on, debt["includes_finance_leases"])
    out["debt_includes_finance_leases"] = debt["includes_finance_leases"]
    out["cash"] = g("cash") or _none("cash", "No cash balance tagged on this date.")
    if out["cash"].get("tag") == "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents":
        out["cash"]["note"] = "Includes restricted cash: the unrestricted figure is not tagged on this date."
    out["short_term_investments"] = g("short_term_investments") or _zero(
        "short_term_investments", on, "No short-term investments tagged; treated as none.")
    out["long_term_investments"] = investments_on(fl, on)
    out["noncontrolling_interests"] = g("nci") or _zero(
        "noncontrolling_interests", on, "No non-controlling interest tagged; treated as none.")
    out["preferred"] = g("preferred") or _zero("preferred", on, "No preferred stock tagged; treated as none.")
    pension = fl.latest_instant("pension_funded_status", on)
    if pension and (_v(pension) or 0) < 0:
        out["pension_deficit"] = dict(pension, value=-_v(pension), kind="derived",
                                      note="Funded status from the latest annual report, pre-tax. "
                                           "Negative status means obligations exceed plan assets.")
    elif pension:
        out["pension_deficit"] = dict(pension, value=0.0, kind="derived",
                                      note="Plans are funded or overfunded ({:,.0f}); a surplus is "
                                           "not added, since it is rarely freely available to "
                                           "shareholders.".format(_v(pension)))
    else:
        out["pension_deficit"] = _zero("pension_deficit", on, "No defined-benefit funded status tagged.")
    out["operating_lease"] = g("operating_lease")
    out["equity"] = g("equity")
    if out["equity"] is None:
        tot, nci = g("equity_incl_nci"), g("nci")
        if tot:
            out["equity"] = _derived("equity", _v(tot) - (_v(nci) or 0.0), [tot, nci],
                                     "equity incl. non-controlling interests - NCI")
        else:
            out["equity"] = _none("equity", "No shareholders' equity tagged on this date.")
    out["equity_incl_nci"] = g("equity_incl_nci")
    out["temporary_equity"] = g("temporary_equity")
    out["assets"] = g("assets")
    out["liabilities"] = g("liabilities")
    out["assets_current"] = g("assets_current")
    out["liabilities_current"] = g("liabilities_current")
    out["ppe"] = g("ppe")
    out["real_estate_net"] = g("real_estate_net")
    out["operating_lease_current"] = g("operating_lease_current")
    out["finance_lease_current"] = g("finance_lease_current")

    # Operating working capital: current assets less cash and short-term
    # investments, less current liabilities other than debt and leases.
    ca, cl = _v(out["assets_current"]), _v(out["liabilities_current"])
    if ca is not None and cl is not None and _v(out["cash"]) is not None:
        excl_a = _v(out["cash"]) + (_v(out["short_term_investments"]) or 0.0)
        excl_l = ((_v(out["debt_current"]) or 0.0) + (_v(out["operating_lease_current"]) or 0.0)
                  + (_v(out["finance_lease_current"]) or 0.0))
        out["nwc"] = _derived("nwc", (ca - excl_a) - (cl - excl_l),
                              [out["assets_current"], out["cash"], out["short_term_investments"],
                               out["liabilities_current"], out["debt_current"],
                               out["operating_lease_current"], out["finance_lease_current"]],
                              "(current assets - cash - short-term investments) - "
                              "(current liabilities - current debt - current lease liabilities)")
        out["operating_current_assets"] = ca - excl_a
        out["operating_current_liabilities"] = cl - excl_l
        if out["finance_lease_current"] is None and _v(out["finance_leases"]):
            out["nwc"]["note"] = ("The current part of finance leases is not tagged separately, so it "
                                  "stays inside current liabilities and slightly lowers working capital.")
    else:
        out["nwc"] = _none("nwc", "The balance sheet is not split into current and non-current "
                                  "(usual for banks, insurers and many REITs).")
    return out


# ---------------------------------------------------------------------------
# The full input set
# ---------------------------------------------------------------------------

def _ratio(a: Optional[float], b: Optional[float]) -> Optional[float]:
    if a is None or b is None or b == 0:
        return None
    return a / b


def history(fl: Filings, fy_ends: List[str]) -> List[Dict[str, Any]]:
    """Up to five fiscal years of the figures the forecast is anchored on,
    newest first, each with its facts."""
    years: List[Dict[str, Any]] = []
    for end in fy_ends[:HISTORY_YEARS + 1]:
        f = {c: fl.flow(c, end) for c in FLOWS}
        if f["da"] is None and f["depreciation"]:
            f["da"] = _derived("da", _v(f["depreciation"]) + (_v(f["amortization"]) or 0.0),
                               [f["depreciation"], f["amortization"]], "depreciation + amortization of intangibles",
                               None if f["amortization"] else
                               "No amortization of intangibles tagged for this year; depreciation only.")
        if f["operating_income"] is None and f["pretax_income"] is not None and f["interest_expense"] is not None:
            # Some filers (Nucor, for one) report no operating-income line.
            # EBIT is then rebuilt as pre-tax income + interest expense -
            # interest income, and said to be: it still holds other
            # non-operating items such as equity-method income.
            f["operating_income"] = _derived(
                "operating_income",
                _v(f["pretax_income"]) + _v(f["interest_expense"]) - (_v(f["interest_income"]) or 0.0),
                [f["pretax_income"], f["interest_expense"], f["interest_income"]],
                "pre-tax income + interest expense - interest income",
                "No operating-income line in the filing; rebuilt from pre-tax income, so other "
                "non-operating items (equity-method income, gains) remain inside it.")
        bs = balance_sheet(fl, end)
        years.append({"fy_end": end, "flows": f, "balance": bs})
    derive(years)
    return years[:HISTORY_YEARS]


def derive(years: List[Dict[str, Any]]) -> None:
    """Ratios computed from each year's facts (and the prior year's), in
    place. Separate from history() so that a figure the reader supplies for a
    line the filings lack can be put in and the ratios recomputed."""
    # Derived ratios, needing the prior year for changes and averages.
    for i, y in enumerate(years):
        f, bs = y["flows"], y["balance"]
        prior = years[i + 1] if i + 1 < len(years) else None
        rev, ebit = _v(f["revenue"]), _v(f["operating_income"])
        pretax, tax = _v(f["pretax_income"]), _v(f["income_tax"])
        da, capex = _v(f["da"]), _v(f["capex"])
        nwc = _v(bs["nwc"])
        nwc_prior = _v(prior["balance"]["nwc"]) if prior else None
        rev_prior = _v(prior["flows"]["revenue"]) if prior else None
        d_nwc = (nwc - nwc_prior) if (nwc is not None and nwc_prior is not None) else None
        eff_tax = _ratio(tax, pretax) if (pretax and pretax > 0) else None
        derived = {
            "revenue_growth": (rev / rev_prior - 1.0) if (rev and rev_prior and rev_prior > 0) else None,
            "ebit_margin": _ratio(ebit, rev),
            "effective_tax_rate": eff_tax,
            "da_pct": _ratio(da, rev), "capex_pct": _ratio(capex, rev),
            "nwc_pct": _ratio(nwc, rev), "change_nwc": d_nwc,
            "sbc_pct": _ratio(_v(f["sbc"]), rev),
            "dep_rate": _ratio(da, _v(prior["balance"]["ppe"])) if prior and _v(prior["balance"]["ppe"]) else None,
        }
        if ebit is not None and eff_tax is not None and da is not None and capex is not None and d_nwc is not None:
            t = min(max(eff_tax, 0.0), 0.5)
            derived["fcff"] = ebit * (1 - t) + da - capex - d_nwc
        else:
            derived["fcff"] = None
        cfo = _v(f["cfo"])
        derived["fcf_simple"] = (cfo - capex) if (cfo is not None and capex is not None) else None
        # Invested capital from the financing side, so it reconciles with the
        # bridge: equity + NCI + debt + finance leases - cash and investments.
        ic = invested_capital(bs)
        derived["invested_capital"] = ic
        ic_prior = invested_capital(prior["balance"]) if prior else None
        if ebit is not None and ic_prior and ic_prior > 0:
            t = eff_tax if eff_tax is not None else 0.21
            derived["roic"] = ebit * (1 - min(max(t, 0.0), 0.5)) / ic_prior
        else:
            derived["roic"] = None
        ni_c = _v(f["net_income_common"])
        eq, eq_prior = _v(bs["equity"]), _v(prior["balance"]["equity"]) if prior else None
        derived["roe"] = (ni_c / ((eq + eq_prior) / 2.0)) if (ni_c is not None and eq and eq_prior and eq + eq_prior > 0) else None
        div = _v(f["dividends_paid"])
        derived["payout_ratio"] = _ratio(div, ni_c) if (ni_c and ni_c > 0 and div is not None) else None
        bb = _v(f["buybacks"])
        derived["buyback_ratio"] = _ratio(bb, ni_c) if (ni_c and ni_c > 0 and bb is not None) else None
        # Tagged unusual items, added back for a normalised margin. Impairment
        # is the larger of the asset-impairment total and its goodwill and
        # intangible parts, because some filers report the total and some the
        # parts, and summing all three would count the parts twice.
        imp_parts = (_v(f["goodwill_impairment"]) or 0.0) + (_v(f["intangible_impairment"]) or 0.0)
        impairment = max(_v(f["asset_impairment"]) or 0.0, imp_parts)
        unusual = impairment + (_v(f["restructuring"]) or 0.0) + max(0.0, _v(f["contingent_consideration"]) or 0.0)
        derived["unusual_items"] = unusual if any(f[k] for k in ("restructuring", "goodwill_impairment",
                                                                "intangible_impairment", "asset_impairment",
                                                                "contingent_consideration")) else None
        derived["ebit_margin_normalized"] = ((ebit + unusual) / rev) if (ebit is not None and rev and unusual) else derived["ebit_margin"]
        acq = _v(f["acquisitions"])
        derived["acquisitions_pct"] = (acq / rev) if (acq is not None and rev) else None
        y["derived"] = derived


def _ytd(fl: Filings, concept: str, start: str, end: str, tol: int = 3,
         tag_only: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """A year-to-date total from a 10-Q: the period starting with the fiscal
    year and ending on `end` (within `tol` days, for 52/53-week quarters)."""
    unit = UNITS.get(concept, "USD")
    for tag in ([tag_only] if tag_only else TAGS[concept]):
        rows = [r for r in fl._rows(tag, unit)                                              # noqa: SLF001
                if r.get("form") in ("10-Q", "10-Q/A") and r.get("start")
                and _near(r["start"], start, 7) and _near(r["end"], end, tol) and _num(r.get("val")) is not None]
        if rows:
            return fl._fact(concept, tag, rows, unit)                                       # noqa: SLF001
    return None


TRAILING = ("revenue", "operating_income", "net_income", "capex", "da", "cfo")


def trailing(fl: Filings, hist: List[Dict[str, Any]], bal_date: str) -> Dict[str, Any]:
    """Trailing twelve months to the latest 10-Q, built the standard way:
    last fiscal year + this year to date - the same months a year earlier.
    Every part is a reported figure, so annual and quarterly periods are
    combined only in this one documented way and never mixed silently."""
    if not hist or not bal_date:
        return {"available": False, "reason": "No fiscal year to start from."}
    fy0 = hist[0]
    if (_days(fy0["fy_end"], bal_date) or 0) < 60:
        return {"available": False, "reason": "No quarter has been reported since the last annual report, so "
                                              "the trailing year is the fiscal year itself."}
    start = None
    for c in ("revenue", "operating_income", "net_income"):
        f = fy0["flows"].get(c)
        if f and f.get("start") and f.get("tag"):
            start = f["start"]
            break
    if start is None:
        return {"available": False, "reason": "The fiscal year's start date is not in the filings."}
    from datetime import timedelta as _td
    cur_start = (date.fromisoformat(fy0["fy_end"]) + _td(days=1)).isoformat()
    prior_end = (date.fromisoformat(bal_date[:10]) - _td(days=364)).isoformat()
    out: Dict[str, Any] = {"available": True, "period_end": bal_date, "fy0_end": fy0["fy_end"], "values": {}}
    for c in TRAILING:
        fy = fy0["flows"].get(c)
        if fy is None or not fy.get("tag"):
            out["values"][c] = {"value": None, "reason": "not a single reported figure for the fiscal year"}
            continue
        # The same tag in all three parts, so one definition throughout.
        cur = _ytd(fl, c, cur_start, bal_date, tag_only=fy["tag"])
        # The comparable months a year earlier, from the fiscal year before.
        prior = _ytd(fl, c, start, prior_end, tol=10, tag_only=fy["tag"]) if cur else None
        if cur is None or prior is None:
            out["values"][c] = {"value": None, "reason": "a year-to-date figure under the same tag is missing"}
            continue
        out["values"][c] = _derived(c, _v(fy) + _v(cur) - _v(prior), [fy, cur, prior],
                                    "fiscal year + year to date - same period a year earlier")
    rev_t, rev_0 = out["values"]["revenue"].get("value"), _v(fy0["flows"].get("revenue"))
    out["revenue_change_vs_fy0"] = (rev_t / rev_0 - 1.0) if (rev_t and rev_0) else None
    ebit_t = out["values"]["operating_income"].get("value")
    out["ebit_margin"] = (ebit_t / rev_t) if (ebit_t is not None and rev_t) else None
    return out


def invested_capital(bs: Dict[str, Any]) -> Optional[float]:
    eq = _v(bs.get("equity"))
    if eq is None:
        return None
    return (eq + (_v(bs.get("noncontrolling_interests")) or 0.0) + (_v(bs.get("preferred")) or 0.0)
            + (_v(bs.get("debt")) or 0.0) + (_v(bs.get("finance_leases")) or 0.0)
            - (_v(bs.get("cash")) or 0.0) - (_v(bs.get("short_term_investments")) or 0.0)
            - (_v(bs.get("long_term_investments")) or 0.0))


def shares(fl: Filings, quote: Dict[str, Any], provider_shares: Optional[float]) -> Dict[str, Any]:
    """Diluted shares for a per-share value: shares outstanding on the latest
    cover page plus the dilutive securities the company itself counted in its
    latest diluted EPS (the gap between its diluted and basic weighted
    averages, which is the treasury-stock-method increment)."""
    cover = fl.cover_shares()
    latest = fl.latest_period_shares() or {}
    dil, bas = latest.get("diluted"), latest.get("basic")
    increment = max(0.0, _v(dil) - _v(bas)) if (dil and bas) else None
    out: Dict[str, Any] = {"increment": increment, "diluted_avg": dil, "basic_avg": bas}
    bal = fl.balance_dates()
    so = fl.instant("shares_outstanding", bal[0]) if bal else None
    if cover:
        basic = _v(cover)
        out["basic"] = cover
        method = "cover-page shares outstanding + dilution in the latest diluted EPS"
    elif so:
        basic = _v(so)
        out["basic"] = so
        method = "balance-sheet shares outstanding + dilution in the latest diluted EPS"
    elif dil:
        basic, increment = _v(dil), 0.0
        out["basic"] = dil
        method = ("weighted-average diluted shares of the latest period (no single cover-page "
                  "count: several share classes)")
    else:
        if provider_shares:
            basic = provider_shares
            out["basic"] = {"value": provider_shares, "kind": "external", "source": "Yahoo Finance quote",
                            "note": "Undated count from the quote feed."}
            method = "quote feed's shares outstanding"
        else:
            return {"value": None, "reason": "No share count in the filings or the quote feed.", **out}
    diluted = basic + (increment or 0.0)
    out.update({"value": diluted, "method": method,
                "note": ("Options and restricted stock already granted are counted through the "
                         "company's own diluted-EPS share count. Future grants are not added: "
                         "they are paid for through the stock compensation expense left in EBIT.")})
    price, mcap = _num(quote.get("price")), _num(quote.get("market_cap"))
    if price and mcap:
        implied = mcap / price
        out["market_implied"] = implied
        if diluted and abs(implied / diluted - 1.0) > 0.05:
            out["cross_check"] = ("The quote's market value implies {:,.0f} shares, {:+.1%} from this count. "
                                  "Share classes, a recent buyback or a listing ratio can explain it; check "
                                  "before trusting the per-share figure.".format(implied, implied / diluted - 1.0))
    return out


def regression_beta(provider, sym: str, bench: str = "SPY") -> Dict[str, Any]:
    """Beta from five years of monthly returns against SPY, for when the quote
    feed gives none. The same kind of estimate the feed reports (a regression
    on past returns), computed here and labelled as computed here."""
    try:
        a = provider.history(sym, period="5y", interval="1mo")
        b = provider.history(bench, period="5y", interval="1mo")
        ra = a["Close"].pct_change().dropna()
        rb = b["Close"].pct_change().dropna()
        ra.index, rb.index = ra.index.to_period("M"), rb.index.to_period("M")
        joined = ra.to_frame("a").join(rb.to_frame("b"), how="inner").dropna()
    except Exception as exc:                                                                # noqa: BLE001
        return {"value": None, "reason": "Price history unavailable ({}).".format(type(exc).__name__)}
    if len(joined) < 36:
        return {"value": None, "reason": "Fewer than 36 months of shared price history."}
    var = float(joined["b"].var())
    if var <= 0:
        return {"value": None, "reason": "No variation in the benchmark's returns."}
    beta = float(joined["a"].cov(joined["b"])) / var
    return {"value": beta, "kind": "derived", "months": int(len(joined)),
            "source": "Computed by Optic: {} months of monthly returns against SPY (Yahoo price history)".format(len(joined)),
            "note": "Used because the quote feed gave no beta."}


def risk_free(provider) -> Dict[str, Any]:
    """The 10-year US Treasury constant-maturity yield, from FRED (DGS10)."""
    from .. import fred
    try:
        obs = fred.observations("DGS10")
        if obs:
            day, value = obs[-1]
            return {"value": float(value) / 100.0, "as_of": str(day), "kind": "reported",
                    "source": "FRED DGS10, 10-year Treasury constant-maturity yield",
                    "url": "https://fred.stlouisfed.org/series/DGS10",
                    "retrieved": retrieved_at("fred:DGS10")}
    except Exception:                                                                       # noqa: BLE001
        pass
    try:
        q = provider.quote("^TNX") or {}
        v = _num(q.get("price"))
        if v:
            v = v / 10.0 if v > 20 else v
            return {"value": v / 100.0, "as_of": q.get("as_of"), "kind": "reported",
                    "source": "Yahoo Finance ^TNX (10-year Treasury yield index)",
                    "note": "FRED did not answer; the exchange index is used instead."}
    except Exception:                                                                       # noqa: BLE001
        pass
    return {"value": None, "reason": "Neither FRED nor the quote feed returned a Treasury yield. "
                                     "Enter a risk-free rate to compute the discount rate."}


def consensus(provider, ticker: str, fy0_revenue: Optional[float]) -> Dict[str, Any]:
    """Analysts' average revenue estimates for the current and next fiscal
    year, used only when their base year matches the filings' last year."""
    try:
        est = provider.estimates(ticker) or {}
    except Exception:                                                                       # noqa: BLE001
        return {"available": False, "reason": "The estimates feed did not answer."}
    rev = est.get("revenue_estimate") or {}
    out: Dict[str, Any] = {"available": False, "source": "Yahoo Finance analyst revenue estimates",
                           "kind": "external_estimate"}
    y0, y1 = rev.get("0y") or {}, rev.get("+1y") or {}
    avg0, ago0, avg1 = _num(y0.get("avg")), _num(y0.get("yearAgoRevenue")), _num(y1.get("avg"))
    if not (avg0 and ago0):
        out["reason"] = "No revenue estimate for the current fiscal year."
        return out
    if fy0_revenue and abs(ago0 / fy0_revenue - 1.0) > 0.03:
        out["reason"] = ("The estimates' base year ({:,.0f}) does not match the last reported fiscal year "
                         "({:,.0f}); the periods may differ, so the estimates are not used.".format(ago0, fy0_revenue))
        return out
    out.update({"available": True, "growth_y1": avg0 / ago0 - 1.0,
                "growth_y2": (avg1 / avg0 - 1.0) if avg1 else None,
                "analysts_y1": _num(y0.get("numberOfAnalysts")), "analysts_y2": _num(y1.get("numberOfAnalysts")),
                "low_y1": _num(y0.get("low")), "high_y1": _num(y0.get("high")),
                "avg_y1": avg0, "avg_y2": avg1})
    return out


def gather(provider, ticker: str, today: Optional[date] = None, force: bool = False) -> Dict[str, Any]:
    """Everything the models need for one company, sourced. Returns
    {"available": False, "reason": ...} when a model cannot honestly be built."""
    sym = (ticker or "").upper().strip()
    today = today or datetime.now(timezone.utc).date()
    try:
        quote = provider.quote(sym) or {}
    except Exception as exc:                                                               # noqa: BLE001
        return {"available": False, "ticker": sym, "reason": "The quote feed did not answer ({}).".format(
            str(exc)[:80])}
    qtype = (quote.get("quote_type") or "").upper()
    if qtype and qtype != "EQUITY":
        # in words a reader uses ("SPY is a fund"), not the feed's type code ("a etf")
        word = {"ETF": "fund", "MUTUALFUND": "mutual fund", "INDEX": "index", "CRYPTOCURRENCY": "cryptocurrency",
                "CURRENCY": "currency", "FUTURE": "futures contract"}.get(qtype, qtype.lower())
        return {"available": False, "ticker": sym,
                "reason": "{} is {} {}, not a company; a cash-flow valuation needs a business's own "
                          "statements.".format(sym, "an" if word[:1] in "aeiou" else "a", word)}
    fl, cik, reason = load_filings(sym, force=force)
    if fl is None:
        return {"available": False, "ticker": sym, "reason": reason}
    fy_ends = fl.fiscal_year_ends()
    other_units = sorted({u for c in ("revenue", "net_income") for t in TAGS[c]
                          for u in ((fl.gaap.get(t) or {}).get("units") or {}) if u != "USD"})
    if not fy_ends and other_units:
        return {"available": False, "ticker": sym,
                "reason": "The filings report in {} rather than US dollars. This model reads USD figures only and "
                          "does not convert, because a per-share value in one currency against a price in another, "
                          "at a rate chosen here, would mix two sources of error.".format(", ".join(other_units))}
    if not fy_ends:
        why = ("The filings are IFRS (a foreign issuer's 20-F); this model reads US-GAAP filings only."
               if fl.ifrs else
               "This registrant has no annual US-GAAP figures yet. A company that recently moved under "
               "a new holding company files its history under the predecessor's CIK, which this "
               "model does not join, so nothing is estimated.")
        return {"available": False, "ticker": sym, "reason": why}
    hist = history(fl, fy_ends)
    fy0 = hist[0]
    bal_dates = fl.balance_dates()
    bal_date = bal_dates[0] if bal_dates else fy0["fy_end"]
    # A balance sheet more than a year past FY0 would mean the base year is
    # stale relative to it; use FY0's own balance sheet then.
    if (_days(fy0["fy_end"], bal_date) or 0) >= 365:
        bal_date = fy0["fy_end"]
    bal = balance_sheet(fl, bal_date) if bal_date != fy0["fy_end"] else fy0["balance"]
    try:
        short = provider.short_interest(sym) or {}
    except Exception:                                                                      # noqa: BLE001
        short = {}
    ttm = trailing(fl, hist, bal_date)
    acq3 = [y["derived"].get("acquisitions_pct") for y in hist[:3]]
    big = [(y["fy_end"], y["derived"]["acquisitions_pct"]) for y in hist[:3]
           if (y["derived"].get("acquisitions_pct") or 0) > 0.10]
    sh = shares(fl, quote, _num(short.get("shares_outstanding")))
    beta, beta_meta = _num(quote.get("beta")), {"source": "Yahoo Finance quote (5-year monthly regression)",
                                                  "kind": "market"}
    if beta is None:
        beta_meta = regression_beta(provider, sym)
        beta = beta_meta.get("value")
    subs = submissions(cik) if cik else {}

    warnings: List[str] = []
    price_ccy = quote.get("currency")
    stmt_ccy = quote.get("financial_currency") or "USD"
    if price_ccy and price_ccy != "USD":
        warnings.append("The price is in {} and the filings in USD. Per-share values are in USD and "
                        "are not comparable with the price without conversion.".format(price_ccy))
    if stmt_ccy and stmt_ccy != "USD":
        warnings.append("The quote feed says the statements are in {}, but the SEC facts read here are "
                        "tagged USD. Check the filing.".format(stmt_ccy))
    age = _days(fy0["fy_end"], today.isoformat()) or 0
    if age > 456:
        warnings.append("The last annual report covers a year that ended {} days ago; a newer one may be "
                        "missing from the filings feed.".format(age))
    d_now, d_fy = _v(bal["debt"]), _v(fy0["balance"]["debt"])
    if bal_date != fy0["fy_end"] and d_now is not None and d_fy and abs(d_now / d_fy - 1.0) > 0.4:
        warnings.append("Debt on {} ({:,.0f}) differs from the last annual report ({:,.0f}) by {:+.0%}. "
                        "Check whether the quarter's filing tags debt differently before relying on "
                        "the bridge.".format(bal_date, d_now, d_fy, d_now / d_fy - 1.0))
    if sh.get("cross_check"):
        warnings.append(sh["cross_check"])
    if big or sum(a for a in acq3 if a) > 0.15:
        warnings.append("Acquisitions cost {} of revenue over the last three years{}. Past revenue growth "
                        "includes bought revenue, and the forecast does not pay for acquisitions, so growth "
                        "carried forward from history may be too high for the capex assumed.".format(
                            "{:.0%}".format(sum(a for a in acq3 if a)),
                            " (more than 10% in " + ", ".join(e[:4] for e, _ in big) + ")" if big else ""))
    restated = sorted({c for y in hist[:3] for c, f in y["flows"].items() if f and f.get("restated")})
    if restated:
        warnings.append("Restated in a later filing (the latest figures are used): {}.".format(
            ", ".join(restated)))

    return {
        "available": True, "ticker": sym, "cik": cik,
        # The quote's name, unless the feed fell back to the bare symbol.
        "name": (quote.get("name") if quote.get("name") and quote.get("name") != sym else None)
                or fl.name or sym,      # as filed: title-casing made "JPMORGAN" read "Jpmorgan"
        "quote": {
            "price": _num(quote.get("price")), "as_of": quote.get("as_of"), "market_time": quote.get("market_time"),
            "currency": price_ccy, "market_cap": _num(quote.get("market_cap")), "beta": beta,
            "beta_meta": beta_meta,
            "dividend_yield": _num(quote.get("dividend_yield")), "sector": quote.get("sector"),
            "industry": quote.get("industry"), "trailing_pe": _num(quote.get("trailing_pe")),
            "price_to_book": _num(quote.get("price_to_book")), "source": "Yahoo Finance quote",
        },
        "profile": subs,
        "fy_ends": fy_ends[:HISTORY_YEARS],
        "history": hist,
        "balance_date": bal_date,
        "balance": bal,
        "trailing": ttm,
        "shares": sh,
        "risk_free": risk_free(provider),
        "consensus": consensus(provider, sym, _v(fy0["flows"]["revenue"])),
        "statement_currency": "USD",
        "retrieved": fl.retrieved,
        "valuation_date": today.isoformat(),
        "warnings": warnings,
        "source_note": ("Statements: SEC EDGAR XBRL company facts (us-gaap), each figure linked to its "
                        "filing. Price, beta and analyst estimates: Yahoo Finance. Risk-free rate: FRED."),
    }


EXTENSION_PATTERNS = {
    "capex": r"CapitalExpenditure|PaymentsToAcquire.*(Property|Plant|Productive|Capital)",
    "da": r"Depreciation",
    "operating_income": r"OperatingIncome",
}


def extension_candidates(ticker: str, concept: str, fy_start: str, fy_end: str, limit: int = 6) -> Dict[str, Any]:
    """Figures the company's 10-K reports under its own extension elements
    (which the SEC facts API leaves out) for a line the model is missing:
    consolidated contexts only, the base fiscal year's exact period, element
    names matching the line. Offered to the reader as suggestions with their
    names; never applied by the model, because which extension is the right
    one is a judgement about the company's own presentation."""
    import re as _re
    import xml.etree.ElementTree as _ET
    from ..analytics import segments as _seg
    pat = EXTENSION_PATTERNS.get(concept)
    if not pat:
        return {"available": False, "reason": "No search defined for this line."}
    try:
        listed = _seg.filings(ticker)
    except Exception as exc:                                                               # noqa: BLE001
        return {"available": False, "reason": "The filing list did not answer ({}).".format(type(exc).__name__)}
    k = next((r for r in (listed.get("rows") or []) if r.get("form") == "10-K"
              and _near(r.get("report_date") or r.get("period") or fy_end, fy_end, 10)), None)
    if not k:
        return {"available": False, "reason": "The base year's 10-K is not in the filing list."}
    try:
        body = feeds.fetch_text(k["instance_url"], 30 * 86400, key="val:ext:" + k["accession"], store=False)
        root = _ET.fromstring(body.encode("utf-8", "replace"))
    except Exception as exc:                                                               # noqa: BLE001
        return {"available": False, "reason": "The 10-K's XBRL document could not be read ({}).".format(
            type(exc).__name__)}
    X = "{http://www.xbrl.org/2003/instance}"
    plain = set()
    for ctx in root.findall(X + "context"):
        ent = ctx.find(X + "entity")
        dims = (ent is not None and ent.find(X + "segment") is not None) or ctx.find(X + "scenario") is not None
        per = ctx.find(X + "period")
        if dims or per is None:
            continue
        if _near(per.findtext(X + "startDate") or "", fy_start, 7) and _near(per.findtext(X + "endDate") or "", fy_end, 7):
            plain.add(ctx.get("id"))
    found: Dict[str, float] = {}
    for el in root:
        m = _re.match(r"\{([^}]+)\}(.+)", el.tag)
        if not m or "fasb.org/us-gaap" in m.group(1) or el.get("contextRef") not in plain:
            continue
        name = m.group(2)
        if not _re.search(pat, name) or _re.search(r"Proceeds|Incurred|NotYetPaid|Commitment|Planned", name):
            continue
        val = _num(el.text)
        if val is not None and name not in found:
            found[name] = val
    cands = sorted(({"element": n, "value": v} for n, v in found.items()), key=lambda c: -abs(c["value"]))[:limit]
    return {"available": bool(cands), "candidates": cands, "accession": k["accession"],
            "url": filing_url(k.get("cik") or "", k["accession"]) if k.get("cik") else None,
            "instance_url": k["instance_url"],
            "reason": None if cands else "The 10-K has no extension element for this line either."}
