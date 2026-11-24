// Figures at a glance (the visual update, 2026-11-11): the small pictures Home and a company's Overview draw from
// figures they already hold, so a reader sees the shape before reading the sentence. Every one carries its own text
// alternative (the figure's one line), states its values as text beside the picture, and never lets colour carry a
// direction alone: a change figure has an arrow and a sign (move()), a bar sits above or below its zero line, a gauge
// has its scale's two ends in words.
//
// Red and green belong to the charts and to the figures that state a direction; gold stays the brand, the one gold
// button, tabs, the level control and the options cone (palette.md). Text in these figures is HTML, not SVG text, so
// it stays at its 13px floor whatever width the figure is drawn at.
import { html, raw } from '../core/dom.js';
import { num, signed, dir, esc, isNum } from '../core/format.js';

export const ARROW = { up: '▲', down: '▼' };

/** A change figure with its arrow and its sign: "▲ +1.27%". `text` is the signed figure as it should read (signed()
 *  already writes + or the minus sign); the arrow is decoration for the eye, the sign is what a screen reader hears. */
export function move(v, text = signed(v), { cls = '' } = {}) {
  const d = dir(v), a = ARROW[d];
  return html`<span class="mv ${d}${cls ? ` ${cls}` : ''}">${a ? html`<span class="mv-a" aria-hidden="true">${a}</span>` : ''}${text}</span>`;
}

/** The same as words, for a figure's text alternative: "up 1.27%", "down 0.50%", "unchanged". */
export const moveWords = (v, text) => (dir(v) === 'up' ? `up ${text}` : dir(v) === 'down' ? `down ${text}` : 'unchanged');

const clamp = (x, a, b) => Math.max(a, Math.min(b, x));

/** A gauge: one reading on a scale with its two ends named. {v, lo, hi, ends: [low words, high words], label}. The
 *  track runs from the down colour to the up colour; the marker and the two end words carry the reading without it. */
export function gauge({ v, lo, hi, ends = ['', ''], label = '' }) {
  if (!isNum(v) || !(hi > lo)) return '';
  const at = clamp(((Number(v) - lo) / (hi - lo)) * 100, 0, 100);
  return html`<div class="gauge" role="img" aria-label="${label || `${num(v, 0)} on a scale from ${num(lo, 0)} to ${num(hi, 0)}`}">
    <span class="gauge-track" aria-hidden="true"><i class="gauge-mark" style="left:${at.toFixed(1)}%"></i></span>
    <span class="gauge-ends" aria-hidden="true"><span>${ends[0]}</span><span>${ends[1]}</span></span></div>`;
}

/** Bars either side of a zero line, one row per part, each with its signed value as text: a score's factors, the
 *  sentiment parts against neutral. rows: [{label, v, text?}]; opts: {max, label, fmt}. Largest first is the caller's. */
export function divBars(rows, { max, label = '', fmt = (v) => signed(v, 1, '') } = {}) {
  const data = (rows || []).filter((r) => isNum(r.v));
  if (!data.length) return '';
  const top = max || Math.max(...data.map((r) => Math.abs(r.v))) || 1;
  return html`<ul class="dbars" aria-label="${label}">${data.map((r) => {
    const w = clamp((Math.abs(r.v) / top) * 50, r.v ? 1.5 : 0, 50), side = r.v > 0 ? 'pos' : r.v < 0 ? 'neg' : 'zero';
    return html`<li><span class="db-l">${r.label}</span><span class="db-track" aria-hidden="true"><i class="db-fill ${side}" style="${r.v >= 0 ? `left:50%` : `right:50%`};width:${w.toFixed(1)}%"></i></span><span class="db-v">${r.text != null ? r.text : fmt(r.v)}</span></li>`;
  })}</ul>`;
}

/** Two or three bars on one scale, each with its value as text: Expected move's priced and typical day, the P/E today
 *  against its usual, institutions and insiders. rows: [{label, v, text, cls}] where cls is 'gold', 'ink' or 'mute'. */
export function pairBars(rows, { max, label = '' } = {}) {
  const data = (rows || []).filter((r) => isNum(r.v));
  if (!data.length) return '';
  const top = max || Math.max(...data.map((r) => r.v)) || 1;
  return html`<ul class="pbars" aria-label="${label}">${data.map((r) => html`<li><span class="pb-l">${r.label}</span><span class="pb-track" aria-hidden="true"><i class="pb-fill ${r.cls || 'gold'}" style="width:${clamp((r.v / top) * 100, 1, 100).toFixed(1)}%"></i></span><span class="pb-v">${r.text}</span></li>`)}</ul>`;
}

/** A donut of the parts of one whole, with the whole in its middle and a legend that states every share as text.
 *  parts: [{label, v}] largest first; opts: {center, sub, label}. The colours are the categorical set, in order. */
const DONUT = ['gold', 'c1', 'c2', 'c4', 'mute'];
export function donut(parts, { center = '', sub = '', label = '' } = {}) {
  const data = (parts || []).filter((p) => isNum(p.v) && p.v > 0);
  const total = data.reduce((a, p) => a + p.v, 0);
  if (data.length < 2 || !(total > 0)) return '';
  const R = 52, C = 2 * Math.PI * R;
  let off = 0;
  const arcs = data.map((p, i) => {
    const len = (p.v / total) * C, gap = data.length > 1 ? Math.min(2, len / 3) : 0;
    const s = `<circle class="dn-arc ${DONUT[i] || 'mute'}" r="${R}" cx="66" cy="66" stroke-dasharray="${(len - gap).toFixed(2)} ${(C - len + gap).toFixed(2)}" stroke-dashoffset="${(-off).toFixed(2)}"/>`;
    off += len;
    return s;
  }).join('');
  const share = (p) => Math.round((p.v / total) * 100);
  const words = label || data.map((p) => `${p.label} ${share(p)}%`).join(', ');
  return html`<div class="donut"><span class="dn-fig"><svg class="dn" viewBox="0 0 132 132" width="132" height="132" role="img" aria-label="${words}"><g transform="rotate(-90 66 66)">${raw(arcs)}</g></svg>
    ${center ? html`<span class="dn-c" aria-hidden="true"><b>${center}</b>${sub ? html`<small>${sub}</small>` : ''}</span>` : ''}</span>
    <ul class="dn-key">${data.map((p, i) => html`<li><i class="sw ${DONUT[i] || 'mute'}" aria-hidden="true"></i><span>${p.label}</span><b>${share(p)}%</b></li>`)}</ul></div>`;
}

export const _test = { clamp, DONUT, esc };
