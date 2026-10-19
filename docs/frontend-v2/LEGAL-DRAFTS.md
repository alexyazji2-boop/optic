# Terms of use and Privacy: drafts (2026-10-19)

`#/terms` and `#/privacy` in v2 (`static/v2/js/pages/legalpages.js`), linked from every page's footer. Written for the owner's front-end checklist ("T&C's page", "privacy policy page").

**Status: drafts, not in force.** `IN_FORCE = false` puts a banner at the top of both pages. Nothing asks a reader to agree to them. They are written from what the code does today, not from a template, and they are not legal advice: they need the owner's details, the owner's approval and a lawyer's review (LAUNCH-REQUIREMENTS.md L1).

## To put them in force
1. Fill every highlighted field. Terms has 6, Privacy has 9:
   - the operator's legal name;
   - the contact address;
   - governing law;
   - refunds;
   - the liability limit;
   - the email provider;
   - the hosting region;
   - log retention;
   - the minimum age;
   - links to Anthropic's and SnapTrade's terms;
   - whether problem reports go on deletion.
2. Have counsel review both texts, including readers' rights under the laws that apply to them.
3. Set `IN_FORCE = true` and change the draft date to the date the terms take effect.
4. Set `TERMS_URL` and `PRIVACY_URL` (for example `https://theopticterminal.com/v2/#/terms`) and `SNAPTRADE_TERMS_URL`, and give the brokerage consent a new version (`app/brokerage/service.py:82-104`).
5. Decide whether sign-up asks for agreement; it does not today.

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
