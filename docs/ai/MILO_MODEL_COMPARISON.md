# Milo: candidate models and how they will be compared

Phase 13 (directive 15, Parts 4 to 6), 2026-11-02.

**No candidate has been evaluated**, so this page ranks none. Directive 15 asks for a ranking "based on completed
evaluations, not reputation", and there are no completed evaluations:
- the Anthropic key on this machine is refused (`401`, BLOCKERS BL-01);
- no other provider's key exists here;
- nothing was bought or signed up for.

What this page has instead:
- the candidates, with facts verified on each provider's own pages;
- the harness that will compare them under the same conditions, and the adaptations each provider needs;
- the method for telling a model's failures from Optic's;
- what running the comparison needs from the owner.

## 1. What Milo needs from a model

From the architecture (`MILO_ARCHITECTURE_AUDIT.md`):

| Requirement | Why | Milo today |
|---|---|---|
| Function calling with JSON-schema tools, several rounds | Milo looks figures up itself: 17 tools, up to 4 rounds and 10 calls an answer | Sonnet 5.5, client tools, results as `tool_result` |
| Prompts of 40,000 to about 90,000 tokens | A ~17,000-token cached prefix, page context up to 60,000 characters, history up to 60,000, tool results up to 12,000 characters each | 1M context |
| Streaming text | The reader sees the answer as it is written; the advice gate holds at most one sentence | SSE through `stream_chat` |
| A reasoning setting | Latency and cost against depth; Milo runs at effort `medium` | adaptive thinking, effort medium |
| Prompt caching | The prefix is about a third of every call | one breakpoint after the system block (C1 would add a second) |
| Data terms fit for readers' data | Questions, page context and, for linked readers, holdings reach the model | Anthropic: no training on API data by default |

## 2. The candidates (facts VERIFIED 2026-11-02 unless marked)

**How the facts were checked.**
- **The research pass:** a background agent read each provider's pages and saved copies.
- **Prices:** every price below was checked against those copies, except Anthropic's. Those were not saved and
  agree with the cost audit's reading of 2026-10-30.
- **Capabilities:** the API notes were checked the same way for OpenAI and Google.
- **Not re-checked:** the open-weight facts marked "research pass".

### Proprietary, higher capability

| Model | Provider, id | Context / max output | Tool calling | Reasoning control | Status |
|---|---|---|---|---|---|
| Claude Fable 5.1 | Anthropic `claude-fable-5-1` | 1M / 128K | yes. Forced `tool_choice` returns 400 | adaptive thinking, always on | active. A Covered Model: 30-day retention, no zero-retention without Anthropic's authorization |
| Claude Opus 5.5 | Anthropic `claude-opus-5-5` | 1M / 128K | yes. Forced `tool_choice` returns 400 | adaptive, effort (default medium) | active. Milo's writers use it today |
| GPT-6 Astra | OpenAI `gpt-6-astra` | 1.05M (922K input) / 128K | yes, Chat Completions and Responses | `reasoning.effort` low to max | listed, not preview |
| Gemini 4 Argon | Google `gemini-4-argon` | 1,048,576 / 65,536 | yes, with parallel calls | thinking low, medium, high | stable. **Prices double on 2026-12-01.** No free tier |

### Proprietary, mid tier

| Model | Provider, id | Context / max output | Tool calling | Reasoning control | Status |
|---|---|---|---|---|---|
| **Claude Sonnet 5.5** (Milo today) | Anthropic `claude-sonnet-5-5` | 1M / 128K | yes. Forced `tool_choice` returns 400 | adaptive. `disabled` is rejected; effort default high, Milo uses medium | active |
| GPT-6.1 Sol | OpenAI `gpt-6.1-sol` | 1.05M (922K) / 128K | **"Tool calling requires the Responses API"** | effort low to max (default medium) | listed |
| GPT-6.1 Terra | OpenAI `gpt-6.1-terra` | 1.05M (922K) / 128K | **Responses API only** for tools | effort none to max (default medium) | listed |
| Gemini 3.8 Flash | Google `gemini-3.8-flash` | 1,048,576 / 65,536 | yes | thinking low, medium, high (`minimal` errors) | stable. **Prices double on 2027-01-01** |

### Proprietary, lightweight

| Model | Provider, id | Context / max output | Tool calling | Reasoning control | Status |
|---|---|---|---|---|---|
| Claude Haiku 5.5 | Anthropic `claude-haiku-5-5` | 1M / 128K | yes | adaptive; effort low to max (default medium) | active. **No server-side refusal fallback.** Prices rise fivefold above 100K-token prompts |
| GPT-6 Luna | OpenAI `gpt-6-luna` | 1.05M (922K) / 128K | Responses API. Chat Completions only with `reasoning_effort: none` | effort none to max | listed |
| Gemini 3.5 Flash-Lite | Google `gemini-3.5-flash-lite` | 1,048,576 / 65,536 | yes | thinking supported (levels not stated) | stable |

