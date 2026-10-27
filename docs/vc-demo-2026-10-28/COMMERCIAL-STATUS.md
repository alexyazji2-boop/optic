# Commercial status, as of Monday 26 October 2026, 10:30 PM ET

A factual inventory for the Wednesday 28 October VC demonstration. **Verified** means
checked today against production (theopticterminal.com, commit `ca490f867c47`) or the
code it runs. **Pending** means work exists or is understood but is not done.
**Unknown** means no evidence either way. Nothing here was purchased, signed, accepted
or sent to a vendor. It is not a legal opinion. It updates
`docs/pitch-2026-10-26/COMMERCIAL-DEPENDENCIES.md`, which is still the longer list.

## Paid plans

| Item | Status | Evidence |
|---|---|---|
| Checkout is off | **Verified** | `GET /api/billing/status` answered `{"available": false, "reason": "Plans are not on sale yet. Every account is on Free."}` |
| Every account is on Free (3 Milo messages a day) | **Verified** | Same response; `PLANS["free"]["ai_calls_per_day"] == 3` in `app/auth/store.py` |
| A paid subscription works end to end (Stripe checkout, webhook, plan change, cancel) | **Unknown** | Never run in production. Code and tests exist; no live Stripe transaction has been made or should be for the demo. |
| Revenue | **None** | Present paid plans as planned, not tested. |

## Data sources by feature

| Feature | Source in production | Commercial display or redistribution rights |
|---|---|---|
| Quotes, daily and intraday bars, fundamentals, estimates, earnings dates, analyst figures, per-company headlines, option chains | Yahoo Finance through `yfinance` (**verified**: `/api/health` says `"provider": "yfinance"`, `"realtime_chain": false`) | **Unknown, and not established.** The `yfinance` README describes Yahoo's data as for personal use. No agreement with Yahoo exists. |
| Overnight (8 PM to 4 AM) prices for single stocks | Robinhood's undocumented market-data endpoint (`app/providers/overnight.py`), always on in production | **Unknown.** Nothing grants a right to display it. The unshipped `p0-readiness` branch (F-02) adds `OPTIC_OVERNIGHT_FEED`, default off; not taken into this branch because switching it off changes a live feed. **Owner decision.** |
| Filings, XBRL segment and statement facts, insider forms | SEC EDGAR | Public data under SEC fair-access rules (declared User-Agent, pacing in code). **Verified** as used. |
| Macro series and release calendars | FRED, BLS, Federal Reserve | Public. FRED series carry their own copyright notices; **pending** a per-series check before a paid product. |
| Off-exchange short volume | FINRA daily files (`app/analytics/extras.py`) | Public files. **Pending** a terms check for redistribution at scale. |
| Congress trades, federal awards | House Clerk disclosures, USAspending | Public records. |
| Market headlines on the Read | Public wire and publisher feeds, headlines and links only | **Pending**: publisher terms for headline display at scale. |
| Company logos in the classic app | Google, unavatar.io, favicone.com, Parqet, Financial Modeling Prep | **Unknown** terms. Named in the privacy policy on this branch. |
| Licensed replacement | None signed | **Pending.** A vendor comparison exists in the owner's private working notes (24 October 2026). One vendor's terms count sending data to an LLM API as redistribution, so Milo has to be named in any order form. No vendor contacted. |
| Real-time chains | Tradier provider exists | Not configured in production (**verified**, `realtime_chain: false`). Tradier's terms forbid display to non-account holders. |
| DoltHub, Cboe history | Behind flags | Off by default in code (`OPTIC_DOLTHUB`, `OPTIC_CBOE_HISTORY` default `false`). |

## Accounts, assistant, brokerage and hosting

| Item | Status | Evidence |
|---|---|---|
| Email (verification, reset) | **Verified off** | `/api/auth/providers`: `"mail": {"available": false, "backend": "log"}`, no `SMTP_HOST`. Needs a relay before inviting readers (see DEMO-READINESS.md, external setup). |
| Sign-in methods | **Verified** | Email and password, and passkeys (`rp_id` theopticterminal.com). Google and Apple are not offered. |
| Milo (Anthropic) | **Verified on** | `/api/health`: `claude-sonnet-5-5`, key from `ANTHROPIC_API_KEY`. Pay per use on the owner's account. A per-user cost model does not exist yet. |
| Brokerage linking (SnapTrade, read-only) | Owner only (`BROKERAGE_OWNER_ONLY`) | A production SnapTrade agreement and the consent page's terms and privacy links are **pending** before opening it to users. |
| Cloudflare Web Analytics | **Verified present** | Cloudflare adds `static.cloudflareinsights.com/beacon.min.js` to HTML served to browsers. The privacy policy on this branch names it. Keep or switch off: **owner decision**. |
| Account backups off the Railway volume | **Pending** | Same-volume daily copies on this branch; an off-host copy and a restore drill need the owner (DEPLOY.md). |
| Terms and Privacy pages | Live; **pending** legal review | `EFFECTIVE` is still October 19, 2026 on this branch, for the owner to set when it ships. |

## Claims to avoid on Wednesday

- Real-time data, or licensed data. Quotes are free and delayed; v2 can show "Live" for a symbol Yahoo reports with no delay (SPY), which is Yahoo's statement, not a licence.
- That any score predicts returns. Optic's own tests found none supported (validation program, 0 of 82; macro score back-test, all unsupported).
- Paid conversion, retention, or a tested subscription flow.
- That accounts are backed up off-host, or that email recovery works.
