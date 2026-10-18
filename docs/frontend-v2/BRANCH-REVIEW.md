# Pending branches: what v2 still needs, and what to integrate or archive

Stage 0 review, 2026-10-18. Read-only: nothing was merged, deleted, pushed or
deployed. The recommendations need the owner's yes, branch by branch.

**Method**
- **Branch list:** every local branch not merged into origin/main (b8d3b50, fetched 2026-10-18).
- **Patch check:** `git cherry` counts commits whose patch is not on origin/main.
- **Per-file 3-way check:** each file a branch changed is compared with the merge base and with origin/main:
  - **shipped:** identical on origin/main;
  - **unshipped:** origin/main never touched it;
  - **diverged:** both sides changed it, so integration needs a merge or a port, not a fast-forward.

  The tool is `~/Optic/work/v2-2026-10-17/stage0/branches/three_way.sh`. Tests and docs are left out of the counts below.

## Integrate (backend that v2 reads through the same API, plus a v2 port)

| Branch | Unshipped | What it adds | What v2 must port | Order and risk |
|---|---|---|---|---|
| **source-foundation** (wt-sources, 68141bd, 15 commits) | 28 files unshipped, 4 diverged (app.js, brokerage.js, workspace.py) | Provenance states, `price_time`/`price_source`, Yahoo refusals held 90s, SEC pacing, Treasury par curve, `/api/health` sources summary, earnings `reporting_currency`, `actual_pending` | **Quote stamp:** "Daily close" when `price_source=daily_bar`; Live / Delayed ~N min / Stale from `price_time` age. **Earnings:** currency-aware amounts, and an "awaited" state. **Footer status:** read the sources summary | 1st. Merge origin/main in, full suite, then the owner's yes. Classic already has its half on the branch |
| **milo-reasoning** (wt-reasoning, 2438029, 18 commits) | 5 app files, 3 diverged (ai.py, app.js) | Portfolio views for Milo, `get_returns`/`get_correlations`, concept cards, caret symbols (^VIX), valuation warnings | Nothing visible. Its earnings-context guard is already covered: v2's Dossier leak guard drops any context object whose symbol differs from the page's (verified in Stage 0) | 2nd. Needs a rebase onto 9af5043 (Sonnet 5.5) |
| **validation** (wt-validation, cb5a41d, 19 commits) | 19 files (app/validation/*, retirement total return), 2 diverged | `/api/validation` history, track record for Milo, wording fixes, retirement total return | **Signal history / track record panel:** port `historyText`, `historySlot`, `trackRecordText` and `trackRecordForward`. This is milestone M4 in MIGRATION.md | 3rd. Owner review of the validation report is still pending |
| **home-released-results** (wt-results, f888236 only) | app/priority.py | Released economic and earnings results in What Matters Today | **v2 Home's What matters today:** render the row's `result` text | With source-foundation. Archive the second commit, d90bbd3 (a Classic menu style) |
| **plate-system**, a4cce8e only (1h bars on clock hours) | app/main.py `clock_hours` / `intraday_bars` | 1h bars at 12:00 to 1:00, not 12:30 to 1:30 | None: v2's chart reads the same bars | Cherry-pick a4cce8e alone |

## Integrate after review (larger, eval-gated)

| Branch | State | Recommendation |
|---|---|---|
| **milo-voice** (wt-milo, 32 commits) | ai.py diverged (+313/-116) from c2abae3; overlaps milo-reasoning | **Holds:** the eval harness (app/milo/checks.py, facts.py, examples) and the voice guide. **First:** rebase onto milo-reasoning. **Gate:** its own ACCEPTANCE.md. **v2:** already has the single Analyst control (from `/api/personas`); the knowledge-level control lives in Settings and in Milo's Answer settings. **Do not deploy** until the eval is rerun on Sonnet 5.5 |

## Archive (keep a tag, then delete the branch only on the owner's word)

| Branch | Why it is not needed |
|---|---|
| desk-redesign | Rejected 2026-10-17. Already tagged `archive/guided-redesign-2026-10-17` |
| home-declutter (wt-home) | **Superseded:** Classic Home only; v2 replaces Home. **Kept:** its "More from today" items (what changed since yesterday, trend board, movers) are on v2's restore list (MIGRATION.md, M7) |
| plate-system, 84211c7 + 72c42d3 | **Superseded:** Classic plate CSS; v2 has its own quote plates. **Integrate instead** only if the owner wants Classic polished while it is still the bridge |
| simplify-pass | Shipped as f091053 (its 3 remaining commits are diverged leftovers) |
| pulse-phone | Superseded by mobile-milo (efb9dcd, 9bfa070) |
| hig-pass (paused) | **Superseded:** Classic CSS; v2 rebuilt both areas. **Not yet checked in v2:** its two findings, table column alignment and chart height drift; v2's audit tests neither, so both are acceptance checks in MIGRATION.md (M1, M8) |
| ux-redesign | Superseded by ux-port and the workspace redesign |
| brokerage-link | Shipped as brokerage-ship 62e6c00 |
| paywall (2026-09-21) | **Superseded:** by app/billing.py (Stripe Pro, off). **Keep:** tag the branch so BUSINESS-MODEL.md stays reachable |
| home-legend, hover-sidebar-only, milo-valuation-context, options-budget, pulse-scout, stale-extended-hours, swing-setups | Every patch is already on origin/main (`git cherry`: 0) |
| main (local) | 485 commits behind and nothing unshipped. Never push it (standing rule) |

## Worktrees
- **Cleanup candidates:** 12 worktrees under the scratchpad's `/private/tmp` are already marked prunable, and about 20 `~/Optic/wt-*` worktrees sit on shipped branches.
- **Not done:** cleanup needs the owner's word, and nothing was removed.

## Sequence

1. **source-foundation,** then **home-released-results** (backend), with the v2 quote-stamp and earnings-currency ports in the same release as v2.
2. **plate-system a4cce8e,** the clock hours.
3. **milo-reasoning,** rebased.
4. **validation,** with v2 milestone M4 (track record).
5. **milo-voice,** gated by its eval.

Each step follows the same rules:
- one branch at a time;
- merge origin/main into the branch, then run the full suite;
- the owner's yes before any push;
- never from the shared checkout's local main.
