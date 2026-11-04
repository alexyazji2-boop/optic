# Handoff 6: the Milo Context Bar

Branch `handoff-6-milo-context`, cut from `main` at c623c264 on 2026-11-04. It does not depend on Handoffs 1 to 5 and
can be reviewed and merged on its own. Not deployed.

## What existed, verified first

The handoff asked for a context test before any building: open AAPL's chart, ask "explain this chart", and see
whether the answer is about AAPL without the reader typing it. Two parts of that test were possible here.

- **The code.** v2's Milo already sent its context with every question: the page's own figures, and a `focus` block
  with the ticker, the page's name, and the chart's range and bar size. The server already followed `focus.ticker` for
  the research pack, the framework and the chart levels.
- **What the model is sent.** Tested with a stand-in for the model that records each request. On the AAPL chart,
  "Explain this chart." reached it with AAPL in the CONTEXT header, so an answer about AAPL was already possible.

The real model was not called. The local server has no working model key, and a call on the live site costs money and
needs your yes. So whether Claude's answer names AAPL is unverified; what it is told is verified.

Measured against the handoff, the gaps were:

| The handoff asks for | What the code did |
|---|---|
| A bar: "Researching: TICKER · Timeframe · Indicators · Section" | A menu labelled "NVDA / Chart"; no bar size, no indicators |
| Indicators with their settings | Indicator names only, with no settings and not in the header |
| The chart's visible range | Not sent |
| Answers say the ticker and timeframe they used | Not asked of Milo. The line above an answer said "About AAPL; asked from AAPL Dossier, Chart" |
| Context logged with the conversation | Not kept: history held the words only |
| Removing context: general questions, no ticker guessed | "No page context" sent no page, but nothing stopped Milo taking the company from earlier answers, and Deep research still took the page's ticker |
| Compare: the focus explicit, never silently chosen | No focus at all; the header said only "the Compare page" |
| An indicator removed mid-conversation is noted | Not tracked |
| A context failure: general mode with a visible note | The answer ended with "Milo could not gather the figures for this question" |
| The header names the chart readably | "with the chart on 6M 60" (the bar size's code, 60, not "hourly") |

So this handoff makes the context visible and editable, and adds what was missing. Nothing that worked was rebuilt.

## What was built

**The bar** (`ui/milo-context.js` says it; `ui/milo.js` draws it).
- **Where it sits:** at the top of Milo's panel, whenever the page has a ticker: "Researching AAPL · Daily · RSI 14,
  MACD 12, 26, 9 · Chart".
- **Change:** pressing the line opens its menu, which:
  - lists the ticker, the timeframe (bar size and range loaded), the dates in view, the indicators with their
    settings, anything else on the chart (the earnings and insider marks), and the Dossier tab;
  - says that Milo only reads it, and never changes the chart, watchlists or alerts;
  - offers what Milo receives, as before: this page, the market only, or nothing.
- **Remove (×):** one press, and Milo answers in general, about no company. The picker then says "No page context"
  with "Use AAPL" beside it, one press back.
- **Following the page:**
  - a navigation repaints it, as does a page registering its context;
  - the chart calls `contextChanged()` on every view change (bar size, range, an indicator on or off) and when new
    bars arrive. A size with no intraday feed falls back to daily, and the bar says Daily.
- **Pages with no ticker** (Home, Markets, Watchlist) keep the "What Milo receives" picker as before. No bar.
- **Width:** beside the page a docked panel is about 440 px wide, so there:
  - the bar takes the first line, and Response settings moves beside the data line;
  - under 500 px the word "Change" gives way to its chevron.
- **On a phone:** the bar is "AAPL · Daily" with the chevron that opens the rest, on Response settings' line. The
  panel's chrome is the same height as before, and the box stays on screen (measured below).

**What is sent** (`buildContext` in `ui/milo.js`; the chart's part from `pages/chart.js`).
- `focus.section`: the Dossier tab.
- `focus.chart`:
  - `interval` and `range`;
  - `visible_from` and `visible_to`: the first and last bar in view, a date on daily and weekly bars, a New York time
    on intraday ones;
  - `indicators`, each `{id, label, settings}`. The settings come from `STUDY_SPEC`, the numbers the chart computes
    with, checked against `ui/pricechart.js`, `ui/studies.js`, `app/analytics/indicators.py` and
    `app/analytics/wavetrend.py`;
  - `compared`: the symbols overlaid on the chart.
- `focus.compare`: on Compare, the names, and `focus` (the one the reader picked, or null).
- `focus.indicators_removed`: indicators that were on the chart at the last question about the same ticker and are
  not now.
- Identifiers and settings only. All 18 indicators on, the focus is under 2,500 characters. The chart page still sends
  a count of its bars, never the bars.

**What Milo is told** (`app/ai.py`: `research_focus`, `context_header`, `_research_lines`).
- **The research, in words:** "The reader is researching AAPL on the Chart tab of its Dossier: daily bars, 6 months
  loaded, 2026-05-07 to 2026-11-04 in view, with MA 20, 50, 200 and RSI 14 on the chart."
- **The ticker needs no typing:** the question is about AAPL unless it names another symbol, and the answer starts by
  saying the ticker and timeframe it is for ("For AAPL, on the daily chart, ...").
- **Where a figure comes from:**
  - a figure from another bar size than the chart's says which;
  - the indicators named are settings, not values;
  - a value comes only from the data or a tool, with its settings and bar size, never from memory.
- **No holdings, no advice:** what the reader has open says what they are researching, not what they own. Milo never
  infers a position, and the answer stays an explanation, not a recommendation.
- **Removed indicators:** if an earlier answer cited one, Milo says in one line that it is no longer on the chart.
- **General mode:** no ticker is in focus. Milo takes no company from the page, from earlier answers or from memory
  unless the question names one, and "explain this chart" gets "none is selected" or a general answer.
- **Compare without a focus:** Milo answers about the comparison, and asks which name rather than choosing one.
  With a focus, it answers about that name.
- **Context unavailable:** none was sent, and Milo is told not to guess a ticker.
- **Who names the indicators:** the server, from its own table by id (`_CTX_INDICATORS`, which a test holds to the
  chart's), so no text from the browser reaches the prompt as an indicator. The tab names, bar sizes and ranges are
  checked the same way, as are the dates (by pattern) and the tickers.
- **Classic:** it sends only the page and the chart's size, and keeps its old one-line header. The general-mode
  wording applies to both apps: it is the same "No page context" choice.

**What the answer says it was for.**
- The chat route sends a `context` event before the answer (`ai.context_used`): what it used, after its checks.
- The panel draws it above the answer in the bar's words: "For AAPL · Daily · MA 20, 50, 200, RSI 14 · Chart, 6:02
  pm". Optic draws this line itself, so it is there whatever the model writes.
- When the question named another company, the line says "About NVDA; AAPL · Daily · Chart attached as context".
- A general answer says "General question: no ticker in focus".
- One whose context could not be read says, as a note, "Page context unavailable: answered in general, with no
  ticker assumed".
- **Kept with the conversation:** each answer's account goes into this browser's Milo history (`context` on the
  answer's message, with the time it was asked), so a reopened conversation still says what each answer was for and
  when.

**Compare.** The bar says "AAPL vs MSFT · No single focus" until the reader picks a name in the menu. The pick:
- turns the bar to "MSFT · Compare, with AAPL";
- makes the server research MSFT;
- belongs to the page: a navigation forgets it.

A focus the browser claims outside the comparison is dropped on both sides.

**Failure.** Each of these sends no page context and is said, never a guessed ticker:
- a page whose context throws;
- a context that cannot be turned into JSON;
- a context the server cannot read;
- a context the server fails to gather.

The bar says "Page context unavailable". The answer goes ahead in general mode, where it used to end with an error.

## Acceptance tests (Handoff 6)

`tests/test_milo_context_bar.py` drives the panel's real code in JavaScriptCore and posts what it builds to the real
chat route. A stand-in for the model records what it was sent.

- **AAPL daily chart, "explain this chart", no AAPL typed; the bar shows AAPL · Daily.**
  `test_acceptance_1_*`. It checks:
  - the bar ("AAPL · Daily", Remove beside it, the whole line said to a screen reader);
  - the focus, with the indicators' settings;
  - the model's CONTEXT ("researching AAPL ... daily bars", "For AAPL, on the daily chart");
  - the `context` event and the line drawn above the answer;
  - that the research pack follows AAPL.
- **Switching to SPY updates the bar and the next answers.** `test_acceptance_2_*`:
  - the bar changes at once on the route;
  - it follows the chart's own changes without a navigation (hourly, then daily);
  - the next question goes as SPY's, with Milo told of the switch from AAPL.
- **Removing context returns Milo to general mode with no ticker guessed.** `test_acceptance_3_*`:
  - nothing from the page is sent, and no ticker;
  - Milo is told not to take one from the page or earlier answers;
  - no company's research is gathered;
  - a ticker forged into general mode is dropped;
  - Deep research and the answer's label take no ticker either.
- **Compare: the focused ticker is explicit, not silently chosen.** `test_acceptance_4_*`:
  - no focus by default, and the bar and Milo say so;
  - a pick in the menu sets it on both sides;
  - a name outside the comparison is never the focus;
  - navigation forgets the pick.
- **Edge cases:**
  - an indicator taken off mid-conversation;
  - a context that cannot be read, in the browser and on the server;
  - no ticker open;
  - the payload's size and contents;
  - the server's own names (with hostile input);
  - no portfolio in the context;
  - each answer's account kept with the conversation;
  - the two sides agreeing;
  - the phone layout;
  - the controls' names and announcements.
- **One older test changed:** `tests/test_v2_milo_streaming.py` pinned the old error on a failed gather. It now pins
  general mode, with the same intent: the reader is told, without the internals.

## Live check, 2026-11-04

On a local server on this branch, with a fresh local test account, real market data, and the stand-in model (a copy
of `~/Optic/work/post-demo-ultra-2026-10-29/tools/milo_standin_ultra.py`). The stand-in quotes the CONTEXT lines it
was sent, so each answer below shows what Milo was told. Its words are not a model's.

- **AAPL, daily, at 1440 px with Milo docked:** the bar read "Researching AAPL · Daily · MA 20, 50, 200 · Chart".
  - "Explain this chart." was answered under "For AAPL · Daily · MA 20, 50, 200 · Chart".
  - The model had been told "The reader is researching AAPL on the Chart tab of its Dossier: daily bars, 6 months
    loaded, 2026-05-07 to 2026-11-04 in view".
  - The first run said 2026-11-03 for the last bar: daily bars are midnight UTC and had been read in New York time.
    Fixed, and checked again.
- **SPY, with the panel open:**
  - the bar turned to "SPY · Hourly · MA 20, 50, 200 · Chart", the chart's own bar size;
  - the earlier answer said "Not about SPY, the page now open", and the panel said the next question would be
    about SPY;
  - "And this one?" was answered under "For SPY · Hourly · ...", with Milo told of the switch from AAPL.
- **Remove (×):** one press.
  - The picker read "No page context · Use SPY", with focus on it.
  - "Explain this chart." was answered under "General question: no ticker in focus".
  - The stand-in, given no ticker, called no tool.
  - "Use SPY" put the bar back.
- **Compare, AAPL and MSFT:**
  - "AAPL vs MSFT · No single focus"; the answer was "For the comparison of AAPL and MSFT, no single name in focus",
    with Milo told to ask rather than choose;
  - picking MSFT in the menu made it "MSFT · Compare, with AAPL", and the answer "For MSFT · Compare, with AAPL".
- **RSI on, then off:** the bar followed each change at once. The next question noted "RSI 14 is no longer on the
  chart. Milo is told, in case an earlier answer used it", and the model was told so.
- **A page context made to throw:**
  - the bar said "Page context unavailable" with its note;
  - the answer was "Page context unavailable: answered in general, with no ticker assumed";
  - Milo was told not to guess a ticker.
- **Home:** no bar; the "Home" picker as before.
- **Phone, 375 by 549:**
  - the bar read "Researching AAPL · Daily", with Remove at 44 px;
  - nothing scrolled sideways, and the box ended at 539 of 549 px;
  - the menu, from the chevron, listed the ticker, "Daily bars, 6 months loaded", "May 7 to Nov 4, 2026", the
    indicators and the tab.
- **Phone, 375 by 360 (a keyboard's worth less):**
  - the bar and Response settings share one line, and the box is still on screen (301 to 360 px);
  - the chrome is the same height as with the picker alone, plus the attached-parts row that was already there.

## Decisions for review

1. **Beside the page, Response settings moves to the data line when the bar is shown.** A docked panel is about
   440 px wide. On the picker's line the bar had room for "AAPL" alone; on its own line it reads in full. On a
   phone, and on pages with no ticker, the layout is unchanged.
2. **Remove holds across pages until changed.** It is the same choice as "No page context", which already held.
   "Use AAPL" puts the page's context back with one press. If you would rather each new page start with its context,
   it is one line.
3. **A context that fails to gather answers in general mode instead of ending the answer.** This is the handoff's
   error state. Classic gets the same answer without a note, since it ignores the new event; Milo is told to say it
   had no page context.
4. **Indicator values are not sent.** The bar and the header carry names and settings; Milo is told a value comes
   only from the data or a tool, with its bar size. Matching the chart's own value exactly is Handoff 7's job, which
   its spec says.
5. **The "For AAPL · Daily" line is Optic's, not the model's.** Milo is also told to open with the ticker and
   timeframe, but its wording is unverified without a model call. The line is there whatever it writes.
6. **Compare starts with no focus.** The handoff's selector is the bar's menu: "The comparison as a whole", then each
   name.

## Found and not fixed here

1. **With Handoff 3 (alexyazji2-boop/optic#11):** on `main` an unknown symbol opens a Dossier, so the bar would name
   it. Handoff 3's not-found page stops that page from being a Dossier. When both are merged, check that its page
   shows no bar.
2. **With Handoff 5 (alexyazji2-boop/optic#13):** a saved conversation keeps its messages and sources. It could keep
   each answer's `context` too, so a reopened saved answer says what it was for. One line in `conversationSpec` once
   both are in.
3. **With Handoff 4 (alexyazji2-boop/optic#12):** the panel's data line here is `main`'s ("Prices are delayed up to
   15 minutes"). Handoff 4 replaces it.
4. **Timeframes on the other tabs.** Only the Chart tab has a bar size. The Overview's small chart sends none, so the
   bar there is "AAPL · Overview".
5. **The chrome on a small phone** (the persona row and the attached list) leaves the conversation little room with
   the keyboard up. That predates this handoff, and the bar adds no height to it.
