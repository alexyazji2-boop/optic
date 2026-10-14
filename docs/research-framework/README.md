# Research framework

Four separate conclusions about one company, each with its own rules, and a
plain-English account of where they agree. Code in `app/research/`; every
rule, formula and threshold is documented in `app/research/METHODS.md` and
listed live at `/api/framework-policy`.

| Question | Answer on the Overview | Milo mode |
|---|---|---|
| Is it a strong business? | Business quality A to F, long-term conviction | long_term |
| Is the price attractive? | Attractive / Fair / Full / Stretched | long_term |
| Is there a trade? | S / A / B / Avoid / No Setup | swing |
| What about earnings? | The best-supported pre-release view, or the post-release audit | pre_earnings, post_earnings |
| All of it | The four, then where they agree | combined |

- `samples/`: representative reports for every mode, from live data on
  2026-10-14, rendered by `app/research/report.py`.
- `milo-eval/`: how Milo's answers were checked (seven questions, prompts
  captured before and after with no model call, stand-in answers, a blinded
  review). The method follows `docs/desk/milo-eval/`.

Grades are framework rules, not probabilities, and none has been shown to
predict returns. Pre-earnings forecasts are saved as immutable snapshots before
each release cutoff (`app/research/forecasts.py`) so that they can be scored
later without hindsight; `/api/framework-quality` reports that record, and says
it is a count until twenty forecasts have been scored.
