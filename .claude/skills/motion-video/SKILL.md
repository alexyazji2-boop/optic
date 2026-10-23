---
name: motion-video
description: Make a motion-graphics video (product promo, launch reel, explainer, animated UI demo, social clip) as code: a deterministic HTML page paints every frame, headless Chromium via Playwright screenshots each one, ffmpeg stitches them into an MP4 with synthesized, beat-locked audio, and Claude watches its own frames, hunts dead frames and re-renders until every scene scores at least 8/10. Use whenever someone asks for a motion design video, animated promo, MP4 of an animation, a "make this UI move" reel, or anything that ends in a rendered video file, even if they never say "render loop". Covers Optic Terminal promos and social clips too, built from Optic's real mark, Milo sprites and captured screens.
---

# Motion video studio

Claude does not make a video. It writes code that paints every single frame, a
browser captures each frame, and ffmpeg stitches them. The studio is set up once
and reused for every video:

```
scene.html  ── window.renderFrame(f) paints frame f, no clocks, no CSS transitions
   │
render.mjs  ── Playwright: for f in 0..N: evaluate(renderFrame(f)); screenshot
   │
frames/f_0000.png …  ──  dead_frames.mjs  ── per-scene motion score, dead runs
   │                         │
   │                    contact sheets → Claude grades each scene /10
   │                         │  < 8 → fix the scene, re-render only its frames
audio.mjs ── synthesized WAV, every hit on the beat grid
   │
ffmpeg ── frames + audio → out.mp4
```

Source: workflow from a @ray_fu TikTok, "How to do motion design with Claude
Opus 5.5" (saved 2026-10-23). His step-by-step guide was gated behind a comment,
so everything below the five steps is filled in here, not taken from him.

## The five steps

1. **Build the headless render-engine loop first** (node, ffmpeg, Playwright).
   The page exposes `window.renderFrame(frame)`; nothing reads `Date.now()`,
   `performance.now()` or `requestAnimationFrame`. Every pixel is a pure function
   of the frame number, so any frame can be re-rendered alone and two renders are
   identical.
2. **Give it real references and real assets.** Left alone, Claude defaults to
   all-caps centered text on a gradient, which looks like AI slop. Before
   writing a scene, collect the actual logo, screenshots, product UI, fonts and
   brand colors (ask for them, or pull them from the codebase), plus one or two
   reference videos/stills of the look wanted. Compose with those.
3. **Enforce real spring physics. Ban basic CSS motion.** No `transition`, no
   `animation`/`@keyframes`, no `ease`/`ease-in-out` cubic-beziers. All motion
   comes from the closed-form springs in `scripts/lib.js` (`spring`, `springTo`)
   evaluated at `t = frame / fps`. Overshoot, settle and stagger are what make UI
   look good.
4. **Synthesize the sound in code and lock every cut to the beat.** Pick a BPM
   and a cut length in beats (e.g. 120 BPM, cut every 2 beats = 1 s = 30 frames
   at 30 fps). Scene boundaries, big entrances and every audio hit sit on
   `beatFrame()`. `audio.mjs` renders the track from the same cue list, so
   off-beat is 0 ms by construction.
5. **Self-critique loop, the real secret.** Claude watches its own frames and
   grades them. Hunt dead frames (nothing on screen moves), re-render, repeat
   until every scene is at least 8/10. Report the grades.

## Setup (once per project)

```bash
mkdir -p video && cd video
cp ~/.claude/skills/motion-video/template/scene.html ~/.claude/skills/motion-video/scripts/* .
npm init -y >/dev/null && npm i -D playwright && npx playwright install chromium
```

`ffmpeg` must be on PATH (`brew install ffmpeg`). The npm step is optional on
this Mac: `render.mjs` falls back to the Playwright copy in the npx cache, and
to the installed Google Chrome when Playwright's own browser isn't downloaded.
Keep `lib.js` next to the scene; the page loads it with `<script src="lib.js">`.

## Writing a scene

Start from `template/scene.html`. Its contract:

- `window.VIDEO = { width, height, fps, frames, bpm, beatsPerCut }`.
- `window.SCENES = [{ name, start, end }]` in frames, boundaries on the beat grid.
- `window.CUES = [{ frame, sound, gain? }]`: audio hits (`kick`, `tick`,
  `whoosh`, `riser`, `pop`, `bass`); `audio.mjs` reads these.
- `window.renderFrame(f)` sets every animated property for frame `f` and returns
  (or returns a Promise once images/fonts are ready). It must be idempotent and
  order-independent: rendering frame 200 cold gives the same pixels as after 199.

Rules for the look:

- Real assets in `assets/`, loaded and awaited (`document.fonts.ready`,
  `img.decode()`) before frame 0.
- Type with hierarchy: a real typeface, mixed case, tracking tuned per size. No
  default all-caps centered headline on a gradient unless the brand calls for it.
- Something moves in every frame of every scene: a slow drift, parallax, a
  cursor, a number ticking, a settling spring. Holding a still frame longer than
  ~0.3 s reads as dead.
- Stagger entrances by 2-4 frames; give heavier elements lower stiffness.
- Transforms and opacity only where possible; canvas for particles and charts.

## Render

```bash
node render.mjs scene.html --workers 4     # all frames → frames/, then out.mp4
node render.mjs scene.html --from 60 --to 119   # re-render one scene only
node render.mjs scene.html --scale 0.5     # fast draft
```

