# Handoff 4: honest loading and a single delay source

Branch `handoff-4-honest-loading`, cut from `main` at c623c264 on 2026-11-04. It does not depend on Handoffs 1 to 3 and
can be reviewed and merged on its own. Not deployed.

## What was wrong

The authenticated audit of 2026-11-03 (defects 3 and 4) found Home panels left on "Loading" and quote delays that
disagree: 15 minutes on the Dossier and in Milo's answers, 20 on Brokerage. Reproduced in the code:

| What happened | Why |
|---|---|
| Brokerage said 20 minutes, the Dossier 15 | Each surface wrote its own sentence. The Dossier read the quote's own stated delay (15 for a Nasdaq stock). Brokerage printed the longest delay among the holdings' quotes (`max(delays)` in `app/brokerage/workspace.py`), which was 20, NYSE's. |
| Everywhere else said "up to 15 minutes" or "about 15" | Hard-coded on Home's panels and their About text, the status line, Settings, alerts, the paper desk, the research sheet, Options, Milo's panel and prompt, Milo's tools, the legal notice's label, the Desk's sources and a dozen payload notes. |
| "Up to 15 minutes" was wrong for NYSE | The feed states 20 minutes for every NYSE listing (JPM, KO, IBM, XOM, BRK-B, measured 2026-11-04). |
| Home panels could show a skeleton for minutes | `workspace.js loadPanel`: request limits of 30 to 90 s, then one quiet retry that put the skeleton back ("Still loading"), so a source that hung showed a skeleton for up to three minutes. A board the server was building was asked again every 12 s with no end, and the 20 s refresh asked a failed panel again forever. |
| Home's Markets tiles had no price time | Their quote read (`fast_info`) carries no trade time or delay; their only time was when Optic asked. |

## What was verified in the codebase

- **Quotes already carry their own time and delay.** Since 2026-10-21 the quote (`app/providers/yf.py quote()`) has
  `trade_time` (the trade's instant) and `delayed_minutes` (the feed's `exchangeDataDelayedBy` for the exchange), and
  the Dossier header used them through `sessionFreshness()`. The handoff asks whether each payload carries `as_of`: a
  quote's `as_of` is when Optic fetched it, not when it traded, so the label reads `trade_time`.
- **What the feed states**, on the local server at 1:46 PM ET on 2026-11-04: NYSE 20 minutes, Nasdaq 15, NYSE Arca
  none (SPY, GLD), the S&P 500 index none, Cboe's indices 15 (^VIX, its last trade 15 minutes old), CME futures 10
  (ES=F, 10 minutes old), over the counter 15 (TCEHY, 16 minutes old), Toronto 15, currencies and crypto none. NYSE and
  Nasdaq trades were seconds old, which is the feed's stated policy against its actual prints.
- **Brokerage uses the same feed** (`session_quotes`), each symbol with its own delay: its 20 was NYSE's.
- **The trend and sector boards' rows** carry `price_as_of` and `price_delayed_minutes`; Home's Markets tiles did not.
- **The research sheet had its own stale line**: `quote_freshness`, the policy's `quote_stale_minutes` (30) plus a
  hard-coded 15.
- **Option chains are a separate feed**: Tradier's is real-time when configured (the test `/api/health` already used),
  the free feed's about 15 minutes behind.

## What was built

**One record of delays** (`app/delays.py`, served at `GET /api/delays`), per source as the handoff lists them: quotes
(by exchange: the longest any exchange states, 20 minutes, the usual 15, the examples), option chains, Brokerage
(holdings as of the broker's sync, priced with Optic's quotes), fundamentals (as filed) and news (as published). It also
holds the stale tolerance, which is the research framework's rule, so the sheet and every label draw the line at the same
place. The server's own sentences read it: the legal notice's label, Milo's prompt, context line and tool notes, the
ticker and option payloads' notes, the Desk's sources, the alerts' notes, Brokerage's price-check note and the sheet.

**One formatter** (`static/v2/js/core/delays.js`) for every price label, from the quote's own stated delay and trade
time, in the reader's timezone (`prefs.zone()`, with the zone's own abbreviation from `Intl`, so a clock change is the
zone's rules, not an offset worked here):

