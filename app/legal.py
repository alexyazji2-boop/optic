"""Canonical legal notices.

Kept in one module so the same wording reaches the UI, the API and any future
consumer, rather than drifting into six slightly different paraphrases. Served at
``/api/legal`` so a caller hitting the JSON directly — which is where the strike
recommendations and the paper-trading ledger actually live — gets the notice too,
not just someone looking at the page.

I am not a lawyer and this is not a substitute for one. These are the standard
disclosures for a tool that outputs specific price levels and a simulated track
record; if this goes beyond a prototype shared with people you know, have counsel
review it and check what registration rules apply where you operate.
"""

from __future__ import annotations

from typing import Any, Dict

# The one-line version, for footers and dense panels.
SHORT = (
    "Not financial advice. For research and education only. You are responsible "
    "for your own decisions."
)

# The full notice.
FULL = (
    "Optic Terminal is an independent research tool. It is not financial, investment, "
    "tax or legal advice, and nothing in it is a recommendation, solicitation or offer "
    "to buy or sell any security, option or other instrument. It is provided for "
    "informational and educational purposes only.\n\n"
    "The operator is not a broker-dealer, not a registered investment adviser, and not "
    "licensed to give investment advice. No output here is personalised advice. If you link a "
    "brokerage account, Optic shows and describes those holdings read-only, but it does not "
    "know or assess your wider finances, tax position, time horizon, obligations or risk "
    "tolerance, and cannot take them into account.\n\n"
    "Every figure is generated from third-party data that may be delayed, incomplete or "
    "wrong, and from models whose assumptions are stated but not guaranteed. Verify "
    "anything you intend to act on against primary sources.\n\n"
    "Trading involves substantial risk of loss and is not suitable for everyone. "
    "Options carry additional risks and can expire worthless, losing the entire premium; "
    "short positions can lose more than the amount invested. Past performance does not "
    "predict future results. You may lose some or all of your capital.\n\n"
    "Consult a licensed financial professional before making any investment decision. "
    "The operator accepts no liability for any loss arising from use of this tool."
)

# Simulated results carry their own well-established disclosure problem: a
# hypothetical record is built with hindsight over the very period it reports on,
# and has none of the costs, slippage or hesitation of real money.
SIMULATED = (
    "Hypothetical performance. These positions were never placed with real money. "
    "Simulated results have inherent limitations: they are prepared with the benefit "
    "of hindsight, assume fills at the mid price, and bear no commission, slippage, "
    "financing cost, borrow cost or tax. No account will necessarily achieve results "
    "resembling these, and simulated performance is not indicative of future results."
)

# Optic Portfolio's own version. Under the 2026-10-21 rules its new trades carry
# a modelled allowance for commission and slippage (app/paper.py), so the generic
# sentence above would be false there. The earlier trades carry none, and it says
# so. The rules took effect when a build with them first opened the ledger, not on
# the day they were approved, so the page dates the change ("Rules changed on")
# and this text points to that line rather than naming a date.
TRACKER_SIMULATED = (
    "Hypothetical performance. These positions were never placed with real money. "
    "Simulated results have inherent limitations: they are prepared with the benefit "
    "of hindsight and assume fills at the mid price. Since the rules change dated on "
    "this page, new trades carry a modelled allowance for commission and slippage; "
    "earlier trades carry none, and none carries financing cost, borrow cost or tax. "
    "No account will necessarily achieve results resembling these, and simulated "
    "performance is not indicative of future results."
)

# Per-area notices, each naming the specific way that area's output could be
# mistaken for advice.
AREAS: Dict[str, str] = {
    "swing": (
        "The contracts, levels and scenarios on this tab are model output from the option "
        "chain and price history, not advice to place any trade. Options can expire "
        "worthless and lose the entire premium."
    ),
    # The page's words since 2026-10-29: the two copies had drifted apart.
    "longterm": (
        "A conviction score summarises historical data. It says nothing about whether this "
        "holding suits your horizon, taxes or existing exposure."
    ),
    "retirement": (
        "A rules-based illustration for comparison against your own plan, not "
        "retirement, investment or tax advice. It is not tailored to your income, tax "
        "situation, other accounts or goals, and contribution limits and eligibility "
        "change. Confirm current rules with the IRS and a licensed professional."
    ),
    "earnings": (
        "Event pricing and estimate history describe what the market is charging, not "
        "what you should do about it. Holding an option through an earnings report can "
        "lose money even when the direction is right."
    ),
    "tracker": TRACKER_SIMULATED,
    "brief": (
        "A summary of published news and filings, not analysis of it and not a "
        "recommendation about any security mentioned. Headlines belong to their "
        "publishers and link to the original; filings link to EDGAR. Nothing here "
        "has been verified independently, and a company's own filing is its "
        "account of events."
    ),
    "macro": (
        "A regime read on the market as a whole. It is not a view on any individual "
        "security and not a recommendation to change your positioning."
    ),
}


