"""The canonical figure registry: what each financial figure Optic shows is, written once.

Owner's Handoff 1 (2026-11-03, docs/claude-handoffs): the same concept read different values on different pages
under labels that did not say why. Measured on AAPL that day: the Financials tab printed net debt of $62.7B in the
chart caption (cash and equivalents only) and $44.0B in the block beside it (cash and short-term investments); the
Overview printed a fiscal-year net margin from Yahoo's statements (26.9%, fiscal 2025) beside Yahoo's own
twelve-month margin (27.6%), while the valuation workspace had already moved to the fiscal 2026 10-K filed that
morning; and Compare's forward P/E came from a long-term model cached at an earlier price than the Dossier's.

So every figure has an entry here, and an entry is a definition rather than a number: what the figure measures at
each knowledge level, its formula in words and in symbols, the inputs it is made of, the kind of period it covers,
its accounting basis and what it cannot tell you. The value for one company is computed by `app/figures/compute.py`,
once, and every surface (the Dossier, Compare, Milo) prints that value and its text.

Where two definitions are both legitimate (a fiscal year or the last twelve months; net debt with or without
operating leases) they are two entries with two ids, and a page that shows both labels both. They are never merged.

Definitions describe; they never judge. No entry calls a reading good, bad, cheap or expensive, and
`tests/test_figure_registry.py` holds every definition to that.
"""

from __future__ import annotations

from typing import Any, Dict, List

# The reader's five knowledge levels, in slider order (app/knowledge.py, static/v2/js/core/prefs.js LEVEL_IDS).
LEVELS = ("new", "beginner", "intermediate", "advanced", "expert")
DEFAULT_LEVEL = "intermediate"