### Open weights, hosted per token

| Model | Weights, licence | Size | Context | Hosts and ids | Tool calling | Notes |
|---|---|---|---|---|---|---|
| Kimi K3 | `moonshotai/Kimi-K3`. MIT-style; a separate agreement only for businesses selling model access with over $20M a year of revenue (research pass) | 2.8T total, 104B active (research pass) | 1,048,576 | Together `moonshotai/Kimi-K3`; Fireworks | listed by Together | always reasons; its reasoning must be sent back unchanged each round (model card) |
| GLM-5.3 | `zai-org/GLM-5.3`. MIT-style (research pass) | 743B, 39B active (research pass) | 1,048,575 | Together `zai-org/GLM-5.3` | listed by Together | |
| DeepSeek V4.1 Flash 1017 | `deepseek-ai/DeepSeek-V4.1-Flash-1017`. MIT | 552B backbone, 8B to 16B active (research pass) | 1,000,000 | Together; Fireworks | listed by Together | the card recommends `max_tokens` of 256K or more |
| gpt-oss-120b | `openai/gpt-oss-120b`. Apache-2.0, published Aug 2025 | 120B | 131,072 on Together | Together; Fireworks | listed | the oldest candidate. Its 131K context is tight for Milo's worst-case prompt (about 90K tokens) |

### Self-hosted

Technically possible for every open-weight model above. `MILO_COST_ANALYSIS.md` section 6 shows it costs more than
any hosted option at every scale considered: one GPU running all the time costs $5,840 a month. It is therefore not
a candidate before Optic is far larger.

### Looked at and left out

| Model | Why |
|---|---|
| Gemini 3.1 Pro | preview only (`gemini-3.1-pro-preview`) |
| Meta Muse Spark Open | its model card is gated (HTTP 401), so its licence could not be read |
| Groq-hosted models | Groq's pricing page redirected to its home page, so there is no verified price |

## 3. Same conditions for every model

`tests/milo_eval/compare.py` runs every model through one loop, and `providers.py` translates.

**What is the same for every model:**
- **The request:** Optic's own (`ai.build_chat_request`). That is the same system prompt, writing rules, advice
  policy, level and horizon blocks, page context and history, on the same benchmark case and fixtures.
- **The tools:** offered by production's rule (`main._milo_toolbox`): the same 16 or 17 definitions. Every call is
  validated and run by Optic's own toolbox on the fixtures, with the same limits (4 rounds, 10 calls, 30 s a call).
  No benchmark case turns web search on, so no model gets a tool another lacks.
