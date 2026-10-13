# Competitive research brief (shared by all research agents)

## About Optic (the product we are researching for)
Optic Terminal (theopticterminal.com) is a retail investment research web app. Promise: "Complex analysis, presented simply."
Users say it is useful but overwhelming; even finance majors struggle with the concepts.
Audience: self-directed retail investors and traders who follow ~5-25 US stocks, plus finance students.
What it has today (all free, data from Yahoo via yfinance, no billing yet):
- Home: market strip, "What matters today", a daily AI-written Read/Desk, "what changed since yesterday" briefing.
- Company page ("Dossier"): Overview with five plain questions (what it does, from the 10-K), Optic Score (short/long term),
  bull and bear case, charts (indicators, stages, MA trend, drawing), financials, earnings, news, insiders, options
  analytics (GEX, expected move, skew, term structure), valuation history.
- Markets (macro, sectors, rotation), Discover/Scan (plain-English screener), Compare, watchlists, watches (alerts),
  paper portfolios, a retirement projector.
- Milo: AI research companion (a snowman mascot). Sees the page context, can propose in-app actions (open chart, add to
  watchlist after confirm, draw a level grounded in computed data, build a screen), writes digests (what changed / why /
  what to watch), explains any figure ("Explain this"), knows the paper book. Free accounts: 3 messages/day.
- Known weaknesses: no validated edge for scores/setups, no email delivery yet, no landing pages/SEO, no billing,
  unlicensed data, dense pages.

## Rules
- Use only public sources: official product pages, help centers/knowledge bases, docs, pricing pages, official
  demo videos/blogs, app store listings, and reputable reviews. Use WebSearch and WebFetch.
- Never sign up, create accounts, log in, enter personal data, accept terms, purchase, or download files.
- Label every finding with an evidence type:
  - **DOC** = official documentation / help center describes it.
  - **MKT** = marketing claim on a product/landing page.
  - **OBS** = you directly observed it on a publicly accessible page (e.g. a public free screener page that loads
    without login). Say exactly what you loaded.
  - **3P** = third-party review/press.
  - **INF** = your inference.
  Never imply you tested a restricted or paid product.
- Record source URL + date read (2026-10-12) for every finding.
- Do not copy proprietary text at length; paraphrase. Quotes under 15 words, max one per competitor.
- WRITE YOUR FILE EARLY (within the first few minutes, a skeleton) AND UPDATE IT INCREMENTALLY after each competitor,
  so work survives if you are interrupted.

## For each competitor, cover
1. Target audience and core promise.
2. The workflow that makes it compelling.
3. Time/steps to first useful insight for a new user.
4. Information hierarchy, defaults, progressive disclosure, terminology (jargon handling).
5. Charting, screening, research, portfolio, alert workflows (whichever apply).
6. AI: context awareness (does it know what's on screen / your holdings?), financial reasoning, sources/citations,
   tools, follow-up actions, response structure, known quality issues/hallucination handling.
7. Mobile usability and continuity between tasks/devices.
8. Recurring value (why come back), subscription packaging, prices, free tier limits, upgrade triggers.
9. Weaknesses, friction, underserved users Optic could address.

## Concrete journeys to assess (for each competitor where applicable, as documented)
- J1: Researching an unfamiliar company from scratch.
- J2: Preparing a swing-trade thesis (multi-day).
- J3: Understanding a sudden price move today.
- J4: Evaluating portfolio exposure / concentration.

## Output format (markdown)
Per competitor: a section with the 9 points and 4 journeys, each finding tagged [DOC/MKT/OBS/3P/INF] with a source link.
Then at the end of your file:
- A table: Competitor strength | User problem solved | Evidence type + source | Implication for Optic
- "Baseline expectations" (what every serious product in this space does that a user will expect)
- "Proven ideas worth adapting" (with how to adapt to Optic's plain-English audience, not copy)
- "Unserved needs / gaps" (evidence-based)
Keep it dense and factual. 2,500-5,000 words.
