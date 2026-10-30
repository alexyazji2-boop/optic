// Dossier, Chart: the data behind the classic studies (C11), for ui/pricechart.js to draw. Only what is on is
// fetched, and each answer is kept for the symbol and the bars it was asked for:
//   Keltner, Donchian, the regression channel and anchored VWAP, and the ADX, Stochastic, on-balance volume,
//     money flow and relative strength panes (C19): /api/indicators, on these very bars (the chart's intraday
//     size and window, weekly, or All), so the lines are bar for bar with the candles;
//   Weinstein stages: /api/stage, the stage of every week; a daily or intraday bar takes its last completed week's;
//   auto trend lines: /api/trendlines, fitted on a year of daily bars, drawn on daily and weekly charts;
//   accumulation zones: /api/longterm, from twelve years of weekly bars;
//   supply and demand: the ticker payload the page already has;
//   WaveTrend: /api/indicators/wavetrend, on these very bars as the panes above are, with its crosses,
//     divergences and what followed them (ui/wavetrend.js draws the pane and the block under the chart).
// None of them calls a model. EMA clouds, MA Trend, TSO, volume by price and session dividers need nothing:
// ui/pricechart.js works them out from the bars.
import * as api from '../core/api.js';
import { num, clean } from '../core/format.js';
import { alignLines, stageOfBars, trendSegments, weekMonday } from '../ui/studies.js';
import { onBars as waveOnBars, evidenceBlock } from '../ui/wavetrend.js';

/* What each one is, for the Indicators menu: the classic app's own descriptions where it has one. */
export const HELP = {
  cloud921: 'The area between the 9 and 21-bar EMAs, blue while the faster is above, amber while it is below: the current leg.',
  cloud2150: 'The area between the 21 and 50-bar EMAs: the trend the current leg is running inside.',
  keltner: 'An EMA with bands at 2x ATR. Worth having because it disagrees with Bollinger: the bands are a multiple of the average range, not of the spread of closes.',
  donchian: 'The highest high and lowest low of the last 20 bars: a breakout is a close outside it.',
  sec: 'A least-squares line through the last 100 bars with bands at 2 standard errors. The R-squared in the note under the chart says whether the line fits at all.',
  vwap: 'The volume-weighted average price paid since the first bar in view (on intraday bars, since the window began). An execution benchmark, not a signal.',
  zones: 'Supply and demand: a narrow base followed by a fast departure, from the daily pattern read; only zones price could reach in about two months.',
  accum: 'From the long-term model\'s twelve years of weekly bars: the 40 and 200-week averages and the retracements of the multi-year range.',
  trends: 'Lines Optic fits to the swing highs and lows of the last year of daily bars, kept only if price touched them more than twice. On daily and weekly bars.',
  vbp: 'The volume traded at each price among the bars in view, from the right edge; the longest bar is the point of control.',
  sessions: 'A dashed line where each trading day starts, on intraday bars.',
  stages: 'Each candle in the colour of its week\'s Weinstein stage: light green basing, green advancing, amber topping, red declining. A daily or hourly bar takes the last completed week\'s, the reading that stood when it printed.',
  // the panes from /api/indicators (C19), in the classic catalogue's words
  adx: 'Trend strength, with direction carried separately by +DI and -DI. Over 25 counts as trending, by Wilder\'s rule. It lags by construction.',
  stochastic: 'Where the close sits inside the last 14 bars\' range. In a strong trend it pins near an extreme for weeks, so 80 has been a bad reason to sell more often than a good one.',
  obv: 'Volume signed by the bar\'s direction, accumulated: whether the volume is going with the price.',
  mfi: 'RSI computed on price times volume rather than price alone, 0 to 100.',
  rs: 'Price divided by SPY, rebased to 100 at the first bar. Rising means doing better than the index, which can also mean losing less.',
  matrend: 'Colours each candle by where it opened and closed against the 10, 20, 50, 100 and 200-bar simple averages: green above all five, red below all five, grey between. While it is on it colours the candles in place of Stages.',
  wavetrend: 'LazyBear\'s oscillator: the typical price against its 9-bar EMA in units of its average distance from it, smoothed over 12 bars (WT1, the area), with a 3-bar average of that (WT2, the line). Dots mark where they cross, larger beyond 53 either side of zero; a line joins two pivots where price and WT2 disagree. Under the chart, what followed each signal on these bars, against entries at random.',
};
const SERVER = ['keltner', 'donchian', 'sec', 'vwap'];
export const SERVER_PANES = ['adx', 'stochastic', 'obv', 'mfi', 'rs'];

let P = null;   // the page: sym(), bars(), iv(), range(), session(), weekly(), firstShown(), t(), repaint()
let S = {};     // this symbol's answers, replaced by reset()
export function bind(page) { P = page; }
export function reset() { S = {}; }

