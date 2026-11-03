# Milo: Phase 13 final report (model evaluation, standards, error policy, cost)

Directive 15 (`docs/post-demo-ultra/directives/15-phase-13-model-selection.md`), 2026-11-02, branch
`phase-12-writing-milo-security` in `~/Optic/wt-phase12`, after Phase 12 was committed. Not pushed, not deployed.
Milo's production model was not changed.

## The short version

- **No model answered a question in this phase.** The Anthropic key on this machine is refused (`401` on the free
  models list, 2026-11-02, BLOCKERS BL-01), and no other provider's key exists here. Every quality figure the
  directive asks for is therefore unmeasured, and this report claims none of them.
- **What exists now:**
  - standards per workload and a formal error policy;
  - a harness that runs Milo's own request, tools and checks on Anthropic, OpenAI, Google and open-weight hosts,
    tested offline;
  - verified prices and terms for 15 candidates, and a cost model checked against the cost audit;
  - a measured router with the routing scenarios priced;
  - an evaluation plan with its budget.
- **Recommendation:**
  - keep one model, Sonnet 5.5;
  - cache the CONTEXT turn (C1, 27% less spend with no change to any answer);
  - run the Sonnet 5.5 baseline on today's code;
  - then test the small models as whole replacements.

  Routing is not justified.

## Part 1: Milo's model and architecture

**Claude Code's model and Milo's are separate.**
- **Claude Code:** the engineering agent writing this report runs on Claude Opus 5.5. It never answers readers.
- **Milo:** the server calls Anthropic's API with `PULSE_MODEL = "claude-sonnet-5-5"` (`app/ai.py:60`).
- **The writers:** Optic's Read, the Desk, earnings briefs and the rest use `MODEL = "claude-opus-5-5"` (`app/ai.py:55`).
- **No environment variable overrides either one,** and `tests/test_pulse_model.py` fails on a model literal
  anywhere else. A switch is one line, under the owner's approval.

**Milo's configuration** (`build_chat_request`, `app/ai.py:3372`):
- `max_tokens` 8,000, `thinking: {type: "adaptive"}`, effort `medium`;
- the server-side refusal fallback (`betas: ["server-side-fallback-2026-07-01"]`, `fallbacks: "default"`);
- streamed;
- one cache breakpoint, on the 53,743-character system block. That block is the base prompt, the format rules,
  Phase 12's writing rules and the advice policy.

**The path of a question:**
1. `POST /api/chat` (`app/main.py:8454`).
2. The spend guard (`_spend_guard`, `:8004`): length, the 300-a-day ceiling, the plan allowance, the hourly burst.
3. Context: the page's figures, named symbols (`_named_and_unknown`, `:4585`), the research pack and the framework.
4. The toolbox by rule (`_milo_toolbox`, `:8305`). `get_my_portfolio` is offered only from the Brokerage page or for
   a question about the reader's own holdings (`_asks_about_own_portfolio`, `:8385`).
5. `stream_chat` (`app/ai.py:3575`): up to 4 tool rounds and 10 calls, 30 s a call, 75 s in all.
6. The advice gate (`StreamGate`, `app/ai_policy.py:1051`), which holds text back by at most one sentence.
7. Server-sent events to the page.

**Three questions traced** (benchmark fixtures, no network, no model; `harness.assemble`):

| Case | Workload, level | Question | Context the server added | Tools | Request size | Server time to the model call |
|---|---|---|---|---|---:|---:|
| BEG-01 | W1, New to Markets | "What is a P/E ratio, in plain words?" | focus, macro, the named-symbol check | 16 | 66,544 characters | 0.041 s |
| FUN-01 | W3, Intermediate | "How has AAPL's quarterly revenue grown?" | AAPL auto-loaded, the research pack | 16 | 67,972 | 0.423 s |
| POR-01 | W6, Intermediate | "Explain my portfolio concentration." | the linked portfolio block (server-built) | 17, with `get_my_portfolio` | 70,580 | 0.019 s |

In all three, **the fixed part dominates**: the cached system block is 53,743 characters and the tools 10,895 to
12,288. The question and its context add 1,300 to 4,000. A definition costs nearly as much to send as a research
question. That is why caching matters more than prompt length.