# What each concept is, at each level. A figure's definition is its concept's sentence followed by its period's.
_CONCEPTS: Dict[str, Dict[str, Any]] = {
    "net_margin": {
        "levels": {
            "new": "Of every dollar of sales, how many cents the company kept as profit after paying all of its "
                   "costs, interest and taxes. A net margin of 25% means it kept 25 cents of each dollar.",
            "beginner": "Net income as a share of revenue: how much of each dollar of sales was left as profit "
                        "after every cost, including interest and tax.",
            "intermediate": "Net income divided by revenue, as a percentage. It shows how much of its sales a "
                            "company keeps after all costs, interest and tax. One-off gains and charges inside net "
                            "income move it too.",
            "advanced": "Bottom-line profitability: net income attributable to the company over total revenue. It "
                        "includes non-operating items, tax and any discontinued operations, so it can move for "
                        "reasons outside the core business; operating margin isolates the business itself.",
            "expert": "Net income attributable to the parent over total revenue, as filed (GAAP). Unadjusted: "
                      "one-off items, tax effects and discontinued operations stay in.",
        },
        "limits": "It is not cash: profit and cash flow can differ widely. A one-off gain or charge can lift or cut "
                  "it for a single period, and typical margins differ by industry.",
    },
    "forward_pe": {
        "levels": {
            "new": "The share price divided by the profit per share analysts expect the company to make in a coming "
                   "year. It says how many dollars buyers are paying today for each dollar of expected yearly "
                   "profit.",
            "beginner": "The share price divided by analysts' expected earnings per share for a coming fiscal year. "
                        "It rests on a forecast, so it is only as reliable as the estimates.",
            "intermediate": "Share price over the consensus forecast of earnings per share. It compares the price "
                            "with what analysts expect the company to earn, rather than what it did earn, which is "
                            "the trailing P/E.",
            "advanced": "Price over the provider's consensus EPS estimate for a coming fiscal year. Estimates are "
                        "usually on the company's adjusted basis and are revised often, so the ratio moves with "
                        "both the price and the estimate.",
            "expert": "Last price over consensus forward EPS (Yahoo Finance's forwardEps). The provider does not "
                      "disclose which fiscal year the estimate covers or the EPS basis it uses.",
        },
        "limits": "Estimates can be wrong and change often. It says nothing about debt or cash, and it has no "
                  "meaning when expected earnings are zero or negative.",
    },
    "free_cash_flow": {
        "levels": {
            "new": "The cash the company's business brought in, minus what it spent on buildings and equipment. It "
                   "is the cash left over that could repay debt, go to shareholders or be kept.",
            "beginner": "Operating cash flow minus capital spending: the cash the business generated after paying "
                        "for the equipment and property it needs.",
            "intermediate": "Cash from operations less capital expenditure. It counts cash actually received and "
                            "spent, unlike net income, but it swings with timing, such as when customers pay and how "
                            "much inventory is built.",
            "advanced": "Operating cash flow less purchases of property, plant and equipment, as filed. Stock-based "
                        "pay is added back inside operating cash flow, and acquisitions are not deducted.",
            "expert": "CFO less capex (PaymentsToAcquirePropertyPlantAndEquipment), as filed. Pre-dividend; stock-"
                      "based compensation added back; acquisitions excluded. Yahoo Finance's own free-cash-flow "
                      "field is a different, provider-estimated measure and is not used.",
        },
        "limits": "A single period can be lifted or cut by timing. It does not deduct stock-based pay or "
                  "acquisitions, and it is not the cash a company pays out.",
    },
    "operating_cash_flow": {
        "levels": {
            "new": "The cash the company's day-to-day business brought in, after paying its suppliers, staff and "
                   "taxes.",
            "beginner": "Cash generated by the company's normal business, from its cash flow statement.",
            "intermediate": "Net cash provided by operating activities: net income adjusted for items that are not "
                            "cash, such as depreciation and stock-based pay, and for changes in working capital.",
            "advanced": "Net cash provided by operating activities, as reported on the cash flow statement. "
                        "Working-capital swings and the add-back of stock-based pay can make it differ widely "
                        "from net income.",
            "expert": "Net cash provided by (used in) operating activities, as filed (GAAP, indirect method).",
        },
        "limits": "It can swing with the timing of payments, and capital spending is not deducted from it; free "
                  "cash flow does that.",
    },
    "net_debt": {
        "levels": {
            "new": "What the company owes on loans and bonds, minus the cash and the investments it can turn into cash quickly. "
                   "Below zero, it holds more cash than it owes, which is called net cash.",
            "beginner": "Borrowings minus cash and short-term investments. Below zero, the company has more cash "
                        "than debt.",
            "intermediate": "Total borrowings (loans, bonds, commercial paper and finance leases) less cash, cash "
                            "equivalents and short-term investments, on the balance sheet date shown. Negative means "
                            "net cash.",
            "advanced": "Debt including current maturities, short-term borrowings, commercial paper and finance "
                        "lease liabilities, less cash and equivalents and current marketable securities. "
                        "Operating lease liabilities and long-term investments are left out.",
            "expert": "Borrowings (long-term debt incl. current maturities, short-term borrowings and commercial "
                      "paper) plus finance lease liabilities, less cash and equivalents and short-term "
                      "investments, at one balance-sheet date. Excludes operating leases, long-term investments "
                      "and pensions.",
        },
        "limits": "A snapshot on one date: debt and cash change every day. Operating leases and long-term "
                  "investments are left out, and for some companies either can be large.",
    },
    "net_debt_with_leases": {
        "levels": {
            "new": "The company's net debt plus what it owes on long leases of offices, stores and equipment. "
                   "Leases are a promise to pay, much like a loan.",
            "beginner": "Net debt plus operating lease liabilities, the rent the company has committed to pay on "
                        "long leases.",
            "intermediate": "Borrowings and all lease liabilities, less cash and short-term investments. Counting "
                            "operating leases treats a long lease like the loan it resembles.",
            "advanced": "Net debt plus operating lease liabilities as reported under ASC 842. Useful when comparing "
                        "companies that lease heavily with ones that own their assets.",
            "expert": "Net debt (above) plus OperatingLeaseLiability, current and noncurrent, as filed.",
        },
        "limits": "Lease liabilities are the present value of committed rent, which depends on the discount rate "
                  "the company chose. A snapshot on one date.",
    },
}

