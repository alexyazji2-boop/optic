# Milo animation changelog

## 2026-11-03 (second pass) — the three worked poses, rendered

Commit `073315a1`. Not pushed, not deployed.

The placeholders are gone. Researching, Analyzing and Writing are now frames of the character himself.

Thirteen frames were added to the sprite sheet: `desk`, `desk-half`, `desk-closed`, `desk-type`, `tablet`,
`tablet-half`, `tablet-closed`, `tablet-near`, `write`, `write-half`, `write-closed`, `write-1`, `write-2`.
The sheet went from 22 frames to 35.

| File | What |
| --- | --- |
| `optic-brand/scout/render_scout.py` | `props(p, P)` builds one of three scenes; `sd_box`, `sd_capsule`, `sd_cyl`, `rot_x_at`, `poly2`; a left arm capsule when a prop moves that hand; materials 8-12 and their shading; the thirteen new `FRAMES` |
| `static/scout/*.webp`, `frames.json` | re-rendered, 35 frames each |
| `static/components/scout.js` | the new names in `FRAME`, `COUNT` 35, `FACE` entries so blinks work in every pose, `POSE` gains `researching`/`analyzing`/`writing`, the `type`/`read`/`pen` loops, and `pose()` keeps a worked pose at Still motion |
| `static/v2/js/ui/milo-activity.js` | the three states point at the new poses and carry no drawn prop; the desk, tablet and notebook SVGs removed |
| `static/v2/css/components.css` | `background-size: 3500%`, the blink keyframe step, the card figure 78 -> 104 px, the removed props' rules gone |
| `static/styles.css` | the same two sprite figures, for the classic app |
| `tests/test_milo_activity.py` | the props test became a check that what he works with is rendered and not drawn, plus the pose/frame contract |

What shaped the geometry, since none of it is obvious from the numbers:

- **The camera is almost level with him**, and every frame shares it. Anything lying flat is foreshortened to
  a few pixels: the first attempt put an open notebook on the desk and rendered a desk with nothing on it.
  Everything stands up instead.
- **The sprite has a transparent background**, so a desk running off both edges reads as a black bar. The
  desk is a narrow table with its ends and legs in frame.
- **His hands are mitts.** A pencil of realistic length vanished inside one; it now runs well past his hand
  at both ends.
- **The scarf stays visible.** The laptop lid and the notebook both stop below it.

Render: `--no-tail --no-hero`, 70 frames, about 11 minutes on this machine. The tail strips and the hero PNG
were not touched.

The 22 standing frames are geometrically identical (`props()` builds nothing without a prop), but the strip
had to be re-encoded to hold 35 frames, so their pixels are not bit-identical: compared against the committed
sheet, the mean channel difference across those 22 frames is 0.23 of 255, with isolated maxima around 35 on
the gold rims. That is WebP re-compression at the new width, not a change to the figure.

One consequence worth knowing: the frame count lives in the renderer, `frames.json`, `scout.js` and twice in
CSS. A tab holding the old stylesheet against the new sheet draws him clipped until it reloads.

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

1. (Closed by the second pass above: the three poses are rendered.)
2. The app's Anthropic key is refused, so no real model answer was produced; scenarios 3, 4, 7 and 8 in the QA
   document are blocked or partial for that reason.
3. `prefers-reduced-motion` was not emulated in the browser; Optic's own `data-motion="reduce"` was, and both
   carry the identical rules in the same block.
