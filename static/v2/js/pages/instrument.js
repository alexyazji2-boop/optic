// One cross-asset instrument: an index level, a yield, a currency pair, a
// commodity or a future, opened from Markets, Discover and Home. Five tiles
// and its chart from /api/instrument. A reference series, not a price you can
// deal at.
import { html, render as draw } from '../core/dom.js';
import * as api from '../core/api.js';
import { num, signed, clean, isNum, dir } from '../core/format.js';
import { skeleton, failed } from '../ui/states.js';
import { button as miloButton, provideContext } from '../ui/milo.js';
import { createPriceChart } from '../ui/pricechart.js';

const RANGES = [['1mo', '1M'], ['3mo', '3M'], ['6mo', '6M'], ['1y', '1Y'], ['2y', '2Y'], ['5y', '5Y']];
let D = {}, live = true, mainEl = null, chart = null, range = '1y', style = 'line';

function paint() {
  if (!live) return;
  const d = D.d, sym = D.sym;
  if (chart) { chart.destroy(); chart = null; }
  const sn = (d || {}).snapshot || {}, dp = Math.abs(sn.last) < 10 ? 4 : 2;
  const rsiWord = !isNum(sn.rsi) ? 'Not enough history' : sn.rsi >= 70 ? 'Overbought territory' : sn.rsi <= 30 ? 'Oversold territory' : 'Mid-range';
  draw(mainEl, html`<header class="page-head"><p class="t-label">${d ? (d.group === 'fx' ? 'FX' : (d.group || 'Instrument')) : 'Instrument'}</p><div class="split"><h1 class="t-display-m">${d ? `${d.name || d.label} (${d.label || sym})` : sym}</h1>
      ${miloButton('Ask Milo what this is', { ask: `What is ${d ? d.label || sym : sym}, and why does it matter for markets right now?`, context: `Instrument, ${sym}` })}</div>${d && (d.about || d.note) ? html`<p class="section-sub">${clean(d.about || d.note)}</p>` : ''}</header>
    ${D.err ? failed('This instrument', D.err, { retry: 'instrument' }) : !d ? skeleton('chart', 1, 'Loading the history') : html`
      <dl class="kv" style="--kv:5"><div><dt>Last</dt><dd>${num(sn.last, dp)} <small class="${dir(sn.chg_1d)}">${signed(sn.chg_1d)}</small></dd></div>
        <div><dt>20 days</dt><dd>${signed(sn.chg_20d)}</dd></div><div><dt>Against the 200-day</dt><dd>${signed(sn.vs_sma200)} <small class="t-muted">${num(sn.sma200, dp)}</small></dd></div>
        <div><dt>RSI</dt><dd>${num(sn.rsi, 0)} <small class="t-muted">${rsiWord}</small></dd></div><div><dt>From the 52-week high</dt><dd>${signed(sn.pct_from_52w_high)}</dd></div></dl>
      <div class="ctools" style="margin-top:18px"><div class="seg" role="group" aria-label="Range">${RANGES.map(([k, l]) => html`<button type="button" data-v2-inst-range="${k}" aria-pressed="${range === k}">${l}</button>`)}</div>
        <div class="seg" role="group" aria-label="Style">${[['line', 'Line'], ['candles', 'Candles'], ['area', 'Area']].map(([k, l]) => html`<button type="button" data-v2-inst-style="${k}" aria-pressed="${style === k}">${l}</button>`)}</div></div>
      <div class="pc-host" id="inst-chart"></div>
      <p class="asof">A reference series, not a price you could deal at. Source: Yahoo Finance. Tiles use a year of bars whatever the range.</p>`}`);
  if (d && (d.dates || []).length > 4) {
    const bars = d.dates.map((t, i) => ({ t: Date.parse(t), o: (d.open || [])[i] ?? d.close[i], h: (d.high || [])[i] ?? d.close[i], l: (d.low || [])[i] ?? d.close[i], c: d.close[i], v: (d.volume || [])[i] || 0 })).filter((b) => isNum(b.c));
    chart = createPriceChart(mainEl.querySelector('#inst-chart'), { bars, style, overlays: { events: false }, panes: { volume: !!d.volume, rsi: false, macd: false }, window: bars.length, label: d.label || sym, height: 400 });
  }
}

async function load() {
  D.d = null; D.err = null; paint();
  try { D.d = await api.get(`/api/instrument?symbol=${encodeURIComponent(D.sym)}&range=${range}`, { ttl: 300000, timeout: 45000 }); if (D.d && D.d.available === false) { D.err = new api.ApiError('notfound', 404, clean(D.d.reason || 'No history.')); D.d = null; } }
  catch (e) { D.err = e; }
  paint();
}
export async function render(main, route) {
  live = true; mainEl = main; D = { sym: route.symbol };
  document.title = `${route.symbol}, Optic`;
  provideContext(() => ({ view: 'instrument', focus_label: D.d && D.d.label ? `${D.d.label} (${D.sym})` : '', instrument: D.d ? { symbol: D.sym, label: D.d.label, snapshot: D.d.snapshot } : null }));
  main.addEventListener('click', (e) => {
    const r = e.target.closest('[data-v2-inst-range]'); if (r) { range = r.dataset.v2InstRange; load(); return; }
    const s = e.target.closest('[data-v2-inst-style]'); if (s) { style = s.dataset.v2InstStyle; if (chart) chart.set({ style }); mainEl.querySelectorAll('[data-v2-inst-style]').forEach((b) => b.setAttribute('aria-pressed', String(b === s))); }
  });
  load();
}
export function dispose() { live = false; if (chart) { chart.destroy(); chart = null; } }
export const retry = { instrument: () => load() };
