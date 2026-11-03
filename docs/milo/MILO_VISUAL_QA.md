# Milo activity states: what was tested

Everything below was executed on 2026-11-03 against the v2 app running locally (`OPTIC_DEFAULT_UI=v2`, port
8072) in the desktop app's browser pane, branch `milo-animation`.

**How the stream was driven.** The app's own Anthropic key is refused (401), so no real model answer could be
produced. Every browser run used the real panel, the real `send()`, the real SSE reader and the real paint
loop, with `window.fetch` stubbed in the page so the SSE frames were pushed by hand in exactly the vocabulary
`app/ai.py` sends (`status`, `retrieved`, `delta`, `error`, `done`). That verifies the panel end to end and
costs nothing. What it cannot verify is the content of an answer, which is noted per scenario below.

**One measurement caveat.** The browser pane throttles timers: an awaited 80 ms came back at about 1070 ms.
Wall-clock figures taken around awaited delays in this harness are therefore meaningless and are not reported.
The performance numbers in `MILO_ANIMATION_SYSTEM.md` are synchronous measurements, which the throttling does
not touch.

## Viewports

| Size | Panel width | View | Result |
| --- | --- | --- | --- |
| 1280 x 900 | 560 px docked | expanded card, 519 x 133 | correct |
| 1440 x 900 | docked | expanded card | checked earlier the same day for prop legibility; the props were enlarged from 52 px to 56-72 px as a result |
| 1100 x 820 / 444 px panel | 444 px | expanded card (bubble 403 px inside it) | correct; this measurement is why `CARD_MIN` is on the panel, not the bubble |
| 375 x 812 (phone) | 375 px full width | compact line, 343 x 44 | correct, no horizontal overflow |

## The 25 scenarios

| # | Scenario | Verdict | Evidence |
| --- | --- | --- | --- |
| 1 | Basic question, no market-data tool | Pass | states `[thinking, thinking, writing, complete]`; Researching and Analyzing never appear |
| 2 | Current market-data question | Pass | tool status then `retrieved` gave `[researching, analyzing, writing, complete]`; the two ticks read "NVDA options analytics", "NVDA quote", which are exactly the labels that returned |
| 3 | Complex financial research question | Partial | the state path and the evidence list are verified as above; the answer's own content could not be produced (key refused) |
| 4 | Multi-tool research request | Partial | two labels in one `retrieved` batch verified in the browser; a second tool round after text has started (`writing -> researching`) is covered by `tests/test_milo_activity.py::test_a_tool_called_after_the_text_starts_is_still_honest`, not in the browser |
| 5 | Long streaming response | Pass | 12 chunks streamed on top of a 48-message conversation: text kept, no horizontal overflow, row stayed in Writing |
| 6 | Short response | Pass | one chunk then `done`: `writing` then Answer ready |
| 7 | Invalid symbol request | **Blocked** | the answer's handling of an unknown ticker is the model's, and the key is refused |
| 8 | Missing market data | Partial | the frontend half is verified (a lookup that returns nothing is not counted, below); the answer's wording about what is missing needs the model |
| 9 | Provider timeout | Partial | a stream that goes silent is verified: after 30 s the panel showed "No reply from the server for 30 seconds. You can keep waiting or stop the answer." and the state held at Thinking without inventing progress. A timeout that ends in a server `error` event is covered by the error run. A genuine upstream timeout was not reproduced |
| 10 | Tool failure | Pass | `retrieved [{label: 'NVDA quote', ok: false}]` then a model round left the state at **Thinking**, with no tick and no "Looked up so far" line. A failed lookup is never shown as evidence |
| 11 | Cancel during Thinking | Pass | row removed, no Answer ready, note "Stopped before Milo answered.", not busy, 0 bubbles |
| 12 | Cancel during Researching | Pass | exchange dropped, "Stopped before Milo answered.", no Answer ready |
| 13 | Cancel during Writing | Pass | partial answer kept, "Stopped by you. This answer is incomplete.", no Answer ready |
| 14 | Close chat during streaming | Pass | text kept arriving while closed; on reopen both sentences were there and the row was still `writing` |
| 15 | Start New Chat | Pass | refused with a toast while an answer was in flight; with nothing in flight it cleared the log (0 bubbles, empty state) and left no activity row |
| 16 | Restore previous conversation | Pass | 3 history rows; reopening one drew 4 bubbles, no activity row, not busy. A finished answer from an old chat does not animate |
| 17 | Switch ticker during processing | Pass | navigated to `#/AMD` mid-answer: the answer kept streaming, the row stayed `writing`, text intact |
| 18 | Rapid consecutive questions | Pass | a second send during an answer was refused; message count unchanged (2 before, 2 after) |
| 19 | Slow network | Partial | the silence case is verified as in #9. Real bandwidth throttling was not applied |
| 20 | Mobile viewport | Pass | 375 x 812: compact row 343 x 44, "Researching / Checking NVDA's quote", no horizontal overflow, the answer area is not pushed below a large character |
| 21 | Reduced-motion settings | Pass (one of two triggers executed) | with `data-motion="reduce"`: zero elements in the card report an `animation-name`, the prop holds its finished shape, dots at .5 opacity, heading and line still correct and still changing. The `prefers-reduced-motion` media query carries the identical rules in the same block and is asserted by `test_reduce_motion_stops_every_animation_in_one_place`, but was not emulated in the browser |
| 22 | Keyboard-only navigation | Pass | 0 focusable elements inside the activity row while an answer was live; `role="status"`, no `tabindex`; Stop and the composer both reachable; props `aria-hidden` |
| 23 | Browser refresh | Pass | refreshed mid-answer: no activity row survived, nothing stuck busy. The interrupted exchange itself is not restored, because history is written when an answer finishes (`milo.js:1061`). That is pre-existing behaviour and unchanged by this work |
| 24 | Interrupted stream | Pass | connection closed with no `done`: the partial answer was kept, "The connection ended before Milo finished. This answer is incomplete." was shown, no Answer ready, not busy |
| 25 | Long conversation history | Pass | 48 messages restored and a live answer streamed on top: no activity row from the restored messages, no horizontal overflow, the answer behaved normally |

