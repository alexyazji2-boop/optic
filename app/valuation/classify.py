"""Which valuation models fit which business, and how much to trust the answer.

A discounted-cash-flow model of free cash flow to the firm assumes debt is a
financing choice and working capital and capex are operating needs. That holds
for most companies and fails for three kinds:

* **Banks and lenders.** Debt and deposits are the raw material, interest is
  the cost of goods sold, and "capex" and "working capital" have no clean
  meaning. Value the equity directly: residual income (book value plus the
  value of returns above the cost of equity) and justified price-to-book.
* **Insurers.** Float and reserves are operating liabilities and regulatory
  capital limits payouts. Same remedy as banks.
* **REITs.** Growth comes from buying property with new equity and debt, and
  depreciation of buildings overstates the economic cost, so earnings are
  restated as funds from operations (FFO). Dividends are most of the payout by
  law, which makes a dividend discount model a reasonable cross-check.

Businesses that have not yet earned a profit can be modelled, but the answer
rests almost entirely on an assumed future margin, so confidence is stated as
low and the reverse DCF (what the price already assumes) leads.

Classification reads the SEC's standard industrial classification code first
and the quote feed's industry label second.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

BANK_SIC = {"6021", "6022", "6029", "6035", "6036", "6111", "6141", "6153", "6159", "6162", "6172", "6189"}
INSURER_SIC = {"6311", "6321", "6324", "6331", "6351", "6361", "6399"}
REIT_SIC = {"6798"}
UTILITY_PREFIX = ("49",)
CYCLICAL_SIC_PREFIX = ("10", "12", "13", "14", "29", "331", "333", "334", "335", "28", "44")

LABELS = {
    "operating": "Operating company",
    "bank": "Bank or lender",
    "insurer": "Insurer",
    "reit": "Real estate investment trust",
    "utility": "Regulated utility",
    "cyclical": "Cyclical (commodity or heavy industry)",
    "unprofitable": "Not yet profitable",
}

MODEL_NAMES = {
    "dcf": "Enterprise DCF (free cash flow to the firm)",
    "fcfe": "Equity DCF (free cash flow to equity)",
    "ddm": "Dividend discount model",
    "residual_income": "Residual income / justified price-to-book",
    "reit_ffo": "REIT funds from operations",
    "comps": "Comparable companies",
    "sotp": "Sum of the parts",
    "reverse_dcf": "Reverse DCF",
}


def business_type(sic: Optional[str], industry: Optional[str], history: List[Dict[str, Any]]) -> str:
    sic = (sic or "").strip()
    ind = (industry or "").lower()
    if sic in REIT_SIC or ind.startswith("reit"):
        return "reit"
    if sic in BANK_SIC or ind.startswith("banks") or "credit services" in ind or "mortgage finance" in ind:
        return "bank"
    if sic in INSURER_SIC or (ind.startswith("insurance") and "brokers" not in ind):
        return "insurer"
    margins = [((y.get("derived") or {}).get("ebit_margin")) for y in history[:3]]
    known = [m for m in margins if m is not None]
    if known and (known[0] <= 0 or sum(1 for m in known if m <= 0) >= 2):
        return "unprofitable"
    if sic.startswith(UTILITY_PREFIX) or ind.startswith("utilities"):
        return "utility"
    if sic.startswith(CYCLICAL_SIC_PREFIX) or ind.startswith(("oil & gas", "steel", "copper", "aluminum",
                                                              "other industrial metals", "coking coal",
                                                              "chemicals", "agricultural inputs", "marine shipping")):
        return "cyclical"
    return "operating"


def suitability(kind: str, facts: Dict[str, Any]) -> Dict[str, Any]:
    """For each model: primary / supporting / limited / not applicable, and why.

    `facts` carries what the decision needs: has_dividend, payout_ratio,
    dividend_years, has_segments, has_nwc, buyback_heavy."""
    fit: Dict[str, Dict[str, str]] = {}
    reasons: List[str] = []

    def put(model: str, level: str, why: str) -> None:
        fit[model] = {"fit": level, "why": why, "name": MODEL_NAMES[model]}

    financial = kind in ("bank", "insurer")
    if financial:
        put("dcf", "not_applicable", "Debt is this business's raw material, not a financing choice, "
            "so free cash flow to the firm and a blended cost of capital do not describe it.")
        put("fcfe", "not_applicable", "Regulatory capital, not cash flow, limits what can be paid out; "
            "an equity cash flow needs a capital plan the filings do not give.")
        put("residual_income", "primary", "Values equity as book value plus returns above the cost of "
            "equity, which is how a balance-sheet business creates value.")
        put("reverse_dcf", "not_applicable", "Shown instead: the return on equity today's price-to-book implies.")
    elif kind == "reit":
        put("dcf", "limited", "Growth comes from buying property with new capital, which an FCFF "
            "forecast of one company's capex cannot represent well.")
        put("fcfe", "not_applicable", "Same problem as FCFF, with the financing added.")
        put("residual_income", "not_applicable", "Depreciated book value of property is not a "
            "meaningful anchor for a REIT.")
        put("reit_ffo", "primary", "Funds from operations restate earnings without property "
            "depreciation, the industry's own yardstick.")
        put("reverse_dcf", "limited", "Shown, with the same caveat as the DCF.")
    else:
        if kind == "unprofitable":
            put("dcf", "limited", "No profitable history to anchor margins on. The value rests on an "
                "assumed future margin, so treat it as a scenario, not an estimate.")
            put("reverse_dcf", "primary", "More informative here: what margin and growth today's price "
                "already assumes.")
            reasons.append("No operating profit in the latest year: the long-run margin is an assumption, "
                           "not a measurement.")
        elif kind == "cyclical":
            put("dcf", "primary", "Works if margins are set at a mid-cycle level, not the latest year's.")
            put("reverse_dcf", "supporting", "What the price implies, to compare with the cycle.")
            reasons.append("Cyclical margins: one year is a poor guide. Base margins use the average of "
                           "the available years.")
        else:
            put("dcf", "primary", "Cash flows are generated by operating assets and financed by debt and "
                "equity, which is what an enterprise DCF models.")
            put("reverse_dcf", "supporting", "What today's price implies, given the other assumptions.")
        put("fcfe", "supporting", "Same cash flows after interest and borrowing, at the cost of equity. "
            "Differs from the FCFF answer when leverage changes.")
        put("residual_income", "not_applicable", "Book value understates the assets of a company "
            "built on brands, software or R&D, so it is not a useful anchor.")
    if "reit_ffo" not in fit:
        put("reit_ffo", "not_applicable", "Not a REIT.")

    has_div = facts.get("has_dividend")
    payout = facts.get("payout_ratio")
    years = facts.get("dividend_years") or 0
    if not has_div:
        put("ddm", "not_applicable", "No regular dividend.")
    elif kind == "reit":
        put("ddm", "supporting", "REITs must distribute most of their taxable income, so dividends "
            "track cash generation.")
    elif payout is not None and 0.3 <= payout <= 1.1 and years >= 3 and not facts.get("buyback_heavy"):
        put("ddm", "supporting", "A steady dividend that pays out {:.0%} of earnings is a reasonable "
            "proxy for what shareholders receive.".format(payout))
    else:
        put("ddm", "limited", "Dividends are a small or irregular part of what is returned "
            "(buybacks or retained earnings dominate), so a dividend model understates value.")

    put("comps", "supporting", "Market-relative: says whether the price is in line with similar "
        "companies, not what the business is worth on its own cash flows.")
    if kind in ("bank", "insurer"):
        put("sotp", "not_applicable", "Segments of a financial company share one balance sheet and one "
            "capital base, so they cannot be valued apart on earnings multiples.")
    else:
        put("sotp", "supporting", "When the filings report operating income by segment, each part can be "
            "valued at its own multiple. Read on request, because it means parsing several filings.")

    if kind in ("bank", "insurer", "reit", "unprofitable"):
        confidence = "limited" if kind != "unprofitable" else "low"
    else:
        confidence = "normal"
    if facts.get("short_history"):
        reasons.append("Fewer than three fiscal years of filings to anchor the assumptions.")
        confidence = "limited" if confidence == "normal" else confidence
    primary = next((m for m, f in fit.items() if f["fit"] == "primary"), "dcf")
    return {"business_type": kind, "label": LABELS[kind], "models": fit, "primary": primary,
            "confidence": confidence, "confidence_reasons": reasons}
