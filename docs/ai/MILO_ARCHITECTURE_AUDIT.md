# Milo: architecture audit

Phase 12 (directive 14, Part 4.1), 2026-11-02. Read from the code on branch `phase-12-writing-milo-security`
(worktree `~/Optic/wt-phase12`, cut from live `main` at `d22522a`), and measured where it says so. Earlier documents
were checked against the code, not trusted: `docs/post-demo-ultra/MILO_TOOLS.md`, `STREAMING_PIPELINE.md` and
`COST_AUDIT.md` describe the same system and still hold where this page does not say otherwise.

## The model

| Item | What the code does | Where |
|---|---|---|
| Provider | Anthropic, through the official Python SDK (`AsyncAnthropic`), built bare so the SDK reads `ANTHROPIC_API_KEY` (or an auth token or `ant` profile); `ANTHROPIC_WORKSPACE_ID` adds the workspace header a personal key needs | `app/ai.py` `_client` |
| Milo's model | `claude-sonnet-5-5` (`PULSE_MODEL`), since 2026-10-16 on the owner's word after a 14-question live comparison with Sonnet 5 (`docs/milo/reasoning-eval/LIVE-MODEL-TRIAL.md`). The live model was not called in this phase: the local key is refused (BL-01), so "this is what production runs" rests on the code and the deployed commit, not on a response header | `app/ai.py:60` |
| The published writers' model | `claude-opus-5-5` (`MODEL`): the morning desk and its read, the daily edition, the weekly update, the earnings, sector and catalyst reads, catalyst extraction. Each is written once and cached | `app/ai.py:55` |
| Also on Sonnet 5.5 | deep research (`/api/research`), the Brokerage portfolio briefing, reading a screener request in words | `app/ai.py` |
| One switch | Every call passes one of the two constants; `tests/test_pulse_model.py` fails on a model literal anywhere else | |
| Request parameters (chat) | `max_tokens` 8,000; `thinking: {type: adaptive}`; `output_config: {effort: medium}`; no temperature set | `build_chat_request` |
| Fallback | The beta `server-side-fallback-2026-07-01` with `fallbacks: "default"`: on a refusal the API re-runs the request on Anthropic's recommended fallback model inside the same call. A refusal that still ends as `stop_reason: refusal` is told to the reader as such | `app/ai.py:65`, `stream_chat` |
| Retries | SDK `max_retries` 5 (429 and 5xx, including 529 overloaded), exponential backoff | `_client` |
| Claude Code is not Milo | This audit was written by Claude Code running Claude Opus 5.5 in the owner's desktop app. That model has nothing to do with Milo: Milo is whatever `PULSE_MODEL` names, called with Optic's own key from Optic's server | |

## The prompt

The system prompt is a list of blocks, in this order, the first one cached:

| Block | Size (characters) | When |
|---|---:|---|
| `SYSTEM_PROMPT` (who Milo is, the data, reasoning standards, the take, trades and scenarios, tools, missing data, the options read, how to write, deep analysis, candidates, boundaries) + `FORMAT_PROMPT` (answer shape, follow-ups, chart and figure tags, action cards, the fair-value model, source tags, the reader's lists, punctuation) + `editorial.WRITING_RULES` (new in Phase 12) + `ai_policy.POLICY_TEXT` | 34,508 + 14,759 + 1,949 + 2,523 = 53,743 in one block with `cache_control: ephemeral` | every request |
| The level's block (`knowledge.prompt_for`: one of five, plus the invariant that no level changes a figure) | about 600 | every request |
| The horizon block (`horizon.prompt_for`) | short | when a horizon is known |
| The research framework's block (`research/milo.py prompt`) | short | when the framework routed the question |
| The persona (lens) | short | when not Neutral |
| The humour block (`FLAVOUR_PROMPT`) | 1,400 | about one Neutral reply in two, never on a loss or a long-form request |
| The policy turn (`ai_policy.turn_instruction`) | short | when the request reader classified the question as one the policy declines |

The tools' definitions add 12,288 characters (17 tools, all offered on a request that has a toolbox except
`get_my_portfolio`, which follows the portfolio rule below).

**Phase 12 changes to the prompts** (details in `docs/editorial/WRITING_CORRECTIONS.md`):
- `app/editorial.py` now holds one set of writing rules. They are appended to every model request, after the
  writer's own prompt and before the advice policy, so the policy reads last. Before this, each writer carried its
  own copy of the voice.
- `FORMAT_PROMPT` keeps the risk paragraph and the condition that would change the read. It no longer mandates a
  closing **Bottom line** heading, which invited restating the answer.
