// Dossier, Chart. The full-height price chart: bar size and range, candles,
// line or area, averages, Bollinger bands, Fibonacci, support and resistance,
// dealer gamma levels, earnings markers, volume, RSI and MACD, and drawings.
//
// Bars: daily from /api/ticker (two years) or /api/daily-bars (All), weekly
// from /api/weekly-bars, intraday from /api/intraday. Like the classic app the
// page opens on hourly bars. Drawings are kept per symbol in the classic key,
// so a line drawn here shows there and the other way round. The view choices
// are a setting of this browser (optic.v2.chart.v1).
import { $, $$, html, render as draw, isPhone } from '../core/dom.js';
import { CLASSIC } from '../core/classic.js';
import * as api from '../core/api.js';
import * as store from '../core/store.js';
import { holds } from '../core/device.js';
import { num, clean, isNum } from '../core/format.js';
import { skeleton, failed } from '../ui/states.js';
import { icon } from '../ui/icons.js';
import { button as miloButton, provideContext, openMilo } from '../ui/milo.js';
import { toast } from '../ui/toast.js';
import { createPriceChart } from '../ui/pricechart.js';
import { core, header, tabs, isFund } from './dossier-frame.js';

const VIEW_KEY = 'optic.v2.chart.v1';
const DRAW_KEY = 'optic.chart.drawings.v2';
const INTERVALS = [
  { key: '1', label: '1m', intraday: true, history: '5d', period: 1 }, { key: '5', label: '5m', intraday: true, history: '1mo', period: 5 },
  { key: '15', label: '15m', intraday: true, history: '60d', period: 30 }, { key: '30', label: '30m', intraday: true, history: '60d', period: 30 },
  { key: '60', label: '1h', intraday: true, history: '1y', period: 91 }, { key: '240', label: '4h', intraday: true, history: '2y', period: 365 },
  { key: 'daily', label: '1D' }, { key: 'weekly', label: '1W' },
];
const RANGES = { daily: { '1M': 21, '3M': 63, '6M': 126, '1Y': 252, All: Infinity }, weekly: { '1M': 5, '3M': 13, '6M': 26, '1Y': 52, All: Infinity } };
const TOOLS = [['select', 'Select and move'], ['hline', 'Horizontal line'], ['vline', 'Vertical line'], ['trend', 'Trend line'], ['ray', 'Ray'], ['rect', 'Rectangle'], ['fibdraw', 'Fibonacci retracement'], ['text', 'Text note']];
const OVERLAYS = [['ma', 'MA 20, 50, 200'], ['ema', 'EMA 9, 21, 50'], ['bb', 'Bollinger 20, 2'], ['fib', 'Fibonacci'], ['sr', 'Support and resistance'], ['gex', 'Dealer gamma levels'], ['msb', 'Market structure breaks'], ['events', 'Earnings']];
const PANES = [['volume', 'Volume'], ['rsi', 'RSI 14'], ['macd', 'MACD 12, 26, 9']];

let D = {}, V = {}, live = true, mainEl = null, chart = null;

function readView() {
  const d = { interval: '60', range: '6M', style: 'candles', session: 'regular', overlays: { ma: true, ema: false, bb: false, fib: false, sr: false, gex: false, msb: false, events: true }, panes: { volume: true, rsi: false, macd: false }, msbK: 5 };
  try { const s = JSON.parse(localStorage.getItem(VIEW_KEY) || 'null'); if (s && typeof s === 'object') { Object.assign(d, s, { overlays: Object.assign(d.overlays, s.overlays || {}), panes: Object.assign(d.panes, s.panes || {}) }); } } catch (e) { /* private */ }
  d.interval = '60'; // the Chart page opens on hourly bars, as in the classic app
  return d;
}
function saveView() { try { localStorage.setItem(VIEW_KEY, JSON.stringify({ range: V.range, style: V.style, session: V.session, overlays: V.overlays, panes: V.panes, msbK: V.msbK })); } catch (e) { /* private */ } }

function readDrawings(sym) {
  if (!holds(store.state.user)) return [];
  try { const all = JSON.parse(localStorage.getItem(DRAW_KEY) || '{}'); return Array.isArray(all[sym]) ? all[sym].filter((d) => d && Array.isArray(d.points)) : []; } catch (e) { return []; }
}
function saveDrawings(sym, list) {
  if (!holds(store.state.user)) { toast('Drawings are not saved: this browser is holding another account\'s things.'); return; }
  try {
    // re-read, so drawings another tab saved for other symbols survive
    const all = JSON.parse(localStorage.getItem(DRAW_KEY) || '{}');
    if (list.length) all[sym] = list; else delete all[sym];
    localStorage.setItem(DRAW_KEY, JSON.stringify(all));
  } catch (e) { toast('This browser refused to save the drawing.'); }
}

