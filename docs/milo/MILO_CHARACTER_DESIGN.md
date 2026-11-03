# Milo, the character

How Milo is drawn in the v2 panel, which poses the activity states use, where every asset comes from, and
what is still missing. Written 2026-11-03 on branch `milo-animation`.

## 1. He is one character, already rendered

Milo is the figure the classic app has always used. He is not drawn in CSS or SVG anywhere in Optic and must
never be: every picture of him comes from the same rendered sprite sheets.

| Piece | Path | What it is |
| --- | --- | --- |
| Driver | `static/components/scout.js` | `window.OpticScout`: poses, gestures, blinks, motion setting, sprite positioning |
| Sheets | `static/scout/scout-{full,compact}@{2,3}x.webp` | 22 frames across one row, plus `-tail` sheets |
| Frame map | `static/scout/frames.json` | frame order and the per-frame pixel size of each sheet |
| Renderer | `optic-brand/scout/render_scout.py` | the numpy SDF raymarcher the sheets are rendered from |
| Loaded by | `static/v2/index.html:38` | a plain script tag, before the app |

Identity, fixed by the render and not by code: white rounded snowman body, gold glasses whose lenses carry the
chart symbol, gold scarf, small smile, soft 3D shading, minimal face. Optic black and gold around him.

Per-frame size: full `288x380` at 3x (`192x253` at 2x), compact `144x156` at 3x (`96x104` at 2x). 22 frames,
one row, positioned with `--scout-x`.

### The 22 frames

`idle`, `idle-half`, `idle-closed`, `lean`, `tilt`, `tilt-half`, `tilt-closed`, `curious`, `curious-half`,
`curious-closed`, `arm-1`, `arm-2`, `arm-3`, `look-l1`, `look-l2`, `look-r1`, `look-r2`, `nod-1`, `nod-2`,
`concerned`, `concerned-half`, `concerned-closed`.

Each resting pose carries its own half-closed and closed lid, so a blink never changes the pose it happens in.
A pose change walks the ladder `idle -> lean -> tilt -> curious` rather than jumping.

### Poses and gestures the driver already has

Poses (`POSE` in scout.js): `idle`->idle, `listening`->tilt, `thinking`->tilt, `searching`->tilt,
`streaming`->idle, `error`->concerned.
Gestures (`GESTURE`): `wave`, `ack`, `nod`, `look`, `curious`, `point`, `bob`.

## 2. What each activity state uses today

The five states are built from the existing frames plus one gold line drawing beside him. The drawing is the
prop, never a second character.

| State | Pose (frames) | Prop beside him | Heading / line |
| --- | --- | --- | --- |
| Thinking | `thinking` -> `tilt` | thought bubble with the chart line drawing itself | Thinking / "Understanding your question" |
| Researching | `searching` -> `tilt`, `look` gesture available | laptop with the Optic aperture on the lid, two books, two cards coming and going | Researching / the tool's own words, else "Looking through Optic's data" |
| Analyzing | `thinking` -> `tilt` | tablet with a chart drawing itself and a three-row checklist | Analyzing / "Connecting what came back" |
| Writing | `streaming` -> `idle` | open notebook, three lines written in turn, pencil, cup | Writing / "Putting it together" |
| Answer ready | `idle` plus the `ack` gesture, played once | three sparkles, once | Answer ready / "Here's what I found" |
| Error | `error` -> `concerned` | none | No answer / "Milo could not finish this one" |
| Cancelled | `idle` | none | Stopped / "Stopped by you" |

The props live in `PROPS` in `static/v2/js/ui/milo-activity.js`: one inline SVG each, stroked in `--c-gold`,
`aria-hidden`, with the screen fills in `--c-gold-wash`. They are Optic's own line iconography, the same family
as the app's icons. No emoji and no stock art is used anywhere in this feature.

## 3. The gap, stated plainly

