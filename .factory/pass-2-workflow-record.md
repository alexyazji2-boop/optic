# Pass 2, item 1: the eight workflows walked, and what the walk found

Walked by `tests/e2e/test_pass2_workflows.py` (a real Chromium against the real server, every feed refused at a
closed port, so every market panel is in its outage case), 2026-11-17, on branch factory/pass-2-works-data-workspace.
Each screen is held to five rules: no page error; no raw machine text; no block still loading once its requests have
settled (30 s cap; a board the server says it is building counts as settled, since the page says so and asks again);
every failed block in the one shared look; a way forward from the page itself. Milo is opened from every screen of
every workflow. The loaded case of "research a company" is walked with the recorded fixtures.

| Workflow | Screens walked |
| --- | --- |
| Research a company | Overview, Chart, Investing, Earnings, Financials, News, Options, research sheet |
| What moved today | Home, Read, Macro, Indices, an instrument (S&P 500), Earnings week |
| Watch names | Watchlist, Alerts (signed in) |
| Screen for candidates | Explore, Scan, Insiders, Analysts |
| Practise or model | Paper Desk, Optic Portfolio, Retirement, Compare |
| Brokerage | Brokerage (signed in) |
| Ask Milo | the Ask Milo button pressed on every screen above, the panel opening each time |
| Account | Settings, Saved research, Sign in (signed in) |

## Defects found and fixed

| # | Where | What the reader saw | Fix |
| --- | --- | --- | --- |
| W1 | Stock page, Company events | "Loading company events" for good whenever the price history answered "No price data found" (the price feed down on a listed symbol): the events were only started on a non-404 answer | started on every answer (`pages/dossier.js`) |
| W2 | Home, the day's figure | the S&P 500 figure's placeholder stayed for good when Home's answer carried no index level, and for as long as Home's panels queued | says "The day's figure did not load. The strip below has the markets." once Home has answered without a level, or after the panels' own wait (10 s); a late figure still draws (`pages/workspace.js`) |
| W3 | Read, Today's priority | a placeholder for up to 90 s on a cold first build (measured 119 s with the feeds down), then "Nothing on the board" | asks with `quick`, says the board is building, and asks again every 10 s up to ten times, as Home's panel already did (`pages/read.js`) |
| W4 | Brokerage, off on the deployment | one sentence and nothing to press: a dead end | the sentence, plus the watchlist and the Paper Desk as the ways on (`pages/brokerage.js`) |
| W5 | Fifteen failed blocks across the app | each written by hand: four headings styles, three retry wirings, two showing the browser's raw error text ("x is not a function") | all drawn by `states.failed`, which now takes a heading, a body, a retry and extra content; the raw error stays in the console; "Could not load" said as "did not load" in three places; held by `tests/test_pass2_states_contract.py` |
| W6 | The suite itself | one dated fixture (an over-the-counter quote of 2026-11-04) made the watchlist save test fail from mid-November | the quote is dated an hour before the run (`tests/test_symbol_not_found.py`) |

## Seen, not changed in this commit

- Earnings week, first build: "Gathering report dates for about 150 companies. The first scan takes a minute or two."
  with a placeholder under it. A truthful building state, kept; the walker accepts it.
- Earnings week: the lone "." reported under the notice is not on the page; it was pytest's progress dot after the probe's printed output (traced 2026-11-17).
