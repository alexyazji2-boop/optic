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
| BL-06 | Docker on this machine | building the production image (`Dockerfile`, python:3.12-slim) locally; the suite runs on the venv's Python 3.9 instead | confirmed 2026-10-29 (`docker` not found) | Railway builds the image on deploy; the suite covers the code | Docker Desktop installed, or a CI build |
| BL-07 | The owner's decision on a model-based output check | a second, model-based reading of each finished AI answer against the advice rules (COMPLIANCE_REVIEW section 5, item 2); it adds one small-model call per answer | raised 2026-10-29 (Phase 02) | the deterministic gate and whole-answer check, with their measured rates | the owner's approval for the spend, then BL-01 to measure it |
| BL-08 | The owner's configuration of the brokerage consent | linking consent naming the published Terms and Privacy policy instead of the 2026-10-12 drafts | raised 2026-10-29 (Phase 02, COMPLIANCE_REVIEW section 7 item 5) | none: engineering cannot choose the version every linked reader re-agrees to | setting `TERMS_URL`, `PRIVACY_URL` and `BROKERAGE_TERMS_VERSION` in Railway |
| BL-09 | The owner's and counsel's decision on the overnight feed and Yahoo data | removing or licensing the Robinhood overnight endpoint and Yahoo Finance data (BUG-022, BUG-023) | raised 2026-10-29 | `OPTIC_OVERNIGHT_FEED` switch (default on, live behaviour unchanged) | a decision, and a licensed provider if needed (data-provider research, 2026-10-24) |