- The writers no longer invite ellipses ("as a pacing device": research, weekly, morning). The weekly no longer
  models its register on "Woohoo! ... Wait, what?" or asks for emphatic capitals.

## What reaches the model: context, history, attachments

- **CONTEXT** is the page's own computed figures as the browser sends them (`ui/milo.js buildContext`), with what
  the server adds for the question (`main._chat_context`):
  - `question_named` (symbols in the question), `auto_loaded` (the first named symbol not on the page),
    `screen_candidates` or `market` for idea or market questions;
  - the research pack (`research`), the framework read (`framework`), the chart levels (`chart_levels`);
  - the reader's linked brokerage (`brokerage_portfolio`), only from the Brokerage page or for a question about
    their own holdings.
- **Budget:** CONTEXT is budgeted to 60,000 characters with per-section caps (`budget_context`), and rides on the
  last user turn so the cached system prefix stays identical.
- **History:** sent by the browser on every request. It is bounded to the last 24 turns and 60,000 characters
  (`bound_history`), and a question to 8,000 characters (413 above that, before the allowance is charged).
- **Memory between conversations:** none on the server. v2 keeps conversations in the browser's localStorage
  under `optic.pulse.history.v1` (30 conversations, 60 messages each), readable only by the account that holds the
  device (`core/device.js holds()`). Classic uses the same key; see the red team's MRT-03 for its gap.
- **Attachments:** PNG, JPEG, GIF, WebP or PDF, up to 4 files of 5 MB each. Each is checked by its first bytes and
  sent base64 in that request only. Nothing is written to disk.
- **What the server strips from browser context** (Phase 12, MRT-05 and MRT-09):
  - every key only the server writes: `brokerage_portfolio`, `brokerage_linked`, `auto_loaded`,
    `auto_load_skipped`, `question_named`, `research`, `chart_levels`, `screen_candidates`, `market`,
    `portfolio_summary`;
  - the reader's own blocks (watchlist, paper book, journal, retirement plan) when the question is not about them
    (BUG-071, and now in deep research too, MRT-04);
  - the Brokerage page's account ids, after they have scoped the block.

## Retrieval

There is **no vector database, embedding index or document store**. "Retrieval" is three deterministic mechanisms:

1. **The page context**, described above.
2. **The research pack** (`app/desk/research.py build`, through `main._with_research`): Optic's own sources chosen
   by the question's intent. These are the company's figures and filings, the macro series, the Desk's evidence, and
   headlines. Each item has a source, a period and a link, and they are listed under an answer as "Sources Milo read"
   (`ai.sources_read`).
3. **Tools** the model calls during the answer (below).

All three read public market data or the asking reader's own rows. Nothing is retrieved by similarity, so there is
no cross-tenant index to leak from. The only per-reader stores are the accounts database's tables (watchlists, saved
research, brokerage links and snapshots), read by the session's user id.

## Tools

17 tools in `app/milo_tools.py` (`SPECS`), run by `Toolbox`:
- **Market and company data:** `get_quote`, `get_options`, `get_chart_levels`, `get_fundamentals`, `get_valuation`,
  `get_earnings`, `get_news`, `get_market`, `compare`, `get_assessment`, `screen_stocks`, `lookup_company`,
  `get_price_history`, `get_filings`, `get_financials`.
- **The reader's own data:** `get_my_watchlists` and `get_my_portfolio`.

Full table: `docs/post-demo-ultra/MILO_TOOLS.md`.
- **Validation before anything runs:** unknown tools and extra keys are refused. Tickers must match
  `^[A-Z0-9^][A-Z0-9.\-^=]{0,11}$`, and enums and bounds are checked. Inputs stream eagerly and are validated server
  side.
- **Limits per answer:** 4 model rounds, 10 calls, 30 s per call within a 75 s budget. A repeated call returns its
  first result. Each result is fitted to 12,000 characters.
- **Freshness:** every result carries `meta`: source, as_of, retrieved_at, units, and the delayed, stale, partial
  and unavailable flags.
- **The reader's tools are bound to the session's user** when the toolbox is built. No input names a reader.
  `get_my_portfolio` is offered only from the Brokerage page, or when a turn asks about the reader's own holdings,
  and never with Milo on Market only or No page context. A tool not offered returns `unsupported` (a compromised
  model cannot run it: `tests/test_milo_redteam.py`).
- **Web search** (Anthropic's server tool `web_search_20260209`) is added only when the reader switches it on (at
  most 5 uses). Deep research uses up to 10 searches and no Optic tools.

## Market-data and financial sources

