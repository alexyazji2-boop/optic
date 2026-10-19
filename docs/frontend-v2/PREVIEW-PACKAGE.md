# Owner-only preview: deployment package for approval

**Date:** 2026-10-18.
**Status:** prepared and verified locally. **Not deployed.** The live app is unchanged until the owner approves this deployment.
**Supersedes:** PREVIEW-PROPOSAL.md. Its rollback section predated fail-closed access and the emergency shutdown.

**The next step is a private preview only** (owner, 2026-10-18). v2 is reachable by the owner's account alone (`OPTIC_V2_ACCESS=owner`), Classic stays everyone's default, and nothing about it is public. Public rollout comes later and only after all three of:
1. **Visual acceptance:** the owner accepts the real experience in the preview (Home, the representative pages side by side, desktop and phone), not screenshots of a prototype.
2. **Functional verification:** the checks in §7 pass on the live preview, and the v2_check audit, the full test suite and the paid-call probe pass on the deployed commit.
3. **Migration requirements:** every capability in CAPABILITY-MATRIX.md is implemented and tested in v2 (M1 to M8 in MIGRATION.md), and launch requirements L1 to L11 are met.

The dark workspace (branch `v2-dark-workspace`, on top of this package) is not part of this package. Whether it joins the private preview is its own approval.

This is a preview of a rebuild still in progress, not a finished rebuild. Ten capabilities are incomplete in v2 and sixteen groups are Classic-only (MIGRATION-TRACKER.md). Classic stays the default for everyone, the owner included, until the owner opts in.

## 1. What would be deployed

**Code**
- **Branch:** `frontend-v2`. Its tip after this package's docs commit is given in the approval message; code as of `3f3d8be`.
- **How it ships:** a fast-forward of `origin/main` from `b8d3b50`, which has not moved since the branch was cut.
- **Commits:** 9 with code changes, the last being `a9e0818`. Every commit after it changes docs only; the approval message gives the exact tip.
  - `de6b20b`, `ba2b06b`, `6fdd4bb`, `8ea0562`, `688f24c`: the v2 pages, rounds 1 to 4.
  - `30ada38`: Stage 0.
  - `3f3d8be`: fail-closed access and the emergency shutdown.
  - `7058a93`: this package.
  - `a9e0818`: the session chip on one line, with no trailing comma (found while showing the preview).
- **Size:** 98 files, +13,313 / −57 lines. The bulk is new files under `static/v2/` and `docs/`.
- **No database migrations, no new dependencies, no new background jobs.**

**Railway variables**

Set before the deploy goes out:

| Variable | Value | If forgotten |
|---|---|---|
| `OPTIC_V2_ACCESS` | `owner` | Unset already means `owner` (fails closed). Set it anyway so the dashboard shows it |
| `OPTIC_DEFAULT_UI` | `classic` | Unset already means `classic` |

**Shipping:** from a worktree at `origin/main`, never the shared checkout's local main.
1. Fetch.
2. Run the full suite green on the exact commit.
3. Fast-forward.
4. Check the deploy came up, using the smoke checks in §6.

The push goes from the owner's Terminal or after an explicit yes in chat.

## 2. Every change a non-owner reader can see or that touches them

Checked side by side against production (`b8d3b50`) unless the line says otherwise.

