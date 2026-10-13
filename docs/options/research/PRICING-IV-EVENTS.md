# Pricing, Greeks, Delta, IV, Expected Move, Expiration and Event Risk

Research for the Optic Terminal Options tab. All sources read 2026-10-13 unless marked otherwise.
Labels: **MATH** (pricing/risk mathematics), **EMP** (empirical, study and sample cited), **HEUR**
(practitioner heuristic), **MKT** (marketing/unverified), **PROP** (proprietary, not reproducible).
**Fact** marks a contractual/regulatory rule taken from the cited exchange, OCC or FINRA document.
Data constraint throughout: Yahoo/yfinance chains give bid, ask, last, volume, prior-session OI, Yahoo's IV,
strike, expiry, ITM flag and last trade time. No IV history, no dividend schedule in the chain, no rates,
quotes ~15 min delayed. Note on citations: the LibKey connector was not available in this session, so DOIs
below come from publisher/RePEc/SSRN listings and were not checked through LibKey.

STATUS: complete (2026-10-13).

---

## 1. Pricing and Greeks

### 1.1 Black-Scholes-Merton with continuous dividend yield (the baseline Optic already uses)
- **MATH.** Generalised BSM (Merton 1973) with continuous yield q:
  C = S e^{-qT} N(d1) - K e^{-rT} N(d2), P = K e^{-rT} N(-d2) - S e^{-qT} N(-d1),
  d1 = [ln(S/K) + (r - q + sigma^2/2)T] / (sigma sqrt T), d2 = d1 - sigma sqrt T.
  Equivalent forward form: F = S e^{(r-q)T}, C = e^{-rT}[F N(d1) - K N(d2)]. Source: standard text
  (Hull, *Options, Futures and Other Derivatives*, ch. on BSM); summary at
  https://acadifi.com/question-bank/q/bsm-n-d2-risk-neutral-probability-1c03ey (read 2026-10-13).
- Rationale: European, lognormal, constant vol. Good enough for Greeks display on liquid names when the
  input IV came from the same model; it is the convention behind Yahoo/broker IV numbers.
- Required data: S, K, T, r, q, sigma. Yahoo chain gives K, T (date only), sigma (Yahoo's IV, method
  undisclosed = **PROP**). S comes from the quote endpoint (delayed). r and q are NOT in the chain: q can be
  approximated from yfinance `dividendYield`/trailing dividends; r must come from elsewhere (Treasury bills).
- Failure modes: (a) discrete dividends on single stocks (yield approximation misprices calls straddling an
  ex-date); (b) American early exercise (deep ITM puts, ITM calls before ex-dividend); (c) Yahoo IV computed
  with unknown r, q, price (mid vs last) and time convention, so recomputing Greeks with Optic's own r/q and
  Yahoo's IV is internally inconsistent; (d) stale `last` prices on illiquid strikes.

### 1.2 Discrete dividends and American exercise
- **MATH.** For a discrete cash dividend D paid at t_D < T, the European escrowed-dividend model replaces S
  with S - PV(D) (Hull). Continuous yield is exact only for indices with a smooth dividend stream; for single
  stocks with one or two quarterly dividends in the option's life, the escrowed model or a binomial tree with
  discrete dividends is the standard fix.
- **MATH.** An American call on a non-dividend stock is never optimally exercised early (Merton 1973). With
  dividends, early exercise of a call is optimal only just before an ex-date, and only if the dividend
  exceeds the call's remaining time value (roughly: D > K(1 - e^{-r(T - t_D)}) plus the put value at the
  same strike). Practitioner restatement: exercise the day before ex-date when the dividend exceeds the
  extrinsic value of the same-strike put (**HEUR**, a put-call-parity shortcut). Sources: Nasdaq/OIC-style
  article https://www.nasdaq.com/articles/how-dividends-affect-early-exercise-calls-2019-03-07; Schwab,
  https://international.schwab.com/story/ex-dividend-dates-understanding-dividend-risk (both read 2026-10-13).
- **MATH.** American puts can be optimally exercised early at any time when deep ITM, because receiving K now
  earns interest; the early-exercise premium grows with r and depth ITM. With r near 4-5% (2023-2026), this is
  not negligible for deep ITM puts with months to expiry.
- Assignment risk implication (**MATH + HEUR**): a short ITM call whose extrinsic value is below the upcoming
  dividend is at high risk of assignment on the day before ex-date; this hits the short leg of covered calls
  and call verticals. Optic can compute this flag with chain data plus the next ex-date and amount (yfinance
  `Ticker.calendar`/`dividends` gives historical and sometimes next ex-dates; not guaranteed).
- Implementation cost: S for a dividend flag; M for a CRR binomial (200 steps) American pricer used only for
  IV inversion/Greeks on single stocks.
- Validation: compare Optic's European BSM price at Yahoo IV to mid for deep ITM puts; the gap is the
  early-exercise premium plus noise. Spot-check against a broker's displayed Greeks (manual, read-only).

### 1.3 Units and conventions (where most "Optic disagrees with my broker" reports come from)
- **MATH** definitions; unit choices are conventions (state them in the UI):
  - Delta: dV/dS per $1 move in the underlying, per share. Per contract multiply by 100 (standard equity
    multiplier). Call delta = e^{-qT}N(d1); put delta = -e^{-qT}N(-d1).
  - Gamma: change in delta per $1 move. Gamma = e^{-qT} n(d1) / (S sigma sqrt T).
  - Theta: dV/dt. The model gives an annual figure; dividing by 365 gives per calendar day, by 252 per trading
    day. Many retail platforms show per calendar day (/365); some use /252. No single correct choice; state it.
    Source: https://www.marketdata.app/sheets/options/how-to-calculate-theta/index.md and
    https://snapfi.netmark.com/glossary/theta-call/ (read 2026-10-13). I could not confirm IBKR's or Schwab's
    displayed theta convention from their public pages; treat broker-specific claims as unverified.
  - Vega: dV/dsigma per 1 vol point (0.01 in sigma), i.e. analytic vega / 100. Vega = S e^{-qT} n(d1) sqrt T / 100.
  - Rho: dV/dr per 1 percentage point (0.01) change in r, i.e. analytic rho / 100. Call rho = K T e^{-rT}N(d2)/100.
