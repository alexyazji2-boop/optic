// The Chart page's chrome, from the classic Charting tab (C12): the reader's chart colours, whether the legend
// is open, and full screen. ui/pricechart.js draws the legend and the navigator; this keeps what is remembered,
// in the classic keys and formats, so a choice made in either app holds in the other.
import { html } from '../core/dom.js';
import { icon } from '../ui/icons.js';

/* ---------------- colours ---------------- */
// {up, down, line}, each a CSS colour; a slot left out follows the theme, so a reader who never chose one
// keeps the light and dark themes' own colours and one who chose orange gets orange in both (classic CHART_COLORS_KEY)
export const COLOURS_KEY = 'optic.chart.colors.v1';
export const SLOTS = [['up', 'Candle up'], ['down', 'Candle down'], ['line', 'Line']];
// the line's default follows the view, green up and red down as the classic line does; its swatch shows the up one
const DEFAULT = { up: '--c-pos', down: '--c-neg', line: '--c-pos' };
// the theme's own colours, then the classic chart's series colours (their dark values) under the classic picker's names
const PRESETS = [['Green', '--c-pos'], ['Red', '--c-neg'], ['Gold', '--c-gold'], ['Blue', '#4a93ea'], ['Orange', '#d95926'], ['Teal', '#199e70'], ['Amber', '#c98500'], ['Pink', '#d55181'], ['Violet', '#9085e9'], ['Ink', '--c-ink'], ['Grey', '--c-ink-3']];

export const isColour = (v) => typeof v === 'string' && !!v.trim() && !(typeof CSS !== 'undefined' && CSS.supports && !CSS.supports('color', v));
export function readColours() {
  const out = {};
  try {
    const raw = JSON.parse(localStorage.getItem(COLOURS_KEY) || '{}');
    // the three slots only, and only colours: anything else would reach an SVG fill and fail there silently
    if (raw && typeof raw === 'object') SLOTS.forEach(([k]) => { if (isColour(raw[k])) out[k] = raw[k]; });
  } catch (e) { /* private mode */ }
  return out;
}
// read again before writing, so a slot the other app changed meanwhile is kept; nothing chosen removes the key, as Reset does there
export function setColour(slot, value) {
  const c = readColours();
  if (value && isColour(value)) c[slot] = value; else delete c[slot];
  try { if (Object.keys(c).length) localStorage.setItem(COLOURS_KEY, JSON.stringify(c)); else localStorage.removeItem(COLOURS_KEY); } catch (e) { /* private mode */ }
  return c;
}
export function resetColours() { try { localStorage.removeItem(COLOURS_KEY); } catch (e) { /* private mode */ } return {}; }

// what the plot draws with: custom properties on the chart page, read by the .pc rules in pages.css
export function applyColours(el, c) {
  if (!el) return;
  [['--pc-up', c.up], ['--pc-down', c.down], ['--pc-line', c.line]].forEach(([p, v]) => { if (v) el.style.setProperty(p, v); else el.style.removeProperty(p); });
  if (c.line) el.style.setProperty('--pc-area', `color-mix(in srgb, ${c.line} 22%, transparent)`); else el.style.removeProperty('--pc-area');
}

const token = (v) => (v.startsWith('--') ? getComputedStyle(document.documentElement).getPropertyValue(v).trim() : v);
function rgbOf(v) {
  const p = document.createElement('span'); p.style.color = v; document.body.appendChild(p);
  const got = getComputedStyle(p).color; p.remove();
  const n = (got.match(/[\d.]+/g) || []).slice(0, 3).map(Number);
  return n.length === 3 ? n : null;
}
// <input type="color"> takes #rrggbb only, and shows black for anything else
export function toHex(v) {
  const n = isColour(v) ? rgbOf(v) : null;
  return n ? `#${n.map((x) => Math.max(0, Math.min(255, Math.round(x))).toString(16).padStart(2, '0')).join('')}` : '#000000';
}
const lum = (n) => { const [r, g, b] = n.map((x) => { const s = x / 255; return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4; }); return 0.2126 * r + 0.7152 * g + 0.0722 * b; };
// the colour behind the plot: the first ancestor with a background of its own
export function surface(el) {
  for (let n = el; n && n.nodeType === 1; n = n.parentElement) {
    const bg = getComputedStyle(n).backgroundColor;
    if (bg && !/^(transparent|rgba\(0, 0, 0, 0\))$/.test(bg)) return bg;
  }
  return token('--c-plane');
}
// 3:1, the contrast a mark needs to read as a shape (a candle body is a graphical object, not text)
export function contrast(v, bg) {
  const a = rgbOf(v), b = rgbOf(bg);
  if (!a || !b) return null;
  const x = lum(a), y = lum(b);
  return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05);
}
export const warnText = (r) => `Hard to see against the chart background at ${r.toFixed(1)}:1. A mark needs about 3:1 to read as a shape.`;

