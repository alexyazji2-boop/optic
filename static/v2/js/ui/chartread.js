// The chart read, carried over from the current app (owner's brief, 2026-10-19, item 16: the classic
// chartReadModel and chartReadHTML, static/app.js). What the chart says in a few lines: the trend and the
// facts it rests on, the nearest support and resistance, and where RSI and MACD stand.
//
// Nothing is asked of a model and nothing is fetched: every figure is in the /api/ticker payload the Chart
// page already loads (`technicals`), so it costs nothing and opens at once. The technicals are computed on
// completed daily sessions, so the read says Daily whatever the bars on screen.
import { html } from '../core/dom.js';
import { num } from '../core/format.js';

const RSI_WORDS = { overbought: 'Overbought', oversold: 'Oversold', bullish: 'Firm', bearish: 'Soft', neutral: 'Neutral' };
const MACD_EVENTS = {
  'bullish crossover today': 'Crossed above its signal today',
  'bearish crossover today': 'Crossed below its signal today',
  'histogram expanding up': 'Momentum building',
  'histogram expanding down': 'Momentum fading',
};
const fin = Number.isFinite;

/** The read from a ticker payload, or null when there is not enough daily history for a 200-day average. */
export function chartReadModel(payload) {
  const t = (payload && payload.technicals) || {};
  const ma = t.moving_averages || {};
  const s20 = ma.sma20 || {}, s50 = ma.sma50 || {}, s200 = ma.sma200 || {};
  if (!fin(s200.value) || !fin(s50.value)) return null;
  const above = (m) => m.position === 'above';
  const st = t.structure || {};

  let trend = 'Mixed trend';
  if (above(s200) && s50.value > s200.value) trend = 'Uptrend';
  else if (!above(s200) && s50.value < s200.value) trend = 'Downtrend';

  const side = (m, n) => (fin(m.distance_pct) ? `Price is ${num(Math.abs(m.distance_pct), 1)}% ${above(m) ? 'above' : 'below'} the ${n}-day average.` : null);
  const facts = [side(s200, 200), side(s50, 50), side(s20, 20)].filter(Boolean);
  if (st.stacked_bullish) facts.push('The 20, 50 and 200-day averages are stacked in rising order.');
  else if (st.stacked_bearish) facts.push('The 20, 50 and 200-day averages are stacked in falling order.');
  else facts.push('The averages are not stacked in order, so the trend is not settled.');
  if (fin(s50.slope_10d_pct)) facts.push(`The 50-day average is ${s50.slope_10d_pct >= 0 ? 'rising' : 'falling'}, ${num(Math.abs(s50.slope_10d_pct), 2)}% over ten sessions.`);
  if (st.cross_event) {
    facts.push(/golden/.test(st.cross_event) ? 'The 50-day crossed above the 200-day in the last five sessions.'
      : 'The 50-day crossed below the 200-day in the last five sessions.');
  }

  // The nearest band either side of price, from the zones the Support and resistance overlay draws.
  const zones = Array.isArray(t.support_resistance) ? t.support_resistance : [];
  const nearest = (role, below) => zones
    .filter((z) => z.role === role && fin(z.distance_pct) && (below ? z.distance_pct <= 0 : z.distance_pct >= 0))
    .sort((a, b) => Math.abs(a.distance_pct) - Math.abs(b.distance_pct))[0] || null;
  const r = t.rsi || {}, m = t.macd || {};
  return {
    trend,
    facts,
    support: nearest('support', true),
    resistance: nearest('resistance', false),
    rsi: fin(r.value) ? `${RSI_WORDS[r.state] || 'Neutral'}, ${num(r.value, 0)}` : null,
    macd: MACD_EVENTS[m.event] || (m.state === 'bullish' ? 'Above its signal' : m.state === 'bearish' ? 'Below its signal' : null),
  };
}

/** The card. state: 'loading' | 'failed' | undefined. */
export function chartReadCard(sym, payload, state) {
  const head = html`<h2 class="t-h3 cr-title" id="cr-h">Chart read, daily</h2>`;
  if (state === 'loading') return html`${head}<p class="cr-note" role="status">Reading ${sym}'s daily technicals.</p>`;
  if (state === 'failed') return html`${head}<p class="cr-note">${sym}'s daily technicals did not load, so there is no read. The chart itself is unaffected.</p>`;
  const model = chartReadModel(payload);
  if (!model) return html`${head}<p class="cr-note">Not enough daily history for a 200-day average yet, so there is no trend to read.</p>`;
  const band = (z) => (z ? `${num(z.band_low, 2)} to ${num(z.band_high, 2)}` : 'None in range');
  const tone = model.trend === 'Uptrend' ? 'up' : model.trend === 'Downtrend' ? 'down' : '';
  return html`${head}
    <p class="cr-trend ${tone}">${model.trend}</p>
    <ul class="cr-facts">${model.facts.map((f) => html`<li>${f}</li>`)}</ul>
    <dl class="cr-rows">
      <div><dt>Nearest support</dt><dd>${band(model.support)}</dd></div>
      <div><dt>Nearest resistance</dt><dd>${band(model.resistance)}</dd></div>
      <div><dt>RSI 14</dt><dd>${model.rsi || 'Not in the data'}</dd></div>
      <div><dt>MACD 12, 26, 9</dt><dd>${model.macd || 'Not in the data'}</dd></div>
    </dl>
    <p class="cr-note">From completed daily sessions, whatever the bars on screen. The zones are the ones Support and resistance draws. Research only, not a recommendation.</p>`;
}
