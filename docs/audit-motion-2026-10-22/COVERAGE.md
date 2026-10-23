# Coverage matrix, audit-motion (base 2e90288, live build)

Status: PASS, FAIL (reproduced), BLOCKED, NOT TESTED. "Fixed" is added once a fix is verified on this branch.
Evidence paths are under ~/Optic/work/audit-motion-2026-10-22/.

## Chart (AAPL, preview :8116, Playwright 1440)
| Item | Status | Evidence |
|---|---|---|
| 18 widgets open and render | PASS | all 18 ready, no console errors |
| Backtest completes; result reconciles with trades | PASS | 24 trades compound to +48.6% (shown +49%); 11/24 wins; avg win/loss match; cost_bps, fill and window in payload |
| Backtest verdict wording at 71% of random books | FAIL P3 | "no better than random entries" beside "beat 71%" (backtest.py:511) |
| Analysts "Revisions: Flat" label | FAIL P3 | ambiguous beside "-5.7% to the mean target"; it is EPS estimate revisions |
| Drawings: create 4 kinds, select, delete, undo, move, reload, per-symbol, remove all with confirm | PASS | drag moved hline 323.92 to 317.16 and saved |
| Bar sizes 1m to 1W, readout synced to symbol and size | PASS | all 8 load |
| Daily bars one session behind with no notice | FAIL P2 | daily last bar Oct 21 while 1h and weekly include Oct 22 (Yahoo has not published the daily bar) |
| Session regular/extended | PASS | 573 vs 1,331 bars at 15m |
| Indicators (RSI pane, Bollinger) draw and persist | PASS | |
| Keyboard: arrows, zoom, Home, screen-reader line | PASS | |
| Touch gestures | NOT TESTED | needs a touch device; physical devices not available |

## Options (AAPL)
| Item | Status | Evidence |
|---|---|---|
| Table bid/ask/mid, spread %, breakeven (strike + ask), cost x100 | PASS | 315C: mid 35.95, BE 351.75, $3,675 |
| Builder: long call, bull call spread, iron condor, calendar; mid vs crossing vs slippage; max gain/loss; breakevens | PASS | all hand-checked |
| Expiry payoff vs theoretical today/14 days separated and labelled | PASS | |
| Picker: tiny budget, report inside hold, hold through, long hold, no options, bad symbol | PASS | why_none counts sum to contracts considered |
| Catalyst timing: ambiguous earnings headline set aside, IV context measured | PASS | |
| Report-day pricing missing for AAPL (vol_surface.event says no scheduled report; Earnings has Nov 2) | FAIL P2 | agent fin-earn side note |

## Financials and Earnings (agent report: evidence/fin-earn/)
| Item | Status | Evidence |
|---|---|---|
| Annual/quarterly switch moves charts, tables, captions together | PASS | AAPL, RIVN |
| Empty period columns shown (RIVN 2021, Q1 2025 all n/a) | FAIL P3 | |
| Two consensus EPS figures for one quarter (hero vs tables) | FAIL P1 | RIVN -0.65 vs -0.72 (earnings.py:100 vs 533-541) |
| Track record EPS basis unlabelled (adjusted vs GAAP chart) | FAIL P2 | CRCL 1.12 vs -4.48 |
| Growth from profit to loss printed as -483.83% | FAIL P1 | CRCL (fundamentals.py:181) |
| n/a without reason | FAIL P3 | RIVN |
| Forward EPS growth from a negative base (+20.8%) | FAIL P2 | RIVN (earnings.py:539,560) |
| Average surprise inflated by a negative estimate (+249%) | FAIL P2 | CRCL (fundamentals.py:409) |
| No estimates shown as $0 | FAIL P1 | SIEB (earnings.py:533) |
| One analyst read as agreement | FAIL P2 | ESP (earnings.py:110-117) |
| "Last 8 reports" spanning 13 years | FAIL P3 | ESP (earnings.py:174) |
| Beat counts disagree in one sentence; "But fell" framing | FAIL P2 | ESP, CRCL (earnings.js:52) |
| Contradictory notes; "historically precedes beats" unsupported | FAIL P2 | fundamentals.py:422, earnings.py:899 |
| "Over the same span" with no span | FAIL P3 | finviz.js:98 |
| Double rounding: -66.6% vs -66.5% for one margin | FAIL P2 | RIVN (fundamentals.py:295) |
| AAPL every sentence and caption matches payload | PASS | |
| SPY fund handling | PASS | |

## Navigation
| Item | Status | Evidence |
|---|---|---|
| Switch company while requests outstanding (6 s delay) shows new identity with skeletons, no old figures | PASS | AAPL to MSFT |
| Rapid repeated navigation (MSFT then NVDA) lands on the last | PASS | |
| Back/forward between companies | PASS | |

