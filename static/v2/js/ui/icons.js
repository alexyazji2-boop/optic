// Line icons, 24px grid, stroked with currentColor. Decorative unless a label
// is passed, because every icon in v2 sits beside visible text.
import { raw } from '../core/dom.js';

const P = {
  home: '<path d="M4 11 12 4l8 7v9h-5v-6H9v6H4z"/>',
  dossier: '<path d="M6 3h9l4 4v14H6z"/><path d="M14 3v5h5M9 12h7M9 16h5"/>',
  compare: '<path d="M8 4v16M16 4v16M4 8h8M12 16h8"/>',
  markets: '<path d="M3 18l5-6 4 3 7-9"/><path d="M15 6h4v4"/>',
  discover: '<circle cx="11" cy="11" r="6.5"/><path d="m16 16 4.5 4.5"/>',
  positions: '<path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/>',
  brokerage: '<path d="M3 10 12 4l9 6M5 10v8M9.5 10v8M14.5 10v8M19 10v8M3 20h18"/>',
  watchlist: '<path d="M2.6 12C5.6 6.6 8.6 4.6 12 4.6s6.4 2 9.4 7.4c-3 5.4-6 7.4-9.4 7.4S5.6 17.4 2.6 12Z"/><circle cx="12" cy="12" r="2.8"/>',
  reports: '<path d="M5 3h10l4 4v14H5z"/><path d="M9 13h6M9 17h4M9 9h2"/>',
  settings: '<circle cx="12" cy="12" r="3"/><path d="M12 2.5v3M12 18.5v3M2.5 12h3M18.5 12h3M5.3 5.3l2.1 2.1M16.6 16.6l2.1 2.1M5.3 18.7l2.1-2.1M16.6 7.4l2.1-2.1"/>',
  more: '<circle cx="5" cy="12" r="1.3"/><circle cx="12" cy="12" r="1.3"/><circle cx="19" cy="12" r="1.3"/>',
  search: '<circle cx="11" cy="11" r="6.5"/><path d="m16 16 4.5 4.5"/>',
  close: '<path d="M6 6l12 12M18 6 6 18"/>',
  chev: '<path d="m9 6 6 6-6 6"/>',
  arrow: '<path d="M5 12h14M13 6l6 6-6 6"/>',
  out: '<path d="M14 4h6v6M20 4l-9 9M18 14v6H4V6h6"/>',
  up: '<path d="m6 15 6-6 6 6"/>',
  down: '<path d="m6 9 6 6 6-6"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  bell: '<path d="M6 16V11a6 6 0 1 1 12 0v5l2 2H4z"/><path d="M10 20a2 2 0 0 0 4 0"/>',
  user: '<circle cx="12" cy="8" r="4"/><path d="M4 21c1.5-4 4.5-6 8-6s6.5 2 8 6"/>',
  milo: '<path d="M4 5h16v11H9l-5 4z"/><path d="M8 10h8M8 13h5"/>',
};

export function icon(name, label = '') {
  const a = label ? `role="img" aria-label="${label}"` : 'aria-hidden="true"';
  return raw(`<svg viewBox="0 0 24 24" ${a} class="ic ic-${name}">${P[name] || ''}</svg>`);
}

// The Optic mark, from static/index.html (the brand's eye and line).
export const brandMark = () => raw(`<svg viewBox="0 0 32 32" aria-hidden="true">
  <path d="M2.6 16C6.3 8.9 10.9 5.4 16 5.4S25.7 8.9 29.4 16C25.7 23.1 21.1 26.6 16 26.6S6.3 23.1 2.6 16Z" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linejoin="round" opacity="0.7"/>
  <path d="M7.4 20.2 11.4 15.6 14.6 17.8 18.6 11.6 21.6 14 23.9 11.4" fill="none" stroke="var(--c-gold-light)" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"/>
  <circle cx="23.9" cy="11.4" r="1.5" fill="var(--c-gold-light)"/></svg>`);
