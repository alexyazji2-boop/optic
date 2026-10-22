# Commercial dependencies before a paid, scaled Optic

Written 2026-10-22 for the Monday 2026-10-26 pitch (audit item 23). This is a list of open business questions, not a legal opinion. Nothing here was purchased, signed or accepted.

## Market data

| Source | What Optic uses it for | Status | What has to happen before charging for it |
|---|---|---|---|
| Yahoo Finance, through the open-source `yfinance` library | Quotes (delayed), daily and intraday bars, option chains, fundamentals, earnings dates, analyst figures, headlines | The production provider (`/api/health` reports it). The library's README says Yahoo's data is for personal use and points to Yahoo's terms. The library's licence covers the code, not the data. | A licensed market-data provider with redistribution rights for quotes, chains and fundamentals, or written terms from Yahoo. Until then, describe Optic as a research prototype on free, delayed data. |
| Tradier (provider exists in `app/providers/tradier.py`) | Option chains, when a token is configured | Not the production provider. A sandbox token is 15 minutes late and the health check says so. | A brokerage or data agreement that covers display to Optic's users. |
| SEC EDGAR (`sec.gov`, `data.sec.gov`) | Filings, XBRL facts, insider forms | Public data under the SEC's fair-access policy (declared User-Agent, request pacing; pacing is in the code). | Keep the pacing; no licence needed for public filings. |
| FRED, BLS, Federal Reserve | Macro series, release calendars | Public. FRED's terms ask for attribution and restrict some third-party series. | Check each FRED series' own copyright notice before redistributing it in a paid product. |
| NASDAQ Trader symbol directory | The search universe | Public file. | Attribution. |
| House Clerk disclosures, USAspending | Congress trades, federal awards | Public records. | None beyond attribution. |
| News feeds (Yahoo, CNBC, Dow Jones feed, Reuters, WSJ, others) | Headlines and links only | Headlines link out to the publisher; no article text is republished. | Publisher terms for headline display at scale, or a licensed news API. |
| DoltHub, Cboe | Research inputs | Behind flags that are off in production. | Their own terms before any production use. |

## Accounts, payments and the assistant

- **SnapTrade** (read-only brokerage linking): live for the owner only (`BROKERAGE_OWNER_ONLY`). A production SnapTrade agreement, and the brokerage consent page's `TERMS_URL`, `PRIVACY_URL` and `BROKERAGE_TERMS_VERSION`, are needed before opening it to users.
- **Stripe** (Pro plan): billing is off; Settings says plans are not on sale. No paid flow has been verified end to end. Present revenue as planned.
- **Anthropic** (Milo): pay-per-use on the owner's account. Each answer costs money; the free allowance is five questions a day. A paid plan needs a cost-per-user model before pricing.
- **Email**: SMTP is not configured; verification links go to the server log. Account email flows are not production-ready.

## Claims to avoid on Monday

- Real-time data. Quotes are delayed about 15 minutes; option chains come from a free feed.
- Proven strategy performance. The validation program found no supported edge, the research rounds of 2026-10-21/22 rejected the one lead, and the simulated books are small samples with losses. Scores are rules-based summaries, not probabilities.
- Options flow as a trade tape, institutional buying, sweeps or opening positions. The feed has volume and the previous session's open interest, nothing about who traded or why.
- Retirement projections as expected outcomes. They are arithmetic on a hypothetical past record, with a sensitivity band.
- Paid-plan readiness or tested subscription revenue.

Suggested line: "Optic brings company fundamentals, market context, options-positioning estimates and a source-aware research assistant into one workspace. It helps users understand the evidence and its limitations."