## Brokerage (agent report: evidence/brokerage/)
| Item | Status | Evidence |
|---|---|---|
| Performance TWR, XIRR, benchmark, flows vs income | PASS | hand-computed |
| Multipliers 100/10/adjusted/missing; direction signs | PASS | |
| options_risk vs scenarios dollar delta with a dividend | FAIL P2 | workspace.py:415-422 passes no dividend_yield; two spot sources |
| Scenarios coverage 100% with 1 of 5 priced | FAIL P1 | scenarios.py:515-516, 152-154 |
| Unpriced-only symbol shown as 0 exposure | FAIL P1 | scenarios.py:332-351 |
| Stock with no quote silently valued at broker price | FAIL P2 | scenarios.py:145; names past 25 |
| Foreign cash dropped to 0 without FX | FAIL P2 | workspace.py:331-338 |
| Unpriced option unmentioned | FAIL P2 | portfolio.py:172-190 |
| Options carry no price_as_of, so stale flag never fires | FAIL P2 | portfolio.py:176-187 |
| Scenario stock price_basis label wrong | FAIL P3 | workspace.py:407-408 |
| Partial sync: options/scenarios do not say what did not arrive | FAIL P2 | workspace.py:373-375, 389-441 |
| Expired/stale connection not carried in section data | FAIL P3 | workspace.py:191 |
| Outage worded as "partial" | FAIL P3 | briefing.py:164-167 |
| Scorecard | NOT TESTED | |

## Navigation state, accounts, accessibility, reliability (Playwright, preview :8116)
| Item | Status | Evidence |
|---|---|---|
| Financials period survives Back | PASS | Quarters kept |
| Scroll restored on Back | PASS | 1,400 px restored |
| Scroll position lost when leaving within 120 ms of scrolling | FAIL P3 | 2,000 px restored as 1,400 (scrollmem.js debounce) |
| Paper Desk ticket: field typed after changing ticker is lost | FAIL P1 | ticker change repaints the form during focus change; "def" never arrives (paper.js change handler) |
| Paper Desk ticket kept within the visit, not across reload | PASS (by design) / P3 | |
| Watchlist add, duplicate refused, double Enter one request, rename, new list, 3-list limit, reorder, remove, undo | PASS | isolated account audit-tester@example.test |
| Watchlist and alerts accept a non-existent symbol | FAIL P2 | ZZZZQX added and alerted |
| Alert validation (empty, negative level, RSI 150), double-click Create makes one alert (server 409 on the second) | PASS | |
| Alert triggering | PASS (fixtures) | 268 watch/alert tests; live loop not run (WATCH_AUTO off, no notifications) |
| Paper Desk open (double-click one trade) and close | PASS | |
| Saved research | PASS (existing tests) | not driven in the browser |
| Names, labels, single h1, page overflow on 11 routes x 1440/390 | PASS | 22 checks |
| Chart heading order jumps h1 to h3 | FAIL P3 | widgets |
| Scan result symbol link 33x14 px on a phone | FAIL P2 | touch target |
| Light theme on rehearsal routes | PASS | |
| Large text: Chart overflows (39 px at 1440, 67 px at 844x390) | FAIL P2 | pricechart.js place2 double-scales under html zoom; tooltip too |
| 200% zoom (720x450) and short landscape (844x390) other routes | PASS | |
| Reduced motion | PASS (blanket rule in base.css) | rechecked after motion work |
| Main payload 500: specific failure and retry; retry recovers | PASS | AMD |
| Hung request times out with a message | PASS | QCOM, 60 s |
| Overview answer cards keep a skeleton after the payload fails or times out | FAIL P2 | dossier.js answers section |
| Secondary source fails, page still usable | PASS | INTC fair value 503 |
| Physical iPhone Safari / Android Chrome | BLOCKED | no authorised device access; viewport emulation only |

## Fixed on this branch (each re-verified in the browser or by its reproduction script)
| Finding | Commit |
|---|---|
| Financials/Earnings: $0 estimates, negative-base growth, two consensus figures, one-analyst agreement, inflated average surprise, "last 8" spanning years, unmeasured claims, swing-to-loss wording, double rounding, EPS basis label, beat framing | f39889a |
| Scenarios/Brokerage: coverage share, unknown not zero, missing quote said, dividend yield, option price times, unpriced option, FX cash, partial sync | b33c119 |
| Paper Desk lost input; Overview stuck skeleton; chart zoom overflow; stale daily bar note; unknown symbols refused; scroll memory; Scan tap target; wording | bef02f9 |
| Options report-day pricing missing for AAPL | 1139d0f |
| Milo: About line, unknown symbols, source labels, accidental Stop, prompt rules | 372918a |
| Motion and loading system | f7490d9 |
| Page line counted hidden skeletons | e8e48b4 |

## Still open
| Item | Status | Note |
|---|---|---|
| Real-model Milo answer quality (26-case set) | BLOCKED | no dedicated test key; owner's live allowance not used |
| Physical iPhone Safari / Android Chrome, touch gestures, software keyboard | BLOCKED | no authorised device access; viewport emulation only |
| Desktop drawer: keyboard trapped but background still takes mouse clicks | Observation | looks deliberate (one inspector you switch between objects); owner's call |
| Empty period columns (RIVN 2021, Q1 2025) | FAIL P3 | not fixed |
| Chart heading order h1 to h3 in widgets | FAIL P3 | not fixed |
| BRK.B not detected as a named symbol in Milo questions (BRK-B is) | FAIL P3 | not fixed |
| Paper Desk ticket not kept across reload | P3 | by design today |
| Brokerage scorecard reconciliation | NOT TESTED | |
| Brokerage expired/stale state carried in section data; outage worded "partial" | FAIL P3 | not fixed |
