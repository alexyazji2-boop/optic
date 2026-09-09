# Optic Terminal

A market research web app. FastAPI + vanilla JS/SVG. **No framework, no build step** —
`static/` is served as-is, so there is nothing to compile and no bundler to configure.

Live at https://theopticterminal.com (Railway, auto-deploys from `main`).

## Running it

```bash
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Tests: `.venv/bin/python -m pytest -q`. There are 1097 and they all pass; keep it that way.

A development account: `.venv/bin/python -m app.seed`. It prints a generated password
once and refuses to run when a hosting platform is in the environment.

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

**"Session" means two different things.** `app/session.py` is about the *market*
session (which trading phase is open). `app/auth/` is about a *sign-in* session. They
share a word and nothing else; a function that says "session" has to say which.

**Accounts are additive and nothing gates the terminal.** Every research endpoint
answers a guest exactly as it did before accounts existed, and that is a requirement,
not a current state of affairs. What an account changes is where the watchlist and
saved research are *kept*. `tests/test_auth_authorization.py` asserts the open
surface stays open, and it is the test that will catch somebody wrapping the wrong
router in a login check.

**Admin is one boolean from the environment, and the second half of it is the
security.** `ADMIN_EMAILS` names who owns the deployment, and `app/auth/admin.py`
requires the account to have *confirmed* that address as well as be listed.
Without the `email_verified` half this would be escalation by registration:
anyone may type any address into the signup form, so the first stranger to sign
up as the owner would be the owner. It is not a column on `users` on purpose, so
a restored backup or a stray UPDATE cannot mint one. Unset, nothing changes and
`OPTIC_WRITE_TOKEN` stays the only way past `_write_guard`.

**The admin branch of `_write_guard` is authorised by a cookie, so it pairs with
`csrf_guard`.** The token branch never needed it: a header an attacker cannot
read is itself the proof. A cookie is sent by the browser whether or not the
reader meant it, and SameSite=Lax is the browser's promise rather than ours.

**Reading source text to prove a control-flow property is a bad test.** One here
grepped `_spend_guard` for a `return` inside the admin branch and passed for the
wrong reason: the word appeared in that branch's own comment. It drives
`_spend_guard` directly now. Same lesson as the two mutation escapes below.

**`PRAGMA foreign_keys=ON` is per connection.** SQLite ships it off. Without it every
`ON DELETE CASCADE` in `app/db.py` is decoration and an orphaned session row still
authenticates. `app/db.py:_connect()` sets it; a second connection helper anywhere
else must too.

**Saved research is at `/api/saved-research`.** `/api/research` was already taken by
the streaming deep-research endpoint in `app/main.py`, which is registered first and
wins. Sharing the path left GET working and POST quietly running a web search.
`tests/test_account_data.py` has a route-collision test that reads main.py's
decorators, because comparing router paths on the running app cannot see a collision
at all: the two entries are the same string.

**An author `display` beats the UA stylesheet's `[hidden] { display: none }`** whatever
the specificity. `.set-pw` set `display: flex` and the password form rendered open on
every visit to Settings. Any rule that gives an element a `display` needs a
`[hidden]` pair beside it.

**`flex-basis` means width in a row and height in a column.** `.settings-select`
carries `flex: 0 1 340px` for the Settings page's row layout. Reused inside a
`flex-direction: column` label, that 340px became the *height* and every input in the
watch builder rendered 340px tall. A control class written for one axis is not
reusable on the other.

**A parameter compared as a string needs its vocabulary written down.** Three watch
conditions shipped comparing a stored parameter against a value produced elsewhere in
the app: `direction` was matched against `up`/`down` where `app/analytics/earnings.py`
produces `rising`/`falling`, `side` read a `kind` field where the provider writes
`action`, and `to` exact-matched a stance where "bullish" has to include "leaning
bullish". All three stored fine, evaluated fine and never fired — and "did not fire" is
also the correct answer most of the time, so nothing looked broken. `CONDITIONS[*]
.param.choices` is now the single source and the UI is generated from it.

**Every control needs a handler, and every handler needs a control.** `data-ws-hide`
was markup with nothing behind it, and three `askPulse()` topics were asked for and
never defined, so `openPulseWith` returned early and the button did nothing. Both
directions are asserted now (`tests/test_auth_client.py`). A dead control does not
error; it takes the click and nothing happens, which reads as a slow app.

**`sliceSeries` on an intraday range returns everything.** `spec.daily` is undefined
on an intraday spec, `Math.min(undefined, total)` is NaN, and `arr.slice(NaN)` is
`slice(0)`. The 1D and 5D pills on the Charting tab drew the full daily history for
months. Intraday now comes from `/api/intraday` via `wsIntraday`, and drawings are
hidden on it because a stored bar index means a different moment on a five-minute
series.

**The assistant must survive the accounts database being gone.** `_spend_guard` reads
the daily allowance out of SQLite and catches `(sqlite3.Error, OSError)` — OSError as
well, because opening the database creates its directory first and an unmounted volume
raises from `os.makedirs`. Catching only the sqlite family left a 500 on `/api/chat`.

**Two market session models.** `app/session.py` is authoritative and models the ten NYSE
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

`ADMIN_EMAILS` is what makes an account the owner. The address has to be
confirmed before it counts, and with no SMTP configured the confirmation link is
written to the server log (`[mail:log]`) rather than emailed.

`APP_URL` must be set once a custom domain is attached. The OAuth redirect URIs, the
WebAuthn RP id and the links inside verification emails are all derived from it, and it
is configuration rather than a read of the Host header because a Host header is
attacker-controlled: a reset link built from one can be aimed at another site.

`.env.example` lists every variable and what each one adds. The app runs with none of
them set.

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