/* ---------------- bars ---------------- */
async function loadBars() {
  const sym = D.sym, enc = encodeURIComponent(sym), iv = INTERVALS.find((x) => x.key === V.interval);
  D.bars = null; D.barsErr = null; paintChart();
  try {
    let bars;
    if (iv.intraday) {
      const d = await api.get(`/api/intraday/${enc}?range=${iv.key}&window=${iv.history}&session=${V.session}`, { ttl: 60000, timeout: 45000 });
      if (!d.available) throw new api.ApiError('notfound', 404, clean(d.reason || 'No intraday bars right now.'));
      bars = d.times.map((t, i) => ({ t: Date.parse(t), o: d.opens[i], h: d.highs[i], l: d.lows[i], c: d.closes[i], v: d.volumes[i] }));
      D.note = d.session_note;
    } else if (V.interval === 'weekly') {
      const d = await api.get(`/api/weekly-bars/${enc}?span=${V.range === 'All' ? 'max' : '10y'}`, { ttl: 3600000, timeout: 45000 });
      bars = d.dates.map((t, i) => ({ t: Date.parse(t), o: d.open[i], h: d.high[i], l: d.low[i], c: d.close[i], v: d.volume[i] }));
      D.note = 'Weekly bars.';
    } else if (V.range === 'All') {
      const d = await api.get(`/api/daily-bars/${enc}`, { ttl: 3600000, timeout: 60000 });
      bars = d.dates.map((t, i) => ({ t: Date.parse(t), o: d.open[i], h: d.high[i], l: d.low[i], c: d.close[i], v: d.volume[i] }));
      D.note = 'Every daily bar since the listing.';
    } else {
      const t = await tickerData();
      const ps = (t.technicals || {}).price_series || {};
      bars = (ps.dates || []).map((x, i) => ({ t: Date.parse(x), o: ps.open[i], h: ps.high[i], l: ps.low[i], c: ps.close[i], v: ps.volume[i] }));
      D.note = 'Daily bars, split-adjusted.';
    }
    bars = bars.filter((b) => isNum(b.c) && isNum(b.t) && b.c > 0).map((b) => ({ t: b.t, o: isNum(b.o) ? b.o : b.c, h: isNum(b.h) ? b.h : b.c, l: isNum(b.l) ? b.l : b.c, c: b.c, v: b.v || 0 }));
    if (bars.length < 5) throw new api.ApiError('notfound', 404, 'Not enough bars to draw.');
    if (D.sym !== sym) return;
    D.bars = bars;
  } catch (e) { if (D.sym === sym) D.barsErr = e; }
  paintChart();
}
async function tickerData() {
  if (!D.tPromise) D.tPromise = api.get(`/api/ticker/${encodeURIComponent(D.sym)}?max_expiries=4&macro=true`, { ttl: 120000, timeout: 60000 }).then((t) => { D.t = t; return t; });
  return D.tPromise;
}

function windowBars() {
  const iv = INTERVALS.find((x) => x.key === V.interval);
  if (iv.intraday) { const last = D.bars[D.bars.length - 1].t, cut = last - iv.period * 86400000; return Math.max(10, D.bars.filter((b) => b.t >= cut).length); }
  const r = RANGES[V.interval === 'weekly' ? 'weekly' : 'daily'][V.range];
  return Number.isFinite(r) ? r : D.bars.length;
}
function levels() {
  const t = D.t || {}, te = t.technicals || {}, g = t.gex || {};
  return { fib: te.fibonacci, sr: te.support_resistance, gex: g.error ? null : { call_wall: ((g.levels || {}).call_wall || {}).strike, put_wall: ((g.levels || {}).put_wall || {}).strike, flip: (g.regime || {}).flip_point } };
}
function events() {
  const eh = ((D.t || {}).company || {}).earnings_history || {};
  return [...(eh.quarters || []).map((q) => ({ t: Date.parse(q.date), kind: 'E', label: `Earnings ${q.date}: EPS ${num(q.eps_reported)} against ${num(q.eps_estimate)}` })),
    ...(eh.upcoming || []).map((q) => ({ t: Date.parse(q.date), kind: 'E', label: `Next report ${q.date}` }))].filter((e) => isNum(e.t));
}

