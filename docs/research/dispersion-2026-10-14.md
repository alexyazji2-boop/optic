# VIXEQ − VIX: does dispersion come before stress? (2026-10-14)

**Claim** (a trading post). "When the spread rises, the S&P 500 can look calm while the average stock becomes much more volatile. That is often where market stress starts."

**Data.**
- Cboe's daily index files: VIXEQ and DSPX from 2014-06-19, COR1M from 2006, the VIX from 1990.
- The S&P 500 from Yahoo.
- Joined sample: 3,098 days.

**Method** (`dispersion_study.py`).
- **Outcomes.** Over the next 21 and 63 sessions: the S&P 500's maximum drawdown from today's close, and the VIX's change.
- **Buckets.** Quintiles of the gap (VIXEQ − VIX), of its 21-day change, of COR1M, of DSPX and of the VIX itself. Quintiles are cut on data up to each day only (expanding, from 504 days), so there is no look-ahead.
- **Overlap.** The windows overlap, so the day counts overstate the independent evidence by roughly 21 to 63 times.

## Result

Share of days followed by an S&P drawdown of 10% or more within 63 sessions, by quintile (lowest to highest):

| Bucketed by | Q1 | Q2 | Q3 | Q4 | Q5 |
|---|---|---|---|---|---|
| VIXEQ − VIX gap | 5.9% | 5.5% | 12.8% | 16.0% | 13.1% |
| Gap's 21-day change | 10.5% | 16.1% | 11.7% | 11.0% | 12.3% |
| COR1M (implied correlation) | 8.4% | 10.9% | 11.0% | 24.1% | 19.7% |
| DSPX | 8.2% | 2.4% | 6.3% | 10.2% | 16.7% |
| **VIX itself** | **0.3%** | **9.0%** | **9.3%** | **16.8%** | **18.6%** |

Mean 63-session drawdown by VIX tercile (rows) and gap tercile (columns), full-sample cuts:

| VIX \ gap | Low | Mid | High |
|---|---|---|---|
| Low | -4.2% | -5.0% | -3.9% |
| Mid | -4.6% | -4.1% | -4.5% |
| High | -3.4% | -5.1% | -5.2% |

**Reading.**
- **The level.** A wide gap came before 10% drawdowns more often than a narrow one. But the VIX alone sorts the same outcomes more sharply, and within each VIX tercile the gap adds nothing consistent.
- **The rise.** A rising gap, which is what the post describes, predicted nothing.
- **Correlation.** High implied correlation was the more informative of the dispersion measures, not low correlation. Correlation spikes during sell-offs, so this is largely the VIX again.

**Verdict.** The descriptive half is supported. A wide gap means single stocks are expected to move a lot but not together, and that is what keeps the index calm. The predictive half ("where stress starts") is unsupported beyond what the VIX already says.

**On 2026-10-13.**
- The gap was 24.5 points, wider than 98% of days since 2014.
- COR1M was 7.6, lower than 99% of days.
- DSPX was at its 96th percentile.

**In the product.**
- The Dispersion panel on the Markets page (`app/analytics/dispersion.py`, `/api/dispersion`) shows these readings, with this finding stated beside them.
- The Desk gets an evidence row whose method tells the writer not to call the gap a warning.
- Milo is told the same.
- Cboe's history files are read only when `OPTIC_CBOE_HISTORY` is set. Cboe's site terms are for personal use, so public display is the owner's decision. Without them, percentiles come from Yahoo (DSPX, from May 2024) and from Optic's own daily store.
