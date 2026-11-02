# Security review (Phase 10, 2026-10-30)

A non-destructive review of the fifteen areas directive 10 section 7 names. Nothing was sent to production or to any
provider: the review read the code (a separate agent, read-only, then every finding was checked against the code here
before it was acted on), the fixes were tested in the suite and on the local server, and the one production fact used
(the domain is proxied by Cloudflare) came from a DNS lookup. No secret was printed, copied or found in the tree or in
git history.

The full draft, with file and line evidence for every claim and the areas that held up, is
`~/Optic/work/post-demo-ultra-2026-10-29/phase10/security/SECURITY_REVIEW_DRAFT.md` (line numbers there are the Phase 09
commit's). Bug numbers are in BUG_REGISTER.md; decisions D-076 to D-090 in DECISIONS.md; tests in
`tests/test_phase10_hardening.py` unless named.

## Findings and what was done

| Finding | Severity | Bug | Outcome |
|---|---|---|---|
| SEC-01 Model spend has no ceiling that free, unverified accounts cannot walk around | High | BUG-152 | FIXED: a server-wide daily ceiling over every question, the owner's aside, before any allowance is charged (`MILO_QUESTIONS_PER_DAY`, 300). Escalated: the number, a console spend limit, and email verification once mail exists (D-076, D-077) |
| SEC-02 One-time tokens in query strings reach the access log | Medium | BUG-153 | VERIFIED: the access log blanks token, code, state and secret values |
| SEC-03 No request-body limit | Medium | BUG-154 | VERIFIED: 413 above 2 MB, the Milo routes sized for their attachments (D-089) |
| SEC-04 Pre-account hijack through unverified registration and provider auto-link | Medium | BUG-155 | VERIFIED: no provider auto-link onto an account with a password (tests/test_auth_providers.py) |
| SEC-05 The data-not-instructions rule covers CONTEXT only | Medium | BUG-156 | FIXED: the rule covers tools, search and files in chat and research; both apps show the host beside each model-written link (D-087). A live model was not tested (no key) |
| SEC-06 The logo cache never evicts and starves the shared pool | Medium | BUG-157 | VERIFIED: listed symbols only, fullmatch, its own pool, an hourly fetch budget |
| SEC-07 Unpinned dependencies, no lock, no scan | Medium | BUG-158 | BLOCKED: a scanner or lock tool needs packages downloaded, the owner's approval (D-085) |
| SEC-08 The Google sign-in state is not bound to its browser | Low | BUG-159 | VERIFIED: a cookie holds the state's hash (tests/test_auth_providers.py) |
| SEC-09 Only part of the CSP is enforced | Low | BUG-160 | Partly: Permissions-Policy and the opener policy added; enforcing the full policy BLOCKED on hashes or nonces and a report collector (D-083) |
| SEC-10 Unversioned font stylesheets without integrity | Low | BUG-161 | BLOCKED: the owner's rule names jsDelivr; pinning needs the files fetched (D-084) |
| SEC-11 A non-ASCII token or signature answers 500 | Low | BUG-162 | VERIFIED: bytes compared |
| SEC-12 Weak email validation | Low | BUG-163 | VERIFIED |
| SEC-13 Passkeys without user verification | Low | BUG-164 | BLOCKED: kept by design for keys without a PIN, the owner's call (D-081) |
| SEC-14 Sessions slide forever; cookie prefix; CSRF binding | Low | BUG-165 | Partly: sessions end 90 days after sign-in; the cookie names and CSRF binding sign everyone out, the owner's (D-082) |
| SEC-15 Classic escaping gaps | Low | BUG-166 | VERIFIED: the single-quoted attribute double-quoted, the release link scheme-checked (D-080) |
| SEC-16 Exception text in public answers | Low | BUG-167 | VERIFIED: hosts, URLs and paths removed (D-088) |
| SEC-17 Reader emails in the mail failure log | Low | BUG-168 | VERIFIED: masked |

Known issues the review added evidence to, all closed in this phase: BUG-006 (API docs public), BUG-030 (the write
token reads reports with reader emails), BUG-052 (diagnostics in public payloads), BUG-053 (unmetered search and logos),
BUG-054 (the spoofable address), BUG-072 (public heavy endpoints), BUG-074 (brokerage controls), BUG-112 (question
length).

## The fifteen areas

| Area | Result |
|---|---|
| Authentication | Sound (Argon2id, hashed session tokens, identical failure answers, single-use resets that end every session, PKCE and nonce on OAuth). Fixed: SEC-04, SEC-08, SEC-12. Escalated: SEC-13 |
| Authorization | No IDOR: every route touching a reader's data scopes its SQL by the session's user id (an AST pass over 236 routes, then each reader-data router read in full) |
| User-specific API access | As above; reader answers are now `private, no-store` with `Vary: Cookie` (Phase 09) |
| Brokerage credential handling | Sound: per-user AES-256-GCM keys wrapped by an environment key, deletion is crypto-shredding, provider errors rebuilt without secrets. Fixed: BUG-074's controls |
| Secret exposure | None found in the tree or history. Fixed: BUG-052, BUG-006 |
| Cross-site scripting | v2 escapes every interpolation (38 `raw()` calls and 46 HTML sinks traced). Fixed: SEC-15. The CSP is not a second line yet (SEC-09) |
| CSRF | Double-submit header on every signed-in write, Lax cookies, JSON-only bodies. Escalated: SEC-14's binding |
| Input validation | Bound SQL parameters everywhere, no subprocess or eval, no SSRF. Fixed: SEC-03, BUG-112, the chart periods (BUG-169) |
| API rate limiting | Fixed: SEC-01, BUG-053, BUG-054, BUG-072, wrong write tokens (BUG-030) |
| Prompt injection | Fixed: SEC-05 |
| Sensitive-data logging | Fixed: SEC-02, SEC-17. Questions, answers and attachments are not logged |
| Database access controls | Parameterised, foreign keys enforced, brokerage payloads sealed; theses and saved research are plaintext by design |
| Dependency vulnerabilities | BLOCKED (SEC-07): installed versions listed in TEST_RESULTS |
| Session handling | Fixed: the 90-day absolute limit. Escalated: SEC-14's cookie names |
| Error-message exposure | Fixed: SEC-16, SEC-11, SEC-12 |

## For the owner (also in BLOCKERS.md)

1. Set `MILO_QUESTIONS_PER_DAY` to the number you want, and a monthly spend limit in the Anthropic console.
2. Close the Railway origin to traffic that does not come through Cloudflare, so `CF-Connecting-IP` cannot be written
   by a caller who goes around it.
3. Approve installing a dependency scanner (pip-audit) and a hashed lock file, or run them in CI.
4. Decide on the `__Host-` cookie names (everyone signs in again once), passkey user verification, and enforcing the
   full CSP after a period of collected reports.
5. Retire Classic's stored write token now that admin sessions cover the same writes.
