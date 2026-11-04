# Handoff 3: invalid-symbol handling (the not-found state)

Branch `handoff-3-invalid-symbols`, cut from `main` at c623c264 on 2026-11-04. It does not depend on Handoffs 1 and 2 and
can be reviewed and merged on its own. Not deployed.

## What was wrong

The authenticated audit of 2026-11-03 (defect 1) opened an address for a symbol that does not exist and got a "MARKETS
Dossier". Reproduced in the code:

| What happened | Why |
|---|---|
| `#/markets` opened a Dossier for "MARKETS", with tabs, an empty chart and a Watch button | The router (`static/v2/js/core/router.js parse`) made any path segment shaped like a ticker (`[A-Z0-9.^=-]{1,12}`) a Dossier route. "markets" is not a page's slug, so it became the symbol MARKETS. |
| Milo was told the page was "MARKETS Dossier, Overview", with MARKETS as its ticker | `ui/milo.js buildContext` takes the route's symbol for any Dossier route, whatever the page found. |
| "MARKETS" could be saved to a watchlist | The Watch button was on the page, and the server's watchlist add checked only a symbol's shape (`app/account.py _symbol`). |
| Compare accepted it as a name | The page took any text; the server then failed it without saying it names no company. |

## What was verified in the codebase

- **The search box's universe** is `app/universe.py`: the Nasdaq Trader directory of US-listed securities, read
  daily and cached on disk, plus the instruments Optic quotes (indices, rates, currencies, futures, crypto).
  `known_symbol()` already answered "listed, not listed, or cannot tell".
