// Charts for v2: a line/area chart with optional event markers, a forward cone
// (an options-implied range) and data tags; a sparkline; and the exposure
// meter. Drawn as SVG at the container's real width so text stays at its
// specified size. Every chart has a text summary for screen readers and a
// keyboard-readable crosshair.
import { num, shortDate, fullDate, esc, monthName } from '../core/format.js';

let seq = 0;

/**
 * series: [{d: 'YYYY-MM-DD', c: number}]
 * opts: { w, h, label, summary, dp, area, events:[{d, kind, label, detail}],
 *         onEvent(d), future (empty sessions after the last close), cone:{lo, hi, label},
 *         tags:[{i?, text, dir}], focusEnd, noTicks, pad }
 * Returns { html, wire(root) }.
 */
export function lineChart(series, opts = {}) {
  const id = 'ch' + (++seq);
  const W = Math.max(280, Math.round(opts.w || 720)), H = Math.round(opts.h || 240);
  const pad = Object.assign({ t: 14, r: 56, b: 26, l: 0 }, opts.pad || {});
  const pts = series.filter((p) => Number.isFinite(p.c));
  if (pts.length < 2) return { html: '', wire() {} };
  let lo = Math.min(...pts.map((p) => p.c)), hi = Math.max(...pts.map((p) => p.c));
  const cone = opts.cone && Number.isFinite(opts.cone.lo) ? opts.cone : null;
  if (cone) { lo = Math.min(lo, cone.lo); hi = Math.max(hi, cone.hi); }
  const span = hi - lo || 1; lo -= span * 0.06; hi += span * 0.06;
  const slots = pts.length - 1 + (opts.future || 0);
  const X = (i) => pad.l + (i / slots) * (W - pad.l - pad.r);
  const Y = (v) => pad.t + (1 - (v - lo) / (hi - lo)) * (H - pad.t - pad.b);
  const dp = opts.dp == null ? 2 : opts.dp;
  const path = pts.map((p, i) => `${i ? 'L' : 'M'}${X(i).toFixed(1)} ${Y(p.c).toFixed(1)}`).join('');
  const last = pts[pts.length - 1];
  const ticks = [0.1, 0.5, 0.9].map((f) => lo + (hi - lo) * f);
  const index = new Map(pts.map((p, i) => [p.d, i]));
  const at = (iso) => { if (index.has(iso)) return index.get(iso); let b = -1; pts.forEach((p, i) => { if (p.d <= iso) b = i; }); return b; };

  const months = [];
  let prevM = '';
  const step = opts.monthStep || (pts.length > 180 ? 3 : 1);
  pts.forEach((p, i) => {
    const m = p.d.slice(0, 7);
    if (m !== prevM && i > 3 && i < pts.length - 6 && (Number(p.d.slice(5, 7)) - 1) % step === 0) {
      months.push(`<text class="ax" x="${X(i).toFixed(1)}" y="${H - 6}" text-anchor="middle">${monthName(Number(p.d.slice(5, 7)))}</text>`);
    }
    prevM = m;
  });

  const events = (opts.events || []).map((e) => {
    const i = at(e.d); if (i < 0) return '';
    const x = X(i).toFixed(1), y = Y(pts[i].c).toFixed(1);
    const label = `${e.label}, ${fullDate(e.d)}`;
    return `<g class="ev-mark" data-ev="${esc(e.d)}"${opts.onEvent ? ` tabindex="0" role="button" aria-label="${esc(label)}"` : ''}>
      <line class="ev-rule" x1="${x}" x2="${x}" y1="${pad.t}" y2="${H - pad.b}"/><circle class="ev-hit" cx="${x}" cy="${y}" r="22"/>
      <circle class="ev-dot" cx="${x}" cy="${y}" r="4.5"/><text class="ev-lab" x="${x}" y="${H - pad.b + 15}" text-anchor="middle">${esc(e.kind)}</text></g>`;
  }).join('');

  let coneSvg = '';
  if (cone) {
    const x0 = X(pts.length - 1), y0 = Y(last.c), x1 = X(slots), yh = Y(cone.hi), yl = Y(cone.lo);
    coneSvg = `<defs><linearGradient id="${id}-cg" x1="0" x2="1"><stop offset="0" style="stop-color:var(--c-cone-a)"/><stop offset="1" style="stop-color:var(--c-cone-b)"/></linearGradient></defs>
      <g class="cone"><path fill="url(#${id}-cg)" d="M${x0} ${y0}L${x1} ${yh}L${x1} ${yl}Z"/>
      <line class="cone-edge" x1="${x0}" y1="${y0}" x2="${x1}" y2="${yh}"/><line class="cone-edge" x1="${x0}" y1="${y0}" x2="${x1}" y2="${yl}"/>
      <line class="cone-end" x1="${x1}" x2="${x1}" y1="${yh}" y2="${yl}"/>
      <text class="tag" x="${x1 - 6}" y="${yh - 8}" text-anchor="end">${num(cone.hi, 0)}</text>
      <text class="tag" x="${x1 - 6}" y="${yl + 18}" text-anchor="end">${num(cone.lo, 0)}</text>
      ${cone.label ? `<text class="tag tag-k" x="${((x0 + x1) / 2 + 8).toFixed(1)}" y="${((yh + yl) / 2 + 4).toFixed(1)}" text-anchor="middle">${esc(cone.label)}</text>` : ''}</g>`;
  }
  const tags = (opts.tags || []).map((t) => {
    const i = t.i == null ? pts.length - 1 : t.i;
    return `<text class="tag ${t.dir || ''}" x="${(X(i) + (t.dx ?? -12)).toFixed(1)}" y="${(Y(pts[i].c) + (t.dy ?? -14)).toFixed(1)}" text-anchor="${t.anchor || 'end'}">${esc(t.text)}</text>`;
  }).join('');
  const area = opts.area ? `<defs><linearGradient id="${id}-g" x1="0" x2="0" y1="0" y2="1"><stop offset="0" style="stop-color:var(--c-area-top)"/><stop offset="1" style="stop-color:var(--c-area-bottom)"/></linearGradient></defs>
      <path class="area" fill="url(#${id}-g)" d="${path}L${X(pts.length - 1).toFixed(1)} ${H - pad.b}L${X(0).toFixed(1)} ${H - pad.b}Z"/>` : '';
  const first = pts[0];
  const change = last.c - first.c;
  const summary = opts.summary || `${opts.label || 'Chart'}: from ${num(first.c, dp)} on ${fullDate(first.d)} to ${num(last.c, dp)} on ${fullDate(last.d)}, ${change >= 0 ? 'up' : 'down'} ${num(Math.abs(change / first.c * 100), 1)} percent. Low ${num(Math.min(...pts.map((p) => p.c)), dp)}, high ${num(Math.max(...pts.map((p) => p.c)), dp)}.`;

  const svg = `<svg class="chart" id="${id}" viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" role="img" aria-label="${esc(summary)}" tabindex="0">
    ${ticks.map((t) => `<line class="grid" x1="${pad.l}" x2="${W - pad.r}" y1="${Y(t).toFixed(1)}" y2="${Y(t).toFixed(1)}"/>${opts.noTicks ? '' : `<text class="ax" x="${W - pad.r + 6}" y="${(Y(t) + 4).toFixed(1)}">${num(t, dp > 0 && t < 1000 ? 0 : 0)}</text>`}`).join('')}
    ${months.join('')}${area}<path class="line" d="${path}"/>${coneSvg}${events}${tags}
    ${opts.focusEnd ? `<circle class="focus-ring" cx="${X(pts.length - 1)}" cy="${Y(last.c)}" r="10"/>` : ''}
    <circle class="end" cx="${X(pts.length - 1)}" cy="${Y(last.c)}" r="3.5"/>
    <g class="xh" style="display:none"><line class="xh-v" y1="${pad.t}" y2="${H - pad.b}"/><circle class="xh-dot" r="4"/></g>
  </svg><div class="chart-tip" aria-hidden="true" style="display:none"></div>`;

  function wire(root) {
    const el = root.querySelector('#' + id); if (!el) return;
    const tip = el.nextElementSibling, xh = el.querySelector('.xh');
    let k = pts.length - 1;
    const show = (i) => {
      k = i;
      const p = pts[i], x = X(i), y = Y(p.c);
      xh.style.display = '';
      xh.querySelector('.xh-v').setAttribute('x1', x); xh.querySelector('.xh-v').setAttribute('x2', x);
      xh.querySelector('.xh-dot').setAttribute('cx', x); xh.querySelector('.xh-dot').setAttribute('cy', y);
      const ev = (opts.events || []).find((e) => at(e.d) === i);
      tip.style.display = '';
      tip.innerHTML = `<b>${num(p.c, dp)}</b> <span>${fullDate(p.d)}</span>${ev ? `<em>${esc(ev.label)}${ev.detail ? ', ' + esc(ev.detail) : ''}</em>` : ''}`;
      const box = el.getBoundingClientRect();
      tip.style.left = Math.min(box.width - 170, Math.max(0, (x / W) * box.width - 70)) + 'px';
    };
    const hide = () => { xh.style.display = 'none'; tip.style.display = 'none'; };
    el.addEventListener('pointermove', (e) => {
      const box = el.getBoundingClientRect();
      const fx = ((e.clientX - box.left) / box.width) * W;
      const i = Math.min(pts.length - 1, Math.max(0, Math.round(((fx - pad.l) / (W - pad.l - pad.r)) * slots)));
      show(i);
    });
    el.addEventListener('pointerleave', hide);
    el.addEventListener('blur', hide);
    el.addEventListener('keydown', (e) => {
      if (e.target !== el) return;
      const jump = e.shiftKey ? 20 : 1;
      if (e.key === 'ArrowLeft') { show(Math.max(0, k - jump)); e.preventDefault(); }
      else if (e.key === 'ArrowRight') { show(Math.min(pts.length - 1, k + jump)); e.preventDefault(); }
      else if (e.key === 'Home') { show(0); e.preventDefault(); }
      else if (e.key === 'End') { show(pts.length - 1); e.preventDefault(); }
    });
    if (opts.onEvent) {
      el.querySelectorAll('.ev-mark').forEach((g) => {
        g.addEventListener('click', () => opts.onEvent(g.dataset.ev, g));
        g.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); e.stopPropagation(); opts.onEvent(g.dataset.ev, g); } });
      });
    }
  }
  return { html: `<div class="chart-wrap">${svg}</div>`, wire };
}

