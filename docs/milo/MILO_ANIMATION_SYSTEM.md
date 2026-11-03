# Milo's activity states: the system

The states, what moves them, how they are drawn, what the motion is, and what happens when a reader has
asked for less of it. Written 2026-11-03 on branch `milo-animation`.

Code: `static/v2/js/ui/milo-activity.js` (states, reducer, views, props),
`static/v2/css/components.css` (`.milo-doing*`, lines 642-719), `static/v2/js/ui/milo.js` (the wiring).
Tests: `tests/test_milo_activity.py`.

## 1. The states

| State | When | Heading | Line (when the server gives no words) |
| --- | --- | --- | --- |
| `idle` | nothing in flight | drawn as nothing | |
| `thinking` | the question has gone and the model has it, with nothing fetched yet | Thinking | Understanding your question |
| `researching` | the server says it is fetching | Researching | Looking through Optic's data |
| `analyzing` | a model round started after at least one lookup returned, before any text | Analyzing | Connecting what came back |
| `writing` | the first chunk of the answer arrived | Writing | Putting it together |
| `complete` | the answer finished | Answer ready | Here's what I found |
| `error` | the stream failed, or ended with no text | No answer | Milo could not finish this one |
| `cancelled` | the reader pressed Stop | Stopped | Stopped by you |

When the server names the step itself ("Checking NVDA's options data", "Reading your watchlists"), its words are
shown in place of the default line. The panel already owned that vocabulary (`stepWords` in milo.js); this
feature reuses it rather than inventing a second one.

## 2. What moves between them

The reducer is `on(record, kind, payload)` in `milo-activity.js`. It is pure: no DOM, no clock, no timers, and
it never infers a step from elapsed time. `MILO_STREAMING_INTEGRATION.md` has the event mapping.

```
             status: a tool / a search / gathering
   thinking ───────────────────────────────────────► researching
      ▲                                                  │
      │ status: a model round, nothing fetched            │ retrieved (something came back)
      │                                                  ▼
      └──────────────── status: a model round ───── analyzing
                          (something fetched)           │
                                                        │ first delta
   any state ── first delta ──► writing ◄───────────────┘
   writing ── status: a tool ──► researching  (one more figure, mid-answer: the same loop going round)
   any state ── done ──► complete    ── error ──► error    ── Stop ──► cancelled
```

Three rules keep it honest:

1. **Researching needs the server to say it is fetching.** A question answered with no lookup goes
   Thinking to Writing and never shows Researching.
2. **Analyzing needs something to have come back.** A second model round with nothing fetched is still
   Thinking. A lookup that returned `ok: false` does not count, so a failed lookup never produces Analyzing.
3. **Nothing is listed that a lookup did not return.** The ticks under Analyzing are the labels the server sent
   on `retrieved`, filtered to the ones that succeeded, at most three, newest last. There is no percentage,
   no step counter and no estimated time anywhere in the feature.

## 3. The two views

| | Expanded card | Compact line |
| --- | --- | --- |
| When | no text yet, not a phone, panel at least 400 px wide | everything else, and always once text is arriving |
| Figure | `scout-full`, 78 px wide, in a 132 px column | `scout-compact`, 34 px |
| Prop | yes, placed per prop | no: the words have the room |
| Surface | own panel inside the bubble, `--c-plane-2`, 1 px `--c-line`, `--r-lg` | no surface |
| Heading | `--t-lg` | `--t-md` |

`CARD_MIN = 400` is measured on the **panel**, not on the bubble. The bubble is the panel less its padding and
the answer's own indent (403 px inside a 444 px panel, measured 2026-11-03), which would have put the
threshold on a number with no meaning. A phone never gets the card: there the panel is the whole screen and
the answer has to come first.

Once the first chunk of text arrives the card gives way to the line, in the same place. Milo shrinks rather
than disappearing, which is what the reference sheet asks for.

## 4. Motion

Two kinds, kept apart.

**The character moves in his own frames.** Researching, Analyzing and Writing are rendered poses on the
sprite sheet (`static/scout`), driven by `static/components/scout.js`: he is at the table with the laptop,
holding the tablet, writing in the notebook. His blinks, his pose changes and the small loops he plays while
working (`type`, `read`, `pen`) are that driver's, stepping through frames of the sheet. Nothing about him is
animated in CSS, and nothing about him is drawn in CSS.

