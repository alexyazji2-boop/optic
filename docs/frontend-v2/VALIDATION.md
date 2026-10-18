# Frontend v2: validation of the first journey (Home, Dossier, Watchlist)

Run on 2026-10-17 against the real backend: a local server on :8075 with the seeded demo account, the sandbox brokerage, and no AI key (nothing can spend). Market data was live from the providers, as of Friday Oct 16's close (weekend).

## What was exercised

| Check | How | Result |
|---|---|---|
| New-visitor Home | Fresh browser: welcome, starters with real prices, Follow, knowledge modes, See your Home | Works; follows write the classic guest keys |
| Returning Home, guest and signed in | Browser list and account list | Strip, market panel, watchlist rows, What matters today, Desk, movers, scan alerts all from live endpoints |
| Portfolio block | Sandbox brokerage | Shown only when a connection exists; not linked in this run |
| Dossier Overview (AAPL, NVDA) | Header, chart, cone, four answers, drawers, two long-term views, verdict, digest, More | Figures equal to the API (price 343.46, trend score 82, case Neutral, fair value 243 to 306, ±5.71%, ±2.46%, 1.05×); the current app shows the same 82/100 |
| NVDA, a range too wide to rate | Fair value payload with `wide: true` | Says "No verdict" and quotes the reason; no meter |
| Watchlist, guest | Add, sort (7), filter (4), search, My order, remove with Undo, new, rename, delete | All correct; stored in the classic format |
| Watchlist, signed in | Same, through `/api/watchlists*` with the CSRF header | All writes reach the server; Free plan's 3-list cap shows the classic message |
| Alerts, signed in | Prefilled from the Dossier's Alert button, add two watches, Check now, mark seen | Server stores them; Check now reports met and not met with evidence |
| Sign in, guest things, sign out | Sign in with guest list present; "Bring them in"; sign out | Question survives navigation; guest names adopted into the account; sign-out shelves the account's keys and reloads, as in the classic app |
| Milo | Dossier Ask Milo, signed out and in | Context line shown; signed out: sign-in prompt; signed in: the server's refusal shown plainly (no key here) |
| Keyboard | Real key presses | ⌘K, type, Enter opens the company; focus lands on the page heading; chart arrows read prices; markers reachable by Tab; Escape closes drawers and returns focus to the opener |
| Screen reader | Accessibility tree read in the browser | One h1 per page, named landmarks, rail links named with "opens in the current app", answers labelled by question and answer, charts with a text summary |
| Automated audit | `launch-audit-2026-10-16/tools/audit.js` on 14 views × ivory and charcoal × desktop 1440 and phone 390, plus the drawers | 0 faults after fixes (contrast, unnamed controls, 24px targets, heading order, duplicate ids, overflow) |
| Loading, empty, error | fetch forced to hang, fail with 502, or return empty, on Home, Dossier and Watchlist, desktop and phone | Each block shows its own skeleton, error with Try again, or empty state; the rest of the page still renders |
| Mobile Safari | iOS 27 simulator, iPhone 17 | Home and Dossier render as in Chrome |
| Performance (warm server) | Navigation and resource timing, cache off | v2's own files: 29 requests, 86 KB transferred (232 KB decoded). The current app's Home: 1,144 KB (3.7 MB decoded). Home makes 8 API requests, the Dossier 11 |
| Test suite | `pytest -q` | 6182 passed, 1 skipped |

## Known limits of this run

- The slowest sources are slow cold: `/api/priority` timed out past 2 minutes while the server was being rate-limited by the data provider after a restart. Home shows a loading line after 8 seconds and the rest of the page is unaffected.
- VoiceOver itself was not driven; the accessibility tree was inspected instead.
- Milo could not produce an answer locally because there is no key; streaming was tested only up to the server's error event.
- The brokerage portfolio block was not seen with a linked sandbox account in this run.
