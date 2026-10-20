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
  return `<ul class="hbars">${data.map((r) => `<li><span class="hb-l">${esc(r.label)}</span><span class="hb-track"><span class="hb-fill" style="width:${Math.max(1, (r.v / top) * 100).toFixed(1)}%"></span></span><span class="hb-v">${esc(r.text != null ? r.text : fmt(r.v))}</span>${r.note ? `<span class="hb-n">${esc(r.note)}</span>` : ''}</li>`).join('')}</ul>`;
}

/* ---------- figures across periods (Financials, Earnings, Milo; 2026-10-20) ----------
   One scale, axis, tooltip and keyboard for the four below. Magnitudes stand on a zero baseline; a missing figure
   is left as a gap and read out as "Not reported", never drawn as zero; the reading follows the pointer or the
   arrow keys, a tap on a phone, and stays inside the chart. Series colours are classes (s1, s2, s3) that each
   metric keeps everywhere (ui/metrics in pages); an estimate is hollow, so it never depends on colour. */
const fin = (v) => typeof v === 'number' && Number.isFinite(v);
/** Round axis values covering lo..hi: about n steps of 1, 2 or 5 times a power of ten, through zero. */
export function niceTicks(lo, hi, n = 4) {
  if (!fin(lo) || !fin(hi)) return [0];
  if (lo === hi) { hi = lo === 0 ? 1 : lo + Math.abs(lo) * 0.1; }
  const raw = (hi - lo) / n, p = 10 ** Math.floor(Math.log10(raw)), f = raw / p;
  const step = (f < 1.5 ? 1 : f < 3 ? 2 : f < 7 ? 5 : 10) * p;
  const out = [];
  for (let v = Math.floor(lo / step) * step; v <= hi + step * 1e-9; v += step) out.push(Math.abs(v) < step * 1e-9 ? 0 : Number(v.toPrecision(12)));
  if (out[out.length - 1] < hi) out.push(Number((out[out.length - 1] + step).toPrecision(12)));
  return out;
}
function frame(groups, opts, lo, hi, H, W, pad) {
  let ticks = niceTicks(lo, hi, opts.tickCount || 4);
  const y0 = Math.min(lo, ticks[0]), y1 = Math.max(hi, ticks[ticks.length - 1]);
  const fmt = opts.axisFmt || opts.fmt || ((v) => compact(v));
  // every axis label different: where the format rounds two steps together ("5.1B", "5.1B"), every other tick goes
  const dup = (ts) => new Set(ts.map((t) => String(fmt(t)))).size < ts.length;
  while (ticks.length > 2 && dup(ticks)) { const z = ticks.indexOf(0); ticks = ticks.filter((t, i) => (i - (z >= 0 ? z : 0)) % 2 === 0); }
  // the axis is as wide as its widest label ("−TWD 1.00T" was cut to "WD 1.00T")
  pad.l = Math.max(pad.l, Math.max(...ticks.map((t) => String(fmt(t)).length)) * 6.6 + 10);
  const gw = (W - pad.l - pad.r) / Math.max(1, groups.length);
  // a label too wide for its column takes two lines, and the line under it (beat, miss) moves down to make room
  const wraps = groups.some((g) => String(g.x).length * 6.4 > gw - 6 && String(g.x).includes(' '));
  if (wraps && !pad.wrapped) { pad.b += 13; pad.wrapped = true; }
  const Y = (v) => pad.t + (1 - (v - y0) / ((y1 - y0) || 1)) * (H - pad.t - pad.b);
  const grid = ticks.map((t) => `<line class="${t === 0 ? 'zero' : 'grid'}" x1="${pad.l}" x2="${W - pad.r}" y1="${Y(t).toFixed(1)}" y2="${Y(t).toFixed(1)}"/><text class="ax" x="${pad.l - 6}" y="${(Y(t) + 4).toFixed(1)}" text-anchor="end">${esc(fmt(t))}</text>`).join('');
  // fewer labels on a narrow chart rather than smaller ones
  const step = Math.max(1, Math.ceil(groups.length / Math.max(2, Math.floor((W - pad.l - pad.r) / (opts.labelWidth || 58)))));
  const keep = (i) => (groups.length - 1 - i) % step === 0;   // the newest period always keeps its label
  const tw = (t) => String(t).length * 6.4;   // about the width of a 12 px label
  const xText = (t, x, y) => {
    const str = String(t);
    if (tw(str) <= gw - 6 || !str.includes(' ')) return `<text class="ax" x="${x}" y="${y}" text-anchor="middle">${esc(str)}</text>`;
    // too wide for its column: two lines, broken at the space nearest the middle
    const sp = [...str].map((ch, k) => (ch === ' ' ? k : -1)).filter((k) => k > 0), mid = str.length / 2;
    const at = sp.reduce((a, k) => (Math.abs(k - mid) < Math.abs(a - mid) ? k : a), sp[0]);
    return `<text class="ax" x="${x}" y="${y}" text-anchor="middle"><tspan x="${x}">${esc(str.slice(0, at))}</tspan><tspan x="${x}" dy="13">${esc(str.slice(at + 1))}</tspan></text>`;
  };
  const subY = H - pad.b + (wraps ? 43 : 30);
  const xl = groups.map((g, i) => (keep(i) ? `${xText(g.x, (pad.l + gw * (i + 0.5)).toFixed(1), H - pad.b + 15)}${g.sub ? `<text class="ax ax-sub ${esc(g.subCls || '')}" x="${(pad.l + gw * (i + 0.5)).toFixed(1)}" y="${subY}" text-anchor="middle">${esc(g.sub)}</text>` : ''}` : '')).join('');
  const refs = (opts.refs || []).filter((r) => fin(r.v)).map((r) => `<line class="ref" x1="${pad.l}" x2="${W - pad.r}" y1="${Y(r.v).toFixed(1)}" y2="${Y(r.v).toFixed(1)}"/><text class="ref-t" x="${pad.l + 4}" y="${(Y(r.v) - 5).toFixed(1)}" text-anchor="start">${esc(r.text || '')}</text>`).join('');
  return { Y, gw, grid, xl, refs };
}
// value labels that would overlap are left out (the tooltip and the table still carry them): first come, first kept
function placeLabels(cands, bounds) {
  const kept = [];
  cands.forEach((c) => {
    const w = String(c.text).length * 6.6;
    if (bounds) c.x = Math.min(Math.max(c.x, bounds.l + w / 2 + 2), bounds.r - w / 2);
    const box = { l: c.x - w / 2, r: c.x + w / 2, t: c.y - 11, b: c.y + 2 };
    if (kept.some((k) => box.l < k.r && box.r > k.l && box.t < k.b && box.b > k.t)) return;
    kept.push(Object.assign(box, c));
  });
  return kept.map((c) => `<text class="vlab${c.cls ? ' ' + c.cls : ''}" x="${c.x.toFixed(1)}" y="${c.y.toFixed(1)}" text-anchor="middle">${esc(c.text)}</text>`).join('');
}
function wireGroups(id, n, gw, padL, W, tipHTML) {
  return function wire(root) {
    const el = root.querySelector('#' + id); if (!el) return;
    const tip = el.nextElementSibling;
    let k = n - 1;
    const show = (i) => {
      k = i;
      el.querySelectorAll('[data-g]').forEach((b) => b.classList.toggle('on', Number(b.dataset.g) === i));
      tip.style.display = ''; tip.innerHTML = tipHTML(i);
      const box = el.getBoundingClientRect(), tw = tip.offsetWidth || 180;
      tip.style.left = `${Math.min(Math.max(0, box.width - tw), Math.max(0, ((padL + gw * (i + 0.5)) / W) * box.width - tw / 2))}px`;
    };
    const hide = () => { tip.style.display = 'none'; el.querySelectorAll('[data-g].on').forEach((b) => b.classList.remove('on')); };
    const at = (e) => { const box = el.getBoundingClientRect(); const fx = ((e.clientX - box.left) / box.width) * W; return Math.min(n - 1, Math.max(0, Math.floor((fx - padL) / gw))); };
    el.addEventListener('pointermove', (e) => { if (e.pointerType !== 'touch') show(at(e)); });
    el.addEventListener('pointerdown', (e) => { if (e.pointerType === 'touch') show(at(e)); });   // a tap reads a period
    el.addEventListener('pointerleave', (e) => { if (e.pointerType !== 'touch') hide(); });
    el.addEventListener('blur', hide);
    el.addEventListener('keydown', (e) => {
      const to = { ArrowLeft: k - 1, ArrowRight: k + 1, Home: 0, End: n - 1 }[e.key];
      if (to === undefined) { if (e.key === 'Escape') hide(); return; }
      show(Math.min(n - 1, Math.max(0, to))); e.preventDefault();
    });
  };
}
const notReported = (s) => s.missingText || 'Not reported';
// periods at either end with no figure in any series are not drawn (an empty column is not an observation); a gap
// between reported periods stays a gap
function trimEnds(groups, series) {
  const has = groups.map((_, i) => series.some((s) => fin((s.values || [])[i])));
  const a = has.indexOf(true), b = has.lastIndexOf(true);
  if (a < 0) return { groups: [], series };
  return { groups: groups.slice(a, b + 1), series: series.map((s) => Object.assign({}, s, { values: (s.values || []).slice(a, b + 1) })) };
}

