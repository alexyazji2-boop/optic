# Decisions

Each entry: what was decided, why, and what would change it.

**D-001 (setup) Work from production, in its own worktree.** Branch `post-demo-ultra` cut from origin/main
`9fa0f36`, which is what theopticterminal.com serves. The shared checkout's local `main` is 704 commits behind
origin and holds other sessions' uncommitted edits; it is left exactly as it was (master rule: preserve
pre-existing uncommitted changes).

**D-002 (setup) Nothing leaves this machine.** The branch has no upstream and is never pushed. Every phase says
"Do not deploy" and the master rules forbid deploys and production-data changes without explicit
authorization, so the owner's older standing instruction to push finished work does not apply here. The
owner's 2026-10-29 "You have permission to do whatever is necessary for this task" is read as covering local
engineering, local servers, local copies of data, test accounts and fixtures. It is not read as permission to
deploy, push, write production data, link real brokerage accounts or change billing, because the task's own
text excludes those.

**D-003 (setup) The directives are saved verbatim.** The overnight controller says they were saved in the
repository; a search of every checkout, docs folder and Downloads found no copy. They are in `directives/`
exactly as sent, so they survive context compaction. Interpretations go here, never into those files.

**D-005 (Phase 01) v2 is the product under repair; Classic is inventoried at route level.** Every visitor gets
v2 at `/` (OPTIC_DEFAULT_UI=v2 since 2026-10-19); Classic is the fallback at `/classic`, kept until the owner
approves retiring it, and the house rule is to leave Classic's copy alone unless the task is about it
(owner, 2026-10-25). So the registry lists Classic's 26 views and what replaces each in v2, and the crawl
checks Classic for script errors and placeholder text. Server-side changes (AI policy, prompts, data
correctness) reach both front ends and are tested for both.

**D-006 (Phase 01) Other branches' unshipped fixes are inputs, merged only when a phase needs them.** Several
local branches hold work the owner has not shipped (FEATURE_REGISTRY Part 7). A phase that needs one (for
example the Milo portfolio-privacy fix for Phase 02/08, or the Milo evaluation harness for Phase 08) takes
only that change, by cherry-pick or by hand, records the source commit here, and runs the full suite; nothing
is merged wholesale, and nothing leaves this machine.

**D-004 (setup) One phase at a time, nothing left behind.** The owner's sequencing instruction (directive 13)
makes every phase a gate: the next phase starts only when the previous one's requirements are PASS or
BLOCKED / UNVERIFIED for a named external reason.

**D-007 (Phase 01) Visual review done in the main session.** Six subagents running at once hit the account's
session limit at about 02:00 ET; the four still running stopped and nothing ran until 04:50 ET. The registry
agents' files were nearly complete (C's counts and D's Classic map were finished by hand); the two screenshot
reviewers had written nothing, so the visual audit was done here from labelled contact sheets and the crawl's
measurements (FEATURE_REGISTRY Part 8). From now on at most two subagents run at a time.
