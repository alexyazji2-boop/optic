// Dossier, Chart. The full-height price chart: bar size and range, candles,
// line or area, averages, Bollinger bands, Fibonacci, support and resistance,
// dealer gamma levels, earnings markers, volume, RSI and MACD, and drawings.
//
// Bars: daily from /api/ticker (two years) or /api/daily-bars (All), weekly
// from /api/weekly-bars, intraday from /api/intraday. Like the classic app the
// page opens on hourly bars. Drawings are kept per symbol in the classic key,
// so a line drawn here shows there and the other way round. The view choices
// are a setting of this browser (optic.v2.chart.v1). The side widgets, from the
// rail beside the plot, are in chart-widgets.js. The classic chart's chrome is in
// chart-chrome.js: colours (optic.chart.colors.v1) and the legend's open or folded
// state (optic.chart.legend.v1) in the classic keys, and full screen; the legend
// and the navigator under the plot are drawn by ui/pricechart.js.
import { $, $$, html, render as draw, isPhone, announce, reducedMotion } from '../core/dom.js';
import { CLASSIC } from '../core/classic.js';
import * as api from '../core/api.js';
import * as store from '../core/store.js';
import { holds } from '../core/device.js';
import { marketSession } from '../core/status.js';
import { num, clean, isNum } from '../core/format.js';
import { skeleton, failed } from '../ui/states.js';
import { icon } from '../ui/icons.js';
import { chartReadCard } from '../ui/chartread.js';
import { button as miloButton, provideContext, openMilo } from '../ui/milo.js';
import { toast } from '../ui/toast.js';
import { createPriceChart } from '../ui/pricechart.js';
import { core, header, tabs, isFund } from './dossier-frame.js';
import * as W from './chart-widgets.js';
import * as ST from './chart-studies.js';
import * as C from './chart-chrome.js';

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
const TOOL_ICON = { select: 'cursor', hline: 'hline', vline: 'vline', trend: 'trend', ray: 'ray', rect: 'rect', fibdraw: 'fib', text: 'text' };
const TOOL_GROUP_STARTS = new Set(['hline', 'rect', 'text']);   // pointer | lines | shapes | notes
// The classic studies (C11) joined these on 2026-10-19, under the classic names; chart-studies.js has their data.
const OVERLAYS = [['ma', 'MA 20, 50, 200'], ['ema', 'EMA 9, 21, 50'], ['cloud921', 'EMA 9 / 21 cloud'], ['cloud2150', 'EMA 21 / 50 cloud'], ['bb', 'Bollinger 20, 2'], ['keltner', 'Keltner channel'], ['donchian', 'Donchian channel'], ['sec', 'Regression channel'], ['vwap', 'Anchored VWAP'],
  ['fib', 'Fibonacci'], ['sr', 'Support and resistance'], ['gex', 'Dealer gamma levels'], ['zones', 'Supply and demand'], ['accum', 'Accumulation zones'], ['trends', 'Auto trend lines'], ['vbp', 'Volume by price'],
  ['msb', 'Market structure breaks'], ['events', 'Earnings'], ['ins', 'Insider trades'], ['sessions', 'Session dividers'],
  ['stages', 'Weinstein stages'], ['matrend', 'MA Trend Identifier']];
// where each group of the Indicators menu starts
const OV_GROUP = { ma: 'Averages and bands', fib: 'Levels', msb: 'Structure and events', stages: 'Candle colours' };
const PANES = [['volume', 'Volume'], ['rsi', 'RSI 14'], ['macd', 'MACD 12, 26, 9'], ['tso', 'Trend Strength Oscillator']];

let D = {}, V = {}, live = true, mainEl = null, chart = null, unsub = null, phoneMq = null;

