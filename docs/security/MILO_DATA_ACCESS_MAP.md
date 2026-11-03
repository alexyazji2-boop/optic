# Milo: data access map

Phase 12 (directive 14, Part 5), 2026-11-02. Every pathway by which Milo reads, searches or sends data. This was
built from the code, with an independent read-only review checked line by line against it, and tested in
`tests/test_milo_redteam.py` and `tests/milo_eval/`. File references are to branch `phase-12-writing-milo-security`.
Earlier maps that this one extends: `docs/post-demo-ultra/DATA_PATHWAYS.md` and `MILO_TOOLS.md`.

## 1. The pathways

Read each row as: reader → Milo → tool or API → data store → authorization check → response → model context.

| # | Entry | What is read | Store or provider | Authorization check | Into the model's context |
|---|---|---|---|---|---|
| P1 | `POST /api/chat` page context | The page's computed figures, as the browser sends them | The browser | None needed: it is the reader's own page. Server-owned keys are stripped (`main._SERVER_KEYS`, MRT-05). The reader's own blocks go only with a question about them (`_personal_blocks_for`) | As CONTEXT, budgeted to 60,000 characters |
| P2 | Chat, server additions | `question_named`, `auto_loaded`, `screen_candidates`, `market`, `research`, `framework`, `chart_levels` | Optic's own computations over public data; the daily brief, shared by everyone | None needed: public data only. The shared framework read no longer takes any browser input (MRT-01) | As CONTEXT |
| P3 | Chat, the linked brokerage | `brokerage_portfolio`: connections (institution, status), accounts (name, institution, type, currency), holdings (symbol, description, quantity, price, value, weight, sector), Optic's calculations, caveats | The accounts database (`app/brokerage/store.py`), SnapTrade or the sandbox, sealed per user with AES-256-GCM | The session's user (`auth_deps.current_user`). `brokerage_scope` intersected with the user's own accounts (`brokerage/service.py:902-913`). Only from the Brokerage page or for a question about their own holdings, never on Market only or No page context | As CONTEXT; the scope ids themselves are removed (MRT-09) |
| P4 | Tool `get_my_portfolio` (7 parts) | Summary, exposure, events (with the reader's saved theses), performance, scorecard, options risk, briefing | As P3, plus Yahoo for prices and calendars | Bound to the session's user when the toolbox is built. No input names a reader; extra keys are refused. Offered under P3's rule, otherwise `unsupported` | As a tool result, at most 12,000 characters |
| P5 | Tool `get_my_watchlists` | The reader's saved lists (name, symbols) | Accounts database `watchlists` | The session's user; a guest gets `signed_in: false`; a failed lookup returns `unavailable` | As a tool result |
| P6 | Tools on public data (15) | Quotes, chains, levels, fundamentals, valuation, earnings, news, the market, compare, the framework, screener, the symbol directory, history, filings, financials | Yahoo Finance, Tradier, SEC EDGAR, FRED, Nasdaq Trader, Optic's caches | Ticker regex, enums and bounds before any fetch. No URL or path input, so no SSRF or traversal | As tool results |
| P7 | Web search (the reader's switch) | Search results the model asks for | Anthropic's server-side web search | The reader turns it on per conversation. The model writes the query | As server tool results, the text treated as data |
| P8 | `POST /api/research` (deep research) | The page context and up to 10 web searches | The browser and Anthropic's web search | Linked keys and server-owned keys stripped. The reader's own blocks stripped unless the question is about them (MRT-04) | Into the research prompt |
| P9 | Attachments | Images and PDFs the reader attaches | The browser, in the request only | Type checked by the file's own bytes; 4 files, 5 MB each; never written to disk | As image and document blocks |
| P10 | Conversation history | Earlier turns of this conversation | The browser (localStorage); not stored on the server | v2: `core/device.js holds()`, so another account's history is not shown. Classic: the same since MRT-03 | As messages, the last 24 turns and 60,000 characters |
| P11 | Preferences | Level, horizon, persona | The browser (and the account, for the level) | Normalised to known values; an unknown value falls back | Selects instruction blocks; no data |

## 2. What leaves Optic's server

| Destination | What is sent | When | Notes |
|---|---|---|---|
| Anthropic (Messages API) | System prompt, CONTEXT (P1 to P3), history, attachments, tool results | Every Milo answer, deep research and AI writer | The reader's brokerage block only under P3's rule. No account numbers, masks, provider ids, email or name. Since MRT-09, no account ids in CONTEXT. One exception remains: the performance part's internal account ids and the broker's own description of an unvalued transfer (`brokerage/performance.py`, see section 4) |
| Anthropic's web search | The query the model writes | Only with web search on | A query is model-written, so an injected instruction could put context words into it. The search provider sees it; no attacker endpoint does |
| The reader's browser | The answer stream and its sources | Every answer | Rendered with escaping; no images; links only http(s), with their host shown, and refused when the address hides its host (MRT-02) |
| Logs | Exception class names, timing, policy removals (rule names and counts) | Server side | Never the question, the answer, tool results or attachments (`ai.py`, `main.py` chat path). One-time tokens are blanked in the access log (SEC-02) |
| Feedback ("Report a problem") | The question (300 characters), about 1,600 characters of the answer, and the reporter's email | Only when the reader sends a report | To the feedback table and by SMTP to the owner. The form says what goes |
| Analytics | Nothing | | No analytics script on either app (ANALYTICS_REVIEW.md: designed, not built) |

## 3. Data classification

| Class | Examples | Milo needs it? | Controls |
|---|---|---|---|
| Public market data | Quotes, bars, chains, headlines | Yes | Freshness and source on every result |
| Licensed financial data | Yahoo Finance (unlicensed for redistribution: BUG-023), Cboe | Yes, as today | Counsel's and the owner's decision (BL-09) |
| Internal application data | The research pack, the framework, signals, the daily brief | Yes | Server-built only; browser copies dropped (MRT-05) |
| Reader preferences | Level, horizon, persona | Yes, as instructions | Normalised |
| Conversation history | The thread | Yes, the thread itself | Browser-held, per device holder |
| Personal information | Email, name | No | Never in a model request (checked in the brokerage block) |
| Brokerage account information | Institution, account name and type | Partly: name and type label the figures | No numbers, masks or provider ids; scope ids removed (MRT-09) |
| Portfolio holdings | Symbols, quantities, values, weights | Only for a question about them | P3's rule, on the server, not in the prompt |
| Access tokens and API keys | Anthropic, SnapTrade, Stripe, the write token | No | Environment only; never in prompts, streams or errors (tested with fake secrets) |
| Internal configuration | Plan limits, flags | No | Not in prompts |
| Confidential system instructions | The system prompt | The model, not the reader | Milo declines to recite it (eval INJ-04). It is not a secret control: nothing in it is a credential |

## 4. Authorization boundaries, checked (Part 5.3)

| Check | Result | Evidence |
|---|---|---|
| User authentication | Request-scoped session from a hashed token, expiry enforced in SQL, 90-day absolute limit | `app/auth/deps.py:28-58`, `auth/store.py:236-249` |
| Tenant (reader) isolation | Every query of a reader's data is scoped by the session's user id; Phase 10's pass over 236 routes found no IDOR | SECURITY_REVIEW.md; the brokerage store and service |
| Row-level security | SQLite has none; scoping is in each query (`WHERE user_id = ?`). Foreign keys are on per connection | `app/db.py _connect` |
| Server-side permission checks for Milo's tools | Reader tools are bound to the session's user at toolbox construction; offered by rule; a tool not offered is `unsupported` | `main._milo_toolbox`, `milo_tools.Toolbox.run` |
| Document access controls | No document store. Saved research, theses and journals are per user. Milo reads theses only through P4 | |
| Tool input validation | Strict schemas, extra keys refused, regex and enums, before any fetch | `milo_tools.validate`; red team tests |
| Database query scoping | Parameterised SQL everywhere; no model-written SQL | Phase 10 review |
| Session isolation | No module state keyed without the user id in the chat path. The workspace caches are keyed by user id; the other caches hold public data | review of `brokerage/workspace.py:120,320,507` and the research, brief and ai caches |
| API token scope | The write token and the admin session gate the owner's routes; `/api/ai/usage` is owner-only | `main.py:6307-6320, 7793-7838` |
| Retrieval result filtering | Retrieval reads public data or the session's own rows; there is no shared index to filter | |

**Not enforced by the model:** every check above is server code. The prompt's rules (data is never an instruction;
describe holdings, never act on them) are a second line, not the control.

## 5. Remaining minimisation gaps (owner decisions, see the red team report)

- **The performance part** (`get_my_portfolio` `performance`) sends Optic's internal account ids, and the broker's
  description of a transfer it could not value. Whether those descriptions can contain account numbers depends on
  the broker; it is unconfirmed with real data (BL-03).
- **Sign-out keeps the last account's things on the device**, in plain localStorage, Milo conversations included.
  This is by design, so they come back at the next sign-in (MRT-06). A shared computer shows them to anyone who
  opens the browser's storage, not to another Optic account.
- **Tools write shared first-of-the-day rows** (IV history, the signal archive) from model-chosen inputs. Anyone can
  already do the same without Milo, through `/api/ticker/{t}?expiries=` (MRT-07).
