# VC demo readiness: what changed, for review

Branch `vc-demo-readiness`, cut from production `ca490f8` on 26 October 2026. Not pushed,
not deployed. Every item below was reproduced first, against the live site, the code or the
recorded data named in its commit. Tests use recorded fixtures and faked services; no paid
model call was made.

## Information that could undermine trust

| Item | What was wrong | What changed |
|---|---|---|
| A. Brokerage headlines | The briefing listed raw Yahoo feeds: NVDA got BlackBerry, Costco and Nike stories, NOW got gas prices. | Each story passes the News page's relevance test (`news.relevance`); market-wide stories are listed once, apart from any holding; a holding with none says so. Symbols that are words (NOW, ALL, ON, IT) count only when written as a ticker. Fixture recorded from the live feeds. |
| B. Segment totals | NVIDIA tags its segment subtotal (139.3B) with `CorporateNonSegmentMember`; Optic showed it as a corporate row, parts summing to 278.6B against 130.4B, with percentages. | That line is left out and the table says why. Shares of a total are shown only when the parts reconcile; a line counts as an aggregate only when it equals the sum of two or more others. Fixtures are excerpts of NVIDIA's 10-K and 10-Q instance documents. |
| C. Market dates | The server's UTC `date.today()` turned over at 8 PM New York time: Brokerage called Tuesday "today", NVDA's report was 21 days away on Earnings and 22 on Overview. | `session.market_today()` is the one market date, used by every countdown on the server; the Overview's client fallback counts from New York too. Tests freeze the clock after UTC midnight, on a weekend and across both DST changes. |

## Cross-page data and Milo

| Item | What changed |
|---|---|
| D. Home quote | When Yahoo's quote document fails, the day's change comes from the bar before (regular-session closes only; none for futures, currencies, coins) and the panel says the quote is partial instead of `n/a (n/a)`. |
| E. Compare context | Milo receives every compared name's displayed figures with units, lookbacks, missing-value reasons, score definitions, the computed time and the limits line. The server no longer looks one name up separately. Measured 9,400 characters for two names. |
| F. News timestamp | "The list was fetched at fetched_at." is gone; the page says "Optic fetched this list at 11:24 PM ET", or nothing when the time is missing. |
| G. Read freshness | The writer is told which session its figures cover and the words to use ("today", "yesterday", "on Friday"); the two breadths are named for what they measure; each edition records its covered session and figure time; bolded percentages are checked against the edition's data and any mismatch is shown. **Includes `0a77d41`** (from the unshipped `input-defects` branch): the regime's breadth input becomes the real share of sectors above their 200-day, which that branch measured changing the regime stance on 261 of 500 replayed sessions. |
| H. Performance windows | Attribution runs over the return's own measured dates and reports the pairs it used; when the dates still differ, the page says it is a separate measurement. |

## Operational readiness

| Item | What changed | Still external |
|---|---|---|
| I. Recovery email | From `p0-readiness` F-42: on a host, only `ADMIN_EMAILS` links are logged. Tests drive the SMTP path against a fake relay. | A relay and its DNS (DEPLOY.md, `SMTP_*`, `EMAIL_FROM`). |
| J. Paid generation | `GET /api/earnings/{T}/brief` only reads; `POST` writes behind `_spend_guard`, CSRF, one write per report at a time, and the daily ceilings from `p0-readiness` F-23 (30 / 30 / 24). Sector and catalyst reads write once per key at a time. Both pages write only on a press. | An Anthropic console spend limit. |
| K. Backups | From F-40: daily scrubbed `accounts.db` copies. New: `python -m app.snapshots verify`, an isolated restore check, tested on a real restore. | An off-host copy and a restore drill (DEPLOY.md). |
| L. Privacy | The policy names Cloudflare's Web Analytics script, which Cloudflare adds at its edge; the email, recovery-copy and usage-record paragraphs match the code (F-43's 400-day sweep included). | Keep or switch off the script; legal review; the `EFFECTIVE` date. |
| M. Commercial status | `COMMERCIAL-STATUS.md`: each item verified, pending or unknown. | Licensing. |

Not taken from `p0-readiness`: F-02 (`OPTIC_OVERNIGHT_FEED`, default off), because it switches
off a live data feed. That is the owner's call.

## Design and accessibility

- Light `--c-pos` `#0d7a42` to `#0c743f`: 4.20:1 on `--c-sunk` failed AA text; now 4.54:1.
  Indicator colours unchanged.
- A drawer gives focus back to the redrawn control when the page repainted under it.
- Phone Chart tab: the actions share the ticker's line; the chart starts at y=360 of 844, from 398.
- Seven section chips have their own short labels instead of being cut mid-phrase.
- Classic's Milo box and file input have accessible names.
- Sandbox brokerage data says on every section that it is test data.
- Text fields and selects are 16px on touch screens, so iOS Safari does not zoom into them on focus
  (Home's ticker box was 13px, the Chart selects 14px).

Proposed, not applied: control edges (input borders) at `--c-line` measure about 1.5:1 against
their panels, under the 3:1 non-text minimum. The nearest passing values are `#847f76` (light)
and `#6a6966` (dark); every input in the app would change, so it waits for the owner.

## An independent review of the branch

A second reader went through the server changes and found eight problems, all fixed in
`57e48dc`: a reader was charged a Milo message when the daily ceiling or a write already in
flight then refused them; an accounts snapshot briefly existed unscrubbed under its final name;
the ticker-list rule matched "IT, AI" and shouted headlines; a morning Read retried after the
open would have called today "yesterday"; attribution with a skipped pair inside the window
claimed the return's dates; the briefing's name lookup was an unbudgeted quote scrape; a kept
brief said it was written "just now"; and write-lock eviction could let two writers run at once.

## Owner decisions

1. Keep or revert `0a77d41`, the regime breadth input (it moves the index read).
2. Cloudflare Web Analytics: keep (and the policy paragraph) or switch off.
3. The policy's `EFFECTIVE` date, and whether the change is announced first.
4. The overnight feed (F-02), not in this branch.
5. The control-edge contrast proposal above.

## Deploying and rolling back

See `DEPLOY.md`. This branch fast-forwards from `ca490f8` and adds no database migration.
Rollback: Railway's dashboard can redeploy the `ca490f8` deployment; on git, revert the range
`ca490f8..vc-demo-readiness` (or one commit) and push. The accounts snapshots it starts writing
(`snapshots/accounts-*.db`) are harmless if left.
