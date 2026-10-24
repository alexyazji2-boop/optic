// The interactive price chart for the Chart page. SVG, redrawn on demand:
// a price pane (candles, line or area, with averages, bands, levels, earnings
// markers, what an open side widget asks for (`marks`, `lines`) and the reader's
// drawings), volume, and optional RSI and MACD panes.
//
// Interaction, under the precedence in docs/frontend-v2/CHART-GESTURES.md: the
// wheel, a trackpad and a pinch zoom and pan (one owner a gesture, the page or the
// chart), a drag pans, Shift-drag or the Measure button measures, the price scale
// stretches, a finger pans sideways and scrolls the page up and down, two pinch,
// and the keyboard (left and right move the crosshair, Shift pans, up and down
// stretch the price scale, + and - zoom, Home and End jump, M measures, Delete
// removes the selected drawing; undo, redo and Delete page-wide where asked).
// Asked for by the Chart page (`names`, `navigator`): the classic chart's legend
// over the plot's corner and its navigator, the whole history small under the
// plot for moving along it.
// Drawings are stored as {kind, points:[{t: epoch ms, p: price}]}, the classic
// app's format, so they line up whatever the bar size.
import { num, esc, compact, signed } from '../core/format.js';
import { makeAxis } from './timeaxis.js';
import { drawOn } from './drawon.js';
import { tsoSeries, maTrendSeries, volumeByPrice, sessionStarts, nyDate, TSO_LEVEL } from './studies.js';
import { TOOL_POINTS, channel, fibExt, pitchfork, riskReward, positionSize, measure, snap, moved, segDist } from './drawings.js';
import { icon } from './icons.js';

/* ---------- indicators (the textbook definitions the classic app uses) ---------- */
export const sma = (v, n) => v.map((_, i) => (i + 1 < n ? null : v.slice(i + 1 - n, i + 1).reduce((a, b) => a + b, 0) / n));
export function ema(v, n) { const k = 2 / (n + 1); let e = null; return v.map((x, i) => { if (i + 1 < n) return null; if (e === null) { e = v.slice(0, n).reduce((a, b) => a + b, 0) / n; return e; } e = x * k + e * (1 - k); return e; }); }
export function rsi(v, n = 14) {
  const out = v.map(() => null); let g = 0, l = 0;
  for (let i = 1; i < v.length; i++) {
    const d = v[i] - v[i - 1];
    if (i <= n) { g += Math.max(d, 0); l += Math.max(-d, 0); if (i === n) { g /= n; l /= n; out[i] = l === 0 ? 100 : 100 - 100 / (1 + g / l); } continue; }
    g = (g * (n - 1) + Math.max(d, 0)) / n; l = (l * (n - 1) + Math.max(-d, 0)) / n;
    out[i] = l === 0 ? 100 : 100 - 100 / (1 + g / l);
  }
  return out;
}
export function macd(v, f = 12, s = 26, sig = 9) {
  const a = ema(v, f), b = ema(v, s);
  const line = v.map((_, i) => (a[i] === null || b[i] === null ? null : a[i] - b[i]));
  const first = line.findIndex((x) => x !== null);
  const sigLine = line.map(() => null);
  if (first >= 0) { const e = ema(line.slice(first), sig); e.forEach((x, i) => { sigLine[first + i] = x; }); }
  return { line, signal: sigLine, hist: line.map((x, i) => (x === null || sigLine[i] === null ? null : x - sigLine[i])) };
}
export function bollinger(v, n = 20, k = 2) {
  const m = sma(v, n);
  const sd = v.map((_, i) => (i + 1 < n ? null : Math.sqrt(v.slice(i + 1 - n, i + 1).reduce((a, x) => a + (x - m[i]) ** 2, 0) / n)));
  return { mid: m, up: m.map((x, i) => (x === null ? null : x + k * sd[i])), dn: m.map((x, i) => (x === null ? null : x - k * sd[i])) };
}

let legendSeq = 0;
// The panes /api/indicators draws (C19): their names, the 0 to 100 scales kept whole, and the colour of each line
// (ADX gold with +DI green and -DI red; otherwise gold, then blue).
const SERVER_PANES = ['adx', 'stochastic', 'obv', 'mfi', 'rs'];
const PANE_NAMES = { adx: 'ADX and DI', stochastic: 'Stochastic 14', obv: 'On-balance volume', mfi: 'Money flow index', rs: 'Relative strength line' };
const BOUNDED = { stochastic: [0, 100], mfi: [0, 100], adx: [0, 50] };
const PANE_LINE = { adx: ['ip0', 'ipu', 'ipd'] };
let clipSeq = 0;   // ids for each chart's price-pane clip   // ids for each chart's legend body

/* ---------- wheel, trackpad and pinch (docs/frontend-v2/CHART-GESTURES.md; Classic's app.js:27896-28177) ----------
 * The zoom follows how far the input moved, e^(k * pixels): a 100 px mouse notch is the 1.15 it always was, and a
 * trackpad's stream of small events no longer jumps to the limit. A pinch (ctrl + wheel) zooms at Chrome's own
 * rate. A sideways stroke, or Shift + wheel, pans. And one gesture has one owner, the page or a chart, until it
 * pauses for LATCH_MS: a page scroll stays a page scroll when a chart passes under the pointer, a zoom stays a zoom
 * when the pointer drifts off, and a gesture that starts on a chart with nowhere to go (every bar shown and
 * scrolling out, or the closest zoom and scrolling in) is the page's. */
export const ZOOM_PER_PX = Math.log(1.15) / 100, PINCH_PER_PX = 0.01, LATCH_MS = 200, MIN_BARS = 10;
/** A wheel delta in pixels: Firefox's lines are 33 px, so one notch zooms alike in every browser. */
export const wheelPx = (d, mode) => (mode === 1 ? d * 33 : mode === 2 ? d * 800 : d);
/** The window `want` bars wide that keeps the bar at `abs` (fractional, over the whole series) `fx` of the way
 *  across the plot, inside the N bars. `to` is inclusive. */
export function zoomedAt(abs, fx, want, N) {
  const w = Math.max(Math.min(MIN_BARS, N), Math.min(N, Math.round(want)));
  const from = Math.max(0, Math.min(N - w, Math.round(abs - fx * (w - 1))));
  return { from, to: from + w - 1 };
}
/** Whether a wheel event has somewhere to go on a window of `span` bars out of N. */
export function wheelRoom(e, span, N) {
  if (e.ctrlKey || e.shiftKey) return true;
  const dx = wheelPx(e.deltaX, e.deltaMode), dy = wheelPx(e.deltaY, e.deltaMode);
  if (Math.abs(dx) > Math.abs(dy)) return true;
  if (dy > 0) return span < N;
  if (dy < 0) return span > Math.min(MIN_BARS, N);
  return false;
}
/** Which way a finger has gone once it has gone `slop` px: 'x', 'y', or null. A tie is the page's. */
export const touchLock = (dx, dy, slop = 8) => (Math.abs(dx) < slop && Math.abs(dy) < slop ? null : Math.abs(dx) > Math.abs(dy) ? 'x' : 'y');
const CHARTS = new Set();   // the price charts on the page, each {host, over(e), room(e), wheel(e)}
let latch = null;           // {owner: 'page' or a chart, at}
function onDocWheel(e) {
  CHARTS.forEach((c) => { if (!c.host.isConnected) CHARTS.delete(c); });
  if (!CHARTS.size) { document.removeEventListener('wheel', onDocWheel, { capture: true }); latch = null; return; }
  const now = e.timeStamp > 0 ? e.timeStamp : performance.now();
  const held = latch && now - latch.at >= 0 && now - latch.at < LATCH_MS ? latch : null;
  if (held && held.owner === 'page' && !e.ctrlKey) { held.at = now; return; }
  let c = [...CHARTS].find((x) => x.over(e)) || null;
  if (held && held.owner !== 'page' && CHARTS.has(held.owner) && c !== held.owner) c = held.owner;   // its gesture, carried on off it
  else if (!c || (!held && !c.room(e))) { latch = { owner: 'page', at: now }; return; }
  latch = { owner: c, at: now };
  e.preventDefault();   // the page must not scroll, or zoom, while the chart does
  c.wheel(e);
}
function registerChart(c) { if (!CHARTS.size) document.addEventListener('wheel', onDocWheel, { capture: true, passive: false }); CHARTS.add(c); }
function unregisterChart(c) { CHARTS.delete(c); if (!CHARTS.size) { document.removeEventListener('wheel', onDocWheel, { capture: true }); latch = null; } }
/** What a measurement between bars a and b of `bars` says, earlier first: the change between their closes, its
 *  percent, the dates (`fmt` turns a bar's time into words) and the bars between. */
export function measuredBars(bars, a, b, fmt) {
  const i = Math.min(a, b), j = Math.max(a, b), ch = bars[j].c - bars[i].c, pct = bars[i].c > 0 ? (ch / bars[i].c) * 100 : null;
  return { i, j, head: `${signed(ch, 2, '')}${pct !== null ? ` (${signed(pct)})` : ''}`, span: `${fmt(bars[i].t)} to ${fmt(bars[j].t)}`, bars: j - i, tone: ch > 0 ? 'up' : ch < 0 ? 'dn' : '' };
}
/** A page-wide key belongs to the chart only while nothing else is handling keys: the page itself, or a button or
 *  link inside `scope`. Never a field, an open menu or dialog, or another widget (amendment 7, 2026-10-21). */
export function keyIsFree(a, scope) {
  if (!a || a === document.body || a === document.documentElement) return true;
  if (!scope || !scope.contains(a)) return false;
  if (a.closest('details[open] .menu-body, [role="dialog"], [role="menu"], [role="listbox"], .drawer')) return false;
  return a.matches('button, a[href], summary') && !a.isContentEditable;
}

/**
 * The navigator's window after a drag: `w` ({from, to}, bar indexes) moved by `d` bars in `mode` ('move' the
 * whole window, 'from' or 'to' one edge), kept inside the N bars of the history and ten bars wide at least
 * (as the zoom keeps it), or the whole history when it is shorter.
 */
export function navWindow(mode, w, d, N) {
  const min = Math.min(10, N);
  let a = w.from, span = w.to - w.from + 1;
  if (mode === 'move') a = w.from + d;
  else if (mode === 'from') { a = Math.max(0, Math.min(w.to - min + 1, w.from + d)); span = w.to - a + 1; }
  else span = Math.min(N - 1, Math.max(w.from + min - 1, w.to + d)) - w.from + 1;
  span = Math.max(min, Math.min(N, Math.round(span)));
  const from = Math.max(0, Math.min(N - span, Math.round(a)));
  return { from, to: from + span - 1 };
}
/** What the legend lists: the page's names (in its menu's order) that are on, the volume pane among them. */
export const legendKeys = (names, overlays, panes) => Object.keys(names || {}).filter((k) => (k === 'volume' ? !!(panes || {}).volume : !!(overlays || {})[k]));
const FIB = [0, 0.236, 0.382, 0.5, 0.618, 0.786, 1];

/**
 * Market structure breaks. A swing high is a bar whose high is above the
 * highs of the `k` bars on each side (a swing low, below the lows). Where the
 * swing formed and when it became knowable are different bars: the level is
 * drawn back to the swing bar, but no one could know it was a swing until
 * the `k` bars after it had closed. The structure level is the latest
 * confirmed swing high (low) not yet broken; a close above it is a bullish
 * break, a close below the swing low a bearish one, and only a close after
 * confirmation counts. Each level breaks once. One forward pass over closed
 * bars, so a later bar never changes a break already recorded (the prefix
 * test in tests/test_frontend_v2_stage0.py). Returns
 * [{dir, from, known, at, price}] as bar indexes: `from` the swing bar,
 * `known` the bar whose close confirmed it, `at` the bar whose close broke it.
 */
export function marketStructure(bars, k = 3) {
  const out = [], n = bars.length;
  let hi = null, lo = null;   // the active structure levels: {i, price}
  for (let j = 0; j < n; j++) {
    const i = j - k;          // the bar that becomes a confirmed swing at j
    if (i >= k) {
      const h = bars[i].h, l = bars[i].l;
      let isHi = true, isLo = true;
      for (let m = i - k; m <= i + k; m++) {
        if (m === i) continue;
        if (!(bars[m].h < h)) isHi = false;
        if (!(bars[m].l > l)) isLo = false;
      }
      if (isHi) hi = { i, known: j, price: h };
      if (isLo) lo = { i, known: j, price: l };
    }
    const c = bars[j].c;
    if (hi && j > hi.known && c > hi.price) { out.push({ dir: 'bull', from: hi.i, known: hi.known, at: j, price: hi.price }); hi = null; }
    if (lo && j > lo.known && c < lo.price) { out.push({ dir: 'bear', from: lo.i, known: lo.known, at: j, price: lo.price }); lo = null; }
  }
  return out;
}

