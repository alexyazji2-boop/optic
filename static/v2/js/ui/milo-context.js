// The Milo Context Bar (Handoff 6): what Milo is researching, said the same way in the panel's bar, above each
// answer and in the conversation kept in history. Pure functions of the focus the panel sends with a question
// (ui/milo.js buildContext) or of what the server says it used (its `context` event, app/ai.py context_used, which
// has the same shape): the ticker, the chart's bar size and range, the dates in view, the indicators with their
// settings, the Dossier tab, and on Compare the names and the one the reader picked, if any. Identifiers and
// settings only: no value is said here, so none can disagree with the chart.

// The chart's bar sizes (pages/chart.js INTERVALS) and ranges in words; app/ai.py has the same two tables
export const TIMEFRAMES = { 1: '1-minute', 5: '5-minute', 15: '15-minute', 30: '30-minute', 60: 'hourly', 240: '4-hour', daily: 'daily', weekly: 'weekly' };
const RANGES = { '1M': '1 month', '3M': '3 months', '6M': '6 months', '1Y': '1 year', ALL: 'all of its history' };
const cap = (s) => (s ? s[0].toUpperCase() + s.slice(1) : '');
const join = (xs) => (xs.length > 1 ? `${xs.slice(0, -1).join(', ')} and ${xs[xs.length - 1]}` : xs[0] || '');
const label = (x) => (typeof x === 'string' ? x : x && x.label) || '';

/** What a focus says Milo is researching, in the shape of the server's context_used. */
export function researchOf(focus) {
  const f = focus || {}, chart = f.chart || {}, cmp = f.compare || null;
  const general = f.scope === 'none' || !!f.unavailable;
  const out = { scope: f.unavailable ? 'none' : f.scope || 'auto', general, unavailable: !!f.unavailable, ticker: null, section: null, timeframe: null, range: null, visible: null, indicators: [], compared: [], compare: null, removed: [] };
  if (general || out.scope === 'market') return out;
  const tickers = cmp ? (cmp.tickers || []).filter(Boolean).slice(0, 4) : [];
  // Compare: the name the reader picked, or none. Never one of them chosen for the reader.
  if (tickers.length >= 2) out.compare = { tickers, focus: tickers.includes(cmp.focus) ? cmp.focus : null };
  out.ticker = out.compare ? out.compare.focus : f.ticker || null;
  if (!out.ticker) return out;
  out.section = f.section || null;
  out.timeframe = TIMEFRAMES[chart.interval] || null;
  if (chart.interval === 'daily' || chart.interval === 'weekly') out.range = RANGES[String(chart.range || '').toUpperCase()] || null;
  if (chart.visible_from && chart.visible_to) out.visible = { from: chart.visible_from, to: chart.visible_to };
  out.indicators = (chart.indicators || []).map(label).filter(Boolean);
  out.compared = (chart.compared || []).filter((s) => s && s !== out.ticker).slice(0, 3);
  out.removed = (f.indicators_removed || []).map(label).filter((x) => x && !out.indicators.includes(x));
  return out;
}

/** The bar's line: "AAPL · Daily · RSI 14, MACD 12, 26, 9 · Chart", or with `short` "AAPL · Daily" (a phone's). */
export function researchLine(rf, { short = false } = {}) {
  if (!rf) return '';
  if (!rf.ticker) return rf.compare ? `${rf.compare.tickers.join(' vs ')} · ${short ? 'No focus' : 'No single focus'}` : '';
  const parts = [rf.ticker];
  if (rf.timeframe) parts.push(cap(rf.timeframe));
  if (short) return parts.join(' · ');
  if (rf.indicators.length) parts.push(rf.indicators.join(', '));
  if (rf.compare) parts.push(`Compare, with ${rf.compare.tickers.filter((t) => t !== rf.ticker).join(', ')}`);
  else if (rf.section) parts.push(rf.section);
  return parts.join(' · ');
}

/** For a screen reader, the line in words: "AAPL, daily chart, with RSI 14 and MACD 12, 26, 9, Chart tab". */
export function researchWords(rf) {
  if (!rf || !rf.ticker) return rf && rf.compare ? `the comparison of ${join(rf.compare.tickers)}, with no single name in focus` : '';
  const out = [rf.timeframe ? `${rf.ticker}, ${rf.timeframe} chart` : rf.ticker];
  if (rf.indicators.length) out.push(`with ${join(rf.indicators)}`);
  if (rf.compare) out.push(`in the comparison with ${join(rf.compare.tickers.filter((t) => t !== rf.ticker))}`);
  else if (rf.section) out.push(`${rf.section} tab`);
  return out.join(', ');
}

