// The interactive price chart for the Chart page. SVG, redrawn on demand:
// a price pane (candles, line or area, with averages, bands, levels, earnings
// markers, what an open side widget asks for (`marks`, `lines`) and the reader's
// drawings), volume, and optional RSI and MACD panes.
//
// Interaction: wheel or pinch to zoom, drag to pan, a crosshair that drives an
// OHLC readout, and the keyboard (arrows move the crosshair, Shift+arrows pan,
// + and - zoom, Home and End jump, Delete removes the selected drawing).
// Asked for by the Chart page (`names`, `navigator`): the classic chart's legend
// over the plot's corner and its navigator, the whole history small under the
// plot for moving along it.
// Drawings are stored as {kind, points:[{t: epoch ms, p: price}]}, the classic
// app's format, so they line up whatever the bar size.
import { num, esc, compact } from '../core/format.js';
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

let legendSeq = 0;   // ids for each chart's legend body

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
const TOOL_POINTS = { hline: 1, vline: 1, text: 1, trend: 2, ray: 2, rect: 2, fibdraw: 2 };
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
  const S = Object.assign({ style: 'candles', overlays: {}, panes: { volume: true, rsi: false, macd: false }, levels: {}, events: [], marks: [], lines: [], drawings: [], tool: 'select', intraday: false }, opts);
  const bars = S.bars;
  const N = bars.length;
  const closes = bars.map((b) => b.c);
  const ind = {
    sma20: sma(closes, 20), sma50: sma(closes, 50), sma200: sma(closes, 200),
    ema9: ema(closes, 9), ema21: ema(closes, 21), ema50: ema(closes, 50),
    bb: bollinger(closes), rsi: rsi(closes), macd: macd(closes),
    msb: marketStructure(bars, S.msbK || 3),
  };
  let from = Math.max(0, N - (S.window || 126)), to = N - 1;
  let cross = -1, crossY = null, sel = -1, pending = null, W = 0, H = 0, layout = null, drag = null, raf = 0;
  const undo = [];

  host.classList.add('pc');
  // the legend sits over the plot's top-left corner (absolute, at its place in the flow); the navigator under it
  host.innerHTML = `<div class="pc-read" aria-live="off"></div>${S.names ? '<div class="pc-leg" role="group" aria-label="Legend"></div>' : ''}<svg class="pc-svg" tabindex="0" role="application" aria-roledescription="price chart"></svg>${S.navigator ? '<svg class="pc-nav" tabindex="0" role="slider" aria-label="Bars shown, from the whole history" aria-valuemin="1"></svg>' : ''}<div class="pc-sr sr" aria-live="polite"></div>`;
  const svg = host.querySelector('.pc-svg'), read = host.querySelector('.pc-read'), live = host.querySelector('.pc-sr');
  // a chart that asked for neither (the Instrument page's) gets detached stand-ins, so nothing below needs a guard
  const leg = host.querySelector('.pc-leg') || document.createElement('div'), nav = host.querySelector('.pc-nav') || document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  // the box that names an insider trade under the pointer (or the keyboard's bar); `flags` are the arrows drawn
  const tipEl = document.createElement('div'); tipEl.className = 'pc-tip'; tipEl.setAttribute('role', 'tooltip'); tipEl.hidden = true; host.appendChild(tipEl);
  let flags = [], hoverP = null;

  // daily and weekly bars are dates (UTC midnight); intraday bars are moments in New York
  const fmtT = (t) => { const d = new Date(t); return S.intraday ? d.toLocaleString('en-US', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit', timeZone: 'America/New_York' }) : d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric', timeZone: 'UTC' }); };
  const idxOfT = (t) => { let lo = 0, hi = N - 1; while (lo < hi) { const m = (lo + hi) >> 1; if (bars[m].t < t) lo = m + 1; else hi = m; } return lo > 0 && Math.abs(bars[lo - 1].t - t) < Math.abs(bars[lo].t - t) ? lo - 1 : lo; };

  function computeLayout() {
    W = Math.max(300, host.clientWidth); H = S.height || Math.round(Math.max(340, Math.min(620, W * 0.55)));
    const panes = []; const r = 56, l = 4;
    const extra = (S.panes.rsi ? 1 : 0) + (S.panes.macd ? 1 : 0);
    const paneH = extra ? Math.round(H * 0.17) : 0;
    const priceH = H - 26 - extra * (paneH + 8);
    panes.push({ id: 'price', y0: 8, y1: 8 + priceH });
    let y = 8 + priceH + 8;
    if (S.panes.rsi) { panes.push({ id: 'rsi', y0: y, y1: y + paneH }); y += paneH + 8; }
    if (S.panes.macd) { panes.push({ id: 'macd', y0: y, y1: y + paneH }); }
    const span = Math.max(1, to - from + 1), bw = (W - l - r) / span;
    return { l, r, panes, bw, X: (i) => l + (i - from + 0.5) * bw, I: (x) => Math.round((x - l) / bw - 0.5 + from) };
  }

  function priceScale(p) {
    let lo = Infinity, hi = -Infinity;
    for (let i = from; i <= to; i++) { const b = bars[i]; if (!b) continue; lo = Math.min(lo, S.style === 'candles' ? b.l : b.c); hi = Math.max(hi, S.style === 'candles' ? b.h : b.c); }
    const sp = (hi - lo) || 1; lo -= sp * 0.06; hi += sp * 0.08;
    return { lo, hi, Y: (v) => p.y0 + (1 - (v - lo) / (hi - lo)) * (p.y1 - p.y0), P: (y) => lo + (1 - (y - p.y0) / (p.y1 - p.y0)) * (hi - lo) };
  }
  const path = (vals, X, Y) => { let d = '', pen = false; for (let i = from; i <= to; i++) { const v = vals[i]; if (v === null || v === undefined || !Number.isFinite(v)) { pen = false; continue; } d += `${pen ? 'L' : 'M'}${X(i).toFixed(1)} ${Y(v).toFixed(1)}`; pen = true; } return d; };

  function draw() {
    raf = 0;
    layout = computeLayout();
    const { X, bw, panes } = layout;
    const pp = panes[0], ps = priceScale(pp); layout.ps = ps;
    let o = '';
    // grid and price axis
    [0.15, 0.5, 0.85].forEach((f) => { const v = ps.lo + (ps.hi - ps.lo) * f, y = ps.Y(v); o += `<line class="g" x1="0" x2="${W - layout.r}" y1="${y.toFixed(1)}" y2="${y.toFixed(1)}"/><text class="ax" x="${W - layout.r + 6}" y="${(y + 4).toFixed(1)}">${num(v, v < 10 ? 2 : v < 1000 ? 1 : 0)}</text>`; });
    // time axis
    const step = Math.max(1, Math.round((to - from) / Math.max(3, Math.floor(W / 120))));
    for (let i = from; i <= to; i += step) o += `<text class="ax" x="${X(i).toFixed(1)}" y="${H - 6}" text-anchor="middle">${esc(S.intraday ? new Date(bars[i].t).toLocaleDateString('en-US', { month: 'short', day: 'numeric', timeZone: 'America/New_York' }) : new Date(bars[i].t).toLocaleDateString('en-US', { month: 'short', year: '2-digit', timeZone: 'UTC' }))}</text>`;
    // volume, under the price
    if (S.panes.volume) {
      let vmax = 0; for (let i = from; i <= to; i++) vmax = Math.max(vmax, bars[i].v || 0);
      const vh = (pp.y1 - pp.y0) * 0.18;
      for (let i = from; i <= to; i++) { const b = bars[i]; if (!b.v) continue; const h = (b.v / (vmax || 1)) * vh; o += `<rect class="vol ${b.c >= b.o ? 'u' : 'd'}" x="${(X(i) - bw * 0.38).toFixed(1)}" y="${(pp.y1 - h).toFixed(1)}" width="${Math.max(0.6, bw * 0.76).toFixed(1)}" height="${h.toFixed(1)}"/>`; }
    }
    // levels
    const L = S.levels || {};
    // a label sits over its line at the left, or under it (`below`) or at the right (`end`) where lines run close
    const hline = (v, cls, t, at = {}) => { if (!Number.isFinite(v) || v < ps.lo || v > ps.hi) return ''; const y = ps.Y(v).toFixed(1); return `<line class="lv ${cls}" x1="0" x2="${W - layout.r}" y1="${y}" y2="${y}"/><text class="lv-t ${cls}" x="${at.end ? W - layout.r - 6 : 6}" y="${at.below ? Number(y) + 14 : y - 4}"${at.end ? ' text-anchor="end"' : ''}>${esc(t)}</text>`; };
    if (S.overlays.fib && L.fib) (L.fib.levels || []).forEach((f) => { o += hline(f.price, 'fib', `Fib ${f.label}`); });
    if (S.overlays.sr && L.sr) L.sr.slice(0, 8).forEach((s) => { o += hline(s.price, s.role === 'support' ? 'sup' : 'res', `${s.role === 'support' ? 'Support' : 'Resistance'} ${num(s.price)}`); });
    // lines a side widget asks for (the stop check's stop, buffered stop and round number)
    (S.lines || []).forEach((l) => { o += hline(l.price, l.cls, l.label, l); });
    if (S.overlays.gex && L.gex) { const g = L.gex; if (g.call_wall) o += hline(g.call_wall, 'gex', `Call wall ${num(g.call_wall, 0)}`); if (g.put_wall) o += hline(g.put_wall, 'gex', `Put wall ${num(g.put_wall, 0)}`); if (g.flip) o += hline(g.flip, 'gex', `Gamma flip ${num(g.flip, 0)}`); }
    // bands and averages
    if (S.overlays.bb) o += `<path class="ov bb" d="${path(ind.bb.up, X, ps.Y)}"/><path class="ov bb" d="${path(ind.bb.dn, X, ps.Y)}"/><path class="ov bbm" d="${path(ind.bb.mid, X, ps.Y)}"/>`;
    if (S.overlays.ma) [['sma20', 'm1'], ['sma50', 'm2'], ['sma200', 'm3']].forEach(([k, c]) => { o += `<path class="ov ${c}" d="${path(ind[k], X, ps.Y)}"/>`; });
    if (S.overlays.ema) [['ema9', 'e1'], ['ema21', 'e2'], ['ema50', 'e3']].forEach(([k, c]) => { o += `<path class="ov ${c}" d="${path(ind[k], X, ps.Y)}"/>`; });
    // price
    if (S.style === 'candles') {
      for (let i = from; i <= to; i++) {
        const b = bars[i], x = X(i), up = b.c >= b.o, y1 = ps.Y(Math.max(b.o, b.c)), y2 = ps.Y(Math.min(b.o, b.c));
        o += `<line class="wick ${up ? 'u' : 'd'}" x1="${x.toFixed(1)}" x2="${x.toFixed(1)}" y1="${ps.Y(b.h).toFixed(1)}" y2="${ps.Y(b.l).toFixed(1)}"/><rect class="body ${up ? 'u' : 'd'}" x="${(x - bw * 0.36).toFixed(1)}" y="${y1.toFixed(1)}" width="${Math.max(1, bw * 0.72).toFixed(1)}" height="${Math.max(0.8, y2 - y1).toFixed(1)}"/>`;
      }
    } else {
      const d = path(closes, X, ps.Y);
      if (S.style === 'area') o += `<path class="area" d="${d}L${X(to).toFixed(1)} ${pp.y1}L${X(from).toFixed(1)} ${pp.y1}Z"/>`;
      o += `<path class="pline" d="${d}"/>`;
    }
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
    // earnings and other events
    (S.overlays.events === false ? [] : S.events).forEach((e) => { const i = idxOfT(e.t); if (i < from || i > to) return; const x = X(i).toFixed(1); o += `<g class="evm"><line x1="${x}" x2="${x}" y1="${pp.y0}" y2="${pp.y1}"/><text x="${x}" y="${pp.y1 - 4}" text-anchor="middle">${esc(e.kind)}</text><title>${esc(e.label)}</title></g>`; });
    // insider trades (S.insiders, from the ticker payload): a green arrow under the bar's low for a purchase, a red
    // one over its high for a sale, one arrow for all of a side's trades in a bar; the box comes from insiderTip()
    flags = [];
    if (S.overlays.ins !== false && (S.insiders || []).length) {
      const by = new Map();
      S.insiders.forEach((it) => { const i = idxOfT(it.t); if (i < from || i > to || !bars[i]) return; const k = `${i}${it.side}`; if (!by.has(k)) by.set(k, { i, side: it.side, items: [] }); by.get(k).items.push(it); });
      by.forEach((f) => {
        const b = bars[f.i], x = X(f.i), buy = f.side === 'buy';
        const tip = buy ? Math.min(pp.y1 - 21, ps.Y(b.l) + 6) : Math.max(pp.y0 + 21, ps.Y(b.h) - 6), d = buy ? 1 : -1;
        const pts = [[0, 0], [7.5, 9], [2, 9], [2, 19], [-2, 19], [-2, 9], [-7.5, 9]].map(([dx, dy]) => `${(x + dx).toFixed(1)} ${(tip + d * dy).toFixed(1)}`);
        o += `<path class="ins ${buy ? 'buy' : 'sell'}" d="M${pts.join('L')}Z"/>`;
        flags.push(Object.assign(f, { x, y: tip + d * 10 }));
      });
    }
    // fills a side widget asks for (the backtest's entries and exits): B under the bar's low, S over its high
    (S.marks || []).forEach((m) => {
      const i = idxOfT(m.t); if (i < from || i > to || !bars[i]) return;
      const b = bars[i], x = X(i), r = 8, buy = m.kind === 'B';
      const y = Math.max(pp.y0 + r, Math.min(pp.y1 - r, buy ? ps.Y(b.l) + r + 4 : ps.Y(b.h) - r - 4));
      o += `<g class="tm ${m.tone === 'neg' ? 'neg' : 'pos'}"><circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="${r}"/><text x="${x.toFixed(1)}" y="${(y + 4).toFixed(1)}" text-anchor="middle">${esc(m.kind)}</text><title>${esc(m.label)}</title></g>`;
    });
    // drawings
    S.drawings.forEach((dr, k) => { o += drawing(dr, k === sel); });
    if (pending && pending.points.length && cross >= 0) o += drawing({ kind: pending.kind, points: [...pending.points, { t: bars[cross].t, p: crossY }] }, false, true);
    // panes
    panes.slice(1).forEach((p) => {
      o += `<line class="pane-sep" x1="0" x2="${W}" y1="${p.y0 - 4}" y2="${p.y0 - 4}"/>`;
      if (p.id === 'rsi') {
        const Y = (v) => p.y0 + (1 - v / 100) * (p.y1 - p.y0);
        o += `<line class="g" x1="0" x2="${W - layout.r}" y1="${Y(70)}" y2="${Y(70)}"/><line class="g" x1="0" x2="${W - layout.r}" y1="${Y(30)}" y2="${Y(30)}"/><text class="ax" x="${W - layout.r + 6}" y="${Y(70) + 4}">70</text><text class="ax" x="${W - layout.r + 6}" y="${Y(30) + 4}">30</text><text class="pane-t" x="6" y="${p.y0 + 12}">RSI 14</text><path class="ov rsi" d="${path(ind.rsi, X, Y)}"/>`;
      } else {
        const m = ind.macd; let mx = 0; for (let i = from; i <= to; i++) [m.line[i], m.signal[i], m.hist[i]].forEach((v) => { if (Number.isFinite(v)) mx = Math.max(mx, Math.abs(v)); });
        const Y = (v) => p.y0 + (1 - (v + (mx || 1)) / (2 * (mx || 1))) * (p.y1 - p.y0);
        for (let i = from; i <= to; i++) { const h = m.hist[i]; if (!Number.isFinite(h)) continue; o += `<rect class="mh ${h >= 0 ? 'u' : 'd'}" x="${(X(i) - bw * 0.35).toFixed(1)}" y="${Math.min(Y(0), Y(h)).toFixed(1)}" width="${Math.max(0.6, bw * 0.7).toFixed(1)}" height="${Math.abs(Y(h) - Y(0)).toFixed(1)}"/>`; }
        o += `<text class="pane-t" x="6" y="${p.y0 + 12}">MACD 12, 26, 9</text><path class="ov macd" d="${path(m.line, X, Y)}"/><path class="ov macds" d="${path(m.signal, X, Y)}"/>`;
      }
    });
    // crosshair
    if (cross >= from && cross <= to) {
      const x = X(cross).toFixed(1);
      o += `<line class="xh" x1="${x}" x2="${x}" y1="${pp.y0}" y2="${H - 22}"/>`;
      if (crossY !== null) { const y = ps.Y(crossY).toFixed(1); o += `<line class="xh" x1="0" x2="${W - layout.r}" y1="${y}" y2="${y}"/><rect class="xh-tag" x="${W - layout.r + 2}" y="${y - 9}" width="${layout.r - 4}" height="18" rx="3"/><text class="xh-t" x="${W - layout.r + 6}" y="${(Number(y) + 4)}">${num(crossY, crossY < 10 ? 2 : 1)}</text>`; }
    }
    svg.setAttribute('viewBox', `0 0 ${W} ${H}`); svg.setAttribute('width', W); svg.setAttribute('height', H);
    svg.innerHTML = o;
    svg.setAttribute('aria-label', summary());
    readout();
    legend(); drawNav();
  }

  function drawing(dr, selected, ghost) {
    const ps = layout.ps, X = layout.X;
    const pts = dr.points.map((q) => ({ x: X(idxOfT(q.t)), y: ps.Y(q.p), p: q.p }));
    const cls = `dr ${selected ? 'sel' : ''} ${ghost ? 'ghost' : ''}`;
    if (dr.kind === 'hline') return `<line class="${cls}" x1="0" x2="${W - layout.r}" y1="${pts[0].y}" y2="${pts[0].y}"/><text class="dr-t" x="${W - layout.r - 4}" y="${pts[0].y - 4}" text-anchor="end">${num(pts[0].p)}${dr.origin === 'milo' ? ' Milo' : ''}</text>`;
    if (dr.kind === 'vline') return `<line class="${cls}" x1="${pts[0].x}" x2="${pts[0].x}" y1="${layout.panes[0].y0}" y2="${layout.panes[0].y1}"/>`;
    if (dr.kind === 'text') return `<text class="dr-text ${selected ? 'sel' : ''}" x="${pts[0].x}" y="${pts[0].y}">${esc(dr.text || '')}</text>`;
    if (pts.length < 2) return '';
    const [a, b] = pts;
    if (dr.kind === 'trend') return `<line class="${cls}" x1="${a.x}" y1="${a.y}" x2="${b.x}" y2="${b.y}"/>`;
    if (dr.kind === 'ray') { const k = (b.y - a.y) / ((b.x - a.x) || 1e-6), x2 = b.x >= a.x ? W - layout.r : 0; return `<line class="${cls}" x1="${a.x}" y1="${a.y}" x2="${x2}" y2="${a.y + k * (x2 - a.x)}"/>`; }
    if (dr.kind === 'rect') return `<rect class="${cls} dr-rect" x="${Math.min(a.x, b.x)}" y="${Math.min(a.y, b.y)}" width="${Math.abs(b.x - a.x)}" height="${Math.abs(b.y - a.y)}"/>`;
    // 0% at the first point, as the classic app draws it
    if (dr.kind === 'fibdraw') return FIB.map((f) => { const p = a.p + (b.p - a.p) * f, y = ps.Y(p); return `<line class="${cls}" x1="${Math.min(a.x, b.x)}" x2="${W - layout.r}" y1="${y}" y2="${y}"/><text class="dr-t" x="${Math.min(a.x, b.x) + 4}" y="${y - 3}">${num(f * 100, 1)}% ${num(p)}</text>`; }).join('');
    // kinds only the classic app draws (channel, pitchfork, ruler, risk box...): shown as their first line
    return `<line class="${cls} dr-other" x1="${a.x}" y1="${a.y}" x2="${b.x}" y2="${b.y}"><title>${esc(dr.kind)}, drawn in full in the current app</title></line>`;
  }

  // The hover box: the arrow nearest the pointer, or with the keyboard the arrow on the crosshair's bar.
  function insiderTip() {
    let f = null;
    if (hoverP && !(drag && drag.moved)) { let best = 22; flags.forEach((g) => { const dx = Math.abs(g.x - hoverP.x), dy = Math.abs(g.y - hoverP.y); if (dx <= Math.max(9, layout.bw / 2 + 3) && dy < best) { best = dy; f = g; } }); }
    else if (document.activeElement === svg && cross >= 0) f = flags.find((g) => g.i === cross) || null;
    if (!f) { tipEl.hidden = true; return; }
    const buy = f.side === 'buy', n = f.items.length, total = f.items.reduce((a, it) => a + (Number(it.value) || 0), 0);
    const day = f.items.every((it) => it.date === f.items[0].date) ? f.items[0].date : '';   // a weekly bar can hold several days
    const head = `<p class="pc-tip-h"><b class="${buy ? 'up' : 'down'}">${n === 1 ? `Insider ${buy ? 'purchase' : 'sale'}` : `${n} insider ${buy ? 'purchases' : 'sales'}`}</b>${day ? ` ${esc(day)}` : ''}</p>${n > 1 && total ? `<p class="t-muted">$${esc(compact(total))} in all</p>` : ''}`;
    const rows = f.items.slice(0, 4).map((it) => `<div class="pc-tip-r"><p><b>${esc(it.who)}</b>${it.role ? `, ${esc(it.role)}` : ''}</p><p>${esc([day ? '' : it.date, it.amount].filter(Boolean).join(', '))}</p>${it.note ? `<p class="t-muted">${esc(it.note)}</p>` : ''}</div>`).join('');
    tipEl.innerHTML = head + rows + (n > 4 ? `<p class="t-muted">And ${n - 4} more on this bar.</p>` : '');
    tipEl.hidden = false;
    // an <svg> has no offsetTop: its place in the host comes from the two boxes
    const r = svg.getBoundingClientRect(), hr = host.getBoundingClientRect(), k = r.width / (W || 1), top0 = r.top - hr.top, hw = host.clientWidth;
    const bw = tipEl.offsetWidth, bh = tipEl.offsetHeight, ax = f.x * k + (r.left - hr.left), ay = f.y * k + top0;
    let left = ax + 14; if (left + bw > hw - 4) left = Math.max(4, ax - 14 - bw);
    // inside the plot, and inside the window when the plot runs past it
    const lo = Math.max(top0, -hr.top + 72) + 4, hi = Math.min(top0 + H * k, window.innerHeight - hr.top) - bh - 4;
    const top = Math.max(lo, Math.min(hi, ay - bh / 2));
    tipEl.style.left = `${Math.round(left)}px`; tipEl.style.top = `${Math.round(top)}px`;
  }
  function readout() {
    insiderTip();
    const i = cross >= 0 ? cross : to, b = bars[i];
    if (!b) { read.textContent = ''; return; }
    const prev = bars[i - 1], chg = prev ? (b.c / prev.c - 1) * 100 : null;
    read.innerHTML = `<b>${esc(fmtT(b.t))}</b> <span>O ${num(b.o)}</span> <span>H ${num(b.h)}</span> <span>L ${num(b.l)}</span> <span>C ${num(b.c)}</span>${chg !== null ? ` <span class="${chg >= 0 ? 'up' : 'down'}">${chg >= 0 ? '+' : '−'}${num(Math.abs(chg))}%</span>` : ''}${b.v ? ` <span class="t-muted">Vol ${num(b.v / 1e6, 1)}M</span>` : ''}`;
  }
  function summary() {
    const a = bars[from], b = bars[to]; if (!a || !b) return 'Price chart';
    const ch = (b.c / a.c - 1) * 100;
    const breaks = S.overlays.msb ? ind.msb.filter((m) => m.at >= from && m.at <= to) : [];
    const last = breaks[breaks.length - 1];
    const msb = S.overlays.msb ? (last ? ` ${breaks.length} market structure break${breaks.length === 1 ? '' : 's'} in view; the latest is ${last.dir === 'bull' ? 'bullish' : 'bearish'}, on ${fmtT(bars[last.at].t)} through ${num(last.price)}.` : ' No market structure break in view.') : '';
    const ins = flags.length ? ` ${flags.reduce((a, g) => a + g.items.length, 0)} insider trades marked.` : '';
    return `${S.label || 'Price'}, ${to - from + 1} bars from ${fmtT(a.t)} to ${fmtT(b.t)}: from ${num(a.c)} to ${num(b.c)}, ${ch >= 0 ? 'up' : 'down'} ${num(Math.abs(ch), 1)} percent.${msb}${ins} Use the arrow keys to read each bar.`;
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
    const x = navX(e);
    if (!ndrag) { nav.dataset.hover = navMode(x, e.pointerType === 'touch'); return; }
    setView(navWindow(ndrag.mode, ndrag, Math.round((x - ndrag.x) * ndrag.per), N));
  });
  const navUp = () => { ndrag = null; delete nav.dataset.drag; };
  nav.addEventListener('pointerup', navUp); nav.addEventListener('pointercancel', navUp);
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
  const fit = () => { from = 0; to = N - 1; redraw(); };

  /* ---------- pointer ---------- */
  const pt = (e) => { const r = svg.getBoundingClientRect(); return { x: (e.clientX - r.left) * (W / r.width), y: (e.clientY - r.top) * (H / r.height) }; };
  const pointers = new Map();
  svg.addEventListener('pointerdown', (e) => {
    try { svg.setPointerCapture(e.pointerId); } catch (err) { /* a pointer the browser no longer tracks */ }
    pointers.set(e.pointerId, pt(e));
    hoverP = pt(e);   // a tap on an arrow opens its box on a touch screen
    if (pointers.size === 2) { const [p1, p2] = [...pointers.values()]; drag = { pinch: Math.abs(p1.x - p2.x), span: to - from + 1 }; return; }
    const p = pt(e), i = Math.max(0, Math.min(N - 1, layout.I(p.x))), price = layout.ps.P(p.y);
    if (S.tool !== 'select') {
      if (!pending) pending = { kind: S.tool, points: [] };
      pending.points.push({ t: bars[i].t, p: +price.toFixed(4) });
      if (pending.points.length >= TOOL_POINTS[S.tool]) finishDrawing();
      redraw(); return;
    }
    const hit = hitTest(p);
    sel = hit; if (S.onSelect) S.onSelect(hit >= 0 ? S.drawings[hit] : null);
    drag = { x: p.x, from, moved: false };
    redraw();
  });
  svg.addEventListener('pointermove', (e) => {
    const p = pt(e);
    if (pointers.has(e.pointerId)) pointers.set(e.pointerId, p);
    if (drag && drag.pinch && pointers.size === 2) { const [p1, p2] = [...pointers.values()]; const d = Math.abs(p1.x - p2.x) || 1; const ns = Math.max(10, Math.min(N, Math.round(drag.span * drag.pinch / d))); const c = to; from = Math.max(0, c - ns + 1); to = c; redraw(); return; }
    if (drag && !drag.pinch) { const dx = p.x - drag.x; if (Math.abs(dx) > 3) drag.moved = true; const span = to - from; from = Math.max(0, Math.min(N - 1 - span, drag.from - Math.round(dx / layout.bw))); to = from + span; }
    cross = Math.max(from, Math.min(to, layout.I(p.x))); crossY = p.y <= layout.panes[0].y1 ? layout.ps.P(p.y) : null;
    hoverP = p;
    redraw();
  });
  const up = (e) => { pointers.delete(e.pointerId); if (pointers.size < 2 && drag && drag.pinch) drag = null; else if (pointers.size === 0) drag = null; };
  svg.addEventListener('pointerup', up); svg.addEventListener('pointercancel', up);
  // a finger lifting also leaves: the box it opened stays until the next touch
  svg.addEventListener('pointerleave', (e) => { if (e.pointerType !== 'touch') hoverP = null; if (!drag) { cross = -1; crossY = null; redraw(); } });
  svg.addEventListener('wheel', (e) => { e.preventDefault(); const p = pt(e); zoom(e.deltaY > 0 ? 1.15 : 1 / 1.15, Math.max(from, Math.min(to, layout.I(p.x)))); }, { passive: false });

  function hitTest(p) {
    const ps = layout.ps, X = layout.X;
    let best = -1, bd = 9;
    S.drawings.forEach((dr, k) => {
      const pts = dr.points.map((q) => ({ x: X(idxOfT(q.t)), y: ps.Y(q.p) }));
      let d = Infinity;
      if (dr.kind === 'hline' || dr.kind === 'fibdraw') d = Math.min(...pts.map((q) => Math.abs(q.y - p.y)));
      else if (dr.kind === 'vline') d = Math.abs(pts[0].x - p.x);
      else if (dr.kind === 'text') d = Math.hypot(pts[0].x - p.x, pts[0].y - p.y) / 2;
      else if (pts.length > 1) { const [a, b] = pts; if (dr.kind === 'rect') d = (p.x >= Math.min(a.x, b.x) - 4 && p.x <= Math.max(a.x, b.x) + 4 && p.y >= Math.min(a.y, b.y) - 4 && p.y <= Math.max(a.y, b.y) + 4) ? 0 : Infinity; else { const t = Math.max(0, Math.min(1, ((p.x - a.x) * (b.x - a.x) + (p.y - a.y) * (b.y - a.y)) / (((b.x - a.x) ** 2 + (b.y - a.y) ** 2) || 1))); d = Math.hypot(p.x - (a.x + t * (b.x - a.x)), p.y - (a.y + t * (b.y - a.y))); } }
      if (d < bd) { bd = d; best = k; }
    });
    return best;
  }

  function finishDrawing() {
    const dr = { id: 'd' + Date.now().toString(36) + Math.random().toString(36).slice(2, 5), kind: pending.kind, points: pending.points, color: 'accent', width: 1.6 };
    pending = null;
    if (dr.kind === 'text') { if (S.askText) S.askText(dr, (text) => { if (text) { dr.text = text.slice(0, 120); commit([...S.drawings, dr]); } }); return; }
    commit([...S.drawings, dr]);
  }
  function commit(next) { undo.push(S.drawings); if (undo.length > 40) undo.shift(); S.drawings = next; if (S.onDrawings) S.onDrawings(next); redraw(); }

  /* ---------- keyboard ---------- */
  svg.addEventListener('keydown', (e) => {
    if (cross < 0) cross = to;
    const k = e.key;
    if (k === 'ArrowLeft' || k === 'ArrowRight') { const d = k === 'ArrowLeft' ? -1 : 1; if (e.shiftKey) pan(d * Math.max(1, Math.round((to - from) / 10))); else { cross = Math.max(0, Math.min(N - 1, cross + d)); if (cross < from) pan(cross - from); if (cross > to) pan(cross - to); } crossY = bars[cross].c; announce(); e.preventDefault(); }
    else if (k === '+' || k === '=') { zoom(1 / 1.25, cross); e.preventDefault(); } else if (k === '-' || k === '_') { zoom(1.25, cross); e.preventDefault(); }
    else if (k === 'Home') { cross = from; crossY = bars[cross].c; announce(); e.preventDefault(); } else if (k === 'End') { cross = to; crossY = bars[cross].c; announce(); e.preventDefault(); }
    else if ((k === 'Delete' || k === 'Backspace') && sel >= 0) { commit(S.drawings.filter((_, j) => j !== sel)); sel = -1; e.preventDefault(); }
    else if (k === 'Escape') { pending = null; sel = -1; if (S.onEscape) S.onEscape(); }
    else if ((e.metaKey || e.ctrlKey) && k.toLowerCase() === 'z') { const prev = undo.pop(); if (prev) { S.drawings = prev; if (S.onDrawings) S.onDrawings(prev); } e.preventDefault(); }
    redraw();
  });
  function announce() { const b = bars[cross], ins = flags.filter((g) => g.i === cross).map((g) => `${g.items.length} insider ${g.side === 'buy' ? 'purchase' : 'sale'}${g.items.length === 1 ? '' : 's'}: ${g.items.map((it) => `${it.who}, ${it.amount}`).join('; ')}`).join('. '); live.textContent = `${fmtT(b.t)}: open ${num(b.o)}, high ${num(b.h)}, low ${num(b.l)}, close ${num(b.c)}.${ins ? ` ${ins}.` : ''}`; }

  const ro = new ResizeObserver(() => redraw()); ro.observe(host);
  draw();

  return {
    set(next) { Object.assign(S, next); if (next.tool) pending = null; redraw(); },
    zoom: (f) => zoom(f, cross >= 0 ? cross : to), fit, pan,
    view: () => ({ from, to }),
    height: () => S.height, navH: () => S.navH || 40,
    /** The market structure breaks in view, newest last, for Milo and the page. */
    structure: () => ind.msb.filter((m) => m.at >= from && m.at <= to).map((m) => ({ direction: m.dir === 'bull' ? 'bullish' : 'bearish', swing_formed_on: fmtT(bars[m.from].t), swing_known_on: fmtT(bars[m.known].t), broke_on: fmtT(bars[m.at].t), close: bars[m.at].c, level: m.price })),
    undo() { const prev = undo.pop(); if (prev) { S.drawings = prev; if (S.onDrawings) S.onDrawings(prev); redraw(); } },
    deleteSelected() { if (sel >= 0) { commit(S.drawings.filter((_, j) => j !== sel)); sel = -1; } },
    clearDrawings() { commit([]); },
    destroy() { ro.disconnect(); },
    focus() { svg.focus(); },
  };
}
