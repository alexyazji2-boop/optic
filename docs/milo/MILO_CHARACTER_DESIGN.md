# Milo, the character

How Milo is drawn in the v2 panel, which poses the activity states use, where every asset comes from, and
what is still missing. Written 2026-11-03 on branch `milo-animation`.

## 1. He is one character, already rendered

Milo is the figure the classic app has always used. He is not drawn in CSS or SVG anywhere in Optic and must
never be: every picture of him comes from the same rendered sprite sheets.

| Piece | Path | What it is |
| --- | --- | --- |
| Driver | `static/components/scout.js` | `window.OpticScout`: poses, gestures, blinks, motion setting, sprite positioning |
| Sheets | `static/scout/scout-{full,compact}@{2,3}x.webp` | 38 frames across one row, plus `-tail` sheets |
| Frame map | `static/scout/frames.json` | frame order and the per-frame pixel size of each sheet |
| Renderer | `optic-brand/scout/render_scout.py` | the numpy SDF raymarcher the sheets are rendered from |
| Loaded by | `static/v2/index.html:38` | a plain script tag, before the app |

Identity, fixed by the render and not by code: white rounded snowman body, gold glasses whose lenses carry the
chart symbol, gold scarf, small smile, soft 3D shading, minimal face. Optic black and gold around him.

Per-frame size: full `288x380` at 3x (`192x253` at 2x), compact `144x156` at 3x (`96x104` at 2x). 22 frames,
one row, positioned with `--scout-x`.

### The 38 frames

Standing, as they always were: `idle`, `idle-half`, `idle-closed`, `lean`, `tilt`, `tilt-half`,
`tilt-closed`, `curious`, `curious-half`, `curious-closed`, `arm-1`, `arm-2`, `arm-3`, `look-l1`, `look-l2`,
`look-r1`, `look-r2`, `nod-1`, `nod-2`, `concerned`, `concerned-half`, `concerned-closed`.

Added 2026-11-03 for the activity states, appended and never inserted: `desk`, `desk-half`, `desk-closed`,
`desk-type`, `tablet`, `tablet-half`, `tablet-closed`, `tablet-near`, `write`, `write-half`, `write-closed`,
`write-1`, `write-2`.

Added the same day, after the owner said the wave read as a twitch: `arm-a`, `arm-b`, `arm-c`, the in-between
arm positions at 15, 47 and 82 degrees. With only `arm-1`, `arm-2` and `arm-3` the wave crossed 35 degrees in
60 ms (about 580 deg/s) with nothing between, and the hand jumped roughly 18 px across and 36 px up at the
welcome size. Every step is now about 17 degrees over 50 ms, near 300 deg/s. The `wave`, `ack` and `point`
gestures in `scout.js` all use them.

Each resting pose carries its own half-closed and closed lid, so a blink never changes the pose it happens
in, and the three new ones are no exception. A pose change walks the ladder `idle -> lean -> tilt -> curious`
rather than jumping; the worked poses sit outside that ladder (they are scenes, not head angles), so moving
to one is a cut.

### Poses and gestures the driver has

Poses (`POSE` in scout.js): `idle`->idle, `listening`->tilt, `thinking`->tilt, `searching`->tilt,
`streaming`->idle, `error`->concerned, `researching`->desk, `analyzing`->tablet, `writing`->write.
Gestures (`GESTURE`): `wave`, `ack`, `nod`, `look`, `curious`, `point`, `bob`, and for the worked poses
`type`, `read`, `pen`.

## 2. What each activity state uses

| State | Pose | What is in the frame | Heading / line |
| --- | --- | --- | --- |
| Thinking | `thinking` -> tilt | a drawn thought bubble with the logo's chart line | Thinking / "Understanding your question" |
| Researching | `researching` -> desk | at the table: a dark laptop with the gold aperture on its lid, two books with gold bands, hands on the keys (`desk-type` loops the typing) | Researching / the tool's own words, else "Looking through Optic's data" |
| Analyzing | `analyzing` -> tablet | a dark tablet held in both hands with the gold chart on the glass (`tablet-near` tips his head toward it) | Analyzing / "Connecting what came back" |
| Writing | `writing` -> write | at the table: an open notebook with a dark cover, written lines, a gold pencil in his hand and a cup (`write-1`, `write-2` move the pencil, and the third line grows) | Writing / "Putting it together" |
| Answer ready | `idle` plus the `ack` gesture, played once | three drawn sparkles | Answer ready / "Here's what I found" |
| Error | `error` -> concerned | nothing | No answer / "Milo could not finish this one" |
| Cancelled | `idle` | nothing | Stopped / "Stopped by you" |

