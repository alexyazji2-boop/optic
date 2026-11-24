# Pass 2, item 2: the six features, tested, with results

Two places each feature was exercised:

- SUITE: this branch's test suite, a real Chromium against the real server on this machine (tests/e2e/), with the
  feeds refused and Anthropic played by the recording stub; route-level tests beside it (tests/).
- COPY: the evaluation copy (Railway conjure-optic-eval, service optic behind the edge-optic gate), still on the
  Pass 1 head 2ed9722 as of 2026-11-17; checked from outside through the gate, signed out. A signed-in check on the
  copy needs an evaluator account password, which the ops Mac's key file does not hold today (it carries the gate
  only), so signed-in rows say so rather than claim a run.

| Feature | SUITE | COPY (2026-11-17, signed out, through the gate) | Result |
| --- | --- | --- | --- |
| Deep Research, his own question | `test_deep_research_sends_the_readers_own_question_and_shows_the_answer`: typed question sent to `/api/research`, reaches the model verbatim, answer drawn and labelled deep research | not run: needs a signed-in account (Milo is account-only) | PASS in the suite (below) |
| Index Read | `test_the_index_read_is_asked_from_the_board_and_answers_in_place`: pressed from the Indices board, answers in place or says why in the shared look | `GET /api/indices/board` 200 with live rows; `GET /api/sectors/SPY/read` 200, a written read with headline, stance and paragraphs ("SPY stays under yesterday's low, and the 200-day is next") | WORKS on the copy |
| Exports (the research sheet) | `test_the_research_sheet_exports_as_a_pdf_with_the_company_and_its_tags`: `#/AAPL/sheet` printed by Chromium to a PDF | the sheet is a page of the app; printing is the browser's; nothing server-side to call | PASS in the suite (below) |
| Passkeys | `test_a_passkey_is_added_in_settings_and_signs_in_on_its_own`: Chromium's virtual authenticator over CDP, added in Settings, then sign-in with the passkey alone; route level in `tests/test_auth_passkeys.py` | `GET /api/auth/providers`: passkey available, RP id `edge-optic-production.up.railway.app` (matches the copy's host, so a ceremony there is valid) | PASS in the suite (below) |
| Brokerage link | `test_the_brokerage_page_says_plainly_what_linking_needs_when_it_is_off`; route level in `tests/test_brokerage.py` (71 tests, SnapTrade played by fakes) | `GET /api/brokerage/status`: "Brokerage linking is not switched on for this deployment." | NOT TESTABLE END TO END on the copy or here: it needs SnapTrade credentials (his, test mode) that neither holds. The off state is clear and has no dead end |
| Alert delivery | `test_the_alerts_page_opens_for_a_symbol_ready_to_set_one`; delivery itself route level in `tests/test_alerts.py` (one email per scan, each sent once, pending when the mail server refuses, off while a blocker stands) | `GET /api/alerts`: delivery `enabled: false`, note "These alerts are shown in Optic; email delivery is not set up for readers." | OFF on the copy. Observed in the code: delivery sends one digest to one configured address (`ALERT_EMAIL_TO`, else `FEEDBACK_EMAIL_TO`), the owner's, not to each reader who set an alert. Readers get alerts in the app only. A decision for him: whether readers should get their own alert emails |

## Run result

Full suite on this branch, 2026-11-17: 9121 passed, 1 skipped, 1 failed (a text-level test reading the old hand-written
Try again markup, updated in the same commit series; 51 of 51 in that file and the states contract after). All six
journeys passed in that run:

- Deep Research, his own question: PASS in the suite (the typed question reached the model verbatim; the answer drawn
  and labelled deep research). Not yet run on the copy: needs a signed-in evaluator (key file holds the gate only).
- Index Read: PASS in the suite (pressed from the board; answers in place, here with the feeds refused, in the shared
  look); WORKS on the copy (a real written read for SPY).
- Exports: PASS in the suite (the research sheet printed by Chromium to a real PDF with the company on it).
- Passkeys: PASS in the suite (added in Settings with a virtual authenticator, then signed in with the passkey alone,
  at localhost). On the copy the RP id matches its host; a ceremony there needs a signed-in evaluator.
- Brokerage link: the off state PASS (says why, offers the watchlist and the Paper Desk); the link itself NOT
  TESTABLE without SnapTrade test credentials.
- Alert delivery: the Alerts page opens the form for the symbol (PASS); delivery logic PASS route level; email
  delivery is OFF on the copy, and by design sends one digest to the owner's address, not to each reader.

To finish on the copy: an `evaluator=` line in ~/.conjure/optic-eval.key (operator), then the Deep Research and
passkey rows run there; SnapTrade test keys from Alexander for the brokerage link.
