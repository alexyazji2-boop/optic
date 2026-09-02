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
    "Not financial advice. For research and education only — you are responsible "
    "for your own decisions."
)

# The full notice.
FULL = (
    "Optic Terminal is an independent research tool. It is not financial, investment, "
    "tax or legal advice, and nothing in it is a recommendation, solicitation or offer "
    "to buy or sell any security, option or other instrument. It is provided for "
    "informational and educational purposes only.\n\n"
    "The operator is not a broker-dealer, not a registered investment adviser, and not "
    "licensed to give investment advice. No output here is personalised: the tool knows "
    "nothing about your finances, tax position, time horizon, obligations or risk "
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

# Per-area notices, each naming the specific way that area's output could be
# mistaken for advice.
AREAS: Dict[str, str] = {
    "swing": (
        "The strikes, limit prices, stops and targets below are model output, not a "
        "recommendation to place any trade. Options can expire worthless and lose the "
        "entire premium."
    ),
    "longterm": (
        "A conviction score is a summary of historical data, not a view on whether this "
        "holding suits you. It says nothing about your horizon, taxes or existing "
        "exposure."
    ),
    "retirement": (
        "A rules-based illustration for comparison against your own plan — not "
        "retirement, investment or tax advice. It is not tailored to your income, tax "
        "situation, other accounts or goals, and contribution limits and eligibility "
        "change. Confirm current rules with the IRS and a licensed professional."
    ),
    "earnings": (
        "Event pricing and estimate history describe what the market is charging, not "
        "what you should do about it. Holding an option through an earnings report can "
        "lose money even when the direction is right."
    ),
    "tracker": SIMULATED,
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


def notice() -> Dict[str, Any]:
    """Everything a client needs to display the disclosures."""
    return {
        "short": SHORT,
        "full": FULL,
        "simulated": SIMULATED,
        "areas": AREAS,
        "not_advice": True,
        "registered_adviser": False,
        "broker_dealer": False,
    }
