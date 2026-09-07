# Optic Terminal

A market research web app. FastAPI + vanilla JS/SVG. **No framework, no build step** —
`static/` is served as-is, so there is nothing to compile and no bundler to configure.

Live at https://theopticterminal.com (Railway, auto-deploys from `main`).

## Running it

```bash
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Tests: `.venv/bin/python -m pytest -q`. There are 656 and they all pass; keep it that way.

There is **no JS test runner** in this project. Client-side behaviour is verified in a
real browser, and client-side *contracts* are asserted by reading `static/*.js` as text
from Python tests. See `tests/test_ui_refactor.py` and `tests/test_ema_clouds.py` for the
pattern — it exists because every silent client failure in this codebase has been a
wiring failure, not a logic one.

## House style

Comments explain **why**, and cite the measurement. "Widened from 130px: the placeholder
truncated to `TICKER OR COI`" is the register. A comment that states what the line does
is noise; a comment that records what went wrong when it was different is the reason
anyone can safely change it later.

**No em dashes in user-facing copy.** This was a deliberate pass over the whole terminal.
`app/ai.py`'s `FORMAT_PROMPT` also instructs Pulse not to use them.

Every panel states what it cannot tell you. A scan says what it did not search; a brief
says what window it covers. When an AI writer fails it returns
`{"available": False, "reason": ...}` — and callers must test `available is not True`,
not `if not brief:`, because a truthy failure dict sails straight past a falsy check.
That bug shipped once.

## Things that will bite you

**Two session models.** `app/session.py` is authoritative and models the ten NYSE
holidays and three early closes from the exchange's rules. `static/app.js` has its own
`marketSessionFromClock()` that knows only about weekends — it is a pre-load fallback
only. `marketSessionET()` defers to the server. Do not add calendar logic to the client;
that duplication is what made the app report a regular session on Labor Day.

**`STATE.ticker` and `STATE.chartSymbol` are independent.** The Analysis tab and the
Charting tab hold different symbols on purpose. Anything that reads "the current symbol"
must say which one it means. Getting this wrong renders one company's data under
another's name with total confidence.

**`aggregateWeekly()` builds a fresh object**, it does not spread the daily one. A field
you do not name is simply absent from a weekly series, and `values || []` turns that into
an empty array with no error — a legend entry and no line.

**`overflow: clip` on the root element breaks IntersectionObserver's implicit root**
app-wide. It lives on `main` for this reason. Relatedly, `overflow-x: hidden` on
html/body breaks `position: sticky`.

**A dead class inside `:not()` or `:has()` does not make a rule dead.** It makes that one
condition vacuously true and leaves the selector's subject live. A dead-code pass deleted
`.grid.c2 > .panel:not(:has(.chart-controls))` on those grounds once.

**CSS specificity:** `table.data td` (0,1,2) beats `.fx-detail td` (0,1,1). A declaration
on an element always beats an inherited value.

**Chart coordinate system.** `svg.chartFrame` carries `{margin, plotW, bars, indexAt}`.
Drawings store bar index + price, never pixels, so they survive a resize. The drawing
layer sits *over* the chart because the chart is rebuilt on every redraw.
`.ws-draw-svg { pointer-events: none }` is load-bearing — without it the overlay swallows
the crosshair, tooltip, hover and measure gestures.

**ResizeObserver always delivers an initial observation.** Recreating an observer with a
reset baseline is a self-sustaining loop; one ran at ~7Hz and destroyed the chart toolbar
between mousedown and mouseup, making every click a no-op.

## Design system

Tokens in `static/styles.css`. Use them; do not introduce hex values.

Spacing is a **4px grid** (`--space-0` through `--space-9`; `--space-0` is the one 2px
sub-grid step). Motion is `--dur-ui` / `--ease-ui` (120ms ease) and every hover state
transitions paint-level properties only — animating a layout property forces a
full-document reflow per frame.

**Colour carries meaning, not identity.** `--pos` / `--neg` are the directional pair used
by candles, volume bars, EMA clouds and every percentage. `--btn-primary` is the one blue
chosen for white text sitting *on* it; the eight `--s1`..`--s8` slots are chosen for
separation from each other and several fail as text. Measure contrast against the surface
the text actually sits on, not the plane behind it.

Breakpoints: 559 (phone), 620, 640, 720, 860, 900, 1080, 1280. `--topbar-h` is published
by a ResizeObserver because the bar is one, two or three rows depending on width.

The ban list, from an explicit audit: no gradient text, no glassmorphism without a
purpose, no cookie-cutter grid blocks, no placeholder copy. Claims must be checkable.

## Deploying

`./publish.sh` — runs tests, checks for secrets, commits, pushes, then waits for the live
commit SHA to match. `DEPLOY.md` has the detail.

`OPTIC_WRITE_TOKEN` must be set in Railway Variables or manual scans and alert-clearing
return 503. Scheduled scans are unaffected.

`.env` is gitignored and mode 600. `data/` and `.share/` are gitignored. Attachments are
never written to disk — base64 passes through to the API and is discarded.

## Discipline that has paid for itself

Dry-run every bulk text transformation before applying. A `src.replace()` over
implicitly-concatenated Python strings silently no-ops; a pass that reported "320 strings
rewritten" had left 344 untouched.

Verify a test catches the defect it names. Mutate the source, confirm the test fails, then
restore. Two tests in this repo passed their mutation on the first attempt — one matched a
shorter form of the same selector elsewhere in the file, one was defeated by Python
reusing stale `.pyc` when the mutation had the same byte length and the same-second mtime.

Measure rather than assert. Profile redraw counts, compute contrast ratios, drive real
mouse input, use `elementsFromPoint` to find the actual hit stack, block the network to
prove tests make no live calls.
