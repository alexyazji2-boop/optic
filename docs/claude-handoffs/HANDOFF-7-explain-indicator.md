# Handoff 7: Explain This Indicator

Branch `handoff-7-explain-indicator`, cut from `handoff-6-milo-context` (Handoff 6, PR #14) on 2026-11-04, because
the handoff depends on Handoff 6's context. Its PR is based on that branch, so the diff shows this handoff alone.
Not deployed.

## What existed, verified first

| The handoff asks to verify | What the code has |
|---|---|
| The indicator inventory and settings model | 23 overlays and 10 panes on the v2 chart (`pages/chart.js` OVERLAYS, PANES), with fixed settings. Handoff 6 recorded each one's settings (`STUDY_SPEC`). |
| Whether values are computed in the browser | Yes, for these five. `ui/pricechart.js` computes the moving averages, Bollinger Bands, RSI and MACD on the chart's bars. Keltner, Donchian, the regression channel, ADX, Stochastic, MFI and the RS line come from `/api/indicators`. |
| What the reader could see | The legend printed the averages' and bands' values at the crosshair's bar. The RSI and MACD panes printed no value at all. |
| Milo's indicator integration | Only an action card that turns an indicator on. Milo could not be sent a reading. |

So the values are passed from the chart, not computed again on the server, as the handoff asks.

## What was built

**The registry** (`app/indicator_registry.py`, served at `GET /api/indicator-registry`), on the pattern of Handoff 1's
figure registry. It is a module of its own, so it does not collide with that branch.
- **Each entry:**
  - the indicator's name and its settings;
  - what it measures at each of the reader's five knowledge levels;
  - the formula in words and in symbols;
  - its limits;
  - where its definition comes from: Wilder (1978) for RSI, Appel for MACD, Bollinger (2001), and the standard
    averages.
- **The first five, as the handoff asks:** RSI 14, MACD 12, 26, 9, MA 20, 50, 200, EMA 9, 21, 50 and Bollinger 20, 2.
  Another joins only with its entry and tests.
- **`clean_reading`** checks what the chart sends:
  - a known indicator, a ticker and a bar size;
  - numbers or nothing for each value, and the bar's date;
  - why there is no value. The browser sends only which case, and the server words it.
- **`describe`** says what a reading describes, from the reading alone, for example "An RSI of 57.78 means that over
  the last 14 bars, with Wilder's smoothing, the average gain on up bars was 1.37 times the average loss on down
  bars."
  - It never judges.
  - It names "overbought" and "oversold" only as names for a reading, "not a forecast".

**The chart** (`ui/pricechart.js`, `pages/chart.js`).
- **Where Explain sits:**
  - on the legend rows of the averages and the bands, and on the RSI and MACD panes, beside Remove;
  - under each of the five in the Indicators and Panes menus while it is on the chart, which is how a phone reaches
    it.
- **`chart.reading(id)`** gives the indicator's values at the latest bar, from the arrays the chart draws.
- **What a press sends:** the reading, the bar's date (a date on daily bars, a New York time on intraday ones),
  whether the bar is still forming, and the bar count.
  - A forming bar is an intraday bar until its period ends, a daily bar on a trading day while the session is open,
    or a weekly bar all week.
- **The panes now print their value** at the crosshair's bar ("RSI 14: 57.78", "MACD 12, 26, 9: 2.36, signal 3.21"),
  so the number Milo is sent is one the reader can see.

**Milo** (`ui/milo.js`, `app/ai.py`, `app/main.py`).
- **A press drafts the question** ("Explain RSI 14 on this AAPL daily chart: …") with the reading attached. Nothing
  is sent until Send, by the owner's standing rule. The reading is about the symbol on screen only, and a press brings
  the page's context back after a Remove.
- **What the server tells Milo:**
  - the reading, as the chart's values and the bar's date;
  - Optic's description of it;
  - the definition at the reader's level, the formula and the limits;
  - the answer's fixed shape: **What it measures**, **The current reading**, **Limitations**, **Sources**.
  - Milo is to quote the values exactly, name both sources, and describe, never advise.
  - With no value, Milo is told why and to give the general explanation only, beginning "Live value unavailable: …".
- **Cost:** an Explain press looks nothing up (no named symbols, market read, research pack, framework or levels).
  It is answered from the reading and the definition.
- **The answer:**
  - Above it, Optic's card: the indicator and its settings, the ticker and bar size, the values as the chart prints
    them with the bar's date, Optic's description, and "still forming" when it is. With no value, it says why and
    that the general explanation follows.
  - Below it, the price data's and the definition's sources, and **More detail**, which drafts the deeper question.
  - The reading is kept with the conversation, as Handoff 6's context is.

**The advice gate** (`app/ai_policy.py`) now also catches two shapes that turn a reading into an order: "RSI at 72
is overbought, consider taking profits" and "it's time to take profits". Its 438 existing tests still pass, and
attributed or hypothetical sentences ("some traders consider trimming") still pass through.

## Acceptance tests (Handoff 7)

`tests/test_explain_indicator.py`, on real AAPL and SPY daily closes
(`tests/fixtures/explain_bars_AAPL_SPY_2026-11-04.json`), the chart's own maths in JavaScriptCore, and the real chat
route with a stand-in for the model.

- **RSI, MACD, SMA and Bollinger explanations on AAPL and SPY show values matching the chart, at two knowledge levels,
  with a limitations section.** `test_acceptance_1_*`:
  - for each of the four, on both tickers, at beginner and advanced, the model is sent every value exactly as the
    chart prints it and the bar's date;
  - it gets the definition for that level (and not another's), the limits, and the four headings;
  - the card prints the same values;
  - a separate test holds the arrays read to the ones the chart draws.
- **Too little history and no value render per the edge-case rules.** `test_acceptance_2_*`:
  - ten bars: "not enough data for a 14-bar RSI yet: it needs 15 bars and the chart has 10";
  - no bars: "the chart's bars did not load";
  - thirty bars: a MACD line with "no signal line yet";
  - the card and the instructions for each.
- **No recommendation language in a test corpus of explanations.** `test_acceptance_3_*`:
  - Optic's own words have none: every level's definition, the formulas, the limits, and the description over a grid
    of 61 readings (the extremes, crossings, closes outside the bands);
  - a corpus of answer sentences that turn readings into orders is caught by the advice gate, and descriptive ones
    pass.
- **Also:**
  - both sides agree on the indicators, their values and their names;
  - Explain sits on each indicator and only drafts;
  - a press gathers no research, says its reading once, and keeps it with the conversation;
  - general mode reads no reading.

## Live check, 2026-11-04

A local server on this branch, the local test account, real market data, and the stand-in model, which quotes what
it was sent.

- **The panes:** AAPL's daily chart printed "RSI 14: 57.78" and "MACD 12, 26, 9: 2.36, signal 3.21", with Explain on
  both.
- **Explain on RSI:**
  - Milo opened with the question drafted and nothing sent.
  - The attached reading was RSI 57.779 on 2026-11-04, 501 bars, not forming, after the close.
  - Sent, the card read "RSI 14 · AAPL · Daily, RSI 57.78 on Nov 4, 2026, An RSI of 57.78 means … 1.37 times the
    average loss", matching the pane.
  - The sources line and More detail were under the answer.
  - Milo had been told the reading, the description, the definition for the reader's level and the four-part shape.
- **A chart whose bars failed:** "Live value unavailable: the chart's bars did not load, so Optic has no live value.
  What follows is the general explanation only."
- **Phone, 390 px:** Explain under MA, Bollinger, RSI and MACD in the menus, the pane buttons at 44 px, and nothing
  scrolls sideways.

## Decisions for review

1. **Explain drafts and does not send.** The handoff says a press "sends Milo" the reading, and it does go with the
   question, but the owner's standing rule is that nothing reaches the model before Send. A press costs a question
   only when sent.
2. **The latest bar's value, not the crosshair's.** "Live value" is the newest bar's, so it is the same wherever the
   reader has scrolled. Its date is always said.
3. **Five indicators.** The handoff's start set (RSI, MACD, SMA/EMA, Bollinger). Keltner, Donchian, ADX, Stochastic,
   MFI, the regression channel and WaveTrend are computed on the server, and each would need its definitions and
   tests first.
4. **The advice gate grew by two shapes.** It applies to every Milo answer, not only explanations. It was measured on
   its existing sets and on the new corpus.

## Found and not fixed here

1. **The registry's home.** When Handoff 1 (PR #9) is merged, the indicator entries could move under `app/figures`
   beside the figure registry. They are kept apart here so the two branches do not collide.
2. **The server-side indicators** (Keltner, Donchian, ADX, Stochastic, MFI, the regression channel, the RS line,
   WaveTrend) have no Explain yet; see decision 3.
3. **A real model's answers** were not read: no model call was made. The shape, values and rules it is given are
   tested; its wording is not.