function readView() {
  const d = { interval: '60', range: '6M', style: 'candles', session: 'regular', read: false, dock: [], overlays: { ma: true, ema: false, bb: false, fib: false, sr: false, gex: false, msb: false, events: true, ins: true, cloud921: false, cloud2150: false, keltner: false, donchian: false, sec: false, vwap: false, zones: false, accum: false, trends: false, vbp: false, sessions: false, stages: false, matrend: false }, panes: { volume: true, rsi: false, macd: false, tso: false }, msbK: 5 };
  try { const s = JSON.parse(localStorage.getItem(VIEW_KEY) || 'null'); if (s && typeof s === 'object') { Object.assign(d, s, { overlays: Object.assign(d.overlays, s.overlays || {}), panes: Object.assign(d.panes, s.panes || {}) }); } } catch (e) { /* private */ }
  d.interval = '60'; // the Chart page opens on hourly bars, as in the classic app
  d.dock = Array.isArray(d.dock) ? d.dock.filter((id, i, a) => W.IDS.includes(id) && a.indexOf(id) === i) : [];
  return d;
}
function saveView() { try { localStorage.setItem(VIEW_KEY, JSON.stringify({ range: V.range, style: V.style, session: V.session, read: V.read, dock: V.dock, overlays: V.overlays, panes: V.panes, msbK: V.msbK })); } catch (e) { /* private */ } }

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
  // seq: a slower answer for the bar size or range chosen before must not replace the one chosen after
  const sym = D.sym, enc = encodeURIComponent(sym), iv = INTERVALS.find((x) => x.key === V.interval), seq = (D.barSeq = (D.barSeq || 0) + 1);
  const current = () => D.sym === sym && D.barSeq === seq;
  D.bars = null; D.barsErr = null; paintChart();
  let note = '';
  try {
    let bars;
    if (iv.intraday) {
      const d = await api.get(`/api/intraday/${enc}?range=${iv.key}&window=${iv.history}&session=${V.session}`, { ttl: 60000, timeout: 45000 });
      if (!d.available) throw new api.ApiError('notfound', 404, clean(d.reason || 'No intraday bars right now.'));
      bars = d.times.map((t, i) => ({ t: Date.parse(t), o: d.opens[i], h: d.highs[i], l: d.lows[i], c: d.closes[i], v: d.volumes[i] }));
      note = d.session_note;
    } else if (V.interval === 'weekly') {
      const d = await api.get(`/api/weekly-bars/${enc}?span=${V.range === 'All' ? 'max' : '10y'}`, { ttl: 3600000, timeout: 45000 });
      bars = d.dates.map((t, i) => ({ t: Date.parse(t), o: d.open[i], h: d.high[i], l: d.low[i], c: d.close[i], v: d.volume[i] }));
      note = 'Weekly bars.';
    } else if (V.range === 'All') {
      const d = await api.get(`/api/daily-bars/${enc}`, { ttl: 3600000, timeout: 60000 });
      bars = d.dates.map((t, i) => ({ t: Date.parse(t), o: d.open[i], h: d.high[i], l: d.low[i], c: d.close[i], v: d.volume[i] }));
      note = 'Every daily bar since the listing.';
    } else {
      const t = await tickerData();
      const ps = (t.technicals || {}).price_series || {};
      bars = (ps.dates || []).map((x, i) => ({ t: Date.parse(x), o: ps.open[i], h: ps.high[i], l: ps.low[i], c: ps.close[i], v: ps.volume[i] }));
      note = 'Daily bars, split-adjusted.';
    }
    bars = bars.filter((b) => isNum(b.c) && isNum(b.t) && b.c > 0).map((b) => ({ t: b.t, o: isNum(b.o) ? b.o : b.c, h: isNum(b.h) ? b.h : b.c, l: isNum(b.l) ? b.l : b.c, c: b.c, v: b.v || 0 }));
    if (bars.length < 5) throw new api.ApiError('notfound', 404, 'Not enough bars to draw.');
    if (!current()) return;
    D.bars = bars; D.note = note;
  } catch (e) { if (!current()) return; D.barsErr = e; }
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
    <label class="select ch-iv"><span class="sr">Bar size</span><select data-v2-ch-iv title="Bar size">${INTERVALS.map((x) => html`<option value="${x.key}" ${x.key === V.interval ? 'selected' : ''}>${x.label}</option>`)}</select></label>
    ${daily ? html`<div class="seg" role="group" aria-label="Range">${Object.keys(RANGES.daily).map((r) => html`<button type="button" data-v2-ch-range="${r}" aria-pressed="${V.range === r}">${r}</button>`)}</div>`
    : html`<div class="seg" role="group" aria-label="Session">${[['regular', 'Regular'], ['extended', 'Extended']].map(([k, l]) => html`<button type="button" data-v2-ch-session="${k}" aria-pressed="${V.session === k}">${l}</button>`)}</div>`}
    <div class="seg seg-ic" role="group" aria-label="Style">${[['candles', 'Candles', 'candles'], ['line', 'Line', 'lineChart'], ['area', 'Area', 'area']].map(([k, l, ic]) => html`<button type="button" data-v2-ch-style="${k}" aria-pressed="${V.style === k}" aria-label="${l}" title="${l}">${icon(ic)}</button>`)}</div>
    <details class="menu"><summary class="btn btn-sm" aria-label="Indicators and levels">${icon('layers')}<span class="ch-lbl">Indicators</span></summary><div class="menu-body ch-imenu">
      ${OVERLAYS.map(([k, l]) => html`${OV_GROUP[k] ? html`<p class="t-label">${OV_GROUP[k]}</p>` : ''}<label class="check"><input type="checkbox" data-v2-ch-ov="${k}" ${V.overlays[k] ? 'checked' : ''} ${k === 'msb' ? html`aria-describedby="ch-msb-help"` : ST.HELP[k] ? html`aria-describedby="ch-help-${k}"` : ''}> <span>${l}</span></label>${ST.HELP[k] ? html`<p class="menu-help" id="ch-help-${k}">${ST.HELP[k]}</p>` : ''}${k === 'msb' ? html`<p class="menu-help" id="ch-msb-help">Marks where a close moved beyond the latest swing high (bullish) or swing low (bearish). A swing is a bar above or below the bars on each side. Its level is drawn back to where it formed, but it only became known once those later bars had closed: the line is dotted before then, with a tick where it became known, and only a close after that counts as a break.</p>
        <label class="ws-sel menu-help">Swing strength <select data-v2-ch-msbk aria-label="Market structure swing strength">${[3, 5, 10].map((k) => html`<option value="${k}" ${V.msbK === k ? 'selected' : ''}>${k} bars each side${k === 3 ? ', more breaks' : k === 10 ? ', fewer' : ''}</option>`)}</select></label>` : ''}`)}
      <p class="t-label">Panes</p>${PANES.map(([k, l]) => html`<label class="check"><input type="checkbox" data-v2-ch-pane="${k}" ${V.panes[k] ? 'checked' : ''}> <span>${l}</span></label>`)}
    </div></details>
    <details class="menu ch-colours"><summary class="btn btn-sm" aria-label="Chart colours" title="Colour of the candles and the line">${icon('palette')}<span class="ch-lbl">Colours</span></summary><div class="menu-body ch-cmenu" id="ch-cmenu"></div></details>
    <button type="button" class="btn btn-sm" data-v2-ch-read aria-pressed="${!!V.read}" aria-controls="ch-read">${icon('trend')}<span class="ch-lbl">Chart read</span></button>
    <button type="button" class="btn btn-sm ch-drawtoggle" data-v2-ch-drawtoggle aria-expanded="${drawOpen()}" aria-controls="ch-draw">${icon('pencil')}<span class="ch-lbl">Draw</span></button>
    <span class="spacer"></span>
    <div class="ch-zoom" role="group" aria-label="Zoom"><button type="button" class="ch-tool" data-v2-ch-zoom="out" aria-label="Zoom out" title="Zoom out">${icon('minus')}</button><button type="button" class="ch-tool" data-v2-ch-zoom="in" aria-label="Zoom in" title="Zoom in">${icon('plus')}</button><button type="button" class="ch-tool" data-v2-ch-fit aria-label="Fit the whole range" title="Fit the whole range">${icon('fit')}</button>${C.maxButton()}</div>
  </div>
  ${D.confirmClear ? html`<p class="confirm ch-confirm" role="alert">Remove all ${D.drawings.length} drawings on ${D.sym}? <button type="button" class="btn btn-sm" data-v2-ch-clear="yes">Remove</button><button type="button" class="btn btn-sm" data-v2-ch-clear="no">Keep them</button></p>` : ''}
  ${D.textFor ? html`<form class="cluster textform" data-v2-ch-text><label class="field field-sm"><span class="sr">Note text</span><input name="t" maxlength="120" placeholder="Note on the chart" required></label><button class="btn btn-sm btn-primary" type="submit">Place it</button><button class="btn btn-sm" type="button" data-v2-ch-textcancel>Cancel</button></form>` : ''}`;
}

// The drawing tools: a column of named icon buttons beside the plot, grouped as pointer, lines, shapes
// and notes; on a phone a row above it, shown when Draw is on (or while a tool other than select is in use).
const drawOpen = () => !isPhone() || !!D.drawOpen || V.tool !== 'select';
function drawbar() {
  return html`<div class="ch-draw" role="toolbar" aria-label="Drawing tools" aria-orientation="${isPhone() ? 'horizontal' : 'vertical'}" ${drawOpen() ? '' : 'hidden'}>
    ${TOOLS.map(([k, l]) => html`${TOOL_GROUP_STARTS.has(k) ? html`<span class="ch-sep" aria-hidden="true"></span>` : ''}<button type="button" class="ch-tool" data-v2-tool="${k}" aria-pressed="${V.tool === k}" aria-label="${l}" title="${l}">${icon(TOOL_ICON[k])}</button>`)}
    <span class="ch-sep" aria-hidden="true"></span>
    <button type="button" class="ch-tool" data-v2-ch-undo aria-label="Undo the last drawing change" title="Undo">${icon('undo')}</button>
    <button type="button" class="ch-tool" data-v2-ch-del aria-label="Delete the selected drawing" title="Delete selected">${icon('trash')}</button>
    <button type="button" class="ch-tool" data-v2-ch-clear="ask" aria-label="Remove all drawings on ${D.sym}" title="Remove all" ${D.drawings.length ? '' : 'disabled'}>${icon('clear')}</button>
  </div>`;
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
    drawings: D.drawings, tool: V.tool, window: windowBars(), label: `${D.sym}, ${iv.label} bars`, ...extras(), ...studies(),
    height: plotHeight(host),
    onDrawings: (list) => { D.drawings = list; saveDrawings(D.sym, list); paintTools(); },
    askText: (dr, done) => { D.textFor = done; paintTools(); const i = $('[data-v2-ch-text] input', mainEl); if (i) i.focus(); },
    onEscape: () => { V.tool = 'select'; chart.set({ tool: 'select' }); paintTools(); },
    // the legend names what the Indicators menu lists, in its order; folded or open is kept in the classic key
    names: LEGEND_NAMES, legendOpen: V.legend, navigator: true, onLegend: (open) => { V.legend = open; C.saveLegend(open); }, onRemove: removeOverlay, navH: navH(),
  });
  // the reading line above the plot is one line or two: measured now it is drawn, the plot takes what is left
  refit();
  syncHeight();
  const n = $('#ch-note', mainEl); if (n) n.textContent = clean(D.note || '');
  const sn = $('#ch-snote', mainEl); if (sn) sn.textContent = ST.notes(V.overlays).join(' ');
}
// The plot fills the window under the toolbar, less the reading line above it (40 until it is drawn) and the
// navigator under it; in full screen all of what is left, less the page's padding under the navigator.
const navH = () => (isPhone() ? 44 : 40);
function plotHeight(host) {
  const svg = $('.pc-svg', host), nav = navH() + 6;
  const top = (svg ? svg.getBoundingClientRect().top : host.getBoundingClientRect().top + 40) + window.scrollY;
  const room = Math.round(window.innerHeight - top - nav - 8);
  if (C.isMax()) return Math.max(isPhone() ? 240 : 320, room - 14);
  return isPhone() ? Math.round(Math.max(280, Math.min(room, window.innerHeight * 0.62 - nav))) : Math.round(Math.max(340, Math.min(room, 900)));
}
// the side widgets are no taller than the chart beside them (--ch-h, in pages.css)
function syncHeight() { const host = $('#ch-body', mainEl), stage = $('.ch-stage', mainEl); if (host && stage) stage.style.setProperty('--ch-h', `${host.offsetHeight}px`); }
// a new height for the chart it has, keeping the bars in view (full screen in and out, a window resized in it)
let fitT = 0;
function refit() {
  if (fitT) return;
  fitT = requestAnimationFrame(() => {
    fitT = 0;
    const host = $('#ch-body', mainEl); if (!live || !chart || !host) return;
    const h = plotHeight(host);
    if (h !== chart.height() || navH() !== chart.navH()) chart.set({ height: h, navH: navH() });
    requestAnimationFrame(syncHeight);
  });
}
const LEGEND_NAMES = Object.fromEntries([...OVERLAYS, ['volume', 'Volume']]);
// the legend's cross: the overlay (or the volume pane) off, as unticking it in Indicators does
function removeOverlay(k) {
  if (k === 'volume') V.panes.volume = false; else V.overlays[k] = false;
  saveView(); paintTools(); if (chart) chart.set({ overlays: V.overlays, panes: V.panes });
  if (k === 'sr') repaintWidget('levels'); if (k === 'ins') repaintWidget('insiders');
  announce(`${LEGEND_NAMES[k]} taken off the chart.`);
}

/* ---------------- colours and full screen (chart-chrome.js) ---------------- */
const chartBg = () => C.surface($('#ch-body', mainEl) || mainEl);
function applyColours() { C.applyColours($('.chart-page', mainEl), V.colours); }
// the menu's rows, drawn when it opens and again after a choice (pressed states, Default, Reset), the focus
// kept on the control that had it
function paintColours(focus) {
  const m = $('#ch-cmenu', mainEl); if (!m) return;
  draw(m, C.colourRows(V.colours, chartBg()));
  const f = focus && $(focus, m); if (f) f.focus();
}
function pickColour(slot, value, focus) {
  V.colours = value === null ? C.resetColours() : C.setColour(slot, value);
  // the rows are drawn again once this click has finished: drawn at once, the pressed button would be gone from
  // the page by the time the click reaches the rule that closes a menu on a click outside it
  applyColours(); setTimeout(() => { if (live) paintColours(focus); }, 0);
}
// a menu that would run past the right of the window opens to the left of its button instead
function placeMenu(d) {
  const m = d.querySelector('.menu-body'); if (!m || isPhone()) return;
  m.style.left = ''; m.style.right = '';
  if (m.getBoundingClientRect().right > document.documentElement.clientWidth - 8) { m.style.left = 'auto'; m.style.right = '0'; }
}
function paintMax() {
  const b = $('[data-v2-ch-max]', mainEl); if (!b) return;
  const on = C.isMax();
  b.setAttribute('aria-pressed', String(on)); b.title = C.maxTitle(on); draw(b, icon(on ? 'shrink' : 'expand'));
}
function toggleMax(on) {
  C.setMax(on);
  if (on) window.scrollTo({ top: 0, behavior: 'instant' });
  paintMax(); refit();
  announce(on ? 'Full screen. Escape or the full screen button goes back.' : 'Out of full screen.');
}
// leaving by a way the page did not choose (Escape or the browser's own exit in its full screen) takes the class too
function onFullChange() { if (!C.nativeFull() && C.isMax()) { C.setMax(false, false); paintMax(); } refit(); }
// Escape leaves full screen, unless it is already cancelling something: a drawing, a note, a menu or a dialog.
// Seen on the way down (capture), before the chart's own Escape puts the tool back to select.
function onMaxKey(e) {
  if (e.key !== 'Escape' || !C.isMax() || C.nativeFull()) return;
  if (V.tool !== 'select' || D.textFor || D.confirmClear || document.querySelector('details.menu[open]')) return;
  if ([...document.querySelectorAll('[aria-modal="true"]')].some((el) => el.getClientRects().length)) return;
  toggleMax(false);
  // after the chart's own Escape, which draws the toolbar again
  setTimeout(() => { const b = $('[data-v2-ch-max]', mainEl); if (b) b.focus(); }, 0);
}
const onResize = () => { if (C.isMax()) refit(); };
// the classic app, or this page in another tab, changed the colours or the legend
function onStorage(e) {
  if (!live) return;
  if (e.key === C.COLOURS_KEY || e.key === null) { V.colours = C.readColours(); applyColours(); paintColours(); }
  if (e.key === C.LEGEND_KEY || e.key === null) { V.legend = C.legendOpen(); if (chart) chart.set({ legendOpen: V.legend }); }
}
function paintTools() { const h = $('#ch-tools', mainEl); if (h) draw(h, toolbar()); const d = $('#ch-draw', mainEl); if (d) draw(d, drawbar()); }

function paint() {
  draw(mainEl, html`${header(D.sym, D, 'chart', { bar: true })}${tabs(D.sym, 'chart', { fund: isFund(D) })}
    <section class="section chart-page" aria-label="${D.sym} chart">
      <div id="ch-tools">${toolbar()}</div>
      <div class="ch-stage"><div id="ch-draw">${drawbar()}</div><div id="ch-body"></div>
        <div class="ch-wrail" id="ch-wrail">${W.rail(shown(), isPhone())}</div>
        <div class="ch-side" id="ch-side" ${V.read || shown().length ? '' : 'hidden'}><aside class="ch-read" id="ch-read" aria-labelledby="cr-h" ${V.read ? '' : 'hidden'}></aside></div></div>
      <div class="split ch-foot"><div><p class="asof" id="ch-note"></p><p class="asof ch-snote" id="ch-snote" aria-live="polite"></p></div>
        <div class="cluster">${miloButton('Explain this chart', { ask: `Explain the ${D.sym} chart: the trend, support, resistance, momentum, volume and risk, and what would invalidate the read.`, context: `${D.sym} Dossier, Chart`, symbol: D.sym })}<a class="textlink" href="${CLASSIC}#/${D.sym}/chart">More chart tools in the current app ${icon('out')}</a></div></div>
      <p class="asof">Wheel or pinch to zoom, drag the chart or the strip under it to move along, arrows to read each bar, plus and minus to zoom. The other drawing tools, and the indicator panes the current app adds (ADX, Stochastic, OBV, MFI, relative strength), are in the current app.</p>
    </section>`);
  applyColours(); paintChart(); paintRead(); syncSide();
}
// The chart read (ui/chartread.js), from the daily technicals this page already loads.
function paintRead() {
  const h = $('#ch-read', mainEl); if (!h) return;
  h.hidden = !V.read;
  const side = $('#ch-side', mainEl); if (side) side.hidden = !V.read && !shown().length;
  if (V.read) draw(h, chartReadCard(D.sym, D.t, D.t ? undefined : D.tErr ? 'failed' : 'loading'));
}

/* ---------------- the side widgets (chart-widgets.js) ---------------- */
// Wide: every widget the reader opened, in the rail's order, between the plot and the rail. A phone: the
// last one opened, under the chart.
const shown = () => (isPhone() ? V.dock.slice(-1) : V.dock.slice());
function syncSide() {
  const side = $('#ch-side', mainEl); if (!side) return;
  W.flush(side);
  const want = W.IDS.filter((id) => shown().includes(id)), added = [];
  $$('.chw', side).forEach((el) => { if (!want.includes(el.dataset.chwPanel)) el.remove(); });
  let prev = $('#ch-read', side);
  want.forEach((id) => {
    let el = $(`#chw-${id}`, side);
    if (!el) { const tmp = document.createElement('div'); draw(tmp, W.panel(id)); el = tmp.firstElementChild; added.push(id); }
    if (prev.nextElementSibling !== el) prev.after(el);
    prev = el;
  });
  side.hidden = !V.read && !want.length;
  added.forEach((id) => W.need(id));
}
// Pressed states in place, so the button that was pressed keeps the focus.
function paintRail() { const s = shown(); $$('[data-chw]', mainEl).forEach((b) => b.setAttribute('aria-pressed', String(s.includes(b.dataset.chw)))); }
function toggleWidget(id) {
  const on = shown().includes(id);
  V.dock = on ? V.dock.filter((x) => x !== id) : isPhone() ? [id] : [...V.dock.filter((x) => x !== id), id];
  saveView(); paintRail(); syncSide(); paintExtras();
  if (on) { announce(`${W.label(id)} closed.`); return; }
  const el = $(`#chw-${id}`, mainEl);
  if (el) el.scrollIntoView({ block: 'nearest', behavior: reducedMotion() ? 'auto' : 'smooth' });
  announce(`${W.label(id)} opened${isPhone() ? ', under the chart' : ''}.`);
}
// A widget's answer arrived: redraw its body after the event that caused it has settled (a change from Tab
// fires before the focus moves), keeping the control that had the focus and any details left open.
const pending = new Set(); let pendingT = 0;
function repaintWidget(id) { pending.add(id); if (!pendingT) pendingT = setTimeout(flushRepaints, 0); }
function flushRepaints() {
  pendingT = 0;
  const ids = [...pending]; pending.clear();
  if (!live) return;
  ids.forEach((id) => {
    const el = $(`#chw-${id}-b`, mainEl); if (!el) return;
    const a = document.activeElement, attr = a && el.contains(a) ? [...a.attributes].find((x) => x.name.startsWith('data-chw')) : null;
    const sel = attr ? `[${attr.name}="${CSS.escape(attr.value)}"]` : null;
    const opened = $$('details[open] > summary', el).map((x) => x.textContent);
    if (id === 'notes') W.flush(el);
    draw(el, W.body(id));
    $$('details > summary', el).forEach((x) => { if (opened.includes(x.textContent)) x.parentElement.open = true; });
    const n = sel && $(sel, el); if (n) n.focus({ preventScroll: true });
  });
}
// The backtest's fills and the stop check's lines, placed on the bars this chart is drawing.
// Insider trades too (the Insider trades overlay, on unless turned off): a trade on a day with no session
// goes to the last bar before it, as the classic chart snaps them.
function extras() {
  const { marks, lines } = W.onChart(shown()), ins = W.insiderMarks(D.t);
  if (!D.bars || (!marks.length && !ins.length)) return { marks: [], lines, insiders: [] };
  const intraday = !!INTERVALS.find((x) => x.key === V.interval).intraday, weekly = V.interval === 'weekly';
  if (D.keysOf !== D.bars) { D.keysOf = D.bars; D.keys = D.bars.map((b) => W.barKey(b.t, intraday)); }
  const place = (list, within) => list.map((m) => Object.assign({}, m, { t: W.barTime(D.bars, D.keys, m.at, { intraday, weekly, within }) })).filter((m) => m.t !== null);
  return { marks: place(marks, 0), lines, insiders: place(ins, 4) };
}
function paintExtras() { if (chart) chart.set(extras()); }
// The studies' data (chart-studies.js), and a line under the chart for each one that is on and has nothing to
// draw yet, or its reading.
function studies() { ST.need(V.overlays); return ST.data(V.overlays); }
function paintStudies() { if (chart) chart.set(Object.assign({ overlays: V.overlays }, ST.data(V.overlays))); const n = $('#ch-snote', mainEl); if (n) n.textContent = ST.notes(V.overlays).join(' '); }
const phase = () => ((D.session || {}).prices || {}).phase || ((D.session || {}).session || {}).phase || (marketSession() || {}).phase || null;