/**
 * Several measures across the same periods, side by side, from zero.
 * groups: [{x, sub?, subCls?}] oldest first; series: [{name, cls, values, hollow?}] values aligned to groups
 * opts: {w, h, label, fmt(v), axisFmt(v), refs: [{v, text}], valueLabels: 'last' | 'all' | 'none', summary, note(i)}
 */
export function groupedBars(groupsIn, seriesIn, opts = {}) {
  const id = 'gb' + (++seq);
  const { groups, series } = trimEnds(groupsIn || [], seriesIn || []);
  const S = (series || []).filter((s) => (s.values || []).some(fin));
  if (!(groups || []).length || !S.length) return { html: '', wire() {} };
  const W = Math.max(280, Math.round(opts.w || 600)), H = Math.round(opts.h || 220);
  const pad = Object.assign({ t: 18, r: 10, b: groups.some((g) => g.sub) ? 40 : 26, l: 54 }, opts.pad || {});
  const fmt = opts.fmt || ((v) => compact(v));
  const all = S.flatMap((s) => s.values.filter(fin)).concat((opts.refs || []).map((r) => r.v).filter(fin));
  const lab = opts.valueLabels || (groups.length * S.length <= 8 ? 'all' : 'last');
  let lo = Math.min(0, ...all), hi = Math.max(0, ...all);
  // room past the longest bars for their labels, so a label never sits on the axis's numbers or the period names
  if (lab !== 'none') { const span = (hi - lo) || 1; if (lo < 0) lo -= span * 0.1; if (hi > 0) hi += span * 0.06; }
  const { Y, gw, grid, xl, refs } = frame(groups, opts, lo, hi, H, W, pad);
  const inner = Math.min(gw * 0.76, S.length * 30), bw = inner / S.length;
  let bars = '', labels = '';
  const cands = [];
  groups.forEach((g, i) => {
    S.forEach((s, j) => {
      const v = s.values[i], x = pad.l + gw * i + (gw - inner) / 2 + j * bw + 1;
      if (!fin(v)) { bars += `<line class="gap-mark" data-g="${i}" x1="${x.toFixed(1)}" x2="${(x + bw - 2).toFixed(1)}" y1="${Y(0).toFixed(1)}" y2="${Y(0).toFixed(1)}"/>`; return; }
      const y = Math.min(Y(v), Y(0)), h = Math.max(1, Math.abs(Y(v) - Y(0)));
      bars += `<rect class="gbar ${s.cls || 's1'}${s.hollow ? ' hollow' : ''}" data-g="${i}" x="${x.toFixed(1)}" y="${y.toFixed(1)}" width="${Math.max(1, bw - 2).toFixed(1)}" height="${h.toFixed(1)}" rx="1.5"/>`;
      if (lab === 'all' || (lab === 'last' && i === groups.length - 1)) cands.push({ x: x + (bw - 2) / 2, y: v >= 0 ? Y(v) - 5 : Y(v) + 13, text: fmt(v) });
    });
  });
  labels = placeLabels(cands, { l: pad.l, r: W - pad.r });
  const n = groups.length, last = n - 1;
  const summary = opts.summary || `${opts.label || 'Bars'}, ${groups[0].x} to ${groups[last].x}. ${groups[last].x}: ${S.map((s) => `${s.name} ${fin(s.values[last]) ? fmt(s.values[last]) : notReported(s)}`).join(', ')}.`;
  const svg = `<svg class="bars gbars" id="${id}" viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" role="img" aria-label="${esc(summary)}" tabindex="0">${grid}${refs}${bars}${labels}${xl}</svg><div class="chart-tip" aria-hidden="true" style="display:none"></div>`;
  const tip = (i) => `<b>${esc(groups[i].x)}</b>${S.map((s) => `<span class="tip-row"><i class="sw ${s.cls || 's1'}${s.hollow ? ' hollow' : ''}"></i>${esc(s.name)} <b>${fin(s.values[i]) ? esc(fmt(s.values[i])) : notReported(s)}</b></span>`).join('')}${opts.note ? `<em>${esc(opts.note(i) || '')}</em>` : ''}`;
  return { html: `<div class="chart-wrap">${svg}</div>`, wire: wireGroups(id, n, gw, pad.l, W, tip) };
}