`render.mjs` refuses to run if any element has a CSS `transition` or
`animation` (that's the "ban basic CSS" rule, enforced; `--allow-css` overrides).
It writes `video.json` (VIDEO, SCENES, CUES, read by the other scripts),
`frames/f_%04d.png`, then `audio.wav` from `CUES`, and muxes `out.mp4` (H.264,
yuv420p, AAC) once every frame exists. `--workers 4` renders in parallel pages
(the 10 s 1080p template takes ~40 s). `--no-audio` or `--no-video` skip steps.

## Critique loop

```bash
node dead_frames.mjs                       # per-scene dead runs + motion curve; exit 1 on FAIL
node contact_sheet.mjs                     # sheets/NN-<scene>_PP.jpg, 1 tile per 3 frames, 6x6 max
```

`dead_frames.mjs` diffs consecutive frames with ffmpeg. A frame is dead when no
pixel changed by more than 3/255 (`--max-delta`); a scene FAILs when a dead run
is longer than ~0.3 s. It writes `critique/dead_frames.json`. A drifting
background counts as motion to the script, so also judge from the sheets
whether the subject itself goes still. Then read every `sheets/*.jpg` (tiles
run left to right, top to bottom, every 3rd frame from the scene start) and
grade each scene /10 on:

| Criterion | What an 8 looks like |
|---|---|
| Motion | No dead run > 9 frames; movement through the whole scene |
| Physics | Springs overshoot and settle; nothing linear or eased-CSS |
| Composition | Real assets, clear focal point, safe margins, no slop layout |
| Type | Legible at phone size, hierarchy, no orphans or clipping |
| Rhythm | Cut and big hits on the beat; entrances staggered |

Write the grades as a table (`Scene 2 is 2/10: 21 dead frames (f0-f29),
nothing moves after the title lands`), fix every scene under 8, re-render only
its frame range, and rerun both scripts. Loop until every scene is 8+, at most
three passes; if a scene still fails, say which and why rather than inflating
the grade. Finish by sending the MP4 and the final grade table.

## Optic Terminal videos

For Optic (theopticterminal.com), start from `template/optic.html`: a 12 s,
5-scene promo (the mark drawing itself, a headline, a real captured chart with a
camera push to two focus points, Milo waving, the end card). It is built only
from the brand's own assets. The owner's frontend rules hold in video too (the
`optic-frontend` skill has them all):

- **No invented figures.** Every number on screen comes from a captured Optic
  screen, and the caption says what it is and when ("SPY, 1 hour chart, at the
  close on Fri Oct 23, 2026"). Re-capture rather than edit a figure. Never imply
  advice; the end card keeps "Research, not financial advice."
- **The look:** charcoal tokens, gold only for the mark, focus, Milo and chart
  data. No glows, gradients, purple, emoji or sparkle icons, and no em dashes in
  copy. Inter and Space Grotesk only (the app's jsDelivr packages, families
  "Inter Variable" and "Space Grotesk Variable"), weights 400 to 600. Navigation
  names exactly as the app shows them.
- **Where to work:** `~/Optic/work/video-<name>/`, outside the repo: frames are
  large and the repo is public.

Setup from the repo root (`~/Optic/options-terminal`, or a worktree of it):

```bash
V=~/Optic/work/video-promo && mkdir -p $V/assets
cp .claude/skills/motion-video/template/optic.html .claude/skills/motion-video/scripts/* $V/
cp static/scout/scout-full@3x.webp static/scout/scout-full-tail@3x.webp $V/assets/
```

Real screens come from a **local server run from a worktree with no `.env`**,
so no page can call a paid model, with `WATCH_AUTO=false`. Never capture the
live site: the browser pane is signed in as the owner, and some views (the Read,
a Dossier's Earnings tab) can spend credit on a cache miss. Then:

```bash
node capture.mjs "http://127.0.0.1:<port>/#/SPY/chart" $V/assets/chart.png \
  --storage '{"optic.theme":"dark"}' --until-gone "Loading" --wait 3000
```

`--storage` is needed because headless Chromium reports a light colour scheme;
the chart can take a minute on a cold server, which `--until-gone` waits out.
After a new capture, re-measure `FOCUS` in `optic.html` (CSS pixels of the
1600 x 1000 capture: look at the PNG, divide its pixel positions by 2). Milo's
poses are indexed in the order of `static/scout/frames.json` (22 poses, 12
scarf frames); `POSE` names the ones the template uses.

## Files

- `scripts/render.mjs`: Playwright frame loop, CSS-motion ban, ffmpeg stitch and mux.
- `scripts/audio.mjs`: WAV synthesizer from `CUES` (no samples, no dependencies).
- `scripts/dead_frames.mjs`: ffmpeg frame diff, per-scene dead-frame report.
- `scripts/contact_sheet.mjs`: per-scene contact sheets for Claude to read.
- `scripts/capture.mjs`: screenshot a real page into `assets/` (`--storage`,
  `--until-gone`, `--hide`, `--theme`).
- `scripts/pw.mjs`: finds Playwright and a browser for the two scripts above.
- `scripts/lib.js`: closed-form springs (`spring`, `springTo`, `settleTime`,
  named `SPRINGS`), beat grid (`beatFrame`, `scenes`), `since`, seeded `rng`.
- `template/scene.html`: a generic 10 s, 4-scene starter (mark, headline,
  product card with count-up and a cursor click on the beat, end card). Its
  brand is a placeholder; swap in real assets first.
- `template/optic.html`: the Optic starter described above.