**Everything around him is CSS.** No animation library was added, no Lottie, no Rive, no new dependency of
any kind. Every CSS animation is declared in one block of `components.css`, which is what lets Reduce motion
stop all of them in one place.

| What | Property | Duration | Easing | Repeats |
| --- | --- | --- | --- | --- |
| Card appearing | `opacity`, `translateY(4px)` | 260 ms | `--ease-out` | once |
| Three dots | `opacity` .22 to 1 | 1.3 s, 170 ms apart | ease-in-out | yes |
| A tick appearing | `opacity`, `scale` | 240 ms, 90 ms apart | ease-out | once per tick |
| Thought bubble floating | `translateY(2px)` | 3.4 s | ease-in-out | yes |
| Its chart line drawing | `stroke-dashoffset` | 2.2 s | ease-in-out | yes |
| Sparkles | `opacity`, `scale` | 900 ms | ease-out | once |

And in the character's own frames (`GESTURE` in scout.js):

| Loop | Frames | Beat |
| --- | --- | --- |
| Typing | `desk-type`, `desk`, alternating | 150-170 ms a frame, five frames |
| Looking at the tablet | `tablet-near`, `tablet` | 820 ms down, 180 ms back |
| Writing | `write-1`, `write-2`, `write-1`, `write` | 150-240 ms a frame |
| Blinking, in every pose | that pose's `-half` and `-closed` lids | 35-50 ms a frame |

He plays one of those, or a blink, every 2 to 4 seconds while working, at Full motion only. No bouncing, no
spinning, no shaking, no flashing; the largest CSS travel in the set is 4 px.

## 5. Reduce motion

Two triggers, one block (`components.css`, "One place for Reduce motion"): the system preference
`prefers-reduced-motion: reduce`, and Optic's own `:root[data-motion="reduce"]`.

With either set: every CSS animation and transform in the activity is off, the thought bubble holds its
finished shape, and the dots sit at .5 opacity instead of pulsing. The character stops moving too, because
`scout.js` already reads both and drops to its Still motion.

**The states still change, and so does the pose.** A state is what Milo is doing, not decoration, so the
heading, the line and the ticks are all still shown and still update, and `Ctl.prototype.pose` keeps a worked
pose at Still motion: Researching still shows him at the desk, Writing still shows him at the notebook. They
simply hold. Only the standing states fall back to the plain resting frame, which is what they always did.

## 6. Accessibility

- The row is one `role="status"`. The heading and line are announced together rather than as two separate
  live regions firing one after the other.
- Props are `aria-hidden="true"` and `focusable="false"`. They carry no information the words do not.
- The row holds nothing focusable and takes no tab stop: measured 2026-11-03, 0 focusable elements inside it
  while an answer was live, with Stop and the composer both still reachable.
- The ticks are a `<ul>`, so they are read as a list of what came back.

## 7. Performance

Measured in the running app, 2026-11-03, Chrome in the app's browser pane. The pane throttles timers, so
wall-clock timings taken around awaited delays there are meaningless and are not reported.

| | Measured |
| --- | --- |
| Reducer, a whole five-event sequence | 3.05 µs |
| Patching the view on a state change | 8.1 µs |
| Rebuilding the view instead | 127.3 µs |
| Card height across all four working states | 141 px, identical: no layout shift |
| New image bytes | none |

The view is **patched in place**, not re-rendered. The first draft replaced the whole view on every state
change, which restarted the mascot's blink timer, reloaded his sprite and re-ran the card's 260 ms fade, so
the card flashed empty between states. `syncActivity` now rebuilds only when the row appears, goes, or changes
size; otherwise it writes the heading, the line, the prop and the ticks in place, and the figure element
survives. That is the 8.1 µs against 127.3 µs above.

No new image is fetched: the panel's empty state already loads the full sprite sheet (`milo.js:320`), and the
activity card reuses it. The props are inline SVG in the module, so they cost no request at all.

Painting is unchanged: `paintLive` still does at most one paint per animation frame, however many events
arrived in it.
