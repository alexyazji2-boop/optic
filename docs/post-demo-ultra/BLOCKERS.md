# Blockers

Each blocker names the external dependency, what it blocks, what was done instead, and what would unblock
it. Expected blockers from earlier work are listed as "to confirm" until Phase 01 re-checks them.

| ID | Dependency | Blocks | Status | Workaround in this branch | Unblocked by |
|---|---|---|---|---|---|
| BL-01 | A working Anthropic API key on this machine | live-model answers for Milo and every AI writer: Phases 02, 05, 06, 07, 08, 11 | **confirmed 2026-10-29 01:45 ET**: the key in `~/Optic/options-terminal/.env` gets `401 invalid x-api-key` on the free `GET /v1/models` (no spend). Production's key works, but calling it means production writes and the owner's credit. | the local stand-in model server; deterministic policy and validator tests | the owner supplies a working key locally, or authorises a bounded number of calls |
| BL-02 | Qualified securities counsel | any conclusion that Terms, Privacy, disclaimers or advice boundaries are legally sufficient | expected | proposals written for review, never applied as legal text | counsel review |
| BL-03 | A live SnapTrade connection with real credentials | live brokerage linking | expected | the sandbox brokerage provider with synthetic holdings | owner-approved sandbox or test credentials |
| BL-04 | Stripe, SMTP | billing and real email | expected | none needed for this overhaul's scope | owner configuration |
| BL-05 | Market hours (9:30 to 16:00 ET) | checks of live quotes, quoted option chains and intraday freshness | time-dependent | fixtures and a fake clock; live-hours checks scheduled when the session reaches them | the clock |