/* ---------------- page ---------------- */
function toolbar() {
  const daily = !INTERVALS.find((x) => x.key === V.interval).intraday;
  return html`<div class="ctools" role="toolbar" aria-label="Chart settings">
    <label class="select"><span class="t-label">Bars</span><select data-v2-ch-iv>${INTERVALS.map((x) => html`<option value="${x.key}" ${x.key === V.interval ? 'selected' : ''}>${x.label}</option>`)}</select></label>
    ${daily ? html`<div class="seg" role="group" aria-label="Range">${Object.keys(RANGES.daily).map((r) => html`<button type="button" data-v2-ch-range="${r}" aria-pressed="${V.range === r}">${r}</button>`)}</div>`
    : html`<div class="seg" role="group" aria-label="Session">${[['regular', 'Regular'], ['extended', 'Extended']].map(([k, l]) => html`<button type="button" data-v2-ch-session="${k}" aria-pressed="${V.session === k}">${l}</button>`)}</div>`}
    <div class="seg" role="group" aria-label="Style">${[['candles', 'Candles'], ['line', 'Line'], ['area', 'Area']].map(([k, l]) => html`<button type="button" data-v2-ch-style="${k}" aria-pressed="${V.style === k}">${l}</button>`)}</div>
    <details class="menu"><summary class="btn btn-sm">Indicators and levels</summary><div class="menu-body">
      <p class="t-label">On the price</p>${OVERLAYS.map(([k, l]) => html`<label class="check"><input type="checkbox" data-v2-ch-ov="${k}" ${V.overlays[k] ? 'checked' : ''} ${k === 'msb' ? html`aria-describedby="ch-msb-help"` : ''}> <span>${l}</span></label>${k === 'msb' ? html`<p class="menu-help" id="ch-msb-help">Marks where a close moved beyond the latest swing high (bullish) or swing low (bearish). A swing is a bar above or below the bars on each side, counted only once they have closed.</p>
        <label class="ws-sel menu-help">Swing strength <select data-v2-ch-msbk aria-label="Market structure swing strength">${[3, 5, 10].map((k) => html`<option value="${k}" ${V.msbK === k ? 'selected' : ''}>${k} bars each side${k === 3 ? ', more breaks' : k === 10 ? ', fewer' : ''}</option>`)}</select></label>` : ''}`)}
      <p class="t-label">Panes</p>${PANES.map(([k, l]) => html`<label class="check"><input type="checkbox" data-v2-ch-pane="${k}" ${V.panes[k] ? 'checked' : ''}> <span>${l}</span></label>`)}
    </div></details>
    <span class="spacer"></span>
    <button type="button" class="icon-btn" data-v2-ch-zoom="in" aria-label="Zoom in">${icon('plus')}</button><button type="button" class="btn btn-sm" data-v2-ch-zoom="out" aria-label="Zoom out">−</button><button type="button" class="btn btn-sm" data-v2-ch-fit>Fit</button>
  </div>
  <details class="drawd" ${isPhone() && V.tool === 'select' && !D.drawOpen ? '' : 'open'}><summary class="btn btn-sm">Drawing tools</summary>
  <div class="drail" role="toolbar" aria-label="Drawing tools">${TOOLS.map(([k, l]) => html`<button type="button" class="chip" data-v2-tool="${k}" aria-pressed="${V.tool === k}">${l}</button>`)}
    <button type="button" class="textlink" data-v2-ch-undo>Undo</button><button type="button" class="textlink" data-v2-ch-del>Delete selected</button>
    ${D.confirmClear ? html`<span class="confirm" role="alert">Remove all ${D.drawings.length} drawings on ${D.sym}? <button type="button" class="btn btn-sm" data-v2-ch-clear="yes">Remove</button><button type="button" class="btn btn-sm" data-v2-ch-clear="no">Keep them</button></span>` : html`<button type="button" class="textlink" data-v2-ch-clear="ask" ${D.drawings.length ? '' : 'disabled'}>Remove all</button>`}</div></details>
  ${D.textFor ? html`<form class="cluster textform" data-v2-ch-text><label class="field field-sm"><span class="sr">Note text</span><input name="t" maxlength="120" placeholder="Note on the chart" required></label><button class="btn btn-sm btn-primary" type="submit">Place it</button><button class="btn btn-sm" type="button" data-v2-ch-textcancel>Cancel</button></form>` : ''}`;
}

