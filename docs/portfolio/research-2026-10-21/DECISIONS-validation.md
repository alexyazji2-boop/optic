# Decisions on the validation period, written before the final period is run

2026-10-21, from `results/r1-development-validation.json` and `results/r2-development-validation.json`, under
PROTOCOL.md as registered. Nothing in the protocol was changed. The final period is run once after this file.

## R1: setups A-D with confluence (eight primary tests)

| Universe | Setup | FULL trades (val) | Mean net R (val) | t | Incremental t | FULL - random t | Test 1 |
|---|---|---|---|---|---|---|---|
| funds | A trend pullback | 495 | -0.112 | -1.21 | -2.58 | -0.67 | fail |
| funds | B breakout retest | 153 | -0.186 | -1.24 | 0.87 | -0.67 | fail |
| funds | C failed breakdown | 92 | 0.105 | 0.44 | 0.94 | 0.70 | fail |
| funds | D range reversion | 22 | 0.169 | 0.56 | 0.58 | 0.53 | fail |
| stocks | A | 406 | 0.103 | 1.14 | 0.88 | 0.01 | fail |
| stocks | B | 179 | 0.020 | 0.15 | 1.95 | -0.54 | fail |
| stocks | C | 66 | 0.077 | 0.49 | 0.30 | -0.09 | fail |
| stocks | D | 20 | 0.417 | 1.39 | 0.97 | 0.91 | fail (and development -0.508, t -2.73) |

Benjamini-Hochberg at q = 0.10: no test passes (smallest p 0.092 against a threshold of 0.0125).

**Decision: all eight are rejected.** None reaches t ≥ 2.0 in validation, so none can be "investigate further"
either (that needs 1.5 ≤ t < 2.0 with the final and robustness tests passing). The final period is run once for the
record, and cannot change these decisions.

Observations, not decisions:
* For fund pullbacks (A), requiring high relative volume and a supportive market made results significantly worse
  in both periods (incremental t -2.21 and -2.58).
* Before costs most price-only versions are slightly positive (about +0.05 to +0.17R); costs of 0.06 to 0.12R a
  trade take it away. Random entries under the same stops and exits earn about the same.
* Exits: a 3R target or a 3-ATR trailing stop was usually better than the 2R target on the same trades; the early
  "no progress" exit and the partial exit were not. Trades gave back about 0.8 to 1.0R from their best close.

## R2: catalysts (stocks)

| Setup | Variant | Trades (val) | Mean net R (val) | t | Development mean (t) |
|---|---|---|---|---|---|
| G1 continuation | control (reaction ≥ +3 points) | 164 | 0.328 | 2.45 | 0.118 (1.05) |
| G1 | trigger (+ volume, strong close) | 88 | 0.413 | 2.70 | 0.176 (1.21) |
| G1 | FULL (+ market context) | 78 | 0.300 | 1.96 | 0.182 (1.06) |
| G2 reversal | FULL | 27 | 0.175 | 0.53 | -0.362 (-1.43) |

G1 FULL: incremental t -0.23 (validation), FULL minus random t 1.42.

**Decisions:**
* **G1 FULL** fails test 1 (t 1.96 against 2.0; incremental and random comparisons fail). Under the protocol it can
  at best be "investigate further", and only if the final period (test 3) and robustness (test 4) pass. Stocks are
  survivor-biased, so it cannot advance in any case.
* **G2: rejected.**
* Recorded, not a candidate: the single-factor control (a strong positive reaction alone) did at least as well as
  the confluence version. Adding volume and market context did not help, so the confluence requirement adds nothing
  here.

## Event policies on R1's stock trades (descriptive)

* The estimated window (previous release + 81 to 101 days) contained the next release 84% of the time.
* Skipping entries made within about 10 sessions of the estimated window removed about 14% of trades, and the
  skipped trades had done better than the rest. Exiting before the window lowered those trades' R
  (validation +0.23R against +0.37R if held).
* Trades held through a release had a higher average (+0.31 and +0.33R, t 2.1 to 4.2) **and fatter left tails**:
  2.7% and 5.1% lost more than 1.5R through a gap, against 0.8% and 1.1% of the others; the 1st percentile was
  -2.0R and -2.4R against -1.4R and -1.5R. The higher average comes from today's survivors and is not evidence; the
  tail is the reason for an event-risk safeguard.
