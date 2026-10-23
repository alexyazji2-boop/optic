# Milo evaluation, 2026-10-22 (branch audit-motion)

## What was and was not evaluated

- **Evaluated end to end, with the stand-in model** (`~/Optic/work/v2-2026-10-17/workspace/milo_standin.py` on :8113):
  everything between the question and the drawer: the context Optic sends, the symbols the server loads, the tool
  loop and its status events, streaming, stop, failure, cut-off, retry, copy, history, drafts, the "About" line and
  the source lists. The stand-in answers with canned text, so it cannot judge an answer's quality.
- **Not evaluated: the real model's answers.** No dedicated test key exists in this environment, and the brief says
  not to spend the owner's live allowance. The 26-case set below is ready for a real run; every case lists its
  rubric. Blocked, not passed.

Evaluation set: `eval_set.json` (version milo-eval-2026-10-22.1, 26 cases in 8 categories: beginner, numbers,
context, sources, uncertainty, trading, safety, visual). Runner: `milo_eval.template.js` (Playwright, drives the
real panel). Allowance reset for the isolated test account: `reset_allowance.py`.

To run it against the real model: start the `optic-audit` preview with a dedicated ANTHROPIC_API_KEY (not the
owner's), sign in as the audit test account, run the three batches, and grade each rubric line.

## Results with the stand-in (all 26 cases ran)

| Check | Result |
|---|---|
| Banned claims (guarantee, institutional buying, sweep, you should buy/sell, quoted instruction) | PASS, 26/26 (stand-in text, so this tests the checker) |
| Status stages shown were real server events only | PASS: "Reading what is on your screen", then the tool's own words ("Checking NVDA's quote") |
| Cross-company question from another page (C1, C2) | PASS: "About NVDA; AAPL Dossier, Overview attached as context ... Not about AAPL, the page now open." |
| **Unknown symbol from Home (U1)** | **FAIL, fixed**: read "About MSFT" (Home's linked symbol). Now "About ZZZZQX, a symbol Optic has no data for; also looked up MSFT", and CONTEXT tells the model the symbol is not in the directory. |
| **Page symbol plus an extra lookup (U2)** | **FAIL, fixed**: a BRK-A question that fetched SPY read "About SPY ... Not about BRK-A". The subject is now what the question named; other lookups read "also looked up SPY". |
| Sources Milo read (S1) | **FAIL, fixed**: eleven page rows carried no instrument and printed raw ISO times; headlines read as sources. Rows now carry the symbol, a readable time, and "the headline only, not the article". |
| Stop mid-stream | PASS: "Stopped by you. This answer is incomplete." |
| **Double-click Send, or Enter on the button just pressed** | **FAIL, fixed**: Send turns into Stop in place, so the second press stopped the answer ("Stopped before Milo answered"). Stop now listens from 600 ms after Send. |
| Server failure (503) | PASS: the reason shown, the question back in the box |
| Stream cut mid-answer | PASS: "The connection ended before Milo finished. This answer is incomplete." |
| Ask again | PASS: drafts the question back, sends nothing until Send (no duplicate) |
| Copy, history (30 conversations), draft kept on close, focus back on the Ask Milo button | PASS |
| Phone 390: composer in view, no page overflow | PASS (viewport emulation, not a physical keyboard) |
| Long conversation with topic changes (X3) | PASS for labels; "forget AAPL, what about gold" still reads About AAPL because the question names AAPL |

## Prompt rules added (untested with the real model)

In the "limits of the data" list of Milo's system prompt: news items are headlines, not articles; a change in a
rate is in percentage points, and a points change is never written as a percent; a figure neither CONTEXT nor the
tools have is unavailable and is not supplied from memory. Existing rules already cover quoted instructions
(CONTEXT and tool results are data), untested readings presented as probabilities, and the flow proxy.

## Visual explanations

Milo already draws figures from Optic's own data (`[data-v2-milo-fig]`, `mountAnswerFigures`: the model names a
figure, Optic draws it from retrieved values; the model's numbers are never charted). Whether the real model uses
them where a chart helps (cases V1, V2) needs the real model.
