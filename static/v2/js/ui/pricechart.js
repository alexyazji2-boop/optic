// The interactive price chart for the Chart page. SVG, redrawn on demand:
// a price pane (candles, line or area, with averages, bands, levels, earnings
// markers, what an open side widget asks for (`marks`, `lines`) and the reader's
// drawings), volume, and optional RSI and MACD panes.
//
// Interaction: wheel or pinch to zoom, drag to pan, a crosshair that drives an
// OHLC readout, and the keyboard (arrows move the crosshair, Shift+arrows pan,
// + and - zoom, Home and End jump, Delete removes the selected drawing).
// Drawings are stored as {kind, points:[{t: epoch ms, p: price}]}, the classic
// app's format, so they line up whatever the bar size.
import { num, esc } from '../core/format.js';

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
  host.innerHTML = `<div class="pc-read" aria-live="off"></div><svg class="pc-svg" tabindex="0" role="application" aria-roledescription="price chart"></svg><div class="pc-sr sr" aria-live="polite"></div>`;
  const svg = host.querySelector('svg'), read = host.querySelector('.pc-read'), live = host.querySelector('.pc-sr');

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

  function readout() {
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
    return `${S.label || 'Price'}, ${to - from + 1} bars from ${fmtT(a.t)} to ${fmtT(b.t)}: from ${num(a.c)} to ${num(b.c)}, ${ch >= 0 ? 'up' : 'down'} ${num(Math.abs(ch), 1)} percent.${msb} Use the arrow keys to read each bar.`;
  }
  const redraw = () => { if (!raf) raf = requestAnimationFrame(draw); };

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
    redraw();
  });
  const up = (e) => { pointers.delete(e.pointerId); if (pointers.size < 2 && drag && drag.pinch) drag = null; else if (pointers.size === 0) drag = null; };
  svg.addEventListener('pointerup', up); svg.addEventListener('pointercancel', up);
  svg.addEventListener('pointerleave', () => { if (!drag) { cross = -1; crossY = null; redraw(); } });
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
  function announce() { const b = bars[cross]; live.textContent = `${fmtT(b.t)}: open ${num(b.o)}, high ${num(b.h)}, low ${num(b.l)}, close ${num(b.c)}.`; }

  const ro = new ResizeObserver(() => redraw()); ro.observe(host);
  draw();

  return {
    set(next) { Object.assign(S, next); if (next.tool) pending = null; redraw(); },
    zoom: (f) => zoom(f, cross >= 0 ? cross : to), fit, pan,
    view: () => ({ from, to }),
    /** The market structure breaks in view, newest last, for Milo and the page. */
    structure: () => ind.msb.filter((m) => m.at >= from && m.at <= to).map((m) => ({ direction: m.dir === 'bull' ? 'bullish' : 'bearish', swing_formed_on: fmtT(bars[m.from].t), swing_known_on: fmtT(bars[m.known].t), broke_on: fmtT(bars[m.at].t), close: bars[m.at].c, level: m.price })),
    undo() { const prev = undo.pop(); if (prev) { S.drawings = prev; if (S.onDrawings) S.onDrawings(prev); redraw(); } },
    deleteSelected() { if (sel >= 0) { commit(S.drawings.filter((_, j) => j !== sel)); sel = -1; } },
    clearDrawings() { commit([]); },
    destroy() { ro.disconnect(); },
    focus() { svg.focus(); },
  };
}
