# Milo's answer, from Send to the last word

Phase 07 of the post-demo overhaul (directive 07, section 1), 2026-10-29. One question followed through the fourteen
stages the directive names, with where each happens in the code and what it was measured to cost before and after this
phase.

## How it was measured

- **What is measured.** Everything Optic does, as it is: the browser's work, the request, the server's routing,
  checks, context and tool round, the safety gate, the transport, and the drawing.
- **What is emulated.** The model. No working key exists on this machine (BLOCKERS BL-01). The stand-in model
  (`tools/milo_standin_ultra.py`, STREAMTEST) answers the way the Messages API does: a quote-tool round, then the first
  token after 0.6 s, then tokens of 2 to 6 characters every 16 ms (about 60 a second) through a 1,300-character
  markdown answer. Every figure below that includes the model's time says so.
- **The tool.** `tools/phase07_measure.py`, in headless Chrome 152, signed in as the local demo account on NVDA's
  Overview. Five answers on the code before Phase 07 (`1652e14`, served on :8252), then five on the code after it
  (:8250), back to back on an idle machine. Three more each with a chart in the answer (STREAMCHART).
- **Instrumentation.** It is injected before the app loads and changes nothing in it. The chat response is teed and
  each event timed. Every animation-frame callback is timed, and long tasks are recorded. A mutation observer notes the
  first visible text and every paragraph and chart element made. Ten characters are typed into the composer while
  the answer streams.
- **Raw results.** `~/Optic/work/post-demo-ultra-2026-10-29/phase07/measure-*.json`, summarised in
  `measure-summary.json`.

Times are milliseconds from the press of Send: the median, with the range in brackets.

## The fourteen stages

| # | Stage | Where | Before | After |
|---|---|---|---|---|
| 1 | User submission | `wire()` submit and Enter handlers, `send()` in `ui/milo.js` | The question is drawn at once | The same |
| 2 | Frontend request creation | `send()`: `buildContext`, the messages, `fetch('/api/chat')` | Request sent at 6.8 (4.6 to 9.1) | 7.6 (5.7 to 9.3) |
| 3 | Backend routing | `@app.post("/api/chat")` in `app/main.py` | Response headers at 101.7 (99.8 to 338.2). The response began only once stage 5 had finished | 24.0 (17.4 to 25.5). The response begins at once |
| 4 | Authentication and session checks | `_spend_guard`, `_count_question`, the session cookie and CSRF header | Inside the time above | The same checks, before the response starts |
| 5 | Context construction | `_chat_context`: the page's figures, the research pack, the framework, chart levels and a linked portfolio, side by side | Nothing reached the reader until it was done: 108.6 to the first byte, 328 for an uncached ticker (PEP). Meanwhile the browser said "Sending your question", then its own "Preparing the answer" once the response began | The same work, now behind a first event: `status: gathering` at 24.3 (17.6 to 25.7), said as "Reading NVDA's figures". The server records `context_ready_ms`: 75.0 (66.7 to 277.5) for NVDA, 366 for uncached PEP |
| 6 | Tool execution | `_milo_toolbox`, the tool loop in `ai.stream_chat` | get_quote under 1 ms. "Checking NVDA's quote" then stayed up for the whole next model round, 3.5 s in the slow-round check | get_quote 0.3 to 0.4 ms, timed per tool. The line goes back to "Working out the answer" the moment the tool returns |
| 7 | Model provider invocation | `ai.stream_chat`: `client.beta.messages.stream` | Not timed by the server | `first_model_event_ms` 97.1, `first_model_text_ms` 719.1. **Emulated model** |
| 8 | First response event | the first `delta` to reach the browser | 835.4 (829.5 to 1067.5) | 835.4 (815.8 to 1041.6). Set by the emulated first token and the safety gate's first sentence |
| 9 | Streaming transport | Server-sent events read with `fetch` (POST, `ReadableStream`), one JSON object an event | 20 text events: whole sentences from the gate, 51 characters at the median, 248 ms apart (p90 416) | The same, by design (DECISIONS D-042) |
| 10 | Frontend chunk processing | `send()`: `TextDecoder` in stream mode, events split on blank lines, `JSON.parse` | Under 1 ms an event | The same |
| 11 | State updates | `S.live.text`; `paintLive()` at most once a frame | Every event rebuilt the whole answer | Every event appends to the text. One paint a frame draws only what changed |
| 12 | Markdown rendering | `paintLive()`, `settledEnd`, `streamingHTML` and `renderAnswer` in `core/milo-text.js` | Each finished paragraph drawn 15 times at the median, up to 18. A chart in the answer made and drawn 16 times (10 to 16). The arriving paragraph was plain text with raw stars and hashes. Frame time p95 2.6, max 3.4 | Each finished paragraph drawn twice in all: once as its last arriving state, then once finished. The chart made and drawn once. The arriving paragraph drawn as markdown. Frame time p95 1.7, max 2.5. No long tasks before or after; the characters typed meanwhile all kept |
| 13 | Auto-scroll | `noteScroll`, `keepEnd`, `restoreView`, a `ResizeObserver` on the log | A reader at the end was left 52 px behind by the composer growing after an answer, and up to 163 px by a chart. A 40 px scroll up was pulled back down. The panel reopened at the top of the conversation | Followed to 0 px through charts and the composer. A scroll up is never pulled back. Reopening restores the reader's place |
| 14 | Response completion | the `done` event; `paintFinished()` | Done at 5,800 (5,760 to 5,984). The finished answer was drawn again, whole | 5,774 (5,704 to 5,962). Finished in place: the paragraphs and the chart already on screen stay. The emulated model's token rate sets this time |

