# v2 load performance: targets and results

## Targets (written 2026-10-18 before the measurement below was run)

**Conditions**
- **Profiles:** the same documented throttling as Stage 0 (`stage0/load_perf.py`).
  - Phone: 390×844, 150 ms round trip, 1.6 Mbps down and 750 kbps up, CPU slowed 4×.
  - Desktop: 1440×900, 40 ms round trip, 10 Mbps, no CPU slowdown.
- **Pages:** v2 and Classic Home and Dossier (AAPL), signed in. Server caches are warmed first, so the figures measure the frontend.
- **Runs:** 9 per cell, cold (cache cleared) and warm (a fresh visit with the cache). Each cell reports the median, the interquartile range (p25 to p75), and the minimum and maximum.

**The two times measured**
- **First paint:** First Contentful Paint.
- **Usable content:** the page's primary figure is on screen (Home: the market strip's numbers; Dossier: the quote) AND at least one content block is filled (120+ characters, no loading placeholder in it). It is the same rule for both apps, each with its own markers. It replaces Stage 0's looser "content ready".

| # | Target | Why |
|---|---|---|
| T1 | Phone, cold: v2 usable content, median ≤ 4.5 s and no slower than Classic's median | The worst realistic first visit must not be worse than today |
| T2 | Phone, warm: v2 usable content, median ≤ 1.5 s and no slower than Classic's median | The common case: a returning reader |
| T3 | Desktop, cold: v2 usable content, median ≤ 2.0 s | |
| T4 | Desktop, warm: v2 usable content, median ≤ 1.0 s and no slower than Classic's median + 0.2 s | Stage 0 showed v2's warm desktop Dossier waiting on the quote |
| T5 | Phone, cold: v2 first paint, median ≤ 3.0 s | Stage 0 measured 2.73 s (2 runs) |
| T6 | Spread: every v2 cell's IQR ≤ 25% of its median, or ≤ 300 ms | Typical, not lucky |
| T7 | No regression against Stage 0: v2 first-paint medians within +10% of Stage 0's | Stage 0 usable content was measured by another rule, so only first paint is compared |

Download size is reported only as context. It is not evidence for any target.

## Results (2026-10-18, `stage0/perf-run3`, 9 runs per cell)

Times are in seconds: the median, then the interquartile range (p25 to p75) in brackets, then the minimum to the maximum.

**Phone (150 ms, 1.6 Mbps, CPU 4×)**

| Page | v2 first paint | v2 usable content | Classic first paint | Classic usable content |
|---|---|---|---|---|
| Home, cold | 2.74 [2.72–2.75] 2.70–2.78 | **3.46** [3.43–3.47] 3.37–4.29 | 3.44 [3.43–3.44] | **7.70** [7.70–7.78] 7.69–7.98 |
| Dossier, cold | 2.72 [2.70–2.73] 2.70–2.75 | **3.35** [3.35–3.38] 3.34–3.41 | 3.43 [3.42–3.44] | **7.24** [7.22–7.26] 7.22–7.34 |
| Home, warm | 0.27 [0.27–0.28] | **0.94** [0.94–0.96] 0.90–1.43 | 0.42 | **1.19** [1.09–1.25] 1.07–1.43 |
| Dossier, warm | 0.27 [0.27–0.27] | **0.92** [0.92–0.92] 0.91–0.92 | 0.42 | **0.80** [0.79–0.80] 0.78–0.81 |

**Desktop (40 ms, 10 Mbps)**

| Page | v2 first paint | v2 usable content | Classic first paint | Classic usable content |
|---|---|---|---|---|
| Home, cold | 0.68 [0.67–0.68] | **0.98** [0.98–1.36] 0.97–1.39 | 0.63 | **1.52** [1.48–1.70] 1.48–2.20 |
| Dossier, cold | 0.68 [0.68–0.68] | **0.88** [0.88–0.88] 0.87–1.08 | 0.62 | **1.33** [1.28–1.38] 1.27–1.74 |
| Home, warm | 0.10 [0.09–0.10] | **0.36** [0.36–0.56] 0.35–0.97 | 0.14 | **0.48** [0.40–0.48] 0.39–0.49 |
| Dossier, warm | 0.10 [0.10–0.11] | **0.26** [0.26–0.26] 0.26–0.46 | 0.14 | **0.28** [0.28–0.28] 0.27–0.29 |

## Against the targets

| # | Target | Result |
|---|---|---|
| T1 | Phone cold usable ≤ 4.5 s and ≤ Classic | **Met.** Home 3.46 s (Classic 7.70 s); Dossier 3.35 s (Classic 7.24 s) |
| T2 | Phone warm usable ≤ 1.5 s and ≤ Classic | **Missed on Dossier.** Home 0.94 s (Classic 1.19 s) meets it. Dossier 0.92 s is under 1.5 s but 0.12 s slower than Classic's 0.80 s, and consistent across all 9 runs, so it is a real gap. Its cause is not isolated; the likely suspects are v2's first Overview section waiting on the larger `/api/ticker` answer, and v2's rendering cost on a 4× slower CPU |
| T3 | Desktop cold usable ≤ 2.0 s | **Met.** 0.98 s and 0.88 s |
| T4 | Desktop warm usable ≤ 1.0 s and ≤ Classic + 0.2 s | **Met.** 0.36 s (Classic 0.48 s), 0.26 s (Classic 0.28 s) |
| T5 | Phone cold first paint ≤ 3.0 s | **Met.** 2.74 s and 2.72 s. Classic: 3.44 s |
| T6 | Every v2 cell's IQR ≤ 25% of median or ≤ 300 ms | **Missed on desktop cold Home.** Runs split into 0.97–0.98 s (6) and 1.36–1.39 s (3). The slow runs also finished their network later (1.31–1.59 s against 0.97 s), so a slower server answer, not the page, appears to gate them. Classic Home shows a similar spread (1.48–2.20 s). The request responsible is not isolated. Every other v2 cell meets T6 |
| T7 | v2 first paint within +10% of Stage 0 | **Met.** Every cell is within 2% of Stage 0's 2-run figures |

**Not covered here:**
- **Production differences:** production serves over HTTP/2 through Railway's edge, while this server is local HTTP/1.1. v2's 73 module requests should cost less there, but that is unmeasured.
- **Other pages:** only Home and Dossier were measured.

**Open items, carried into M8:**
- T2 on the phone warm Dossier;
- T6 on desktop cold Home, where the slow request has to be found first;
- a production measurement in the owner preview, using Server-Timing on `/api/ticker` and the same scripts against the live URL, with the owner's session.