# ------------------------------------------------------------ the registry
#
# The exact wording each page of the v2 front end shows, keyed by the v2 area
# id (post-demo overhaul, 2026-10-29). This is the single source:
# static/v2/js/core/legal.js carries a copy so notices draw on the first paint
# without a request, and tests/test_legal_registry.py fails when the two differ.
# Before this, the client's copy had drifted from AREAS (a Milo notice, a Paper
# Desk notice and an Indices notice the server did not have, and a long-term
# notice in different words), and seven areas had no notice at all.
#
# Markup is the operator's own (<strong> only), never anything from a reader or
# a feed. Short on purpose: one line beside the content it qualifies, with the
# full disclaimer and the Terms one press away, rather than legal text repeated
# on every screen.
# 2026-11-02: the Optic Portfolio notice says which trades carry costs (the
# 2026-10-21 book rules).
REGISTRY_VERSION = "disclosures-2026-11-02"

PAGE_AREAS: Dict[str, str] = {
    "pulse": "<strong>Not financial advice.</strong> Milo states which way the <em>data</em> leans and how strongly. That is a reading of numbers on this screen, not a recommendation for you: it does not know your horizon, capital or tax position, and even with a linked brokerage it describes your holdings rather than judging whether any of this suits you. It can be confidently wrong. The inputs are delayed, several are labelled proxies, and a lean is not a forecast.",
    "overview": "<strong>Research, not a recommendation.</strong> The grades, scores and levels on this page are rules applied to past data. They have not been shown to predict returns, and they say nothing about whether a holding suits you.",
    "chart": "<strong>Research, not a recommendation.</strong> Indicators and levels describe past prices, not signals to buy or sell. The drawing tools do arithmetic on the points you place.",
    "swing": "<strong>Not a recommendation.</strong> The contracts, levels and scenarios on this tab are model output from the option chain and price history, not advice to place any trade. Options can expire worthless and lose the entire premium.",
    "long": "<strong>Not a recommendation.</strong> A conviction score summarises historical data. It says nothing about whether this holding suits your horizon, taxes or existing exposure.",
    "roth": "<strong>Not retirement or tax advice.</strong> A rules-based illustration to compare against your own plan. It is not tailored to your income, tax situation, other accounts or goals, and contribution limits and eligibility change. Confirm current rules with the IRS and a licensed professional.",
    "earnings": "<strong>Not a recommendation.</strong> Event pricing describes what the market is charging, not what you should do about it. Holding an option through a report can lose money even when the direction is right.",
    "tracker": "<strong>Hypothetical performance.</strong> These positions were never placed with real money. Simulated results are prepared with the benefit of hindsight and assume fills at the mid price. Since the rules change dated on this page, new trades carry a modelled allowance for commission and slippage; earlier trades carry none, and none carries financing, borrow cost or tax. No real account would necessarily achieve results resembling these, and simulated performance does not indicate future results.",
    "paper": "<strong>Hypothetical performance.</strong> Positions you enter here were never placed with real money. Marks assume you could trade at the last price or the chain mid, and bear no commission, slippage, financing, borrow cost, assignment risk or tax. A short position here cannot fail to borrow and an option here is never exercised early. No real account would necessarily achieve results resembling these.",
    "market": "<strong>Not a recommendation.</strong> A regime read on the market as a whole, not a view on any individual security, and not advice to change your positioning.",
    "indices": "<strong>Not a recommendation.</strong> Long-run index context, not advice to buy, sell or hold any index fund.",
    "brief": "<strong>Not a recommendation.</strong> A summary of published news, not analysis of it, and not a view on any security mentioned. Headlines belong to their publishers and link to the original, and nothing here has been verified independently. Scheduled releases are calendar dates, not forecasts.",
    "screen": "<strong>Research, not a recommendation.</strong> A screen lists the names that meet the rules shown. Being on a list is not a recommendation, and the screens have not been shown to predict returns.",
    "insiders": "<strong>Not a recommendation.</strong> Filed trades are public records of what insiders and members of Congress reported, often days or weeks after the trade. They are not signals to follow.",
    "analysts": "<strong>Not a recommendation from Optic.</strong> Ratings and price targets are the analysts' own, as reported by the data source. Optic does not endorse or check them.",
    "brokerage": "<strong>Not financial advice.</strong> Optic describes your linked holdings, read-only. It does not know your wider finances, taxes or goals, and nothing here suggests buying, selling or rebalancing.",
}

# The footer line every v2 page carries, the same in the Classic footer.
FOOTER_LINE = ("<strong>Not financial advice.</strong> Optic Terminal is an independent research tool, not a "
               "broker-dealer or investment adviser. Data may be delayed or wrong, and trading involves "
               "substantial risk of loss.")

# How AI-written text and data limits are named wherever they appear, so every
# surface says them the same way (COMPLIANCE_REVIEW.md, "Context-sensitive disclosure").
LABELS: Dict[str, str] = {
    "ai_written": "Written by an AI model from the data shown",
    "ai_short": "AI-written",
    "delayed": "Quotes delayed about 15 minutes during the session",
    "modelled": "Model output, from stated assumptions",
    "third_party": "From a third-party source, not checked by Optic",
    "simulated": "Hypothetical, never placed with real money",
}


def notice() -> Dict[str, Any]:
    """Everything a client needs to display the disclosures."""
    return {
        "short": SHORT,
        "full": FULL,
        "simulated": SIMULATED,
        "areas": AREAS,
        "page_areas": PAGE_AREAS,
        "footer": FOOTER_LINE,
        "labels": LABELS,
        "version": REGISTRY_VERSION,
        "not_advice": True,
        "registered_adviser": False,
        "broker_dealer": False,
    }