export function spark(values, label = '') {
  const v = (values || []).filter(Number.isFinite);
  if (v.length < 2) return '';
  const W = 112, H = 32, lo = Math.min(...v), hi = Math.max(...v), s = hi - lo || 1;
  const d = v.map((x, i) => `${i ? 'L' : 'M'}${((i / (v.length - 1)) * W).toFixed(1)} ${(2 + (1 - (x - lo) / s) * (H - 4)).toFixed(1)}`).join('');
  const up = v[v.length - 1] >= v[0];
  return `<svg class="spark ${up ? 'up' : 'down'}" viewBox="0 0 ${W} ${H}" ${label ? `role="img" aria-label="${esc(label)}"` : 'aria-hidden="true"'}><path d="${d}"/></svg>`;
}

/** Where a price sits against a fair value range, read like a light meter. */
export function meter({ lo, mid, hi, price, w = 260, showMid = false }) {
  if (![lo, hi, price].every(Number.isFinite)) return '';
  const W = w, H = 62, l = 6, r = W - 6;
  const min = Math.floor(Math.min(lo, price) * 0.9 / 10) * 10, max = Math.ceil(Math.max(hi, price) * 1.06 / 10) * 10;
  const X = (v) => l + (v - min) / (max - min) * (r - l);
  const ticks = [];
  for (let i = 0; i <= 24; i++) { const x = l + i * (r - l) / 24; ticks.push(`<line class="tk${i % 6 === 0 ? ' major' : ''}" x1="${x.toFixed(1)}" x2="${x.toFixed(1)}" y1="38" y2="${i % 6 === 0 ? 48 : 44}"/>`); }
  return `<svg class="meter" viewBox="0 0 ${W} ${H}" width="${W}" role="img" aria-label="Price ${num(price)} against an estimated fair value range of ${num(lo, 0)} to ${num(hi, 0)}">
    <rect class="fair" x="${X(lo).toFixed(1)}" y="24" width="${(X(hi) - X(lo)).toFixed(1)}" height="14" rx="3"/>
    <line class="edge" x1="${X(lo).toFixed(1)}" x2="${X(lo).toFixed(1)}" y1="22" y2="40"/><line class="edge" x1="${X(hi).toFixed(1)}" x2="${X(hi).toFixed(1)}" y1="22" y2="40"/>
    ${ticks.join('')}<path class="mark" d="M${(X(price) - 6).toFixed(1)} 12 L${(X(price) + 6).toFixed(1)} 12 L${X(price).toFixed(1)} 21 Z"/>
    <text class="px" x="${Math.min(r, X(price)).toFixed(1)}" y="8" text-anchor="${X(price) > W - 40 ? 'end' : 'middle'}">${num(price, 0)}</text>
    <text x="${X(lo).toFixed(1)}" y="60" text-anchor="middle">${num(lo, 0)}</text><text x="${X(hi).toFixed(1)}" y="60" text-anchor="middle">${num(hi, 0)}</text>
    ${showMid && Number.isFinite(mid) ? `<text x="${X(mid).toFixed(1)}" y="60" text-anchor="middle">fair ${num(mid, 0)}</text>` : ''}</svg>`;
}

/** Mount charts into .chart-slot[data-chart] elements at their real width; redraw on resize. */
const slots = new Set();
export function mountCharts(root, makers) {
  root.querySelectorAll('.chart-slot[data-chart]').forEach((el) => {
    const make = makers[el.dataset.chart]; if (!make) return;
    const draw = () => {
      const w = Math.max(280, Math.round(el.clientWidth || 0));
      if (el._w === w && el._drawn) return;
      el._w = w;
      const out = make(w);
      if (!out) return;
      el.innerHTML = typeof out === 'string' ? out : out.html;
      el._drawn = true;
      if (out.wire) out.wire(el);
    };
    el._draw = draw; slots.add(el); draw();
  });
}
let rt;
window.addEventListener('resize', () => {
  clearTimeout(rt);
  rt = setTimeout(() => slots.forEach((el) => { if (!document.contains(el)) slots.delete(el); else el._draw(); }), 140);
});
