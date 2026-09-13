# Optic Terminal

A market research web app. FastAPI + vanilla JS/SVG. **No framework, no build step** —
`static/` is served as-is, so there is nothing to compile and no bundler to configure.

Live at https://theopticterminal.com (Railway, auto-deploys from `main`).

## Running it

```bash
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Tests: `.venv/bin/python -m pytest -q`. There are 1670 and they all pass; keep it that way.

A development account: `.venv/bin/python -m app.seed`. It prints a generated password
once and refuses to run when a hosting platform is in the environment.

`tests/test_js_parses.py` evaluates `charts.js` and `app.js` under macOS's
JavaScriptCore and asserts that the cross-panel functions exist. It skips where
`jsc` is absent. It exists because two edits to one region deleted `maLabel`
while twelve call sites kept referencing it, and nothing caught it: the file
parsed, the Python suite passed, and the only symptom was an empty chart legend.

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

**A `data-*` attribute is a namespace, and it is already crowded.** A colour
picker for the price mark shipped rendering `data-ws-color`, which the indicator
style editor had already claimed. Its handler sits earlier in the same click
listener, so it matched first, called `setOverlayStyle(undefined, ...)` — which
rejects an unknown id — and returned. Nothing threw, nothing was corrupted, the
menu closed and no colour changed: a dead control, from a name collision that no
tool reports. Grep for the attribute before inventing it. The price mark now
uses `data-ws-mark-*`.

**Colour cannot carry a meaning the number contradicts.** The home pulse strip
inverted VIX so a rising fear gauge painted red, and the comment claimed a
direction word carried the meaning alongside it. There was no word, so a reader
saw `+2.16%` in red, and red means *down* in every other percentage in this app.
It was reported as a rendering fault. Colouring by sign would only move the lie
the other way: green on a rising VIX says higher fear is good news. VIX and the
10Y now take no directional colour and say the reading in words, because neither
direction is good or bad on its own.

**`--pos`/`--neg` and the candle pair are not the same pair.** Candles have
always been `s3`/`s8` and the volume strip `pos`/`neg`. Anything that unifies
them restyles every chart in the app for readers who never asked. The chart
colour override passes the reader's choice to volume *only when they made one*.

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

**The Charting tab and the Swing chart must agree, and four things made them
disagree.** They draw the same instrument from the same flags, so anything that
resolves *how* a series looks has to be one function called by both. What went
wrong: the five price-pane studies (Bollinger, Keltner, Donchian, regression,
VWAP) drew only on Swing and were absent from the tab whose job is charting; the
Swing tab substituted a hardcoded `s1/s2/s4` for the SMAs in candle mode, so the
same SMA 20 was a different colour on each tab and a colour chosen in the
indicator dialog was honoured on one and dropped on the other; the study palette
was seeded from different sets, so `allocateOverlayColors` gave one study two
colours; and the labels disagreed, with `200-day SMA` hardcoded on a chart that
has a Weekly pill. `maColorsOnChart`, `chartBaseColors` and `maLabel` are now the
single answers, and `tests/test_indicator_parity.py` holds them there.

**Defaults yield to choices; choices yield to nothing; defaults do not push each
other.** That is the whole rule in `maColorsOnChart`, and three versions of it
were wrong: one added every resolved colour to the taken pile, so choosing SMA
50's colour silently recoloured two other averages; one compared defaults only
against the candle pair, leaving a chosen colour and a default drawn alike; one
let a displaced average squat on a colour a later average was keeping.

**`STATE.indicators` belongs to the Analysis tab.** It is keyed on
`STATE.ticker`. The Charting tab has `wsIndicators`, keyed on
`STATE.chartSymbol`, because drawing the former on the latter puts one company's
bands over another company's candles and labels them correctly.

**The no-ticker guard in `switchView` is an allow-list by omission, so every
new view is ticker-specific by default.** Add a view that is not about one
loaded symbol and it renders "No ticker loaded" instead of itself: the loader
runs, the requests never fire, and it looks like the render failed. Watchlist,
Alerts and now Explore have each been caught. A new non-ticker view has to join
that array in the same commit.

**A new view needs registering in five places.** The section in `index.html`,
the `views` map, `NAV_GROUPS`, the `switchView` loader dispatch, and
`PALETTE_PLACES`. Missing any one is a different broken symptom, which is why
`tests/test_explore.py` asserts all five.

**The composite score is measured to be decoration, and three places now
depend on that.** `/api/evaluate` reports it "does not beat a single raw
momentum number at 3 of 3 horizons... the weights are decoration rather than
signal". So: the stance panel has no 0-100 headline, "what changed" does not
diff the score, and no Optic Score badge was added when a product brief asked
for one. What survives the finding is the stance, the conviction, and the
per-component bars with their real weights, all of which the app already shows.
A big number would be the most confident thing on the page and the least
supported.

**"What changed" snapshots on the client because the server keeps no per-symbol
state.** `/api/snapshots` is ledger backups. `snapshotOf()` stores seven
readings under the symbol on each ticker load, and the next visit diffs them.
Read the prior one *before* writing the new one or the diff is always empty.
Each field decides for itself whether it moved, so a reading absent on either
visit is skipped: "undefined became bullish" is not news.

**`:hover` is not an input method, it is a device capability.** The section
dropdowns opened on `:hover` and `:focus-within` only, and a phone has neither:
Safari does not focus a `<button>` when you tap it, so the caret pointed at a
menu that could not be opened at all. Worse, the tap ran `switchView`, which
replaces `nav.innerHTML` and destroys the element any transient hover was
sitting on. A tap now opens the menu instead of navigating, gated on
`(hover: none)` rather than on a width, because a 370px desktop window still has
a mouse and a landscape iPad is 1024px wide and still has none. The `:hover`
rules are inside `@media (hover: hover)` for the other half of it: unscoped,
a tap sets `:hover` and it sticks, so the menu drew over the page it had just
navigated to. Any new hover-revealed control needs all three routes.

**A phone override belongs after the rule it overrides.** `.hm-greet` is
defined near the bottom of `styles.css`, and a `@media (max-width: 719px)` block
placed up with the other phone rules set `display: none` on it and the greeting
stayed on screen: equal specificity, later source order wins. The command-centre
phone block sits at the end of the file for that reason.

**Four things are hidden on a phone and all four are duplicates.** The brand row
(the header says OPTIC TERMINAL), the greeting (the session block above says
REGULAR SESSION and the local time), the ticker pills, and the homepage search
form (the topbar carries `#ticker-input` with the same live results). Measured at
375x812: those plus the session legend were the difference between the day's
cross-asset moves being at y=839 on an 812px screen and at y=537.