| # | Change | What a non-owner sees | Evidence |
|---|---|---|---|
| N1 | "/" now goes through the frontend switch | **The page:** the same Classic page. Its HTML differs by 3 lines, a hidden "Try the new design" paragraph that is never shown to them. **Headers:** gains `Vary: Cookie` | Regression sweep: the "/" diff |
| N2 | New address `/classic` | The Classic page | Unit tests |
| N3 | Anything under `/v2` | **Pages:** the Classic page. **Files:** 404. Production returns 404 there today, because v2 is not deployed | Access rehearsal P1; unit tests on 14 address forms |
| N4 | `X-Optic-V2: closed` header on API answers | **Visible effect:** none; Classic ignores it. **Cost:** an owner check on each API request, +0.25 ms median on `/api/session` (2.22 against 1.97 ms) | Regression timing |
| N5 | `/api/build` gains `v2`, `ui`, `v2_open` | Nothing; Classic reads only `build` | `test_new_build_notice` |
| N6 | Thesis saves keep the stored snapshot when the save sends none | **The behaviour change readers will notice:** Classic's Brokerage thesis form no longer wipes the Dossier thesis check | Production: 9 snapshot fields became 0 after a Brokerage save. Branch: all 9 kept, the check conditions included |
| N7 | Google and Apple sign-in return | **From Classic at "/":** unchanged. **From `/classic`:** returns to `/classic`. **Hostile `next` values:** "/" | 7 parameterised tests |
| N8 | Classic's 37 data-built links pass through `safeHref` | **What changes:** only `http(s)`, `mailto`, in-app and same-site links survive; any other scheme becomes `#`. **Result:** no working link changed | Regression sweep: 0 links that work in production became `#`, across 75 page loads per build |
| N9 | `cached=true` on `/api/brief`, `/api/weekly`, `/api/catalyst-mode` | Nothing: the default is unchanged and only v2 asks with it | Stage 0 tests |
| N10 | The v2 files are on the server | Nothing: not reachable by them (N3) | Access rehearsal |

**Across the sweep:**
- **Page errors:** 0 new on the branch, against 0 in production.
- **Link counts:** one page's count differed. That was live-data timing: an extra headlines panel loaded, and every link in it is a valid address.

### 2a. If the dark workspace (`v2-dark-workspace`) joins the preview: what else a Classic reader would meet

| # | Change | What a non-owner sees | Evidence |
|---|---|---|---|
| D1 | `/api/priority` and `/api/earnings-week` are served from their last build while a fresh one runs, and the build is kept on disk (`data/boards/`) | **After a deploy:** Classic's What matters today and Earnings tab answer at once from the last build (labelled with its time) instead of waiting up to 90 s for a scan. **Never:** a build from another New York day. **The very first build ever:** unchanged, Classic waits for it as today; only v2 asks for the quick "building" answer (`quick=true`) | `tests/test_board_serving.py` (8 tests); cold timings in PERFORMANCE.md |
| D2 | The sandbox brokerage (development only) eases its balance estimate into the account's value, and a reconnect after a dev-server restart keeps the same connection | Nothing in production, which uses SnapTrade | `tests/test_brokerage.py`, `tests/test_brokerage_performance.py` |

## 3. Verification results

Run against the real app on this machine, with each scratch server on its own copy of the local data.

| Check | Run against | Done | Passed | Failed | Skipped | Not tested |
|---|---|---|---|---|---|---|
| Full test suite | `3f3d8be` | 6,222 | 6,221 | 0 | 1 (live EDGAR read, needs `OPTIC_LIVE_EDGAR=1`; not v2) | none |
| Access and both rollback modes (`access_rehearsal.py`) | current code | 46 | 46 | 0 | 0 | see §7 |
| Classic and v2 data round trips (`roundtrip.py`) | current code | 62 | 62 | 0 | 0 | see below |
| Saved research, v2 to Classic, signed in and guest (`saved_research_reverse.py`) | current code | 9 | 9 | 0 | 0 | none |
| Classic against production, side by side (`classic_regression.py`) | `b8d3b50` against current code | 150 page loads, 1 thesis flow, 1 timing | 0 regressions found | 0 | 0 | none |
| Performance targets (`load_perf2.py`, 288 loads) | current code | 7 targets | 5 met | 2 missed (§5) | 0 | production network (§7) |
| Paid calls on load, v2 (`paid_call_probe.py`) | current code | 80 page loads (40 views × desktop and phone) | 80 with 0 model calls | 0 | 0 | buttons labelled as model calls; scheduled jobs |
| Accessibility audit (`v2_check.py --audit`) | current code | 28 captures (7 views × 2 sizes × 2 themes) | 28 at 0 faults | 0 | 0 | screen readers (L9) |
| Passkey sign-in and registration (`passkey_check.py`) | Stage 0 code; sign-in code unchanged since | 2 | 2 | 0 | 0 | a real device (§7) |