## Parts 2 and 3: the standard and the error policy

- **`MILO_QUALITY_STANDARDS.md`**: ten workloads (W1 to W10) and two cross-cutting safeguards (S1 advice, S2
  adversarial input). Each has expected behaviour, data sources, tools, depth, accuracy criteria, latency targets,
  risk, length, what is prohibited, and how it is evaluated.
- **`MILO_ACCEPTABLE_ERROR_POLICY.md`**: four severities, set by what a mistake costs the reader:
  - **Severity 0** blocks a release, and none is allowed in a release-gate set of at least 299 answers;
  - **Severity 1** at most 2% per workload;
  - **Severity 2** at most 10%;
  - **Severity 3** tracked.

  No composite score hides a severity.

## Part 4: the harness

| Piece | What it does | Tested |
|---|---|---|
| `tests/milo_eval/compare.py` | Runs a model on the benchmark through Optic's own request, toolbox and output check. Records every field Part 4 lists, with severities, a 70/30 dev/held-out split and a criteria hash. Refuses without a key or a `--max-dollars` cap; `--dry-run` sends nothing | `tests/test_milo_compare.py`, 12 tests |
| `tests/milo_eval/providers.py` | Adapters for Anthropic (production's request unchanged), the OpenAI Responses API, OpenAI-compatible hosts (Chat Completions) and Gemini. Each provider's needs are documented in `MILO_MODEL_COMPARISON.md` section 3 | offline, against reply shapes from each provider's documentation; dry runs of five adapters produced well-formed requests |
| `tests/milo_eval/stats.py` | Wilson intervals, the zero-failure bound, the sample needed | `tests/test_milo_stats.py` |
| `tests/milo_eval/cost_model.py` | Cost per question, workload and model, and per month at 100, 1,000 and 10,000 MAU | `tests/test_milo_cost_model.py`, which reproduces the cost audit's figures |
| `tests/milo_eval/router.py` | The routing analysis | the same file |
| `tests/milo_eval/prices.json` | Verified list prices, with sources and announced changes | |

**Defects found and fixed in the harness itself:**
1. **Wrong API for OpenAI.** The OpenAI adapter used Chat Completions, where OpenAI's current models cannot call
   tools. It now uses the Responses API.
2. **Costs on different bases.** Anthropic's adapter reported only uncached input while the others reported all
   input. On top of that, cache writes were also charged as fresh input.
3. **Gemini's thinking uncounted.** Its thinking tokens, which Gemini reports apart from its output, went unbilled.
4. **Kimi K3's reasoning dropped.** The OpenAI-compatible adapter dropped the reasoning field Kimi K3 requires back.
5. **An invalid parameter for Haiku 5.5.** It would have been sent a fallback parameter it does not support.
6. **No output cap outside Anthropic.** Only Anthropic's request carried production's output cap.

Each would have skewed a comparison against a provider. Each now has a test.

## Part 5: Claude Sonnet 5.5 (the current model)

**Its exact configuration** is the one in Part 1: `claude-sonnet-5-5`, adaptive thinking, effort medium, 8,000
output tokens, the default server-side fallback, one cache breakpoint.

| Measure (directive Part 5) | Status |
|---|---|
| 1. Financial factual accuracy | **not measured on today's code**; see "the one earlier sample" below |
| 2. Tool selection | request level: **246 of 246** tool-offering checks pass (Optic offers the right tools). What the model then calls: not measured |
| 3. Mathematical correctness | request level: the calculation cases recompute from the tools' figures. The model's arithmetic: not measured |
| 4. Source grounding | not measured (the `grounded` check is ready) |
| 5. Hallucination frequency | not measured |
| 6. Multi-turn context | request level: all 15 multi-turn cases pass, 6 of them checking that the research ticker follows the thread. Answer level: not measured |
| 7. Advice safeguards | Optic's own layer, measured on unseen sets: **the output check catches 32% of advice sentences (16 of 50, set F) and the request reader 30% (18 of 60)**. The model's own adherence: not measured |
| 8. Data-access security | Optic's own layer: the red team's 38 tests pass, and cross-reader access is refused at the server. The model's behaviour under injection: not measured |
| 9 and 10. Beginner and advanced explanation quality | not measured (human rubric) |
| 11 and 12. Time to first text, total time | Optic's own share measured with a stand-in model: median 0.31 s to first text, 0.65 s in all, p95 4.7 s and 5.0 s. The model's share: not measured |
| 13. Cost per completed task | modelled: $0.138 a typical question warm, $0.178 cold; $0.147 the average at 1,000 MAU (`MILO_COST_ANALYSIS.md`). The only measurement, $0.107 a call (2026-10-11), predates the tools |
| 14. Error and timeout rates | Optic's own: 0 errors and 0 timeouts in 72 local answers with the stand-in. The model's: not measured |

**The one earlier sample of Sonnet 5.5's answers.**
- **The trial:** on 2026-10-16, the owner's account asked the same 14 questions of Sonnet 5.5 and Sonnet 5 on the
  live site (`docs/milo/reasoning-eval/LIVE-MODEL-TRIAL.md`). One reviewer, not blinded, one run each.
- **Against Sonnet 5:** Sonnet 5.5 was better on 9 (64%, interval 39% to 84%), worse on 2, even on 3, and faster in
  all (182 s against 256 s).
- **Against Phase 13's standard:** 5 of Sonnet 5.5's 14 answers contain at least one factual error (36%, interval
  16% to 61%). The errors were a wrong three-month return, weights mis-added to 61.8% for 62.8%, a share of long
  value called a share of the whole account, and, twice, a claim that fund look-through does not exist. That is far
  from the 98% grounding and 2% Severity 1 targets.
- **Why it does not decide the question:** several of those errors came from tools production lacked then. The
  window-return tool (`get_price_history`, 2026-10-30) and the look-through coverage in the portfolio tool came
  later. So the sample says the code of 2026-10-16 failed the standard. It says nothing measured about today's.

**Conclusion: Sonnet 5.5 has not been shown to meet Optic's standard.** The directive forbids claiming it does
without evidence, and the only answer-level evidence, on older code, falls short.

## Part 6: alternative models

`MILO_MODEL_COMPARISON.md` covers:
- **15 candidates with verified facts:** Anthropic (4), OpenAI GPT-6 (4), Google Gemini (3), and open weights
  hosted on Together and Fireworks (4), plus self-hosting;
- **the conditions held equal and the adaptations each provider needs;**
- **the method for telling a model's failures from Optic's;**
- **each provider's data terms.** One finding there: AI Studio logs every request for 55 days by default in Google
  projects created since 2026-10-26.

None was evaluated.

## Part 7: cost per quality

`MILO_COST_ANALYSIS.md`. Key figures for Milo chat a month, at the prices in force on 2027-01-01:

| | 100 MAU | 1,000 MAU | 10,000 MAU (300 a day) | 10,000 MAU, demand served |
|---|---:|---:|---:|---:|
| Sonnet 5.5 as built | $86 | $758 | $1,090 | $6,619 |
| Sonnet 5.5 with C1 | $65 | $553 | $783 | $4,571 |
| Haiku 5.5 | $4 | $39 | $56 | $341 |
| GPT-6.1 Terra | $29 | $229 | $343 | $2,285 |
| Gemini 3.8 Flash | $44 | $382 | $547 | $3,282 |
| DeepSeek V4.1 Flash (hosted) | $8 | $65 | $91 | $528 |
| Opus 5.5 | $172 | $1,517 | $2,180 | $13,238 |

- **The ratios hold under every assumption tested; the dollar figures move up to twofold** with the unmeasured token
  ratio.
- **Self-hosting an open-weight model** costs more than any hosted option at every scale here.
- **The cheapest model meeting each workload's standard cannot be named,** because no model is measured. Section 8
  of the cost analysis gives the cheapest-first procedure and its price: the Sonnet 5.5 baseline is $48 to $69 at
  three trials.

## Part 8: routing

`MILO_ROUTING_RECOMMENDATION.md`.
- **The router:** a deterministic router from Optic's own classifiers agrees with the benchmark's labels on 126 of
  181 cases (69.6%, interval 62.6% to 75.8%), at 0.127 ms a decision. It sends 12 of 15 unavailable-data questions,
  and 4 of 15 injection attempts, to the cheap market-data route.
- **The saving:** the directive's example saves 10% with a perfect router. The measured router saves 16%, and the
  extra six points come from its mistakes. C1 alone saves 27%.
- **Conclusion:** routing is not justified by the evidence.

## Part 9: quality gates and statistics

- **The thresholds:** the directive's proposed targets are adopted per workload, with Wilson intervals beside every
  rate (`MILO_QUALITY_STANDARDS.md`, "Thresholds").
- **Zero failures:** "none observed" is reported with its bound:
  - 14 failure-free answers bound the rate at 19%;
  - 299 are needed to show under 1%;
  - 149 to show under 2%.
- **Sample sizes:**
  - the current benchmark supports a first read of most workloads at three trials (about 45 answers each);
  - W7 has only 5 cases, too few to measure;
  - the high-risk workloads (W2, W6, W10, S1, S2) need twice the cases before a release decision.

## Part 10: the seven answers

1. **What standard must Milo meet?** The per-workload standard in `MILO_QUALITY_STANDARDS.md`. Its floors:
   - at least 98% of figures grounded in what the tools returned, per workload;
   - the right tools offered (99%, already 246 of 246 at request level);
   - **no fabricated current price, no cross-reader data and no personal trading instruction** in a release-gate
     set of at least 299 answers;
   - at least 90% on relevance and clarity, read by a person, per workload.

   The high-risk workloads are W2 market data, W6 portfolio, W10 unavailable data, S1 advice and S2 adversarial
   input. They need twice the cases.
2. **What mistakes are acceptable?** Severity 3 (style), tracked. Severity 2 (incomplete, not misleading) up to 10%
   per workload. Severity 1 (wrong where it matters) up to 2%, each one read and given a regression case.
   **Severity 0 never** (`MILO_ACCEPTABLE_ERROR_POLICY.md`).
3. **Does Sonnet 5.5 meet the standards?** **Not shown.** No answer was measured on today's code. The one earlier
   sample (14 answers, 2026-10-16, older tools) had a factual error in 5 of them, which is far below the standard.
4. **If not, which other models might qualify?** None can be ranked: none has been evaluated, and the directive rules
   out a ranking by reputation. The candidates, and the cheapest-first order in which to test them, are in the
   model comparison and the cost analysis.
5. **If Sonnet 5.5 qualifies, are there cheaper alternatives that also qualify?** Unknown until measured. What is
   known is what is at stake: at 1,000 MAU, Haiku 5.5 would cost $39 a month against $553 for Sonnet 5.5 with C1.
   GPT-6.1 Terra would cost $229 and DeepSeek V4.1 Flash $65. Each needs the whole benchmark and the release-gate
   sizes before it could replace Sonnet 5.5.
6. **One model or several?** **One.** Routing saves less than C1 alone. Its router cannot see unavailable data or
   injections, and it multiplies evaluation, failure modes and voices (routing recommendation).
7. **What should improve whatever the model?**
   1. **C1:** mark the CONTEXT turn as cacheable across tool rounds. 27% of Milo's spend, no change to any answer
      (COST_AUDIT C1).
   2. **The advice safeguards** catch about a third of unseen phrasing (set F). The gap needs a person reading a
      sample of S1 answers in every evaluation. A model-based second reading of each answer (BL-07, about $0.0003
      an answer at Haiku 5.5's prices) is worth testing once a key works. Counsel decides the legal standard (BL-02).
   3. **Context gathering is the slow tail.** Optic's own p95 is 4.6 s before the model starts, from the research
      pack's and the framework's fetches on a cold cache.
   4. **The ledger:** record a round the reader cancels (C2), and record thinking tokens, so cost per question and
      per workload can be read rather than estimated.
   5. **The ceiling bounds questions, not dollars.** A dollar ceiling from the ledger, and the Anthropic console's
      spend limit, would bound cost (COST_AUDIT section 9.2).
   6. **The benchmark:**
      - W7 needs more cases;
      - the high-risk workloads need twice their current cases;
      - the advice suite needs a fresh unseen set each round. A set is a fair measure only until it has been read
        and tuned against: set E became development material in Phase 12, and set F has been measured once.
   7. **Measure the token ratio** with the free counting endpoint. It moves every cost figure by up to twofold.
   8. **Web search on Anthropic** re-writes the cached prefix whenever a reader toggles it. That is already one of
      the cost model's prefix variants. It is worth knowing before web search is used more.

## The recommendation, item by item

| The directive asks for | Answer |
|---|---|
| Best-performing tested model | **None tested.** |
| Lowest-cost qualifying tested model | **None tested.** |
| Best quality-to-cost option | **None measured.** The cost side is ready: Sonnet 5.5 with C1 is the cheapest way to run today's model, at $553 a month at 1,000 MAU. |
| Recommended architecture | **One model, Sonnet 5.5, unchanged, with C1.** Test the small models (Haiku 5.5, GPT-6 Luna, Gemini 3.5 Flash-Lite, DeepSeek V4.1 Flash) as whole replacements after the baseline. No router. |
| Expected operating-cost assumptions | 10% of monthly actives ask on a given day, 2 questions each; chat 85% of questions; the workload mix in the cost analysis; 4 characters a token (unmeasured); 2% of answers paid twice; prices on 2027-01-01. Milo chat on Sonnet 5.5 with C1: about $65, $553 and $783 a month at 100, 1,000 and 10,000 MAU under the 300-a-day ceiling, and $4,571 with demand served. |
| Critical remaining uncertainties | (1) every quality figure, since no model answered; (2) the token ratio, up to twofold on cost; (3) the workload mix, since no traffic is labelled; (4) each model's answer length and reasoning; (5) the benchmark's fixtures are synthetic and written by the team that built Milo; (6) whether a new provider's terms suit readers' data; (7) announced price changes (both Gemini models double within two months). |
| Required human review | A person reads a sample of S1 (advice) and S2 (injection) answers in every run. Clarity and relevance are scored by a person on at least 30 answers per workload. Every failed check is classified as the model's or Optic's before models are compared. Counsel reviews any new provider's data terms and the Privacy Policy change it needs. |
| Required approval before changing production | The owner's explicit approval of the model change (directive 15). A completed evaluation passing every gate on the held-out split, with the release-gate sizes for the high-risk workloads. Counsel's sign-off on the provider's terms if it is not Anthropic. C1 is not a model change, but it is a production change and ships only on the owner's word. |

## What was done, and how to check it

**New in this phase** (on top of Phase 12's commits `35348c98` and `6b27721b`):
- **Docs:** `docs/ai/MILO_QUALITY_STANDARDS.md`, `MILO_ACCEPTABLE_ERROR_POLICY.md`, `MILO_MODEL_COMPARISON.md`,
  `MILO_COST_ANALYSIS.md`, `MILO_ROUTING_RECOMMENDATION.md` and this report.
- **Code:** `tests/milo_eval/` gained `compare.py`, `providers.py`, `stats.py`, `cost_model.py`, `router.py` and
  `prices.json`. `cases.py` gained the workload label (W1 to W10, S1, S2) on all 181 cases.
- **Tests:** `tests/test_milo_compare.py`, `tests/test_milo_cost_model.py` and `tests/test_milo_stats.py`.
- **Machine-readable results:** `docs/ai/eval-results/cost-model/cost-model.json` and
  `docs/ai/eval-results/routing/routing.json`.

**Nothing was spent.** No model was called, no account was opened, and no purchase was made. The research pass read
public pages only.

```bash
.venv/bin/python -m pytest -q tests/test_milo_compare.py tests/test_milo_cost_model.py tests/test_milo_stats.py
.venv/bin/python -m tests.milo_eval.cost_model --budget
.venv/bin/python -m tests.milo_eval.router
.venv/bin/python -m tests.milo_eval.compare --provider openai --model gpt-6.1-sol --dry-run --only ACC-quote-AAPL --out /tmp/dry
```

When a key works, the baseline (refuses without a key, stops at the cap):

```bash
.venv/bin/python -m tests.milo_eval.compare --provider anthropic --model claude-sonnet-5-5 --trials 3 --max-dollars 100 --out OUT
```