- Time to expiry (**MATH convention, documented by Cboe**): Cboe's VIX methodology counts time in minutes,
  T = minutes / 525,600, with the settlement-day minutes counted to 8:30 a.m. CT for AM-settled standard SPX
  and to 3:00 p.m. CT for PM-settled weeklies. Source: Cboe VIX Methodology PDF,
  https://cdn.cboe.com/resources/vix/VIX_Methodology.pdf (read 2026-10-13). For equity options, the last
  trading moment is the 4:00 p.m. ET close on expiration day. Optic should set expiry = 16:00 ET on the expiry
  date for PM-settled products and to the 9:30 ET open for AM-settled SPX/NDX/RUT standard monthlies, and use
  calendar time (/365) consistently. Using "days = expiry date - today" in whole days produces large errors
  on 0-2 DTE options (on expiry morning T would be 0 and Greeks blow up or divide by zero).
- Risk-free rate (**MATH convention**): Cboe interpolates US Treasury Constant Maturity yields with a cubic
  spline to each expiry (same VIX source). Brokers vary (some use SOFR/OIS or a broker curve; not publicly
  documented, **PROP**). For Optic: a 1- or 3-month T-bill yield (FRED DGS1MO/DGS3MO or Treasury daily par
  yield curve) interpolated by expiry is defensible. Effect is second-order except for rho, deep ITM puts and
  long-dated LEAPS.
- Why model values differ from broker values (summary): different IV per strike (mid vs mark vs last;
  smoothed surface vs raw), different T (minutes vs days, calendar vs trading), different r and q, European vs
  American model, dividend treatment, and quote timing (Yahoo delayed ~15 min vs broker real-time). Optic
  should show "Model: Black-Scholes, European, q = x%, r = y%, T to 4pm ET" in a tooltip.

### 1.4 Higher-order Greeks used by Optic's VEX
- **MATH.** Vanna = d(delta)/d(sigma) = d(vega)/dS = -e^{-qT} n(d1) d2 / sigma. Units: change in delta per
  1.00 change in sigma; divide by 100 for "per vol point". Charm (delta decay) = d(delta)/dt as calendar time passes (= -d(delta)/d(tau)); for a call:
  charm = q e^{-qT}N(d1) - e^{-qT} n(d1) [2(r-q)T - d2 sigma sqrt T] / (2 T sigma sqrt T), per year; divide by
  365 for per calendar day. Volga/vomma = vega d1 d2 / sigma. Source: standard texts (Haug, *The Complete Guide
  to Option Pricing Formulas*, 2nd ed., 2007); not re-fetched online.
- Optic's VEX (vanna x OI x 100 x sign assumption) inherits the dealer-positioning assumption of GEX
  (**HEUR/PROP**: the dealer sign is not observable from Yahoo data). Optic should label VEX as "if dealers are
  short calls / long puts" and state units (e.g. $ delta change per 1 vol point).

---

## 2. Delta

### 2.1 What delta is
- **MATH.** Delta is the hedge ratio: the first-order change in option value for a $1 change in the
  underlying, under the model. It changes with price (gamma), time (charm) and vol (vanna). For a move dS,
  dV ~ delta dS + 0.5 gamma dS^2; delta alone underestimates gains and overstates losses for long options
  on large moves.
- **MATH.** Delta is not a probability. Under BSM the risk-neutral probability that a call finishes ITM is
  N(d2); call delta is e^{-qT}N(d1), which is the ITM probability under the stock-numeraire measure. N(d1) >
  N(d2) always (they differ by sigma sqrt T), so call delta overstates the risk-neutral ITM probability; the gap
  is small for short-dated, low-vol options and large for long-dated or high-vol ones. Source:
  https://acadifi.com/question-bank/q/bsm-n-d2-risk-neutral-probability-1c03ey;
  https://snapfi.netmark.com/glossary/delta-call/ (read 2026-10-13).
- **MATH.** Even N(d2) is a risk-neutral probability: it uses drift r - q, not the real-world expected return,
  and it ignores the volatility risk premium (Section 3), so it is not a forecast. Real-world probability of
  finishing ITM differs by (mu - r) drift and by the gap between implied and future realised vol.
- **MATH.** With skew, the risk-neutral ITM probability is the digital price, -dC/dK, which adds a skew
  term: P(S_T > K) = N(d2) - e^{rT} x vega_analytic x dsigma/dK (Breeden-Litzenberger logic). With normal
  equity put skew (dsigma/dK < 0) the skew term is positive, so the market-implied probability of finishing
  above an OTM call strike is higher than N(d2) at that strike's IV, and the probability of finishing below
  an OTM put strike is lower than N(-d2) suggests. Optic can estimate it model-free from adjacent mids:
  P(S_T > K) ~ e^{rT}[C(K - h) - C(K + h)] / (2h). Requires two-sided quotes on both strikes.
- **Probability of profit** is a different quantity again: for a long call, P(S_T > K + premium), not P(S_T > K).