- **Symbols outside the directory.** Over-the-counter and foreign listings (TCEHY, Tencent's ADR) are not in the
  directory, but have quotes and Dossiers today. The quote source (`PROVIDER.quote`) tells "no price" apart from "the
  source failed", and gives the last trade's time.
- **Existing not-found pieces.** A path not shaped like a symbol went to a generic "Page not found" (`pages/bridge.js`).
  The Overview showed an empty state when both the quote and the snapshot found nothing, but inside a Dossier frame.
- **Milo already flags** a symbol the question names that the directory does not have; the page's own symbol was not
  checked.

## What was built

**The check** (`app/symbol_check.py`, `GET /api/symbol-check?q=&from=`), against the search box's universe:

1. In the directory, or an instrument Optic quotes: listed.
2. Not in the directory: the quote source is asked, and a trade in the last ten days counts. This is how TCEHY still
   opens.
3. A quote whose last trade is older: no longer trades. The date is said; a delisting is not, since nothing verifies
   one.
4. Otherwise: unknown, with the closest listings. Symbols one edit away come first, by trading volume (APPL and AAPLL
   suggest AAPL), then what the search box finds for the text. Stocks and funds are each said to be one.

Spellings are one company: `aapl`, `brk.b`, `BRK/B` and `brk b` are AAPL and BRK-B. The directory or the quote
source failing is "could not check": never a not-found and never a Dossier. Answers are kept briefly: an unknown ten
minutes, a listed one six hours, a traded one an hour, and "could not check" never. A listed symbol is answered from
the directory in memory, on the event loop; anything else runs on the check's own four threads, so a Dossier's check
never queues behind other pages' data requests.

**The gate** (`static/v2/js/app.js show`, `core/symbolcheck.js`). Every page about one symbol checks it before
anything is drawn: the Dossier's seven tabs, the research sheet and the instrument page. The check runs alongside the
page's code being fetched. After 160 ms it shows "Looking up SYM". A symbol the reader has opened before is answered
from this browser for a day, so it costs nothing; a first visit costs one round trip, measured at 12 ms locally. The
check times out after eight seconds into the "could not check" state.

**The not-found page** (`pages/notfound.js`), at the address the reader opened, with no redirect:
- the heading "No company found for 'XXXX'", and a line saying why;
- a search box holding what was typed;
- the closest listings, each one press away, at 44px;
- "Markets Read" first when the text is a section's name;
- buttons for Discover and Markets Read.

There's nothing Dossier-shaped on it: no header strip, tabs, chart or figures, and Milo's context has no symbol. A
symbol that no longer trades gets its last trade date. An address with no symbol, or one that isn't a symbol, says so.

**The guards.**
- *Watchlist:* the store refuses a symbol the check refuses, or cannot check. The server refuses an unknown one too,
  reading only the directory already in memory, so a save never starts its download.
- *Compare:* every name is checked before comparing, and a refused one is offered its closest listings. The server
  leaves out an unknown name before fetching anything for it.
- *Milo:* the server drops a page symbol that names nothing from the context, with a note.

**The log.** Each miss is logged as `invalid symbol 'TEXT' (status) from PAGE`, sanitised, and counted for the owner
at `GET /api/admin/symbol-misses` (the owner's guard, as Metrics).
- The text keeps printable characters only, at most 24, so a newline cannot forge a log line.
- The page is an Optic route without its query, or another site's origin.
- Nothing about the reader is logged.
- The counts are kept in memory since the server started.

**What the browser keeps.** The symbols a browser found listed (`optic.v2.symbols.known.v1`) show which companies a
reader opened, so the key is personal. It joins the personal-keys list shared by Classic and v2 (`static/app.js`,
`core/device.js`), so it moves aside when another reader signs in. That one line is the only change to Classic.

## Acceptance tests (Handoff 3)

`tests/test_symbol_not_found.py`:

- **Ten invalid symbols** (`test_acceptance_1_*`): gibberish, typos of AAPL, empty, special characters, `<script>`,
  a newline. All are refused by the check and draw the not-found page with nothing of a Dossier.
- **Valid symbols** (`test_acceptance_2_*`): case and share-class spellings resolve, and funds, indices and an
  over-the-counter listing open their pages.
- **Nothing bogus saved** (`test_acceptance_3_*`): not to a watchlist (the store and the server), not to Compare, not
  to Milo's context.
- **Logged** (`test_acceptance_4_*`): sanitised, with the referring page, no reader identity; the owner's list.
- **Edge cases:** no longer trading, the check unavailable, answers kept briefly, the phone layout.

## Live check, 2026-11-04 (local server on this branch, real data)

- **Refused:** `#/MARKETS`, `#/ZZZZQX`, `#/APPL`, `#/AAPLL`, `#/%20`, `#/%25`, `#/AAPL!`, `#/<script>`,
  `#/instrument/`, `#/QWERTYUIOP/financials`, `#/XXXX/chart` and `#/apple inc` all draw the not-found page, with no
  tabs and no header. `#/MARKETS` offers Markets Read, then Robinhood Markets and Tradeweb Markets; `#/APPL` offers
  AAPL first.
- **Opened:** `#/aapl`, `#/brk.b`, `#/BRK%2FB`, `#/spy`, `#/msft/financials` and `#/instrument/^GSPC` open their pages.
- **Guards:** the watchlist refused MARKETS, APPL and %, and took NVDA. Compare refused APPL and offered AAPL, APP,
  APPF and APPN.
- **Milo:** on the not-found page its context has no ticker.
- **Phone, 375px:** no sideways scroll, 44px rows, and the search box at 16px.
- **Local timing caveat:** the local server speaks HTTP/1.1, so a check can wait behind earlier pages' requests in
  the browser's six-connection limit. The live site serves HTTP/2, which shares one connection.

## Found and not fixed here

1. **Classic** (`/classic#/MARKETS`) still draws its own page for any ticker-shaped address, under the owner's rule
   that it takes security fixes only.
2. **Verified delisting dates** need a source Optic does not have; until then a symbol that no longer trades is said to
   by its last trade date.
3. **Bad-link counts** live in memory and reset on a deploy; keeping them across deploys would need a table.
4. **Pages do not cancel their requests** when the reader moves on, which is what fills the HTTP/1.1 connection slots
   locally.