export async function render(main, route) {
  live = true; mainEl = main;
  const sym = route.symbol;
  V = Object.assign(readView(), { tool: 'select', colours: C.readColours(), legend: C.legendOpen() });
  // #/SYM/chart?interval=daily&range=1Y&show=ov:ma (from Milo's chart and study cards)
  const pr = route.params || {};
  if (INTERVALS.some((x) => x.key === pr.interval)) V.interval = pr.interval;
  if (RANGES.daily[pr.range] !== undefined) V.range = pr.range;
  const [kind, id] = String(pr.show || '').split(':');
  if (kind === 'ov' && id in V.overlays) V.overlays[id] = true;
  if (kind === 'pane' && id in V.panes) V.panes[id] = true;
  D = { sym, drawings: readDrawings(sym) };
  W.bind({ sym: () => D.sym, t: () => D.t, tErr: () => D.tErr, phase, repaint: repaintWidget, chart: paintExtras,
    overlayOn: (k) => !!V.overlays[k], overlay: (k, on) => { V.overlays[k] = on; saveView(); paintTools(); if (chart) chart.set({ overlays: V.overlays }); } });
  W.reset();
  ST.bind({ sym: () => D.sym, bars: () => D.bars, iv: () => INTERVALS.find((x) => x.key === V.interval), range: () => V.range, session: () => V.session, weekly: () => V.interval === 'weekly',
    firstShown: () => (D.bars ? D.bars[Math.max(0, D.bars.length - windowBars())].t : null), t: () => D.t, repaint: () => { if (live) paintStudies(); } });
  ST.reset();
  if (unsub) unsub();
  unsub = store.subscribe((what) => { if (what === 'lists') repaintWidget('watchlist'); });
  if (!phoneMq) { phoneMq = matchMedia('(max-width: 860px)'); phoneMq.addEventListener('change', onPhoneChange); }
  document.addEventListener('keydown', onMaxKey, true);
  ['fullscreenchange', 'webkitfullscreenchange'].forEach((n) => document.addEventListener(n, onFullChange));
  window.addEventListener('resize', onResize); window.addEventListener('storage', onStorage);
  store.pushRecent(sym);
  document.title = `${sym} Chart, Optic`;
  provideContext(() => ({ view: 'chart', ticker: sym, chart: { symbol: sym, interval: V.interval, range: V.range, studies_on: OVERLAYS.filter(([k]) => V.overlays[k]).map(([, l]) => l).concat(PANES.filter(([k]) => V.panes[k] && k !== 'volume').map(([, l]) => l)), drawings: D.drawings.length, bars: (D.bars || []).length, market_structure_breaks: V.overlays.msb && chart ? { method: `Swing high or low with ${V.msbK || 5} bars either side. The swing forms at its own bar but is only known once the ${V.msbK || 5} bars after it have closed; a close beyond the latest known, unbroken swing is a break. Earlier breaks never change as new bars arrive.`, in_view: chart.structure().slice(-6) } : undefined }, technicals: D.t ? { bias: D.t.technicals.bias, rsi: D.t.technicals.rsi, macd: D.t.technicals.macd, support_resistance: D.t.technicals.support_resistance, moving_averages: D.t.technicals.moving_averages } : null, widgets: W.context(shown()) }));
  paint(); wire(main);
  core(sym).then((c) => { if (D.sym !== sym || !live) return; Object.assign(D, { quote: c.quote, session: c.session, quoteError: c.quoteError }); const h = $('.dhead', mainEl); if (h) { const tmp = document.createElement('div'); draw(tmp, header(sym, D, 'chart', { bar: true })); h.replaceWith(tmp.firstElementChild); } repaintWidget('stats'); });
  loadTicker(sym);
  loadBars();
}
function loadTicker(sym) {
  D.tErr = null;
  tickerData().then(() => { if (live && D.sym === sym) { if (D.bars) paintChart(); paintRead(); afterTicker(); } }).catch((e) => { if (live && D.sym === sym) { D.tErr = e || true; D.tPromise = null; paintRead(); afterTicker(); } });
}
// The widgets that read the ticker payload are drawn again, and the stop check can start once it knows the plan's stop.
function afterTicker() { shown().forEach((id) => { if (W.FROM_TICKER.includes(id)) { repaintWidget(id); W.need(id); } }); }
function onPhoneChange() {
  if (!live) return;
  const r = $('#ch-wrail', mainEl); if (r) draw(r, W.rail(shown(), isPhone()));
  syncSide(); paintExtras(); refit();
}
export function dispose() {
  live = false; W.flush(mainEl || document);
  if (C.isMax()) C.setMax(false);
  document.removeEventListener('keydown', onMaxKey, true);
  ['fullscreenchange', 'webkitfullscreenchange'].forEach((n) => document.removeEventListener(n, onFullChange));
  window.removeEventListener('resize', onResize); window.removeEventListener('storage', onStorage);
  if (unsub) { unsub(); unsub = null; }
  if (phoneMq) { phoneMq.removeEventListener('change', onPhoneChange); phoneMq = null; }
  if (chart) { chart.destroy(); chart = null; }
}
export const retry = Object.assign({ bars: () => loadBars(), ticker: () => { D.tPromise = null; D.tErr = null; afterTicker(); paintRead(); loadTicker(D.sym); } },
  Object.fromEntries(W.IDS.map((id) => [`w-${id}`, () => W.retry(id)])));