### 2.2 Delta ranges by strategy: evidence vs heuristic
- **HEUR.** The "sell ~16-30 delta" and "buy 70+ delta for stock replacement" guides come from practitioner
  education (tastylive backtests on SPY/ index short premium; broker education). tastylive studies are
  in-house backtests without published code or full methods (**PROP/HEUR**). They show positive historical
  returns for short premium on indices, which is consistent with the academic variance risk premium (EMP,
  Section 3), but they do not establish an optimal delta.
- **EMP (related).** Academic evidence that index option sellers earned a premium on average: Coval & Shumway
  (2001, *Journal of Finance* 56(3)) on S&P 500 straddles; Bakshi & Kapadia (2003, *RFS* 16(2)) on negative
  volatility risk premium in delta-hedged gains. Those are index results; single-stock evidence is weaker and
  mixed. (Citations from standard literature; not re-fetched.)
- Optic implication: present delta as "approx. shares-equivalent exposure" and, separately, "market-implied
  chance of finishing ITM (risk-neutral, not a forecast)" using N(d2) or the skew-adjusted spread estimate.
  Do not label delta "probability of profit".

---

## 3. Implied volatility

### 3.1 What Yahoo's IV column is (and is not)
- **PROP.** Yahoo does not publish how `impliedVolatility` is computed (model, price used, r, q, timestamp).
  Users report wrong values, especially outside market hours. Sources: https://github.com/schepal/yahoo_vol;
  R-SIG-Finance thread (2016) https://r-mailing-lists.thecoatlessprofessor.com/lists/r-sig-finance/msg/msg-f06e6e87e238
  (both read 2026-10-13). A 2024 *Journal of Futures Markets* study of OptionMetrics found that a one-minute
  timestamp mismatch between option and stock closes creates artificial IV spreads, and wrong dividend inputs
  create IV outliers (summarised in the same search; vendor-agnostic lesson, **EMP**).
- Optic should invert its own IV from the bid/ask mid with its own S, T, r, q (Section 1), keep Yahoo's IV only
  as a fallback, and drop quotes with bid = 0 or spread/mid > ~50% (Cboe's VIX excludes zero-bid options and
  stops after two consecutive zero bids; https://cdn.cboe.com/resources/vix/VIX_Methodology.pdf). Outside
  09:30-16:00 ET, Yahoo's bid/ask are often zero or stale; flag "quotes from last session".
- Validation: on liquid names (SPY, AAPL), compare self-inverted mid IV vs Yahoo IV across strikes during RTH;
  expect agreement within ~1 vol point near ATM. Large systematic gaps indicate a T or q convention mismatch.

### 3.2 IV rank vs IV percentile
- **HEUR (definitions, practitioner standard; tastylive).** IV Rank = (IV_now - min IV_252) / (max IV_252 -
  min IV_252) x 100. IV Percentile = share of the past 252 trading days with IV below IV_now, x 100. IVR is
  driven by two extreme days; IVP is less sensitive to one spike. tastylive does not state which IV series
  (which expiry/composite) it uses. Source: https://www.tastylive.com/definitions/iv-rank-iv-percentile (read
  2026-10-13). Both require a daily IV history for the same constant-maturity series (e.g., 30-day ATM IV).