With a chart in the answer, three runs each: first visible text 1,028 before (836 to 1,138) and 849 after (838 to
852); done 5,902 and 5,852.

## What the reader sees, in order

At 1440 by 900, NVDA, from the slow-round check (C08: the stand-in waits 2.5 s before its tool call and 3.5 s before
its first word):

| ms | Line in the answer | What is happening |
|---|---|---|
| 0 | Sending your question… | The request is on its way |
| 101 | Reading NVDA's figures… | The server is gathering the page's figures (`gathering`) |
| 201 | Working out the answer… | The model's first round has started (`writing`) |
| 2,702 | Checking NVDA's quote… | The model asked for the quote tool, and Optic is running it |
| 2,727 | Working out the answer… | The tool returned and the model's second round started |
| about 6,320 | The answer's first sentence | Text has arrived; no activity line is shown with text |

After 30 seconds with nothing from the server, the line "No reply from the server for 30 seconds. You can keep
waiting or stop the answer." appears, and it goes when anything arrives (C09). No activity line remains after the
answer ends (C08).

## The transport stays

The server already streamed genuine text deltas (`messages.stream`) as server-sent events read with `fetch`. That is
the right transport for a one-way answer with a POST body, cookies and a CSRF header. WebSockets would add a second
protocol and a connection to keep alive for no gain, and EventSource cannot POST. Nothing was replaced (D-043).

## Where the time goes, and what is left

- **The safety gate.** The first visible word waits for the first complete sentence (D-042). In the emulation the
  gate held text for up to 747 ms (`gate_hold_max_ms`).
- **The model's time to its first token.** With the real model this is the largest wait, and it cannot be measured
  here (BL-01). Each answer now logs its own timing (`milo timing:` in the server log, `timing` in the `done` event),
  so the first live answers will give the real figures.
- **The context.** Optic's own work before the model starts: about 75 ms with warm caches, about 370 ms for an
  uncached ticker. It now happens behind a truthful activity line instead of a silent wait. Parts of it run on the
  event loop before their first await. That held the first line back to about 85 ms until a 5 ms yield was added
  after it, and it holds every other request on the server for those milliseconds. Moving that work off the loop is
  Phase 10's (BUG-113).
