# Investor readiness audit: defect log

Branch `investor-readiness` from production `a783dc5` (27 October 2026, evening ET). Every defect below was
reproduced on a local copy of production (same commit, sandbox brokerage, stand-in model, no keys), and where
marked, on the live site read-only as a signed-out visitor. "Fixed and verified" means a test that fails without
the fix (where marked "mutation-checked", the fix was removed and the test failed) and a browser check after it.

Priorities: **P0** broken core journey, misleading financial data, security, crash; **P1** broken secondary
feature, stalled section, failure without recovery; **P2** polish.

## Fixed and verified

| ID | P | Where | What was wrong | Root cause | Fix (commit) | Verified by |
|---|---|---|---|---|---|---|
| D01 | P1 | Dossier, Options (any liquid name) | "The contracts did not load. No options chain for 'NVDA'." after Yahoo refused a request; Try again answered from cache for 60 s, and an empty expiry list was kept 30 minutes as "No listed options". | yfinance turns Yahoo's 401 "Invalid Crumb" into an empty list or `calls=None` without raising; `app/providers/yf.py` cached those as facts and `app/main.py` answered 404. | Refused reads are marked (`Unread`, `_unread_frame`) and never cached; research, picker and chain answer 503 with what happened; a symbol with none still gets 404 (d6950df). | `tests/test_options_unread.py` (7, mutation-checked); browser: NVDA Options loads; live NVDA Options loaded. |
| D02 | P1 | `#/SYM/sheet`, printable research sheet | Never rendered in any browser: skeleton forever, no heading. Also on the live site now. | `toLocaleString` with `dateStyle`/`timeStyle` plus `timeZoneName`, which V8 and JavaScriptCore both reject. | Component options instead (a5407e7). | `tests/test_date_format_options.py` scans all front-end formats; browser: sheet renders with heading and title. |
| D03 | P1 | `#/BRK.B` and any dot share class; Milo's tools | Every panel: "No price data found for 'BRK.B'"; Milo looked up the unknown symbol. Also on the live site now. | The router passed the dot form through; Yahoo's symbol is BRK-B (search already mapped it). | Router and Milo's tool input map `X.A`/`X.B` to `X-A`/`X-B`; suffixes like SHOP.TO untouched (00839e0). | `tests/test_v2_search_nav.py`, `tests/test_milo_tools.py`; browser: BRK-B Overview loads in full. |
| D04 | P0 | Financials, Overview bull/bear rules, research sheet (NVDA and any company holding short-term investments) | NVIDIA shown as "Net debt $435.0M"; it holds $62.6B in cash and short-term investments against $11.0B of debt. | Net cash used cash and equivalents only. | Net cash = cash and short-term investments less debt when the statement has the line; pages say what was counted (ce29e51). | `tests/test_financials_definitions.py`; API and page: "Net cash $51.5B, Cash and short-term investments $62.6B, debt $11.0B". |
| D05 | P1 | Overview of an unknown ticker | Under "Optic has no listing for ZZZZQ": a red "price history did not load, Try again" and four "Insufficient Data" verdicts, Watch and Ask Milo for a symbol that does not exist. | The page drew every section whatever the quote said. | When quote and history both say not found, the page stops at one card with Search and Home (7928e6c). | Browser: no error states, one card. |
| D06 | P1 | Overview when the quote source fails | A feed outage would have said "Optic has no listing for NVDA". | `unreachable: true` from `/api/quote` was read as not found. | Read as a source failure (7928e6c). | Code path; browser on the normal path. Not reproduced live (needs an outage). |
| D07 | P2 | Home linked panels, recents | A mistyped ticker whose quote timed out stayed in recents and became a guest's Home link ("No quote for ZZZZQ"). | The Overview recorded the symbol before the quote confirmed it. | Recorded once the quote confirms it (7928e6c). | Code review; browser recrawl. |
| D08 | P2 | Logos | A missing logo was asked for again on every repaint (4 requests for one page). | No memory of failures. | Failed logos remembered for the visit (7928e6c). | Browser request count. |
| D09 | P2 | Not-found address | No heading, the tab kept the previous page's title. Also live. | Bridge page drew a state card only. | Heading, title, Home link (7928e6c). | Browser: h1 "Page not found", title. |
| D10 | P2 | Glossary terms on Macro, Read, Scan, Compare (first visit) | Dotted terms took the click and did nothing. | Their handlers live in `ui/term.js`, loaded only by pages that build a term by hand. | `ui/glossmark.js` imports it (19aaee1). | `tests/test_v2_parity_b9b.py`; browser: fresh Macro, term opens its definition. |
| D11 | P1 | Charts using `ui/bars.js` (Options implied volatility by expiry, others with 0-decimal axes) | Gridlines at 12.5, 13.5, 14.5 labelled 13%, 14%, 15%: every point read half a point off. | Duplicate labels were thinned to every other tick, which could keep the half-steps. | A coarser round step first (2a8ac47). | `tests/test_v2_dataviz.py` (mutation-checked with the real SPY range). |
| D12 | P2 | Phone tables (Insiders, Analysts, Scan, Investing, Retirement, Explore) | Columns ran off the right edge with nothing saying the table scrolls. | `.tscroll` had no affordance. | Overflowing scrollers are marked and say "Scroll sideways for every column." (Home's wording), phone and touch only (22bfda1). | Browser at 390 and 1440; design-standard and checklist tests. |
| D13 | P2 | Copy | "The inputs above lean..." with nothing above (Macro); FOMC sentence broken mid-way; "past month ."; "A Index Read"; "1 months ago"; "a 8.7% move"; "SPY a setup triggered"; "yfinance" in reader text; "Earnings this week" over next week. | Source strings. | Corrected at source (6ec7d80). | Tests updated where they pinned text; browser. |
| D14 | P2 | Compare vs Dossier scores | NVDA's Overview short term 65 and Compare's swing 39 read as a contradiction. | Two different models, each documented on its own page only. | Compare says its scores are its own and why a Dossier's differ (6ec7d80). | Browser. |
| D15 | P2 | Tests | `test_read_freshness` failed every 27 October after 9:30 ET (also on production's commit). | Real clock in a date-dependent case. | Pinned to 7 AM ET (cfab8ae). | Suite. |
| D16 | P2 | Password reset link that has expired | Toast said to request a new link and left the reader on Home. | Boot only knew `#/signin`. | Opens the request form (ba86289). | Browser: lands on "Reset your password". |
| D17 | P2 | Brokerage, Connections | "After you finish at the provider, it returns you to Brokerage in the classic app": untrue, the callback lands in this app. | Stale copy. | Corrected (61698f6). | Browser after a sandbox link. |
| D18 | P1 | Overview pre-earnings view (NVDA) | "because beat EPS consensus in 100% of 8 quarters": no subject, on the demo company's Overview. | Evidence lines joined after "because" as written. | Lines that start with the company's verb name the company (568a1ae). | `tests/test_research_earnings.py`. |
| D19 | P1 | Investing, DCF notes | "Restated in a later filing: basic_shares_avg, diluted_shares_avg, dps, eps_diluted"; debt as "33,366,000,000". | Code keys and raw integers in reader text. | Words for every statement line; dollars as $33.4B (f04b672). | `tests/test_valuation_engine.py`. |
| D20 | P1 | Research sheet evidence; Overview company summary | "Trading above the 200-day average. 99 ." | The first-sentence split ended a sentence at every full stop, so a decimal cut it; a stray space at source. | Decimal-safe split in both pages; source space removed (bb77a7a). | `tests/test_research_sheet.py`. |
| D21 | P2 | Overview, Coming up | NVDA's Nov 17 report listed above three Oct 28 events. | Report added first so the cut keeps it, never sorted. | Kept items listed by date (1280797). | `tests/test_v2_overview_classic_port.py`, `test_v2_parity_b6a.py` updated. |
| D22 | P2 | Overview of a coin | "More on Bitcoin USD": a heading over nothing. | Section drawn with no items. | Left out when empty (1280797). | Code; recrawl. |

## Found, not fixed (with the reason)

| ID | P | Where | What | Why not fixed tonight | Proposed fix |
|---|---|---|---|---|---|
| O01 | P1 | Futures (WTI, gold) on Home and instrument pages, evenings | After the 6 PM ET reopen, the day's change is measured from today's settlement: crude reads "Last 99.88 −0.02%" while its chart says the session fell 1.85%. | Changes the meaning of every futures change in the app; needs a decision on which base to show. | Label the base ("since the 2:30 PM settle") or show the session change after the settle. |
| O02 | P1 | Crypto (BTC-USD) Overview | "The past year" is 252 bars, about eight months of a market that trades daily; disagrees with the 52-week high. | "The past year" is 252 sessions in four coupled places (chart, headline, trade answer, Classic); a half-change makes them disagree. | Calendar-date windows in `windowOf`, `trendFinding`, `overview-research` series together. |
| O03 | P1 | Milo on any page (owner's account only) | `get_my_portfolio` is offered on every page, so a Compare question quoted the owner's real holdings. | Fixed on `milo-portfolio-privacy` (2236205); the owner said not to push it. Investors' own accounts have no brokerage linked on production. | Owner decision: ship 2236205. |
| O04 | P2 | Overview pre-earnings view | "which tends to precede results above them": a predictive claim the validation program did not support. | Open owner decision since 27 October. | Soften or remove. |
| O05 | P2 | Overview Four questions | "(method research-1.0, policy policy-2026-10-14)" in reader text. | Deliberate traceability of the published rules; owner's call. | Move into How this works. |
| O06 | P2 | Options research table | "Tight 3.2%" beside "Fair 0.3%": the grade weighs open interest and volume, the word names the spread. | Vocabulary change across the Options tab and its method text. | Rename the grade ("Liquid / Fair / Thin") or show the reason beside it. |
| O07 | P2 | Two models with overlapping horizons | Overview short term 65 vs Compare swing 39; long term 81 vs 74; Investing's long-term breakdown differs from Overview's. | Product design; D14 says so on Compare. | One shared definition per horizon. |
| O08 | P2 | Rounding | Macro "55%" vs "54% above 200-day" for one 54.5%; Compare "rose 2%" vs "+1.5%"; Retirement 94% + 7%. | Many call sites. | One rounding rule per figure. |
| O09 | P2 | Earnings calendar | MRK with no name; "PFE PFE"; after-close reporters show only "Reported". | Feed data; not reproduced against the code yet. | Fall back to the profile name; read the released result. |
| O10 | P2 | Phone layout | Insiders rows 200 px tall (dates wrap); one 11.7 px label at Large text on Options; chip strips past the edge at Large text; Dossier tab-header wraps the company name on non-Overview tabs. | Polish; time. | Date cells nowrap; token sizes. |
| O11 | P2 | Alerts on a phone | After saving an edit, focus does not return to the row's Edit button (desktop does). | Found late. | Restore focus after the drawer closes. |
| O12 | P2 | Instrument pages | 10-year yield "Last 4.9930" without %; change in % of the yield where Home says bp; empty Volume pane for yields; "Vol 0.0M" for futures. | Formatting per instrument kind. | Units by kind; hide volume where the feed has none. |
| O13 | P2 | Company wording on non-companies | BTC "What the company does", "Share price"; SPY "What the company is"; ETF "next earnings report" checkbox. | Many templates. | Kind-aware labels. |
| O14 | P2 | News timeline strip | Three "Oct 27" axis labels, overlapping markers. | Time. | Hour labels on a one-day span. |
| O15 | Owner | Legal pages | Privacy says email delivery is not switched on and gives a Gmail contact. Accurate today. | Owner: SMTP provider, contact address. | Owner action. |

## Not defects (checked and closed)

- Home's first row ends at different heights: the owner's rule of 18 October ("any other panel sizes to its content
  and never stretches, so it is never half empty"); its lists scroll inside by design.
- A black box over Macro's regime card in one capture: not reproduced in ten timed samples without the crawler's
  animation override; an artefact of forcing animations off mid-fade.
- Milo on a phone: the sheet closes when the page changes (by design); the answer finishes in the background and
  is there on reopening. The box is not focused on touch screens, so the keyboard does not cover the answer.
- Insiders "Insider filings Loading": the SEC index was cold on a fresh server; warm it answers in milliseconds,
  and the view says "Failed" after 60 s if it never does.
- Browser suite failures traced to checks written before later redesigns: search row markup (`b.tick`),
  scan's `.sc-next`, the Optic Portfolio's hypothetical notice moved to the legal notice, Milo's Compare context
  renamed `ranks` to `scores`, the Earnings quarters table moved under View data.
