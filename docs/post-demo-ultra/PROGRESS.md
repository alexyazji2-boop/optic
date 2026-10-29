# Progress

Read this and [REQUIREMENTS_MATRIX.md](REQUIREMENTS_MATRIX.md) before changing anything (directive 12).

## Current state

- **Current phase:** 01 discovery and baseline (in progress).
- **Branch / worktree:** `post-demo-ultra` in `~/Optic/wt-ultra`, from `9fa0f36` (tag `post-demo-ultra-baseline`). Upstream unset; nothing pushed.
- **Commits on the branch:** `fce3e71` setup (directives, tracking files, CLAUDE.md section).
- **Local server:** launch config `optic-ultra` (:8250, stand-in model :8251, data `~/Optic/ultra-data`, sandbox brokerage, jobs off, no real model key). Seed password in `~/Optic/ultra-data/seed-output.txt` (never print it).
- **Working folder (outside the repo):** `~/Optic/work/post-demo-ultra-2026-10-29/` (tools/, crawl1/, baseline/, milo/, registry/).
- **Next action:** registry A and B merged into `registry/` and BUG-032..055 (verified the top claims: Macro pair setups, Scan trigger levels, `#/market` link, login CSRF BUG-043, skip link BUG-044, sizing persona BUG-045). Waiting on registry C (Dossier), D (tracking/owner/Classic), visual V1 and V2, and the dead-click chain; then merge, set R01 statuses, commit, Phase 02.

## Phase 01 so far

Done (evidence in TEST_RESULTS.md, BUG_REGISTER.md, FEATURE_REGISTRY.md):
- Baseline suite 7108 passed / 1 skipped / 6 warnings; `node --check` 122/122; ruff F 59 findings; route table 241 / 231 API.
- Architecture written (FEATURE_REGISTRY Part 1).
- Guest crawl at 1440/1280/768/390 of 56 routes (448 loads with the signed-in pass): 0 overflow, 0 script errors, 0 error states; density and small targets recorded.
- Reproduced in the browser: BUG-001 (advanced switch appends), BUG-002 (it rewrites the knowledge level), BUG-003 ("Follows AMD" on Home), BUG-004/005 (reading load); Dossier and palette search work for "nvidia", "amd" + immediate Enter, "msft".
- Milo stand-in probe: first byte 0.3 s warm, 1.5 to 2.2 s cold (context built before the stream starts).
- Security baseline (partial): guards per handler reviewed (no unguarded user-data route found), headers, cookie flags, `/docs` exposed live (BUG-006), overnight Robinhood feed without flag (BUG-022).

Also done since: signed-in crawl (0 script errors, 0 overflow; duplicate `/api/brokerage/status` on every brokerage page), Classic crawl at 1440 and 390 (26 views, 0 script errors; BUG-028/029), loading-state capture (BUG-031), contact-sheet pass at 390 and 1440 (four compliance candidates BUG-024 to BUG-027), API inventory (registry/api-routes.md, 232 routes), rendered inventory (registry/rendered-inventory.md, 56 routes x guest and signed in), journeys (Part 4), dependency map (Part 5), security baseline (Part 6), unshipped branches (Part 7), BL-01 confirmed (local key 401).

Not done yet: per-route source registry entries (agents A-D), detailed visual review (agents V1-V2), dead-click results, R01 statuses, commit.
