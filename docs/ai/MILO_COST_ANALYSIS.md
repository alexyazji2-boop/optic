# Milo: what a question costs, by model, and what Milo costs a month

Phase 13 (directive 15, Part 7), 2026-11-02. This is a **cost model, not a measured bill**. No model answered a
question in this phase: the Anthropic key on this machine is refused (`401`, BLOCKERS BL-01) and no other provider's
key exists here. Every dollar figure below comes from three inputs, each labelled where it is used: what Optic sends
(measured from the code), the shape of an answer (assumptions, from the 2026-10-30 cost audit), and list prices
(read from each provider's page on 2026-11-02).

**What this page cannot do yet.** It cannot set cost against quality, because no model's quality has been measured on
Milo's benchmark. It therefore cannot name the cheapest model that meets each workload's standard. Section 8 says
how that will be found, and what finding it costs.

```bash
.venv/bin/python -m tests.milo_eval.cost_model --budget   # docs/ai/eval-results/cost-model/cost-model.json, 6 s, no network
.venv/bin/python -m tests.milo_eval.router                # docs/ai/eval-results/routing/routing.json
.venv/bin/python -m pytest -q tests/test_milo_cost_model.py
```

**The check on the arithmetic.** Given the cost audit's prefix size (16,300 tokens), the model reproduces the audit's
own figures for Sonnet 5.5:
- per question: $0.14 warm, $0.18 cold, $0.10 with the CONTEXT turn cached (C1);
- per month: $89.76, $802, $1,159 and $7,109 at 100, 1,000 and 10,000 MAU (at the ceiling and with demand served).

`tests/test_milo_cost_model.py` holds both to within 1%.

## 1. Inputs

### 1.1 What Optic sends (MEASURED from the code)

| Part | Characters | Tokens (ASSUMPTION: 4 characters a token for prose, 3.5 for JSON, the audit's ratios) |
|---|---:|---:|
| Cached system block: `SYSTEM_PROMPT` + `FORMAT_PROMPT` + `WRITING_RULES` + `POLICY_TEXT` | 53,743 | 13,436 |
| Tool definitions as streamed, 16 (17 with `get_my_portfolio`) | 10,895 (12,288) | 3,113 (3,511) |
| Anthropic's tool-use system prompt (pricing page) | | 286 |
| **Cached prefix** | | **16,835** (17,233 with the portfolio tool) |

- **Phase 12's prompt changes** (the writing rules, 1,949 characters, and edits to the format rules) added 2,134
  characters, about 535 tokens, to every question's prefix: about $0.0014 a cold question on Sonnet 5.5 and $0.0001
  a warm one.
- **The benchmark's requests** (fixtures, measured) are a median of 68,412 characters, from 66,201 to 83,981.
  Production pages send more context than the fixtures do, which is why the shapes below use the audit's production
  sizes.

**The token ratio is the largest single uncertainty.**
- **No tokenizer is reachable here.** Token counting is free on Anthropic's API but needs a working key.
- **Tokenizers differ.** Anthropic's page says Claude 4.7 and later produce about 30% more tokens than earlier Claude
  models for the same text, and other providers count differently again. This model gives every provider the same
  counts, so **a cost difference under about 30% between providers is inside the uncertainty.**
- **The one measurement does not settle it.** On 2026-10-11, each of six chat calls wrote about 11,700 tokens to the
  cache (`~/Optic/work/analysis-2026-10-11/MEASURED.md`). The cached block then live (`767e8fa`) was 17,263 to
  19,640 characters, which is 1.5 to 1.7 characters a token if nothing else was cached. If the reader had web search
  switched on, the search tool's own instructions sit in that prefix too, and their size is not documented in what
  was read. Section 4 shows the figures at 3 and at 1.7 characters a token.

### 1.2 The shape of an answer (ASSUMPTION)

The audit's typical Dossier question and its light question, plus three variants that each change one thing. The
shape a workload takes follows the tools its benchmark cases need.

| Shape | Workloads | Model calls | Page context | History | Tool results per round | Answer's output |
|---|---|---:|---:|---:|---|---:|
| light | W1 definitions, W9 help | 1 | 2,300 | 0 | none | 1,000 |
| typical | W2, W3, W4, W5, W10, S1, S2 | 2.5 (a third call half the time) | 15,700 | 1,000 | 3,400, then 1,700 | 2,000 |
| thread | W8 follow-ups | 2.5 | 15,700 | 4,000 | 3,400, then 1,700 | 2,000 |
| portfolio | W6 | 2.5, with 17 tools | 19,700 | 1,000 | 3,400, then 1,700 | 2,000 |
| research | W7 multi-source | 3.5 | 15,700 | 1,000 | 3,400, 3,400, then 1,700 | 2,500 |

The same for every shape (the audit's figures):
- 500 tokens of level, horizon, framework and lens blocks after the breakpoint;
- a 50-token question;
- 800 tokens of assistant content (thinking and tool calls) carried into each later round and billed as input;
- 800 output tokens on a round that only calls tools.

**Output includes reasoning.** Every provider here bills reasoning as output: Anthropic's thinking, OpenAI's reasoning
tokens, and Gemini's thinking, which Gemini reports apart from its output (thinking guide, 2026-11-02). The harness
records each provider's own figure.

### 1.3 Prices (VERIFIED on each provider's page, 2026-11-02)

Per million tokens, standard tier, global routing. Sources are in `tests/milo_eval/prices.json`.
- **OpenAI, Google, Together and Fireworks:** every price was checked against the copies of their pages that the
  research pass saved.
- **Anthropic:** these are the research pass's reading of the pricing page, which agrees with the cost audit's
  reading of 2026-10-30.

| Provider | Model | Input | Cached input | Cache write | Output | Notes |
|---|---|---:|---:|---:|---:|---|
| Anthropic | `claude-fable-5-1` | $10 | $0.25 | $12.50 | $50 | 1M context; Covered Model (30-day retention, no ZDR unless Anthropic authorizes it) |
| Anthropic | `claude-opus-5-5` | $4 | $0.20 | $5 | $20 | Milo's writers today |
| Anthropic | `claude-sonnet-5-5` | $2 | $0.10 | $2.50 | $10 | **Milo today** |
| Anthropic | `claude-haiku-5-5` | $0.10 | $0.01 | $0.125 | $0.50 | to 100K-token prompts; above it $0.50 / $0.05 / $0.625 / $2.50 |
| OpenAI | `gpt-6-astra` | $10 | $1.00 | $12.50 | $50 | over 272K input tokens: 2x input and cache, 1.5x output |
| OpenAI | `gpt-6.1-sol` | $2 | $0.10 | $2.50 | $10 | tool calls need the Responses API |
| OpenAI | `gpt-6.1-terra` | $1 | $0.05 | $1.25 | $5 | tool calls need the Responses API |
| OpenAI | `gpt-6-luna` | $0.10 | $0.01 | $0.125 | $0.50 | function calling in Chat Completions only with reasoning off |
| Google | `gemini-4-argon` | $2 (**$4 from 2026-12-01**) | $0.10 ($0.20) | none listed | $10 ($20) | implicit caching only |
| Google | `gemini-3.8-flash` | $0.75 (**$1.50 from 2027-01-01**) | $0.075 ($0.15) | none listed | $3.75 ($7.50) | |
| Google | `gemini-3.5-flash-lite` | $0.30 | $0.03 | none listed | $2.50 | |
| Together | `moonshotai/Kimi-K3` (open weights) | $3 | $0.30 | none listed | $15 | Fireworks lists the same |
| Together | `zai-org/GLM-5.3` (open weights) | $1.40 | $0.26 | none listed | $4.40 | |
| Together | `deepseek-ai/DeepSeek-V4.1-Flash-1017` (open weights) | $0.30 | $0.006 | none listed | $1.20 | Fireworks lists the same |
| Fireworks | `gpt-oss-120b` (open weights, Aug 2025) | $0.15 | $0.015 | none listed | $0.60 | |

- **Planning date.** The monthly figures use the prices in force on **2027-01-01**, the earliest a change of model
  could reach readers after an evaluation, the owner's approval and a privacy review. That doubles both Gemini
  models' prices. At today's prices, Gemini 4 Argon would be $480 a month at 1,000 MAU, against $959 from the
  planning date.
- **One conflict, resolved.** The Claude API reference bundled with Claude Code lists Sonnet 5.5's cache read at
  $0.20. Anthropic's pricing page says $0.10 (0.05x input), as it did on 2026-10-30. The page is used.

### 1.4 Volume (the cost audit's assumptions A3 to A5, unchanged)

- 10% of monthly actives ask Milo on a given day, 2 questions each, over 30.4 days.
- Chat is 85% of what is asked. The rest is deep research, scan requests, earnings briefs and portfolio briefings,
  which this page does not re-price; the audit's figures for them stand.
- The server-wide ceiling of 300 questions a day (`MILO_QUESTIONS_PER_DAY`) applies unless a row says "demand
  served".
- This gives 517, 5,168 and 7,752 chat questions a month at 100, 1,000 and 10,000 MAU (51,680 with demand served).

**The mix of chat questions (ASSUMPTION; there is no traffic to count).** The ledger records whether a request was
chat or research, not what was asked. This is a product guess, set before any model was priced:

| W1 | W2 | W3 | W4 | W5 | W6 | W7 | W8 | W9 | W10 | S1 | S2 |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 12% | 20% | 10% | 10% | 12% | 6% | 6% | 12% | 4% | 2% | 5% | 1% |

**Repeated answers (ASSUMPTION): 2% of answers are paid twice.** That covers a stream cut and asked again, a refusal
re-run under the fallback model, and a server error after partial output. It is not measured: the ledger skips a
round the reader cancels (COST_AUDIT C2). A request that fails before generating anything is not billed by these
providers; the client's own retries of 429s and 5xx responses cost nothing.

### 1.5 How each provider's cache is billed (VERIFIED rules; the warm share is an ASSUMPTION)

| Rule | Who | What is cached | Write | Life |
|---|---|---|---|---|
| explicit | Anthropic | only up to a breakpoint the request places. **Optic places one, after the system block**, so the page context is paid at the full price on every tool round | 1.25x input | 5 minutes, renewed on each hit |
| implicit-latest | OpenAI GPT-5.6 and later | the provider writes through the latest message on its own, and the harness adds an explicit breakpoint after the system block, as production has. Every round reads what the round before it sent | 1.25x input | 30 minutes minimum |
| implicit | Google; Together and Fireworks | any repeated prefix, read at the cached price. Gemini 4 reprocesses the last 2,050 tokens when a round adds fewer than that; Milo's rounds add 2,500 to 4,200 | none listed | not stated, so given Anthropic's 5 minutes here |

- **The warm share** is the chance a question's first call finds the prefix cached. It is the audit's Poisson
  estimate: arrivals over 14 active hours, one cache life of memory, 1.5 prefix variants (web search on or off, the
  portfolio tool or not).
- **On Anthropic models** that gives 8% at 100 MAU, 55% at 1,000 and 70% at the ceiling. OpenAI's 30-minute minimum
  raises its warm share to 99% at 1,000 MAU.

## 2. Cost per question and per month, by model

Milo chat only, at the planning date's prices, with the 2% repeat allowance in the monthly columns. "Warm" means the
prefix is already cached.

| Model | Cache | W1 light, warm | Typical (W2), cold / warm | W6 portfolio, warm | W7 research, warm | Average question at 1,000 MAU | 100 MAU | 1,000 MAU | 10,000 at the ceiling | 10,000, demand served |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `claude-fable-5-1` | explicit | $0.083 | $0.884 / $0.677 | $0.778 | $1.024 | $0.726 | $426 | $3,750 | $5,383 | $32,579 |
| `claude-opus-5-5` | explicit | $0.035 | $0.356 / $0.275 | $0.315 | $0.415 | $0.293 | $172 | $1,517 | $2,180 | $13,238 |
| **`claude-sonnet-5-5`** (today) | explicit | $0.017 | $0.178 / $0.138 | $0.158 | $0.208 | $0.147 | **$86** | **$758** | **$1,090** | **$6,619** |
| `claude-haiku-5-5` | explicit | $0.001 | $0.009 / $0.007 | $0.008 | $0.011 | $0.007 | $4 | $39 | $56 | $341 |
| `gpt-6-astra` | implicit-latest | $0.102 | $0.707 / $0.514 | $0.571 | $0.672 | $0.477 | $309 | $2,465 | $3,685 | $24,561 |
| `gpt-6.1-sol` | implicit-latest | $0.019 | $0.136 / $0.096 | $0.106 | $0.123 | $0.089 | $59 | $459 | $686 | $4,570 |
| `gpt-6.1-terra` | implicit-latest | $0.009 | $0.068 / $0.048 | $0.053 | $0.062 | $0.044 | $29 | $229 | $343 | $2,285 |
| `gpt-6-luna` | implicit-latest | $0.001 | $0.007 / $0.005 | $0.006 | $0.007 | $0.005 | $3 | $25 | $37 | $246 |
| `gemini-4-argon` | implicit | $0.035 | $0.233 / $0.169 | $0.186 | $0.220 | $0.186 | $112 | $959 | $1,364 | $8,067 |
| `gemini-3.8-flash` | implicit | $0.014 | $0.091 / $0.069 | $0.076 | $0.091 | $0.074 | $44 | $382 | $547 | $3,282 |
| `gemini-3.5-flash-lite` | implicit | $0.004 | $0.021 / $0.017 | $0.018 | $0.023 | $0.018 | $10 | $92 | $133 | $811 |
| `moonshotai/Kimi-K3` | implicit | $0.029 | $0.183 / $0.137 | $0.151 | $0.181 | $0.148 | $88 | $765 | $1,094 | $6,564 |
| `zai-org/GLM-5.3` | implicit | $0.013 | $0.083 / $0.064 | $0.071 | $0.086 | $0.068 | $40 | $353 | $507 | $3,073 |
| `deepseek-ai/DeepSeek-V4.1-Flash-1017` | implicit | $0.002 | $0.016 / $0.011 | $0.012 | $0.014 | $0.013 | $8 | $65 | $91 | $528 |
| `gpt-oss-120b` (Fireworks) | implicit | $0.001 | $0.009 / $0.006 | $0.007 | $0.008 | $0.007 | $4 | $36 | $51 | $305 |

**With the CONTEXT turn cached (C1), Anthropic's models only:**

| Model | Typical, warm | Average at 1,000 MAU | 100 MAU | 1,000 MAU | 10,000 at the ceiling | 10,000, demand served |
|---|---:|---:|---:|---:|---:|---:|
| `claude-fable-5-1` | $0.461 | $0.521 | $320 | $2,692 | $3,796 | $21,998 |
| `claude-opus-5-5` | $0.192 | $0.214 | $131 | $1,107 | $1,566 | $9,141 |
| **`claude-sonnet-5-5`** | $0.096 | $0.107 | **$65** | **$553** | **$783** | **$4,571** |
| `claude-haiku-5-5` | $0.005 | $0.006 | $3 | $29 | $42 | $246 |

**What the table says:**
1. **Sonnet 5.5 and GPT-6.1 Sol have the same list prices**, yet a typical question costs $0.138 on one and $0.096 on
   the other. The whole difference is caching. OpenAI caches through the latest message on its own, while Optic's
   Anthropic request caches only the system block. With C1, Sonnet 5.5 costs $0.096 too. The rest of Sol's lower
   monthly figure comes from OpenAI's 30-minute cache life. **This is Optic's to fix (C1), not a reason to change
   provider.**
2. **The small models are 12 to 28 times cheaper per question** than Sonnet 5.5 as built: Haiku 5.5 ($0.007), GPT-6
   Luna ($0.005), DeepSeek V4.1 Flash ($0.011) and gpt-oss-120b ($0.006). That is the saving at stake if one of them
   meets the standard, which is unmeasured.
3. **The flagships cost 1.2 to 5 times Sonnet 5.5** per question: Gemini 4 Argon $0.169 from December, Opus 5.5
   $0.275, GPT-6 Astra $0.514, Fable 5.1 $0.677.
4. **At every scale, Milo chat on Sonnet 5.5 costs less than the market-data licence the owner is weighing** ($2,049
   to $2,399 a month), except with demand served at 10,000 MAU.

**Where chat sits in the whole bill** (the audit's 1,000-MAU totals, otherwise unchanged):
- **Model spend in all:** $981 a month. Chat is $802 of it in the audit, $758 here. The difference is the mix: the
  audit priced every chat question as a typical one, and the 16% light questions here cost far less.
- **Other model calls:** deep research $102, the other Milo kinds $15, scheduled writers $30, and sector and catalyst
  reads $31.
- **Everything that is not a model:** $172 to $198.

## 3. Cost per completed task, by part

What a typical Sonnet 5.5 question pays for, warm, as built:
- **Input:** 50,675 fresh input tokens across 2.5 calls, mostly the page context paid again on each round: $0.101.
- **Cached input:** 42,088 tokens, which is the prefix read on each call: $0.004.
- **Output:** 3,200 tokens, thinking included: $0.032.
- **Repeats:** 2% of answers.

C1 turns the fresh input into cache reads and writes, which is where its 27% saving comes from.

| Part | Included | Where it comes from |
|---|---|---|
| Input tokens, fresh | yes | the shapes in section 1.2 |
| Cached tokens, read and written | yes | each provider's rule, section 1.5 |
| Output and reasoning tokens | yes | billed as output by every provider here |
| Tool calls | yes: the extra rounds, and the tool results billed as input | Optic's tools call Optic's own data (Yahoo, SEC, Treasury). That costs nothing per call as built, and a licensed-data plan is a fixed monthly fee whatever the model |
| Web search | no: the ledger measured none | $10 per 1,000 searches at Anthropic and OpenAI, $14 per 1,000 at Google after 5,000 free a month, plus the results billed as input. Two searches add about $0.02 and 5,000 input tokens to a question. Toggling search on Anthropic also re-writes the cached prefix (prompt-caching page) |
| Retries and failed requests | 2% of answers repeated | section 1.4 |
| Infrastructure | unchanged by the choice of a hosted model | Railway etc., COST_AUDIT section 8: $14 to $107 a month |
| External data providers | unchanged by the model | a model that calls more tools sends more requests to Yahoo's 2-a-second budget. The harness records tool calls per answer, model by model |

## 4. How far the conclusions move with the assumptions

Milo chat per month at 1,000 MAU:

| Case | Sonnet 5.5 as built | with C1 | Haiku 5.5 | GPT-6.1 Sol | light questions to Haiku 5.5, perfect router |
|---|---:|---:|---:|---:|---:|
| Central case | $758 | $553 (-27%) | $39 (20x cheaper) | $459 (-39%) | $741 (-2%) |
| A token is 3 characters, not 4 (input x1.33) | $953 | $681 (-29%) | $49 (20x cheaper) | $555 (-42%) | $934 (-2%) |
| A token is 1.7 characters (input x2.35) | $1,550 | $1,071 (-31%) | $99 (16x cheaper) | $850 (-45%) | $1,522 (-2%) |
| Answers 50% longer (thinking included) | $808 | $603 (-25%) | $41 (20x cheaper) | $508 (-37%) | $787 (-3%) |
| Light questions twice as common (32%) | $650 | $485 (-25%) | $33 (20x cheaper) | $391 (-40%) | $613 (-6%) |
| Light questions half as common (8%) | $813 | $588 (-28%) | $42 (20x cheaper) | $493 (-39%) | $805 (-1%) |
| No repeated answers | $743 | $543 (-27%) | $38 (20x cheaper) | $450 (-39%) | $727 (-2%) |
| 5% of answers paid twice | $781 | $570 (-27%) | $40 (20x cheaper) | $472 (-39%) | $763 (-2%) |

**What holds in every case:**
- C1 saves 25% to 31%.
- Routing only the light questions saves 1% to 6%.
- The small models are 16 to 20 times cheaper.

The absolute figures move up to twofold with the token ratio. **Read the dollar amounts as a range and the ratios as
the finding.**

## 5. Peak concurrency and rate limits

Assumptions:
- 15% of a day's questions arrive in the busiest hour, around the market open (ASSUMPTION);
- an answer takes 20 seconds from send to done (ASSUMPTION; the stand-in measured 0.65 s of Optic's own work, and a
  model adds its own time);
- 2.5 model calls per answer.

| | Questions a day | Peak hour | Answers in flight, peak hour average | Model calls a minute at peak | Fresh input tokens a minute at peak (as built) |
|---|---:|---:|---:|---:|---:|
| 100 MAU | 20 | 3 | 0.02 | 0.1 | about 2,500 |
| 1,000 MAU | 200 | 30 | 0.17 | 1.3 | about 25,000 |
| 10,000 MAU at the ceiling | 300 | 45 | 0.25 | 1.9 | about 38,000 |
| 10,000 MAU, demand served | 2,000 | 300 | 1.7 | 12.5 | about 250,000 |

- **Rate limits do not bind.** Anthropic's Start tier allows 1,000 requests and 2,000,000 input tokens a minute on
  Sonnet 5.5, and cache reads do not count toward input limits (COST_AUDIT section 2). Bursts of several times the
  hourly average still fit.
- **What binds first** is the organisation's monthly spend cap ($500 on Start, $1,000 on Build), then the server's
  300-a-day ceiling (COST_AUDIT section 9).
- For a self-hosted model, the same figures size the deployment: a few answers in flight at 10,000 MAU, each with a
  prompt of about 40,000 tokens.

## 6. Open-weight models: hosted per token, or self-hosted

**Hosted per token** (Together, Fireworks) is priced like any API: rows in section 2.
- **Data handling:**
  - Fireworks keeps no prompt or generation data for open models without an opt-in (its data-handling page,
    checked).
  - Together's terms were read by the research pass and not re-checked: they store prompts and responses by
    default, may use them for product improvement, and offer zero retention as an admin setting.
- **Licences:**
  - DeepSeek V4.1 Flash is MIT.
  - Kimi K3's licence needs a separate agreement only for a business selling model access with over $20M a year of
    revenue. Optic would not be selling model access.
  - GLM-5.3's MIT-style licence adds a security review only for model-access sellers with over $10B of revenue.

**Self-hosted**, at Fireworks' listed on-demand GPU prices (checked; 730 hours a month, running all the time):

| Deployment | Per hour | Per month | What it could run (the research pass's reading of vLLM's recipes, not re-checked) |
|---|---:|---:|---|
| 1 x H100 80 GB | $8 | $5,840 | `gpt-oss-120b` (MXFP4 weights fit one 80 GB GPU) |
| 4 x GB300 288 GB | $80 | $58,400 | DeepSeek V4.1 Flash (recipe: 4 x GB200 NVL4, which has no published hourly price) |
| 8 x B200 180 GB | $104 | $75,920 | |
| 8 x B300 288 GB | $120 | $87,600 | GLM-5.3 (FP8); Kimi K3 (MXFP4; "multi-node for real production traffic") |

**Self-hosting does not pay at any scale considered here.**
- **Even one GPU costs too much.** A single H100 running all the time costs $5,840 a month. That is more than
  serving every question on Sonnet 5.5 at 1,000 MAU ($758) and close to serving every question at 10,000 MAU
  ($6,619).
- **The same models are far cheaper hosted.** GLM-5.3 hosted at 10,000 MAU with demand served is $3,073, and
  DeepSeek V4.1 Flash is $528.
- **The costs left out** all make it worse:
  - a second node for redundancy, which doubles the bill;
  - capacity planning;
  - upgrades to the serving stack and the weights;
  - monitoring and on-call engineering.
- **Peak load (section 5) is a few answers in flight**, so a dedicated deployment would sit mostly idle.

## 7. Where the money is, and the safe saving

1. **C1, caching the CONTEXT turn across tool rounds, saves 27%.** That is about $205 a month at 1,000 MAU and $2,050
   at 10,000 with demand served. It changes no answer: the request is the same, with one more cache breakpoint.
   **It is the largest saving available without a quality question**, and every provider comparison should be read
   against Sonnet 5.5 with C1 ($553 at 1,000 MAU), not as built.

   **Shipped to live main as `1a1cf58b`** on 2026-11-03 (04:29 UTC), on the owner's word. The branch carries the
   same lines as `9e0a6ea9` and `3eab5fc7`. It uses the API's
   automatic caching, a top-level `cache_control` that moves forward each round, beside the system block's own
   breakpoint. The messages stay exactly as they were. Tested: every round's request carries both markers and
   re-sends the round before it unchanged, and the test fails without the change. Checked end to end on the local
   server with the stand-in model. The ledger's `cache_read_tokens` per chat call is the measure, which needs real
   questions on the live site.
2. **A cheaper model for everything is worth 10 to 20 times more than any routing.** Moving all chat to Haiku 5.5
   would save about $719 a month at 1,000 MAU. Routing only the light questions saves $17 to $31. Section 8 and
   `MILO_ROUTING_RECOMMENDATION.md` say why that makes a single-model evaluation of the small models the first paid
   test after the baseline.
3. **The flagships are not a cost question until they are a quality one.** Opus 5.5 costs about twice Sonnet 5.5 and
   Fable 5.1 about five times. They are worth their price only if Sonnet 5.5 fails a workload that one of them
   passes.

## 8. Cost against quality: what can be said, and what it costs to find out

**No model's quality is measured,** so there is no frontier to draw yet and no "cheapest qualifying model" to name
per workload. The procedure that will name one, per workload, once keys work:
1. **Baseline first.** Run Sonnet 5.5, today's model, on the whole benchmark, 3 trials. If it fails a gate, that
   gate's failures are analysed before any other model is tried: a failure caused by Optic's retrieval, prompts or
   tools will fail every model (directive 15 Part 6).
2. **Cheapest first.** Run the candidates from cheapest to dearest on the same split, and stop at the first that
   passes every gate for a workload (`MILO_QUALITY_STANDARDS.md`, `MILO_ACCEPTABLE_ERROR_POLICY.md`).
3. **Hold-out last.** Confirm a qualifying model on the held-out 30% before anyone reads its answers there.
4. **Then the release-gate sizes** for the high-risk workloads: about 300 answers with no Severity 0 failure.

**What each run would cost** (today's prices; the low figure uses the harness's rule of thumb on the fixtures'
request sizes, the high one this model's production-sized shapes):

| Model | Whole benchmark, 181 cases x 3 trials | High-risk workloads only (W2, W6, W10, S1, S2), 92 cases x 3 |
|---|---:|---:|
| `claude-fable-5-1` | $240 to $339 | $192 |
| `claude-opus-5-5` | $96 to $138 | $78 |
| **`claude-sonnet-5-5`** (the baseline) | **$48 to $69** | **$39** |
| `claude-haiku-5-5` | $2.40 to $3.55 | $2.01 |
| `gpt-6-astra` | $240 to $257 | $145 |
| `gpt-6.1-sol` | $48 | $27 |
| `gpt-6.1-terra` | $24 | $13 |
| `gpt-6-luna` | $2.40 to $2.57 | $1.45 |
| `gemini-4-argon` | $42 to $48 | $24 |
| `gemini-3.8-flash` | $17 to $18 | $10 |
| `gemini-3.5-flash-lite` | $7.86 to $8.45 | $4.74 |
| `moonshotai/Kimi-K3` | $68 to $72 | $39 |
| `zai-org/GLM-5.3` | $32 | $18 |
| `deepseek-ai/DeepSeek-V4.1-Flash-1017` | $5.52 to $7.01 | $3.12 |
| `gpt-oss-120b` (Fireworks) | $3.18 to $3.51 | $1.80 |

- **A first round would cost about $130 to $155, and none of it is approved.** That round is the Sonnet 5.5
  baseline, then Haiku 5.5, GPT-6.1 Terra, Gemini 3.8 Flash, DeepSeek V4.1 Flash and GLM-5.3 on the whole benchmark.
  The runner stops at its `--max-dollars` cap.
- **Accounts come first.** Every provider other than Anthropic needs an account and a key, which are the owner's to
  open. A provider that would ever see readers' data also needs its terms reviewed before production.
- **The larger cost is people's time.** Reading a sample of S1 and S2 answers (the advice and injection safeguards)
  and of each workload's answers against the clarity rubric is more work than the dollars.

## 9. What would replace the estimates with measurements

1. **A working key.** The token-counting endpoint is free and replaces the 4-characters-a-token assumption for the
   prefix, the page context and the tool results.
2. **The baseline run.** Its usage gives calls per answer, thinking tokens, cache reads and writes per round, and
   output per workload.
3. **The production ledger** (`/api/ai/usage`, owner only) together with the Metrics page's question counts gives
   cost per question as readers actually ask. Recording `thinking_tokens` there would show how much of the output
   is reasoning (COST_AUDIT section 11).
4. **A sample of real questions, labelled by workload,** replaces the assumed mix. It could come from the ledger's
   request kinds plus the question text, read by the owner, since reader questions are private data.
