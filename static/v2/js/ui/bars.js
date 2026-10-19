// Bar charts drawn as SVG at their container's real width.
//   signedBars: one bar per category around a zero line (dealer gamma by
//     strike, net premium, revisions). Positive up, negative down, both in
//     ink so colour never carries sign alone; a marker line can show spot.
//   hbars: labelled horizontal bars for shares (allocation, segments).
// Each chart carries a text summary and a keyboard-readable tooltip.
import { num, esc, compact } from '../core/format.js';

let seq = 0;

/**
 * rows: [{x: number|string, v: number, label?: string}]
 * opts: {w, h, label, marker: {x, text}, fmt(v), xfmt(x), lines: [{x, text}], pad}
 */
export function signedBars(rows, opts = {}) {
  const id = 'sb' + (++seq);
  const data = (rows || []).filter((r) => Number.isFinite(r.v));
  if (!data.length) return { html: '', wire() {} };
  const W = Math.max(280, Math.round(opts.w || 600)), H = Math.round(opts.h || 180);
  const pad = Object.assign({ t: 18, r: 12, b: 26, l: 12 }, opts.pad || {});
  const fmt = opts.fmt || ((v) => compact(v));
  const xfmt = opts.xfmt || ((x) => (typeof x === 'number' ? num(x, x % 1 ? 1 : 0) : String(x)));
  const max = Math.max(...data.map((r) => Math.abs(r.v))) || 1;
  const bw = (W - pad.l - pad.r) / data.length;
  const zero = pad.t + (H - pad.t - pad.b) / 2;
  const half = (H - pad.t - pad.b) / 2 - 2;
  const numeric = data.every((r) => typeof r.x === 'number');
  // The bars stand one per strike, evenly spaced by rank, and strikes are not evenly spaced in price; a
  // marker placed on a straight price scale drew "Now" at 344.73 on the 350 bar (market-hours check,
  // 2026-10-19). It goes between its two neighbouring bars instead.
  const xAt = (x) => {
    if (!numeric || !Number.isFinite(x)) return null;
    const xs = data.map((r) => r.x), n = xs.length, mid = (i) => pad.l + bw / 2 + i * bw;
    if (n === 1) return mid(0);
    const up = xs[n - 1] >= xs[0];
    const before = (a, b) => (up ? a <= b : a >= b);
    if (before(x, xs[0])) return mid(0);
    if (before(xs[n - 1], x)) return mid(n - 1);
    for (let i = 0; i < n - 1; i += 1) {
      if (before(xs[i], x) && before(x, xs[i + 1])) return mid(i + (x - xs[i]) / ((xs[i + 1] - xs[i]) || 1));
    }
    return null;
  };
  const bars = data.map((r, i) => {
    const x = pad.l + i * bw + 1, h = (Math.abs(r.v) / max) * half;
    const y = r.v >= 0 ? zero - h : zero;
    return `<rect class="bar ${r.v >= 0 ? 'pos' : 'neg'}" x="${x.toFixed(1)}" y="${y.toFixed(1)}" width="${Math.max(1, bw - 2).toFixed(1)}" height="${Math.max(1, h).toFixed(1)}" rx="1.5" data-i="${i}"/>`;
  }).join('');
  const step = Math.max(1, Math.ceil(data.length / Math.max(3, Math.floor(W / 70))));
  const ticks = data.map((r, i) => (i % step === 0 ? `<text class="ax" x="${(pad.l + i * bw + bw / 2).toFixed(1)}" y="${H - 6}" text-anchor="middle">${esc(xfmt(r.x))}</text>` : '')).join('');
  const lines = [...(opts.lines || []), ...(opts.marker ? [opts.marker] : [])].map((m) => {
    const x = xAt(m.x); if (x === null || !Number.isFinite(x)) return '';
    return `<line class="mk" x1="${x.toFixed(1)}" x2="${x.toFixed(1)}" y1="${pad.t - 6}" y2="${H - pad.b}"/><text class="mk-t" x="${x.toFixed(1)}" y="${pad.t - 8}" text-anchor="middle">${esc(m.text)}</text>`;
  }).join('');
  const pos = data.filter((r) => r.v > 0).length;
  const summary = opts.summary || `${opts.label || 'Bars'}: ${data.length} values, ${pos} positive and ${data.length - pos} negative. Largest ${fmt(data.reduce((a, r) => (Math.abs(r.v) > Math.abs(a.v) ? r : a)).v)} at ${xfmt(data.reduce((a, r) => (Math.abs(r.v) > Math.abs(a.v) ? r : a)).x)}.`;
  const svg = `<svg class="bars" id="${id}" viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" role="img" aria-label="${esc(summary)}" tabindex="0">
    <line class="zero" x1="${pad.l}" x2="${W - pad.r}" y1="${zero}" y2="${zero}"/>${bars}${lines}${ticks}</svg><div class="chart-tip" aria-hidden="true" style="display:none"></div>`;
  function wire(root) {
    const el = root.querySelector('#' + id); if (!el) return;
    const tip = el.nextElementSibling;
    let k = data.length - 1;
    const show = (i) => {
      k = i; const r = data[i];
      el.querySelectorAll('.bar').forEach((b) => b.classList.toggle('on', Number(b.dataset.i) === i));
      tip.style.display = ''; tip.innerHTML = `<b>${esc(fmt(r.v))}</b> <span>${esc(r.label || xfmt(r.x))}</span>`;
      const box = el.getBoundingClientRect();
      tip.style.left = Math.min(box.width - 170, Math.max(0, ((pad.l + i * bw) / W) * box.width - 60)) + 'px';
    };
    const hide = () => { tip.style.display = 'none'; el.querySelectorAll('.bar.on').forEach((b) => b.classList.remove('on')); };
    el.addEventListener('pointermove', (e) => { const box = el.getBoundingClientRect(); const fx = ((e.clientX - box.left) / box.width) * W; show(Math.min(data.length - 1, Math.max(0, Math.floor((fx - pad.l) / bw)))); });
    el.addEventListener('pointerleave', hide); el.addEventListener('blur', hide);
    el.addEventListener('keydown', (e) => {
      if (e.key === 'ArrowLeft') { show(Math.max(0, k - 1)); e.preventDefault(); }
      else if (e.key === 'ArrowRight') { show(Math.min(data.length - 1, k + 1)); e.preventDefault(); }
      else if (e.key === 'Home') { show(0); e.preventDefault(); } else if (e.key === 'End') { show(data.length - 1); e.preventDefault(); }
    });
  }
  return { html: `<div class="chart-wrap">${svg}</div>`, wire };
}

/** rows: [{label, v, note?}] with v a share (0 to 100) or any positive value. */
export function hbars(rows, { fmt = (v) => `${num(v, 1)}%`, max } = {}) {
  const data = (rows || []).filter((r) => Number.isFinite(r.v));
  if (!data.length) return '';
  const top = max || Math.max(...data.map((r) => r.v)) || 1;
  return `<ul class="hbars">${data.map((r) => `<li><span class="hb-l">${esc(r.label)}</span><span class="hb-track"><span class="hb-fill" style="width:${Math.max(1, (r.v / top) * 100).toFixed(1)}%"></span></span><span class="hb-v">${esc(fmt(r.v))}</span>${r.note ? `<span class="hb-n">${esc(r.note)}</span>` : ''}</li>`).join('')}</ul>`;
}