// The menu's rows: for each slot its colour now, the presets, any colour from the wheel, and Default once one is chosen.
export function colourRows(c, bg) {
  const ink = rgbOf(token('--c-ink'));
  const presets = PRESETS.map(([name, v]) => [name === 'Ink' ? (ink && lum(ink) > 0.5 ? 'White' : 'Black') : name, toHex(token(v))]);
  return html`${SLOTS.map(([slot, label]) => {
    const chosen = !!c[slot], now = toHex(c[slot] || token(DEFAULT[slot])), r = contrast(now, bg), poor = r !== null && r < 3;
    return html`<div class="cc-row" role="group" aria-labelledby="cc-${slot}">
      <div class="cc-head"><span class="cc-l" id="cc-${slot}">${label}</span><span class="cc-now" data-v2-cc-now="${slot}" style="background:${now}" title="${chosen ? `Your colour, ${now}` : `The theme's colour, ${now}`}"></span>${chosen ? html`<button type="button" class="btn btn-sm" data-v2-cc-clear="${slot}" title="Back to the theme's colour">Default</button>` : ''}</div>
      <div class="cc-sw">${presets.map(([name, hex]) => html`<button type="button" class="cc-swatch" style="--sw:${hex}" aria-pressed="${now === hex}" data-v2-cc="${slot}" data-v2-cc-v="${hex}" aria-label="${label}: ${name}" title="${name}"></button>`)}<label class="cc-wheel" title="Any colour">${icon('plus')}<input type="color" data-v2-cc-pick="${slot}" value="${now}" aria-label="${label}: any colour"></label></div>
      <p class="cc-warn" data-v2-cc-warn="${slot}" ${poor ? '' : 'hidden'}>${poor ? warnText(r) : ''}</p>
    </div>`;
  })}<button type="button" class="btn btn-sm cc-reset" data-v2-cc-reset ${Object.keys(c).length ? '' : 'disabled'}>Reset all to the theme</button>`;
}
// while the wheel is dragged: the row's swatch and its contrast note, in place (the menu is not redrawn under the pointer)
export function liveRow(input, bg) {
  const row = input.closest('.cc-row'); if (!row) return;
  const now = row.querySelector('[data-v2-cc-now]'); if (now) now.style.background = input.value;
  const w = row.querySelector('[data-v2-cc-warn]'); if (!w) return;
  const r = contrast(input.value, bg), poor = r !== null && r < 3;
  w.hidden = !poor; w.textContent = poor ? warnText(r) : '';
}

/* ---------------- legend ---------------- */
// 'open' or 'closed', folded unless opened (classic WS_LEGEND_KEY)
export const LEGEND_KEY = 'optic.chart.legend.v1';
export function legendOpen() { try { return localStorage.getItem(LEGEND_KEY) === 'open'; } catch (e) { return false; } }
export function saveLegend(open) { try { localStorage.setItem(LEGEND_KEY, open ? 'open' : 'closed'); } catch (e) { /* private mode */ } }

/* ---------------- full screen ---------------- */
// Two mechanisms, as in the classic chart. The class does the work (pages.css html.ch-max: the rail, top bar,
// phone bar, footer and tabs go, the chart page takes the window) and cannot be refused. The browser's own full
// screen is asked for on top, on the root so the toasts and the screen-reader messages stay in it; a refusal
// (an iPhone, a frame, a policy) is a normal answer, since the class has already given the chart the window.
const MAX = 'ch-max';
export const isMax = () => document.documentElement.classList.contains(MAX);
export const nativeFull = () => document.fullscreenElement || document.webkitFullscreenElement || null;
export function setMax(on, native = true) {
  document.documentElement.classList.toggle(MAX, !!on);
  if (!native) return;
  const root = document.documentElement;
  try {
    if (on && !nativeFull()) { const req = root.requestFullscreen || root.webkitRequestFullscreen; const p = req && req.call(root); if (p && p.catch) p.catch(() => {}); }
    if (!on && nativeFull()) { const ex = document.exitFullscreen || document.webkitExitFullscreen; const p = ex && ex.call(document); if (p && p.catch) p.catch(() => {}); }
  } catch (e) { /* older engines throw instead of rejecting */ }
}
export const maxTitle = (on) => (on ? 'Back to the rest of Optic. Escape does this too.' : 'Give the chart the whole window. Its tools, widgets and drawings come with it.');
export const maxButton = () => html`<button type="button" class="ch-tool" data-v2-ch-max aria-pressed="${isMax()}" aria-label="Full screen" title="${maxTitle(isMax())}">${icon(isMax() ? 'shrink' : 'expand')}</button>`;
