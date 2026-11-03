# Milo: one model or several?

Phase 13 (directive 15, Part 8), 2026-11-02. **Recommendation: one model, and no router.** Cache the CONTEXT turn
(C1) first, then measure today's model. Test the small models as single-model replacements, not as routes.
Nothing here was built into the app. The router below is analysis code in the test tree, as the directive asks
("Do not implement this architecture automatically").

```bash
.venv/bin/python -m tests.milo_eval.router      # docs/ai/eval-results/routing/routing.json, no network, no model
.venv/bin/python -m pytest -q tests/test_milo_cost_model.py
```

## What was tested

**A deterministic router** (`tests/milo_eval/router.py`) picks a workload from what production has before a model
starts:
- the question, the earlier turns and the page;
- Optic's own classifiers: the advice policy's request reader, the definition test and the own-portfolio test in
  `app/main.py`;
- the server's symbol lookup (`_named_and_unknown`), so that "What is AAPL at?" is not read as a definition.

It was scored against the 181 benchmark cases' workload labels. Those labels were set by the benchmark's authors, so
"accuracy" here means agreement with them, not ground truth.

**The architecture priced** is the directive's example, mapped to models:
- definitions, navigation and routine market data to the small fast model (Claude Haiku 5.5);
- multi-source research to the larger one (Claude Opus 5.5);
- everything else, every advice request and every adversarial input to today's model (Claude Sonnet 5.5).

Every route stays inside Anthropic, so the comparison isolates routing from a change of provider. The costs come from
`MILO_COST_ANALYSIS.md`'s model. Each misrouted question keeps its own workload's work, pays its route's price, and
each model keeps its own cache.

**No model was run** (BLOCKERS BL-01). The routes' quality is therefore unknown, and a router can only be judged
here on whether it sends questions where they belong, what that would save, and what it would put at risk.

## Results

### Routing accuracy (measured)

126 of 181 cases go where their label says: **69.6%** (95% interval 62.6% to 75.8%). One decision takes 0.127 ms.

| Workload | Routed as labelled | 95% interval | Where the rest went |
|---|---|---|---|
| W1 definitions | 13 of 16 | 57% to 93% | W3 2, W2 1 |
| W2 market data | 31 of 32 | 84% to 99% | W3 1 |
| W3 fundamentals | 12 of 12 | 76% to 100% | |
| W4 technical | 6 of 16 | 19% to 61% | W1 4 (indicator definitions), W5 3, W7 2, W2 1 |
| W5 Dossier | 11 of 17 | 41% to 83% | W2 5, W4 1 |
| W6 portfolio | 13 of 17 | 53% to 90% | W2 2, W7 2 |
| W7 multi-source | 5 of 5 | 57% to 100% | |
| W8 follow-ups | 13 of 15 | 62% to 96% | S1 2 |
| W9 help | 5 of 8 | 31% to 86% | W1 1, W2 1, W6 1 |
| **W10 unavailable data** | **1 of 15** | 1% to 30% | **W2 12**, W3 2 |
| S1 advice requests | 13 of 13 | 77% to 100% | |
| **S2 adversarial input** | **3 of 15** | 7% to 45% | W2 4, S1 3, W5 2, W6 2, W8 1 |

**What a route receives is what matters.** The example's cheap route (W1, W2 and W9 to Haiku 5.5) would receive 80
of the benchmark's questions. Only 52 of them (65%, interval 54% to 75%) belong to its own workloads. The other 28
are:
- 12 of the 15 unavailable-data questions;
- 5 Dossier questions and 5 technical ones;
- 4 injection attempts;
- 2 portfolio questions.

**Why the misroutes cannot be fixed from the words:**
- **Unavailable data:** whether a figure is missing is known only after the tools run. "What is the order book for
  AAPL?" reads like a market-data question. W10 is also where a model is most tempted to fill a gap with an invented
  figure, which is Severity 0.
- **Adversarial input:** an injection arrives inside a page, a headline or an earlier turn as often as in the
  question, and most are written to look like ordinary requests.

The 4 cases a definition route would wrongly take (IND-03, IND-06, IND-09, IND-13) are indicator definitions. That
one is benign.

### Cost (modelled; Milo chat a month, prices in force on 2027-01-01)

| Architecture | 100 MAU | 1,000 MAU | 10,000 MAU at the ceiling | 10,000 MAU, demand served | Questions on a model their workload's route would not use |
|---|---:|---:|---:|---:|---:|
| **One model, Sonnet 5.5, as built** | $86 | $758 | $1,090 | $6,619 | 0 |
| **One model, with C1** | **$65 (-24%)** | **$553 (-27%)** | **$783 (-28%)** | **$4,571 (-31%)** | 0 |
| Definitions and help to Haiku 5.5 | $80 (-7%) | $727 (-4%) | $1,051 (-4%) | $6,343 (-4%) | |
| Definitions to Haiku 5.5, help answered without a model | $80 (-7%) | $727 (-4%) | $1,051 (-4%) | $6,341 (-4%) | |
| The directive's example, perfect router | $72 (-16%) | $681 (-10%) | $997 (-9%) | $5,934 (-10%) | 0 |
| The directive's example, measured router | $67 (-22%) | $639 (-16%) | $937 (-14%) | $5,532 (-16%) | 13.8%, of which 3.9% high-risk |
| The directive's example with C1 | $50 (-42%) | $462 (-39%) | $672 (-38%) | $3,764 (-43%) | 13.8% |
| Definitions and help to Haiku 5.5, with C1 | $60 (-30%) | $527 (-31%) | $750 (-31%) | $4,338 (-34%) | |
| Every question to Haiku 5.5 (the bound, if one small model qualified) | $4 (-95%) | $39 (-95%) | $56 (-95%) | $341 (-95%) | 0 |