function wire(main) {
  main.addEventListener('change', (e) => {
    const el = e.target;
    if (el.closest('.chw') && W.onChange(e)) return;
    if (el.matches('[data-v2-cc-pick]')) { pickColour(el.dataset.v2CcPick, el.value, `[data-v2-cc-pick="${el.dataset.v2CcPick}"]`); return; }
    if (el.matches('[data-v2-ch-iv]')) { V.interval = el.value; if (V.interval === 'weekly' && !RANGES.weekly[V.range]) V.range = '1Y'; paintTools(); loadBars(); return; }
    if (el.matches('[data-v2-ch-msbk]')) { V.msbK = Number(el.value) || 5; saveView(); paintChart(); return; }
    if (el.matches('[data-v2-ch-ov]')) { V.overlays[el.dataset.v2ChOv] = el.checked; saveView(); ST.need(V.overlays); paintStudies(); if (el.dataset.v2ChOv === 'sr') repaintWidget('levels'); if (el.dataset.v2ChOv === 'ins') repaintWidget('insiders'); return; }
    if (el.matches('[data-v2-ch-pane]')) { V.panes[el.dataset.v2ChPane] = el.checked; saveView(); paintChart(); }
  });
  main.addEventListener('click', (e) => {
    const t = (s) => e.target.closest(s);
    let b;
    if ((b = t('[data-chw]'))) { toggleWidget(b.dataset.chw); return; }
    if ((b = t('[data-chw-close]'))) { const id = b.dataset.chwClose; toggleWidget(id); const r = $(`[data-chw="${id}"]`, mainEl); if (r) r.focus(); return; }
    if (t('.chw') && W.onClick(e)) return;
    if ((b = t('[data-v2-ch-range]'))) { const was = V.range; V.range = b.dataset.v2ChRange; saveView(); paintTools(); if (V.range === 'All' || was === 'All') loadBars(); else paintChart(); return; }
    if ((b = t('[data-v2-ch-session]'))) { V.session = b.dataset.v2ChSession; saveView(); paintTools(); loadBars(); return; }
    if ((b = t('[data-v2-ch-read]'))) { V.read = !V.read; saveView(); paintTools(); paintRead(); paintChart(); const again = $('[data-v2-ch-read]', mainEl); if (again) again.focus(); return; }
    if ((b = t('[data-v2-ch-style]'))) { V.style = b.dataset.v2ChStyle; saveView(); paintTools(); if (chart) chart.set({ style: V.style }); return; }
    if ((b = t('[data-v2-ch-zoom]'))) { if (chart) chart.zoom(b.dataset.v2ChZoom === 'in' ? 0.75 : 1.33); return; }
    if (t('[data-v2-ch-fit]')) { if (chart) chart.fit(); return; }
    if (t('[data-v2-ch-max]')) { toggleMax(!C.isMax()); return; }
    if ((b = t('[data-v2-cc]'))) { pickColour(b.dataset.v2Cc, b.dataset.v2CcV, `[data-v2-cc="${b.dataset.v2Cc}"][data-v2-cc-v="${b.dataset.v2CcV}"]`); return; }
    if ((b = t('[data-v2-cc-clear]'))) { pickColour(b.dataset.v2CcClear, '', `[data-v2-cc-pick="${b.dataset.v2CcClear}"]`); return; }
    if (t('[data-v2-cc-reset]')) { pickColour(null, null, '[data-v2-cc]'); return; }
    if (t('[data-v2-ch-drawtoggle]')) { D.drawOpen = !drawOpen(); paintTools(); const f = $('#ch-draw .ch-tool', mainEl); if (D.drawOpen && f) f.focus(); return; }
    if ((b = t('[data-v2-tool]'))) { V.tool = b.dataset.v2Tool; paintTools(); if (chart) { chart.set({ tool: V.tool }); } if (V.tool !== 'select') toast(`${TOOLS.find((x) => x[0] === V.tool)[1]}: click the chart to place it. Escape cancels.`); return; }
    if (t('[data-v2-ch-undo]')) { if (chart) chart.undo(); return; }
    if (t('[data-v2-ch-del]')) { if (chart) chart.deleteSelected(); return; }
    if ((b = t('[data-v2-ch-clear]'))) { const v = b.dataset.v2ChClear; if (v === 'ask') { D.confirmClear = true; paintTools(); const k = $('[data-v2-ch-clear="no"]', mainEl); if (k) k.focus(); } else { D.confirmClear = false; if (v === 'yes' && chart) chart.clearDrawings(); paintTools(); } return; }
    if (t('[data-v2-ch-textcancel]')) { D.textFor = null; paintTools(); }
  });
  // the widget rail is one toolbar stop: arrows move along it, Home and End jump to its ends
  main.addEventListener('keydown', (e) => {
    const b = e.target.closest && e.target.closest('.chw-btn'); if (!b) return;
    const all = $$('.chw-btn', mainEl), i = all.indexOf(b);
    const j = { ArrowDown: i + 1, ArrowRight: i + 1, ArrowUp: i - 1, ArrowLeft: i - 1, Home: 0, End: all.length - 1 }[e.key];
    if (j === undefined) return;
    e.preventDefault();
    const k = (j + all.length) % all.length;
    all.forEach((x, n) => { x.tabIndex = n === k ? 0 : -1; });
    all[k].focus();
  });
  main.addEventListener('input', (e) => {
    const p = e.target.closest && e.target.closest('[data-v2-cc-pick]'); if (!p) return;
    V.colours = Object.assign({}, V.colours, { [p.dataset.v2CcPick]: p.value }); applyColours(); C.liveRow(p, chartBg());
  });
  main.addEventListener('toggle', (e) => { if (e.target.matches && e.target.matches('details.ch-colours') && e.target.open) { paintColours(); placeMenu(e.target); } }, true);
  main.addEventListener('submit', (e) => {
    if (e.target.closest('.chw') && W.onSubmit(e)) return;
    const f = e.target.closest('[data-v2-ch-text]'); if (!f) return;
    e.preventDefault();
    const done = D.textFor; D.textFor = null; done(String(f.t.value || '').trim()); paintTools();
    V.tool = 'select'; if (chart) { chart.set({ tool: 'select' }); chart.focus(); } paintTools();
  });
}
void $$; void openMilo;
