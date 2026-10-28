# Investor readiness audit, 27 October 2026

Audit and repair of the terminal investors will be shown on Wednesday 28 October, done the evening before on
branch `investor-readiness`, cut from production `a783dc5` (live build `a783dc562dcc`). **Not pushed, not
deployed.** Coverage is in `MATRIX.md`, every defect with its cause and verification in `DEFECTS.md`.

## The judgement

Optic is ready for an investor to explore the planned path and most of the terminal on their own, with the
limits below. The branch fixes the defects that would most damage trust if an investor found them: a cash-rich
company shown as net-indebted, an Options tab that could claim NVIDIA has no options, a research sheet that never
opens, a dot share class (BRK.B) that finds nothing, charts whose gridlines are labelled half a point off, a
grammatically broken sentence on the demo company's Overview, and internal field names in reader text. Until the
branch is deployed, those defects are **live** (checked on production tonight: the sheet, BRK.B and the not-found
page fail there now).

What this audit could not establish: the quality of Milo's answers from the real model (only a stand-in was
used, so no paid call was made), real brokerage linking (only the sandbox), email delivery on production (it is
in log mode), and the Classic app beyond an error-level crawl.

## Scope

- **v2**, the app served at "/": 36 views at 41 addresses; crawled at 51 addresses as a guest and signed in, at
  1440 and 390 px, cold and warm (306 page loads), then once more on the fixed build (204 loads).
- **Live site** read-only as a signed-out visitor: 40 addresses at 1440 and 390 (80 loads), with every request that
  could start a paid model write held back in the browser.