**What the table says:**
1. **C1 alone saves more than any routing.** It saves 24% to 31%, with no change to any answer, no new model and no
   new code path.
2. **The example saves 10% with a perfect router.** The measured router saves 16%, and the extra six points come
   from its mistakes: cheaper answers to questions sent to the wrong model, high-risk ones among them. A saving that
   grows as routing gets worse is not one to build on.
3. **Routing only the light questions saves 4%**, about $31 a month at 1,000 MAU. It is not worth a second model's
   evaluation, prompts and failure modes.
4. **Answering help questions without a model saves nothing measurable.** They are 4% of the assumed mix at $0.017
   each, and Optic has no help index to answer them from. Doing it would be a product decision, made for accuracy,
   not cost.
5. **The saving that matters is a whole-model one.** If a small model met the standard on every workload, the bill
   would fall by 95%. That is a single-model evaluation, and it needs no router.

### The directive's other criteria

| Criterion | Finding | Evidence |
|---|---|---|
| Added latency | 0.127 ms a decision for the rule-based router, measured. A model-based classifier would add a model call before every answer, its time to first token and its cost: not measured (no key) | `routing.json` |
| Reliability | More models add more ways to fail. Haiku 5.5 has no server-side refusal fallback, so a refusal reaches the reader where Sonnet 5.5 would re-run it. Each model's limits and outages are its own. Routing inside one provider shares that provider's outages | Claude API reference (Haiku 5.5); `providers.py` `NO_FALLBACK` |
| Maintenance | The router is a dozen patterns that every new page and feature must be checked against. **Every prompt change would need the benchmark on every route's model:** three runs instead of one, about $146 to $210 a round at three trials against $48 to $69 for Sonnet 5.5 alone (cost analysis, section 8) | `router.py`; evaluation budget |
| Security consistency | Holds by construction: routing would choose only the model, so the same server code applies to every route (the system prompt, the advice policy, the output check, the toolbox and its authorization rule). **What routing would change is who must resist injection:** S2's cases spread across five routes, so every route's model would have to pass S2 itself | `MILO_DATA_ACCESS_MAP.md`; S2 confusion above |
| User experience | One voice becomes several. A follow-up that changes model loses the earlier turn's thinking: on Sonnet 5.5, Haiku 5.5 and Opus 5.5, thinking blocks are tied to the model that wrote them. The cache restarts too. The same question asked twice could get a different model's answer, which a research tool cannot afford | Claude API reference (thinking blocks); cost model (one cache per model) |
| Regression risk | A misroute is invisible to the reader and to the checks. **Each route's model must therefore qualify on every workload the router sends it**, not only its own. With the measured confusion, the cheap route receives W10, S2, W5 and W6 questions, so a cheap model would have to pass those gates anyway. That is most of the way to qualifying it for everything, and then routing has no purpose | the "what a route receives" figures above |

## Recommendation

1. **Keep one model.** Routing is not justified by these results:
   - its saving is 4% to 10% with a perfect router, less than C1 alone;
   - the router cannot see the two risks that matter most (unavailable data and injection);
   - it would multiply the evaluation and the failure modes.
2. **C1 has shipped.** It is the one saving with no quality question attached. It went to live main as `1a1cf58b`
   on 2026-11-03, on the owner's word, with its own tests. The ledger's cache hits will show what it saves
   (COST_AUDIT C1).
3. **Evaluate the small models as replacements, not routes.** Run Haiku 5.5, GPT-6 Luna, Gemini 3.5 Flash-Lite and
   DeepSeek V4.1 Flash, each on the whole benchmark, after the Sonnet 5.5 baseline. A small model that passes every
   gate saves far more than any router. One that fails only W1 and W9 is no use to a router either, since those
   questions are cheap already.
4. **Revisit routing only on measured evidence.** That means a cheaper model passing the high-volume workloads (W2
   to W5) and failing others, plus a router whose misroutes into the cheap route land only on workloads the cheap
   model also passes. Any router then built should:
   - route on the server, after the toolbox and the policy have run their checks, so every route keeps one set of
     safeguards;
   - send an unrecognised question to the default model;
   - keep a thread on one model.
5. **High-risk requests stay with safeguards, not a bigger model,** as they are today:
   - the advice request reader adds the policy's instruction;
   - the output check removes a sentence that decides for the reader;
   - the toolbox refuses a tool the question was not offered;
   - the server alone decides what portfolio data exists.

   None of these depends on the model, and the red team tests them (`tests/test_milo_redteam.py`).