/** Measures across periods as lines with a point at each period (margins: percentages, on their own scale).
 * A gap in a series breaks its line rather than joining across it. */
export function periodLines(groupsIn, seriesIn, opts = {}) {
  const id = 'pl' + (++seq);
  const { groups, series } = trimEnds(groupsIn || [], seriesIn || []);
  const S = (series || []).filter((s) => (s.values || []).some(fin));
  if (!(groups || []).length || !S.length) return { html: '', wire() {} };
  const W = Math.max(280, Math.round(opts.w || 600)), H = Math.round(opts.h || 200);
  const pad = Object.assign({ t: 16, r: 12, b: 26, l: 46 }, opts.pad || {});
  const fmt = opts.fmt || ((v) => num(v, 1));
  const all = S.flatMap((s) => s.values.filter(fin));
  let lo = opts.zero === false ? Math.min(...all) : Math.min(0, ...all), hi = Math.max(...all);
  // off zero, the scale still spans at least 5% of the values, so a count that barely moved looks it
  if (opts.zero === false) { const need = Math.abs(hi) * (opts.minSpan || 0.05); if (hi - lo < need) { const mid = (hi + lo) / 2; lo = mid - need / 2; hi = mid + need / 2; } }
  const { Y, gw, grid, xl } = frame(groups, opts, lo, hi, H, W, pad);
  const X = (i) => pad.l + gw * (i + 0.5);
  let paths = '', dots = '', ends = '';
  S.forEach((s) => {
    let d = '', pen = false;
    s.values.forEach((v, i) => { if (!fin(v)) { pen = false; return; } d += `${pen ? 'L' : 'M'}${X(i).toFixed(1)} ${Y(v).toFixed(1)}`; pen = true; dots += `<circle class="pdot ${s.cls || 's1'}" data-g="${i}" cx="${X(i).toFixed(1)}" cy="${Y(v).toFixed(1)}" r="4"/>`; });
    paths += `<path class="pline ${s.cls || 's1'}" d="${d}"/>`;
  });
  // the newest value of each line, named at its end when there is room (direct labels; the key carries the rest)
  const lastVals = S.map((s) => ({ s, i: s.values.map(fin).lastIndexOf(true) })).filter((o) => o.i >= 0);
  const ys = lastVals.map(({ s, i }) => ({ s, i, y: Y(s.values[i]) - 9 })).sort((a, b) => a.y - b.y);
  for (let k = 1; k < ys.length; k++) if (ys[k].y - ys[k - 1].y < 13) ys[k].y = ys[k - 1].y + 13;
  ys.forEach(({ s, i, y }) => { ends += `<text class="vlab ${s.cls || 's1'}-t" x="${(X(i) - 8).toFixed(1)}" y="${y.toFixed(1)}" text-anchor="end">${esc(fmt(s.values[i]))}</text>`; });
  const n = groups.length, last = n - 1;
  const summary = opts.summary || `${opts.label || 'Lines'}, ${groups[0].x} to ${groups[last].x}. ${groups[last].x}: ${S.map((s) => `${s.name} ${fin(s.values[last]) ? fmt(s.values[last]) : 'not reported'}`).join(', ')}.`;
  const svg = `<svg class="bars plines" id="${id}" viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" role="img" aria-label="${esc(summary)}" tabindex="0">${grid}${paths}${dots}${ends}${xl}</svg><div class="chart-tip" aria-hidden="true" style="display:none"></div>`;
  const tip = (i) => `<b>${esc(groups[i].x)}</b>${S.map((s) => `<span class="tip-row"><i class="sw ${s.cls || 's1'}"></i>${esc(s.name)} <b>${fin(s.values[i]) ? esc(fmt(s.values[i])) : 'Not reported'}</b></span>`).join('')}`;
  return { html: `<div class="chart-wrap">${svg}</div>`, wire: wireGroups(id, n, gw, pad.l, W, tip) };
}