- **The output cap:** production's 8,000 tokens, reasoning included, in each provider's own field.
- **The finished answer** goes through the advice policy's output check, as in production. The row keeps both the
  raw text (the model's behaviour) and the shown text (what a reader would see).
- **The checks:** the same answer checks with the same severities (`MILO_ACCEPTABLE_ERROR_POLICY.md`), on a fixed
  split. The criteria hash is written into every run, so a change of criteria after a result is visible.
- **The record:** usage in one convention (all prompt tokens, cached and written apart, output with reasoning), cost
  from `prices.json`, time per round, tool calls with their status, and the stop reason of each round.

**Adaptations, each because a provider requires it** (directive 15 Part 6: "Do not disadvantage a candidate through
an incompatible tool format"):

| Provider | Adaptation | Why |
|---|---|---|
| Anthropic | none, except that Haiku 5.5 is sent no `fallbacks` or fallback beta | Haiku 5.5 has no server-side fallback (Claude API reference). Sending one could fail the request for a reason that is not the model's |
| OpenAI | the Responses API (`provider openai`), stateless (`store: false`), every output item sent back, encrypted reasoning included | tool calls need it on Sol and Terra, and on Luna with reasoning. OpenAI's reasoning guide says reasoning items "must also be passed back with tool call outputs". Stateless keeps nothing at OpenAI beyond its abuse logs |
| OpenAI | the system prompt as a developer message, with an explicit cache breakpoint after the block production caches | the documented way to cache reusable instructions ("Top-level `instructions` cannot contain an explicit breakpoint") |
| Google | tools as `functionDeclarations` with the schema keys Gemini accepts; the model's parts sent back unchanged | Gemini's schema dialect is a subset of JSON Schema. Thought signatures live inside parts and "are required to maintain reasoning continuity across multi-turn interactions" (thinking guide). Arguments are validated against Optic's full schema anyway |
| Open-weight hosts | Chat Completions; the assistant turn sent back with its `reasoning_content` | Kimi K3's card requires each assistant message, reasoning included, to be sent back unchanged |
| All | the reasoning setting is each provider's own, mapped to Milo's `medium` | `reasoning.effort` for OpenAI, `thinkingConfig` for Gemini, `reasoning_effort` on the hosts. Anthropic's `thinking` block is not sent elsewhere |
| DeepSeek V4.1 Flash | run at production's cap and at its card's recommendation, both reported | an 8,000-token cap could cut its reasoning short. The stop reason shows it |

**What is not equal, and is said so:**
- **Tokenizers differ,** so the same text bills differently on each provider. The cost model gives every provider
  the same counts, and the harness records each provider's own.
- **The harness does not stream.** Production does, and time to first text is measured only on Anthropic's streamed
  path (`run_model.py`). Total time is measured for every provider.
- **Milo's prompts were written for Claude** over months of review. A model that needs different prompting is tested
  first on the prompt as it is. Any change made for one model is recorded as that model's adaptation, and the
  baseline is rerun with the change, so a prompt fix is not credited to the model.

## 4. Telling a model's failures from Optic's

A failed check is first classified by what the model was given. The row has everything needed: the context, every
tool call with its status and result, and the checks with their details.

| A failure is | When | Example |
|---|---|---|
| **Optic's** (retrieval, tools, prompt) | the evidence the answer needed was not offered, or a tool returned an error or a stale flag the model then reported correctly | a figure the fixtures lack; a tool timing out |
| **Optic's** (the check) | the answer is right and the check is wrong. A person reads it, and the check is fixed for every model before any result is compared | a grounding check missing a rounded figure |
| **The model's** | the evidence was in the context or the tool results and the answer misused it, invented something, or broke an instruction | a price not in the quote result; a sentence that decides for the reader |
| **Shared** | every model fails the same case the same way | treated as Optic's until shown otherwise |

The request level is already measured, and it is Optic's own part: **181 of 181 cases and 1,231 of 1,231 checks
pass** (Phase 12). Any answer-level failure therefore starts from a known-good request.

## 5. Results

**None.** No candidate answered a question.

The four results the directive asks for (best-performing, lowest-cost qualifying, best quality for cost, and a
ranking) cannot be given. Any ranking here would rest on reputation, which the directive rules out.

## 6. What running the comparison needs

1. **A working Anthropic key** (BL-01), for the Sonnet 5.5 baseline. That is $48 to $69 for the benchmark at three
   trials.
2. **Approval of a budget** for the candidates (cost analysis, section 8). A first round of the five cheaper
   candidates costs about $80 to $85 on top of the baseline, and the runner stops at its cap.
3. **Accounts and keys** at OpenAI, Google and Together or Fireworks. They are the owner's to open, and no purchase
   or sign-up was made in this phase.
4. **Evaluation uses only the benchmark's synthetic fixtures,** with no reader's data. Before any provider other
   than Anthropic could serve readers:
   - its terms need review against Optic's Privacy Policy, which would have to name it as a processor (counsel,
     BL-02);
   - its retention settings need setting (below).
5. **People's time** to read samples of the advice and injection answers and to score clarity. Subjective scores
   are never left to a judge model alone (directive 15 Part 4).

### Data handling, for when readers' data is involved

| Provider | Training on API data | Retention | Zero retention |
|---|---|---|---|
| Anthropic (research pass, not re-checked) | not by default | the privacy centre says inputs and outputs are deleted within 30 days; the API's data-retention page says content is not retained by default except for Covered Models. **Which applies is to confirm with Anthropic.** Flagged content can be kept up to 2 years. Fable 5.1 requires 30-day retention | by arrangement with Anthropic, per organisation |
| OpenAI | not since 2023-03-01 unless opted in | abuse-monitoring logs up to 30 days. The Responses API stores state 30 days unless `store: false` | needs OpenAI's approval |
| Google (paid tier) | not used to improve products | **AI Studio logging is on by default for projects created on or after 2026-10-26, kept up to 55 days**. Search grounding keeps prompts and output 30 days | Google points to Vertex AI for guaranteed zero retention |
| Together | research pass, not re-checked: stores prompts and responses by default, may use them for product improvement, training opt-in | | an admin setting |
| Fireworks | no storage for open models without an opt-in (checked) | Responses API with `store=True` keeps data up to 30 days | the default for open models |

**A new Google project would log every request** for up to 55 days unless logging is turned off first. That
matters for any project made to evaluate Gemini, even on synthetic data, and decides whether it could ever carry
readers' data.