// "2026-05-06" or "2026-10-28T09:30", New York's, as a reader says it: "May 6, 2026", "Oct 28, 9:30 am"
function stamp(s, withYear) {
  const m = /^(\d{4})-(\d{2})-(\d{2})(?:[T ](\d{2}):(\d{2}))?$/.exec(String(s || ''));
  if (!m) return '';
  const day = new Date(Date.UTC(+m[1], +m[2] - 1, +m[3])).toLocaleDateString('en-US', { month: 'short', day: 'numeric', timeZone: 'UTC' });
  if (m[4] === undefined) return withYear ? `${day}, ${m[1]}` : day;
  const h = +m[4], ap = h < 12 ? 'am' : 'pm', h12 = h % 12 || 12;
  return `${day}, ${h12}:${m[5]} ${ap}`;
}
/** The dates in view: "May 6 to Nov 4, 2026", or with times on intraday bars "Oct 28, 9:30 am to Nov 4, 1:00 pm ET". */
export function visibleWords(v) {
  if (!v || !v.from || !v.to) return '';
  const intraday = String(v.from).length > 10;
  const sameYear = String(v.from).slice(0, 4) === String(v.to).slice(0, 4);
  return `${stamp(v.from, !sameYear && !intraday)} to ${stamp(v.to, !intraday)}${intraday ? ' ET' : ''}`;
}

/** Each part of the research, labelled, for the bar's menu. */
export function researchRows(rf) {
  if (rf && !rf.ticker && rf.compare) return [['Comparing', join(rf.compare.tickers)], ['Focus', 'None: the comparison as a whole']];
  if (!rf || !rf.ticker) return [];
  const rows = [['Ticker', rf.ticker]];
  if (rf.timeframe) rows.push(['Timeframe', `${cap(rf.timeframe)} bars${rf.range ? `, ${rf.range} loaded` : ''}`]);
  if (rf.visible) rows.push(['In view', visibleWords(rf.visible)]);
  if (rf.timeframe) rows.push(['Indicators', rf.indicators.length ? rf.indicators.join('; ') : 'None']);
  if (rf.compared.length) rows.push(['Compared with', rf.compared.join(', ')]);
  if (rf.compare) rows.push(['Compare', `with ${join(rf.compare.tickers.filter((t) => t !== rf.ticker))}`]);
  else if (rf.section) rows.push(['Dossier', rf.section]);
  return rows;
}

/** Indicators on the chart at the last question and not now, the ticker unchanged, as {id, label}: the server names
 *  them by id (app/ai.py _CTX_INDICATORS), the panel's note by label. */
export function removedSince(last, focus) {
  const f = focus || {}, now = (f.chart || {}).indicators;
  if (!last || !Array.isArray(now) || !f.ticker || last.ticker !== f.ticker) return [];
  const on = now.map((x) => x && x.id);
  return (last.indicators || []).filter((x) => x && x.id && !on.includes(x.id));
}

/** What an answer was for, above it: "For AAPL · Daily · RSI 14 · Chart", or why it was for no company. */
export function usedLine(used) {
  if (!used) return '';
  if (used.unavailable) return 'Page context unavailable: answered in general, with no ticker assumed';
  if (used.general) return 'General question: no ticker in focus';
  if (used.ticker) return `For ${researchLine(used)}`;
  if (used.compare) return `For the comparison of ${join(used.compare.tickers)}, no single name in focus`;
  return '';
}

/** A copy small enough to keep with each answer in the conversation's history. */
export function keepUsed(used) {
  if (!used || typeof used !== 'object') return null;
  const s = (v, n = 40) => (typeof v === 'string' ? v.slice(0, n) : null);
  const list = (v, n) => (Array.isArray(v) ? v.map((x) => s(x, 60)).filter(Boolean).slice(0, n) : []);
  const out = { scope: s(used.scope, 8), general: !!used.general, unavailable: !!used.unavailable, ticker: s(used.ticker, 12), section: s(used.section), timeframe: s(used.timeframe, 12), range: s(used.range), visible: used.visible && s(used.visible.from, 16) && s(used.visible.to, 16) ? { from: s(used.visible.from, 16), to: s(used.visible.to, 16) } : null,
    indicators: list(used.indicators, 12), compared: list(used.compared, 3), removed: list(used.removed, 12), compare: null, at: s(used.at, 40) };
  if (used.compare && Array.isArray(used.compare.tickers)) out.compare = { tickers: list(used.compare.tickers, 4), focus: s(used.compare.focus, 12) };
  return out;
}