**The 62 round trips**

Each one writes through one app's own code and checks what the other app shows, plus the store underneath. Both directions are covered.

| Area | Checks |
|---|---|
| Watchlists, including the list left open | 10 |
| Price alerts | 5 |
| Theses, Classic Dossier against v2 Brokerage | 9 |
| Valuation scenarios | 5 |
| Saved research, both directions | 3 |
| Paper trades | 4 |
| Retirement | 3 |
| Chart drawings | 5 |
| Milo history | 3 |
| Preferences | 4 |
| Recent symbols | 2 |
| Account isolation across two accounts, in both apps | 8 |
| Sign-ins | 1 |

**Not covered by the round trips:**
- **DCF models:** v2 has no editor yet (C13, M2).
- **Legacy drawings (`optic.chart.drawings.v1`):** only Classic migrates them.
- **Real brokerage data:** the brokerage is a sandbox locally.

**The saved-research case left open in Stage 0** is now tested in both directions, signed in and as a guest.

**Superseded:** Stage 0's `rollback_rehearsal.py` (20 of 20). Its last phase expected v2 to be open with no setting; that is now fail-closed by design.

## 4. Access restriction and both rollback modes

**Fails closed.** With `OPTIC_V2_ACCESS` unset (the proposed deploy):
- **Who was tested:** a signed-out reader and a non-owner account, each holding an `optic_ui=v2` cookie.
- **Pages:** they got Classic at `/`, `/v2/`, `/V2/`, `/v2/index.html` and `/v2/#/AAPL`.
- **Files:** every v2 file returned 404 (app.js, store.js, `/V2/JS/APP.JS`, base.css), and no address returned v2 page or module source.
- **Footer:** Classic did not offer "Try the new design".
- **The owner** got v2 at `/v2/` and Classic at `/` until opting in.
- **Unreadable settings:** any value other than `all`, `owner` or `off` means `off` (unit tests).

**Normal rollback:** `OPTIC_DEFAULT_UI=classic`.
- **Readers who never chose v2:** "/" serves Classic again. An open v2 tab offers "Open the classic app", with Later.
- **Readers who chose v2:** they keep it (rehearsal P3).

**Emergency shutdown:** `OPTIC_V2_ACCESS=off`.
- **Scope:** v2 is closed to everyone, the owner included, whatever their cookie says.
- **Open tabs:** an open v2 tab is told at its very next request, with no Later. Its next move lands on Classic at the same page (`/classic#/AAPL`).
- **What the reader kept:** they stayed signed in, and their watchlist change, theme and Milo conversation made in v2 were all there in Classic.
- **Every v2 page and file** was refused, the owner's included.
- **Choices are not erased:** the cookie is kept, and when v2 reopens (P5) the reader's choice brings v2 back.

**How long each takes:**
- **Locally:** each setting change took a 2.1 to 2.3 s restart.
- **On Railway:** a variable change redeploys. The last measured deploy gap was about 10 s.

## 5. Performance

Full tables are in PERFORMANCE.md. The targets were written before the measurement, the throttling matches Stage 0, and each cell has 9 runs.

**Phone, cold:**
- **Usable content:** v2 3.46 s (Home) and 3.35 s (Dossier), against Classic's 7.70 s and 7.24 s.
- **First paint:** v2 2.74 s against Classic's 3.44 s.

**Missed targets** (stated, not relaxed):
- **T2, phone warm Dossier:** v2 0.92 s against Classic's 0.80 s. It is consistent, so it is a real gap.
- **T6, desktop cold Home:** 3 of 9 runs took 1.36 to 1.39 s against 0.98 s for the rest. They track a slower server answer, but the request responsible is not isolated.

Both are open items in M8. Neither blocks an owner-only preview, but each must be met before v2 becomes anyone's default.

## 6. Smoke checks right after the deploy