These are the sources the tools and the context read (MILO_TOOLS.md has which tool reads which):
- Yahoo Finance: quotes, history, chains, estimates, statements, headlines. Unlicensed for redistribution (BUG-023,
  BL-09).
- Tradier, when configured.
- SEC EDGAR: submissions and XBRL company facts.
- FRED: the 10-year yield.
- Nasdaq Trader's symbol directory.
- Cboe indices, for dispersion.
- An undocumented Robinhood overnight endpoint, behind `OPTIC_OVERNIGHT_FEED` (BUG-022).

## Citations

- **Source tags:** the model tags a figure with `[[src KEY]]`, the CONTEXT key it came from, and the panel turns
  the tag into a chip that opens that panel (`core/milo-text.js SOURCES`). A figure from a tool is
  `[[src retrieved]]`.
- **Lists under the answer:** "Sources Milo read" lists the research pack's items as they reached the model; a
  separate list shows what the tools retrieved, with each one's time.
- **Web search** results are listed with title and link (`done.citations`).
- **Links the model writes** are shown with their host beside them. Since Phase 12 (MRT-02), a link whose address
  hides its host is shown as plain words.
- The evaluation suite checks every citable key has a chip (`citation_plumbing`).

## Streaming

`POST /api/chat` returns `text/event-stream` (`STREAMING_PIPELINE.md`):
- **Events:** `status` (gathering, thinking, writing, a tool's words), `assumed` (level and horizon), `notice`
  (the policy line, for a declined request), `delta` (text), `retrieved` (tools so far), `attachments` (files
  refused), `amend` (the cleaned answer when a sentence broke the policy), `done` (model, citations, sources,
  retrieved, loaded, named, usage, timing) and `error`.
- **The stream gate:** `ai_policy.StreamGate` holds text back by at most one sentence, so a sentence the output
  check removes never reaches the reader. The whole answer is checked again at the end.

## Error handling

- `_human_error` turns an exception into a fixed sentence plus its class name. No message text, host, path or key
  reaches the reader (Phase 10, SEC-16; re-tested with a fake secret in the exception, `tests/test_milo_redteam.py`).
- A refusal says so. A tool's failure reaches the model as `unavailable` with the class name only, and a timeout
  as `unavailable` with "do not guess the figures".
- A context-gathering failure is an `error` event ("Milo could not gather the figures for this question").
- A history turn that is not a dict no longer ends the stream silently (MRT-08).

## Usage, cost and limits

- **The ledger:** every call goes through `_ask` or `_streamed` and is recorded in `app/ai_store.py`, with input,
  output, cache read and cache write tokens, web searches, the stop reason, and whether the answer was thrown away.
  Prices come from Anthropic's list as read on 2026-10-30: Sonnet 5.5 is $2 input, $2.50 cache write, $0.10 cache
  hit and $10 output per million tokens; Opus 5.5 is $4, $5, $0.20 and $20; web search is $0.01 a search. The
  owner's page is `/api/ai/usage` (owner session or write token only).
- **Measured cost per message:** about $0.11 (COST_AUDIT.md and `app/auth/store.py`, from the live ledger). Not
  re-measured in this phase, since no model can be called here (BL-01).
- **Who may ask:**
  - guests get 401 by default (`GUEST_AI_CALLS_PER_DAY` 0);
  - Free accounts get 3 a day, Pro 15 a day and 100 in 30 days (`PLANS`);
  - every address is capped at 30 an hour (`AI_CALLS_PER_HOUR`);
  - there is a server-wide ceiling of 300 a day (`MILO_QUESTIONS_PER_DAY`, BL-10);
  - the owner is exempt.
- **Provider rate limits** are the Anthropic account's own and are not configured or measured in this repository.

## What changed in this phase, in one place

| Change | Why | Test |
|---|---|---|
| One writing block for every model request | Part 3.4: shared editorial guidance | `tests/test_editorial_standards.py` |
| No browser `vol_event` in the shared framework read; a caller's event is never cached or saved | MRT-01, cross-reader integrity | `tests/test_milo_redteam.py` |
| Server-owned keys dropped from browser context | MRT-05 | same |
| Deep research drops the reader's blocks for a question not about them | MRT-04 | same |
| Account ids kept from the model | MRT-09, minimisation | same |
| Links that hide their host shown as words (v2 and Classic) | MRT-02 | same |
| Classic hides and keeps the previous account's conversations when a device switch fails | MRT-03 | same |
| A malformed history turn ends in an event | MRT-08 | same |
| The request reader and output check widened | Benchmark cases ADV-R09 to R12, MUL-11, INJ-09; sets D and E | `tests/test_ai_policy_requests.py`, `tests/test_milo_eval.py` |
