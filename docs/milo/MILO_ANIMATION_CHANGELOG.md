# Milo animation changelog

## 2026-11-03 — five activity states, from the server's own events

Branch `milo-animation`, cut from `origin/main` `1a1cf58b`. Commit `ba314e64`, plus this file.
Not pushed. Not deployed.

### What changed for a reader

While an answer is coming, the panel used to show one grey line of status text and a sliding bar. It now shows
Milo doing what he is actually doing, in five states: **Thinking**, **Researching**, **Analyzing**,
**Writing**, **Answer ready**, with **error** and **cancelled** behaviour of their own. The mascot is the one
the app already renders. Beside him is a gold line drawing of the thing he is using: a thought bubble, a
laptop with books, a tablet, a notebook and pencil, three sparkles at the end.

Which states appear depends on the work. A question answered with no lookup shows Thinking then Writing. A
question that needed a figure shows Researching, and lists what came back. A question whose lookup failed
shows neither Researching evidence nor Analyzing.

### Files

| File | Lines | What |
| --- | --- | --- |
| `static/v2/js/ui/milo-activity.js` | +191, new | the states, the pure reducer, the two views, the props, `syncActivity` |
| `static/v2/js/ui/milo.js` | +68 / -13 | the wiring: `act` on the live record, three event lines, `expandedNow`, `scoutInActivity`, Answer ready in `paintFinished`, `liveLinesHTML` split so the activity is patched and the rest is replaced |
| `static/v2/css/components.css` | +84 | `.milo-doing*`, the card, the props and their motion, one Reduce-motion block |
| `tests/test_milo_activity.py` | +180, new | 18 cases: the sequences, the source contracts, the name-collision guard, Reduce motion, the no-invented-progress rules |
| `tests/test_v2_milo_streaming.py` | +4 / -2 | two assertions quoted lines this change renames; they now quote the new ones and guard the same behaviour |
| `docs/milo/*.md` | +450, new | the five documents |

No dependency was added. No image was added. No backend file was touched.

### Defects found and fixed during the work

| Problem | Fix |
| --- | --- |
| `esc` imported from `core/dom.js`, which does not export it | import from `core/format.js` |
| `.milo-act` was already Milo's action cards, so the new row inherited their border, padding and background | renamed every class to `.milo-doing*`, and `data-act` to `data-doing` |
| The card threshold was measured on the bubble (403 px inside a 444 px panel), a number with no meaning | measure the panel; `CARD_MIN = 400`, and never on a phone |
| The prop collided with the heading | the figure took its own 132 px column, with the prop placed per prop via `:has()` |
| At 52 px a laptop with books read as one gold smudge | props enlarged to 56-72 px and redrawn with fewer parts |
| The thought bubble's tail was invisible (2 px stroked rings) | fill the tail circles instead of stroking them |
| The card flashed empty on every state change: the whole view was re-rendered, restarting the mascot's blink timer, reloading his sprite and re-running the 260 ms fade | `syncActivity` patches in place; the view is rebuilt only when it appears, goes or changes size. 8.1 µs against 127.3 µs |
| After patching, the mascot's pose stopped updating | call `scoutInActivity` on every paint, not only on a rebuild |

### Tests

Full suite: **8249 passed, 1 skipped**, 4 min 25 s (`WATCH_AUTO=false`, `options-terminal/.venv`).
New: 18 cases in `tests/test_milo_activity.py`.
Browser: 25 scenarios, recorded one by one in `MILO_VISUAL_QA.md`.

### Known gaps

1. Three of the five poses are placeholders: the standing Milo plus a prop, not Milo seated at a desk, holding
   a tablet, or writing. Exact specifications for rendering those are in `MILO_CHARACTER_DESIGN.md` section 3.
2. The app's Anthropic key is refused, so no real model answer was produced; scenarios 3, 4, 7 and 8 in the QA
   document are blocked or partial for that reason.
3. `prefers-reduced-motion` was not emulated in the browser; Optic's own `data-motion="reduce"` was, and both
   carry the identical rules in the same block.
