# How the activity is driven by the real stream

Every state change comes from an event `app/ai.py` actually sends. Nothing is inferred from elapsed time, and
nothing in this feature delays a single byte of the answer. Written 2026-11-03 on branch `milo-animation`.

## 1. What the server sends

`stream_chat` in `app/ai.py` writes Server-Sent Events over `POST /api/chat` (and `/api/research` for deep
research). The ones the activity reads:

| Event | Where it is sent | What it means |
| --- | --- | --- |
| `status {state: "writing"}` | `ai.py:3655`, at the top of the model loop | a round of the model is starting |
| `status {state: "thinking"}` | `ai.py:3664` | the model opened a thinking block |
| `status {state: "searching the web" / "reading results"}` | `ai.py:3666,3668` | the model's own web search |
| `status {state: "searching" / "reading and weighing sources"}` | `ai.py:3854,3856` | deep research |
| `status {state: <the tool's own words>}` | `ai.py:3737` | a tool is about to run; the words come from `milo_tools.status_words` |
| `retrieved {items: [...]}` | `ai.py:3742` | what has been looked up so far, each with a label and `ok` |
| `delta {text}` | `ai.py:3677,3764` | a chunk of the answer |
| `error {message}` | `ai.py:3618,3793` | the request failed |
| `done` | end of stream | the answer finished |

Two events the activity deliberately ignores: `status {state: "some files were not sent: ..."}` (`ai.py:3624`)
is a problem report, not a step, and is filtered by `NOT_A_STEP`; `attachments`, `assumed`, `notice` and
`amend` are about the answer, not about what Milo is doing.

## 2. The mapping

In `static/v2/js/ui/milo-activity.js`, `on(record, kind, payload)`:

| Event in | State out | Why |
| --- | --- | --- |
| `status`, a tool's words / a search / anything not `writing` or `thinking` | `researching` | the server is telling us it is fetching |
| `status` `writing` or `thinking`, nothing fetched yet, no text yet | `thinking` | a model round with nothing behind it |
| `status` `writing` or `thinking`, something fetched, no text yet | `analyzing` | the model has gone round again on what came back |
| `status` `writing` or `thinking`, text already started | `writing` | the same answer, still being written |
| `retrieved` with at least one `ok` item | `researching` (if no text yet), and the labels are kept | something came back |
| `retrieved` with only failed items | state unchanged, nothing kept | a lookup that returned nothing is not evidence |
| first `delta` | `writing` | text is arriving |
| `done` | `complete` | |
| `error`, or the stream ending with no text | `error` | |
| Stop | `cancelled` | |

`writing -> researching` is allowed: the model can ask for one more figure after the text has started, and that
is the same loop going round, not a fabrication.

## 3. Where it is wired

`static/v2/js/ui/milo.js`, inside the existing SSE reader. Three lines were added to the event loop:

```js
if (ev === 'delta')          { ...; S.live.act = actOn(S.live.act, 'delta'); ...; paintLive(); ... }
else if (ev === 'status')    { ...; S.live.act = actOn(S.live.act, 'status', p); paintLive(); ... }
else if (ev === 'retrieved') { ...; S.live.act = actOn(S.live.act, 'retrieved', p.items); paintLive(); }
```

`S.live.act` is created by `actBegin(deep)` in `send()`, on the same record that already held the live text,
the status line and the symbol. `paintLive` then calls `syncActivity(lines, L.act, { expanded, stepWords })`
and `scoutInActivity(lines)` on every paint.

## 4. What was not changed

The streaming path itself is untouched. Specifically, none of this was modified: the fetch and its reader, the
SSE chunk parsing, `renderAnswer` and `streamingHTML` (the markdown renderer), the two-a-piece figure and
action limits, the scroll management (`noteScroll`, `keepEnd`), the abort controller and Stop, the amend
handling, the history write, or the answer's sources, actions and follow-ups.

There is no typewriter effect anywhere, and none was added. Text is drawn as it arrives, in the same
at-most-one-paint-per-frame loop as before.

## 5. The answer never waits for the character

When the answer finishes, `paintFinished(i, live, ok)`:

1. draws the finished answer, its sources, its actions, its follow-ups and its notices, as it always did;
2. in the same frame, swaps the row Milo was already standing in to Answer ready;
3. after `DONE_MS` (1600 ms) removes **only that row**.

No timer sits between the answer and the reader. Measured 2026-11-03: at the moment the `done` event landed,
the actions (Copy, Ask again, Report a problem), the AI disclosure and the follow-up example were all drawn
alongside the Answer ready row, and the row retired on its own 1.6 s later with nothing else moving.

Answer ready is shown only for an answer that actually landed: `paintFinished(ai, liveWas, !failed && !ended
&& !!reply.trim())`. A failure, a Stop and a cut-off stream all pass `ok: false`, and the row is removed
instead. Verified in the browser for all three.

## 6. One answer at a time, and no stale events

- `S.live` is a single record, created per send and cleared when the answer ends. The activity lives on it, so
  it cannot outlive its own answer.
- The panel refuses a second question while one is in flight (verified: sending again during an answer left
  the message count unchanged and showed a toast), and Stop aborts the request, so there is never a second
  live stream writing into the record.
- `paintLive` only ever patches the bubble marked `data-v2-live`, which is the one the current answer owns.
- Starting a new conversation while busy is refused with a toast; with nothing in flight it clears the log and
  leaves no activity behind (verified).
- A conversation reopened from history draws no activity at all: the record is gone, and `syncActivity` with
  no record removes the row (verified: 4 bubbles restored, no row, not busy).

## 7. Deep research

`send(text, { deep: true })` posts to `/api/research`, which sends the same `status` / `delta` / `error` /
`done` vocabulary. `actBegin(deep)` records the flag. The same states apply; the deep-research search statuses
(`searching`, `reading and weighing sources`) are in `SEARCH_STEPS` and map to Researching.