| Check | Expected |
|---|---|
| `curl -s https://<site>/api/build` (signed out) | Has `v2` and `"v2_open": false`; header `X-Optic-V2: closed` |
| `curl -s https://<site>/v2/` (signed out) | Classic HTML: has `id="legal-footer"`, no `optic-build` |
| `curl -s -o /dev/null -w "%{http_code}" https://<site>/v2/js/app.js` | `404` |
| `curl -s https://<site>/` with `-H "Cookie: optic_ui=v2"` | Classic HTML |
| Owner, signed in, opens `/v2/` | v2 loads; the footer has "Use the classic app" |
| Owner opens `/` | Classic, unchanged |
| Usage in Reports, Claude usage, before and after a 10-minute v2 browse | No change from page loads |

## 7. Checks that need the live owner-only preview
These cannot be done locally:

| Area | Check on the real account or device | Why only live |
|---|---|---|
| Milo, a real model | The end-to-end path is checked locally with a stand-in model (`milo_e2e.py`, 7 of 7); the answers themselves are not. Ask from three Home panels (Contracts, Quote and chart, What matters today) with a linked ticker: the answer is about that panel and that ticker, uses Optic's figures rather than invented ones, and its sources open | The local server has no model key on purpose |
| Milo | Ask a real question on the Dossier and on Options. Check it streams, the sources open, an answer chart draws, and "Watch"/"Save" cards work. Ask a follow-up after moving to another symbol: the panel names the new symbol | No model key locally (stubbed streams only) |
| Milo, mobile | On an iPhone in Safari, type a question with the keyboard up. The box stays above it; Stop works; History reopens the conversation | Emulation only so far |
| Sign-in | On the iPhone: sign out, then sign in with the passkey. If Google or Apple is configured, start sign-in from `/v2/` and land back on `/v2/`. Password reset only if mail is configured (L2) | Virtual authenticator only; providers not configured locally |
| Brokerage | Open Brokerage in v2 on the real linked accounts. Check holdings, performance and events match Classic, and a thesis edit in v2 shows in Classic's Brokerage and keeps the Dossier thesis check | Sandbox provider locally |
| Mobile layout | Home, Dossier, Options and Watchlist on the iPhone, portrait. The phone bar is unchanged; nothing scrolls sideways | Simulator and emulation only |
| Performance | Re-run the throttled scripts against the live URL with the owner's session, and read Server-Timing on `/api/ticker` | HTTP/2 and Railway's edge are unmeasured |
| Spend | Claude usage unchanged by browsing v2 | Probe used a recording stand-in |
| Edge behaviour | `X-Optic-V2` reaches the browser through Railway's edge; private module caching is respected | Local server only |
| Rollback | Optional, with the owner present: set `OPTIC_V2_ACCESS=off`, confirm an open v2 tab moves to Classic, then set it back to `owner` | Rehearsed locally only |

## 8. Unresolved limitations
- **Not tested anywhere yet:** real model answers, real provider sign-in, a real iPhone keyboard, real brokerage data, production performance, and production edge caching (§7).
- **Performance:** T2 and T6 are missed (§5).
- **The rebuild is not complete:** 10 incomplete capabilities and 16 Classic-only groups remain, tracked row by row in MIGRATION-TRACKER.md through M1 to M8.
- **Classic issues found but not changed**, because Classic is live (STAGE0-EVIDENCE.md §7):
  - the thesis-check save blanks two Brokerage fields;
  - placeholder watchlist chips after a reload;
  - model calls on load for Earnings, Read and Macro (L11).
- **Launch requirements L1 to L11 are open.** None blocks an owner-only preview. All of them block making v2 public.
- **Branches:** the integrate and archive recommendations in BRANCH-REVIEW.md are untouched. Nothing was merged, archived or deleted.

## 9. What approval covers
- **Approval covers only:** the deploy above with `OPTIC_V2_ACCESS=owner` and `OPTIC_DEFAULT_UI=classic`, and the smoke checks.
- **Each needs its own approval later:**
  - opening v2 to all;
  - making v2 the default;
  - integrating or archiving branches;
  - any change to Classic's live behaviour beyond §2;
  - retiring Classic.
