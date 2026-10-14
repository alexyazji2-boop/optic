"""The research framework: five kinds of question, kept apart.

A strong company, an attractive valuation, a favourable trading setup and a
positive earnings reaction are four different conclusions, and a reader who is
shown one score for all of them cannot tell which one the answer turns on. This
package answers each with its own rules:

* `long_term`  - business quality, then valuation, then the chart as context.
* `swing`      - setup, confirmation, invalidation, reward-to-risk, grade.
* `pre_earnings` / `post_earnings` - the expectations hurdle, three separate
  predictions (results, guidance, reaction), and a review of the saved forecast
  once results are out.
* `combined`   - the separate assessments, then where they agree and disagree.

The arithmetic is deterministic and lives here (`trade_math`, `quality`,
`swing`, `earnings`). Milo explains these results and never computes them.
`policy` holds every threshold as a named, versioned, configurable rule;
`forecasts` keeps pre-earnings forecasts as immutable snapshots so they can be
scored later without hindsight. METHODS.md documents each rule and its source.
"""

METHOD_VERSION = "research-1.0"