- **MATH/EMP: a realised-vol proxy measures a different thing.** Implied variance is a risk-neutral expectation
  and contains a variance risk premium (VRP). Carr & Wu (2009, *RFS* 22(3):1311-1341, DOI 10.1093/rfs/hhn038)
  synthesise variance swap rates from option portfolios for 5 indices and 35 stocks (1996-2003) and find
  strongly negative VRPs (implied > subsequent realised) for indices; the premium is smaller and less uniform for
  single stocks (https://ideas.repec.org/a/oup/rfinst/v22y2009i3p1311-1341..html, read 2026-10-13).
  Bollerslev, Tauchen & Zhou (2009, *RFS* 22(11):4463-4492, DOI 10.1093/rfs/hhp008) show the implied-minus-
  realised variance gap predicts quarterly S&P 500 returns after 1990 (https://scholars.duke.edu/publication/732839).
  Implication: ranking today's IV against a 1-year range of realised vol will read "high" most of the time on
  indices, simply because IV usually exceeds RV. It is not an IV rank and must not be labelled one.
- Options for Optic:
  1. (S) Rename the current metric "IV vs realised vol" and show the ratio IV30/RV20 (or IV - RV in vol points),
     which is a legitimate VRP-style quantity, with the note "IV is usually above realised; ratio > 1 is normal".
  2. (M) Start storing a daily snapshot of Optic's own 30-day constant-maturity ATM IV per ticker at ~15:45 ET
     (or first fetch after close, flagged). After 60 trading days show a provisional percentile; after 252, true
     IVR/IVP. Cost: one row per ticker per day.
  3. (S) For SPX/Nasdaq/Russell, Cboe indices on Yahoo (^VIX, ^VIX9D, ^VIX3M, ^VXN, ^RVX) have full history and
     give a real IV rank/percentile today (availability on Yahoo to be verified per symbol).

### 3.3 Term structure
- **MATH.** Build per-expiry ATM IV at the forward (strike where call mid - put mid crosses zero, F = K +
  e^{rT}(C - P), as in Cboe's VIX method), interpolating IV in log-moneyness between the two strikes around F.
  Constant-maturity points (7, 30, 60, 90 days) by linear interpolation in total variance sigma^2 T between the
  bracketing expiries, the same weighting VIX uses for 30 days
  (VIX = 100 sqrt{[T1 s1^2 (N2 - N30)/(N2 - N1) + T2 s2^2 (N30 - N1)/(N2 - N1)] x N365/N30}).
  Source: https://cdn.cboe.com/resources/vix/VIX_Methodology.pdf (read 2026-10-13).
- Total variance must be non-decreasing in T (calendar no-arbitrage, **MATH**); if sigma1^2 T1 > sigma2^2 T2 the
  data is bad or an event sits in the front expiry. Optic should check this and flag rather than plot it.
- **HEUR.** "Backwardation" (front IV > back IV) signals near-term event or stress; contango is normal. Useful
  as description, not as a timing signal. Weekends/holidays create a sawtooth in calendar-day IV for weeklies
  (moontower, https://moontowermeta.com/how-an-option-trader-extracts-earnings-from-a-vol-term-structure/, read
  2026-10-13).

### 3.4 Skew measures
- **MATH/HEUR conventions.**
  - 25-delta risk reversal: RR25 = IV(25-delta call) - IV(25-delta put), same expiry (FX convention; equity desks
    often quote put minus call as "skew"; Optic must state the sign). Normally negative for equity indices.
  - 25-delta butterfly: BF25 = [IV(25c) + IV(25p)]/2 - IV(ATM): curvature/tail price.
  - Normalised slope: (IV(25p) - IV(ATM)) / IV(ATM), comparable across names with different vol levels.
  - Model-free: Cboe SKEW index (based on Bakshi-Kapadia-Madan risk-neutral skewness), SPX only.
  Deltas must be computed with each strike's own IV and fixed (r, q, T); interpolate IV in delta space.
- **EMP.** Xing, Zhang & Zhao (2010, *JFQA* 45(3):641-662): steepest single-stock smirk (OTM put IV - ATM call IV)
  quintile underperformed flattest by ~10.9%/yr risk-adjusted, 1996-2005; a later preprint reports the effect is
  weaker after 2020 (https://ideas.repec.org/a/cup/jfinqa/v45y2010i03p641-662_00.html; arXiv 2608.26115, unreviewed).
  Cremers & Weinbaum (2010, *JFQA* 45(2):335-367): call-minus-put IV spread at matched strikes predicted weekly
  returns (~50 bp/week long-short, 1996-2005), declining over the sample
  (https://ideas.repec.org/a/cup/jfinqa/v45y2010i02p335-367_00.html). These are cross-sectional, weekly-rebalanced
  portfolio results on OptionMetrics data, not single-ticker trade signals; and they predate today's retail flow.
- **MATH: put-call IV gap at the same strike is mostly parity, not sentiment.** For European options C - P =
  S e^{-qT} - K e^{-rT}. If Optic's q (or borrow cost) is wrong, call and put IVs at the same strike diverge
  mechanically. Hard-to-borrow stocks show put IV >> call IV because the stock-borrow fee acts like an extra
  dividend; American exercise and pre-ex-dividend calls add further gaps. Optic can back out the implied
  forward/"implied dividend+borrow" per expiry from ATM call-put mids, then use that forward for all IVs, which
  removes most of the gap. Flag gaps > a few vol points as "possible borrow/dividend effect", not "bearish".

### 3.5 VIX as a model-free reference
- **MATH.** VIX = 30-day risk-neutral expected variance (variance-swap strip) of SPX from OTM option mids weighted
  by dK/K^2, with forward from put-call parity, CMT rates via cubic spline, time in minutes, near/next expiries
  of 23-37 days interpolated to 30 days (Cboe methodology above). It is not BSM ATM IV; VIX is usually above ATM
  IV because the strip includes the put wing.
- Optic use: a per-ticker "VIX-style 30d IV" can be computed from Yahoo chains with the same formula (data
  available: bid/ask/strike/expiry), but wings on single stocks are thin and Yahoo bids are delayed; truncate
  at two zero bids as Cboe does and label as an approximation. Validation: compute it for SPY and compare with
  ^VIX (SPY vs SPX differ by dividends/American style; expect ~0.5-1.5 pt differences).

---

## 4. Expected move

### 4.1 Straddle vs 1-SD move (the units differ)
- **MATH.** Under BSM with ATM-forward strike, straddle = e^{-rT} E|S_T - F| ~ sqrt(2/pi) x sigma S sqrt T
  ~ 0.798 sigma S sqrt T. So the ATM straddle is (approximately) the market price of the expected ABSOLUTE move
  (mean absolute deviation), and the 1-SD move is sigma S sqrt T ~ 1.25 x straddle.
- **HEUR.** tastylive's "expected move" = 85% of the front-month ATM straddle (or average of ATM straddle and
  1st-OTM strangle), recommended only the day before a binary event or close to expiration.
  Source: https://www.tastylive.com/definitions/calculating-expected-move (read 2026-10-13). 0.85 x straddle ~
  0.68 x 1-SD, i.e. a band narrower than one standard deviation; the commonly repeated "contains the move 68% of
  the time" is therefore inconsistent with the math unless the distribution is fat-tailed (**MKT/HEUR**; it is
  repeated by third-party explainers such as https://flashalpha.com/concepts/expected-move without evidence).
- **MATH.** 1-SD move from IV: EM_1sd = S x sigma x sqrt(T), with T in years using calendar time to the expiry
  timestamp (Section 1.3). Under the lognormal model, P(|ln(S_T/S)| < sigma sqrt T) ~ 68% (risk-neutral). The
  price band is asymmetric: [S e^{-sigma sqrt T}, S e^{+sigma sqrt T}].
- What a 1-SD move does not mean: (a) not a real-world probability (risk-neutral, includes VRP so IV-based bands
  are on average too wide on indices; Section 3.2); (b) not symmetric under skew (the risk-neutral down tail is
  fatter); (c) not a bound (equity returns are fat-tailed; >3-SD days occur far more often than normal implies);
  (d) not a path statement (price can breach the band intraday and finish inside).
- Optic recommendation: show one number with an explicit definition. Preferred: "Options price a typical move of
  +/-$X (ATM straddle, = expected absolute move)" and, in detail view, "1-SD range (from IV): $L-$H". Do not mix the
  two or apply 0.85 without saying so.
- Validation (EMP, Optic can run itself): log the straddle-implied move at each earnings/weekly expiry and the
  realised |close-to-close| move; report hit rates and mean ratio realised/implied by ticker class. No IV history
  is needed, just storing the prediction before the event.

### 4.2 Earnings implied move from the term structure
- **MATH (variance additivity).** Model each expiry's total variance as base variance plus one event jump:
  sigma_i^2 T_i = sigma_b^2 T_i + E (E = event variance, in annualised-vol^2 x years units).
  - With one expiry before (T0, IV s0) and one after (T1, IV s1) the event, assuming the pre-event IV is the base:
    E = s1^2 T1 - s0^2 T1.
  - With two expiries both after the event (T1 < T2) and constant base vol:
    E = T1 T2 (s1^2 - s2^2) / (T2 - T1); sigma_b^2 = (s2^2 T2 - s1^2 T1) / (T2 - T1).
  - Event 1-SD move = sqrt(E) (fraction of S); expected absolute move ~ 0.8 sqrt(E).
  Worked practitioner version with 39 regular days + 1 event day: moontower,
  https://moontowermeta.com/how-an-option-trader-extracts-earnings-from-a-vol-term-structure/ (read 2026-10-13).
  Caveats from that source: result depends on base-vol assumption and calendar convention; other events (CPI,
  FOMC) also bump the curve; events far out are diluted. Require E > 0; if negative, show nothing.
- Simple alternative (what most retail tools show, **HEUR**): front-expiry-after-earnings ATM straddle / S (minus a
  base-vol allowance for extra days). Close when the expiry is 1-3 days after the event.
- Data in Yahoo chains: yes (ATM bid/ask for each weekly expiry; earnings date from yfinance calendar, which is
  sometimes estimated, flag "unconfirmed date").

### 4.3 IV crush: evidence
- **EMP.** Patell & Wolfson (1979, *J. Accounting & Economics* 1:117-140): BSM implied variances of calls rise into
  annual earnings announcements and fall afterwards (https://www.gsb.stanford.edu/faculty-research/publications/anticipated-information-releases-reflected-call-option-prices,
  read 2026-10-13). Dubinsky, Johannes, Kaeck & Seeger (2019, *RFS* 32(2):646-687, DOI 10.1093/rfs/hhy060):
  option-implied earnings-day uncertainty is large, time-varying, and informative about future volatility; adding
  earnings-date jumps cuts pricing errors substantially (https://ideas.repec.org/a/oup/rfinst/v32y2019i2p646-687..html).
- **EMP (conflicting with "always sell the crush").** Gao, Xing & Zhang (2018, *JFQA* 53(6):2587-2617, DOI
  10.1017/S0022109018000285): ATM straddles bought 3 days before announcements and held to the announcement earned
  ~3.34% on average (significant), larger for small, high-vol, high-kurtosis firms; i.e. pre-announcement option
  prices on average UNDERstated earnings uncertainty in their sample, even though IV falls after the event
  (https://resolve.cambridge.org/core/journals/journal-of-financial-and-quantitative-analysis/article/anticipating-uncertainty-straddles-around-earnings-announcements/7B34877AD5E06304BA3C55FBA3219FDD).
  Transaction costs (wide single-stock spreads) absorb much of such returns in practice.
- Implication: IV crush is a certainty about IV (it falls once the event passes), not about P&L. Optic may say "IV
  is expected to drop after the report; long options need a move larger than ~$X to profit" and must not imply that
  selling earnings premium has positive expectation.

---

## 5. Expiration and event risk

### 5.1 Settlement and exercise style (facts Optic should encode per root symbol)
- **Fact (exchange specs).** SPX (standard, 3rd Friday) is European, cash-settled, AM-settled: last trading day is
  ordinarily the preceding business day (usually Thursday), and the settlement value (SET) uses opening prints of
  each component on expiration morning. SPXW (weeklies, Mon-Fri and EOM, including 3rd-Friday PM series) is
  European, cash-settled, PM-settled on closing prints; expiring SPXW trade until 3:00 p.m. CT (4:00 p.m. ET).
  Multiplier $100; cash delivered next business day. Source: Cboe SPX specifications,
  https://ww2.cboe.com/tradable_products/sp_500/spx_options/specifications (read 2026-10-13).
- XSP (Mini-SPX, 1/10 SPX): European, cash-settled, PM-settled weeklies; Cboe lists it as Section 1256-eligible.
  SPY options: American, physically settled in ETF shares, PM. Source:
  https://www.cboe.com/insights/posts/why-trade-xsp-vs-spy-a-breakdown-of-the-benefits (Cboe, 2023-06-01; read
  2026-10-13). Tax fact only (no advice): Cboe states that gains/losses on certain exchange-listed index options
  (incl. SPX) may be taxed 60% long-term / 40% short-term under IRC Section 1256, subject to the Code's criteria;
  ETF and equity options are not Section 1256 contracts (same Cboe sources).
- NDX: European, cash-settled; standard 3rd-Friday NDX is AM-settled (value XQO from Nasdaq Official Opening
  Prices); NDXP (Mon-Fri) is PM-settled (XQC). Source: https://www.nasdaq.com/NDX_NDXP_Factsheet and SEC release
  34-96980 https://www.sec.gov/file/34-96980 (read 2026-10-13).
- Equity and ETF options: American, physically settled (100 shares per contract), stop trading at 4:00 p.m. ET on
  expiry (some ETF options trade to 4:15 p.m. ET; check per product).
- **Optic risk (data, HEUR):** Yahoo's ^SPX chain can mix SPX (AM) and SPXW (PM) series on the same date; the
  root is visible in `contractSymbol`. Optic should parse the root, set the expiry timestamp accordingly (AM:
  09:30 ET open on expiry day; PM: 16:00 ET) and show "AM-settled: last trade Thursday" on those rows. Verify on a
  live 3rd-Friday chain.
- AM-settlement risk (**MATH/fact**): the SET can differ materially from Thursday's close (overnight gap), and the
  position cannot be closed after Thursday's session. Optic's Greeks for AM series should use T to Friday open.

### 5.2 Exercise by exception, cut-offs and pin risk
- **Fact (OCC/FINRA).** OCC Rule 805 exercise-by-exception: expiring equity options ITM by $0.01 or more (based on
  the underlying's closing price) are exercised automatically unless the holder submits contrary instructions;
  the threshold was lowered from $0.05 to $0.01 effective the June 2008 expiration (SR-OCC-2007-18,
  https://www.sec.gov/file/34-57163; Phlx memo https://www.nasdaqtrader.com/content/phlxmemos/2008/Jun/1107-08.pdf;
  IBKR https://www.interactivebrokers.com/en/trading/delivery-exercise-actions.php; read 2026-10-13). Holders may
  give a Contrary Exercise Advice until 5:30 p.m. ET on expiry; brokers may set earlier cut-offs (FINRA Information
  Notice 2021-02-03, https://www.finra.org/rules-guidance/notices/information-notice-020321). Cash-settled index
  options are auto-exercised when the settlement amount is positive (OCC rule exhibits, SR-OCC-2022-003/009 on
  sec.gov; current rulebook text not independently confirmed).
- **MATH/fact: pin risk.** A short option with the underlying near the strike at the close cannot know if it will be
  assigned: after-hours moves until 5:30 p.m. ET can lead longs to exercise (or not) against the $0.01 default.
  Result: an unintended long/short 100-share position per contract over a weekend. Physical settlement only; cash-
  settled European index options have no pin-assignment ambiguity (but AM settlement has gap risk).
- **EMP.** Ni, Pearson & Poteshman (2005, *JFE* 78(1):49-87, DOI 10.1016/j.jfineco.2004.08.005): optionable stocks'
  closes cluster at strikes on expiration dates; returns altered by >= 16.5 bp on average; attributed to market-
  maker hedge rebalancing and to manipulation by proprietary traders (CBOE/ISE data, 1996-2001 era)
  (https://scholars.hkbu.edu.hk/en/publications/stock-price-clustering-on-option-expiration-dates-3/). Effect sizes
  in today's market are not established; "max pain" style claims that prices are pulled to the strike minimizing
  option-holder value are **HEUR/MKT** and are not the same finding.
- **Optic flag (S):** for any equity/ETF position the plan suggests holding into expiry, show "Within X% of strike
  at expiry: assignment uncertain (pin risk). Close before 4:00 p.m. ET to avoid it." Compute from delayed spot.

### 5.3 Early assignment and dividends (American products)
- **MATH (see 1.2).** Short ITM calls with extrinsic < next dividend are likely assigned the day before ex-date;
  deep ITM short puts can be assigned any time once extrinsic ~ 0 (more likely with higher r).
- **Fact (OCC).** Ordinary (regular) cash dividends do not adjust contracts; non-ordinary (special) dividends are
  normally adjusted if >= $0.125/share ($12.50 per standard contract). OCC 2024 information memo and 2012 by-law
  change (CFTC/SEC filings, e.g. https://www.cftc.gov/filings/orgrules/rules02202411923.pdf, read 2026-10-13).
  Optic should not treat an adjusted (non-standard deliverable) series like a standard one; Yahoo marks these only
  through odd contract symbols (e.g., root with a digit), so filter or flag them.
- Spread risk: early assignment on the short leg of a vertical turns a defined-risk spread into a stock + long
  option position temporarily; max loss is unchanged only if the long leg is exercised/sold promptly (**MATH**).

### 5.4 0DTE: growth and evidence
- **Fact (Cboe, interested party).** SPX 0DTE reached a record 62.4% of SPX volume in Aug 2025 (~2.4M contracts/day);
  retail estimated ~50-60% of SPX 0DTE volume; >95% of 0DTE trades are long options or spreads; customer flow
  "extremely balanced"; net market-maker gamma hedging at most ~0.2% of SPX daily liquidity. Sources: Cboe
  Insights (M. Xu), https://www.cboe.com/insights/posts/spx-0-dte-options-jump-to-record-62-share-in-august
  (2025-09-02) and https://www.cboe.com/insights/posts/0-dt-es-decoded-positioning-trends-and-market-impact
  (2025-05-02), read 2026-10-13. Cboe's full-year 2025 SPX 0DTE share ~59% (Cboe IR, Jan 2026). Note Cboe earns fees
  on this volume; its positioning data are proprietary (**PROP**) but observed (trade-level open/close, customer vs MM).
- **EMP.** Beckmeyer, Branger & Gayda (2023, SSRN 4404704), Cboe SPX trade data with trader-type codes, Jan 2021-Feb
  2023: retail lost >$70M on 0DTE SPX; average daily retail loss $184k overall, $358k after daily expirations
  began (May 2022); >$50M of losses attributed to transaction costs (bid-ask). Secondary summaries:
  https://www.bloomberg.com/news/articles/2023-04-21/day-traders-lose-358-000-per-day-gambling-on-zero-day-options;
  https://neudata.co/literature-reviews/zero-day-to-expiry-options-a-losing-bet-for-retail-traders (read
  2026-10-13; SSRN page returned 403).
- **EMP.** Dim, Eraker & Vilkov (working paper, 2024): higher 0DTE open-interest gamma is associated with LOWER
  intraday realised volatility; no evidence 0DTE gamma propagates volatility; volume shocks do not amplify returns
  (Oxford seminar abstract https://www.maths.ox.ac.uk/node/67396; read 2026-10-13). Adams et al. (SSRN 5641974)
  report MM net gamma predicts lower next-10-minute SPX volatility (QuantPedia summary). Some other studies find a
  positive 0DTE-volatility association; evidence is not uniform (Princeton thesis 2026 literature review).
- **EMP.** Bandi, Fusari & Reno, "0DTE Option Pricing" (SSRN 4503344; JF forthcoming per one reference list,
  unconfirmed): intraday SPX 0DTE data Jan 2014-May 2023; standard models misprice 0DTEs; time-varying skewness and
  kurtosis via leverage and vol-of-vol fix much of it; 0DTE variance/return risk premia are estimated
  (https://liverpool.ac.uk/management/conferences-and-events/0dte-option-pricing-seminar). Related work finds 0DTEs
  carry large risk premia that transaction costs largely erase (HKUST, 2026,
  https://bm.hkust.edu.hk/bizinsight/2026/04/are-0dte-options-mispriced; not peer-reviewed).
- Implications for Optic: (a) Yahoo data (15-min delayed, no sizes) is unfit for intraday 0DTE decisions; GEX/VEX
  built on prior-session OI ignore all same-day 0DTE positioning, which on SPX is most of the volume; label GEX as
  "based on yesterday's open interest; excludes today's 0DTE trades". (b) BSM Greeks become numerically unstable
  as T -> 0 (gamma ~ 1/sqrt T); compute T in minutes, floor T at e.g. 5 minutes, and hide gamma/theta for the
  last 30 minutes. (c) Do not generate 0DTE entry plans; if shown, show spread cost as % of premium first.

---

## Research-to-implementation matrix

| Approach | Evidence type | Data in Optic now? | Build or change | Effort | Validation |
|---|---|---|---|---|---|
| T in minutes to 16:00 ET (09:30 for AM-settled), /365 | MATH (Cboe VIX convention) | Yes (expiry date + clock) | Replace day-count T; root parse SPX vs SPXW | S | Greeks continuous through expiry day; compare to broker on 0-2 DTE |
| Self-inverted IV from mid with own r, q | MATH | Bid/ask yes; r no; q partial | Add T-bill rate (FRED/Treasury daily), q from yfinance; Brent solver; drop zero bids | S-M | Agreement with Yahoo IV near ATM on SPY/AAPL within ~1 pt |
| Implied forward from ATM put-call mids | MATH | Yes | Per-expiry F; use F for ATM, deltas, skew | S | Put/call IV gap at ATM collapses to < 1 pt on liquid names |
| American pricer (CRR/BAW) for single stocks | MATH | Needs dividend dates | Binomial with discrete dividends for IV/Greeks | M | Deep ITM put mid vs European model gap |
| Early-assignment / ex-div flag | MATH + HEUR | Ex-date partial (yfinance) | Flag short ITM call where extrinsic < dividend before ex-date | S | Back-check flagged names vs ex-dates |
| Greek units in UI (theta/day calendar, vega/1pt, rho/1pt) | MATH convention | Yes | Tooltip text + unit labels | S | Manual broker comparison |
| Delta vs N(d2) vs skew-adjusted ITM probability | MATH | Yes | Show "chance ITM (risk-neutral)" via spread of mids; never "probability of profit" from delta | S | Sum of adjacent-strike digitals monotone, within [0,1] |
| Rename IV-rank proxy to IV/RV ratio | MATH/EMP (VRP) | Yes | Relabel; IV30/RV20 | S | Ratio > 1 most days on SPY (expected under VRP) |
| Store daily 30d CM ATM IV; true IVR/IVP later | HEUR definition | No history | Daily snapshot job (1 row/ticker/day) | M | Compare SPY-derived series with ^VIX percentile |
| Cboe vol indices (^VIX, ^VIX9D, ^VIX3M, ^VXN, ^RVX) | MATH (model-free) | Likely on Yahoo, verify | Real IV rank and term structure for index names | S | Matches Cboe published values |
| Constant-maturity term structure (total-variance interp.) | MATH | Yes | Interpolate in sigma^2 T; flag calendar-arb violations | S | Monotone total variance |
| RR25 / BF25 / normalised skew | MATH conv.; EMP weak for timing | Yes (if wings quoted) | Delta-space interpolation with per-strike IV; state sign | M | Stable day-to-day on SPY; NaN when wings thin |
| Straddle expected move (= expected absolute move) | MATH | Yes | One definition; show 1-SD range separately; no 0.85 without label | S | Log implied vs realised moves per event |
| Earnings event variance from term structure | MATH + EMP (DJKS 2019) | Yes (+earnings date) | Two-expiry decomposition; E > 0 check | S-M | Implied vs realised earnings move log |
| Pin-risk and AM-settlement notices | Fact (OCC/FINRA/Cboe) | Yes | Text flags by root/expiry/moneyness | S | Unit tests on synthetic chains |
| GEX/VEX caveat for 0DTE | EMP (Cboe; Dim et al.) | OI prior session only | Label; exclude same-day expiry or show separately | S | n/a (disclosure) |

---

## What Optic must NOT claim

1. **"Delta = probability of profit" or "delta = probability ITM."** Call delta is e^{-qT}N(d1), not N(d2); both are
   risk-neutral, not forecasts; probability of profit must include the premium paid. (MATH; Section 2.)
2. **"IV rank" computed from realised volatility.** IV and RV are different quantities; IV exceeds RV on average
   (Carr & Wu 2009; Bollerslev, Tauchen & Zhou 2009), so the proxy is biased toward "high".
3. **"The market expects a move of $X with 68% probability"** using 0.85 x straddle, or any expected-move band as a
   real-world probability. 0.85 x straddle ~ 0.68 SD; IV-based bands are risk-neutral and include a premium.
4. **"IV crush makes selling before earnings profitable."** IV reliably falls after the event, but Gao, Xing & Zhang
   (2018) found pre-announcement ATM straddles earned positive average returns in their sample.
5. **"Skew / put-call IV gap shows bearish sentiment"** for a single ticker. Same-strike gaps are largely parity
   effects (dividends, borrow, American exercise, wrong q); cross-sectional smirk predictability (Xing et al.;
   Cremers & Weinbaum) is portfolio-level, weekly-rebalanced, and has weakened.
6. **"Dealers are short gamma here" as fact.** Dealer sign is not observable in Yahoo data; Cboe, which sees
   open/close and customer/MM flags, reports MM 0DTE gamma near zero and balanced customer flow. (PROP/HEUR.)
7. **"0DTE flows drive / will crash the market."** Main academic and exchange evidence (Dim, Eraker & Vilkov;
   Cboe) finds no destabilising effect on average; evidence is mixed, not conclusive either way.
8. **"Stocks get pinned to max pain."** Ni, Pearson & Poteshman document strike clustering at expiry for optionable
   stocks, a modest average effect in a 1990s-2000s sample; it is not a max-pain forecast.
9. **"Our Greeks match your broker."** Different T, r, q, IV source and American vs European models make
   small differences normal; say which model Optic uses.
10. **"Index options have no risk at expiry."** European cash settlement removes early assignment and pin
    ambiguity, but AM-settled SPX/NDX settle on Friday's opening prints after trading ends Thursday (gap risk).
11. **Tax outcomes.** Optic may state the Section 1256 classification as a fact with a "consult a tax adviser" note;
    it must not estimate anyone's tax or say a product "saves tax".

---

## Formulas and definitions Optic should adopt (units stated)

Inputs: S spot ($), K strike ($), T years = minutes to expiry timestamp / 525,600 (expiry 16:00 ET for PM-settled
and equity; 09:30 ET on expiry day for AM-settled SPX/NDX/RUT monthlies), r continuously compounded risk-free rate
(interpolated T-bill/CMT yield to T, decimal), q continuous dividend yield (or implied from the forward), sigma IV
(decimal per year). n() standard normal pdf, N() cdf.

- Forward: F = S e^{(r-q)T}; implied F from market = K* + e^{rT}(C_mid(K*) - P_mid(K*)) at the strike K* with
  smallest |C - P|. Implied carry: (r - q_impl) = ln(F/S)/T.
- d1 = [ln(F/K) + sigma^2 T/2] / (sigma sqrt T); d2 = d1 - sigma sqrt T.
- Call delta = e^{-qT} N(d1); put delta = -e^{-qT} N(-d1). Units: $ option per $1 underlying (per share). Position
  delta in shares = delta x 100 x contracts.
- Gamma = e^{-qT} n(d1) / (S sigma sqrt T). Units: delta per $1. Dollar gamma for 1% move:
  Gamma x S^2 x 0.01 x 100 per contract (state this unit in GEX).
- Vega (per vol point) = S e^{-qT} n(d1) sqrt T / 100. Units: $ per share per 1.00 IV point.
- Theta (per calendar day) = Theta_annual / 365, with
  Theta_call,annual = -S e^{-qT} n(d1) sigma / (2 sqrt T) - r K e^{-rT} N(d2) + q S e^{-qT} N(d1).
- Rho (per 1 percentage point) = K T e^{-rT} N(d2) / 100 (call); -K T e^{-rT} N(-d2) / 100 (put).
- Vanna = -e^{-qT} n(d1) d2 / sigma (delta per 1.00 sigma); per vol point divide by 100.
- Charm (call, per calendar day) = [q e^{-qT} N(d1) - e^{-qT} n(d1) (2(r-q)T - d2 sigma sqrt T)/(2T sigma sqrt T)] / 365.
- Risk-neutral P(S_T > K) = N(d2) (flat vol); skew-aware: e^{rT}[C(K-h) - C(K+h)]/(2h) from mids.
- Straddle expected absolute move ($) = C_mid(K_ATM) + P_mid(K_ATM) ~ 0.798 sigma S sqrt T.
- 1-SD move ($) = S sigma sqrt T; 1-SD price range = [S e^{-sigma sqrt T}, S e^{sigma sqrt T}].
- Constant-maturity IV at tau: w = (T2 - tau)/(T2 - T1); sigma_tau = sqrt{[w sigma1^2 T1 + (1-w) sigma2^2 T2]/tau}.
- Event variance (two post-event expiries): E = T1 T2 (s1^2 - s2^2)/(T2 - T1); event 1-SD move = sqrt(E) (fraction
  of S); expected absolute event move ~ 0.8 sqrt(E). With pre/post pair: E = (s_post^2 - s_pre^2) T_post.
- IV Rank (%) = 100 (IV_t - min_{252} IV)/(max_{252} IV - min_{252} IV); IV Percentile (%) = 100 x
  #{days in last 252 with IV < IV_t}/252; both on the same 30-day constant-maturity ATM IV series.
- IV/RV ratio = IV30 / RV20, RV20 = sqrt(252/20 x sum of squared daily log returns over 20 days) (close-to-close).
- RR25 = IV(25-delta call) - IV(25-delta put); BF25 = [IV(25c) + IV(25p)]/2 - IV(ATM_F). Vol points.
- Early-exercise (call) flag: short call ITM, ex-date before expiry, and P_mid(K) (extrinsic proxy) < next dividend.
- Pin-risk flag: equity/ETF, expiry today or next session, |S - K|/S < max(0.5%, 0.25 x daily 1-SD move).