# What each kind of period means, said once and appended to every figure that covers one.
PERIODS: Dict[str, Dict[str, str]] = {
    "annual": {"name": "Fiscal year", "sentence": "Covers one complete fiscal year, the company's own reporting "
                                                  "year, which need not end in December."},
    "ttm": {"name": "Last 12 months", "sentence": "Covers the trailing twelve months: the last four reported "
                                                  "quarters added together."},
    "balance": {"name": "Balance sheet", "sentence": "Measured on one balance-sheet date, not over a period."},
    "forward": {"name": "Forward estimate", "sentence": "Uses the price at the time shown and the latest analysts' "
                                                        "average estimate."},
}

# The one way a trailing-twelve-month amount is built from filings (app/valuation/inputs.py trailing()).
TTM_RULE = ("Each twelve-month amount is the last fiscal year plus this fiscal year to date, less the same months "
            "a year earlier; that equals the last four reported quarters.")

_ENTRIES: List[Dict[str, Any]] = [
    {"id": "net_margin_fy", "concept": "net_margin", "name": "Net margin, fiscal year", "short": "Net margin",
     "unit": "percent", "period": "annual", "basis": "GAAP, as filed",
     "formula": "Net income divided by revenue, times 100, both for the same fiscal year.",
     "symbols": "net margin = net income / revenue x 100",
     "inputs": [{"key": "net_income", "name": "Net income attributable to the company"},
                {"key": "revenue", "name": "Total revenue"}],
     "related": ["net_margin_ttm"]},
    {"id": "net_margin_ttm", "concept": "net_margin", "name": "Net margin, last 12 months", "short": "Net margin",
     "unit": "percent", "period": "ttm", "basis": "GAAP, as filed",
     "formula": "Twelve-month net income divided by twelve-month revenue, times 100. " + TTM_RULE,
     "symbols": "net margin (TTM) = sum of 4 quarters' net income / sum of 4 quarters' revenue x 100",
     "inputs": [{"key": "net_income", "name": "Net income attributable to the company, 12 months"},
                {"key": "revenue", "name": "Total revenue, 12 months"}],
     "related": ["net_margin_fy"]},
    {"id": "forward_pe", "concept": "forward_pe", "name": "Forward P/E", "short": "Forward P/E",
     "unit": "multiple", "period": "forward", "basis": "Analysts' estimate",
     "formula": "The share price divided by analysts' average forecast of earnings per share for a coming fiscal "
                "year.",
     "symbols": "forward P/E = price / forward EPS",
     "inputs": [{"key": "price", "name": "Share price"},
                {"key": "forward_eps", "name": "Forward EPS, analysts' average estimate"}],
     "related": []},
    {"id": "free_cash_flow_fy", "concept": "free_cash_flow", "name": "Free cash flow, fiscal year",
     "short": "Free cash flow", "unit": "money", "period": "annual", "basis": "Non-GAAP, from GAAP lines as filed",
     "formula": "Operating cash flow minus capital expenditure, both for the same fiscal year.",
     "symbols": "FCF = operating cash flow - capital expenditure",
     "inputs": [{"key": "cfo", "name": "Operating cash flow"},
                {"key": "capex", "name": "Capital expenditure (purchases of property and equipment)"}],
     "related": ["free_cash_flow_ttm", "operating_cash_flow_fy"]},
    {"id": "free_cash_flow_ttm", "concept": "free_cash_flow", "name": "Free cash flow, last 12 months",
     "short": "Free cash flow", "unit": "money", "period": "ttm", "basis": "Non-GAAP, from GAAP lines as filed",
     "formula": "Twelve-month operating cash flow minus twelve-month capital expenditure. " + TTM_RULE,
     "symbols": "FCF (TTM) = operating cash flow (TTM) - capital expenditure (TTM)",
     "inputs": [{"key": "cfo", "name": "Operating cash flow, 12 months"},
                {"key": "capex", "name": "Capital expenditure, 12 months"}],
     "related": ["free_cash_flow_fy", "operating_cash_flow_ttm"]},
    {"id": "operating_cash_flow_fy", "concept": "operating_cash_flow", "name": "Operating cash flow, fiscal year",
     "short": "Operating cash flow", "unit": "money", "period": "annual", "basis": "GAAP, as filed",
     "formula": "Net cash provided by operating activities for the fiscal year, from the cash flow statement.",
     "symbols": "operating cash flow = net cash provided by operating activities",
     "inputs": [{"key": "cfo", "name": "Net cash provided by operating activities"}],
     "related": ["operating_cash_flow_ttm", "free_cash_flow_fy"]},
    {"id": "operating_cash_flow_ttm", "concept": "operating_cash_flow", "name": "Operating cash flow, last 12 months",
     "short": "Operating cash flow", "unit": "money", "period": "ttm", "basis": "GAAP, as filed",
     "formula": "Net cash provided by operating activities over the last twelve months. " + TTM_RULE,
     "symbols": "operating cash flow (TTM) = sum of 4 quarters' net cash provided by operating activities",
     "inputs": [{"key": "cfo", "name": "Net cash provided by operating activities, 12 months"}],
     "related": ["operating_cash_flow_fy", "free_cash_flow_ttm"]},
    {"id": "net_debt", "concept": "net_debt", "name": "Net debt", "short": "Net debt", "unit": "money",
     "period": "balance", "basis": "Non-GAAP, from GAAP balances as filed",
     "formula": "Borrowings plus finance lease liabilities, minus cash and cash equivalents and short-term "
                "investments, all on the same balance-sheet date. Negative means net cash.",
     "symbols": "net debt = debt + finance leases - cash - short-term investments",
     "inputs": [{"key": "debt", "name": "Borrowings (long-term debt incl. current maturities, short-term "
                                       "borrowings, commercial paper)"},
                {"key": "finance_leases", "name": "Finance lease liabilities"},
                {"key": "cash", "name": "Cash and cash equivalents"},
                {"key": "short_term_investments", "name": "Short-term investments"}],
     "related": ["net_debt_with_leases"]},
    {"id": "net_debt_with_leases", "concept": "net_debt_with_leases", "name": "Net debt including operating leases",
     "short": "Net debt incl. leases", "unit": "money", "period": "balance", "basis": "Non-GAAP, from GAAP balances as filed",
     "formula": "Net debt plus operating lease liabilities, on the same balance-sheet date.",
     "symbols": "net debt incl. leases = net debt + operating lease liabilities",
     "inputs": [{"key": "net_debt", "name": "Net debt"},
                {"key": "operating_lease", "name": "Operating lease liabilities"}],
     "related": ["net_debt"]},
]

