// A line chart over a numeric x axis (price), for payoff curves and the
// gamma profile: several named series, a zero line, vertical markers (spot,
// breakevens, flip) and a keyboard-readable crosshair. Drawn at real width.
import { num, esc } from '../core/format.js';

let seq = 0;

/**
 * series: [{name, xs, ys, cls}]  (cls: 'main' | 'alt' | 'faint')
 * opts: {w, h, label, xlo, xhi, markers: [{x, text, cls}], dots: [{x, y, text}],
 *        yfmt(v), xfmt(x), fill (shade main above/below zero), summary}
 */
export function xyChart(series, opts = {}) {
  const id = 'xy' + (++seq);
  const W = Math.max(280, Math.round(opts.w || 640)), H = Math.round(opts.h || 260);
  const pad = Object.assign({ t: 16, r: 14, b: 28, l: 62 }, opts.pad || {});
  let yfmt = opts.yfmt, xfmt = opts.xfmt;   // defaults below take the decimals each axis's range needs
  const S = series.map((s) => {
    const pts = s.xs.map((x, i) => [Number(x), Number(s.ys[i])]).filter(([x, y]) => Number.isFinite(x) && Number.isFinite(y)
      && (opts.xlo == null || x >= opts.xlo) && (opts.xhi == null || x <= opts.xhi));
    return Object.assign({}, s, { pts });
  }).filter((s) => s.pts.length > 1);
  if (!S.length) return { html: '', wire() {} };
  const allX = S.flatMap((s) => s.pts.map((p) => p[0])), allY = S.flatMap((s) => s.pts.map((p) => p[1]));
  const x0 = opts.xlo ?? Math.min(...allX), x1 = opts.xhi ?? Math.max(...allX);
  let y0 = Math.min(0, ...allY), y1 = Math.max(0, ...allY);
  const sp = (y1 - y0) || 1; y0 -= sp * 0.06; y1 += sp * 0.06;
  // Enough decimals that neighbouring ticks differ: a delta axis (0 to 1) printed "0 / 0 / 1" (2026-10-19).
  const dpFor = (gap) => (gap >= 20 ? 0 : gap >= 2 ? 1 : gap >= 0.2 ? 2 : 3);
  if (!yfmt) { const d = dpFor((y1 - y0) * 0.4); yfmt = (v) => num(v, d); }
  if (!xfmt) { const d = dpFor((x1 - x0) * 0.25); xfmt = (x) => num(x, d); }
  const X = (x) => pad.l + ((x - x0) / ((x1 - x0) || 1)) * (W - pad.l - pad.r);
  const Y = (y) => pad.t + (1 - (y - y0) / ((y1 - y0) || 1)) * (H - pad.t - pad.b);
  const path = (pts) => pts.map(([x, y], i) => `${i ? 'L' : 'M'}${X(x).toFixed(1)} ${Y(y).toFixed(1)}`).join('');
  const main = S[0];
  let fill = '';
  if (opts.fill) {
    const z = Y(0);
    fill = `<defs><clipPath id="${id}-up"><rect x="0" y="0" width="${W}" height="${z}"/></clipPath><clipPath id="${id}-dn"><rect x="0" y="${z}" width="${W}" height="${H - z}"/></clipPath></defs>
      <path class="fill-up" clip-path="url(#${id}-up)" d="${path(main.pts)}L${X(main.pts[main.pts.length - 1][0]).toFixed(1)} ${z}L${X(main.pts[0][0]).toFixed(1)} ${z}Z"/>
      <path class="fill-dn" clip-path="url(#${id}-dn)" d="${path(main.pts)}L${X(main.pts[main.pts.length - 1][0]).toFixed(1)} ${z}L${X(main.pts[0][0]).toFixed(1)} ${z}Z"/>`;
  }
  const yt = [y0 + (y1 - y0) * 0.1, (y0 + y1) / 2, y0 + (y1 - y0) * 0.9];
  const xt = [0.08, 0.3, 0.5, 0.7, 0.92].map((f) => x0 + (x1 - x0) * f);
  const markers = (opts.markers || []).filter((m) => Number.isFinite(m.x) && m.x >= x0 && m.x <= x1).map((m) => `<line class="mk ${m.cls || ''}" x1="${X(m.x).toFixed(1)}" x2="${X(m.x).toFixed(1)}" y1="${pad.t}" y2="${H - pad.b}"/>${m.text ? `<text class="mk-t" x="${X(m.x).toFixed(1)}" y="${pad.t - 4}" text-anchor="middle">${esc(m.text)}</text>` : ''}`).join('');
  const dots = (opts.dots || []).filter((d) => Number.isFinite(d.x) && d.x >= x0 && d.x <= x1).map((d) => `<circle class="dot" cx="${X(d.x).toFixed(1)}" cy="${Y(d.y || 0).toFixed(1)}" r="4.5"/>`).join('');
  const summary = opts.summary || `${opts.label || 'Chart'} from ${xfmt(x0)} to ${xfmt(x1)}.`;
  const svg = `<svg class="xy" id="${id}" viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" role="img" aria-label="${esc(summary)}" tabindex="0">
    ${yt.map((t) => `<line class="grid" x1="${pad.l}" x2="${W - pad.r}" y1="${Y(t).toFixed(1)}" y2="${Y(t).toFixed(1)}"/><text class="ax" x="${pad.l - 8}" y="${(Y(t) + 4).toFixed(1)}" text-anchor="end">${esc(yfmt(t))}</text>`).join('')}
    ${xt.map((t) => `<text class="ax" x="${X(t).toFixed(1)}" y="${H - 8}" text-anchor="middle">${esc(xfmt(t))}</text>`).join('')}
    <line class="zero" x1="${pad.l}" x2="${W - pad.r}" y1="${Y(0).toFixed(1)}" y2="${Y(0).toFixed(1)}"/>
    ${fill}${S.slice().reverse().map((s) => `<path class="ln ${s.cls || 'main'}" d="${path(s.pts)}"/>`).join('')}${markers}${dots}
    <g class="xh" style="display:none"><line class="xh-v" y1="${pad.t}" y2="${H - pad.b}"/></g></svg>
    <div class="chart-tip" aria-hidden="true" style="display:none"></div>`;
  function wire(root) {
    const el = root.querySelector('#' + id); if (!el) return;
    const tip = el.nextElementSibling, xh = el.querySelector('.xh');
    const xs = main.pts.map((p) => p[0]);
    let k = xs.findIndex((x) => x >= ((opts.markers || [])[0] || {}).x) ; if (k < 0) k = Math.floor(xs.length / 2);
    const valAt = (s, x) => { const p = s.pts; let j = p.findIndex((q) => q[0] >= x); if (j <= 0) return p[Math.max(0, j)][1]; const [ax, ay] = p[j - 1], [bx, by] = p[j]; return ay + ((x - ax) / ((bx - ax) || 1)) * (by - ay); };
    const show = (i) => {
      k = Math.max(0, Math.min(xs.length - 1, i)); const x = xs[k];
      xh.style.display = ''; const l = xh.querySelector('line'); l.setAttribute('x1', X(x)); l.setAttribute('x2', X(x));
      tip.style.display = '';
      tip.innerHTML = `<b>${esc(xfmt(x))}</b>${S.map((s) => `<em>${esc(s.name)}: ${esc(yfmt(valAt(s, x)))}</em>`).join('')}`;
      const box = el.getBoundingClientRect();
      tip.style.left = Math.min(box.width - 190, Math.max(0, (X(x) / W) * box.width - 80)) + 'px';
    };
    const hide = () => { xh.style.display = 'none'; tip.style.display = 'none'; };
    el.addEventListener('pointermove', (e) => { const box = el.getBoundingClientRect(); const fx = x0 + (((e.clientX - box.left) / box.width) * W - pad.l) / (W - pad.l - pad.r) * (x1 - x0); let best = 0; xs.forEach((x, j) => { if (Math.abs(x - fx) < Math.abs(xs[best] - fx)) best = j; }); show(best); });
    el.addEventListener('pointerleave', hide); el.addEventListener('blur', hide);
    el.addEventListener('keydown', (e) => {
      const j = e.shiftKey ? 10 : 1;
      if (e.key === 'ArrowLeft') { show(k - j); e.preventDefault(); } else if (e.key === 'ArrowRight') { show(k + j); e.preventDefault(); }
      else if (e.key === 'Home') { show(0); e.preventDefault(); } else if (e.key === 'End') { show(xs.length - 1); e.preventDefault(); }
    });
  }
  return { html: `<div class="chart-wrap">${svg}</div>`, wire };
}
