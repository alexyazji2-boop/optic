// Small DOM helpers shared by every v2 page: query, html templating with
// escaping, focus management, and one polite live region for announcements.
import { esc } from './format.js';

export const $ = (sel, root = document) => root.querySelector(sel);
export const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

// Tagged template: interpolated values are escaped unless wrapped in raw().
const RAW = Symbol('raw');
export const raw = (s) => ({ [RAW]: true, s: String(s == null ? '' : s) });
// A value that is the whole of an href or src is checked as an address: a
// server-supplied link (a headline, a filing, a source) with a javascript: or
// data: scheme becomes "#". Escaping stops markup, not a scheme.
const URL_ATTR = /\b(?:href|src|action|formaction|xlink:href)\s*=\s*["']$/i;
export function safeUrl(u) {
  const s = String(u == null ? '' : u).trim();
  if (!s) return '#';
  if (/^(?:https?:|mailto:)/i.test(s)) return s;
  if (s.startsWith('//')) return '#';
  if (/^[a-z][a-z0-9+.-]*:/i.test(s.replace(/[\u0000-\u0020]/g, ''))) return '#';
  return s;
}
export function html(strings, ...vals) {
  let out = '';
  strings.forEach((str, i) => {
    out += str;
    if (i < vals.length) {
      const v = vals[i];
      out += URL_ATTR.test(str) && (typeof v === 'string' || typeof v === 'number') ? esc(safeUrl(v)) : flat(v);
    }
  });
  return raw(out);
}
// Booleans print as "true"/"false" so aria-pressed="${on}" is valid; write
// conditionals as ternaries, never `cond && html`.
function flat(v) {
  if (v == null) return '';
  if (typeof v === 'boolean') return String(v);
  if (Array.isArray(v)) return v.map(flat).join('');
  if (typeof v === 'object' && v[RAW]) return v.s;
  return esc(v);
}
// A redraw used to close any menu the reader had open: in iOS Safari a Dossier's ⋯ menu closed under the
// finger when the page's data arrived and redrew the header (2026-10-19). A ⋯ or Indicators menu
// (`details.menu`) that the redraw draws again is reopened.
const menuKey = (d) => { const s = d.querySelector(':scope > summary'); return s ? `${d.className}|${s.getAttribute('aria-label') || s.textContent.trim()}` : null; };
export const render = (el, tpl) => {
  const open = el.querySelectorAll ? [...el.querySelectorAll('details.menu[open]')].map(menuKey).filter(Boolean) : [];
  el.innerHTML = flat(tpl);
  if (open.length) el.querySelectorAll('details.menu').forEach((d) => { if (open.includes(menuKey(d))) d.open = true; });
  return el;
};
export const toString = (tpl) => flat(tpl);

// Focusable children, in tab order, that are actually visible.
export function focusables(root) {
  return $$('a[href],button:not([disabled]),input:not([disabled]),select,textarea,[tabindex]:not([tabindex="-1"])', root)
    .filter((el) => el.getClientRects().length > 0 && !el.closest('[hidden]'));
}

// Keep Tab inside root; returns an uninstall function.
export function trapFocus(root, onEscape) {
  const onKey = (e) => {
    if (e.key === 'Escape' && onEscape) { e.preventDefault(); onEscape(); return; }
    if (e.key !== 'Tab') return;
    const f = focusables(root);
    if (!f.length) return;
    const first = f[0], last = f[f.length - 1];
    if (e.shiftKey && document.activeElement === first) { last.focus(); e.preventDefault(); }
    else if (!e.shiftKey && document.activeElement === last) { first.focus(); e.preventDefault(); }
  };
  root.addEventListener('keydown', onKey);
  return () => root.removeEventListener('keydown', onKey);
}

// One shared polite live region for status messages screen readers should hear.
let live;
export function announce(msg) {
  if (!live) {
    live = document.createElement('p');
    live.className = 'sr';
    live.setAttribute('role', 'status');
    live.setAttribute('aria-live', 'polite');
    document.body.appendChild(live);
  }
  live.textContent = '';
  setTimeout(() => { live.textContent = msg; }, 30);
}

/** The system's reduced-motion setting, or Settings' Motion: Reduce (html[data-motion], core/prefs.js). */
export const reducedMotion = () => document.documentElement.getAttribute('data-motion') === 'reduce' || !!(window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches);
export const isPhone = () => matchMedia('(max-width: 860px)').matches;