/** A bridge from one figure to another through what changes it, only for figures that reconcile (the caller
 * checks): steps [{x, v, kind: 'total' | 'step'}], each step drawn from where the last one ended. */
export function bridgeBars(steps, opts = {}) {
  const id = 'br' + (++seq);
  const data = (steps || []).filter((s) => fin(s.v));
  if (data.length < 2) return { html: '', wire() {} };
  const W = Math.max(280, Math.round(opts.w || 420)), H = Math.round(opts.h || 190);
  const pad = Object.assign({ t: 18, r: 10, b: 26, l: 54 }, opts.pad || {});
  const fmt = opts.fmt || ((v) => compact(v));
  let run = 0; const spans = data.map((s) => { const a = s.kind === 'total' ? 0 : run, b = s.kind === 'total' ? s.v : run + s.v; run = b; return [a, b]; });
  const vals = spans.flat();
  const { Y, gw, grid, xl } = frame(data, opts, Math.min(0, ...vals), Math.max(0, ...vals), H, W, pad);
  const bw = Math.min(gw * 0.56, 64);
  let bars = '', labels = '', joins = '';
  spans.forEach(([a, b], i) => {
    const x = pad.l + gw * i + (gw - bw) / 2, s = data[i];
    bars += `<rect class="gbar ${s.kind === 'total' ? (s.cls || 's1') : (s.v < 0 ? 'step-out' : 'step-in')}" data-g="${i}" x="${x.toFixed(1)}" y="${Math.min(Y(a), Y(b)).toFixed(1)}" width="${bw.toFixed(1)}" height="${Math.max(1, Math.abs(Y(a) - Y(b))).toFixed(1)}" rx="1.5"/>`;
    labels += `<text class="vlab" x="${(x + bw / 2).toFixed(1)}" y="${(Math.min(Y(a), Y(b)) - 5).toFixed(1)}" text-anchor="middle">${esc(s.kind === 'total' ? fmt(s.v) : `${s.v < 0 ? '−' : '+'}${fmt(Math.abs(s.v))}`)}</text>`;
    if (i < spans.length - 1) joins += `<line class="join" x1="${(x + bw).toFixed(1)}" x2="${(x + gw).toFixed(1)}" y1="${Y(b).toFixed(1)}" y2="${Y(b).toFixed(1)}"/>`;
  });
  const summary = opts.summary || `${opts.label || 'Bridge'}: ${data.map((s) => `${s.x} ${fmt(s.v)}`).join(', ')}.`;
  const svg = `<svg class="bars bbars" id="${id}" viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" role="img" aria-label="${esc(summary)}" tabindex="0">${grid}${joins}${bars}${labels}${xl}</svg><div class="chart-tip" aria-hidden="true" style="display:none"></div>`;
  const tip = (i) => `<b>${esc(data[i].x)}</b> <span>${esc(fmt(data[i].v))}</span>${opts.note ? `<em>${esc(opts.note(i) || '')}</em>` : ''}`;
  return { html: `<div class="chart-wrap">${svg}</div>`, wire: wireGroups(id, data.length, gw, pad.l, W, tip) };
}