REGISTRY: Dict[str, Dict[str, Any]] = {e["id"]: e for e in _ENTRIES}
IDS = tuple(REGISTRY)
# The required fields of an entry, which the registry test holds every entry to.
REQUIRED = ("id", "concept", "name", "short", "unit", "period", "basis", "formula", "symbols", "inputs", "related")
UNITS = ("percent", "money", "multiple")


def definition(fid: str, level: str = DEFAULT_LEVEL) -> str:
    """The plain-English definition of one figure at one knowledge level, with its period sentence.

    An unknown level reads as the default rather than failing: a level the reader's browser stored before the five
    levels existed still gets a definition."""
    e = REGISTRY[fid]
    c = _CONCEPTS[e["concept"]]
    lv = level if level in LEVELS else DEFAULT_LEVEL
    return "{} {}".format(c["levels"][lv], PERIODS[e["period"]]["sentence"])


def public() -> Dict[str, Any]:
    """The registry as the client reads it, fetched once per session (GET /api/figures/registry)."""
    out = {}
    for fid, e in REGISTRY.items():
        c = _CONCEPTS[e["concept"]]
        out[fid] = dict(e, definitions={lv: definition(fid, lv) for lv in LEVELS}, limits=c["limits"],
                        period_name=PERIODS[e["period"]]["name"])
    return {"version": VERSION, "levels": list(LEVELS), "default_level": DEFAULT_LEVEL, "figures": out}


# Bumped whenever an entry's meaning changes, so a cached copy in a reader's session is replaced.
VERSION = "2026-11-04.1"