function paintChart() {
  const host = $('#ch-body', mainEl); if (!host) return;
  if (D.barsErr) { if (chart) { chart.destroy(); chart = null; } draw(host, failed('The bars', D.barsErr, { retry: 'bars' })); return; }
  if (!D.bars) { if (chart) { chart.destroy(); chart = null; } draw(host, skeleton('chart', 1, 'Loading bars')); return; }
  const iv = INTERVALS.find((x) => x.key === V.interval);
  host.innerHTML = '<div class="pc-host"></div>';
  if (chart) chart.destroy();
  chart = createPriceChart(host.firstChild, {
    bars: D.bars, intraday: !!iv.intraday, msbK: V.msbK || 5, style: V.style, overlays: V.overlays, panes: V.panes, levels: levels(), events: events(),
    drawings: D.drawings, tool: V.tool, window: windowBars(), label: `${D.sym}, ${iv.label} bars`,
    height: Math.round(Math.max(380, Math.min(window.innerHeight - 260, 720))),
    onDrawings: (list) => { D.drawings = list; saveDrawings(D.sym, list); paintTools(); },
    askText: (dr, done) => { D.textFor = done; paintTools(); const i = $('[data-v2-ch-text] input', mainEl); if (i) i.focus(); },
    onEscape: () => { V.tool = 'select'; chart.set({ tool: 'select' }); paintTools(); },
  });
  const n = $('#ch-note', mainEl); if (n) n.textContent = clean(D.note || '');
  const k = $('#ch-key', mainEl);
  if (k) draw(k, html`${V.overlays.ma ? html`<span><i class="m1"></i>SMA 20</span><span><i class="m2"></i>SMA 50</span><span><i class="m3"></i>SMA 200</span>` : ''}${V.overlays.ema ? html`<span><i class="e1"></i>EMA 9</span><span><i class="e2"></i>EMA 21</span><span><i class="e3"></i>EMA 50</span>` : ''}${V.overlays.bb ? html`<span><i class="o2"></i>Bollinger 20, 2</span>` : ''}${V.overlays.events ? html`<span><b class="kE">E</b> earnings</span>` : ''}`);
}
function paintTools() { const h = $('#ch-tools', mainEl); if (h) draw(h, toolbar()); }

function paint() {
  draw(mainEl, html`${header(D.sym, D, 'chart', { compact: true })}${tabs(D.sym, 'chart', { fund: isFund(D) })}
    <section class="section chart-page" aria-label="${D.sym} chart">
      <div id="ch-tools">${toolbar()}</div>
      <div id="ch-body"></div>
      <p class="legend-line" id="ch-key" aria-label="Key"></p>
      <div class="split ch-foot"><p class="asof" id="ch-note"></p>
        <div class="cluster">${miloButton('Explain this chart', { ask: `Explain the ${D.sym} chart: the trend, support, resistance, momentum, volume and risk, and what would invalidate the read.`, context: `${D.sym} Dossier, Chart`, symbol: D.sym })}<a class="textlink" href="${CLASSIC}#/${D.sym}/chart">More chart tools in the current app ${icon('out')}</a></div></div>
      <p class="asof">Wheel or pinch to zoom, drag to move along, arrows to read each bar, plus and minus to zoom. Studies, stages, MA Trend, volume by price, backtests, pairs, the stop check and the side widgets are in the current app.</p>
    </section>`);
  paintChart();
}