## The per-test checks the brief asked for

| Check | Result |
| --- | --- |
| Correct character state | verified in every run above by reading `data-doing` and `data-scout` |
| Correct status text | the server's own words win where it sends them ("Checking NVDA's options data"), the state's default line otherwise |
| Correct event transitions | the sequences above, plus 18 automated cases in `tests/test_milo_activity.py` |
| No stale conversation state | #14, #15, #16, #17, #23, #25 |
| No duplicate messages | #18 (count unchanged), #11 (0 bubbles after a cancel with no text) |
| No fabricated activity | #1 (no Researching without a lookup), #10 (a failed lookup is not evidence), and there is no percentage, step count or time estimate anywhere in the feature |
| No broken streaming | #5, #14, #17, #24 |
| No unnecessary delays | the finished answer, its sources, actions and follow-ups are drawn in the same frame as `done`; only the row retires, 1.6 s later |
| No layout overflow | checked at 375, 444, 560 and 1440; card height identical (141 px) across all four working states |
| No console errors | `read_console_messages` with `onlyErrors`: none, across the whole session |
| Correct final response behaviour | #6, #13, #24, and Answer ready shown only for an answer that landed |

## Screenshots captured

Thinking card (thought-bubble prop, with the 30-second quiet notice beneath it); Researching card (laptop and
books prop, "Checking NVDA's options data"); Analyzing card (tablet prop, two gold ticks naming the two
lookups that returned); Writing compact row with the answer above it and "Looked up so far" beneath; Answer
ready row with the answer's actions already drawn beside it; the phone view at 375 x 812. They are attached to
the session rather than committed, since `docs/` holds no binaries.

## The rendered poses (2026-11-03, second pass)

The three worked poses were placeholders in the first pass: the standing Milo plus a gold line drawing. They
are now rendered frames of the character himself. Re-checked after the render:

| Check | Result |
| --- | --- |
| The sheet | 35 frames, `scout-full@3x.webp` 10080 x 380 and `scout-compact@3x.webp` 5040 x 156, both exactly `frame x 35` |
| The standing frames | unchanged: `props()` builds nothing for a pose with no prop, so those 22 march the scene they always did |
| Researching | card at a 560 px panel: frame `desk`, no drawn prop, Milo at the table with the laptop, its gold aperture and the two books |
| Analyzing | frame `tablet`, the gold chart on the glass, the two ticks naming the lookups that returned |
| Writing | collapses to the inline row as text arrives, frame `write` |
| Answer ready | frame `idle` with the `ack` wave, prop `done` (the sparkles) |
| Card height | 167 px, identical across all four working states: no layout shift |
| Phone, 375 x 812 | inline row 44 px with the `desk` bust, no horizontal overflow |
| At the inline size | all three worked busts were rendered down to 34 px and inspected: the laptop, the tablet's gold chart and the notebook with its pencil each stay legible and distinct |
| Still motion | `OpticScout.setMotion('still')` holds frame `desk` and the heading Researching: the pose stays, only the movement goes |
| Reduce motion | with `data-motion="reduce"`, zero elements in the card report an `animation-name` |
| CSS frame count | `background-size: 3500% 100%` live in the panel, `frames.json` 35: the two agree, which is what the clipped figure in the first reload was about |
| Console | no errors |
| Rebase | rebased onto `origin/main` `5bcf5972` before shipping; no file overlapped that commit, so nothing was resolved by hand |

## Remaining defects and gaps

1. **The figure is cut off until the page is reloaded.** Changing the frame count changes
   `background-size` in CSS and the sheet at the same time; a tab still running the old stylesheet against
   the new sheet slices him wrong. It fixes itself on reload and matters only to someone holding the app
   open across this deploy, but it is the reason a staging check should start with a hard reload.
2. **No answer-level verification.** Scenarios 3, 4, 7 and 8 need a working model key. Nothing in this stage
   changes what Milo says, but that is an assertion from the diff, not a measurement.
3. **`prefers-reduced-motion` not emulated**, only Optic's own `data-motion="reduce"`. Same CSS block, same
   rules.
4. **Real network throttling not applied** (#19). Only the silence case was exercised.
5. The panel's tab order reaches Stop at position 131 of 133 in a long conversation. That is the panel's
   existing structure, not something this feature introduced, and it is worth its own look.
