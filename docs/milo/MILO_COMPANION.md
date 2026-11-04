# Milo, the persistent companion

Written 2026-11-03 on branch `milo-companion`, cut from `origin/main` `c623c264`. Not deployed, not merged.

## 1. Why he used to disappear

He was not one character. He was three, each owned by a different piece of markup, and each of them was
destroyed by something the conversation did routinely.

| Figure | Where it lived | What removed it |
| --- | --- | --- |
| The welcome figure | inside `openingHTML()`, the empty-conversation screen | the first question: the opening is replaced by the log |
| The header bust | `.milo-id` in the drawer header | removed by hand on 2026-11-03 at the owner's request |
| The activity figure | inside the streaming answer bubble, `.milo-live-lines` | `paintFinished()` replaces the live bubble with the settled answer, and a timer removed the row 1.6 s after that |

So the two moments a reader most wants him, pressing Send and reading the finished answer, were exactly the
two moments his element was torn down. Nothing was broken in the sense of throwing an error: the markup that
held him was simply not his, and it belonged to things with shorter lives than the conversation.

Two further consequences fell out of the same cause. Because the activity figure was built inside the answer,
it had to shrink to 34 CSS px once text arrived, or it would have pushed the answer down the screen. And
because it was rebuilt whenever its size changed, his sprite reloaded and his blink timer restarted.

## 2. What replaced it

One companion, in the drawer's header, which is a **sibling** of the scrolling log rather than a part of it.

```
.drawer-panel.milo-panel
  header.drawer-head          <- the companion lives here: figure, name, status, and his guide menu
    .milo-co                     never rebuilt, never removed, outside everything that redraws
    .drawer-acts                 history / new / close, absolutely placed so he can centre
  .drawer-body
    .milo
      .milo-chrome            <- context and settings
      .milo-log-wrap > .milo-log   <- the conversation, the only thing that scrolls
      form.milo-form          <- composer
```

Nothing that happens to the conversation can reach him: the log scrolls inside its own box, `paintLog()`
redraws the log, and `paintFinished()` replaces the answer bubble. All three are below `.drawer-head`.

| Piece | What it does |
| --- | --- |
| `coEl()` | the one `.milo-co` in the open panel, or null |
| `coCtl()` | his controller; `OpticScout.attach` returns the one already on the element, so this is cheap on every paint |
| `paintCompanion(act, via)` | patches status text and data attributes in place, then sets the pose; `via` plays one gesture into it |
| `syncCompanion()` (milo-activity.js) | writes only what changed; never `innerHTML`, never removes the region |
| `coState()` | the live answer's state, or `SC.rest` between answers |
| `companionEnd(ok, ended)` | the outcome, then a settle timer that checks nothing newer is running |

`slot: 'companion'` is his alone, attached in exactly one place. The old `welcome`, `reply` and `activity`
slots are gone, along with `SC.i` / `SC.state` / `SC.via`, which existed to track which of the three figures
was the current one.

## 3. Truthfulness

The state machine did not change: `on(record, kind, payload)` in `milo-activity.js` is the same pure reducer,
driven by `status`, `retrieved`, `delta`, `done` and `error` from `app/ai.py`. Researching still requires the
server to say it is fetching, Analyzing still requires a lookup to have returned, and a failed lookup is still
not evidence. What changed is only where the result is drawn.

The statuses are one line each: Ready, Thinking, Researching, Analyzing, Writing, Answer ready, Stopped,
Couldn't finish. Under it sits the server's own words for the step when it sends them ("Checking NVDA's
filings") and nothing at all when it does not.

### Keeping up with the round (2026-11-03)

The owner's report was that it "is just stuck on thinking and then sometimes switches to writing". Two
separate causes, one on each side:

- **The server went quiet in the middle of a round.** It sent `writing` as the round began (which is
  Thinking until text arrives) and then nothing at all until a tool actually ran. A round that reasoned for
  twenty seconds and then asked for three lookups spent all of it on Thinking. The stream already carried
  the moment the model stopped reasoning and started naming a tool - `content_block_start` for a `tool_use`
  block - and that was being dropped. It is now forwarded as `looking up what it needs`, guarded by
  `will_fetch` so a call the round's limits would refuse is never announced as research.
- **Thinking played the writing animation.** The loop for a pose was picked by a chain of equality tests
  ending in `pen`, so `chin` - the one scene that is neither a desk nor a tablet - fell through to the
  notebook frames. He was *literally* switching to writing while the heading said Thinking. Each pose now
  names its own loop (`LOOP` in `components/scout.js`) and a test fails if a scene has none, or if a loop
  plays a frame from outside its own pose.

## 4. The assets

Two things were rendered for this stage, both as geometry in `optic-brand/scout/render_scout.py`:

- **Headphones**, on every working pose. A slim charcoal band over the top of the head and a cup at each ear,
  with a bead of gold along the band and a gold rim circling each cup. The gold is the point: it is the same
  weight as the rims of his glasses, so they read as his own rather than as a pair of cans borrowed from
  somewhere else. He has none in Thinking, so putting them on **is** the move into research.
- **`chin`, `chin-half`, `chin-closed`**, the hand under the jaw. `POSE.thinking` was a head tilt, which told
  nobody he was thinking. His arm is a stub about a third of the distance from his shoulder to his chin, so
  for this pose it is drawn longer and tapered; a straight arm at full reach only got as high as his belly.
- **`chin-2`, `chin-3`**, the two small head moves the thinking pose ponders on: a settle, and a glance off to
  the side. The chin hand is now held in the **head's** frame rather than the world's, so it goes where the
  chin goes and the mitt never drifts off the jaw when the head moves. The canonical `chin` frame comes out
  bit-for-bit identical, because there the two transforms cancel.

The sheet is 43 frames. `scout.js` measures the one the browser actually loaded (shipped in `c623c264`), so
the count moving again cannot slice him wrong.

## 5. Behaviour

| When | What he does |
| --- | --- |
| The panel opens | one wave, then rest. A 60 s cooldown, so closing and reopening does not wave again |
| The reader types | an attentive tilt toward the composer, back to rest after 2.5 s of quiet. Never while he is working |
| The question is sent | a nod, then Thinking. The nod is set up before the request and nothing waits on it |
| He waits on the model | the pondering loop: a settle, a glance away, a blink. Never the writing frames |
| Research begins | headphones on, at the desk |
| Text arrives | the notebook |
| The scene changes | he dips out and back over 90 ms, so a laptop becoming a tablet is a transition, not a cut |
| The answer lands | Answer ready and one small wave, then he settles to Ready after 2.5 s and stays |
| Stopped, or failed | Stopped / Couldn't finish, work motion stops, he stays |
| He is clicked | one wave or curious tilt, at most one per 900 ms, and never while he is working |

The settle timer checks `!S.busy && !S.live` before it runs, and sending a question clears it, so a finished
answer cannot reach into the next one.

## 6. What is not here

- **No thought bubble or drawn props.** The poses carry the state, and a header is too small to hold both.
  The old gold line drawings were deleted with the in-log card.
- **No pointer tracking.** The brief lists it as optional and after the core; it is not done.
- **No microphone, ever.** The attentive pose is named `listening` in the driver for the composer, not for
  audio. Optic records none and asks for no audio permission.