| The quote | The label |
|---|---|
| States a delay, in session | `Delayed 15 min · as of 1:34 PM EST` |
| States a delay other than the usual 15 | `Delayed 20 min (NYSE) · as of 1:34 PM EST`: the exchange the number belongs to |
| States none, trade under two minutes old | `Live · as of 1:34 PM EST` (the owner's safeguard of 2026-10-21) |
| States none, older trade | `As of 1:34 PM EST` |
| States nothing | `Delayed up to 20 min · as of ...`, the conservative reading |
| Older than its delay plus 30 minutes, in session | `Stale · as of 12:56 PM EST` |
| Market closed or a holiday | `Market closed · last close Tue Nov 3` |
| Pre-market, after hours or overnight | `Pre-market · last close Tue Nov 3`, with the session's own print labelled beside it; `Pre-market · regular session only · last close Tue Nov 3` when the data holds no print of the session |
| The delay record could not be read | `Delayed up to 20 min · as of ... · delay info unavailable`, never "Live" |

A panel or table of several prices gets the range of their delays and the oldest current trade's time: `Delayed 0 to 15
min by exchange · as of 2:00 PM EST`, with stale ones counted ("· 1 stale"). Labels are elements that redraw themselves
in place when the reader changes timezone in Settings, when a device on "My device's time zone" moves, and every 30
seconds, so "Live" ages into "As of" and an old price into "Stale" without a reload.

**Every surface reads them.**
- *Chart and Dossier headers:* `dossier-frame.js` (`quoteCtx`, `priceWhen`, the header's label element), and the
  Overview's plain price line. An extended-hours print's time is in the reader's zone.
- *Brokerage:* each holding's quote has its label under it, and the page's quotes pill gives the range of the holdings'
  delays instead of the longest. The server sends `delay_range` and each quote's trade time, exchange and session.
- *Home:* each quoted panel's footer is its own prices' label (Markets, Quote, Index and sector trends, Your portfolio);
  the rest say the longest delay or the chain's in session and the session by name outside it. The Markets tiles now
  carry each row's trade time and stated delay from the feed's batch read (`stated_times`, one request).
- *Footers and statements:* the status line, Settings, Milo's panel, alerts, the paper desk, Options and the research
  sheet use `quotesSentence()`, `upTo()` or `chainWords()`.

**Loading that always ends** (`workspace.js loadPanel`):
- A panel shows its skeleton (the shape of its rows) for at most 10 seconds. Then the skeleton gives way to
  "Couldn't load {panel}." in the panel's own box, saying what happened, with a Retry button. An answer that arrives
  later replaces it.
- A failure is asked again by itself after 5, 15 and 45 seconds, then only when the reader presses Retry. A source that
  is down costs four requests a visit, never a loop.
- A retry, or the next 20 s refresh, joins a request still in flight for the same panel, ticker and setting rather
  than sending another. The 20 s refresh re-reads only panels that have figures, so a failed panel is never asked on a
  timer.
- A board the server is still building is re-read at most 10 times, then its footer says "Still building: Refresh to
  check".
- Retry is a button, so the keyboard reaches it. When it is pressed, focus moves to the panel's body. When an automatic
  retry redraws the panel, focus stays on Retry. When content replaces it, focus moves to the body. Panels load and
  fail independently.
- 10 seconds is the handover pack's figure, checked against the code: warm, every Home endpoint answered in under 2
  seconds locally (Markets 1.9 s, the rest under 0.4 s), and after a restart every panel had answered inside 10. A
  provider stall like the one of 2026-10-21 (over 30 s) now says so at 10 s and fills in when it ends.

## Acceptance tests (Handoff 4)

`tests/test_honest_loading.py`:

- **Delay labels agree on charts, Dossier, brokerage quotes and footers for the test set.**
  `test_acceptance_1_delay_labels_agree_on_chart_dossier_brokerage_and_footers` renders the Chart header, the Dossier
  header, the Brokerage holdings row and Home's Quote panel footer for AAPL, BRK-B, SPY, ^VIX, ES=F, TCEHY and a quote
  stating no delay, and requires the same label on all four. It also checks that the page footer's statement covers
  every one of them. Further tests show the server, the legal label, Milo's prompt and tools, Settings and Milo's panel
  reading the same record, and Brokerage sending a range.
- **Killing a panel's data source produces a retry state within the timeout, not infinite loading.**
  `test_acceptance_2_a_killed_source_gives_a_retry_state_within_the_timeout`: the Markets panel's source never answers,
  and at 10 seconds it says "Couldn't load Markets at a glance." with Retry, while another panel drew at once. Further
  tests cover a late answer replacing the retry state, the backoff (four requests, then none until Retry), a retry
  joining a request in flight, and the bounded polling of a building board.
- **Stale quotes carry a stale label; the market-closed state renders correctly.**
  `test_acceptance_3_*`: stale on the header, Brokerage and a list; a price stating no delay going stale; closed, a
  holiday, pre-market with and without its own print, and a Brokerage price that is a pre-market print. A further test
  covers labels ageing in place as the clock moves.
- **Edge cases:** the delay record failing (the longest delay and the note on every label, never "Live", asked again a
  minute later); the reader's timezone and a change to it (New York, Los Angeles, Tokyo, London); both sides of the
  2026-11-01 clock change; labels never hidden at phone widths; and a ratchet that fails if a delay number is written
  outside `app/delays.py` and `core/delays.js`.

These run in JavaScriptCore on a virtual clock with a stand-in fetch, since JavaScriptCore waits on real timers and has
no `clearTimeout`, `setInterval` or `AbortController`.

## Live check, 2026-11-04 (local server on this branch, real data, regular session)

- **Chart and Dossier headers agree:**

  | Symbol | Label |
  |---|---|
  | AAPL | Delayed 15 min · as of 2:08 PM EST |
  | BRK-B | Delayed 20 min (NYSE) · as of 2:08 PM EST |
  | SPY | Live · as of 2:08 PM EST |
  | ^VIX | Delayed 15 min · as of 1:53 PM EST |
  | ES=F | Delayed 10 min (CME) · as of 1:58 PM EST |
  | TCEHY | Delayed 15 min · as of 1:52 PM EST |

- **Home footers:** Markets "Delayed 0 to 15 min by exchange · as of 2:00 PM EST" (the VIX tile the oldest); Quote
  "Delayed 20 min (NYSE) · as of 2:15 PM EST" for PG; Watchlist "Delayed up to 20 min" (its rows are daily bars with
  no trade time). The status line: "From Yahoo Finance. Quotes are delayed up to 20 minutes during the session, by
  exchange; each price states its own delay and the time of its trade."
- **A killed source:** with the Quote panel's requests made to hang, it showed its skeleton at 9 s and "Couldn't load
  Quote and chart. It has not answered in 10 seconds. It appears here if it arrives." with Retry at 11 s. Markets,
  Watchlist, What matters today and the Desk were unaffected. With requests answering 500, it said "The source
  answered: Upstream failed. Optic asks again by itself (1 of 3)."
- **Keyboard:** Enter on Retry retried and put focus in the panel's body. An automatic retry kept focus on Retry, and
  the content arriving moved it to the body.
- **Phone, 375 px:** no sideways scroll. The long footer labels wrap to a second line and none is clipped.
- **Not checked live:** Brokerage, since the local server has no linked account (covered by the tests).

## Decisions for review

1. **"Up to 20 minutes" replaces "up to 15" in every general statement**, because NYSE states 20. That includes the
   legal notice's `delayed` label (served by `/api/legal`, not shown by a v2 page) and Milo's prompt. The legal label
   is counsel's text: please confirm.
2. **The exchange is named when its delay is not the usual 15** ("Delayed 20 min (NYSE)", "Delayed 10 min (CME)"), so
   the 20 explains itself where it appears. The handoff says to name the provider when its delay differs; the provider
   is the same, and the exchange is where the difference comes from.
3. **"Live" is kept** under the owner's safeguard of 2026-10-21: the feed states no delay and the trade is under two
   minutes old. Without the delay record it is never said.
4. **One stale line:** the research framework's `quote_stale_minutes` (30), past the quote's own delay (or 20 when it
   states none). The research sheet's line moves from 30 + 15 to 30 + the quote's delay: 45 minutes for Nasdaq, 50 for
   NYSE, 30 for a quote stating none.
5. **The automatic retry count continues across a Retry press** and starts again on a new visit to Home or a new
   ticker, so pressing Retry never restarts the automatic ones.
6. **Brokerage keeps `delayed_minutes`** (the longest) beside the new `delay_range`, for any reader of the old field.
7. **Two clocks in a Home footer:** "Updated 2:15 PM" is when Optic asked, and "as of 2:00 PM" is the oldest trade.
   The writing rules ask that each time says what it measures. If one is wanted, the trade time is the one to keep.

## Found and not fixed here

1. **Classic** keeps its own delay wording, under the owner's rule that it takes security fixes only.
2. **Other pages' loading.** Dossier tabs and the Markets pages end their loading at the API's own limit (20 s by
   default) in a failed state. The audit's defect, and this work, was Home's panels.
3. **Extended-hours prints** state no delay of their own in the feed, so they are labelled with their time only.
4. **The watchlist's rows are daily bars** with no trade time, so its footer states the longest delay rather than a
   time. A batch quote read like the Markets strip's would let it say both.