const get = (key, url, opts) => {
  if (S[key] !== undefined || S[key + 'Busy']) return;
  const box = S;
  box[key + 'Busy'] = true;
  api.get(url, opts).then((r) => { box[key] = r; }, (e) => { box[key] = { available: false, reason: e.message || 'did not load' }; })
    .finally(() => { box[key + 'Busy'] = false; if (S === box && P) P.repaint(); });
};
// The query for /api/indicators that matches the chart's bars, as the classic studyQuery builds it.
function barsQuery() {
  const iv = P.iv();
  if (iv.intraday) return `intraday=${iv.key}&window=${iv.history}&session=${P.session()}`;
  if (P.weekly()) return `weekly=true&range=${P.range() === 'All' ? 'max' : '10y'}`;
  return P.range() === 'All' ? 'range=max' : '';
}
// `on` is the overlays and the panes together: what is ticked in Indicators
function serverKey(on) {
  const ids = SERVER.concat(SERVER_PANES).filter((k) => on[k]);
  if (!ids.length || !P.bars()) return null;
  // VWAP's anchor is the first bar in view (its week's Monday on weekly bars); intraday the server anchors itself
  let anchor = '';
  if (on.vwap && !P.iv().intraday) { const t = P.firstShown(); const d = t ? new Date(t).toISOString().slice(0, 10) : ''; anchor = P.weekly() ? weekMonday(d) || d : d; }
  return [ids.join(','), barsQuery(), anchor].join('|');
}

/** Start whatever the studies that are on need. Safe to call on every redraw: each request is made once. */
export function need(on) {
  if (!P) return;
  const enc = encodeURIComponent(P.sym());
  const k = serverKey(on);
  if (k && S.indKey !== k) {
    const [ids, q, anchor] = k.split('|'), box = S;
    S.indKey = k; S.ind = undefined;
    api.get(`/api/indicators/${enc}?ids=${ids}${q ? `&${q}` : ''}${anchor ? `&anchor=${anchor}` : ''}`, { ttl: 300000, timeout: 60000 })
      .then((r) => { if (box.indKey === k) box.ind = r; }, (e) => { if (box.indKey === k) box.ind = { available: false, reason: e.message || 'did not load' }; })
      .finally(() => { if (S === box && box.indKey === k && P) P.repaint(); });
  }
  // WaveTrend on the same bars as the panes above; daily bars ask for nothing and get the route's ten years
  if (on.wavetrend && P.bars() && S.wtKey !== barsQuery()) {
    const q = barsQuery(), box = S;
    S.wtKey = q; S.wt = undefined;
    api.get(`/api/indicators/wavetrend/${enc}${q ? `?${q}` : ''}`, { ttl: 300000, timeout: 60000 })
      .then((r) => { if (box.wtKey === q) box.wt = r; }, (e) => { if (box.wtKey === q) box.wt = { available: false, reason: e.message || 'did not load' }; })
      .finally(() => { if (S === box && box.wtKey === q && P) P.repaint(); });
  }
  if (on.stages) get('stage', `/api/stage?symbol=${enc}`, { ttl: 3600000, timeout: 45000 });
  if (on.trends) get('tl', `/api/trendlines/${enc}`, { ttl: 600000, timeout: 45000 });
  if (on.accum) get('lt', `/api/longterm/${enc}`, { ttl: 3600000, timeout: 60000 });
}

/* Laid on the current bars, kept until the bars or the answer change. */
const memo = new Map();
const once = (name, deps, fn) => { const m = memo.get(name); if (m && m.deps.length === deps.length && m.deps.every((d, i) => d === deps[i])) return m.v; const v = fn(); memo.set(name, { deps, v }); return v; };
const dayKeys = (bars) => bars.map((b) => new Date(b.t).toISOString().slice(0, 10));

/** The panes in an /api/indicators answer, laid on the bars: each one's lines and reference levels, or why not. */
export function panesFrom(ind, bars) {
  return Object.fromEntries(SERVER_PANES.filter((k) => ((ind || {}).indicators || {})[k]).map((k) => {
    const x = ind.indicators[k];
    return [k, x.available === false ? { name: x.name, reason: x.reason || 'not available for these bars' } : { name: x.name, lines: alignLines(ind.dates, x.lines, bars), reference: x.reference || [] }];
  }));
}

