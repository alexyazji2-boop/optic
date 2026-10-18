# Owner-only preview: proposal for review

> **Superseded by PREVIEW-PACKAGE.md** (2026-10-18). Two things changed since this was written. Access now fails closed: unset means owner-only. There is also a separate emergency shutdown, `OPTIC_V2_ACCESS=off`. This file's rollback table describes the earlier design.

Stage 0, 2026-10-18. A proposal only: nothing here is deployed. Each step below that touches production needs its own approval.

## What the preview is
- **Who sees v2:** the owner alone, on the production site, at `https://<site>/v2/`. Everyone else keeps the classic app at every address.
- **"/" does not change.** It serves the classic app to everyone, the owner included, unless the owner opts in with the footer link.
- **Both apps read the same account and the same browser keys.** Nothing is migrated, so leaving the preview loses nothing.

## The change, when approved
1. **Ship the frontend-v2 branch:**
   - from a worktree at origin/main, never the shared checkout's local main;
   - full suite green first (6,202 passed and 1 skipped on the Stage 0 branch);
   - fast-forward only.
2. **Set two Railway variables before that deploy:**
   - `OPTIC_V2_ACCESS=owner` (v2 is refused to everyone but the owner; they get the classic app at `/v2/`);
   - `OPTIC_DEFAULT_UI=classic` (the default; set explicitly so it is visible in the dashboard).
3. **Who counts as the owner:** the account in `ADMIN_EMAILS`. The server decides it from the signed-in session; it is never decided in the browser.

**What else the deploy changes, all behind the same release:**
- **Server:**
  - `/classic` always serves the classic app.
  - `/v2/` serves v2 with versioned, immutable asset addresses.
  - `/api/build` adds `v2`, `ui` and `v2_open`.
- **Sign-in:** a Google or Apple sign-in started from v2 returns to v2.
- **Theses:** a Brokerage thesis save no longer wipes the Dossier thesis snapshot (a fix for both apps).
- **Classic:**
  - every `href` it builds from data goes through `safeHref`;
  - its footer can offer "Try the new design", but only when v2 is open to that reader, so not to anyone but the owner during the preview.
- **Unchanged:** production serves the classic app to every reader exactly as before.

## Rollback (rehearsed 2026-10-18, 20 of 20 checks: STAGE0-EVIDENCE.md §10)

| Situation | Action | What a reader with v2 open sees |
|---|---|---|
| End the preview entirely, owner included | Redeploy the previous build (revert the merge). No setting closes v2 to the owner, by design: unsetting `OPTIC_V2_ACCESS` would open it to everyone | The owner's open v2 tab keeps working until reloaded; on reload "/" and the hash route serve the classic app |
| v2 at "/" must stop (after a later default switch) | `OPTIC_DEFAULT_UI=classic` | Readers who never chose v2 are moved back. Readers who chose v2 keep it (their choice is a cookie) |
| v2 must close to everyone but the owner | `OPTIC_V2_ACCESS=owner` | Everyone else is moved back, whatever they chose. `/` and `/v2/` both serve the classic app to them |

**How long a rollback takes:**
- **Locally:** a restart with the new setting took 2.1 to 2.6 seconds.
- **On Railway:** a variable change redeploys. The last measured deploy gap was about 10 seconds (2026-10-06).

**What survived a rollback, checked on the classic app afterwards:**
- the reader stayed signed in;
- a watchlist change made in v2 was there;
- the theme chosen in v2 was applied;
- the Milo conversation was kept.

## The owner's checklist in the preview

Data and spend:
- **Real data:** use the owner's real account and linked brokerage, which local checks could not do (sandbox only).
- **No spend on load:** check usage in Reports, Claude usage before and after a browse. The local probe found 0 calls on load; production should match.

Sign-in, on the owner's iPhone:
- **Passkey:** sign out, then sign back in with the passkey.
- **Google:** if configured, check that sign-in starts and returns to `/v2/`.
- **Password reset:** request a reset only if mail is configured (L2). Otherwise check the on-screen message.

Milo, on a phone:
- **Keyboard:** ask a question with the keyboard up (iOS Safari). The box should stay above the keyboard.
- **Stop:** stop an answer partway, then reopen it from History. It should be marked as stopped.

Moving between the two apps:
- **Classic to v2:** open a symbol in Classic, follow it, then open it in v2. It should be in the open list.
- **v2 to Classic:** change the open list in v2, then open the chart dock in Classic. The dock should show that list.
- **Classic-only tools:** follow every "Open in the classic app" link from a Classic-only tool (the chart studies, the DCF editor, the thesis check). Each should land on the same symbol and section.

Recording problems:
- **Reporting:** report anything odd with "Report a problem" in the v2 footer. Reports land in Reports, Problem Reports, tagged with the page.

## When the preview ends
- **Decided by the checks, not the calendar:**
  - the owner's checklist passes;
  - a week of the owner's own use raises no unresolved blocker in Problem Reports.
- **Next step:** opt-in for everyone (`OPTIC_V2_ACCESS=all`), which needs its own approval.
- **The default switch** comes after M1 to M8 in MIGRATION.md.
- **Classic is retired** only after every retained capability is migrated and verified and the observation period is complete. Elapsed time alone is not enough.