The brief asks for five rendered poses: Milo with a hand on his chin, Milo **sitting at a desk** at a laptop,
Milo **holding a tablet**, Milo **seated with a notebook and pencil**, and Milo waving.

Three of those do not exist. Nothing in `static/scout/` shows him seated, holding anything, or with furniture.
What shipped uses the pose he does have for each state and puts the desk, the tablet and the notebook beside
him as gold line drawings. That is a deliberate substitution, taken because the brief says to "define exact
asset specifications and use approved temporary placeholders rather than attempting to recreate a complex 3D
character from CSS alone". It is a placeholder, and it is the one thing in this stage that does not match the
reference sheet.

### Exact specification for the three missing poses

If the owner wants the rendered versions, these are the specifications. The renderer exists and works:
`optic-brand/scout/render_scout.py`, timed on this machine at about 45 s per full frame and 21 s per compact
frame, so a sheet of new frames is minutes of CPU, not a new pipeline.

Shared rules for every new frame:
- Same character solid, same materials, same gold (`#b0861b` family), same key light and soft shadow as the
  existing sheet. Render from the same scene file so the shading matches frame to frame.
- Transparent background, premultiplied alpha, WebP, at 2x and 3x.
- Same frame box as the sheet it joins. A seated or propped pose is wider than the standing one, so these
  frames need a **wider camera window**: widen the frame box for the whole sheet rather than cropping him,
  then update `frames.json` (`full`/`compact` sizes) and re-export every frame at the new box so one row stays
  one row.
- Append new frames to the end of the `frames` array. Never reorder: `FRAME` in scout.js is index-based and a
  reorder silently shifts every pose.

| New pose | Frames needed | Geometry | Used by |
| --- | --- | --- | --- |
| `desk` | `desk`, `desk-half`, `desk-closed`, `desk-type-1`, `desk-type-2` | Milo seated three-quarter at a dark desk, dark laptop lid toward the viewer carrying a small gold aperture mark, two stacked books at his left. Hands at the keyboard; `desk-type-1/2` move the hands about 4 px for a typing loop. Lid glow is baked into the render, not animated in CSS. | Researching |
| `tablet` | `tablet`, `tablet-half`, `tablet-closed`, `tablet-near` | Milo standing, head angled down toward a dark tablet held in both hands, gold chart on the glass. `tablet-near` tips the head a further 6 degrees toward it for the look-down beat. | Analyzing |
| `write` | `write`, `write-half`, `write-closed`, `write-1`, `write-2` | Milo seated at the same desk, open notebook, pencil in his right hand, small gold-rimmed cup at the right edge. `write-1/2` travel the pencil hand across about 10 px for the writing loop. | Writing |

Driver changes those frames would need, all in `static/components/scout.js`: add each name to `FRAME` with its
index, raise `COUNT`, add `FACE` entries so blinks work in the new resting poses, add `LEVEL` entries (seated
poses sit outside the upright/lean/tilt/curious ladder and should not be walked through it, so give them a
direct cut), and add `POSE` names `researching`, `analyzing`, `writing` pointing at them. The activity module
then only needs its `scout:` values changed in `ACTIVITY`; nothing else in the panel moves.

Until that is done the props stay. They are the substitute, they are labelled as such here, and the states
read correctly without them because the heading and the line carry the meaning.

## 4. Consistency rules

1. Never draw Milo. Every picture of him is `OpticScout.html(...)` over the rendered sheets.
2. Never recolor him, never change his face, never swap in another snowman.
3. Props are beside him, in `--c-gold`, line work only, `aria-hidden`, and never overlap his face.
4. One figure per context. The panel header bust, the empty state and the activity figure each take their own
   slot (`O.attach(el, { slot })`) so one never stops another's gesture.
5. The full sheet is already fetched by the panel's empty state (`milo.js:320`), so the activity card adds no
   image bytes to the panel.
6. Reduce motion stops the props and the dots; the character's own motion is governed by his existing motion
   setting (Full / Subtle / Still) in Response settings, which this feature did not change.