- **Classic** at `/classic` (reachable from v2's footer): 26 view addresses, error-level only.
- **Server**: 235 API routes, exercised through the pages that use them; write and paid routes only locally.
- **Journeys**: first use (account, email confirmation, first follow, sign out, reset), Milo end to end, sandbox
  brokerage (six scenarios, cancel, sync, disconnect), and the project's own v2 browser checks.

## Method

A local copy of production (same commit) with its own data, the sandbox brokerage, a stand-in for the model API
(no key, nothing spent), owner rights for a seeded test account, and a local mail relay that keeps messages.
Headless Chrome drove every page and recorded errors, stuck loaders, placeholder text, overflow, clipping,
missing headings, failed and duplicate requests; three reviewers read every full-page screenshot, and each of
their findings was checked against the page or the code before it was logged. A click pass pressed every visible
control on the busiest pages to find controls that do nothing. Details in `MATRIX.md`.

## What was fixed (22 defects, 16 commits)

| | Defects |
|---|---|
| Misleading financial data | D04 net cash without short-term investments (NVIDIA "Net debt $435.0M" instead of $51.5B net cash); D11 chart gridlines labelled half a point off; D01 a refused feed read reported as "No options chain for 'NVDA'" and cached |
| Broken pages and states | D02 research sheet never rendered in any browser; D03 `#/BRK.B` found nothing; D05 an unknown ticker's Overview drew an error and four verdicts under "no listing"; D06 a feed outage would have said "no listing"; D09 not-found page without a heading |
| Dead or misleading controls | D10 glossary terms did nothing on a first visit to Macro, Read, Scan, Compare; D16 an expired reset link left the reader on Home; D17 Brokerage said linking returns you to the classic app |
| Reader text | D18 "because beat EPS consensus" on NVDA's Overview; D19 code keys and raw integers in DCF notes; D20 "Trading above the 200-day average. 99 ." on the sheet; D13 nine copy errors; D14 Compare explains why its scores differ from a Dossier's |
| Layout and data hygiene | D12 wide phone tables say they scroll; D21 Coming up in date order; D22 no empty "More on" section; D07 mistyped symbols kept out of recents; D08 failed logos not re-requested |
| Tests | D15 a date-dependent test that failed on production's commit every 27 October after 9:30 ET |

## Validation

- **Test suite:** production's commit before: 7,073 passed, 1 failed (D15), 1 skipped. Branch head: **7,093
  passed, 1 skipped, 0 failed**: 19 tests added and the failing one fixed. The options and axis tests were checked
  to fail with their fix removed; the date-format scan checks itself against the sheet's old footer.
- **Design rules:** `tests/test_v2_design_standard.py` and `test_v2_checklist.py` pass.
- **Browser, fixed build:** 188 of 204 page loads clean; the other 16 are expected 404s for the unknown ticker (its
  page shows one clean card), a duplicated brokerage status request, and one cold-cache Home load.
- **Journeys:** first use 14/14; Milo 20/20 at 1440 (stand-in), phone behaviour checked by hand; sandbox brokerage:
  standard, edge, partial, expired and outage scenarios, cancel, sync, disconnect, and the connect rate limit.
- **Project browser checks** (quick mode, 390 and 1440): chart 19/19, Milo 19/19, release-extra 13/13 (links,
  keyboard focus, failure and recovery, stock/ETF/index, empty account), adopt 1/1; search 39/42, navigation
  23/28, watchlists 27/28, alerts 23/26, workspace 21/24, options 34/36, compare 22/26, financials 18/26, scan
  16/18, ownership 13/14, Milo evaluation 4/5, positions 14/16; phone sweep 108 of 160 rows clean (the rest are
  P2: chip strips at Large text, rows under the phone bar in capped tables, one 11.7 px label). Failures traced to
  checks written before later redesigns are named in `DEFECTS.md`; ten individual failures were not re-traced
  and are listed as such in `MATRIX.md`.

## Integrations

| Verified with the real service | In a provider sandbox | With a stand-in | Blocked or not tested |
|---|---|---|---|
| Yahoo Finance (local and live, read-only), SEC EDGAR, House Clerk, USAspending, FRED and Treasury rates (rendered) | Brokerage linking, holdings, partial sync, expiry, outage, cancel, disconnect | Milo and every written read (stand-in model); email (local relay) | Milo with the real model (needs paid calls; not asked); SnapTrade with a real broker (the owner's accounts); production email (log mode); Stripe (off); Google and Apple sign-in (not configured); passkeys (need an authenticator) |

## Outstanding

Not fixed, with the reason, in `DEFECTS.md` (O01 to O15). The ones an investor could notice:

1. **O01** In the evening, futures (WTI, gold) show the change since today's settlement: crude read "−0.02%"
   tonight on a day it fell 1.8%. Affects Home's Markets at a glance after 6 PM ET; correct during the session.
2. **O02** Bitcoin's "past year" covers about eight months.
3. **O03** Milo is offered the portfolio tool on every page; on the owner's account a Compare question can quote
   real holdings. The fix is on `milo-portfolio-privacy` (2236205), held by the owner. Investors' accounts have
   no brokerage linked, so they cannot see this; present from an ordinary account, never the owner's.
4. **O04** The Overview's pre-earnings view still says rising estimates "tend to precede results above them",
   which the validation program did not support (open owner decision).
5. **O06, O07, O08** Vocabulary and rounding: "Tight 3.2%" beside "Fair 0.3%" on Options; Overview and Compare
   score the same horizon differently (Compare now says so); a few figures rounded two ways.

## Investor demonstration checklist

**Before (deploy decision first):**
- [ ] Owner decides whether to deploy this branch tonight. If yes: `git fetch`, confirm `origin/main` is still
      `a783dc5`, run the full suite from `investor-readiness`, fast-forward push, wait for `/api/health` to show the
      new commit, then rehearse on the live site. Rollback: redeploy `a783dc5` in Railway.
- [ ] If not deployed: do not open the research sheet (`#/SYM/sheet`, "Export"), do not type `BRK.B` in the address
      bar (search for Berkshire instead), and avoid NVDA's Financials net cash line and SPY's implied volatility
      chart.
- [ ] Present from an ordinary account in a fresh browser profile, not the owner's (owner menus, real brokerage,
      O03).
- [ ] Warm the path 30 minutes ahead: Home, NVDA Overview, Chart, Options, Compare NVDA and MSFT.
- [ ] Present during market hours if possible (O01 is an evening effect).

**On the path:**
- [ ] Home: every panel names its source and time.
- [ ] Search NVDA: Overview, Chart (VWAP purple, EMA 50 red, EMA 21 green, EMA 9 white), Options.
- [ ] Compare NVDA and MSFT; point at the line saying these are Compare's own scores.
- [ ] Ask Milo about the comparison; it answers from the figures on screen. Real-model answers were not checked
      tonight: rehearse one question beforehand.

**If something fails:**
- [ ] A panel says it did not load: press Try again once; on the fixed build an options refusal says the data
      source did not answer, which is honest to show.
- [ ] Slow cold symbols: move to a warmed one (NVDA, MSFT, SPY).
- [ ] Milo slow or refusing: show the comparison table and "Optic's take", which carry the same figures.
- [ ] Production down: a local build of the same commit (`optic-investor` in `~/Desktop/.claude/launch.json`),
      said to be a local copy.

## Files

- `MATRIX.md`: every route and feature with method, result and limits.
- `DEFECTS.md`: fixed, open and closed findings.
- Working files, scripts and screenshots: `~/Optic/work/investor-audit-2026-10-27/` (crawler `crawl.py`, live
  read-only crawler `prod_crawl.py`, click pass `deadclicks.py`, journeys `first_use.py`, `milo_deep.py`,
  `brokerage_journey.py`, `brokerage_sync.py`, Classic `classic_crawl.py`).