**Every command-bar action has to open something that exists.** The scan ids are
checked against the catalogue `/api/scanners` publishes, and the views against
`PALETTE_PLACES`. An action that opens a view Optic does not have reads as a
broken feature rather than a missing one, which is worse. `runScan` is the entry
point for a scan; a first draft of the actions list added an `openScan` wrapper
that duplicated it, fifty lines from the comment in this file saying there is no
`openScan`.

**The homepage is a market command centre and the strip is its first element.**
`#cc-strip` sits above the brand and the search and is filled separately from
`#hm-market`, so it does not wait behind the watchlist and the movers scan.
Everything on it comes from `/api/home`, which already carried nineteen macro
instruments grouped by asset class. The brand is one 30px row because the page
header already says OPTIC TERMINAL; the display-size wordmark and the three-line
lede were about 340px of branding above the fold and the lede now heads the tour
at the foot.

**Rank a cross-asset list by the move against each instrument's own range, not
by raw percent.** `atr_pct` is on every instrument in that payload. Raw percent
ranks by which instrument is inherently jumpiest: it led with VVIX +6.4% and Nat
Gas -3.9% while the Russell was down 1.3% in fourth, and VVIX moves 4.9% on an
average day against the Russell's 1.1%. The multiple is displayed, because
without it the order looks like a plain sort by the bigger number.

**There is no same-day movers leaderboard in this app, and the copy says so.**
The scanners rank on twenty- and sixty-day rate of change over a universe a
background job builds across ~3000 symbols, and `available: false` is a normal
cold-start state rather than an error. The block is headed "Moved most this
month" for that reason. Ranking today's movers would need a same-day quote for
the whole universe, which no feed here carries.

**Error copy that names the deployment goes stale when the deployment moves.**
Three places told the reader "this address is a temporary tunnel and changes
every time the server restarts", which was true on a Cloudflare quick tunnel and
is wrong twice on a custom domain: the link is fine, and reloading is exactly
what fixes it. `originIsEphemeral()` tests the hostname for `trycloudflare.com`
and the copy branches on it, so both cases get true words. `app/alerts.py` had
the same premise in prose and now reads `is_hosted()`. A test asserts no
reader-facing string in that module asserts a laptop, scoped with `ast` so it
does not trip over the docstring's own past-tense account.

**A heading is a claim.** The factor panel was titled "Why it's moving" with
the day's change beside it, and its body ranks the model's inputs by *absolute*
score, so the three strongest can all read bullish on a day the price closed
lower. They did, and it was reported as a rendering bug. Nothing about the
ranking was wrong. It is "What's pulling hardest" now, the change is labelled
`today` so it reads as context, and the method line spends its one sentence on
the thing readers actually trip over rather than restating the heading.

**A control offered only in the empty state is worse than no control.**
`askPulse` was on the empty branch of both the factor panel and What matters
next and absent from their populated branches, so the Ask Pulse button appeared
when there was nothing to ask about and vanished as soon as there was. The
existing both-directions check could not see it: the topic *is* referenced, just
from the wrong branch. `tests/test_why_moving.py` audits every `pl-h` header for
the pair instead.

**An insider filing's direction is in `action`, never in the sign of
`shares`.** `recent_transactions` carries `shares` as a positive magnitude, so
`shares > 0 ? 'Bought' : 'Sold'` is true for every row. The dock widget did
exactly that and rendered six green "Bought" lines on TSLA where three were
sales and three were option conversions: not one was a purchase. `action` is
three-way, and the third value is the absence of a direction rather than a third
kind of it. `insiderEvents` already dropped `other` from the chart markers and
says why; the dock widget was the surface that never got the same treatment.
This is the third time this session a direction was read from the wrong field,
after `watches.py` and the VIX tile.

**A checkbox fires `change`; a button fires `click`.** `data-ws-opt` is handled
in a `change` listener, which is right for the overlay checkboxes. The one-item
menus render a button instead, and the first version reused that attribute: the
Fibs button rendered perfectly, was correctly wired, and did nothing at all. It
has `data-ws-toggle` and a click branch. Two shapes, two events, two names.

**A menu with one option is not a menu.** `wsToolbar` renders a single-item,
non-`manage` menu as a direct toggle. Written as a rule about the item count
rather than a special case for `fibs`, so a menu that loses its options becomes
a button and one that gains a second becomes a dropdown again.

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