/** What the chart draws for the studies that are on, from whatever has arrived. */
export function data(on) {
  const out = { studies: {}, stageNames: null };
  if (!P || !P.bars()) return out;
  const bars = P.bars(), iv = P.iv(), st = out.studies;
  const ind = S.ind;
  if (ind && ind.available !== false && S.indKey === serverKey(on)) {
    st.lines = once('lines', [ind, bars], () => Object.fromEntries(SERVER.filter((k) => (ind.indicators || {})[k] && ind.indicators[k].available !== false).map((k) => [k, alignLines(ind.dates, ind.indicators[k].lines, bars)])));
    st.panes = once('panes', [ind, bars], () => panesFrom(ind, bars));
  }
  if (on.wavetrend && S.wt && S.wtKey === barsQuery()) {
    const w = S.wt;
    st.wavetrend = w.available === false ? { reason: w.reason || 'not available for these bars' } : once('wavetrend', [w, bars], () => waveOnBars(w, bars));
  }
  if (on.stages && S.stage && S.stage.available === true) {
    st.stages = once('stages', [S.stage, bars], () => stageOfBars(bars, S.stage.history, { weekly: P.weekly(), intraday: !!iv.intraday }));
    out.stageNames = S.stage.names || null;
  }
  if (on.trends && S.tl && S.tl.available && !iv.intraday) st.trends = once('trends', [S.tl, bars], () => trendSegments(S.tl, dayKeys(bars), { weekly: P.weekly() }));
  if (on.accum && S.lt && S.lt.holding) st.accum = ((S.lt.holding.accumulation_zones) || []).filter((z) => z && Number.isFinite(z.price)).map((z) => ({ price: z.price, label: `${z.label} ${num(z.price)}` }));
  const t = P.t();
  // on intraday bars, the intraday answer's own zones (P.patterns); else the daily pattern read's
  const pat = (P.patterns && P.patterns()) || (t && t.patterns) || null;
  if (on.zones && pat) st.zones = ((pat.zones) || []).filter((z) => !z.out_of_horizon && Number.isFinite(z.top) && Number.isFinite(z.bottom)).map((z) => ({ t: Date.parse(String(z.formed).length > 10 ? z.formed : `${z.formed}T00:00:00Z`), top: z.top, bottom: z.bottom, side: z.side, broken: !!z.broken }));
  return out;
}

/** A line under the chart for each study that is on and has nothing to draw, saying why, or its reading. */
export function notes(on) {
  if (!P || !P.bars()) return [];
  const out = [], iv = P.iv(), ind = S.ind;
  const ids = SERVER.concat(SERVER_PANES).filter((k) => on[k]);
  if (ids.length) {
    if (ind === undefined) out.push('Loading the indicators.');
    else if (ind && ind.available === false) out.push(`The indicators did not load: ${ind.reason || 'no answer'}.`);
    else if (ind) ids.forEach((k) => { const x = (ind.indicators || {})[k]; if (!x) return; if (x.available === false) out.push(`${x.name || k}: ${x.reason || 'not available for these bars'}.`); else if (x.reading) out.push(`${x.name}: ${clean(x.reading)}`); });
  }
  if (on.stages) { if (S.stage === undefined) out.push('Loading the stages.'); else if (S.stage.available !== true) out.push(`Weinstein stages: ${S.stage.reason || 'not available for this symbol'}.`); else out.push(clean(`${String(S.stage.label || '').replace(' · ', ', ')}. ${S.stage.explain || ''}`).trim()); }
  if (on.trends) { if (iv.intraday) out.push('Auto trend lines are drawn on daily and weekly bars.'); else if (S.tl === undefined) out.push('Loading the trend lines.'); else if (!S.tl.available) out.push(`Auto trend lines: ${S.tl.reason || 'none found'}.`); else if (!(S.tl.lines || []).length) out.push('Auto trend lines: none that price touched more than twice and can still reach.'); }
  if (on.accum) { if (S.lt === undefined) out.push('Loading the accumulation zones.'); else if (!S.lt.holding) out.push(`Accumulation zones: ${S.lt.reason || 'not available for this symbol'}.`); }
  if (on.zones) { const t = P.t(); if (!t) out.push('Loading supply and demand.'); else if (!(((t.patterns || {}).zones) || []).some((z) => !z.out_of_horizon)) out.push('Supply and demand: no zone within reach of the price.'); }
  if (on.sessions && !iv.intraday) out.push('Session dividers are drawn on intraday bars.');
  if (on.wavetrend) { const w = S.wt; if (w === undefined || S.wtKey !== barsQuery()) out.push('Loading WaveTrend.'); else if (w.available === false) out.push(`WaveTrend: ${clean(w.reason || 'not available for these bars')}.`); }
  return out;
}

/** What followed WaveTrend's signals on these bars, under the chart while its pane is on and its answer is in. */
export function evidence(on) {
  if (!P || !P.bars() || !on.wavetrend || !S.wt || S.wt.available === false || S.wtKey !== barsQuery()) return '';
  return evidenceBlock(S.wt);
}
