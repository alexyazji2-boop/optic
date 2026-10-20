# Terms of use and Privacy policy (in force from 2026-10-19)

`#/terms` and `#/privacy` in v2 (`static/v2/js/pages/legalpages.js`), linked from every page's footer. Written for the owner's front-end checklist ("T&C's page", "privacy policy page").

**Status: in force from October 19, 2026** (the owner: "draft the legal pages and publish"). `IN_FORCE = true`, `EFFECTIVE`, `OPERATOR` and `CONTACT` are constants at the top of `legalpages.js`. Both sign-up forms (v2 `pages/signin.js`, Classic `static/auth.js`) say that creating an account, with email or with Google or Apple, is agreeing to both; Classic's footer links them at `/v2/#/terms` and `/v2/#/privacy`. **Not reviewed by a lawyer**, and LAUNCH-REQUIREMENTS.md L1 stays open for that review.

## How each field was filled
| Field | Value | From |
|---|---|---|
| Operator | Optic Terminal | the owner chose "a company" without naming one; the product name stands until a registered name is given |
| Contact | theopticterminal@gmail.com | the owner |
| Governing law | Massachusetts, United States; courts located in Massachusetts | the owner |
| Minimum age | 13, with a parent's agreement under 18; brokerage linking and paid plans adults only | the owner (13), the adult-only parts from SnapTrade's and Stripe's own requirements |
| Refunds | none for part of a period; an erroneous charge refunded; legal refunds unaffected | standard terms, proposed and stated to the owner |
| Liability cap | the greater of 12 months' payments and US$100, as far as the law allows | standard terms, proposed and stated to the owner |
| Email provider | not switched on: nothing is emailed, the address and link go to the server log | Railway has no SMTP_* variables (`app/auth/mailer.py:83-93`) |
| Hosting region | Railway, Amsterdam, Netherlands | the service's replica region in Railway (ams) |
| Log retention | up to 90 days | Railway's docs (7 days Hobby, 30 Pro) and support (90 days for all plans) disagree; the upper figure is stated |
| Third-party terms | anthropic.com/legal/commercial-terms and /privacy; snaptrade.com/terms-and-conditions | the public pages |
| Problem reports on deletion | kept without the email or the account | `app/auth/store.delete_user`, tested in `tests/test_auth_accounts.py` |
| Rights | by email, answered within 30 days; EU, UK and Californian rights named | there is still no self-serve download |

## Still to do
- **Brokerage consent:** it shows these pages only once `TERMS_URL`, `PRIVACY_URL` and a new `BROKERAGE_TERMS_VERSION` are set in Railway (`app/brokerage/service.py:85-104`), which asks every reader to agree again.
- **Email:** an SMTP service (SMTP_HOST and the rest), then name it in the Email section.
- **Counsel's review.**
- **If v2 is shut off** (`OPTIC_V2_ACCESS=off`): `/v2/` serves Classic, which has no `#/terms` route, so the pages would need a home outside v2.

## What each statement rests on
| Statement | Evidence |
|---|---|
| Registration takes email, first name, optional last name and password | `app/auth/routes.py:167-209`, `app/auth/store.py:58-79` |
| Passwords hashed with Argon2id | `app/auth/passwords.py:31-40` |
| Session, reset and verification tokens kept as SHA-256 hashes | `app/auth/tokens.py:1-31` |
| What Google and Apple sign-in keep | `app/auth/oauth.py:101, 122, 281-310`; `app/auth/linking.py:133-140` |
| What a passkey keeps | `app/auth/store.py:355-372` |
| Sessions keep IP address and user agent; listed and revocable in Settings | `app/auth/store.py:196-214`, `app/auth/routes.py:503-540` |
| Two cookies, `optic_session` and `optic_csrf`, with their lifetimes | `app/auth/config.py:23-47, 73-87`, `app/auth/deps.py:115-123` |
| No analytics or tracking scripts; fonts from jsDelivr | `static/v2/index.html:17-19` (no third-party scripts) |
| Saved to the account: watchlists, research, watches, theses, valuations, models, signals, portfolio alerts | `app/db.py:310-905` |
| Milo chats and paper trades stay in the browser | `static/v2/js/ui/milo.js:28`; `app/papertrade.py:1-15` |
| What Anthropic receives, and when holdings are included | `app/main.py:7239-7330`; `app/ai.py:3119` (web search only when on) |
| Usage ledger without identity, 92 days | `app/ai_store.py:72-85, 120` |
| Milo allowance kept under a hashed id | `app/main.py:6926-6944` |
| SnapTrade: read-only, random user id, encrypted per user | `app/brokerage/snaptrade.py:179-192`, `app/vault.py:1-31` |
| Snapshots: newest 30 plus one a day for 400 days | `app/brokerage/store.py:270-271` |
| Plan lapse: SnapTrade copy removed after 7 days, Optic's after 30 | `app/brokerage/service.py:15-51` |
| Stripe receives the account id and, once, the email; Optic keeps plan, status, ids, renewal | `app/billing.py:140-157` |
| Cancel through the Stripe billing portal | `app/billing.py:1-3, 172` |
| Expired sessions and links deleted hourly; rate-limit rows after a day (Milo monthly after 31) | `app/db.py:960-993` |
| Delete account removes everything, cancels Stripe and removes brokerage data | `app/auth/routes.py:719-753` |
| Problem reports survive deletion | `app/db.py:520-567` (no foreign key) |

## Found while drafting
- **Fixed:** the brokerage consent record's `ip_hash` column held the plain address. It is a hash now: `app/auth/ratelimit.hashed_ip`, test in `tests/test_brokerage.py`. Earlier rows keep the plain value.
- **For the owner:**
  - Problem reports keep the reporter's email after the account is deleted.
  - There is no download of a reader's data.
  - Session IP addresses are stored in plain text, which is common, and the draft says so.
  - `accounts.db` has no backup (DEPLOY.md), which is operational rather than a policy matter.