export async function render(main, route) {
  live = true; mainEl = main;
  const sym = route.symbol;
  V = Object.assign(readView(), { tool: 'select' });
  // #/SYM/chart?interval=daily&range=1Y&show=ov:ma (from Milo's chart and study cards)
  const pr = route.params || {};
  if (INTERVALS.some((x) => x.key === pr.interval)) V.interval = pr.interval;
  if (RANGES.daily[pr.range] !== undefined) V.range = pr.range;
  const [kind, id] = String(pr.show || '').split(':');
  if (kind === 'ov' && id in V.overlays) V.overlays[id] = true;
  if (kind === 'pane' && id in V.panes) V.panes[id] = true;
  D = { sym, drawings: readDrawings(sym) };
  store.pushRecent(sym);
  document.title = `${sym} Chart, Optic`;
  provideContext(() => ({ view: 'chart', ticker: sym, chart: { symbol: sym, interval: V.interval, range: V.range, drawings: D.drawings.length, bars: (D.bars || []).length, market_structure_breaks: V.overlays.msb && chart ? { method: `Swing high or low with ${V.msbK || 5} bars either side, confirmed only after those bars close; a close beyond the latest unbroken swing is a break`, in_view: chart.structure().slice(-6) } : undefined }, technicals: D.t ? { bias: D.t.technicals.bias, rsi: D.t.technicals.rsi, macd: D.t.technicals.macd, support_resistance: D.t.technicals.support_resistance, moving_averages: D.t.technicals.moving_averages } : null }));
  paint(); wire(main);
  core(sym).then((c) => { if (D.sym !== sym || !live) return; Object.assign(D, { quote: c.quote, session: c.session, quoteError: c.quoteError }); const h = $('.dhead', mainEl); if (h) { const tmp = document.createElement('div'); draw(tmp, header(sym, D, 'chart', { compact: true })); h.replaceWith(tmp.firstElementChild); } });
  tickerData().then(() => { if (live && D.sym === sym && D.bars) paintChart(); }).catch(() => {});
  loadBars();
}
export function dispose() { live = false; if (chart) { chart.destroy(); chart = null; } }
export const retry = { bars: () => loadBars() };

function wire(main) {
  main.addEventListener('change', (e) => {
    const el = e.target;
    if (el.matches('[data-v2-ch-iv]')) { V.interval = el.value; if (V.interval === 'weekly' && !RANGES.weekly[V.range]) V.range = '1Y'; paintTools(); loadBars(); return; }
    if (el.matches('[data-v2-ch-msbk]')) { V.msbK = Number(el.value) || 5; saveView(); paintChart(); return; }
    if (el.matches('[data-v2-ch-ov]')) { V.overlays[el.dataset.v2ChOv] = el.checked; saveView(); if (chart) chart.set({ overlays: V.overlays }); return; }
    if (el.matches('[data-v2-ch-pane]')) { V.panes[el.dataset.v2ChPane] = el.checked; saveView(); paintChart(); }
  });
  main.addEventListener('click', (e) => {
    const t = (s) => e.target.closest(s);
    let b;
    if ((b = t('[data-v2-ch-range]'))) { const was = V.range; V.range = b.dataset.v2ChRange; saveView(); paintTools(); if (V.range === 'All' || was === 'All') loadBars(); else paintChart(); return; }
    if ((b = t('[data-v2-ch-session]'))) { V.session = b.dataset.v2ChSession; saveView(); paintTools(); loadBars(); return; }
    if ((b = t('[data-v2-ch-style]'))) { V.style = b.dataset.v2ChStyle; saveView(); paintTools(); if (chart) chart.set({ style: V.style }); return; }
    if ((b = t('[data-v2-ch-zoom]'))) { if (chart) chart.zoom(b.dataset.v2ChZoom === 'in' ? 0.75 : 1.33); return; }
    if (t('[data-v2-ch-fit]')) { if (chart) chart.fit(); return; }
    if (e.target.closest('.drawd > summary')) { D.drawOpen = !e.target.closest('details').open; return; }
    if ((b = t('[data-v2-tool]'))) { V.tool = b.dataset.v2Tool; paintTools(); if (chart) { chart.set({ tool: V.tool }); } if (V.tool !== 'select') toast(`${TOOLS.find((x) => x[0] === V.tool)[1]}: click the chart to place it. Escape cancels.`); return; }
    if (t('[data-v2-ch-undo]')) { if (chart) chart.undo(); return; }
    if (t('[data-v2-ch-del]')) { if (chart) chart.deleteSelected(); return; }
    if ((b = t('[data-v2-ch-clear]'))) { const v = b.dataset.v2ChClear; if (v === 'ask') { D.confirmClear = true; paintTools(); const k = $('[data-v2-ch-clear="no"]', mainEl); if (k) k.focus(); } else { D.confirmClear = false; if (v === 'yes' && chart) chart.clearDrawings(); paintTools(); } return; }
    if (t('[data-v2-ch-textcancel]')) { D.textFor = null; paintTools(); }
  });
  main.addEventListener('submit', (e) => {
    const f = e.target.closest('[data-v2-ch-text]'); if (!f) return;
    e.preventDefault();
    const done = D.textFor; D.textFor = null; done(String(f.t.value || '').trim()); paintTools();
    V.tool = 'select'; if (chart) { chart.set({ tool: 'select' }); chart.focus(); } paintTools();
  });
}
void $$; void openMilo;