/** The parts of a whole across periods, stacked from zero, each bar's total above it; for parts at or above zero
 * only (the caller checks) and never scaled to 100. parts: [{name, cls, values}] largest first. */
export function stackedBars(groupsIn, partsIn, opts = {}) {
  const id = 'st' + (++seq);
  const { groups, series: parts } = trimEnds(groupsIn || [], partsIn || []);
  const P = (parts || []).filter((p) => (p.values || []).some(fin));
  if (!(groups || []).length || !P.length) return { html: '', wire() {} };
  const W = Math.max(280, Math.round(opts.w || 600)), H = Math.round(opts.h || 220);
  const pad = Object.assign({ t: 20, r: 10, b: 26, l: 54 }, opts.pad || {});
  const fmt = opts.fmt || ((v) => compact(v));
  const totals = groups.map((_, i) => P.reduce((a, p) => a + (fin(p.values[i]) ? p.values[i] : 0), 0));
  const { Y, gw, grid, xl } = frame(groups, opts, 0, Math.max(...totals), H, W, pad);
  const bw = Math.min(gw * 0.6, 56);
  let bars = '', labels = '';
  groups.forEach((g, i) => {
    let base = 0; const x = pad.l + gw * i + (gw - bw) / 2;
    P.forEach((p) => { const v = p.values[i]; if (!fin(v) || v <= 0) return; bars += `<rect class="gbar ${p.cls || 's1'}" data-g="${i}" x="${x.toFixed(1)}" y="${Y(base + v).toFixed(1)}" width="${bw.toFixed(1)}" height="${Math.max(1, Y(base) - Y(base + v) - 1).toFixed(1)}"/>`; base += v; });
    if (totals[i] > 0 && (groups.length <= 6 || i === groups.length - 1)) labels += `<text class="vlab" x="${(x + bw / 2).toFixed(1)}" y="${(Y(totals[i]) - 5).toFixed(1)}" text-anchor="middle">${esc(fmt(totals[i]))}</text>`;
  });
  const last = groups.length - 1;
  const summary = opts.summary || `${opts.label || 'Composition'}, ${groups[0].x} to ${groups[last].x}. ${groups[last].x}: ${P.map((p) => `${p.name} ${fin(p.values[last]) ? fmt(p.values[last]) : 'not reported'}`).join(', ')}; total ${fmt(totals[last])}.`;
  const svg = `<svg class="bars sbars" id="${id}" viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" role="img" aria-label="${esc(summary)}" tabindex="0">${grid}${bars}${labels}${xl}</svg><div class="chart-tip" aria-hidden="true" style="display:none"></div>`;
  const tip = (i) => `<b>${esc(groups[i].x)}</b>${P.map((p) => `<span class="tip-row"><i class="sw ${p.cls || 's1'}"></i>${esc(p.name)} <b>${fin(p.values[i]) ? esc(fmt(p.values[i])) : 'Not reported'}</b>${fin(p.values[i]) && totals[i] > 0 ? ` <small>${num((p.values[i] / totals[i]) * 100, 0)}%</small>` : ''}</span>`).join('')}<span class="tip-row">Total <b>${esc(fmt(totals[i]))}</b></span>`;
  return { html: `<div class="chart-wrap">${svg}</div>`, wire: wireGroups(id, groups.length, gw, pad.l, W, tip) };
}