Two drawings remain, in `PROPS` in `static/v2/js/ui/milo-activity.js`: the thought bubble and the sparkles,
neither of which is a pose he has. The desk, the tablet and the notebook used to be drawn there too and are
not any more: a drawn laptop beside a rendered one was two laptops.

## 3. How the three worked poses were built

The renderer is a signed-distance scene ray-marched in numpy, so a new pose is new geometry, not a new
drawing. `props(p, P)` in `render_scout.py` builds one of three scenes when a pose asks for one, and nothing
at all when it does not, so the 22 standing frames march exactly the scene they always did.

Two things shaped the result:

**The camera is almost level with him**, at `[0.10, 1.75, 14.0]`, and every frame has to share it. Anything
lying flat on a desk is foreshortened to a few pixels and simply disappears: the first attempt put an open
notebook on the desk and rendered a desk with nothing on it. Everything therefore stands up. The laptop is
read from the back of its lid, the books are a stack that rises above the table, the tablet is tipped toward
the viewer, and the notebook is propped against the table rather than lying open on it.

**The sprite has a transparent background.** A desk running off both edges of the frame reads as a black bar
rather than as furniture, so the desk is a narrow table, 2.1 units wide, with both ends and both legs in
frame.

Materials added to the shader: 8 shell (laptop, tablet, cup), 9 desk, 10 paper, 11 book cloth, 12 legs. They
are lit by the same key, fill, sky, shadow and occlusion as he is, so they sit in his world rather than being
pasted onto it.

Three things had to be true and are checked in the renders:

1. **The scarf stays visible.** It is one of the features that make him him, so the laptop lid and the
   notebook both stop below it. The first pass had the lid crossing the scarf.
2. **The hands read as holding something.** His hands are mitts: the first pencil was a realistic length and
   vanished inside one, so the pencil now runs well past his hand at both ends.
3. **The props read at card size.** The figure is 104 CSS px wide in the card, which is 36% of the 3x frame.
   The gold aperture, the gold book bands, the chart on the glass and the pencil are what carry each scene at
   that size; everything smaller was removed.

### If a fourth pose is ever wanted

Follow the same path. Add frames to the **end** of `FRAMES` in `render_scout.py`, give the resting pose its
own `-half` and `-closed` lids, add the names to `FRAME` in `scout.js` with their indices, raise `COUNT`, add
a `FACE` entry, add a `POSE` name, and leave `LEVEL` alone so the change is a cut. Then re-render, and update
the two places in CSS that carry the frame count: `background-size: 3800% 100%` (in `static/styles.css` and
`static/v2/css/components.css`) and the per-frame step in `@keyframes scout-badge-blink`, which is
`100 / (frames - 1)` per frame. `tests/test_pulse_scout.py` checks all of that against `frames.json`.

## 4. Consistency rules

1. Never draw Milo. Every picture of him is `OpticScout.html(...)` over the rendered sheets.
2. Never recolor him, never change his face, never swap in another snowman.
3. Props are beside him, in `--c-gold`, line work only, `aria-hidden`, and never overlap his face.
4. One figure per context. The panel header bust, the empty state and the activity figure each take their own
   slot (`O.attach(el, { slot })`) so one never stops another's gesture.
5. The full sheet is already fetched by the panel's empty state (`milo.js:320`), so the activity card adds no
   request to the panel. The sheet itself grew with the thirteen new frames, which is the one real cost:
   `scout-full@3x.webp` and `scout-compact@3x.webp` are both larger than before.
6. Reduce motion stops the drawn props and the dots, and holds the figure still, but **not** in the plain
   standing pose: `Ctl.prototype.pose` keeps a worked pose at Still motion, because what he is working with
   is the state itself and not decoration. Researching still shows him at the desk, just not typing. His
   motion setting (Full / Subtle / Still) in Response settings governs the movement, as it always did.
7. The frame count lives in four places and they should agree: `FRAMES` in the renderer, `frames` in
   `frames.json`, `FRAME` and `COUNT` in `scout.js`, and the fallback figures in `static/styles.css` and
   `static/v2/css/components.css`. Since 2026-11-03 a disagreement no longer breaks him: `scout.js` measures
   the sheet the browser actually loaded and publishes `--scout-frames` and `--scout-step` on `<html>`, which
   both stylesheets read, and it never asks for a frame past the end of that sheet. Keep the figures in step
   anyway, so a page whose script has not run still looks right.