export function createPriceChart(host, opts) {
  const S = Object.assign({ style: 'candles', overlays: {}, panes: { volume: true, rsi: false, macd: false }, levels: {}, events: [], filings: [], marks: [], lines: [], drawings: [], tool: 'select', intraday: false }, opts);
  const bars = S.bars;
  const N = bars.length;
  const closes = bars.map((b) => b.c);
  const indicators = () => ({
    sma20: sma(closes, 20), sma50: sma(closes, 50), sma200: sma(closes, 200),
    ema9: ema(closes, 9), ema21: ema(closes, 21), ema50: ema(closes, 50),
    bb: bollinger(closes), rsi: rsi(closes), macd: macd(closes),
    msb: marketStructure(bars, S.msbK || 3),
    // the classic studies (ui/studies.js): TSO's pane, MA Trend's candle colours, session dividers on intraday bars
    tso: tsoSeries(bars.map((b) => b.h), bars.map((b) => b.l), closes), mat: maTrendSeries(bars.map((b) => b.o), closes),
    sess: S.intraday ? sessionStarts(bars) : [],
  });
  const ind = indicators();
  let from = Math.max(0, N - (S.window || 126)), to = N - 1;
  const home0 = { from, to };   // the view the chart opened on, which Reset zoom goes back to
  // a chart rebuilt on the same bars (a pane added, the chart read opened) keeps where the reader had zoomed
  if (S.view && S.view.to <= N - 1 && S.view.from >= 0 && S.view.to > S.view.from) { from = S.view.from; to = S.view.to; }
  // where a moment sits on these bars (ui/timeaxis.js): drawings and events keep their day at any bar size
  const AX = makeAxis(bars, !!S.intraday);
  let zoomedWas = null;
  let cross = -1, crossY = null, sel = -1, pending = null, W = 0, H = 0, layout = null, drag = null, raf = 0;
  // the undo history survives a rebuild on the same bars, as the view does
  const undo = (S.history && S.history.undo) || [], redo = (S.history && S.history.redo) || [];
  let touchy = false;   // the last pointer was a finger: wider targets, a larger move before a drag
  // the price scale's stretch (1 is the range the bars ask for), a measurement {a, b} in bar indexes ({key} when the
  // keyboard made it), Measure on, and the touch gesture under way
  let yZoom = S.yZoom || 1, ms = null, mOn = false, tg = null;
  const changed = () => { if (S.onChange) S.onChange({ canUndo: undo.length > 0, canRedo: redo.length > 0, selected: sel >= 0 }); };
  // A finger scrolls the page up and down over the chart and pans it sideways (pan-y); while a tool is placing
  // points or a drawing is selected, the chart takes the whole gesture.
  const syncTouch = () => { svg.style.touchAction = S.tool !== 'select' || sel >= 0 || mOn ? 'none' : 'pan-y'; };
  const CLIP = `pc-clip-${++clipSeq}`;
  // Settings' Text size zooms the page: getBoundingClientRect then reports screen pixels while style.left takes CSS
  // pixels, so the price-scale handle was placed past the chart and the page scrolled sideways under Large (39 px at
  // 1440, 67 px at 844 x 390: audit 2026-10-22). Boxes are divided by this before they position anything.
  const cssZoom = (hr) => (host.offsetWidth ? (hr || host.getBoundingClientRect()).width / host.offsetWidth : 1) || 1;

  host.classList.add('pc');
  // the legend sits over the plot's top-left corner (absolute, at its place in the flow); the navigator under it
  host.innerHTML = `<div class="pc-read" aria-live="off"></div>${S.names ? '<div class="pc-leg" role="group" aria-label="Legend"></div>' : ''}<svg class="pc-svg" tabindex="0" role="application" aria-roledescription="price chart"></svg>${S.navigator ? '<svg class="pc-nav" tabindex="0" role="slider" aria-label="Bars shown, from the whole history" aria-valuemin="1"></svg>' : ''}<div class="pc-sr sr" aria-live="polite"></div>`
    // the price scale as a handle (a strip over the axis gutter that the page's scroll never takes), the chart's own
    // buttons at the foot of the price (Measure; on touch screens, zoom out and in), and a remove button on each pane
    + `<div class="pc-scale" title="Drag up or down to stretch the price scale. Double-click to fit it to the bars."></div>`
    + `<div class="pc-ctl" role="group" aria-label="Chart tools"><button type="button" class="pc-cb pc-msb" data-pc-measure aria-pressed="false" aria-label="Measure between two bars" title="Measure: drag between two bars (or Shift-drag, or M)">${icon('ruler').s}</button>`
    + `<button type="button" class="pc-cb pc-z" data-pc-zoom="out" aria-label="Zoom out" title="Zoom out">${icon('minus').s}</button><button type="button" class="pc-cb pc-z" data-pc-zoom="in" aria-label="Zoom in" title="Zoom in">${icon('plus').s}</button></div>`
    // Reset zoom over the plot, for a page that asks (the Chart page on a phone): in the toolbar it wrapped onto a row
    // of its own the moment a pan began, and pushed the plot 38 px down under the finger (motion check 2026-10-24).
    // It stands above the chart's own buttons: beside them its 44 px reached the volume pane's remove button at 390.
    + (S.homeButton ? '<button type="button" class="pc-cb pc-home" data-pc-home hidden title="Back to the view the chart opened on">Reset zoom</button>' : '')
    + `<div class="pc-panex"></div>`;
  const svg = host.querySelector('.pc-svg'), read = host.querySelector('.pc-read'), live = host.querySelector('.pc-sr');
  const scaleEl = host.querySelector('.pc-scale'), ctl = host.querySelector('.pc-ctl'), panex = host.querySelector('.pc-panex'), homeEl = host.querySelector('[data-pc-home]');
  // a chart that asked for neither (the Instrument page's) gets detached stand-ins, so nothing below needs a guard
  const leg = host.querySelector('.pc-leg') || document.createElement('div'), nav = host.querySelector('.pc-nav') || document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  // the box that names an insider trade under the pointer (or the keyboard's bar); `flags` are the arrows drawn
  const tipEl = document.createElement('div'); tipEl.className = 'pc-tip'; tipEl.setAttribute('role', 'tooltip'); tipEl.hidden = true; host.appendChild(tipEl);
  let flags = [], hoverP = null, fileMarks = [];
  // crosshair sync with the page's line charts of the same `sync` group, by date, on daily and weekly bars only
  // (ui/chart.js has the other half); `told` is the date last sent or taken, so a date taken is not sent back
  const SYNC_ID = `pc${clipSeq}`; let told;

  // daily and weekly bars are dates (UTC midnight); intraday bars are moments in New York
  // a page can name its own bars (`when`: the Investing tab's weeks and months), else the date or the moment
  const fmtT = (t) => { const w = S.when && S.when(t); if (w) return w; const d = new Date(t); return S.intraday ? d.toLocaleString('en-US', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit', timeZone: 'America/New_York' }) : d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric', timeZone: 'UTC' }); };
  const idxOfT = (t) => { let lo = 0, hi = N - 1; while (lo < hi) { const m = (lo + hi) >> 1; if (bars[m].t < t) lo = m + 1; else hi = m; } return lo > 0 && Math.abs(bars[lo - 1].t - t) < Math.abs(bars[lo].t - t) ? lo - 1 : lo; };

  function computeLayout() {
    W = Math.max(300, host.clientWidth); H = S.height || Math.round(Math.max(340, Math.min(620, W * 0.55)));
    const panes = []; const r = 56, l = 4;
    const extra = (S.panes.rsi ? 1 : 0) + (S.panes.macd ? 1 : 0) + (S.panes.tso ? 1 : 0) + SERVER_PANES.filter((k) => S.panes[k]).length;
    // each pane a sixth of the height, or a share of half of it once there are more than three
    const paneH = extra ? Math.round(H * Math.min(0.17, 0.5 / extra)) : 0;
    const priceH = H - 26 - extra * (paneH + 8);
    // volume in its own band at the foot of the price, labelled, as the classic chart draws it
    const volH = S.panes.volume ? Math.round(priceH * 0.2) : 0;
    panes.push({ id: 'price', y0: 8, y1: 8 + priceH - (volH ? volH + 6 : 0) });
    if (volH) panes.push({ id: 'vol', y0: 8 + priceH - volH, y1: 8 + priceH });
    let y = 8 + priceH + 8;
    if (S.panes.rsi) { panes.push({ id: 'rsi', y0: y, y1: y + paneH }); y += paneH + 8; }
    if (S.panes.macd) { panes.push({ id: 'macd', y0: y, y1: y + paneH }); y += paneH + 8; }
    if (S.panes.tso) { panes.push({ id: 'tso', y0: y, y1: y + paneH }); y += paneH + 8; }
    SERVER_PANES.filter((k) => S.panes[k]).forEach((k) => { panes.push({ id: k, y0: y, y1: y + paneH, server: true }); y += paneH + 8; });
    const span = Math.max(1, to - from + 1), bw = (W - l - r) / span;
    return { l, r, panes, bw, X: (i) => l + (i - from + 0.5) * bw, I: (x) => Math.round((x - l) / bw - 0.5 + from) };
  }

  /* ---------- comparison (motion proposal Phase 2, 2026-10-24) ----------
   * S.compare: { anchor: epoch ms, series: [{ sym, cls, closes }] }. Each series' `closes` is aligned to these bars by
   * time, null where that symbol has no bar on this one's (a gap, never a carried value). The price pane then shows
   * every line as the percent change from its close on the anchor bar, labelled with the anchor's date; the price
   * scale, indicators, levels, insider arrows and drawings, all in price, stand aside until the comparison ends. */
  const cmpOn = () => !!(S.compare && (S.compare.series || []).length);
  function cmpState() {
    if (!cmpOn()) return null;
    // the start bar is the first at or after the start's moment: a daily start on hourly bars is that day's first hour,
    // never the hour before it
    let ai = bars.findIndex((b) => b.t >= S.compare.anchor);
    if (ai < 0) ai = N - 1;
    // each line's base is its own close on the anchor bar, or its first close after it when it has none there
    const rebase = (vals) => { let k = ai; while (k < N && !Number.isFinite(vals[k])) k += 1; if (k >= N) return null; const base = vals[k]; return { from: k, pct: vals.map((v) => (Number.isFinite(v) ? (v / base - 1) * 100 : null)) }; };
    const lines = [Object.assign({ sym: (S.title && S.title.sym) || 'Price', cls: 'cm0', closes }, rebase(closes))]
      .concat(S.compare.series.map((x) => { const r = rebase(x.closes); return r ? Object.assign({ sym: x.sym, cls: x.cls, closes: x.closes }, r) : null; }).filter(Boolean));
    return { ai, lines };
  }
  function priceScale(p, C) {
    if (C) {
      let lo = Infinity, hi = -Infinity;
      C.lines.forEach((l) => { for (let i = from; i <= to; i++) { const v = l.pct[i]; if (Number.isFinite(v)) { lo = Math.min(lo, v); hi = Math.max(hi, v); } } });
      if (!Number.isFinite(lo)) { lo = -1; hi = 1; }
      lo = Math.min(lo, 0); hi = Math.max(hi, 0);   // the anchor's 0% is always on the scale
      const sp = (hi - lo) || 1; lo -= sp * 0.06; hi += sp * 0.08;
      if (yZoom !== 1) { const mid = (lo + hi) / 2, half = (hi - lo) / 2 / yZoom; lo = mid - half; hi = mid + half; }
      return { lo, hi, pct: true, Y: (v) => p.y0 + (1 - (v - lo) / (hi - lo)) * (p.y1 - p.y0), P: (y) => lo + (1 - (y - p.y0) / (p.y1 - p.y0)) * (hi - lo) };
    }
    let lo = Infinity, hi = -Infinity;
    for (let i = from; i <= to; i++) { const b = bars[i]; if (!b) continue; lo = Math.min(lo, S.style === 'candles' ? b.l : b.c); hi = Math.max(hi, S.style === 'candles' ? b.h : b.c); }
    const sp = (hi - lo) || 1; lo -= sp * 0.06; hi += sp * 0.08;
    if (yZoom !== 1) { const mid = (lo + hi) / 2, half = (hi - lo) / 2 / yZoom; lo = mid - half; hi = mid + half; }
    return { lo, hi, Y: (v) => p.y0 + (1 - (v - lo) / (hi - lo)) * (p.y1 - p.y0), P: (y) => lo + (1 - (y - p.y0) / (p.y1 - p.y0)) * (hi - lo) };
  }
  const path = (vals, X, Y) => { let d = '', pen = false; for (let i = from; i <= to; i++) { const v = vals[i]; if (v === null || v === undefined || !Number.isFinite(v)) { pen = false; continue; } d += `${pen ? 'L' : 'M'}${X(i).toFixed(1)} ${Y(v).toFixed(1)}`; pen = true; } return d; };

  // the classic draw-on, once, on a line or area chart's first draw; not on a rebuild that keeps the view
  // (a pane added, a refresh). Any later redraw (a tick, the crosshair, a resize) ends it at once: the figures are
  // never held back for it (it used to make redraws wait up to 620 ms)
  let anim = null, animWin = '', first = true, holdT = 0, drawnW = -1;
  function draw() {
    raf = 0; drawnW = host.clientWidth;
    layout = computeLayout();
    const { X, bw, panes } = layout;
    const C = cmpState();
    const pp = panes[0], ps = priceScale(pp, C); layout.ps = ps; layout.cmp = C;
    let o = '';
    // grid and price axis (in percent from the anchor while comparing)
    [0.15, 0.5, 0.85].forEach((f) => { const v = ps.lo + (ps.hi - ps.lo) * f, y = ps.Y(v); o += `<line class="g" x1="0" x2="${W - layout.r}" y1="${y.toFixed(1)}" y2="${y.toFixed(1)}"/><text class="ax" x="${W - layout.r + 6}" y="${(y + 4).toFixed(1)}">${C ? signed(v, Math.abs(ps.hi - ps.lo) < 6 ? 1 : 0) : num(v, v < 10 ? 2 : v < 1000 ? 1 : 0)}</text>`; });
    // time axis
    const step = Math.max(1, Math.round((to - from) / Math.max(3, Math.floor(W / 120))));
    for (let i = from; i <= to; i += step) o += `<text class="ax" x="${Math.max(2, X(i)).toFixed(1)}" y="${H - 6}" text-anchor="${X(i) < 20 ? 'start' : 'middle'}">${esc(S.intraday ? new Date(bars[i].t).toLocaleDateString('en-US', { month: 'short', day: 'numeric', timeZone: 'America/New_York' }) : new Date(bars[i].t).toLocaleDateString('en-US', { month: 'short', year: '2-digit', timeZone: 'UTC' }))}</text>`;
    // everything on the price stays in the price pane: a 200-bar average or a channel below the scale ran into
    // the panes under it
    o += `<defs><clipPath id="${CLIP}"><rect x="0" y="${pp.y0}" width="${W - layout.r}" height="${pp.y1 - pp.y0}"/></clipPath></defs><g clip-path="url(#${CLIP})">`;
    let endsSvg = '';
    if (!C) {
    // levels
    const L = S.levels || {};
    // a label sits over its line at the left, or under it (`below`) or at the right (`end`) where lines run close;
    // a `crowd` label, and a band's, is left off where one already drawn on its side is within 15 px (the line stays)
    const taken = [], room = (side, y) => { if (taken.some((q) => q.side === side && Math.abs(q.y - y) < 15)) return false; taken.push({ side, y }); return true; };
    const hline = (v, cls, t, at = {}) => { if (!Number.isFinite(v) || v < ps.lo || v > ps.hi) return ''; const y = ps.Y(v).toFixed(1), ty = at.below ? Number(y) + 14 : y - 4; return `<line class="lv ${cls}" x1="0" x2="${W - layout.r}" y1="${y}" y2="${y}"/>${at.crowd && !room(at.end ? 'r' : 'l', Number(ty)) ? '' : `<text class="lv-t ${cls}" x="${at.end ? W - layout.r - 6 : 6}" y="${ty}"${at.end ? ' text-anchor="end"' : ''}>${esc(t)}</text>`}`; };
    if (S.overlays.fib && L.fib) (L.fib.levels || []).forEach((f) => { o += hline(f.price, 'fib', `Fib ${f.label}`); });
    if (S.overlays.sr && L.sr) L.sr.slice(0, 8).forEach((s) => { o += hline(s.price, s.role === 'support' ? 'sup' : 'res', `${s.role === 'support' ? 'Support' : 'Resistance'} ${num(s.price)}`); });
    // lines a side widget asks for (the stop check's stop, buffered stop and round number)
    (S.lines || []).forEach((l) => { o += hline(l.price, l.cls, l.label, l); });
    if (S.overlays.gex && L.gex) { const g = L.gex; if (g.call_wall) o += hline(g.call_wall, 'gex', `Call wall ${num(g.call_wall, 0)}`); if (g.put_wall) o += hline(g.put_wall, 'gex', `Put wall ${num(g.put_wall, 0)}`); if (g.flip) o += hline(g.flip, 'gex', `Gamma flip ${num(g.flip, 0)}`); }
    // the classic studies on the price (ui/studies.js; the data for most is fetched by the page, only while on)
    const OV = S.overlays, SD = S.studies || {}, right = W - layout.r;
    // supply and demand zones from the day's pattern read: a band from the bar it formed to the right edge
    if (OV.zones) (SD.zones || []).forEach((z) => { const i0 = Math.max(from, idxOfT(z.t)); if (idxOfT(z.t) > to) return; const y1 = ps.Y(z.top), y2 = ps.Y(z.bottom); if (y2 < pp.y0 || y1 > pp.y1) return; const x0 = X(i0) - bw / 2; o += `<rect class="zn ${z.side === 'supply' ? 'sup' : 'dem'}${z.broken ? ' brk' : ''}" x="${x0.toFixed(1)}" y="${Math.max(pp.y0, y1).toFixed(1)}" width="${Math.max(2, right - x0).toFixed(1)}" height="${Math.max(2, Math.min(pp.y1, y2) - Math.max(pp.y0, y1)).toFixed(1)}"/><text class="lv-t zn-t" x="${(x0 + 4).toFixed(1)}" y="${(Math.max(pp.y0, y1) + 13).toFixed(1)}">${z.side === 'supply' ? 'Supply' : 'Demand'} ${num(z.bottom)} to ${num(z.top)}${z.broken ? ', broken' : ''}</text>`; });
    // accumulation zones from the long-term model's weekly bars: a level each, named at the right
    if (OV.accum) (SD.accum || []).forEach((z) => { o += hline(z.price, 'acc', z.label, { end: true }); });
    // the server's channels and VWAP, bar for bar with these candles
    // the server's channels and VWAP, bar for bar with these candles; a channel's middle line is dashed
    [['keltner', 'kc'], ['donchian', 'dc'], ['sec', 'rc'], ['vwap', 'vw']].forEach(([k, cls]) => {
      if (OV[k] && SD.lines && SD.lines[k]) SD.lines[k].forEach((ln) => { o += `<path class="ov sl ${cls}${/mid|fit/i.test(ln.name) ? ' mid' : ''}" d="${path(ln.values, X, ps.Y)}"/>`; });
    });
    // EMA clouds: the area between two averages, blue while the faster is above, amber while it is below; a run
    // that changes side starts at the last bar of the one before, so the two meet
    const cloud = (fa, sl) => {
      let out = '', run = [];
      const flush = () => { if (run.length > 1) out += `<path class="cl ${run[0].up ? 'up' : 'dn'}" d="M${run.map((q) => `${q.x} ${q.a}`).join('L')}L${run.slice().reverse().map((q) => `${q.x} ${q.b}`).join('L')}Z"/>`; run = []; };
      for (let i = from; i <= to; i++) {
        const a = fa[i], b = sl[i];
        if (!Number.isFinite(a) || !Number.isFinite(b)) { flush(); continue; }
        const q = { x: X(i).toFixed(1), a: ps.Y(a).toFixed(1), b: ps.Y(b).toFixed(1), up: a >= b };
        if (run.length && run[0].up !== q.up) { const last = run[run.length - 1]; flush(); run = [Object.assign({}, last, { up: q.up })]; }
        run.push(q);
      }
      flush();
      return out;
    };
    if (OV.cloud921) o += cloud(ind.ema9, ind.ema21);
    if (OV.cloud2150) o += cloud(ind.ema21, ind.ema50);
    // auto trend lines (daily and weekly bars): the part of each line in view, read off the line at both ends
    if (OV.trends && !S.intraday) (SD.trends || []).forEach((t) => { const a = Math.max(t.i1, from), b = Math.min(t.i2, to); if (a >= b) return; const at = (i) => t.p1 + (t.p2 - t.p1) * (i - t.i1) / Math.max(1, t.i2 - t.i1); o += `<line class="tl ${t.up ? 'up' : 'dn'}${t.broken ? ' brk' : ''}" x1="${X(a).toFixed(1)}" y1="${ps.Y(at(a)).toFixed(1)}" x2="${X(b).toFixed(1)}" y2="${ps.Y(at(b)).toFixed(1)}"><title>${esc(t.label)}</title></line>`; });
    // volume by price, for the bars in view: bars from the right edge, the point of control the strongest
    if (OV.vbp) { const vb = volumeByPrice(bars.slice(from, to + 1).map((b) => b.c), bars.slice(from, to + 1).map((b) => b.v || 0)); if (vb) { const mx = Math.max(...vb.map((q) => q.volume)), wmax = (right - layout.l) * 0.22; vb.forEach((q) => { const y1 = ps.Y(q.hi), y2 = ps.Y(q.lo), w = (q.volume / mx) * wmax; o += `<rect class="vbp${q.poc ? ' poc' : ''}" x="${(right - w).toFixed(1)}" y="${(y1 + 0.5).toFixed(1)}" width="${w.toFixed(1)}" height="${Math.max(0.5, y2 - y1 - 1).toFixed(1)}"/>`; }); } }
    // pre- and post-market bars shaded apart from the regular session (the bars' own `extended` flags)
    if (S.extended && S.intraday) { let i = from; while (i <= to) { if (!S.extended[i]) { i += 1; continue; } let j = i; while (j + 1 <= to && S.extended[j + 1]) j += 1; o += `<rect class="ext-band" x="${(X(i) - bw / 2).toFixed(1)}" y="${pp.y0}" width="${((j - i + 1) * bw).toFixed(1)}" height="${pp.y1 - pp.y0}"><title>Pre- or post-market: thin books</title></rect>`; i = j + 1; } }
    // session dividers on intraday bars: a dashed line where each trading day starts
    if (OV.sessions && S.intraday) ind.sess.forEach((i) => { if (i < from || i > to) return; const x = (X(i) - bw / 2).toFixed(1); o += `<line class="sdiv" x1="${x}" x2="${x}" y1="${pp.y0}" y2="${H - 22}"/>`; });
    // a page's own bands and series (the Investing tab's weekly structure: support and resistance as shaded bands
    // from the weekly frame, the 40 and 200-bar averages), on the same bars; the strongest band comes first, so
    // where labels would stack it is the weaker ones that go
    (S.bands || []).forEach((b) => { const y1 = ps.Y(b.hi), y2 = ps.Y(b.lo); if (y2 < pp.y0 || y1 > pp.y1) return; const top = Math.max(pp.y0, y1); o += `<rect class="band ${b.role === 'resistance' ? 'res' : 'sup'}" x="0" y="${top.toFixed(1)}" width="${W - layout.r}" height="${Math.max(1.5, Math.min(pp.y1, y2) - top).toFixed(1)}"/>${b.label && room('l', top - 3) ? `<text class="lv-t ${b.role === 'resistance' ? 'res' : 'sup'}" x="6" y="${(top - 3).toFixed(1)}">${esc(b.label)}</text>` : ''}`; });
    (S.series || []).forEach((sr) => { o += `<path class="ov ${sr.cls || ''}" d="${path(sr.values, X, ps.Y)}"/>`; });
    // bands and averages
    if (S.overlays.bb) o += `<path class="ov bb" d="${path(ind.bb.up, X, ps.Y)}"/><path class="ov bb" d="${path(ind.bb.dn, X, ps.Y)}"/><path class="ov bbm" d="${path(ind.bb.mid, X, ps.Y)}"/>`;
    if (S.overlays.ma) [['sma20', 'm1'], ['sma50', 'm2'], ['sma200', 'm3']].forEach(([k, c]) => { o += `<path class="ov ${c}" d="${path(ind[k], X, ps.Y)}"/>`; });
    if (S.overlays.ema) [['ema9', 'e1'], ['ema21', 'e2'], ['ema50', 'e3']].forEach(([k, c]) => { o += `<path class="ov ${c}" d="${path(ind[k], X, ps.Y)}"/>`; });
    // the EMAs and VWAP named at the right end of what is in view (owner, 2026-10-24): colour alone told them apart
    const ends = [];
    const endOf = (vals) => { if (!vals) return null; for (let i = to; i >= from; i--) if (Number.isFinite(vals[i])) return vals[i]; return null; };
    if (S.overlays.ema) [['ema9', 'e1', 'EMA 9'], ['ema21', 'e2', 'EMA 21'], ['ema50', 'e3', 'EMA 50']].forEach(([k, c, t]) => { const v = endOf(ind[k]); if (v !== null) ends.push({ v, c, t }); });
    if (OV.vwap && SD.lines && SD.lines.vwap) SD.lines.vwap.forEach((ln) => { const v = endOf(ln.values); if (v !== null) ends.push({ v, c: 'vw', t: 'VWAP' }); });
    // price
    // candle colours: MA Trend's (above all five averages, below all five, between) over Weinstein stages
    const tint = OV.matrend ? (i) => (ind.mat[i] === 1 ? ' tint mt1' : ind.mat[i] === -1 ? ' tint mt4' : ind.mat[i] === 0 ? ' tint mt0' : '')
      : OV.stages && SD.stages ? (i) => (SD.stages[i] ? ` tint st${SD.stages[i]}` : ' tint st0') : () => '';
    if (S.style === 'candles') {
      for (let i = from; i <= to; i++) {
        const b = bars[i], x = X(i), up = b.c >= b.o, y1 = ps.Y(Math.max(b.o, b.c)), y2 = ps.Y(Math.min(b.o, b.c)), tc = tint(i);
        o += `<line class="wick ${up ? 'u' : 'd'}${tc}" x1="${x.toFixed(1)}" x2="${x.toFixed(1)}" y1="${ps.Y(b.h).toFixed(1)}" y2="${ps.Y(b.l).toFixed(1)}"/><rect class="body ${up ? 'u' : 'd'}${tc}" x="${(x - bw * 0.36).toFixed(1)}" y="${y1.toFixed(1)}" width="${Math.max(1, bw * 0.72).toFixed(1)}" height="${Math.max(0.8, y2 - y1).toFixed(1)}"/>`;
      }
    } else {
      const d = path(closes, X, ps.Y);
      // green while the view ends at or above where it starts, red below, as the classic line is (a colour the
      // reader chose wins, through --pc-line)
      const way = bars[to] && bars[from] && bars[to].c >= bars[from].c ? 'up' : 'dn';
      if (S.style === 'area') o += `<path class="area ${way}" d="${d}L${X(to).toFixed(1)} ${pp.y1}L${X(from).toFixed(1)} ${pp.y1}Z"/>`;
      o += `<path class="pline ${way}" d="${d}"/>`;
    }
    // the last price, as the classic chart marks it: a dashed line across the plot and its value tagged on the axis
    // green or red with the day's move: on intraday bars against the last close of the session before
    { const lb = bars[N - 1], v = lb && lb.c; let pb = bars[N - 2]; if (S.intraday && lb) { const d = nyDate(lb.t); for (let j = N - 2; j >= 0; j--) if (nyDate(bars[j].t) !== d) { pb = bars[j]; break; } } if (Number.isFinite(v) && v >= ps.lo && v <= ps.hi) { const y = ps.Y(v).toFixed(1), up = !pb || v >= pb.c; o += `<line class="lastp ${up ? 'up' : 'dn'}" x1="0" x2="${W - layout.r}" y1="${y}" y2="${y}"/>`; layout.last = { y, up, v }; } else layout.last = null; }
    // the end labels, right-aligned inside the plot, drawn after the markers so nothing covers them; where two would
    // overlap the lower one steps down
    { const pl = ends.filter((e) => e.v >= ps.lo && e.v <= ps.hi).map((e) => Object.assign(e, { y: ps.Y(e.v) + 4 })).sort((a, b) => a.y - b.y); let last = -Infinity;
      pl.forEach((e) => { e.y = Math.min(pp.y1 - 2, Math.max(e.y, last + 13)); last = e.y; endsSvg += `<text class="endl ${e.c}" x="${(right - 6).toFixed(1)}" y="${e.y.toFixed(1)}" text-anchor="end">${e.t}</text>`; }); }
    // the stage of each run named along the foot of the price, where there is room
    if (OV.stages && !OV.matrend && SD.stages && S.style === 'candles') { let a = from; for (let i = from; i <= to + 1; i++) { if (i <= to && SD.stages[i] === SD.stages[a]) continue; const n = SD.stages[a]; if (n && (i - a) * bw > 96) o += `<text class="st-t st${n}" x="${(X(a) - bw / 2 + 4).toFixed(1)}" y="${(pp.y1 - 5).toFixed(1)}">Stage ${n}, ${esc((S.stageNames || {})[n] || '')}</text>`; a = i; } }
    // market structure breaks: the level dotted from the swing bar to the bar that confirmed it (before it
    // was knowable), solid from confirmation to the break, a tick where it became known, a mark on the breaking close
    if (S.overlays.msb) ind.msb.forEach((m) => {
      if (m.at < from || m.from > to) return;
      const xa = X(Math.max(m.from, from)), xk = X(Math.min(Math.max(m.known, from), to)), xb = X(Math.min(m.at, to)), y = ps.Y(m.price), bull = m.dir === 'bull';
      if (y < pp.y0 || y > pp.y1) return;
      const word = bull ? 'Bullish' : 'Bearish', at = bars[m.at];
      o += `<g class="msb ${bull ? 'bull' : 'bear'}">`
        + (m.known > from ? `<line class="pre" x1="${xa.toFixed(1)}" x2="${xk.toFixed(1)}" y1="${y.toFixed(1)}" y2="${y.toFixed(1)}"/>` : '')
        + `<line x1="${xk.toFixed(1)}" x2="${xb.toFixed(1)}" y1="${y.toFixed(1)}" y2="${y.toFixed(1)}"/>`
        + (m.known >= from && m.known <= to ? `<line class="known" x1="${xk.toFixed(1)}" x2="${xk.toFixed(1)}" y1="${(y - 5).toFixed(1)}" y2="${(y + 5).toFixed(1)}"/>` : '')
        + `<text x="${(xk + 3).toFixed(1)}" y="${(bull ? y - 6 : y + 14).toFixed(1)}">MSB</text>`
        + (m.at <= to ? `<circle cx="${X(m.at).toFixed(1)}" cy="${ps.Y(at.c).toFixed(1)}" r="${Math.max(5, Math.min(10, bw * 0.9)).toFixed(1)}"/>` : '')
        + `<title>${word} market structure break. Swing ${bull ? 'high' : 'low'} of ${num(m.price)} formed ${fmtT(bars[m.from].t)}; known as a swing from ${fmtT(bars[m.known].t)}, once the bars after it had closed (dotted before then); broken ${fmtT(at.t)} by a close of ${num(at.c)}.</title></g>`;
    });
    } else {
      // the comparison: a dotted line on the anchor bar, where every line is 0%, the zero line, and each symbol's
      // line in percent; each named at its right end with its change, as the indicators are
      if (C.ai >= from && C.ai <= to) { const x = X(C.ai).toFixed(1); o += `<line class="cm-anchor" x1="${x}" x2="${x}" y1="${pp.y0}" y2="${pp.y1}"/>`; }
      { const y0 = ps.Y(0).toFixed(1); o += `<line class="cm-zero" x1="0" x2="${W - layout.r}" y1="${y0}" y2="${y0}"/>`; }
      C.lines.forEach((l) => { o += `<path class="cmp ${l.cls}" d="${path(l.pct, X, ps.Y)}"/>`; });
      const right = W - layout.r, pl = [];
      C.lines.forEach((l) => { for (let i = to; i >= from; i--) if (Number.isFinite(l.pct[i])) { pl.push({ y: ps.Y(l.pct[i]) + 4, c: l.cls, t: `${l.sym} ${signed(l.pct[i], 1)}` }); break; } });
      pl.sort((a, b) => a.y - b.y); let last = -Infinity;
      pl.forEach((e) => { e.y = Math.min(pp.y1 - 2, Math.max(e.y, last + 13)); last = e.y; endsSvg += `<text class="endl ${e.c}" x="${(right - 6).toFixed(1)}" y="${e.y.toFixed(1)}" text-anchor="end">${esc(e.t)}</text>`; });
    }
    // earnings and other events
    (S.overlays.events === false ? [] : S.events).forEach((e) => { const i = AX.bar(e.t); if (i < 0 || i < from || i > to) return; const x = X(i).toFixed(1);
      // a marker on the newest bar or the first kept its label inside the plot rather than cut off at the edge
      const edge = X(i) > W - layout.r - 36 ? ['end', X(i) - 4] : X(i) < 36 ? ['start', X(i) + 4] : ['middle', X(i)];
      o += `<g class="evm"><line x1="${x}" x2="${x}" y1="${pp.y0}" y2="${pp.y1}"/><text x="${edge[1].toFixed(1)}" y="${pp.y1 - 4}" text-anchor="${edge[0]}">${esc(e.kind)}</text><title>${esc(e.label)}</title></g>`; });
    // SEC filings (S.filings: the ticker payload's EDGAR list, its latest notable filings), on the bar of the day each was
    // filed: a dotted line and the form at the top of the price, where the earnings marks' letters at the foot are clear;
    // a form within 34 px of the one before keeps its line and leaves its label off
    fileMarks = [];
    if (S.overlays.filings && (S.filings || []).length) {
      // the legend sits over the plot's top-left corner: a form under it keeps its line and loses its label
      let lastX = -1e9; const legW = S.names && leg.offsetWidth ? leg.offsetLeft + leg.offsetWidth + 6 : 0;
      S.filings.slice().sort((a, b) => a.t - b.t).forEach((f) => {
        const i = AX.bar(f.t); if (i < 0 || i < from || i > to) return;
        const x = X(i), room = x - lastX >= 34 && x - 14 > legW; if (room) lastX = x;
        const edge = x > W - layout.r - 30 ? ['end', x - 3] : x < 30 ? ['start', x + 3] : ['middle', x];
        fileMarks.push({ i, f });
        o += `<g class="fim"><line x1="${x.toFixed(1)}" x2="${x.toFixed(1)}" y1="${pp.y0 + 16}" y2="${pp.y1}"/>${room ? `<text x="${edge[1].toFixed(1)}" y="${pp.y0 + 12}" text-anchor="${edge[0]}">${esc(f.form)}</text>` : ''}<title>${esc(f.label)}</title></g>`;
      });
    }
    // insider trades (S.insiders, from the ticker payload): a green arrow under the bar's low for a purchase, a red
    // one over its high for a sale, one arrow for all of a side's trades in a bar; the box comes from insiderTip()
    flags = [];
    if (!C && S.overlays.ins !== false && (S.insiders || []).length) {
      const by = new Map();
      S.insiders.forEach((it) => { const i = AX.bar(it.t); if (i < 0 || i < from || i > to || !bars[i]) return; const k = `${i}${it.side}`; if (!by.has(k)) by.set(k, { i, side: it.side, items: [] }); by.get(k).items.push(it); });
      by.forEach((f) => {
        const b = bars[f.i], x = X(f.i), buy = f.side === 'buy';
        const tip = buy ? Math.min(pp.y1 - 21, ps.Y(b.l) + 6) : Math.max(pp.y0 + 21, ps.Y(b.h) - 6), d = buy ? 1 : -1;
        const pts = [[0, 0], [7.5, 9], [2, 9], [2, 19], [-2, 19], [-2, 9], [-7.5, 9]].map(([dx, dy]) => `${(x + dx).toFixed(1)} ${(tip + d * dy).toFixed(1)}`);
        o += `<path class="ins ${buy ? 'buy' : 'sell'}" d="M${pts.join('L')}Z"/>`;
        flags.push(Object.assign(f, { x, y: tip + d * 10 }));
      });
    }
    // fills a side widget asks for (the backtest's entries and exits): B under the bar's low, S over its high
    (C ? [] : (S.marks || [])).forEach((m) => {
      const i = AX.bar(m.t); if (i < 0 || i < from || i > to || !bars[i]) return;
      const b = bars[i], x = X(i), r = 8, buy = m.kind === 'B';
      const y = Math.max(pp.y0 + r, Math.min(pp.y1 - r, buy ? ps.Y(b.l) + r + 4 : ps.Y(b.h) - r - 4));
      o += `<g class="tm ${m.tone === 'neg' ? 'neg' : 'pos'}"><circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="${r}"/><text x="${x.toFixed(1)}" y="${(y + 4).toFixed(1)}" text-anchor="middle">${esc(m.kind)}</text><title>${esc(m.label)}</title></g>`;
    });
    // drawings
    if (!C) S.drawings.forEach((dr, k) => { o += drawing(dr, k === sel); });
    // the tool being placed, to the pointer (snapped as a click there would be)
    if (!C && pending && pending.points.length) pending.points.forEach((q) => { o += `<circle class="dr-h dr-placed" cx="${X(AX.f(q.t)).toFixed(1)}" cy="${ps.Y(q.p).toFixed(1)}" r="5"/>`; });
    if (!C && pending && pending.points.length && cross >= 0 && crossY !== null) o += drawing({ kind: pending.kind, points: [...pending.points, { t: bars[cross].t, p: S.snap ? snap(bars[cross], crossY, ps.Y).price : crossY }] }, false, true);
    if (!C) o += msSvg();
    o += '</g>';
    // panes
    panes.slice(1).forEach((p) => {
      if (p.id === 'vol') {
        let vmax = 0; for (let i = from; i <= to; i++) vmax = Math.max(vmax, bars[i].v || 0);
        const vh = p.y1 - p.y0 - 14;
        for (let i = from; i <= to; i++) { const b = bars[i]; if (!b.v) continue; const h = (b.v / (vmax || 1)) * vh; o += `<rect class="vol ${b.c >= b.o ? 'u' : 'd'}" x="${(X(i) - bw * 0.38).toFixed(1)}" y="${(p.y1 - h).toFixed(1)}" width="${Math.max(0.6, bw * 0.76).toFixed(1)}" height="${h.toFixed(1)}"/>`; }
        o += `<text class="pane-t" x="6" y="${p.y0 + 11}">Volume</text>`;
        return;
      }
      o += `<line class="pane-sep" x1="0" x2="${W}" y1="${p.y0 - 4}" y2="${p.y0 - 4}"/>`;
      if (p.id === 'rsi') {
        const Y = (v) => p.y0 + (1 - v / 100) * (p.y1 - p.y0);
        o += `<line class="g" x1="0" x2="${W - layout.r}" y1="${Y(70)}" y2="${Y(70)}"/><line class="g" x1="0" x2="${W - layout.r}" y1="${Y(30)}" y2="${Y(30)}"/><text class="ax" x="${W - layout.r + 6}" y="${Y(70) + 4}">70</text><text class="ax" x="${W - layout.r + 6}" y="${Y(30) + 4}">30</text><text class="pane-t" x="6" y="${p.y0 + 12}">RSI 14</text><path class="ov rsi" d="${path(ind.rsi, X, Y)}"/>`;
      } else if (p.server) {
        // a pane /api/indicators computed (C19): its lines, its reference levels dashed, the values at the crosshair's bar
        const sp = ((S.studies || {}).panes || {})[p.id], name = PANE_NAMES[p.id];
        if (!sp || !sp.lines) { o += `<text class="pane-t" x="6" y="${p.y0 + 12}">${esc(name)}: ${esc(sp ? sp.reason : 'loading')}</text>`; return; }
        let lo = Infinity, hi = -Infinity;
        sp.lines.forEach((ln) => { for (let i = from; i <= to; i++) { const v = ln.values[i]; if (Number.isFinite(v)) { lo = Math.min(lo, v); hi = Math.max(hi, v); } } });
        if (BOUNDED[p.id]) { lo = Math.min(lo, BOUNDED[p.id][0]); hi = Math.max(hi, BOUNDED[p.id][1]); }
        if (!Number.isFinite(lo)) { o += `<text class="pane-t" x="6" y="${p.y0 + 12}">${esc(name)}: not enough bars</text>`; return; }
        const pad = (hi - lo || 1) * 0.08, a = lo - pad, z = hi + pad, Y = (v) => p.y0 + (1 - (v - a) / (z - a)) * (p.y1 - p.y0);
        const fmtV = (v) => (Math.abs(v) >= 1e5 ? compact(v) : num(v, Math.abs(v) >= 100 ? 0 : 1));
        (sp.reference || []).forEach((r) => { if (r.value < a || r.value > z) return; o += `<line class="g ref" x1="0" x2="${W - layout.r}" y1="${Y(r.value).toFixed(1)}" y2="${Y(r.value).toFixed(1)}"/><text class="ax" x="${W - layout.r + 6}" y="${(Y(r.value) + 4).toFixed(1)}">${esc(Number.isInteger(r.value) ? String(r.value) : fmtV(r.value))}</text>`; });
        sp.lines.forEach((ln, j) => { o += `<path class="ov ip ${PANE_LINE[p.id] ? PANE_LINE[p.id][j] || `ip${j}` : `ip${j}`}" d="${path(ln.values, X, Y)}"/>`; });
        const at = cross >= 0 ? cross : to;
        // SVG collapses runs of spaces, so the values are set off with a colon and commas
        const vals = sp.lines.filter((ln) => Number.isFinite(ln.values[at])).map((ln) => (sp.lines.length === 1 ? fmtV(ln.values[at]) : `${ln.name} ${fmtV(ln.values[at])}`));
        o += `<text class="pane-t" x="6" y="${p.y0 + 12}">${esc(name)}${vals.length ? `: ${esc(vals.join(', '))}` : ''}</text>`;
      } else if (p.id === 'tso') {
        // Trend Strength Oscillator: past +50 or -50 a strong trend has run far and fast ("overextended")
        let mx = 100; for (let i = from; i <= to; i++) { const v = ind.tso[i]; if (Number.isFinite(v)) mx = Math.max(mx, Math.abs(v)); }
        const Y = (v) => p.y0 + (1 - (v + mx) / (2 * mx)) * (p.y1 - p.y0);
        o += `<line class="g" x1="0" x2="${W - layout.r}" y1="${Y(TSO_LEVEL)}" y2="${Y(TSO_LEVEL)}"/><line class="g" x1="0" x2="${W - layout.r}" y1="${Y(-TSO_LEVEL)}" y2="${Y(-TSO_LEVEL)}"/><line class="g z" x1="0" x2="${W - layout.r}" y1="${Y(0)}" y2="${Y(0)}"/><text class="ax" x="${W - layout.r + 6}" y="${Y(TSO_LEVEL) + 4}">+50</text><text class="ax" x="${W - layout.r + 6}" y="${Y(-TSO_LEVEL) + 4}">−50</text><text class="pane-t" x="6" y="${p.y0 + 12}">TSO 14, 14, 5</text><path class="ov tso" d="${path(ind.tso, X, Y)}"/>`;
      } else {
        const m = ind.macd; let mx = 0; for (let i = from; i <= to; i++) [m.line[i], m.signal[i], m.hist[i]].forEach((v) => { if (Number.isFinite(v)) mx = Math.max(mx, Math.abs(v)); });
        const Y = (v) => p.y0 + (1 - (v + (mx || 1)) / (2 * (mx || 1))) * (p.y1 - p.y0);
        for (let i = from; i <= to; i++) { const h = m.hist[i]; if (!Number.isFinite(h)) continue; o += `<rect class="mh ${h >= 0 ? 'u' : 'd'}" x="${(X(i) - bw * 0.35).toFixed(1)}" y="${Math.min(Y(0), Y(h)).toFixed(1)}" width="${Math.max(0.6, bw * 0.7).toFixed(1)}" height="${Math.abs(Y(h) - Y(0)).toFixed(1)}"/>`; }
        o += `<text class="pane-t" x="6" y="${p.y0 + 12}">MACD 12, 26, 9</text><path class="ov macd" d="${path(m.line, X, Y)}"/><path class="ov macds" d="${path(m.signal, X, Y)}"/>`;
      }
    });
    if (layout.last) o += `<rect class="lastp-tag ${layout.last.up ? 'up' : 'dn'}" x="${W - layout.r + 2}" y="${layout.last.y - 9}" width="${layout.r - 4}" height="18" rx="3"/><text class="lastp-t" x="${W - layout.r + 6}" y="${Number(layout.last.y) + 4}">${num(layout.last.v, layout.last.v < 10 ? 2 : layout.last.v < 1000 ? 2 : 0)}</text>`;
    o += endsSvg;
    // crosshair
    if (cross >= from && cross <= to) {
      const x = X(cross).toFixed(1);
      o += `<line class="xh" x1="${x}" x2="${x}" y1="${pp.y0}" y2="${H - 22}"/>`;
      // comparing, the level line sits on this symbol's own line at the bar being read, so the tag is a figure drawn
      if (C && Number.isFinite(C.lines[0].pct[cross])) { const v = C.lines[0].pct[cross], y = ps.Y(v).toFixed(1); o += `<line class="xh" x1="0" x2="${W - layout.r}" y1="${y}" y2="${y}"/><rect class="xh-tag" x="${W - layout.r + 2}" y="${y - 9}" width="${layout.r - 4}" height="18" rx="3"/><text class="xh-t" x="${W - layout.r + 6}" y="${(Number(y) + 4)}">${signed(v, 1)}</text>`; }
      else if (!C && crossY !== null) { const y = ps.Y(crossY).toFixed(1); o += `<line class="xh" x1="0" x2="${W - layout.r}" y1="${y}" y2="${y}"/><rect class="xh-tag" x="${W - layout.r + 2}" y="${y - 9}" width="${layout.r - 4}" height="18" rx="3"/><text class="xh-t" x="${W - layout.r + 6}" y="${(Number(y) + 4)}">${num(crossY, crossY < 10 ? 2 : 1)}</text>`; }
    }
    svg.setAttribute('viewBox', `0 0 ${W} ${H}`); svg.setAttribute('width', W); svg.setAttribute('height', H);
    svg.innerHTML = o;
    // a draw-on under way carries on while the same bars are in view (a settling redraw, a rescaled price axis, the
    // crosshair); a zoom, a pan or a new bar ends it on the spot. Either way the figures drawn are the current ones.
    if (anim) { if (anim.busy() && animWin === `${from}:${to}:${N}:${S.style}`) anim.carry(); else { anim.finish(); anim = null; } }
    if (ms) fitPlate();
    if (first) { first = false; if (S.animate !== false && !S.view && (S.style === 'line' || S.style === 'area')) { anim = drawOn(svg, { lines: '.pline', fades: '.area' }); animWin = `${from}:${to}:${N}:${S.style}`; } }
    svg.setAttribute('aria-label', summary());
    readout();
    const zoomed = from !== home0.from || to !== home0.to || yZoom !== 1;
    if (zoomed !== zoomedWas && homeEl) homeEl.hidden = !zoomed;
    place2();
    if (zoomed !== zoomedWas) { zoomedWas = zoomed; if (S.onView) S.onView({ zoomed }); }
    legend(); drawNav();
  }

  // A measurement: the band between the two bars, their closes marked, and a plate with the change and the dates.
  function msSvg() {
    if (!ms) return '';
    const r = measuredBars(bars, ms.a, ms.b, fmtT), X = layout.X, ps = layout.ps, pp = layout.panes[0], right = W - layout.r;
    const xa = X(r.i), xb = X(r.j);
    const dots = [r.i, r.j].filter((i) => i >= from && i <= to).map((i) => `<circle class="dr-dot ${r.tone}" cx="${X(i).toFixed(1)}" cy="${ps.Y(bars[i].c).toFixed(1)}" r="4"/>`).join('');
    if (r.i === r.j) return `<g class="pc-ms"><line class="dr-edge" x1="${xa.toFixed(1)}" x2="${xa.toFixed(1)}" y1="${pp.y0}" y2="${pp.y1}"/>${dots}</g>`;
    // the dates and the bars on one line, or on two where a narrow chart cannot hold them; the plate is fitted to
    // the drawn text afterwards (fitPlate)
    const nb = `${r.bars} bar${r.bars === 1 ? '' : 's'}`, one = `${r.span}, ${nb}`;
    const lines = one.length * 7.2 + 24 <= right - 8 ? [one] : [`${fmtT(bars[r.i].t)} to`, `${fmtT(bars[r.j].t)}, ${nb}`];
    const w = Math.min(right - 8, Math.max(r.head.length * 8.4, ...lines.map((t) => t.length * 7.2)) + 24), mx = Math.min(Math.max((xa + xb) / 2, w / 2 + 4), right - w / 2 - 4), ph = 22 + 16 * lines.length;
    // the plate sits at the top of the price, clear of the legend over its corner (below it, or at the foot when the
    // open legend runs down the plot); seen under the folded legend on a phone, 2026-10-21
    let y = pp.y0 + 6;
    const lr = S.names ? leg.getBoundingClientRect() : null;
    if (lr && lr.width) {
      const sr = svg.getBoundingClientRect(), k = sr.width / (W || 1), lx0 = (lr.left - sr.left) / k, lx1 = (lr.right - sr.left) / k, ly1 = (lr.bottom - sr.top) / k;
      if (mx - w / 2 < lx1 + 4 && mx + w / 2 > lx0 - 4 && y < ly1 + 4) y = ly1 + 6 > pp.y0 + (pp.y1 - pp.y0) / 2 ? pp.y1 - ph - 6 : ly1 + 6;
    }
    return `<g class="pc-ms"><rect class="dr-rng ${r.tone}" x="${xa.toFixed(1)}" y="${pp.y0}" width="${Math.max(1, xb - xa).toFixed(1)}" height="${pp.y1 - pp.y0}"/>`
      + `<line class="dr-edge ${r.tone}" x1="${xa.toFixed(1)}" x2="${xa.toFixed(1)}" y1="${pp.y0}" y2="${pp.y1}"/><line class="dr-edge ${r.tone}" x1="${xb.toFixed(1)}" x2="${xb.toFixed(1)}" y1="${pp.y0}" y2="${pp.y1}"/>${dots}`
      + `<rect class="dr-plate" x="${(mx - w / 2).toFixed(1)}" y="${y.toFixed(1)}" width="${w.toFixed(1)}" height="${ph}" rx="6"/><text class="dr-pf ${r.tone}" x="${mx.toFixed(1)}" y="${(y + 15).toFixed(1)}" text-anchor="middle">${esc(r.head)}</text>`
      + lines.map((t, n) => `<text class="dr-pt" x="${mx.toFixed(1)}" y="${(y + 31 + 16 * n).toFixed(1)}" text-anchor="middle">${esc(t)}</text>`).join('') + '</g>';
  }
  // The plate's width from its drawn text (a font's real widths, not a guess), centred where it was and kept inside
  // the plot.
  function fitPlate() {
    const g = svg.querySelector('.pc-ms'), plate = g && g.querySelector('.dr-plate'); if (!plate) return;
    const ts = [...g.querySelectorAll('text')], right = W - layout.r;
    let w = 0; ts.forEach((t) => { try { w = Math.max(w, t.getBBox().width); } catch (e) { /* not laid out */ } });
    if (!w) return;
    w = Math.min(right - 4, w + 24);
    const c = Number(plate.getAttribute('x')) + Number(plate.getAttribute('width')) / 2, mx = Math.min(Math.max(c, w / 2 + 2), right - w / 2 - 2);
    plate.setAttribute('x', (mx - w / 2).toFixed(1)); plate.setAttribute('width', w.toFixed(1));
    ts.forEach((t) => t.setAttribute('x', mx.toFixed(1)));
  }
  // The chart's own HTML over the plot, placed from the layout: the price scale's strip over the axis gutter, the
  // buttons at the foot of the price, and a remove button at the top right of each pane (rebuilt only when the
  // panes change, so a button is never replaced under the pointer).
  let placedSig = '', paneSig = '';
  const PANE_LABEL = Object.assign({ vol: 'Volume', rsi: 'RSI 14', macd: 'MACD 12, 26, 9', tso: 'Trend Strength Oscillator' }, PANE_NAMES);
  function place2() {
    const panes = layout.panes, foot = (panes.find((q) => q.id === 'vol') || panes[0]).y1, sig = [W, H, panes.map((q) => `${q.id}:${q.y0}`).join(',')].join('|');
    const ps2 = S.onRemove ? panes.slice(1).map((q) => q.id).join(',') : '';
    if (ps2 !== paneSig) { paneSig = ps2; panex.innerHTML = S.onRemove ? panes.slice(1).map((q) => { const k = q.id === 'vol' ? 'volume' : q.id, name = esc(PANE_LABEL[q.id] || q.id); return `<button type="button" class="pc-px" data-pc-pane="${esc(k)}" data-pane-at="${esc(q.id)}" aria-label="Remove the ${name} pane" title="Remove ${name}">${icon('close').s}</button>`; }).join('') : ''; placedSig = ''; }
    // an <svg> has no offsetTop: its place in the host comes from the two boxes, in CSS pixels (cssZoom)
    const r = svg.getBoundingClientRect(), hr = host.getBoundingClientRect(), z = cssZoom(hr), k = r.width / (W || 1) / z, top0 = (r.top - hr.top) / z, left0 = (r.left - hr.left) / z;
    const at = `${sig}|${Math.round(top0)}|${Math.round(left0)}|${k.toFixed(3)}|${ctl.offsetHeight}`;
    if (at === placedSig) return;
    placedSig = at;
    Object.assign(scaleEl.style, { left: `${left0 + (W - layout.r) * k}px`, top: `${top0 + panes[0].y0 * k}px`, width: `${layout.r * k}px`, height: `${(panes[0].y1 - panes[0].y0) * k}px` });
    // where the volume band is too short for its label and the buttons (a 360 px phone), they start after the label
    const vol = panes.find((q) => q.id === 'vol'), bh = ctl.offsetHeight || 36;
    let lx = (layout.l + 6) * k;
    if (vol && (vol.y1 - vol.y0) * k < bh + 16) { const t = [...svg.querySelectorAll('text.pane-t')].find((x) => x.textContent === 'Volume'); if (t) lx = (6 + t.getBBox().width + 10) * k; }
    Object.assign(ctl.style, { left: `${left0 + lx}px`, top: `${top0 + foot * k - bh - 4}px` });
    // Reset zoom over the foot of the price, clear of the volume band's label (or above the buttons with no band)
    if (homeEl) Object.assign(homeEl.style, { left: `${left0 + lx}px`, top: `${(vol ? top0 + vol.y0 * k : top0 + foot * k - bh - 4) - bh - 6}px` });
    panex.querySelectorAll('[data-pane-at]').forEach((b) => { const q = panes.find((x) => x.id === b.dataset.paneAt); if (q) Object.assign(b.style, { top: `${top0 + (q.y0 - 2) * k}px`, left: `${left0 + (W - layout.r) * k - 40}px` }); });
  }

  // One drawing as SVG: its shape, its labels, and on the selected one a handle at each point (drag one to move
  // that point, drag the shape to move it all). A tool still being placed draws what its points so far make.
  function drawing(dr, selected, ghost) {
    const ps = layout.ps, X = layout.X, right = W - layout.r, last = N - 1;
    const q = dr.points.map((x) => ({ i: AX.f(x.t), p: x.p, t: x.t }));
    const pts = q.map((x) => ({ x: X(x.i), y: ps.Y(x.p), p: x.p }));
    const cls = `dr ${selected ? 'sel' : ''} ${ghost ? 'ghost' : ''}`;
    const seg = (g, c = cls) => `<line class="${c}" x1="${X(g.i1).toFixed(1)}" y1="${ps.Y(g.p1).toFixed(1)}" x2="${X(g.i2).toFixed(1)}" y2="${ps.Y(g.p2).toFixed(1)}"/>`;
    const handles = selected && !ghost ? pts.map((x) => `<circle class="dr-h" cx="${x.x.toFixed(1)}" cy="${x.y.toFixed(1)}" r="5"/>`).join('') : '';
    const lab = (x, y, t, c = 'dr-t', anchor = '') => `<text class="${c}" x="${x.toFixed(1)}" y="${y.toFixed(1)}"${anchor ? ` text-anchor="${anchor}"` : ''}>${esc(t)}</text>`;
    const need = TOOL_POINTS[dr.kind] || 2;
    let out = '';
    if (dr.kind === 'hline') out = `<line class="${cls}" x1="0" x2="${right}" y1="${pts[0].y}" y2="${pts[0].y}"/>${lab(right - 4, pts[0].y - 4, `${num(pts[0].p)}${dr.origin === 'milo' ? ' Milo' : ''}`, 'dr-t', 'end')}`;
    else if (dr.kind === 'vline') out = `<line class="${cls}" x1="${pts[0].x}" x2="${pts[0].x}" y1="${layout.panes[0].y0}" y2="${layout.panes[0].y1}"/>`;
    else if (dr.kind === 'text') out = `<text class="dr-text ${selected ? 'sel' : ''}" x="${pts[0].x}" y="${pts[0].y}">${esc(dr.text || '')}</text>`;
    else if (pts.length < 2) out = '';
    else if (pts.length < need) out = `<line class="${cls}" x1="${pts[0].x}" y1="${pts[0].y}" x2="${pts[1].x}" y2="${pts[1].y}"/>`;   // the first leg of a three-point tool
    else {
      const [a, b] = pts;
      if (dr.kind === 'trend') out = `<line class="${cls}" x1="${a.x}" y1="${a.y}" x2="${b.x}" y2="${b.y}"/>`;
      else if (dr.kind === 'ray') { const k = (b.y - a.y) / ((b.x - a.x) || 1e-6), x2 = b.x >= a.x ? right : 0; out = `<line class="${cls}" x1="${a.x}" y1="${a.y}" x2="${x2}" y2="${a.y + k * (x2 - a.x)}"/>`; }
      else if (dr.kind === 'rect') out = `<rect class="${cls} dr-rect" x="${Math.min(a.x, b.x)}" y="${Math.min(a.y, b.y)}" width="${Math.abs(b.x - a.x)}" height="${Math.abs(b.y - a.y)}"/>`;
      // 0% at the first point, as the classic app draws it
      else if (dr.kind === 'fibdraw') out = FIB.map((f) => { const pr = a.p + (b.p - a.p) * f, y = ps.Y(pr); return `<line class="${cls}" x1="${Math.min(a.x, b.x)}" x2="${right}" y1="${y}" y2="${y}"/>${lab(Math.min(a.x, b.x) + 4, y - 3, `${num(f * 100, 1)}% ${num(pr)}`)}`; }).join('');
      else if (dr.kind === 'channel') { const [l1, l2] = channel(q[0], q[1], q[2], last); out = `<path class="dr-fill" d="M${X(l1.i1).toFixed(1)} ${ps.Y(l1.p1).toFixed(1)}L${X(l1.i2).toFixed(1)} ${ps.Y(l1.p2).toFixed(1)}L${X(l2.i2).toFixed(1)} ${ps.Y(l2.p2).toFixed(1)}L${X(l2.i1).toFixed(1)} ${ps.Y(l2.p1).toFixed(1)}Z"/>${seg(l1)}${seg(l2)}`; }
      else if (dr.kind === 'fibext') { const x1 = Math.min(pts[0].x, pts[2].x); out = `<line class="${cls} dr-thin" x1="${a.x}" y1="${a.y}" x2="${b.x}" y2="${b.y}"/><line class="${cls} dr-thin" x1="${b.x}" y1="${b.y}" x2="${pts[2].x}" y2="${pts[2].y}"/>` + fibExt(q[0], q[1], q[2]).map((l) => { const y = ps.Y(l.price); return `<line class="${cls}${l.r === 1 || l.r === 1.618 ? '' : ' dr-thin'}" x1="${x1}" x2="${right}" y1="${y}" y2="${y}"/>${lab(x1 + 4, y - 3, `${l.r} ${num(l.price)}`)}`; }).join(''); }
      else if (dr.kind === 'pitchfork') { const f = pitchfork(q[0], q[1], q[2], last); out = seg(f.handle, `${cls} dr-dash`) + f.tines.map((g, k) => seg(g, k ? `${cls} dr-thin` : cls)).join(''); }
      else if (dr.kind === 'arrow') { const ang = Math.atan2(b.y - a.y, b.x - a.x), h = 10; out = `<line class="${cls}" x1="${a.x}" y1="${a.y}" x2="${b.x}" y2="${b.y}"/><path class="dr-head" d="M${b.x} ${b.y}L${(b.x - h * Math.cos(ang - 0.4)).toFixed(1)} ${(b.y - h * Math.sin(ang - 0.4)).toFixed(1)}L${(b.x - h * Math.cos(ang + 0.4)).toFixed(1)} ${(b.y - h * Math.sin(ang + 0.4)).toFixed(1)}Z"/>`; }
      else if (dr.kind === 'ruler') {
        const m = measure(q[0], q[1]), lo = Math.min(a.x, b.x), hi = Math.max(a.x, b.x), y0 = layout.panes[0].y0, y1 = layout.panes[0].y1, tone = m.change > 0 ? 'up' : m.change < 0 ? 'dn' : '';
        const early = q[0].t <= q[1].t ? q[0] : q[1], late = early === q[0] ? q[1] : q[0], mx = Math.min(Math.max((lo + hi) / 2, 70), right - 70);
        const span = `${fmtT(early.t)} to ${fmtT(late.t)}, ${m.bars} bar${m.bars === 1 ? '' : 's'}`, fig = `${m.change > 0 ? '+' : m.change < 0 ? '−' : ''}${num(Math.abs(m.change))}, ${m.change > 0 ? '+' : m.change < 0 ? '−' : ''}${num(Math.abs(m.pct))}%`;
        out = `<rect class="dr-rng ${tone}" x="${lo.toFixed(1)}" y="${y0}" width="${Math.max(1, hi - lo).toFixed(1)}" height="${y1 - y0}"/><line class="dr-edge ${tone}" x1="${lo}" x2="${lo}" y1="${y0}" y2="${y1}"/><line class="dr-edge ${tone}" x1="${hi}" x2="${hi}" y1="${y0}" y2="${y1}"/>`
          + pts.map((x) => `<circle class="dr-dot ${tone}" cx="${x.x}" cy="${x.y}" r="4"/>`).join('')
          + `<rect class="dr-plate" x="${(mx - 92).toFixed(1)}" y="${y0 + 6}" width="184" height="36" rx="6"/>${lab(mx, y0 + 20, span, 'dr-pt', 'middle')}${lab(mx, y0 + 36, fig, `dr-pf ${tone}`, 'middle')}`;
      } else if (dr.kind === 'rr') {
        const [e, st, tg] = q, k = riskReward(e, st, tg), x1 = X(Math.min(e.i, st.i, tg.i)), yE = ps.Y(e.p), yS = ps.Y(st.p), yT = ps.Y(tg.p);
        out = `<rect class="dr-risk" x="${x1.toFixed(1)}" y="${Math.min(yE, yS).toFixed(1)}" width="${(right - x1).toFixed(1)}" height="${Math.abs(yS - yE).toFixed(1)}"/><rect class="dr-reward" x="${x1.toFixed(1)}" y="${Math.min(yE, yT).toFixed(1)}" width="${(right - x1).toFixed(1)}" height="${Math.abs(yT - yE).toFixed(1)}"/>${lab(x1 + 5, yE - 5, `${k.r === null ? 'n/a' : `${num(k.r, 2)}R`}, risk ${num(k.risk)}, reward ${num(k.reward)}`, 'dr-tb')}`;
      } else if (dr.kind === 'position') {
        const [e, st, bp] = q, k = positionSize(e, st, bp), x1 = X(Math.min(e.i, st.i)), yE = ps.Y(e.p), yS = ps.Y(st.p);
        out = `<rect class="dr-risk" x="${x1.toFixed(1)}" y="${Math.min(yE, yS).toFixed(1)}" width="${(right - x1).toFixed(1)}" height="${Math.abs(yS - yE).toFixed(1)}"/><line class="${cls} dr-dash" x1="${x1}" x2="${right}" y1="${pts[2].y}" y2="${pts[2].y}"/>${lab(x1 + 5, Math.min(yE, yS) - 5, `${num(k.shares, 0)} shares, ${num(k.perShare)} a share at risk, risk $${num(k.budget, 0)}`, 'dr-tb')}${lab(x1 + 5, pts[2].y - 4, `Budget line: $100 a dollar from the entry`)}`;
      } else out = `<line class="${cls} dr-other" x1="${a.x}" y1="${a.y}" x2="${b.x}" y2="${b.y}"><title>${esc(dr.kind)}</title></line>`;
    }
    return out + handles;
  }


  // The arrow nearest a point of the plot, within a bar and 22 px, or null.
  function flagAt(p) {
    if (!p || !layout) return null;
    let f = null, best = 22;
    flags.forEach((g) => { const dx = Math.abs(g.x - p.x), dy = Math.abs(g.y - p.y); if (dx <= Math.max(9, layout.bw / 2 + 3) && dy < best) { best = dy; f = g; } });
    return f;
  }
  // A press on an arrow (or Enter on its bar) opens the page's insider view for the stock, as Classic's markers did
  // (openInsidersFor, app.js:40316), where the page asks for it (`onInsider`)
  const openInsider = (f) => { if (f && S.onInsider) { S.onInsider({ side: f.side, items: f.items }); return true; } return false; };
  // The hover box: the arrow nearest the pointer, or with the keyboard the arrow on the crosshair's bar.
  function insiderTip() {
    let f = null;
    if (hoverP && !(drag && drag.moved)) f = flagAt(hoverP);
    else if (document.activeElement === svg && cross >= 0) f = flags.find((g) => g.i === cross) || null;
    if (!f) { tipEl.hidden = true; return; }
    const buy = f.side === 'buy', n = f.items.length, total = f.items.reduce((a, it) => a + (Number(it.value) || 0), 0);
    const day = f.items.every((it) => it.date === f.items[0].date) ? f.items[0].date : '';   // a weekly bar can hold several days
    const head = `<p class="pc-tip-h"><b class="${buy ? 'up' : 'down'}">${n === 1 ? `Insider ${buy ? 'purchase' : 'sale'}` : `${n} insider ${buy ? 'purchases' : 'sales'}`}</b>${day ? ` ${esc(day)}` : ''}</p>${n > 1 && total ? `<p class="t-muted">$${esc(compact(total))} in all</p>` : ''}`;
    const rows = f.items.slice(0, 4).map((it) => `<div class="pc-tip-r"><p><b>${esc(it.who)}</b>${it.role ? `, ${esc(it.role)}` : ''}</p><p>${esc([day ? '' : it.date, it.amount].filter(Boolean).join(', '))}</p>${it.note ? `<p class="t-muted">${esc(it.note)}</p>` : ''}</div>`).join('');
    tipEl.innerHTML = head + rows + (n > 4 ? `<p class="t-muted">And ${n - 4} more on this bar.</p>` : '') + (S.onInsider ? `<p class="t-muted">${touchy ? 'Tap the arrow' : 'Press it, or Enter'} to open the insider filings.</p>` : '');
    tipEl.hidden = false;
    // an <svg> has no offsetTop: its place in the host comes from the two boxes
    const r = svg.getBoundingClientRect(), hr = host.getBoundingClientRect(), z = cssZoom(hr), k = r.width / (W || 1) / z, top0 = (r.top - hr.top) / z, hw = host.clientWidth;
    const bw = tipEl.offsetWidth, bh = tipEl.offsetHeight, ax = f.x * k + (r.left - hr.left) / z, ay = f.y * k + top0;
    let left = ax + 14; if (left + bw > hw - 4) left = Math.max(4, ax - 14 - bw);
    // inside the plot, and inside the window when the plot runs past it
    const lo = Math.max(top0, (-hr.top + 72) / z) + 4, hi = Math.min(top0 + H * k, (window.innerHeight - hr.top) / z) - bh - 4;
    const top = Math.max(lo, Math.min(hi, ay - bh / 2));
    tipEl.style.left = `${Math.round(left)}px`; tipEl.style.top = `${Math.round(top)}px`;
  }
  function readout() {
    if (S.sync && !S.intraday) {
      const d = cross >= 0 && bars[cross] ? new Date(bars[cross].t).toISOString().slice(0, 10) : null;
      if (d !== told) { told = d; document.dispatchEvent(new CustomEvent('v2:xsync', { detail: { group: S.sync, d, src: SYNC_ID } })); }
    }
    insiderTip();
    const i = cross >= 0 ? cross : to, b = bars[i];
    if (!b) { read.textContent = ''; return; }
    // comparing: each line's change from the anchor and its close on this bar, or that it has no bar here
    const C = layout && layout.cmp;
    if (C) {
      read.innerHTML = `${S.title ? `<b class="pc-sym">${esc(S.title.sym)}</b> <span class="pc-what">Percent from ${esc(fmtT(bars[C.ai].t))}</span> ` : ''}<b>${esc(fmtT(b.t))}</b> ${C.lines.map((l) => `<span class="cm-r ${l.cls}"><b>${esc(l.sym)}</b> ${Number.isFinite(l.pct[i]) ? `${signed(l.pct[i], 1)} <span class="cm-px">(${num(l.closes[i])})</span>` : 'no bar this day'}</span>`).join(' ')}`;
      return;
    }
    const prev = bars[i - 1], chg = prev ? (b.c / prev.c - 1) * 100 : null;
    const filed = fileMarks.filter((m) => m.i === i).map((m) => m.f.form);
    read.innerHTML = `${S.title ? `<b class="pc-sym">${esc(S.title.sym)}</b> <span class="pc-what">${esc(S.title.what)}</span> ` : ''}<b>${esc(fmtT(b.t))}</b> <span>O ${num(b.o)}</span> <span>H ${num(b.h)}</span> <span>L ${num(b.l)}</span> <span>C ${num(b.c)}</span>${chg !== null ? ` <span class="${chg >= 0 ? 'up' : 'down'}">${chg >= 0 ? '+' : '−'}${num(Math.abs(chg))}%</span>` : ''}${b.v ? ` <span class="t-muted">Vol ${num(b.v / 1e6, 1)}M</span>` : ''}${filed.length ? ` <span class="pc-fil">${esc(filed.join(', '))} filed</span>` : ''}`;
  }
  function summary() {
    const a = bars[from], b = bars[to]; if (!a || !b) return 'Price chart';
    const C = layout && layout.cmp;
    if (C) {
      const at = (l) => { for (let k = to; k >= from; k--) if (Number.isFinite(l.pct[k])) return `${l.sym} ${signed(l.pct[k], 1)}`; return `${l.sym} no bars in view`; };
      return `Comparison in percent from ${fmtT(bars[C.ai].t)}, ${fmtT(a.t)} to ${fmtT(b.t)}: ${C.lines.map(at).join(', ')}. Left and right read each bar.`;
    }
    const ch = (b.c / a.c - 1) * 100;
    const breaks = S.overlays.msb ? ind.msb.filter((m) => m.at >= from && m.at <= to) : [];
    const last = breaks[breaks.length - 1];
    const msb = S.overlays.msb ? (last ? ` ${breaks.length} market structure break${breaks.length === 1 ? '' : 's'} in view; the latest is ${last.dir === 'bull' ? 'bullish' : 'bearish'}, on ${fmtT(bars[last.at].t)} through ${num(last.price)}.` : ' No market structure break in view.') : '';
    const ins = (flags.length ? ` ${flags.reduce((a, g) => a + g.items.length, 0)} insider trades marked.` : '') + (fileMarks.length ? ` ${fileMarks.length} SEC filing${fileMarks.length === 1 ? '' : 's'} marked.` : '');
    return `${S.label || 'Price'}, ${to - from + 1} bars from ${fmtT(a.t)} to ${fmtT(b.t)}: from ${num(a.c)} to ${num(b.c)}, ${ch >= 0 ? 'up' : 'down'} ${num(Math.abs(ch), 1)} percent.${msb}${ins} Left and right read each bar, up and down stretch the price scale, plus and minus zoom, M measures.`;
  }
  const redraw = () => { if (!raf) raf = requestAnimationFrame(draw); };

  /* ---------- legend (the classic chart's; the page keeps it open or folded in optic.chart.legend.v1) ---------- */
  // A row for each overlay on the price, keyed in the colour it is drawn in, with its value at the crosshair's
  // bar (the last bar shown otherwise); folded, the count alone. The rows are rebuilt only when what they list
  // changes, so a hover never replaces a button under the pointer; the values are written in place.
  const LINES = { ma: [['sma20', 'm1', 'SMA 20'], ['sma50', 'm2', 'SMA 50'], ['sma200', 'm3', 'SMA 200']], ema: [['ema9', 'e1', 'EMA 9'], ['ema21', 'e2', 'EMA 21'], ['ema50', 'e3', 'EMA 50']] };
  const ARROW = (cls, d) => `<svg class="pc-la ${cls}" viewBox="0 0 12 14" aria-hidden="true"><path d="${d}"/></svg>`;
  const KEY = {
    bb: '<i class="o2"></i>', fib: '<i class="kfib"></i>', sr: '<i class="ksup"></i><i class="kres"></i>', gex: '<i class="kgex"></i>',
    msb: '<i class="kbull"></i><i class="kbear"></i>', events: '<b class="kE">E</b>', volume: '<i class="kvol"></i>',
    cloud921: '<i class="kcu"></i><i class="kcd"></i>', cloud2150: '<i class="kcu"></i><i class="kcd"></i>', keltner: '<i class="kkc"></i>', donchian: '<i class="kdc"></i>', sec: '<i class="krc"></i>', vwap: '<i class="kvw"></i>',
    zones: '<i class="kzs"></i><i class="kzd"></i>', accum: '<i class="kacc"></i>', trends: '<i class="ktu"></i><i class="ktd"></i>', vbp: '<i class="kvbp"></i>', sessions: '<i class="ksd"></i>',
    stages: '<i class="kst1"></i><i class="kst2"></i><i class="kst3"></i><i class="kst4"></i>', matrend: '<i class="kmt1"></i><i class="kmt0"></i><i class="kmt4"></i>',
  };
  const VALUE = { bb: 'bb', msb: 'msb' };
  const lid = `pc-lb-${++legendSeq}`;
  leg.innerHTML = `<button type="button" class="pc-lt" aria-controls="${lid}">${icon('chev').s}<span></span></button><div class="pc-lb" id="${lid}"></div>`;
  const legT = leg.querySelector('.pc-lt'), legB = leg.querySelector('.pc-lb');
  let legSig = '';
  function legend() {
    if (!S.names) return;
    const keys = legendKeys(S.names, S.overlays, S.panes), open = !!S.legendOpen, nd = S.drawings.length, sig = JSON.stringify([keys, open, nd]);
    if (sig !== legSig) {
      legSig = sig;
      const names = S.names || {}, n = keys.length;
      legT.setAttribute('aria-expanded', String(open));
      legT.title = `${open ? 'Fold' : 'Open'} the legend`;
      legT.lastChild.textContent = `${n ? `${n} overlay${n === 1 ? '' : 's'}` : 'No overlays'}${nd ? `, ${nd} drawing${nd === 1 ? '' : 's'}` : ''}`;
      legB.hidden = !open;
      legB.innerHTML = !open ? '' : (keys.map((k) => {
        const name = esc(names[k]);
        const what = LINES[k] ? `<span class="pc-ln">${LINES[k].map(([id, c, l]) => `<span class="pc-li"><i class="${c}"></i>${l} <b data-lv="${id}"></b></span>`).join('')}</span>`
          : k === 'ins' ? `<span class="pc-ln"><span class="pc-li">${name}</span><span class="pc-li">${ARROW('buy', 'M6 0 12 7H7.5v7h-3V7H0Z')}purchase</span><span class="pc-li">${ARROW('sell', 'M6 14 0 7h4.5V0h3v7H12Z')}sale</span></span>`
            : `<span class="pc-ln"><span class="pc-li">${KEY[k] || ''}${name}${VALUE[k] ? ` <b data-lv="${VALUE[k]}"></b>` : ''}</span></span>`;
        return `<div class="pc-lr">${what}<button type="button" class="pc-lx" data-pc-off="${esc(k)}" aria-label="Remove ${name}" title="Remove ${name}">${icon('close').s}</button></div>`;
      }).join('') || '<p class="pc-le">Nothing on the price. Add an overlay from Indicators.</p>');
    }
    if (!open) return;
    const i = cross >= 0 ? cross : to;
    legB.querySelectorAll('[data-lv]').forEach((el) => {
      const id = el.dataset.lv;
      let t;
      if (id === 'bb') t = Number.isFinite(ind.bb.up[i]) ? `upper ${num(ind.bb.up[i])}, lower ${num(ind.bb.dn[i])}` : 'not enough bars';
      else if (id === 'msb') t = `${ind.msb.filter((m) => m.at >= from && m.at <= to).length} in view`;
      else t = Number.isFinite(ind[id][i]) ? num(ind[id][i]) : 'not enough bars';
      if (el.textContent !== t) el.textContent = t;
    });
  }
  leg.addEventListener('click', (e) => {
    const off = e.target.closest('[data-pc-off]');
    if (off) { legT.focus(); if (S.onRemove) S.onRemove(off.dataset.pcOff); return; }
    if (e.target.closest('.pc-lt')) { S.legendOpen = !S.legendOpen; if (S.onLegend) S.onLegend(S.legendOpen); legend(); }
  });

  /* ---------- navigator (the classic chart's overview strip) ---------- */
  // The whole series drawn small under the plot, across the plot's own width, with the bars on screen marked.
  // Drag the window to move along, drag an edge to show more or fewer bars, press outside it to jump there.
  // The line is built once for a width; a move only redraws the window.
  let navBase = null, ndrag = null;
  const navGeo = () => { const x0 = layout.l, x1 = W - layout.r, w = Math.max(1, x1 - x0); return { x0, x1, w, X: (i) => x0 + (N > 1 ? i / (N - 1) : 0) * w, I: (x) => Math.round(((x - x0) / w) * (N - 1)) }; };
  function drawNav() {
    if (!S.navigator) return;
    const NH = S.navH || 40, g = navGeo();
    if (!navBase || navBase.W !== W || navBase.NH !== NH) {
      let lo = Infinity, hi = -Infinity;
      closes.forEach((c) => { if (c < lo) lo = c; if (c > hi) hi = c; });
      const Y = (v) => NH - 4 - ((v - lo) / ((hi - lo) || 1)) * (NH - 10);
      const step = N > g.w * 2 ? N / g.w : 1;   // about one point a pixel on a long history
      let d = '';
      for (let k = 0; k < N; k += step) { const i = Math.min(N - 1, Math.round(k)); d += `${d ? 'L' : 'M'}${g.X(i).toFixed(1)} ${Y(closes[i]).toFixed(1)}`; }
      d += `L${g.X(N - 1).toFixed(1)} ${Y(closes[N - 1]).toFixed(1)}`;
      navBase = { W, NH, s: `<rect class="nv-bg" x="${g.x0}" y="0.5" width="${g.w.toFixed(1)}" height="${NH - 1}" rx="4"/><path class="nv-area" d="${d}L${g.x1.toFixed(1)} ${NH - 1}L${g.x0} ${NH - 1}Z"/><path class="nv-line" d="${d}"/>` };
      nav.setAttribute('viewBox', `0 0 ${W} ${NH}`); nav.setAttribute('width', W); nav.setAttribute('height', NH);
    }
    const a = g.X(from), b = Math.max(a + 6, g.X(to)), gh = Math.round(NH * 0.44), gy = ((NH - gh) / 2).toFixed(1);
    nav.innerHTML = navBase.s
      + `<rect class="nv-mask" x="${g.x0}" y="0.5" width="${Math.max(0, a - g.x0).toFixed(1)}" height="${NH - 1}"/><rect class="nv-mask" x="${b.toFixed(1)}" y="0.5" width="${Math.max(0, g.x1 - b).toFixed(1)}" height="${NH - 1}"/>`
      + `<rect class="nv-win" x="${a.toFixed(1)}" y="1" width="${(b - a).toFixed(1)}" height="${NH - 2}" rx="3"/>`
      + `<rect class="nv-grip" x="${(a - 2).toFixed(1)}" y="${gy}" width="4" height="${gh}" rx="2"/><rect class="nv-grip" x="${(b - 2).toFixed(1)}" y="${gy}" width="4" height="${gh}" rx="2"/>`;
    nav.setAttribute('aria-valuemax', String(N)); nav.setAttribute('aria-valuenow', String(to + 1));
    nav.setAttribute('aria-valuetext', `${fmtT(bars[from].t)} to ${fmtT(bars[to].t)}, ${to - from + 1} of ${N} bars`);
  }
  const setView = (v) => { from = v.from; to = v.to; redraw(); };
  const navX = (e) => { const r = nav.getBoundingClientRect(); return (e.clientX - r.left) * (W / (r.width || 1)); };
  function navMode(x, touch) {
    const g = navGeo(), a = g.X(from), b = Math.max(a + 6, g.X(to)), grab = touch ? 16 : 8, inner = Math.min(grab, (b - a) / 3);
    if (x > a + inner && x < b - inner) return 'move';
    if (Math.abs(x - a) <= grab && Math.abs(x - a) <= Math.abs(x - b)) return 'from';
    if (Math.abs(x - b) <= grab) return 'to';
    return 'jump';
  }
  nav.addEventListener('pointerdown', (e) => {
    if (e.pointerType === 'mouse' && e.button !== 0) return;
    if (e.button !== 0) return;
    e.preventDefault();
    try { nav.setPointerCapture(e.pointerId); } catch (err) { /* a pointer the browser no longer tracks */ }
    const x = navX(e), g = navGeo();
    let mode = navMode(x, e.pointerType === 'touch');
    // a press outside the window centres it there, and the same press can go on to drag it
    if (mode === 'jump') { const half = Math.floor((to - from + 1) / 2); setView(navWindow('move', { from, to }, g.I(x) - half - from, N)); mode = 'move'; }
    ndrag = { mode, x, from, to, per: (N - 1) / g.w };
    nav.dataset.drag = mode;
  });
  nav.addEventListener('pointermove', (e) => {
    if (ndrag && e.pointerType === 'mouse' && e.buttons === 0) { ndrag = null; delete nav.dataset.drag; return; }
    const x = navX(e);
    if (!ndrag) { nav.dataset.hover = navMode(x, e.pointerType === 'touch'); return; }
    setView(navWindow(ndrag.mode, ndrag, Math.round((x - ndrag.x) * ndrag.per), N));
  });
  const navUp = () => { ndrag = null; delete nav.dataset.drag; };
  nav.addEventListener('pointerup', navUp); nav.addEventListener('pointercancel', navUp); nav.addEventListener('lostpointercapture', navUp);
  // a slider for the keyboard: arrows move a tenth of the view, Page Up and Page Down a whole view, Home and End
  // go to the ends, plus and minus show fewer or more bars
  nav.addEventListener('keydown', (e) => {
    const span = to - from + 1, step = Math.max(1, Math.round(span / 10)), k = e.key, mid = Math.round((from + to) / 2);
    const d = { ArrowLeft: -step, ArrowDown: -step, ArrowRight: step, ArrowUp: step, PageDown: -span, PageUp: span, Home: -from, End: N - 1 - to }[k];
    if (d !== undefined) { e.preventDefault(); setView(navWindow('move', { from, to }, d, N)); return; }
    if (k === '+' || k === '=') { e.preventDefault(); zoom(1 / 1.25, mid); } else if (k === '-' || k === '_') { e.preventDefault(); zoom(1.25, mid); }
  });

  /* ---------- view changes ---------- */
  function zoom(factor, anchor = null) {
    const span = to - from + 1, ns = Math.max(10, Math.min(N, Math.round(span * factor)));
    const a = anchor === null ? to : anchor, ratio = (a - from) / Math.max(1, span - 1);
    from = Math.round(a - ratio * (ns - 1)); to = from + ns - 1;
    if (to > N - 1) { to = N - 1; from = Math.max(0, to - ns + 1); } if (from < 0) { from = 0; to = Math.min(N - 1, ns - 1); }
    redraw();
  }
  function pan(d) { const span = to - from; from = Math.max(0, Math.min(N - 1 - span, from + d)); to = from + span; redraw(); }
  const fit = () => { from = 0; to = N - 1; yZoom = 1; redraw(); };

  /* ---------- pointer, touch and wheel (docs/frontend-v2/CHART-GESTURES.md) ---------- */
  const pt = (e) => { const r = svg.getBoundingClientRect(); return { x: (e.clientX - r.left) * (W / r.width), y: (e.clientY - r.top) * (H / r.height) }; };
  const idx = (p) => Math.max(from, Math.min(to, layout.I(p.x)));
  const plotFx = (x) => Math.max(0, Math.min(1, (x - layout.l) / Math.max(1, W - layout.l - layout.r)));
  const onScale = (p) => !!layout && p.x > W - layout.r && p.y >= layout.panes[0].y0 && p.y <= layout.panes[0].y1;
  const setWin = (w) => { from = w.from; to = w.to; };
  const readAt = (p) => { cross = idx(p); crossY = p.y <= layout.panes[0].y1 ? layout.ps.P(p.y) : null; };
  const pointers = new Map();
  function down(e) {
    // only the main button pans, draws or selects: a right click opened the browser's menu, which swallowed the
    // release, and the chart then panned with the mouse and no button held (owner, 2026-10-20)
    if (e.pointerType === 'mouse' && e.button !== 0) return;
    if (!layout) return;
    try { svg.setPointerCapture(e.pointerId); } catch (err) { /* a pointer the browser no longer tracks */ }
    const p = pt(e);
    pointers.set(e.pointerId, p);
    hoverP = p;   // a tap on an arrow opens its box on a touch screen
    touchy = e.pointerType === 'touch' || e.pointerType === 'pen';
    if (touchy) { touchDown(e, p); return; }
    if (S.tool !== 'select' && !cmpOn()) { place(p); return; }
    if (onScale(p)) { drag = { mode: 'scale', cy: e.clientY, z: yZoom }; svg.dataset.drag = 'scale'; return; }
    // on the selected drawing's handle: move that point; Shift or Measure: measure; on a drawing: select it and
    // move it all; else pan
    const h = handleAt(p);
    if (h >= 0) { drag = { mode: 'handle', k: sel, h, before: S.drawings, moved: false }; return; }
    if (e.shiftKey || mOn) { ms = { a: idx(p), b: idx(p) }; drag = { mode: 'measure' }; redraw(); return; }
    ms = null;
    const hit = hitTest(p);
    sel = hit; if (S.onSelect) S.onSelect(hit >= 0 ? S.drawings[hit] : null); syncTouch(); changed();
    drag = hit >= 0 ? { mode: 'body', k: hit, x: p.x, y: p.y, pts: S.drawings[hit].points, before: S.drawings, moved: false } : { mode: 'pan', x: p.x, from, moved: false };
    redraw();
  }
  // A tool placing points: a press puts one down, and a drag from it puts the next where it lifts (a two-point
  // shape in one drag), or the next press does.
  function place(p) {
    if (!pending) pending = { kind: S.tool, points: [] };
    const at = pointAt(p);
    pending.points.push({ t: at.t, p: at.p });
    if (pending.points.length >= TOOL_POINTS[S.tool]) { finishDrawing(); drag = null; } else drag = { mode: 'place', x: p.x, y: p.y, n: pending.points.length, moved: false };
    redraw();
  }
  // One finger: a tap reads the bar; sideways first pans, up or down first is the page's scroll (the svg keeps
  // pan-y), decided over the first 8 px; held still 300 ms, it reads the bars as it moves and the page holds still.
  // Two fingers pinch about their midpoint, and moving both pans; held, then a second finger, measures.
  function touchDown(e, p) {
    document.documentElement.classList.add('pc-touching');   // iOS's long press would select text and show its loupe
    if (pointers.size === 2) {
      if (!tg || tg.mode === 'page' || tg.mode === 'cancelled') return;
      clearTimeout(tg.hold);
      const [a, b] = [...pointers.values()];
      cross = -1; crossY = null;
      if (tg.held || mOn) { tg.mode = 'measure'; ms = { a: idx(a), b: idx(b) }; drag = { mode: 'measure' }; redraw(); return; }
      const span = to - from + 1, fx = plotFx((a.x + b.x) / 2);
      tg.mode = 'pinch'; tg.pinch = { a, b, span, abs: from + fx * Math.max(0, span - 1) }; drag = null; redraw(); return;
    }
    if (pointers.size > 2) return;
    tg = { mode: 'wait', x0: e.clientX, y0: e.clientY, p0: p, held: false, locked: false, hold: 0 };
    if (onScale(p)) { tg.mode = 'scale'; drag = { mode: 'scale', cy: e.clientY, z: yZoom }; cross = -1; crossY = null; return; }
    if (mOn && S.tool === 'select') { tg.mode = 'measure1'; ms = { a: idx(p), b: idx(p) }; drag = { mode: 'measure' }; cross = -1; crossY = null; redraw(); return; }
    readAt(p);
    if (S.tool !== 'select' && !cmpOn()) { tg.mode = 'place'; place(p); return; }
    const h = handleAt(p);
    if (h >= 0) { tg.mode = 'draw'; drag = { mode: 'handle', k: sel, h, before: S.drawings, moved: false }; redraw(); return; }
    const hit = hitTest(p);
    if (hit >= 0 || sel >= 0) { sel = hit; if (S.onSelect) S.onSelect(hit >= 0 ? S.drawings[hit] : null); syncTouch(); changed(); }
    if (hit >= 0) { tg.mode = 'draw'; drag = { mode: 'body', k: hit, x: p.x, y: p.y, pts: S.drawings[hit].points, before: S.drawings, moved: false }; redraw(); return; }
    ms = null;
    tg.mode = to - from + 1 < N ? 'wait' : 'scrub';   // with every bar shown there is nothing to pan: sideways reads
    const t = tg;
    t.hold = setTimeout(() => { if (tg === t && !t.locked && (t.mode === 'wait' || t.mode === 'scrub')) { t.held = true; t.mode = 'hold'; } }, 300);
    redraw();
  }
  function touchMove(e, p) {
    const t = tg;
    if (t.mode === 'pinch') {
      if (pointers.size < 2) return;
      const [a, b] = [...pointers.values()], q = t.pinch;
      const d0 = Math.hypot(q.b.x - q.a.x, q.b.y - q.a.y), d1 = Math.hypot(b.x - a.x, b.y - a.y);
      setWin(zoomedAt(q.abs, plotFx((a.x + b.x) / 2), q.span / (d0 > 0 && d1 > 0 ? d1 / d0 : 1), N)); redraw(); return;
    }
    if (t.mode === 'measure') { if (pointers.size === 2) { const [a, b] = [...pointers.values()]; ms = { a: idx(a), b: idx(b) }; redraw(); } return; }
    if ((t.mode === 'wait' || t.mode === 'scrub') && !t.locked) {
      const lock = touchLock(e.clientX - t.x0, e.clientY - t.y0);
      if (!lock) return;
      t.locked = true; clearTimeout(t.hold);
      if (lock === 'y') { t.mode = 'page'; cross = -1; crossY = null; hoverP = null; redraw(); return; }   // the page's scroll
      if (t.mode === 'wait') { t.mode = 'pan'; cross = -1; crossY = null; drag = { mode: 'pan', x: t.p0.x, from, moved: true }; }
    }
    if (t.mode === 'scrub' || t.mode === 'hold') { readAt(p); redraw(); return; }
    if (t.mode === 'measure1') { if (ms) ms.b = idx(p); redraw(); return; }
    if (t.mode === 'place') { dragMove(e, p); readAt(p); redraw(); return; }
    if (t.mode === 'pan' || t.mode === 'scale' || t.mode === 'draw') { dragMove(e, p); redraw(); }
  }
  function dragMove(e, p) {
    if (!drag) return;
    if (drag.mode === 'scale') { yZoom = Math.max(0.25, Math.min(8, drag.z * Math.exp((drag.cy - e.clientY) / 160))); return; }
    if (drag.mode === 'measure') { if (ms) ms.b = idx(p); return; }
    if (drag.mode === 'place') { if (Math.hypot(p.x - drag.x, p.y - drag.y) > (touchy ? 8 : 4)) drag.moved = true; return; }
    if (drag.mode === 'handle') { const at = pointAt(p), dr = S.drawings[drag.k]; S.drawings = S.drawings.map((x, j) => (j === drag.k ? Object.assign({}, dr, { points: dr.points.map((q, n) => (n === drag.h ? { t: at.t, p: at.p } : q)) }) : x)); drag.moved = true; return; }
    if (drag.mode === 'body') { const di = Math.round((p.x - drag.x) / layout.bw), dp = layout.ps.P(p.y) - layout.ps.P(drag.y); if (Math.abs(p.x - drag.x) > (touchy ? 8 : 3) || Math.abs(p.y - drag.y) > (touchy ? 8 : 3)) { drag.moved = true; S.drawings = S.drawings.map((x, j) => (j === drag.k ? Object.assign({}, x, { points: moved(drag.pts, di, dp, AX) }) : x)); } return; }
    if (drag.mode === 'pan') {
      const dx = p.x - drag.x;
      if (!drag.moved && Math.abs(dx) <= 3) return;   // a few pixels of slack before a press becomes a pan
      drag.moved = true; svg.dataset.drag = 'pan';
      const span = to - from; from = Math.max(0, Math.min(N - 1 - span, drag.from - Math.round(dx / layout.bw))); to = from + span;
    }
  }
  function move(e) {
    // a mouse with no button down is not dragging, whatever release went missing (a menu, another window, a lost
    // capture): end the drag here rather than pan with the cursor
    if (e.pointerType === 'mouse' && e.buttons === 0 && (drag || pointers.has(e.pointerId))) up(e);
    if (!layout) return;
    const p = pt(e);
    if (pointers.has(e.pointerId)) { pointers.set(e.pointerId, p); if (!svg.hasPointerCapture(e.pointerId)) { try { svg.setPointerCapture(e.pointerId); } catch (err) { /* no longer active */ } } }
    hoverP = p;
    if (e.pointerType !== 'mouse' && tg && pointers.has(e.pointerId)) { touchMove(e, p); return; }
    if (!drag && S.onInsider) svg.style.cursor = flagAt(p) ? 'pointer' : '';
    dragMove(e, p);
    // the crosshair follows the pointer, except while it stretches the scale or measures (the band is the reading)
    if (drag && (drag.mode === 'scale' || drag.mode === 'measure')) { cross = -1; crossY = null; } else readAt(p);
    redraw();
  }
  function up(e) {
    const had = pointers.delete(e.pointerId), touch = e.pointerType !== 'mouse';
    if (touch && tg && had) {
      if (e.type === 'pointercancel') { endTouch(true); return; }
      if (pointers.size === 1) {
        // the finger left over from a pinch pans from where it is; one lifted from a measurement leaves it read
        if (tg.mode === 'pinch') { const [rest] = [...pointers.values()]; tg.mode = 'pan'; drag = { mode: 'pan', x: rest.x, from, moved: true }; }
        else if (tg.mode === 'measure') { finishMeasure(); tg.mode = 'hold'; drag = null; }
        return;
      }
      if (pointers.size) return;
    }
    if (touch && tg && !tg.locked && !tg.held && (tg.mode === 'wait' || tg.mode === 'scrub') && openInsider(flagAt(tg.p0))) { drag = null; endTouch(false); return; }
    if (!touch && drag && drag.mode === 'pan' && !drag.moved && layout && openInsider(flagAt(pt(e)))) { drag = null; return; }
    if (drag) {
      // a drawing moved is one change to undo, kept when the pointer lifts
      if ((drag.mode === 'handle' || drag.mode === 'body') && drag.moved) { undo.push(drag.before); if (undo.length > 40) undo.shift(); redo.length = 0; if (S.onDrawings) S.onDrawings(S.drawings); }
      else if (drag.mode === 'place' && drag.moved && pending && pending.points.length === drag.n && layout) { const at = pointAt(pt(e)); pending.points.push({ t: at.t, p: at.p }); if (pending.points.length >= TOOL_POINTS[pending.kind]) finishDrawing(); }
      else if (drag.mode === 'measure') finishMeasure();
    }
    drag = null; delete svg.dataset.drag;
    if (touch) endTouch(false);
    redraw();
  }
  function endTouch(cancelled) {
    if (tg) clearTimeout(tg.hold);
    if (cancelled) {
      // a cancel is the page's scroll taking the finger: the reading it started goes with it, and a drawing half
      // moved goes back
      if (tg && ['wait', 'page', 'scrub', 'hold'].includes(tg.mode)) { cross = -1; crossY = null; hoverP = null; }
      if (drag && (drag.mode === 'handle' || drag.mode === 'body') && drag.moved) S.drawings = drag.before;
      if (drag && drag.mode === 'measure') finishMeasure();
      drag = null; delete svg.dataset.drag;
    }
    tg = null; pointers.clear();
    document.documentElement.classList.remove('pc-touching');
    redraw();
  }
  function finishMeasure() { if (ms && ms.a !== ms.b) { const r = measuredBars(bars, ms.a, ms.b, fmtT); live.textContent = `Measured ${r.span}: ${r.head}.`; } }
  // Escape mid-drag puts things back: a drawing where it was, the view, the price scale; a measurement goes
  function cancelDrag() {
    if (!drag || drag.mode === 'cancelled') return false;
    if ((drag.mode === 'handle' || drag.mode === 'body') && drag.moved) S.drawings = drag.before;
    else if (drag.mode === 'pan') { const w = to - from; from = drag.from; to = from + w; }
    else if (drag.mode === 'scale') yZoom = drag.z;
    else if (drag.mode === 'measure') ms = null;
    else if (drag.mode === 'place') pending = null;
    drag = { mode: 'cancelled' }; if (tg) tg.mode = 'cancelled';   // nothing more until the pointer lifts
    delete svg.dataset.drag; redraw(); return true;
  }
  function setMeasure(on) {
    mOn = !!on; if (!mOn) ms = null;
    host.classList.toggle('is-measuring', mOn);
    const b = host.querySelector('[data-pc-measure]'); if (b) b.setAttribute('aria-pressed', String(mOn));
    syncTouch(); redraw();
  }
  [svg, scaleEl].forEach((el) => el.addEventListener('pointerdown', down));
  svg.addEventListener('pointermove', move);
  // the price scale's strip carries its own drag when the svg could not take the pointer from it
  scaleEl.addEventListener('pointermove', (e) => { if (!svg.hasPointerCapture(e.pointerId)) move(e); });
  ['pointerup', 'pointercancel'].forEach((t) => scaleEl.addEventListener(t, (e) => { if (!svg.hasPointerCapture(e.pointerId)) up(e); }));
  svg.addEventListener('pointerup', up); svg.addEventListener('pointercancel', up);
  // a capture lost with the button still down is not a release (headless Chrome drops it at the first move after a
  // press on the bare plot); one lost with nothing held is the release that went missing
  svg.addEventListener('lostpointercapture', (e) => { if (pointers.has(e.pointerId) && e.pointerType === 'mouse' && e.buttons === 0) up(e); });
  // a finger lifting also leaves: the box it opened stays until the next touch
  svg.addEventListener('pointerleave', (e) => { if (e.pointerType !== 'mouse') return; hoverP = null; if (!drag) { cross = -1; crossY = null; if (ms && !mOn && !ms.key) ms = null; redraw(); } });
  // once a hold, a pinch, a pan, a measurement or a drawing has the finger, the page holds still; before a direction
  // is decided it does not, so a swipe up or down still scrolls
  const HELD = ['hold', 'pinch', 'measure', 'measure1', 'pan', 'scale', 'draw', 'place', 'cancelled'];
  svg.addEventListener('touchmove', (e) => { if (tg && (HELD.includes(tg.mode) || (tg.mode === 'scrub' && tg.locked))) e.preventDefault(); }, { passive: false });
  svg.addEventListener('touchstart', (e) => { if (e.touches.length > 1) e.preventDefault(); }, { passive: false });
  ['contextmenu', 'selectstart'].forEach((t) => svg.addEventListener(t, (e) => { if (tg || drag) e.preventDefault(); }));
  // the price scale: drag up to stretch the prices, down to squeeze them; a double press fits them to the bars
  scaleEl.addEventListener('dblclick', (e) => { e.preventDefault(); yZoom = 1; redraw(); });
  svg.addEventListener('dblclick', (e) => { if (layout && onScale(pt(e))) { yZoom = 1; redraw(); } });
  // Safari's trackpad pinch: gesture events with a scale from the pinch's start (no ctrl + wheel), which would
  // otherwise zoom the whole page. A pinch of two fingers on a phone is the touch handler's, so these stand aside.
  let gst = null;
  svg.addEventListener('gesturestart', (e) => { e.preventDefault(); if (tg || !layout) return; const r = svg.getBoundingClientRect(), fx = plotFx((e.clientX - r.left) * (W / (r.width || 1))); gst = { span: to - from + 1, abs: from + fx * (to - from), fx }; }, { passive: false });
  svg.addEventListener('gesturechange', (e) => { e.preventDefault(); if (!gst || tg) return; const sc = Number(e.scale); if (!(sc > 0)) return; setWin(zoomedAt(gst.abs, gst.fx, gst.span / sc, N)); redraw(); }, { passive: false });
  svg.addEventListener('gestureend', (e) => { e.preventDefault(); gst = null; }, { passive: false });
  // the wheel: one listener for every chart on the page (onDocWheel), so each gesture has one owner
  const acc = { z: 0, p: 0, abs: NaN, fx: 0.5, x: NaN, win: null, raf: 0 };
  const wheelHandle = {
    host,
    over: (e) => !!layout && (svg.contains(e.target) || scaleEl.contains(e.target)),
    room: (e) => wheelRoom(e, to - from + 1, N),
    wheel(e) {
      if (gst) return;
      const dx = wheelPx(e.deltaX, e.deltaMode), dy = wheelPx(e.deltaY, e.deltaMode);
      // the point to zoom about, held while the pointer stays still and nothing else moves the window, so a run of
      // notches does not slide the chart sideways under it
      const r = svg.getBoundingClientRect(), fx = plotFx((e.clientX - r.left) * (W / (r.width || 1)));
      const ours = acc.win && acc.win.from === from && acc.win.to === to, still = Math.abs(e.clientX - acc.x) <= 1;
      if (!(ours && still && Number.isFinite(acc.abs))) { acc.abs = from + fx * Math.max(0, to - from); acc.fx = fx; acc.x = e.clientX; acc.win = { from, to }; }
      if (e.ctrlKey) acc.z += dy * PINCH_PER_PX;
      else if (e.shiftKey) acc.p += dx || dy;
      else if (Math.abs(dx) > Math.abs(dy)) acc.p += dx;
      else acc.z += dy * ZOOM_PER_PX;
      if (!acc.raf) acc.raf = requestAnimationFrame(flushWheel);
    },
  };
  // gathered per frame: redrawing on each of sixty events a second is what makes a smooth gesture judder
  function flushWheel() {
    acc.raf = 0;
    if (!layout) return;
    const span = to - from + 1, lo = Math.min(MIN_BARS, N);
    if (acc.z) {
      const want = Math.max(lo, Math.min(N, Math.round(span * Math.exp(acc.z))));
      if (want !== span) { setWin(zoomedAt(acc.abs, acc.fx, want, N)); acc.z -= Math.log(want / span); }
      if (want === lo || want === N) acc.z = 0;   // at a limit, carrying the rest would make the first move back feel stuck
    }
    if (acc.p) {
      const r = svg.getBoundingClientRect(), perPx = 1 / (layout.bw * ((r.width || W) / W)), n = Math.trunc(acc.p * perPx);
      if (n) { const w = to - from; from = Math.max(0, Math.min(N - 1 - w, from + n)); to = from + w; acc.p -= n / perPx; acc.abs += n; }
    }
    acc.win = { from, to };
    redraw();
  }
  registerChart(wheelHandle);
  // undo, redo and Delete from anywhere on the page that asked (`pageKeys`, its scope), never from a field, an open
  // menu or another widget; and Escape mid-drag wherever focus is (Classic's app.js:28680-28709)
  const pageKey = (e) => {
    if (e.defaultPrevented || !host.isConnected || document.activeElement === svg) return;
    if (e.key === 'Escape') { if (drag && cancelDrag()) e.preventDefault(); return; }
    if (!S.pageKeys || !keyIsFree(document.activeElement, S.pageKeys)) return;
    const k = e.key, meta = e.metaKey || e.ctrlKey;
    if (meta && !e.altKey && k.toLowerCase() === 'z') { e.preventDefault(); if (e.shiftKey) redoOne(); else undoOne(); }
    else if (meta && !e.altKey && k.toLowerCase() === 'y') { e.preventDefault(); redoOne(); }
    else if ((k === 'Delete' || k === 'Backspace') && !meta && sel >= 0) { e.preventDefault(); commit(S.drawings.filter((_, j) => j !== sel)); sel = -1; }
  };
  document.addEventListener('keydown', pageKey);
  host.addEventListener('click', (e) => {
    const b = e.target.closest('[data-pc-zoom], [data-pc-measure], [data-pc-pane], [data-pc-home]');
    if (!b || !host.contains(b)) return;
    if (b.hasAttribute('data-pc-home')) { home(); return; }
    if (b.dataset.pcZoom) { zoom(b.dataset.pcZoom === 'in' ? 1 / 1.5 : 1.5, to); return; }   // about the latest bar shown
    if (b.hasAttribute('data-pc-measure')) { setMeasure(!mOn); return; }
    if (b.dataset.pcPane && S.onRemove) S.onRemove(b.dataset.pcPane);
  });

  // The drawing under the pointer, or -1: within 9 px of a line, or inside a box or a measured range.
  function hitTest(p) {
    const ps = layout.ps, X = layout.X, right = W - layout.r, last = N - 1;
    let best = -1, bd = touchy ? 20 : 9;   // a finger's tap is wider than a pointer's
    const segD = (g) => segDist(p.x, p.y, X(g.i1), ps.Y(g.p1), X(g.i2), ps.Y(g.p2));
    const inBox = (x1, x2, y1, y2) => (p.x >= Math.min(x1, x2) - 4 && p.x <= Math.max(x1, x2) + 4 && p.y >= Math.min(y1, y2) - 4 && p.y <= Math.max(y1, y2) + 4 ? 0 : Infinity);
    S.drawings.forEach((dr, k) => {
      const q = dr.points.map((x) => ({ i: AX.f(x.t), p: x.p })), pts = q.map((x) => ({ x: X(x.i), y: ps.Y(x.p) }));
      let d = Infinity;
      if (dr.kind === 'hline' || dr.kind === 'fibdraw') d = Math.min(...pts.map((x) => Math.abs(x.y - p.y)));
      else if (dr.kind === 'vline') d = Math.abs(pts[0].x - p.x);
      else if (dr.kind === 'text') d = Math.hypot(pts[0].x - p.x, pts[0].y - p.y) / 2;
      else if (pts.length > 1) {
        const [a, b] = pts;
        if (dr.kind === 'rect') d = inBox(a.x, b.x, a.y, b.y);
        else if (dr.kind === 'ruler') d = inBox(a.x, b.x, layout.panes[0].y0, layout.panes[0].y1);
        else if ((dr.kind === 'rr' || dr.kind === 'position') && q.length === 3) d = dr.kind === 'rr' ? inBox(X(Math.min(q[0].i, q[1].i, q[2].i)), right, Math.min(...pts.map((x) => x.y)), Math.max(...pts.map((x) => x.y))) : inBox(X(Math.min(q[0].i, q[1].i)), right, a.y, b.y);
        else if (dr.kind === 'channel' && q.length === 3) d = Math.min(...channel(q[0], q[1], q[2], last).map(segD));
        else if (dr.kind === 'pitchfork' && q.length === 3) { const f = pitchfork(q[0], q[1], q[2], last); d = Math.min(segD(f.handle), ...f.tines.map(segD)); }
        else if (dr.kind === 'fibext' && q.length === 3) d = Math.min(...fibExt(q[0], q[1], q[2]).map((l) => (p.x >= Math.min(pts[0].x, pts[2].x) - 4 ? Math.abs(ps.Y(l.price) - p.y) : Infinity)));
        else d = segDist(p.x, p.y, a.x, a.y, b.x, b.y);
      }
      if (d < bd) { bd = d; best = k; }
    });
    return best;
  }
  // The handle of the selected drawing under the pointer, or -1.
  function handleAt(p) {
    if (sel < 0 || !S.drawings[sel]) return -1;
    const ps = layout.ps, X = layout.X;
    return S.drawings[sel].points.findIndex((x) => Math.hypot(X(AX.f(x.t)) - p.x, ps.Y(x.p) - p.y) <= (touchy ? 20 : 9));
  }
  // A point placed or dragged: on its bar, and with snapping on at the bar's open, high, low or close when one is close.
  function pointAt(p) {
    const i = Math.max(0, Math.min(N - 1, layout.I(p.x))), price = layout.ps.P(p.y);
    const at = S.snap ? snap(bars[i], price, layout.ps.Y) : { price, field: null };
    return { t: bars[i].t, p: +at.price.toFixed(4), field: at.field };
  }


  function finishDrawing() {
    const dr = { id: 'd' + Date.now().toString(36) + Math.random().toString(36).slice(2, 5), kind: pending.kind, points: pending.points, color: 'accent', width: 1.6 };
    pending = null;
    if (dr.kind === 'text') { if (S.askText) S.askText(dr, (text) => { if (text) { dr.text = text.slice(0, 120); commit([...S.drawings, dr]); } }); return; }
    commit([...S.drawings, dr]);
  }
  function commit(next) { undo.push(S.drawings); if (undo.length > 40) undo.shift(); redo.length = 0; S.drawings = next; if (S.onDrawings) S.onDrawings(next); syncTouch(); changed(); redraw(); }
  function undoOne() { const prev = undo.pop(); if (prev) { redo.push(S.drawings); S.drawings = prev; sel = -1; if (S.onDrawings) S.onDrawings(prev); syncTouch(); changed(); redraw(); } }
  function redoOne() { const next = redo.pop(); if (next) { undo.push(S.drawings); S.drawings = next; sel = -1; if (S.onDrawings) S.onDrawings(next); syncTouch(); changed(); redraw(); } }

  /* ---------- keyboard ---------- */
  svg.addEventListener('keydown', (e) => {
    if (cross < 0) cross = to;
    const k = e.key;
    if (k === 'ArrowLeft' || k === 'ArrowRight') { const d = k === 'ArrowLeft' ? -1 : 1; if (e.shiftKey) pan(d * Math.max(1, Math.round((to - from) / 10))); else { cross = Math.max(0, Math.min(N - 1, cross + d)); if (cross < from) pan(cross - from); if (cross > to) pan(cross - to); } crossY = bars[cross].c; if (ms && ms.key) ms.b = cross; announce(); e.preventDefault(); }
    else if (k === 'ArrowUp' || k === 'ArrowDown') { yZoom = Math.max(0.25, Math.min(8, yZoom * (k === 'ArrowUp' ? 1.12 : 1 / 1.12))); e.preventDefault(); }
    else if ((k === 'Enter' || k === ' ') && S.onInsider && flags.some((g) => g.i === cross)) { e.preventDefault(); openInsider(flags.find((g) => g.i === cross)); return; }
    else if ((k === 'm' || k === 'M') && !e.metaKey && !e.ctrlKey && !e.altKey && !cmpOn()) { ms = ms && ms.key ? null : { a: cross, b: cross, key: true }; announce(); e.preventDefault(); }
    else if (k === '+' || k === '=') { zoom(1 / 1.25, cross); e.preventDefault(); } else if (k === '-' || k === '_') { zoom(1.25, cross); e.preventDefault(); }
    else if (k === 'Home') { cross = from; crossY = bars[cross].c; announce(); e.preventDefault(); } else if (k === 'End') { cross = to; crossY = bars[cross].c; announce(); e.preventDefault(); }
    else if ((k === 'Delete' || k === 'Backspace') && sel >= 0) { commit(S.drawings.filter((_, j) => j !== sel)); sel = -1; e.preventDefault(); }
    else if (k === 'Escape') { if (cancelDrag()) { e.preventDefault(); return; } if (ms) { ms = null; redraw(); return; } pending = null; sel = -1; syncTouch(); changed(); if (S.onEscape) S.onEscape(); }
    else if ((e.metaKey || e.ctrlKey) && k.toLowerCase() === 'z') { if (e.shiftKey) redoOne(); else undoOne(); e.preventDefault(); }
    else if ((e.metaKey || e.ctrlKey) && k.toLowerCase() === 'y') { redoOne(); e.preventDefault(); }
    redraw();
  });
  function announce() {
    if (ms && ms.key) { const r = measuredBars(bars, ms.a, ms.b, fmtT); live.textContent = ms.a === ms.b ? `Measuring from ${fmtT(bars[ms.a].t)}. Move with the arrow keys; Escape clears.` : `${r.span}: ${r.head}.`; return; }
    const b = bars[cross], ins = flags.filter((g) => g.i === cross).map((g) => `${g.items.length} insider ${g.side === 'buy' ? 'purchase' : 'sale'}${g.items.length === 1 ? '' : 's'}: ${g.items.map((it) => `${it.who}, ${it.amount}`).join('; ')}`).join('. '); live.textContent = `${fmtT(b.t)}: open ${num(b.o)}, high ${num(b.h)}, low ${num(b.l)}, close ${num(b.c)}.${ins ? ` ${ins}.` : ''}`; }

  /** Back to the bars the chart opened on, and a stretched price scale back to 1. */
  function home() { from = home0.from; to = home0.to; yZoom = 1; redraw(); }

  // only a change of width redraws: the observer's first call, just after the first draw, would otherwise end the draw-on
  const ro = new ResizeObserver(() => { if (host.clientWidth !== drawnW) redraw(); }); ro.observe(host);
  const onSync = (e) => {
    const q = e.detail || {};
    if (!S.sync || S.intraday || q.group !== S.sync || q.src === SYNC_ID) return;
    if (drag || tg) return;   // the reader has this chart in hand
    told = q.d;
    if (q.d === null) { cross = -1; crossY = null; redraw(); return; }
    const i = bars.findIndex((b) => new Date(b.t).toISOString().slice(0, 10) === q.d);
    cross = i >= 0 && i >= from && i <= to ? i : -1; crossY = null; redraw();
  };
  document.addEventListener('v2:xsync', onSync);
  syncTouch();
  draw();

  return {
    set(next) { Object.assign(S, next); if (next.tool) pending = null; if ('drawings' in next && sel >= S.drawings.length) sel = -1; syncTouch(); redraw(); },
    zoom: (f) => zoom(f, cross >= 0 ? cross : to), fit, pan, home,
    measure: (on) => setMeasure(on), measuring: () => mOn,
    /** Something has the chart under the reader's hand: a drag, a touch or a pointer held. */
    busy: () => !!(drag || tg || pointers.size),
    /** A live price into the newest bar, still forming (the page knows when it is): its close, and its high or low
     *  when the price passes them, with the indicators read again. The view is not touched. Declines (false) while
     *  the chart is under the reader's hand; the next tick tries again. */
    tick(price) {
      if (!(Number(price) > 0) || drag || tg || pointers.size) return false;
      const b = bars[N - 1]; if (!b) return false;
      if (b.c === price) return true;
      b.c = price; if (price > b.h) b.h = price; if (price < b.l) b.l = price;
      closes[N - 1] = price; Object.assign(ind, indicators());
      redraw(); return true;
    },
    view: () => ({ from, to }),
    height: () => S.height, navH: () => S.navH || 40,
    /** The market structure breaks in view, newest last, for Milo and the page. */
    structure: () => ind.msb.filter((m) => m.at >= from && m.at <= to).map((m) => ({ direction: m.dir === 'bull' ? 'bullish' : 'bearish', swing_formed_on: fmtT(bars[m.from].t), swing_known_on: fmtT(bars[m.known].t), broke_on: fmtT(bars[m.at].t), close: bars[m.at].c, level: m.price })),
    undo: undoOne, redo: redoOne, canUndo: () => undo.length > 0, canRedo: () => redo.length > 0, selected: () => sel >= 0,
    /** What a rebuild on the same bars carries over: the zoom, the price scale's stretch and the undo history. */
    keep: () => ({ view: { from, to }, history: { undo, redo }, yZoom }),
    deleteSelected() { if (sel >= 0) { commit(S.drawings.filter((_, j) => j !== sel)); sel = -1; } },
    clearDrawings() { commit([]); },
    destroy() { document.removeEventListener('v2:xsync', onSync); ro.disconnect(); clearTimeout(holdT); anim = null; unregisterChart(wheelHandle); document.removeEventListener('keydown', pageKey); cancelAnimationFrame(acc.raf); if (tg) clearTimeout(tg.hold); document.documentElement.classList.remove('pc-touching'); },
    focus() { svg.focus(); },
  };
}
