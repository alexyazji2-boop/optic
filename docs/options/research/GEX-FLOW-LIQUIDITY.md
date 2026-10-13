# GEX, Flow and Liquidity: research notes for Optic Options tab

Researcher: options microstructure agent. All sources read 2026-10-13 unless noted.
Labels: MATH, EMP, HEUR, MKT, PROP (see _BRIEF.md).

STATUS: complete 2026-10-13. Paywalled papers were read via abstracts, open working papers or summaries where noted; LibKey connector was not available in this session.

## 1. Dealer gamma, vanna, charm exposure
### 1.1 Formula conventions and units

- **Original SqueezeMetrics definition (MATH + HEUR sign).** "Gamma Exposure (GEX): Quantifying hedge rebalancing in SPX options", Mar 2016, rev. Dec 2017, https://squeezemetrics.com/download/white_paper.pdf (read 2026-10-13). Per strike/expiry: call GEX = Gamma x OI x 100; put GEX = Gamma x OI x (-100). Units: **shares of underlying to re-hedge per 1-point move**. Market GEX = sum over every strike and expiry. Four stated assumptions: (1) every contract is held on one side by a delta-hedging market maker; (2) calls are sold by investors (call overwriting/collars) and bought by MMs; (3) puts are bought by investors and sold by MMs; (4) MMs hedge exactly to model delta (no hedging bands). The paper concedes trade direction is unknowable because most SPX volume prints at mid.
- **Dollar conversions in use (MATH).** Per $1 move: Gamma x OI x 100 x S (dollars of delta per $1). Per 1% move: Gamma x OI x 100 x S x (0.01 x S) = Gamma x OI x 100 x S^2 x 0.01 (dollars of delta per 1% move). SpotGamma states the per-1% form with "modeled dealer position" in place of signed OI and warns per-$1 and per-1% charts are not comparable (https://spotgamma.com/gamma-exposure-gex/, page "last updated" Aug 18 2026, read 2026-10-13). Baltussen et al. (2021) use Gamma x OI x 100 x P (per index point, dollar-ish) and normalise by S&P 500 market value.
- **Normalisation (MATH/HEUR).** Raw dollar GEX scales with S^2 x OI, so cross-ticker comparison needs a normaliser (market value as in Baltussen et al.; shares outstanding as in Ni et al.; or $ADV, most intuitive for users).
- **Vanna and charm exposure (MATH, HEUR sign).** Vanna = d(delta)/d(sigma) = d(vega)/dS; Black-Scholes (no dividends) vanna = -phi(d1) d2 / sigma. VEX per 1 vol point = vanna x OI x 100 x S x 0.01 (dollar delta change per 1 IV point). Charm = d(delta)/dt (delta decay), usually quoted per calendar day. They inherit the GEX sign assumption plus IV-surface error (sensitive to the sigma used and sticky-strike vs sticky-delta). No peer-reviewed study validates a stand-alone "vanna exposure" predictor; vanna/charm "flows" around OPEX are **HEUR/MKT**.

### 1.2 Published methodologies (SqueezeMetrics, SpotGamma, Menthor Q, Cboe)

| Provider | What is public | Sign source | Label |
|---|---|---|---|
| SqueezeMetrics GEX (white paper above) | Full formula + 4 assumptions; empirical claim: highest vs 2nd-highest GEX quartile -> next-day SPX s.d. 0.55% vs 0.65%; positive GEX "dampens", negative "magnifies" | Fixed convention: MMs long calls, short puts | Formula MATH; sign HEUR; predictive claim EMP-weak (in-house, no out-of-sample stats, no t-stats); "difficult to come up with an alternate explanation" is MKT |
| SqueezeMetrics DIX | Dark-pool index from FINRA short-sale volume; unrelated to options chains | n/a | HEUR; not reproducible from Yahoo |
| SpotGamma (https://spotgamma.com/gamma-exposure-gex/, read 2026-10-13) | Per-1% formula; definitions of Zero Gamma (re-price GEX over hypothetical spots, find crossing), Call Wall, Put Wall; explicitly says walls are "not an automatic ceiling/floor" and GEX "is a model output, not an exchange-published statistic" | Proprietary "Options Inventory Model" + intraday trades | Definitions MATH/HEUR; positions PROP; Volatility Trigger, Risk Pivot PROP |
| Menthor Q (https://menthorq.com/guide/free-daily-report-explained/, https://menthorq.com/wp-content/uploads/2023/11/Product-Training-Gamma-Levels.pdf, via search summary 2026-10-13) | Call Resistance = strike with largest net call gamma; Put Support = strike with largest net put gamma; HVL = gamma flip; 0DTE variants | "Open interest, market positioning and proprietary quantitative logic" | Levels HEUR; engine PROP; "rallies often stall" MKT/HEUR |
| Cboe, M. Xu, "Much Ado About 0DTEs", 2023-09-08, https://www.cboe.com/insights/posts/volatility-insights-evaluating-the-market-impact-of-spx-0-dte-options (read 2026-10-13) | Uses Cboe's own customer-vs-MM, buy/sell, open/close tags to track MM net position per strike; net gamma per 1% move | **Observed** MM inventory (exchange data) | EMP (SPX 0DTE only; Cboe has a commercial interest in 0DTE being seen as benign) |

Key point: the only public numbers built on **observed** market-maker inventory (Cboe 2023; Ni-Pearson-Poteshman-White; Garleanu-Pedersen-Poteshman) use exchange open/close-by-origin data. Every retail GEX chart built from OI alone, including Optic's, uses the SqueezeMetrics convention.

### 1.3 Who is net long/short options (dealer-sign evidence)

- **Baltussen, Da, Lammers & Martens (2021), JFE 142:377-403**, https://academicweb.nd.edu/~zda/intramom.pdf (read 2026-10-13). **EMP.** 60+ futures, 1974-2020. Last-30-minute return is predicted by the rest-of-day return; they attribute part of this to short-gamma hedging. They compute S&P 500 "NGE" from OptionMetrics OI 1996-2017 (SqueezeMetrics data extends to May 2020; footnote says their replication of SqueezeMetrics 2002-2017 was "virtually identical") using exactly the SqueezeMetrics four assumptions. Result (Table 7): on NGE<0 days the slope of r_LH on r_ROD is 6.63 (t=4.78, R^2 3.58%); on NGE>=0 days 0.82 (t=1.03, insignificant). 2,930 negative vs 3,158 positive days. **Caveats the authors themselves state:** NGE is positive on most days, possibly an artefact of the long-call/short-put assumption plus upward drift; data omit OTC options and actual end-user positions. Their justification for the sign comes from literature, not observed dealer books.
- **Garleanu, Pedersen & Poteshman (2009), RFS 22(10)** "Demand-based option pricing" (cited inside Baltussen et al.): **EMP**, Cboe open/close data by investor type. End users are net long S&P 500 index options, with large net long OTM puts; this supports the "dealers short index puts" half of the convention. Their single-stock cross-section indicates options are cheaper where end-user demand is more negative (net selling); the exact published wording on aggregate single-stock positioning was not verified (NBER WP https://www.nber.org/papers/w11843).
- **Lakonishok, Lee, Pearson & Poteshman (2007), RFS 20(3):813-857** "Option market activity", https://ideas.repec.org/a/oup/rfinst/v20y2007i3p813-857..html and working paper https://www.business.kaist.ac.kr/faculty/inmoo/Articles/lakonishokLeePearsonPoteshman22May2006.pdf (read via abstract/summary 2026-10-13). **EMP**, Cboe open/close by investor class, single-stock options (1990-2001). Non-market-maker investors hold more written than purchased calls (much of it covered calls) and also more written than purchased puts; only firm proprietary traders are net long puts. Implication: in single stocks public customers are net **sellers** of both calls and puts on average, so MMs are on average net long both, i.e. the "short puts" half of the convention is wrong for single names in that sample. Sample predates 0DTE and the 2020-21 retail call-buying wave.
- **Ni, Pearson, Poteshman & White (2021), RFS 34(4):1952-1986**, "Does option trading have a pervasive impact on underlying stock prices?"; 2006 working paper https://ou.edu/dam/price/Finance/CFS/paper/pdf/pearsonPoteshmanWhite.pdf (read 2026-10-13). **EMP.** Observed MM (and firm-prop) net positions from Cboe/ISE data, 1990-2001, ~2,300 stocks, Black-Scholes gamma normalised by S / shares outstanding. Next-day absolute return of the lowest MM-net-gamma decile is ~100 bp higher than the highest decile; a 1 s.d. shock to MM net gamma ~ 37 bp change in absolute return (~12% of mean 310 bp). Gamma changes from existing positions are isolated to rule out volatility-informed trading. This is the strongest evidence that **sign-correct** dealer gamma predicts **volatility magnitude**, not direction.
- **Goyenko & Zhang (2019)** and **Cici & Palacios (2015)** (cited inside Baltussen et al.): end-user net demand positive for SPX puts and negative for SPX calls; mutual funds mostly write calls and buy index puts. **EMP**, index-focused.
- **0DTE.** Cboe (2023, above): median MM net gamma in SPX 0DTE at 15:30 was +$173m per 1% (IQR -$1.1bn to +$2.4bn); intraday average $170-670m, ~0.04-0.17% of daily S&P futures liquidity; customer flow "very balanced" (example strike: MM bought 52k, sold 55k). Dim, Eraker & Vilkov (2024) "0DTEs: Trading, Gamma Risk and Volatility Propagation", SSRN 4692190 (SSRN blocked; read via summaries https://harbourfrontquant.substack.com/p/the-rise-of-0dte-options-cause-for, 2026-10-13): high 0DTE OI gamma is associated with **lower**, not higher, intraday volatility and does not propagate; volume shocks do not amplify past returns. **EMP**, but details of their sign method not verified here. Conflicting evidence exists (some studies link 0DTE activity to higher volatility; noted in a 2026 Princeton thesis abstract, https://theses-dissertations.princeton.edu/entities/publication/61115cd1-cb09-4a8b-9230-ff488fc2a386).
- **Barbon & Buraschi, "Gamma Fragility"** (working paper, rev. 2021-03-19, https://abarbon.com/papers/gamma-fragility, abstract read 2026-10-13). **EMP (working paper).** Negative stock-level gamma imbalance x illiquidity -> intraday momentum; positive -> reversal; strongest in least liquid stocks; linked to flash-crash frequency. Sign method not confirmed from the abstract.

**Synthesis on the sign:** For **SPX/SPY index** options, evidence (GPP 2009; Goyenko-Zhang; Cici-Palacios; Baltussen et al.) supports end users net long puts and net short calls, so the convention is defensible as a first approximation (HEUR backed by EMP). For **single stocks**, evidence (Lakonishok et al. 2007; GPP 2009 cross-section) says public customers are net sellers on average, and retail call buying since 2020 (section 2.4) makes call-side positioning ticker- and period-specific. Applying the index convention to a meme stock or a single name is not supported. Optic should label single-stock GEX "assumed positioning" and prefer an unsigned "gamma concentration by strike" there.

### 1.4 Walls, flip, pinning: what the evidence says

- **Pinning (EMP).** Ni, Pearson & Poteshman (2005), JFE 78(1):49-87, "Stock price clustering on option expiration dates", https://ideas.repec.org/a/eee/jfinec/v78y2005i1p49-87.html (abstract, read 2026-10-13): optionable stocks' expiration-day closes cluster at strikes; returns shifted by at least 16.5 bp on average per expiration (~$9bn market cap); attributed to MM hedge rebalancing plus manipulation by firm proprietary traders (the full-text conditioning on MM net purchased positions was not re-verified here; the hedging mechanism requires hedgers to be net long gamma at the strike, because long-gamma hedgers sell rallies and buy dips toward it). Golez & Jackwerth (2012), JFE 106(3):566-585, https://ideas.repec.org/a/eee/jfinec/v106y2012i3p566-585.html: S&P 500 futures gravitate to ATM strike on serial-option expiry days. Theory: Avellaneda & Lipkin (2003) (large OI + MM delta hedging -> finite pinning probability). **Scope:** effect is a close-at-expiration phenomenon of tens of bp, conditional on dealers being **long** gamma at that strike. It is not evidence that a "gamma wall" days or weeks away caps price.
- **Max pain (HEUR/MKT).** No peer-reviewed support beyond the pinning literature above; max pain assumes writers manipulate to minimise payout and ignores who holds what.
- **Gamma flip / zero gamma (MATH as computation; HEUR as signal).** The flip is the spot S* where convention-signed sum Gamma_i(S*) x OI_i x 100 x S*^2 x 0.01 changes sign, re-pricing gamma at each hypothetical S* (holding IV fixed, sticky-strike). Evidence that the **sign of aggregate dealer gamma** conditions volatility and intraday autocorrelation: Baltussen et al. 2021 (index, convention sign), Ni et al. 2021 (single stocks, observed sign), Barbon-Buraschi. No published study validates a specific flip **price level** as support/resistance or as a predictor of direction. Flip location is fragile: it depends on the IV used per strike, on which expiries are included, on OI that is a day old, and on the sign convention; small changes can move it by several percent.
- **Call wall / put wall (HEUR).** "Largest |GEX| strike" is a descriptive concentration statistic. Mechanism only makes sense if dealers are long gamma there (dampening near strike, as in pinning). SpotGamma itself calls walls neither ceilings nor floors. No academic test of "walls" as levels found. Label as **HEUR**, and "acts as resistance" as **MKT**.
- **What GEX predicts, per evidence:** magnitude of next-day/intraday moves and return autocorrelation (momentum vs reversal), conditional on sign being right. It does **not** predict direction. Effects are larger in illiquid names, smaller in mega-cap liquid markets.

### 1.5 Approach records (GEX family)

**A1. Convention-signed GEX by strike (current Optic).** Source: SqueezeMetrics; SpotGamma. Rationale: hedge flow per move. Data: BS gamma from Yahoo IV, prior-session OI, spot (all in Yahoo; OI stale intraday; IV unreliable on illiquid strikes). Applies: index ETFs and very liquid names; weak for single stocks. Failure modes: sign assumption; OI misses same-day/0DTE opens; no OTC; IV errors. Cost: exists. Validate: compare Optic's SPY GEX sign history with SqueezeMetrics' published GEX series (check terms); next-day |return| by sign bucket.

**A2. Unsigned gamma concentration ("where hedging is most sensitive").** Rationale: avoids sign claim; still identifies strikes with large gamma notional. Data: same as A1. Conditions: all tickers. Weakness: says nothing about dampen vs amplify. Cost S. Validate: pinning test at expiry (close distance to max-concentration strike vs a placebo strike).

**A3. Normalised GEX (per 1% move / ADV $).** Rationale: comparable across tickers, as Ni et al. normalise by shares outstanding and Baltussen et al. by market value. Data: Yahoo average volume available. Cost S. Validate: decile sort of next-day |return| on Optic's own snapshots (Optic must start storing daily snapshots).

**A4. Vanna/charm exposure.** Rationale: delta change from IV and time. Data: same plus a consistent IV. Weakness: no empirical validation; doubles down on sign assumption and IV noise. Cost exists. Recommendation: keep as advanced-only, label HEUR.

**A5. Observed-inventory GEX.** Requires Cboe Open-Close (origin + open/close) or a vendor modelled inventory (SpotGamma, PROP). Cost L + paid data. Validate against Cboe published SPX numbers.
## 2. Unusual options activity and flow

### 2.1 What chain snapshots can and cannot show (MATH/definitional)

Yahoo chain fields: cumulative day volume (delayed ~15 min), OI (OCC prior-session value, does not change intraday), bid/ask (no sizes, no quote time), last price + lastTradeDate (one print, possibly a spread leg or an auction print), Yahoo IV.

| Question | From snapshot? | Why |
|---|---|---|
| Was activity large relative to normal? | Yes | volume vs OI, volume vs own history (if Optic stores history), volume vs stock volume |
| Were positions opened? | Partly, next day only | Vol > OI implies at least some volume could not all be closes; next-day dOI = opens - closes (net), unsigned |
| Bought or sold? | **No** | no trade prices/conditions/quotes at trade time; last price vs current bid/ask is a single, possibly stale print |
| Opening vs closing? | **No** intraday | requires exchange open/close tags (Cboe Open-Close, ISE Trade Profile) |
| Single trade vs many? Sweep? Block? | **No** | requires OPRA tape + conditions (ISOI, SLAI) and sizes |
| Spread leg or outright? | **No** | requires MLET/MLFT condition codes or complex-book data |
| Hedged with stock (delta-neutral / tied)? | **No** | requires stock-tied indicators, not in OPRA consolidated summary |
| Who traded (retail, institution, MM)? | **No** | requires origin codes (open-close products) or PFOF/price-improvement flags on the tape |
| Premium spent | Approximate only | vol x mid x 100 uses current mid, not trade prices |

A snapshot "unusual activity" list is therefore an **activity-concentration screen** ("traded N x its OI / usual volume"). "Smart money", "bullish flow", "sweeps" or "whales" built from Yahoo is **MKT**.

### 2.2 Trade-level data: what it adds and its limits

- **OPRA condition codes** (vendor transcriptions of the OPRA spec: QuoteMedia https://support.quotemedia.com/support/solutions/articles/13000100515-trade-indicators-for-options-opra- ; Barchart https://www.barchart.com/education/options-time-sales-conditions ; read 2026-10-13; verify against the OPRA Binary Participant Interface spec before coding): SLAN = single-leg auction non-ISO (price-improvement, facilitation, solicitation); SLAI = same, ISO; SLCN/SCLI = single-leg cross, no exposure (e.g. QCC); MLET = multi-leg electronic in complex order book; MLFT = multi-leg floor; ISOI = intermarket sweep order; SLFT = floor single-leg. **MATH/definitional.** A "sweep" in vendor flow products typically means ISO prints across several exchanges within a short window: a vendor construct (HEUR), not an OPRA field.
- **Aggressor side (EMP).** Savickas & Wilson (2003), JFQA 38(4):881-902, https://ideas.repec.org/a/cup/jfinqa/v38y2003i04p881-902_00.html (summary read 2026-10-13): on Cboe data with true direction, quote rule 83% correct (on classifiable trades), Lee-Ready 80%, EMO 77%, tick 59%; mid-spread trades unclassifiable by the quote rule; complex index trades misclassified about half the time; excluding them lifts quote rule above 87%. Modern price-improvement auctions put many retail prints inside the spread (Bryzgalova et al. 2023), so classification is harder now; "bought at ask" is a probability, not a fact.
- **Opening/closing and origin (EMP-grade data).** Cboe Open-Close Volume Summary (https://datashop.cboe.com/open-close-cboe-c2-exchange, read 2026-10-13): Cboe exchanges only (C1, C2, BZX, EDGX), by origin (customer, professional customer, broker-dealer, market maker), buy/sell, open/close, customer size buckets (<100, 100-199, >199). EOD and 1- or 10-minute intraday versions. Nasdaq ISE Open/Close Trade Profile (filings: https://listingcenter.nasdaq.com/assets/rulebook/ise/filings/SR-ISE-2024-32.pdf; field doc https://m.nasdaqtrader.com/content/ProductsServices/DATAPRODUCTS/ISE/ISE-GEMX%20Consolidated%20Field%20Description%20-%20May%202017%20v2.pdf ; read via search summary 2026-10-13): ISE-only, origin customer/professional/firm (a 2026 filing proposes renaming it "ISE Trade Outline" and adding market makers; status unverified). Both cover **only their own exchanges' volume**, not the whole market.

### 2.3 Evidence on informed options trading

- **Easley, O'Hara & Srinivas (1998)**, JF 53(2):431-465 (abstract/summaries, https://rpc.cfainstitute.org/research/cfa-digest/1998/11/option-volume-and-stock-prices-evidence-on-where-informed-traders-trade-digest-summary, read 2026-10-13). **EMP, small sample** (50 firms, 44 days per Pan-Poteshman). **Signed** option volume ("positive news" = buy calls/sell puts; "negative news" = sell calls/buy puts) carries information about stock prices; **unsigned** volume did not. Results mostly contemporaneous.
- **Pan & Poteshman (2006)**, RFS 19(3):871-908, NBER WP https://www.nber.org/papers/w10925 (read 2026-10-13). **EMP**, Cboe 1990-2001. Put/call ratio from **volume initiated by non-market-maker buyers opening new positions**: low-ratio stocks beat high-ratio stocks by >40 bp next day and >1% next week (risk-adjusted, long-short, gross of costs). Stronger for small stocks and high-leverage contracts. Source is **non-public** information: the publicly observable component did not carry the predictability.
- **Why Optic's snapshot P/C volume ratio is not the Pan-Poteshman signal:** (1) it mixes buys and sells (a put sale and a put purchase both add put volume); (2) it mixes opening and closing trades; (3) it includes market-maker and spread-leg volume; (4) it is computed per ticker in isolation, whereas the PP result is a **cross-sectional** sort; (5) PP found the predictive part was not publicly observable in real time; (6) the sample is 1990-2001, before pennies, weeklies and the PFOF retail boom. A total-volume P/C ratio is a descriptive (HEUR); its use as a contrarian indicator is practitioner lore.
- **Johnson & So (2012)**, JFE 106(2):262-286, https://ideas.repec.org/a/eee/jfinec/v106y2012i2p262-286.html (abstract, read 2026-10-13). **EMP.** O/S = total option volume / stock volume (**unsigned, computable from snapshots**). Lowest O/S decile beats highest by 0.34% per week; stronger when short-sale costs are high; O/S predicts earnings news. Mechanism: short-sale constraints push negative informed traders into options.
- **Ge, Lin & Pearson (2016)**, JFE 120(3):601-622, https://ideas.repec.org/a/eee/jfinec/v120y2016i3p601-622.html (abstract, read 2026-10-13). **EMP.** Decomposing O/S with signed open/close volume: **opening call purchases** are the strongest predictor, then closing call sales; synthetic-short trades are not more informative; leverage is the main channel. So the informative piece of O/S is directional and only identifiable with open/close data.
- **Augustin, Brenner & Subrahmanyam (2019)**, Mgmt Sci 65(12):5697-5720, https://ideas.repec.org/a/inm/ormnsc/v65y2019i12p5697-5720.html (read 2026-10-13). **EMP.** 1,859 US takeovers 1996-2012: ~25% of targets show positive abnormal option volume pre-announcement, concentrated in short-dated OTM calls; SEC litigates ~8% of deals. Supports the existence of informed "unusual" activity before some events, but says nothing about the hit rate of a generic unusual-volume screen (most spikes are not pre-M&A).
- **Muravyev (2016)**, JF 71(2):673-708, DOI 10.1111/jofi.12380 (abstract, read 2026-10-13). **EMP.** Option price impact is driven more by **market-maker inventory risk** than by asymmetric information; past order imbalance predicts option returns (1 s.d. inventory-related imbalance ~ 1% higher next-day option return). Implication: heavy one-sided flow mostly makes **that option** more expensive; it is not automatically a stock-direction signal.

### 2.4 Retail flow evidence

- **Bryzgalova, Pavlova & Sikorskaya (2023)**, JF 78(6):3465-3514, DOI 10.1111/jofi.13285, open copy https://lbsresearch.london.edu/id/eprint/2827/ (text read 2026-10-13). **EMP.** Identify wholesaler (retail) trades using the OPRA price-improvement-mechanism flag introduced Nov 2019 (type SLAN: single-leg non-ISO PIM). Retail share of option volume rose above 60% (with PFOF; ~90% of PFOF from three wholesalers). Half of retail trades are in options with under a week to expiry, whose average quoted spread is ~12.6% of price; retail loses money on average: about **$2.1bn losses Nov 2019-Jun 2021**, with **$6.4bn** of indirect trading costs (trade price vs midquote) vs ~$0.9bn commissions. They warn the common "small trade = retail" proxy has many false positives because institutions split orders.
- **de Silva, Smith & So, "Losing is optional"** (working paper, AFA copy June 2023; https://www.gsb.stanford.edu/faculty-research/working-papers/losing-optional-retail-option-trading-expected-announcement, read via summaries 2026-10-13). **EMP.** Nasdaq origin-coded data (~25% of market volume), 2010-Feb 2021. Retail buys options before earnings, especially high expected-volatility ones; overpays relative to realised vol, pays very wide spreads, exits slowly; losses ~5-9% on average around announcements, 10-14% for high-expected-vol events; market makers are main beneficiaries.
- **Implication for Optic:** for a retail audience the most evidence-backed help Optic can give is about **costs** (spread as % of premium, earnings IV crush, chasing short-dated OTM calls), not about decoding "flow".

### 2.5 Approach records (flow family)

**F1. Activity-concentration screen (rename current "unusual activity").** Source: definitional. Data: volume, OI (Yahoo, yes). Rules: vol/OI >= 1 and vol >= floor (e.g., 500) and a liquidity gate (section 3.5). Conditions: any optionable stock; breaks near expiry (OI decays) and on 0DTE (OI near zero, ratios explode). Weakness: unsigned, cannot separate buy/sell/open/close/spread. Cost S. Validate: store daily snapshots; next day, check dOI vs volume to report the share of flagged contracts that were net openings.

**F2. Next-day OI confirmation.** dOI_t = OI_t - OI_(t-1) is net contracts opened. Data: requires Optic to persist OI by contract (Yahoo provides daily). Weakness: net, unsigned, one day late. Cost S-M. Validate: fraction of F1 flags with dOI > 0.5 x volume.

**F3. O/S ratio (Johnson & So).** Data: sum of chain volume (Yahoo) / stock volume (Yahoo). Conditions: cross-section of many stocks, weekly horizon. Weakness: cross-sectional signal, published 2012 so likely decayed; needs a universe and history; not a single-stock "alert". Cost M. Validate: decile backtest on stored snapshots over 6-12 months before showing any return claim. Present as "options activity relative to stock activity", not a forecast.

**F4. Signed/open-close flow (PP, Ge-Lin-Pearson).** Requires Cboe Open-Close or ISE Trade Profile (paid, partial market), or OPRA + classification (noisy). Cost L + data. Validate: replicate PP-style cross-sectional sort.

**F5. Retail-cost education.** Data: spread % (Yahoo). Cost S. Evidence strongest (BPS 2023, dSS).


## 3. Liquidity and execution quality

### 3.1 Spread measures (MATH definitions; EMP evidence)

- Quoted spread $ = ask - bid; relative quoted spread = (ask - bid) / mid, mid = (bid + ask)/2. Spread in ticks = (ask - bid) / minimum increment.
- Effective spread (needs trade prices) = 2 x |P - mid_t|, or 2 x D x (P - mid_t) with D = +1 buy / -1 sell; relative = / mid_t. Realised spread = 2 x D x (P - mid_(t+dt)); price impact = effective - realised. Price improvement per contract (buy) = ask_t - P. These need OPRA trades + NBBO at the trade time: **not computable from Yahoo**.
- **Muravyev & Pearson (2020)**, RFS 33(11):4973-5014, https://ideas.repec.org/a/oup/rfinst/v33y2020i11p4973-5014..html (abstract, read 2026-10-13). **EMP.** Option quotes are predictable at high frequency; traders who time executions (buy when fair value is near the ask) pay effective spreads under 40% of conventional measures; the overall average effective spread is about a quarter below conventional estimates. Investors who cannot time trades (typical retail) bear roughly the conventional effective spread. So quoted spread is an **upper-bound-ish guide** for a retail limit order at mid, and a fair cost estimate for a market order.
- **Retail benchmark (EMP):** Bryzgalova et al. (2023): retail's favoured sub-week options average a 12.6% quoted spread; indirect costs ($6.4bn) dwarfed commissions over Nov 2019-Jun 2021. De Silva et al.: spreads widen sharply before high-expected-vol earnings.
- **Execution-quality disclosure:** SEC Rule 605 covers **NMS stocks only**, and options are excluded by definition; the 2024 amendments (adopted 2024-03-06, compliance 2025-12-14) did not add options (https://www.sec.gov/news/press-release/2024-32; FINRA definitional note in https://www.finra.org/sites/default/files/2025-04/sr-finra-2025-002.pdf; read 2026-10-13). Rule 606 routing reports (incl. PFOF) do cover options. So there is no standardised public options execution-quality statistic Optic could cite per broker; any "you'll get filled at mid" claim is **MKT**.

### 3.2 Quote pathologies in Yahoo data (MATH/definitional, HEUR handling)

- **Zero bid:** no displayed buyer; a long holder cannot sell except at 0 or by working an offer. Mid = ask/2 is a fiction; Yahoo IV is often extreme or bogus there. Treat as "no two-sided market".
- **Locked/crossed (bid >= ask):** in a live NBBO, locks/crosses are prohibited by the options linkage plan except transiently; in a delayed or after-hours snapshot they usually mean stale or mismatched quotes. Exclude from greeks/GEX inputs that use mid, flag "quote error".
- **After hours / weekends:** Yahoo frequently returns zeros or the closing quote; no quote timestamp. Show "quotes as of last session close" and do not grade liquidity on zero quotes.
- **Stale last price:** last is one print; lastTradeDate may be days old; it can be a spread leg (MLET), an auction print, or a late report. Never use last for valuation, P/L or IV when a two-sided quote exists; display its age.
- **No quote size:** a 1-lot at the bid and a 500-lot look identical; tight-but-tiny markets are invisible. Any Optic liquidity grade is a **price-width grade only**.
- **15-minute delay + stale OI:** Volume/OI ratios intraday compare live-ish volume with yesterday's OI.

### 3.3 Complex orders and tick rules

- **Complex Order Book (COB):** Cboe complex orders (up to 16 legs) execute against resting complex interest or against the **derived net market** from the leg books; leg orders are generated when a complex order is priced inside the derived net market; complex auctions (COA, 100 ms) can give price improvement (https://www.cboe.com/markets/us/options/trading/complex-orders/; SEC filing example https://www.sec.gov/file/34-69987; read 2026-10-13). **MATH/institutional fact.** Hence a vertical can often fill tighter than "sum of leg spreads": the natural (worst-case) spread price is (buy leg ask - sell leg bid); market makers quote the package against their net risk (the legs partly hedge each other), and complex orders can trade at prices between leg ticks. Optic should show both **natural** and **mid** prices for verticals and call the leg-spread sum a worst case, not the expected cost.
- **Minimum increments (MATH/rule):** Penny Interval Program (permanent since 2020; approval order https://www.federalregister.gov/documents/2020/04/07/2020-07224/ ; Cboe annual review notice https://cdn.cboe.com/resources/product_update/2023/Penny-Interval-Program-Annual-Review-and-Rebalancing.pdf; read 2026-10-13): program classes quote $0.01 below $3.00 and $0.05 at/above $3.00; SPY, QQQ, IWM $0.01 at all prices; non-program classes $0.05 below $3.00 and $0.10 at/above. Membership rebalanced annually by activity (top-300 adds, removals outside top-425). Consequence: a $0.20 option in a non-penny class cannot have a spread below $0.05 = 25% of price. Relative spread alone mis-grades cheap options; use ticks too.

### 3.4 How tools grade liquidity

- **tastytrade/tastylive** 1-4 star liquidity rating: based on volume, bid/ask width, OI across strikes and multiple expirations; formula and cutoffs **not public** (https://www.tastylive.com/concepts-strategies/options-liquidity, https://www.tastylive.com/definitions/liquidity; read 2026-10-13). **PROP/HEUR.**
- **OptionStrat:** no public methodology found for its liquidity warnings (searched 2026-10-13). **PROP/unknown.**
- General broker education (tastylive; Schaeffer's https://www.schaeffersresearch.com/content/education/2017/10/30/how-options-liquidity-impacts-trading) uses spread %, OI "a few hundred", and volume: **HEUR** with no published validation.

### 3.5 Proposed transparent thresholds for Optic (HEUR, documented so users can see them)

Per contract, during regular hours only (skip if bid = ask = 0):
1. **Validity:** ask > 0; ask > bid; bid >= 0. Else grade "No market / quote error".
2. **Spread metrics:** spread% = (ask - bid)/mid; ticks = (ask - bid)/tick, with tick from the penny-program rule (Optic can approximate: SPY/QQQ/IWM $0.01; otherwise $0.01 if price < 3 and the class is in the program, else $0.05/$0.10; a static yearly list of program classes is published by exchanges).
3. **Grade (price-width only):**
   - **Tight:** spread% <= 5% and bid > 0.
   - **OK:** spread% <= 10%.
   - **Wide:** spread% <= 25%.
   - **Very wide / avoid market orders:** spread% > 25% or bid = 0.
   - Add the tag **"at minimum tick"** when ticks <= 1: the spread cannot get narrower, so the cost is structural to a cheap contract (explain this rather than upgrading the grade).
   Anchors: 12.6% is the average quoted spread of the sub-week options where half of retail trades occur (BPS 2023), so "Wide" (>10%) begins just below what retail typically pays; 5%/10% are common practitioner cutoffs (HEUR).
4. **Activity:** "Active today" if volume >= 10 and lastTradeDate is today; "Established" if OI >= 100. Shown separately, not blended into one score.
5. **Strategy cost:** for a vertical, natural cost = sum of (pay ask, receive bid); mid cost; show "round-trip cost at natural as % of max profit". This is the single most useful number for a retail spread trader and needs only Yahoo data.
6. **Entry-plan rule:** never pick a contract graded Very wide or No market; prefer Tight/OK; never value with last when bid/ask exist.
Validate: if Optic later gets OPRA trades (section 4), compare grade with realised effective spread; until then, check internal consistency (grade distribution by ticker/moneyness/DTE) and spot-check against a broker screen.


## 4. Data providers that fill Yahoo's gaps (prices as published, read 2026-10-13)

Gap codes: **T** = trade tape with OPRA conditions; **Q** = NBBO with sizes/timestamps; **OI** = intraday or reliable daily OI; **OC** = open/close + origin; **IV** = historical IV / surfaces / IV rank; **RT** = real-time.

| Provider | Published price (date read 2026-10-13) | Fills | Licensing notes |
|---|---|---|---|
| Cboe DataShop Open-Close (https://datashop.cboe.com/open-close-cboe-c2-exchange) | DataShop page shows no price; SEC filing SR-CBOE-2024-002 (Release 34-99326, 2024-01-11, https://www.sec.gov/files/rules/sro/cboe/2024/34-99326.pdf) raised C1 Intraday Open-Close from $2,000 to **$3,000/month ($36,000/yr)**; ad-hoc historical intraday $1,000 per month of data. Same filing cites ISE Open/Close Trade Profile $2,000/mo intraday, $1,000/mo historical; PHLX PHOTO $2,500/$1,000; Nasdaq NOTO $750/$500; GEMX $1,000/$750 | OC (own exchange only; C1 EOD from 2005, 1-min from 2019) | Raw data internal use only; derived-data external distribution needs extra fee and approval |
| Databento OPRA.PILLAR (https://databento.com/catalog/opra/OPRA.PILLAR) | Standard **$199/mo** (live, license fees included); Plus $1,500/mo, Unlimited $4,000/mo (catalog page; general pricing page shows $1,750/$4,500, so tiers vary by dataset or changed); historical usage-based per GB (rate via estimator) | T, Q (CMBP-1 top-of-book with sizes, from 2013-04-01), OI (OPRA start-of-day statistics), RT | Historical needs no license; live needs exchange licence; redistribution depends on dataset |
| ThetaData (https://www.thetadata.net/pricing) | Options Value **$40/mo** (6 yr, 1-min); Standard **$80/mo** (10 yr, tick-level, every OPRA NBBO quote); Pro **$160/mo** (14 yr, every trade) | T, Q, OI (has OI history endpoint), RT | Retail prices are **personal use only, no redistribution or business use**; business plan separate (price not public) |
| Massive (Polygon.io renamed) (https://massive.com/pricing?product=options) | Basic $0 (EOD); Starter **$29** (15-min delayed, greeks/IV, daily OI, 2 yr); Developer **$79** (+ trades, 4 yr); Advanced **$199** (real-time, + quotes, 5+ yr) | T (Developer+), Q (Advanced), OI daily, IV/greeks snapshot | All listed plans "individual use"; business pricing not public |
| ORATS (https://orats.com/data-api) | Delayed Data API **$199/mo** (EOD history from 2007, IV rank history, SMV smoothed surfaces, earnings); Live $299; Live Intraday $599 (1-min from Aug 2020); All-In $899; Time & Sales add-on $299 (from 2022-09-09). (A search-cached ORATS page showed $49/mo for non-professional delayed; conflicting, verify) | IV (strongest fit: historical IV, IV rank, surfaces, earnings moves), T (add-on), RT | Live needs exchange agreements; non-pro vs business terms not stated on page |
| Tradier (https://docs.tradier.com/docs/market-data) | Price for data not stated; real-time for brokerage account holders; ORATS greeks/IV updated hourly; ORATS add-on $99/mo (https://brokerage.tradier.com/platforms/orats) | RT quotes, greeks | Requires a brokerage account: unsuitable as a data vendor for a multi-user app |
| Intrinio (https://intrinio.com/blog/get-affordable-us-options-data-options-gold-plan) | Not public (Silver delayed, Gold real-time); OPRA display fees billed separately, "typically $600-$2,000" | T (incl. sweep/block-tagged unusual activity), Q, IV/greeks | Display to outside users requires OPRA vendor agreement |
| OptionMetrics IvyDB US (https://optionmetrics.com/wp-content/uploads/2023/03/IvyDB-US-Brochure.pdf; WRDS) | Not public (annual licence) | IV (EOD from 1996, standardised surfaces 30d-2y, deltas 20-80); OI daily | Academic via WRDS; commercial licence separate; not for real-time display |

General: any **external display** of real-time or delayed OPRA-derived data in Optic triggers OPRA vendor/subscriber fees and agreements regardless of vendor (Intrinio note above). Yahoo's own terms are a separate question for a commercial app (outside this brief).

**Cheapest path per gap:** IV history/IV rank -> ORATS delayed or Optic storing its own daily ATM IV from Yahoo snapshots (free, starts the history clock now). Trade tape/aggressor/sweeps -> ThetaData or Massive for prototyping (personal licence), then a business licence before showing users. Open/close -> Cboe/ISE products ($2-3k/mo, partial market). Quote sizes -> Massive Advanced, ThetaData Standard, Databento.

## 5. Research-to-implementation matrix

| Approach | Evidence type | Data in Optic now? | Build / change | Effort | Validation |
|---|---|---|---|---|---|
| GEX by strike, convention sign | Formula MATH; sign HEUR (index EMP-backed, single stock contradicted) | Yes (stale OI) | Label "assumes dealers long calls, short puts"; show units ("$ delta per 1% move"); single stocks default to unsigned concentration | S | Compare SPY sign history vs SqueezeMetrics; next-day abs-return by sign bucket on stored snapshots |
| Gamma flip | Computation MATH; level-as-signal HEUR | Yes | Show as zone (+/- band from IV sensitivity), state stale-OI date; hide if GEX profile never crosses or crosses multiple times | S | Recompute with +/-2 vol pts IV; if flip moves > 2% call it "unstable" |
| Call/put walls | HEUR; MKT if called support/resistance | Yes | Rename "largest gamma strikes"; drop support/resistance wording | S | Expiry-day pinning test vs placebo strikes |
| Vanna/charm exposure | MATH formula; no validation | Yes | Advanced-only, HEUR label | S | none credible; keep descriptive |
| Normalised GEX (% of ADV) | EMP-motivated (Ni et al.; Baltussen) | Yes | Add hedge-flow per 1% / 20-day $ADV | S | Decile sort of next-day abs return |
| Activity-concentration ("unusual") | Definitional | Yes | Rename; add liquidity gate; drop "bullish/bearish" wording unless signed data | S | Next-day dOI share |
| dOI confirmation | Definitional | Needs stored OI | Persist daily OI per contract | M | Coverage/consistency |
| O/S ratio | EMP (Johnson-So 2012) | Yes (chain vol + stock vol) | Descriptive "options vs stock activity"; no return claim | S-M | Cross-sectional backtest on own history |
| P/C volume ratio | HEUR (not Pan-Poteshman) | Yes | Add caption: mixes buys/sells, opens/closes | S | n/a |
| Signed/open-close flow | EMP (PP 2006; GLP 2016) | No | Paid Cboe/ISE data | L | Replicate PP sort |
| Liquidity grade | HEUR thresholds anchored on EMP (BPS 12.6%) | Yes (no sizes) | Section 3.5 grade, ticks + %, zero-bid/locked handling | S | Spot-check vs broker; later vs effective spreads |
| Vertical natural vs mid cost | MATH | Yes | Show both and cost % of max profit | S | Unit tests |
| IV rank | needs IV history | No (realised-vol proxy) | Store daily ATM IV per ticker from Yahoo now; or ORATS | S (store) / M (vendor) | After 252 days compare to ORATS |
| Observed dealer inventory | EMP (Cboe 2023) | No | Vendor (PROP) or Cboe data | L | Cboe published figures |

## 6. What Optic must NOT claim

1. **"Dealers are long/short gamma here"** as fact. Public OI has no side; the only evidence with observed inventory uses exchange origin data (Ni et al. 2021; Cboe 2023). SpotGamma itself calls GEX a model output. Say "if dealers hold the typical positioning...".
2. **"Call wall = resistance, put wall = support", "price will pin to max pain".** Pinning evidence is an expiration-day close effect of ~16.5 bp average (NPP 2005), conditional on hedgers being long gamma; no study validates walls as levels. Vendors themselves disclaim it.
3. **"Below the flip, the market will fall / volatility will spike".** Evidence links negative gamma to larger moves and intraday momentum (Baltussen et al. 2021; Ni et al. 2021), **not to direction**, and effects are conditional and modest. Baltussen et al. warn their sign proxy is positive on most days partly by construction.
4. **"0DTE dealer hedging drives the market".** Cboe 2023 and Dim-Eraker-Vilkov 2024 find balanced 0DTE flow and no amplification on average (conflicting studies exist).
5. **"Smart money / whale / sweep / bullish flow"** from Yahoo snapshots. Snapshots carry no side, open/close, sweep or origin. Even with OPRA, the quote rule is ~80-87% accurate on old Cboe data and worse for complex and auction prints (Savickas-Wilson 2003; Bryzgalova et al. 2023).
6. **"High put/call ratio predicts a drop" (or a contrarian bounce)** citing Pan-Poteshman. Their signal is open-buy, non-MM, cross-sectional, and its predictive part was not publicly observable.
7. **"Unusual activity predicts takeovers/earnings".** About 25% of M&A targets show abnormal pre-deal volume (Augustin et al. 2019); the base rate of M&A among flagged contracts is tiny.
8. **"You'll fill at mid" / "liquid" without qualification.** No quote sizes in Yahoo; options are outside Rule 605; retail typically pays wide spreads (12.6% average, BPS 2023). Say "price-width grade; size unknown".
9. **"IV rank"** when it is a realised-vol percentile. Call it "realised-volatility percentile" until IV history exists.
10. Any GEX number without **units and as-of time** (per $1 vs per 1% differ by a factor of S/100).

## 7. Formulas and definitions to adopt (units explicit)

- Contract multiplier M = 100 (check for adjusted/non-standard deliverables; Yahoo does not flag them reliably, so treat contracts with odd strikes/roots as suspect).
- BS gamma Gamma = phi(d1) / (S sigma sqrt(T)) [per $1 of S, per share]; with continuous dividend yield q multiply by e^(-qT).
- **Dollar GEX per 1% move** (per contract line): GEX_i = s_i x Gamma_i x OI_i x M x S^2 x 0.01, s_i = +1 calls, -1 puts under the convention [units: $ of delta-hedge per 1% move in S]. Per $1 move: divide by (0.01 x S) [units: shares x $ per $1]. **Share GEX per $1** (SqueezeMetrics original): s_i x Gamma_i x OI_i x M [shares per $1].
- **Normalised GEX** = sum GEX_i (per 1%) / ADV$_20d [fraction of a typical day's dollar volume that hedging would trade per 1% move].
- **Unsigned gamma concentration** at strike K = sum over expiries of |Gamma| x OI x M x S^2 x 0.01.
- **Gamma flip** S* = root of G(S') = sum s_i Gamma_i(S', sigma_i, T_i) OI_i M S'^2 0.01 on a grid S' in [0.8S, 1.2S], IV held at each contract's current sigma (sticky strike); report "none" or "multiple" when appropriate.
- **Vanna** (BS) = -e^(-qT) phi(d1) d2 / sigma [delta per unit vol]; **VEX per vol point** = s_i x Vanna_i x OI_i x M x S x 0.01 [$ delta per +1 IV point]. **Charm** = d(delta)/dt per calendar day (use the BS closed form with q; report per day). Both HEUR as flow signals.
- **Relative quoted spread** = (ask - bid)/((ask + bid)/2), valid only if 0 <= bid < ask. **Spread in ticks** = (ask - bid)/tick (penny-program rule, section 3.3).
- **Effective spread** (when trades available) = 2 x D x (P - mid_t)/mid_t.
- **Vertical natural debit** = ask_long - bid_short; **mid debit** = mid_long - mid_short; **round-trip cost %** = (natural - mid) x 2 / max profit.
- **Vol/OI** = day volume / prior-session OI (undefined when OI = 0: show "new series").
- **dOI_t** = OI_t - OI_(t-1) [net contracts opened; unsigned].
- **O/S** = sum chain volume x M / stock share volume (Johnson & So use contract volume over share volume; keep Optic's ratio definition fixed and documented).
- **P/C volume ratio** = put volume / call volume (all strikes, chosen expiries); **P/C OI ratio** likewise; both descriptive.
